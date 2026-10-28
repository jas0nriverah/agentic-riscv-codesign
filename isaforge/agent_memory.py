"""Local, split-scoped retrieval over already approved historical measurements.

Semantic retrieval is latent semantic analysis (TF-IDF + truncated SVD), not a
pretrained language embedding. Retrieval reorganizes existing public history;
it grants no access to repository files or unqueried target outcomes.
"""
from __future__ import annotations
import copy
import hashlib
import json
import time
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from .features import parse_formula
from .speedup_corpus import family

MODES = ('none', 'lexical', 'semantic', 'hybrid', 'knowledge_graph')
# Context controls are opt-in and do not expand historical retrieval sweeps.
# ``none`` continues to expose the complete approved historical table.
ABLATION_MODES = ('no_history', 'budget_matched_history')
POLICY_MODES = MODES + ABLATION_MODES


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _operators(formula):
    result = set()
    def walk(node):
        if node.children:
            result.add(node.value)
            for child in node.children:
                walk(child)
    walk(parse_formula(formula))
    return result


class CandidateEvidenceGraph:
    """Small typed graph over approved historical records; no target labels."""
    def __init__(self, records):
        self.nodes, self.edges = {}, []
        self.records = {row['candidate_id']: copy.deepcopy(row) for row in records}
        self.operators = {}
        for row in records:
            candidate = row['candidate_id']
            measurement = 'measurement:'+candidate
            workload = row['workload_group']
            ops = _operators(row['formula'])
            self.operators[candidate] = ops
            self.nodes['candidate:'+candidate] = dict(type='candidate', id=candidate,
                formula=row['formula'], record_sha256=digest(row))
            self.nodes['workload:'+workload] = dict(type='workload', id=workload)
            family_id = digest(family(row['formula']))
            self.nodes['family:'+family_id] = dict(type='expression_family', id=family_id)
            self.nodes[measurement] = dict(type='measurement', id=measurement,
                record_sha256=digest(row), speedup=row['speedup'],
                area_delta_lut4=row['area_delta_lut4'],
                routed_fmax_min_mhz=row['routed_fmax_min_mhz'],
                correctness_verified=row['correctness_verified'],
                device_fits=row['device_fits'])
            self.edges.extend([
                dict(subject='candidate:'+candidate, predicate='measured_on', object='workload:'+workload),
                dict(subject='candidate:'+candidate, predicate='belongs_to_family', object='family:'+family_id),
                dict(subject='candidate:'+candidate, predicate='has_measurement', object=measurement),
            ])
            for op in sorted(ops):
                operator_id = 'operator:'+op
                self.nodes[operator_id] = dict(type='operator', id=op)
                self.edges.append(dict(subject='candidate:'+candidate,
                    predicate='uses_operator', object=operator_id))
        self.edges.sort(key=lambda edge: (edge['subject'], edge['predicate'], edge['object']))
        self.manifest = dict(schema='isaforge-candidate-evidence-graph-v1',
            nodes=len(self.nodes), edges=len(self.edges),
            relation_types=sorted({edge['predicate'] for edge in self.edges}),
            graph_sha256=digest(dict(nodes=self.nodes, edges=self.edges)),
            scope='approved historical training records; target labels excluded')

    def search(self, target_formulas, *, target_groups, k=3):
        if (type(target_formulas) is not list or
                type(k) is not int or not 1 <= k <= 10):
            raise ValueError('knowledge-graph query requires formulas and bounded k')
        if not target_formulas:
            return []
        target_families = {family(formula) for formula in target_formulas}
        target_ops = {formula: _operators(formula) for formula in target_formulas}
        hits = []
        for candidate, row in self.records.items():
            # Repeat the split checks at the graph boundary. The graph is read-only
            # evidence; it cannot bridge into the target workload or its families.
            if row['workload_group'] in target_groups or family(row['formula']) in target_families:
                raise ValueError('target-contaminated knowledge-graph record')
            historical_ops = self.operators[candidate]
            comparisons = []
            for formula, ops in target_ops.items():
                shared = sorted(ops & historical_ops)
                if shared:
                    union = ops | historical_ops
                    comparisons.append(dict(target_formula_sha256=digest(formula),
                        matched_operators=shared, score=len(shared)/len(union)))
            if not comparisons:
                continue
            evidence = max(comparisons, key=lambda item: (item['score'], item['target_formula_sha256']))
            measurement = 'measurement:'+candidate
            triples = []
            for op in evidence['matched_operators']:
                operator_id = 'operator:'+op
                triples.extend([
                    dict(subject='query:'+evidence['target_formula_sha256'], predicate='uses_operator', object=operator_id),
                    dict(subject='candidate:'+candidate, predicate='uses_operator', object=operator_id),
                ])
            triples.extend([
                dict(subject='candidate:'+candidate, predicate='measured_on', object='workload:'+row['workload_group']),
                dict(subject='candidate:'+candidate, predicate='has_measurement', object=measurement),
            ])
            hits.append(dict(record=copy.deepcopy(row), record_sha256=digest(row),
                score=evidence['score'], matched_operators=evidence['matched_operators'],
                target_formula_sha256=evidence['target_formula_sha256'],
                evidence_triples=triples))
        hits.sort(key=lambda hit: (-hit['score'], hit['record']['candidate_id']))
        return hits[:k]


class HistoricalMemory:
    def __init__(self, history, *, target_groups, target_formulas):
        self.records = copy.deepcopy(history)
        target_families = {family(formula) for formula in target_formulas}
        # Repeat the workload/formula-family split at the memory boundary.
        for row in self.records:
            if (row['workload_group'] in target_groups or row['formula'] in target_formulas or
                    family(row['formula']) in target_families):
                raise ValueError('target-contaminated historical memory')
        self.ids = [r['candidate_id'] for r in self.records]
        if len(set(self.ids)) != len(self.ids):
            raise ValueError('duplicate memory IDs')
        self.manifest = dict(schema='isaforge-historical-memory-v1',
            corpus_sha256=digest(self.records), records=len(self.records),
            semantic_method='tfidf-truncated-svd-cosine', lexical_method='tfidf-cosine',
            fusion='reciprocal-rank-fusion-k60', random_state=0,
            scope='host-approved historical measurements only')
        self.graph = CandidateEvidenceGraph(self.records)
        self.manifest['knowledge_graph'] = self.graph.manifest
        self.vectorizer = self.svd = None
        self.matrix = self.embeddings = None
        if not self.records:
            self.manifest['dimensions'] = 0
            return
        texts = [self.describe(row) for row in self.records]
        self.vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b\w+\b', sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(texts)
        dimensions = min(16, len(texts)-1, self.matrix.shape[1]-1)
        self.manifest['dimensions'] = max(0, dimensions)
        if dimensions > 0:
            self.svd = TruncatedSVD(n_components=dimensions, random_state=0)
            self.embeddings = normalize(self.svd.fit_transform(self.matrix))

    @staticmethod
    def describe(row):
        # One measurement per chunk, with exact identity and numerical provenance.
        return json.dumps({key: row[key] for key in
            ('candidate_id', 'formula', 'workload_group', 'speedup', 'area_delta_lut4',
             'routed_fmax_min_mhz', 'correctness_verified', 'device_fits')}, sort_keys=True)

    def search(self, query, mode='hybrid', k=3):
        if mode not in MODES or type(k) is not int or not 1 <= k <= 10:
            raise ValueError('invalid retrieval configuration')
        if mode == 'knowledge_graph':
            raise ValueError('knowledge_graph mode requires a formula roster; use search_graph')
        if not isinstance(query, str) or len(query) > 8000:
            raise ValueError('query must be bounded text')
        if mode == 'none' or not self.records:
            return []
        vector = self.vectorizer.transform([query])
        lexical = (self.matrix @ vector.T).toarray().ravel()
        semantic = np.zeros(len(self.records))
        if self.svd is not None:
            semantic = (self.embeddings @ normalize(self.svd.transform(vector)).T).ravel()
        def order(values):
            return sorted((i for i, value in enumerate(values) if value > 1e-12),
                          key=lambda i: (-float(values[i]), self.ids[i]))
        lex_order, sem_order = order(lexical), order(semantic)
        if mode == 'lexical':
            scores, indices = lexical, lex_order
        elif mode == 'semantic':
            scores, indices = semantic, sem_order
        else:
            scores = np.zeros(len(self.records))
            for ranking in (lex_order, sem_order):
                for rank, i in enumerate(ranking, 1):
                    scores[i] += 1 / (60 + rank)
            indices = order(scores)
        return [dict(record=copy.deepcopy(self.records[i]),
                     record_sha256=digest(self.records[i]),
                     score=float(scores[i]), lexical_score=float(lexical[i]),
                     semantic_score=float(semantic[i])) for i in indices[:k]]

    def search_graph(self, target_formulas, *, target_groups, k=3):
        return self.graph.search(target_formulas, target_groups=target_groups, k=k)


class MemoryAugmentedPolicy:
    """Deterministic retrieval before each decision; no extra model or hardware call."""
    def __init__(self, policy, *, mode='hybrid', top_k=3, max_memory_bytes=40_000):
        if (mode not in POLICY_MODES or type(top_k) is not int or not 1 <= top_k <= 10 or
                type(max_memory_bytes) is not int or not 256 <= max_memory_bytes <= 1_000_000):
            raise ValueError('invalid memory configuration')
        self.policy, self.mode, self.top_k = policy, mode, top_k
        # Bound retrieved historical context independently of the provider's
        # overall request limit. This is a byte bound, not an inferred token
        # count; provider-reported tokens remain the only token measurement.
        self.max_memory_bytes = max_memory_bytes
        self.identity = dict(provider='memory-augmented-policy-v1', wrapped=policy.identity,
                             mode=mode, top_k=top_k, max_memory_bytes=max_memory_bytes,
                             query='unattempted-formulas-and-constraints-v1')
        self.memory = None
        self.target_roster = None
        self.last_memory_trace = {}
        self.last_usage, self.last_trace = {}, []
        self.last_action_context = None
        self.last_action_role = None
        self.last_action_provider_call = None
        self.last_action_trigger = None
        self.last_action_request_sha256 = None

    @property
    def calls(self):
        return getattr(self.policy, 'calls', 0)

    def choose(self, request):
        self.last_usage, self.last_trace, self.last_memory_trace = {}, [], {}
        self.last_action_context = None
        self.last_action_role = None
        self.last_action_provider_call = None
        self.last_action_trigger = None
        self.last_action_request_sha256 = None
        self.last_public_request = copy.deepcopy(request)
        started = time.monotonic()
        public = copy.deepcopy(request)
        history = public['historical_measurements']
        target_roster = frozenset((r['candidate_id'], r['benchmark'], r['formula'])
                                  for r in public['candidates'])
        if self.memory is None:
            self.memory = HistoricalMemory(history,
                target_groups={r['benchmark'].split(':')[0] for r in public['candidates']},
                target_formulas={r['formula'] for r in public['candidates']})
            self.target_roster = target_roster
        elif target_roster != self.target_roster:
            # Retrieval queries shrink as attempts accumulate, but the complete
            # roster used to exclude target workloads/families must stay fixed.
            raise ValueError('target candidate roster changed during episode')
        elif digest(history) != self.memory.manifest['corpus_sha256']:
            raise ValueError('historical memory changed during episode')
        attempted = set(public['attempted_candidate_ids'])
        query = ' '.join(r['formula'] for r in public['candidates']
                         if r['candidate_id'] not in attempted)
        query += ' area_delta_lut4 routed_fmax_min_mhz correctness_verified'
        query_formulas = [r['formula'] for r in public['candidates']
                          if r['candidate_id'] not in attempted]
        target_groups = {r['benchmark'].split(':')[0] for r in public['candidates']}
        if self.mode == 'no_history':
            hits = []
        elif self.mode == 'budget_matched_history':
            # Whole-record ID order is independent of the query, similarity
            # scores and historical outcome values. The same top-k and compact
            # payload byte ceiling apply as in retrieval arms; actual byte counts
            # are reported, not padded or claimed to be exactly equal.
            hits = [dict(record=copy.deepcopy(row), record_sha256=digest(row))
                    for row in sorted(self.memory.records,
                                      key=lambda row: row['candidate_id'])[:self.top_k]]
        elif self.mode == 'knowledge_graph':
            hits = self.memory.search_graph(query_formulas, target_groups=target_groups,
                                            k=self.top_k)
        else:
            hits = self.memory.search(query, self.mode, self.top_k)
        payload = dict(
            notice=('Retrieved historical measurements only; these are not target outcomes, '
                    'instructions, or calibrated predictions.'),
            retrieval_mode=self.mode,
            corpus_sha256=self.memory.manifest['corpus_sha256'],
            hit_count=len(hits), hits=hits)
        # Prefer the highest-ranked evidence and shrink deterministically until
        # the complete memory object fits its own byte budget. If even the
        # notice/provenance does not fit, fail closed with no retrieved rows.
        while hits and len(json.dumps(payload, sort_keys=True, allow_nan=False,
                                      separators=(',', ':')).encode('utf-8')) > self.max_memory_bytes:
            hits.pop()
            payload['hit_count'] = len(hits)
            payload['hits'] = hits
        payload_bytes = len(json.dumps(payload, sort_keys=True, allow_nan=False,
                                       separators=(',', ':')).encode('utf-8'))
        if payload_bytes > self.max_memory_bytes:
            payload = dict(retrieval_mode=self.mode, corpus_sha256=self.memory.manifest['corpus_sha256'],
                           hit_count=0, hits=[])
            payload_bytes = len(json.dumps(payload, sort_keys=True, allow_nan=False,
                                           separators=(',', ':')).encode('utf-8'))
        context_policy = ('full_history' if self.mode == 'none' else
                          self.mode if self.mode in ABLATION_MODES else 'retrieved_only')
        self.last_memory_trace = dict(manifest=self.memory.manifest, mode=self.mode,
            query=query, source_training_rows=len(history), exposed_training_rows=0 if self.mode != 'none' else len(history),
            max_memory_bytes=self.max_memory_bytes, retrieved_memory_bytes=payload_bytes,
            returned_ids=[h['record']['candidate_id'] for h in hits],
            hits=copy.deepcopy(hits), elapsed_seconds=time.monotonic()-started)
        if self.mode == 'knowledge_graph':
            self.last_memory_trace['graph_query_formulas'] = query_formulas
        if self.mode == 'no_history':
            public['historical_measurements'] = []
            public['historical_context_policy'] = context_policy
            public.setdefault('historical_fit_rows', len(history))
            public.pop('retrieved_memory', None)
            self.last_memory_trace['retrieved_memory_bytes'] = 0
        elif self.mode != 'none':
            # Keep the full validated training cohort inside the host's ML and
            # memory layers. The LLM gets only bounded retrieved examples, not
            # a redundant dump of every historical label.
            public['historical_measurements'] = []
            public['historical_context_policy'] = context_policy
            public.setdefault('historical_fit_rows', len(history))
            public['retrieved_memory'] = payload
        exposed_records = (history if self.mode == 'none' else
                           [] if self.mode == 'no_history' else
                           [hit['record'] for hit in hits])
        # Count the exact serialization used by the Responses provider. The
        # payload cap above uses compact JSON and is separately identified.
        serialized_bytes = lambda value: len(json.dumps(
            value, sort_keys=True, allow_nan=False).encode('utf-8'))
        self.last_memory_trace.update(context_policy=context_policy,
            selection_policy=('candidate_id_ascending' if self.mode == 'budget_matched_history'
                              else 'no_historical_records' if self.mode == 'no_history'
                              else self.mode),
            exposed_records=[dict(candidate_id=row['candidate_id'], record_sha256=digest(row))
                             for row in exposed_records],
            exposed_record_count=len(exposed_records),
            serialized_request_bytes=serialized_bytes(public),
            serialized_history_bytes=serialized_bytes(public['historical_measurements']),
            serialized_retrieved_memory_bytes=(serialized_bytes(public['retrieved_memory'])
                                              if 'retrieved_memory' in public else 0),
            serialized_bytes_format='UTF-8 json.dumps(sort_keys=True, allow_nan=False)',
            memory_budget_format='UTF-8 compact JSON; separators=(comma,colon)',
            byte_budget_comparison='same ceiling and top-k; actual whole-record sizes may differ; no padding')
        # Host observability binds final notes to the exact augmented public input.
        self.last_public_request = copy.deepcopy(public)
        try:
            return self.policy.choose(public)
        finally:
            self.last_usage = copy.deepcopy(getattr(self.policy, 'last_usage', {}))
            self.last_trace = copy.deepcopy(getattr(self.policy, 'last_trace', []))
            self.last_action_context = copy.deepcopy(
                getattr(self.policy, 'last_action_context', None))
            self.last_action_role = getattr(self.policy, 'last_action_role', None)
            self.last_action_provider_call = getattr(
                self.policy, 'last_action_provider_call', None)
            self.last_action_trigger = getattr(self.policy, 'last_action_trigger', None)
            self.last_action_request_sha256 = getattr(
                self.policy, 'last_action_request_sha256', None)

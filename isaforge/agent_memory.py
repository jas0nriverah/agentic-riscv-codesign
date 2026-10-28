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

MODES = ('none', 'lexical', 'semantic', 'hybrid')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class HistoricalMemory:
    def __init__(self, history, *, target_groups, target_formulas):
        self.records = copy.deepcopy(history)
        # Defense in depth. Host performs the fuller expression-family split.
        for row in self.records:
            if row['workload_group'] in target_groups or row['formula'] in target_formulas:
                raise ValueError('target-contaminated historical memory')
        self.ids = [r['candidate_id'] for r in self.records]
        if len(set(self.ids)) != len(self.ids):
            raise ValueError('duplicate memory IDs')
        self.manifest = dict(schema='isaforge-historical-memory-v1',
            corpus_sha256=digest(self.records), records=len(self.records),
            semantic_method='tfidf-truncated-svd-cosine', lexical_method='tfidf-cosine',
            fusion='reciprocal-rank-fusion-k60', random_state=0,
            scope='host-approved historical measurements only')
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


class MemoryAugmentedPolicy:
    """Deterministic retrieval before each decision; no extra model or hardware call."""
    def __init__(self, policy, *, mode='hybrid', top_k=3):
        if mode not in MODES or type(top_k) is not int or not 1 <= top_k <= 10:
            raise ValueError('invalid memory configuration')
        self.policy, self.mode, self.top_k = policy, mode, top_k
        self.identity = dict(provider='memory-augmented-policy-v1', wrapped=policy.identity,
                             mode=mode, top_k=top_k, query='unattempted-formulas-and-constraints-v1')
        self.memory = None
        self.last_memory_trace = {}
        self.last_usage, self.last_trace = {}, []

    @property
    def calls(self):
        return getattr(self.policy, 'calls', 0)

    def choose(self, request):
        self.last_usage, self.last_trace, self.last_memory_trace = {}, [], {}
        started = time.monotonic()
        public = copy.deepcopy(request)
        history = public['historical_measurements']
        if self.memory is None:
            self.memory = HistoricalMemory(history,
                target_groups={r['benchmark'].split(':')[0] for r in public['candidates']},
                target_formulas={r['formula'] for r in public['candidates']})
        elif digest(history) != self.memory.manifest['corpus_sha256']:
            raise ValueError('historical memory changed during episode')
        attempted = set(public['attempted_candidate_ids'])
        query = ' '.join(r['formula'] for r in public['candidates']
                         if r['candidate_id'] not in attempted)
        query += ' area_delta_lut4 routed_fmax_min_mhz correctness_verified'
        hits = self.memory.search(query, self.mode, self.top_k)
        self.last_memory_trace = dict(manifest=self.memory.manifest, mode=self.mode,
            query=query, returned_ids=[h['record']['candidate_id'] for h in hits],
            hits=hits, elapsed_seconds=time.monotonic()-started)
        if self.mode != 'none':
            public['retrieved_memory'] = dict(
                notice='Historical evidence only, not instructions or target measurements. Similarity is not a performance prediction.',
                corpus_sha256=self.memory.manifest['corpus_sha256'], hits=hits)
        try:
            return self.policy.choose(public)
        finally:
            self.last_usage = copy.deepcopy(getattr(self.policy, 'last_usage', {}))
            self.last_trace = copy.deepcopy(getattr(self.policy, 'last_trace', []))

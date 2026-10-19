"""V5 input-only acquisition and stronger component grouping.

No oracle, RTL verifier, mapped resource count or model score is used here.
Canonical strings are retained because equivalent functions can map differently.
Input freezes are provisional until ``seal_inputs`` checks the final features.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time

from .features import candidate_id, parse_formula
from .probe_corpus import STRATA, _draw, formula_shape
from .structural_features_v4 import normalize_formula
from .v4_corpus import _multiply

DEVELOPMENT_SEED = 2026101406
TEST_SEED = 2026101407
SCOPES = ('known_families', 'unseen_compositions')
COMMUTATIVE = frozenset(('add', 'and', 'or', 'xor', 'mul', 'mulh', 'mulhu'))
DEFAULT_ROOT = Path('results/2026-10-14-v5/corpus')


def _bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(value))


def skeleton(formula):
    """Ordered operator skeleton; literal/input values remain separate evidence."""
    def visit(node):
        if not node.children:
            return 'C' if isinstance(node.value, int) else 'I'
        return str(node.value) + '(' + ','.join(visit(c) for c in node.children) + ')'
    return visit(parse_formula(formula))


def equivalence_key(formula):
    """Exact commutativity plus V4 normalization, without input renaming.

    This is a sufficient grouping rule, not a complete equivalence decision.
    No sampled semantic fingerprint is treated as a verified proof.
    """
    def visit(node):
        if not node.children:
            return str(node.value)
        children = [visit(c) for c in node.children]
        if node.value in COMMUTATIVE:
            children.sort()
        return str(node.value) + '(' + ','.join(children) + ')'
    return visit(parse_formula(normalize_formula(formula)))


def signatures(formula):
    canonical = parse_formula(formula).canonical()
    normalized = normalize_formula(canonical)
    return {'normalized_formula': normalized, 'original_skeleton': skeleton(canonical),
            'normalized_skeleton': skeleton(normalized), 'equivalence_key': equivalence_key(canonical)}


def group_components(rows, feature_records=None, verified_equivalences=(), *, include_skeletons=False):
    """Return formula -> stable component id, joining all supplied evidence.

    ``feature_records`` are records with formula and values/feature_values.
    Their normalized_formula, when present, is the current extractor's
    normalization and is additionally joined; acquisition uses frozen V4 only.
    Proof records require formula_a, formula_b, status='proved', a method in
    {'yosys_sat','smt','algebraic_identity'}, and an evidence_sha256. Callers
    must verify the referenced evidence before passing proof records.
    ``include_skeletons=True`` joins both skeleton partitions for CV/family
    analysis. It is deliberately false for the known-family test endpoint.
    """
    formulas = sorted({parse_formula(r['formula']).canonical() for r in rows})
    parent = {f: f for f in formulas}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    seen = {}
    for f in formulas:
        sig = signatures(f)
        keys = [('normalized', sig['normalized_formula']), ('equivalence', sig['equivalence_key'])]
        if include_skeletons:
            keys += [('original_skeleton', sig['original_skeleton']),
                     ('normalized_skeleton', sig['normalized_skeleton'])]
        for key in keys:
            if key in seen:
                union(f, seen[key])
            else:
                seen[key] = f
    feature_seen = {}
    schema_length = None
    recorded = set()
    for record in feature_records or ():
        f = parse_formula(record['formula']).canonical()
        if f not in parent or f in recorded:
            raise ValueError('Feature record formula missing from rows or duplicated')
        recorded.add(f)
        if 'normalized_formula' in record:
            normalized = parse_formula(record['normalized_formula']).canonical()
            keys = [('normalized', normalized)]
            if include_skeletons:
                keys.append(('normalized_skeleton', skeleton(normalized)))
            for key in keys:
                if key in seen:
                    union(f, seen[key])
                else:
                    seen[key] = f
        raw = record.get('values', record.get('feature_values'))
        if not isinstance(raw, (list, tuple)) or not raw:
            raise ValueError('Features require a nonempty numeric vector')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw):
            raise ValueError('Features require finite numeric values')
        if schema_length is None:
            schema_length = len(raw)
        if len(raw) != schema_length:
            raise ValueError('Feature vector schema differs')
        vector = tuple(float(v) for v in raw)
        if vector in feature_seen:
            union(f, feature_seen[vector])
        else:
            feature_seen[vector] = f
    for proof in verified_equivalences:
        if (proof.get('status') != 'proved' or proof.get('method') not in
                ('yosys_sat', 'smt', 'algebraic_identity') or
                not isinstance(proof.get('evidence_sha256'), str) or
                len(proof['evidence_sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in proof['evidence_sha256'])):
            raise ValueError('Equivalence requires verified proof evidence; samples are insufficient')
        a, b = (parse_formula(proof[k]).canonical() for k in ('formula_a', 'formula_b'))
        if a not in parent or b not in parent:
            raise ValueError('Equivalence proof names an unknown formula')
        union(a, b)
    members = defaultdict(list)
    for f in formulas:
        members[find(f)].append(f)
    identifiers = {root: hashlib.sha256(_bytes(fs)).hexdigest() for root, fs in members.items()}
    return {f: identifiers[find(f)] for f in formulas}


def seal_inputs(development, test, development_features, test_features, verified_equivalences=()):
    """Fail closed on component leakage before fitting, with all features present."""
    for rows, records in ((development, development_features), (test, test_features)):
        expected = {parse_formula(r['formula']).canonical() for r in rows}
        observed = [parse_formula(r['formula']).canonical() for r in records]
        if len(observed) != len(set(observed)) or set(observed) != expected:
            raise ValueError('Sealing requires complete unique feature coverage')
    combined = list(development) + list(test)
    components = group_components(combined, list(development_features) + list(test_features), verified_equivalences)
    development_ids = {components[r['formula']] for r in development}
    overlaps = [r['formula'] for r in test if components[r['formula']] in development_ids]
    if overlaps:
        raise ValueError('Strong-component development/test overlap: ' + json.dumps(overlaps))
    original = {skeleton(r['formula']) for r in development}
    normalized = {skeleton(normalize_formula(r['formula'])) for r in development}
    novel = [r for r in test if r.get('evaluation_scope') == 'unseen_compositions']
    if any(skeleton(r['formula']) in original or skeleton(normalize_formula(r['formula'])) in normalized for r in novel):
        raise ValueError('Unseen composition has a development-seen skeleton')
    current_normalized = {skeleton(r['normalized_formula']) for r in development_features
                          if 'normalized_formula' in r}
    current_test = {r['formula']: r for r in test_features}
    if any('normalized_formula' in current_test[r['formula']] and
            skeleton(current_test[r['formula']]['normalized_formula']) in current_normalized for r in novel):
        raise ValueError('Unseen composition has a current-normalizer development-seen skeleton')
    return {'schema': 'isaforge-v5-input-seal-v1', 'status': 'sealed',
            'component_count': len(set(components.values())), 'components': components,
            'development_formula_count': len(development), 'test_formula_count': len(test),
            'feature_schema_size': len((list(development_features) + list(test_features))[0].get('values',
                (list(development_features) + list(test_features))[0].get('feature_values'))),
            'cross_cohort_component_count': 0, 'verified_equivalence_count': len(verified_equivalences),
            'current_normalizer_record_count': sum('normalized_formula' in r for r in
                list(development_features) + list(test_features)),
            'scope_counts': dict(Counter(r['evaluation_scope'] for r in test)),
            'limitations': ['Grouping is sufficient, not a complete semantic-equivalence proof.',
                           'Known-family endpoint permits familiar skeletons; unseen endpoint does not.']}


def _composed(stratum, rng):
    """Reserved 5-10-operation compositions, exceeding V4's 2-4-op templates."""
    a, b = rng.sample(('in0', 'in1'), 2)
    c, k = rng.choice((-2047, -129, -17, 7, 33, 511)), rng.randrange(1, 2147483647)
    t, u = rng.randrange(1, 31), rng.randrange(1, 31)
    mask, mask2 = rng.getrandbits(32) | 1, rng.getrandbits(32) | 1
    op = rng.choice(('add', 'sub', 'and', 'or', 'xor'))
    if stratum == 'arithmetic_chain':
        return f'xor(sub(add(addi({a},{c}),xori({b},{k})),srli({a},{t})),slli({b},{u}))'
    if stratum == 'shared_diamond':
        shared = f'{op}({a},{b})'
        return f'xor(add(andi({shared},{mask}),srli({shared},{t})),sub(slli({shared},{u}),addi({b},{c})))'
    if stratum == 'parallel_branches':
        return f'{op}(xor(addi({a},{c}),slli({b},{t})),and(xori({b},{k}),srli(andi({a},{mask}),{u})))'
    if stratum == 'mask_logic':
        return f'xor(or(andi({a},{mask}),slli(andi({b},{mask2}),{t})),and(xori({a},{k}),srli({b},{u})))'
    if stratum == 'constant_shifts':
        return f'add(srli(xor(slli({a},{t}),andi({b},{mask})),{u}),srai(addi({b},{c}),{t}))'
    if stratum == 'variable_shifts':
        return f'sra(xor(addi({a},{c}),srli({b},{t})),andi(add(xori({b},{k}),srli({a},{u})),31))'
    if stratum == 'comparators':
        return f'add(slli(slt(addi({a},{c}),srli({b},{t})),{u}),xor(sltiu(andi({b},{mask}),{k}),andi({a},{mask2})))'
    if stratum == 'multiplication':
        mul = rng.choice(('mul', 'mulh', 'mulhu', 'mulhsu'))
        return f'xor(srli({mul}(andi({a},{mask}),srai({b},{t})),{u}),slti(xori({a},{k}),{c}))'
    raise ValueError('Unknown stratum')


def generate(excluded, count, seed, cohort, *, development_formulas=None):
    if cohort not in ('development', 'test') or isinstance(count, bool) or not isinstance(count, int) or count <= 0 or count % 16:
        raise ValueError('Cohort must be development/test and count a positive multiple of 16')
    excluded = {parse_formula(f).canonical() for f in excluded}
    seen = set(excluded)
    normalized_seen = {equivalence_key(f) for f in excluded}
    development_formulas = excluded if development_formulas is None else {
        parse_formula(f).canonical() for f in development_formulas}
    original_skeletons = {skeleton(f) for f in development_formulas}
    normalized_skeletons = {skeleton(normalize_formula(f)) for f in development_formulas}
    rng = random.Random(seed)
    rows = []
    scopes = ('targeted_development',) if cohort == 'development' else SCOPES
    for scope in scopes:
        for stratum in STRATA:
            for slot in range(count // (len(scopes) * len(STRATA))):
                for attempt in range(100000):
                    if scope == 'unseen_compositions':
                        formula, meta = _composed(stratum, rng), {'template': 'reserved_composition_' + stratum,
                            'operand_regime': 'composed_' + stratum}
                    elif stratum == 'multiplication':
                        multiply_slot = ((slot // 2) % 8) * 4 + slot % 4 if cohort == 'test' else slot
                        formula, meta = _multiply(multiply_slot, rng)
                        if cohort == 'development' and slot % 2:
                            # Broader support positions and extra output demand.
                            formula = f'xor({formula},andi(in0,{rng.getrandbits(32)}))'
                            meta = {**meta, 'template': 'targeted_product_output_mix'}
                    else:
                        formula, meta = _draw(stratum, rng), {'template': 'known_' + stratum,
                            'operand_regime': stratum}
                        if cohort == 'development' and slot % 2:
                            formula = f'{rng.choice(("addi", "xori", "srli"))}({formula},{rng.randrange(1,31)})'
                            meta = {**meta, 'template': 'targeted_wrapper_' + stratum}
                    formula = parse_formula(formula).canonical()
                    sig = signatures(formula)
                    if formula in seen or (cohort == 'test' and sig['equivalence_key'] in normalized_seen):
                        continue
                    if scope == 'unseen_compositions' and (sig['original_skeleton'] in original_skeletons or
                            sig['normalized_skeleton'] in normalized_skeletons):
                        continue
                    operations, inputs = formula_shape(formula)
                    if 2 <= operations <= 12 and 1 <= inputs <= 2:
                        break
                else:
                    raise ValueError('Cannot populate planned input pool; no measurements authorize relaxation')
                seen.add(formula)
                normalized_seen.add(sig['equivalence_key'])
                benchmark = f'v5_{cohort}_{scope}_{stratum}'
                rows.append({'benchmark': benchmark, 'candidate_id': candidate_id(benchmark, formula),
                    'formula': formula, 'stratum': stratum, 'cohort': cohort, 'evaluation_scope': scope,
                    'generation_slot': slot, 'generation_attempt': attempt,
                    'distinct_operation_count': operations, 'input_count': inputs, **meta, **sig,
                    'provenance': 'synthetic formula; input-only generation; no executed application or measured outcome'})
    return rows


def historical_formulas(root):
    root = Path(root)
    rows = json.loads((root / 'results/2026-10-13-v4/development-data.json').read_text())
    rows += json.loads((root / 'results/2026-10-13-v4/corpus/test/candidates.json').read_text())
    formulas = {parse_formula(r['formula']).canonical() for r in rows}
    if len(formulas) != 1545:
        raise ValueError('Expected all 1545 consumed historical formulas as development')
    return formulas


def freeze(root=DEFAULT_ROOT, *, repository_root=Path('.'), development_count=512, test_count=256):
    repository_root = Path(repository_root)
    old = historical_formulas(repository_root)
    development = generate(old, development_count, DEVELOPMENT_SEED, 'development')
    all_development = old | {r['formula'] for r in development}
    test = generate(all_development, test_count, TEST_SEED, 'test', development_formulas=all_development)
    source_paths = [Path(__file__), repository_root / 'docs/v5-protocol.md',
                    repository_root / 'isaforge/structural_features_v4.py',
                    repository_root / 'isaforge/v4_corpus.py', repository_root / 'isaforge/probe_corpus.py',
                    repository_root / 'isaforge/features.py']
    sources = {str(p.resolve()): _sha(p) for p in source_paths}
    for cohort, rows, exclusions, seed in (
            ('development', development, old, DEVELOPMENT_SEED),
            ('test', test, all_development, TEST_SEED)):
        directory = Path(root) / cohort
        core = {'schema': 'isaforge-v5-input-freeze-v1', 'cohort': cohort, 'seed': seed,
                'candidate_count': len(rows), 'excluded_formula_count': len(exclusions),
                'candidate_sha256': hashlib.sha256(_bytes(rows)).hexdigest(),
                'excluded_sha256': hashlib.sha256(_bytes(sorted(exclusions))).hexdigest(),
                'stratum_counts': dict(Counter(r['stratum'] for r in rows)),
                'scope_counts': dict(Counter(r['evaluation_scope'] for r in rows)),
                'runtime_source_sha256': sources,
                'input_seal_status': 'provisional; complete feature components must be sealed before fitting',
                'label_access': 'development may be measured; test RTL verification/mapping/labels sealed until all models and predictions freeze',
                'target': 'original syntax isolated default synth_ice40 SB_LUT4; no CPU performance claim'}
        existing = directory / 'freeze.json'
        if existing.exists():
            previous = json.loads(existing.read_text())
            if any(previous.get(k) != v for k, v in core.items()) or _sha(directory / 'candidates.json') != core['candidate_sha256']:
                raise ValueError('Existing input freeze differs; use a separately named acquisition directory')
        else:
            if directory.exists() and any(directory.iterdir()):
                raise ValueError('Nonempty candidate directory without a freeze')
            _write(directory / 'candidates.json', rows)
            _write(directory / 'excluded-formulas.json', sorted(exclusions))
            _write(existing, {**core, 'frozen_at_utc': datetime.now(timezone.utc).isoformat()})
    return development, test


def repair_test_inputs(root, cache_root, *, max_attempts=8):
    """Retain rejected input-only pools and regenerate before any fit or labels.

    The seed, generator, scope sizes and strata remain fixed. Only formulas
    proven to violate input independence are added to cumulative exclusions.
    Features for previously drawn formulas are reused; newly drawn formulas
    get the same current extractor. Mapped test labels are never accessed.
    """
    from .area_model_v5 import FeatureExtractor, columns, source_hashes
    root = Path(root).resolve()
    if any((root / name).exists() for name in
            ('freeze.json', 'training-start.json', 'label-release.json', 'corpus/test/dataset.json')):
        raise ValueError('Input repair is allowed only before fitting, release and test labels')
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 8:
        raise ValueError('Input repair attempts must be between one and eight')
    development_file = root / 'development-features.json'
    development = json.loads(development_file.read_text())['records']
    development_rows = [{'formula': r['formula']} for r in development]
    if len(development_rows) != 2057 or len({r['formula'] for r in development_rows}) != 2057:
        raise ValueError('Expected complete 2057-row development feature records')
    feature_file = root / 'test-features.json'
    feature_archive = json.loads(feature_file.read_text())
    if tuple(feature_archive['columns']) != columns():
        raise ValueError('Repair requires the current feature schema')
    retained = {r['formula']: r for r in feature_archive['records']}
    historical_development = {r['formula'] for r in development}
    original_skeletons = {skeleton(f) for f in historical_development}
    v4_skeletons = {skeleton(normalize_formula(f)) for f in historical_development}
    current_skeletons = {skeleton(r['normalized_formula']) for r in development}
    journal_path = root / 'input-rejections.json'
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else {
        'schema': 'isaforge-v5-input-rejections-v1', 'policy': 'fixed generator and seed; input independence only',
        'attempts': [], 'test_labels_accessed': False}
    if len(journal['attempts']) > max_attempts:
        raise ValueError('Input-only repair already exhausted its declared attempt bound')
    rejected = {r['formula'] for attempt in journal['attempts'] for r in attempt['rejections']}
    extractor = FeatureExtractor(cache_root)
    expected_sources = source_hashes()
    for attempt_number in range(max_attempts + 1):
        rows = json.loads((root / 'corpus/test/candidates.json').read_text())
        missing = [r for r in rows if r['formula'] not in retained]
        started = time.perf_counter()
        if missing:
            _, extracted = extractor.matrix(missing, workers=2)
            retained.update({r['formula']: r for r in extracted})
        records = [retained[r['formula']] for r in rows]
        _write(feature_file, {'columns': columns(), 'records': records})
        if source_hashes() != expected_sources:
            raise ValueError('Repair feature sources changed; stop before fitting')
        components = group_components(development_rows + rows, development + records)
        development_ids = {components[r['formula']] for r in development_rows}
        rejections = []
        for row, record in zip(rows, records):
            reasons = []
            if components[row['formula']] in development_ids:
                reasons.append('cross_cohort_identity_or_exact_feature_component')
            if row['evaluation_scope'] == 'unseen_compositions':
                if skeleton(row['formula']) in original_skeletons:
                    reasons.append('original_skeleton_seen_in_development')
                if skeleton(normalize_formula(row['formula'])) in v4_skeletons:
                    reasons.append('acquisition_normalized_skeleton_seen_in_development')
                if skeleton(record['normalized_formula']) in current_skeletons:
                    reasons.append('current_normalized_skeleton_seen_in_development')
            if reasons:
                rejections.append({'formula': row['formula'], 'candidate_id': row['candidate_id'],
                    'evaluation_scope': row['evaluation_scope'], 'stratum': row['stratum'], 'reasons': reasons})
        if not rejections:
            seal = seal_inputs(development_rows, rows, development, records)
            _write(root / 'input-seal.json', seal)
            journal['status'] = 'sealed'
            journal['final_candidate_sha256'] = _sha(root / 'corpus/test/candidates.json')
            journal['final_test_features_sha256'] = _sha(feature_file)
            journal['current_source_sha256'] = expected_sources
            journal['sealed_at_utc'] = datetime.now(timezone.utc).isoformat()
            _write(journal_path, journal)
            print(json.dumps({'status': 'sealed', 'attempts_rejected': len(journal['attempts']),
                'cumulative_excluded_formulas': len(rejected), 'test_count': len(rows),
                'test_labels_accessed': False}), flush=True)
            return seal
        archive = root / 'input-attempts' / f'test-{len(journal["attempts"]):04d}'
        archive.mkdir(parents=True, exist_ok=False)
        shutil.copytree(root / 'corpus/test', archive / 'inputs')
        shutil.copy2(feature_file, archive / 'test-features.json')
        if (root / 'feature-extraction.json').exists():
            shutil.copy2(root / 'feature-extraction.json', archive / 'feature-extraction.json')
        report = {'attempt_directory': str(archive.relative_to(root)),
            'candidate_sha256': _sha(root / 'corpus/test/candidates.json'),
            'test_features_sha256': _sha(feature_file), 'rejections': rejections,
            'new_formula_features_extracted': len(missing),
            'feature_extraction_seconds': time.perf_counter() - started,
            'source_sha256': expected_sources, 'test_labels_accessed': False}
        _write(archive / 'rejections.json', report)
        journal['attempts'].append(report)
        _write(journal_path, journal)
        rejected.update(r['formula'] for r in rejections)
        if len(journal['attempts']) > max_attempts:
            raise ValueError('Input-only repair exhausted its declared attempt bound; no fitting authorized')
        replacement = generate(historical_development | rejected, 256, TEST_SEED, 'test',
                               development_formulas=historical_development)
        old_freeze = json.loads((root / 'corpus/test/freeze.json').read_text())
        replacement_freeze = {**old_freeze, 'candidate_sha256': hashlib.sha256(_bytes(replacement)).hexdigest(),
            'excluded_formula_count': len(historical_development | rejected),
            'excluded_sha256': hashlib.sha256(_bytes(sorted(historical_development | rejected))).hexdigest(),
            'runtime_source_sha256': {path: _sha(path) for path in old_freeze['runtime_source_sha256']},
            'selection_source_sha256': expected_sources, 'input_repair_revision': len(journal['attempts']),
            'previous_candidate_sha256': report['candidate_sha256'], 'input_only_excluded_formula_count': len(rejected),
            'input_seal_status': 'provisional; complete feature components must be sealed before fitting',
            'frozen_at_utc': datetime.now(timezone.utc).isoformat()}
        _write(root / 'corpus/test/candidates.json', replacement)
        _write(root / 'corpus/test/excluded-formulas.json', sorted(historical_development | rejected))
        _write(root / 'corpus/test/freeze.json', replacement_freeze)
        print(f'Input-only attempt {len(journal["attempts"])} rejected {len(rejections)} rows; regenerated fixed 256-input pool.', flush=True)
    raise AssertionError('Unreachable acquisition state')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--repository-root', type=Path, default=Path('.'))
    parser.add_argument('--repair-test', action='store_true')
    parser.add_argument('--cache-root', type=Path, default=Path('generated/v5-features'))
    args = parser.parse_args(argv)
    if args.repair_test:
        repair_test_inputs(args.root, args.cache_root)
        return 0
    development, test = freeze(args.root, repository_root=args.repository_root)
    print(json.dumps({'development_count': len(development), 'test_count': len(test),
                      'test_labels_collected': False, 'input_seal': 'required before fitting'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

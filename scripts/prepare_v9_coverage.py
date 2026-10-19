#!/usr/bin/env python3
"""Prepare the fixed48 coverage-development inputs; no synthesis or fitting.

The original1665 targets are pre-existing training inputs. Newly proposed V9
target files are never accessed. Historical evaluation targets are only named
by existing completion digests and are not parsed here.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import area_model_v6 as v6
from isaforge import semantic_features_v7 as semantic
from isaforge.features import parse_formula
from isaforge.structural_features_v5 import normalize_formula
from isaforge.v5_corpus import equivalence_key, skeleton

V8 = 'results/2026-10-15-v8-application-transfer'
V6 = 'results/2026-10-14-v6'
CONSTANT_BASES = (11, 85, 341, 511)
CONSTANT_SCALES = (1, 4)
SHIFTS = (1, 2, 3, 4, 8, 12, 24, 30)
PARAMETERS = dict(v6.FIXED_PARAMETERS)
SCHEMA = 'isaforge-v9-coverage-preparation-v1'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def record(path, root):
    import os
    path = Path(path).resolve()
    return {'path': os.path.relpath(path, Path(root).resolve()), 'sha256': sha(path)}


def checked(entry, root):
    path = (Path(root) / entry['path']).resolve()
    require(path.is_file() and sha(path) == entry['sha256'], 'Changed bound file: ' + entry['path'])
    return path


def required_sources(repository=ROOT, training_script=None, collector_script=None):
    repository = Path(repository).resolve()
    trainer = Path(training_script or repository / 'scripts/train_v9_coverage.py').resolve()
    collector = Path(collector_script or repository / 'scripts/measure_v9_coverage.py').resolve()
    return [repository / 'scripts/prepare_v9_coverage.py', repository / 'tests/test_prepare_v9_coverage.py', trainer,
        repository / 'tests/test_train_v9_coverage.py', collector, repository / 'tests/test_measure_v9_coverage.py',
        repository / 'tests/test_train_v9_coverage_audit.py',
        repository / 'scripts/measure_v6.py', repository / 'scripts/evaluate_v6.py', repository / 'scripts/evaluate_v8_applications.py',
        repository / 'docs/v9-training-coverage-direction.md', *sorted((repository / 'isaforge').glob('*.py'))]


def historical_file(path, bindings):
    path = Path(path).resolve()
    require(bindings.get(path) == sha(path), 'Historical frozen input differs: ' + str(path))


def committed_metadata(repository, paths):
    """Authenticate completed historical manifests to their existing Git bytes."""
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    records = []
    for path in paths:
        path = Path(path).resolve()
        relative = path.relative_to(repository).as_posix()
        data = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=repository)
        digest = hashlib.sha256(data).hexdigest()
        require(digest == sha(path), 'Historical completion/freeze differs from committed bytes: ' + relative)
        records.append({'path': relative, 'sha256': digest})
    return {'commit': commit, 'files': records}


def fixed_candidates():
    output = []
    for constant in sorted(base * scale for base in CONSTANT_BASES for scale in CONSTANT_SCALES):
        for context, formula in (
            ('direct_product', f'mul(in0,addi(0,{constant}))'),
            ('add_after_product', f'add(mul(in0,addi(0,{constant})),in1)'),
            ('sub_before_product', f'mul(sub(in0,in1),addi(0,{constant}))'),
            ('masked_sub_before_product', f'mul(sub(andi(in0,63),in1),addi(0,{constant}))'),
        ):
            output.append({'formula': formula, 'context': context, 'constant_u32': constant})
    for shift in SHIFTS:
        for operation in ('add', 'sub'):
            output.append({'formula': f'sub(srai({operation}(in0,in1),{shift}),srai(in1,31))',
                'context': operation + '_signed_shift_sign_sub', 'shift': shift})
    for row in output:
        formula = row['formula']
        row['candidate_id'] = 'v9-coverage:' + hashlib.sha256(formula.encode()).hexdigest()
        root = parse_formula(formula)
        pending = [root]
        count = 0
        while pending:
            node = pending.pop()
            if not node.children:
                continue
            count += 1
            if node.value in ('addi', 'andi', 'ori', 'xori', 'slti', 'sltiu'):
                require(-2048 <= node.children[-1].value <= 2047, 'Nonencodable signed12 immediate')
            if node.value in ('slli', 'srli', 'srai'):
                require(0 <= node.children[-1].value <= 31, 'Nonencodable shift immediate')
            pending.extend(node.children)
        require(2 <= count <= 4 and root.canonical() == formula, 'Expected canonical2..4-operation original')
        row['operation_count'] = count
    require(len(output) == len({r['formula'] for r in output}) == 48, 'Exactly48 unique originals required')
    return output


def identity_keys(record):
    original = parse_formula(record['formula']).canonical()
    forms = {original}
    if 'normalized_formula' in record:
        forms.add(parse_formula(record['normalized_formula']).canonical())
    modes = record.get('v7_modes')
    if modes is not None:
        for mode in ('bit', 'affine', 'combined'):
            stored = modes.get(mode, {})
            if stored.get('metadata', {}).get('status') == 'accepted':
                forms.add(parse_formula(stored['normalized_formula']).canonical())
        # A legacy combined field cannot override a recorded fallback/rejection.
    elif 'v7_combined_normalized_formula' in record:
        forms.add(parse_formula(record['v7_combined_normalized_formula']).canonical())
    return {'canonical_original': {original}, 'original_or_accepted_normal_form': forms,
        'frozen_commutative_normalization': {equivalence_key(f) for f in forms},
        'ordered_skeleton': {skeleton(f) for f in forms}}


def duplicate_report(consumed, proposals):
    indices = defaultdict(lambda: defaultdict(set))
    for row in consumed:
        original = row['formula']
        for channel, keys in identity_keys(row).items():
            for key in keys:
                indices[channel][key].add(original)
    results = []
    for row in proposals:
        matches = {channel: sorted({formula for key in keys for formula in indices[channel].get(key, ())})
                   for channel, keys in identity_keys(row).items()}
        results.append({'formula': row['formula'], 'matches': matches,
            'canonical_original_seen': bool(matches['canonical_original']),
            'declared_functional_alias': any(matches[c] for c in (
                'original_or_accepted_normal_form', 'frozen_commutative_normalization'))})
    internal = []
    for i, row in enumerate(proposals):
        keys = identity_keys(row)
        for other in proposals[:i]:
            other_keys = identity_keys(other)
            overlap = {c: sorted(keys[c] & other_keys[c]) for c in keys if keys[c] & other_keys[c]}
            if overlap:
                internal.append({'formula_a': other['formula'], 'formula_b': row['formula'],
                    'channels': overlap, 'functional_alias': any(c in overlap for c in (
                        'original_or_accepted_normal_form', 'frozen_commutative_normalization'))})
    return {'schema': 'isaforge-v9-coverage-duplicates-v1', 'consumed_unique_originals': len({r['formula'] for r in consumed}),
        'proposed_originals': len(proposals), 'records': results, 'within_proposal_matches': internal,
        'canonical_original_seen_count': sum(r['canonical_original_seen'] for r in results),
        'declared_functional_alias_count': sum(r['declared_functional_alias'] for r in results),
        'within_proposal_functional_alias_pairs': sum(r['functional_alias'] for r in internal),
        'scope': 'Complete prior input union; canonical originals, saved V5 normalization and accepted V7 bit/affine/combined normal forms, and frozen commutative normalization are separate tests. Rejected/fallback V7 modes do not add aliases. Skeletons are structural diagnostics, not equivalence proofs. No vector extraction/collision test or exhaustive functional-inequality claim. All48 originals retained regardless of diagnostic matches.'}


def prior_inputs(repository):
    """Replay the sealed2764 registry from its committed ZIP, then add all V8."""
    root = repository / V8
    point = read(root / 'point-freeze.json')
    seal = read(root / 'input-seal.json')
    bindings = {(root / r['path']).resolve(): r['sha256'] for r in [*point['files'], *seal['files']]}
    index_path = root / 'archive-indexes/prelabel.json'
    require(bindings.get(index_path) == sha(index_path), 'Consumed archive index not bound to V8 freeze')
    index = read(index_path)
    archive = checked(index['archive'], index_path.parent)
    require(bindings.get(archive) == sha(archive), 'Consumed archive not bound to V8 freeze')
    members = {r['path']: r for r in index['files']}
    require(len(members) == len(index['files']), 'Duplicate archive manifest members')
    with zipfile.ZipFile(archive) as raw:
        require(len(raw.namelist()) == len(set(raw.namelist())) and set(raw.namelist()) == set(members), 'Archive member coverage differs')
        def member(name):
            data = raw.read(name)
            entry = members[name]
            require(len(data) == entry.get('bytes', entry.get('size')) and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Archived consumed member differs')
            return json.loads(data)
        base = member('consumed/features.json')
        completion = member('consumed/completion.json')
        start = member('consumed/start.json')
    require(len(base['records']) == completion['formulas'] == 2764, 'Complete2764 consumed registry required')
    require(completion.get('labels_read') is False and completion.get('model_predictions_read') is False, 'Historical input-only registry contract differs')
    fresh_path = root / 'features.json'
    require(bindings.get(fresh_path) == sha(fresh_path), 'V8 features not frozen')
    fresh = read(fresh_path)
    require(base['columns'] == fresh['columns'] and len(fresh['records']) == 146, 'Complete full455 V8 union required')
    union = {}
    sources = defaultdict(set)
    for name, records in (('pre_v8_consumed', base['records']), ('v8_consumed', fresh['records'])):
        require(len({r['formula'] for r in records}) == len(records), 'Duplicate canonical original within prior registry')
        for row in records:
            formula = parse_formula(row['formula']).canonical()
            require(formula == row['formula'], 'Prior original not canonical')
            # Keep EVERY accepted historical form, including different first-run
            # fallbacks for a shared original, rather than selecting a favorite.
            forms = identity_keys(row)['original_or_accepted_normal_form']
            union.setdefault(formula, set()).update(forms)
            sources[formula].add(name)
    compact = [{'formula': f, 'accepted_forms': sorted(union[f]), 'sources': sorted(sources[f])} for f in sorted(union)]
    # Expand saved forms into records without losing any identity evidence.
    expanded = [{'formula': r['formula'], 'normalized_formula': f} for r in compact for f in r['accepted_forms']]
    return compact, expanded, [root / 'point-freeze.json', root / 'input-seal.json', index_path, archive, fresh_path], {
        'pre_v8_unique': 2764, 'v8_unique': 146, 'union_unique': len(compact),
        'shared_canonical_originals': sum(len(r['sources']) == 2 for r in compact),
        'historical_registry_source_counts': start.get('source_counts', {})}


def validate_preparation(root):
    """Source/input validation only; never reads V9 target measurements."""
    root = Path(root).resolve()
    manifest = read(root / 'preparation.json')
    require(manifest.get('schema') == SCHEMA and manifest.get('status') == 'prepared-inputs-only', 'Complete V9 input preparation required')
    require(manifest.get('new_labels_read') is False and manifest.get('model_fits') == 0, 'Input-only contract differs')
    records = manifest['files']
    require(len({str((root / r['path']).resolve()) for r in records}) == len(records), 'Duplicate bound files')
    for entry in records:
        checked(entry, root)
    recipe = read(checked(manifest['recipe'], root))
    candidates = read(checked(manifest['candidates'], root))
    require(candidates == fixed_candidates(), 'Fixed exact48 cohort differs')
    require(recipe.get('schema') == 'isaforge-v9-coverage-recipe-v1'
        and recipe.get('new_training_formula_count') == 48 and recipe.get('original_training_formula_count') == 1665
        and recipe.get('fixed_parameters') == PARAMETERS and recipe.get('model_fits') == 1
        and recipe.get('feature_columns') == list(v6.columns())
        and recipe.get('selected_columns') == list(v6.mapping_columns())
        and recipe.get('selected_indices') == v6.mapping_indices().tolist(), 'Fixed training/schema recipe differs')
    expected = {'workers': 2, 'verification_seed': 2026101519, 'vectors_per_formula': 2148,
        'original_rtl_only': True, 'new_measurement_count': 48}
    require(recipe.get('measurement') == expected, 'Fixed target measurement recipe differs')
    require(set(recipe['frozen_tool']) == {'version', 'executable_sha256'}, 'Exact frozen tool identity required')
    required = required_sources(ROOT, ROOT / recipe['training_script'], ROOT / recipe['collector_script'])
    require(set(recipe['required_sources']) == {p.relative_to(ROOT).as_posix() for p in required}, 'Required source inventory differs')
    bound = {(root / e['path']).resolve() for e in records}
    require(all(p in bound for p in required), 'Required source binding missing')
    require(all((root / manifest[k]['path']).resolve() in bound for k in ('recipe', 'candidates')), 'Manifest artifacts not flat-bound')
    return manifest, recipe, candidates


def run(root, *, repository=ROOT, training_script=None, collector_script=None, prior_preflight=None):
    root, repository = Path(root).resolve(), Path(repository).resolve()
    require(not root.exists(), 'Fresh immutable preparation directory required')
    training_script = Path(training_script or repository / 'scripts/train_v9_coverage.py').resolve()
    collector_script = Path(collector_script or repository / 'scripts/measure_v9_coverage.py').resolve()
    sources = required_sources(repository, training_script, collector_script)
    require(all(p.is_file() and p.is_relative_to(repository) for p in sources), 'All reviewed collector/trainer/tests/runtime sources must exist before preparation')
    source_before = {p: sha(p) for p in sources}
    preflight_bytes = Path(prior_preflight).read_bytes() if prior_preflight is not None else None
    if preflight_bytes is not None:
        previous = json.loads(preflight_bytes)
        require(len(previous.get('proof_statuses', {})) == 48, 'Complete prior preflight statuses required')
    candidates = fixed_candidates()
    compact, consumed, source_paths, counts = prior_inputs(repository)
    identities = []
    for row in candidates:
        proof = semantic.analyze_modes(row['formula'], budget=semantic.Budget(proof_timeout_ms=500))
        identities.append({**row, 'normalized_formula': normalize_formula(row['formula']),
            'v7_combined_normalized_formula': proof['combined']['normalized_formula'], 'v7_modes': proof})
    duplicates = duplicate_report(consumed, identities)
    old_root = repository / V8
    original_path = old_root / 'training/training-data.json'
    old_point = read(old_root / 'point-freeze.json')
    frozen_bindings = {(old_root / r['path']).resolve(): r['sha256'] for r in old_point['files']}
    require(frozen_bindings.get(original_path) == sha(original_path), 'Original1665 source differs from frozen V8 lineage')
    original = read(original_path)
    require(len(original['rows']) == len(original['values']) == 1665 and len(original['columns']) == 455,
            'Exact original1665/full455 source required')
    original336 = {'schema': 'isaforge-v9-original-training336-v1', 'columns': list(v6.columns()),
        'rows': original['rows'], 'values': [r[:336] for r in original['values']],
        'training_provenance': original['training_provenance'], 'frozen_tool': original['frozen_tool']}
    require(original['columns'][:336] == original336['columns'] and all(len(r) == 455 for r in original['values']), 'Original V6 prefix schema differs')
    old_completion = read(old_root / 'measurements/completion.json')
    prior_completion_path = repository / V6 / 'corpus/test/completion.json'
    prior_completion = read(prior_completion_path)
    require(old_completion.get('complete') is True and old_completion.get('failures') == []
        and prior_completion.get('complete') is True and prior_completion.get('failures') == [], 'Completed consumed cohorts required')
    prior_point_path = repository / V6 / 'point-freeze.json'
    prior_point = read(prior_point_path)
    prior_bindings = {(prior_point_path.parent / r['path']).resolve(): r['sha256'] for r in prior_point['files']}
    for name in ('corpus/test/candidates.json', 'corpus/test/features.json', 'corpus/test/freeze.json'):
        historical_file(repository / V6 / name, prior_bindings)
    prior_prediction = prior_point['models']['mapping_v6']['test_predictions']
    checked(prior_prediction, prior_point_path.parent)
    history = committed_metadata(repository, [old_root / 'point-freeze.json', old_root / 'measurements/completion.json',
        prior_point_path, prior_completion_path])
    evaluation_paths = [old_root / n for n in ('rows.json', 'programs.json', 'features.json', 'point-freeze.json', 'measurements/completion.json')]
    evaluation_paths += [repository / V6 / n for n in ('corpus/test/features.json', 'corpus/test/candidates.json', 'corpus/test/freeze.json',
        'corpus/test/completion.json', 'point-freeze.json', 'point-predictions/mapping_v6-test.json')]
    baseline = old_point['models']['mapping_v6']
    baseline_paths = [(old_root / baseline[k]['path']).resolve() for k in ('artifact', 'schema', 'predictions')]
    require(all(sha((old_root / baseline[k]['path']).resolve()) == baseline[k]['sha256']
                for k in ('artifact', 'schema', 'predictions')), 'Original baseline artifact/schema/points differ')
    paths = list(dict.fromkeys([*sources, *source_paths, original_path, prior_completion_path, *evaluation_paths, *baseline_paths]))
    bindings = [record(p, root) for p in paths]
    root.mkdir(parents=True)
    if preflight_bytes is not None:
        with (root / 'prior-input-preflight.json').open('xb') as stream:
            stream.write(preflight_bytes)
    write(root / 'candidates.json', candidates)
    write(root / 'original-training.json', original336)
    write(root / 'consumed-input-ledger.json', {'schema': 'isaforge-v9-complete-consumed-input-ledger-v1', 'counts': counts, 'records': compact})
    write(root / 'identity-analysis.json', identities)
    write(root / 'duplicate-analysis.json', duplicates)
    write(root / 'premeasurement-input-changes.json', {
        'schema': 'isaforge-v9-premeasurement-proposal-changes-v1', 'new_labels_read': False, 'model_fits': 0,
        'initial_draft': {'constant_bases': [11, 37, 341, 21845], 'constant_scales': [1, 32], 'shifts': [1, 2, 4, 8, 12, 16, 24, 30]},
        'final': {'constant_bases': list(CONSTANT_BASES), 'constant_scales': list(CONSTANT_SCALES), 'shifts': list(SHIFTS)},
        'reasons': ['Replace shift16 with3 because the shift16 add/sign-sub original is already in consumed V8.',
            'Replace constant grid before measurement to keep every addi(0,K) within signed12-bit immediates, max2044, while varying positive-constant density and trailing zeros.'],
        'no_outcome_dependent_candidate_change': True})
    recipe = {'schema': 'isaforge-v9-coverage-recipe-v1', 'scope': 'Consumed development evidence only; no fresh generalization claim',
        'original_training_formula_count': 1665, 'new_training_formula_count': 48, 'model_fits': 1,
        'fixed_parameters': PARAMETERS, 'feature_columns': list(v6.columns()), 'selected_columns': list(v6.mapping_columns()),
        'selected_indices': v6.mapping_indices().tolist(), 'frozen_tool': original['frozen_tool'],
        'original_training': record(root / 'original-training.json', root),
        'baseline_model': {k: record((old_root / baseline[k]['path']).resolve(), root) for k in ('artifact', 'schema', 'predictions')},
        'new_features': {'path': 'features.json', 'schema': 'existing-V6-full336', 'formula_count': 48,
            'status': 'not-extracted-at-input-preparation', 'source': 'source-bound isaforge.area_model_v6.FeatureExtractor'},
        'training_rules': {'equal_formula_weights': True, 'retuning': False, 'original_generic_graph_zero_rule': True,
            'drop_or_replace_failed_targets': False, 'all_48_originals_retained': True},
        'measurement': {'workers': 2, 'verification_seed': 2026101519, 'vectors_per_formula': 2148, 'original_rtl_only': True, 'new_measurement_count': 48},
        'evaluation': {'primary': 'all4 V8 equal-family MAE augmented minus frozen mapping_v6',
            'secondary': ['all6 V8 constant-low-multiply rows', 'cap32/64/128 false accepts and rejects', 'true56 signed-shift case', 'consumed V6 test192 regression'],
            'in_sample': 'Original1665 diagnostics are in-sample and labeled as such',
            'target_path_base': 'repository-root',
            'v8': {'root': str(Path(V8)), 'labels': {'path': str(Path(V8) / 'measurements' / old_completion['attempt'] / 'labels.json'), 'sha256': old_completion['labels_sha256']}},
            'v6_test': {'root': str(Path(V6) / 'corpus/test'), 'labels': {'path': str(Path(V6) / 'corpus/test' / prior_completion['attempt'] / 'dataset.json'), 'sha256': prior_completion['dataset_sha256']}}},
        'historical_committed_metadata': history,
        'identity_analysis_history': {'prior_input_only_preflight': preflight_bytes is not None,
            'prior_preflight_complete_certificates_retained': False if preflight_bytes is not None else None,
            'retained_proof_scope': 'Complete first500ms attempts within this preparation; not a claim of first-ever cold analysis. No timed result selection or preferred retry.',
            'prior_preflight_report': record(root / 'prior-input-preflight.json', root) if preflight_bytes is not None else None},
        'training_script': training_script.relative_to(repository).as_posix(),
        'collector_script': collector_script.relative_to(repository).as_posix(),
        'required_sources': [p.relative_to(repository).as_posix() for p in sources],
        'no_yosys_verilator_or_fit_called_during_preparation': True}
    write(root / 'recipe.json', recipe)
    produced = [root / n for n in ('candidates.json', 'original-training.json', 'consumed-input-ledger.json', 'identity-analysis.json', 'duplicate-analysis.json', 'premeasurement-input-changes.json', 'recipe.json')]
    if preflight_bytes is not None:
        produced.append(root / 'prior-input-preflight.json')
    manifest = {'schema': SCHEMA, 'status': 'prepared-inputs-only', 'prepared_at_utc': now(),
        'new_labels_read': False, 'model_fits': 0, 'candidate_count': 48,
        'candidates': record(root / 'candidates.json', root), 'recipe': record(root / 'recipe.json', root),
        'files': [*bindings, *[record(p, root) for p in produced]],
        'consumed_counts': counts, 'duplicate_summary': {k: duplicates[k] for k in ('canonical_original_seen_count', 'declared_functional_alias_count', 'within_proposal_functional_alias_pairs')},
        'solver_identity': semantic.solver_identity(),
        'scope': 'Input identities and original training data only. No new hardware target or model fit; new graph features not extracted. Review and committed source binding precede separate parent measurement release.'}
    write(root / 'preparation.json', manifest)
    require(all(sha(path) == digest for path, digest in source_before.items()), 'Source changed during preparation')
    validate_preparation(root)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--training-script', type=Path)
    parser.add_argument('--collector-script', type=Path)
    parser.add_argument('--prior-preflight', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.root, training_script=args.training_script, collector_script=args.collector_script,
                         prior_preflight=args.prior_preflight), indent=2))

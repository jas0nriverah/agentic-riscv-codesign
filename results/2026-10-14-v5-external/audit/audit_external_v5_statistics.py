#!/usr/bin/env python3
"""Independent external-transfer audit; input-only until explicit release mode.

Never fits or collects labels. Scoring and optional raw recount are enabled only
after the parent authorizes release and the measurement completion record exists.
Uses independent metric helpers, not the repository's evaluators.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from audit_v5_statistics import aligned, digest, match, scalar_metrics, timestamp

FAMILIES = ('graph_shortest_paths', 'speech_codec', 'multiset_word_search')
PROGRAM_COUNTS = {'external_v5_dijkstra': 5, 'external_v5_adpcm_dec': 47, 'external_v5_anagram': 28}
PROGRAM_FAMILY = dict(zip(PROGRAM_COUNTS, FAMILIES))
MODELS = ('sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics', 'masterrtl_fixed', 'v4_frozen')
MATCHED = MODELS[:4]


def read(path):
    return json.loads(Path(path).read_text())


def skeleton(node):
    if not node.children:
        return 'C' if isinstance(node.value, int) else 'I'
    return str(node.value)+'('+','.join(skeleton(c) for c in node.children)+')'


def ledger(root):
    manifest = read(root/'freeze.json')
    assert manifest['schema'] == 'isaforge-external-v5-freeze-v1'
    assert set(manifest['models']) == set(MODELS)
    assert manifest['primary_comparison'] == 'dual_semantics minus sog_tuned'
    assert manifest['primary'] == 'Equal-weight three-family MAE on all80 program/formula rows'
    assert manifest['fitting_performed'] is False and manifest['external_target_labels_read'] is False
    files = [root/'freeze.json']
    for record in manifest['files']:
        path = (root/record['path']).resolve()
        assert digest(path) == record['sha256'], path
        files.append(path)
    for entry in manifest['models'].values():
        assert timestamp(entry['frozen_at_utc']) <= timestamp(manifest['frozen_at_utc'])
        for kind in ('artifact', 'schema', 'predictions'):
            path = (root/entry[kind]['path']).resolve()
            assert digest(path) == entry[kind]['sha256'], path
            files.append(path)
    return manifest, sorted(set(files))


def audit_inputs(root, v5_root):
    manifest, files = ledger(root)
    repository = root.parents[1]
    sys.path.insert(0, str(repository))
    from isaforge.features import candidate_id, parse_formula
    from isaforge.structural_features_v5 import normalize_formula
    rows = read(root/'candidates.json')
    assert len(rows) == 80 and len({r['formula'] for r in rows}) == 79
    assert Counter(r['benchmark'] for r in rows) == Counter(PROGRAM_COUNTS)
    assert len({(r['benchmark'], r['candidate_id']) for r in rows}) == 80
    assert digest(root/'candidates.json') == manifest['candidate_sha256']
    for r in rows:
        assert r['family'] == PROGRAM_FAMILY[r['benchmark']]
        assert r['stratum'] == r['family']
        assert parse_formula(r['formula']).canonical() == r['formula']
        assert candidate_id(r['benchmark'], r['formula']) == r['candidate_id']
        assert not {'lut4_count', 'carry_count', 'predicted_lut4'}.intersection(r)
    external_records = read(root/'features.json')['records']
    external = {r['formula']: r for r in external_records}
    assert len(external_records) == len(external) == 79
    assert set(external) == {r['formula'] for r in rows}
    references = {'development': read(v5_root/'development-features.json')['records'],
                  'consumed_v5_test': read(v5_root/'test-features.json')['records']}
    assert len(references['development']) == 2057 and len(references['consumed_v5_test']) == 256
    assert len({r['formula'] for records in references.values() for r in records}) == 2313
    indices = {}
    for cohort, records in references.items():
        assert len({r['formula'] for r in records}) == len(records)
        indices[cohort] = defaultdict(set)
        for r in records:
            normalized = normalize_formula(r['formula'])
            assert normalized == r['normalized_formula']
            indices[cohort]['exact'].add(r['formula'])
            indices[cohort]['normalized'].add(normalized)
            indices[cohort]['full_feature'].add(tuple(r['values']))
            indices[cohort]['original_skeleton'].add(skeleton(parse_formula(r['formula'])))
            indices[cohort]['normalized_skeleton'].add(skeleton(parse_formula(normalized)))
    novelty = []
    for r in rows:
        f = r['formula']
        normalized = normalize_formula(f)
        assert normalized == external[f]['normalized_formula']
        keys = {'exact': f, 'normalized': normalized, 'full_feature': tuple(external[f]['values']),
            'original_skeleton': skeleton(parse_formula(f)),
            'normalized_skeleton': skeleton(parse_formula(normalized))}
        overlap = {cohort: {k: key in index[k] for k, key in keys.items()}
                   for cohort, index in indices.items()}
        novelty.append({**{k:r[k] for k in ('benchmark', 'candidate_id', 'formula', 'family')},
            'normalized_formula': normalized, 'overlap': overlap,
            'strict_novel': not any(any(v.values()) for v in overlap.values()),
            'formula_novel': not any(any(v[k] for k in ('exact', 'normalized', 'full_feature'))
                                     for v in overlap.values())})
    counts = {cohort: {key: sum(r['overlap'][cohort][key] for r in novelty)
                      for key in indices[cohort]} for cohort in indices}
    recorded_overlap = read(root/'overlap.json')
    match({'records': novelty, 'counts': counts,
           'strict_novel_rows': sum(r['strict_novel'] for r in novelty),
           'formula_novel_rows': sum(r['formula_novel'] for r in novelty)}, recorded_overlap, 'novelty')
    predictions = {}
    for name, entry in manifest['models'].items():
        p, ordered = aligned(rows, read(root/entry['predictions']['path']), 'predicted_lut4')
        for f in external:
            assert len(set(p[[i for i,r in enumerate(rows) if r['formula'] == f]])) == 1
        predictions[name] = ordered
    # Independently replay fixed estimators on the already frozen feature
    # matrix. This checks point/bound/dispersion/domain fields without labels,
    # model fitting, normalization feature extraction or hardware invocation.
    import joblib
    feature_columns = read(root/'features.json')['columns']
    matrix = np.array([external[r['formula']]['values'] for r in rows], dtype=float)
    source_manifest = read(root/manifest['model_source_freeze']['path'])
    prediction_checks = {}
    for name in MATCHED:
        entry = manifest['models'][name]
        assert entry['artifact']['sha256'] == source_manifest['models'][name]['artifact']['sha256']
        schema = read(root/entry['schema']['path'])
        assert feature_columns == schema['feature_columns']
        obj = joblib.load(root/entry['artifact']['path'])
        if name == 'dual_semantics':
            selected = list(range(len(feature_columns)))
        else:
            prefixes = {'sog_tuned': ('sog_',), 'original_graph': ('sog_', 'original_'),
                        'dual_graph': ('sog_', 'original_', 'normalized_', 'absolute_channel_delta_')}[name]
            selected = [i for i,n in enumerate(feature_columns) if n.startswith(prefixes)]
        p = np.asarray(obj.estimator.predict(matrix[:, selected]))
        if schema['configuration'].startswith('xgb_log_'):
            p = np.expm1(p)
        p = np.maximum(p, 0)
        zero = matrix[:, feature_columns.index('original_gate_count')] == 0
        p[zero] = 0
        domain = ((matrix[:, selected] < np.array(obj.feature_minimum)[selected]) |
                  (matrix[:, selected] > np.array(obj.feature_maximum)[selected])).sum(axis=1)
        dispersion = None
        if schema['configuration'].startswith('extra_'):
            dispersion = np.std([tree.predict(matrix[:, selected]) for tree in obj.estimator.estimators_], axis=0)
            dispersion[zero] = 0
        margin = schema['calibration']['upper_margin_lut4']
        for i, row in enumerate(predictions[name]):
            match({'predicted_lut4': float(p[i]), 'upper_lut4': None if margin is None else float(p[i]+margin),
                   'tree_disagreement_lut4': None if dispersion is None else float(dispersion[i]),
                   'outside_training_feature_ranges': int(domain[i])}, row, name+'.feature_replay')
        prediction_checks[name] = {'fixed_estimator_feature_replay_passed': True,
            'selected_feature_count': len(selected), 'ood_rows': int(np.count_nonzero(domain)),
            'ood_rows_by_family': {f: int(np.count_nonzero(domain[[r['family'] == f for r in rows]]))
                                   for f in FAMILIES}}
    family_counts = Counter(r['family'] for r in rows)
    masks = {'all': np.ones(80, dtype=bool),
             'strict_novel': np.array([r['strict_novel'] for r in novelty]),
             'formula_novel': np.array([r['formula_novel'] for r in novelty])}
    subset_counts = {scope: {family: sum(bool(keep) and r['family'] == family for r, keep in zip(rows, mask))
                           for family in FAMILIES} for scope, mask in masks.items()}
    public = {'status': 'input-only checks passed; no external labels accessed',
        'program_formula_count': 80, 'unique_formula_count': 79,
        'program_counts': dict(Counter(r['benchmark'] for r in rows)),
        'primary_family_weights': {f: 1/3 for f in FAMILIES},
        'primary_per_row_weights': {f: 1/(3*family_counts[f]) for f in FAMILIES},
        'reference_formula_count': 2313, 'novelty_match_counts': counts,
        'novelty_subset_family_counts': subset_counts,
        'complete_macro_available': {scope: all(c.values()) for scope,c in subset_counts.items()},
        'frozen_file_count': len(files), 'freeze_sha256': digest(root/'freeze.json'),
        'independent_prediction_feature_checks': prediction_checks,
        'limits': ['Three curated programs/families, not a population sample.',
            'Dijkstra covers one shortest-path invocation, not the full workload.',
            'Familiar formulas/structures remain in the complete primary endpoint.',
            'Structural-group calibration does not provide a 90% whole-application guarantee.']}
    return public, manifest, rows, novelty, predictions, masks, files


def scoped_metrics(rows, y, p, mask):
    family = np.array([r['family'] for r in rows])
    counts = {f: int(np.count_nonzero(mask & (family == f))) for f in FAMILIES}
    if not mask.any():
        return {'row_count': 0, 'family_counts': counts, 'macro_family_mae_lut4': None, 'status': 'empty subset'}
    by_family = {f: scalar_metrics(y[mask & (family == f)], p[mask & (family == f)])
                 for f in FAMILIES if counts[f]}
    complete = all(counts.values())
    return {**scalar_metrics(y[mask], p[mask]), 'row_count': int(mask.sum()),
        'family_counts': counts, 'by_family': by_family,
        'macro_family_mae_lut4': float(np.mean([by_family[f]['mae_lut4'] for f in FAMILIES])) if complete else None,
        'status': 'all three families represented' if complete else 'incomplete family coverage; three-family macro unavailable'}


def uncertainty(rows, prediction_rows, mask, truth, margin):
    bounds = np.array([np.inf if r['upper_lut4'] is None else r['upper_lut4'] for r in prediction_rows])
    if margin is None:
        assert not np.isfinite(bounds).any()
    else:
        assert all(r['upper_lut4'] == r['predicted_lut4']+margin for r in prediction_rows)
    chosen = bounds[mask]
    finite = np.isfinite(chosen)
    covered = truth[mask] <= chosen
    ood = np.array([r['outside_training_feature_ranges'] for r in prediction_rows])[mask]
    if not mask.any():
        return {'count': 0}
    return {'count': int(mask.sum()), 'candidate_coverage': float(covered.mean()),
        'covered_count': int(covered.sum()), 'finite_fraction': float(finite.mean()),
        'mean_upper_minus_target_lut4': float(np.mean(chosen-truth[mask])) if finite.all() else None,
        'outside_selected_feature_range_count': int(np.count_nonzero(ood)),
        'mean_outside_selected_feature_dimensions': float(ood.mean()),
        'maximum_outside_selected_feature_dimensions': int(ood.max())}


def official_bound_fields(rows, predictions, truth):
    """Independently reconstruct finite-bound-only diagnostics and family units."""
    families = np.array([r['family'] for r in rows])
    bound = np.array([np.inf if r['upper_lut4'] is None else r['upper_lut4'] for r in predictions])
    finite = np.array([r['upper_lut4'] is not None for r in predictions]) & np.isfinite(bound)
    outside = np.array([r['outside_training_feature_ranges'] for r in predictions])
    def cell(chosen):
        selected = chosen & finite
        residual = bound[selected]-truth[selected]
        count = int(chosen.sum())
        return {'row_count': count, 'finite_bound_count': int(selected.sum()),
            'finite_bound_fraction': float(selected.sum()/count) if count else None,
            'observed_candidate_coverage': float((residual >= 0).mean()) if len(residual) else None,
            'mean_slack_lut4': float(residual.mean()) if len(residual) else None,
            'minimum_slack_lut4': float(residual.min()) if len(residual) else None,
            'outside_feature_range_rows': int(np.count_nonzero(outside[chosen])),
            'outside_feature_range_dimensions_sum': int(outside[chosen].sum())}
    return {'all': cell(np.ones(len(rows), dtype=bool)),
        'by_family': {f: cell(families == f) for f in FAMILIES},
        'whole_family_coverage_count': sum(bool(np.all(finite[families == f] &
            (bound[families == f] >= truth[families == f]))) for f in FAMILIES)}


def audit_released(root, v5_root, *, raw_generated_root=None):
    structure, manifest, rows, novelty, predictions, masks, files = audit_inputs(root, v5_root)
    release = read(root/'label-release.json')
    assert release['authorized_after_parent_review'] is True
    assert release['freeze_sha256'] == digest(root/'freeze.json')
    assert release['candidate_sha256'] == manifest['candidate_sha256']
    assert timestamp(release['released_at_utc']) > timestamp(manifest['frozen_at_utc'])
    review = release['parent_review']
    assert read(root/'label-approval.json') == review
    assert digest(root/'label-approval.json') == release['review_sha256']
    assert review['approved_for_label_release'] is True
    assert review['freeze_commit'] == release['freeze_commit']
    assert review['freeze_sha256'] == release['freeze_sha256']
    assert timestamp(manifest['frozen_at_utc']) <= timestamp(review['reviewed_at_utc']) <= timestamp(release['released_at_utc'])
    repository = root.parents[1]
    for path in files:
        relative = path.relative_to(repository).as_posix()
        committed = subprocess.run(['git', 'show', release['freeze_commit']+':'+relative],
                                   cwd=repository, capture_output=True, check=True).stdout
        assert hashlib.sha256(committed).hexdigest() == digest(path), relative
    completion = read(root/'measurements/completion.json')
    assert completion['complete'] is True and not completion['failures']
    assert completion['unique_formula_count'] == 79 and completion['program_formula_count'] == 80
    assert completion['release'] == release
    assert completion['collector_sha256'] == digest(repository/'scripts/measure_external_v5.py')
    assert completion['original_rtl_only'] is True
    assert completion['tool'] == manifest['measurement_tool']['version']
    assert completion['tool_sha256'] == manifest['measurement_tool']['executable_sha256']
    directory = root/'measurements'/completion['attempt'] if 'attempt' in completion else root/'measurements'
    assert directory.resolve().is_relative_to((root/'measurements').resolve())
    for name, key in [('dataset.json','dataset_sha256'), ('verification.json','verification_sha256'),
                      ('unique-measurements.json','unique_measurements_sha256')]:
        assert digest(directory/name) == completion[key]
    proofs = read(directory/'verification.json')
    assert len(proofs) == 1 and proofs[0]['verified'] is True
    assert proofs[0]['formula_count'] == 79 and proofs[0]['vectors_per_formula'] == 2148
    assert proofs[0]['total_comparisons'] == 79*2148
    truth, labels = aligned(rows, read(directory/'dataset.json'), 'lut4_count')
    unique = read(directory/'unique-measurements.json')
    assert len(unique) == len({r['formula'] for r in unique}) == 79
    unique_lookup = {r['formula']: r for r in unique}
    assert set(unique_lookup) == {r['formula'] for r in rows}
    for row, source in zip(rows, labels):
        measured = unique_lookup[row['formula']]
        assert source['correctness_verified'] is True and source['measurement_source'] == 'rtl_synthesis'
        assert source['stratum'] == row['family'] and int(source['lut4_count']) == source['lut4_count']
        assert source['lut4_count'] == measured['ice40_lut4_count']
        assert source['carry_count'] == measured['ice40_carry_count']
        assert source['rtl_sha256'] == measured['rtl_sha256']
        assert measured['tool'] == completion['tool'] and measured['tool_sha256'] == completion['tool_sha256']
        assert timestamp(measured['measured_at_utc']) >= timestamp(release['released_at_utc'])
    first = {}
    for i,r in enumerate(rows):
        first.setdefault(r['formula'], i)
    unique_indices = np.array(list(first.values()))
    score = read(root/'evaluation.json')
    assert score['freeze_sha256'] == digest(root/'freeze.json')
    assert score['primary'] == manifest['primary'] and score['primary_comparison'] == manifest['primary_comparison']
    models, estimates, bound_diagnostics = {}, {}, {}
    families = np.array([r['family'] for r in rows])
    for name in MODELS:
        p = np.array([r['predicted_lut4'] for r in predictions[name]])
        estimates[name] = p
        reconstructed = {scope: scoped_metrics(rows, truth, p, mask) for scope,mask in masks.items()}
        reconstructed['unique_formula_pooled_secondary'] = scalar_metrics(truth[unique_indices], p[unique_indices])
        reconstructed['candidate_errors'] = [{**r, 'lut4_count': float(y), 'predicted_lut4': float(estimate),
            'absolute_error_lut4': float(abs(y-estimate))} for r,y,estimate in zip(rows,truth,p)]
        match(reconstructed, score['models'][name], name)
        models[name] = reconstructed
        if name in MATCHED:
            schema = read(root/manifest['models'][name]['schema']['path'])
            margin = schema['calibration']['upper_margin_lut4']
            bound_diagnostics[name] = {scope: {'all_selected': uncertainty(rows, predictions[name], mask, truth, margin),
                'by_family': {f: uncertainty(rows, predictions[name], mask & (families == f), truth, margin)
                              for f in FAMILIES}} for scope,mask in masks.items()}
            fields = official_bound_fields(rows, predictions[name], truth)
            match(fields, score['models'][name]['frozen_bound_diagnostics'], name+'.bound_diagnostics')
            models[name]['frozen_bound_diagnostics'] = fields
    comparisons = {}
    for scope in masks:
        full = models['dual_semantics'][scope]['macro_family_mae_lut4']
        sog = models['sog_tuned'][scope]['macro_family_mae_lut4']
        difference = None if full is None or sog is None else full-sog
        comparisons[scope] = {'macro_family_mae_difference_lut4': difference}
        match(comparisons[scope], score['paired_comparisons'][scope], 'comparison.'+scope)
    raw_audit = None
    if raw_generated_root is not None:
        from isaforge.rtl import generate_rtl
        for formula, measured in unique_lookup.items():
            folder = raw_generated_root/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
            for file, field in [('candidate.v','rtl_sha256'), ('ice40.ys','script_sha256'),
                                ('ice40.log','log_sha256'), ('ice40-netlist.json','netlist_sha256')]:
                assert digest(folder/file) == measured[field], folder/file
            assert hashlib.sha256(generate_rtl(formula).encode()).hexdigest() == measured['rtl_sha256']
            netlist = read(folder/'ice40-netlist.json')
            counts = Counter(c['type'] for c in netlist['modules']['candidate'].get('cells',{}).values())
            assert counts.get('SB_LUT4',0) == measured['ice40_lut4_count']
            assert counts.get('SB_CARRY',0) == measured['ice40_carry_count']
        raw_audit = {'unique_netlists_recounted': 79, 'raw_resource_and_hash_checks_passed': True}
    return {'status': 'passed', 'source_sha256': digest(__file__), 'input_structure': structure,
        'freeze_commit': release['freeze_commit'], 'frozen_files_verified_against_commit': len(files),
        'evaluation_sha256': digest(root/'evaluation.json'), 'models': models,
        'paired_comparisons': comparisons, 'independent_bound_diagnostics': bound_diagnostics,
        'raw_audit': raw_audit, 'limits': structure['limits']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--v5-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--after-release', action='store_true')
    parser.add_argument('--raw-generated-root', type=Path)
    args = parser.parse_args()
    assert not args.raw_generated_root or args.after_release
    root, v5_root = args.root.resolve(), args.v5_root.resolve()
    result = audit_released(root, v5_root, raw_generated_root=args.raw_generated_root) if args.after_release else audit_inputs(root, v5_root)[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': result['status'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()

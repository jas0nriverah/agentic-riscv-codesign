#!/usr/bin/env python3
"""Independent V5 statistical reconstruction; input-only unless release is explicit.

Never imports the evaluator or invokes synthesis/feature extraction/fitting.
The release-scoring option is for use only after the parent authorizes release.
Trusted model artifacts can then be read to replay calibration predictions on
already frozen features; no labels or observations are changed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

SCOPES = ('known_families', 'unseen_compositions')
MODELS = {'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics', 'masterrtl_fixed', 'v4_frozen'}
MATCHED = {'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics'}
CAPS = (16, 32, 64, 128, 256)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    assert value.tzinfo is not None and value.utcoffset().total_seconds() == 0
    return value


def match(actual, recorded, location):
    """Compare numeric reconstructions and every explicitly supplied nested key."""
    if isinstance(actual, dict):
        assert isinstance(recorded, dict), location
        for name, value in actual.items():
            assert name in recorded, f'{location}.{name} absent'
            match(value, recorded[name], f'{location}.{name}')
    elif isinstance(actual, list):
        assert len(actual) == len(recorded), location
        for i, (a, b) in enumerate(zip(actual, recorded)):
            match(a, b, f'{location}[{i}]')
    elif isinstance(actual, float):
        assert isinstance(recorded, (int, float)) and math.isclose(actual, recorded, abs_tol=1e-8, rel_tol=1e-10), (location, actual, recorded)
    else:
        assert actual == recorded, (location, actual, recorded)


def aligned(candidates, rows, field):
    index = {(r['benchmark'], r['candidate_id']): r for r in rows}
    assert len(index) == len(rows) == len(candidates)
    expected = {(r['benchmark'], r['candidate_id']) for r in candidates}
    assert set(index) == expected
    ordered = [index[(r['benchmark'], r['candidate_id'])] for r in candidates]
    assert all(r['formula'] == c['formula'] for r, c in zip(ordered, candidates))
    assert all(not isinstance(r[field], bool) and isinstance(r[field], (int, float)) and
               math.isfinite(r[field]) and r[field] >= 0 for r in ordered)
    return np.asarray([r[field] for r in ordered], dtype=float), ordered


def scalar_metrics(truth, prediction):
    error = np.abs(prediction - truth)
    positive = truth > 0
    zeros = ~positive
    relative = error[positive] / truth[positive] * 100
    cap_metrics = {}
    for cap in CAPS:
        truly_ok, predicted_ok = truth <= cap, prediction <= cap
        ta = int(np.count_nonzero(truly_ok & predicted_ok))
        tr = int(np.count_nonzero(~truly_ok & ~predicted_ok))
        fa = int(np.count_nonzero(~truly_ok & predicted_ok))
        fr = int(np.count_nonzero(truly_ok & ~predicted_ok))
        cap_metrics[str(cap)] = {
            'true_accept_count': ta, 'true_reject_count': tr,
            'false_accept_count': fa, 'false_reject_count': fr,
            'true_feasible_count': ta+fr, 'true_infeasible_count': tr+fa,
            'predicted_feasible_count': ta+fa,
            'false_accept_rate_among_true_infeasible': fa/(tr+fa) if tr+fa else None,
            'false_reject_rate_among_true_feasible': fr/(ta+fr) if ta+fr else None,
            'infeasible_fraction_among_predicted_feasible': fa/(ta+fa) if ta+fa else None}
    return {'sample_count': len(truth), 'mae_lut4': float(sum(error)/len(error)),
        'rmsle': float(math.sqrt(sum((np.log1p(truth)-np.log1p(prediction))**2)/len(truth))),
        'positive_mape_percent': float(np.mean(relative)) if len(relative) else None,
        'positive_median_ape_percent': float(np.median(relative)) if len(relative) else None,
        'positive_count': int(positive.sum()), 'zero_count': int(zeros.sum()),
        'zero_target_mae_lut4': float(error[zeros].mean()) if zeros.any() else None,
        'cap_feasibility': cap_metrics, 'signed_bias_lut4': float((prediction-truth).mean()),
        'absolute_error_quantiles': {str(q): float(np.quantile(error, q)) for q in (.5, .9, .95, .99)},
        'maximum_underprediction_lut4': float(np.maximum(truth-prediction, 0).max())}


def bootstrap_difference(difference, strata, clusters, replicates=10000):
    """Independently aggregate cluster draw multiplicities with matrix products."""
    cluster_names, stratum_names = sorted(set(clusters)), sorted(set(strata))
    totals = np.zeros((len(cluster_names), len(stratum_names)))
    numbers = np.zeros_like(totals)
    for i, cluster in enumerate(cluster_names):
        for j, stratum in enumerate(stratum_names):
            subset = (clusters == cluster) & (strata == stratum)
            totals[i, j] = np.sum(difference[subset])
            numbers[i, j] = np.count_nonzero(subset)
    generator = np.random.default_rng(2026101418)
    samples, attempts = [], 0
    identity = np.eye(len(cluster_names), dtype=int)
    while len(samples) < replicates and attempts < 100*replicates:
        batch = min(512, replicates-len(samples), 100*replicates-attempts)
        choices = generator.integers(0, len(cluster_names), (batch, len(cluster_names)))
        multiplicity = identity[choices].sum(axis=1)
        denominators, numerators = multiplicity@numbers, multiplicity@totals
        valid = np.min(denominators, axis=1) > 0
        samples.extend(np.mean(numerators[valid]/denominators[valid], axis=1).tolist())
        attempts += batch
    assert len(samples) == replicates, 'Empty-stratum bootstrap retry budget exhausted'
    return {'macro_stratum_mae_difference_lut4': float(np.mean([difference[strata == s].mean() for s in stratum_names])),
        'descriptive_cluster_bootstrap_95_interval': np.quantile(samples, [.025, .975]).tolist(),
        'replicates': replicates, 'cluster_count': len(cluster_names), 'attempts': attempts,
        'empty_stratum_draws_rejected': attempts-replicates, 'seed': 2026101418,
        'cluster_sizes': {c: int(np.count_nonzero(clusters == c)) for c in cluster_names},
        'v5_smaller_absolute_error_count': int(np.count_nonzero(difference < 0)),
        'equal_absolute_error_count': int(np.count_nonzero(difference == 0)),
        'v5_larger_absolute_error_count': int(np.count_nonzero(difference > 0))}


def input_structure(root):
    """Use only candidate strings, frozen feature records and split identities."""
    candidates = read(root/'corpus/test/candidates.json')
    records = read(root/'test-features.json')['records']
    assert len(candidates) == len(records) == 256
    assert not any('lut4_count' in r for r in candidates+records)
    clusters = read(root/'test-clusters.json')['component_by_formula']
    by_scope = {}
    for scope in SCOPES:
        selected = [r for r in candidates if r['evaluation_scope'] == scope]
        sizes = Counter(clusters[r['formula']] for r in selected)
        by_stratum = {s: len({clusters[r['formula']] for r in selected if r['stratum'] == s})
                      for s in sorted({r['stratum'] for r in selected})}
        by_scope[scope] = {'candidate_count': len(selected), 'cluster_count': len(sizes),
            'cluster_size_distribution': dict(sorted(Counter(sizes.values()).items())),
            'clusters_per_stratum': by_stratum,
            'strata_with_one_cluster': [s for s, count in by_stratum.items() if count == 1]}
    split = read(root/'split.json')
    fit = split['fit_indices']
    calibration = split['calibration_indices']
    return {'mode': 'input-only; test labels not accessed', 'test_candidate_sha256': digest(root/'corpus/test/candidates.json'),
        'by_scope': by_scope, 'fit_count': len(fit), 'calibration_count': len(calibration),
        'fit_group_count': split['fit_group_count'], 'calibration_group_count': split['calibration_group_count'],
        'limitations': ['Synthetic compositions do not measure application transfer.',
            'One family in a stratum cannot estimate variation between unseen families.',
            'Curated strata and rejected empty bootstrap draws condition descriptive uncertainty.']}


def audit_released(root, *, replay_calibration=False):
    manifest = read(root/'freeze.json')
    assert manifest['primary'] == 'unseen_compositions macro-stratum MAE'
    assert manifest['primary_comparison'] == 'dual_semantics minus sog_tuned'
    assert set(manifest['models']) == MODELS
    frozen = timestamp(manifest['frozen_at_utc'])
    for record in manifest['files']:
        assert digest((root/record['path']).resolve()) == record['sha256'], record['path']
    release = read(root/'label-release.json')
    assert release['freeze_sha256'] == digest(root/'freeze.json')
    assert release['candidate_sha256'] == manifest['test_candidate_sha256']
    assert timestamp(release['released_at_utc']) > frozen
    completion = read(root/'corpus/test/completion.json')
    assert completion['complete'] is True and completion['measured_count'] == 256 and not completion['failures']
    assert completion['release'] == release
    for filename, key in [('candidates.json', 'candidate_sha256'), ('dataset.json', 'dataset_sha256'),
                          ('verification.json', 'verification_sha256')]:
        assert digest(root/'corpus/test'/filename) == completion[key]
    candidates = read(root/'corpus/test/candidates.json')
    truth, labeled = aligned(candidates, read(root/'corpus/test/dataset.json'), 'lut4_count')
    assert all(r['correctness_verified'] is True and r['measurement_source'] == 'rtl_synthesis'
               and r['stratum'] == c['stratum'] and int(r['lut4_count']) == r['lut4_count']
               for r, c in zip(labeled, candidates))
    score = read(root/'evaluation.json')
    assert score['freeze_sha256'] == digest(root/'freeze.json')
    assert score['primary'] == manifest['primary'] and score['primary_comparison'] == manifest['primary_comparison']
    strata = np.array([r['stratum'] for r in candidates])
    scopes = np.array([r['evaluation_scope'] for r in candidates])
    cluster_map = read(root/'test-clusters.json')['component_by_formula']
    clusters = np.array([cluster_map[r['formula']] for r in candidates])
    split = read(root/'split.json')
    calibration_indices = split['calibration_indices']
    development_features = read(root/'development-features.json') if replay_calibration else None
    development_rows = read(root/'development-data.json') if replay_calibration else None
    if replay_calibration:
        import joblib
        sys.path.insert(0, str(root.parents[1]))
    estimates, models, calibration_checks = {}, {}, {}
    for name, entry in sorted(manifest['models'].items()):
        for item in ('artifact', 'schema', 'predictions'):
            assert digest((root/entry[item]['path']).resolve()) == entry[item]['sha256']
        assert timestamp(entry['frozen_at_utc']) <= frozen
        prediction, prediction_rows = aligned(candidates, read(root/entry['predictions']['path']), 'predicted_lut4')
        estimates[name] = prediction
        independent = {'all': scalar_metrics(truth, prediction), 'by_scope': {}}
        for scope in SCOPES:
            subset = scopes == scope
            cell = scalar_metrics(truth[subset], prediction[subset])
            cell['by_stratum'] = {s: scalar_metrics(truth[subset & (strata == s)], prediction[subset & (strata == s)])
                                 for s in sorted(set(strata))}
            cell['macro_stratum_mae_lut4'] = float(np.mean([c['mae_lut4'] for c in cell['by_stratum'].values()]))
            if name in MATCHED:
                bound = np.array([np.inf if r['upper_lut4'] is None else r['upper_lut4'] for r in prediction_rows])
                covered = truth <= bound
                finite = np.isfinite(bound[subset])
                cell['upper_bound'] = {
                    'candidate_coverage': float(covered[subset].mean()),
                    'whole_component_coverage': float(np.mean([all(covered[subset & (clusters == c)]) for c in set(clusters[subset])])),
                    'finite_fraction': float(finite.mean()),
                    'mean_upper_minus_target_lut4': float((bound[subset]-truth[subset]).mean()) if finite.all() else None}
                for s, stratum_cell in cell['by_stratum'].items():
                    chosen = subset & (strata == s)
                    stratum_cell['upper_bound_candidate_coverage'] = float(covered[chosen].mean())
                    stratum_cell['upper_bound_whole_component_coverage'] = float(np.mean([
                        all(covered[chosen & (clusters == c)]) for c in set(clusters[chosen])]))
            independent['by_scope'][scope] = cell
        match(independent, score['models'][name], name)
        errors = score['models'][name]['candidate_errors']
        assert len(errors) == 256
        for i, r in enumerate(errors):
            match({'formula': candidates[i]['formula'], 'lut4_count': float(truth[i]),
                   'predicted_lut4': float(prediction[i]), 'signed_error_lut4': float(prediction[i]-truth[i]),
                   'absolute_error_lut4': float(abs(prediction[i]-truth[i]))}, r, f'{name}.candidate[{i}]')
        models[name] = independent
        if name in MATCHED:
            schema = read(root/entry['schema']['path'])
            cal = schema['calibration']
            groups = split['component_by_formula']
            calibration_group_count = split['calibration_group_count']
            expected_rank = math.ceil((calibration_group_count+1)*(1-cal['alpha']))
            match({'group_count': calibration_group_count, 'rank': expected_rank}, cal, name+'.calibration')
            assert cal['upper_margin_lut4'] is None if expected_rank > calibration_group_count else cal['upper_margin_lut4'] >= 0
            if replay_calibration:
                obj = joblib.load(root/entry['artifact']['path'])
                matrix = np.array([r['values'] for r in development_features['records']])[calibration_indices]
                names = development_features['columns']
                if name == 'sog_tuned':
                    selected = [i for i, c in enumerate(names) if c.startswith('sog_')]
                elif name == 'original_graph':
                    selected = [i for i, c in enumerate(names) if c.startswith(('sog_', 'original_'))]
                elif name == 'dual_graph':
                    selected = [i for i, c in enumerate(names) if c.startswith(('sog_', 'original_', 'normalized_', 'absolute_channel_delta_'))]
                else:
                    selected = list(range(len(names)))
                p = np.asarray(obj.estimator.predict(matrix[:, selected]))
                if schema['configuration'].startswith('xgb_log_'):
                    p = np.expm1(p)
                p = np.maximum(p, 0)
                p[matrix[:, names.index('original_gate_count')] == 0] = 0
                y = np.array([development_rows[i]['lut4_count'] for i in calibration_indices])
                group_names = np.array([groups[development_rows[i]['formula']] for i in calibration_indices])
                maxima = sorted(max((y-p)[group_names == g]) for g in set(group_names))
                margin = None if expected_rank > len(maxima) else max(0., float(maxima[expected_rank-1]))
                match({'upper_margin_lut4': margin}, cal, name+'.calibration')
                calibration_checks[name] = {'group_count': len(maxima), 'rank': expected_rank,
                    'margin_lut4': margin, 'full_residual_quantile_replayed': True}
            else:
                calibration_checks[name] = {'group_count': calibration_group_count, 'rank': expected_rank,
                    'margin_lut4': cal['upper_margin_lut4'], 'full_residual_quantile_replayed': False}
    comparisons = {}
    for scope in SCOPES:
        subset = scopes == scope
        comparisons[scope] = {}
        for name in sorted(MODELS-{'dual_semantics'}):
            delta = np.abs(estimates['dual_semantics']-truth)-np.abs(estimates[name]-truth)
            paired = bootstrap_difference(delta[subset], strata[subset], clusters[subset])
            match(paired, score['paired_comparisons'][scope][name], 'paired.'+scope+'.'+name)
            comparisons[scope][name] = paired
    return {'status': 'passed', 'source_sha256': digest(__file__),
        'evaluation_sha256': digest(root/'evaluation.json'), 'models': models,
        'paired_comparisons': comparisons, 'calibration_checks': calibration_checks,
        'input_structure': input_structure(root), 'primary_comparison': comparisons['unseen_compositions']['sog_tuned'],
        'limits': ['Independent scalar/cluster reconstruction is not a raw-netlist resource audit.',
            'Curated synthetic outcomes cannot establish application or CPU performance gains.',
            'Cluster intervals are conditional descriptions; five novel strata each have one family.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--score-after-release', action='store_true')
    parser.add_argument('--replay-calibration', action='store_true')
    args = parser.parse_args()
    assert not args.replay_calibration or args.score_after_release
    result = audit_released(args.root.resolve(), replay_calibration=args.replay_calibration) if args.score_after_release else input_structure(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': result.get('status', 'input-only complete'), 'output': str(args.output)}))


if __name__ == '__main__':
    main()

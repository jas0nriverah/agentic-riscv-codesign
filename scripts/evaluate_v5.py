#!/usr/bin/env python3
"""Score every frozen V5 predictor; no fitting or hardware feature extraction."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from evaluate_v4 import aligned, metrics, utc

MODELS = {'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics', 'masterrtl_fixed', 'v4_frozen'}
SCOPES = ('known_families', 'unseen_compositions')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(record, root):
    path = (root/record['path']).resolve()
    if sha(path) != record['sha256']:
        raise ValueError(f'Frozen file changed: {path}')
    return path


def validate_freeze(root):
    root = Path(root).resolve()
    manifest = read(root/'freeze.json')
    if manifest['schema'] != 'isaforge-v5-freeze-v1' or set(manifest['models']) != MODELS:
        raise ValueError('Incomplete V5 freeze')
    frozen_time = utc(manifest['frozen_at_utc'])
    paths = [checked(r, root) for r in manifest['files']]
    required = [root/name for name in ('input-seal.json', 'test-clusters.json', 'development-data.json',
                'development-features.json', 'test-features.json', 'split.json',
                'training-start.json', 'development-evaluation.json',
                'corpus/test/candidates.json', 'corpus/test/freeze.json',
                'corpus/development/completion.json', 'corpus/development/verification.json')]
    required += [Path(__file__).with_name(name) for name in ('train_v5.py', 'measure_v5.py')]
    required += [Path(__file__).resolve().parents[1]/'docs/v5-protocol.md']
    if not {p.resolve() for p in required} <= set(paths):
        raise ValueError('Manifest omits a required frozen input')
    if Path(__file__).resolve() not in paths or Path(__file__).with_name('evaluate_v4.py').resolve() not in paths:
        raise ValueError('Evaluator implementation must be frozen')
    candidates = read(root/'corpus/test/candidates.json')
    if (len(candidates) != 256 or len({r['formula'] for r in candidates}) != 256
            or sha(root/'corpus/test/candidates.json') != manifest['test_candidate_sha256']):
        raise ValueError('Changed test pool')
    strata = sorted({r['stratum'] for r in candidates})
    if len(strata) != 8:
        raise ValueError('Expected eight strata')
    for scope in SCOPES:
        for stratum in strata:
            if sum(r['evaluation_scope'] == scope and r['stratum'] == stratum for r in candidates) != 16:
                raise ValueError('Expected16 examples per scope/stratum')
    seal = read(root/'input-seal.json')
    if seal['status'] != 'sealed' or seal['cross_cohort_component_count'] != 0:
        raise ValueError('Input independence seal required')
    cluster_map = read(root/'test-clusters.json')['component_by_formula']
    if set(cluster_map) != {r['formula'] for r in candidates}:
        raise ValueError('Test cluster partition incomplete')
    development = read(root/'development-data.json')
    if (len(development) != 2057 or len({r['formula'] for r in development}) != 2057
            or {r['formula'] for r in development} & {r['formula'] for r in candidates}):
        raise ValueError('Development count/overlap failure')
    split = read(root/'split.json')
    fit, calibration = split['fit_indices'], split['calibration_indices']
    if len(set(fit)) != len(fit) or len(set(calibration)) != len(calibration) or set(fit) & set(calibration) or set(fit+calibration) != set(range(len(development))):
        raise ValueError('Invalid fitting/calibration partition')
    components = split['component_by_formula']
    if {components[development[i]['formula']] for i in fit} & {components[development[i]['formula']] for i in calibration}:
        raise ValueError('Calibration component leakage')
    start = read(root/'training-start.json')
    if not utc(read(root/'corpus/test/freeze.json')['frozen_at_utc']) <= utc(start['started_at_utc']) <= frozen_time:
        raise ValueError('Invalid candidate/training/bundle chronology')
    for name, digest in start['sources'].items():
        path = Path(__file__).resolve().parents[1]/'isaforge'/name
        if path not in paths or sha(path) != digest:
            raise ValueError('Training runtime source not frozen')
    for r in start['dataset_sources']:
        checked(r, root)
    predictions = {}
    for name, entry in manifest['models'].items():
        if not utc(start['started_at_utc']) <= utc(entry['frozen_at_utc']) <= frozen_time:
            raise ValueError('Prediction freeze occurs after bundle freeze')
        checked(entry['artifact'], root)
        checked(entry['schema'], root)
        predictions[name] = read(checked(entry['predictions'], root))
        aligned(candidates, predictions[name], 'predicted_lut4')
        if name in {'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics'}:
            schema = read(checked(entry['schema'], root))
            if (schema['artifact_sha256'] != entry['artifact']['sha256']
                    or schema['runtime_source_sha256'] != start['sources']
                    or schema['view'] != name or schema['training_formula_count'] != len(fit)):
                raise ValueError('Model schema disagrees with frozen training or artifact')
            margin = schema['calibration']['upper_margin_lut4']
            if margin is not None and (isinstance(margin, bool) or not isinstance(margin, (int, float)) or not np.isfinite(margin) or margin < 0):
                raise ValueError('Invalid schema calibration margin')
            for row in predictions[name]:
                upper = row['upper_lut4']
                if ((margin is None and upper is not None) or (margin is not None and
                    (upper is None or isinstance(upper, bool) or not isinstance(upper, (int, float)) or not np.isfinite(upper)
                     or upper != row['predicted_lut4']+margin))):
                    raise ValueError('Invalid upper prediction bound')
    return manifest, candidates, predictions, seal


def extended_metrics(y, p):
    error = abs(y-p)
    return {**metrics(y, p), 'signed_bias_lut4': float((p-y).mean()),
            'absolute_error_quantiles': {str(q): float(np.quantile(error, q)) for q in (.5, .9, .95, .99)},
            'maximum_underprediction_lut4': float(max(0., max(y-p)))}


def paired_clusters(difference, strata, components, replicates=10000):
    """Global cluster bootstrap with fixed macro-stratum weighting.

    Empty-stratum draws are discarded and redrawn, with attempts reported. If
    fewer than requested valid replicates exist after100x attempts, fail closed.
    """
    difference, strata, components = np.asarray(difference), np.asarray(strata), np.asarray(components)
    if (difference.ndim != 1 or strata.ndim != 1 or components.ndim != 1
            or len(difference) == 0 or len(difference) != len(strata) or len(difference) != len(components)
            or not np.isfinite(difference).all()
            or isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1):
        raise ValueError('Bootstrap requires aligned finite data and positive integer replicates')
    unique = sorted(set(components))
    names = sorted(set(strata))
    sums = np.zeros((len(unique), len(names)))
    counts = np.zeros_like(sums)
    for i, component in enumerate(unique):
        for j, stratum in enumerate(names):
            selected = (components == component) & (strata == stratum)
            sums[i, j] = difference[selected].sum()
            counts[i, j] = selected.sum()
    rng = np.random.default_rng(2026101418)
    samples, attempts = [], 0
    while len(samples) < replicates and attempts < 100*replicates:
        chosen = rng.integers(0, len(unique), size=(min(512, replicates-len(samples), 100*replicates-attempts), len(unique)))
        denominators = counts[chosen].sum(axis=1)
        numerators = sums[chosen].sum(axis=1)
        valid = np.all(denominators > 0, axis=1)
        samples.extend(np.mean(numerators[valid]/denominators[valid], axis=1).tolist())
        attempts += len(chosen)
    if len(samples) != replicates:
        raise ValueError('Insufficient nonempty-stratum bootstrap draws')
    return {'macro_stratum_mae_difference_lut4': float(np.mean([difference[strata == s].mean() for s in names])),
            'descriptive_cluster_bootstrap_95_interval': np.quantile(samples, [.025, .975]).tolist(),
            'replicates': replicates, 'cluster_count': len(unique), 'attempts': attempts,
            'empty_stratum_draws_rejected': attempts-replicates, 'seed': 2026101418,
            'cluster_sizes': {c: int(np.sum(components == c)) for c in unique},
            'scope': 'post-freeze descriptive cluster resampling, conditional on curated strata'}


def evaluate(root):
    root = Path(root).resolve()
    manifest, candidates, predictions, seal = validate_freeze(root)
    release = read(root/'label-release.json')
    if (release['freeze_sha256'] != sha(root/'freeze.json')
            or release['candidate_sha256'] != manifest['test_candidate_sha256']
            or utc(release['released_at_utc']) <= utc(manifest['frozen_at_utc'])):
        raise ValueError('Labels require a valid release after model freeze')
    completion = read(root/'corpus/test/completion.json')
    if completion['complete'] is not True or completion['measured_count'] != 256 or completion['failures']:
        raise ValueError('Test measurements incomplete')
    if completion['release'] != release or completion['collector_sha256'] != sha(Path(__file__).with_name('measure_v5.py')):
        raise ValueError('Measurement provenance differs from frozen release or collector')
    for filename, key in [('candidates.json', 'candidate_sha256'), ('dataset.json', 'dataset_sha256'), ('verification.json', 'verification_sha256')]:
        if sha(root/'corpus/test'/filename) != completion[key]:
            raise ValueError('Test artifact differs from completion')
    y = aligned(candidates, read(root/'corpus/test/dataset.json'), 'lut4_count', measured=True)
    strata = np.asarray([r['stratum'] for r in candidates])
    scopes = np.asarray([r['evaluation_scope'] for r in candidates])
    cluster_record = read(root/'test-clusters.json')
    cluster_map = cluster_record['component_by_formula']
    if set(cluster_map) != {r['formula'] for r in candidates}:
        raise ValueError('Test cluster partition incomplete')
    components = np.asarray([cluster_map[r['formula']] for r in candidates])
    estimates = {n: aligned(candidates, rows, 'predicted_lut4') for n, rows in predictions.items()}
    result = {'schema': 'isaforge-v5-evaluation-v1', 'evaluated_at_utc': datetime.now(timezone.utc).isoformat(),
              'freeze_sha256': sha(root/'freeze.json'), 'models': {}, 'paired_comparisons': {},
              'primary': manifest['primary'], 'primary_comparison': manifest['primary_comparison'],
              'test_cluster_definition': cluster_record['definition'],
              'scope': 'synthetic isolated original-RTL LUT4 prediction; not CPU or acquisition performance'}
    for name, p in estimates.items():
        model = {'all': extended_metrics(y, p), 'by_scope': {},
                 'candidate_errors': [{**r, 'lut4_count': float(a), 'predicted_lut4': float(b),
                                       'signed_error_lut4': float(b-a),
                                       'absolute_error_lut4': float(abs(a-b))} for r, a, b in zip(candidates, y, p)]}
        indexed = {r['formula']: r for r in predictions[name]}
        for scope in SCOPES:
            ix = scopes == scope
            entry = extended_metrics(y[ix], p[ix])
            entry['by_stratum'] = {s: extended_metrics(y[ix & (strata == s)], p[ix & (strata == s)]) for s in sorted(set(strata))}
            entry['macro_stratum_mae_lut4'] = float(np.mean([v['mae_lut4'] for v in entry['by_stratum'].values()]))
            if name in {'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics'}:
                bounds = np.asarray([np.inf if indexed[r['formula']]['upper_lut4'] is None else indexed[r['formula']]['upper_lut4'] for r in candidates])
                covered = y <= bounds
                finite = np.isfinite(bounds[ix])
                entry['upper_bound'] = {'candidate_coverage': float(covered[ix].mean()),
                    'whole_component_coverage': float(np.mean([covered[ix & (components == c)].all() for c in set(components[ix])])),
                    'finite_fraction': float(finite.mean()),
                    'mean_upper_minus_target_lut4': float((bounds[ix]-y[ix]).mean()) if finite.all() else None,
                    'assumption': 'complete-group exchangeability; unestablished under composition shift'}
                for stratum, cell in entry['by_stratum'].items():
                    selected = ix & (strata == stratum)
                    cell['upper_bound_candidate_coverage'] = float(covered[selected].mean())
                    cell['upper_bound_whole_component_coverage'] = float(np.mean([
                        covered[selected & (components == c)].all() for c in set(components[selected])]))
            model['by_scope'][scope] = entry
        result['models'][name] = model
    for scope in SCOPES:
        ix = scopes == scope
        result['paired_comparisons'][scope] = {}
        for name, p in estimates.items():
            if name == 'dual_semantics':
                continue
            delta = abs(estimates['dual_semantics']-y)-abs(p-y)
            result['paired_comparisons'][scope][name] = paired_clusters(delta[ix], strata[ix], components[ix])
            result['paired_comparisons'][scope][name].update({
                'v5_smaller_absolute_error_count': int(np.sum(delta[ix] < 0)),
                'equal_absolute_error_count': int(np.sum(delta[ix] == 0)),
                'v5_larger_absolute_error_count': int(np.sum(delta[ix] > 0))})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('results/2026-10-14-v5'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({n: {s: m['by_scope'][s]['mae_lut4'] for s in SCOPES} for n, m in result['models'].items()}, indent=2))

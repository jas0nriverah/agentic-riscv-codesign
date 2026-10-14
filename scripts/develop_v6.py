#!/usr/bin/env python3
"""Fitting-only V6 seed diagnostics; never read calibration/test outcomes.

Reuses the frozen V5 fitting rows/folds. Scores are development evidence
designed after V5 results were inspected, not a new independent model test.
Outputs must be outside this repository and never overwrite an existing run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits

from isaforge.area_model import _versions
from isaforge.area_model_v5 import columns, original_zero, source_hashes, view_indices

VIEWS = ('original_graph', 'dual_graph', 'dual_semantics')
SEEDS = tuple(range(2026101421, 2026101426))


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def fold_plan(fit_indices, validation_indices, groups):
    """Validate complete fitting-only folds, including component disjointness."""
    fitting = list(fit_indices)
    if len(fitting) != len(set(fitting)) or len(validation_indices) != 5:
        raise ValueError('Expected unique fitting rows and five frozen folds')
    valid_rows = [i for fold in validation_indices for i in fold]
    if len(valid_rows) != len(set(valid_rows)) or set(valid_rows) != set(fitting):
        raise ValueError('Frozen validation folds must partition fitting rows only')
    positions = {index: i for i, index in enumerate(fitting)}
    plan = []
    for validation in validation_indices:
        train = [i for i in fitting if i not in set(validation)]
        if not validation or not train:
            raise ValueError('Every fold needs training and validation rows')
        if {groups[i] for i in train} & {groups[i] for i in validation}:
            raise ValueError('Component crosses training and validation')
        plan.append((np.array([positions[i] for i in train]),
                     np.array([positions[i] for i in validation])))
    return plan


def metrics(y, prediction, strata):
    error = prediction-y
    def cell(mask):
        actual, residual = y[mask], error[mask]
        return {'count': int(mask.sum()), 'mae_lut4': float(np.abs(residual).mean()),
            'signed_bias_lut4': float(residual.mean()),
            'median_absolute_error_lut4': float(np.median(np.abs(residual))),
            'p95_absolute_error_lut4': float(np.quantile(np.abs(residual), .95)),
            'maximum_underprediction_lut4': float(np.maximum(-residual, 0).max()),
            'underprediction_count': int((residual < 0).sum()),
            'overprediction_count': int((residual > 0).sum()),
            'exact_prediction_count': int((residual == 0).sum())}
    grouped = {s: cell(strata == s) for s in sorted(set(strata))}
    return {'mae_lut4': float(np.abs(error).mean()),
            'macro_stratum_mae_lut4': float(np.mean([v['mae_lut4'] for v in grouped.values()])),
            'rmsle': float(np.sqrt(np.mean((np.log1p(prediction)-np.log1p(y))**2))),
            'by_stratum': grouped}


@threadpool_limits.wrap(limits=1)
def run(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Development results must be outside the frozen repository')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Existing development run cannot be overwritten')
    inputs = [root/'development-data.json', root/'development-features.json', root/'split.json']
    manifest = read(root/'freeze.json')
    frozen_records = {(root/r['path']).resolve(): r['sha256'] for r in manifest['files']}
    if any(p not in frozen_records or sha(p) != frozen_records[p] for p in inputs):
        raise ValueError('Frozen development input hashes differ')
    snapshot = source_hashes()
    frozen_sources = read(root/'training-start.json')['sources']
    if snapshot != frozen_sources:
        raise ValueError('V5 runtime sources changed')
    all_rows, features, split = (read(p) for p in inputs)
    if tuple(features['columns']) != columns():
        raise ValueError('Frozen feature schema differs')
    if len(all_rows) != len(features['records']) or any(a['formula'] != b['formula']
            for a, b in zip(all_rows, features['records'])):
        raise ValueError('Development rows/features are misaligned')
    fit = split['fit_indices']
    calibration = set(split['calibration_indices'])
    if set(fit) & calibration or len(fit) != 1665:
        raise ValueError('Expected the exact 1665 fitting rows without calibration')
    rows = [all_rows[i] for i in fit]
    x = np.asarray([features['records'][i]['values'] for i in fit], dtype=float)
    y = np.asarray([all_rows[i]['lut4_count'] for i in fit], dtype=float)
    strata = np.asarray([all_rows[i].get('stratum', 'workload') for i in fit])
    groups = {i: split['component_by_formula'][all_rows[i]['formula']] for i in fit}
    folds = fold_plan(fit, split['fold_validation_indices'], groups)
    if not np.isfinite(x).all() or np.any(x < 0) or not np.isfinite(y).all() or np.any(y < 0):
        raise ValueError('Invalid fitting data')
    # Retain the fitting rows only. All calibration/test labels are excluded
    # from arrays, fits, metrics, seed summaries and model-direction selection.
    del all_rows, features
    write(output/'run-start.json', {'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'post-V5 fitting-only development; no independent-test claim',
        'input_sha256': {str(p): sha(p) for p in inputs}, 'v5_freeze_sha256': sha(root/'freeze.json'),
        'runtime_source_sha256': snapshot, 'diagnostic_script_sha256': sha(__file__),
        'versions': _versions(), 'seeds': SEEDS, 'views': VIEWS, 'fit_count': len(rows),
        'calibration_rows_used': 0, 'test_rows_used': 0,
        'fitting_formula_indices': fit, 'fold_validation_indices': split['fold_validation_indices'],
        'stratum_counts': {s: int(np.sum(strata == s)) for s in sorted(set(strata))}})
    all_predictions, scored = {}, {}
    for view in VIEWS:
        indices = view_indices(view)
        values = x[:, indices]
        all_predictions[view], scored[view] = [], {}
        for seed in SEEDS:
            prediction = np.zeros(len(rows))
            timings = []
            parameters = None
            for training, validation in folds:
                began = time.perf_counter()
                model = ExtraTreesRegressor(n_estimators=300, min_samples_leaf=1,
                    max_features=1., n_jobs=1, random_state=seed)
                model.fit(values[training], y[training])
                prediction[validation] = np.maximum(model.predict(values[validation]), 0)
                timings.append(time.perf_counter()-began)
                current = model.get_params(deep=True)
                if parameters is not None and current != parameters:
                    raise ValueError('Parameters changed between folds')
                parameters = current
            prediction[original_zero(x)] = 0
            observed = metrics(y, prediction, strata)
            scored[view][str(seed)] = {**observed, 'fitted_parameters': parameters,
                'fold_fit_predict_seconds': timings, 'feature_count': len(indices)}
            all_predictions[view].append(prediction)
            write(output/'predictions'/f'{view}-seed-{seed}.json', [
                {'development_index': fit[i], 'formula': r['formula'], 'stratum': strata[i],
                 'lut4_count': float(y[i]), 'predicted_lut4': float(prediction[i]),
                 'signed_error_lut4': float(prediction[i]-y[i])} for i, r in enumerate(rows)])
            write(output/'metrics'/f'{view}-seed-{seed}.json', scored[view][str(seed)])
            print(view, seed, f"macro-MAE={observed['macro_stratum_mae_lut4']:.6f}", flush=True)
    summary = {'scope': 'fitting-only CV across five seeds; exploratory post-V5 development',
        'all_configurations': scored, 'by_view': {}, 'paired_seed_differences': {},
        'limits': ['OOF development scores are not independent future generalization.',
            'Five seeds estimate observed algorithm instability, not a confidence interval.',
            'Calibration/test labels are not used for fitting or selection.',
            'No V5 model replacement or repaired holdout result is produced.']}
    for view, predictions in all_predictions.items():
        matrix = np.asarray(predictions)
        maes = np.array([scored[view][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS])
        summary['by_view'][view] = {'macro_mae_mean': float(maes.mean()),
            'macro_mae_std_across_seeds': float(maes.std(ddof=1)),
            'macro_mae_min': float(maes.min()), 'macro_mae_max': float(maes.max()),
            'ensemble_oof_metrics': metrics(y, matrix.mean(0), strata),
            'prediction_seed_std_mean': float(matrix.std(0, ddof=1).mean()),
            'prediction_seed_std_p95': float(np.quantile(matrix.std(0, ddof=1), .95)),
            'stratum_seed_metrics': {s: {metric: [scored[view][str(seed)]['by_stratum'][s][metric]
                for seed in SEEDS] for metric in ('mae_lut4', 'signed_bias_lut4', 'maximum_underprediction_lut4')}
                for s in sorted(set(strata))}}
    for comparison in ('dual_graph', 'dual_semantics'):
        differences = [scored[comparison][str(seed)]['macro_stratum_mae_lut4']-
            scored['original_graph'][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS]
        summary['paired_seed_differences'][comparison+'_minus_original_graph'] = {
            'differences_lut4': differences, 'mean': float(np.mean(differences)),
            'smaller_error_seed_count': int(np.sum(np.asarray(differences) < 0)),
            'larger_error_seed_count': int(np.sum(np.asarray(differences) > 0))}
    if source_hashes() != snapshot or any(sha(p) != frozen_records[p] for p in inputs):
        raise ValueError('Sources or development data changed; run is invalid')
    write(output/'summary.json', summary)
    print(json.dumps({'output': str(output), 'fitting_rows': len(rows), 'calibration_rows_used': 0,
                      'test_rows_used': 0, 'views': summary['by_view']}, allow_nan=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.root, arguments.output)

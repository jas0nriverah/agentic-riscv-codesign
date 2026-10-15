#!/usr/bin/env python3
"""Replay all30 local V12 forests against their saved held-out points.

This never fits or recreates missing models. The large joblib artifacts are
required local evidence; the separate standard-library point/metric audit does
not substitute for loading these models and repeating inference.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
import sklearn.ensemble._forest as forest_runtime
import sklearn.tree._tree as tree_runtime
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge.area_model_v6 import estimator_fingerprint

SEEDS = (2026101421, 2026101422, 2026101423)
VIEWS = ('raw', 'log1p')
PARAMETERS = {'n_estimators': 300, 'criterion': 'squared_error',
              'min_samples_leaf': 1, 'max_features': 1.0, 'n_jobs': 1}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def runtime():
    files = [Path(sys.executable).resolve(), Path(forest_runtime.__file__).resolve(),
             Path(tree_runtime.__file__).resolve()]
    return {'python': platform.python_version(),
            'packages': {name: importlib.metadata.version(name) for name in
                         ('numpy', 'scipy', 'scikit-learn', 'joblib', 'threadpoolctl')},
            'files': [{'path': str(path), 'sha256': sha(path)} for path in files]}


def decoded_points(encoded, view, zero):
    values = np.asarray(encoded, dtype=float)
    zero = np.asarray(zero)
    need(view in VIEWS and values.shape == zero.shape and zero.dtype == np.dtype(bool)
         and np.isfinite(values).all(), 'Matched finite encoded values and boolean zero mask required')
    with np.errstate(over='raise', invalid='raise'):
        before = np.maximum(np.expm1(values) if view == 'log1p' else values, 0)
    need(np.isfinite(before).all(), 'Decoded prediction overflow')
    points = before.copy()
    points[zero] = 0
    return before, points


@contextmanager
def no_fitting():
    original = ExtraTreesRegressor.fit
    def forbidden(*args, **kwargs):
        raise RuntimeError('Model inference replay must never fit')
    ExtraTreesRegressor.fit = forbidden
    try:
        yield
    finally:
        ExtraTreesRegressor.fit = original


def run(root):
    root = Path(root).resolve()
    attempt = root / 'fit-attempt-0000'
    done = read(attempt / 'completion.json')
    need(done.get('schema') == 'isaforge-v12-fit-completion-v1' and done.get('complete') is True
         and done.get('error') is None
         and all(type(done.get(key)) is int and done[key] == 30 for key in
                 ('fits_attempted', 'fits_completed', 'maximum_fits')), 'Complete exact30-fit attempt required')
    prep_path = root / 'preparation.json'
    prep = read(prep_path)
    need(sha(prep_path) == done['preparation_sha256'], 'Completed preparation digest differs')
    bindings = {(root / entry['path']).resolve(): entry['sha256'] for entry in prep['files']}
    for name in ('fitting.json', 'matrix.npy', 'split.json', 'recipe.json', 'runtime.json'):
        path = root / name
        need(bindings.get(path) == sha(path), 'Frozen inference payload differs: ' + name)
    fingerprint_source = ROOT / 'isaforge/area_model_v6.py'
    need(bindings.get(fingerprint_source) == sha(fingerprint_source), 'Shared fingerprint source differs')
    need(sha(attempt / 'summary.json') == done['summary_sha256'], 'Published summary differs')
    recipe = read(root / 'recipe.json')
    need(recipe['seeds'] == list(SEEDS) and recipe['target_views'] == list(VIEWS)
         and recipe['parameters'] == PARAMETERS and recipe['folds'] == 5, 'Fixed paired30-fit recipe required')
    schedule = [{'seed': seed, 'view': view, 'fold': fold, 'fit_index': index + 1}
                for index, (seed, view, fold) in enumerate(
                    (seed, view, fold) for seed in SEEDS for view in VIEWS for fold in range(5))]
    need(prep['fit_schedule'] == schedule, 'Fixed fit schedule differs')

    data = read(root / 'fitting.json')
    rows, zero = data['rows'], np.asarray(data['original_zero'])
    matrix = np.load(root / 'matrix.npy', allow_pickle=False)
    split = read(root / 'split.json')
    need(len(rows) == len({row['formula'] for row in rows}) == 1713
         and matrix.shape == (1713, 217) and matrix.dtype == np.dtype('<f4')
         and np.isfinite(matrix).all() and zero.shape == (1713,) and zero.dtype == np.dtype(bool),
         'Complete frozen1713x217 matrix/identities/zero mask required')
    fold_ids = np.asarray(split['fold_ids'])
    need(fold_ids.shape == (1713,) and set(fold_ids.tolist()) == set(range(5)), 'Complete fivefold identity required')
    recorded_runtime, current_runtime = read(root / 'runtime.json'), runtime()
    need(current_runtime['python'] == recorded_runtime['python']
         and current_runtime['packages'] == recorded_runtime['packages'], 'Use the recorded Python/package versions for exact model replay')

    forecasts, forecast_hashes, coverage = {}, {}, {}
    extra_fields = {'fold', 'original_zero', 'encoded_prediction', 'decoded_before_zero', 'predicted_lut4'}
    for seed in SEEDS:
        for view in VIEWS:
            path = attempt / 'predictions' / f'{view}-seed-{seed}.json'
            saved = read(path)
            need(len(saved) == 1713, 'Every view/seed needs all1713 held-out rows')
            for i, (record, row) in enumerate(zip(saved, rows)):
                need(set(record) == set(row) | extra_fields and all(record[key] == value for key, value in row.items())
                     and type(record['fold']) is int and record['fold'] == fold_ids[i]
                     and type(record['original_zero']) is bool and record['original_zero'] == zero[i], 'Saved forecast row/label/fold identity differs')
            forecasts[seed, view] = saved
            forecast_hashes[path.relative_to(root).as_posix()] = sha(path)
            coverage[seed, view] = np.zeros(1713, dtype=int)

    # Check existence and recorded byte hashes before unpickling any artifact.
    jobs = []
    for job in schedule:
        index, seed, view, fold = (job[key] for key in ('fit_index', 'seed', 'view', 'fold'))
        receipt = read(attempt / 'receipts' / f'{index:02d}-completed.json')
        start = read(attempt / 'receipts' / f'{index:02d}-start.json')
        need(all(receipt[key] == value and start[key] == value for key, value in job.items())
             and all(receipt[key] == value for key, value in start.items())
             and receipt['save_load_points_exact'] is True, 'Completed/start receipt identity differs')
        expected_path = attempt / 'models' / f'{index:02d}-{view}-seed-{seed}-fold-{fold}.joblib'
        artifact = (attempt / receipt['artifact']['path']).resolve()
        need(artifact == expected_path and artifact.is_file(), 'Required local model is missing; replay never recreates models: ' + str(expected_path))
        need(sha(artifact) == receipt['artifact']['sha256'] and artifact.stat().st_size == receipt['artifact_bytes'], 'Saved model byte hash/size differs')
        training, validation = np.flatnonzero(fold_ids != fold), np.flatnonzero(fold_ids == fold)
        need(receipt['training_indices'] == training.tolist() == split['folds'][fold]['training_indices']
             and receipt['validation_indices'] == validation.tolist() == split['folds'][fold]['validation_indices'], 'Model training/validation membership differs')
        need(receipt['parameters'] == {**PARAMETERS, 'random_state': seed}, 'Recorded model parameters differ')
        jobs.append((job, receipt, artifact, validation))
    need(set((attempt / 'models').glob('*.joblib')) == {job[2] for job in jobs}, 'Exactly the declared30 local models required')

    model_reports = []
    with no_fitting(), threadpool_limits(limits=1):
        for job, receipt, artifact, validation in jobs:
            model = joblib.load(artifact)
            need(type(model) is ExtraTreesRegressor, 'Unexpected saved model class')
            expected_params = ExtraTreesRegressor(**PARAMETERS, random_state=job['seed']).get_params(deep=True)
            need(model.get_params(deep=True) == expected_params and len(model.estimators_) == 300
                 and int(model.n_features_in_) == 217 and estimator_fingerprint(model) == receipt['estimator_fingerprint'], 'Fitted parameters/tree fingerprint differ')
            prediction = np.asarray(model.predict(matrix[validation]), dtype=float)
            saved = forecasts[job['seed'], job['view']]
            expected = np.asarray([saved[i]['encoded_prediction'] for i in validation], dtype=float)
            need(prediction.shape == expected.shape and np.isfinite(prediction).all()
                 and np.array_equal(prediction, expected), 'Encoded saved-model inference differs')
            before, points = decoded_points(prediction, job['view'], zero[validation])
            need(np.array_equal(before, np.asarray([saved[i]['decoded_before_zero'] for i in validation]))
                 and np.array_equal(points, np.asarray([saved[i]['predicted_lut4'] for i in validation])), 'Decoded/zero-overridden saved-model points differ')
            coverage[job['seed'], job['view']][validation] += 1
            need(sha(artifact) == receipt['artifact']['sha256'], 'Model changed during inference')
            model_reports.append({**job, 'artifact': artifact.relative_to(root).as_posix(),
                'artifact_sha256': receipt['artifact']['sha256'], 'artifact_bytes': artifact.stat().st_size,
                'estimator_fingerprint': receipt['estimator_fingerprint'], 'parameters_exact': True,
                'heldout_points_compared': len(validation), 'encoded_points_exact': True,
                'decoded_before_zero_exact': True, 'final_points_exact': True})
    need(all(np.all(count == 1) for count in coverage.values()), 'Exactly one held-out inference per row/seed/view required')
    for name, expected in forecast_hashes.items():
        need(sha(root / name) == expected, 'Saved forecast changed during replay')
    return {'schema': 'isaforge-v12-independent-local-model-inference-v1', 'status': 'pass',
        'preparation_sha256': sha(prep_path), 'completion_sha256': sha(attempt / 'completion.json'),
        'summary_sha256': done['summary_sha256'], 'script_sha256': sha(__file__),
        'fingerprint_helper_sha256': sha(fingerprint_source), 'runtime': current_runtime,
        'recorded_runtime_versions_exact': True,
        'recorded_runtime_file_hashes_exact': [entry['sha256'] for entry in current_runtime['files']] == [entry['sha256'] for entry in recorded_runtime['files']],
        'models_loaded': len(model_reports), 'model_bytes': sum(row['artifact_bytes'] for row in model_reports),
        'heldout_points_compared': sum(row['heldout_points_compared'] for row in model_reports),
        'points_per_seed_view': 1713, 'all_row_coverage_exactly_once': True,
        'models': model_reports, 'forecast_file_hashes': forecast_hashes,
        'new_fits': 0, 'new_features': 0, 'new_physical_labels': 0,
        'local_models_required': True,
        'artifact_distribution': 'These large joblib models are local evidence, not assumed to be distributed in Git. Missing files fail; this replay does not fit replacements.',
        'scope': 'Independent saved-model inference and inverse/zero-override replay over all30 fold forests. Uses shared named-state fingerprint helper. Distinct from standard-library saved-point/metric replay; no new fit, external evaluation target, native hardware job or model promotion.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New report file; never overwrite evidence')
    args = parser.parse_args()
    result = run(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('status', 'models_loaded', 'model_bytes', 'heldout_points_compared', 'recorded_runtime_file_hashes_exact')}, indent=2))

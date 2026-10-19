"""Structural resource priors with bounded, regularized residual corrections.

All existing benchmark labels are development data. Nested program holdouts
control fitting and selection leakage, but cannot make already inspected data
an independent test. Use a frozen artifact for any subsequent independent probe.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any
import warnings

import numpy as np
from scipy.optimize import lsq_linear
from scipy.stats import pearsonr
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .area_model import (_metrics, _read_rows, _unique_formulas, _validated_rows,
                         _versions, benchmark_split, save_area_model, train_area_model)
from .area_model_v2 import (FEATURE_COLUMNS as V2_FEATURE_COLUMNS,
                           RESOURCE_COLUMNS as V2_RESOURCE_COLUMNS,
                           ResourcePredictor,
                           feature_matrix as v2_feature_matrix,
                           resource_matrix as v2_resource_matrix,
                           save_model as save_v2_model,
                           train_resource_model, train_v2_model)
from .features import parse_formula
from .structural_features_v3 import (FEATURE_NAMES, RESOURCE_NAMES, RESOURCE_PRIOR,
                                     feature_dict, proven_zero_lut)

SCHEMA_VERSION = 3
SEED = 20261013
TARGET = 'isolated iCE40 mapped SB_LUT4 count'
FEATURE_SETS = ('original', 'structural')
FEATURE_COLUMNS = tuple(V2_FEATURE_COLUMNS) + tuple(FEATURE_NAMES)
# Written before seeing new probe labels. Selection uses only macro program MAE.
# The candidate grid is deliberately small; no tuning occurs on outer folds.
CONFIG_GRID = {
    'v2_resource': {'estimator': 'none', 'baseline': 'v2_resource'},
    'feature_resource': {'estimator': 'none', 'baseline': 'feature_resource'},
    'ridge_10': {'estimator': 'ridge', 'alpha': 10.0, 'baseline': 'feature_resource'},
    'ridge_100': {'estimator': 'ridge', 'alpha': 100.0, 'baseline': 'feature_resource'},
    'huber_10': {'estimator': 'huber', 'alpha': 10.0, 'epsilon': 1.35,
                 'baseline': 'feature_resource'},
    'huber_100': {'estimator': 'huber', 'alpha': 100.0, 'epsilon': 1.35,
                  'baseline': 'feature_resource'},
}
MODEL_CONFIG = {
    'candidate_grid': CONFIG_GRID,
    'primary_selection_metric': 'macro_program_mae_lut4',
    'residual_target': 'log1p(label)-log1p(feature_resource)',
    'residual_shrinkage': 0.5,
    'residual_clip': [-0.7, 0.7],
    'feature_transform': 'log1p all nonnegative formula features, then standardize',
    'resource_ridge_alpha': 10.0,
    'resource_fit': 'nonnegative raw LUT4 regression, no intercept, physical coefficient prior',
    'structural_resource_columns': list(RESOURCE_NAMES),
    'structural_resource_prior': list(RESOURCE_PRIOR),
    'huber_max_iter': 300,
    'huber_tol': 1e-5,
}


@lru_cache(maxsize=16384)
def _formula_vector(formula: str) -> tuple[float, ...]:
    original = v2_feature_matrix([{'formula': formula}])[0]
    structural = feature_dict(formula)
    values = tuple(original) + tuple(structural[name] for name in FEATURE_NAMES)
    if not all(np.isfinite(value) and value >= 0 for value in values):
        raise ValueError('v3 features must be finite and nonnegative')
    return values


def feature_matrix(rows: list[dict], feature_set: str = 'structural') -> np.ndarray:
    """Only a formula is read; labels, measurements and traces cannot enter."""
    if feature_set not in FEATURE_SETS: raise ValueError('unknown v3 feature set')
    columns = len(V2_FEATURE_COLUMNS) if feature_set == 'original' else len(FEATURE_COLUMNS)
    if not rows: return np.empty((0, columns))
    return np.asarray([_formula_vector(parse_formula(row['formula']).canonical())[:columns]
                       for row in rows], dtype=float)


def resource_matrix(rows: list[dict]) -> np.ndarray:
    if not rows: return np.empty((0, len(RESOURCE_NAMES)))
    return np.asarray([[feature_dict(parse_formula(row['formula']).canonical())[name]
                        for name in RESOURCE_NAMES] for row in rows], dtype=float)


def _residual_matrix(rows, base, feature_set):
    return np.column_stack((np.log1p(feature_matrix(rows, feature_set)), np.log1p(base)))


def metrics(truth, predicted) -> dict:
    """MAPE excludes true zeros; zero behavior is reported explicitly."""
    y, p = np.asarray(truth, dtype=float), np.asarray(predicted, dtype=float)
    if len(y) == 0: return {'sample_count': 0}
    if not np.isfinite(y).all() or not np.isfinite(p).all() or np.any(y < 0) or np.any(p < 0):
        raise ValueError('metrics require finite nonnegative observations and predictions')
    result = _metrics(y.tolist(), p.tolist())
    result['pearson'] = float(pearsonr(y, p).statistic) if len(y) > 1 and np.ptp(y) and np.ptp(p) else None
    zero, nonzero = y == 0, y > 0
    result['nonzero_mape_percent'] = float(100*np.mean(np.abs(y[nonzero]-p[nonzero])/y[nonzero])) if nonzero.any() else None
    result['zero_error_counts'] = {
        'true_zero_count': int(zero.sum()),
        'true_zero_predicted_nonzero_count': int(np.sum(zero & (p > 1e-9))),
        'positive_true_predicted_zero_count': int(np.sum(nonzero & (p <= 1e-9))),
        'zero_mae_lut4': float(np.mean(p[zero])) if zero.any() else None,
        'zero_max_predicted_lut4': float(np.max(p[zero])) if zero.any() else None,
    }
    if result['nonzero_lut4_metrics'] is not None:
        yn, pn = y[nonzero], p[nonzero]
        result['nonzero_lut4_metrics']['mape_percent'] = result['nonzero_mape_percent']
        result['nonzero_lut4_metrics']['pearson'] = float(pearsonr(yn, pn).statistic) if len(yn) > 1 and np.ptp(yn) and np.ptp(pn) else None
    return result


@dataclass
class StructuralResourcePredictor:
    coefficients: np.ndarray
    training_formula_count: int
    resource_columns: tuple[str, ...] = tuple(RESOURCE_NAMES)

    def values(self, rows):
        if self.resource_columns != tuple(RESOURCE_NAMES): raise ValueError('v3 resource schema mismatch')
        values = np.maximum(resource_matrix(rows) @ self.coefficients, 0)
        if not np.isfinite(values).all(): raise ValueError('nonfinite structural resource prediction')
        return values

    def predict(self, rows):
        return _predictions(rows, self.values(rows), 'structural_resource')


@dataclass
class V3Predictor:
    baseline: ResourcePredictor | StructuralResourcePredictor
    estimator: Any
    candidate_name: str
    feature_set: str
    training_formula_count: int
    convergence_warning_count: int = 0
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS

    def predict(self, rows):
        if self.feature_columns != FEATURE_COLUMNS: raise ValueError('v3 feature schema mismatch')
        if not rows: return []
        base = self.baseline.values(rows)
        values = base.copy()
        if self.estimator is not None:
            correction = self.estimator.predict(_residual_matrix(rows, base, self.feature_set))
            correction = np.clip(correction * MODEL_CONFIG['residual_shrinkage'],
                                 *MODEL_CONFIG['residual_clip'])
            values = np.maximum(np.expm1(np.log1p(base) + correction), 0)
        # An explicitly proved constant/wiring expression has zero isolated
        # combinational LUT cost. This is an algebraic proof, not a learned gate.
        if self.feature_set == 'structural' and self.candidate_name != 'v2_resource':
            values[[proven_zero_lut(row['formula']) for row in rows]] = 0
        else:
            values[np.all(v2_resource_matrix(rows) == 0, axis=1)] = 0
        if not np.isfinite(values).all(): raise ValueError('nonfinite v3 prediction')
        return _predictions(rows, values, 'v3_' + self.feature_set + '_' + self.candidate_name)


def _predictions(rows, values, name):
    return [{**{key: row[key] for key in ('candidate_id', 'benchmark', 'formula') if key in row},
             'predicted_lut4': float(value), 'model': name, 'target': TARGET}
            for row, value in zip(rows, values)]


def train_structural_resource(rows) -> StructuralResourcePredictor:
    rows = _unique_formulas(_validated_rows(rows))
    x, y = resource_matrix(rows), np.asarray([row['lut4_count'] for row in rows])
    prior = np.asarray(RESOURCE_PRIOR, dtype=float)
    penalty = np.sqrt(MODEL_CONFIG['resource_ridge_alpha']) * np.eye(len(prior))
    fitted = lsq_linear(np.vstack((x, penalty)), np.concatenate((y, penalty @ prior)),
                        bounds=(0, np.inf), tol=1e-10)
    if not fitted.success: raise ValueError('structural resource regression did not converge')
    return StructuralResourcePredictor(fitted.x, len(rows))


def train_v3_model(rows, candidate_name='huber_100', feature_set='structural',
                   seed=SEED, baseline=None) -> V3Predictor:
    """Fit one prespecified candidate; evaluation selects without test labels."""
    if candidate_name not in CONFIG_GRID: raise ValueError('unknown v3 candidate')
    if feature_set not in FEATURE_SETS: raise ValueError('unknown v3 feature set')
    rows = _unique_formulas(_validated_rows(rows))
    config = CONFIG_GRID[candidate_name]
    use_v2 = feature_set == 'original' or config['baseline'] == 'v2_resource'
    baseline = baseline or (train_resource_model(rows) if use_v2 else train_structural_resource(rows))
    estimator, count = None, 0
    if config['estimator'] != 'none':
        base = baseline.values(rows)
        y = np.log1p([row['lut4_count'] for row in rows]) - np.log1p(base)
        if config['estimator'] == 'ridge':
            regression = Ridge(alpha=config['alpha'])
        else:
            regression = HuberRegressor(alpha=config['alpha'], epsilon=config['epsilon'],
                                       max_iter=MODEL_CONFIG['huber_max_iter'], tol=MODEL_CONFIG['huber_tol'])
        estimator = make_pipeline(StandardScaler(), regression)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', ConvergenceWarning)
            estimator.fit(_residual_matrix(rows, base, feature_set), y)
        count = sum(issubclass(item.category, ConvergenceWarning) for item in caught)
    return V3Predictor(baseline, estimator, candidate_name, feature_set, len(rows), count)


class _Fitter:
    """Cache symmetric inner folds without sharing any held-out labels."""
    def __init__(self):
        self.models = {}
        self.baselines = {}

    def model(self, rows, candidate, feature_set):
        identity = tuple(sorted((row['formula'], float(row['lut4_count'])) for row in _unique_formulas(rows)))
        key = identity, candidate, feature_set
        if key not in self.models:
            kind = 'v2' if feature_set == 'original' or candidate == 'v2_resource' else 'structural'
            base_key = identity, kind
            if base_key not in self.baselines:
                self.baselines[base_key] = train_resource_model(rows) if kind == 'v2' else train_structural_resource(rows)
            self.models[key] = train_v3_model(rows, candidate, feature_set, baseline=self.baselines[base_key])
        return self.models[key]


def _macro(fold_metrics):
    keys = ('mae_lut4', 'rmsle', 'nonzero_mape_percent', 'pearson', 'spearman')
    return {'macro_program_' + key: float(np.mean([fold[key] for fold in fold_metrics if fold.get(key) is not None]))
            if any(fold.get(key) is not None for fold in fold_metrics) else None for key in keys}


def select_model(rows, feature_set='structural', fitter=None):
    """Inner program holdout selection, excluding every matching formula."""
    fitter = fitter or _Fitter()
    pooled = {name: {'truth': [], 'predicted': []} for name in CONFIG_GRID}
    fold_metrics = {name: [] for name in CONFIG_GRID}
    folds = []
    for benchmark in sorted({row['benchmark'] for row in rows}):
        train, validation, excluded = benchmark_split(rows, benchmark)
        detail = {'held_out_benchmark': benchmark, 'train_formula_count': len(_unique_formulas(train)),
                  'validation_size': len(validation), 'excluded_matching_formula_rows': excluded}
        if not train or not validation:
            folds.append({**detail, 'status': 'skipped_no_novel_training_formulas'})
            continue
        truth = [row['lut4_count'] for row in validation]
        detail.update(status='evaluated', predictions={}, metrics={}, convergence_warnings={})
        for name in CONFIG_GRID:
            model = fitter.model(train, name, feature_set)
            predicted = [item['predicted_lut4'] for item in model.predict(validation)]
            pooled[name]['truth'].extend(truth); pooled[name]['predicted'].extend(predicted)
            detail['metrics'][name] = metrics(truth, predicted)
            detail['predictions'][name] = [
                {**{key: row[key] for key in ('benchmark', 'candidate_id', 'formula') if key in row},
                 'measured_lut4': actual, 'predicted_lut4': value}
                for row, actual, value in zip(validation, truth, predicted)]
            detail['convergence_warnings'][name] = model.convergence_warning_count
            fold_metrics[name].append(detail['metrics'][name])
        folds.append(detail)
    summary = {name: {**_macro(fold_metrics[name]), 'pooled': metrics(values['truth'], values['predicted'])}
               for name, values in pooled.items() if values['truth']}
    # Fixed ordering prefers the simplest candidate when scores are exactly equal.
    chosen = min(summary, key=lambda name: (summary[name]['macro_program_mae_lut4'], list(CONFIG_GRID).index(name))) if summary else 'v2_resource'
    return chosen, {'selected_candidate': chosen, 'feature_set': feature_set,
                    'selection_reason': 'minimum macro program-held-out MAE; prespecified ordering breaks ties' if summary else 'no eligible folds; resource default',
                    'metrics_by_candidate': summary, 'folds': folds}


def _source_hashes():
    directory = Path(__file__).parent
    return {name: hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in (
        'area_model_v3.py', 'structural_features_v3.py', 'area_model_v2.py', 'area_model.py', 'features.py', 'rtl.py')}


def save_model(model, directory, name='area-model-v3', metadata=None):
    import joblib
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / (name + '.joblib'); joblib.dump(model, artifact)
    schema = {**(metadata or {}), 'schema_version': SCHEMA_VERSION,
              'feature_columns': list(FEATURE_COLUMNS), 'model_config': MODEL_CONFIG,
              'candidate_name': model.candidate_name, 'feature_set': model.feature_set,
              'training_formula_count': model.training_formula_count,
              'training_convergence_warning_count': model.convergence_warning_count,
              'baseline_kind': type(model.baseline).__name__,
              'baseline_resource_coefficients': dict(zip(
                  RESOURCE_NAMES if isinstance(model.baseline, StructuralResourcePredictor) else V2_RESOURCE_COLUMNS,
                  model.baseline.coefficients.tolist())),
              'trained_at_utc': datetime.now(timezone.utc).isoformat(), 'versions': _versions(),
              'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
              'runtime_source_sha256': _source_hashes()}
    schema_path = artifact.with_suffix('.json'); schema_path.write_text(json.dumps(schema, indent=2)+'\n')
    return {'model_path': str(artifact), 'schema_path': str(schema_path), 'artifact_sha256': schema['artifact_sha256']}


def load_area_model_v3(path):
    """Load trusted local pickle after checking artifact/schema/source hashes."""
    import joblib
    path = Path(path); schema = json.loads(path.with_suffix('.json').read_text())
    if schema.get('schema_version') != SCHEMA_VERSION or schema.get('feature_columns') != list(FEATURE_COLUMNS):
        raise ValueError('v3 feature/schema mismatch')
    if schema.get('model_config') != MODEL_CONFIG: raise ValueError('v3 configuration mismatch')
    if schema.get('artifact_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('v3 artifact hash mismatch')
    if schema.get('runtime_source_sha256') != _source_hashes():
        raise ValueError('v3 runtime dependency source differs from frozen artifact')
    model = joblib.load(path)
    if not isinstance(model, V3Predictor) or model.feature_columns != FEATURE_COLUMNS:
        raise ValueError('invalid v3 artifact')
    if model.candidate_name != schema.get('candidate_name') or model.feature_set != schema.get('feature_set'):
        raise ValueError('v3 persisted model configuration mismatch')
    return model


load_model = load_area_model_v3


@threadpool_limits.wrap(limits=1, user_api='blas')
def develop_and_freeze(rows, directory, seed=SEED):
    rows = _validated_rows(rows)
    if len({row['benchmark'] for row in rows}) < 3: raise ValueError('nested evaluation requires at least three programs')
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=True)
    if (directory/'preregistration.json').exists():
        raise ValueError('v3 output directory is already frozen; use a new directory for a new development run')
    source_snapshot = _source_hashes()
    frozen_grid = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
                   'model_config': MODEL_CONFIG, 'feature_columns': list(FEATURE_COLUMNS),
                   'status': 'fixed before scores; all existing benchmark labels development'}
    (directory/'config-grid.json').write_text(json.dumps(frozen_grid, indent=2)+'\n')
    fitter = _Fitter()
    names = ('resource_v2', 'v1_xgboost_log', 'v2_residual_xgb', 'v3_original', 'v3_structural')
    pooled = {name: {'truth': [], 'predicted': []} for name in names}
    metrics_by_fold = {name: [] for name in names}
    folds = []
    for benchmark in sorted({row['benchmark'] for row in rows}):
        train, test, excluded = benchmark_split(rows, benchmark)
        if not train: continue
        print(f'Development outer fold {benchmark}', flush=True)
        detail = {'held_out_benchmark': benchmark, 'train_formula_count': len(_unique_formulas(train)),
                  'train_benchmarks': sorted({row['benchmark'] for row in train}),
                  'test_size': len(test), 'excluded_matching_formula_rows': excluded,
                  'inner_selection': {}, 'metrics': {}, 'predictions': {}}
        models = {'resource_v2': train_resource_model(train),
                  'v1_xgboost_log': train_area_model(train, 'xgboost_log', seed),
                  'v2_residual_xgb': train_v2_model(train, seed)}
        for feature_set in FEATURE_SETS:
            chosen, selection = select_model(train, feature_set, fitter)
            detail['inner_selection'][feature_set] = selection
            models['v3_' + feature_set] = fitter.model(train, chosen, feature_set)
        truth = [row['lut4_count'] for row in test]
        for name, model in models.items():
            predictions = model.predict(test)
            predicted = [item['predicted_lut4'] for item in predictions]
            pooled[name]['truth'].extend(truth); pooled[name]['predicted'].extend(predicted)
            detail['metrics'][name] = metrics(truth, predicted)
            metrics_by_fold[name].append(detail['metrics'][name])
            detail['predictions'][name] = [{**prediction, 'measured_lut4': actual} for prediction, actual in zip(predictions, truth)]
        folds.append(detail)
        # Persist progress so selection/predictions remain inspectable on failure.
        (directory/'development-progress.json').write_text(json.dumps({'completed_outer_folds': len(folds), 'last_benchmark': benchmark}, indent=2)+'\n')
    selections, artifacts = {}, {}
    if _source_hashes() != source_snapshot:
        raise ValueError('runtime source changed during development; no artifacts may be frozen from mixed sources')
    dataset_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    metadata = {'training_dataset_sha256': dataset_hash,
                'training_dataset_hash_method': 'sorted-key compact JSON of validated rows with normalized float labels',
                'training_row_count': len(rows), 'unique_formula_count': len(_unique_formulas(rows)),
                'benchmark_names': sorted({row['benchmark'] for row in rows}), 'seed': seed,
                'target': TARGET, 'measurement_source': 'rtl_synthesis',
                'evaluation_status': 'DEVELOPMENT: all original, transfer and final benchmark labels previously seen'}
    for feature_set in FEATURE_SETS:
        chosen, selection = select_model(rows, feature_set, fitter)
        selections[feature_set] = selection
        artifacts['v3_' + feature_set] = save_model(fitter.model(rows, chosen, feature_set), directory,
                                                   'area-model-v3' if feature_set == 'structural' else 'area-model-v3-original', metadata)
    artifacts['resource_v2'] = save_v2_model(train_resource_model(rows), directory, 'resource-v2-full', metadata)
    artifacts['v2_residual_xgb'] = save_v2_model(train_v2_model(rows, seed), directory, 'area-model-v2-full', metadata)
    artifacts['v1_xgboost_log'] = save_area_model(train_area_model(rows, 'xgboost_log', seed),
                                                directory/'v1-full', metadata)
    report = {**metadata, 'method': 'nested leave-one-program-out, matching formula exclusion in outer and inner folds',
              'model_config': MODEL_CONFIG, 'feature_columns': list(FEATURE_COLUMNS),
              'folds': folds, 'pooled_metrics': {name: metrics(values['truth'], values['predicted']) for name, values in pooled.items()},
              'macro_program_metrics': {name: _macro(values) for name, values in metrics_by_fold.items()},
              'final_selection': selections, 'artifacts': artifacts, 'runtime_source_sha256': _source_hashes(),
              'limitations': ['All benchmark labels have been inspected in earlier model development; nested scores remain development evidence.',
                              'Small unique formula corpus; sparse multiplication/high-half coverage limits transfer.',
                              'LUT4 is an isolated synthesis resource proxy; results do not establish ASIC area, timing or processor speedup.',
                              'MAPE excludes true zeros and is not an accuracy percentage; absolute and log errors answer different questions.',
                              'No calibrated prediction intervals; bounded residuals preserve structural extrapolation but can limit correction.']}
    (directory/'development-evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    if _source_hashes() != source_snapshot:
        raise ValueError('runtime source changed during final fitting; artifacts remain provisional and are not frozen')
    preregistration = {**metadata, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                      'artifacts': artifacts, 'model_config': MODEL_CONFIG,
                      'runtime_source_sha256': _source_hashes(),
                      'primary_metric': 'macro family MAE on all novel independently collected stress formulas',
                      'secondary_metrics': ['pooled MAE', 'RMSLE', 'positive-label MAPE', 'Pearson', 'Spearman', 'zero error counts', 'per-family metrics'],
                      'reporting': 'Report all frozen comparisons, all families, novel/overlap subsets. No refit, grid change or winner substitution after probe labels.'}
    (directory/'preregistration.json').write_text(json.dumps(preregistration, indent=2)+'\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    train = commands.add_parser('train')
    train.add_argument('--rows', required=True, action='append')
    train.add_argument('--output-dir', required=True)
    train.add_argument('--seed', type=int, default=SEED)
    predict = commands.add_parser('predict')
    predict.add_argument('--model', required=True); predict.add_argument('--candidates', required=True)
    predict.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'train':
        rows = [row for path in args.rows for row in _read_rows(path)]
        report = develop_and_freeze(rows, args.output_dir, args.seed)
        print(json.dumps({'macro_program_metrics': report['macro_program_metrics'],
                          'pooled_metrics': report['pooled_metrics'], 'artifacts': report['artifacts']}, indent=2))
    else:
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        predictions = load_area_model_v3(args.model).predict(_read_rows(args.candidates))
        output.write_text(json.dumps(predictions, indent=2)+'\n')
        print(f'Wrote {len(predictions)} label-free LUT4 predictions to {output}')
    return 0


if __name__ == '__main__':
    from .area_model_v3 import main as canonical_main
    raise SystemExit(canonical_main())

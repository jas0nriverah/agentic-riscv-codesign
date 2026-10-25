"""A deployable predictor of measured iCE40 LUT4 cost from candidate formulas.

Model choice uses nested benchmark holdouts. Identical formulas are excluded
from training whenever present in the validation/test split. This predicts an
isolated hardware-resource proxy; it does not predict processor speedup.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from .features import OPERATIONS, Expression, parse_formula

SCHEMA_VERSION = 1
AREA_FEATURE_COLUMNS = (
    'depth', 'tree_op_count', 'unique_op_count', 'repeated_subexpression_count',
    'input_count', 'constant_count', 'unique_constant_count', 'zero_constant_count',
    'negative_constant_count', 'constant_unsigned_width_sum', 'constant_unsigned_width_max',
    'constant_popcount_sum', 'constant_popcount_max', 'constant_signed_width_sum',
    'constant_signed_width_max', 'variable_shift_count', 'immediate_shift_sum',
    'immediate_shift_max', 'multiply_count', 'constant_multiply_count',
    'output_known_zero_bits', 'output_known_one_bits', 'output_unknown_bits', 'output_is_constant',
    'add_operand_overlap_bits_sum', 'add_operand_overlap_bits_max',
) + tuple(f'op_{op}' for op in OPERATIONS)

# Fixed before outer evaluation. Selection is based on inner pooled RMSLE only.
MODEL_CONFIGS = {
    'mean': {'target_transform': 'none'},
    'ridge_log': {'alpha': 10.0, 'target_transform': 'log1p'},
    'extra_trees_log': {'n_estimators': 128, 'min_samples_leaf': 1,
                        'max_features': 1.0, 'target_transform': 'log1p'},
    'random_forest_log': {'n_estimators': 128, 'min_samples_leaf': 1,
                         'max_features': 1.0, 'target_transform': 'log1p'},
    'xgboost_log': {'n_estimators': 160, 'max_depth': 3, 'learning_rate': 0.07,
                    'min_child_weight': 2, 'reg_lambda': 2.0,
                    'target_transform': 'log1p'},
}


def _known_bits(node: Expression) -> tuple[int, int]:
    """Conservative RV32 known-zero/known-one propagation, without synthesis.

    Masks contain only provable bit values. Correlation is discarded, except
    explicit x-x/x^x identities; this can miss constants but cannot invent one.
    """
    mask = 0xFFFFFFFF
    if not node.children:
        if isinstance(node.value, int):
            value = node.value & mask
            return mask ^ value, value
        return 0, 0
    bits = [_known_bits(child) for child in node.children]
    az, ao = bits[0]
    if node.value == 'lui':
        return az, ao
    bz, bo = bits[1]
    op = str(node.value)
    if az | ao == mask and bz | bo == mask:
        from .rtl import evaluate_formula
        value = evaluate_formula(node, 0, 0)
        return mask ^ value, value
    same = node.children[0].canonical() == node.children[1].canonical()
    if op in ('sub', 'xor') and same:
        return mask, 0
    if op in ('and', 'andi'):
        return az | bz, ao & bo
    if op in ('or', 'ori'):
        return az & bz, ao | bo
    if op in ('xor', 'xori'):
        return (az & bz) | (ao & bo), (az & bo) | (ao & bz)
    if op in ('add', 'addi', 'sub'):
        # Abstract full-adder propagation. Set-valued carry/operand bits give
        # an overapproximation, so only fixed output bits enter the masks.
        zero = one = 0
        carry = {1} if op == 'sub' else {0}
        if op == 'sub':
            bz, bo = bo, bz
        for i in range(32):
            a_values = {0} if az & (1 << i) else {1} if ao & (1 << i) else {0, 1}
            b_values = {0} if bz & (1 << i) else {1} if bo & (1 << i) else {0, 1}
            sums = {a + b + c for a in a_values for b in b_values for c in carry}
            output = {value & 1 for value in sums}
            if output == {0}: zero |= 1 << i
            if output == {1}: one |= 1 << i
            carry = {value >> 1 for value in sums}
        return zero, one
    if op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
        possibilities = [distance for distance in range(32)
                         if distance & (bz & 31) == 0 and distance & (bo & 31) == bo & 31]
        zero = one = mask
        for distance in possibilities:
            if op in ('sll', 'slli'):
                z = ((az << distance) | ((1 << distance) - 1)) & mask
                o = (ao << distance) & mask
            else:
                fill = mask ^ (mask >> distance)
                z, o = az >> distance, ao >> distance
                if op in ('srl', 'srli') or az & 0x80000000:
                    z |= fill
                elif ao & 0x80000000:
                    o |= fill
            zero &= z
            one &= o
        return zero, one
    if op in ('mul', 'mulh', 'mulhu', 'mulhsu') and (az == mask or bz == mask):
        return mask, 0
    if op in ('slt', 'slti', 'sltu', 'sltiu'):
        if same:
            return mask, 0
        def bounds(z: int, o: int) -> tuple[int, int]:
            if op in ('sltu', 'sltiu'):
                return o, mask ^ z
            # Signed extrema choose negative/positive sign if allowed.
            lower = (o & 0x7FFFFFFF) - (2**31 if not z & 0x80000000 else 0)
            upper = ((mask ^ z) & 0x7FFFFFFF) - (2**31 if o & 0x80000000 else 0)
            return lower, upper
        amin, amax = bounds(az, ao)
        bmin, bmax = bounds(bz, bo)
        if amax < bmin:
            return mask ^ 1, 1
        if amin >= bmax:
            return mask, 0
        return mask ^ 1, 0
    return 0, 0


@lru_cache(maxsize=16384)
def _formula_features(formula: str) -> tuple[float, ...]:
    root = parse_formula(formula)
    counts: Counter[str] = Counter()
    unique_ops: set[str] = set()
    inputs: set[str] = set()
    constants: list[int] = []
    immediate_shifts: list[int] = []
    variable_shifts = constant_multiply = 0
    add_overlap_bits: list[int] = []

    def visit(node: Expression) -> int:
        nonlocal variable_shifts, constant_multiply
        if not node.children:
            if isinstance(node.value, int):
                constants.append(node.value & 0xFFFFFFFF)
            else:
                inputs.add(str(node.value))
            return 0
        op = str(node.value)
        counts[op] += 1
        unique_ops.add(node.canonical())
        if op in ('sll', 'srl', 'sra'):
            variable_shifts += 1
        if op in ('slli', 'srli', 'srai'):
            immediate_shifts.append(int(node.children[1].value) & 31)
        if op in ('mul', 'mulh', 'mulhu', 'mulhsu') and any(
                (lambda bits: bits[0] | bits[1] == 0xFFFFFFFF)(_known_bits(c)) for c in node.children):
            constant_multiply += 1
        if op in ('add', 'addi'):
            az, _ = _known_bits(node.children[0])
            bz, _ = _known_bits(node.children[1])
            add_overlap_bits.append(((0xFFFFFFFF ^ az) & (0xFFFFFFFF ^ bz)).bit_count())
        return 1 + max(visit(child) for child in node.children)

    depth = visit(root)
    known_zero, known_one = _known_bits(root)
    unsigned_widths = [value.bit_length() for value in constants]
    popcounts = [value.bit_count() for value in constants]
    signed = [value - 2**32 if value & 2**31 else value for value in constants]
    signed_widths = [(value if value >= 0 else ~value).bit_length() + 1 for value in signed]
    values = {
        'depth': depth, 'tree_op_count': sum(counts.values()), 'unique_op_count': len(unique_ops),
        'repeated_subexpression_count': sum(counts.values()) - len(unique_ops),
        'input_count': len(inputs), 'constant_count': len(constants),
        'unique_constant_count': len(set(constants)), 'zero_constant_count': constants.count(0),
        'negative_constant_count': sum(value < 0 for value in signed),
        'constant_unsigned_width_sum': sum(unsigned_widths),
        'constant_unsigned_width_max': max(unsigned_widths, default=0),
        'constant_popcount_sum': sum(popcounts), 'constant_popcount_max': max(popcounts, default=0),
        'constant_signed_width_sum': sum(signed_widths),
        'constant_signed_width_max': max(signed_widths, default=0),
        'variable_shift_count': variable_shifts, 'immediate_shift_sum': sum(immediate_shifts),
        'immediate_shift_max': max(immediate_shifts, default=0),
        'multiply_count': sum(counts[op] for op in ('mul', 'mulh', 'mulhu', 'mulhsu')),
        'constant_multiply_count': constant_multiply,
        'output_known_zero_bits': known_zero.bit_count(), 'output_known_one_bits': known_one.bit_count(),
        'output_unknown_bits': 32 - (known_zero | known_one).bit_count(),
        'output_is_constant': int(known_zero | known_one == 0xFFFFFFFF),
        'add_operand_overlap_bits_sum': sum(add_overlap_bits),
        'add_operand_overlap_bits_max': max(add_overlap_bits, default=0),
    }
    values.update({f'op_{op}': counts[op] for op in OPERATIONS})
    return tuple(float(values[column]) for column in AREA_FEATURE_COLUMNS)


def area_feature_matrix(rows: list[dict]) -> np.ndarray:
    """Only formula-derived features; row measurements/frequencies are ignored."""
    if not rows:
        return np.empty((0, len(AREA_FEATURE_COLUMNS)))
    return np.asarray([_formula_features(parse_formula(row['formula']).canonical()) for row in rows], dtype=float)


def _validated_rows(rows: list[dict]) -> list[dict]:
    if not rows:
        raise ValueError('at least one actual synthesis training row is required')
    validated = []
    labels: dict[str, float] = {}
    identities: set[tuple[str, str]] = set()
    for row in rows:
        if row.get('measurement_source') != 'rtl_synthesis':
            raise ValueError("area labels require measurement_source='rtl_synthesis'")
        benchmark = row.get('benchmark')
        if not isinstance(benchmark, str) or not benchmark.strip():
            raise ValueError('each area training row requires a benchmark')
        formula = parse_formula(row.get('formula')).canonical()
        value = row.get('lut4_count', row.get('ice40_lut4_count'))
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError('LUT4 counts must be finite nonnegative numbers')
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError('LUT4 counts must be finite nonnegative numbers') from error
        if not math.isfinite(value) or value < 0:
            raise ValueError('LUT4 counts must be finite nonnegative numbers')
        if formula in labels and labels[formula] != value:
            raise ValueError('the same formula has inconsistent synthesis labels')
        if (benchmark, formula) in identities:
            raise ValueError('duplicate formula within benchmark')
        labels[formula] = value
        identities.add((benchmark, formula))
        validated.append({**row, 'formula': formula, 'lut4_count': value})
    return validated


def benchmark_split(rows: list[dict], held_out_benchmark: str) -> tuple[list[dict], list[dict], int]:
    """Exclude the entire test benchmark and all matching test formulas."""
    test = [row for row in rows if row['benchmark'] == held_out_benchmark]
    formulas = {row['formula'] for row in test}
    other = [row for row in rows if row['benchmark'] != held_out_benchmark]
    train = [row for row in other if row['formula'] not in formulas]
    return train, test, len(other) - len(train)


def _unique_formulas(rows: list[dict]) -> list[dict]:
    return list({row['formula']: row for row in rows}.values())


def _new_estimator(name: str, seed: int):
    if name == 'mean':
        from sklearn.dummy import DummyRegressor
        return DummyRegressor(strategy='mean')
    if name == 'ridge_log':
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), Ridge(alpha=MODEL_CONFIGS[name]['alpha']))
    options = {key: value for key, value in MODEL_CONFIGS[name].items() if key != 'target_transform'}
    if name == 'extra_trees_log':
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor(**options, random_state=seed, n_jobs=1)
    if name == 'random_forest_log':
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(**options, random_state=seed, n_jobs=1)
    if name == 'xgboost_log':
        from xgboost import XGBRegressor
        return XGBRegressor(**options, random_state=seed, n_jobs=1, objective='reg:squarederror',
                            tree_method='hist', verbosity=0)
    raise ValueError(f'unknown area estimator {name}')


@dataclass
class AreaPredictor:
    """Fitted formula-to-LUT4 estimator; predictions are nonnegative real counts."""
    estimator_name: str
    seed: int
    estimator: Any
    training_formula_count: int
    feature_columns: tuple[str, ...] = AREA_FEATURE_COLUMNS

    def predict(self, rows: list[dict]) -> list[dict]:
        if self.feature_columns != AREA_FEATURE_COLUMNS:
            raise ValueError('area-model feature schema does not match this runtime')
        if not rows:
            return []
        values = np.asarray(self.estimator.predict(area_feature_matrix(rows)), dtype=float)
        if self.estimator_name != 'mean':
            # Bounds only avoid numeric overflow; predictions are not capped to training labels.
            values = np.expm1(np.clip(values, -700, 700))
        values = np.maximum(values, 0)
        if not np.isfinite(values).all():
            raise ValueError('area estimator produced nonfinite predictions')
        return [{**{key: row[key] for key in ('candidate_id', 'benchmark', 'formula') if key in row},
                 'predicted_lut4': float(value), 'target': 'isolated iCE40 mapped SB_LUT4 count'}
                for row, value in zip(rows, values)]


def train_area_model(rows: list[dict], estimator_name: str = 'extra_trees_log', seed: int = 0) -> AreaPredictor:
    validated = _unique_formulas(_validated_rows(rows))
    estimator = _new_estimator(estimator_name, seed)
    targets = np.asarray([row['lut4_count'] for row in validated])
    estimator.fit(area_feature_matrix(validated), targets if estimator_name == 'mean' else np.log1p(targets))
    return AreaPredictor(estimator_name, seed, estimator, len(validated))


def _metrics(truth: list[float], predicted: list[float]) -> dict:
    y, p = np.asarray(truth, dtype=float), np.asarray(predicted, dtype=float)
    rho = None
    if len(y) >= 2 and np.ptp(y) > 0 and np.ptp(p) > 0:
        correlation = float(spearmanr(y, p).statistic)
        if math.isfinite(correlation):
            rho = correlation
    result = {'mae_lut4': float(np.mean(np.abs(y - p))),
              'rmsle': float(np.sqrt(np.mean((np.log1p(y) - np.log1p(p))**2))),
              'spearman': rho, 'sample_count': len(y), 'zero_lut4_count': int(np.sum(y == 0))}
    nonzero = y > 0
    if nonzero.any():
        yn, pn = y[nonzero], p[nonzero]
        nonzero_rho = None
        if len(yn) >= 2 and np.ptp(yn) > 0 and np.ptp(pn) > 0:
            coefficient = float(spearmanr(yn, pn).statistic)
            if math.isfinite(coefficient): nonzero_rho = coefficient
        result['nonzero_lut4_metrics'] = {
            'mae_lut4': float(np.mean(np.abs(yn - pn))),
            'rmsle': float(np.sqrt(np.mean((np.log1p(yn) - np.log1p(pn))**2))),
            'spearman': nonzero_rho, 'sample_count': int(nonzero.sum())}
    else:
        result['nonzero_lut4_metrics'] = None
    return result


def _select_model(rows: list[dict], seed: int) -> tuple[str, dict]:
    """Choose using only inner benchmark folds; score all prespecified models."""
    benchmarks = sorted({row['benchmark'] for row in rows})
    scores = {name: {'truth': [], 'predicted': []} for name in MODEL_CONFIGS}
    folds = []
    for benchmark in benchmarks:
        train, validation, duplicates = benchmark_split(rows, benchmark)
        train = _unique_formulas(train)
        detail = {'held_out_benchmark': benchmark, 'train_formula_count': len(train),
                  'validation_size': len(validation), 'excluded_matching_formula_rows': duplicates}
        if not train or not validation:
            detail['status'] = 'skipped_no_novel_training_formulas'
            folds.append(detail)
            continue
        detail['status'] = 'evaluated'
        folds.append(detail)
        truth = [row['lut4_count'] for row in validation]
        for name in MODEL_CONFIGS:
            model = train_area_model(train, name, seed)
            predicted = [row['predicted_lut4'] for row in model.predict(validation)]
            scores[name]['truth'].extend(truth)
            scores[name]['predicted'].extend(predicted)
    metrics = {name: _metrics(values['truth'], values['predicted'])
               for name, values in scores.items() if values['truth']}
    if not metrics:
        # Prespecified default is used only when no inner evaluation is possible.
        chosen = 'extra_trees_log'
        reason = 'no eligible inner folds; prespecified extra_trees_log default'
    else:
        chosen = min(metrics, key=lambda name: (metrics[name]['rmsle'], name))
        reason = 'minimum pooled inner benchmark-held-out RMSLE'
    return chosen, {'selected_estimator': chosen, 'selection_reason': reason,
                    'metrics_by_estimator': metrics, 'folds': folds}


def _versions() -> dict[str, str]:
    return {package: importlib.metadata.version(package) for package in ('numpy', 'scipy', 'scikit-learn', 'xgboost', 'joblib')}


def save_area_model(model: AreaPredictor, output_dir: str | Path, metadata: dict | None = None) -> dict:
    import joblib
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / 'area-model.joblib'
    joblib.dump(model, artifact)
    schema = {'schema_version': SCHEMA_VERSION, 'target': 'isolated iCE40 mapped SB_LUT4 count',
              'measurement_source': 'rtl_synthesis', 'feature_columns': list(AREA_FEATURE_COLUMNS),
              'estimator_name': model.estimator_name, 'seed': model.seed,
              'training_formula_count': model.training_formula_count,
              'model_config': MODEL_CONFIGS[model.estimator_name], 'versions': _versions(),
              'trained_at_utc': datetime.now(timezone.utc).isoformat(),
              'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
              **(metadata or {})}
    (directory / 'area-model.json').write_text(json.dumps(schema, indent=2) + '\n')
    return {'model_path': str(artifact), 'schema_path': str(directory / 'area-model.json')}


def load_area_model(path: str | Path) -> AreaPredictor:
    """Load a trusted local joblib artifact. Never load downloaded untrusted pickle."""
    import joblib
    artifact = Path(path)
    schema = json.loads(artifact.with_suffix('.json').read_text())
    if schema.get('schema_version') != SCHEMA_VERSION or schema.get('feature_columns') != list(AREA_FEATURE_COLUMNS):
        raise ValueError('area-model feature/schema version mismatch')
    if schema.get('artifact_sha256') != hashlib.sha256(artifact.read_bytes()).hexdigest():
        raise ValueError('area-model artifact hash mismatch')
    model = joblib.load(artifact)
    if not isinstance(model, AreaPredictor) or model.feature_columns != AREA_FEATURE_COLUMNS:
        raise ValueError('invalid area-model artifact')
    return model


def evaluate_and_train(rows: list[dict], output_dir: str | Path, seed: int = 0) -> dict:
    """Nested benchmark evaluation, then select on all data and persist final model."""
    rows = _validated_rows(rows)
    benchmarks = sorted({row['benchmark'] for row in rows})
    if len(benchmarks) < 3:
        raise ValueError('nested area-model evaluation requires at least three benchmarks')
    folds = []
    pooled_truth: list[float] = []
    pooled_predictions: list[float] = []
    pooled_baseline: list[float] = []
    comparison = {name: {'truth': [], 'predicted': []} for name in MODEL_CONFIGS}
    for benchmark in benchmarks:
        train, test, excluded = benchmark_split(rows, benchmark)
        train = _unique_formulas(train)
        fold = {'held_out_benchmark': benchmark, 'train_formula_count': len(train), 'test_size': len(test),
                'train_benchmarks': sorted({row['benchmark'] for row in train}),
                'excluded_matching_formula_rows': excluded}
        if not train:
            fold['status'] = 'skipped_no_novel_training_formulas'
            folds.append(fold)
            continue
        # Keep all benchmark occurrences for inner grouping; fitting deduplicates
        # formulas, but removing occurrences before splitting could erase groups.
        outer_rows = [row for row in rows if row['benchmark'] != benchmark and
                      row['formula'] not in {item['formula'] for item in test}]
        chosen, selection = _select_model(outer_rows, seed)
        truth = [row['lut4_count'] for row in test]
        predictions = None
        by_estimator = {}
        for name in MODEL_CONFIGS:
            model = train_area_model(train, name, seed)
            predicted = [item['predicted_lut4'] for item in model.predict(test)]
            by_estimator[name] = _metrics(truth, predicted)
            comparison[name]['truth'].extend(truth)
            comparison[name]['predicted'].extend(predicted)
            if name == chosen:
                predictions = predicted
            if name == 'mean':
                baseline = predicted
        assert predictions is not None
        fold.update(status='evaluated', selected_estimator=chosen, inner_selection=selection,
                    metrics=_metrics(truth, predictions), mean_baseline_metrics=_metrics(truth, baseline),
                    metrics_by_estimator=by_estimator,
                    predictions=[{**{key: row[key] for key in ('candidate_id', 'formula') if key in row},
                                  'measured_lut4': actual, 'predicted_lut4': predicted,
                                  'mean_baseline_predicted_lut4': base}
                                 for row, actual, predicted, base in zip(test, truth, predictions, baseline)])
        folds.append(fold)
        pooled_truth.extend(truth)
        pooled_predictions.extend(predictions)
        pooled_baseline.extend(baseline)
    final_choice, final_selection = _select_model(rows, seed)
    final = train_area_model(rows, final_choice, seed)
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    training_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    provenance = {'training_dataset_sha256': training_hash,
                  'training_dataset_hash_method': 'SHA256 of sorted-key compact JSON of validated rows; LUT labels normalized to floats',
                  'synthesis_tools': sorted({row['synthesis_tool'] for row in rows if 'synthesis_tool' in row}),
                  'label_unit': 'SB_LUT4 cells from Yosys synth_ice40 defaults',
                  'rtl_source_hashes': sorted({row['rtl_sha256'] for row in rows if 'rtl_sha256' in row})}
    paths = save_area_model(final, directory, {'selection': final_selection, **provenance})
    report = {'method': 'nested leave-one-benchmark-out with identical-formula exclusion',
              'target': 'isolated iCE40 mapped SB_LUT4 count', 'measurement_source': 'rtl_synthesis',
              'seed': seed, 'row_count': len(rows), 'unique_formula_count': len({row['formula'] for row in rows}),
              'benchmark_count': len(benchmarks), 'feature_columns': list(AREA_FEATURE_COLUMNS),
              'candidate_model_configs': MODEL_CONFIGS, 'folds': folds,
              'pooled_metrics': _metrics(pooled_truth, pooled_predictions) if pooled_truth else None,
              'pooled_mean_baseline_metrics': _metrics(pooled_truth, pooled_baseline) if pooled_truth else None,
              'outer_model_comparison': {name: _metrics(values['truth'], values['predicted'])
                                         for name, values in comparison.items() if values['truth']},
              'final_selection': final_selection, 'final_estimator': final_choice, **paths, **provenance,
              'limitations': ['Synthesized LUT4 resources; no clock, physical area, or processor-speedup prediction.',
                              'Small candidate dataset; sampled benchmark families may not represent future workloads.',
                              'Final artifact refits all data; only outer-fold predictions measure unseen-benchmark performance.',
                              'Point predictions have no calibrated confidence intervals.']}
    if report['pooled_metrics'] is not None:
        actual, base = report['pooled_metrics'], report['pooled_mean_baseline_metrics']
        report['improvement_over_mean'] = {
            'mae_fraction': 1 - actual['mae_lut4'] / base['mae_lut4'] if base['mae_lut4'] else None,
            'rmsle_fraction': 1 - actual['rmsle'] / base['rmsle'] if base['rmsle'] else None}
    (directory / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def _read_rows(path: str) -> list[dict]:
    content = Path(path).read_text()
    try:
        rows = json.loads(content)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    if not isinstance(rows, list):
        raise ValueError('input must be a JSON array or JSONL rows')
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    train = subparsers.add_parser('train')
    train.add_argument('--rows', required=True)
    train.add_argument('--output-dir', required=True)
    train.add_argument('--seed', type=int, default=0)
    predict = subparsers.add_parser('predict')
    predict.add_argument('--model', required=True)
    predict.add_argument('--candidates', required=True)
    predict.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'train':
        report = evaluate_and_train(_read_rows(args.rows), args.output_dir, args.seed)
        print(json.dumps({key: report[key] for key in ('final_estimator', 'pooled_metrics', 'model_path')}, indent=2))
    else:
        model = load_area_model(args.model)
        predictions = model.predict(_read_rows(args.candidates))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(predictions, indent=2) + '\n')
        print(f'Wrote {len(predictions)} LUT4 predictions to {output}')
    return 0


if __name__ == '__main__':
    # Train through the canonical module so saved classes are importable by
    # other processes, rather than recorded as __main__.AreaPredictor.
    from isaforge.area_model import main as module_main
    raise SystemExit(module_main())

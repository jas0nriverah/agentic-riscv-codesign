"""Formula-only resource regression and a fixed residual ML LUT4 predictor.

The original benchmark corpus is development data for this version. Any honest
test of improvement requires independent labels collected after model freezing.
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

import numpy as np
from scipy.optimize import lsq_linear

from .area_model import (AREA_FEATURE_COLUMNS, _known_bits, _metrics, _read_rows,
                         _unique_formulas, _validated_rows, _versions,
                         area_feature_matrix, benchmark_split, train_area_model)
from .features import Expression, parse_formula

MASK = 2**32 - 1
SCHEMA_VERSION = 2
RESOURCE_COLUMNS = ('logic_bits', 'adder_active_bits', 'adder_overlap_bits',
                    'compare_bits', 'barrel_mux_bits', 'variable_mul_partial_products',
                    'constant_mul_adder_bits')
EXTRA_COLUMNS = RESOURCE_COLUMNS + (
    'live_operation_count', 'live_unknown_bits_sum', 'operand_unsigned_width_sum',
    'operand_signed_width_sum', 'multiply_operand_width_product_sum',
    'multiply_operand_width_product_max', 'multiply_output_demand_bits_sum',
    'multiply_operand_width_reduction_bits_sum', 'multiply_constant_popcount_sum',
    'multiply_constant_csd_terms_sum', 'shared_live_node_count',
)
FEATURE_COLUMNS = AREA_FEATURE_COLUMNS + EXTRA_COLUMNS
# Two deliberately fixed models, not a hyperparameter search. Coefficients of
# the resource model are fitted nonnegative in raw LUT4 units. The ML model
# learns a log residual against that extrapolating model.
MODEL_CONFIG = {
    'resource_ridge': {'ridge_alpha': 1.0, 'coefficient_prior': [1., 1., 1., 1., 1., 2., 1.],
                       'fit_intercept': False, 'nonnegative_coefficients': True},
    'resource_residual_xgb': {'n_estimators': 160, 'max_depth': 3, 'learning_rate': 0.07,
                             'min_child_weight': 2, 'reg_lambda': 2.0,
                             'target': 'log1p(label) - log1p(resource_ridge)',
                             'resource_feature_transform': 'log1p',
                             'residual_clip': [-2.0, 2.0]},
}


def _not(token):
    if isinstance(token, int):
        return 1 - token
    if token[0] == 'not':
        return token[1]
    return ('not', token)


@lru_cache(maxsize=65536)
def _symbols(node: Expression) -> tuple:
    """Track constants, wiring and sign-bit copies; other bits stay opaque.

    This is not a symbolic circuit simulator. Opaque bits preserve identity only
    for identical subexpressions. In particular we never assume independent
    sign-extension bits are fresh variables when estimating multiplier widths.
    """
    if not node.children:
        if isinstance(node.value, int):
            return tuple((node.value >> bit) & 1 for bit in range(32))
        return tuple(('input', node.value, bit) for bit in range(32))
    children = [_symbols(child) for child in node.children]
    a = children[0]
    op = str(node.value)
    z, o = _known_bits(node)
    output = [0 if z & (1 << bit) else 1 if o & (1 << bit)
              else ('opaque', node.canonical(), bit) for bit in range(32)]
    if op == 'lui':
        return a
    b = children[1]
    if op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'):
        for bit, (x, y) in enumerate(zip(a, b)):
            if op in ('and', 'andi'):
                if x == 0 or y == 0: output[bit] = 0
                elif x == 1 or x == y: output[bit] = y
                elif y == 1: output[bit] = x
                elif x == _not(y): output[bit] = 0
            elif op in ('or', 'ori'):
                if x == 1 or y == 1: output[bit] = 1
                elif x == 0 or x == y: output[bit] = y
                elif y == 0: output[bit] = x
                elif x == _not(y): output[bit] = 1
            else:
                if x == y: output[bit] = 0
                elif x == 0: output[bit] = y
                elif y == 0: output[bit] = x
                elif x == 1: output[bit] = _not(y)
                elif y == 1: output[bit] = _not(x)
                elif x == _not(y): output[bit] = 1
    elif op in ('add', 'addi', 'sub'):
        if all(token == 0 for token in b): return a
        if op != 'sub' and all(token == 0 for token in a): return b
        if op != 'sub':
            if a == b:
                return (0,) + a[:31]
            # Disjoint possibly-one bit positions cannot generate a carry.
            if not any(x != 0 and y != 0 for x, y in zip(a, b)):
                return tuple(y if x == 0 else x for x, y in zip(a, b))
    elif op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai') and all(
            isinstance(token, int) for token in b[:5]):
        shift = sum(token << bit for bit, token in enumerate(b[:5]))
        for bit in range(32):
            source = bit - shift if op in ('sll', 'slli') else bit + shift
            output[bit] = a[source] if 0 <= source < 32 else (
                a[31] if op in ('sra', 'srai') else 0)
    elif op in ('mul', 'mulh', 'mulhu', 'mulhsu'):
        aw = max((i+1 for i, token in enumerate(a) if token != 0), default=0)
        bw = max((i+1 for i, token in enumerate(b) if token != 0), default=0)
        if op == 'mul':
            for variable, constant in ((a, b), (b, a)):
                if all(isinstance(token, int) for token in constant):
                    value = sum(token << bit for bit, token in enumerate(constant))
                    if value and value & (value - 1) == 0:
                        shift = value.bit_length() - 1
                        return tuple(variable[bit-shift] if bit >= shift else 0 for bit in range(32))
            for bit in range(min(aw+bw, 32), 32): output[bit] = 0
        elif aw+bw <= 32 and (op == 'mulhu' or a[31] == 0 and (op == 'mulhsu' or b[31] == 0)):
            return (0,) * 32
    return tuple(output)


def _widths(tokens: tuple) -> tuple[int, int]:
    unsigned = max((bit + 1 for bit, token in enumerate(tokens) if token != 0), default=0)
    signed = 32
    while signed > 1 and tokens[signed-2] == tokens[31]:
        signed -= 1
    return unsigned, signed


def _constant(tokens: tuple) -> int | None:
    return sum(token << bit for bit, token in enumerate(tokens)) if all(
        isinstance(token, int) for token in tokens) else None


def _csd_terms(value: int) -> int:
    """Number of nonzero canonical signed digits, a shift/add sparsity proxy."""
    value = abs(value)
    count = 0
    while value:
        if value & 1:
            value -= 2 - (value & 3)
            count += 1
        value >>= 1
    return count


@lru_cache(maxsize=16384)
def _resource_features(formula: str) -> tuple[float, ...]:
    root = parse_formula(formula)
    nodes: dict[str, Expression] = {}
    references: dict[str, int] = {}

    def collect(node: Expression):
        key = node.canonical()
        references[key] = references.get(key, 0) + 1
        if key in nodes: return
        for child in node.children: collect(child)
        nodes[key] = node
    collect(root)
    demanded: dict[str, int] = {}

    def demand(node: Expression, bits: int):
        key = node.canonical()
        symbols = _symbols(node)
        bits &= sum(1 << i for i, token in enumerate(symbols) if not isinstance(token, int))
        new = bits & ~demanded.get(key, 0)
        if not new: return
        demanded[key] = demanded.get(key, 0) | bits
        if not node.children: return
        op = str(node.value)
        if op == 'lui':
            demand(node.children[0], new)
            return
        a, b = node.children
        asy, bsy = _symbols(a), _symbols(b)
        if op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'):
            # Known output bits have already been removed; pass remaining bits.
            demand(a, new); demand(b, new)
        elif op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
            z, o = _known_bits(b)
            possibilities = [d for d in range(32) if d & (z & 31) == 0 and d & (o & 31) == o & 31]
            source_bits = 0
            for distance in possibilities:
                for bit in range(32):
                    if not new & (1 << bit): continue
                    source = bit-distance if op in ('sll', 'slli') else bit+distance
                    if 0 <= source < 32: source_bits |= 1 << source
                    elif op in ('sra', 'srai'): source_bits |= 1 << 31
            demand(a, source_bits); demand(b, 31)
        elif op == 'mul':
            # A power-of-two constant multiplier is wiring, with shifted demand.
            for variable, constant in ((a, b), (b, a)):
                value = _constant(_symbols(constant))
                if value is not None and value and value & (value-1) == 0:
                    demand(variable, new >> (value.bit_length()-1))
                    return
            upto = (1 << new.bit_length()) - 1
            demand(a, upto); demand(b, upto)
        elif op in ('add', 'addi', 'sub'):
            if op != 'sub' and asy == bsy:
                demand(a, new >> 1)
                return
            if _symbols(node) == asy:
                demand(a, new)
                return
            if _symbols(node) == bsy:
                demand(b, new)
                return
            if op != 'sub' and not any(x != 0 and y != 0 for x, y in zip(asy, bsy)):
                demand(a, new); demand(b, new)
                return
            # Carry chains require every lower operand bit, including bits whose
            # own output is discarded. This is deliberately conservative.
            upto = (1 << new.bit_length()) - 1
            demand(a, upto); demand(b, upto)
        else:
            demand(a, MASK); demand(b, MASK)
    demand(root, MASK)
    values = dict.fromkeys(EXTRA_COLUMNS, 0.)
    for key, node in nodes.items():
        bits = demanded.get(key, 0)
        if not bits or not node.children: continue
        values['live_operation_count'] += 1
        values['live_unknown_bits_sum'] += bits.bit_count()
        values['shared_live_node_count'] += int(references[key] > 1)
        op = str(node.value)
        sy = _symbols(node)
        child_sy = [_symbols(child) for child in node.children]
        for tokens in child_sy:
            uw, sw = _widths(tokens)
            values['operand_unsigned_width_sum'] += uw
            values['operand_signed_width_sum'] += sw
        if op == 'lui': continue
        a, b = child_sy
        if op in ('and', 'andi', 'or', 'ori', 'xor', 'xori'):
            values['logic_bits'] += sum(bool(bits & (1 << bit)) and sy[bit] not in (a[bit], b[bit])
                                        for bit in range(32))
        elif op in ('add', 'addi', 'sub'):
            if sy == a or sy == b or op != 'sub' and (
                    a == b or not any(x != 0 and y != 0 for x, y in zip(a, b))):
                continue
            upto = bits.bit_length()
            values['adder_active_bits'] += sum(not isinstance(sy[bit], int) for bit in range(upto))
            values['adder_overlap_bits'] += sum(a[bit] != 0 and b[bit] != 0 for bit in range(upto))
        elif op in ('slt', 'slti', 'sltu', 'sltiu'):
            values['compare_bits'] += max(_widths(a)[0], _widths(b)[0])
        elif op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
            stages = sum(not isinstance(token, int) for token in b[:5])
            values['barrel_mux_bits'] += stages * bits.bit_count()
        elif op in ('mul', 'mulh', 'mulhu', 'mulhsu'):
            aw, asign = _widths(a); bw, bsign = _widths(b)
            # Low multiplication is modulo 2**32, so either signed or unsigned
            # representation can reduce an operand. High-half signedness is
            # instruction-specific. Sign handling is an approximation, not RTL.
            aw = min(aw, asign) if op in ('mul', 'mulh', 'mulhsu') else aw
            bw = min(bw, bsign) if op in ('mul', 'mulh') else bw
            product = aw * bw
            values['multiply_operand_width_product_sum'] += product
            values['multiply_operand_width_product_max'] = max(values['multiply_operand_width_product_max'], product)
            values['multiply_operand_width_reduction_bits_sum'] += 64-aw-bw
            values['multiply_output_demand_bits_sum'] += bits.bit_count()
            high = bits.bit_length()-1 + (32 if op != 'mul' else 0)
            const_a, const_b = _constant(a), _constant(b)
            if const_a is None and const_b is None:
                values['variable_mul_partial_products'] += sum(i+j <= high for i in range(aw) for j in range(bw))
            else:
                constant, width = (const_a, bw) if const_a is not None else (const_b, aw)
                assert constant is not None
                signed_constant = constant - 2**32 if constant & 2**31 else constant
                terms = _csd_terms(signed_constant)
                values['multiply_constant_popcount_sum'] += constant.bit_count()
                values['multiply_constant_csd_terms_sum'] += terms
                positions = [i for i in range(32) if constant & (1 << i)]
                # First shift is wiring; each remaining binary partial row
                # requires an adder over the live overlapping operand width.
                lanes = [max(0, min(width, high-i+1)) for i in positions]
                values['constant_mul_adder_bits'] += max(0, sum(lanes)-max(lanes, default=0))
    return tuple(float(values[column]) for column in EXTRA_COLUMNS)


def feature_matrix(rows: list[dict]) -> np.ndarray:
    """Formula is the sole input; no measurement or trace fields are consulted."""
    if not rows: return np.empty((0, len(FEATURE_COLUMNS)))
    extra = np.asarray([_resource_features(parse_formula(row['formula']).canonical()) for row in rows])
    return np.column_stack((area_feature_matrix(rows), extra))


def resource_matrix(rows: list[dict]) -> np.ndarray:
    x = feature_matrix(rows)
    start = len(AREA_FEATURE_COLUMNS)
    return x[:, start:start+len(RESOURCE_COLUMNS)]


def _ml_matrix(rows: list[dict], baseline: np.ndarray) -> np.ndarray:
    x = feature_matrix(rows)
    x[:, len(AREA_FEATURE_COLUMNS):] = np.log1p(x[:, len(AREA_FEATURE_COLUMNS):])
    return np.column_stack((x, np.log1p(baseline)))


@dataclass
class ResourcePredictor:
    coefficients: np.ndarray
    training_formula_count: int
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS

    def values(self, rows: list[dict]) -> np.ndarray:
        if self.feature_columns != FEATURE_COLUMNS: raise ValueError('v2 feature schema mismatch')
        values = resource_matrix(rows) @ self.coefficients
        if not np.isfinite(values).all(): raise ValueError('nonfinite resource prediction')
        return np.maximum(values, 0)

    def predict(self, rows: list[dict]) -> list[dict]:
        return _predictions(rows, self.values(rows), 'resource_ridge')


@dataclass
class ResidualPredictor:
    baseline: ResourcePredictor
    estimator: Any
    seed: int
    training_formula_count: int
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS

    def predict(self, rows: list[dict]) -> list[dict]:
        if self.feature_columns != FEATURE_COLUMNS: raise ValueError('v2 feature schema mismatch')
        if not rows: return []
        base = self.baseline.values(rows)
        correction = np.clip(self.estimator.predict(_ml_matrix(rows, base)),
                             *MODEL_CONFIG['resource_residual_xgb']['residual_clip'])
        values = np.maximum(np.expm1(np.log1p(base) + correction), 0)
        # Abstractly proved constant or entirely wire-only expressions cost zero.
        values[np.all(resource_matrix(rows) == 0, axis=1)] = 0
        if not np.isfinite(values).all(): raise ValueError('nonfinite v2 prediction')
        return _predictions(rows, values, 'resource_residual_xgb')


def _predictions(rows, values, name):
    return [{**{key: row[key] for key in ('candidate_id', 'benchmark', 'formula') if key in row},
             'predicted_lut4': float(value), 'model': name,
             'target': 'isolated iCE40 mapped SB_LUT4 count'} for row, value in zip(rows, values)]


def train_resource_model(rows: list[dict]) -> ResourcePredictor:
    rows = _unique_formulas(_validated_rows(rows))
    x = resource_matrix(rows)
    y = np.asarray([row['lut4_count'] for row in rows])
    options = MODEL_CONFIG['resource_ridge']
    # Resource columns have physical units. Penalize dimensionless relative
    # coefficient deviation from an elementary one/two LUT-per-bit prior.
    prior = np.asarray(options['coefficient_prior'])
    penalty = np.sqrt(options['ridge_alpha']) * np.eye(len(RESOURCE_COLUMNS))
    fit = lsq_linear(np.vstack((x, penalty)), np.concatenate((y, penalty @ prior)),
                     bounds=(0, np.inf), tol=1e-10)
    if not fit.success: raise ValueError(f'resource regression failed: {fit.message}')
    return ResourcePredictor(fit.x, len(rows))


def train_v2_model(rows: list[dict], seed: int = 20261013) -> ResidualPredictor:
    from xgboost import XGBRegressor
    rows = _unique_formulas(_validated_rows(rows))
    baseline = train_resource_model(rows)
    base = baseline.values(rows)
    y = np.log1p([row['lut4_count'] for row in rows]) - np.log1p(base)
    config = MODEL_CONFIG['resource_residual_xgb']
    kwargs = {key: config[key] for key in ('n_estimators', 'max_depth', 'learning_rate', 'min_child_weight', 'reg_lambda')}
    estimator = XGBRegressor(**kwargs, random_state=seed, n_jobs=1,
                             objective='reg:squarederror', tree_method='hist', verbosity=0)
    estimator.fit(_ml_matrix(rows, base), y)
    return ResidualPredictor(baseline, estimator, seed, len(rows))


def _source_hashes() -> dict[str, str]:
    directory = Path(__file__).parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ('area_model_v2.py', 'area_model.py', 'features.py', 'rtl.py')}


def save_model(model: ResourcePredictor | ResidualPredictor, directory: str | Path,
               name: str, metadata: dict | None = None) -> dict:
    import joblib
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / f'{name}.joblib'
    joblib.dump(model, artifact)
    schema = {'schema_version': SCHEMA_VERSION, 'feature_columns': list(FEATURE_COLUMNS),
              'model_name': name, 'model_configs': MODEL_CONFIG, 'versions': _versions(),
              'training_formula_count': model.training_formula_count,
              'trained_at_utc': datetime.now(timezone.utc).isoformat(),
              'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
              'module_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'runtime_source_sha256': _source_hashes(),
              **(metadata or {})}
    schema_path = artifact.with_suffix('.json')
    schema_path.write_text(json.dumps(schema, indent=2) + '\n')
    return {'model_path': str(artifact), 'schema_path': str(schema_path),
            'artifact_sha256': schema['artifact_sha256']}


def load_model(path: str | Path) -> ResourcePredictor | ResidualPredictor:
    """Load a trusted local pickle only, checking artifact and runtime schemas."""
    import joblib
    path = Path(path)
    schema = json.loads(path.with_suffix('.json').read_text())
    if schema.get('schema_version') != SCHEMA_VERSION or schema.get('feature_columns') != list(FEATURE_COLUMNS):
        raise ValueError('v2 feature/schema mismatch')
    if schema.get('model_configs') != MODEL_CONFIG: raise ValueError('v2 configuration mismatch')
    if schema.get('artifact_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('v2 artifact hash mismatch')
    if schema.get('module_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('v2 runtime source differs from frozen artifact')
    if schema.get('runtime_source_sha256') != _source_hashes():
        raise ValueError('v2 runtime dependency source differs from frozen artifact')
    model = joblib.load(path)
    if not isinstance(model, (ResourcePredictor, ResidualPredictor)) or model.feature_columns != FEATURE_COLUMNS:
        raise ValueError('invalid v2 artifact')
    return model


def load_area_model_v2(path: str | Path) -> ResourcePredictor | ResidualPredictor:
    """Public inference entry point matching the v1 row/prediction interface."""
    return load_model(path)


def develop_and_freeze(rows: list[dict], directory: str | Path, seed: int = 20261013) -> dict:
    """Exploratory original-corpus grouped comparison, then frozen full refits.

    No nested or unbiased claim is made: v1 outer predictions motivated v2.
    Fresh unseen-family labels must remain inaccessible until this is saved.
    """
    rows = _validated_rows(rows)
    pooled = {name: {'truth': [], 'predicted': []} for name in ('resource_ridge', 'resource_residual_xgb', 'v1_xgboost_log')}
    folds = []
    for benchmark in sorted({row['benchmark'] for row in rows}):
        train, test, excluded = benchmark_split(rows, benchmark)
        if not train: continue
        models = {'resource_ridge': train_resource_model(train),
                  'resource_residual_xgb': train_v2_model(train, seed),
                  'v1_xgboost_log': train_area_model(train, 'xgboost_log', seed)}
        truth = [row['lut4_count'] for row in test]
        fold = {'held_out_benchmark': benchmark, 'test_size': len(test),
                'train_formula_count': len(_unique_formulas(train)),
                'excluded_matching_formula_rows': excluded, 'metrics': {}, 'predictions': {}}
        for name, model in models.items():
            predictions = model.predict(test)
            predicted = [row['predicted_lut4'] for row in predictions]
            pooled[name]['truth'].extend(truth); pooled[name]['predicted'].extend(predicted)
            fold['metrics'][name] = _metrics(truth, predicted)
            fold['predictions'][name] = [{**prediction, 'measured_lut4': actual} for prediction, actual in zip(predictions, truth)]
        folds.append(fold)
    dataset_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    metadata = {'training_dataset_sha256': dataset_hash,
                'training_dataset_hash_method': 'sorted-key compact JSON of validated rows; labels normalized to floats',
                'benchmark_names': sorted({row['benchmark'] for row in rows}), 'training_row_count': len(rows),
                'evaluation_status': 'frozen before new-family evaluation; original-corpus results exploratory',
                'target': 'isolated iCE40 mapped SB_LUT4 count', 'measurement_source': 'rtl_synthesis',
                'seed': seed}
    baseline = train_resource_model(rows)
    model = train_v2_model(rows, seed)
    paths = {'resource_ridge': save_model(baseline, directory, 'resource-ridge', metadata),
             'resource_residual_xgb': save_model(model, directory, 'area-model-v2', metadata)}
    report = {**metadata, 'method': 'exploratory benchmark holdout with identical-formula exclusion',
              'model_configs': MODEL_CONFIG, 'folds': folds,
              'pooled_metrics': {name: _metrics(values['truth'], values['predicted']) for name, values in pooled.items()},
              'resource_coefficients': dict(zip(RESOURCE_COLUMNS, baseline.coefficients.tolist())),
              'artifacts': paths,
              'limitations': ['Old-corpus grouped scores are development results and cannot establish unbiased v2 improvement.',
                              'Approximate combinational resource proxies are not synthesis, physical area, timing, or CPU speedup.',
                              'Only nine distinct multiplication formulas existed in the original corpus.',
                              'Fresh-family evaluation must use these frozen artifacts without retraining or changing configuration.']}
    directory = Path(directory)
    (directory / 'development-evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    preregistration = {**metadata, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                      'artifacts': paths, 'model_configs': MODEL_CONFIG,
                      'module_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'runtime_source_sha256': _source_hashes(),
                      'feature_columns': list(FEATURE_COLUMNS),
                      'primary_metric': 'pooled RMSLE on fresh formulas absent from the original training corpus',
                      'secondary_metrics': ['MAE LUT4', 'Spearman', 'nonzero-LUT4 RMSLE/MAE/Spearman', 'per-family metrics'],
                      'comparators': ['frozen original v1 XGBoost', 'frozen resource_ridge'],
                      'reporting': 'Report all models, all families, novel and overlapping formula subsets; no refit or winner substitution.'}
    (directory / 'preregistration.json').write_text(json.dumps(preregistration, indent=2) + '\n')
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    train = commands.add_parser('train')
    train.add_argument('--rows', required=True); train.add_argument('--output-dir', required=True)
    train.add_argument('--seed', type=int, default=20261013)
    predict = commands.add_parser('predict')
    predict.add_argument('--model', required=True); predict.add_argument('--candidates', required=True)
    predict.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'train':
        report = develop_and_freeze(_read_rows(args.rows), args.output_dir, args.seed)
        print(json.dumps({'exploratory_pooled_metrics': report['pooled_metrics'], 'artifacts': report['artifacts']}, indent=2))
    else:
        predictions = load_model(args.model).predict(_read_rows(args.candidates))
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(predictions, indent=2) + '\n')
        print(f'Wrote {len(predictions)} LUT4 predictions to {output}')
    return 0


if __name__ == '__main__':
    # The canonical module owns persisted classes. Executing training directly
    # in __main__ would produce an artifact that ordinary library loading cannot
    # unpickle in another process.
    from .area_model_v2 import main as canonical_main
    raise SystemExit(canonical_main())

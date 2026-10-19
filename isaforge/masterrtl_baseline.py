"""Matched MasterRTL area-recipe adaptation for isolated iCE40 LUT4 labels.

This is a retrained adaptation of the public 14-feature SOG / 25-tree depth-12
XGBoost recipe, not the paper's ASIC-area model or a reproduction of its scores.
Inference needs label-free Yosys pre-ABC bit-graph extraction on cache misses.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

import numpy as np
from threadpoolctl import threadpool_limits

from .area_model import _read_rows, _unique_formulas, _validated_rows, _versions, benchmark_split
from .area_model_v3 import _macro, metrics
from .features import parse_formula
from .rtl import generate_rtl
from .synthesis import _yosys_quote

SCHEMA_VERSION = 1
REFERENCE_COMMIT = '5bccf38f8db7bb511a793a709863e7cb1b333ab5'
REFERENCE_URL = 'https://github.com/hkust-zhiyao/MasterRTL'
REFERENCE_FILES = ('ML_model/train/train.py', 'ML_model/train/preprocess.py',
                   'vlg2ir/graph_stat.py', 'feature_extract/area/feature_extra_graph_stat.py',
                   'ys_script/run_TinyRocket_sog.ys', 'std_PPA.json')
FEATURE_COLUMNS = ('dff_bits', 'register_fanout', 'io_bits', 'and_count', 'or_count',
                   'not_count', 'xor_count', 'mux_count', 'estimated_sequential_area',
                   'estimated_combinational_area', 'estimated_total_area',
                   'estimated_static_power', 'estimated_dynamic_power', 'estimated_total_power')
# Exact values for the five SOG primitive operators in the public std_PPA.json.
WEIGHTS = {'area_comb': {'And': 1.064, 'Or': 1.064, 'Unot': 0.798, 'Xor': 1.596, 'Mux': 1.862},
           'stat_pwr': {'And': 0.02507, 'Or': 0.02269, 'Unot': 0.106, 'Xor': 0.03616, 'Mux': 0.03593},
           'dyn_pwr': {'And': 3.1, 'Or': 3.1, 'Unot': 1.8, 'Xor': 2.45, 'Mux': 2.6}}
PRIMITIVE_TYPES = {'$_AND_': 'And', '$_OR_': 'Or', '$_NOT_': 'Unot', '$_XOR_': 'Xor', '$_MUX_': 'Mux'}
PIPELINE = 'hierarchy -check -top candidate; proc; flatten; opt; fsm; opt; memory; opt; techmap; opt'
MODEL_CONFIG = {'n_estimators': 25, 'max_depth': 12, 'n_jobs': 1, 'random_state': 20261013,
                'target_transform': 'none', 'other_xgboost_parameters': 'installed-library defaults',
                'nonnegative_prediction_clip': True, 'feature_recipe': 'MasterRTL public cal_oper 14-feature area recipe',
                'pipeline': PIPELINE, 'primitive_weights': WEIGHTS}
TARGET = 'isolated iCE40 mapped SB_LUT4 count'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_hashes():
    directory = Path(__file__).parent
    return {name: _sha(directory/name) for name in ('masterrtl_baseline.py', 'synthesis.py',
        'area_model_v3.py', 'structural_features_v3.py', 'area_model_v2.py', 'area_model.py', 'features.py', 'rtl.py')}


@lru_cache(maxsize=8)
def _tool_identity(executable, size, mtime):
    version = subprocess.run([executable, '-V'], check=True, capture_output=True, text=True).stdout.strip()
    return {'executable': executable, 'version': version, 'executable_sha256': _sha(executable)}


def tool_identity(yosys='yosys'):
    executable = shutil.which(yosys)
    if executable is None: raise RuntimeError('Yosys is required for MasterRTL SOG feature extraction')
    executable = str(Path(executable).resolve())
    stat = Path(executable).stat()
    return _tool_identity(executable, stat.st_size, stat.st_mtime_ns).copy()


def netlist_features(netlist):
    """Apply cal_oper to one-bit pre-ABC JSON primitive operators.

    Direct JSON traversal replaces Pyverilog graph parsing. Each primitive
    output is one bit, so operator count and area-weighted width coincide.
    Sequential/register-fanout entries are zero for this combinational scope.
    """
    module = netlist['modules']['candidate']
    counts = Counter(cell['type'] for cell in module.get('cells', {}).values())
    unsupported = set(counts) - set(PRIMITIVE_TYPES)
    if unsupported: raise ValueError(f'unsupported pre-ABC SOG cell types: {sorted(unsupported)}')
    for cell in module.get('cells', {}).values():
        outputs = [bits for name, bits in cell['connections'].items() if cell['port_directions'][name] == 'output']
        if len(outputs) != 1 or len(outputs[0]) != 1: raise ValueError('SOG primitive must have exactly one single-bit output')
    io = sum(len(port['bits']) for port in module.get('ports', {}).values())
    operators = {op: counts[typ] for typ, op in PRIMITIVE_TYPES.items()}
    weighted = {kind: float(round(sum(operators[op] * value for op, value in weights.items()), 0))
                for kind, weights in WEIGHTS.items()}
    comb, static, dynamic = (weighted[name] for name in ('area_comb', 'stat_pwr', 'dyn_pwr'))
    vector = [0., 0., float(io), float(operators['And']), float(operators['Or']), float(operators['Unot']),
              float(operators['Xor']), float(operators['Mux']), 0., comb, comb, static, dynamic, static+dynamic]
    return vector, dict(sorted(counts.items()))


class SOGExtractor:
    def __init__(self, cache_dir, *, yosys='yosys', timeout=900, frozen_tool=None):
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tool = dict(frozen_tool) if frozen_tool is not None else tool_identity(yosys)
        self.yosys = yosys
        self.source_hashes = _source_hashes()
        self.timeout = timeout
        self.context = {'pipeline': PIPELINE, 'tool': self.tool,
                        'runtime_source_sha256': self.source_hashes,
                        'feature_columns': list(FEATURE_COLUMNS), 'weights': WEIGHTS}

    def key(self, formula):
        canonical = parse_formula(formula).canonical()
        key = hashlib.sha256(json.dumps({'formula': canonical, **self.context}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return canonical, key

    def extract(self, formula):
        canonical, key = self.key(formula)
        directory = self.cache_dir/key
        record_path = directory/'features.json'
        if record_path.exists():
            record = json.loads(record_path.read_text())
            if record.get('cache_key') != key or record.get('formula') != canonical or record.get('context') != self.context:
                raise ValueError('SOG cache context or formula mismatch')
            vector = record.get('feature_values')
            if not isinstance(vector, list) or len(vector) != len(FEATURE_COLUMNS) or not np.isfinite(vector).all() or np.any(np.asarray(vector) < 0):
                raise ValueError('invalid cached SOG feature vector')
            digest = hashlib.sha256(json.dumps(vector, separators=(',', ':')).encode()).hexdigest()
            if record.get('feature_values_sha256') != digest: raise ValueError('SOG cached features hash mismatch')
            for filename in ('candidate.v', 'sog.ys', 'sog.json', 'sog.v', 'sog.log'):
                if not (directory/filename).exists() or _sha(directory/filename) != record.get('files_sha256', {}).get(filename):
                    raise ValueError('SOG retained source/netlist/log hash mismatch')
            derived, counts = netlist_features(json.loads((directory/'sog.json').read_text()))
            if derived != vector or counts != record.get('primitive_cell_counts'):
                raise ValueError('SOG cached features differ from retained primitive graph')
            return record, True
        directory.mkdir(parents=True, exist_ok=True)
        actual_tool = tool_identity(self.yosys)
        if any(actual_tool[key] != self.tool[key] for key in ('version', 'executable_sha256')):
            raise ValueError('MasterRTL cold extraction requires the frozen Yosys version and executable hash')
        started = time.perf_counter()
        rtl = directory/'candidate.v'; rtl.write_text(generate_rtl(canonical))
        netlist = directory/'sog.json'; sog = directory/'sog.v'
        script = directory/'sog.ys'
        script.write_text(f'read_verilog {_yosys_quote(rtl)}\n{PIPELINE}\ncheck -assert\nwrite_json {_yosys_quote(netlist)}\nwrite_verilog {_yosys_quote(sog)}\nstat\n')
        process = subprocess.run([actual_tool['executable'], '-s', str(script)], capture_output=True, text=True, timeout=self.timeout)
        log = directory/'sog.log'; log.write_text(process.stdout+process.stderr)
        if process.returncode: raise RuntimeError(f'Yosys pre-ABC extraction failed; see {log}')
        vector, counts = netlist_features(json.loads(netlist.read_text()))
        record = {'formula': canonical, 'cache_key': key, 'context': self.context,
                  'feature_values': vector, 'feature_values_sha256': hashlib.sha256(json.dumps(vector, separators=(',', ':')).encode()).hexdigest(),
                  'primitive_cell_counts': counts, 'cold_extraction_seconds': time.perf_counter()-started,
                  'files_sha256': {path.name: _sha(path) for path in (rtl, script, netlist, sog, log)},
                  'extracted_at_utc': datetime.now(timezone.utc).isoformat()}
        temporary = directory/'features.json.tmp'; temporary.write_text(json.dumps(record, indent=2)+'\n'); temporary.replace(record_path)
        return record, False

    def matrix(self, rows, workers=1):
        formulas = [row['formula'] for row in rows]
        if not formulas: return np.empty((0, len(FEATURE_COLUMNS)))
        if workers == 1:
            results = [self.extract(formula) for formula in formulas]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(self.extract, formulas))
        return np.asarray([record['feature_values'] for record, cached in results], dtype=float)


def collect_features(rows, cache_dir, workers=2):
    extractor = SOGExtractor(cache_dir)
    unique = _unique_formulas([{'formula': parse_formula(row['formula']).canonical()} for row in rows])
    started = time.perf_counter()
    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (record, cached) in enumerate(pool.map(extractor.extract, [row['formula'] for row in unique]), 1):
            records.append({'formula': record['formula'], 'cache_key': record['cache_key'],
                            'feature_values': record['feature_values'], 'primitive_cell_counts': record['primitive_cell_counts'],
                            'cache_hit': cached, 'cold_extraction_seconds': record['cold_extraction_seconds'],
                            'features_json_sha256': _sha(extractor.cache_dir/record['cache_key']/'features.json')})
            if index % 50 == 0: print(f'Extracted {index}/{len(unique)} SOG feature vectors', flush=True)
    cold_batch = time.perf_counter()-started
    warm_started = time.perf_counter(); extractor.matrix(unique, workers=workers)
    warm_batch = time.perf_counter()-warm_started
    return {'formula_count': len(unique), 'worker_count': workers, 'initial_batch_seconds': cold_batch,
            'initial_cache_hit_count': sum(record['cache_hit'] for record in records),
            'warm_cached_feature_batch_seconds': warm_batch, 'tool': extractor.tool,
            'runtime_source_sha256': extractor.source_hashes, 'feature_columns': list(FEATURE_COLUMNS),
            'records': records}


@dataclass
class MasterRTLPredictor:
    estimator: Any
    training_formula_count: int
    cache_dir: str
    frozen_tool: dict | None = None
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS

    def predict(self, rows):
        if self.feature_columns != FEATURE_COLUMNS: raise ValueError('MasterRTL feature schema mismatch')
        if not rows: return []
        x = SOGExtractor(self.cache_dir, frozen_tool=self.frozen_tool).matrix(rows)
        values = np.maximum(np.asarray(self.estimator.predict(x), dtype=float), 0)
        if not np.isfinite(values).all(): raise ValueError('nonfinite MasterRTL prediction')
        return [{**{key: row[key] for key in ('candidate_id', 'benchmark', 'formula') if key in row},
                 'predicted_lut4': float(value), 'model': 'masterrtl_sog', 'target': TARGET}
                for row, value in zip(rows, values)]


def train_model(rows, cache_dir):
    from xgboost import XGBRegressor
    rows = _unique_formulas(_validated_rows(rows))
    x = SOGExtractor(cache_dir).matrix(rows)
    model = XGBRegressor(n_estimators=MODEL_CONFIG['n_estimators'], max_depth=MODEL_CONFIG['max_depth'],
                         n_jobs=MODEL_CONFIG['n_jobs'], random_state=MODEL_CONFIG['random_state'])
    model.fit(x, np.asarray([row['lut4_count'] for row in rows], dtype=float))
    return MasterRTLPredictor(model, len(rows), str(Path(cache_dir).resolve()), tool_identity())


def reference_provenance(directory):
    directory = Path(directory).resolve()
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=directory, check=True, capture_output=True, text=True).stdout.strip()
    if commit != REFERENCE_COMMIT: raise ValueError('MasterRTL reference commit differs from preregistered recipe')
    standard = json.loads((directory/'std_PPA.json').read_text())
    if any(standard[kind][op] != value for kind, values in WEIGHTS.items() for op, value in values.items()):
        raise ValueError('embedded primitive weights differ from reference')
    return {'repository': REFERENCE_URL, 'commit': commit,
            'source_file_sha256': {name: _sha(directory/name) for name in REFERENCE_FILES}}


def save_model(model, directory, metadata=None):
    import joblib
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=True)
    path = directory/'masterrtl-sog.joblib'; joblib.dump(model, path)
    schema = {**(metadata or {}), 'schema_version': SCHEMA_VERSION, 'feature_columns': list(FEATURE_COLUMNS),
              'model_config': MODEL_CONFIG, 'target': TARGET, 'training_formula_count': model.training_formula_count,
              'versions': _versions(), 'trained_at_utc': datetime.now(timezone.utc).isoformat(),
              'artifact_sha256': _sha(path), 'runtime_source_sha256': _source_hashes(),
              'feature_cache_dir': model.cache_dir, 'tool': tool_identity(),
              'fitted_xgboost_parameters': model.estimator.get_params()}
    schema_path = path.with_suffix('.json'); schema_path.write_text(json.dumps(schema, indent=2)+'\n')
    return {'model_path': str(path), 'schema_path': str(schema_path), 'artifact_sha256': schema['artifact_sha256']}


def load_model(path, cache_dir=None):
    """Load a trusted local artifact and verify its frozen recipe and runtime."""
    import joblib
    path = Path(path); schema = json.loads(path.with_suffix('.json').read_text())
    if schema.get('schema_version') != SCHEMA_VERSION or schema.get('feature_columns') != list(FEATURE_COLUMNS):
        raise ValueError('MasterRTL feature/schema mismatch')
    if schema.get('model_config') != MODEL_CONFIG: raise ValueError('MasterRTL configuration mismatch')
    if schema.get('artifact_sha256') != _sha(path): raise ValueError('MasterRTL artifact hash mismatch')
    if schema.get('runtime_source_sha256') != _source_hashes(): raise ValueError('MasterRTL runtime source differs from frozen artifact')
    model = joblib.load(path)
    if not isinstance(model, MasterRTLPredictor) or model.feature_columns != FEATURE_COLUMNS:
        raise ValueError('invalid MasterRTL artifact')
    model.cache_dir = str(Path(cache_dir).resolve()) if cache_dir is not None else str(path.resolve().parent/'sog-cache')
    model.frozen_tool = dict(schema['tool'])
    return model


@threadpool_limits.wrap(limits=1, user_api='blas')
def develop_and_freeze(rows, probe_inputs, directory, reference_dir, workers=2):
    rows = _validated_rows(rows)
    directory = Path(directory).resolve(); directory.mkdir(parents=True, exist_ok=True)
    if (directory/'preregistration.json').exists(): raise ValueError('MasterRTL output directory is already frozen')
    if len({row['benchmark'] for row in rows}) < 3: raise ValueError('development evaluation requires at least three programs')
    # No measurement, verification or trace fields from probe inputs are read.
    probe_formulas = [{'formula': parse_formula(row['formula']).canonical()} for row in probe_inputs]
    cache_dir = directory/'sog-cache'
    source_snapshot = _source_hashes()
    provenance = reference_provenance(reference_dir)
    protocol_path = Path(__file__).resolve().parents[1]/'docs/masterrtl-matched-protocol.md'
    metadata = {'reference_provenance': provenance,
                'training_dataset_sha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'training_dataset_hash_method': 'sorted-key compact JSON of validated rows with float normalized labels',
                'training_row_count': len(rows), 'unique_formula_count': len(_unique_formulas(rows)),
                'benchmark_names': sorted({row['benchmark'] for row in rows}),
                'probe_input_formula_sha256': hashlib.sha256(json.dumps(sorted(row['formula'] for row in probe_formulas), separators=(',', ':')).encode()).hexdigest(),
                'probe_input_formula_count': len(probe_formulas), 'protocol_sha256': _sha(protocol_path),
                'evaluation_status': 'DEVELOPMENT: all benchmark labels previously seen; new probe labels blinded until freeze'}
    protocol = {**metadata, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'model_config': MODEL_CONFIG,
                'feature_columns': list(FEATURE_COLUMNS), 'runtime_source_sha256': source_snapshot,
                'primary_metric': 'macro family MAE on new independent stress probe, novelty and all-family results reported',
                'secondary_metrics': ['pooled MAE', 'RMSLE', 'positive-label MAPE', 'Pearson', 'Spearman', 'zero error counts'],
                'reporting': 'No model selection or hyperparameter tuning; report all six frozen matched-target comparators'}
    (directory/'protocol-before-scores.json').write_text(json.dumps(protocol, indent=2)+'\n')
    extraction = collect_features(rows+probe_formulas, cache_dir, workers)
    (directory/'feature-extraction.json').write_text(json.dumps(extraction, indent=2)+'\n')
    folds, truth_pooled, predicted_pooled = [], [], []
    for benchmark in sorted({row['benchmark'] for row in rows}):
        print(f'MasterRTL development outer fold {benchmark}', flush=True)
        train, test, excluded = benchmark_split(rows, benchmark)
        if not train: continue
        model = train_model(train, cache_dir)
        predictions = model.predict(test)
        truth = [row['lut4_count'] for row in test]
        predicted = [prediction['predicted_lut4'] for prediction in predictions]
        folds.append({'held_out_benchmark': benchmark, 'train_formula_count': len(_unique_formulas(train)),
                      'test_size': len(test), 'excluded_matching_formula_rows': excluded,
                      'train_benchmarks': sorted({row['benchmark'] for row in train}),
                      'metrics': {'masterrtl_sog': metrics(truth, predicted)},
                      'predictions': {'masterrtl_sog': [{**prediction, 'measured_lut4': actual} for prediction, actual in zip(predictions, truth)]}})
        truth_pooled.extend(truth); predicted_pooled.extend(predicted)
    model = train_model(rows, cache_dir)
    if _source_hashes() != source_snapshot or _sha(protocol_path) != metadata['protocol_sha256']:
        raise ValueError('MasterRTL sources/protocol changed during development; freeze rejected')
    artifacts = {'masterrtl_sog': save_model(model, directory, metadata)}
    # Inference timing uses formula-only inputs and never reads new labels.
    started = time.perf_counter(); model.predict(probe_formulas); warm_inference = time.perf_counter()-started
    report = {**metadata, 'model_config': MODEL_CONFIG, 'feature_columns': list(FEATURE_COLUMNS),
              'method': 'fixed public recipe, leave-one-program-out with matching formula exclusion; no candidate selection',
              'folds': folds, 'pooled_metrics': {'masterrtl_sog': metrics(truth_pooled, predicted_pooled)},
              'macro_program_metrics': {'masterrtl_sog': _macro([fold['metrics']['masterrtl_sog'] for fold in folds])},
              'artifacts': artifacts, 'runtime_source_sha256': source_snapshot,
              'feature_extraction': {key: value for key, value in extraction.items() if key != 'records'},
              'timing': {'warm_cached_feature_plus_ml_probe_seconds': warm_inference,
                         'warm_probe_formula_count': len(probe_formulas),
                         'cold_extraction_included_in_initial_batch': True,
                         'note': 'Cached feature inference and mandatory cold Yosys preprocessing are different costs; no synthesized label is used by either.'},
              'limitations': ['Matched-target adaptation, not reproduction of MasterRTL published ASIC area results.',
                              'Direct one-bit primitive JSON counting replaces the authors Pyverilog graph parser; all declared IO bits are counted.',
                              'Published repository does not pin XGBoost defaults/version; installed version and all fitted parameters are recorded.',
                              'Combinational formulas have no DFF/register-fanout/sequence features; full sequential-design results cannot be inferred.',
                              'All benchmark data are development; only subsequent frozen probe labels are independent of this fit.',
                              'Yosys pre-ABC synthesis/bit-blasting is mandatory on cache misses; this is not purely syntactic formula inference.']}
    (directory/'development-evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    (directory/'preregistration.json').write_text(json.dumps({**protocol, 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                                                           'artifacts': artifacts}, indent=2)+'\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    train = commands.add_parser('train')
    train.add_argument('--rows', required=True, action='append'); train.add_argument('--probe-inputs', required=True)
    train.add_argument('--output-dir', required=True); train.add_argument('--reference-dir', required=True)
    train.add_argument('--workers', type=int, choices=(1, 2), default=2)
    predict = commands.add_parser('predict')
    predict.add_argument('--model', required=True); predict.add_argument('--candidates', required=True)
    predict.add_argument('--output', required=True); predict.add_argument('--cache-dir')
    args = parser.parse_args(argv)
    if args.command == 'train':
        report = develop_and_freeze([row for path in args.rows for row in _read_rows(path)],
                                   _read_rows(args.probe_inputs), args.output_dir, args.reference_dir, args.workers)
        print(json.dumps({key: report[key] for key in ('macro_program_metrics', 'pooled_metrics', 'artifacts', 'timing')}, indent=2))
    else:
        started = time.perf_counter()
        model = load_model(args.model, args.cache_dir)
        predictions = model.predict(_read_rows(args.candidates))
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(predictions, indent=2)+'\n')
        print(json.dumps({'predictions': len(predictions), 'load_plus_feature_plus_ml_seconds': time.perf_counter()-started}))
    return 0


if __name__ == '__main__':
    from .masterrtl_baseline import main as canonical_main
    raise SystemExit(canonical_main())

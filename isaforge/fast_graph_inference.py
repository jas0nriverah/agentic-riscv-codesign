"""Exact original-graph V5 inference with only its selected feature channels.

Loads the unchanged trusted artifact through the existing strict V5 loader.
Extracts original generic graph and SOG14; no normalization or semantic feature
evaluation. Zeros fill unused schema columns only for the frozen predictor's
adapter; selected inputs, zero rule, uncertainty and domain checks are unchanged.
This is an inference optimization, not a fitted model or an accuracy revision.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from . import area_model_v5 as v5
from .features import parse_formula
from .graph_features_v5 import GraphExtractor, CHANNEL_COLUMNS
from .masterrtl_baseline import SOGExtractor, FEATURE_COLUMNS as SOG_COLUMNS


class FastOriginalGraphPredictor:
    def __init__(self, model, *, workers=1):
        if model.view != 'original_graph':
            raise ValueError('Fast inference supports only the frozen original_graph view')
        if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 4:
            raise ValueError('Workers must be an integer between one and four')
        self.model = model
        self.workers = workers

    def predict(self, rows):
        if not rows:
            return []
        canonical = [parse_formula(r['formula']).canonical() for r in rows]
        formulas = list(dict.fromkeys(canonical))
        graph = GraphExtractor(Path(self.model.cache_root)/'generic', frozen_tool=self.model.frozen_tool)
        sog = SOGExtractor(Path(self.model.cache_root)/'sog',
            frozen_tool={**graph.tool, 'executable': 'yosys'})
        if self.workers == 1:
            records = [graph._channel(f) for f in formulas]
        else:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                records = list(pool.map(graph._channel, formulas))
        # Deduplication also prevents concurrent SOG writes for repeated formulas.
        sog_values = sog.matrix([{'formula': f} for f in formulas], workers=self.workers)
        original_values = np.asarray([r['feature_values'] for r in records], dtype=float)
        if (original_values.shape != (len(formulas), len(CHANNEL_COLUMNS)) or
                sog_values.shape != (len(formulas), len(SOG_COLUMNS))):
            raise ValueError('Original graph/SOG feature schema differs')
        schema = v5.columns()
        original_positions = [schema.index('original_'+n) for n in CHANNEL_COLUMNS]
        selected = list(range(len(SOG_COLUMNS))) + original_positions
        if selected != v5.view_indices('original_graph').tolist():
            raise ValueError('Frozen original_graph view is no longer the two selected channels')
        values = np.zeros((len(formulas), len(schema)), dtype=float)
        values[:, :len(SOG_COLUMNS)] = sog_values
        values[:, original_positions] = original_values
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError('Original graph/SOG features must be finite and nonnegative')
        positions = {formula: i for i, formula in enumerate(formulas)}
        aligned = values[[positions[f] for f in canonical]]
        return self.model.predict_features(rows, aligned)


def load_model(path, cache_root=None, *, workers=1):
    """Preserve every existing artifact/source/environment metadata check."""
    return FastOriginalGraphPredictor(v5.load_model(path, cache_root), workers=workers)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def benchmark(model_path, candidates_path, expected_path, cache_root, *, warm_repeats=3):
    """Sequential one-worker cold/warm timing with exact complete-output checks."""
    model_path, candidates_path, expected_path, cache_root = map(Path,
        (model_path, candidates_path, expected_path, cache_root))
    if cache_root.exists():
        raise ValueError('Cold benchmark requires an absent cache root')
    if isinstance(warm_repeats, bool) or not isinstance(warm_repeats, int) or warm_repeats < 1:
        raise ValueError('Warm repeats must be a positive integer')
    rows = json.loads(candidates_path.read_text())
    expected = json.loads(expected_path.read_text())
    snapshot = v5.source_hashes()
    result = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'formula_count': len(rows),
        'worker_count': 1, 'artifact_sha256': sha(model_path),
        'candidate_sha256': sha(candidates_path), 'expected_prediction_sha256': sha(expected_path),
        'wrapper_source_sha256': sha(__file__), 'frozen_runtime_source_sha256': snapshot,
        'timings': {}, 'scope': 'same-machine sequential feature-plus-prediction timing; startup and JSON output excluded',
        'limits': ['Single cold run per implementation; no runtime confidence interval.',
            'Cache warmth and process scheduling affect wall time.',
            'Outputs equal the frozen original_graph model; no accuracy gain or acquisition saving is claimed.']}
    for name, loader in (('standard', v5.load_model), ('original_only', load_model)):
        began = time.perf_counter()
        model = loader(model_path, cache_root/name)
        loading = time.perf_counter()-began
        elapsed = []
        for _ in range(1+warm_repeats):
            began = time.perf_counter()
            prediction = model.predict(rows)
            elapsed.append(time.perf_counter()-began)
            if prediction != expected:
                raise ValueError(f'{name}: complete outputs differ from frozen predictions')
        result['timings'][name] = {'model_load_seconds': loading,
            'cold_features_and_prediction_seconds': elapsed[0],
            'warm_features_and_prediction_seconds': elapsed[1:],
            'warm_median_seconds': float(np.median(elapsed[1:])),
            'all_point_upper_dispersion_domain_fields_identical': True}
        print(name, result['timings'][name], flush=True)
    if v5.source_hashes() != snapshot:
        raise ValueError('Frozen runtime sources changed during benchmark')
    standard = result['timings']['standard']['cold_features_and_prediction_seconds']
    fast = result['timings']['original_only']['cold_features_and_prediction_seconds']
    result['observed_cold_speedup_ratio'] = standard/fast
    result['observed_cold_time_reduction_percent'] = 100*(standard-fast)/standard
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--cache-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--expected-predictions', type=Path)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(argv)
    if args.benchmark:
        if args.expected_predictions is None or args.workers != 1:
            parser.error('Benchmark requires expected predictions and exactly one worker')
        result = benchmark(args.model, args.candidates, args.expected_predictions, args.cache_root)
    else:
        rows = json.loads(args.candidates.read_text())
        result = load_model(args.model, args.cache_root, workers=args.workers).predict(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Run saved-model inference with label-free inputs and measured local latency."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time


def infer(model, rows, repeats=20):
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats must be a positive integer')
    if not rows:
        raise ValueError('at least one candidate is required')
    inputs = [{k: row[k] for k in ('benchmark', 'candidate_id', 'formula')} for row in rows]
    started = time.perf_counter()
    predictions = model.predict(inputs)
    first_seconds = time.perf_counter() - started
    durations = []
    for _ in range(repeats):
        started = time.perf_counter()
        repeated = model.predict(inputs)
        durations.append(time.perf_counter() - started)
        if repeated != predictions:
            raise ValueError('frozen inference is not deterministic')
    return predictions, {'row_count': len(inputs), 'first_batch_seconds': first_seconds,
                         'warm_batch_seconds': durations,
                         'median_warm_batch_seconds': statistics.median(durations),
                         'median_warm_per_candidate_seconds': statistics.median(durations) / len(inputs),
                         'input_fields': ['benchmark', 'candidate_id', 'formula'],
                         'timing_scope': 'In-memory CPU inference; excludes JSON IO, process startup, and model loading.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--kind', choices=['v1', 'v2', 'v3', 'masterrtl'], default='v1')
    parser.add_argument('--candidates', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.kind == 'v1':
        from .area_model import load_area_model as load
    elif args.kind == 'v2':
        from .area_model_v2 import load_area_model_v2 as load
    elif args.kind == 'v3':
        from .area_model_v3 import load_model as load
    else:
        from .masterrtl_baseline import load_model as load
    started = time.perf_counter()
    model = load(args.model)
    load_seconds = time.perf_counter() - started
    rows = json.loads(args.candidates.read_text())
    predictions, metadata = infer(model, rows)
    if args.kind == 'masterrtl':
        metadata['timing_scope'] = 'Feature-plus-ML inference includes cache file IO, integrity checks, graph traversal, and cold Yosys extraction on misses; excludes input/output JSON serialization, process startup, and model loading.'
    metadata.update(model_path=str(args.model), model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                    model_load_seconds=load_seconds,
                    candidates_sha256=hashlib.sha256(args.candidates.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(predictions, indent=2, allow_nan=False) + '\n')
    args.output.with_suffix('.timing.json').write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: metadata[k] for k in ('row_count', 'model_load_seconds', 'median_warm_batch_seconds')}, indent=2))


if __name__ == '__main__':
    main()

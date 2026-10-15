#!/usr/bin/env python3
"""Run point-only V8 inference with native evidence or exact stored features."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from isaforge import area_model_v8 as v8
from isaforge.features import parse_formula
from train_v6 import read, sha, write


def run(model_path, candidates_path, output, cache_root, feature_path=None):
    model_path, candidates_path, output = map(Path, (model_path, candidates_path, output))
    if output.exists():
        raise ValueError('Inference evidence output is immutable')
    bound_paths = [model_path, model_path.with_suffix('.json'), candidates_path]
    if feature_path is not None:
        bound_paths.append(Path(feature_path))
    start_hashes = {str(p): sha(p) for p in bound_paths}
    source_hashes = v8.source_hashes()
    started = time.perf_counter()
    model = v8.load_model(model_path, cache_root)
    loaded = time.perf_counter()
    rows = read(candidates_path)
    if feature_path is None:
        # One timed proof attempt per distinct circuit; program memberships must
        # not cause independent timeout outcomes for the same native formula.
        unique = [{'formula': f} for f in sorted({parse_formula(r['formula']).canonical() for r in rows})]
        result = model.predict_with_evidence(unique)
        by_formula = {r['formula']: r for r in result['predictions']}
        result['predictions'] = [{**by_formula[parse_formula(row['formula']).canonical()],
                                  **{k: row[k] for k in ('benchmark', 'candidate_id', 'formula') if k in row}}
                                 for row in rows]
        mode = 'native-extraction-with-recorded-proofs-and-fallbacks'
    else:
        feature_path = Path(feature_path)
        features = read(feature_path)
        records = {parse_formula(r['formula']).canonical(): r for r in features['records']}
        if len(records) != len(features['records']) or set(records) != {parse_formula(r['formula']).canonical() for r in rows}:
            raise ValueError('Stored feature file must cover exactly the candidate formula union')
        result = {'predictions': model.predict_features(rows, [records[parse_formula(r['formula']).canonical()]['values'] for r in rows],
                                                        feature_columns=features['columns']),
                  'feature_file_sha256': sha(feature_path), 'compatibility_report': model.compatibility_report()}
        mode = 'stored-full455-feature-replay-no-native-extraction'
    if any(sha(path) != digest for path, digest in start_hashes.items()) or v8.source_hashes() != source_hashes:
        raise ValueError('Inference source or input changed during execution')
    result.update(schema='isaforge-v8-inference-evidence-v1', mode=mode, input_sha256=start_hashes,
                  model_artifact_sha256=sha(model_path), model_schema_sha256=sha(model_path.with_suffix('.json')),
                  candidate_file_sha256=sha(candidates_path), model_load_seconds=loaded-started,
                  inference_seconds=time.perf_counter()-loaded, application_rows=len(rows),
                  upper_bounds_available=False)
    write(output, result)
    print(f'Wrote {len(rows)} point predictions ({mode}) to {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'candidates', 'output', 'cache-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--features', type=Path, help='Replay exact saved full455 feature evidence instead of native extraction')
    a = parser.parse_args()
    run(a.model, a.candidates, a.output, a.cache_root, a.features)

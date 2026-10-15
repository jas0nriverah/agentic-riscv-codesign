#!/usr/bin/env python3
"""Prepare a label-blind V9 schedule, then separately replay consumed labels.

No forest refits, new synthesis, timed normalization, or dynamic acquisition.
Preparation writes its immutable binding manifest before the public payload.
Evaluation seals all unqueried forecasts before full-target scoring.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from isaforge import area_adaptation_v9 as adaptation


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def write(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def now():
    return datetime.now(timezone.utc).isoformat()


def record(path, base):
    return {'path': os.path.relpath(Path(path).resolve(), base), 'sha256': sha(path)}


def checked(entry, base):
    path = (Path(base) / entry['path']).resolve()
    if sha(path) != entry['sha256']:
        raise ValueError('Bound input changed: ' + str(path))
    return path


def source_paths():
    return [Path(__file__).resolve(), Path(adaptation.__file__).resolve(),
            ROOT / 'docs/v9-budgeted-adaptation-protocol.md']


@contextmanager
def public_input_guard(root):
    """Reject actual target/evaluation file opens during public preparation."""
    root = Path(root).resolve()
    active = True

    def guard(event, args):
        if active and event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.is_relative_to(root) and ('measurements' in path.parts
                    or 'label' in path.name.lower() or 'evaluation' in path.name.lower()
                    or path.name == 'training-data.json'):
                raise RuntimeError('V9 preparation forbids target/evaluation reads: ' + str(path))

    # Python audit hooks cannot be removed; deactivate this scoped hook on exit.
    sys.addaudithook(guard)
    try:
        yield
    finally:
        active = False


@contextmanager
def no_fit_or_extraction():
    """Guard preparation's only native-dependent action: frozen tree apply."""
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor
    from isaforge import area_model_v5 as v5, area_model_v6 as v6, area_model_v8 as v8
    from isaforge import semantic_features_v7 as semantic
    with ExitStack() as stack:
        for cls in (ExtraTreesRegressor, DecisionTreeRegressor, ExtraTreeRegressor):
            stack.enter_context(patch.object(cls, 'fit', side_effect=RuntimeError('V9 forbids fitting')))
        for module in (v5, v6, v8):
            stack.enter_context(patch.object(module.FeatureExtractor, 'matrix', side_effect=RuntimeError('V9 forbids extraction')))
        stack.enter_context(patch.object(semantic, 'analyze_modes', side_effect=RuntimeError('V9 forbids normalization retries')))
        stack.enter_context(patch('subprocess.Popen', side_effect=RuntimeError('V9 forbids native subprocesses')))
        yield


def prepare(root, output):
    with public_input_guard(root):
        return _prepare(root, output)


def _prepare(root, output):
    """Read only explicit public inputs and historical model artifacts."""
    from isaforge import area_model_v5 as v5, area_model_v6 as v6, area_model_v8 as v8
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Preparation directory is immutable; use a fresh path')
    seal_path, freeze_path = root / 'input-seal.json', root / 'point-freeze.json'
    seal, freeze = read(seal_path), read(freeze_path)
    if (seal.get('runtime_source_sha256') != v8.source_hashes()
            or freeze.get('point_only') is not True or freeze.get('new_estimator_fits') != 2):
        raise ValueError('Original source-bound V8 input and point freezes required')
    paths = [seal_path, freeze_path, *source_paths()]
    rows_path = checked(seal['rows'], root)
    feature_path = checked(seal['features'], root)
    programs_path = root / 'programs.json'
    # programs.json is among the V8 seal's bound public input files.
    bound = {(root / item['path']).resolve(): item['sha256'] for item in seal['files']}
    if bound.get(programs_path) != sha(programs_path):
        raise ValueError('Declared programs must be bound in V8 input seal')
    model_entry = freeze['models']['mapping_v6']
    artifact = checked(model_entry['artifact'], root)
    schema = checked(model_entry['schema'], root)
    predictions_path = checked(model_entry['predictions'], root)
    paths += [rows_path, feature_path, programs_path, artifact, schema, predictions_path]
    before = {str(p): sha(p) for p in paths}
    features = read(feature_path)
    if tuple(features['columns']) != v8.columns():
        raise ValueError('Exact sealed full455 column names/order required')
    rows, programs, predictions = read(rows_path), read(programs_path), read(predictions_path)
    _, _, points = adaptation.public_rows(rows, programs, predictions)
    records = {adaptation.canonical(r['formula']): r for r in features['records']}
    formulas = sorted(points)
    if len(records) != len(features['records']) or set(records) != set(formulas):
        raise ValueError('Complete unique stored full455 formula union required')
    matrix = np.asarray([records[f]['values'] for f in formulas], dtype=float)
    if matrix.shape != (len(formulas), 455) or not np.isfinite(matrix).all() or np.any(matrix < 0):
        raise ValueError('Finite nonnegative full455 features required')
    with no_fit_or_extraction():
        model = v6.load_model(artifact)
        if model.kind != 'mapping_v6' or model.calibration['status'] != 'uncalibrated':
            raise ValueError('Exact frozen point-only mapping control required')
        selected = v6.mapping_indices()
        if len(selected) != 217 or tuple(features['columns'][i] for i in selected) != v6.mapping_columns():
            raise ValueError('Strict selected mapping217 column order required')
        leaves = model.estimator.apply(matrix[:, selected])
        if leaves.shape != (len(formulas), 300):
            raise ValueError('All 300 frozen tree positions required')
        check_rows = [{'formula': f} for f in formulas]
        observed = model.predict_features(check_rows, matrix[:, :336])
        if any(row['predicted_lut4'] != points[f] for f, row in zip(formulas, observed)):
            raise ValueError('Frozen artifact/full455 point replay differs')
    zero = dict(zip(formulas, (bool(v) for v in v5.original_zero(matrix[:, :313]))))
    payload = adaptation.prepare(rows, programs, predictions, features['records'], leaves, zero)
    payload['selected_mapping_columns'] = list(v6.mapping_columns())
    payload['selected_mapping_indices'] = selected.tolist()
    if {str(p): sha(p) for p in paths} != before:
        raise ValueError('Source/public input changed during preparation')
    output.mkdir(parents=True)
    # Manifest is written first. A partial attempt remains visible and cannot be
    # replaced. Its payload hash commits every schedule/kernel/exclusion byte.
    manifest = {'schema': 'isaforge-v9-adaptation-preparation-v1', 'prepared_at_utc': now(),
                'protocol': adaptation.PROTOCOL, 'files': [record(p, output) for p in paths],
                'public_payload': {'path': 'public-prepared.json', 'sha256': hashlib.sha256(encoded(payload)).hexdigest()},
                'v8_root_relative': os.path.relpath(root, output),
                'application_labels_read': False, 'application_evaluation_read': False,
                'new_fits': 0, 'new_labels': 0, 'new_feature_extractions': 0,
                'proof_or_normalization_retries': 0, 'python': sys.executable}
    write(output / 'preparation.json', manifest)
    write(output / 'public-prepared.json', payload)
    print(f'Prepared immutable label-blind schedules for {len(payload["episodes"])} families at {output}')
    return manifest


def load_prepared(directory):
    directory = Path(directory).resolve()
    manifest = read(directory / 'preparation.json')
    if manifest.get('schema') != 'isaforge-v9-adaptation-preparation-v1' or manifest.get('protocol') != adaptation.PROTOCOL:
        raise ValueError('Fixed V9 preparation protocol required')
    paths = [checked(item, directory) for item in manifest['files']]
    if any(path not in paths for path in source_paths()):
        raise ValueError('Preparation must bind current implementation and protocol sources')
    payload_path = checked(manifest['public_payload'], directory)
    payload = read(payload_path)
    if payload.get('schema') != 'isaforge-v9-adaptation-public-v1' or payload.get('protocol') != adaptation.PROTOCOL:
        raise ValueError('Fixed prepared public payload required')
    if adaptation.leaf_kernel(payload['leaf_ids']).tolist() != payload['kernel']:
        raise ValueError('Prepared same-tree kernel differs')
    for episode in payload['episodes']:
        rows = [r for r in payload['rows'] if r['family'] == episode['family']]
        if adaptation.query_schedule(rows, payload['base_points']) != episode['schedule']:
            raise ValueError('Frozen query schedule differs')
        if any(adaptation.exclusion(payload, episode, b) != episode['prefixes'][str(b)] for b in adaptation.BUDGETS):
            raise ValueError('Frozen prefix group exclusion differs')
    return manifest, payload


def evaluate(prepared_dir, output, review_path):
    """Reveal paid labels sequentially; final full targets are scorer-only."""
    prepared_dir, output = Path(prepared_dir).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Development evaluation is immutable; use a fresh path')
    manifest, payload = load_prepared(prepared_dir)
    review_path = Path(review_path).resolve()
    review = read(review_path)
    if (review.get('status') != 'approved-consumed-development-replay'
            or review.get('preparation_sha256') != sha(prepared_dir / 'preparation.json')
            or review.get('public_payload_sha256') != sha(prepared_dir / 'public-prepared.json')):
        raise ValueError('Independent review and parent release bound to this preparation required')
    root = (prepared_dir / manifest['v8_root_relative']).resolve()
    completion_path = root / 'measurements/completion.json'
    completion = read(completion_path)
    if completion.get('complete') is not True or completion.get('failures') != []:
        raise ValueError('Complete consumed V8 measurements required')
    attempt = completion['attempt']
    if not isinstance(attempt, str) or not re.fullmatch(r'attempt-[0-9]{4}', attempt):
        raise ValueError('Owned V8 measurement attempt required')
    labels_path = root / 'measurements' / attempt / 'labels.json'
    if sha(labels_path) != completion['labels_sha256']:
        raise ValueError('Completed label digest differs')
    bindings = [prepared_dir / 'preparation.json', prepared_dir / 'public-prepared.json', review_path,
                completion_path, labels_path, *source_paths()]
    before = {str(p): sha(p) for p in bindings}
    output.mkdir(parents=True)
    write(output / 'evaluation-start.json', {'schema': 'isaforge-v9-development-evaluation-start-v1',
          'started_at_utc': now(), 'protocol': adaptation.PROTOCOL,
          'files': [record(p, output) for p in bindings], 'scope': 'consumed-V8-development-only'})
    labels = read(labels_path)
    targets = {adaptation.canonical(r['formula']): adaptation.integer(r['lut4_count'], 'original target') for r in labels}
    if len(targets) != len(labels) or set(targets) != set(payload['formulas']):
        raise ValueError('Complete unique original target union required')
    # The adapter never receives this dictionary: query returns a single charged
    # value, and replay resets its visible dictionary between family episodes.
    def query(_family, formula):
        return targets[formula]
    replayed = adaptation.replay(payload, query)
    write(output / 'unqueried-forecasts.json', replayed)
    # No unseen target has entered any correction. Full targets now score the
    # already-written unqueried predictions; this cannot change the query log.
    result = adaptation.score(payload, replayed, targets)
    result['provenance'] = {'preparation_sha256': sha(prepared_dir / 'preparation.json'),
                            'public_payload_sha256': sha(prepared_dir / 'public-prepared.json'),
                            'forecast_sha256': sha(output / 'unqueried-forecasts.json'),
                            'completion_sha256': sha(completion_path), 'labels_sha256': sha(labels_path)}
    result['costs'] = {'per_family_queries': {episode['family']: len(episode['schedule']) for episode in payload['episodes']},
                       'simulated_family_query_reveals': len(replayed['query_log']),
                       'unique_original_physical_labels_reused': len({q['formula'] for q in replayed['query_log']}),
                       'new_physical_measurements': 0, 'new_estimator_fits': 0}
    if {str(p): sha(p) for p in bindings} != before:
        raise ValueError('Bound source/evidence changed during evaluation')
    write(output / 'evaluation.json', result)
    write(output / 'completion.json', {'schema': 'isaforge-v9-development-completion-v1', 'complete': True,
          'completed_at_utc': now(), 'forecast_sha256': sha(output / 'unqueried-forecasts.json'),
          'evaluation_sha256': sha(output / 'evaluation.json'), 'source_and_input_sha256': before})
    print(f'Completed bounded consumed-V8 development evaluation at {output}')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='stage', required=True)
    p = subparsers.add_parser('prepare')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = subparsers.add_parser('evaluate')
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare(args.root, args.output)
    else:
        evaluate(args.prepared, args.output, args.review)

#!/usr/bin/env python3
"""Fixed input-only coverage routing between frozen uncalibrated V6 and V9.

V6 is the fallback. V9 is selected only by the two original-AST coverage classes
below. This router has no fitted parameters, label inputs or threshold selection.
Cached-feature inference never invokes feature extraction or native tools.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from isaforge import area_model_v6 as frozen
from isaforge.features import Expression, parse_formula

MODELS = {
    'V6': ('results/2026-10-14-v6/models/mapping_v6.joblib',
           '1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56', 1665),
    'V9': ('results/2026-10-15-v9-coverage-development/fit-attempt-0000/models/mapping-coverage.joblib',
           'dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d', 1713),
}
GATE = {
    'schema': 'isaforge-v15-scoped-coverage-gate-v1',
    'fallback': 'V6', 'covered': 'V9', 'tree': 'original parsed AST; no normalization or constant folding',
    'constant_low_multiply': 'Any mul node with either operand a literal K or exact addi(0,K), integer 1<=K<=2047.',
    'signed_shift_difference': 'Any sub(srai(A,k),srai(B,31)), integer 0<=k<=31; A and B each contain an input and may differ.',
    'training_motivation': 'V9 added 32 constant products and 16 signed-shift formulas.',
    'scope': 'Fixed syntactic coverage routing, no label/prediction/error thresholds, formula IDs, training or calibration.',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def literal(node, value=None):
    return not node.children and type(node.value) is int and (value is None or node.value == value)


def positive_small_constant(node):
    if node.value == 'addi' and len(node.children) == 2 and literal(node.children[0], 0):
        node = node.children[1]
    return literal(node) and 1 <= node.value <= 2047


def contains_input(node):
    return any(not part.children and part.value in ('in0', 'in1') for part in walk(node))


def route(formula):
    """Return the fixed route using only the original formula AST."""
    classes = set()
    for node in walk(parse_formula(formula)):
        if node.value == 'mul' and any(positive_small_constant(child) for child in node.children):
            classes.add('constant-low-multiply')
        if node.value == 'sub':
            lhs, rhs = node.children
            if (lhs.value == rhs.value == 'srai' and literal(lhs.children[1])
                    and 0 <= lhs.children[1].value <= 31 and literal(rhs.children[1], 31)
                    and contains_input(lhs.children[0]) and contains_input(rhs.children[0])):
                classes.add('signed-shift-difference')
    return {'source_model': 'V9' if classes else 'V6', 'coverage_classes': sorted(classes)}


def validate_rows(rows):
    need(type(rows) is list, 'Original rows must be a list')
    for row in rows:
        need(type(row) is dict and type(row.get('formula')) is str, 'Original formula required')
        parse_formula(row['formula'])


def validate_points(rows, points):
    need(type(points) is list and len(points) == len(rows), 'Complete frozen points required')
    for row, point in zip(rows, points):
        need(point['formula'] == row['formula'] and all(point.get(k) == row[k] for k in ('candidate_id', 'benchmark') if k in row), 'Ordered original point identity differs')
        value = point['predicted_lut4']
        need(type(value) in (int, float) and np.isfinite(value) and value >= 0
             and point['upper_lut4'] is None and point['calibration_status'] == 'uncalibrated', 'Finite uncalibrated frozen points required')


def combine_points(rows, v6_points, v9_points):
    """Select exact frozen point dictionaries; keep routing evidence separate."""
    validate_rows(rows)
    validate_points(rows, v6_points)
    validate_points(rows, v9_points)
    routes = [dict({k: row[k] for k in ('candidate_id', 'formula', 'benchmark') if k in row}, **route(row['formula'])) for row in rows]
    points = [copy.deepcopy(v9_points[i] if item['source_model'] == 'V9' else v6_points[i]) for i, item in enumerate(routes)]
    return points, routes


def predict_models(rows, x):
    """Run the exact frozen pair once and return V6, V9 and scoped V15 points."""
    validate_rows(rows)
    x = np.asarray(x, dtype=float)
    need(x.shape == (len(rows), 336) and np.isfinite(x).all() and np.all(x >= 0), 'Finite nonnegative full336 matrix required')
    points = {}
    tool = None
    for name, (relative, expected_sha, count) in MODELS.items():
        path = ROOT/relative
        need(sha(path) == expected_sha, 'Frozen '+name+' artifact changed')
        model = frozen.load_model(path)
        need(model.kind == 'mapping_v6' and model.training_formula_count == count
             and model.calibration['status'] == 'uncalibrated' and model.calibration['upper_margin_lut4'] is None,
             'Exact frozen uncalibrated '+name+' required')
        if tool is None:
            tool = model.frozen_tool
        need(model.frozen_tool == tool, 'Frozen feature tools differ')
        points[name] = model.predict_features(rows, x)
    points['V15'], routes = combine_points(rows, points['V6'], points['V9'])
    return points, routes


def cached_matrix(rows, features):
    validate_rows(rows)
    need(type(features) is dict and features['columns'] == list(frozen.columns())
         and len(features['records']) == len(rows), 'Complete ordered full336 feature archive required')
    for row, feature in zip(rows, features['records']):
        need(feature['formula'] == row['formula'] and all(feature.get(k) == row[k] for k in ('candidate_id',) if k in row), 'Cached original feature identity differs')
        need(type(feature['values']) is list and len(feature['values']) == 336
             and all(type(v) in (int, float) and np.isfinite(v) and v >= 0 for v in feature['values']), 'Finite nonnegative full336 feature values required')
    return np.asarray([r['values'] for r in features['records']], dtype=float).reshape((len(rows), 336))


def run(rows_path, features_path, output):
    output = Path(output)
    need(not output.exists(), 'Fresh scoped prediction output required')
    rows_path, features_path = Path(rows_path), Path(features_path)
    rows = json.loads(rows_path.read_text()); features = json.loads(features_path.read_text())
    x = cached_matrix(rows, features)
    models, routes = predict_models(rows, x)
    result = {'schema': 'isaforge-v15-scoped-points-v1', 'gate': GATE, 'candidate_count': len(rows),
              'models': models, 'routes': routes, 'fits': 0, 'calibration_jobs': 0, 'native_jobs': 0,
              'source_sha256': sha(__file__), 'rows_sha256': sha(rows_path), 'features_sha256': sha(features_path),
              'frozen_models': {name: {'path': relative, 'sha256': digest, 'training_formula_count': count} for name, (relative, digest, count) in MODELS.items()},
              'scope': 'V15 is a post-V11 diagnostic design. Prior-panel scores are retrospective; only separately frozen new stress inputs provide prospective evidence. Exact chosen points retain frozen model metadata and zero override.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.rows, args.features, args.output)
    print(json.dumps({'candidate_count': result['candidate_count'], 'routes': {name: sum(row['source_model'] == name for row in result['routes']) for name in MODELS}, 'output': str(args.output)}))

#!/usr/bin/env python3
"""Predict isolated iCE40 LUT4 area with frozen ExtraTrees models; never fit.

Cached full336 features need no native tools. A cache miss without --features
uses the frozen label-free Yosys extractor. Scoped routing is fixed by the
original formula AST, without labels, predicted errors or calibration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from isaforge import area_model_v6 as runtime
from isaforge.features import parse_formula

MODELS = {
    'base': ('1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56',
             '42d21cd093ed9b863668fcc01d12ed4d09ebb1590e0bdffb408fdf66d5f74676', 1665),
    'coverage': ('dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d',
                 '0af6acebfd07cfa0688c36777a14bff816a5c254032050bcf75b1ff1c947dd06', 1713),
}
DESCRIPTIONS = {
    'base': 'Frozen 300-tree ExtraTrees model trained on 1665 circuits; 336 input features, 217 selected.',
    'coverage': 'Frozen 300-tree ExtraTrees model trained on 1713 circuits, including 48 targeted coverage additions; same 336/217 schema.',
    'scoped': 'Base fallback; coverage model only for fixed positive constant low products or input-bearing signed-shift differences.',
}


def need(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walk(node):
    yield node
    for child in node.children: yield from walk(child)


def literal(node, value=None):
    return not node.children and type(node.value) is int and (value is None or node.value == value)


def route(formula):
    """The frozen scoped gate examines original AST nodes, without folding."""
    classes = set()
    for node in walk(parse_formula(formula)):
        if node.value == 'mul':
            for operand in node.children:
                if operand.value == 'addi' and literal(operand.children[0], 0): operand = operand.children[1]
                if literal(operand) and 1 <= operand.value <= 2047: classes.add('constant-low-multiply')
        if node.value == 'sub':
            lhs, rhs = node.children
            if (lhs.value == rhs.value == 'srai' and literal(lhs.children[1]) and 0 <= lhs.children[1].value <= 31
                    and literal(rhs.children[1], 31)
                    and all(any(part.value in ('in0','in1') for part in walk(side.children[0])) for side in (lhs,rhs))):
                classes.add('signed-shift-difference')
    return {'source_model': 'coverage' if classes else 'base', 'coverage_classes': sorted(classes)}


def matrix(rows, features):
    need(features['columns'] == list(runtime.columns()) and len(features['records']) == len(rows), 'Complete ordered 336 feature schema required')
    for row, saved in zip(rows, features['records']):
        need(saved['formula'] == row['formula'] and all(saved.get(k) == row[k] for k in ('candidate_id',) if k in row), 'Original feature row identity differs')
        need(type(saved['values']) is list and len(saved['values']) == 336
             and all(type(v) in (int,float) and np.isfinite(v) and v >= 0 for v in saved['values']), 'Finite nonnegative 336 feature values required')
    return np.asarray([row['values'] for row in features['records']], dtype=float).reshape((len(rows),336))


def load(name):
    artifact_sha, metadata_sha, count = MODELS[name]; path = ROOT/'models'/name/'model.joblib'
    need(sha(path) == artifact_sha and sha(path.with_suffix('.json')) == metadata_sha, 'Frozen '+name+' artifact/metadata hash differs')
    model = runtime.load_model(path)
    need(model.kind == 'mapping_v6' and model.training_formula_count == count and model.calibration['status'] == 'uncalibrated'
         and model.calibration['upper_margin_lut4'] is None, 'Exact frozen uncalibrated model required')
    return model


def predict(rows, x, name='base', loaded=None):
    need(name in (*MODELS,'scoped'), 'Unknown model')
    need(type(rows) is list and all(type(r) is dict and type(r.get('formula')) is str for r in rows), 'Original candidate rows required')
    for row in rows: parse_formula(row['formula'])
    x = np.asarray(x,dtype=float)
    need(x.shape == (len(rows),336) and np.isfinite(x).all() and np.all(x >= 0), 'Finite nonnegative full336 matrix required')
    routes = [{**{k:r[k] for k in ('candidate_id','formula') if k in r}, **(route(r['formula']) if name == 'scoped' else {'source_model':name,'coverage_classes':[]})} for r in rows]
    points = [None]*len(rows); loaded = dict(loaded or {})
    for source in MODELS:
        indices = [i for i,r in enumerate(routes) if r['source_model'] == source]
        if not indices: continue
        if source not in loaded: loaded[source] = load(source)
        saved = loaded[source].predict_features([rows[i] for i in indices],x[indices,:])
        need(len(saved) == len(indices), 'Complete selected frozen points required')
        for i, point in zip(indices,saved):
            need(point['formula'] == rows[i]['formula'] and all(point.get(k) == rows[i][k] for k in ('candidate_id','benchmark') if k in rows[i]), 'Frozen point identity differs')
            need(type(point['predicted_lut4']) in (int,float) and np.isfinite(point['predicted_lut4']) and point['predicted_lut4'] >= 0
                 and point['upper_lut4'] is None and point['calibration_status'] == 'uncalibrated', 'Finite uncalibrated point required')
            points[i] = point
    return points, routes


def run(candidates, features, name, output, cache_root):
    candidates, output = Path(candidates), Path(output); need(not output.exists(), 'Fresh prediction output required')
    rows = json.loads(candidates.read_text()); loaded = {}
    if features is not None:
        features = Path(features); x = matrix(rows,json.loads(features.read_text()))
    else:
        initial = 'base' if name == 'scoped' else name; loaded[initial] = load(initial)
        x,_ = runtime.FeatureExtractor(cache_root,frozen_tool=loaded[initial].frozen_tool).matrix(rows,workers=1)
    points,routes = predict(rows,x,name,loaded)
    result = {'model': name, 'description': DESCRIPTIONS[name], 'predictions': points, 'routes': routes,
              'candidate_count':len(rows),'calibration_status':'uncalibrated','fits':0,
              'candidate_sha256':sha(candidates),'features_sha256':sha(features) if features is not None else None,
              'source_sha256':sha(__file__),'scope':'Isolated iCE40 LUT4 point predictions; no calibrated safety, CPU timing, power or energy claim.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,required=True); parser.add_argument('--features',type=Path)
    parser.add_argument('--model',choices=(*MODELS,'scoped'),default='base'); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cache-root',type=Path,default=ROOT/'generated/inference-features')
    args = parser.parse_args(); result = run(args.candidates,args.features,args.model,args.output,args.cache_root)
    print(json.dumps({'model':args.model,'candidate_count':result['candidate_count'],'output':str(args.output)}))

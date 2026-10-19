#!/usr/bin/env python3
"""Fit one fixed V6 mapping model and freeze all new/control point predictions.

Only the exact old1665 fitting labels are used. Fresh192 calibration/test rows
must already be input-sealed. New calibration/test labels are never read here.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from isaforge import area_model_v5 as v5
from isaforge import area_model_v6 as v6
from isaforge import masterrtl_baseline as master
from isaforge.area_model import _versions
from isaforge.area_model_v4 import load_model as load_v4
from isaforge.v6_corpus import validate_inputs
from evaluate_v4 import aligned

OLD_MODELS=('sog_tuned','original_graph','dual_graph','dual_semantics','masterrtl_fixed','v4_frozen')
NEW_MODELS=v6.KINDS
SCOPES=('calibration','test')


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def record(path,base):return {'path':os.path.relpath(Path(path).resolve(),base),'sha256':sha(path)}
def checked(entry,base):
    path=(Path(base)/entry['path']).resolve()
    if sha(path)!=entry['sha256']:raise ValueError(f'Frozen source input changed: {path}')
    return path


def select_fitting(old_root,consumed_features):
    """Select only hash-bound old fitting rows/features; no fresh labels."""
    old=read(old_root/'freeze.json');frozen={(old_root/r['path']).resolve():r['sha256'] for r in old['files']}
    inputs=[old_root/name for name in ('development-data.json','development-features.json','split.json','training-start.json')]
    for path in inputs:
        if frozen.get(path.resolve())!=sha(path):raise ValueError('Old fitting input not hash-bound')
    if read(inputs[3])['sources']!=v5.source_hashes():raise ValueError('Frozen V5 runtime differs')
    split=read(inputs[2]);fit=split['fit_indices']
    if len(fit)!=1665 or len(set(fit))!=1665 or set(fit)&set(split['calibration_indices']):
        raise ValueError('Exact original1665 fitting rows required')
    all_rows=read(inputs[0]);old_features=read(inputs[1]);rows=[all_rows[i] for i in fit];del all_rows
    if tuple(old_features['columns'])!=v5.columns():raise ValueError('Old fitting feature schema differs')
    current={r['formula']:r for r in consumed_features}
    if len(current)!=len(consumed_features):raise ValueError('Unique consumed feature records required')
    selected=[]
    for row,index in zip(rows,fit):
        values=current[row['formula']]['values']
        if len(values)!=336 or values[:313]!=old_features['records'][index]['values']:
            raise ValueError('Consumed V6 feature replay differs from old fitting features')
        selected.append(values)
    x=np.asarray(selected,dtype=float);y=np.asarray([r['lut4_count'] for r in rows],dtype=float)
    if not np.isfinite(x).all() or np.any(x<0) or not np.isfinite(y).all() or np.any(y<0):raise ValueError('Invalid old fitting data')
    return rows,fit,x,y,inputs


@threadpool_limits.wrap(limits=1)
def run(root,v5_root,cache_root):
    root,v5_root,cache_root=map(lambda p:Path(p).resolve(),(root,v5_root,cache_root))
    if (root/'point-freeze.json').exists() or (root/'training-start.json').exists():
        raise ValueError('Existing V6 point training/freeze is immutable; preserve failed attempts')
    for scope in SCOPES:
        for name in ('label-release.json','completion.json','dataset.json','raw-evidence.json','raw-evidence.zip'):
            if (root/'corpus'/scope/name).exists():raise ValueError('Fresh labels have been released; fitting is blocked')
    prepared=validate_inputs(root/'corpus',repo_root=ROOT)
    rows_by_scope=prepared['cohorts'];features_by_scope=prepared['records']
    old=read(v5_root/'freeze.json')
    if set(old['models'])!=set(OLD_MODELS):raise ValueError('All six frozen controls required')
    consumed=read(root/'corpus/consumed-features.json')
    if tuple(consumed['columns'])!=v6.columns():raise ValueError('Full336 consumed feature schema required')
    rows,fit,x,y,fit_inputs=select_fitting(v5_root,consumed['records'])
    controls={name:v5.load_model(checked(old['models'][name]['artifact'],v5_root),cache_root) for name in OLD_MODELS[:4]}
    primary=controls['dual_graph'];tool=primary.frozen_tool
    estimator=ExtraTreesRegressor(**v6.FIXED_PARAMETERS)
    if estimator.get_params()!=primary.estimator.get_params():
        raise ValueError('New mapping estimator must exactly match all primary control parameters, including seed')
    for name in ('dual_graph','dual_semantics'):
        schema=read(checked(old['models'][name]['schema'],v5_root))
        if (schema['training_formula_count']!=1665 or schema['training_dataset_sha256']!=sha(v5_root/'development-data.json')
                or schema['split_sha256']!=sha(v5_root/'split.json')):raise ValueError('Old expert fitting provenance differs')
    for name,entry in old['models'].items():
        checked(entry['artifact'],v5_root);checked(entry['schema'],v5_root)
    for scope in SCOPES:
        if prepared['freezes'][scope]['frozen_tool']!=tool:raise ValueError('Fresh input tool differs from primary control')
    sources=v6.source_hashes()
    controls_files=[ROOT/'scripts'/n for n in ('train_v6.py','prepare_v6_inputs.py','evaluate_v6.py','measure_v6.py')]
    controls_files += [ROOT/'docs/v6-protocol.md',ROOT/'isaforge/v6_corpus.py',ROOT/'tests/test_area_model_v6.py',ROOT/'tests/test_evaluate_v6.py']
    corpus_files=list((root/'corpus').rglob('*.json'))
    consumed_bindings=read(root/'corpus/consumed-manifest.json')['sources']
    consumed_files=[ROOT/r[key] for r in consumed_bindings for key in ('path','freeze_path')]
    acquisition=read(root/'corpus/acquisition-plan.json')
    if 'tool_input_metadata_sha256' in acquisition:
        metadata=v5_root/'feature-extraction.json'
        if sha(metadata)!=acquisition['tool_input_metadata_sha256']:raise ValueError('Acquisition tool metadata differs')
        consumed_files.append(metadata)
    acquisition_sources=[ROOT/n for n in prepared['seal']['source_sha256']]
    all_inputs=[*fit_inputs,v5_root/'freeze.json',*corpus_files,*controls_files,*consumed_files,*acquisition_sources,*(ROOT/'isaforge'/n for n in sources)]
    input_hashes={str(path):sha(path) for path in all_inputs}
    fit_digest=hashlib.sha256(json.dumps(fit,separators=(',',':')).encode()).hexdigest()
    start={'fit_indices_sha256':fit_digest,'schema':'isaforge-v6-training-start-v1','started_at_utc':now(),'fit_indices':fit,
           'runtime_source_sha256':sources,'versions':_versions(),'training_formula_count':1665,
           'configuration':v6.FIXED_PARAMETERS,'full_estimator_parameters':estimator.get_params(),
           'primary_estimator_parameters':primary.estimator.get_params(),'input_sha256':input_hashes,
           'fresh_calibration_labels_read':False,'fresh_test_labels_read':False,'calibration_used_for_selection':False,
           'source_v5_freeze':record(v5_root/'freeze.json',root),'frozen_tool':tool}
    write(root/'training-start.json',start)
    estimator.fit(x[:,v6.mapping_indices()],y)
    provenance={'fit_indices_sha256':fit_digest,'fit_indices':fit,
                'training_dataset_sha256':sha(v5_root/'development-data.json'),'development_dataset_sha256':sha(v5_root/'development-data.json'),
                'development_features_sha256':sha(v5_root/'development-features.json'),'split_sha256':sha(v5_root/'split.json')}
    arguments={'estimator':estimator,'feature_columns':v6.columns(),'training_formula_count':1665,
               'feature_minimum':x.min(axis=0).tolist(),'feature_maximum':x.max(axis=0).tolist(),
               'frozen_tool':tool,'runtime_source_sha256':sources,'training_provenance':provenance,'cache_root':str(cache_root)}
    mapping=v6.V6Predictor(**arguments,kind='mapping_v6',calibration=v6.uncalibrated())
    semantic_entry=old['models']['dual_semantics']
    router=v6.V6Predictor(**arguments,kind='router_v6',calibration=v6.uncalibrated(),semantic_expert=controls['dual_semantics'],
        semantic_source={k+'_sha256':semantic_entry[k]['sha256'] for k in ('artifact','schema')})
    new={'mapping_v6':mapping,'router_v6':router};entries={}
    for name,model in new.items():
        saved=v6.save_model(model,root/'models'/f'{name}.joblib')
        # Round-trip before any fresh prediction; no target labels involved.
        reloaded=v6.load_model(saved['artifact'],cache_root)
        if reloaded.estimator.get_params()!=primary.estimator.get_params():raise ValueError('Saved primary parameter equality lost')
        new[name]=reloaded;entries[name]={k:record(saved[k],root) for k in ('artifact','schema')}
    for name in OLD_MODELS:entries[name]={k:record(checked(old['models'][name][k],v5_root),root) for k in ('artifact','schema')}
    baseline_master=master.load_model(checked(old['models']['masterrtl_fixed']['artifact'],v5_root),cache_root/'sog')
    baseline_v4=load_v4(checked(old['models']['v4_frozen']['artifact'],v5_root),cache_root/'v4')
    for name in (*NEW_MODELS,*OLD_MODELS):
        for scope in SCOPES:
            candidates=rows_by_scope[scope];current=features_by_scope[scope]
            values=np.asarray([r['values'] for r in current],dtype=float)
            if name in new:predictions=new[name].predict_features(candidates,values)
            elif name in controls:predictions=controls[name].predict_features(candidates,values[:,:313])
            elif name=='masterrtl_fixed':predictions=baseline_master.predict(candidates)
            else:predictions=baseline_v4.predict(candidates)
            aligned(candidates,predictions,'predicted_lut4')
            if name in new and any(r['upper_lut4'] is not None for r in predictions):raise ValueError('Uncalibrated V6 must have null bounds')
            path=root/'point-predictions'/f'{name}-{scope}.json';write(path,predictions)
            entries[name][scope+'_predictions']=record(path,root)
        entries[name]['frozen_at_utc']=now()
        print('Frozen point predictions',name,flush=True)
    if v6.source_hashes()!=sources or any(sha(path)!=digest for path,digest in input_hashes.items()):
        raise ValueError('V6 source/input changed during fitting or prediction')
    files=[*all_inputs,root/'training-start.json']
    manifest={'schema':'isaforge-v6-point-freeze-v1','frozen_at_utc':now(),'models':entries,
              'files':[record(path,root) for path in dict.fromkeys(files)],'source_v5_freeze':record(v5_root/'freeze.json',root),
              'training_formula_count':1665,'frozen_tool':tool,'primary_comparison':'mapping_v6 minus dual_graph',
              'router_role':'Predeclared secondary; semantic expert on AST mul, mapping otherwise',
              'fresh_calibration_labels_read':False,'fresh_test_labels_read':False,'new_estimator_fits':1}
    write(root/'point-freeze.json',manifest)
    from evaluate_v6 import validate_point_freeze
    validate_point_freeze(root)
    print(json.dumps({'point_freeze_sha256':sha(root/'point-freeze.json'),'training_formula_count':1665,
                      'calibration_labels_released':False,'test_labels_released':False}))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v6')
    parser.add_argument('--v5-root',type=Path,default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--cache-root',type=Path,default=ROOT/'generated/v5-features')
    args=parser.parse_args();run(args.root,args.v5_root,args.cache_root)

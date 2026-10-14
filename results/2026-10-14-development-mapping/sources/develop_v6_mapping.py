#!/usr/bin/env python3
"""One fixed graph-descriptor ablation using existing fitting-only cached DAGs.

No target mapping, feature synthesis, test/external inputs, estimator search or
calibration. Three fixed seeds at most, same five component folds and estimator
configuration, all strata/tails retained. Outputs cannot enter the repository.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
from develop_v6 import fold_plan,metrics
from develop_v6_targeted import fitting_inputs,read,sha,write,aligned_oof
from isaforge.area_model import _versions
from isaforge.area_model_v5 import columns,original_zero,view_indices,source_hashes
from isaforge.graph_features_v5 import PIPELINE,SCHEMA,source_hashes as graph_sources
from isaforge.mapping_features_v6 import FEATURE_NAMES,CUT_SIZE,CUT_BUDGET,feature_dict
from isaforge.rtl import generate_rtl

SEEDS=(2026101421,2026101422,2026101423)
CONFIGURATION={'n_estimators':300,'min_samples_leaf':1,'max_features':1.,'n_jobs':1}


def cached_graph(folder,feature_record,expected_tool=None):
    """Strictly read an existing original generic graph; never invoke a tool."""
    folder=Path(folder);manifest=folder/'features.json'
    if not manifest.is_file():raise ValueError('Original generic cache missing; regeneration forbidden')
    if sha(manifest)!=feature_record['original_manifest_sha256']:raise ValueError('Original cache manifest changed')
    cached=read(manifest);context=cached['context']
    if (cached['formula']!=feature_record['formula'] or cached['cache_key']!=feature_record['original_cache_key']
            or context['schema']!=SCHEMA or context['pipeline']!=PIPELINE
            or context['runtime_source_sha256']!=graph_sources()):
        raise ValueError('Original generic cache identity/context differs')
    if expected_tool is not None and context.get('tool')!=expected_tool:raise ValueError('Original generic cache tool differs')
    for name in ('candidate.v','extract.ys','word.json','graph.json','extract.log'):
        path=folder/name
        if not path.is_file() or sha(path)!=cached['files_sha256'].get(name):raise ValueError('Original generic cache bytes changed')
    if (folder/'candidate.v').read_text()!=generate_rtl(feature_record['formula']):raise ValueError('Original cached RTL differs')
    return folder/'graph.json',{'cache_key':cached['cache_key'],'manifest_sha256':sha(manifest),
        'files_sha256':cached['files_sha256'],'formula':cached['formula']}


@threadpool_limits.wrap(limits=1)
def run(root,diagnostics,cache_root,output,seeds=SEEDS):
    root,diagnostics,cache_root,output=map(lambda p:Path(p).resolve(),(root,diagnostics,cache_root,output))
    if tuple(seeds) not in (SEEDS[:1],SEEDS):raise ValueError('Only fixed first seed or fixed three seeds permitted')
    if output==ROOT or ROOT in output.parents:raise ValueError('Development output must be outside repository')
    if output.exists() and any(output.iterdir()):raise ValueError('Existing mapping study cannot be overwritten')
    rows,fit,inputs=fitting_inputs(root,diagnostics);features=read(root/'development-features.json');split=read(root/'split.json')
    if tuple(features['columns'])!=columns():raise ValueError('Feature schema changed')
    records=[features['records'][i] for i in fit]
    if any(r['formula']!=f['formula'] for r,f in zip(rows,records)):raise ValueError('Fitting feature alignment differs')
    groups={i:split['component_by_formula'][r['formula']] for i,r in zip(fit,rows)}
    folds=fold_plan(fit,split['fold_validation_indices'],groups)
    x=np.asarray([r['values'] for r in records],dtype=float);y=np.asarray([r['lut4_count'] for r in rows],dtype=float)
    strata=np.array([r.get('stratum','workload') for r in rows]);base=x[:,view_indices('dual_graph')]
    sources=[Path(__file__).resolve(),ROOT/'isaforge/mapping_features_v6.py',ROOT/'scripts/develop_v6.py',ROOT/'scripts/develop_v6_targeted.py']
    manifest=read(root/'freeze.json');schema_record=manifest['models']['dual_graph']['schema']
    schema_path=(root/schema_record['path']).resolve()
    if sha(schema_path)!=schema_record['sha256']:raise ValueError('Frozen control schema changed')
    expected_tool=read(schema_path)['frozen_tool']
    diagnostic_inputs=[diagnostics/'run-start.json',diagnostics/'source-manifest.json',
        *(diagnostics/'predictions'/f'dual_graph-seed-{seed}.json' for seed in seeds)]
    hashes={str(p):sha(p) for p in (*inputs,root/'freeze.json',schema_path,*sources,*diagnostic_inputs)}
    began=time.perf_counter();graph_paths=[];cache_records=[]
    for record in records:
        path,provenance=cached_graph(cache_root/record['original_cache_key'],record,expected_tool)
        graph_paths.append(path);cache_records.append(provenance)
    # Entire cohort/configuration/cache/source provenance fixed before extraction
    # and fitting. Nothing is excluded because of a label, runtime or error.
    write(output/'plan.json',{'schema':'isaforge-v6-mapping-development-v1','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Post-V5 fitting-only targeted ablation; not an independent test',
        'versions':_versions(),'frozen_tool':expected_tool,'configuration':CONFIGURATION,'seeds':seeds,'views':['dual_graph','dual_graph_plus_mapping'],
        'fitting_formula_indices':fit,'fold_validation_indices':split['fold_validation_indices'],
        'feature_names':FEATURE_NAMES,'cut_size':CUT_SIZE,'cut_budget':CUT_BUDGET,
        'input_sha256':hashes,'original_graph_cache':cache_records,
        'calibration_rows_used':0,'test_rows_used':0,'external_rows_used':0,'new_hardware_measurements':0,
        'limitations':'Bounded structural cuts, gate-reuse/MFFC and area-flow proxies; no target mapping/Boolean matching/carry model/optimality guarantee.'})
    for path in sources:
        target=output/'sources'/path.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    mapped=[]
    for i,path in enumerate(graph_paths):
        values=feature_dict(read(path));mapped.append([values[n] for n in FEATURE_NAMES])
        if (i+1)%200==0:print('cached DAG features',i+1,'/',len(rows),flush=True)
    block=np.asarray(mapped,dtype=float)
    if block.shape!=(1665,len(FEATURE_NAMES)) or not np.isfinite(block).all() or np.any(block<0):raise ValueError('Invalid mapping descriptor matrix')
    write(output/'features.json',{'columns':FEATURE_NAMES,'records':[{'formula':r['formula'],'development_index':i,'values':v}
        for r,i,v in zip(rows,fit,block.tolist())]})
    extraction_seconds=time.perf_counter()-began
    matrices={'dual_graph':base,'dual_graph_plus_mapping':np.column_stack((base,block))}
    scores={view:{} for view in matrices};timings={view:{} for view in matrices}
    for seed in seeds:
        for view,values in matrices.items():
            prediction=np.zeros(len(rows));fold_times=[]
            for training,validation in folds:
                before=time.perf_counter();model=ExtraTreesRegressor(**CONFIGURATION,random_state=seed)
                model.fit(values[training],y[training]);prediction[validation]=np.maximum(model.predict(values[validation]),0)
                fold_times.append(time.perf_counter()-before)
            prediction[original_zero(x)]=0
            if view=='dual_graph':
                reference=aligned_oof(rows,fit,read(diagnostics/'predictions'/f'dual_graph-seed-{seed}.json'))
                if not np.array_equal(reference,prediction):raise ValueError('Matched dual-graph control failed exact prediction replay')
            scores[view][str(seed)]=metrics(y,prediction,strata);timings[view][str(seed)]=fold_times
            write(output/'predictions'/f'{view}-seed-{seed}.json',[{'development_index':fit[i],'formula':r['formula'],'stratum':strata[i],
                'lut4_count':float(y[i]),'predicted_lut4':float(prediction[i])} for i,r in enumerate(rows)])
            write(output/'progress.json',{'scores':scores,'fold_fit_predict_seconds':timings})
            print(view,seed,'macro-MAE',scores[view][str(seed)]['macro_stratum_mae_lut4'],flush=True)
    summary={'scope':'Fitting-only development; no model selection or repaired heldout score','scores':scores,
        'fold_fit_predict_seconds':timings,'feature_extraction_and_provenance_seconds':extraction_seconds,
        'feature_count':{view:values.shape[1] for view,values in matrices.items()},
        'truncation':{'rows_with_truncation':int(np.sum(block[:,FEATURE_NAMES.index('truncated_gate_count')]>0)),
          'truncated_gates_total':float(block[:,FEATURE_NAMES.index('truncated_gate_count')].sum()),
          'discarded_merge_states_total':float(block[:,FEATURE_NAMES.index('discarded_merge_states')].sum())},
        'paired_differences':{},'by_view':{},'source_plan_sha256':sha(output/'plan.json'),
        'limits':['All rows remain, including truncated graphs. No target mapping or feature regeneration.',
                  'Cut/MFFC counts and area-flow values are generic structural descriptors, not LUT/carry labels.',
                  'Fixed seeds share data/folds; seed variation is not population uncertainty.',
                  'Original graph only; functional cut truth tables, normalized cuts and target carry chains are untested.']}
    for view in matrices:
        maes=[scores[view][str(seed)]['macro_stratum_mae_lut4'] for seed in seeds]
        summary['by_view'][view]={'macro_mae_mean':float(np.mean(maes)),
            'macro_mae_sample_sd':float(np.std(maes,ddof=1)) if len(maes)>1 else None,
            'by_stratum_mean_mae':{s:float(np.mean([scores[view][str(seed)]['by_stratum'][s]['mae_lut4'] for seed in seeds])) for s in sorted(set(strata))}}
    differences=[scores['dual_graph_plus_mapping'][str(seed)]['macro_stratum_mae_lut4']-scores['dual_graph'][str(seed)]['macro_stratum_mae_lut4'] for seed in seeds]
    summary['paired_differences']={'values_lut4':differences,'mean_lut4':float(np.mean(differences)),
       'improved_seed_count':int(np.sum(np.array(differences)<0)),
       'per_stratum_mean_difference':{s:summary['by_view']['dual_graph_plus_mapping']['by_stratum_mean_mae'][s]-summary['by_view']['dual_graph']['by_stratum_mean_mae'][s] for s in sorted(set(strata))}}
    if any(sha(path)!=digest for path,digest in hashes.items()):raise ValueError('Study input/source changed')
    for path,record in zip(graph_paths,cache_records):
        if sha(path)!=record['files_sha256']['graph.json']:raise ValueError('Cached original DAG changed during run')
    write(output/'summary.json',summary);print(json.dumps(summary['paired_differences'],indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--diagnostics',type=Path,default=ROOT/'results/2026-10-14-development-diagnostics')
    parser.add_argument('--cache-root',type=Path,default=ROOT/'generated/v5-features/generic')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--single-seed',action='store_true')
    args=parser.parse_args();run(args.root,args.diagnostics,args.cache_root,args.output,SEEDS[:1] if args.single_seed else SEEDS)

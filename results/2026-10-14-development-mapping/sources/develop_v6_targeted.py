#!/usr/bin/env python3
"""Fixed AST-routed feature-view ablation on existing fitting-only OOF rows.

No model fitting, feature generation, hardware tools, calibration/test outcomes,
or external inputs. Both router variants and all five inherited seeds remain
reported. This post-V5 development analysis cannot repair a consumed test.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from develop_v6 import fold_plan,metrics
from isaforge.features import parse_formula
from isaforge.area_model_v5 import source_hashes

SEEDS=tuple(range(2026101421,2026101426))
VIEWS=('original_graph','dual_graph','dual_semantics')
ROUTERS={'original_graph_mul_semantics':'original_graph','dual_graph_mul_semantics':'dual_graph'}
MULTIPLY=frozenset(('mul','mulh','mulhu','mulhsu'))
SOURCES=(
 {'title':'MasterRTL: A Pre-Synthesis PPA Estimation Framework for Any RTL Design',
  'url':'https://arxiv.org/abs/2311.08441',
  'relevance':'A bit-level simple-operator graph reduces abstraction mismatch. This supports keeping original graphs as a control; it does not establish FPGA LUT4 transfer.'},
 {'title':'Improvements to Technology Mapping for LUT-Based FPGAs',
  'url':'https://people.eecs.berkeley.edu/~alanmi/publications/2006/fpga06_map.pdf',
  'relevance':'Section2 defines feasible cuts and MFFCs; sections3-5 discuss cut enumeration, area recovery and structural choices. These motivate bounded4-cut and reuse descriptors beyond gate counts, not new algorithmic claims.'},
 {'title':'Combinational and Sequential Mapping with Priority Cuts',
  'url':'https://people.eecs.berkeley.edu/~alanmi/publications/2007/iccad07_map.pdf',
  'relevance':'Sections4.1-4.4 retain a small fixed number of cuts and rank by depth, leaves and area flow. A future fixed-budget descriptor can mirror this without calling target mapping.'},
 {'title':'Conformal Prediction Beyond Exchangeability',
  'url':'https://arxiv.org/abs/2202.13415',
  'relevance':'Coverage under nonexchangeability needs additional control; development seed stability or a new gate does not validate existing bounds on shifted applications.'},
)


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def recorded_input_digest(records,path):
    """Match the hash-bound repository suffix after relocating a checkout."""
    suffix='results/2026-10-14-v5/'+Path(path).name
    matches=[value for name,value in records.items() if Path(name).as_posix().endswith('/'+suffix) or name==suffix]
    if len(matches)!=1:
        raise ValueError('Diagnostic input identity is missing or ambiguous')
    return matches[0]


def has_multiply(formula):
    """Pure syntax decision, including dead products; no stratum/label lookup."""
    pending=[parse_formula(formula)]
    while pending:
        node=pending.pop()
        if node.value in MULTIPLY:return True
        pending.extend(node.children)
    return False


def route_predictions(formulas,base,semantic):
    base,semantic=np.asarray(base,dtype=float),np.asarray(semantic,dtype=float)
    if base.shape!=(len(formulas),) or semantic.shape!=base.shape:
        raise ValueError('Router requires aligned one-dimensional predictions')
    if not np.isfinite(base).all() or not np.isfinite(semantic).all() or np.any(base<0) or np.any(semantic<0):
        raise ValueError('Router inputs must be finite nonnegative predictions')
    gate=np.array([has_multiply(f) for f in formulas])
    return np.where(gate,semantic,base)


def fitting_inputs(root,diagnostics):
    """Select the exact1665 fit rows before any numerical label operations."""
    manifest=read(root/'freeze.json');start=read(diagnostics/'run-start.json')
    frozen={(root/r['path']).resolve():r['sha256'] for r in manifest['files']}
    inputs=[root/'development-data.json',root/'development-features.json',root/'split.json']
    for path in inputs:
        if frozen.get(path.resolve())!=sha(path):raise ValueError('Frozen development input changed')
        if recorded_input_digest(start['input_sha256'],path)!=sha(path):
            raise ValueError('Diagnostic inputs differ from frozen development')
    if start['v5_freeze_sha256']!=sha(root/'freeze.json') or start['runtime_source_sha256']!=source_hashes():
        raise ValueError('Diagnostic runtime/freeze differs')
    if start.get('calibration_rows_used')!=0 or start.get('test_rows_used')!=0:
        raise ValueError('Only fitting-only diagnostics allowed')
    split=read(inputs[2]);fit=split['fit_indices'];calibration=set(split['calibration_indices'])
    if len(fit)!=1665 or len(set(fit))!=1665 or set(fit)&calibration:
        raise ValueError('Expected exact1665 fitting rows isolated from calibration')
    if start['fitting_formula_indices']!=fit or start['fold_validation_indices']!=split['fold_validation_indices']:
        raise ValueError('Diagnostic folds differ from frozen fitting folds')
    all_rows=read(inputs[0]);rows=[all_rows[i] for i in fit];del all_rows
    groups={i:split['component_by_formula'][r['formula']] for i,r in zip(fit,rows)}
    fold_plan(fit,split['fold_validation_indices'],groups)
    return rows,fit,inputs


def aligned_oof(rows,fit,records):
    if len(records)!=len(rows):raise ValueError('OOF prediction coverage differs')
    result=[]
    for row,index,record in zip(rows,fit,records):
        if (record['development_index']!=index or record['formula']!=row['formula']
                or record['stratum']!=row.get('stratum','workload')
                or record['lut4_count']!=row['lut4_count']):
            raise ValueError('OOF identities/labels are not fitting-row aligned')
        value=record['predicted_lut4']
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not np.isfinite(value) or value<0:
            raise ValueError('Invalid OOF prediction')
        result.append(value)
    return np.asarray(result,dtype=float)


def run(root,diagnostics,output):
    root,diagnostics,output=map(lambda p:Path(p).resolve(),(root,diagnostics,output))
    if output==ROOT or ROOT in output.parents:raise ValueError('Development output must be outside repository')
    if output.exists() and any(output.iterdir()):raise ValueError('Existing development run is immutable')
    rows,fit,inputs=fitting_inputs(root,diagnostics)
    prediction_paths=[diagnostics/'predictions'/f'{view}-seed-{seed}.json' for view in VIEWS for seed in SEEDS]
    dependencies=[*inputs,root/'freeze.json',diagnostics/'run-start.json',diagnostics/'source-manifest.json',
                  *prediction_paths,Path(__file__).resolve(),ROOT/'scripts/develop_v6.py',ROOT/'isaforge/features.py']
    hashes={str(path):sha(path) for path in dependencies}
    formulas=[r['formula'] for r in rows];gate=np.array([has_multiply(f) for f in formulas])
    strata=np.asarray([r.get('stratum','workload') for r in rows])
    y=np.asarray([r['lut4_count'] for r in rows],dtype=float)
    # Record the complete fixed plan before computing router outcomes.
    write(output/'plan.json',{'schema':'isaforge-v6-targeted-development-v1','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Post-V5 fitting-only development; no independent-test claim','sources':SOURCES,
        'gate':'AST contains mul/mulh/mulhu/mulhsu: dual_semantics; otherwise named base',
        'routers':ROUTERS,'controls':VIEWS,'seeds':SEEDS,'fitting_formula_indices':fit,
        'fold_validation_indices':read(root/'split.json')['fold_validation_indices'],
        'calibration_rows_used':0,'test_rows_used':0,'external_rows_used':0,'new_fits':0,'new_hardware_measurements':0,
        'input_sha256':hashes,'primary':'Macro-stratum fitting OOF MAE; report every fixed router, base, seed and stratum',
        'routing_counts':{'semantic':int(gate.sum()),'base':int((~gate).sum())}})
    output.joinpath('sources').mkdir(exist_ok=True)
    shutil.copyfile(__file__,output/'sources/develop_v6_targeted.py')
    predictions={view:{} for view in (*VIEWS,*ROUTERS)};scores={view:{} for view in predictions}
    for seed in SEEDS:
        for view in VIEWS:
            p=aligned_oof(rows,fit,read(diagnostics/'predictions'/f'{view}-seed-{seed}.json'))
            predictions[view][seed]=p;scores[view][str(seed)]=metrics(y,p,strata)
        for variant,base in ROUTERS.items():
            p=route_predictions(formulas,predictions[base][seed],predictions['dual_semantics'][seed])
            predictions[variant][seed]=p;scores[variant][str(seed)]=metrics(y,p,strata)
            write(output/'predictions'/f'{variant}-seed-{seed}.json',[
                {'development_index':fit[i],'formula':r['formula'],'stratum':strata[i],
                 'lut4_count':float(y[i]),'predicted_lut4':float(p[i]),
                 'routed_view':'dual_semantics' if gate[i] else base} for i,r in enumerate(rows)])
    summary={'scope':'Development only; fixed router variants were specified before this run; no new independent evidence',
        'all_seeds':scores,'by_variant':{},'paired_comparisons':{},'routing_counts':read(output/'plan.json')['routing_counts'],
        'routing_counts_by_stratum':{s:{'semantic':int(np.sum(gate & (strata==s))),'base':int(np.sum(~gate & (strata==s)))} for s in sorted(set(strata))},
        'inference_complexity':{
          'deterministic_classifier':'O(AST nodes), no fitted gate or target/stratum lookup',
          'model_artifacts':'Two existing experts per router; no trained deployment artifact produced here',
          'selected_feature_columns':{'original_graph':74,'dual_graph':194,'dual_semantics':313},
          'runtime_limit':'Frozen extractor still computes all313 channels. Actual speed/memory savings require separately implemented view-aware extraction and benchmark; no runtime gain measured.',
          'bounds':'No gate calibration performed. Routing existing point models does not transfer their bounds; V6 needs fresh group calibration and independent workloads.'},
        'limits':['Post-V5 hypothesis uses consumed development diagnostics; OOF improvement is not a repaired test score.',
                  'Five inherited seeds describe algorithm stability, not independent observations or a population confidence interval.',
                  'Both experts were trained on the same fold training rows; conditional expert retraining is not tested.',
                  'A syntactic product routes to semantics even if normalization eliminates it; the gate is deliberately fixed.',
                  'No calibration/test/external outcomes entered router choice, fits or metrics.']}
    for view in predictions:
        values=np.array([scores[view][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS])
        summary['by_variant'][view]={'macro_mae_mean':float(values.mean()),'macro_mae_sample_sd':float(values.std(ddof=1)),
          'macro_mae_min':float(values.min()),'macro_mae_max':float(values.max()),
          'by_stratum_mean_mae':{s:float(np.mean([scores[view][str(seed)]['by_stratum'][s]['mae_lut4'] for seed in SEEDS])) for s in sorted(set(strata))},
          'maximum_underprediction_across_seeds':float(max(v['maximum_underprediction_lut4'] for score in scores[view].values() for v in score['by_stratum'].values()))}
    for router,base in ROUTERS.items():
        for control in (base,'dual_semantics'):
            differences=[scores[router][str(seed)]['macro_stratum_mae_lut4']-scores[control][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS]
            summary['paired_comparisons'][router+'_minus_'+control]={'differences_lut4':differences,'mean':float(np.mean(differences)),
              'improved_seeds':int(np.sum(np.array(differences)<0)),
              'per_stratum_mean_difference':{s:summary['by_variant'][router]['by_stratum_mean_mae'][s]-summary['by_variant'][control]['by_stratum_mean_mae'][s] for s in sorted(set(strata))}}
    if any(sha(path)!=digest for path,digest in hashes.items()):raise ValueError('Input/source changed during development run')
    write(output/'summary.json',summary)
    print(json.dumps({'output':str(output),'by_variant':summary['by_variant'],'paired_comparisons':summary['paired_comparisons']},indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5')
    parser.add_argument('--diagnostics',type=Path,default=ROOT/'results/2026-10-14-development-diagnostics')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.root,args.diagnostics,args.output)

#!/usr/bin/env python3
"""A separate, zero-fit point policy with exactly the base model's cap decisions.

Only cached, explicit 336-column features are accepted. No native jobs or fits.
All first-study data, including its former fresh40, are now consumed evidence.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import train_targeted_coverage as prior

read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-budget-preserving-coverage-v1'
NAME='budget_preserving_coverage'
POLICY={'caps_lut4':[32,64,128],
        'formula':'p=min(max(base,scoped_augmented217),nextcap(base))',
        'nextcap':'Smallest member of32/64/128 greater than or equal to base; positive infinity when base>128.',
        'route':prior.ROUTE,'fits':0,'calibrated':False,
        'limitation':'Exactly preserves base feasible/infeasible decisions at these three caps, including every existing base mistake; cannot improve budget classification there.'}
PRIOR=ROOT/'results/targeted-coverage'


def source_hashes():
    return {str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'tests/test_budget_preserving_coverage.py')}
def policy(base,scoped):
    b,s=np.asarray(base,dtype=float),np.asarray(scoped,dtype=float)
    need(b.shape==s.shape and b.ndim==1 and np.isfinite(b).all() and np.isfinite(s).all() and
         (b>=0).all() and (s>=0).all(), 'Aligned finite nonnegative point vectors required')
    upper=np.full(b.shape,np.inf)
    for cap in reversed(POLICY['caps_lut4']): upper=np.where(b<=cap,cap,upper)
    return np.minimum(np.maximum(b,s),upper)
def invariants(base,values):
    b,p=np.asarray(base,dtype=float),np.asarray(values,dtype=float)
    need(b.shape==p.shape and b.ndim==1 and np.isfinite(b).all() and np.isfinite(p).all() and
         (b>=0).all() and (p>=0).all(), 'Finite aligned points required')
    return {'pointwise_prediction_at_least_base':bool((p>=b).all()),
        'pointwise_cap_decisions_identical':{str(cap):bool(np.array_equal(p<=cap,b<=cap)) for cap in POLICY['caps_lut4']}}
def passed(check):
    return check['pointwise_prediction_at_least_base'] and all(check['pointwise_cap_decisions_identical'].values())
def metrics(panels):
    result={}
    for name,row in panels.items():
        b,p=row['models']['base'],row['models'][NAME];y=row['actual_lut4']
        m={'base':prior.model_metrics(b,y),NAME:prior.model_metrics(p,y)}
        m['checks']=invariants(b,p);m['comparison']=prior.compare(m['base'],m[NAME]);result[name]=m
    motivation=result['selection-validation']['comparison']
    gate=all(motivation[k] for k in ('mae_strictly_improved','positive_mape_strictly_improved')) and all(passed(m['checks']) for m in result.values())
    return {'panels':result,'development_gate_passed':gate,
        'scope':'All panels consumed, including first fresh40. Other-panel mean-error regressions are reported and do not disappear behind cap invariants.'}
def authenticate(output):
    protocol=read(output/'protocol.json')
    need(protocol['schema']==SCHEMA and protocol['policy']==POLICY and protocol['sources_sha256']==source_hashes(), 'Frozen policy/source differs')
    for name,digest in protocol['inputs_sha256'].items():need(sha(ROOT/name)==digest,'Frozen input differs: '+name)
    prior.load(PRIOR)
    return protocol
def project(row):
    b,s=row['models']['base'],row['models']['scoped_augmented217']
    return {**{k:row[k] for k in ('candidate_ids','formulas','actual_lut4') if k in row},
        'models':{'base':b,NAME:policy(b,s).tolist()},'source_scoped_points':s,'routes':row['routes']}


def prepare(output,fresh):
    need(not output.exists(),'Fresh policy output required')
    need(not (fresh/'labels.json').exists(),'Policy protocol must precede second fresh labels')
    rows=read(fresh/'candidates.json')
    need(len(rows)==32 and read(fresh/'novelty.json')['status']=='pass','Novel complete32 second fresh inputs required')
    prior.load(PRIOR)
    paths=[PRIOR/n for n in ('protocol.json','model-freeze.json','model.joblib','model.json','development-predictions.json',
                             'development-metrics.json','fresh-predictions.json','fresh-point-freeze.json','fresh-metrics.json')]
    paths += [ROOT/'models/base'/n for n in ('model.joblib','model.json')]
    paths += [ROOT/'results/targeted-coverage-validation'/n for n in ('candidates.json','labels.json')]
    paths += [fresh/n for n in ('candidates.json','novelty.json','plan.json')]
    protocol={'schema':SCHEMA,'frozen_at_utc':now(),'policy':POLICY,'new_fits':0,'native_jobs':0,
        'fresh':prior.relative(fresh),'fresh_count':32,'candidate_weight_source':prior.relative(PRIOR/'model.joblib'),
        'feature_columns':list(prior.v6.columns()),'sources_sha256':source_hashes(),
        'inputs_sha256':{prior.relative(p):sha(p) for p in paths},
        'development_rule':'MAE and positive-target MAPE strictly lower on consumed motivating40; predictions>=base and exactly equal p<=cap decisions pointwise at EACH32/64/128 on every retained panel including consumed first fresh40.',
        'fresh_rule':'MAE and positive-target MAPE strictly lower on independent second fresh32; pointwise p>=base and exact cap decisions at32/64/128; maximum underprediction and FA/FR counts separately no worse.',
        'missing_rule':'Retain every predeclared row; missing features or labels block eligibility; no replacements, retries, new fits or threshold search.',
        'scope':'Experimental isolated iCE40 LUT4 point policy. No optimality, calibrated safety, application transfer, timing, power or CPU guarantee. Base budget decisions remain unchanged.'}
    write(output/'protocol.json',protocol)
    panels={name:project(row) for name,row in read(PRIOR/'development-predictions.json').items()}
    former=read(PRIOR/'fresh-predictions.json'); old=ROOT/'results/targeted-coverage-validation'
    former['actual_lut4']=prior.labels_for(read(old/'candidates.json'),read(old/'labels.json'))
    panels['consumed-first-fresh40']=project(former)
    write(output/'development-predictions.json',panels)
    write(output/'development-metrics.json',metrics(panels))
    write(output/'policy-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'files_sha256':{n:sha(output/n) for n in ('development-predictions.json','development-metrics.json')},'new_fits':0})
    return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0,'development_gate_passed':read(output/'development-metrics.json')['development_gate_passed']}
def loaded_points(rows,payload):
    candidate=prior.load(PRIOR);base=prior.base_inference.load('base');x=prior.feature_matrix(rows,payload)
    values,routes=prior.points(rows,x,candidate,base)
    return {**values,NAME:policy(values['base'],values['scoped_augmented217']).tolist()},values['scoped_augmented217'],routes
def cap_decisions(models):
    return {name:{str(cap):(np.asarray(models[name])<=cap).tolist() for cap in POLICY['caps_lut4']}
            for name in ('base',NAME)}
def freeze_fresh(output):
    protocol=authenticate(output);fresh=ROOT/protocol['fresh']
    need(not (fresh/'labels.json').exists(),'Second fresh points must precede labels')
    rows=read(fresh/'candidates.json');models,s,routes=loaded_points(rows,read(fresh/'features.json'))
    checks=invariants(models['base'],models[NAME]);need(passed(checks),'Policy invariants failed')
    write(output/'fresh-predictions.json',{'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],
        'formulas':[r['formula'] for r in rows],'models':models,'source_scoped_points':s,'routes':routes,'checks':checks,
        'cap_decisions':cap_decisions(models)})
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'policy_freeze_sha256':sha(output/'policy-freeze.json'),'predictions_sha256':sha(output/'fresh-predictions.json'),
        'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False,'new_fits':0}
    write(output/'fresh-point-freeze.json',seal);return seal
def score(output):
    protocol=authenticate(output);fresh=ROOT/protocol['fresh'];seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('policy_freeze_sha256',output/'policy-freeze.json'),
                     ('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]:
        need(seal[key]==sha(path),'Sealed second fresh payload differs: '+key)
    saved=read(output/'fresh-predictions.json');rows=read(fresh/'candidates.json')
    need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Fresh point alignment differs')
    y=prior.labels_for(rows,read(fresh/'labels.json'));m={name:prior.model_metrics(saved['models'][name],y) for name in ('base',NAME)}
    checks=invariants(saved['models']['base'],saved['models'][NAME]);comparison=prior.compare(m['base'],m[NAME])
    fresh_gate=passed(checks) and all(comparison.values());dev=read(output/'development-metrics.json')['development_gate_passed']
    result={'schema':SCHEMA,'models':m,'checks':checks,'comparison':comparison,'fresh_gate_passed':fresh_gate,
        'development_gate_passed':dev,'scoped_experimental_eligibility':fresh_gate and dev,'new_fits':0,
        'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),'scope':protocol['scope']}
    write(output/'fresh-metrics.json',result);return result
def predict_cached(output,candidates,features,destination):
    authenticate(output);rows=read(candidates);models,s,routes=loaded_points(rows,read(features))
    result={'schema':SCHEMA,'model':NAME,'candidate_ids':[r.get('candidate_id') for r in rows],
        'formulas':[r['formula'] for r in rows],'models':models,'source_scoped_points':s,'routes':routes,
        'checks':invariants(models['base'],models[NAME]),'fits':0,'native_jobs':0,'calibration_status':'uncalibrated',
        'cap_decisions':cap_decisions(models),'policy':POLICY,'upper_lut4':None,
        'scope':read(output/'protocol.json')['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,result);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','freeze-fresh','score','predict','predict-cached'))
    parser.add_argument('--output',type=Path,default=ROOT/'results/budget-preserving-coverage')
    parser.add_argument('--fresh',type=Path,default=ROOT/'results/budget-preserving-validation')
    parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
    a=parser.parse_args();out=a.output.resolve()
    if a.command=='prepare':result=prepare(out,a.fresh.resolve())
    elif a.command in ('predict','predict-cached'):
        need(all((a.candidates,a.features,a.prediction_output)),'Explicit cached candidates/features/output required')
        result=predict_cached(out,a.candidates,a.features,a.prediction_output)
    else:result={'freeze-fresh':freeze_fresh,'score':score}[a.command](out)
    print(json.dumps(result,indent=2))

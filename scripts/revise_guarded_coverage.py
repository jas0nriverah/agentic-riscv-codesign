#!/usr/bin/env python3
"""One bounded coverage revision with preregistered routing and cached inference.

All previous panels are consumed development data. No native jobs are launched.
New test labels are read only after the fitted model and ordered points are sealed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import train_targeted_coverage as prior
import budget_preserving_coverage as incumbent

read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-guarded-revision-v1'
PRIMARY='guard_revised'
FALLBACK='guard_revised_static_abstain'
CANDIDATES=(PRIMARY,FALLBACK)
NAMES=('base','incumbent_guard',*CANDIDATES)
OUT=ROOT/'results/guarded-revision'
TRAIN=ROOT/'results/guarded-revision-data'
FRESH=ROOT/'results/guarded-revision-validation'
POLICIES={'guard':incumbent.POLICY['formula'],'caps_lut4':[32,64,128],
    'primary_route':prior.ROUTE,
    'repair_route':'Within original active route, use new1761 forest only if any signed sra/srai AND sub AND xor/xori occur anywhere; otherwise incumbent1729 forest.',
    'fallback_abstention':'Use base where original mixed_arithmetic route AND any srai node AND no variable_shift node. Otherwise primary route.',
    'development_selection':'First primary if every development gate passes, else fallback if every development gate passes, else no eligible model and primary evaluated diagnostically.',
    'prediction_inputs':'Original AST and explicit336 cached features only; no IDs, labels or predicted errors.'}
GATES={'retained':'Each complete retained panel MAE and positive-target MAPE <=base; maximum underprediction <=base; p>=base and identical cap decisions pointwise at each32/64/128.',
       'named_regressions':'Arithmetic-stress32 and consumed-second-fresh32 signed_dual_arithmetic4: MAE and positive-target MAPE <=base and strictly <incumbent.',
       'fresh':'All40: MAE and positive-target MAPE strictly <base AND <=incumbent; maximum underprediction <=base and identical cap decisions at each32/64/128; development eligibility required.',
       'missing':'All rows retained, no replacements/retries. Missing features/labels blocks eligibility. No postlabel threshold, route or criterion changes.'}


def source_hashes():
    return {prior.relative(p):sha(p) for p in (Path(__file__),ROOT/'tests/test_revise_guarded_coverage.py',
        ROOT/'scripts/budget_preserving_coverage.py',ROOT/'scripts/train_targeted_coverage.py',ROOT/'scripts/predict.py',
        *sorted((ROOT/'isaforge').glob('*.py')))}

def routes(formula):
    original=prior.route(formula)
    nodes=list(prior.walk(prior.parse_formula(formula)))
    ops={n.value for n in nodes}
    static_signed='srai' in ops
    repair=bool(ops & {'sra','srai'}) and 'sub' in ops and bool(ops & {'xor','xori'})
    classes=original['coverage_classes']
    abstain='mixed-arithmetic-xor' in classes and static_signed and 'variable-shift' not in classes
    return {**original,'signed_static_abstention':abstain,'signed_arithmetic_repair':repair}

def points(rows,x,candidate,base=None,old=None):
    base=base or prior.base_inference.load('base')
    old=old or prior.load(incumbent.PRIOR)
    b=np.asarray([r['predicted_lut4'] for r in base.predict_features(rows,x)])
    a=np.asarray([r['predicted_lut4'] for r in candidate.predict_features(rows,x)])
    o=np.asarray([r['predicted_lut4'] for r in old.predict_features(rows,x)])
    routing=[routes(r['formula']) for r in rows]
    selected=np.asarray([r['source_model']=='augmented217' for r in routing])
    abstain=np.asarray([r['signed_static_abstention'] for r in routing])
    repair=np.asarray([r['signed_arithmetic_repair'] for r in routing])
    revised=np.where(repair,a,o)
    return {'base':b.tolist(),'incumbent_guard':incumbent.policy(b,np.where(selected,o,b)).tolist(),
        PRIMARY:incumbent.policy(b,np.where(selected,revised,b)).tolist(),
        FALLBACK:incumbent.policy(b,np.where(selected & ~abstain,revised,b)).tolist()},routing

def accuracy_no_worse(base,candidate,strict=False):
    op=(lambda x,y:x<y) if strict else (lambda x,y:x<=y)
    return {k:bool(candidate[k] is not None and base[k] is not None and op(candidate[k],base[k]))
        for k in ('mae_lut4','positive_mape_percent')}

def panel_metrics(row):
    y=row['actual_lut4'];models=row['models']
    m={n:prior.model_metrics(models[n],y) for n in NAMES}
    m['checks']={n:{'accuracy_no_worse_base':accuracy_no_worse(m['base'],m[n]),
        'accuracy_strictly_better_incumbent':accuracy_no_worse(m['incumbent_guard'],m[n],True),
        'invariants':incumbent.invariants(models['base'],models[n]),
        'maximum_underprediction_no_worse':m[n]['maximum_underprediction_lut4']<=m['base']['maximum_underprediction_lut4']} for n in CANDIDATES}
    return m

def development_metrics(panels):
    metrics={name:panel_metrics(row) for name,row in panels.items()}
    signed=panels['consumed-second-fresh32'];mask=[i for i,r in enumerate(read(ROOT/'results/budget-preserving-validation/candidates.json')) if r['template']=='signed_dual_arithmetic']
    need(len(mask)==4,'Exact signed_dual_arithmetic4 subgroup required')
    subgroup={'actual_lut4':[signed['actual_lut4'][i] for i in mask],
        'models':{n:[signed['models'][n][i] for i in mask] for n in NAMES}}
    named={'arithmetic-stress32':metrics['arithmetic-stress'],'signed_dual_arithmetic4':panel_metrics(subgroup)}
    gates={}
    for n in CANDIDATES:
        retained=all(all(m['checks'][n]['accuracy_no_worse_base'].values()) and incumbent.passed(m['checks'][n]['invariants']) and m['checks'][n]['maximum_underprediction_no_worse'] for m in metrics.values())
        regression=all(all(m['checks'][n]['accuracy_no_worse_base'].values()) and all(m['checks'][n]['accuracy_strictly_better_incumbent'].values()) for m in named.values())
        gates[n]={'all_retained_panels_pass':retained,'both_named_regressions_fixed':regression,'development_gate_passed':retained and regression}
    selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
    return {'panels':metrics,'named_regressions':named,'gates':gates,'selected_candidate':selected,
        'evaluated_candidate':selected or PRIMARY,'all_panels_consumed':True,'independent_test':False}

def authenticate(output):
    protocol=read(output/'protocol.json')
    need(protocol['schema']==SCHEMA and protocol['policies']==POLICIES and protocol['gates']==GATES,'Frozen protocol differs')
    need(protocol['sources_sha256']==source_hashes(),'Frozen revision source differs')
    for path,digest in protocol['inputs_sha256'].items():need(sha(ROOT/path)==digest,'Frozen input differs: '+path)
    prior.load(incumbent.PRIOR)
    return protocol

def prepare(output,training,fresh):
    need(not (output/'protocol.json').exists(),'Revision protocol already exists')
    need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(),'Protocol must precede new labels')
    t,f=read(training/'candidates.json'),read(fresh/'candidates.json')
    need(len(t)==32 and len(f)==40,'Exact32 training and40 independent test required')
    need(not ({r['formula'] for r in t}&{r['formula'] for r in f}),'Train/test overlap')
    for d in (training,fresh):need(read(d/'novelty.json')['status']=='pass','Novelty screen failed')
    inputs=[ROOT/'results/feature-comparison'/n for n in ('inputs.npz','columns.json','rows.json')]
    inputs += [ROOT/'results/targeted-coverage-data'/n for n in ('candidates.json','features.json','labels.json')]
    inputs += [incumbent.PRIOR/n for n in ('protocol.json','model-freeze.json','model.joblib','model.json')]
    inputs += [ROOT/'results/budget-preserving-coverage'/n for n in ('protocol.json','development-predictions.json','fresh-predictions.json','fresh-metrics.json')]
    inputs += [ROOT/'models/base'/n for n in ('model.joblib','model.json')]
    for name in prior.PANELS:
        folder=ROOT/'results'/name;inputs += [folder/'features.json']
        inputs += [folder/'candidates.json',folder/'labels.json'] if name=='selection-validation' else [folder/'observations.json']
    for name in ('targeted-coverage-validation','budget-preserving-validation'):
        inputs += [ROOT/'results'/name/n for n in ('candidates.json','features.json','labels.json')]
    for d in (training,fresh):inputs += [d/n for n in ('candidates.json','novelty.json','plan.json')]
    protocol={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),
        'policies':POLICIES,'gates':GATES,'configuration':prior.v6.FIXED_PARAMETERS,
        'original_training_count':1665,'prior_targeted_training_count':64,'new_training_count':32,'total_training_count':1761,
        'planned_fits':1,'maximum_fits':2,'maximum_fit_seconds':120,'workers':1,'native_threads':1,'native_jobs':0,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),
        'retained_panels':{**prior.PANELS,'consumed-first-fresh40':40,'consumed-second-fresh32':32},
        'consumed_evaluation_rows_used_for_fitting':0,'chronology':'Protocol/cohorts before new training labels; one fit; deterministic development selection; model+all40points before fresh labels.',
        'scope':'Experimental isolated iCE40 LUT4 points; uncalibrated, no CPU/timing/power/application-transfer guarantee. Exact base cap decisions preserve its existing budget errors.',
        'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(p):sha(p) for p in inputs}}
    write(output/'protocol.json',protocol)
    return {'protocol_sha256':sha(output/'protocol.json'),'fits':0}

def retained_panels(candidate):
    base=prior.base_inference.load('base');old=prior.load(incumbent.PRIOR);panels={}
    for name in prior.PANELS:
        rows,x,y=prior.retained_panel(name);models,routing=points(rows,x,candidate,base,old)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':y,'models':models,'routes':routing}
    for name,folder in [('consumed-first-fresh40','targeted-coverage-validation'),('consumed-second-fresh32','budget-preserving-validation')]:
        d=ROOT/'results'/folder;rows=read(d/'candidates.json');x=prior.feature_matrix(rows,read(d/'features.json'))
        models,routing=points(rows,x,candidate,base,old)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':prior.labels_for(rows,read(d/'labels.json')),'models':models,'routes':routing}
    return panels

def load(output):
    authenticate(output);seal=read(output/'model-freeze.json')
    need(seal['schema']==SCHEMA and seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==1,'Exact one-fit seal required')
    for n,d in seal['files_sha256'].items():need(sha(output/n)==d,'Frozen fitted file differs: '+n)
    model=prior.v6.load_model(output/'model.joblib')
    need(model.kind=='mapping_v6' and model.training_formula_count==1761 and model.calibration['status']=='uncalibrated' and model.calibration['upper_margin_lut4'] is None and model.training_provenance['protocol_sha256']==sha(output/'protocol.json'),'Exact1761 uncalibrated model required')
    return model

def run(output):
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    protocol=authenticate(output);training=ROOT/protocol['training'];fresh=ROOT/protocol['fresh']
    need(not (output/'run-start.json').exists(),'Fit already attempted')
    need(not (fresh/'labels.json').exists(),'Fresh labels must be unavailable')
    blocks=[];targets=[]
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        columns=read(ROOT/'results/feature-comparison/columns.json')
        blocks.append(data['x'][:,[columns.index(n) for n in prior.v6.columns()]]);targets.append(data['y'])
    for d,count in [(ROOT/'results/targeted-coverage-data',64),(training,32)]:
        rows=read(d/'candidates.json');need(len(rows)==count,'Training row count differs')
        blocks.append(prior.feature_matrix(rows,read(d/'features.json')));targets.append(np.asarray(prior.labels_for(rows,read(d/'labels.json')),dtype=float))
    x,y=np.vstack(blocks),np.concatenate(targets);need(x.shape==(1761,336) and y.shape==(1761,),'1761 training contract differs')
    started=time.monotonic();write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'planned_fits':1,'maximum_fits':2,'maximum_fit_seconds':120})
    def deadline(signum,frame):raise TimeoutError('120-second fit stage exhausted')
    previous=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120);fits=[]
    try:
        with threadpool_limits(limits=1):
            model=ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS);began=time.monotonic();model.fit(x[:,prior.v6.mapping_indices()],y)
            fits.append({'fit_index':1,'seed':prior.v6.FIXED_PARAMETERS['random_state'],'feature_count':217,'training_count':1761,'fit_seconds':time.monotonic()-began})
            write(output/'timings.json',fits);base=prior.base_inference.load('base')
            candidate=prior.v6.V6Predictor(estimator=model,kind='mapping_v6',feature_columns=prior.v6.columns(),training_formula_count=1761,
                calibration=prior.v6.uncalibrated(),feature_minimum=x.min(axis=0).tolist(),feature_maximum=x.max(axis=0).tolist(),
                frozen_tool=base.frozen_tool,runtime_source_sha256=prior.v6.source_hashes(),training_provenance={'experimental_only':True,
                    'protocol_sha256':sha(output/'protocol.json'),'original_count':1665,'prior_targeted_count':64,'new_training_count':32,
                    'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'consumed_evaluation_rows_used':0})
            prior.v6.save_model(candidate,output/'model.joblib');panels=retained_panels(candidate)
            write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
        seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started,
            'files_sha256':{n:sha(output/n) for n in ('model.joblib','model.json','timings.json','development-predictions.json','development-metrics.json','run-start.json')}}
        write(output/'model-freeze.json',seal);return seal
    except BaseException as error:
        write(output/'failure.json',{'error':str(error),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started});raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)

def freeze_fresh(output):
    protocol=authenticate(output);fresh=ROOT/protocol['fresh'];need(not (fresh/'labels.json').exists(),'Fresh points must precede labels')
    candidate=load(output);rows=read(fresh/'candidates.json');models,routing=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),candidate)
    dev=read(output/'development-metrics.json')
    saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'routes':routing,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],
        'checks':{n:incumbent.invariants(models['base'],models[n]) for n in CANDIDATES}}
    need(all(incumbent.passed(c) for c in saved['checks'].values()),'Guard invariants failed');write(output/'fresh-predictions.json',saved)
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'model_freeze_sha256':sha(output/'model-freeze.json'),
        'predictions_sha256':sha(output/'fresh-predictions.json'),'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False}
    write(output/'fresh-point-freeze.json',seal)
    bindings={prior.relative(p):sha(p) for p in (output/'protocol.json',output/'model-freeze.json',output/'fresh-point-freeze.json',output/'fresh-predictions.json',fresh/'features.json',fresh/'candidates.json')}
    write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':bindings})
    return seal

def score(output):
    protocol=authenticate(output);load(output);fresh=ROOT/protocol['fresh'];seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('model_freeze_sha256',output/'model-freeze.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]:need(seal[key]==sha(path),'Sealed fresh payload differs: '+key)
    rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Fresh point alignment differs')
    y=prior.labels_for(rows,read(fresh/'labels.json'));m=panel_metrics({'models':saved['models'],'actual_lut4':y});dev=read(output/'development-metrics.json');gates={}
    for n in CANDIDATES:
        checks={'strictly_better_base':accuracy_no_worse(m['base'],m[n],True),'no_worse_incumbent':accuracy_no_worse(m['incumbent_guard'],m[n]),
            'guard_invariants':m['checks'][n]['invariants'],'maximum_underprediction_no_worse':m['checks'][n]['maximum_underprediction_no_worse']}
        freshpass=all(checks['strictly_better_base'].values()) and all(checks['no_worse_incumbent'].values()) and incumbent.passed(checks['guard_invariants']) and checks['maximum_underprediction_no_worse']
        gates[n]={'checks':checks,'fresh_gate_passed':freshpass,'development_gate_passed':dev['gates'][n]['development_gate_passed'],
            'eligible':freshpass and dev['selected_candidate']==n}
    selected=dev['selected_candidate'];result={'schema':SCHEMA,'models':m,'gates':gates,'selected_candidate':selected,
        'evaluated_candidate':dev['evaluated_candidate'],'scoped_experimental_eligibility':bool(selected and gates[selected]['eligible']),
        'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),'fits':1,'native_jobs':0,'scope':protocol['scope']}
    write(output/'fresh-metrics.json',result);return result

def predict_cached(output,candidates,features,destination):
    protocol=authenticate(output);candidate=load(output);rows=read(candidates);models,routing=points(rows,prior.feature_matrix(rows,read(features)),candidate)
    dev=read(output/'development-metrics.json');evaluated=dev['evaluated_candidate']
    result={'schema':SCHEMA,'model':evaluated,'selected_candidate':dev['selected_candidate'],'development_eligible':dev['selected_candidate'] is not None,
        'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':models,'predicted_lut4':models[evaluated],
        'routes':routing,'checks':{n:incumbent.invariants(models['base'],models[n]) for n in CANDIDATES},'fits':0,'native_jobs':0,
        'calibration_status':'uncalibrated','upper_lut4':None,'policies':POLICIES,'scope':protocol['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,result);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','run','freeze-fresh','score','predict-cached'))
    parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--training',type=Path,default=TRAIN);parser.add_argument('--fresh',type=Path,default=FRESH)
    parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if args.command=='prepare':result=prepare(out,args.training.resolve(),args.fresh.resolve())
    elif args.command=='predict-cached':
        need(all((args.candidates,args.features,args.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,args.candidates,args.features,args.prediction_output)
    else:result={'run':run,'freeze-fresh':freeze_fresh,'score':score}[args.command](out)
    print(json.dumps(result,indent=2))

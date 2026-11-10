#!/usr/bin/env python3
"""One bounded, narrowly routed coverage refinement; all inference is cached.

The previous seven evaluation panels are consumed development evidence. The
fixed two-policy hierarchy is selected before new test labels; no native jobs.
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
import revise_guarded_coverage as previous
prior,guard=previous.prior,previous.incumbent
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-signed-refinement-v1'
PRIMARY='signed_refinement'
FALLBACK='signed_refinement_compound_fallback'
CANDIDATES=(PRIMARY,FALLBACK)
CURRENT='incumbent_current'
NAMES=('base','earlier_guard',CURRENT,*CANDIDATES)
OUT=ROOT/'results/signed-refinement'
TRAIN=ROOT/'results/signed-refinement-data'
FRESH=ROOT/'results/signed-refinement-validation'
OLD=ROOT/'results/guarded-revision'
POLICIES={'guard':'p=min(max(base,scoped),nextcap(base)); nextcap is smallest32/64/128 >=base, or infinity',
    'caps_lut4':[32,64,128],
    'compound_route':'Any original sra node with in0/in1 anywhere in its second (shift) operand subtree AND BOTH addi and xori anywhere in its first (data) operand subtree.',
    'add_boolean_route':'Any original sra node with input-bearing second operand, AND add AND xor AND (and OR or) anywhere in original AST, with NO sub or mul/mulh/mulhu/mulhsu anywhere.',
    'primary':'New1793 forest only on compound OR add_boolean; current guarded policy elsewhere. Apply unchanged base cap guard.',
    'fallback':'Earlier1729 guarded point on compound (takes precedence); new1793 forest on add_boolean; current guarded point elsewhere. Apply unchanged base cap guard.',
    'development_selection':'First primary if every development gate passes; else fallback if every development gate passes; else no eligible model and primary evaluated diagnostically. Freeze selection before fresh labels.',
    'input_scope':'Original AST and explicit cached336-column features only. No IDs, labels, error lookup, normalization, threshold search or postlabel route changes.',
    'complexity':'Composite of four fixed300-tree forests (base1665, prior1729, previous1761, new1793) plus structural routing and cap guard; not a pure learned selector.'}
GATES={'retained':'All seven complete retained panels MAE and positive-target MAPE <=current incumbent; p>=base and identical pointwise decisions at caps32/64/128; maximum underprediction <=current incumbent (and <=base).',
    'new_named_fixes':'Research192 MAE <=earlier1729 guarded policy. Consumed third-fresh heldout_signed_variable_add_boolean4 MAE <=base AND positive-target MAPE <=current incumbent.',
    'prior_named_fixes':'Arithmetic-stress32 and consumed second-fresh signed_dual_arithmetic4 MAE and positive-target MAPE <=current incumbent.',
    'fresh':'Complete new40 MAE AND positive-target MAPE strictly <current incumbent AND base; exact pointwise base cap decisions32/64/128, p>=base and maximum underprediction <=current incumbent (and <=base); selected development policy only.',
    'missing':'Every predeclared row retained; missing/failed features or labels block eligibility; no replacements, retries, extra fits or postlabel criterion changes.'}


def source_hashes():
    return {prior.relative(p):sha(p) for p in (Path(__file__),ROOT/'tests/test_refine_signed_coverage.py',
        ROOT/'scripts/revise_guarded_coverage.py',ROOT/'scripts/budget_preserving_coverage.py',
        ROOT/'scripts/train_targeted_coverage.py',ROOT/'scripts/predict.py',*sorted((ROOT/'isaforge').glob('*.py')))}

def route(formula):
    nodes=list(prior.walk(prior.parse_formula(formula)));ops={n.value for n in nodes}
    signed=[n for n in nodes if n.value=='sra' and any(c.value in ('in0','in1') for c in prior.walk(n.children[1]))]
    compound=any({'addi','xori'} <= {c.value for c in prior.walk(n.children[0])} for n in signed)
    add_boolean=bool(signed) and {'add','xor'}<=ops and bool(ops&{'and','or'}) and not bool(ops&({'sub'}|set(prior.v6.MULTIPLY)))
    return {'compound':compound,'add_boolean':add_boolean,'new_coverage':compound or add_boolean}

def points(rows,x,candidate,base=None,old=None,current=None):
    current=current or previous.load(OLD)
    values,_=previous.points(rows,x,current,base,old)
    b=np.asarray(values['base']);earlier=np.asarray(values['incumbent_guard']);existing=np.asarray(values[previous.FALLBACK])
    new=np.asarray([r['predicted_lut4'] for r in candidate.predict_features(rows,x)])
    routing=[route(r['formula']) for r in rows]
    scope=np.asarray([r['new_coverage'] for r in routing],dtype=bool)
    compound=np.asarray([r['compound'] for r in routing],dtype=bool)
    primary=np.where(scope,new,existing)
    fallback=np.where(compound,earlier,primary)
    return {'base':b.tolist(),'earlier_guard':earlier.tolist(),CURRENT:existing.tolist(),
        PRIMARY:guard.policy(b,primary).tolist(),FALLBACK:guard.policy(b,fallback).tolist()},routing

def accuracy(reference,candidate,strict=False):
    op=(lambda x,y:x<y) if strict else (lambda x,y:x<=y)
    return {k:bool(candidate[k] is not None and reference[k] is not None and op(candidate[k],reference[k])) for k in ('mae_lut4','positive_mape_percent')}

def panel_metrics(row):
    y=row['actual_lut4'];models=row['models'];m={n:prior.model_metrics(models[n],y) for n in NAMES}
    m['checks']={n:{'accuracy_no_worse_current':accuracy(m[CURRENT],m[n]),
        'invariants':guard.invariants(models['base'],models[n]),
        'maximum_underprediction_no_worse_base':m[n]['maximum_underprediction_lut4']<=m['base']['maximum_underprediction_lut4'],
        'maximum_underprediction_no_worse_current':m[n]['maximum_underprediction_lut4']<=m[CURRENT]['maximum_underprediction_lut4']} for n in CANDIDATES}
    return m

def subgroup(row,folder,template):
    rows=read(folder/'candidates.json');indices=[i for i,r in enumerate(rows) if r['template']==template]
    need(len(indices)==4,'Complete preregistered four-case subgroup required: '+template)
    return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
        'models':{n:[row['models'][n][i] for i in indices] for n in NAMES}})

def development_metrics(panels):
    metrics={name:panel_metrics(row) for name,row in panels.items()}
    named={'research192':metrics['research-baselines'],
        'signed_add_boolean4':subgroup(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'arithmetic_stress32':metrics['arithmetic-stress'],
        'signed_dual_arithmetic4':subgroup(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic')}
    gates={}
    for n in CANDIDATES:
        retained=all(all(m['checks'][n]['accuracy_no_worse_current'].values()) and guard.passed(m['checks'][n]['invariants']) and m['checks'][n]['maximum_underprediction_no_worse_base'] and m['checks'][n]['maximum_underprediction_no_worse_current'] for m in metrics.values())
        research=named['research192'][n]['mae_lut4']<=named['research192']['earlier_guard']['mae_lut4']
        add=named['signed_add_boolean4'];addfix=add[n]['mae_lut4']<=add['base']['mae_lut4'] and add[n]['positive_mape_percent']<=add[CURRENT]['positive_mape_percent']
        oldfix=all(all(accuracy(named[k][CURRENT],named[k][n]).values()) for k in ('arithmetic_stress32','signed_dual_arithmetic4'))
        gates[n]={'all_seven_retained_panels_pass':retained,'research_mae_no_worse_earlier_guard':research,
            'signed_add_boolean_fixed':addfix,'both_prior_named_fixes_retained':oldfix,'development_gate_passed':retained and research and addfix and oldfix}
    selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
    return {'panels':metrics,'named_regressions':named,'gates':gates,'selected_candidate':selected,
        'evaluated_candidate':selected or PRIMARY,'all_panels_consumed':True,'independent_test':False}

def authenticate(output):
    protocol=read(output/'protocol.json')
    need(protocol['schema']==SCHEMA and protocol['policies']==POLICIES and protocol['gates']==GATES,'Frozen protocol differs')
    need(protocol['sources_sha256']==source_hashes(),'Frozen refinement source differs')
    for p,d in protocol['inputs_sha256'].items():need(sha(ROOT/p)==d,'Frozen input differs: '+p)
    previous.load(OLD)
    need(read(OLD/'development-metrics.json')['selected_candidate']==previous.FALLBACK,'Expected current incumbent policy differs')
    return protocol

def prepare(output,training,fresh):
    need(not (output/'protocol.json').exists(),'Refinement protocol already exists')
    need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(),'Protocol must precede all new labels')
    t,f=read(training/'candidates.json'),read(fresh/'candidates.json')
    need(len(t)==32 and len(f)==40,'Exact32training/40fresh required')
    need(not ({r['formula'] for r in t}&{r['formula'] for r in f}),'Train/test overlap')
    for d in (training,fresh):need(read(d/'novelty.json')['status']=='pass','Novelty screen failed')
    inputs=[ROOT/'results/feature-comparison'/n for n in ('inputs.npz','columns.json','rows.json')]
    for folder in ('targeted-coverage-data','guarded-revision-data'):
        inputs += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
    for folder in (guard.PRIOR,OLD):inputs += [folder/n for n in ('protocol.json','model-freeze.json','model.joblib','model.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json')]
    inputs += [ROOT/'models/base'/n for n in ('model.joblib','model.json')]
    for name in prior.PANELS:
        d=ROOT/'results'/name;inputs += [d/'features.json'];inputs += [d/'candidates.json',d/'labels.json'] if name=='selection-validation' else [d/'observations.json']
    for folder in ('targeted-coverage-validation','budget-preserving-validation','guarded-revision-validation'):
        inputs += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
    for d in (training,fresh):inputs += [d/n for n in ('candidates.json','novelty.json','plan.json')]
    protocol={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),
        'policies':POLICIES,'gates':GATES,'configuration':prior.v6.FIXED_PARAMETERS,
        'original_training_count':1665,'prior_targeted_training_count':64,'previous_revision_training_count':32,'new_training_count':32,'total_training_count':1793,
        'planned_fits':1,'maximum_fits':1,'maximum_fit_seconds':120,'workers':1,'native_threads':1,'native_jobs':0,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),
        'retained_panels':{**prior.PANELS,'consumed-first-fresh40':40,'consumed-second-fresh32':32,'consumed-third-fresh40':40},
        'consumed_evaluation_rows_used_for_fitting':0,'chronology':'Protocol/cohorts before any new training labels; one fit; deterministic development selection; weights and all40freshpoints before new test labels.',
        'scope':'Experimental isolated iCE40 LUT4 point estimates, uncalibrated. No optimality, CPU/timing/power/application-transfer guarantee; exact base cap decisions preserve existing mistakes.',
        'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(p):sha(p) for p in inputs}}
    write(output/'protocol.json',protocol);return {'protocol_sha256':sha(output/'protocol.json'),'fits':0}

def panel_inputs():
    for name in prior.PANELS:
        yield name,prior.retained_panel(name)
    for name,folder in [('consumed-first-fresh40','targeted-coverage-validation'),('consumed-second-fresh32','budget-preserving-validation'),('consumed-third-fresh40','guarded-revision-validation')]:
        d=ROOT/'results'/folder;rows=read(d/'candidates.json')
        yield name,(rows,prior.feature_matrix(rows,read(d/'features.json')),prior.labels_for(rows,read(d/'labels.json')))

def retained_panels(candidate):
    base=prior.base_inference.load('base');old=prior.load(guard.PRIOR);current=previous.load(OLD);panels={}
    for name,(rows,x,y) in panel_inputs():
        models,routing=points(rows,x,candidate,base,old,current)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':y,'models':models,'routes':routing}
    return panels

def load(output):
    authenticate(output);seal=read(output/'model-freeze.json')
    need(seal['schema']==SCHEMA and seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==1,'Exact one-fit seal required')
    for n,d in seal['files_sha256'].items():need(sha(output/n)==d,'Frozen fitted artifact differs: '+n)
    model=prior.v6.load_model(output/'model.joblib')
    need(model.kind=='mapping_v6' and model.training_formula_count==1793 and model.calibration['status']=='uncalibrated' and model.calibration['upper_margin_lut4'] is None and model.training_provenance['protocol_sha256']==sha(output/'protocol.json'),'Exact1793 uncalibrated forest required')
    return model

def run(output):
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    protocol=authenticate(output);training=ROOT/protocol['training'];fresh=ROOT/protocol['fresh']
    need(not (output/'run-start.json').exists(),'Fit already attempted');need(not (fresh/'labels.json').exists(),'Fresh labels must remain unavailable')
    blocks=[];targets=[]
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        columns=read(ROOT/'results/feature-comparison/columns.json');blocks.append(data['x'][:,[columns.index(n) for n in prior.v6.columns()]]);targets.append(data['y'])
    for d,count in [(ROOT/'results/targeted-coverage-data',64),(ROOT/'results/guarded-revision-data',32),(training,32)]:
        rows=read(d/'candidates.json');need(len(rows)==count,'Training row count differs')
        blocks.append(prior.feature_matrix(rows,read(d/'features.json')));targets.append(np.asarray(prior.labels_for(rows,read(d/'labels.json')),dtype=float))
    x,y=np.vstack(blocks),np.concatenate(targets);need(x.shape==(1793,336) and y.shape==(1793,),'1793 training contract differs')
    started=time.monotonic();write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'planned_fits':1,'maximum_fits':1,'maximum_fit_seconds':120})
    def deadline(signum,frame):raise TimeoutError('120-second bounded fit stage exhausted')
    previous_handler=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120);fits=[]
    try:
        with threadpool_limits(limits=1):
            model=ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS);began=time.monotonic();model.fit(x[:,prior.v6.mapping_indices()],y)
            fits.append({'fit_index':1,'seed':prior.v6.FIXED_PARAMETERS['random_state'],'feature_count':217,'training_count':1793,'fit_seconds':time.monotonic()-began})
            write(output/'timings.json',fits);base=prior.base_inference.load('base')
            candidate=prior.v6.V6Predictor(estimator=model,kind='mapping_v6',feature_columns=prior.v6.columns(),training_formula_count=1793,
                calibration=prior.v6.uncalibrated(),feature_minimum=x.min(axis=0).tolist(),feature_maximum=x.max(axis=0).tolist(),
                frozen_tool=base.frozen_tool,runtime_source_sha256=prior.v6.source_hashes(),training_provenance={'experimental_only':True,
                    'protocol_sha256':sha(output/'protocol.json'),'original_count':1665,'prior_targeted_count':64,'previous_revision_count':32,'new_training_count':32,
                    'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'consumed_evaluation_rows_used':0})
            prior.v6.save_model(candidate,output/'model.joblib');panels=retained_panels(candidate)
            write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
        seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started,
            'files_sha256':{n:sha(output/n) for n in ('model.joblib','model.json','timings.json','development-predictions.json','development-metrics.json','run-start.json')}}
        write(output/'model-freeze.json',seal);return seal
    except BaseException as error:
        write(output/'failure.json',{'error':str(error),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started});raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)

def freeze_fresh(output):
    protocol=authenticate(output);fresh=ROOT/protocol['fresh'];need(not (fresh/'labels.json').exists(),'Fresh points must precede labels')
    candidate=load(output);rows=read(fresh/'candidates.json');models,routing=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),candidate);dev=read(output/'development-metrics.json')
    saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'routes':routing,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],
        'checks':{n:guard.invariants(models['base'],models[n]) for n in CANDIDATES}}
    need(all(guard.passed(c) for c in saved['checks'].values()),'Guard invariants failed');write(output/'fresh-predictions.json',saved)
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'model_freeze_sha256':sha(output/'model-freeze.json'),
        'predictions_sha256':sha(output/'fresh-predictions.json'),'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False}
    write(output/'fresh-point-freeze.json',seal)
    bindings={prior.relative(p):sha(p) for p in (output/'protocol.json',output/'model-freeze.json',output/'fresh-point-freeze.json',output/'fresh-predictions.json',fresh/'features.json',fresh/'candidates.json')}
    write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':bindings});return seal

def score_values(saved,y,dev):
    m=panel_metrics({'models':saved['models'],'actual_lut4':y});gates={}
    for n in CANDIDATES:
        checks={'strictly_better_base':accuracy(m['base'],m[n],True),'strictly_better_current':accuracy(m[CURRENT],m[n],True),
            'invariants':m['checks'][n]['invariants'],'maximum_underprediction_no_worse_base':m['checks'][n]['maximum_underprediction_no_worse_base'],
            'maximum_underprediction_no_worse_current':m['checks'][n]['maximum_underprediction_no_worse_current']}
        passed=all(checks['strictly_better_base'].values()) and all(checks['strictly_better_current'].values()) and guard.passed(checks['invariants']) and checks['maximum_underprediction_no_worse_base'] and checks['maximum_underprediction_no_worse_current']
        gates[n]={'checks':checks,'fresh_gate_passed':passed,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':passed and dev['selected_candidate']==n}
    selected=dev['selected_candidate']
    return m,gates,bool(selected and gates[selected]['eligible'])

def score(output):
    protocol=authenticate(output);load(output);fresh=ROOT/protocol['fresh'];seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('model_freeze_sha256',output/'model-freeze.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]:need(seal[key]==sha(path),'Sealed fresh payload differs: '+key)
    rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Fresh alignment differs')
    y=prior.labels_for(rows,read(fresh/'labels.json'));dev=read(output/'development-metrics.json');m,gates,eligible=score_values(saved,y,dev)
    result={'schema':SCHEMA,'models':m,'gates':gates,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],
        'scoped_experimental_eligibility':eligible,'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),
        'fits':1,'native_jobs':0,'scope':protocol['scope']}
    write(output/'fresh-metrics.json',result);return result

def predict_cached(output,candidates,features,destination):
    protocol=authenticate(output);candidate=load(output);rows=read(candidates);models,routing=points(rows,prior.feature_matrix(rows,read(features)),candidate)
    dev=read(output/'development-metrics.json');evaluated=dev['evaluated_candidate']
    result={'schema':SCHEMA,'model':evaluated,'selected_candidate':dev['selected_candidate'],'development_eligible':dev['selected_candidate'] is not None,
        'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':models,'predicted_lut4':models[evaluated],
        'routes':routing,'checks':{n:guard.invariants(models['base'],models[n]) for n in CANDIDATES},'fits':0,'native_jobs':0,
        'calibration_status':'uncalibrated','upper_lut4':None,'policies':POLICIES,'scope':protocol['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,result);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}

def replay(output):
    protocol=authenticate(output);candidate=load(output);panels=retained_panels(candidate)
    need(panels==read(output/'development-predictions.json'),'Development point replay differs')
    dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Development metric replay differs')
    fresh=ROOT/protocol['fresh'];rows=read(fresh/'candidates.json');models,routing=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),candidate)
    saved=read(output/'fresh-predictions.json');need(saved['models']==models and saved['routes']==routing,'Fresh point replay differs')
    scored=False
    if (output/'fresh-metrics.json').exists():
        y=prior.labels_for(rows,read(fresh/'labels.json'));m,gates,eligible=score_values(saved,y,dev);result=read(output/'fresh-metrics.json')
        need(m==result['models'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Fresh metric replay differs');scored=True
    return {'status':'pass','development_rows':sum(len(z['actual_lut4']) for z in panels.values()),'fresh_rows':len(rows),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare','run','freeze-fresh','score','predict-cached','replay'))
    p.add_argument('--output',type=Path,default=OUT);p.add_argument('--training',type=Path,default=TRAIN);p.add_argument('--fresh',type=Path,default=FRESH)
    p.add_argument('--candidates',type=Path);p.add_argument('--features',type=Path);p.add_argument('--prediction-output',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if a.command=='prepare':result=prepare(out,a.training.resolve(),a.fresh.resolve())
    elif a.command=='predict-cached':
        need(all((a.candidates,a.features,a.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,a.candidates,a.features,a.prediction_output)
    else:result={'run':run,'freeze-fresh':freeze_fresh,'score':score,'replay':replay}[a.command](out)
    print(json.dumps(result,indent=2))

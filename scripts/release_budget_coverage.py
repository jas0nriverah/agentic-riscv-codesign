#!/usr/bin/env python3
"""One bounded upward budget release, sealed before fresh labels.

All eight prior panels are consumed development evidence. Inference uses only
original AST routing, cached features and fixed forests; no labels or IDs.
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
import refine_signed_coverage as signed
prior=signed.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-budget-release-v1'
PRIMARY='budget_release'
FALLBACK='budget_release_compound_only'
CANDIDATES=(PRIMARY,FALLBACK)
CURRENT='incumbent_signed'
PREVIOUS='previous_guarded'
ABLATION='release1793_uncapped'
NAMES=('base',PREVIOUS,CURRENT,ABLATION,*CANDIDATES)
OUT=ROOT/'results/budget-release'
TRAIN=ROOT/'results/budget-release-data'
FRESH=ROOT/'results/budget-release-validation'
CAPS=(32,64,128)
TOLERANCE=1e-10
POLICIES={
    'primary':'On signed-refinement compound OR add_boolean original-AST route, p=max(incumbent_signed,new1825_raw); incumbent_signed elsewhere.',
    'fallback':'On signed-refinement compound original-AST route only, p=max(incumbent_signed,new1825_raw); incumbent_signed elsewhere.',
    'routes':signed.POLICIES['compound_route']+'; '+signed.POLICIES['add_boolean_route'],
    'cap_rule':'No cap clipping. Accept iff p<=cap, inclusive; caps32/64/128. Upward release can reduce FA and increase FR; evaluate separately.',
    'selection':'First primary if all development gates pass, else fallback if all pass, else no eligible candidate; primary evaluated diagnostically. Freeze before fresh labels.',
    'inputs':'Original formula AST and explicit cached336features only. No label/error/id lookup or routing, normalization, threshold search, or postlabel policy changes.',
    'diagnostic_ablation':'release1793_uncapped=max(incumbent_signed,1793raw) on primary scope; incumbent elsewhere. Cached zero-fit comparator, never selectable.',
    'complexity':'Five fixed300-tree217-feature forests plus AST routing; one new forest fitted on1825 training rows. Uncalibrated point estimate.'}
GATES={
    'retained':'Each complete eight retained panels: MAE and positive-target MAPE <=incumbent_signed; maximum underprediction <=incumbent_signed; FA and FR separately <=incumbent_signed at each32/64/128. All prior named fixes likewise.',
    'remaining_regression':'Consumed fourth-fresh40 heldout_compound_signed_add_xor4 MAE and positive-target MAPE <=previous_guarded (1761 policy), to repair the actual remaining regression.',
    'fresh':'Complete40 MAE and positive-target MAPE strictly <incumbent_signed AND base; FA and FR separately <=incumbent_signed per cap, with strictly fewer summed FA cap events; maximum underprediction <=incumbent_signed. All fresh compound-route rows MAE and MAPE <=incumbent_signed. Only development-selected candidate eligible.',
    'tolerance':TOLERANCE,
    'missing':'Every preregistered row retained; missing/failed features or labels block eligibility. No replacements, retries, additional fits, threshold search or postlabel criteria changes.'}


def source_hashes():
    paths=[Path(__file__),ROOT/'tests/test_release_budget_coverage.py',ROOT/'scripts/refine_signed_coverage.py',ROOT/'scripts/revise_guarded_coverage.py',ROOT/'scripts/budget_preserving_coverage.py',ROOT/'scripts/train_targeted_coverage.py',ROOT/'scripts/predict.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    return {prior.relative(p):sha(p) for p in paths}


def points(rows,x,candidate,incumbent=None):
    incumbent=incumbent or signed.load(signed.OUT)
    old,routing=signed.points(rows,x,incumbent)
    current=np.asarray(old[signed.PRIMARY]);raw=np.asarray([r['predicted_lut4'] for r in candidate.predict_features(rows,x)])
    oldraw=np.asarray([r['predicted_lut4'] for r in incumbent.predict_features(rows,x)])
    compound=np.asarray([r['compound'] for r in routing],dtype=bool)
    scope=np.asarray([r['new_coverage'] for r in routing],dtype=bool)
    return {'base':old['base'],PREVIOUS:old[signed.CURRENT],CURRENT:current.tolist(),
        ABLATION:np.where(scope,np.maximum(current,oldraw),current).tolist(),
        PRIMARY:np.where(scope,np.maximum(current,raw),current).tolist(),
        FALLBACK:np.where(compound,np.maximum(current,raw),current).tolist()},routing


def accuracy(reference,candidate,strict=False):
    return {k:bool(candidate[k] is not None and reference[k] is not None and
        (candidate[k]<reference[k]-TOLERANCE if strict else candidate[k]<=reference[k]+TOLERANCE))
        for k in ('mae_lut4','positive_mape_percent')}


def cap_events(reference,candidate,y):
    r,c,y=map(np.asarray,(reference,candidate,y))
    return {str(cap):{'actual_accept':int(np.sum(y<=cap)),'actual_reject':int(np.sum(y>cap)),
        'corrected_false_accept':int(np.sum((r<=cap)&(c>cap)&(y>cap))),
        'new_false_accept':int(np.sum((r>cap)&(c<=cap)&(y>cap))),
        'corrected_false_reject':int(np.sum((r>cap)&(c<=cap)&(y<=cap))),
        'new_false_reject':int(np.sum((r<=cap)&(c>cap)&(y<=cap)))} for cap in CAPS}


def panel_metrics(row):
    y=row['actual_lut4'];models=row['models'];m={n:prior.model_metrics(models[n],y) for n in NAMES}
    m['checks']={}
    for n in CANDIDATES:
        caps={str(cap):{k:m[n]['caps'][str(cap)][k]<=m[CURRENT]['caps'][str(cap)][k] for k in ('false_accept','false_reject')} for cap in CAPS}
        m['checks'][n]={'accuracy_no_worse_current':accuracy(m[CURRENT],m[n]),'caps_no_worse_current':caps,
            'pointwise_at_least_current':bool(np.all(np.asarray(models[n])>=np.asarray(models[CURRENT]))),
            'maximum_underprediction_no_worse_current':m[n]['maximum_underprediction_lut4']<=m[CURRENT]['maximum_underprediction_lut4']+TOLERANCE,
            'cap_events':cap_events(models[CURRENT],models[n],y)}
    return m


def passes(check):
    return all(check['accuracy_no_worse_current'].values()) and all(all(v.values()) for v in check['caps_no_worse_current'].values()) and check['pointwise_at_least_current'] and check['maximum_underprediction_no_worse_current']


def subset(row,indices):
    need(bool(indices),'Empty required subgroup')
    return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
        'models':{n:[row['models'][n][i] for i in indices] for n in NAMES}})


def template_group(row,folder,template):
    indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template]
    need(len(indices)==4,'Exact four-case named subgroup required: '+template)
    return subset(row,indices)


def development_metrics(panels):
    metrics={name:panel_metrics(row) for name,row in panels.items()}
    named={'compound_signed_add_xor4':template_group(panels['consumed-fourth-fresh40'],signed.FRESH,'heldout_compound_signed_add_xor'),
        'signed_add_boolean4':template_group(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'arithmetic_stress32':metrics['arithmetic-stress'],
        'signed_dual_arithmetic4':template_group(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic')}
    gates={}
    for n in CANDIDATES:
        retained=all(passes(m['checks'][n]) for m in metrics.values())
        fixed=all(accuracy(named['compound_signed_add_xor4'][PREVIOUS],named['compound_signed_add_xor4'][n]).values())
        preserved=all(passes(named[k]['checks'][n]) for k in ('signed_add_boolean4','arithmetic_stress32','signed_dual_arithmetic4'))
        gates[n]={'all_eight_retained_panels_pass':retained,'compound_remaining_regression_fixed':fixed,
            'all_prior_named_fixes_preserved':preserved,'development_gate_passed':retained and fixed and preserved}
    selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
    return {'panels':metrics,'named_regressions':named,'gates':gates,'selected_candidate':selected,
        'evaluated_candidate':selected or PRIMARY,'all_panels_consumed':True,'independent_test':False}


def panel_inputs():
    yield from signed.panel_inputs()
    rows=read(signed.FRESH/'candidates.json')
    yield 'consumed-fourth-fresh40',(rows,prior.feature_matrix(rows,read(signed.FRESH/'features.json')),prior.labels_for(rows,read(signed.FRESH/'labels.json')))


def retained_panels(candidate):
    incumbent=signed.load(signed.OUT);panels={}
    for name,(rows,x,y) in panel_inputs():
        models,routing=points(rows,x,candidate,incumbent)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':y,'models':models,'routes':routing}
    return panels


def authenticate(output):
    protocol=read(output/'protocol.json')
    need(protocol['schema']==SCHEMA and protocol['policies']==POLICIES and protocol['gates']==GATES,'Frozen protocol differs')
    need(protocol['sources_sha256']==source_hashes(),'Frozen source differs')
    for p,d in protocol['inputs_sha256'].items():need(sha(ROOT/p)==d,'Frozen input differs: '+p)
    signed.load(signed.OUT)
    return protocol


def prepare(output,training,fresh):
    need(not (output/'protocol.json').exists(),'Protocol already frozen')
    need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(),'Freeze before all new labels')
    t,f=read(training/'candidates.json'),read(fresh/'candidates.json')
    need(len(t)==32 and len(f)==40,'Exact32training/40fresh required')
    need(not ({r['formula'] for r in t}&{r['formula'] for r in f}),'Train/test overlap')
    for d in (training,fresh):need(read(d/'novelty.json')['status']=='pass','Novelty failed')
    paths=[ROOT/'results/feature-comparison'/n for n in ('inputs.npz','columns.json','rows.json')]
    for folder in ('targeted-coverage-data','guarded-revision-data','signed-refinement-data'):
        paths += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
    paths += [signed.OUT/n for n in ('protocol.json','model-freeze.json','model.joblib','model.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json')]
    for name in prior.PANELS:
        d=ROOT/'results'/name;paths += [d/'features.json'];paths += [d/'candidates.json',d/'labels.json'] if name=='selection-validation' else [d/'observations.json']
    for folder in ('targeted-coverage-validation','budget-preserving-validation','guarded-revision-validation','signed-refinement-validation'):
        paths += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
    for d in (training,fresh):paths += [d/n for n in ('candidates.json','novelty.json','plan.json')]
    counts={**prior.PANELS,'consumed-first-fresh40':40,'consumed-second-fresh32':32,'consumed-third-fresh40':40,'consumed-fourth-fresh40':40}
    protocol={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),
        'policies':POLICIES,'gates':GATES,'configuration':prior.v6.FIXED_PARAMETERS,'total_training_count':1825,
        'original_training_count':1665,'prior_extra_training_count':128,'new_training_count':32,
        'planned_fits':1,'maximum_fits':1,'maximum_fit_seconds':120,'workers':1,'native_threads':1,'native_jobs':0,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),'retained_panels':counts,
        'fresh_compound_indices':[i for i,r in enumerate(f) if signed.route(r['formula'])['compound']],
        'consumed_evaluation_rows_used_for_fitting':0,
        'chronology':'Protocol/cohorts before all new labels; one fit; deterministic development selection; model and all40freshpoints frozen before fresh labels.',
        'scope':'Experimental isolated iCE40 LUT4 point estimates; uncalibrated. No optimality, calibrated safety, timing, power, CPU or application-transfer guarantee.',
        'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(p):sha(p) for p in paths}}
    need(bool(protocol['fresh_compound_indices']),'Fresh compound subgroup required')
    write(output/'protocol.json',protocol);return {'protocol_sha256':sha(output/'protocol.json'),'fits':0}


def load(output):
    authenticate(output);seal=read(output/'model-freeze.json')
    need(seal['schema']==SCHEMA and seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==1,'Exact one-fit seal required')
    for n,d in seal['files_sha256'].items():need(sha(output/n)==d,'Frozen fitted artifact differs: '+n)
    model=prior.v6.load_model(output/'model.joblib')
    need(model.kind=='mapping_v6' and model.training_formula_count==1825 and model.calibration['status']=='uncalibrated' and model.calibration['upper_margin_lut4'] is None and model.training_provenance['protocol_sha256']==sha(output/'protocol.json'),'Exact1825uncalibrated forest required')
    return model


def run(output):
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    protocol=authenticate(output);training=ROOT/protocol['training'];fresh=ROOT/protocol['fresh']
    need(not (output/'run-start.json').exists(),'Fit already attempted');need(not (fresh/'labels.json').exists(),'Fresh labels must remain unavailable')
    blocks=[];targets=[]
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        columns=read(ROOT/'results/feature-comparison/columns.json');blocks.append(data['x'][:,[columns.index(n) for n in prior.v6.columns()]]);targets.append(data['y'])
    for d,count in [(ROOT/'results/targeted-coverage-data',64),(ROOT/'results/guarded-revision-data',32),(ROOT/'results/signed-refinement-data',32),(training,32)]:
        rows=read(d/'candidates.json');need(len(rows)==count,'Training count differs')
        blocks.append(prior.feature_matrix(rows,read(d/'features.json')));targets.append(np.asarray(prior.labels_for(rows,read(d/'labels.json')),dtype=float))
    x,y=np.vstack(blocks),np.concatenate(targets);need(x.shape==(1825,336) and y.shape==(1825,),'1825 training contract differs')
    started=time.monotonic();write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'planned_fits':1,'maximum_fits':1,'maximum_fit_seconds':120})
    def deadline(signum,frame):raise TimeoutError('120-second fit stage exhausted')
    handler=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120);fits=[]
    try:
        with threadpool_limits(limits=1):
            model=ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS);began=time.monotonic();model.fit(x[:,prior.v6.mapping_indices()],y)
            fits.append({'fit_index':1,'seed':prior.v6.FIXED_PARAMETERS['random_state'],'feature_count':217,'training_count':1825,'fit_seconds':time.monotonic()-began})
            write(output/'timings.json',fits);base=prior.base_inference.load('base')
            candidate=prior.v6.V6Predictor(estimator=model,kind='mapping_v6',feature_columns=prior.v6.columns(),training_formula_count=1825,
                calibration=prior.v6.uncalibrated(),feature_minimum=x.min(axis=0).tolist(),feature_maximum=x.max(axis=0).tolist(),
                frozen_tool=base.frozen_tool,runtime_source_sha256=prior.v6.source_hashes(),training_provenance={'experimental_only':True,
                    'protocol_sha256':sha(output/'protocol.json'),'original_count':1665,'prior_extra_count':128,'new_training_count':32,
                    'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),'consumed_evaluation_rows_used':0})
            prior.v6.save_model(candidate,output/'model.joblib');panels=retained_panels(candidate)
            write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
        seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started,
            'files_sha256':{n:sha(output/n) for n in ('model.joblib','model.json','timings.json','development-predictions.json','development-metrics.json','run-start.json')}}
        write(output/'model-freeze.json',seal);return seal
    except BaseException as error:
        write(output/'failure.json',{'error':str(error),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started});raise
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)


def freeze_fresh(output):
    protocol=authenticate(output);fresh=ROOT/protocol['fresh'];need(not (fresh/'labels.json').exists(),'Freeze points before labels')
    rows=read(fresh/'candidates.json');models,routing=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),load(output));dev=read(output/'development-metrics.json')
    need(all(np.all(np.asarray(models[n])>=np.asarray(models[CURRENT])) for n in CANDIDATES),'Upward invariant failed')
    saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'routes':routing,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate']}
    write(output/'fresh-predictions.json',saved)
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'model_freeze_sha256':sha(output/'model-freeze.json'),
        'predictions_sha256':sha(output/'fresh-predictions.json'),'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False}
    write(output/'fresh-point-freeze.json',seal)
    bindings={prior.relative(p):sha(p) for p in (output/'protocol.json',output/'model-freeze.json',output/'fresh-point-freeze.json',output/'fresh-predictions.json',fresh/'features.json',fresh/'candidates.json')}
    write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':bindings});return seal


def score_values(saved,y,dev,compound_indices):
    row={'models':saved['models'],'actual_lut4':y};m=panel_metrics(row);compound=subset(row,compound_indices);gates={}
    for n in CANDIDATES:
        checks={'strictly_better_base':accuracy(m['base'],m[n],True),'strictly_better_current':accuracy(m[CURRENT],m[n],True),
            'retained_style':m['checks'][n],
            'strictly_fewer_false_accept_cap_events':sum(m[n]['caps'][str(cap)]['false_accept'] for cap in CAPS)<sum(m[CURRENT]['caps'][str(cap)]['false_accept'] for cap in CAPS),
            'compound_accuracy_no_worse_current':accuracy(compound[CURRENT],compound[n])}
        passed=all(checks['strictly_better_base'].values()) and all(checks['strictly_better_current'].values()) and passes(checks['retained_style']) and checks['strictly_fewer_false_accept_cap_events'] and all(checks['compound_accuracy_no_worse_current'].values())
        gates[n]={'checks':checks,'fresh_gate_passed':passed,'development_gate_passed':dev['gates'][n]['development_gate_passed'],
            'eligible':passed and dev['selected_candidate']==n}
    selected=dev['selected_candidate']
    return m,compound,gates,bool(selected and gates[selected]['eligible'])


def score(output):
    protocol=authenticate(output);load(output);fresh=ROOT/protocol['fresh'];seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('model_freeze_sha256',output/'model-freeze.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]:need(seal[key]==sha(path),'Sealed payload differs: '+key)
    rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Fresh alignment differs')
    y=prior.labels_for(rows,read(fresh/'labels.json'));dev=read(output/'development-metrics.json');m,compound,gates,eligible=score_values(saved,y,dev,protocol['fresh_compound_indices'])
    result={'schema':SCHEMA,'models':m,'fresh_compound_subgroup':compound,'fresh_compound_count':len(protocol['fresh_compound_indices']),
        'gates':gates,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],
        'scoped_experimental_eligibility':eligible,'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),
        'fits':1,'native_jobs':0,'scope':protocol['scope']}
    write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
    protocol=authenticate(output);rows=read(candidates);models,routing=points(rows,prior.feature_matrix(rows,read(features)),load(output));dev=read(output/'development-metrics.json');evaluated=dev['evaluated_candidate']
    result={'schema':SCHEMA,'model':evaluated,'selected_candidate':dev['selected_candidate'],'development_eligible':dev['selected_candidate'] is not None,
        'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':models,'predicted_lut4':models[evaluated],
        'routes':routing,'fits':0,'native_jobs':0,'calibration_status':'uncalibrated','upper_lut4':None,'policies':POLICIES,'scope':protocol['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,result);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}


def replay(output):
    protocol=authenticate(output);candidate=load(output);panels=retained_panels(candidate)
    need(panels==read(output/'development-predictions.json'),'Development replay differs');dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Development metric replay differs')
    fresh=ROOT/protocol['fresh'];rows=read(fresh/'candidates.json');models,routing=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),candidate);saved=read(output/'fresh-predictions.json')
    need(saved['models']==models and saved['routes']==routing,'Fresh point replay differs');scored=False
    if (output/'fresh-metrics.json').exists():
        m,compound,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),dev,protocol['fresh_compound_indices']);result=read(output/'fresh-metrics.json')
        need(m==result['models'] and compound==result['fresh_compound_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Fresh metric replay differs');scored=True
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

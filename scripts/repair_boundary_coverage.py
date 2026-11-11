#!/usr/bin/env python3
"""Zero-fit, development-informed forest-median adjudication at fixed LUT caps.

All nine older panels are consumed. One policy is frozen before fresh labels;
existing1825forest weights remain unchanged. Tree spread is not calibrated risk.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import release_budget_coverage as release
prior=release.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-boundary-repair-v1'
NAME='boundary_median'
CURRENT=release.CURRENT
BUDGET=release.FALLBACK
NAMES=('base',CURRENT,BUDGET,NAME)
CAPS=(32,64,128)
TOLERANCE=1e-10
OUT=ROOT/'results/boundary-repair'
FRESH=ROOT/'results/boundary-repair-validation'
POLICY={
    'route':release.signed.POLICIES['compound_route'],
    'median':'numpy.median of all300 scalar tree predictions from existing1825forest, on217mappingfeatures; for even300, arithmetic mean of sorted positions149and150 (zero-based). This is not equivalent to strict-majority cap voting.',
    'formula':'Start with frozen budget_release_compound_only. On compound route, find each cap in[32,64,128] for which incumbent_signed<=cap<release AND forest_median<=cap. If any, return smallest qualifying cap; otherwise return release. Outside compound route return release exactly.',
    'decisions':'Accept iff point<=cap, inclusive. Exact cap values, no floating tolerance in inference or cap decisions.',
    'selection':'One fixed candidate; eligible for fresh promotion only if every development gate passes. No alternative selection, extra fits, parameter search or postlabel changes.',
    'inputs':'Original AST, explicit cached336features, frozen forest outputs and fixed caps only. No labels, IDs, predicted errors, normalized formulas or case lookup in inference.',
    'interpretation':'Parameter-free but informed by consumed development evidence. Correlated tree predictions and their median do not provide calibrated uncertainty or universal hardware safety.'}
GATES={
    'retained':'Each complete nine consumed panels and prior named subgroups: MAE and positive-target MAPE <=budget_release_compound_only; FA<=budget_release_compound_only and FR<=incumbent_signed separately at each32/64/128; maximum underprediction<=both comparators; incumbent_signed<=point<=release and exact release elsewhere.',
    'named_failure':'Consumed fifth-fresh40 index12 (fixed by frozen candidate manifest for evaluation only) actual125 and release>128; repaired point<=128. No inference lookup.',
    'fresh':'Complete40: MAE and MAPE strictly<incumbent_signed AND <=budget_release_compound_only; FA<=release and FR<=signed separately percap32/64/128; strictly fewer summed FA circuit-budget events than signed; maximum underprediction<=release and signed. Fresh compound subset MAE/MAPE<=release and all cap/tail gates. At least one fresh point must change versus release, so repair transfer is exercised. Development eligibility required.',
    'tolerance':TOLERANCE,
    'missing':'All preregistered rows retained; missing/failed features or labels blocks eligibility. No retries, replacements, fits, cohort filtering or criterion changes.'}


def source_hashes():
    return {prior.relative(p):sha(p) for p in (Path(__file__),ROOT/'tests/test_repair_boundary_coverage.py',ROOT/'scripts/release_budget_coverage.py',ROOT/'scripts/refine_signed_coverage.py',ROOT/'scripts/revise_guarded_coverage.py',ROOT/'scripts/budget_preserving_coverage.py',ROOT/'scripts/train_targeted_coverage.py',ROOT/'scripts/predict.py',*sorted((ROOT/'isaforge').glob('*.py')))}


def adjudicate(incumbent,budget,medians,compound):
    incumbent,budget,medians=np.asarray(incumbent),np.asarray(budget),np.asarray(medians)
    result=budget.copy();limits=[]
    for i,active in enumerate(compound):
        caps=[cap for cap in CAPS if active and incumbent[i]<=cap<budget[i] and medians[i]<=cap]
        if caps:result[i]=min(caps)
        limits.append(caps)
    return result,limits


def tree_medians(model,x):
    need(len(model.estimator.estimators_)==300,'Existing300-tree forest required')
    values=np.asarray([tree.predict(x[:,prior.v6.mapping_indices()]) for tree in model.estimator.estimators_])
    return np.median(values,axis=0),values


def points(rows,x,model=None):
    model=model or release.load(release.OUT)
    old,routing=release.points(rows,x,model)
    medians,trees=tree_medians(model,x)
    p,limits=adjudicate(old[CURRENT],old[BUDGET],medians,[r['compound'] for r in routing])
    models={n:old[n] for n in ('base',CURRENT,BUDGET)};models[NAME]=p.tolist()
    details={'forest_medians_lut4':medians.tolist(),'qualifying_caps_lut4':limits,
        'tree_predictions_above_cap':{str(cap):np.sum(trees>cap,axis=0).tolist() for cap in CAPS}}
    return models,routing,details


def accuracy(reference,candidate,strict=False):
    return {k:bool(reference[k] is not None and candidate[k] is not None and (candidate[k]<reference[k]-TOLERANCE if strict else candidate[k]<=reference[k]+TOLERANCE)) for k in ('mae_lut4','positive_mape_percent')}


def panel_metrics(row):
    y=row['actual_lut4'];models=row['models'];m={n:prior.model_metrics(models[n],y) for n in NAMES}
    m['checks']={'accuracy_no_worse_release':accuracy(m[BUDGET],m[NAME]),
        'caps':{str(cap):{'false_accept_no_worse_release':m[NAME]['caps'][str(cap)]['false_accept']<=m[BUDGET]['caps'][str(cap)]['false_accept'],
            'false_reject_no_worse_signed':m[NAME]['caps'][str(cap)]['false_reject']<=m[CURRENT]['caps'][str(cap)]['false_reject']} for cap in CAPS},
        'maximum_underprediction_no_worse_release':m[NAME]['maximum_underprediction_lut4']<=m[BUDGET]['maximum_underprediction_lut4']+TOLERANCE,
        'maximum_underprediction_no_worse_signed':m[NAME]['maximum_underprediction_lut4']<=m[CURRENT]['maximum_underprediction_lut4']+TOLERANCE,
        'pointwise_between_signed_and_release':bool(np.all(np.asarray(models[NAME])>=np.asarray(models[CURRENT])) and np.all(np.asarray(models[NAME])<=np.asarray(models[BUDGET]))),
        'events_vs_signed':release.cap_events(models[CURRENT],models[NAME],y),
        'events_vs_release':release.cap_events(models[BUDGET],models[NAME],y)}
    return m


def passed(checks):
    return all(checks['accuracy_no_worse_release'].values()) and all(all(v.values()) for v in checks['caps'].values()) and checks['maximum_underprediction_no_worse_release'] and checks['maximum_underprediction_no_worse_signed'] and checks['pointwise_between_signed_and_release']


def subset(row,indices):
    need(bool(indices),'Required subgroup empty')
    return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
        'models':{n:[row['models'][n][i] for i in indices] for n in NAMES}})


def template_group(row,folder,template):
    indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template]
    need(len(indices)==4,'Exact four-case named subgroup required: '+template)
    return subset(row,indices)


def panel_inputs():
    yield from release.panel_inputs()
    rows=read(release.FRESH/'candidates.json')
    yield 'consumed-fifth-fresh40',(rows,prior.feature_matrix(rows,read(release.FRESH/'features.json')),prior.labels_for(rows,read(release.FRESH/'labels.json')))


def retained_panels():
    model=release.load(release.OUT);panels={}
    for name,(rows,x,y) in panel_inputs():
        models,routing,details=points(rows,x,model)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':y,'models':models,'routes':routing,**details}
    return panels


def development_metrics(panels):
    metrics={name:panel_metrics(row) for name,row in panels.items()}
    named={'arithmetic_stress32':metrics['arithmetic-stress'],
        'signed_dual_arithmetic4':template_group(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic'),
        'signed_add_boolean4':template_group(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'compound_signed_add_xor4':template_group(panels['consumed-fourth-fresh40'],release.signed.FRESH,'heldout_compound_signed_add_xor'),
        'fifth_compound_signed_add_xor4':template_group(panels['consumed-fifth-fresh40'],release.FRESH,'heldout_compound_signed_add_xor'),
        'fifth_compound_signed_xordata_addxor4':template_group(panels['consumed-fifth-fresh40'],release.FRESH,'heldout_compound_signed_xordata_addxor')}
    row=panels['consumed-fifth-fresh40'];i=12
    need(row['actual_lut4'][i]==125 and row['models'][BUDGET][i]>128,'Named consumed failure differs')
    failure={'candidate_id':row['candidate_ids'][i],'formula':row['formulas'][i],'actual_lut4':row['actual_lut4'][i],
        'signed_lut4':row['models'][CURRENT][i],'release_lut4':row['models'][BUDGET][i],'repaired_lut4':row['models'][NAME][i],
        'median_lut4':row['forest_medians_lut4'][i],'repaired_at_cap128':row['models'][NAME][i]<=128}
    retained=all(passed(m['checks']) for m in metrics.values());prior_fixes=all(passed(m['checks']) for m in named.values())
    untouched=all(row['models'][NAME][i]==row['models'][BUDGET][i] for row in panels.values() for i,r in enumerate(row['routes']) if not r['compound'])
    gates={'all_nine_retained_panels_pass':retained,'all_prior_named_subgroups_preserved':prior_fixes,'named_failure_repaired':failure['repaired_at_cap128'],
        'outside_compound_exactly_release':untouched,'development_gate_passed':retained and prior_fixes and failure['repaired_at_cap128'] and untouched}
    return {'panels':metrics,'named_regressions':named,'named_failure':failure,'gates':{NAME:gates},
        'selected_candidate':NAME if gates['development_gate_passed'] else None,'evaluated_candidate':NAME,'all_panels_consumed':True,'independent_test':False}


def authenticate(output):
    p=read(output/'protocol.json')
    need(p['schema']==SCHEMA and p['policy']==POLICY and p['gates']==GATES,'Frozen protocol differs')
    need(p['sources_sha256']==source_hashes(),'Frozen source differs')
    for name,digest in p['inputs_sha256'].items():need(sha(ROOT/name)==digest,'Frozen input differs: '+name)
    release.load(release.OUT);return p


def prepare(output,fresh):
    need(not (output/'protocol.json').exists(),'Protocol already frozen');need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Freeze before new labels/attempts')
    need(not (fresh/'features.json').exists(),'Freeze before fresh features')
    rows=read(fresh/'candidates.json');need(len(rows)==40,'Exact40fresh required');need(read(fresh/'novelty.json')['status']=='pass','Novelty failed')
    goal=ROOT/'results/boundary-repair-goal.json';write(output/'goal-at-freeze.json',read(goal))
    paths=[output/'goal-at-freeze.json']+[release.OUT/n for n in ('protocol.json','model-freeze.json','model.joblib','model.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json')]
    for name in prior.PANELS:
        d=ROOT/'results'/name;paths += [d/'features.json'];paths += [d/'candidates.json',d/'labels.json'] if name=='selection-validation' else [d/'observations.json']
    for folder in ('targeted-coverage-validation','budget-preserving-validation','guarded-revision-validation','signed-refinement-validation','budget-release-validation'):
        paths += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
    paths += [fresh/n for n in ('candidates.json','novelty.json','plan.json')]
    p={'schema':SCHEMA,'frozen_at_utc':now(),'fresh':prior.relative(fresh),'policy':POLICY,'gates':GATES,
        'goal_source_sha256':sha(goal),'finite_candidates':[NAME],
        'existing_forest_training_count':1825,'existing_forest_trees':300,'planned_fits':0,'maximum_fits':0,'new_training_rows':0,'workers':1,'native_threads':1,'native_jobs':0,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),
        'retained_panels':{**prior.PANELS,'consumed-first-fresh40':40,'consumed-second-fresh32':32,'consumed-third-fresh40':40,'consumed-fourth-fresh40':40,'consumed-fifth-fresh40':40},
        'fresh_compound_indices':[i for i,r in enumerate(rows) if release.signed.route(r['formula'])['compound']],
        'named_failure_evaluation_only':{'panel':'consumed-fifth-fresh40','index':12,'cap':128},
        'chronology':'Policy/cohort before features or labels; zero-fit development seal; all40ordered predictions before fresh labels; independent lifecycle audits.',
        'scope':'Targeted synthetic isolated iCE40 LUT4 points. Development-informed uncalibrated decision heuristic; no universal hardware safety, timing, power, full-CPU or application-transfer guarantee.',
        'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(x):sha(x) for x in paths}}
    need(len(p['fresh_compound_indices'])==32,'Fresh32compound+8outside controls required')
    write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}


def freeze_policy(output):
    authenticate(output);need(not (output/'policy-freeze.json').exists(),'Policy already frozen')
    panels=retained_panels();write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'new_fits':0,
        'files_sha256':{n:sha(output/n) for n in ('development-predictions.json','development-metrics.json')}}
    write(output/'policy-freeze.json',seal);return seal


def load(output):
    authenticate(output);seal=read(output/'policy-freeze.json')
    need(seal['protocol_sha256']==sha(output/'protocol.json') and seal['new_fits']==0,'Zero-fit seal required')
    for name,digest in seal['files_sha256'].items():need(sha(output/name)==digest,'Sealed development artifact differs')
    return release.load(release.OUT)


def freeze_fresh(output):
    p=authenticate(output);fresh=ROOT/p['fresh'];need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Freeze fresh points before labels/attempts')
    rows=read(fresh/'candidates.json');models,routing,details=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')),load(output));dev=read(output/'development-metrics.json')
    saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'routes':routing,**details,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME}
    write(output/'fresh-predictions.json',saved)
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'policy_freeze_sha256':sha(output/'policy-freeze.json'),
        'predictions_sha256':sha(output/'fresh-predictions.json'),'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False,'new_fits':0}
    write(output/'fresh-point-freeze.json',seal)
    bindings={prior.relative(x):sha(x) for x in (output/'protocol.json',output/'policy-freeze.json',output/'fresh-point-freeze.json',output/'fresh-predictions.json',fresh/'features.json',fresh/'candidates.json')}
    write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':bindings});return seal


def score_values(saved,y,dev,compound_indices):
    row={'models':saved['models'],'actual_lut4':y};m=panel_metrics(row);compound=subset(row,compound_indices)
    changed=sum(a!=b for a,b in zip(saved['models'][NAME],saved['models'][BUDGET]))
    checks={'fresh_modified_prediction_count':changed,'fresh_repair_exercised':changed>=1,'strictly_better_signed':accuracy(m[CURRENT],m[NAME],True),'retained_style':m['checks'],'compound_subset_passes':passed(compound['checks']),
        'strictly_fewer_false_accept_cap_events_than_signed':sum(m[NAME]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(m[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),
        'outside_compound_exactly_release':all(saved['models'][NAME][i]==saved['models'][BUDGET][i] for i,r in enumerate(saved['routes']) if not r['compound'])}
    fresh_pass=checks['fresh_repair_exercised'] and all(checks['strictly_better_signed'].values()) and passed(checks['retained_style']) and checks['compound_subset_passes'] and checks['strictly_fewer_false_accept_cap_events_than_signed'] and checks['outside_compound_exactly_release']
    eligible=fresh_pass and dev['selected_candidate']==NAME
    return m,compound,{NAME:{'checks':checks,'fresh_gate_passed':fresh_pass,'development_gate_passed':dev['gates'][NAME]['development_gate_passed'],'eligible':eligible}},eligible


def score(output):
    p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('policy_freeze_sha256',output/'policy-freeze.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]:need(seal[key]==sha(path),'Sealed payload differs: '+key)
    rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Fresh alignment differs')
    m,compound,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),read(output/'development-metrics.json'),p['fresh_compound_indices'])
    result={'schema':SCHEMA,'models':m,'fresh_compound_subgroup':compound,'fresh_compound_count':len(p['fresh_compound_indices']),
        'gates':gates,'selected_candidate':saved['selected_candidate'],'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,
        'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),'fits':0,'native_jobs':0,'scope':p['scope']}
    write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
    p=authenticate(output);rows=read(candidates);models,routing,details=points(rows,prior.feature_matrix(rows,read(features)),load(output));dev=read(output/'development-metrics.json')
    result={'schema':SCHEMA,'model':NAME,'selected_candidate':dev['selected_candidate'],'development_eligible':dev['selected_candidate'] is not None,
        'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':models,'predicted_lut4':models[NAME],
        'routes':routing,**details,'fits':0,'native_jobs':0,'calibration_status':'uncalibrated','upper_lut4':None,'policy':POLICY,'scope':p['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,result);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}


def replay(output):
    p=authenticate(output);load(output);panels=retained_panels();need(panels==read(output/'development-predictions.json'),'Development replay differs')
    dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Development metric replay differs')
    fresh=ROOT/p['fresh'];rows=read(fresh/'candidates.json');models,routing,details=points(rows,prior.feature_matrix(rows,read(fresh/'features.json')));saved=read(output/'fresh-predictions.json')
    need(saved['models']==models and saved['routes']==routing and all(saved[k]==v for k,v in details.items()),'Fresh point replay differs');scored=False
    if (output/'fresh-metrics.json').exists():
        m,compound,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),dev,p['fresh_compound_indices']);result=read(output/'fresh-metrics.json')
        need(m==result['models'] and compound==result['fresh_compound_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Fresh metric replay differs');scored=True
    return {'status':'pass','development_rows':sum(len(r['actual_lut4']) for r in panels.values()),'fresh_rows':len(rows),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-policy','freeze-fresh','score','predict-cached','replay'))
    parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--fresh',type=Path,default=FRESH)
    parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if args.command=='prepare':result=prepare(out,args.fresh.resolve())
    elif args.command=='predict-cached':
        need(all((args.candidates,args.features,args.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,args.candidates,args.features,args.prediction_output)
    else:result={'freeze-policy':freeze_policy,'freeze-fresh':freeze_fresh,'score':score,'replay':replay}[args.command](out)
    print(json.dumps(result,indent=2))

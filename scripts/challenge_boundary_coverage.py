#!/usr/bin/env python3
"""Prospective, conditional activation challenge for the unchanged median rule.

Freeze a finite input-only pool and selection procedure before features. Log all
pool points, then select by prediction disagreement before any synthesis labels.
This is a conditional challenge, not representative population performance.
"""
from __future__ import annotations
import argparse
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import repair_boundary_coverage as boundary
prior=boundary.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-boundary-challenge-v1'
NAME,CURRENT,BUDGET,NAMES=boundary.NAME,boundary.CURRENT,boundary.BUDGET,boundary.NAMES
OUT=ROOT/'results/boundary-challenge'
FRESH=ROOT/'results/boundary-challenge-validation'
CAPS=boundary.CAPS
POLICY={'method':'Exactly the previously frozen boundary_median implementation; no new or changed weights, route, cap, median, tolerance, prediction or calibration rule.',
    'frozen_boundary_protocol_sha256':sha(boundary.OUT/'protocol.json'),
    'evidence_scope':'Complementary conditional activation challenge and separate unchanged broad40 panel. No pooled metric, representative-population claim, or relabeling of the earlier inactive trial as eligible.'}
SELECTION={'pool_count':200,'target_pool_count':192,'reserved_controls':8,'maximum_selected_active':16,
    'active':'boundary_median point differs exactly from budget_release_compound_only; frozen prediction outputs only, never labels.',
    'feature_freshness':'Exact217mapping-feature float64 equality against all1825training plus823consumed rows. Historical matches retained but excluded from active eligibility. Round-robin selects at most one active per within-pool217cluster, first occurrence under frozen ordering. All8controls fixed; any control historical match or duplicate among selected217keys blocks eligibility without replacement.',
    'ordering':'Group active noncontrol pool indices by template; sorted template names. Repeatedly take first remaining pool index from each template in that order until16 or queues exhausted, skipping active rows whose217key was already selected. Within-template order is original frozen pool order. Append all8 reserved controls in pool order.',
    'coverage':'At least4 selected active cases from at least2 templates; at least1 selected active case whose actual clamp point is128 and whose release point exceeds128.',
    'missing':'No quota filling, pool extension, replacements, retries, label-based selection or filtering. Retain every pool feature/point and every selected label, including failures; insufficient activity blocks eligibility.'}
GATES={'retained':'All ten complete consumed panels and prior named subgroups: MAE/MAPE/FA/maxunder no worse than release, FR no worse signed percap32/64/128; bounds signed<=repair<=release. Consumed125 failure remains repaired.',
    'broad40':'Separately retain the entire unchanged broad40 panel: strict MAE/MAPE and summed circuit-budget FA gains vs signed; FA<=release and FR<=signed separately percap; tail<=release and signed. Original broad40 trial remains ineligible due activity0; do not pool it with conditional selected data.',
    'conditional':'Selected complete challenge AND active-only subset: MAE/MAPE/FA/maxunder<=release, FR<=signed percap32/64/128, bounds signed<=repair<=release; no strict FA gain vs signed demanded for this prediction-conditioned population. Selection coverage and development gates required.',
    'tolerance':boundary.TOLERANCE,'postlabel':'No policy, route, weights, selection, threshold, cohort or criterion changes after labels. Failure remains ineligible.'}


def source_hashes():
    paths=[Path(__file__),ROOT/'tests/test_challenge_boundary_coverage.py',ROOT/'scripts/repair_boundary_coverage.py',ROOT/'tests/test_repair_boundary_coverage.py',ROOT/'scripts/release_budget_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    return {prior.relative(p):sha(p) for p in paths}


def historical_feature_paths():
    paths=[ROOT/'results/feature-comparison/inputs.npz',ROOT/'results/feature-comparison/columns.json']
    folders=['targeted-coverage-data','guarded-revision-data','signed-refinement-data','budget-release-data',*prior.PANELS,
        'targeted-coverage-validation','budget-preserving-validation','guarded-revision-validation','signed-refinement-validation','budget-release-validation','boundary-repair-validation']
    return paths+[ROOT/'results'/folder/'features.json' for folder in folders]


def feature_key(values):
    key=np.asarray(values,dtype='<f8').copy();key[key==0]=0.
    return hashlib.sha256(key.tobytes()).hexdigest()


def feature_freshness(x):
    columns=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as original:
        blocks=[original['x'][:,[columns.index(n) for n in prior.v6.mapping_columns()]]]
    for path in historical_feature_paths()[2:]:
        saved=read(path);positions=[saved['columns'].index(n) for n in prior.v6.mapping_columns()]
        blocks.append(np.asarray([row['values'] for row in saved['records']],dtype=float)[:,positions])
    history=np.vstack(blocks);need(history.shape==(2648,217),'Exact1825training+823consumed feature inventory required')
    known={tuple(float(v) for v in row) for row in history}
    selected=x[:,prior.v6.mapping_indices()]
    keys=[feature_key(row) for row in selected];clusters={};representatives=[]
    for i,row in enumerate(selected):
        key=tuple(float(v) for v in row);clusters.setdefault(key,[]).append(i);representatives.append(clusters[key][0])
    return {'historical_feature_row_count':len(history),'historical_unique217_count':len(known),
        'pool_feature_keys':keys,'pool_feature_cluster_representatives':representatives,'historical_match_pool_indices':[i for i,row in enumerate(selected) if tuple(float(v) for v in row) in known],
        'within_pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1],
        'equality':'Exact float64 numeric217mapping-feature tuples; Grouping uses exact numeric tuples; first pool indices identify exact clusters. SHA256keys normalize signed zero for inspection only. Labels unused.'}


def choose(pool,models,freshness):
    need(len(pool)==SELECTION['pool_count'],'Exact frozen200 pool required')
    controls=[i for i,r in enumerate(pool) if r['reserved_control']]
    need(len(controls)==8,'Exactly8 reserved controls required')
    keys=freshness['pool_feature_cluster_representatives'];historical=set(freshness['historical_match_pool_indices'])
    queues={};raw_active=[];eligible=[]
    for i,row in enumerate(pool):
        if row['reserved_control']:
            need(models[NAME][i]==models[BUDGET][i],'Reserved control must be inactive')
        elif models[NAME][i]!=models[BUDGET][i]:
            raw_active.append(i)
            if i not in historical:eligible.append(i);queues.setdefault(row['template'],[]).append(i)
    active=[];seen=set();skipped=[]
    while len(active)<16 and any(queues.values()):
        for template in sorted(queues):
            if len(active)>=16:break
            while queues[template] and keys[queues[template][0]] in seen:skipped.append(queues[template].pop(0))
            if queues[template] and len(active)<16:
                index=queues[template].pop(0);active.append(index);seen.add(keys[index])
    return {'raw_active_pool_indices':raw_active,'historical_collision_active_pool_indices':[i for i in raw_active if i in historical],
        'eligible_active_pool_indices':eligible,'selected_active_pool_indices':active,'skipped_duplicate_active_pool_indices':skipped,
        'reserved_control_pool_indices':controls,'selected_pool_indices':active+controls}


def coverage(pool,models,selection,freshness):
    active=selection['selected_active_pool_indices'];templates=sorted({pool[i]['template'] for i in active})
    caps={str(cap):sum(models[NAME][i]==cap<models[BUDGET][i] for i in active) for cap in CAPS}
    keys=freshness['pool_feature_cluster_representatives'];historical=set(freshness['historical_match_pool_indices']);selected=selection['selected_pool_indices']
    checks={'reserved_controls_feature_novel':not bool(historical&set(selection['reserved_control_pool_indices'])),'selected_feature_keys_unique':len({keys[i] for i in selected})==len(selected),
        'at_least_four_active':len(active)>=4,'at_least_two_active_templates':len(templates)>=2,'at_least_one_cap128_clamp':caps['128']>=1}
    return {'pool_count':len(pool),'raw_active_count':len(selection['raw_active_pool_indices']),'eligible_active_count':len(selection['eligible_active_pool_indices']),
        'eligible_unique_active_count':len({keys[i] for i in selection['eligible_active_pool_indices']}),
        'selected_active_count':len(active),'selected_control_count':len(selection['reserved_control_pool_indices']),
        'selected_total_count':len(selection['selected_pool_indices']),'selected_active_templates':templates,
        'selected_active_clamp_caps':caps,'checks':checks,'passed':all(checks.values())}


def panel_inputs():
    yield from boundary.panel_inputs()
    rows=read(boundary.FRESH/'candidates.json')
    yield 'consumed-sixth-broad40',(rows,prior.feature_matrix(rows,read(boundary.FRESH/'features.json')),prior.labels_for(rows,read(boundary.FRESH/'labels.json')))


def retained_panels():
    model=boundary.release.load(boundary.release.OUT);panels={}
    for name,(rows,x,y) in panel_inputs():
        models,routes,details=boundary.points(rows,x,model)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':y,'models':models,'routes':routes,**details}
    return panels


def development_metrics(panels):
    metrics={name:boundary.panel_metrics(row) for name,row in panels.items()}
    older={name:row for name,row in panels.items() if name!='consumed-sixth-broad40'}
    old=boundary.development_metrics(older);named=old['named_regressions']
    rows=read(boundary.FRESH/'candidates.json');indices=[i for i,r in enumerate(rows) if boundary.release.signed.route(r['formula'])['compound']]
    need(len(indices)==32,'Exact broad32 compound subset required')
    named['broad_compound32']=boundary.subset(panels['consumed-sixth-broad40'],indices)
    broad=metrics['consumed-sixth-broad40']
    broad_checks={'strictly_better_signed':boundary.accuracy(broad[CURRENT],broad[NAME],True),
        'retained_style':broad['checks'],
        'strictly_fewer_false_accept_cap_events_than_signed':sum(broad[NAME]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(broad[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS)}
    broad_pass=all(broad_checks['strictly_better_signed'].values()) and boundary.passed(broad['checks']) and broad_checks['strictly_fewer_false_accept_cap_events_than_signed']
    gates={'all_ten_retained_panels_pass':all(boundary.passed(m['checks']) for m in metrics.values()),
        'all_prior_named_subgroups_preserved':all(boundary.passed(m['checks']) for m in named.values()),
        'named_failure_repaired':old['named_failure']['repaired_at_cap128'],'separate_broad40_metric_criteria_pass':broad_pass}
    gates['development_gate_passed']=all(gates.values())
    return {'panels':metrics,'named_regressions':named,'named_failure':old['named_failure'],
        'separate_broad40_checks':broad_checks,'prior_broad_trial_scoped_experimental_eligibility':read(boundary.OUT/'fresh-metrics.json')['scoped_experimental_eligibility'],
        'gates':{NAME:gates},'selected_candidate':NAME if gates['development_gate_passed'] else None,'evaluated_candidate':NAME,
        'all_panels_consumed':True,'independent_test':False,'no_pooled_metric':True}


def authenticate(output):
    p=read(output/'protocol.json')
    need(p['schema']==SCHEMA and p['policy']==POLICY and p['selection']==SELECTION and p['gates']==GATES,'Frozen challenge protocol differs')
    need(p['sources_sha256']==source_hashes(),'Frozen challenge source differs')
    for path,digest in p['inputs_sha256'].items():need(sha(ROOT/path)==digest,'Frozen input differs: '+path)
    boundary.load(boundary.OUT);return p


def prepare(output,fresh):
    need(not (output/'protocol.json').exists(),'Protocol already frozen')
    for name in ('pool-features.json','features.json','labels.json','feature-attempt.json','label-attempt.json','selection.json'):
        need(not (fresh/name).exists(),'Freeze before features, selection and labels: '+name)
    pool=read(fresh/'pool-candidates.json');need(len(pool)==200,'Exact200pool required');need(read(fresh/'novelty.json')['status']=='pass','Pool novelty failed')
    need(sum(r['reserved_control'] for r in pool)==8,'Exactly8 controls')
    goal=ROOT/'results/boundary-repair-goal.json';write(output/'goal-at-freeze.json',read(goal))
    paths=[output/'goal-at-freeze.json']+[boundary.OUT/n for n in ('protocol.json','policy-freeze.json','development-predictions.json','development-metrics.json','fresh-point-freeze.json','fresh-predictions.json','fresh-metrics.json')]
    paths += [boundary.FRESH/n for n in ('candidates.json','features.json','labels.json','plan.json')]
    paths += [fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
    paths += historical_feature_paths()
    p={'schema':SCHEMA,'frozen_at_utc':now(),'fresh':prior.relative(fresh),'policy':POLICY,'selection':SELECTION,'gates':GATES,
        'finite_candidates':[NAME],'planned_fits':0,'maximum_fits':0,'new_training_rows':0,'native_jobs':0,'native_threads':1,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),
        'retained_panels':{**read(boundary.OUT/'protocol.json')['retained_panels'],'consumed-sixth-broad40':40},
        'reserved_control_pool_indices':[i for i,r in enumerate(pool) if r['reserved_control']],
        'goal_source_sha256':sha(goal),'chronology':'Pool, unchanged rule, selection and gates before all pool features; retain all ordered pool points; deterministic selection and all selected points before any labels; independent lifecycle receipts.',
        'scope':'Prospective conditional activation challenge selected using frozen model disagreement; not representative unconditioned fresh performance. Separate broad40 metric evidence, no pooling. Uncalibrated isolated iCE40 LUT4 point heuristic.',
        'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(x):sha(x) for x in paths}}
    write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}


def freeze_policy(output):
    authenticate(output);need(not (output/'policy-freeze.json').exists(),'Policy seal already exists')
    panels=retained_panels();write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'new_fits':0,
        'files_sha256':{name:sha(output/name) for name in ('development-predictions.json','development-metrics.json')}}
    write(output/'policy-freeze.json',seal);return seal


def load(output):
    authenticate(output);seal=read(output/'policy-freeze.json')
    need(seal['protocol_sha256']==sha(output/'protocol.json') and seal['new_fits']==0,'Zero-fit challenge seal required')
    for name,digest in seal['files_sha256'].items():need(sha(output/name)==digest,'Sealed challenge artifact differs')
    return boundary.load(boundary.OUT)


def frozen_subset(saved,indices):
    return {'candidate_ids':[saved['candidate_ids'][i] for i in indices],'formulas':[saved['formulas'][i] for i in indices],
        'models':{n:[saved['models'][n][i] for i in indices] for n in NAMES},'routes':[saved['routes'][i] for i in indices],
        'forest_medians_lut4':[saved['forest_medians_lut4'][i] for i in indices],
        'qualifying_caps_lut4':[saved['qualifying_caps_lut4'][i] for i in indices],
        'tree_predictions_above_cap':{c:[v[i] for i in indices] for c,v in saved['tree_predictions_above_cap'].items()}}


def freeze_selection(output):
    p=authenticate(output);fresh=ROOT/p['fresh']
    for name in ('labels.json','label-attempt.json','selection.json'):need(not (fresh/name).exists(),'Selection must precede labels and be single attempt')
    pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');models,routes,details=boundary.points(pool,prior.feature_matrix(pool,features),load(output));dev=read(output/'development-metrics.json')
    saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in pool],'formulas':[r['formula'] for r in pool],
        'models':models,'routes':routes,**details,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME}
    write(output/'pool-predictions.json',saved)
    freshness=feature_freshness(prior.feature_matrix(pool,features));write(output/'pool-feature-freshness.json',freshness)
    selection=choose(pool,models,freshness);selection_coverage=coverage(pool,models,selection,freshness)
    selected=selection['selected_pool_indices'];selection_payload={'schema':SCHEMA,'frozen_at_utc':now(),**selection,'coverage':selection_coverage,
        'protocol_sha256':sha(output/'protocol.json'),'pool_candidates_sha256':sha(fresh/'pool-candidates.json'),
        'pool_features_sha256':sha(fresh/'pool-features.json'),'pool_feature_freshness_sha256':sha(output/'pool-feature-freshness.json'),'pool_predictions_sha256':sha(output/'pool-predictions.json'),'labels_present':False}
    write(fresh/'selection.json',selection_payload);write(fresh/'candidates.json',[pool[i] for i in selected])
    write(fresh/'features.json',{'columns':features['columns'],'records':[features['records'][i] for i in selected]})
    points={'schema':SCHEMA,'created_at_utc':now(),**frozen_subset(saved,selected),'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME,'selection_coverage':selection_coverage,
        'active_selected_indices':list(range(len(selection['selected_active_pool_indices'])))}
    write(output/'fresh-predictions.json',points)
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'policy_freeze_sha256':sha(output/'policy-freeze.json'),
        'pool_feature_freshness_sha256':sha(output/'pool-feature-freshness.json'),'pool_predictions_sha256':sha(output/'pool-predictions.json'),'pool_features_sha256':sha(fresh/'pool-features.json'),'pool_candidates_sha256':sha(fresh/'pool-candidates.json'),
        'selection_sha256':sha(fresh/'selection.json'),'predictions_sha256':sha(output/'fresh-predictions.json'),
        'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False,'new_fits':0}
    write(output/'fresh-point-freeze.json',seal)
    paths=[output/n for n in ('protocol.json','policy-freeze.json','pool-predictions.json','pool-feature-freshness.json','fresh-predictions.json','fresh-point-freeze.json')]
    paths += [fresh/n for n in ('pool-candidates.json','pool-features.json','selection.json','candidates.json','features.json')]
    write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':{prior.relative(x):sha(x) for x in paths}})
    return {'point_freeze':seal,'selection_coverage':selection_coverage,'new_fits':0}


def score_values(saved,y,dev):
    row={'models':saved['models'],'actual_lut4':y};m=boundary.panel_metrics(row);active_indices=saved['active_selected_indices']
    active=boundary.subset(row,active_indices) if active_indices else None
    checks={'selection_coverage':saved['selection_coverage'],'selected_complete_passes':boundary.passed(m['checks']),
        'active_subset_passes':bool(active and boundary.passed(active['checks'])),
        'separate_broad40_metric_criteria_pass':dev['gates'][NAME]['separate_broad40_metric_criteria_pass'],
        'reserved_controls_exactly_release':all(saved['models'][NAME][i]==saved['models'][BUDGET][i] for i in range(len(y)) if i not in active_indices)}
    passed=checks['selection_coverage']['passed'] and checks['selected_complete_passes'] and checks['active_subset_passes'] and checks['separate_broad40_metric_criteria_pass'] and checks['reserved_controls_exactly_release']
    eligible=passed and dev['selected_candidate']==NAME
    gates={NAME:{'checks':checks,'fresh_gate_passed':passed,'development_gate_passed':dev['gates'][NAME]['development_gate_passed'],'eligible':eligible}}
    return m,active,gates,eligible


def check_point_seal(output):
    p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
    pairs=[('protocol_sha256',output/'protocol.json'),('policy_freeze_sha256',output/'policy-freeze.json'),('pool_feature_freshness_sha256',output/'pool-feature-freshness.json'),('pool_predictions_sha256',output/'pool-predictions.json'),('pool_features_sha256',fresh/'pool-features.json'),('pool_candidates_sha256',fresh/'pool-candidates.json'),('selection_sha256',fresh/'selection.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]
    for key,path in pairs:need(seal[key]==sha(path),'Sealed challenge payload differs: '+key)
    return p,fresh


def score(output):
    p,fresh=check_point_seal(output);rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json')
    need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Selected alignment differs')
    m,active,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),read(output/'development-metrics.json'))
    result={'schema':SCHEMA,'models':m,'active_subgroup':active,'selection_coverage':saved['selection_coverage'],'gates':gates,
        'selected_candidate':saved['selected_candidate'],'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,
        'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),
        'fits':0,'native_jobs':0,'scope':p['scope'],'no_pooled_metric':True}
    write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
    p=authenticate(output);rows=read(candidates);models,routes,details=boundary.points(rows,prior.feature_matrix(rows,read(features)),load(output));dev=read(output/'development-metrics.json')
    value={'schema':SCHEMA,'model':NAME,'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'predicted_lut4':models[NAME],'routes':routes,**details,'selected_candidate':dev['selected_candidate'],
        'fits':0,'native_jobs':0,'calibration_status':'uncalibrated','upper_lut4':None,'scope':p['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,value);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}


def replay(output):
    p,fresh=check_point_seal(output);panels=retained_panels();need(panels==read(output/'development-predictions.json'),'Challenge development replay differs')
    dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Challenge development metrics differ')
    pool=read(fresh/'pool-candidates.json');models,routes,details=boundary.points(pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')),load(output));saved=read(output/'pool-predictions.json')
    need(models==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'All-pool point replay differs')
    freshness=feature_freshness(prior.feature_matrix(pool,read(fresh/'pool-features.json')));need(freshness==read(output/'pool-feature-freshness.json'),'Feature freshness replay differs')
    selection=choose(pool,models,freshness);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,models,selection,freshness),'Selection replay differs')
    selected=selection['selected_pool_indices'];points=read(output/'fresh-predictions.json');need(all(points[k]==v for k,v in frozen_subset(saved,selected).items()),'Selected point replay differs')
    need(read(fresh/'candidates.json')==[pool[i] for i in selected],'Selected candidates differ')
    features=read(fresh/'pool-features.json');need(read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in selected]},'Selected features differ')
    scored=False
    if (output/'fresh-metrics.json').exists():
        rows=read(fresh/'candidates.json');m,active,gates,eligible=score_values(points,prior.labels_for(rows,read(fresh/'labels.json')),dev);result=read(output/'fresh-metrics.json')
        need(m==result['models'] and active==result['active_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Challenge fresh metric replay differs');scored=True
    return {'status':'pass','development_rows':sum(len(r['actual_lut4']) for r in panels.values()),'pool_rows':len(pool),'selected_rows':len(selected),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-policy','freeze-selection','score','predict-cached','replay'))
    parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--fresh',type=Path,default=FRESH)
    parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if args.command=='prepare':result=prepare(out,args.fresh.resolve())
    elif args.command=='predict-cached':
        need(all((args.candidates,args.features,args.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,args.candidates,args.features,args.prediction_output)
    else:result={'freeze-policy':freeze_policy,'freeze-selection':freeze_selection,'score':score,'replay':replay}[args.command](out)
    print(json.dumps(result,indent=2))

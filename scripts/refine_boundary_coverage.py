#!/usr/bin/env python3
"""One development-informed structural gate; prospective general and active panels.

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
import challenge_boundary_coverage as previous
boundary=previous.boundary
prior=boundary.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-boundary-refinement-v1'
NAME='boundary_structural'
BROAD=boundary.NAME
CURRENT,BUDGET=boundary.CURRENT,boundary.BUDGET
NAMES=(*boundary.NAMES,NAME)
OUT=ROOT/'results/boundary-refinement'
FRESH=ROOT/'results/boundary-refinement-validation'
CAPS=boundary.CAPS
POLICY={'method':'Apply the unchanged even300-tree median cap adjudication only on a new original-dataflow structural gate; release elsewhere. No fits or weight changes.',
    'structural_gate':'Original root is xor; either xor operand is add; either operand of that SAME add is a DIRECT sra with input-bearing shift operand and both addi and xori in its OWN data subtree. No constants, IDs, labels, normalization or case lookup. Test both commutative operand positions.',
    'median':'Exactly the frozen boundary_median prediction on gated formulas, including numpy even median average at sorted positions149/150 and smallest qualifying cap32/64/128. Else frozen budget_release_compound_only exactly.',
    'framing':'Development-informed AST/dataflow hypothesis, not an established synthesis mechanism or calibrated uncertainty. Earlier negative receipts remain failed.'}
SELECTION={'pool_count':128,'general_count':32,'general_controls':8,'challenge_pool_count':96,'maximum_selected_active':16,
    'active':'Only challenge-cohort rows whose boundary_structural point differs exactly from release; no labels.',
    'feature_freshness':'Exact217 float64 tuples against2866 historical rows:1825 fitted +841 consumed evaluation +all200 prior challenge pool rows (18 labelled overlaps,182 previously unlabelled). All retained. General32 historical/intra-general duplicates block eligibility. Challenge historical matches and keys shared with general32 excluded; round-robin keeps one active per remaining cluster. No replacements.',
    'ordering':'All general32 retained in frozen pool order. Eligible active challenge rows grouped by sorted template name; round-robin first remaining original pool index, skipping already selected217 keys; stop immediately at16 or exhaustion. Append actives after general32 for unique labels.',
    'conditional_full':'Selected actives plus the SAME8 fixed excluded-root general controls; shared controls explicitly disclosed, no pooling or independence claim. Active-only separately gated.',
    'coverage':'At least4 selected feature-novel actives across at least2 templates; at least1 actual cap128 clamp.',
    'missing':'All128 features and points retained; general32 and every selected active labelled. No extensions, filling, replacements, retries or postlabel filtering.'}
GATES={'retained':'All eleven consumed panels841rows and named subgroups: MAE/MAPE/FA/tail<=release, FR<=signed separately percap32/64/128, signed<=point<=release. Preserve original125 repair, all8 latest correctedFR and both latest correct rejections.',
    'general':'Complete fixed general32: MAE and MAPE strictly<signed AND <=release; FA<=release and FR<=signed separately percap; summed FA circuit-budget events strictly<signed; maxunder<=release and signed. General32 feature-novel/unique; no selection/filtering.',
    'conditional':'Selected active-only AND conditional-full(active+8shared general controls): MAE/MAPE/FA/tail<=release, FR<=signed percap32/64/128, signed<=point<=release. Prospective coverage>=4active/2templates/cap128. No strict conditional FA gain vs signed demanded.',
    'tolerance':boundary.TOLERANCE,'postlabel':'No policy, weight, route, cohort, selection, gate or threshold changes after labels; no pooled success metric.'}


def source_hashes():
    paths=[Path(__file__),ROOT/'tests/test_refine_boundary_coverage.py',ROOT/'scripts/challenge_boundary_coverage.py',ROOT/'scripts/repair_boundary_coverage.py',ROOT/'tests/test_repair_boundary_coverage.py',ROOT/'scripts/release_budget_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    return {prior.relative(p):sha(p) for p in paths}


def structural_route(formula):
    walk=prior.walk
    def compound(node):
        return node.value=='sra' and any(n.value in ('in0','in1') for n in walk(node.children[1])) and {'addi','xori'}<={n.value for n in walk(node.children[0])}
    root=prior.parse_formula(formula)
    return root.value=='xor' and any(child.value=='add' and any(compound(operand) for operand in child.children) for child in root.children)


def points(rows,x,model=None):
    models,routes,details=boundary.points(rows,x,model)
    scope=[structural_route(row['formula']) for row in rows]
    models[NAME]=np.where(scope,models[BROAD],models[BUDGET]).tolist()
    return models,routes,{**details,'structural_scope':scope,'applied_qualifying_caps_lut4':[caps if active else [] for caps,active in zip(details['qualifying_caps_lut4'],scope)]}


def panel_metrics(row):
    metrics={n:prior.model_metrics(row['models'][n],row['actual_lut4']) for n in NAMES}
    bridge={n:row['models'][n] for n in boundary.NAMES};bridge[BROAD]=row['models'][NAME]
    metrics['checks']=boundary.panel_metrics({'models':bridge,'actual_lut4':row['actual_lut4']})['checks']
    return metrics


def subset(row,indices):
    need(bool(indices),'Required subgroup empty')
    return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
        'models':{n:[row['models'][n][i] for i in indices] for n in NAMES}})


def template_group(row,folder,template):
    indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template]
    need(len(indices)==4,'Named subgroup must have4cases')
    return subset(row,indices)


def historical_feature_paths():
    return previous.historical_feature_paths()+[previous.FRESH/'features.json',previous.FRESH/'pool-features.json']


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
    history=np.vstack(blocks);need(history.shape==(2866,217),'Exact1825training+841evaluation+200priorpool feature rows required')
    known={tuple(float(v) for v in row) for row in history}
    selected=x[:,prior.v6.mapping_indices()]
    keys=[feature_key(row) for row in selected];clusters={};representatives=[]
    for i,row in enumerate(selected):
        key=tuple(float(v) for v in row);clusters.setdefault(key,[]).append(i);representatives.append(clusters[key][0])
    return {'historical_components':{'fitted_rows':1825,'consumed_evaluation_rows':841,'prior_pool_rows':200,'prior_pool_labelled_overlap':18,'prior_pool_previously_unlabelled':182},'historical_feature_row_count':len(history),'historical_unique217_count':len(known),
        'pool_feature_keys':keys,'pool_feature_cluster_representatives':representatives,'historical_match_pool_indices':[i for i,row in enumerate(selected) if tuple(float(v) for v in row) in known],
        'within_pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1],
        'equality':'Exact float64 numeric217mapping-feature tuples; Grouping uses exact numeric tuples; first pool indices identify exact clusters. SHA256keys normalize signed zero for inspection only. Labels unused.'}


def choose(pool,models,freshness):
    need(len(pool)==128,'Exact128pool required')
    general=[i for i,r in enumerate(pool) if r['cohort']=='general'];controls=[i for i,r in enumerate(pool) if r['reserved_control']]
    need(len(general)==32 and len(controls)==8 and set(controls)<=set(general),'Fixed32general/8sharedcontrols required')
    keys=freshness['pool_feature_cluster_representatives'];history=set(freshness['historical_match_pool_indices'])
    general_keys={keys[i] for i in general};queues={};raw=[];eligible=[];general_collisions=[]
    for i,row in enumerate(pool):
        if row['cohort']!='challenge':continue
        if models[NAME][i]!=models[BUDGET][i]:
            raw.append(i)
            if keys[i] in general_keys:general_collisions.append(i)
            elif i not in history:eligible.append(i);queues.setdefault(row['template'],[]).append(i)
    active=[];seen=set(general_keys);skipped=[]
    while len(active)<16 and any(queues.values()):
        for template in sorted(queues):
            if len(active)>=16:break
            while queues[template] and keys[queues[template][0]] in seen:skipped.append(queues[template].pop(0))
            if queues[template]:
                index=queues[template].pop(0);active.append(index);seen.add(keys[index])
    return {'general_pool_indices':general,'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,
        'historical_collision_active_pool_indices':[i for i in raw if i in history],
        'general_feature_collision_active_pool_indices':general_collisions,'eligible_active_pool_indices':eligible,
        'selected_active_pool_indices':active,'skipped_duplicate_active_pool_indices':skipped,'selected_pool_indices':general+active}


def coverage(pool,models,selection,freshness):
    active=selection['selected_active_pool_indices'];general=selection['general_pool_indices'];selected=selection['selected_pool_indices']
    keys=freshness['pool_feature_cluster_representatives'];history=set(freshness['historical_match_pool_indices'])
    templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(models[NAME][i]==c<models[BUDGET][i] for i in active) for c in CAPS}
    checks={'general_feature_novel':not bool(history&set(general)),'general_feature_keys_unique':len({keys[i] for i in general})==32,
        'selected_feature_keys_unique':len({keys[i] for i in selected})==len(selected),
        'at_least_four_active':len(active)>=4,'at_least_two_active_templates':len(templates)>=2,'at_least_one_cap128_clamp':caps['128']>=1}
    return {'pool_count':len(pool),'general_count':32,'conditional_shared_control_count':8,'raw_active_count':len(selection['raw_active_pool_indices']),
        'eligible_active_count':len(selection['eligible_active_pool_indices']),'eligible_unique_active_count':len({keys[i] for i in selection['eligible_active_pool_indices']}),
        'selected_active_count':len(active),'selected_unique_label_count':len(selected),'conditional_full_count':len(active)+8,
        'selected_active_templates':templates,'selected_active_clamp_caps':caps,'checks':checks,'passed':all(checks.values())}


def panel_inputs():
    yield from previous.panel_inputs()
    rows=read(previous.FRESH/'candidates.json')
    yield 'consumed-seventh-conditional18',(rows,prior.feature_matrix(rows,read(previous.FRESH/'features.json')),prior.labels_for(rows,read(previous.FRESH/'labels.json')))


def retained_panels():
    model=boundary.release.load(boundary.release.OUT);panels={}
    for name,(rows,x,y) in panel_inputs():
        models,routes,details=points(rows,x,model)
        panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],
            'actual_lut4':y,'models':models,'routes':routes,**details}
    return panels


def development_metrics(panels):
    metrics={name:panel_metrics(row) for name,row in panels.items()}
    named={'arithmetic_stress32':metrics['arithmetic-stress'],
        'signed_dual_arithmetic4':template_group(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic'),
        'signed_add_boolean4':template_group(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
        'compound_signed_add_xor4':template_group(panels['consumed-fourth-fresh40'],boundary.release.signed.FRESH,'heldout_compound_signed_add_xor'),
        'fifth_compound_signed_add_xor4':template_group(panels['consumed-fifth-fresh40'],boundary.release.FRESH,'heldout_compound_signed_add_xor'),
        'fifth_compound_signed_xordata_addxor4':template_group(panels['consumed-fifth-fresh40'],boundary.release.FRESH,'heldout_compound_signed_xordata_addxor')}
    broad_rows=read(boundary.FRESH/'candidates.json');broad_indices=[i for i,row in enumerate(broad_rows) if boundary.release.signed.route(row['formula'])['compound']]
    need(len(broad_indices)==32,'Exact consumed broad compound32 required');named['broad_compound32']=subset(panels['consumed-sixth-broad40'],broad_indices)
    original=panels['consumed-fifth-fresh40'];latest=panels['consumed-seventh-conditional18']
    original_ok=original['actual_lut4'][12]==125 and original['models'][NAME][12]<=128
    fr_indices=[i for i,y in enumerate(latest['actual_lut4']) if y<=128<latest['models'][BUDGET][i]]
    need(len(fr_indices)==8,'Exact8 consumed false rejections required')
    fa_indices=[i for i,y in enumerate(latest['actual_lut4']) if any(latest['models'][BROAD][i]<=cap<latest['models'][BUDGET][i] and y>cap for cap in CAPS)]
    need(len(fa_indices)==2,'Exact2 prior false acceptances required')
    named['eight_corrected_fr']=subset(latest,fr_indices);named['two_previous_new_fa']=subset(latest,fa_indices)
    failure_checks={'original125_repaired':original_ok,'all_eight_fr_retained':all(latest['models'][NAME][i]<=128 for i in fr_indices),
        'both_previous_new_fa_rejected':all(latest['models'][NAME][i]>cap for i in fa_indices for cap in CAPS if latest['models'][BROAD][i]<=cap<latest['models'][BUDGET][i] and latest['actual_lut4'][i]>cap)}
    outside=all(row['models'][NAME][i]==row['models'][BUDGET][i] for row in panels.values() for i,active in enumerate(row['structural_scope']) if not active)
    gates={'all_eleven_retained_panels_pass':all(boundary.passed(m['checks']) for m in metrics.values()),
        'all_named_subgroups_preserved':all(boundary.passed(m['checks']) for m in named.values()),'all_named_decision_repairs_preserved':all(failure_checks.values()),'outside_structural_gate_exact_release':outside}
    gates['development_gate_passed']=all(gates.values())
    return {'panels':metrics,'named_regressions':named,'named_decision_checks':failure_checks,'gates':{NAME:gates},
        'selected_candidate':NAME if gates['development_gate_passed'] else None,'evaluated_candidate':NAME,'all_panels_consumed':True,'independent_test':False,'no_pooled_metric':True}


def authenticate(output):
    p=read(output/'protocol.json')
    need(p['schema']==SCHEMA and p['policy']==POLICY and p['selection']==SELECTION and p['gates']==GATES,'Frozen challenge protocol differs')
    need(p['sources_sha256']==source_hashes(),'Frozen challenge source differs')
    for path,digest in p['inputs_sha256'].items():need(sha(ROOT/path)==digest,'Frozen input differs: '+path)
    previous.load(previous.OUT);return p


def prepare(output,fresh):
    need(not (output/'protocol.json').exists(),'Protocol already frozen')
    for name in ('pool-features.json','features.json','labels.json','feature-attempt.json','label-attempt.json','selection.json'):
        need(not (fresh/name).exists(),'Freeze before features, selection and labels: '+name)
    pool=read(fresh/'pool-candidates.json');need(len(pool)==128,'Exact128pool required');need(read(fresh/'novelty.json')['status']=='pass','Pool novelty failed')
    need(sum(r['reserved_control'] for r in pool)==8 and sum(r['cohort']=='general' for r in pool)==32,'Fixed32general/8controls required')
    goal=ROOT/'results/boundary-repair-goal.json';write(output/'goal-at-freeze.json',read(goal))
    paths=[output/'goal-at-freeze.json']+[previous.OUT/n for n in ('protocol.json','policy-freeze.json','development-predictions.json','development-metrics.json','fresh-point-freeze.json','fresh-predictions.json','fresh-metrics.json')]
    paths += [previous.FRESH/n for n in ('pool-candidates.json','pool-features.json','candidates.json','features.json','labels.json','plan.json')]
    paths += [fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
    paths += historical_feature_paths()
    p={'schema':SCHEMA,'frozen_at_utc':now(),'fresh':prior.relative(fresh),'policy':POLICY,'selection':SELECTION,'gates':GATES,
        'finite_candidates':[NAME],'planned_fits':0,'maximum_fits':0,'new_training_rows':0,'native_jobs':0,'native_threads':1,
        'feature_columns':list(prior.v6.columns()),'selected_columns':list(prior.v6.mapping_columns()),
        'retained_panels':{**read(previous.OUT/'protocol.json')['retained_panels'],'consumed-seventh-conditional18':18},
        'reserved_control_pool_indices':[i for i,r in enumerate(pool) if r['reserved_control']],'general_pool_indices':[i for i,r in enumerate(pool) if r['cohort']=='general'],
        'goal_source_sha256':sha(goal),'chronology':'Pool, single new structural gate over unchanged median weights, selection and gates before all pool features; retain all ordered pool points; deterministic selection and all selected points before any labels; independent lifecycle receipts.',
        'scope':'Fixed general32 plus separate prospective conditional activation challenge;8 controls explicitly shared, no pooled metrics or independence claim. Development-informed uncalibrated structural isolated iCE40 LUT4 heuristic; no universal safety, timing, power, CPU or application-transfer guarantee.',
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
    return previous.load(previous.OUT)


def frozen_subset(saved,indices):
    return {'candidate_ids':[saved['candidate_ids'][i] for i in indices],'formulas':[saved['formulas'][i] for i in indices],
        'models':{n:[saved['models'][n][i] for i in indices] for n in NAMES},'routes':[saved['routes'][i] for i in indices],
        'forest_medians_lut4':[saved['forest_medians_lut4'][i] for i in indices],
        'qualifying_caps_lut4':[saved['qualifying_caps_lut4'][i] for i in indices],
        'tree_predictions_above_cap':{c:[v[i] for i in indices] for c,v in saved['tree_predictions_above_cap'].items()},'structural_scope':[saved['structural_scope'][i] for i in indices],'applied_qualifying_caps_lut4':[saved['applied_qualifying_caps_lut4'][i] for i in indices]}


def freeze_selection(output):
    p=authenticate(output);fresh=ROOT/p['fresh']
    for name in ('labels.json','label-attempt.json','selection.json'):need(not (fresh/name).exists(),'Selection must precede labels and be single attempt')
    pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');models,routes,details=points(pool,prior.feature_matrix(pool,features),load(output));dev=read(output/'development-metrics.json')
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
    selected_points={'schema':SCHEMA,'created_at_utc':now(),**frozen_subset(saved,selected),'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME,'selection_coverage':selection_coverage,
        'active_selected_indices':list(range(32,len(selected))),'general_selected_indices':list(range(32)),
        'conditional_selected_indices':list(range(32,len(selected)))+[selected.index(i) for i in selection['reserved_control_pool_indices']],
        'shared_control_selected_indices':[selected.index(i) for i in selection['reserved_control_pool_indices']],'shared_control_count':8}
    write(output/'fresh-predictions.json',selected_points)
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
    row={'models':saved['models'],'actual_lut4':y};general=subset(row,saved['general_selected_indices'])
    active=subset(row,saved['active_selected_indices']) if saved['active_selected_indices'] else None
    conditional=subset(row,saved['conditional_selected_indices'])
    general_checks={'retained_style':general['checks'],'strictly_better_signed':boundary.accuracy(general[CURRENT],general[NAME],True),
        'strictly_fewer_false_accept_cap_events_than_signed':sum(general[NAME]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS)}
    general_pass=boundary.passed(general['checks']) and all(general_checks['strictly_better_signed'].values()) and general_checks['strictly_fewer_false_accept_cap_events_than_signed']
    checks={'selection_coverage':saved['selection_coverage'],'general':general_checks,'general_passes':general_pass,
        'conditional_full_passes':boundary.passed(conditional['checks']),'active_subset_passes':bool(active and boundary.passed(active['checks'])),
        'outside_structural_gate_exact_release':all(saved['models'][NAME][i]==saved['models'][BUDGET][i] for i,scope in enumerate(saved['structural_scope']) if not scope)}
    passed=checks['selection_coverage']['passed'] and general_pass and checks['conditional_full_passes'] and checks['active_subset_passes'] and checks['outside_structural_gate_exact_release']
    eligible=passed and dev['selected_candidate']==NAME
    return general,conditional,active,{NAME:{'checks':checks,'fresh_gate_passed':passed,'development_gate_passed':dev['gates'][NAME]['development_gate_passed'],'eligible':eligible}},eligible


def check_point_seal(output):
    p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
    pairs=[('protocol_sha256',output/'protocol.json'),('policy_freeze_sha256',output/'policy-freeze.json'),('pool_feature_freshness_sha256',output/'pool-feature-freshness.json'),('pool_predictions_sha256',output/'pool-predictions.json'),('pool_features_sha256',fresh/'pool-features.json'),('pool_candidates_sha256',fresh/'pool-candidates.json'),('selection_sha256',fresh/'selection.json'),('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),('candidates_sha256',fresh/'candidates.json')]
    for key,path in pairs:need(seal[key]==sha(path),'Sealed challenge payload differs: '+key)
    return p,fresh


def score(output):
    p,fresh=check_point_seal(output);rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json')
    need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows],'Selected alignment differs')
    m,conditional,active,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),read(output/'development-metrics.json'))
    result={'schema':SCHEMA,'models':m,'conditional_models':conditional,'active_subgroup':active,'selection_coverage':saved['selection_coverage'],'gates':gates,
        'general_count':len(saved['general_selected_indices']),'conditional_count':len(saved['conditional_selected_indices']),'active_count':len(saved['active_selected_indices']),'shared_control_count':8,'unique_label_count':len(rows),
        'selected_candidate':saved['selected_candidate'],'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,
        'fresh_labels_sha256':sha(fresh/'labels.json'),'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),
        'fits':0,'native_jobs':0,'scope':p['scope'],'no_pooled_metric':True}
    write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
    p=authenticate(output);rows=read(candidates);models,routes,details=points(rows,prior.feature_matrix(rows,read(features)),load(output));dev=read(output/'development-metrics.json')
    value={'schema':SCHEMA,'model':NAME,'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],
        'models':models,'predicted_lut4':models[NAME],'routes':routes,**details,'selected_candidate':dev['selected_candidate'],
        'fits':0,'native_jobs':0,'calibration_status':'uncalibrated','upper_lut4':None,'scope':p['scope'],
        'features_sha256':sha(features),'candidates_sha256':sha(candidates),'protocol_sha256':sha(output/'protocol.json')}
    write(destination,value);return {'predictions':len(rows),'output':str(destination),'new_fits':0,'native_jobs':0}


def replay(output):
    p,fresh=check_point_seal(output);panels=retained_panels();need(panels==read(output/'development-predictions.json'),'Challenge development replay differs')
    dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Challenge development metrics differ')
    pool=read(fresh/'pool-candidates.json');models,routes,details=points(pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')),load(output));saved=read(output/'pool-predictions.json')
    need(models==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'All-pool point replay differs')
    freshness=feature_freshness(prior.feature_matrix(pool,read(fresh/'pool-features.json')));need(freshness==read(output/'pool-feature-freshness.json'),'Feature freshness replay differs')
    selection=choose(pool,models,freshness);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,models,selection,freshness),'Selection replay differs')
    selected=selection['selected_pool_indices'];selected_saved=read(output/'fresh-predictions.json');need(all(selected_saved[k]==v for k,v in frozen_subset(saved,selected).items()),'Selected point replay differs')
    need(read(fresh/'candidates.json')==[pool[i] for i in selected],'Selected candidates differ')
    features=read(fresh/'pool-features.json');need(read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in selected]},'Selected features differ')
    scored=False
    if (output/'fresh-metrics.json').exists():
        rows=read(fresh/'candidates.json');m,conditional,active,gates,eligible=score_values(selected_saved,prior.labels_for(rows,read(fresh/'labels.json')),dev);result=read(output/'fresh-metrics.json')
        need(m==result['models'] and conditional==result['conditional_models'] and active==result['active_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Challenge fresh metric replay differs');scored=True
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

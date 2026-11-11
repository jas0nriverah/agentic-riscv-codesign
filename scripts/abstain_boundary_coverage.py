#!/usr/bin/env python3
"""Zero-fit same-chain training-coverage abstention for fixed learned decisions.

Support uses training FORMULAS only, not their labels. All eligible chains are
checked jointly per chain, never by mixing aggregate min/max feature columns.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import learn_boundary_coverage as previous
local=previous.local
prior=previous.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
NAME='boundary_abstention'
LEARNED=previous.FALLBACK
CURRENT,BUDGET,STRUCTURAL=previous.CURRENT,previous.BUDGET,previous.PREVIOUS
NAMES=(*previous.NAMES,NAME)
CAPS=previous.CAPS
OUT=ROOT/'results/boundary-abstention'
FRESH=ROOT/'results/boundary-abstention-validation'
SCHEMA='isaforge-boundary-abstention-v1'
POLICY={'weights':'Exactly the sealed1857-row217-feature coverage-only forest; zero fits. Other frozen models retained as diagnostics, never candidates.',
 'cell':'For EACH same-chain learning-eligible rootxor/add/directcompoundSRA: own conservative data unknown span<=16 means narrow, while span>16 means wide (including17..31, not necessarily all32unknown); intersection of OWN data and OWN post-add input-bearing nonleaf subtree keys nonempty means shared, else unshared. Frozen prior known-bit/subtree semantics.',
 'training_support':'Enumerate eligible chains of all1857 frozen training FORMULAS; include cells with positive occurrence count, no target,ID,error or model-score filtering. Freeze counts/support before new features/labels.',
 'multi_chain':'Permit a NEW learned override only when there is at least one eligible chain and EVERY eligible chain cell is supported. ANY unsupported chain abstains the whole formula. No aggregate min-width/max-sharing pairing.',
 'prediction':'If all eligible cells supported, use frozen boundary_coverage_only exactly; otherwise previous_structural exactly. Outside learning scope previous_structural. No mean/median/threshold/weight changes or per-case exceptions.',
 'scope':'Input-coverage heuristic, not calibrated risk or universal safety. Original AST and frozen learned predictions only; labels/IDs never determine inference.'}
SELECTION={'pool_count':128,'general_count':32,'unsupported_count':8,'challenge_count':88,'maximum_active':16,'shared_controls':8,
 'fixed':'General32 then fixedunsupported8 always labeled in frozen pool order. All128 features/points retained. Challenge activity=guarded candidate<=cap<previous_structural, not inherited median changes.',
 'freshness':'Exact217/233 tuple equality against all fitted/evaluated/previous pool feature rows. Fixed40 history or internal duplicates block eligibility without replacements. Challenge history/fixed-key matches excluded; round-robin picks one per cluster in both representations.',
 'ordering':'Sort eligible challenge template names; repeatedly take first remaining originalpoolindex per template, skipping already selected217/233 clusters; stop immediately at16 or exhaustion. Append actions after fixed40.',
 'coverage':'At least4 supported NEW learned actions across at least2 templates including128; fixedunsupported8 must contain at least1 blocked would-be learned cap override beforelabels.',
 'populations':'General32, fixedunsupported8, active-only, and conditional-full(active+SAME8generaloutsidecontrols) separately gated. Shared controls disclosed, no pooled/independence claim.',
 'missing':'No pool extension, filling, retries, replacements or postlabel selection/filtering. All fixed rows remain, including abstentions.'}
GATES={'retained':'All15complete retained panels938metricrows/922records and prior named subsets: MAE/MAPE/tail<=release,previous_structural,learned217; FA<=release FR<=signed separately32/64/128; bounds signed<=learned<=guard<=previous<=release. Preserve30requiredrepairs+safe122 and reject159.',
 'general':'Completegeneral32 strict MAE/MAPE and summedFA-event gains vs signed, plus all retained-style gates. No filtering.',
 'other_fresh':'Fixedunsupported8, conditional-full and active-only each pass the same no-lossaccuracy/tail/FA/FR gates, with exact previous_structural fallback for unsupported. Prospective supported4/2/128 and>=1blocked override coverage required; never call a block correct withouttruth.',
 'tolerance':previous.GATES['tolerance'],'failure':'Any failed or missing gate remains ineligible. No source,cell,weight,cap,cohort,selection or margin change after labels.'}


def chain_cells(formula):
 result=[]
 for data,control,post,outer in local.chains(formula):
  span=local.unknown_shape(data)[0]
  if outer.value not in ('and','or','xor') and span>16:continue
  shared=len(local.nonleaf_subtrees(data)&local.nonleaf_subtrees(post))
  result.append({'unknown_span':span,'shared_nonleaf_count':shared,'outer_operator':outer.value,
   'cell':('narrow' if span<=16 else 'wide')+('_shared' if shared else '_unshared')})
 return result


def derive_support(formulas):
 counts={};eligible_formulas=0;chains=0
 for formula in formulas:
  cells=chain_cells(formula);eligible_formulas+=bool(cells)
  for row in cells:counts[row['cell']]=counts.get(row['cell'],0)+1;chains+=1
 return {'training_formula_count':len(formulas),'eligible_formula_count':eligible_formulas,'eligible_chain_count':chains,
  'cell_counts':dict(sorted(counts.items())),'supported_cells':sorted(counts),'input_only':True}


def guard(formulas,learned,structural,support):
 known=set(support['supported_cells']);values=[];details=[]
 for i,formula in enumerate(formulas):
  cells=chain_cells(formula);allowed=bool(cells) and all(r['cell'] in known for r in cells)
  point=learned[i] if allowed else structural[i];values.append(point)
  details.append({'chains':cells,'all_cells_supported':allowed,'unsupported_cells':sorted({r['cell'] for r in cells if r['cell'] not in known}),
   'blocked_caps':[c for c in CAPS if learned[i]<=c<point],'supported_new_caps':[c for c in CAPS if point<=c<structural[i]]})
 return values,details


def source_hashes():
 paths=[Path(__file__),ROOT/'tests/test_abstain_boundary_coverage.py',ROOT/'scripts/learn_boundary_coverage.py',ROOT/'scripts/boundary_coverage_features.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 return {prior.relative(p):sha(p) for p in paths}


def points(rows,x,models,support,old=None):
 values,routes,details=previous.points(rows,x,models,old)
 values[NAME],cells=guard([r['formula'] for r in rows],values[LEARNED],values[STRUCTURAL],support)
 return values,routes,{**details,'coverage_guard':cells}


def panel_metrics(row):
 y=row['actual_lut4'];v=row['models'];m={n:prior.model_metrics(v[n],y) for n in NAMES}
 m['checks']={'accuracy_no_worse':{ref:previous.accuracy(m[ref],m[NAME]) for ref in (BUDGET,STRUCTURAL,LEARNED)},
  'caps':{str(c):{'false_accept_no_worse_release':m[NAME]['caps'][str(c)]['false_accept']<=m[BUDGET]['caps'][str(c)]['false_accept'],
   'false_reject_no_worse_signed':m[NAME]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject']} for c in CAPS},
  'maximum_underprediction_no_worse':all(m[NAME]['maximum_underprediction_lut4']<=m[n]['maximum_underprediction_lut4']+GATES['tolerance'] for n in (BUDGET,STRUCTURAL,LEARNED,CURRENT)),
  'pointwise_bounds':bool(np.all(np.asarray(v[NAME])>=np.asarray(v[LEARNED])) and np.all(np.asarray(v[NAME])<=np.asarray(v[STRUCTURAL])) and np.all(np.asarray(v[LEARNED])>=np.asarray(v[CURRENT])) and np.all(np.asarray(v[STRUCTURAL])<=np.asarray(v[BUDGET]))),
  'events':{ref:previous.incumbent.boundary.release.cap_events(v[ref],v[NAME],y) for ref in (CURRENT,BUDGET,STRUCTURAL,LEARNED)}}
 return m


def passed(c):return all(all(v.values()) for v in c['accuracy_no_worse'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']


def subset(row,indices):
 need(bool(indices),'Empty required population')
 return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],'models':{n:[row['models'][n][i] for i in indices] for n in NAMES}})


def template_group(row,folder,template):
 indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template];need(len(indices)==4,'Named4 differs');return subset(row,indices)


def panel_inputs():
 yield from previous.panel_inputs()
 rows=read(previous.FRESH/'candidates.json');x=prior.feature_matrix(rows,read(previous.FRESH/'features.json'));y=prior.labels_for(rows,read(previous.FRESH/'labels.json'));saved=read(previous.OUT/'fresh-predictions.json')
 for name,key in [('consumed-ninth-general32','general_selected_indices'),('consumed-ninth-conditional9','conditional_selected_indices')]:
  ix=saved[key];yield name,([rows[i] for i in ix],x[ix,:],[y[i] for i in ix])


def retained_panels(models,support):
 old=previous.incumbent.previous.load(previous.incumbent.previous.OUT);panels={}
 for name,(rows,x,y) in panel_inputs():
  values,routes,details=points(rows,x,models,support,old)
  panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':y,'models':values,'routes':routes,**details}
 return panels


def development_metrics(panels):
 m={n:panel_metrics(row) for n,row in panels.items()};b=previous.incumbent.boundary
 named={'arithmetic_stress32':m['arithmetic-stress'],
  'signed_dual_arithmetic4':template_group(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic'),
  'signed_add_boolean4':template_group(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
  'compound_signed_add_xor4':template_group(panels['consumed-fourth-fresh40'],b.release.signed.FRESH,'heldout_compound_signed_add_xor'),
  'fifth_compound_signed_add_xor4':template_group(panels['consumed-fifth-fresh40'],b.release.FRESH,'heldout_compound_signed_add_xor'),
  'fifth_compound_signed_xordata_addxor4':template_group(panels['consumed-fifth-fresh40'],b.release.FRESH,'heldout_compound_signed_xordata_addxor')}
 broad=read(b.FRESH/'candidates.json');named['broad_compound32']=subset(panels['consumed-sixth-broad40'],[i for i,r in enumerate(broad) if b.release.signed.route(r['formula'])['compound']])
 latest=panels['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(latest['actual_lut4']) if y<=128<latest['models'][BUDGET][i]];fa=[i for i,y in enumerate(latest['actual_lut4']) if any(latest['models']['boundary_median'][i]<=c<latest['models'][BUDGET][i] and y>c for c in CAPS)]
 named['eight_corrected_fr']=subset(latest,fr);named['two_previous_new_fa']=subset(latest,fa)
 general=panels['consumed-eighth-general32'];four=[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][STRUCTURAL][i]];named['four_confident_fr']=subset(general,four);named['prior_active16']=subset(panels['consumed-eighth-conditional24'],list(range(16)))
 required=read(previous.OUT/'development-metrics.json')['required_rejection_cases'];lookup={i:row['models'][NAME][j] for row in panels.values() for j,i in enumerate(row['candidate_ids'])}
 all30=all(lookup[r['candidate_id']]<=r['cap'] for r in required);need(len(required)==30,'Required30 changed')
 safe=panels['consumed-ninth-general32'];safe_ix=[i for i,y in enumerate(safe['actual_lut4']) if y<=128<safe['models'][STRUCTURAL][i] and safe['models'][LEARNED][i]<=128];need(len(safe_ix)==1 and safe['actual_lut4'][safe_ix[0]]==122,'Safe122 differs')
 named['safe122']=subset(safe,safe_ix);bad=panels['consumed-ninth-conditional9'];bad_ix=[i for i,y in enumerate(bad['actual_lut4']) if y>128 and bad['models'][LEARNED][i]<=128<bad['models'][STRUCTURAL][i]];need(len(bad_ix)==1 and bad['actual_lut4'][bad_ix[0]]==159,'Unsafe159 differs');named['unsafe159']=subset(bad,bad_ix)
 guards={'all_fifteen_retained_panels_pass':all(passed(x['checks']) for x in m.values()),'all_named_subsets_preserved':all(passed(x['checks']) for x in named.values()),'all_thirty_required_repairs_preserved':all30,'safe122_preserved':all(safe['models'][NAME][i]<=128 for i in safe_ix),'unsafe159_rejected':all(bad['models'][NAME][i]>128 for i in bad_ix)}
 guards['development_gate_passed']=all(guards.values())
 return {'panels':m,'named_regressions':named,'gates':{NAME:guards},'selected_candidate':NAME if guards['development_gate_passed'] else None,'evaluated_candidate':NAME,'retained_metric_rows':938,'retained_circuit_records':922,'shared_controls':16,'all_panels_consumed':True,'independent_test':False,'no_pooled_metric':True}


def historical_records():
 formulas,x=previous.historical_records();blocks=[x]
 for path in (previous.TRAIN/'features.json',previous.FRESH/'features.json',previous.FRESH/'pool-features.json'):
  p=read(path);positions=[p['columns'].index(n) for n in prior.v6.mapping_columns()];blocks.append(np.asarray([r['values'] for r in p['records']])[:,positions]);formulas.extend(r['formula'] for r in p['records'])
 x=np.vstack(blocks);need(x.shape==(3235,217) and len(formulas)==3235,'3235 historical rows required');return formulas,x


def feature_freshness(pool,x):
 formulas,h=historical_records();reports={}
 for kind in ('coverage','augmented'):
  history=np.hstack([h,np.asarray([local.features(f) for f in formulas])]) if kind=='augmented' else h
  values=previous.inputs(pool,x,kind);known={tuple(float(v) for v in a) for a in history};groups={};rep=[];keys=[tuple(float(v) for v in a) for a in values]
  for i,key in enumerate(keys):groups.setdefault(key,[]).append(i);rep.append(groups[key][0])
  reports[kind]={'historical_unique_count':len(known),'historical_matches':[i for i,k in enumerate(keys) if k in known],'cluster_representatives':rep,'duplicate_clusters':[v for v in groups.values() if len(v)>1]}
 return {'historical_rows':3235,'fitted_rows':1857,'evaluated_circuit_records':922,'prior_pool_rows':[200,128,128],'representations':reports,'equality':'Exact float64 numeric217/233 tuples; labels unused.'}


def authenticate(output):
 p=read(output/'protocol.json');need(p['schema']==SCHEMA and p['policy']==POLICY and p['selection']==SELECTION and p['gates']==GATES,'Frozen abstention policy differs');need(p['sources_sha256']==source_hashes(),'Source differs')
 for n,d in p['inputs_sha256'].items():need(sha(ROOT/n)==d,'Input differs: '+n)
 manifest=read(previous.OUT/'training-manifest.json');need(derive_support([r['formula'] for r in manifest['rows']])==read(output/'support-cells.json'),'Formula-only training support differs')
 previous.load(previous.OUT);return p


def prepare(output,fresh):
 need(not (output/'protocol.json').exists(),'Protocol already frozen')
 for n in ('pool-features.json','feature-attempt.json','selection.json','labels.json','label-attempt.json'):need(not (fresh/n).exists(),'Freeze before features/labels')
 pool=read(fresh/'pool-candidates.json');need(len(pool)==128 and read(fresh/'novelty.json')['status']=='pass','Fixed128 novelty required')
 manifest=read(previous.OUT/'training-manifest.json');support=derive_support([r['formula'] for r in manifest['rows']]);need(support['training_formula_count']==1857 and support['eligible_chain_count']==32,'Exact frozen training support required');write(output/'support-cells.json',support)
 goal=ROOT/'results/boundary-repair-goal.json';update=ROOT/'results/boundary-repair-goal-update.json';write(output/'goal-at-freeze.json',read(goal));write(output/'goal-update-at-freeze.json',read(update))
 paths=[output/'support-cells.json',output/'goal-at-freeze.json',output/'goal-update-at-freeze.json']
 paths += [previous.OUT/n for n in ('protocol.json','model-freeze.json','training-manifest.json','training-inputs.npz','coverage.joblib','coverage.json','development-predictions.json','development-metrics.json','fresh-point-freeze.json','fresh-predictions.json','fresh-metrics.json','audit.json')]
 paths += [previous.TRAIN/'features.json']+[previous.FRESH/n for n in ('pool-candidates.json','pool-features.json','candidates.json','features.json','labels.json','plan.json')]
 paths += previous.historical_feature_paths()+[ROOT/'results/feature-comparison/rows.json']+[fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
 counts={**read(previous.OUT/'protocol.json')['retained_panels'],'consumed-ninth-general32':32,'consumed-ninth-conditional9':9}
 p={'schema':SCHEMA,'frozen_at_utc':now(),'fresh':prior.relative(fresh),'policy':POLICY,'selection':SELECTION,'gates':GATES,'finite_candidates':[NAME],'planned_fits':0,'maximum_fits':0,'native_jobs':0,'retained_panels':counts,'goal_source_sha256':sha(goal),'goal_update_source_sha256':sha(update),'scope':'Fixedgeneral32+fixedunsupported8+separate supported-action challenge;8general controls shared with conditional-full. No pooled metric/independence/universal safety or calibrated risk claim. Unchanged1857/217 model, zero fits.','sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(x):sha(x) for x in paths}}
 write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}


def freeze_policy(output):
 authenticate(output);need(not (output/'policy-freeze.json').exists(),'Policy already sealed');models=previous.load(previous.OUT);support=read(output/'support-cells.json');panels=retained_panels(models,support)
 write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels));seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'new_fits':0,'files_sha256':{n:sha(output/n) for n in ('development-predictions.json','development-metrics.json')}};write(output/'policy-freeze.json',seal);return seal


def load(output):
 authenticate(output);seal=read(output/'policy-freeze.json');need(seal['protocol_sha256']==sha(output/'protocol.json') and seal['new_fits']==0,'Zero-fit seal required')
 for n,d in seal['files_sha256'].items():need(sha(output/n)==d,'Sealed policy artifact differs')
 return previous.load(previous.OUT)


def choose(pool,values,details,freshness):
 general=[i for i,r in enumerate(pool) if r['cohort']=='general'];unsupported=[i for i,r in enumerate(pool) if r['cohort']=='unsupported'];controls=[i for i,r in enumerate(pool) if r['reserved_control']];fixed=general+unsupported
 need(len(pool)==128 and len(general)==32 and len(unsupported)==8 and len(controls)==8,'Fixed128 split differs')
 reps={k:r['cluster_representatives'] for k,r in freshness['representations'].items()};history=set().union(*(r['historical_matches'] for r in freshness['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()};raw=[];eligible=[];queues={};fixed_collision=[]
 for i,r in enumerate(pool):
  if r['cohort']!='challenge' or not any(values[NAME][i]<=c<values[STRUCTURAL][i] for c in CAPS):continue
  raw.append(i)
  if any(reps[k][i] in seen[k] for k in reps):fixed_collision.append(i)
  elif i not in history:eligible.append(i);queues.setdefault(r['template'],[]).append(i)
 active=[];skipped=[]
 while len(active)<16 and any(queues.values()):
  for template in sorted(queues):
   if len(active)>=16:break
   while queues[template] and any(reps[k][queues[template][0]] in seen[k] for k in reps):skipped.append(queues[template].pop(0))
   if queues[template]:
    i=queues[template].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 return {'general_pool_indices':general,'unsupported_pool_indices':unsupported,'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in history],'fixed_collision_active_pool_indices':fixed_collision,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':fixed+active}


def coverage(pool,values,details,selection,freshness):
 fixed=selection['general_pool_indices']+selection['unsupported_pool_indices'];active=selection['selected_active_pool_indices'];selected=selection['selected_pool_indices'];checks={}
 for kind,r in freshness['representations'].items():
  keys=r['cluster_representatives'];history=set(r['historical_matches']);checks[kind+'_fixed_fresh']=not bool(history&set(fixed));checks[kind+'_fixed_unique']=len({keys[i] for i in fixed})==40;checks[kind+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[NAME][i]<=c<values[STRUCTURAL][i] for i in active) for c in CAPS};blocked=[i for i in selection['unsupported_pool_indices'] if details['coverage_guard'][i]['blocked_caps']]
 checks.update({'at_least_four_supported_actions':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128_action':caps['128']>=1,'at_least_one_fixed_blocked_override':len(blocked)>=1})
 return {'pool_count':128,'general_count':32,'unsupported_count':8,'shared_control_count':8,'raw_active_count':len(selection['raw_active_pool_indices']),'eligible_active_count':len(selection['eligible_active_pool_indices']),'selected_active_count':len(active),'selected_templates':templates,'supported_action_caps':caps,'blocked_override_count':len(blocked),'blocked_unsupported_pool_indices':blocked,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}


def point_subset(saved,indices):
 result=previous.point_subset(saved,indices);result['models'][NAME]=[saved['models'][NAME][i] for i in indices];result['coverage_guard']=[saved['coverage_guard'][i] for i in indices];return result


def freeze_selection(output):
 p=authenticate(output);fresh=ROOT/p['fresh'];need(not (fresh/'selection.json').exists() and not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Single prelabel selection required')
 pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');values,routes,details=points(pool,prior.feature_matrix(pool,features),load(output),read(output/'support-cells.json'));dev=read(output/'development-metrics.json')
 saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in pool],'formulas':[r['formula'] for r in pool],'templates':[r['template'] for r in pool],'models':values,'routes':routes,**details,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME};write(output/'pool-predictions.json',saved)
 freshness=feature_freshness(pool,prior.feature_matrix(pool,features));write(output/'feature-freshness.json',freshness);selection=choose(pool,values,details,freshness);cov=coverage(pool,values,details,selection,freshness);indices=selection['selected_pool_indices']
 write(fresh/'selection.json',{'schema':SCHEMA,'frozen_at_utc':now(),**selection,'coverage':cov,'pool_predictions_sha256':sha(output/'pool-predictions.json'),'labels_present':False});write(fresh/'candidates.json',[pool[i] for i in indices]);write(fresh/'features.json',{'columns':features['columns'],'records':[features['records'][i] for i in indices]})
 selected={'schema':SCHEMA,'created_at_utc':now(),**point_subset(saved,indices),'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME,'selection_coverage':cov,'general_selected_indices':list(range(32)),'unsupported_selected_indices':list(range(32,40)),'active_selected_indices':list(range(40,len(indices))),'shared_control_selected_indices':[indices.index(i) for i in selection['reserved_control_pool_indices']]};selected['conditional_selected_indices']=selected['active_selected_indices']+selected['shared_control_selected_indices'];write(output/'fresh-predictions.json',selected)
 paths=[output/n for n in ('protocol.json','support-cells.json','policy-freeze.json','feature-freshness.json','pool-predictions.json','fresh-predictions.json')]+[fresh/n for n in ('pool-candidates.json','pool-features.json','selection.json','candidates.json','features.json')]
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'fresh_labels_present':False,'new_fits':0,'bindings':{prior.relative(x):sha(x) for x in paths}};write(output/'fresh-point-freeze.json',seal);paths.append(output/'fresh-point-freeze.json');write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':{prior.relative(x):sha(x) for x in paths}});return {'selection_coverage':cov,'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json')}


def score_values(saved,y,dev):
 row={**saved,'actual_lut4':y};g=subset(row,saved['general_selected_indices']);u=subset(row,saved['unsupported_selected_indices']);c=subset(row,saved['conditional_selected_indices']);a=subset(row,saved['active_selected_indices']) if saved['active_selected_indices'] else None
 checks={'coverage':saved['selection_coverage'],'general_no_loss':passed(g['checks']),'general_strict_signed':previous.accuracy(g[CURRENT],g[NAME],True),'general_strict_fa_gain_signed':sum(g[NAME]['caps'][str(z)]['false_accept'] for z in CAPS)<sum(g[CURRENT]['caps'][str(z)]['false_accept'] for z in CAPS),
  'unsupported_passes':passed(u['checks']),'conditional_full_passes':passed(c['checks']),'active_subset_passes':bool(a and passed(a['checks'])),'unsupported_exact_previous':all(saved['models'][NAME][i]==saved['models'][STRUCTURAL][i] for i in saved['unsupported_selected_indices'])}
 ok=checks['coverage']['passed'] and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['unsupported_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes'] and checks['unsupported_exact_previous'];eligible=ok and dev['selected_candidate']==NAME
 return g,u,c,a,{NAME:{'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][NAME]['development_gate_passed'],'eligible':eligible}},eligible


def verify_fresh(output):
 p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
 for n,d in seal['bindings'].items():need(sha(ROOT/n)==d,'Frozen freshpayload differs')
 return p,fresh


def score(output):
 p,fresh=verify_fresh(output);rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows],'Selectedalignment differs');g,u,c,a,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),read(output/'development-metrics.json'))
 result={'schema':SCHEMA,'models':g,'unsupported_models':u,'conditional_models':c,'active_subgroup':a,'gates':gates,'selection_coverage':saved['selection_coverage'],'selected_candidate':saved['selected_candidate'],'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,'general_count':32,'unsupported_count':8,'conditional_count':len(saved['conditional_selected_indices']),'active_count':len(saved['active_selected_indices']),'shared_controls':8,'unique_label_count':len(rows),'fits':0,'native_jobs':0,'no_pooled_metric':True,'fresh_labels_sha256':sha(fresh/'labels.json'),'scope':p['scope']};write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
 p=authenticate(output);rows=read(candidates);values,routes,details=points(rows,prior.feature_matrix(rows,read(features)),load(output),read(output/'support-cells.json'));dev=read(output/'development-metrics.json')
 write(destination,{'schema':SCHEMA,'model':NAME,'selected_candidate':dev['selected_candidate'],'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':values,'predicted_lut4':values[NAME],'routes':routes,**details,'fits':0,'native_jobs':0,'upper_lut4':None,'calibration_status':'uncalibrated','candidates_sha256':sha(candidates),'features_sha256':sha(features),'protocol_sha256':sha(output/'protocol.json'),'scope':p['scope']});return {'predictions':len(rows),'new_fits':0,'native_jobs':0,'output':str(destination)}


def replay(output):
 p,fresh=verify_fresh(output);models=load(output);support=read(output/'support-cells.json');panels=retained_panels(models,support);need(panels==read(output/'development-predictions.json'),'Developmentpoints differ');dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Developmentmetrics differ')
 pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');values,routes,details=points(pool,prior.feature_matrix(pool,features),models,support);saved=read(output/'pool-predictions.json');need(values==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'Poolpoints differ');fr=feature_freshness(pool,prior.feature_matrix(pool,features));need(fr==read(output/'feature-freshness.json'),'Freshness differs')
 selection=choose(pool,values,details,fr);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,values,details,selection,fr),'Selection differs');ix=selection['selected_pool_indices'];selected=read(output/'fresh-predictions.json');need(all(selected[k]==v for k,v in point_subset(saved,ix).items()),'Selectedpoints differ');need(read(fresh/'candidates.json')==[pool[i] for i in ix] and read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in ix]},'Selectedinput differs')
 scored=False
 if (output/'fresh-metrics.json').exists():
  g,u,c,a,gates,eligible=score_values(selected,prior.labels_for(read(fresh/'candidates.json'),read(fresh/'labels.json')),dev);r=read(output/'fresh-metrics.json');need(g==r['models'] and u==r['unsupported_models'] and c==r['conditional_models'] and a==r['active_subgroup'] and gates==r['gates'] and eligible==r['scoped_experimental_eligibility'],'Freshmetric differs');scored=True
 return {'status':'pass','retained_metric_rows':938,'retained_circuit_records':922,'pool_rows':128,'selected_rows':len(ix),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-policy','freeze-selection','score','predict-cached','replay'));parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--fresh',type=Path,default=FRESH);parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path);a=parser.parse_args();out=a.output.resolve()
 if a.command=='prepare':result=prepare(out,a.fresh.resolve())
 elif a.command=='predict-cached':
  need(all((a.candidates,a.features,a.prediction_output)),'Explicitcached inputs/outputrequired');result=predict_cached(out,a.candidates,a.features,a.prediction_output)
 else:result={'freeze-policy':freeze_policy,'freeze-selection':freeze_selection,'score':score,'replay':replay}[a.command](out)
 print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Matched release-first pipeline corroboration with pure carry-refined features.

Two fixed fits share1889 training rows, differ only by16 localized AST columns.
A deterministic development hierarchy is frozen before new labels; no native
job is launched here. Learned raw means support fixed physical cap decisions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import signal
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import abstain_boundary_coverage as baseline
previous=baseline.previous
incumbent=previous.incumbent
import boundary_carry_features as local
prior=incumbent.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-boundary-corroboration-v1'
PRIMARY='corroborated_augmented'
FALLBACK='corroborated_coverage_only'
CANDIDATES=(PRIMARY,FALLBACK)
KINDS={PRIMARY:'augmented',FALLBACK:'coverage'}
CURRENT,BUDGET=baseline.CURRENT,baseline.BUDGET
PREVIOUS=baseline.NAME
STRUCTURAL,LEARNED=baseline.STRUCTURAL,baseline.LEARNED
REFERENCES=(BUDGET,STRUCTURAL,LEARNED,PREVIOUS)
NAMES=(*baseline.NAMES,*CANDIDATES)
CAPS=incumbent.CAPS
OUT=ROOT/'results/boundary-corroboration'
TRAIN=ROOT/'results/boundary-corroboration-data'
FRESH=ROOT/'results/boundary-corroboration-validation'
POLICY={'scope':'ALL original rootxor/add/DIRECTcompoundSRA chains, including outer-input cases; data addi+xori and input control must bind to the SAME shift.',
 'decision':'Start from budget_release_compound_only. For each physicalcap32/64/128 require signed<=cap<release, ALLsame-chain training cells covered, and NEWtrained RAWMEAN<=cap. Return smallest qualifyingcap; otherwise release exactly. NO legacy median/structural/learned acceptance bypass.',
 'bounds':'signed<=candidate<=release, deliberately allowing correction of inherited64 acceptances by raising them towardrelease.',
 'support':'Per ALLrootchain: own carry-refined unknownspan<=16 narrow elsewide, own data/postadd nonleaf subtree sharing. Every cell must occur in the1889trainingFORMULAS; no labels/IDs/errors used. Freeze and disclose allcounts, including ifallfourcells occur.',
 'fit_order':['augmented233','coverage217'],'configuration':prior.v6.FIXED_PARAMETERS,
 'selection':'Firstaugmented if everydevelopmentgatepasses, elsecoverage-only ifeverygatepasses, elsenone/augmenteddiagnostic. No postfreshswap.',
 'training':'Exactlysame frozen1857fittedrows+32noveltraining; no consumedlabels. Matched300treefixedseed/parameters,one thread. New16block includes carryanalysis but ablation does not isolatecarryalone.',
 'scope_limit':'Learned physicalbudget-decision support, not global point-regressor replacement or calibratedrisk. No capmargin/seedgrid, no oldsource mutation.'}
GATES={'retained':'All18panels992metricrows/968records +namedsubsets,43requiredacceptances/6rejections. MAE/MAPE/tail<=release,structural,learned217,abstention; FA<=release FR<=signed per32/64/128; boundssigned<=candidate<=release.',
 'general':'Completefreshgeneral32 strict MAE/MAPE andFA-event gainsvssigned, plusallretainedstyleaccuracy/tail/capgates. No filtering.',
 'other_fresh':'Fixedsharing8,fixedlegacy8,conditional-full(actions+same8generalcontrols),active-only eachpasssamehardgates. No pooling or independenceclaim.',
 'activity':'Atleast4NEWacceptances candidate<=cap<oldabstention from>=2templates including128; fixedlegacy8>=1veto oldabstention<=64<candidate; fixedsharing8>=1veto oldlearned217<=128<candidate. Prediction-defined beforelabels; correctness onlyaftertruth.',
 'missing':'All32train+128poolretained. No retries,replacements,extensions,fitsbeyondmatched2,postlabelcolumns/policy/gatechanges.',
 'tolerance':incumbent.boundary.TOLERANCE}


def runtime_versions():
 import sklearn,joblib
 return {'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}


def source_hashes():
 paths=[Path(__file__),ROOT/'scripts/boundary_carry_features.py',ROOT/'tests/test_learn_boundary_corroboration.py',ROOT/'tests/test_boundary_carry_features.py',ROOT/'scripts/abstain_boundary_coverage.py',ROOT/'scripts/learn_boundary_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 return {prior.relative(p):sha(p) for p in paths}


def columns(kind):
 return list(prior.v6.mapping_columns())+(list(local.COLUMNS) if kind=='augmented' else [])


def inputs(rows,x,kind):
 base=x if x.shape[1]==217 else x[:,prior.v6.mapping_indices()]
 return np.hstack([base,np.asarray([local.features(r['formula']) for r in rows],dtype=float)]) if kind=='augmented' else base


def budget_support(signed,release,raw,scope):
 result=np.asarray(release,dtype=float).copy();supported=[]
 for i,active in enumerate(scope):
  caps=[cap for cap in CAPS if active and signed[i]<=cap<release[i] and raw[i]<=cap]
  if caps:result[i]=min(caps)
  supported.append(caps)
 return result.tolist(),supported

def cells(formula):
 return [('narrow' if local.unknown_shape(data)[0]<=16 else 'wide')+('_shared' if local.nonleaf_subtrees(data)&local.nonleaf_subtrees(post) else '_unshared') for data,control,post,outer in local.chains(formula)]


def derive_support(formulas):
 counts={};matched=0
 for formula in formulas:
  rows=cells(formula);matched+=bool(rows)
  for cell in rows:counts[cell]=counts.get(cell,0)+1
 return {'training_formula_count':len(formulas),'structural_formula_count':matched,'chain_count':sum(counts.values()),'cell_counts':dict(sorted(counts.items())),'supported_cells':sorted(counts),'input_only':True}


def points(rows,x,models,support,old_payload=None):
 if old_payload is None:
  oldmodels=baseline.load(baseline.OUT);oldcells=read(baseline.OUT/'support-cells.json')
  values,routes,details=baseline.points(rows,x,oldmodels,oldcells)
 else:
  values={n:list(v) for n,v in old_payload['models'].items()};routes=old_payload['routes']
  details={k:v for k,v in old_payload.items() if k not in ('candidate_ids','formulas','actual_lut4','models','routes')}
 cell_rows=[cells(r['formula']) for r in rows];known=set(support['supported_cells']);scope=[bool(v) and all(c in known for c in v) for v in cell_rows]
 raw={};caps={};provenance={}
 for name in CANDIDATES:
  kind=KINDS[name];raw[name]=models[kind].predict(inputs(rows,x,kind)).tolist();values[name],caps[name]=budget_support(values[CURRENT],values[BUDGET],raw[name],scope)
  provenance[name]=[{str(c):{'signed_accepts':values[CURRENT][i]<=c,'release_accepts':values[BUDGET][i]<=c,'structural_proposal':values[STRUCTURAL][i]<=c<values[BUDGET][i],
    'oldlearned_proposal':values[LEARNED][i]<=c<values[BUDGET][i],'oldabstention_proposal':values[PREVIOUS][i]<=c<values[BUDGET][i],
    'new_raw_accepts':raw[name][i]<=c,'covered':scope[i],'candidate_accepts':values[name][i]<=c} for c in CAPS} for i in range(len(rows))]
 return values,routes,{**details,'pipeline_cells':cell_rows,'pipeline_covered':scope,'corroboration_raw_lut4':raw,'corroborated_caps_lut4':caps,'proposal_provenance':provenance}

def accuracy(reference,candidate,strict=False):return incumbent.boundary.accuracy(reference,candidate,strict)


def panel_metrics(row):
 y=row['actual_lut4'];v=row['models'];m={n:prior.model_metrics(v[n],y) for n in NAMES};checks={}
 for name in CANDIDATES:
  checks[name]={'accuracy_no_worse':{r:accuracy(m[r],m[name]) for r in REFERENCES},
   'caps':{str(c):{'false_accept_no_worse_release':m[name]['caps'][str(c)]['false_accept']<=m[BUDGET]['caps'][str(c)]['false_accept'],
    'false_reject_no_worse_signed':m[name]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject']} for c in CAPS},
   'maximum_underprediction_no_worse':all(m[name]['maximum_underprediction_lut4']<=m[r]['maximum_underprediction_lut4']+GATES['tolerance'] for r in (*REFERENCES,CURRENT)),
   'pointwise_bounds':bool(np.all(np.asarray(v[name])>=np.asarray(v[CURRENT])) and np.all(np.asarray(v[name])<=np.asarray(v[BUDGET]))),
   'events':{r:incumbent.boundary.release.cap_events(v[r],v[name],y) for r in (*REFERENCES,CURRENT)}}
 m['checks']=checks
 if 'corroboration_raw_lut4' in row:m['raw_model_metrics']={n:prior.model_metrics(row['corroboration_raw_lut4'][n],y) for n in CANDIDATES}
 return m

def passed(c):return all(all(v.values()) for v in c['accuracy_no_worse'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']

def subset(row,indices):
 need(bool(indices),'Empty required subgroup')
 return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
  'models':{n:[row['models'][n][i] for i in indices] for n in NAMES},
  **({'corroboration_raw_lut4':{n:[row['corroboration_raw_lut4'][n][i] for i in indices] for n in CANDIDATES}} if 'corroboration_raw_lut4' in row else {})})


def template_group(row,folder,template):
 indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template];need(len(indices)==4,'Exact named4 required')
 return subset(row,indices)


def panel_inputs():
 yield from baseline.panel_inputs()
 rows=read(baseline.FRESH/'candidates.json');x=prior.feature_matrix(rows,read(baseline.FRESH/'features.json'));y=prior.labels_for(rows,read(baseline.FRESH/'labels.json'));saved=read(baseline.OUT/'fresh-predictions.json')
 for name,key in [('consumed-tenth-general32','general_selected_indices'),('consumed-tenth-unsupported8','unsupported_selected_indices'),('consumed-tenth-conditional14','conditional_selected_indices')]:
  ix=saved[key];yield name,([rows[i] for i in ix],x[ix,:],[y[i] for i in ix])

def retained_panels(models,support):
 old=read(baseline.OUT/'development-predictions.json');fresh=read(baseline.OUT/'fresh-predictions.json');rows=read(baseline.FRESH/'candidates.json');y=prior.labels_for(rows,read(baseline.FRESH/'labels.json'))
 for name,key in [('consumed-tenth-general32','general_selected_indices'),('consumed-tenth-unsupported8','unsupported_selected_indices'),('consumed-tenth-conditional14','conditional_selected_indices')]:
  ix=fresh[key];old[name]={**baseline.point_subset(fresh,ix),'actual_lut4':[y[i] for i in ix]}
 result={}
 for name,(rows,x,y) in panel_inputs():
  cached=old[name];need(cached['formulas']==[r['formula'] for r in rows],'Cached frozen baseline alignment differs')
  v,routes,details=points(rows,x,models,support,cached)
  result[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':y,'models':v,'routes':routes,**details}
 return result

def development_metrics(panels):
 metrics={n:panel_metrics(row) for n,row in panels.items()};targets=read(OUT/'evaluation-targets.json');accept=targets['established_repairs']+targets['remaining_fr_targets'];reject=targets['required_rejections']
 need(len(accept)==43 and len(reject)==6,'Frozen43/6 evaluation inventory differs')
 lookup={i:(row,j) for row in panels.values() for j,i in enumerate(row['candidate_ids'])};named={}
 # Inherited named groups are recomputed from their frozen row identities below.
 def group(panel,folder,template):return template_group(panels[panel],folder,template)
 b=incumbent.boundary
 named['arithmetic_stress32']=metrics['arithmetic-stress']
 named['signed_dual_arithmetic4']=group('consumed-second-fresh32',ROOT/'results/budget-preserving-validation','signed_dual_arithmetic')
 named['signed_add_boolean4']=group('consumed-third-fresh40',ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean')
 named['compound_signed_add_xor4']=group('consumed-fourth-fresh40',b.release.signed.FRESH,'heldout_compound_signed_add_xor')
 named['fifth_compound_signed_add_xor4']=group('consumed-fifth-fresh40',b.release.FRESH,'heldout_compound_signed_add_xor')
 named['fifth_compound_signed_xordata_addxor4']=group('consumed-fifth-fresh40',b.release.FRESH,'heldout_compound_signed_xordata_addxor')
 br=read(b.FRESH/'candidates.json');named['broad_compound32']=subset(panels['consumed-sixth-broad40'],[i for i,r in enumerate(br) if b.release.signed.route(r['formula'])['compound']])
 named['prior_active16']=subset(panels['consumed-eighth-conditional24'],list(range(16)))
 latest=panels['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(latest['actual_lut4']) if y<=128<latest['models'][BUDGET][i]];fa=[i for i,y in enumerate(latest['actual_lut4']) if any(latest['models']['boundary_median'][i]<=c<latest['models'][BUDGET][i] and y>c for c in CAPS)]
 need(len(fr)==8 and len(fa)==2,'Known8FR/2FA mapping differs');named['eight_corrected_fr']=subset(latest,fr);named['two_previous_new_fa']=subset(latest,fa)
 general=panels['consumed-eighth-general32'];four=[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][STRUCTURAL][i]];need(len(four)==4,'Exact4 confident errors required');named['four_confident_fr']=subset(general,four)
 safe=panels['consumed-ninth-general32'];safe_ix=[i for i,y in enumerate(safe['actual_lut4']) if y<=128<safe['models'][STRUCTURAL][i] and safe['models'][LEARNED][i]<=128];need(len(safe_ix)==1 and safe['actual_lut4'][safe_ix[0]]==122,'Safe122 differs');named['safe122']=subset(safe,safe_ix)
 bad=panels['consumed-ninth-conditional9'];bad_ix=[i for i,y in enumerate(bad['actual_lut4']) if y>128 and bad['models'][LEARNED][i]<=128<bad['models'][STRUCTURAL][i]];need(len(bad_ix)==1 and bad['actual_lut4'][bad_ix[0]]==159,'Unsafe159 differs');named['unsafe159']=subset(bad,bad_ix)
 named['latest_active6']=subset(panels['consumed-tenth-conditional14'],list(range(6)))
 def targets_metric(items):
  return panel_metrics({'actual_lut4':[item['actual_lut4'] for item in items],'models':{n:[lookup[item['candidate_id']][0]['models'][n][lookup[item['candidate_id']][1]] for item in items] for n in NAMES}})
 named['established39']=targets_metric(targets['established_repairs']);named['remaining_fr4']=targets_metric(targets['remaining_fr_targets']);named['protected_rejections6']=targets_metric(reject)
 gates={};decision_cases=[]
 for item in [*accept,*reject]:
  row,i=lookup[item['candidate_id']];need(row['actual_lut4'][i]==item['actual_lut4'],'Frozen evaluation target differs')
  decision_cases.append({**{k:item[k] for k in ('candidate_id','formula','actual_lut4','cap')},'expected':'accept' if item in accept else 'reject','predictions':{n:row['models'][n][i] for n in CANDIDATES}})
 for n in CANDIDATES:
  all_accept=all(lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]]<=r['cap'] for r in accept)
  all_reject=all(lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]]>r['cap'] for r in reject)
  c={'all_eighteen_panels_pass':all(passed(m['checks'][n]) for m in metrics.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_forty_three_acceptances_pass':all_accept,'all_six_rejections_pass':all_reject}
  c['development_gate_passed']=all(c.values());gates[n]=c
 selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
 return {'panels':metrics,'named_regressions':named,'evaluation_cases':decision_cases,'gates':gates,'selected_candidate':selected,'evaluated_candidate':selected or PRIMARY,'all_panels_consumed':True,'independent_test':False,'retained_metric_rows':992,'retained_circuit_records':968,'shared_controls':24,'no_pooled_metric':True}

def historical_feature_paths():
 return previous.historical_feature_paths()+[previous.TRAIN/'features.json',previous.FRESH/'features.json',previous.FRESH/'pool-features.json',baseline.FRESH/'features.json',baseline.FRESH/'pool-features.json']

def historical_records():
 formulas,x=baseline.historical_records();blocks=[x]
 for path in (baseline.FRESH/'features.json',baseline.FRESH/'pool-features.json'):
  p=read(path);pos=[p['columns'].index(n) for n in prior.v6.mapping_columns()];blocks.append(np.asarray([r['values'] for r in p['records']])[:,pos]);formulas.extend(r['formula'] for r in p['records'])
 x=np.vstack(blocks);need(x.shape==(3409,217) and len(formulas)==3409,'3409 historical rows required');return formulas,x

def feature_freshness(training_rows,tx,pool_rows,px):
 formulas,h=historical_records();haug=np.hstack([h,np.asarray([local.features(f) for f in formulas])]);t={k:inputs(training_rows,tx,k) for k in ('coverage','augmented')};pool={k:inputs(pool_rows,px,k) for k in ('coverage','augmented')};reports={}
 for kind,history in [('coverage',h),('augmented',haug)]:
  known={tuple(float(v) for v in row) for row in history};train_keys=[tuple(float(v) for v in row) for row in t[kind]];both=known|set(train_keys);keys=[tuple(float(v) for v in row) for row in pool[kind]];clusters={};reps=[]
  for i,key in enumerate(keys):clusters.setdefault(key,[]).append(i);reps.append(clusters[key][0])
  reports[kind]={'historical_unique_count':len(known),'training_historical_matches':[i for i,k in enumerate(train_keys) if k in known],
   'training_unique_count':len(set(train_keys)),'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in both],
   'pool_cluster_representatives':reps,'pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1]}
 return {'historical_rows':3409,'fitted_rows':1857,'unique_consumed_labels':968,'prior_pool_rows':[200,128,128,128],
  'representations':reports,'training_fresh':all(not r['training_historical_matches'] and r['training_unique_count']==32 for r in reports.values()),
  'equality':'Exact float64 numeric tuples; no rounding, no labels.'}


def authenticate(output):
 p=read(output/'protocol.json');need(p['schema']==SCHEMA and p['policy']==POLICY and p['gates']==GATES and p['local_features']==local.SCHEMA,'Frozen coverage protocol differs');need(p['sources_sha256']==source_hashes(),'Source differs');need(p['runtime_versions']==runtime_versions(),'Frozen runtime differs')
 for n,d in p['inputs_sha256'].items():need(sha(ROOT/n)==d,'Input differs: '+n)
 baseline.load(baseline.OUT);return p


def prepare(output,training,fresh):
 need(not (output/'protocol.json').exists(),'Protocol already frozen')
 for d in (training,fresh):
  for n in ('features.json','pool-features.json','feature-attempt.json','labels.json','label-attempt.json'):need(not (d/n).exists(),'Freeze before features/labels')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');need(len(t)==32 and len(pool)==128,'Exact32/128 required')
 for d in (training,fresh):need(read(d/'novelty.json')['status']=='pass','Novelty failed')
 need(all(local.learning_scope(r['formula']) for r in t),'Training outside allroot scope')
 old_manifest=read(previous.OUT/'training-manifest.json')['rows'];support=derive_support([r['formula'] for r in old_manifest]+[r['formula'] for r in t]);need(support['training_formula_count']==1889,'Support training count differs');write(output/'support-cells.json',support)
 goal=ROOT/'results/boundary-repair-goal.json';update=ROOT/'results/boundary-repair-goal-update.json';write(output/'goal-at-freeze.json',read(goal));write(output/'goal-update-at-freeze.json',read(update))
 paths=[output/n for n in ('support-cells.json','goal-at-freeze.json','goal-update-at-freeze.json','evaluation-targets.json','method-rationale.json','measurement-input-profile-audit.json')]
 paths+=historical_feature_paths()+[ROOT/'results/feature-comparison/rows.json']
 paths +=[previous.OUT/n for n in ('protocol.json','model-freeze.json','training-inputs.npz','training-manifest.json','audit.json')]
 paths +=[baseline.OUT/n for n in ('protocol.json','policy-freeze.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json','audit.json')]
 paths +=[baseline.FRESH/n for n in ('candidates.json','features.json','labels.json','pool-candidates.json','pool-features.json','plan.json')]
 paths +=[training/n for n in ('candidates.json','novelty.json','plan.json')]+[fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
 counts={**read(baseline.OUT/'protocol.json')['retained_panels'],'consumed-tenth-general32':32,'consumed-tenth-unsupported8':8,'consumed-tenth-conditional14':14}
 p={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),'policy':POLICY,'gates':GATES,'local_features':local.SCHEMA,
  'planned_fits':2,'maximum_fits':2,'maximum_fit_seconds':120,'fit_threads':1,'total_training_rows':1889,'consumed_labels_fitted':0,'base_columns':list(prior.v6.mapping_columns()),'augmented_columns':columns('augmented'),'retained_panels':counts,
  'selection':{'general_count':32,'sharing_count':8,'legacy_count':8,'challenge_count':80,'shared_controls':8,'maximum_active':16,'minimum_active':4,'minimum_templates':2,'requires_cap128':True,
   'active':'Selectedcandidate<=cap<oldabstention. Fixedlegacy8 requires>=1oldabstention64acceptanceveto; sharing8requires>=1oldlearned217128acceptanceveto. Prediction-defined, notcalledcorrect beforelabels.',
   'order':'Fixedgeneral32/sharing8/legacy8 first48. Challengehistorical/training/fixed217or233matchesexcluded, sortedtemplate roundrobin originalindex order, oneperclusterbothrepresentations, appendup16. Fixedcollisions blockeligibility; no filtering/refill/extensions.',
   'populations':'General/sharing/legacy/conditional-full(active+SAME8generalcontrols)/active-only separatelygated, no pooling or independenceclaim.'},
  'goal_source_sha256':sha(goal),'goal_update_source_sha256':sha(update),'runtime_versions':runtime_versions(),'scope':'Matchedcoverage/representation learning withrelease-first whole-pipeline corroboration. TargetedfiniteiCE40LUT4 evidence, uncalibrated, no universal safety/timing/power/CPUguarantee.',
  'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(x):sha(x) for x in paths}}
 write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}

def freeze_features(output):
 p=authenticate(output);training=ROOT/p['training'];fresh=ROOT/p['fresh'];need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(),'Feature receipt before new labels')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(t,prior.feature_matrix(t,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')))
 write(output/'feature-freshness.json',report);paths=[training/'features.json',fresh/'pool-features.json',output/'feature-freshness.json']
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'training_fresh':report['training_fresh'],'bindings':{prior.relative(x):sha(x) for x in paths}}
 write(output/'feature-freeze.json',seal);return seal


def training_data(training):
 manifest=read(previous.OUT/'training-manifest.json')['rows'];rows=[{'candidate_id':r['candidate_id'],'formula':r['formula']} for r in manifest]
 with np.load(previous.OUT/'training-inputs.npz',allow_pickle=False) as data:base_x=data['coverage'];base_y=data['y']
 new=read(training/'candidates.json');need(len(new)==32,'Exactnew32trainingrequired');new_x=inputs(new,prior.feature_matrix(new,read(training/'features.json')),'coverage');new_y=np.asarray(prior.labels_for(new,read(training/'labels.json')))
 rows.extend(new);x=np.vstack([base_x,new_x]);y=np.concatenate([base_y,new_y]);need(len(rows)==1889 and x.shape==(1889,217) and y.shape==(1889,),'1889matchedtrainingcontractdiffers');return rows,x,y

def run(output):
 from sklearn.ensemble import ExtraTreesRegressor
 from threadpoolctl import threadpool_limits
 import joblib
 p=authenticate(output);training=ROOT/p['training'];fresh=ROOT/p['fresh'];need(not (output/'run-start.json').exists(),'Single fit stage only');need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Fresh labels unavailable')
 feature=read(output/'feature-freeze.json');need(feature['training_fresh'],'Training feature novelty failed')
 for n,d in feature['bindings'].items():need(sha(ROOT/n)==d,'Frozenfeature differs')
 rows,x,y=training_data(training)
 write(output/'training-manifest.json',{'schema':SCHEMA,'rows':[{'training_index':i,'candidate_id':r.get('candidate_id','original:'+str(i)),'formula':r['formula'],'actual_lut4':float(y[i]),'source':'frozen1857' if i<1857 else 'new_training32'} for i,r in enumerate(rows)],'consumed_evaluation_labels_fitted':0})
 need(not (output/'training-inputs.npz').exists(),'Trainingmatrix already exists');np.savez_compressed(output/'training-inputs.npz',coverage=inputs(rows,x,'coverage'),augmented=inputs(rows,x,'augmented'),y=y)
 write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'training_labels_sha256':sha(training/'labels.json'),'training_features_sha256':sha(training/'features.json'),'planned_fits':2,'maximum_fits':2})
 started=time.monotonic();fits=[];models={}
 def deadline(signum,frame):raise TimeoutError('120second fixed fit stage exhausted')
 old=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120)
 try:
  with threadpool_limits(limits=1):
   for index,kind in enumerate(('augmented','coverage'),1):
    write(output/('fit-attempt-'+str(index)+'.json'),{'fit_index':index,'kind':kind,'started_at_utc':now(),'training_count':1889,'feature_count':len(columns(kind)),'training_inputs_sha256':sha(output/'training-inputs.npz'),'configuration':prior.v6.FIXED_PARAMETERS})
    began=time.monotonic();model=ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS);model.fit(inputs(rows,x,kind),y);models[kind]=model
    fits.append({'index':index,'kind':kind,'training_count':1889,'feature_count':len(columns(kind)),'fit_seconds':time.monotonic()-began});joblib.dump(model,output/(kind+'.joblib'))
    write(output/(kind+'.json'),{'schema':SCHEMA,'kind':kind,'columns':columns(kind),'training_count':1889,'new_training_count':32,'old_training_count':1857,'consumed_labels_fitted':0,'configuration':prior.v6.FIXED_PARAMETERS,'calibration':'uncalibrated','upper_lut4':None,'artifact_sha256':sha(output/(kind+'.joblib')),'protocol_sha256':sha(output/'protocol.json'),'runtime_versions':runtime_versions()})
   write(output/'timings.json',fits);panels=retained_panels(models,read(output/'support-cells.json'));write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
  names=['training-manifest.json','training-inputs.npz','fit-attempt-1.json','fit-attempt-2.json','augmented.joblib','coverage.joblib','augmented.json','coverage.json','timings.json','development-predictions.json','development-metrics.json','run-start.json']
  seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'feature_freeze_sha256':sha(output/'feature-freeze.json'),'fits_completed':2,'wall_seconds':time.monotonic()-started,'files_sha256':{n:sha(output/n) for n in names}}
  write(output/'model-freeze.json',seal);return seal
 except BaseException as e:write(output/'failure.json',{'error':str(e),'fits_completed':len(fits),'fit_records':fits,'maximum_fits':2,'wall_seconds':time.monotonic()-started});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)


def load(output):
 import joblib
 authenticate(output);seal=read(output/'model-freeze.json');need(seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==2,'Two matched fit seal required')
 for n,d in seal['files_sha256'].items():need(sha(output/n)==d,'Fittedartifact differs')
 result={}
 for kind in ('augmented','coverage'):
  meta=read(output/(kind+'.json'));model=joblib.load(output/(kind+'.joblib'))
  need(meta['columns']==columns(kind) and meta['training_count']==1889 and meta['artifact_sha256']==sha(output/(kind+'.joblib')) and model.n_features_in_==len(columns(kind)) and model.get_params()==__import__('sklearn.ensemble',fromlist=['ExtraTreesRegressor']).ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS).get_params(),'Exactfixed matched forest required');result[kind]=model
 return result


def choose(pool,values,freshness,evaluated):
 groups={c:[i for i,r in enumerate(pool) if r['cohort']==c] for c in ('general','sharing','legacy')};fixed=groups['general']+groups['sharing']+groups['legacy'];controls=[i for i,r in enumerate(pool) if r['reserved_control']]
 need(len(pool)==128 and len(groups['general'])==32 and len(groups['sharing'])==len(groups['legacy'])==8 and len(controls)==8,'Fixed128splitdiffers')
 reps={k:r['pool_cluster_representatives'] for k,r in freshness['representations'].items()};history=set().union(*(r['pool_historical_or_training_matches'] for r in freshness['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()};queues={};raw=[];eligible=[];excluded_fixed=[]
 for i,row in enumerate(pool):
  if row['cohort']!='challenge' or not any(values[evaluated][i]<=c<values[PREVIOUS][i] for c in CAPS):continue
  raw.append(i)
  if any(reps[k][i] in seen[k] for k in reps):excluded_fixed.append(i)
  elif i not in history:eligible.append(i);queues.setdefault(row['template'],[]).append(i)
 active=[];skipped=[]
 while len(active)<16 and any(queues.values()):
  for template in sorted(queues):
   if len(active)>=16:break
   while queues[template] and any(reps[k][queues[template][0]] in seen[k] for k in reps):skipped.append(queues[template].pop(0))
   if queues[template]:
    i=queues[template].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 return {**{c+'_pool_indices':v for c,v in groups.items()},'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in history],'fixed_feature_collision_active_pool_indices':excluded_fixed,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':fixed+active}

def coverage(pool,values,selection,freshness,evaluated):
 fixed=selection['general_pool_indices']+selection['sharing_pool_indices']+selection['legacy_pool_indices'];active=selection['selected_active_pool_indices'];selected=selection['selected_pool_indices'];checks={}
 for kind,r in freshness['representations'].items():
  keys=r['pool_cluster_representatives'];history=set(r['pool_historical_or_training_matches']);checks[kind+'_fixed_novel']=not bool(history&set(fixed));checks[kind+'_fixed_unique']=len({keys[i] for i in fixed})==48;checks[kind+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[PREVIOUS][i] for i in active) for c in CAPS}
 legacy=[i for i in selection['legacy_pool_indices'] if values[PREVIOUS][i]<=64<values[evaluated][i]];sharing=[i for i in selection['sharing_pool_indices'] if values[LEARNED][i]<=128<values[evaluated][i]]
 checks.update({'at_least_four_new_acceptances':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1,'at_least_one_legacy64_veto':len(legacy)>=1,'at_least_one_sharing128_veto':len(sharing)>=1})
 return {'pool_count':128,'general_count':32,'sharing_count':8,'legacy_count':8,'shared_control_count':8,'raw_active_count':len(selection['raw_active_pool_indices']),'eligible_active_count':len(selection['eligible_active_pool_indices']),'selected_active_count':len(active),'selected_templates':templates,'acceptance_caps':caps,'legacy64_veto_count':len(legacy),'legacy64_veto_pool_indices':legacy,'sharing128_veto_count':len(sharing),'sharing128_veto_pool_indices':sharing,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}

def point_subset(saved,indices):
 result=baseline.point_subset(saved,indices)
 for n in CANDIDATES:result['models'][n]=[saved['models'][n][i] for i in indices]
 for key in ('pipeline_cells','pipeline_covered'):result[key]=[saved[key][i] for i in indices]
 for key in ('corroboration_raw_lut4','corroborated_caps_lut4','proposal_provenance'):result[key]={n:[v[i] for i in indices] for n,v in saved[key].items()}
 return result

def freeze_selection(output):
 p=authenticate(output);fresh=ROOT/p['fresh'];need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists() and not (fresh/'selection.json').exists(),'Single prelabel selection required')
 pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');models=load(output);values,routes,details=points(pool,prior.feature_matrix(pool,features),models,read(output/'support-cells.json'));dev=read(output/'development-metrics.json');evaluated=dev['evaluated_candidate']
 saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in pool],'formulas':[r['formula'] for r in pool],'templates':[r['template'] for r in pool],'models':values,'routes':routes,**details,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':evaluated}
 write(output/'pool-predictions.json',saved);freshness=read(output/'feature-freshness.json');selection=choose(pool,values,freshness,evaluated);cov=coverage(pool,values,selection,freshness,evaluated);indices=selection['selected_pool_indices']
 write(fresh/'selection.json',{'schema':SCHEMA,'frozen_at_utc':now(),**selection,'coverage':cov,'evaluated_candidate':evaluated,'pool_predictions_sha256':sha(output/'pool-predictions.json'),'labels_present':False});write(fresh/'candidates.json',[pool[i] for i in indices]);write(fresh/'features.json',{'columns':features['columns'],'records':[features['records'][i] for i in indices]})
 selected={'schema':SCHEMA,'created_at_utc':now(),**point_subset(saved,indices),'selected_candidate':dev['selected_candidate'],'evaluated_candidate':evaluated,'selection_coverage':cov,'general_selected_indices':list(range(32)),'sharing_selected_indices':list(range(32,40)),'legacy_selected_indices':list(range(40,48)),'active_selected_indices':list(range(48,len(indices))),'shared_control_selected_indices':[indices.index(i) for i in selection['reserved_control_pool_indices']]}
 selected['conditional_selected_indices']=selected['active_selected_indices']+selected['shared_control_selected_indices'];write(output/'fresh-predictions.json',selected)
 paths=[output/n for n in ('protocol.json','support-cells.json','feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-predictions.json')]+[fresh/n for n in ('pool-candidates.json','pool-features.json','selection.json','candidates.json','features.json')]
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'fresh_labels_present':False,'new_fits':0,'bindings':{prior.relative(x):sha(x) for x in paths}};write(output/'fresh-point-freeze.json',seal)
 paths.append(output/'fresh-point-freeze.json');write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':{prior.relative(x):sha(x) for x in paths}});return {'selection_coverage':cov,'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json')}


def score_values(saved,y,dev):
 row={**saved,'actual_lut4':y};g=subset(row,saved['general_selected_indices']);sharing=subset(row,saved['sharing_selected_indices']);legacy=subset(row,saved['legacy_selected_indices']);c=subset(row,saved['conditional_selected_indices']);a=subset(row,saved['active_selected_indices']) if saved['active_selected_indices'] else None;gates={}
 for n in CANDIDATES:
  active=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=z<saved['models'][PREVIOUS][i] for z in CAPS)]
  activity={'acceptances':len(active),'templates':len({saved['templates'][i] for i in active}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][PREVIOUS][i] for i in active),
   'legacy64_veto':sum(saved['models'][PREVIOUS][i]<=64<saved['models'][n][i] for i in saved['legacy_selected_indices']),
   'sharing128_veto':sum(saved['models'][LEARNED][i]<=128<saved['models'][n][i] for i in saved['sharing_selected_indices'])}
  activity_ok=activity['acceptances']>=4 and activity['templates']>=2 and activity['cap128']>=1 and activity['legacy64_veto']>=1 and activity['sharing128_veto']>=1
  checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_ok,
   'general_no_loss':passed(g['checks'][n]),'general_strict_signed':accuracy(g[CURRENT],g[n],True),
   'general_strict_fa_gain_signed':sum(g[n]['caps'][str(z)]['false_accept'] for z in CAPS)<sum(g[CURRENT]['caps'][str(z)]['false_accept'] for z in CAPS),
   'sharing_passes':passed(sharing['checks'][n]),'legacy_passes':passed(legacy['checks'][n]),'conditional_full_passes':passed(c['checks'][n]),'active_subset_passes':bool(a and passed(a['checks'][n]))}
  ok=checks['coverage']['passed'] and activity_ok and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['sharing_passes'] and checks['legacy_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes']
  gates[n]={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':ok and dev['selected_candidate']==n}
 selected=dev['selected_candidate'];return g,sharing,legacy,c,a,gates,bool(selected and gates[selected]['eligible'])

def verify_fresh(output):
 p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
 for n,d in seal['bindings'].items():need(sha(ROOT/n)==d,'Frozen fresh payload differs: '+n)
 return p,fresh


def score(output):
 p,fresh=verify_fresh(output);rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows],'Selected alignment differs');dev=read(output/'development-metrics.json')
 general,sharing,legacy,conditional,active,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),dev)
 result={'schema':SCHEMA,'models':general,'sharing_models':sharing,'legacy_models':legacy,'conditional_models':conditional,'active_subgroup':active,'gates':gates,'selection_coverage':saved['selection_coverage'],'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],'scoped_experimental_eligibility':eligible,'general_count':32,'sharing_count':8,'legacy_count':8,'conditional_count':len(saved['conditional_selected_indices']),'active_count':len(saved['active_selected_indices']),'shared_controls':8,'unique_label_count':len(rows),'fits':2,'native_jobs':0,'no_pooled_metric':True,'fresh_labels_sha256':sha(fresh/'labels.json'),'scope':p['scope']}
 write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
 p=authenticate(output);rows=read(candidates);values,routes,details=points(rows,prior.feature_matrix(rows,read(features)),load(output),read(output/'support-cells.json'));dev=read(output/'development-metrics.json');n=dev['evaluated_candidate']
 write(destination,{'schema':SCHEMA,'model':n,'selected_candidate':dev['selected_candidate'],'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':values,'predicted_lut4':values[n],'routes':routes,**details,'fits':0,'native_jobs':0,'upper_lut4':None,'calibration_status':'uncalibrated','candidates_sha256':sha(candidates),'features_sha256':sha(features),'protocol_sha256':sha(output/'protocol.json'),'scope':p['scope']})
 return {'predictions':len(rows),'new_fits':0,'native_jobs':0,'output':str(destination)}


def replay(output):
 p,fresh=verify_fresh(output);models=load(output);panels=retained_panels(models,read(output/'support-cells.json'));need(panels==read(output/'development-predictions.json'),'Developmentpoint replay differs');dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Developmentmetric replay differs')
 training=ROOT/p['training'];tr=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(tr,prior.feature_matrix(tr,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')));need(report==read(output/'feature-freshness.json'),'Featurefreshness replay differs')
 values,routes,details=points(pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')),models,read(output/'support-cells.json'));saved=read(output/'pool-predictions.json');need(values==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'Poolpoint replay differs')
 selection=choose(pool,values,report,dev['evaluated_candidate']);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,values,selection,report,dev['evaluated_candidate']),'Selection replay differs');indices=selection['selected_pool_indices'];selected=read(output/'fresh-predictions.json');need(all(selected[k]==v for k,v in point_subset(saved,indices).items()),'Selectedpoint replay differs')
 need(read(fresh/'candidates.json')==[pool[i] for i in indices],'Selectedcandidates differ');features=read(fresh/'pool-features.json');need(read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in indices]},'Selectedfeatures differ')
 scored=False
 if (output/'fresh-metrics.json').exists():
  g,sharing,legacy,c,a,gates,eligible=score_values(selected,prior.labels_for(read(fresh/'candidates.json'),read(fresh/'labels.json')),dev);result=read(output/'fresh-metrics.json');need(g==result['models'] and sharing==result['sharing_models'] and legacy==result['legacy_models'] and c==result['conditional_models'] and a==result['active_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Freshmetric replay differs');scored=True
 return {'status':'pass','retained_metric_rows':992,'retained_unique_circuits':968,'pool_rows':128,'selected_rows':len(indices),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-features','run','freeze-selection','score','predict-cached','replay'));parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--training',type=Path,default=TRAIN);parser.add_argument('--fresh',type=Path,default=FRESH);parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
 a=parser.parse_args();out=a.output.resolve()
 if a.command=='prepare':result=prepare(out,a.training.resolve(),a.fresh.resolve())
 elif a.command=='predict-cached':
  need(all((a.candidates,a.features,a.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,a.candidates,a.features,a.prediction_output)
 else:result={'freeze-features':freeze_features,'run':run,'freeze-selection':freeze_selection,'score':score,'replay':replay}[a.command](out)
 print(json.dumps(result,indent=2))

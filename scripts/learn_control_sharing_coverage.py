#!/usr/bin/env python3
"""One fixed233 feasibility classifier with prospective control/sharing coverage."""
from __future__ import annotations
import argparse,json,platform,signal,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import learn_boundary_feasibility as baseline
local,prior,incumbent=baseline.local,baseline.prior,baseline.incumbent
read,write,sha,need,now=baseline.read,baseline.write,baseline.sha,baseline.need,baseline.now
SCHEMA='isaforge-control-sharing-coverage-v1'
NAME=PRIMARY='control_sharing_coverage';CANDIDATES=(NAME,);KINDS={NAME:'augmented'}
CURRENT,BUDGET=baseline.CURRENT,baseline.BUDGET
STRUCTURAL,LEARNED,ABSTENTION=baseline.STRUCTURAL,baseline.LEARNED,baseline.ABSTENTION
FROZEN_BASELINE=PREVIOUS=baseline.PRIMARY
REFERENCES=baseline.REFERENCES
NAMES=(*baseline.NAMES,NAME);CAPS=baseline.CAPS
OUT=ROOT/'results/control-sharing-coverage';TRAIN=ROOT/'results/control-sharing-coverage-data';FRESH=ROOT/'results/control-sharing-coverage-validation'
PROB_TOL=baseline.PROB_TOL;PARAMETERS=baseline.PARAMETERS
VALIDATED_PANELS=('consumed-twelfth-general32','consumed-twelfth-legacy8')
POLICY={'scope':baseline.POLICY['scope'],'support':'Same-chain formula-only width/sharing cells from frozen1889+new32 training formulas; every eligible chain must be supported. Allfour cells already represented before intervention.',
 'decision':baseline.POLICY['decision'],'bounds':baseline.POLICY['bounds'],'baseline_limits':baseline.POLICY['baseline_limits'],'targets':baseline.POLICY['targets'],'class_mapping':baseline.POLICY['class_mapping'],
 'configuration':PARAMETERS,'planned_fits':1,'training':'One fixed233 native multioutput classifier on exactly frozen1889+32 genuinely new training rows=1921. No consumed evaluation labels fitted. No feature, threshold, seed, weight or parameter change.',
 'comparison':'Reuse frozen1889-row feasibility_augmented as zero-fit baseline. No refit of baseline and no217representation ablation. This intervention changes training coverage only, within the fixed algorithm/columns/rule.',
 'selection':'Select the single new candidate only if all development gates pass; otherwise selectnone and retain it as diagnostic. No postfreshlabel switch.',
 'validated_baseline_preservation':'Existing six comparators apply everywhere. The latest passing classifier is an additional MAE/MAPE/tail comparator only on retained latestgeneral32/latestlegacy8 and freshgeneral32/freshlegacy8; not on its unsafe active subgroup.',
 'interpretation':'Synthetic coverage-transfer experiment, uncalibrated probabilities, no cost-mechanism or universal safety/CPU guarantee.'}
GATES={'retained':'All26panels1113metricrows/1073records(shared40controls), every inheritednamed group, expandedrequiredtargets. Existing six accuracy/tail comparators unchanged, FA<=release FR<=signed separately32/64/128, zero newcase mistakes, signed<=candidate<=release.',
 'validated_gains':'Preserve frozen feasibility_augmented MAE/MAPE/tail on retained latestgeneral32/latestlegacy8 and prospective freshgeneral32/freshlegacy8. Do not add this failed model as an accuracy comparator on its unsafe active8.',
 'general':'Completefreshgeneral32 strict MAE/positiveMAPE and totalFA-event gainsvssigned plusallhardgates. PositiveMAPE=100*mean(abs(y-p)/y) over y>0; zero targets retained in MAE/cap/tail.',
 'other_fresh':'Sharing8,legacy8,conditional-full(active+SAME8generalcontrols),active-only separatelypasshardgates; no pooling/independenceclaim.',
 'activity':'Atleast4newacceptances versus frozen feasibility_augmented across>=2templatesincluding128, legacy64veto oldabstention>=1, sharing128veto oldlearned217>=1; prediction-defined, truth checkedafterlabels.',
 'missing':'All32train+96pool inputs/features/points retained. Fixed48alwayslabelled thenup16actions. Onefit only, no retries/replacements/extensions/extra variants or postlabel feature/rule/gatechanges.',
 'tolerance':1e-10,'probability_roundoff_tolerance':PROB_TOL}

def runtime_versions():
 import sklearn,joblib
 return {'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}

def source_hashes():
 paths=[Path(__file__),ROOT/'tests/test_learn_control_sharing_coverage.py',ROOT/'scripts/learn_boundary_feasibility.py',ROOT/'scripts/boundary_carry_features.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 return {prior.relative(p):sha(p) for p in paths}


def columns(kind='augmented'):return baseline.columns(kind)
def inputs(rows,x,kind='augmented'):return baseline.inputs(rows,x,kind)
def cells(formula):return baseline.cells(formula)
def derive_support(formulas):return baseline.derive_support(formulas)
def accuracy(reference,candidate,strict=False):return baseline.accuracy(reference,candidate,strict)
def positive_probabilities(model,x):return baseline.positive_probabilities(model,x)
def budget_support(signed,release,probabilities,scope):return baseline.budget_support(signed,release,probabilities,scope)

def points(rows,x,models,support,old_payload=None):
 if old_payload is None:values,routes,details=baseline.points(rows,x,baseline.load(baseline.OUT),read(baseline.OUT/'support-cells.json'))
 else:
  values={n:list(v) for n,v in old_payload['models'].items()};routes=old_payload['routes'];details={k:v for k,v in old_payload.items() if k not in ('candidate_ids','formulas','actual_lut4','models','routes')}
 chain_cells=[cells(r['formula']) for r in rows];known=set(support['supported_cells']);scope=[bool(v) and all(c in known for c in v) for v in chain_cells]
 probabilities={};caps={}
 for name in CANDIDATES:
  probabilities[name]=positive_probabilities(models[KINDS[name]],inputs(rows,x,KINDS[name])).tolist();values[name],caps[name]=budget_support(values[CURRENT],values[BUDGET],probabilities[name],scope)
 return values,routes,{**details,'coverage_cells':chain_cells,'coverage_covered':scope,'coverage_feasibility_probabilities':probabilities,'coverage_supported_caps':caps}

def panel_metrics(row,preserve_validated_baseline=False):
 y=row['actual_lut4'];v=row['models'];refs=(*REFERENCES,FROZEN_BASELINE) if preserve_validated_baseline else REFERENCES;m={n:prior.model_metrics(v[n],y) for n in NAMES};checks={}
 for n in CANDIDATES:
  checks[n]={'accuracy_no_worse':{r:accuracy(m[r],m[n]) for r in refs},
   'caps':{str(c):{'false_accept_no_worse_release':m[n]['caps'][str(c)]['false_accept']<=m[BUDGET]['caps'][str(c)]['false_accept'],
    'false_reject_no_worse_signed':m[n]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject'],
    'no_new_false_accept_cases':not any(v[n][i]<=c<v[BUDGET][i] and y[i]>c for i in range(len(y))),
    'no_new_false_reject_cases':not any(v[CURRENT][i]<=c<v[n][i] and y[i]<=c for i in range(len(y)))} for c in CAPS},
   'maximum_underprediction_no_worse':all(m[n]['maximum_underprediction_lut4']<=m[r]['maximum_underprediction_lut4']+GATES['tolerance'] for r in (*refs,CURRENT)),
   'pointwise_bounds':bool(np.all(np.asarray(v[n])>=np.asarray(v[CURRENT])) and np.all(np.asarray(v[n])<=np.asarray(v[BUDGET]))),
   'events':{r:incumbent.boundary.release.cap_events(v[r],v[n],y) for r in (*refs,CURRENT)}}
 m['checks']=checks
 if 'coverage_feasibility_probabilities' in row:
  m['probability_metrics']={n:{str(c):{'brier_score':float(np.mean((np.asarray(row['coverage_feasibility_probabilities'][n])[:,j]-(np.asarray(y)<=c))**2)),
   'raw_probability_decision_errors':int(np.sum((np.asarray(row['coverage_feasibility_probabilities'][n])[:,j]>=.5)!=(np.asarray(y)<=c)))} for j,c in enumerate(CAPS)} for n in CANDIDATES}
 return m

def passed(c):return baseline.passed(c)

def subset(row,indices,preserve_validated_baseline=False):
 need(bool(indices),'Empty required subgroup')
 return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],'models':{n:[row['models'][n][i] for i in indices] for n in NAMES},
  **({'coverage_feasibility_probabilities':{n:[row['coverage_feasibility_probabilities'][n][i] for i in indices] for n in CANDIDATES}} if 'coverage_feasibility_probabilities' in row else {})},preserve_validated_baseline)

def template_group(row,folder,template):
 indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template];need(len(indices)==4,'Exact named4 required')
 return subset(row,indices)

def panel_inputs():
 yield from baseline.panel_inputs()
 rows=read(baseline.FRESH/'candidates.json');x=prior.feature_matrix(rows,read(baseline.FRESH/'features.json'));y=prior.labels_for(rows,read(baseline.FRESH/'labels.json'));saved=read(baseline.OUT/'fresh-predictions.json')
 for name,key in [('consumed-twelfth-general32','general_selected_indices'),('consumed-twelfth-sharing8','sharing_selected_indices'),('consumed-twelfth-legacy8','legacy_selected_indices'),('consumed-twelfth-conditional16','conditional_selected_indices')]:
  ix=saved[key];yield name,([rows[i] for i in ix],x[ix,:],[y[i] for i in ix])

def retained_panels(models,support):
 old=read(baseline.OUT/'development-predictions.json');fresh=read(baseline.OUT/'fresh-predictions.json');rows=read(baseline.FRESH/'candidates.json');y=prior.labels_for(rows,read(baseline.FRESH/'labels.json'))
 for name,key in [('consumed-twelfth-general32','general_selected_indices'),('consumed-twelfth-sharing8','sharing_selected_indices'),('consumed-twelfth-legacy8','legacy_selected_indices'),('consumed-twelfth-conditional16','conditional_selected_indices')]:
  ix=fresh[key];old[name]={**baseline.point_subset(fresh,ix),'actual_lut4':[y[i] for i in ix]}
 result={}
 for name,(rows,x,y) in panel_inputs():
  cached=old[name];need(cached['formulas']==[r['formula'] for r in rows],'Cached comparator alignment differs')
  v,routes,details=points(rows,x,models,support,cached);result[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':y,'models':v,'routes':routes,**details}
 return result

def development_metrics(panels):
 metrics={n:panel_metrics(row,n in VALIDATED_PANELS) for n,row in panels.items()};targets=read(OUT/'evaluation-targets.json');previous_targets=read(baseline.OUT/'evaluation-targets.json');original=read(baseline.baseline.OUT/'evaluation-targets.json');accept=targets['required_acceptances'];reject=targets['required_rejections']
 need(len(accept)==targets['required_acceptances_count'] and len(reject)==targets['required_rejections_count'],'Expanded evaluation inventory differs')
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
 named['established39']=targets_metric(original['established_repairs']);named['remaining_fr4']=targets_metric(original['remaining_fr_targets']);named['protected_rejections6']=targets_metric(original['required_rejections']);named['expanded_acceptances']=targets_metric(previous_targets['required_acceptances']);named['expanded_rejections']=targets_metric(previous_targets['required_rejections'])
 named['latest_active1']=subset(panels['consumed-eleventh-conditional9'],[0])
 latest_accept=[r for r in previous_targets['required_acceptances'] if r['origin_group'].startswith('latest49')];latest_reject=[r for r in previous_targets['required_rejections'] if r['origin_group'].startswith('latest49')]
 corrected=[r for r in latest_accept if any(r['previous_points_lut4'][n]<=r['cap'] for n in baseline.baseline.CANDIDATES)]
 missing=[r for r in latest_accept if r not in corrected];core=[r for r in latest_reject if r['core_protected_rejection']];other=[r for r in latest_reject if not r['core_protected_rejection']]
 for key,items in [('latest_required_acceptances7',latest_accept),('latest_corrected_cases5',corrected),('latest_remaining_false_rejections2',missing),('latest_core_rejections4',core),('latest_other_rejections13',other)]:
  need(bool(items),'Expanded named subgroup missing:'+key);named[key]=targets_metric(items)
 named['latest_general32_validated_gain']=metrics['consumed-twelfth-general32'];named['latest_legacy8_validated_gain']=metrics['consumed-twelfth-legacy8']
 named['latest_active8']=subset(panels['consumed-twelfth-conditional16'],list(range(8)))
 active=panels['consumed-twelfth-conditional16'];safe=[i for i in range(8) if active['actual_lut4'][i]<=128];unsafe=[i for i in range(8) if active['actual_lut4'][i]>128]
 need(len(safe)==5 and len(unsafe)==3,'Latest5safe/3unsafe activity differs');named['latest_active_safe5']=subset(active,safe);named['latest_active_unsafe3']=subset(active,unsafe)
 sharing=panels['consumed-twelfth-sharing8'];sharing_ix=[i for i,y in enumerate(sharing['actual_lut4']) if y<=128<sharing['models'][FROZEN_BASELINE][i] and sharing['models'][CURRENT][i]<=128]
 need(len(sharing_ix)==1 and sharing['actual_lut4'][sharing_ix[0]]==125,'Latestsharing125 differs');named['latest_sharing_fr125']=subset(sharing,sharing_ix)
 named['all_required_acceptances']=targets_metric(accept);named['all_required_rejections']=targets_metric(reject)
 gates={};decision_cases=[]
 for item in [*accept,*reject]:
  row,i=lookup[item['candidate_id']];need(row['actual_lut4'][i]==item['actual_lut4'],'Frozen evaluation target differs')
  decision_cases.append({**{k:item[k] for k in ('candidate_id','formula','actual_lut4','cap')},'expected':'accept' if item in accept else 'reject','predictions':{n:row['models'][n][i] for n in CANDIDATES}})
 for n in CANDIDATES:
  all_accept=all(lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]]<=r['cap'] for r in accept)
  all_reject=all(lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]]>r['cap'] for r in reject)
  c={'all_twenty_six_panels_pass':all(passed(m['checks'][n]) for m in metrics.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_required_acceptances_pass':all_accept,'all_required_rejections_pass':all_reject}
  c['development_gate_passed']=all(c.values());gates[n]=c
 selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
 return {'panels':metrics,'named_regressions':named,'evaluation_cases':decision_cases,'gates':gates,'selected_candidate':selected,'evaluated_candidate':selected or PRIMARY,'all_panels_consumed':True,'independent_test':False,'retained_metric_rows':1113,'retained_circuit_records':1073,'shared_controls':40,'no_pooled_metric':True}

def historical_feature_paths():return baseline.historical_feature_paths()+[baseline.FRESH/'features.json',baseline.FRESH/'pool-features.json']

def historical_records():
 formulas,x=baseline.historical_records();blocks=[x]
 for path in (baseline.FRESH/'features.json',baseline.FRESH/'pool-features.json'):
  p=read(path);pos=[p['columns'].index(n) for n in prior.v6.mapping_columns()];blocks.append(np.asarray([r['values'] for r in p['records']])[:,pos]);formulas.extend(r['formula'] for r in p['records'])
 x=np.vstack(blocks);need(x.shape==(3802,217) and len(formulas)==3802,'3802 historical rows required');return formulas,x

def feature_freshness(training_rows,tx,pool_rows,px):
 formulas,h=historical_records();haug=np.hstack([h,np.asarray([local.features(f) for f in formulas])]);reports={}
 for kind,history in [('coverage',h),('augmented',haug)]:
  known={tuple(float(v) for v in row) for row in history};t=inputs(training_rows,tx,kind);train_keys=[tuple(float(v) for v in row) for row in t];allknown=known|set(train_keys);p=inputs(pool_rows,px,kind);keys=[tuple(float(v) for v in row) for row in p];clusters={};reps=[]
  for i,key in enumerate(keys):clusters.setdefault(key,[]).append(i);reps.append(clusters[key][0])
  reports[kind]={'historical_unique_count':len(known),'training_historical_matches':[i for i,k in enumerate(train_keys) if k in known],'training_unique_count':len(set(train_keys)),'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in allknown],'pool_cluster_representatives':reps,'pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1]}
 return {'historical_rows':3802,'fitted_rows':1889,'unique_consumed_labels':1073,'prior_pool_rows':[200,128,128,128,128,128],'representations':reports,'training_fresh':all(not v['training_historical_matches'] and v['training_unique_count']==32 for v in reports.values()),'equality':'Exactfloat64 tuples; no rounding or target labels.'}


def training_data(training):
 manifest=read(baseline.OUT/'training-manifest.json')['rows']
 with np.load(baseline.OUT/'training-inputs.npz',allow_pickle=False) as d:x={k:d[k].copy() for k in ('coverage','augmented')};y=d['y'].copy()
 need(len(manifest)==1889 and x['coverage'].shape==(1889,217) and x['augmented'].shape==(1889,233),'Exactfrozen1889base required')
 new=read(training/'candidates.json');nx=prior.feature_matrix(new,read(training/'features.json'));ny=np.asarray(prior.labels_for(new,read(training/'labels.json')))
 need(len(new)==32,'Exactly32newtraining required');rows=[{'candidate_id':r['candidate_id'],'formula':r['formula'],'actual_lut4':float(y[i]),'fit_source':'frozen1889'} for i,r in enumerate(manifest)]
 rows +=[{'candidate_id':r['candidate_id'],'formula':r['formula'],'actual_lut4':float(ny[i]),'fit_source':'new_training32'} for i,r in enumerate(new)]
 x={k:np.vstack([v,inputs(new,nx,k)]) for k,v in x.items()};y=np.concatenate([y,ny]);labels=(y[:,None]<=np.asarray(CAPS)[None,:]).astype(np.uint8)
 need(x['augmented'].shape==(1921,233) and np.array_equal(x['coverage'],x['augmented'][:,:217]) and y.shape==(1921,),'Matched1921matrixcontract differs')
 return rows,x,y,labels

def authenticate(output):
 p=read(output/'protocol.json');need(p['schema']==SCHEMA and p['policy']==POLICY and p['gates']==GATES and p['local_features']==local.SCHEMA,'Frozen feasibility protocol differs')
 need(p['sources_sha256']==source_hashes() and p['runtime_versions']==runtime_versions(),'Frozen source/runtime differs')
 for n,d in p['inputs_sha256'].items():need(sha(ROOT/n)==d,'Input differs:'+n)
 return p

def prepare(output,training,fresh):
 need(not (output/'protocol.json').exists(),'Protocol already frozen')
 for folder in (training,fresh):
  for n in ('pool-features.json','features.json','feature-attempt.json','labels.json','label-attempt.json','selection.json'):need(not (folder/n).exists(),'Freeze before features/labels/attempts')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');need(len(t)==32 and len(pool)==96 and all(read(f/'novelty.json')['status']=='pass' for f in (training,fresh)),'Frozen novel32+96 required')
 manifest=read(baseline.OUT/'training-manifest.json')['rows'];support=derive_support([r['formula'] for r in manifest]+[r['formula'] for r in t]);need(support['training_formula_count']==1921,'1921formula support required');write(output/'support-cells.json',support)
 goals=[('results/boundary-repair-goal.json','goal-at-freeze.json'),('results/boundary-repair-goal-update.json','goal-update-at-freeze.json'),('results/research-goal-current.json','research-goal-current-at-freeze.json')]
 for source,target in goals:write(output/target,read(ROOT/source))
 targets=read(output/'evaluation-targets.json');counts={**read(baseline.OUT/'protocol.json')['retained_panels'],'consumed-twelfth-general32':32,'consumed-twelfth-sharing8':8,'consumed-twelfth-legacy8':8,'consumed-twelfth-conditional16':16}
 paths=[output/n for n in ('support-cells.json','evaluation-targets.json','method-rationale.json','prior-coverage-diagnosis.json','analytical-feasibility-review.json','measurement-input-profile-audit.json','input-family-revision-v1.json','prefreeze-family-review.json','rejected-joint-inputs-v1.json','rejected-measurement-input-draft-v1.py','prefreeze-audit-source-v1.py','preregistration.md','goal-at-freeze.json','goal-update-at-freeze.json','research-goal-current-at-freeze.json')]+historical_feature_paths()
 paths+=[baseline.OUT/n for n in ('protocol.json','model-freeze.json','training-inputs.npz','training-manifest.json','evaluation-targets.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json','audit.json','policy-limitations.json','next-experiment-hypothesis.json')]
 paths+=[baseline.FRESH/n for n in ('candidates.json','features.json','labels.json','pool-candidates.json','pool-features.json','plan.json')]+[training/n for n in ('candidates.json','novelty.json','plan.json')]+[fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
 p={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),'policy':POLICY,'gates':GATES,'local_features':local.SCHEMA,'planned_fits':1,'maximum_fits':1,'maximum_fit_seconds':120,'fit_threads':1,'total_training_rows':1921,'new_training_labels':32,'consumed_labels_fitted':0,'columns':columns(),'base_columns':columns('coverage'),'retained_panels':counts,'validated_baseline_panels':list(VALIDATED_PANELS),'validated_baseline_fresh_populations':['general32','legacy8'],
  'required_acceptance_count':targets['required_acceptances_count'],'required_rejection_count':targets['required_rejections_count'],'sample_weight':None,'configuration_all_parameters':__import__('sklearn.ensemble',fromlist=['ExtraTreesClassifier']).ExtraTreesClassifier(**PARAMETERS).get_params(),
  'selection':{'general_count':32,'sharing_count':8,'legacy_count':8,'challenge_count':48,'shared_controls':8,'maximum_active':16,'minimum_active':4,'minimum_templates':2,'requires_cap128':True,'active_comparator':PREVIOUS,'legacy64_veto_comparator':ABSTENTION,'sharing128_veto_comparator':LEARNED,
   'order':'Fixed48 then sortedtemplate roundrobin originalindexorder; exclude history/training/fixed/selected collisions in either217/233. No replacement, extension, quotas or label filtering.','populations':'General/sharing/legacy/conditional-full(active+SAME8generalcontrols)/active-only separatelygated; no pooledmetric or independenceclaim.'},
  'execution_prerequisites':'Independent exactprotocol preflight, joint feature/freshness freeze and pretrain receipt, training32labels, then exactprotocol parent execution-authorization.json allow_one_classifier_fit=true and bindings for training labels/features/completion; authenticate every receipt binding before fit; freshlabels only after allpoint/selection freeze and independentprelabel.',
  'goal_sources_sha256':{source:sha(ROOT/source) for source,target in goals},'runtime_versions':runtime_versions(),'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(q):sha(q) for q in paths},'scope':'Single synthetic iCE40LUT4 coverage intervention; no calibrated risk, application/CPU/timing/power or universal safety guarantee.'}
 write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0,'native_jobs':0}


def freeze_features(output):
 p=authenticate(output);training=ROOT/p['training'];fresh=ROOT/p['fresh'];need(not (training/'labels.json').exists() and not (training/'label-attempt.json').exists() and not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Freeze before any newlabels')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(t,prior.feature_matrix(t,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')));write(output/'feature-freshness.json',report)
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'training_fresh':report['training_fresh'],'bindings':{prior.relative(q):sha(q) for q in (training/'features.json',fresh/'pool-features.json',output/'feature-freshness.json')}};write(output/'feature-freeze.json',seal);return seal

def validate_execution_approval(output,training):
 protocol_sha=sha(output/'protocol.json');approval=read(output/'execution-authorization.json')
 need(approval['protocol_sha256']==protocol_sha and approval['allow_one_classifier_fit'] is True and approval['authorizer']=='parent','Parent protocol-specific approval required')
 audit=read(training/'preflight-audit.json')
 need(audit['status']=='pass' and audit['bindings'].get(prior.relative(output/'protocol.json'))==protocol_sha,'Independent approval must bind this exact protocol')
 pretrain=read(training/'pretrain-audit.json');need(pretrain['status']=='pass' and pretrain['bindings'].get(prior.relative(output/'protocol.json'))==protocol_sha,'Independent pretrain approval must bind this exact protocol')
 for receipt in (audit,pretrain,approval):
  for path,digest in receipt.get('bindings',{}).items():need(sha(ROOT/path)==digest,'Execution receipt binding changed:'+path)
 for filename in ('labels.json','features.json','completion.json'):
  path=training/filename;need(approval.get('bindings',{}).get(prior.relative(path))==sha(path),'Parent fit approval must bind training '+filename)
 return approval,audit

def validate_feature_freeze(output):
 feature=read(output/'feature-freeze.json');need(feature['protocol_sha256']==sha(output/'protocol.json'),'Fresh-feature freeze must precede fits')
 for path,digest in feature['bindings'].items():need(sha(ROOT/path)==digest,'Frozen fresh feature differs:'+path)
 return feature

def run(output):
 from sklearn.ensemble import ExtraTreesClassifier
 from threadpoolctl import threadpool_limits
 import joblib
 p=authenticate(output);fresh=ROOT/p['fresh'];training=ROOT/p['training'];need(not (output/'run-start.json').exists(),'Single one-fit stage only')
 need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Fresh labels unavailable')
 validate_execution_approval(output,training)
 feature=validate_feature_freeze(output);need(feature['training_fresh'],'Novel training features required')
 manifest,x,y,labels=training_data(training);write(output/'training-manifest.json',{'schema':SCHEMA,'rows':manifest,'consumed_evaluation_labels_fitted':0,'new_training_labels':32})
 need(not (output/'training-inputs.npz').exists(),'Training matrices already exist');np.savez_compressed(output/'training-inputs.npz',coverage=x['coverage'],augmented=x['augmented'],y=y,feasibility=labels)
 write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'authorization_sha256':sha(output/'execution-authorization.json'),'independent_preflight_sha256':sha(training/'preflight-audit.json'),'planned_fits':1,'maximum_fits':1,'training_labels_sha256':sha(training/'labels.json'),'training_features_sha256':sha(training/'features.json')})
 started=time.monotonic();fits=[];models={}
 def deadline(signum,frame):raise TimeoutError('120second one-fit stage exhausted')
 handler=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120)
 try:
  with threadpool_limits(limits=1):
   for index,kind in enumerate(('augmented',),1):
    write(output/('fit-attempt-'+str(index)+'.json'),{'fit_index':index,'kind':kind,'started_at_utc':now(),'training_count':1921,'feature_count':len(columns(kind)),'training_inputs_sha256':sha(output/'training-inputs.npz'),'configuration':PARAMETERS,'sample_weight':None})
    began=time.monotonic();model=ExtraTreesClassifier(**PARAMETERS);model.fit(x[kind],labels,sample_weight=None);models[kind]=model;positive_probabilities(model,x[kind])
    fits.append({'index':index,'kind':kind,'training_count':1921,'feature_count':len(columns(kind)),'fit_seconds':time.monotonic()-began});joblib.dump(model,output/(kind+'.joblib'))
    write(output/(kind+'.json'),{'schema':SCHEMA,'kind':kind,'columns':columns(kind),'training_count':1921,'new_training_count':32,'consumed_labels_fitted':0,'configuration':PARAMETERS,'classes_by_cap':[a.tolist() for a in model.classes_],'outputs':list(CAPS),'positive_class':1,'sample_weight':None,'calibration':'uncalibrated','artifact_sha256':sha(output/(kind+'.joblib')),'protocol_sha256':sha(output/'protocol.json'),'runtime_versions':runtime_versions()})
   write(output/'timings.json',fits);panels=retained_panels(models,read(output/'support-cells.json'));write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
  names=['training-manifest.json','training-inputs.npz','fit-attempt-1.json','augmented.joblib','augmented.json','timings.json','development-predictions.json','development-metrics.json','run-start.json','execution-authorization.json']
  seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'fits_completed':1,'feature_freeze_sha256':sha(output/'feature-freeze.json'),'wall_seconds':time.monotonic()-started,'files_sha256':{n:sha(output/n) for n in names}};write(output/'model-freeze.json',seal);return seal
 except BaseException as e:write(output/'failure.json',{'error':str(e),'fits_completed':len(fits),'fit_records':fits,'maximum_fits':1,'wall_seconds':time.monotonic()-started});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)

def load(output):
 import joblib
 from sklearn.ensemble import ExtraTreesClassifier
 authenticate(output);seal=read(output/'model-freeze.json');need(seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==1,'One classifier fit seal required')
 for n,h in seal['files_sha256'].items():need(sha(output/n)==h,'Frozen classifier artifact differs:'+n)
 models={}
 for kind in ('augmented',):
  meta=read(output/(kind+'.json'));model=joblib.load(output/(kind+'.joblib'))
  need(isinstance(model,ExtraTreesClassifier) and model.get_params()==ExtraTreesClassifier(**PARAMETERS).get_params() and model.n_features_in_==len(columns(kind)) and model.n_outputs_==3 and meta['classes_by_cap']==[a.tolist() for a in model.classes_],'Exact native shared-partition classifier required');models[kind]=model
 return models

def choose(pool,values,freshness,evaluated):
 groups={c:[i for i,r in enumerate(pool) if r['cohort']==c] for c in ('general','sharing','legacy')};fixed=groups['general']+groups['sharing']+groups['legacy'];controls=[i for i,r in enumerate(pool) if r['reserved_control']]
 need(len(pool)==96 and len(groups['general'])==32 and len(groups['sharing'])==len(groups['legacy'])==8 and len(controls)==8,'Fixed96splitdiffers')
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
 legacy=[i for i in selection['legacy_pool_indices'] if values[ABSTENTION][i]<=64<values[evaluated][i]];sharing=[i for i in selection['sharing_pool_indices'] if values[LEARNED][i]<=128<values[evaluated][i]]
 checks.update({'at_least_four_new_acceptances':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1,'at_least_one_legacy64_veto':len(legacy)>=1,'at_least_one_sharing128_veto':len(sharing)>=1})
 return {'pool_count':96,'general_count':32,'sharing_count':8,'legacy_count':8,'shared_control_count':8,'raw_active_count':len(selection['raw_active_pool_indices']),'eligible_active_count':len(selection['eligible_active_pool_indices']),'selected_active_count':len(active),'selected_templates':templates,'acceptance_caps':caps,'legacy64_veto_count':len(legacy),'legacy64_veto_pool_indices':legacy,'sharing128_veto_count':len(sharing),'sharing128_veto_pool_indices':sharing,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}

def point_subset(saved,indices):
 result=baseline.point_subset(saved,indices);result['models'][NAME]=[saved['models'][NAME][i] for i in indices]
 for key in ('coverage_cells','coverage_covered'):result[key]=[saved[key][i] for i in indices]
 for key in ('coverage_feasibility_probabilities','coverage_supported_caps'):result[key]={n:[v[i] for i in indices] for n,v in saved[key].items()}
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
 row={**saved,'actual_lut4':y};g=subset(row,saved['general_selected_indices'],True);sharing=subset(row,saved['sharing_selected_indices']);legacy=subset(row,saved['legacy_selected_indices'],True);c=subset(row,saved['conditional_selected_indices']);a=subset(row,saved['active_selected_indices']) if saved['active_selected_indices'] else None;gates={}
 for n in CANDIDATES:
  active=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=z<saved['models'][PREVIOUS][i] for z in CAPS)]
  activity={'acceptances':len(active),'templates':len({saved['templates'][i] for i in active}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][PREVIOUS][i] for i in active),
   'legacy64_veto':sum(saved['models'][ABSTENTION][i]<=64<saved['models'][n][i] for i in saved['legacy_selected_indices']),
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
 result={'schema':SCHEMA,'models':general,'sharing_models':sharing,'legacy_models':legacy,'conditional_models':conditional,'active_subgroup':active,'gates':gates,'selection_coverage':saved['selection_coverage'],'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],'scoped_experimental_eligibility':eligible,'general_count':32,'sharing_count':8,'legacy_count':8,'conditional_count':len(saved['conditional_selected_indices']),'active_count':len(saved['active_selected_indices']),'shared_controls':8,'unique_label_count':len(rows),'fits':1,'native_jobs':0,'no_pooled_metric':True,'fresh_labels_sha256':sha(fresh/'labels.json'),'scope':p['scope']}
 write(output/'fresh-metrics.json',result);return result

def predict_cached(output,candidates,features,destination):
 p=authenticate(output);rows=read(candidates);values,routes,details=points(rows,prior.feature_matrix(rows,read(features)),load(output),read(output/'support-cells.json'));dev=read(output/'development-metrics.json');n=dev['evaluated_candidate']
 write(destination,{'schema':SCHEMA,'model':n,'selected_candidate':dev['selected_candidate'],'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':values,'predicted_lut4':values[n],'routes':routes,**details,'fits':0,'native_jobs':0,'upper_lut4':None,'calibration_status':'uncalibrated','candidates_sha256':sha(candidates),'features_sha256':sha(features),'protocol_sha256':sha(output/'protocol.json'),'scope':p['scope']})
 return {'predictions':len(rows),'new_fits':0,'native_jobs':0,'output':str(destination)}

def replay(output):
 p,fresh=verify_fresh(output);models=load(output);panels=retained_panels(models,read(output/'support-cells.json'));need(panels==read(output/'development-predictions.json'),'Developmentpoint replay differs');dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Developmentmetric replay differs')
 training=ROOT/p['training'];t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(t,prior.feature_matrix(t,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')));need(report==read(output/'feature-freshness.json'),'Featurefreshness replay differs')
 values,routes,details=points(pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')),models,read(output/'support-cells.json'));saved=read(output/'pool-predictions.json');need(values==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'Poolpoint replay differs')
 selection=choose(pool,values,report,dev['evaluated_candidate']);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,values,selection,report,dev['evaluated_candidate']),'Selection replay differs');indices=selection['selected_pool_indices'];selected=read(output/'fresh-predictions.json');need(all(selected[k]==v for k,v in point_subset(saved,indices).items()),'Selectedpoint replay differs')
 need(read(fresh/'candidates.json')==[pool[i] for i in indices],'Selectedcandidates differ');features=read(fresh/'pool-features.json');need(read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in indices]},'Selectedfeatures differ')
 scored=False
 if (output/'fresh-metrics.json').exists():
  g,sharing,legacy,c,a,gates,eligible=score_values(selected,prior.labels_for(read(fresh/'candidates.json'),read(fresh/'labels.json')),dev);result=read(output/'fresh-metrics.json');need(g==result['models'] and sharing==result['sharing_models'] and legacy==result['legacy_models'] and c==result['conditional_models'] and a==result['active_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Freshmetric replay differs');scored=True
 return {'status':'pass','retained_metric_rows':1113,'retained_unique_circuits':1073,'pool_rows':96,'selected_rows':len(indices),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-features','run','freeze-selection','score','predict-cached','replay'));parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--training',type=Path,default=TRAIN);parser.add_argument('--fresh',type=Path,default=FRESH);parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
 a=parser.parse_args();out=a.output.resolve()
 if a.command=='prepare':result=prepare(out,a.training.resolve(),a.fresh.resolve())
 elif a.command=='predict-cached':
  need(all((a.candidates,a.features,a.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,a.candidates,a.features,a.prediction_output)
 else:result={'freeze-features':freeze_features,'run':run,'freeze-selection':freeze_selection,'score':score,'replay':replay}[a.command](out)
 print(json.dumps(result,indent=2))

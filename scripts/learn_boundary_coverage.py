#!/usr/bin/env python3
"""Matched bounded coverage/representation learning; all evaluation is cached.

Two fixed fits share1857 training rows, differ only by16 localized AST columns.
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
import refine_boundary_coverage as incumbent
import boundary_coverage_features as local
prior=incumbent.prior
read,write,sha,need,now=prior.read,prior.write,prior.sha,prior.need,prior.now
SCHEMA='isaforge-boundary-coverage-v1'
PRIMARY='boundary_augmented'
FALLBACK='boundary_coverage_only'
CANDIDATES=(PRIMARY,FALLBACK)
KINDS={PRIMARY:'augmented',FALLBACK:'coverage'}
CURRENT,BUDGET,PREVIOUS=incumbent.CURRENT,incumbent.BUDGET,incumbent.NAME
NAMES=(*incumbent.NAMES,*CANDIDATES)
CAPS=incumbent.CAPS
OUT=ROOT/'results/boundary-coverage'
TRAIN=ROOT/'results/boundary-coverage-data'
FRESH=ROOT/'results/boundary-coverage-validation'
POLICY={'learning_scope':local.SCHEMA['learning_scope'],
 'learned_decision':'On learning scope, for each cap32/64/128 require signed<=cap<previous_structural AND newly trained RAW MEAN<=cap. Return smallest qualifying cap; otherwise previous_structural exactly. Outside scope previous_structural exactly. No margin, additional median or threshold tuning.',
 'fit_order':['augmented233','coverage217'],
 'configuration':prior.v6.FIXED_PARAMETERS,
 'selection':'First augmented233 if all development gates pass; else coverage217 if all pass; else no eligible candidate and augmented diagnostic. Both matched forests and raw metrics retained; no postfresh swap.',
 'training':'Same1825 frozen fitted rows plus32 new training, no consumed evaluation labels. Both300-tree forests fixedseed/parameters, n_jobs1 and threadpool1. Plain sklearn estimator serialization; source helpers under scripts only.',
 'scope':'Learned budget-decision support, not global point-regressor replacement or calibrated safety. Original formulas/features only; no labels/IDs/errors in prediction or local feature columns.'}
GATES={'retained':'All13 retained complete panels897 metric rows (889unique circuits;8shared controls) and every named subgroup: MAE/MAPE/tail<=release AND previous_structural; FA<=release and FR<=signed separately32/64/128; signed<=candidate<=previous_structural<=release. Explicitly repair four confident generalFR and preserve all older repairs/rejections.',
 'general':'Fixed fresh general32: strict MAE/MAPE and summed FA-event gains vs signed; MAE/MAPE/tail<=release AND previous_structural, FA<=release FR<=signed percap. All fixed general feature-novel, no filtering.',
 'conditional':'NEW learned correction activity candidate<=cap<previous_structural, >=4feature-novel selected cases/>=2templates/>=1cap128. Active-only AND conditional-full(actives+same8generalcontrols) pass no-loss accuracy/tail versus release AND previous_structural, FA<=release FR<=signed. No pooled or independence claim.',
 'missing':'No failures/retries/replacements/pool extensions/new fits/postlabel changes. All32training+128pool features retained; missing training freshness blocks fitting eligibility. Both fits attempted only in fixed order once; maximum2.',
 'tolerance':incumbent.boundary.TOLERANCE}


def runtime_versions():
 import sklearn,joblib
 return {'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}


def source_hashes():
 paths=[Path(__file__),ROOT/'scripts/boundary_coverage_features.py',ROOT/'tests/test_learn_boundary_coverage.py',ROOT/'tests/test_boundary_coverage_features.py',ROOT/'scripts/refine_boundary_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 return {prior.relative(p):sha(p) for p in paths}


def columns(kind):
 return list(prior.v6.mapping_columns())+(list(local.COLUMNS) if kind=='augmented' else [])


def inputs(rows,x,kind):
 base=x[:,prior.v6.mapping_indices()]
 return np.hstack([base,np.asarray([local.features(r['formula']) for r in rows],dtype=float)]) if kind=='augmented' else base


def budget_support(signed,previous,raw,scope):
 result=np.asarray(previous,dtype=float).copy();supported=[]
 for i,active in enumerate(scope):
  caps=[cap for cap in CAPS if active and signed[i]<=cap<previous[i] and raw[i]<=cap]
  if caps:result[i]=min(caps)
  supported.append(caps)
 return result.tolist(),supported


def points(rows,x,models,old=None):
 old=old or incumbent.previous.load(incumbent.previous.OUT)
 values,routes,details=incumbent.points(rows,x,old)
 scope=[local.learning_scope(r['formula']) for r in rows];raw={};support={}
 for name in CANDIDATES:
  kind=KINDS[name];raw[name]=models[kind].predict(inputs(rows,x,kind)).tolist()
  values[name],support[name]=budget_support(values[CURRENT],values[PREVIOUS],raw[name],scope)
 return values,routes,{**details,'learning_scope':scope,'learned_raw_lut4':raw,'learned_supported_caps_lut4':support}


def accuracy(reference,candidate,strict=False):return incumbent.boundary.accuracy(reference,candidate,strict)


def panel_metrics(row):
 y=row['actual_lut4'];values=row['models'];metrics={n:prior.model_metrics(values[n],y) for n in NAMES};checks={}
 for name in CANDIDATES:
  checks[name]={'accuracy_no_worse_release':accuracy(metrics[BUDGET],metrics[name]),'accuracy_no_worse_previous':accuracy(metrics[PREVIOUS],metrics[name]),
   'caps':{str(c):{'false_accept_no_worse_release':metrics[name]['caps'][str(c)]['false_accept']<=metrics[BUDGET]['caps'][str(c)]['false_accept'],
     'false_reject_no_worse_signed':metrics[name]['caps'][str(c)]['false_reject']<=metrics[CURRENT]['caps'][str(c)]['false_reject']} for c in CAPS},
   'maximum_underprediction_no_worse':all(metrics[name]['maximum_underprediction_lut4']<=metrics[n]['maximum_underprediction_lut4']+GATES['tolerance'] for n in (BUDGET,PREVIOUS,CURRENT)),
   'pointwise_bounds':bool(np.all(np.asarray(values[name])>=np.asarray(values[CURRENT])) and np.all(np.asarray(values[name])<=np.asarray(values[PREVIOUS])) and np.all(np.asarray(values[PREVIOUS])<=np.asarray(values[BUDGET]))),
   'events_vs_signed':incumbent.boundary.release.cap_events(values[CURRENT],values[name],y),
   'events_vs_release':incumbent.boundary.release.cap_events(values[BUDGET],values[name],y),
   'events_vs_previous':incumbent.boundary.release.cap_events(values[PREVIOUS],values[name],y)}
 metrics['checks']=checks
 if 'learned_raw_lut4' in row:metrics['raw_model_metrics']={n:prior.model_metrics(row['learned_raw_lut4'][n],y) for n in CANDIDATES}
 return metrics


def passed(check):
 return all(check['accuracy_no_worse_release'].values()) and all(check['accuracy_no_worse_previous'].values()) and all(all(v.values()) for v in check['caps'].values()) and check['maximum_underprediction_no_worse'] and check['pointwise_bounds']


def subset(row,indices):
 need(bool(indices),'Empty required subgroup')
 return panel_metrics({'actual_lut4':[row['actual_lut4'][i] for i in indices],
  'models':{n:[row['models'][n][i] for i in indices] for n in NAMES},
  **({'learned_raw_lut4':{n:[row['learned_raw_lut4'][n][i] for i in indices] for n in CANDIDATES}} if 'learned_raw_lut4' in row else {})})


def template_group(row,folder,template):
 indices=[i for i,r in enumerate(read(folder/'candidates.json')) if r['template']==template];need(len(indices)==4,'Exact named4 required')
 return subset(row,indices)


def panel_inputs():
 yield from incumbent.panel_inputs()
 rows=read(incumbent.FRESH/'candidates.json');x=prior.feature_matrix(rows,read(incumbent.FRESH/'features.json'));y=prior.labels_for(rows,read(incumbent.FRESH/'labels.json'));saved=read(incumbent.OUT/'fresh-predictions.json')
 for name,key in [('consumed-eighth-general32','general_selected_indices'),('consumed-eighth-conditional24','conditional_selected_indices')]:
  indices=saved[key];yield name,([rows[i] for i in indices],x[indices,:],[y[i] for i in indices])


def retained_panels(models):
 old=incumbent.previous.load(incumbent.previous.OUT);panels={}
 for name,(rows,x,y) in panel_inputs():
  values,routes,details=points(rows,x,models,old)
  panels[name]={'candidate_ids':[r['candidate_id'] for r in rows],'formulas':[r['formula'] for r in rows],'actual_lut4':y,'models':values,'routes':routes,**details}
 return panels


def development_metrics(panels):
 metrics={n:panel_metrics(row) for n,row in panels.items()};b=incumbent.boundary
 named={'arithmetic_stress32':metrics['arithmetic-stress'],
  'signed_dual_arithmetic4':template_group(panels['consumed-second-fresh32'],ROOT/'results/budget-preserving-validation','signed_dual_arithmetic'),
  'signed_add_boolean4':template_group(panels['consumed-third-fresh40'],ROOT/'results/guarded-revision-validation','heldout_signed_variable_add_boolean'),
  'compound_signed_add_xor4':template_group(panels['consumed-fourth-fresh40'],b.release.signed.FRESH,'heldout_compound_signed_add_xor'),
  'fifth_compound_signed_add_xor4':template_group(panels['consumed-fifth-fresh40'],b.release.FRESH,'heldout_compound_signed_add_xor'),
  'fifth_compound_signed_xordata_addxor4':template_group(panels['consumed-fifth-fresh40'],b.release.FRESH,'heldout_compound_signed_xordata_addxor')}
 broad_rows=read(b.FRESH/'candidates.json');named['broad_compound32']=subset(panels['consumed-sixth-broad40'],[i for i,r in enumerate(broad_rows) if b.release.signed.route(r['formula'])['compound']])
 latest=panels['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(latest['actual_lut4']) if y<=128<latest['models'][BUDGET][i]]
 fa=[i for i,y in enumerate(latest['actual_lut4']) if any(latest['models'][incumbent.BROAD][i]<=c<latest['models'][BUDGET][i] and y>c for c in CAPS)]
 need(len(fr)==8 and len(fa)==2,'Known8FR/2FA mapping differs');named['eight_corrected_fr']=subset(latest,fr);named['two_previous_new_fa']=subset(latest,fa)
 general=panels['consumed-eighth-general32'];four=[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][PREVIOUS][i]]
 need(len(four)==4,'Exact4 confident errors required');named['four_confident_fr']=subset(general,four)
 named['prior_active16']=subset(panels['consumed-eighth-conditional24'],list(range(16)))
 required=[]
 def add_cases(panel,indices,group):
  row=panels[panel]
  for i in indices:required.append({'group':group,'candidate_id':row['candidate_ids'][i],'formula':row['formulas'][i],'actual_lut4':row['actual_lut4'][i],'cap':128,'predictions':{n:row['models'][n][i] for n in CANDIDATES}})
 add_cases('consumed-fifth-fresh40',[12],'original125')
 add_cases('consumed-seventh-conditional18',fr,'later_eight')
 add_cases('consumed-eighth-general32',[i for i,y in enumerate(general['actual_lut4']) if y<=128<general['models'][BUDGET][i]],'general_five')
 add_cases('consumed-eighth-conditional24',list(range(16)),'active_sixteen')
 need(len(required)==30 and len({r['candidate_id'] for r in required})==30,'Exact30 unique required repairs')
 gates={} 
 for n in CANDIDATES:
  original=panels['consumed-fifth-fresh40']['models'][n][12]<=128
  decision=original and all(latest['models'][n][i]<=128 for i in fr) and all(latest['models'][n][i]>c for i in fa for c in CAPS if latest['models'][incumbent.BROAD][i]<=c<latest['models'][BUDGET][i] and latest['actual_lut4'][i]>c) and all(general['models'][n][i]<=128 for i in four)
  outside=all(row['models'][n][i]==row['models'][PREVIOUS][i] for row in panels.values() for i,active in enumerate(row['learning_scope']) if not active)
  check={'all_thirteen_retained_panels_pass':all(passed(m['checks'][n]) for m in metrics.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_explicit_decision_repairs_pass':decision,'all_thirty_required_rejections_repaired':all(r['predictions'][n]<=r['cap'] for r in required),'outside_learning_scope_exact_previous':outside}
  check['development_gate_passed']=all(check.values());gates[n]=check
 selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None)
 return {'panels':metrics,'named_regressions':named,'required_rejection_cases':required,'gates':gates,'selected_candidate':selected,'evaluated_candidate':selected or PRIMARY,
  'all_panels_consumed':True,'independent_test':False,'metric_rows':897,'unique_consumed_circuits':889,'shared_controls':8,'no_pooled_metric':True}


def historical_feature_paths():return incumbent.historical_feature_paths()+[incumbent.FRESH/'features.json',incumbent.FRESH/'pool-features.json']


def historical_records():
 cols=read(ROOT/'results/feature-comparison/columns.json');rows=read(ROOT/'results/feature-comparison/rows.json')
 with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:blocks=[data['x'][:,[cols.index(n) for n in prior.v6.mapping_columns()]]]
 formulas=[r['formula'] for r in rows]
 for path in historical_feature_paths()[2:]:
  payload=read(path);positions=[payload['columns'].index(n) for n in prior.v6.mapping_columns()];blocks.append(np.asarray([r['values'] for r in payload['records']])[:,positions]);formulas.extend(r['formula'] for r in payload['records'])
 matrix=np.vstack(blocks);need(matrix.shape==(3042,217) and len(formulas)==3042,'3042 historical rows required')
 return formulas,matrix


def feature_freshness(training_rows,tx,pool_rows,px):
 formulas,h=historical_records();haug=np.hstack([h,np.asarray([local.features(f) for f in formulas])]);t={k:inputs(training_rows,tx,k) for k in ('coverage','augmented')};pool={k:inputs(pool_rows,px,k) for k in ('coverage','augmented')};reports={}
 for kind,history in [('coverage',h),('augmented',haug)]:
  known={tuple(float(v) for v in row) for row in history};train_keys=[tuple(float(v) for v in row) for row in t[kind]];both=known|set(train_keys);keys=[tuple(float(v) for v in row) for row in pool[kind]];clusters={};reps=[]
  for i,key in enumerate(keys):clusters.setdefault(key,[]).append(i);reps.append(clusters[key][0])
  reports[kind]={'historical_unique_count':len(known),'training_historical_matches':[i for i,k in enumerate(train_keys) if k in known],
   'training_unique_count':len(set(train_keys)),'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in both],
   'pool_cluster_representatives':reps,'pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1]}
 return {'historical_rows':3042,'fitted_rows':1825,'unique_consumed_labels':889,'prior_pool_rows':[200,128],
  'representations':reports,'training_fresh':all(not r['training_historical_matches'] and r['training_unique_count']==32 for r in reports.values()),
  'equality':'Exact float64 numeric tuples; no rounding, no labels.'}


def authenticate(output):
 p=read(output/'protocol.json');need(p['schema']==SCHEMA and p['policy']==POLICY and p['gates']==GATES and p['local_features']==local.SCHEMA,'Frozen coverage protocol differs');need(p['sources_sha256']==source_hashes(),'Source differs');need(p['runtime_versions']==runtime_versions(),'Frozen runtime differs')
 for n,d in p['inputs_sha256'].items():need(sha(ROOT/n)==d,'Input differs: '+n)
 incumbent.load(incumbent.OUT);return p


def prepare(output,training,fresh):
 need(not (output/'protocol.json').exists(),'Protocol already frozen')
 for d in (training,fresh):
  for n in ('features.json','pool-features.json','feature-attempt.json','labels.json','label-attempt.json'):need(not (d/n).exists(),'Freeze before features/labels')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');need(len(t)==32 and len(pool)==128,'Exact32+128 required')
 for d in (training,fresh):need(read(d/'novelty.json')['status']=='pass','Novelty failed')
 need(all(local.learning_scope(r['formula']) for r in t),'Training outside declared learning scope')
 goal=ROOT/'results/boundary-repair-goal.json';write(output/'goal-at-freeze.json',read(goal))
 goal_update=ROOT/'results/boundary-repair-goal-update.json';write(output/'goal-update-at-freeze.json',read(goal_update))
 paths=[output/'goal-at-freeze.json',output/'goal-update-at-freeze.json',output/'input-coverage-audit.json',ROOT/'results/feature-comparison/rows.json']+historical_feature_paths()
 for folder in ('targeted-coverage-data','guarded-revision-data','signed-refinement-data','budget-release-data'):paths += [ROOT/'results'/folder/n for n in ('candidates.json','features.json','labels.json')]
 paths += [incumbent.OUT/n for n in ('protocol.json','policy-freeze.json','development-predictions.json','development-metrics.json','fresh-predictions.json','fresh-metrics.json')]
 paths += [training/n for n in ('candidates.json','novelty.json','plan.json')]+[fresh/n for n in ('pool-candidates.json','novelty.json','plan.json')]
 counts={**read(incumbent.OUT/'protocol.json')['retained_panels'],'consumed-eighth-general32':32,'consumed-eighth-conditional24':24}
 p={'schema':SCHEMA,'frozen_at_utc':now(),'training':prior.relative(training),'fresh':prior.relative(fresh),'policy':POLICY,'gates':GATES,'local_features':local.SCHEMA,
  'planned_fits':2,'maximum_fits':2,'maximum_fit_seconds':120,'fit_threads':1,'total_training_rows':1857,'consumed_labels_fitted':0,
  'base_columns':list(prior.v6.mapping_columns()),'augmented_columns':columns('augmented'),'retained_panels':counts,
  'selection':{'general_count':32,'shared_controls':8,'challenge_count':96,'maximum_active':16,'minimum_active':4,'minimum_templates':2,'requires_cap128':True,
   'active':'evaluated learned candidate<=cap<previous_structural on a physicalcap, not inherited correction vsrelease',
   'order':'Fixed general32 first. Exclude challenge historical/training/general217 or233 matches, then sorted-template round-robin originalpoolorder with one per cluster in BOTH representations; append up16active. Generalhistorical/train/within-general matches block eligibility withoutreplacement.',
   'missing':'No pool extension, quota filling, retry, replacement or label-based selection. Conditional-full uses active+same8fixedgeneralcontrols; active-only separate; no pooled metric.'},
  'goal_source_sha256':sha(goal),'goal_update_source_sha256':sha(goal_update),'runtime_versions':runtime_versions(),'scope':'Fixed freshgeneral32 and separate learned-correction challenge,8sharedcontrols, no population/independence/pooling claim. Uncalibrated isolatediCE40 LUT4 decision heuristic.',
  'sources_sha256':source_hashes(),'inputs_sha256':{prior.relative(x):sha(x) for x in paths}}
 write(output/'protocol.json',p);return {'protocol_sha256':sha(output/'protocol.json'),'new_fits':0}


def freeze_features(output):
 p=authenticate(output);training=ROOT/p['training'];fresh=ROOT/p['fresh'];need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(),'Feature receipt before new labels')
 t=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(t,prior.feature_matrix(t,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')))
 write(output/'feature-freshness.json',report);paths=[training/'features.json',fresh/'pool-features.json',output/'feature-freshness.json']
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'training_fresh':report['training_fresh'],'bindings':{prior.relative(x):sha(x) for x in paths}}
 write(output/'feature-freeze.json',seal);return seal


def training_data(training):
 cols=read(ROOT/'results/feature-comparison/columns.json');rows=read(ROOT/'results/feature-comparison/rows.json')
 with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:x=[data['x'][:,[cols.index(n) for n in prior.v6.columns()]]];y=[data['y']]
 for d,count in [(ROOT/'results/targeted-coverage-data',64),(ROOT/'results/guarded-revision-data',32),(ROOT/'results/signed-refinement-data',32),(ROOT/'results/budget-release-data',32),(training,32)]:
  r=read(d/'candidates.json');need(len(r)==count,'Trainingcount differs');rows.extend(r);x.append(prior.feature_matrix(r,read(d/'features.json')));y.append(np.asarray(prior.labels_for(r,read(d/'labels.json'))))
 x,y=np.vstack(x),np.concatenate(y);need(len(rows)==1857 and x.shape==(1857,336) and y.shape==(1857,),'1857 training contract differs')
 return rows,x,y


def run(output):
 from sklearn.ensemble import ExtraTreesRegressor
 from threadpoolctl import threadpool_limits
 import joblib
 p=authenticate(output);training=ROOT/p['training'];fresh=ROOT/p['fresh'];need(not (output/'run-start.json').exists(),'Single fit stage only');need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists(),'Fresh labels unavailable')
 feature=read(output/'feature-freeze.json');need(feature['training_fresh'],'Training feature novelty failed')
 for n,d in feature['bindings'].items():need(sha(ROOT/n)==d,'Frozenfeature differs')
 rows,x,y=training_data(training)
 write(output/'training-manifest.json',{'schema':SCHEMA,'rows':[{'training_index':i,'candidate_id':r.get('candidate_id','original:'+str(i)),'formula':r['formula'],'actual_lut4':float(y[i]),'source':'original1665' if i<1665 else 'frozen_extra160' if i<1825 else 'new_training32'} for i,r in enumerate(rows)],'consumed_evaluation_labels_fitted':0})
 need(not (output/'training-inputs.npz').exists(),'Trainingmatrix already exists');np.savez_compressed(output/'training-inputs.npz',coverage=inputs(rows,x,'coverage'),augmented=inputs(rows,x,'augmented'),y=y)
 write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),'training_labels_sha256':sha(training/'labels.json'),'training_features_sha256':sha(training/'features.json'),'planned_fits':2,'maximum_fits':2})
 started=time.monotonic();fits=[];models={}
 def deadline(signum,frame):raise TimeoutError('120second fixed fit stage exhausted')
 old=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120)
 try:
  with threadpool_limits(limits=1):
   for index,kind in enumerate(('augmented','coverage'),1):
    write(output/('fit-attempt-'+str(index)+'.json'),{'fit_index':index,'kind':kind,'started_at_utc':now(),'training_count':1857,'feature_count':len(columns(kind)),'training_inputs_sha256':sha(output/'training-inputs.npz'),'configuration':prior.v6.FIXED_PARAMETERS})
    began=time.monotonic();model=ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS);model.fit(inputs(rows,x,kind),y);models[kind]=model
    fits.append({'index':index,'kind':kind,'training_count':1857,'feature_count':len(columns(kind)),'fit_seconds':time.monotonic()-began});joblib.dump(model,output/(kind+'.joblib'))
    write(output/(kind+'.json'),{'schema':SCHEMA,'kind':kind,'columns':columns(kind),'training_count':1857,'new_training_count':32,'old_training_count':1825,'consumed_labels_fitted':0,'configuration':prior.v6.FIXED_PARAMETERS,'calibration':'uncalibrated','upper_lut4':None,'artifact_sha256':sha(output/(kind+'.joblib')),'protocol_sha256':sha(output/'protocol.json'),'runtime_versions':runtime_versions()})
   write(output/'timings.json',fits);panels=retained_panels(models);write(output/'development-predictions.json',panels);write(output/'development-metrics.json',development_metrics(panels))
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
  need(meta['columns']==columns(kind) and meta['training_count']==1857 and meta['artifact_sha256']==sha(output/(kind+'.joblib')) and model.n_features_in_==len(columns(kind)) and model.get_params()==__import__('sklearn.ensemble',fromlist=['ExtraTreesRegressor']).ExtraTreesRegressor(**prior.v6.FIXED_PARAMETERS).get_params(),'Exactfixed matched forest required');result[kind]=model
 return result


def choose(pool,values,freshness,evaluated):
 general=[i for i,r in enumerate(pool) if r['cohort']=='general'];controls=[i for i,r in enumerate(pool) if r['reserved_control']];need(len(pool)==128 and len(general)==32 and len(controls)==8,'Fixed128/32/8split differs')
 reps={k:r['pool_cluster_representatives'] for k,r in freshness['representations'].items()};historical=set().union(*(r['pool_historical_or_training_matches'] for r in freshness['representations'].values()));general_keys={k:{v[i] for i in general} for k,v in reps.items()};raw=[];eligible=[];queues={};excluded_general=[]
 for i,row in enumerate(pool):
  if row['cohort']!='challenge' or not any(values[evaluated][i]<=c<values[PREVIOUS][i] for c in CAPS):continue
  raw.append(i)
  if any(reps[k][i] in general_keys[k] for k in reps):excluded_general.append(i)
  elif i not in historical:eligible.append(i);queues.setdefault(row['template'],[]).append(i)
 active=[];seen={k:set(v) for k,v in general_keys.items()};skipped=[]
 while len(active)<16 and any(queues.values()):
  for template in sorted(queues):
   if len(active)>=16:break
   while queues[template] and any(reps[k][queues[template][0]] in seen[k] for k in reps):skipped.append(queues[template].pop(0))
   if queues[template]:
    i=queues[template].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 return {'general_pool_indices':general,'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in historical],'general_feature_collision_active_pool_indices':excluded_general,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':general+active}


def coverage(pool,values,selection,freshness,evaluated):
 general=selection['general_pool_indices'];active=selection['selected_active_pool_indices'];selected=selection['selected_pool_indices'];checks={}
 for kind,r in freshness['representations'].items():
  keys=r['pool_cluster_representatives'];history=set(r['pool_historical_or_training_matches']);checks[kind+'_general_feature_novel']=not bool(history&set(general));checks[kind+'_general_unique']=len({keys[i] for i in general})==32;checks[kind+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[PREVIOUS][i] for i in active) for c in CAPS};checks.update({'at_least_four_new_learned_corrections':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1})
 return {'pool_count':len(pool),'general_count':32,'shared_control_count':8,'raw_active_count':len(selection['raw_active_pool_indices']),'eligible_active_count':len(selection['eligible_active_pool_indices']),'selected_active_count':len(active),'selected_templates':templates,'correction_caps':caps,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}


def point_subset(saved,indices):
 keys=('candidate_ids','formulas','templates','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','learning_scope')
 result={k:[saved[k][i] for i in indices] for k in keys}
 for key in ('models','tree_predictions_above_cap','learned_raw_lut4','learned_supported_caps_lut4'):result[key]={n:[v[i] for i in indices] for n,v in saved[key].items()}
 return result


def freeze_selection(output):
 p=authenticate(output);fresh=ROOT/p['fresh'];need(not (fresh/'labels.json').exists() and not (fresh/'label-attempt.json').exists() and not (fresh/'selection.json').exists(),'Single prelabel selection required')
 pool=read(fresh/'pool-candidates.json');features=read(fresh/'pool-features.json');models=load(output);values,routes,details=points(pool,prior.feature_matrix(pool,features),models);dev=read(output/'development-metrics.json');evaluated=dev['evaluated_candidate']
 saved={'schema':SCHEMA,'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in pool],'formulas':[r['formula'] for r in pool],'templates':[r['template'] for r in pool],'models':values,'routes':routes,**details,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':evaluated}
 write(output/'pool-predictions.json',saved);freshness=read(output/'feature-freshness.json');selection=choose(pool,values,freshness,evaluated);cov=coverage(pool,values,selection,freshness,evaluated);indices=selection['selected_pool_indices']
 write(fresh/'selection.json',{'schema':SCHEMA,'frozen_at_utc':now(),**selection,'coverage':cov,'evaluated_candidate':evaluated,'pool_predictions_sha256':sha(output/'pool-predictions.json'),'labels_present':False});write(fresh/'candidates.json',[pool[i] for i in indices]);write(fresh/'features.json',{'columns':features['columns'],'records':[features['records'][i] for i in indices]})
 selected={'schema':SCHEMA,'created_at_utc':now(),**point_subset(saved,indices),'selected_candidate':dev['selected_candidate'],'evaluated_candidate':evaluated,'selection_coverage':cov,'general_selected_indices':list(range(32)),'active_selected_indices':list(range(32,len(indices))),'shared_control_selected_indices':[indices.index(i) for i in selection['reserved_control_pool_indices']]}
 selected['conditional_selected_indices']=selected['active_selected_indices']+selected['shared_control_selected_indices'];write(output/'fresh-predictions.json',selected)
 paths=[output/n for n in ('protocol.json','feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-predictions.json')]+[fresh/n for n in ('pool-candidates.json','pool-features.json','selection.json','candidates.json','features.json')]
 seal={'schema':SCHEMA,'frozen_at_utc':now(),'fresh_labels_present':False,'new_fits':0,'bindings':{prior.relative(x):sha(x) for x in paths}};write(output/'fresh-point-freeze.json',seal)
 paths.append(output/'fresh-point-freeze.json');write(fresh/'point-freeze.json',{'schema':SCHEMA,'frozen_at_utc':now(),'target_label_jobs':0,'bindings':{prior.relative(x):sha(x) for x in paths}});return {'selection_coverage':cov,'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json')}


def score_values(saved,y,dev):
 row={**saved,'actual_lut4':y};general=subset(row,saved['general_selected_indices']);conditional=subset(row,saved['conditional_selected_indices']);active=subset(row,saved['active_selected_indices']) if saved['active_selected_indices'] else None;gates={}
 for n in CANDIDATES:
  new_active=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=c<saved['models'][PREVIOUS][i] for c in CAPS)]
  activity={'new_corrections':len(new_active),'templates':len({saved['templates'][i] for i in new_active}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][PREVIOUS][i] for i in new_active)}
  activity_pass=activity['new_corrections']>=4 and activity['templates']>=2 and activity['cap128']>=1
  checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_pass,'general_no_loss':passed(general['checks'][n]),'general_strict_signed':accuracy(general[CURRENT],general[n],True),
   'general_strict_fa_gain_signed':sum(general[n]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),
   'conditional_full_passes':passed(conditional['checks'][n]),'active_subset_passes':bool(active and passed(active['checks'][n]))}
  ok=checks['coverage']['passed'] and activity_pass and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['conditional_full_passes'] and checks['active_subset_passes']
  gates[n]={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':ok and dev['selected_candidate']==n}
 chosen=dev['selected_candidate'];return general,conditional,active,gates,bool(chosen and gates[chosen]['eligible'])


def verify_fresh(output):
 p=authenticate(output);load(output);fresh=ROOT/p['fresh'];seal=read(output/'fresh-point-freeze.json')
 for n,d in seal['bindings'].items():need(sha(ROOT/n)==d,'Frozen fresh payload differs: '+n)
 return p,fresh


def score(output):
 p,fresh=verify_fresh(output);rows=read(fresh/'candidates.json');saved=read(output/'fresh-predictions.json');need(saved['candidate_ids']==[r['candidate_id'] for r in rows],'Selected alignment differs');dev=read(output/'development-metrics.json')
 general,conditional,active,gates,eligible=score_values(saved,prior.labels_for(rows,read(fresh/'labels.json')),dev)
 result={'schema':SCHEMA,'models':general,'conditional_models':conditional,'active_subgroup':active,'gates':gates,'selection_coverage':saved['selection_coverage'],'selected_candidate':dev['selected_candidate'],'evaluated_candidate':dev['evaluated_candidate'],'scoped_experimental_eligibility':eligible,'general_count':32,'conditional_count':len(saved['conditional_selected_indices']),'active_count':len(saved['active_selected_indices']),'shared_controls':8,'unique_label_count':len(rows),'fits':2,'native_jobs':0,'no_pooled_metric':True,'fresh_labels_sha256':sha(fresh/'labels.json'),'scope':p['scope']}
 write(output/'fresh-metrics.json',result);return result


def predict_cached(output,candidates,features,destination):
 p=authenticate(output);rows=read(candidates);values,routes,details=points(rows,prior.feature_matrix(rows,read(features)),load(output));dev=read(output/'development-metrics.json');n=dev['evaluated_candidate']
 write(destination,{'schema':SCHEMA,'model':n,'selected_candidate':dev['selected_candidate'],'candidate_ids':[r.get('candidate_id') for r in rows],'formulas':[r['formula'] for r in rows],'models':values,'predicted_lut4':values[n],'routes':routes,**details,'fits':0,'native_jobs':0,'upper_lut4':None,'calibration_status':'uncalibrated','candidates_sha256':sha(candidates),'features_sha256':sha(features),'protocol_sha256':sha(output/'protocol.json'),'scope':p['scope']})
 return {'predictions':len(rows),'new_fits':0,'native_jobs':0,'output':str(destination)}


def replay(output):
 p,fresh=verify_fresh(output);models=load(output);panels=retained_panels(models);need(panels==read(output/'development-predictions.json'),'Developmentpoint replay differs');dev=development_metrics(panels);need(dev==read(output/'development-metrics.json'),'Developmentmetric replay differs')
 training=ROOT/p['training'];tr=read(training/'candidates.json');pool=read(fresh/'pool-candidates.json');report=feature_freshness(tr,prior.feature_matrix(tr,read(training/'features.json')),pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')));need(report==read(output/'feature-freshness.json'),'Featurefreshness replay differs')
 values,routes,details=points(pool,prior.feature_matrix(pool,read(fresh/'pool-features.json')),models);saved=read(output/'pool-predictions.json');need(values==saved['models'] and routes==saved['routes'] and all(saved[k]==v for k,v in details.items()),'Poolpoint replay differs')
 selection=choose(pool,values,report,dev['evaluated_candidate']);stored=read(fresh/'selection.json');need(all(stored[k]==v for k,v in selection.items()) and stored['coverage']==coverage(pool,values,selection,report,dev['evaluated_candidate']),'Selection replay differs');indices=selection['selected_pool_indices'];selected=read(output/'fresh-predictions.json');need(all(selected[k]==v for k,v in point_subset(saved,indices).items()),'Selectedpoint replay differs')
 need(read(fresh/'candidates.json')==[pool[i] for i in indices],'Selectedcandidates differ');features=read(fresh/'pool-features.json');need(read(fresh/'features.json')=={'columns':features['columns'],'records':[features['records'][i] for i in indices]},'Selectedfeatures differ')
 scored=False
 if (output/'fresh-metrics.json').exists():
  g,c,a,gates,eligible=score_values(selected,prior.labels_for(read(fresh/'candidates.json'),read(fresh/'labels.json')),dev);result=read(output/'fresh-metrics.json');need(g==result['models'] and c==result['conditional_models'] and a==result['active_subgroup'] and gates==result['gates'] and eligible==result['scoped_experimental_eligibility'],'Freshmetric replay differs');scored=True
 return {'status':'pass','retained_metric_rows':897,'retained_unique_circuits':889,'pool_rows':128,'selected_rows':len(indices),'fresh_metrics_replayed':scored,'new_fits':0,'native_jobs':0,'writes':0}


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','freeze-features','run','freeze-selection','score','predict-cached','replay'));parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--training',type=Path,default=TRAIN);parser.add_argument('--fresh',type=Path,default=FRESH);parser.add_argument('--candidates',type=Path);parser.add_argument('--features',type=Path);parser.add_argument('--prediction-output',type=Path)
 a=parser.parse_args();out=a.output.resolve()
 if a.command=='prepare':result=prepare(out,a.training.resolve(),a.fresh.resolve())
 elif a.command=='predict-cached':
  need(all((a.candidates,a.features,a.prediction_output)),'Explicit cached inputs/output required');result=predict_cached(out,a.candidates,a.features,a.prediction_output)
 else:result={'freeze-features':freeze_features,'run':run,'freeze-selection':freeze_selection,'score':score,'replay':replay}[a.command](out)
 print(json.dumps(result,indent=2))

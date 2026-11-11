#!/usr/bin/env python3
"""Independent control/sharing coverage audit. No fits or native jobs."""
from __future__ import annotations
import argparse,itertools,json,math,random,subprocess,sys,zipfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_boundary_feasibility as previous
import audit_boundary_corroboration as regression
import audit_boundary_coverage as feature
import audit_targeted_coverage as old
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/control-sharing-coverage';TRAIN=ROOT/'results/control-sharing-coverage-data';TEST=ROOT/'results/control-sharing-coverage-validation';PRIOR=ROOT/'results/boundary-feasibility'
CURRENT,RELEASE=previous.CURRENT,previous.RELEASE
BASELINE='feasibility_augmented';NAME='control_sharing_coverage';CAPS=(32,64,128);TOL=1e-10;PROB_TOL=1e-12
REFERENCES=previous.REFERENCES


def check_bindings(mapping,root=ROOT):
 for n,h in mapping.items():assert sha(root/n)==h,n


def preserved():
 s=read(OUT/'auditor-prior-artifacts.json');check_bindings(s['files']);g=read(ROOT/s['goal_ledger']['path']);g.pop('status',None);assert g==s['goal_ledger']['protected_content'];assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==s['submodules'];return len(s['files'])


def receipt(path,body,write=False):
 body={'schema':'independent-control-sharing-coverage-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
 if write:
  with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
 else:
  saved=read(path);actual=dict(body)
  for d in (saved,actual):d.pop('audited_at_utc',None)
  assert saved==actual,'Receipt replay differs:'+str(path)
 return body


def input_profiles(formula):
 result=[]
 for data,control,post,outer in feature.ast_chains(formula):
  and_control=any(isinstance(n,tuple) and n[0]=='and' and all(feature.ast_dependencies(c) for c in n[1]) and set().union(*(feature.ast_dependencies(c) for c in n[1]))=={'in0','in1'} for n in old.nodes(control))
  repeat=isinstance(post,tuple) and post[0]=='and' and all(feature.ast_dependencies(c) for c in post[1]) and feature.ast_subtree_key(post)==feature.ast_subtree_key(outer) and feature.ast_nonleaf_subtrees(post)<=feature.ast_nonleaf_subtrees(data)
  z,o=regression.known_bits(control);bits=((regression.MASK^(z|o))&31).bit_count();result.append({'both_input_and_control':and_control,'repeated_and_data_post_outer':bool(repeat),'unknown_low_control_bits':bits})
 return result


def lowbit_normalize(node,bits=32):
 """Preserve the demanded low bits; only rewrite masked fixed arithmetic shifts.

 Bitwise and modular ADD/SUB/MUL low outputs depend on the same low inputs.
 Other operations conservatively demand all input bits. Variable shift amounts
 use only low5 bits; right-shift data conservatively demands all32 bits.
 """
 if not isinstance(node,tuple):return node
 op,args=node
 if op in ('sra','srl'):return op,(lowbit_normalize(args[0],32),lowbit_normalize(args[1],5))
 if op=='sll':return op,(lowbit_normalize(args[0],bits),lowbit_normalize(args[1],5))
 safe={'and','andi','or','ori','xor','xori','add','addi','sub','mul','slli'}
 demands=[bits if op in safe else 32]*len(args)
 if op=='andi' and isinstance(args[1],int):demands[0]=min(bits,(args[1]&((1<<bits)-1)).bit_length())
 if op in ('srai','srli') and isinstance(args[1],int):
  shift=args[1]&31
  if bits+shift<=32:op='srli'
  demands[0]=min(32,bits+shift)
 return op,tuple(lowbit_normalize(c,b) for c,b in zip(args,demands))


def family_key(formula):
 def walk(n,swap):
  if isinstance(n,int):return '#'
  if isinstance(n,str):return ('in1' if n=='in0' else 'in0') if swap else n
  op,args=n;args=[walk(c,swap) for c in args]
  if op in ('and','or','xor','add'):args.sort(key=repr)
  return op,tuple(args)
 n=lowbit_normalize(previous.modular_normalize(old.parse(formula)))
 return min(repr(walk(n,False)),repr(walk(n,True)))


def family_overlaps(training,pool,history):
 hk={family_key(f) for f in history};tk={};result=[]
 for i,r in enumerate(training):tk.setdefault(family_key(r['formula']),[]).append(i)
 for i,r in enumerate(pool):
  if family_key(r['formula']) in tk:result.append({'pool_index':i,'template':r['template'],'training_indices':tk[family_key(r['formula'])]})
 historical=[{'kind':kind,'index':i,'template':r['template']} for kind,rows in (('train',training),('pool',pool)) for i,r in enumerate(rows) if family_key(r['formula']) in hk]
 return {'historical_structural_family_overlaps':historical,'training_pool_structural_family_overlaps':result}


def prior_profile_review():
 d=read(OUT/'prior-coverage-diagnosis.json');manifest=PRIOR/'training-manifest.json';assert d['training_manifest_sha256']==sha(manifest);rows=read(manifest)['rows'];groups={}
 for group in ('both_input_and_control','repeated_and_data_post_outer'):
  matched=[];bits=Counter()
  for row in rows:
   profiles=[r for r in input_profiles(row['formula']) if r[group]]
   if profiles:matched.append(row);bits.update(r['unknown_low_control_bits'] for r in profiles)
  groups[group]={'training_rows':len(matched),'class_counts':{str(c):{'feasible':sum(r['actual_lut4']<=c for r in matched),'infeasible':sum(r['actual_lut4']>c for r in matched)} for c in CAPS},'control_bit_counts':{str(i):bits[i] for i in range(6)}}
 assert len(rows)==d['training_count']==1889 and groups==d['group_counts'] and groups['both_input_and_control']['training_rows']==6 and groups['repeated_and_data_post_outer']['training_rows']==0
 p=read(PRIOR/'fresh-predictions.json')
 for r in d['consumed_failure_examples']:assert r['formula']==p['formulas'][r['selected_index']] and r['input_only_profiles']==input_profiles(r['formula'])
 return {'source_sha256':sha(OUT/'prior-coverage-diagnosis.json'),'training_rows':1889,'groups':groups,'all_four_consumed_failure_profiles_verified':True,'no_future_inputs_or_labels_used':True,'no_causal_mechanism_or_transfer_claim':True}


def frozen_panels():
 panels=read(PRIOR/'development-predictions.json');p=read(PRIOR/'fresh-predictions.json');labels=read(ROOT/'results/boundary-feasibility-validation/labels.json')
 for name,key in (('consumed-twelfth-general32','general_selected_indices'),('consumed-twelfth-sharing8','sharing_selected_indices'),('consumed-twelfth-legacy8','legacy_selected_indices'),('consumed-twelfth-conditional16','conditional_selected_indices')):
  ix=p[key];panels[name]={'candidate_ids':[p['candidate_ids'][i] for i in ix],'formulas':[p['formulas'][i] for i in ix],'actual_lut4':[labels[i]['lut4'] for i in ix],'models':{n:[v[i] for i in ix] for n,v in p['models'].items()}}
 assert len(panels)==26 and sum(len(r['actual_lut4']) for r in panels.values())==1113
 return panels


def oracle_values(row):
 result=[];alphabets=[]
 for i,y in enumerate(row['actual_lut4']):
  s=row['models'][CURRENT][i];r=row['models'][RELEASE][i];scope=bool(feature.ast_chains(row['formulas'][i]));alphabet=sorted({r,*[float(c) for c in CAPS if scope and s<=c<r]})
  allowed=[p for p in alphabet if all(not(p<=c<r and y>c) and not(s<=c<p and y<=c) for c in CAPS)]
  assert allowed,(row['candidate_ids'][i],y,s,r,alphabet)
  alphabets.append(allowed);result.append(min(allowed,key=lambda p:abs(y-p)))
 return result,alphabets


def comparator_feasibility():
 panels=frozen_panels();reports={};unique=True
 for name,row in panels.items():
  points,allowed=oracle_values(row);unique=unique and all(len(v)==1 for v in allowed);m=old.metrics(row['actual_lut4'],points);refs={n:old.metrics(row['actual_lut4'],row['models'][n]) for n in REFERENCES}
  reports[name]={'count':len(points),'all_points_feasible':True,'all_points_unique_under_all_cap_gates':all(len(v)==1 for v in allowed),'oracle_MAE_lower_bound':m['mae_lut4'],'oracle_positive_MAPE_lower_bound':m['positive_mape_percent'],'six_original_accuracy_comparators_feasible':{n:feature.accuracy(v,m) for n,v in refs.items()},'six_original_maximum_underprediction_comparators_feasible':{n:m['maximum_underprediction_lut4']<=v['maximum_underprediction_lut4']+TOL for n,v in refs.items()}}
  if name in ('consumed-twelfth-general32','consumed-twelfth-legacy8'):
   baseline=old.metrics(row['actual_lut4'],row['models'][BASELINE]);reports[name]['added_passing_classifier_comparator_feasible']=feature.accuracy(baseline,m);reports[name]['added_passing_classifier_tail_feasible']=m['maximum_underprediction_lut4']<=baseline['maximum_underprediction_lut4']+TOL;reports[name]['oracle_exactly_matches_existing_passing_classifier']=points==row['models'][BASELINE]
 row=panels['consumed-twelfth-conditional16'];active={k:[v[i] for i in range(8)] for k,v in row.items() if k!='models'};active['models']={n:v[:8] for n,v in row['models'].items()};p,allowed=oracle_values(active);m=old.metrics(active['actual_lut4'],p);baseline=old.metrics(active['actual_lut4'],active['models'][BASELINE]);impossible={'population':'latest_failed_active8','oracle_MAE_lower_bound':m['mae_lut4'],'unsafe_classifier_MAE':baseline['mae_lut4'],'oracle_positive_MAPE_lower_bound':m['positive_mape_percent'],'unsafe_classifier_positive_MAPE':baseline['positive_mape_percent'],'adding_unsafe_classifier_as_area_accuracy_comparator_is_impossible':m['mae_lut4']>baseline['mae_lut4']+TOL,'reason':'Correctly rejecting129/130/129 at128 requires release fallback138.6567/139.7667/144.82. Those larger absolute errors cannot be hidden by changing the other five accepted cap-snap outputs. This is only an evaluation oracle, never inference or a training target.'}
 assert unique and impossible['adding_unsafe_classifier_as_area_accuracy_comparator_is_impossible']
 return {'scope':'Consumed-data feasibility analysis ONLY, never inference/training/fresh selection. Known labels select a hypothetical cap-correct oracle solely to test declared gates for contradictions.','panels':reports,'unique_feasible_point_for_every_consumed_row':unique,'added_classifier_comparator_only_latest_passing_general_and_legacy':True,'deliberately_excluded_impossible_failed_active_comparator':impossible,'future_unknown_cohort_gates_remain_empirical_not_guaranteed':True,'all_original_gates_retained':True}


def relative(p):return str(p.relative_to(ROOT))


def authenticate():
 import learn_control_sharing_coverage as m
 p=m.authenticate(OUT);assert p['planned_fits']==p['maximum_fits']==1 and p['fit_threads']==1 and p['total_training_rows']==1921 and p['new_training_labels']==32 and p['consumed_labels_fitted']==0
 assert p['configuration_all_parameters']==read(PRIOR/'protocol.json')['configuration_all_parameters'] and p['columns']==read(PRIOR/'protocol.json')['columns']['augmented'] if isinstance(read(PRIOR/'protocol.json')['columns'],dict) else p['columns']==m.columns()
 assert p['required_acceptance_count']==62 and p['required_rejection_count']==38 and p['validated_baseline_panels']==['consumed-twelfth-general32','consumed-twelfth-legacy8']
 plan=read(TRAIN/'plan.json');assert read(TEST/'plan.json')==plan and plan['training_count']==32 and plan['pool_count']==96 and plan['maximum_selected_count']==64
 assert plan['policy']=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128],'budget_accounting':'summed_worker_process_seconds','stage_wall_safety_reserve_seconds':1.0}
 for k in ('sources','inputs','prior_inventory_sources','design_audit_inputs'):check_bindings(plan[k])
 for tool in read(TRAIN/'tools.json').values():assert sha(tool['path'])==tool['sha256']
 targets=read(OUT/'evaluation-targets.json');check_bindings(targets['bindings']);accept=targets['required_acceptances'];reject=targets['required_rejections'];assert len(accept)==62 and len(reject)==38 and len(targets['core_required_rejections'])==15
 keys=[(r['candidate_id'],r['cap']) for r in accept+reject];assert len(set(keys))==100
 for r in accept:assert r['actual_lut4']<=r['cap'] and r['previous_points_lut4'][CURRENT]<=r['cap']<r['previous_points_lut4'][RELEASE]
 for r in reject:assert r['actual_lut4']>r['cap'] and r['previous_points_lut4'][RELEASE]>r['cap']
 return p


def bindings():
 paths=[OUT/n for n in ('protocol.json','auditor-prior-artifacts.json','evaluation-targets.json','prior-coverage-diagnosis.json','method-rationale.json','analytical-feasibility-review.json','measurement-input-profile-audit.json','support-cells.json','goal-at-freeze.json','goal-update-at-freeze.json','research-goal-current-at-freeze.json')]
 paths +=[d/n for d in (TRAIN,TEST) for n in ('plan.json','novelty.json','historical-formulas.json','tools.json')]+[TRAIN/'candidates.json',TEST/'pool-candidates.json']
 return {relative(p):sha(p) for p in paths}


def identity_audit():
 history=set(read(TRAIN/'historical-formulas.json'));assert history==set(read(TEST/'historical-formulas.json'));required=set(read(ROOT/'results/boundary-feasibility-validation/historical-formulas.json'))
 for n in ('pool-candidates.json','candidates.json'):required.update(r['formula'] for r in read(ROOT/'results/boundary-feasibility-validation'/n))
 for r in read(ROOT/'results/boundary-feasibility-validation/novelty.json')['comparisons']:required.update(r['forms'])
 assert required<=history
 known=set().union(*(feature.prior.identity_keys(f) for f in history));skeletons={old.skeleton(f) for f in history};normal={previous.modular_formula(f) for f in history};nk=set().union(*(feature.prior.identity_keys(f) for f in normal));ns={old.skeleton(f) for f in normal};seen=set();modseen=set();train_sk={old.skeleton(r['formula']) for r in read(TRAIN/'candidates.json')}
 for folder,file,count in ((TRAIN,'candidates.json',32),(TEST,'pool-candidates.json',96)):
  rows=read(folder/file);novel=read(folder/'novelty.json');assert len(rows)==len(novel['comparisons'])==count and novel['status']=='pass'
  for row,e in zip(rows,novel['comparisons']):
   assert row['candidate_id']==e['candidate_id'];keys=set().union(*(feature.prior.identity_keys(f) for f in {row['formula'],*e['forms']}));assert not keys&known and not keys&seen and old.skeleton(row['formula']) not in skeletons;seen.update(keys)
   if folder==TEST:assert old.skeleton(row['formula']) not in train_sk
   n=previous.modular_formula(row['formula']);keys=feature.prior.identity_keys(n);assert e['modular_normalized_formula']==n and not keys&nk and not keys&modseen and old.skeleton(n) not in ns;modseen.update(keys)
 return {'historical_formulas':len(history),'new_training_rows':32,'fresh_pool_rows':96,'original_alias_and_modular_identity_or_skeleton_collisions':0,'all_latest128_including72_unlabelled_consumed':True,'sound_modular_rules':previous.modular_rules_check(),'finite_screen_not_exhaustive_equivalence':True}


def profile_review():
 d=read(OUT/'measurement-input-profile-audit.json');check_bindings(d['sources']);rows=read(TRAIN/'candidates.json');assert len(rows)==32 and [r['formula'] for r in d['new_training']]==[r['formula'] for r in rows]
 counts={k:sum(any(p[k] for p in input_profiles(r['formula'])) for r in rows) for k in ('both_input_and_control','repeated_and_data_post_outer')};assert counts==d['group_counts']=={'both_input_and_control':16,'repeated_and_data_post_outer':16}
 for r in [*d['new_training'],*d['cohort_profiles']]:
  assert feature.ast_features(r['formula'])==r['features16']
  independent=input_profiles(r['formula']);assert len(independent)==len(r['profiles'])
  for a,b in zip(independent,r['profiles']):assert all(a[k]==b[k] for k in ('both_input_and_control','repeated_and_data_post_outer'))
 return {'training_profile_counts':counts,'new_training_and_pool_feature_vectors_independently_replayed':128,'all_four_consumed_failure_profiles_verified':prior_profile_review(),'coordinate_matches_not_cost_or_safety_guarantees':True}


def preflight(write=False):
 p=authenticate();count=preserved()
 if write:assert not any((d/n).exists() for d in (TRAIN,TEST) for n in ('features.json','pool-features.json','feature-attempt.json','labels.json','label-attempt.json')) and not (OUT/'run-start.json').exists()
 feasibility=comparator_feasibility()
 for panel in feasibility['panels'].values():assert all(all(v.values()) for v in panel['six_original_accuracy_comparators_feasible'].values()) and all(panel['six_original_maximum_underprediction_comparators_feasible'].values())
 return receipt(TRAIN/'preflight-audit.json',{'bindings':bindings(),'scientific_artifacts_preserved':count,'identity_and_modular_novelty':identity_audit(),'input_profile_review':profile_review(),'analytical_comparator_feasibility':feasibility,'reviewed_policy':p['policy'],'reviewed_gates':p['gates'],'reviewed_selection':p['selection'],'one_fixed233_fit_on1889_plus32_no_consumed_labels':True,'fixed0_5_tie_acceptance_parameters_unchanged':True,'summed_worker_seconds300_peak2_and_parent_stage_authorization_required':True,'no_new_features_training_labels_fit_attempts_at_receipt':True,'postmeasurement_training_label_audit_required_before_fit':True},write)


def native_body(folder,name):
 if (folder/'raw').exists():return (folder/'raw'/name).read_bytes()
 with zipfile.ZipFile(folder/read(folder/'raw-evidence-manifest.json')['archive']) as z:return z.read('raw/'+name)


def stage_authorization(stage,write=False):
 name={'features':'feature','train-labels':'training-label','test-labels':'fresh-label'}[stage]+'-parent-authorization-at-audit.json';path=TRAIN/name
 if write:
  a=read(TRAIN/'parent-authorization.json');assert stage in a['authorized_stages']
  with path.open('x') as f:json.dump(a,f,indent=2);f.write('\n')
 a=read(path);assert a['status']=='approved' and a['approved_by']=='parent' and stage in a['authorized_stages'] and a['plan_sha256']==sha(TRAIN/'plan.json') and a['protocol_sha256']==sha(OUT/'protocol.json')
 return path


def chronology(level='features'):
 from datetime import datetime
 reports=[read(TRAIN/'feature-completion.json')]
 if level!='features':reports.append(read(TRAIN/'completion.json'))
 if level=='fresh':reports.append(read(TEST/'completion.json'))
 total=wall=0;events=[];end=None
 for report in reports:
  assert report['complete'] and not report['failures'];jobs=report['native_worker_jobs'];old.job_audit(report)
  if end:assert end<min(j['started_at_utc'] for j in jobs)
  end=max(j['finished_at_utc'] for j in jobs);summed=sum(j['native_elapsed_seconds'] for j in jobs);assert math.isclose(summed,report['native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(summed,report['summed_worker_native_seconds'],abs_tol=1e-9)
  budget=300-total;assert math.isclose(report['native_budget_seconds'],budget,abs_tol=1e-9) and math.isclose(report['stage_wall_budget_seconds'],(budget-1)/2,abs_tol=1e-9)
  for j in jobs:
   interval=(datetime.fromisoformat(j['finished_at_utc'])-datetime.fromisoformat(j['started_at_utc'])).total_seconds();assert 0<j['native_elapsed_seconds']<=j['job_wall_elapsed_seconds']+1e-9<=interval+.01;events.extend(((j['started_at_utc'],1),(j['finished_at_utc'],-1)))
  total+=summed;wall+=report['stage_wall_elapsed_seconds'];assert math.isclose(total,report['total_native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(total,report['total_summed_worker_native_seconds'],abs_tol=1e-9)
 assert total<=300;active=peak=0
 for _,n in sorted(events,key=lambda e:(e[0],e[1])):active+=n;peak=max(peak,active)
 assert active==0 and peak<=2
 assert Counter((j['kind'],j['stage']) for j in reports[0]['native_worker_jobs'])=={('train','feature'):32,('test','feature'):96}
 assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
 if level!='features':
  assert Counter(j['stage'] for j in reports[1]['native_worker_jobs'])=={'verify':1,'label':32};assert read(TRAIN/'pretrain-audit.json')['audited_at_utc']<read(TRAIN/'label-attempt.json')['started_at_utc']
 if level=='fresh':
  n=len(read(TEST/'candidates.json'));assert Counter(j['stage'] for j in reports[2]['native_worker_jobs'])=={'verify':1,'label':n};assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
 for r in reports[1:]:assert max(j['finished_at_utc'] for j in r['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in r['native_worker_jobs'] if j['stage']=='label')
 return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'summed_worker_native_seconds':total,'stage_wall_seconds_separately':wall,'recorded_worker_peak':peak,'budget_unit':'summed_worker_process_seconds'}


def feature_review():
 import numpy as np
 import learn_control_sharing_coverage as m
 historical,base=m.historical_records();assert base.shape==(3802,217);aug=np.hstack((base,np.asarray([regression.ast_features(f) for f in historical])));report={};train=read(TRAIN/'candidates.json');pool=read(TEST/'pool-candidates.json')
 x={}
 for folder,filename,rows,kind in ((TRAIN,'features.json',train,'train'),(TEST,'pool-features.json',pool,'test')):
  data=read(folder/filename);assert len(data['columns'])==336 and len(data['records'])==len(rows);x[kind]=feature.prior.feature_matrix(rows,data)
  for j in read(TRAIN/'feature-completion.json')['native_worker_jobs']:
   if j['kind']!=kind:continue
   prefix='features/'+str(j['index'])+'/';assert json.loads(native_body(folder,prefix+'result.json'))==data['records'][j['index']] and json.loads(native_body(folder,prefix+'worker.json'))==j and digest(native_body(folder,prefix+'worker.log'))==j['log_sha256']
 for kind,history in (('coverage',base),('augmented',aug)):
  values=lambda rows,b:b if kind=='coverage' else np.hstack((b,np.asarray([regression.ast_features(r['formula']) for r in rows])))
  hk={tuple(v) for v in history};tk=[tuple(v) for v in values(train,x['train'])];pk=[tuple(v) for v in values(pool,x['test'])];clusters={};reps=[]
  for i,k in enumerate(pk):clusters.setdefault(k,[]).append(i);reps.append(clusters[k][0])
  report[kind]={'historical_unique_count':len(hk),'training_historical_matches':[i for i,k in enumerate(tk) if k in hk],'training_unique_count':len(set(tk)),'pool_historical_or_training_matches':[i for i,k in enumerate(pk) if k in hk|set(tk)],'pool_cluster_representatives':reps,'pool_duplicate_clusters':[v for v in clusters.values() if len(v)>1]}
 result={'historical_rows':3802,'fitted_rows':1889,'unique_consumed_labels':1073,'prior_pool_rows':[200,128,128,128,128,128],'representations':report,'training_fresh':all(not v['training_historical_matches'] and v['training_unique_count']==32 for v in report.values()),'equality':'Exactfloat64 tuples; no rounding or target labels.'}
 assert result==read(OUT/'feature-freshness.json');seal=read(OUT/'feature-freeze.json');assert seal['training_fresh']==result['training_fresh'] and seal['protocol_sha256']==sha(OUT/'protocol.json');check_bindings(seal['bindings']);assert read(TRAIN/'feature-completion.json')['completed_at_utc']<seal['frozen_at_utc']
 return result


def pretrain(write=False):
 authenticate();preflight(False);count=preserved();jobs=chronology();fresh=feature_review();assert fresh['training_fresh']
 if write:assert not any((d/n).exists() for d in (TRAIN,TEST) for n in ('labels.json','label-attempt.json')) and not (OUT/'run-start.json').exists()
 auth=stage_authorization('features',write);files=[auth,TRAIN/'feature-completion.json',TRAIN/'features.json',TEST/'pool-features.json',OUT/'feature-freeze.json',OUT/'feature-freshness.json']
 return receipt(TRAIN/'pretrain-audit.json',{'bindings':{**bindings(),**{relative(p):sha(p) for p in files}},'scientific_artifacts_preserved':count,'feature_freshness':fresh,'native_accounting':jobs,'raw_feature_results_worker_records_and_logs_authenticated':128,'training_and_fresh_labels_absent_at_receipt':True,'immutable_feature_authorization_snapshot':relative(auth)},write)


def raw_audit(folder):
 rows=read(folder/'candidates.json');labels=read(folder/'labels.json');assert len(rows)==len(labels) and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
 manifest=read(folder/'raw-evidence-manifest.json');archive=folder/manifest['archive'];assert sha(archive)==manifest['archive_sha256'];members={r['path']:r for r in manifest['files']};kind='train' if folder==TRAIN else 'test'
 with zipfile.ZipFile(archive) as z:
  assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)
  for n,r in members.items():body=z.read(n);assert digest(body)==r['sha256'] and len(body)==r['bytes']
  get=lambda n:z.read('raw/'+n)
  feature_jobs=[j for j in read(TRAIN/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind];label_jobs=read(folder/'completion.json')['native_worker_jobs']
  for j in feature_jobs+label_jobs:
   directory='verification' if j['stage']=='verify' else j['stage']+'s/'+str(j['index']);assert json.loads(get(directory+'/worker.json'))==j and digest(get(directory+'/worker.log'))==j['log_sha256']
  proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode();assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148 and proof['random_seed']==read(TRAIN/'plan.json')['proof_random_seeds'][kind] and proof['total_comparisons']==2148*len(rows)
  assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256'];boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1];rng=random.Random(proof['random_seed']);expected=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)];parsed=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()];assert [(r[0],r[1]) for r in parsed]==expected;trees=[old.parse(r['formula']) for r in rows]
  for a,b,*targets in parsed:assert [old.evaluate(t,a,b) for t in trees]==targets
  assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
  for i,(row,label) in enumerate(zip(rows,labels)):
   assert label['status']=='complete' and label['formula']==row['formula'] and json.loads(get(f'labels/{i}/result.json'))==label
   net=get(f'labels/{i}/ice40-netlist.json');assert digest(net)==label['netlist_sha256'];c=Counter(v['type'] for v in json.loads(net)['modules']['candidate']['cells'].values());assert c['SB_LUT4']==label['lut4'] and c['SB_CARRY']==label['carry'];source=get(f'labels/{i}/candidate.v').decode();assert digest(source.encode())==label['rtl_sha256'] and source.replace('module candidate(',f'module candidate_{i}(') in rtl
   body=get(f'labels/{i}/metrics.json');m=json.loads(body);assert digest(body)==label['metrics_sha256'] and m['ice40_lut4_count']==label['lut4'] and m['ice40_carry_count']==label['carry'] and m['measurement_source']=='rtl_synthesis' and 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
  features=read(folder/('features.json' if kind=='train' else 'pool-features.json'))
  for i,r in enumerate(features['records']):assert json.loads(get(f'features/{i}/result.json'))==r
 return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'independent_original_RV32_comparisons':2148*len(rows),'feature_results_authenticated':len(features['records']),'worker_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}


def training_labels(write=False):
 authenticate();pretrain(False);count=preserved();jobs=chronology('training');proof=raw_audit(TRAIN)
 if write:assert not (OUT/'run-start.json').exists() and not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 auth=stage_authorization('train-labels',write);files=[auth,TRAIN/'labels.json',TRAIN/'completion.json',TRAIN/'raw-evidence-manifest.json',TRAIN/read(TRAIN/'raw-evidence-manifest.json')['archive'],TRAIN/'pretrain-audit.json']
 return receipt(TRAIN/'training-label-audit.json',{'bindings':{**bindings(),**{relative(p):sha(p) for p in files}},'scientific_artifacts_preserved':count,'native_accounting':jobs,'new_training_labels_independently_verified':32,'native_RTL_proof_netlists_and_measurements':proof,'fresh_labels_and_fit_attempts_absent_at_receipt':True,'parent_must_bind_this_receipt_and_training_labels_features_completion_before_one_fit':True,'immutable_training_label_authorization_snapshot':relative(auth)},write)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=('analysis','preflight','pretrain','training-labels'),default='analysis',nargs='?');p.add_argument('--write',action='store_true');a=p.parse_args();fn={'preflight':preflight,'pretrain':pretrain,'training-labels':training_labels}.get(a.command);result=fn(a.write) if fn else {'prior_profile':prior_profile_review(),'comparator_feasibility':comparator_feasibility()};print(json.dumps(result,indent=2))

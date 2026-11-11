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


def matrix(rows,payload):
 import numpy as np
 assert len(rows)==len(payload['records']) and [r['formula'] for r in rows]==[r['formula'] for r in payload['records']]
 columns=read(PRIOR/'augmented.json')['columns'][:217];positions=[payload['columns'].index(c) for c in columns];x=np.asarray([r['values'] for r in payload['records']],dtype=float)[:,positions];assert x.shape==(len(rows),217) and np.isfinite(x).all() and (x>=0).all();return x


def authenticate():
 import learn_control_sharing_coverage as m
 p=m.authenticate(OUT);assert p['planned_fits']==p['maximum_fits']==1 and p['fit_threads']==1 and p['total_training_rows']==1921 and p['new_training_labels']==32 and p['consumed_labels_fitted']==0
 assert p['configuration_all_parameters']==read(PRIOR/'protocol.json')['configuration_all_parameters']
 assert p['columns']==read(PRIOR/'augmented.json')['columns']==m.columns()
 assert p['required_acceptance_count']==62 and p['required_rejection_count']==38 and p['validated_baseline_panels']==['consumed-twelfth-general32','consumed-twelfth-legacy8']
 formulas=[r['formula'] for r in read(PRIOR/'training-manifest.json')['rows']]+[r['formula'] for r in read(TRAIN/'candidates.json')];chains=[regression.cells(f) for f in formulas];counts=Counter(r['cell'] for chain in chains for r in chain);assert read(OUT/'support-cells.json')=={'training_formula_count':1921,'structural_formula_count':sum(bool(c) for c in chains),'chain_count':sum(len(c) for c in chains),'cell_counts':dict(sorted(counts.items())),'supported_cells':sorted(counts),'input_only':True}
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
 paths +=[OUT/n for n in ('prefreeze-family-review.json','prefreeze-audit-source-v1.py','rejected-measurement-input-draft-v1.py','rejected-joint-inputs-v1.json','input-family-revision-v1.json','parent-preflight-validation.json')]
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
 family=family_overlaps(read(TRAIN/'candidates.json'),read(TEST/'pool-candidates.json'),history);assert not any(family.values());rejected=read(OUT/'rejected-joint-inputs-v1.json');found=family_overlaps(rejected['training'],rejected['pool'],history);finding=read(OUT/'prefreeze-family-review.json');check_bindings(finding['bindings']);assert sha(OUT/'prefreeze-audit-source-v1.py')==finding['audit_normalizer_source_sha256'] and found['training_pool_structural_family_overlaps']==finding['training_pool_structural_family_overlaps'] and not found['historical_structural_family_overlaps']
 revised=read(OUT/'input-family-revision-v1.json');assert revised['training_unchanged'] and revised['training_before_sha256']==revised['training_after_sha256'] and read(TRAIN/'candidates.json')==rejected['training'];pool=read(TEST/'pool-candidates.json');changed=[i for i,(a,b) in enumerate(zip(rejected['pool'],pool)) if a!=b];assert changed==list(range(48,56))+list(range(64,72))==revised['changed_pool_indices']
 return {'historical_formulas':len(history),'new_training_rows':32,'fresh_pool_rows':96,'original_alias_and_modular_identity_or_skeleton_collisions':0,'masked_shift_input_swap_commutative_family_collisions':0,'rejected16_prefreeze_family_overlaps_preserved_and_reproduced':True,'only_two_challenge_families_revised_before_freeze':True,'all_latest128_including72_unlabelled_consumed':True,'sound_modular_rules':previous.modular_rules_check(),'finite_screen_not_exhaustive_equivalence':True}


def profile_review():
 d=read(OUT/'measurement-input-profile-audit.json');check_bindings(d['sources']);rows=read(TRAIN/'candidates.json');assert len(rows)==32 and [r['formula'] for r in d['new_training']]==[r['formula'] for r in rows]
 counts={k:sum(any(p[k] for p in input_profiles(r['formula'])) for r in rows) for k in ('both_input_and_control','repeated_and_data_post_outer')};assert counts==d['group_counts']=={'both_input_and_control':16,'repeated_and_data_post_outer':16}
 for r in [*d['new_training'],*d['cohort_profiles']]:
  assert regression.ast_features(r['formula'])==r['features16']
  independent=input_profiles(r['formula']);assert len(independent)==len(r['profiles'])
  for a,b in zip(independent,r['profiles']):assert all(a[k]==b[k] for k in ('both_input_and_control','repeated_and_data_post_outer'))
 return {'training_profile_counts':counts,'new_training_and_pool_feature_vectors_independently_replayed':128,'all_four_consumed_failure_profiles_verified':prior_profile_review(),'coordinate_matches_not_cost_or_safety_guarantees':True}


def preflight(write=False):
 p=authenticate();count=preserved()
 check_bindings(read(OUT/'parent-preflight-validation.json')['bindings'])
 if write:assert not any((d/n).exists() for d in (TRAIN,TEST) for n in ('features.json','pool-features.json','feature-attempt.json','labels.json','label-attempt.json')) and not (OUT/'run-start.json').exists()
 feasibility=comparator_feasibility()
 for panel in feasibility['panels'].values():assert all(all(v.values()) for v in panel['six_original_accuracy_comparators_feasible'].values()) and all(panel['six_original_maximum_underprediction_comparators_feasible'].values())
 return receipt(TRAIN/'preflight-audit.json',{'bindings':bindings(),'scientific_artifacts_preserved':count,'identity_and_modular_novelty':identity_audit(),'input_profile_review':profile_review(),'analytical_comparator_feasibility':feasibility,'reviewed_policy':p['policy'],'reviewed_gates':p['gates'],'reviewed_selection':p['selection'],'one_fixed233_fit_on1889_plus32_no_consumed_labels':True,'fixed0_5_tie_acceptance_parameters_unchanged':True,'summed_worker_seconds300_peak2_and_parent_stage_authorization_required':True,'no_new_features_training_labels_fit_attempts_at_receipt':True,'postmeasurement_training_label_audit_required_before_fit':True},write)


def native_body(folder,name):
 if (folder/'raw').exists():return (folder/'raw'/name).read_bytes()
 with zipfile.ZipFile(folder/read(folder/'raw-evidence-manifest.json')['archive']) as z:return z.read('raw/'+name)


def stage_authorization(stage,write=False):
 name={'features':'feature','train-labels':'training-label','test-labels':'fresh-label'}[stage]+'-parent-authorization-at-audit.json';path=TRAIN/name
 if write and not path.exists():
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
  data=read(folder/filename);assert len(data['columns'])==336 and len(data['records'])==len(rows);x[kind]=matrix(rows,data)
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


def raw_audit(folder,allow_incomplete=False):
 rows=read(folder/'candidates.json');labels=read(folder/'labels.json');assert len(rows)==len(labels) and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
 manifest=read(folder/'raw-evidence-manifest.json');archive=folder/manifest['archive'];assert sha(archive)==manifest['archive_sha256'];members={r['path']:r for r in manifest['files']};kind='train' if folder==TRAIN else 'test'
 with zipfile.ZipFile(archive) as z:
  assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)
  for n,r in members.items():body=z.read(n);assert digest(body)==r['sha256'] and len(body)==r['bytes']
  get=lambda n:z.read('raw/'+n)
  feature_jobs=[j for j in read(TRAIN/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind];label_jobs=read(folder/'completion.json')['native_worker_jobs']
  for j in feature_jobs+label_jobs:
   directory='verification' if j['stage']=='verify' else j['stage']+'s/'+str(j['index']);assert json.loads(get(directory+'/worker.json'))==j
   if j['log_sha256'] is not None:assert digest(get(directory+'/worker.log'))==j['log_sha256']
   else:assert allow_incomplete and j['native_elapsed_seconds']==0 and 'raw/'+directory+'/worker.log' not in members
  proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode();assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148 and proof['random_seed']==read(TRAIN/'plan.json')['proof_random_seeds'][kind] and proof['total_comparisons']==2148*len(rows)
  assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256'];boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1];rng=random.Random(proof['random_seed']);expected=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)];parsed=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()];assert [(r[0],r[1]) for r in parsed]==expected;trees=[old.parse(r['formula']) for r in rows]
  for a,b,*targets in parsed:assert [old.evaluate(t,a,b) for t in trees]==targets
  assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
  for i,(row,label) in enumerate(zip(rows,labels)):
   if allow_incomplete and label['status']!='complete':
    assert label['status']=='failed' and label['formula']==row['formula'] and ('raw/'+f'labels/{i}/result.json') not in members
    continue
   assert label['status']=='complete' and label['formula']==row['formula'] and json.loads(get(f'labels/{i}/result.json'))==label
   net=get(f'labels/{i}/ice40-netlist.json');assert digest(net)==label['netlist_sha256'];c=Counter(v['type'] for v in json.loads(net)['modules']['candidate']['cells'].values());assert c['SB_LUT4']==label['lut4'] and c['SB_CARRY']==label['carry'];source=get(f'labels/{i}/candidate.v').decode();assert digest(source.encode())==label['rtl_sha256'] and source.replace('module candidate(',f'module candidate_{i}(') in rtl
   body=get(f'labels/{i}/metrics.json');m=json.loads(body);assert digest(body)==label['metrics_sha256'] and m['ice40_lut4_count']==label['lut4'] and m['ice40_carry_count']==label['carry'] and m['measurement_source']=='rtl_synthesis' and 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
  features=read(folder/('features.json' if kind=='train' else 'pool-features.json'))
  for i,r in enumerate(features['records']):assert json.loads(get(f'features/{i}/result.json'))==r
 result={'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':sum(r['status']=='complete' for r in labels),'independent_original_RV32_comparisons':2148*len(rows),'feature_results_authenticated':len(features['records']),'worker_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}
 if allow_incomplete:result.update({'selected_status_records_authenticated':len(rows),'completed_labels':sum(r['status']=='complete' for r in labels),'failed_or_unattempted_labels':sum(r['status']!='complete' for r in labels),'all_partial_timeout_and_unattempted_raw_members_preserved':True})
 return result


def training_labels(write=False):
 import numpy as np
 authenticate();pretrain(False);count=preserved();jobs=chronology('training');proof=raw_audit(TRAIN)
 if write:assert not (OUT/'run-start.json').exists() and not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 oldrows=read(PRIOR/'training-manifest.json')['rows'];new=read(TRAIN/'candidates.json');targets=np.asarray([r['lut4'] for r in read(TRAIN/'labels.json')]);oldids={r['candidate_id'] for r in oldrows};consumed={cid for row in frozen_panels().values() for cid in row['candidate_ids']};consumed_formulas={f for row in frozen_panels().values() for f in row['formulas']};assert len(new)==32 and not {r['candidate_id'] for r in new}&(oldids|consumed) and not {r['formula'] for r in new}&consumed_formulas
 with np.load(PRIOR/'training-inputs.npz',allow_pickle=False) as d:
  assert d['coverage'].shape==(1889,217) and d['augmented'].shape==(1889,233) and np.array_equal(d['coverage'],d['augmented'][:,:217]) and np.array_equal(d['y'],np.asarray([r['actual_lut4'] for r in oldrows]));combined=np.concatenate((d['y'],targets))
 membership={'frozen_prefix_rows':1889,'new_rows':32,'total_planned_rows':1921,'new_training_IDs_and_formulas_disjoint_from_all1073_consumed_evaluation_records':True,'frozen_ordered_prefix_features_and_targets_authenticated':True,'new_training_label_minimum':int(targets.min()),'new_training_label_maximum':int(targets.max()),'new_training_class_counts':{str(c):{'feasible':int((targets<=c).sum()),'infeasible':int((targets>c).sum())} for c in CAPS},'combined_class_counts':{str(c):{'feasible':int((combined<=c).sum()),'infeasible':int((combined>c).sum())} for c in CAPS},'fit_matrices_and_leaf_membership_to_be_verified_after_single_fit':True}
 auth=stage_authorization('train-labels',write);files=[auth,TRAIN/'labels.json',TRAIN/'completion.json',TRAIN/'raw-evidence-manifest.json',TRAIN/read(TRAIN/'raw-evidence-manifest.json')['archive'],TRAIN/'pretrain-audit.json']
 return receipt(TRAIN/'training-label-audit.json',{'bindings':{**bindings(),**{relative(p):sha(p) for p in files}},'scientific_artifacts_preserved':count,'native_accounting':jobs,'new_training_labels_independently_verified':32,'native_RTL_proof_netlists_and_measurements':proof,'training_membership':membership,'fresh_labels_and_fit_attempts_absent_at_receipt':True,'parent_must_bind_this_receipt_and_training_labels_features_completion_before_one_fit':True,'immutable_training_label_authorization_snapshot':relative(auth)},write)


_MODEL=None


def model_audit():
 global _MODEL
 if _MODEL is not None:return _MODEL
 import numpy as np,joblib
 from sklearn.ensemble import ExtraTreesClassifier
 p=authenticate();seal=read(OUT/'model-freeze.json');assert seal['protocol_sha256']==sha(OUT/'protocol.json') and seal['fits_completed']==1 and seal['wall_seconds']<=120 and seal['feature_freeze_sha256']==sha(OUT/'feature-freeze.json');check_bindings(seal['files_sha256'],OUT)
 oldrows=read(PRIOR/'training-manifest.json')['rows'];new=read(TRAIN/'candidates.json');ynew=np.asarray([r['lut4'] for r in read(TRAIN/'labels.json')]);nf=matrix(new,read(TRAIN/'features.json'))
 with np.load(PRIOR/'training-inputs.npz',allow_pickle=False) as d:oldbase=d['coverage'].copy();oldaug=d['augmented'].copy();oldy=d['y'].copy()
 base=np.vstack((oldbase,nf));x=np.vstack((oldaug,np.hstack((nf,np.asarray([regression.ast_features(r['formula']) for r in new])))));y=np.concatenate((oldy,ynew));labels=(y[:,None]<=np.asarray(CAPS)[None,:]).astype(np.uint8)
 assert base.shape==(1921,217) and x.shape==(1921,233) and np.array_equal(base,x[:,:217]);assert np.array_equal(oldy,np.asarray([r['actual_lut4'] for r in oldrows]))
 with np.load(OUT/'training-inputs.npz',allow_pickle=False) as d:assert np.array_equal(d['coverage'],base) and np.array_equal(d['augmented'],x) and np.array_equal(d['y'],y) and np.array_equal(d['feasibility'],labels)
 expected=[{'candidate_id':r['candidate_id'],'formula':r['formula'],'actual_lut4':float(oldy[i]),'fit_source':'frozen1889'} for i,r in enumerate(oldrows)]+[{'candidate_id':r['candidate_id'],'formula':r['formula'],'actual_lut4':float(ynew[i]),'fit_source':'new_training32'} for i,r in enumerate(new)]
 manifest=read(OUT/'training-manifest.json');assert manifest['rows']==expected and manifest['consumed_evaluation_labels_fitted']==0 and manifest['new_training_labels']==32
 consumed={cid for r in frozen_panels().values() for cid in r['candidate_ids']};assert not consumed&{r['candidate_id'] for r in expected}
 auth=read(OUT/'execution-authorization.json');assert auth['authorizer']=='parent' and auth['protocol_sha256']==sha(OUT/'protocol.json') and auth['allow_one_classifier_fit'] is True;check_bindings(auth['bindings'])
 for q in (TRAIN/'labels.json',TRAIN/'features.json',TRAIN/'completion.json',TRAIN/'training-label-audit.json'):assert auth['bindings'][relative(q)]==sha(q)
 start=read(OUT/'run-start.json');attempt=read(OUT/'fit-attempt-1.json');assert len(list(OUT.glob('fit-attempt-*.json')))==1 and start['authorization_sha256']==sha(OUT/'execution-authorization.json') and start['training_labels_sha256']==sha(TRAIN/'labels.json') and start['training_features_sha256']==sha(TRAIN/'features.json')
 assert read(TRAIN/'completion.json')['completed_at_utc']<read(TRAIN/'training-label-audit.json')['audited_at_utc']<start['started_at_utc']<=attempt['started_at_utc']<seal['frozen_at_utc'];assert attempt['training_count']==1921 and attempt['feature_count']==233 and attempt['kind']=='augmented' and attempt['sample_weight'] is None and attempt['training_inputs_sha256']==sha(OUT/'training-inputs.npz')
 model=joblib.load(OUT/'augmented.joblib');meta=read(OUT/'augmented.json');assert type(model) is ExtraTreesClassifier and model.get_params()==ExtraTreesClassifier(**p['configuration_all_parameters']).get_params() and model.n_features_in_==233 and model.n_outputs_==3 and len(model.estimators_)==300
 classes=[np.asarray(c) for c in model.classes_];assert all(np.array_equal(c,np.unique(labels[:,j])) for j,c in enumerate(classes));assert meta['classes_by_cap']==[c.tolist() for c in classes] and meta['outputs']==list(CAPS) and meta['positive_class']==1 and meta['sample_weight'] is None and meta['training_count']==1921 and meta['new_training_count']==32 and meta['consumed_labels_fitted']==0 and meta['artifact_sha256']==sha(OUT/'augmented.joblib')
 leaves=0
 for tree in model.estimators_:
  assert tree.tree_.n_node_samples[0]==1921 and tree.n_outputs_==3;leaf=tree.apply(x);count=np.bincount(leaf,minlength=tree.tree_.node_count);used=count>0;assert (tree.tree_.children_left[used]==-1).all() and np.array_equal(count[used],tree.tree_.n_node_samples[used]) and np.allclose(tree.tree_.weighted_n_node_samples[used],count[used],rtol=0,atol=1e-12);positive=[]
  for j,c in enumerate(classes):
   sums=np.bincount(leaf,weights=labels[:,j],minlength=tree.tree_.node_count);expect=sums[used]/count[used]
   for k,label in enumerate(c):assert np.allclose(tree.tree_.value[used,j,k],expect if label==1 else 1-expect,rtol=0,atol=PROB_TOL)
   positive.append(expect)
  assert (np.diff(np.column_stack(positive),axis=1)>=-PROB_TOL).all();leaves+=int(used.sum())
 previous.probabilities(model,x)
 proof={'training_rows':1921,'frozen1889_prefix_order_features_and_targets_exact':True,'new_training_labels':32,'consumed_evaluation_labels_fitted':0,'selected_features':233,'trees_verified':300,'new_training_leaf_assignments_checked':1921*300,'nested_binary_training_assignments_checked':1921*300*3,'leaf_class_counts_probabilities_and_equal_sample_weights_verified':leaves,'classes_by_cap':[c.tolist() for c in classes],'monotone_leaf_probabilities_without_sorting':True,'frozen1889_classifier_and_old_regressor_forensics_reused_by_immutable_hash':True,'fit_records':read(OUT/'timings.json')}
 _MODEL=(model,proof);return _MODEL


def candidate_points(formulas,features,old_values):
 import numpy as np
 base=matrix([{'formula':f} for f in formulas],features);x=np.hstack((base,np.asarray([regression.ast_features(f) for f in formulas])));model,_=model_audit();p=previous.probabilities(model,x).tolist();cells=[[r['cell'] for r in regression.cells(f)] for f in formulas];known=set(read(OUT/'support-cells.json')['supported_cells']);covered=[bool(r) and all(c in known for c in r) for r in cells];out=[];caps=[]
 for s,r,prob,scope in zip(old_values[CURRENT],old_values[RELEASE],p,covered):
  eligible=[c for j,c in enumerate(CAPS) if scope and s<=c<r and prob[j]>=.5];caps.append(eligible);out.append(min(eligible) if eligible else r)
 return out,{'coverage_cells':cells,'coverage_covered':covered,'coverage_feasibility_probabilities':{NAME:p},'coverage_supported_caps':{NAME:caps}}


def metrics(y,values,probabilities=None,validated=False):
 import numpy as np
 m={n:old.metrics(y,v) for n,v in values.items()};refs=(*REFERENCES,BASELINE) if validated else REFERENCES;v=values[NAME]
 m['checks']={NAME:{'accuracy_no_worse':{n:feature.accuracy(m[n],m[NAME]) for n in refs},'caps':{str(c):{'false_accept_no_worse_release':m[NAME]['caps'][str(c)]['false_accept']<=m[RELEASE]['caps'][str(c)]['false_accept'],'false_reject_no_worse_signed':m[NAME]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject'],'no_new_false_accept_cases':not any(v[i]<=c<values[RELEASE][i] and y[i]>c for i in range(len(y))),'no_new_false_reject_cases':not any(values[CURRENT][i]<=c<v[i] and y[i]<=c for i in range(len(y)))} for c in CAPS},'maximum_underprediction_no_worse':all(m[NAME]['maximum_underprediction_lut4']<=m[n]['maximum_underprediction_lut4']+TOL for n in (*refs,CURRENT)),'pointwise_bounds':all(s<=p<=r for s,p,r in zip(values[CURRENT],v,values[RELEASE])),'events':{n:feature.prior.cap_events(values[n],v,y) for n in (*refs,CURRENT)}}}
 if probabilities is not None:m['probability_metrics']={NAME:{str(c):{'brier_score':float(np.mean((np.asarray(probabilities)[:,j]-(np.asarray(y)<=c))**2)),'raw_probability_decision_errors':int(np.sum((np.asarray(probabilities)[:,j]>=.5)!=(np.asarray(y)<=c)))} for j,c in enumerate(CAPS)}}
 return m


def development():
 import learn_control_sharing_coverage as m
 frozen=frozen_panels();saved=read(OUT/'development-predictions.json');assert set(saved)==set(frozen);stored=read(OUT/'development-metrics.json')
 for n,(rows,x,y) in m.panel_inputs():
  row=saved[n];oldrow=frozen[n];assert row['candidate_ids']==oldrow['candidate_ids'] and row['formulas']==oldrow['formulas'] and row['actual_lut4']==oldrow['actual_lut4'];assert {k:v for k,v in row['models'].items() if k!=NAME}==oldrow['models']
  columns=list(m.prior.v6.columns());features={'columns':columns,'records':[{'formula':r['formula'],'values':v.tolist(),'status':'complete'} for r,v in zip(rows,x)]};p,details=candidate_points(row['formulas'],features,row['models']);assert p==row['models'][NAME]
  for k,v in details.items():assert row[k]==v,(n,k)
  own=metrics(y,row['models'],details['coverage_feasibility_probabilities'][NAME],n in m.VALIDATED_PANELS);old.compare_metric(stored['panels'][n],own)
 # Named membership definitions are reviewed against the preserved identities;
 # numeric panel/cap gates and new probabilities above are independent.
 expected=m.development_metrics(saved);assert expected==stored and len(stored['named_regressions'])==33
 return {'gates':stored['gates'],'selected_candidate':stored['selected_candidate'],'evaluated_candidate':stored['evaluated_candidate'],'retained_metric_rows':1113,'retained_circuit_records':1073,'shared_controls':40,'named_subsets':list(stored['named_regressions']),'evaluation_cases':stored['evaluation_cases'],'new_candidate_retained_predictions_independently_replayed':1113,'old12_policy_points_reused_by_prior_artifact_hash':1113*12}


def select(pool,values,fresh,evaluated):
 groups={c:[i for i,r in enumerate(pool) if r['cohort']==c] for c in ('general','sharing','legacy')};fixed=groups['general']+groups['sharing']+groups['legacy'];controls=[i for i,r in enumerate(pool) if r['reserved_control']];reps={k:r['pool_cluster_representatives'] for k,r in fresh['representations'].items()};history=set().union(*(r['pool_historical_or_training_matches'] for r in fresh['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()}
 raw=[i for i,r in enumerate(pool) if r['cohort']=='challenge' and any(values[evaluated][i]<=c<values[BASELINE][i] for c in CAPS)];collision=[i for i in raw if any(reps[k][i] in seen[k] for k in reps)];eligible=[i for i in raw if i not in history and i not in collision];queues={}
 for i in eligible:queues.setdefault(pool[i]['template'],[]).append(i)
 active=[];skipped=[]
 while len(active)<16 and any(queues.values()):
  for template in sorted(queues):
   if len(active)>=16:break
   while queues[template] and any(reps[k][queues[template][0]] in seen[k] for k in reps):skipped.append(queues[template].pop(0))
   if queues[template]:
    i=queues[template].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 selected=fixed+active;selection={**{c+'_pool_indices':v for c,v in groups.items()},'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in history],'fixed_feature_collision_active_pool_indices':collision,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':selected};checks={}
 for k,r in fresh['representations'].items():
  keys=r['pool_cluster_representatives'];checks[k+'_fixed_novel']=not bool(set(r['pool_historical_or_training_matches'])&set(fixed));checks[k+'_fixed_unique']=len({keys[i] for i in fixed})==48;checks[k+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[BASELINE][i] for i in active) for c in CAPS};legacy=[i for i in groups['legacy'] if values[previous.ABSTENTION][i]<=64<values[evaluated][i]];sharing=[i for i in groups['sharing'] if values[previous.LEARNED][i]<=128<values[evaluated][i]]
 checks.update({'at_least_four_new_acceptances':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1,'at_least_one_legacy64_veto':len(legacy)>=1,'at_least_one_sharing128_veto':len(sharing)>=1})
 coverage={'pool_count':96,'general_count':32,'sharing_count':8,'legacy_count':8,'shared_control_count':8,'raw_active_count':len(raw),'eligible_active_count':len(eligible),'selected_active_count':len(active),'selected_templates':templates,'acceptance_caps':caps,'legacy64_veto_count':len(legacy),'legacy64_veto_pool_indices':legacy,'sharing128_veto_count':len(sharing),'sharing128_veto_pool_indices':sharing,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}
 return selection,coverage


def fresh_points():
 import numpy as np
 import learn_boundary_feasibility as baseline
 import learn_control_sharing_coverage as m
 dev=development();pool=read(TEST/'pool-candidates.json');f=read(TEST/'pool-features.json');stored=read(OUT/'pool-predictions.json');matrix(pool,f);x=np.asarray([r['values'] for r in f['records']])
 oldvalues,routes,details=baseline.points(pool,x,baseline.load(PRIOR),read(PRIOR/'support-cells.json'));candidate,extra=candidate_points([r['formula'] for r in pool],f,oldvalues);values={**oldvalues,NAME:candidate};details.update(extra)
 assert stored['models']==values and stored['routes']==routes and stored['candidate_ids']==[r['candidate_id'] for r in pool] and stored['formulas']==[r['formula'] for r in pool] and stored['templates']==[r['template'] for r in pool]
 for k,v in details.items():assert stored[k]==v,k
 fresh=feature_review();selection,coverage=select(pool,values,fresh,dev['evaluated_candidate']);s=read(TEST/'selection.json')
 for k,v in selection.items():assert s[k]==v,k
 assert s['coverage']==coverage and s['labels_present'] is False and s['pool_predictions_sha256']==sha(OUT/'pool-predictions.json')
 ix=selection['selected_pool_indices'];saved=read(OUT/'fresh-predictions.json');assert read(TEST/'candidates.json')==[pool[i] for i in ix] and read(TEST/'features.json')=={'columns':f['columns'],'records':[f['records'][i] for i in ix]}
 for k in ('candidate_ids','formulas','templates','routes',*details):
  assert saved[k]==({n:[v[i] for i in ix] for n,v in stored[k].items()} if isinstance(stored[k],dict) else [stored[k][i] for i in ix]),k
 assert saved['models']=={n:[v[i] for i in ix] for n,v in values.items()} and saved['general_selected_indices']==list(range(32)) and saved['sharing_selected_indices']==list(range(32,40)) and saved['legacy_selected_indices']==list(range(40,48)) and saved['active_selected_indices']==list(range(48,len(ix))) and saved['shared_control_selected_indices']==list(range(24,32)) and saved['conditional_selected_indices']==list(range(48,len(ix)))+list(range(24,32))
 assert saved['selection_coverage']==coverage and saved['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==dev['evaluated_candidate']
 seal=read(OUT/'fresh-point-freeze.json');bridge=read(TEST/'point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0 and bridge['target_label_jobs']==0;check_bindings(seal['bindings']);check_bindings(bridge['bindings']);assert read(OUT/'model-freeze.json')['frozen_at_utc']<stored['created_at_utc']<s['frozen_at_utc']<seal['frozen_at_utc']
 return saved,dev,fresh


def cached_inference(saved):
 c=read(OUT/'cached-inference-check.json');assert c['model']==saved['evaluated_candidate'] and c['selected_candidate']==saved['selected_candidate'] and c['fits']==c['native_jobs']==0 and c['calibration_status']=='uncalibrated' and c['upper_lut4'] is None
 required=('candidate_ids','formulas','models','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap','learning_scope','learned_raw_lut4','learned_supported_caps_lut4','coverage_guard','pipeline_cells','pipeline_covered','corroboration_raw_lut4','corroborated_caps_lut4','proposal_provenance','feasibility_cells','feasibility_covered','feasibility_probabilities','feasibility_supported_caps','coverage_cells','coverage_covered','coverage_feasibility_probabilities','coverage_supported_caps')
 for k in required:assert k in c and c[k]==saved[k],k
 for k,v in saved.items():
  if k in c and k not in ('schema','created_at_utc'):assert c[k]==v,k
 assert c['predicted_lut4']==saved['models'][saved['evaluated_candidate']] and c['protocol_sha256']==sha(OUT/'protocol.json') and c['features_sha256']==sha(TEST/'features.json') and c['candidates_sha256']==sha(TEST/'candidates.json')
 return {'artifact_sha256':sha(OUT/'cached-inference-check.json'),'thirteen_model_points_and_all_fields_checked':13*len(saved['candidate_ids']),'uncalibrated':True,'fits':0,'native_jobs':0}


def training_profile_truth_review():
 profile=read(OUT/'measurement-input-profile-audit.json');labels=read(TRAIN/'labels.json');training=profile['new_training'];result=[]
 for target in profile['consumed_target_profiles']:
  matches=[i for i,row in enumerate(training) if row['features16']==target['features16']];costs=[labels[i]['lut4'] for i in matches];assert len(matches)==target['matches']['new32']['full16']==2
  result.append({'consumed_selected_index':target['selected_index'],'matched_new_training_indices':matches,'matched_new_costs_lut4':costs,'feasible_at128':sum(c<=128 for c in costs),'infeasible_at128':sum(c>128 for c in costs)})
 assert next(r for r in result if r['consumed_selected_index']==36)['matched_new_costs_lut4']==[125,127]
 for r in result:
  if r['consumed_selected_index'] in (51,53,55):assert sorted(r['matched_new_costs_lut4'])==[125,128]
 return {'cases':result,'matching16_descriptors_does_not_imply_matching_area_or_safe_transfer':True,'unsafe_consumed129_130_129_profiles_have_only_feasible_matching_new_training_examples':True,'new_training_has13_infeasible_at128_overall_but_not_in_these_exact_profile_matches':True,'postmeasurement_descriptive_only_no_recipe_or_cohort_changes':True}


def prelabel(write=False):
 authenticate();count=preserved();training_labels(False);saved,dev,fresh=fresh_points();_,proof=model_audit();jobs=chronology('training')
 if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 files=[OUT/n for n in ('execution-authorization.json','feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-point-freeze.json','fresh-predictions.json','cached-inference-check.json')]+[TRAIN/n for n in ('pretrain-audit.json','training-label-audit.json','feature-parent-authorization-at-audit.json','training-label-parent-authorization-at-audit.json')]+[TEST/n for n in ('selection.json','candidates.json','features.json','point-freeze.json','pool-features.json')]
 return receipt(TEST/'prelabel-audit.json',{'bindings':{**bindings(),**{relative(p):sha(p) for p in files}},'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,'development':dev,'new_training_matrix_and_leaf_probability_audit':proof,'feature_freshness':fresh,'selection_coverage':saved['selection_coverage'],'all96_pool_new_classifier_probability_values_replayed':96*3,'all13_selected_policy_points_replayed':13*len(saved['candidate_ids']),'baseline1889_classifier_reused_without_fit_or_repeated_old_leaf_forensics':True,'cached_inference':cached_inference(saved),'native_accounting_to_date':jobs,'fixed48_always_labelled_shared_controls_not_independent':True,'conditional_population_prediction_selected_not_representative':True,'no_pooled_metric':True,'fixed_half_tie_and_monotone_shared_tree_probabilities_verified':True},write)


def incomplete_native_review():
 from datetime import datetime
 prior=chronology('training');r=read(TEST/'completion.json');assert not r['complete'] and r['failures'] and r['label_count']==16;workers=r['native_worker_jobs'];assert Counter(j['stage'] for j in workers)=={'verify':1,'label':55}
 launched=[j for j in workers if j['native_elapsed_seconds']>0];unattempted=[j for j in workers if j['native_elapsed_seconds']==0];timeout=[j for j in launched if j['error']];complete=[j for j in launched if not j['error']];assert len(launched)==19 and len(unattempted)==37 and len(timeout)==2 and len(complete)==17
 assert all(j['stage']=='label' and j['returncode'] is None and j['log_sha256'] is None and 'Sharednativedeadlineexhausted' in j['error'] for j in unattempted);assert all(j['stage']=='label' and j['returncode'] is None and 'TimeoutError' in j['error'] for j in timeout)
 summed=sum(j['native_elapsed_seconds'] for j in workers);budget=300-prior['summed_worker_native_seconds'];assert math.isclose(summed,r['native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(summed,r['summed_worker_native_seconds'],abs_tol=1e-9) and math.isclose(r['native_budget_seconds'],budget,abs_tol=1e-9) and math.isclose(r['stage_wall_budget_seconds'],(budget-1)/2,abs_tol=1e-9)
 total=prior['summed_worker_native_seconds']+summed;assert math.isclose(total,r['total_native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(total,r['total_summed_worker_native_seconds'],abs_tol=1e-9) and total<=300
 reports=[read(TRAIN/'feature-completion.json'),read(TRAIN/'completion.json'),r];events=[]
 for report in reports:
  for j in report['native_worker_jobs']:
   interval=(datetime.fromisoformat(j['finished_at_utc'])-datetime.fromisoformat(j['started_at_utc'])).total_seconds();assert 0<=j['native_elapsed_seconds']<=j['job_wall_elapsed_seconds']+1e-9<=interval+.01
   if j['native_elapsed_seconds']>0:events.extend(((j['started_at_utc'],1),(j['finished_at_utc'],-1)))
 active=peak=0
 for _,n in sorted(events,key=lambda e:(e[0],e[1])):active+=n;peak=max(peak,active)
 assert active==0 and peak<=2;assert max(j['finished_at_utc'] for j in reports[1]['native_worker_jobs'])<min(j['started_at_utc'] for j in workers)
 assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc'] and read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in workers)
 assert max(j['finished_at_utc'] for j in workers if j['stage']=='verify')<min(j['started_at_utc'] for j in launched if j['stage']=='label')
 return {'summed_worker_native_seconds':total,'stage_wall_seconds_separately':prior['stage_wall_seconds_separately']+r['stage_wall_elapsed_seconds'],'recorded_worker_peak':peak,'native_budget_unit':'summed_worker_process_seconds','native_jobs':sum(j['native_elapsed_seconds']>0 for report in reports for j in report['native_worker_jobs']),'scheduled_worker_status_records':sum(len(report['native_worker_jobs']) for report in reports),'fresh_launched_processes':19,'fresh_worker_status_records':56,'fresh_completed_label_processes':16,'fresh_timeout_processes':2,'fresh_unattempted_label_records':37,'fresh_verification_processes':1,'fresh_summed_worker_seconds':summed,'fresh_stage_wall_seconds':r['stage_wall_elapsed_seconds'],'fresh_stage_wall_deadline_seconds':r['stage_wall_budget_seconds'],'unused_summed_budget_seconds':300-total,'no_retry_extension_replacement_or_slack_reuse':True}


def incomplete_audit(write=False):
 authenticate();count=preserved();prelabel(False);saved,dev,fresh=fresh_points();_,proof=model_audit();jobs=incomplete_native_review();rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert len(rows)==len(labels)==55 and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels] and saved['candidate_ids']==[r['candidate_id'] for r in rows]
 completed=[i for i,r in enumerate(labels) if r['status']=='complete'];failed=[i for i,r in enumerate(labels) if r['status']=='failed'];assert completed==list(range(16)) and failed==list(range(16,55));assert not (OUT/'fresh-metrics.json').exists(),'Incomplete primary populations must not be scored'
 auth=stage_authorization('test-labels',write);native=raw_audit(TEST,True);outcome=read(OUT/'incomplete-outcome.json')
 assert outcome['scoped_experimental_eligibility'] is False
 for k in ('bindings','sources'):
  if isinstance(outcome.get(k),dict):check_bindings(outcome[k])
 diagnostics=read(OUT/'failure-diagnostics.json')
 for k in ('bindings','sources'):
  if isinstance(diagnostics.get(k),dict):check_bindings(diagnostics[k])
 lookup={cid:(row,i) for row in read(OUT/'development-predictions.json').values() for i,cid in enumerate(row['candidate_ids'])};targets=read(OUT/'evaluation-targets.json');required=[]
 for expected,key in (('accept','required_acceptances'),('reject','required_rejections')):
  for t in targets[key]:
   row,i=lookup[t['candidate_id']];p=row['models'][NAME][i];passed=(p<=t['cap']) if expected=='accept' else (p>t['cap']);required.append({'candidate_id':t['candidate_id'],'formula':t['formula'],'actual_lut4':t['actual_lut4'],'cap':t['cap'],'expected':expected,'prediction_lut4':p,'probability':row['coverage_feasibility_probabilities'][NAME][i][CAPS.index(t['cap'])],'passed':passed})
 bad=[r for r in required if not r['passed']];assert len(bad)==4 and sorted(r['actual_lut4'] for r in bad)==[129,129,130,157] and all(r['expected']=='reject' and r['cap']==128 for r in bad)
 statuses={}
 for name,key in (('general32','general_selected_indices'),('sharing8','sharing_selected_indices'),('legacy8','legacy_selected_indices'),('conditional_full','conditional_selected_indices'),('active_only','active_selected_indices')):
  ix=saved[key];statuses[name]={'required_count':len(ix),'completed_count':sum(i in completed for i in ix),'missing_count':sum(i not in completed for i in ix),'primary_evaluation_status':'not_evaluable_incomplete','primary_metrics':None,'gate_passed':False}
 assert statuses['general32']['completed_count']==16 and all(statuses[k]['completed_count']==0 for k in ('sharing8','legacy8','conditional_full','active_only'))
 c=dev['gates'][NAME];scientific={'development_selected_candidate_exists':dev['selected_candidate'] is not None,'all26_retained1113_metric_rows1073_records_preserved':c['all_twenty_six_panels_pass'],'all33_named_subgroups_preserved':c['all_named_subgroups_preserved'],'all62_required_acceptances_original_and_latest_repairs':c['all_required_acceptances_pass'],'all38_protected_rejections_including129_130_129_and157':c['all_required_rejections_pass'],'fresh_all55_required_labels_complete':False,'fresh_general32_strict_signed_gains_and_all_comparators_proven':False,'fresh_sharing8_hard_gates_proven':False,'fresh_legacy8_hard_gates_proven':False,'fresh_conditional_full_hard_gates_proven':False,'fresh_active_only_hard_gates_proven':False,'prospective_activity_and_feature_novelty_gates_pass':saved['selection_coverage']['passed'],'exact1921_training_one_fixed233_fit_no_consumed_labels':True,'new1921_shared_tree_leaf_targets_class_mapping_and_nested_probabilities_verified':True,'model_all96_points_and55selection_frozen_before_fresh_labels':True,'true_summed_worker_seconds_at_most300_and_peak2':jobs['summed_worker_native_seconds']<=300 and jobs['recorded_worker_peak']<=2,'all1008_prior_scientific_files_preserved_status_only_goal_exception':count==1008,'all_failed_partial_and_unattempted_evidence_preserved_without_retry':True,'no_full_population_metrics_inferred_from16_completed':True};assert not all(scientific.values())
 files=[auth,OUT/'incomplete-outcome.json',OUT/'failure-diagnostics.json',TEST/'completion.json',TEST/'labels.json',TEST/'raw-evidence-manifest.json',TEST/read(TEST/'raw-evidence-manifest.json')['archive']]
 observations=[{'selected_index':i,'pool_index':rows[i]['pool_index'],'candidate_id':rows[i]['candidate_id'],'formula':rows[i]['formula'],'actual_lut4':labels[i]['lut4'],'prediction_lut4':saved['models'][NAME][i]} for i in completed]
 body={'bindings':{relative(p):sha(p) for p in files},'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'original_goal_ledger_status_only_mutable':True,'current_goal_clarification_fully_preserved':True,'integrity_status':'pass','validation_outcome':'incomplete_fresh_measurement_and_failed_development','fits':1,'new_training_labels':32,'training_rows':1921,'new_training_matrix_and_leaf_probability_proof':proof,'frozen_baseline_forensics_reused_by_immutable_hash':True,'native_accounting':jobs,'identity_modular_and_lowbit_inputswap_family_novelty':identity_audit(),'input_profile_coverage':profile_review(),'observed_training_profile_targets':training_profile_truth_review(),'analytical_comparator_feasibility':comparator_feasibility(),'feature_freshness':fresh,'training_native_raw_evidence':read(TRAIN/'training-label-audit.json')['native_RTL_proof_netlists_and_measurements'],'fresh_native_raw_evidence':native,'cached_inference':cached_inference(saved),'development':dev,'required_decision_cases':required,'failed_required_rejections':bad,'fresh_population_status':statuses,'fresh_general32':None,'fresh_sharing8':None,'fresh_legacy8':None,'fresh_conditional_full':None,'fresh_active_only':None,'fresh_gates':None,'selected_candidate':None,'evaluated_candidate':NAME,'scoped_experimental_eligibility':False,'selection_coverage':saved['selection_coverage'],'pool_count':96,'selected_unique_label_count':55,'completed_fresh_labels':16,'timeout_fresh_labels':2,'unattempted_fresh_labels':37,'completed_selected_indices':completed,'timeout_selected_indices':[16,17],'unattempted_selected_indices':list(range(18,55)),'completed_observations_descriptive_only':observations,'completed_observations_are_not_any_complete_fresh_population':True,'all41_unselected_pool_rows_and_all96_features_probabilities_retained':True,'shared_control_count':8,'shared_controls_not_independent':True,'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':False,'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,'fresh_primary_metrics_intentionally_absent':True,'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,'false_acceptance_sum_unit':'Circuit-budget events, not unique circuits. No full fresh cap rates or accuracy metrics are reported with missing labels.','mape_definition':'100*mean(abs(actual-prediction)/actual) over actual>0; zero targets remain in MAE, cap and tail metrics. No primary fresh MAPE estimated here.','limitations':['The conservative predeclared native wall deadline stopped the attempt with16/55 labels,2 timeouts and37 unattempted. Remaining summed-process margin is not authorization for a retry.','Four protected consumed rejection targets still fail despite all62 required acceptances passing; scientific development eligibility was already false before fresh labels.','Exact16-descriptor matches for the unsafe129/130/129 targets are feasible125/128 training examples; descriptor coverage does not establish unsafe-class coverage or cost transfer.','Finite originalRTL vector proof covers all55 selected formulas, while mapped-netlist synthesis labels exist for only16; these are different evidence types.','One fixed training-coverage intervention, uncalibrated probabilities, finite novelty screens and no CPU, timing, power or universal safety claim.']}
 return receipt(OUT/'audit.json',body,write)


def final_audit(write=False):
 if not read(TEST/'completion.json')['complete']:return incomplete_audit(write)
 authenticate();count=preserved();prelabel(False);jobs=chronology('fresh');saved,dev,fresh=fresh_points();_,proof=model_audit();rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels];y=[r['lut4'] for r in labels];stored=read(OUT/'fresh-metrics.json')
 def sub(ix,validated=False):return metrics([y[i] for i in ix],{n:[v[i] for i in ix] for n,v in saved['models'].items()},[saved['coverage_feasibility_probabilities'][NAME][i] for i in ix],validated)
 general=sub(saved['general_selected_indices'],True);sharing=sub(saved['sharing_selected_indices']);legacy=sub(saved['legacy_selected_indices'],True);conditional=sub(saved['conditional_selected_indices']);active=sub(saved['active_selected_indices']) if saved['active_selected_indices'] else None
 fields=sum(old.compare_metric(stored[k],v) for k,v in (('models',general),('sharing_models',sharing),('legacy_models',legacy),('conditional_models',conditional)))
 if active:fields+=old.compare_metric(stored['active_subgroup'],active)
 else:assert stored['active_subgroup'] is None
 ix=[i for i in saved['active_selected_indices'] if any(saved['models'][NAME][i]<=c<saved['models'][BASELINE][i] for c in CAPS)];activity={'acceptances':len(ix),'templates':len({saved['templates'][i] for i in ix}),'cap128':sum(saved['models'][NAME][i]<=128<saved['models'][BASELINE][i] for i in ix),'legacy64_veto':sum(saved['models'][previous.ABSTENTION][i]<=64<saved['models'][NAME][i] for i in saved['legacy_selected_indices']),'sharing128_veto':sum(saved['models'][previous.LEARNED][i]<=128<saved['models'][NAME][i] for i in saved['sharing_selected_indices'])};activity_ok=activity['acceptances']>=4 and activity['templates']>=2 and activity['cap128']>=1 and activity['legacy64_veto']>=1 and activity['sharing128_veto']>=1
 checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_ok,'general_no_loss':previous.passed(general['checks'][NAME]),'general_strict_signed':feature.accuracy(general[CURRENT],general[NAME],True),'general_strict_fa_gain_signed':sum(general[NAME]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),'sharing_passes':previous.passed(sharing['checks'][NAME]),'legacy_passes':previous.passed(legacy['checks'][NAME]),'conditional_full_passes':previous.passed(conditional['checks'][NAME]),'active_subset_passes':bool(active and previous.passed(active['checks'][NAME]))}
 ok=checks['coverage']['passed'] and activity_ok and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['sharing_passes'] and checks['legacy_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes'];chosen=dev['selected_candidate'];eligible=ok and chosen==NAME;gate={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][NAME]['development_gate_passed'],'eligible':eligible};assert stored['gates']=={NAME:gate} and stored['scoped_experimental_eligibility']==eligible and stored['selected_candidate']==chosen and stored['evaluated_candidate']==NAME
 assert stored['selection_coverage']==saved['selection_coverage'] and stored['general_count']==32 and stored['sharing_count']==stored['legacy_count']==8 and stored['active_count']==len(saved['active_selected_indices']) and stored['conditional_count']==len(saved['conditional_selected_indices']) and stored['shared_controls']==8 and stored['unique_label_count']==len(y) and stored['fits']==1 and stored['native_jobs']==0 and stored['no_pooled_metric'] and stored['fresh_labels_sha256']==sha(TEST/'labels.json')
 auth=stage_authorization('test-labels',write);assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<read(TEST/'label-attempt.json')['started_at_utc'];native=raw_audit(TEST)
 def decisions(ix):
  result={}
  for ref in (CURRENT,*REFERENCES,BASELINE):
   caps={}
   for c in CAPS:
    events=[]
    for i in ix:
     before=saved['models'][ref][i];after=saved['models'][NAME][i]
     if (before<=c)==(after<=c):continue
     event=('corrected_false_reject' if y[i]<=c else 'new_false_accept') if after<=c else ('new_false_reject' if y[i]<=c else 'corrected_false_accept')
     events.append({'selected_index':i,'pool_index':read(TEST/'selection.json')['selected_pool_indices'][i],'candidate_id':rows[i]['candidate_id'],'template':rows[i]['template'],'formula':rows[i]['formula'],'actual_lut4':y[i],'reference_lut4':before,'prediction_lut4':after,'feasibility_probability':saved['coverage_feasibility_probabilities'][NAME][i][CAPS.index(c)],'event':event})
    feasible=sum(y[i]<=c for i in ix);caps[str(c)]={'actual_feasible':feasible,'actual_infeasible':len(ix)-feasible,'changed_decisions':events}
   result[ref]=caps
  return result
 d=dev['gates'][NAME];scientific={'development_selected_candidate_exists':chosen is not None,'all26_retained1113_metric_rows1073_records_preserved':d['all_twenty_six_panels_pass'],'all33_named_subgroups_preserved':d['all_named_subgroups_preserved'],'all62_required_acceptances_original125_all_prior_repairs_latest_sharing125':d['all_required_acceptances_pass'],'all38_rejections_including_core15_107_113_159_and129_130_129':d['all_required_rejections_pass'],'latest_passing_general_legacy_classifier_accuracy_and_tail_preserved':all(general['checks'][NAME]['accuracy_no_worse'][BASELINE].values()) and all(legacy['checks'][NAME]['accuracy_no_worse'][BASELINE].values()) and general[NAME]['maximum_underprediction_lut4']<=general[BASELINE]['maximum_underprediction_lut4']+TOL and legacy[NAME]['maximum_underprediction_lut4']<=legacy[BASELINE]['maximum_underprediction_lut4']+TOL,'fresh_general_strict_signed_MAE_MAPE_FA_gains':all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'],'fresh_general_no_loss_original_six_and_extra_validated_baseline_tail_FA_FR':checks['general_no_loss'],'all_prospective_activity_and_feature_novelty_requirements':checks['coverage']['passed'] and activity_ok,'fixed_sharing8_no_loss_and_cap_gates':checks['sharing_passes'],'fixed_legacy8_no_loss_and_cap_gates':checks['legacy_passes'],'conditional_full_no_loss_and_cap_gates':checks['conditional_full_passes'],'active_only_no_loss_and_cap_gates':checks['active_subset_passes'],'exact_frozen1889_plus32_novel_training_no_consumed_labels':proof['consumed_evaluation_labels_fitted']==0,'single_shared_tree233_fit_same_parameters_0_5_tie_and_monotone_probabilities':True,'source_cohorts_targets_policy_gates_frozen_before_new_features_training_labels_fit':True,'model_and_all96_points_selection_frozen_before_fresh_labels':True,'summed_native_worker_seconds_at_most300_peak2_and_one_one_thread_fit':jobs['summed_worker_native_seconds']<=300 and jobs['recorded_worker_peak']<=2,'all1008_prior_scientific_files_preserved_goal_status_only_exception':count==1008,'training_labels_independently_audited_before_parent_fit_authorization':True,'native_original_RTL_proof_netlist_counts_cached_inference_chronology_verified':True,'separate_targeted_synthetic_and_conditional_populations_no_pooled_claim':True}
 assert all(scientific.values())==eligible
 diagnostics={}
 if (OUT/'failure-diagnostics.json').exists():
  diagnostic=read(OUT/'failure-diagnostics.json')
  for k in ('bindings','sources'):
   if isinstance(diagnostic.get(k),dict):check_bindings(diagnostic[k])
  diagnostics={'artifact_sha256':sha(OUT/'failure-diagnostics.json'),'bindings_authenticated':True,'audit_own_case_metrics_and_events_authoritative':True}
 files=[auth,TEST/'labels.json',TEST/'completion.json',TEST/'raw-evidence-manifest.json',TEST/read(TEST/'raw-evidence-manifest.json')['archive'],OUT/'fresh-metrics.json']
 if (OUT/'failure-diagnostics.json').exists():files.append(OUT/'failure-diagnostics.json')
 template_metrics={t:sub([i for i,r in enumerate(rows) if r['template']==t]) for t in sorted({r['template'] for r in rows})}
 body={'bindings':{relative(p):sha(p) for p in files},'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'original_goal_ledger_status_only_mutable':True,'current_goal_clarification_fully_preserved':True,'fits':1,'new_training_labels':32,'training_rows':1921,'new_training_matrix_and_leaf_probability_proof':proof,'baseline1889_classifier_and_old_forest_forensics_reused_by_immutable_hash':True,'native_accounting':jobs,'identity_modular_and_lowbit_inputswap_family_novelty':identity_audit(),'input_profile_coverage':profile_review(),'observed_training_profile_targets':training_profile_truth_review(),'analytical_comparator_feasibility':comparator_feasibility(),'feature_freshness':fresh,'training_native_raw_evidence':read(TRAIN/'training-label-audit.json')['native_RTL_proof_netlists_and_measurements'],'fresh_native_raw_evidence':native,'cached_inference':cached_inference(saved),'descriptive_diagnostics':diagnostics,'development':dev,'fresh_general32':general,'fresh_sharing8':sharing,'fresh_legacy8':legacy,'fresh_conditional_full':conditional,'fresh_active_only':active,'fresh_template_metrics_descriptive':template_metrics,'fresh_gates':{NAME:gate},'selected_candidate':chosen,'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,'selection_coverage':saved['selection_coverage'],'pool_count':96,'selected_unique_label_count':len(y),'all_unselected_pool_rows_features_probabilities_retained':True,'shared_control_count':8,'shared_control_selected_indices':saved['shared_control_selected_indices'],'shared_controls_not_independent':True,'general_cap_decision_cases':decisions(saved['general_selected_indices']),'sharing_cap_decision_cases':decisions(saved['sharing_selected_indices']),'legacy_cap_decision_cases':decisions(saved['legacy_selected_indices']),'conditional_full_cap_decision_cases':decisions(saved['conditional_selected_indices']),'active_only_cap_decision_cases':decisions(saved['active_selected_indices']),'selected_numeric_fields_compared':fields,'new_candidate_development_and_pool_predictions_replayed':1113+96,'selected_policy_points_checked':len(y)*13,'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':all(scientific.values()),'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,'false_acceptance_sum_unit':'Circuit-budget events, not unique circuits. Per-cap feasible/infeasible denominators and changed-case identities are reported separately.','mape_definition':'100*mean(abs(actual-prediction)/actual) over actual>0; zero targets remain in MAE, cap and tail metrics.','bound_limits':'signed<=candidate<=release; release false acceptances and signed false rejections cannot be corrected. Count no-worse therefore forbids new individual mistakes against those references.','limitations':['One prospective training-coverage intervention with the frozen233 descriptor, algorithm, seed, parameters and half threshold; no separate causal attribution to the two added training subgroups.','Probabilities are uncalibrated class-frequency estimates, not certified risk or hardware safety.','Allfour support cells already existed; within-scope guard is inactive.','Novelty uses finite structural/identity screens including masked-shift equivalence and input renaming; not exhaustive semantic or application independence.','Finite2148-vector originalRTL checks and cell recounts do not prove mappednetlist functional equivalence, timing, power or CPU performance.']}
 return receipt(OUT/'audit.json',body,write)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=('analysis','preflight','pretrain','training-labels','prelabel','final'),default='analysis',nargs='?');p.add_argument('--write',action='store_true');a=p.parse_args();fn={'preflight':preflight,'pretrain':pretrain,'training-labels':training_labels,'prelabel':prelabel,'final':final_audit}.get(a.command);result=fn(a.write) if fn else {'prior_profile':prior_profile_review(),'comparator_feasibility':comparator_feasibility()};print(json.dumps(result,indent=2))

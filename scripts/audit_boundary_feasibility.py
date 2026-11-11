#!/usr/bin/env python3
"""Independent nested-feasibility audit; no fitting or native jobs."""
from __future__ import annotations
import argparse
from collections import Counter
from functools import lru_cache
import itertools,json,math,random,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_boundary_corroboration as regression
import audit_boundary_abstention as oldpolicy
import audit_boundary_coverage as feature
import audit_targeted_coverage as old
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/boundary-feasibility';TEST=ROOT/'results/boundary-feasibility-validation';PRIOR=ROOT/'results/boundary-corroboration'
CAPS=(32,64,128);TOL=1e-10;PROB_TOL=1e-12;MASK=(1<<32)-1
CURRENT='incumbent_signed';RELEASE='budget_release_compound_only';STRUCTURAL='boundary_structural';LEARNED='boundary_coverage_only';ABSTENTION='boundary_abstention';PREVIOUS='corroborated_augmented'
CANDIDATES=('feasibility_augmented','feasibility_coverage_only');KINDS=dict(zip(CANDIDATES,('augmented','coverage')))
REFERENCES=(RELEASE,STRUCTURAL,LEARNED,ABSTENTION,*regression.CANDIDATES)
COUNTS={**regression.COUNTS,'consumed-eleventh-general32':32,'consumed-eleventh-sharing8':8,'consumed-eleventh-legacy8':8,'consumed-eleventh-conditional9':9}


def check_bindings(mapping,root=ROOT):
 for n,h in mapping.items():assert sha(root/n)==h,n


def preserved():
 s=read(OUT/'auditor-prior-artifacts.json');check_bindings(s['files']);g=read(ROOT/s['goal_ledger']['path']);g.pop('status',None);assert g==s['goal_ledger']['protected_content'];assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==s['submodules'];return len(s['files'])


def receipt(path,body,write=False):
 body={'schema':'independent-boundary-feasibility-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
 if write:
  with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
 else:
  saved=read(path);actual=dict(body)
  for d in (saved,actual):d.pop('audited_at_utc',None)
  assert saved==actual,'Receipt replay differs:'+str(path)
 return body


def modular_normalize(node):
 """Two sound decoded-RV32 identities; intentionally not exhaustive equivalence."""
 if not isinstance(node,tuple):return node
 op,args=node;args=tuple(modular_normalize(x) for x in args)
 if op=='addi' and isinstance(args[1],int) and isinstance(args[0],tuple) and args[0][0]=='addi' and isinstance(args[0][1][1],int):
  return modular_normalize(('addi',(args[0][1][0],(args[0][1][1]+args[1])&MASK)))
 if op=='andi' and isinstance(args[1],int) and args[1]>0 and args[1]&(args[1]+1)==0 and isinstance(args[0],tuple) and args[0][0]=='addi' and isinstance(args[0][1][1],int) and args[0][1][1]%(args[1]+1)==0:
  return modular_normalize(('andi',(args[0][1][0],args[1])))
 return op,args


def formula_string(node):
 if not isinstance(node,tuple):return str(node)
 return node[0]+'('+','.join(formula_string(n) for n in node[1])+')'


def modular_formula(formula):return formula_string(modular_normalize(old.parse(formula)))


def modular_rules_check():
 examples=('andi(addi(in0,2),1)','addi(addi(in0,9),2)','andi(addi(xori(in1,15),2),1)','andi(addi(in0,-4),3)');values=[*range(256),0x7fffffff,0x80000000,0xffffffff];count=0
 for f in examples:
  n=old.parse(f);r=modular_normalize(n)
  for a in values:
   for b in (0,1,3,0xffffffff):assert old.evaluate(n,a,b)==old.evaluate(r,a,b);count+=1
 assert modular_formula(examples[0])=='andi(in0,1)' and modular_formula(examples[1])=='addi(in0,11)'
 assert modular_formula('andi(addi(in0,2),3)')=='andi(addi(in0,2),3)' and old.evaluate(old.parse('andi(addi(in0,2),3)'),0,0)==2
 return {'rules':['ADDI(ADDI(x,a),b)=ADDI(x,(a+b)mod2^32)','ANDI(ADDI(x,k),2^w-1)=ANDI(x,2^w-1) when k mod2^w=0'],'decoded_RV32_vector_comparisons':count,'plus2_under_mask1_removed':True,'nested9_plus2_collapses11':True,'plus2_under_mask3_preserved':True,'scope':'Sound finite rewrite screen, not exhaustive semantic equivalence.'}


def modular_overlap(rows,history):
 known={};identity={}
 for f in history:
  normalized=modular_formula(f);known.setdefault(old.skeleton(normalized),f);identity.setdefault(normalized,f)
 matches=[];exact=[]
 for i,r in enumerate(rows):
  n=modular_formula(r['formula']);k=old.skeleton(n)
  if k in known:matches.append({'pool_index':i,'template':r['template'],'parameter':r['parameter'],'formula':r['formula'],'normalized_formula':n,'historical_formula':known[k],'normalized_historical_formula':modular_formula(known[k]),'normalized_constant_erased_skeleton':k})
  if n in identity:exact.append({'pool_index':i,'historical_formula':identity[n]})
 return matches,exact


def panel_sources():
 result=regression.panel_sources();folder=ROOT/'results/boundary-corroboration-validation';rows=read(folder/'candidates.json');labels=read(folder/'labels.json');f=read(folder/'features.json');p=read(PRIOR/'fresh-predictions.json')
 for name,key in (('consumed-eleventh-general32','general_selected_indices'),('consumed-eleventh-sharing8','sharing_selected_indices'),('consumed-eleventh-legacy8','legacy_selected_indices'),('consumed-eleventh-conditional9','conditional_selected_indices')):
  ix=p[key];result[name]=({'candidate_ids':[rows[i]['candidate_id'] for i in ix],'formulas':[rows[i]['formula'] for i in ix],'actual_lut4':[labels[i]['lut4'] for i in ix]},{'columns':f['columns'],'records':[f['records'][i] for i in ix]})
 assert len(result)==22 and sum(COUNTS.values())==1049;return result


def historical_records():
 import numpy as np
 formulas,x=regression.historical_records();blocks=[x]
 for folder,filename in (('boundary-corroboration-data','features.json'),('boundary-corroboration-validation','features.json'),('boundary-corroboration-validation','pool-features.json')):
  f=read(ROOT/'results'/folder/filename);blocks.append(oldpolicy.matrix(f));formulas.extend(r['formula'] for r in f['records'])
 x=np.vstack(blocks);assert x.shape==(3618,217) and len(formulas)==3618;return formulas,x


def training_data():
 import numpy as np
 rows=read(PRIOR/'training-manifest.json')['rows']
 with np.load(PRIOR/'training-inputs.npz',allow_pickle=False) as d:x={k:d[k].copy() for k in ('coverage','augmented')};y=d['y'].copy()
 assert len(rows)==1889 and x['coverage'].shape==(1889,217) and x['augmented'].shape==(1889,233) and np.array_equal(x['coverage'],x['augmented'][:,:217]) and np.array_equal(y,np.asarray([r['actual_lut4'] for r in rows]))
 labels=np.column_stack([y<=c for c in CAPS]).astype(np.uint8);assert (labels[:,0]<=labels[:,1]).all() and (labels[:,1]<=labels[:,2]).all()
 counts={str(c):{'feasible':int(labels[:,j].sum()),'infeasible':int(len(y)-labels[:,j].sum())} for j,c in enumerate(CAPS)};assert counts==read(OUT/'method-rationale.json')['observed_training_class_counts']
 assert np.array_equal(x['augmented'][:,217:],np.asarray([regression.ast_features(r['formula']) for r in rows]))
 return rows,x,y,labels


_REGRESSORS=None

def baseline_regressors():
 global _REGRESSORS
 if _REGRESSORS is None:
  import joblib
  audit=read(PRIOR/'audit.json');assert audit['status']=='pass' and audit['matched_training_forensics']['consumed_evaluation_labels_fitted']==0;check_bindings(read(PRIOR/'model-freeze.json')['files_sha256'],PRIOR)
  _REGRESSORS={k:joblib.load(PRIOR/(k+'.joblib')) for k in ('augmented','coverage')}
 return _REGRESSORS


def baseline_points(row,f):
 import numpy as np
 values,routes,details=oldpolicy.points(row,f);x=oldpolicy.matrix(f);cells=[[r['cell'] for r in regression.cells(formula)] for formula in row['formulas']];known=set(read(PRIOR/'support-cells.json')['supported_cells']);scope=[bool(c) and all(k in known for k in c) for c in cells];raw={};limits={};provenance={}
 for n in regression.CANDIDATES:
  kind=regression.KINDS[n];xx=np.hstack([x,np.asarray([regression.ast_features(formula) for formula in row['formulas']])]) if kind=='augmented' else x;raw[n]=baseline_regressors()[kind].predict(xx).tolist();out=[];caps=[]
  for s,r,p,active in zip(values[CURRENT],values[RELEASE],raw[n],scope):
   cc=[c for c in CAPS if active and s<=c<r and p<=c];out.append(min(cc) if cc else r);caps.append(cc)
  values[n]=out;limits[n]=caps;provenance[n]=[{str(c):{'signed_accepts':values[CURRENT][i]<=c,'release_accepts':values[RELEASE][i]<=c,'structural_proposal':values[STRUCTURAL][i]<=c<values[RELEASE][i],'oldlearned_proposal':values[LEARNED][i]<=c<values[RELEASE][i],'oldabstention_proposal':values[ABSTENTION][i]<=c<values[RELEASE][i],'new_raw_accepts':raw[n][i]<=c,'covered':scope[i],'candidate_accepts':values[n][i]<=c} for c in CAPS} for i in range(len(row['formulas']))]
 return values,routes,{**details,'pipeline_cells':cells,'pipeline_covered':scope,'corroboration_raw_lut4':raw,'corroborated_caps_lut4':limits,'proposal_provenance':provenance}


def classifier_leaf_audit(model,x,labels):
 import numpy as np
 assert model.n_outputs_==3 and len(model.estimators_)==300 and model.bootstrap is False and model.class_weight is None
 classes=[np.asarray(c) for c in model.classes_];assert all(np.array_equal(c,np.unique(labels[:,j])) for j,c in enumerate(classes));leaves=0
 for tree in model.estimators_:
  assert tree.tree_.n_node_samples[0]==1889 and tree.n_outputs_==3
  leaf=tree.apply(x);counts=np.bincount(leaf,minlength=tree.tree_.node_count);used=counts>0;assert (tree.tree_.children_left[used]==-1).all() and np.array_equal(counts[used],tree.tree_.n_node_samples[used]) and np.allclose(tree.tree_.weighted_n_node_samples[used],counts[used],rtol=0,atol=1e-12)
  positive=[]
  for j,c in enumerate(classes):
   sums=np.bincount(leaf,weights=labels[:,j],minlength=tree.tree_.node_count);expected=sums[used]/counts[used]
   for k,label in enumerate(c):assert np.allclose(tree.tree_.value[used,j,k],expected if label==1 else 1-expected,rtol=0,atol=PROB_TOL)
   positive.append(expected)
  p=np.column_stack(positive);assert (np.diff(p,axis=1)>=-PROB_TOL).all();leaves+=int(used.sum())
 return {'trees_verified':300,'training_rows':1889,'selected_features':x.shape[1],'training_leaf_assignments_checked':1889*300,'nested_binary_target_assignments_checked':1889*300*3,'leaf_class_counts_probabilities_and_equal_sample_weights_verified':leaves,'monotone_leaf_probabilities':True,'classes_by_cap':[c.tolist() for c in classes],'new_fits':0}


def probabilities(model,x):
 import numpy as np
 result=np.zeros((len(x),3),dtype=float)
 for tree in model.estimators_:
  leaf=tree.apply(x)
  for j,classes in enumerate(model.classes_):
   indices=np.flatnonzero(np.asarray(classes)==1)
   if len(indices):result[:,j]+=tree.tree_.value[leaf,j,indices[0]]
 result/=len(model.estimators_)
 assert np.isfinite(result).all() and (result>=0).all() and (result<=1).all() and (np.diff(result,axis=1)>=-PROB_TOL).all()
 raw=model.predict_proba(x)
 for j,classes in enumerate(model.classes_):
  index=np.flatnonzero(np.asarray(classes)==1);expected=raw[j][:,index[0]] if len(index) else np.zeros(len(x));assert np.allclose(result[:,j],expected,rtol=0,atol=PROB_TOL)
 return result


def identity_audit():
 rows=read(TEST/'pool-candidates.json');history=set(read(TEST/'historical-formulas.json'));required=set(read(ROOT/'results/boundary-corroboration-data/historical-formulas.json'));aliases=set()
 for folder,filename in (('boundary-corroboration-data','candidates.json'),('boundary-corroboration-validation','pool-candidates.json')):
  required.update(r['formula'] for r in read(ROOT/'results'/folder/filename))
  for r in read(ROOT/'results'/folder/'novelty.json')['comparisons']:aliases.update(r['forms'])
 assert required|aliases<=history;known=set().union(*(feature.prior.identity_keys(f) for f in history));seen=set();sk={old.skeleton(f) for f in history};novel=read(TEST/'novelty.json');assert len(rows)==len(novel['comparisons'])==128 and novel['status']=='pass'
 for r,e in zip(rows,novel['comparisons']):
  assert r['candidate_id']==e['candidate_id'];keys=set().union(*(feature.prior.identity_keys(f) for f in {r['formula'],*e['forms']}));assert not keys&known and not keys&seen and old.skeleton(r['formula']) not in sk;seen.update(keys)
 matches,exact=modular_overlap(rows,history);assert not matches and not exact
 normalized_known=set().union(*(feature.prior.identity_keys(modular_formula(f)) for f in history));seen=set()
 for r,e in zip(rows,novel['comparisons']):
  n=modular_formula(r['formula']);keys=feature.prior.identity_keys(n);assert e['modular_normalized_formula']==n and not keys&normalized_known and not keys&seen;seen.update(keys)
 review=read(OUT/'prefreeze-input-review.json');assert sha(OUT/'rejected-measurement-draft-v1.py')==review['original_draft_source_sha256'];rejected=read(OUT/'rejected-input-manifest-v1.json');matches,exact=modular_overlap(rejected['candidates'],history);assert len(matches)==36 and not exact and [r['pool_index'] for r in matches]==review['implicated_pool_indices']
 return {'historical_formulas':len(history),'fresh_pool_rows':128,'original_and_modular_identity_or_structural_family_collisions':0,'rejected_prefreeze36_rows_preserved':True,'sound_modular_rules':modular_rules_check(),'all_latest32_training_and128_pool_including79_unlabelled_consumed':True}


def analytical_review():
 targets=read(OUT/'evaluation-targets.json');check_bindings(targets['bindings']);assert len(targets['required_acceptances'])==50 and len(targets['required_rejections'])==23 and len(targets['core_required_rejections'])==10
 keys=[(r['candidate_id'],r['cap']) for r in targets['required_acceptances']+targets['required_rejections']];assert len(keys)==len(set(keys))==73
 for r in targets['required_acceptances']:assert r['actual_lut4']<=r['cap'] and r['previous_points_lut4'][CURRENT]<=r['cap']<r['previous_points_lut4'][RELEASE]
 for r in targets['required_rejections']:assert r['actual_lut4']>r['cap'] and r['previous_points_lut4'][RELEASE]>r['cap']
 limits=read(OUT/'policy-limitations.json');assert limits['source_sha256']==sha(PRIOR/'failure-diagnostics.json');fresh=read(PRIOR/'fresh-predictions.json');labels=read(ROOT/'results/boundary-corroboration-validation/labels.json');lookup={cid:i for i,cid in enumerate(fresh['candidate_ids'])}
 for r in limits['unrepairable_consumed_cases']:
  i=lookup[r['candidate_id']];assert r['actual_lut4']==labels[i]['lut4'] and r['signed_lut4']==fresh['models'][CURRENT][i] and r['release_lut4']==fresh['models'][RELEASE][i]
  assert (r['actual_lut4']>r['cap'] and r['release_lut4']<=r['cap']) if r['error']=='false_accept' else (r['actual_lut4']<=r['cap'] and r['signed_lut4']>r['cap'])
  assert (r['candidate_id'],r['cap']) not in keys
 rows,x,y,binary=training_data();rationale=read(OUT/'method-rationale.json');assert rationale['training_npz_sha256']==sha(PRIOR/'training-inputs.npz')
 return {'required_acceptances':50,'required_rejections':23,'core_protected_rejections':10,'all_targets_implied_by_existing_per_case_no_new_error_gates':True,'bound_limited_cases_independently_verified':6,'no_impossible_inventory_target':True,'training_rows':1889,'matched_feature_counts':[217,233],'nested_training_binary_class_counts':rationale['observed_training_class_counts'],'no_new_training_or_consumed_evaluation_targets':True}


def authenticate():
 import numpy,sklearn,joblib,platform
 p=read(OUT/'protocol.json');plan=read(TEST/'plan.json');assert p['schema']=='isaforge-boundary-feasibility-v1' and p['planned_fits']==p['maximum_fits']==2 and p['fit_threads']==1 and p['maximum_fit_seconds']==120 and p['total_training_rows']==1889 and p['new_training_labels']==p['consumed_labels_fitted']==0 and p['retained_panels']==COUNTS
 assert p['gates']['tolerance']==TOL and p['gates']['probability_roundoff_tolerance']==PROB_TOL and p['required_acceptance_count']==50 and p['required_rejection_count']==23 and p['sample_weight'] is None
 assert p['policy']['fit_order']==['augmented233','coverage217'];cfg=p['configuration_all_parameters'];assert cfg==p['policy']['configuration'] and cfg['n_estimators']==300 and cfg['n_jobs']==1 and cfg['class_weight'] is None and cfg['bootstrap'] is False and cfg['criterion']=='gini' and cfg['max_features']==1.0 and cfg['warm_start'] is False and cfg['max_samples'] is None and cfg['monotonic_cst'] is None
 assert p['runtime_versions']=={'python':platform.python_version(),'numpy':numpy.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}
 for k in ('sources_sha256','inputs_sha256'):check_bindings(p[k])
 assert plan['schema']=='boundary-feasibility-pool128-v1' and plan['new_training_label_count']==0 and plan['pool_count']==128 and plan['general_count']==32 and plan['sharing_count']==plan['legacy_count']==8 and plan['challenge_count']==80 and plan['maximum_selected_count']==64
 policy=plan['policy'];assert policy=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128],'budget_accounting':'summed_worker_process_seconds','stage_wall_safety_reserve_seconds':1.0}
 for k in ('sources','inputs','prior_inventory_sources','prefreeze_review_inputs'):check_bindings(plan[k])
 rows=read(TEST/'pool-candidates.json');assert len(rows)==128 and [i for i,r in enumerate(rows) if r['cohort']=='general']==list(range(32)) and [i for i,r in enumerate(rows) if r['cohort']=='sharing']==list(range(32,40)) and [i for i,r in enumerate(rows) if r['cohort']=='legacy']==list(range(40,48)) and [i for i,r in enumerate(rows) if r['reserved_control']]==list(range(24,32))
 for t in read(TEST/'tools.json').values():assert sha(t['path'])==t['sha256']
 return p


def bindings():
 files=[OUT/n for n in ('protocol.json','auditor-prior-artifacts.json','evaluation-targets.json','method-rationale.json','policy-limitations.json','support-cells.json','goal-at-freeze.json','goal-update-at-freeze.json','research-goal-current-at-freeze.json','prefreeze-input-review.json','rejected-input-manifest-v1.json','rejected-measurement-draft-v1.py','parent-preflight-validation.json')]+[TEST/n for n in ('plan.json','pool-candidates.json','novelty.json','historical-formulas.json','tools.json')]
 return {str(p.relative_to(ROOT)):sha(p) for p in files}


def preflight(write=False):
 p=authenticate();count=preserved()
 if write:
  assert not any((TEST/n).exists() for n in ('pool-features.json','features.json','feature-attempt.json','label-attempt.json','labels.json','selection.json')) and not (OUT/'run-start.json').exists() and not list(OUT.glob('fit-attempt-*.json')) and not list(OUT.glob('*.joblib'))
 a=analytical_review();assert p['class_counts']==a['nested_training_binary_class_counts'];check_bindings(read(OUT/'parent-preflight-validation.json')['bindings'])
 return receipt(TEST/'preflight-audit.json',{'bindings':bindings(),'scientific_artifacts_preserved':count,'identity_and_modular_novelty_audit':identity_audit(),'analytical_and_training_review':a,'reviewed_policy':p['policy'],'reviewed_selection':p['selection'],'reviewed_gates':p['gates'],'all_full_classifier_parameters_explicit':p['configuration_all_parameters'],'fixed_probability_threshold':0.5,'exact_threshold_tie_accepts':True,'no_probability_sorting_clipping_or_calibration':True,'native_budget_unit':'summed_worker_process_seconds','native_parent_stage_authorization_plan_and_protocol_bound':True,'classifier_parent_authorization_and_exact_preflight_required':True,'fits_and_native_execution_require_parent_receipts_not_granted_by_this_audit':True,'no_new_features_labels_fit_attempts_at_receipt':True,'new_training_labels':0,'planned_fits':2},write)


_CLASSIFIERS=None

def classifier_models():
 global _CLASSIFIERS
 if _CLASSIFIERS is not None:return _CLASSIFIERS
 import numpy as np,joblib
 from sklearn.ensemble import ExtraTreesClassifier
 p=authenticate();seal=read(OUT/'model-freeze.json');assert seal['protocol_sha256']==sha(OUT/'protocol.json') and seal['fits_completed']==2 and seal['wall_seconds']<=120 and seal['feature_freeze_sha256']==sha(OUT/'feature-freeze.json');check_bindings(seal['files_sha256'],OUT)
 rows,x,y,labels=training_data();manifest=read(OUT/'training-manifest.json');assert manifest['rows']==rows and manifest['consumed_evaluation_labels_fitted']==manifest['new_training_labels']==0
 with np.load(OUT/'training-inputs.npz',allow_pickle=False) as d:assert np.array_equal(d['coverage'],x['coverage']) and np.array_equal(d['augmented'],x['augmented']) and np.array_equal(d['y'],y) and np.array_equal(d['feasibility'],labels)
 approval=read(OUT/'execution-authorization.json');assert approval['authorizer']=='parent' and approval['protocol_sha256']==sha(OUT/'protocol.json') and approval['allow_two_classifier_fits'] is True
 start=read(OUT/'run-start.json');attempts=[read(OUT/f'fit-attempt-{i}.json') for i in (1,2)];timing=read(OUT/'timings.json');assert start['authorization_sha256']==sha(OUT/'execution-authorization.json') and start['independent_preflight_sha256']==sha(TEST/'preflight-audit.json') and start['planned_fits']==start['maximum_fits']==2
 assert read(TEST/'feature-completion.json')['completed_at_utc']<read(OUT/'feature-freeze.json')['frozen_at_utc']<start['started_at_utc']<=attempts[0]['started_at_utc']<attempts[1]['started_at_utc']<seal['frozen_at_utc'];assert [r['kind'] for r in timing]==['augmented','coverage']
 models={};proof={}
 for index,kind in enumerate(('augmented','coverage'),1):
  model=joblib.load(OUT/(kind+'.joblib'));meta=read(OUT/(kind+'.json'));a=attempts[index-1];assert type(model) is ExtraTreesClassifier and model.get_params()==ExtraTreesClassifier(**p['configuration_all_parameters']).get_params() and model.n_features_in_==x[kind].shape[1] and model.n_outputs_==3
  assert a['fit_index']==index and a['kind']==kind and a['training_count']==1889 and a['feature_count']==x[kind].shape[1] and a['sample_weight'] is None and a['configuration']==p['configuration_all_parameters'] and a['training_inputs_sha256']==sha(OUT/'training-inputs.npz')
  assert meta['classes_by_cap']==[c.tolist() for c in model.classes_] and meta['outputs']==list(CAPS) and meta['positive_class']==1 and meta['sample_weight'] is None and meta['training_count']==1889 and meta['new_training_count']==meta['consumed_labels_fitted']==0 and meta['artifact_sha256']==sha(OUT/(kind+'.joblib')) and meta['protocol_sha256']==sha(OUT/'protocol.json')
  proof[kind]=classifier_leaf_audit(model,x[kind],labels);probabilities(model,x[kind]);models[kind]=model
 _CLASSIFIERS=models,{'frozen1889_input_target_order_exact':True,'same217_prefix_plus_frozen16_columns_exact':True,'nested_labels_rederived_only_from_fitted_training_targets':True,'new_training_labels':0,'consumed_evaluation_labels_fitted':0,'class_counts':p['class_counts'],'fits':proof,'new_training_leaf_assignments_checked':1889*300*2,'nested_binary_training_assignments_checked':1889*300*3*2,'old_forest_leaf_forensics_reused_by_immutable_hash_not_repeated':True,'fixed_fit_order':['augmented','coverage'],'fit_records':timing}
 return _CLASSIFIERS


def points(row,f):
 import numpy as np
 values,routes,details=baseline_points(row,f);x=oldpolicy.matrix(f);cell_rows=[[r['cell'] for r in regression.cells(formula)] for formula in row['formulas']];known=set(read(OUT/'support-cells.json')['supported_cells']);scope=[bool(c) and all(k in known for k in c) for c in cell_rows];probs={};caps={};models,_=classifier_models()
 for n in CANDIDATES:
  kind=KINDS[n];xx=np.hstack([x,np.asarray([regression.ast_features(formula) for formula in row['formulas']])]) if kind=='augmented' else x;probs[n]=probabilities(models[kind],xx).tolist();out=[];support=[]
  for i,(s,r,active) in enumerate(zip(values[CURRENT],values[RELEASE],scope)):
   cc=[c for j,c in enumerate(CAPS) if active and s<=c<r and probs[n][i][j]>=0.5];out.append(min(cc) if cc else r);support.append(cc)
  values[n]=out;caps[n]=support
 return values,routes,{**details,'feasibility_cells':cell_rows,'feasibility_covered':scope,'feasibility_probabilities':probs,'feasibility_supported_caps':caps}


def metrics(y,values,probs=None):
 import numpy as np
 m={n:old.metrics(y,v) for n,v in values.items()};checks={}
 for n in CANDIDATES:
  checks[n]={'accuracy_no_worse':{r:feature.accuracy(m[r],m[n]) for r in REFERENCES},'caps':{str(c):{'false_accept_no_worse_release':m[n]['caps'][str(c)]['false_accept']<=m[RELEASE]['caps'][str(c)]['false_accept'],'false_reject_no_worse_signed':m[n]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject'],'no_new_false_accept_cases':not any(values[n][i]<=c<values[RELEASE][i] and y[i]>c for i in range(len(y))),'no_new_false_reject_cases':not any(values[CURRENT][i]<=c<values[n][i] and y[i]<=c for i in range(len(y)))} for c in CAPS},'maximum_underprediction_no_worse':all(m[n]['maximum_underprediction_lut4']<=m[r]['maximum_underprediction_lut4']+TOL for r in (*REFERENCES,CURRENT)),'pointwise_bounds':all(s<=p<=r for s,p,r in zip(values[CURRENT],values[n],values[RELEASE])),'events':{r:feature.prior.cap_events(values[r],values[n],y) for r in (*REFERENCES,CURRENT)}}
 m['checks']=checks
 if probs is not None:m['probability_metrics']={n:{str(c):{'brier_score':float(np.mean((np.asarray(probs[n])[:,j]-(np.asarray(y)<=c))**2)),'raw_probability_decision_errors':int(np.sum((np.asarray(probs[n])[:,j]>=0.5)!=(np.asarray(y)<=c)))} for j,c in enumerate(CAPS)} for n in CANDIDATES}
 return m


def passed(c):return all(all(v.values()) for v in c['accuracy_no_worse'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']


def feature_freshness():
 import numpy as np
 formulas,h=historical_records();rows=read(TEST/'pool-candidates.json');x=oldpolicy.matrix(read(TEST/'pool-features.json'));assert x.shape==(128,217);reports={}
 for kind in ('coverage','augmented'):
  history=np.hstack([h,np.asarray([regression.ast_features(f) for f in formulas])]) if kind=='augmented' else h;current=np.hstack([x,np.asarray([regression.ast_features(r['formula']) for r in rows])]) if kind=='augmented' else x
  known={tuple(float(v) for v in row) for row in history};keys=[tuple(float(v) for v in row) for row in current];groups={};rep=[]
  for i,key in enumerate(keys):groups.setdefault(key,[]).append(i);rep.append(groups[key][0])
  reports[kind]={'historical_unique_count':len(known),'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in known],'pool_cluster_representatives':rep,'pool_duplicate_clusters':[v for v in groups.values() if len(v)>1]}
 return {'historical_rows':3618,'fitted_rows':1889,'unique_consumed_labels':1017,'prior_pool_rows':[200,128,128,128,128],'representations':reports,'equality':'Exactfloat64 tuples; no rounding or labels.'}


def development():
 saved=read(OUT/'development-predictions.json');stored=read(OUT/'development-metrics.json');computed={};assert set(saved)==set(COUNTS)
 for name,(r,f) in panel_sources().items():
  assert len(r['actual_lut4'])==COUNTS[name]
  for k,v in r.items():assert saved[name][k]==v,(name,k)
  values,routes,details=points(r,f);assert saved[name]['models']==values and saved[name]['routes']==routes,name
  for k,v in details.items():assert saved[name][k]==v,(name,k)
  computed[name]=metrics(r['actual_lut4'],values,details['feasibility_probabilities']);old.compare_metric(stored['panels'][name],computed[name])
 def sub(name,ix):
  r=saved[name];return metrics([r['actual_lut4'][i] for i in ix],{n:[v[i] for i in ix] for n,v in r['models'].items()},{n:[v[i] for i in ix] for n,v in r['feasibility_probabilities'].items()})
 def group(name,folder,template):
  ix=[i for i,r in enumerate(read(ROOT/'results'/folder/'candidates.json')) if r['template']==template];assert len(ix)==4;return sub(name,ix)
 named={'arithmetic_stress32':computed['arithmetic-stress'],'signed_dual_arithmetic4':group('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),'signed_add_boolean4':group('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),'compound_signed_add_xor4':group('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_add_xor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_xordata_addxor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_xordata_addxor')}
 r=saved['consumed-sixth-broad40'];named['broad_compound32']=sub('consumed-sixth-broad40',[i for i,f in enumerate(r['formulas']) if feature.prior.predicates(f)[0]])
 r=saved['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][RELEASE][i]];fa=[i for i,y in enumerate(r['actual_lut4']) if any(r['models']['boundary_median'][i]<=c<r['models'][RELEASE][i] and y>c for c in CAPS)];assert len(fr)==8 and len(fa)==2;named['eight_corrected_fr']=sub('consumed-seventh-conditional18',fr);named['two_previous_new_fa']=sub('consumed-seventh-conditional18',fa)
 r=saved['consumed-eighth-general32'];four=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][STRUCTURAL][i]];assert len(four)==4;named['four_confident_fr']=sub('consumed-eighth-general32',four);named['prior_active16']=sub('consumed-eighth-conditional24',list(range(16)))
 r=saved['consumed-ninth-general32'];ix=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][STRUCTURAL][i] and r['models'][LEARNED][i]<=128];assert len(ix)==1 and r['actual_lut4'][ix[0]]==122;named['safe122']=sub('consumed-ninth-general32',ix)
 r=saved['consumed-ninth-conditional9'];ix=[i for i,y in enumerate(r['actual_lut4']) if y>128 and r['models'][LEARNED][i]<=128<r['models'][STRUCTURAL][i]];assert len(ix)==1 and r['actual_lut4'][ix[0]]==159;named['unsafe159']=sub('consumed-ninth-conditional9',ix);named['latest_active6']=sub('consumed-tenth-conditional14',list(range(6)))
 lookup={cid:(r,i) for r in saved.values() for i,cid in enumerate(r['candidate_ids'])};original=read(PRIOR/'evaluation-targets.json');targets=read(OUT/'evaluation-targets.json');accept=targets['required_acceptances'];reject=targets['required_rejections']
 def target_metrics(rr):return metrics([r['actual_lut4'] for r in rr],{n:[lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]] for r in rr] for n in next(iter(saved.values()))['models']})
 named['established39']=target_metrics(original['established_repairs']);named['remaining_fr4']=target_metrics(original['remaining_fr_targets']);named['protected_rejections6']=target_metrics(original['required_rejections']);named['expanded_acceptances']=target_metrics(accept);named['expanded_rejections']=target_metrics(reject);named['latest_active1']=sub('consumed-eleventh-conditional9',[0])
 latest_accept=[r for r in accept if r['origin_group'].startswith('latest49')];latest_reject=[r for r in reject if r['origin_group'].startswith('latest49')];corrected=[r for r in latest_accept if any(r['previous_points_lut4'][n]<=r['cap'] for n in regression.CANDIDATES)];missing=[r for r in latest_accept if r not in corrected];core=[r for r in latest_reject if r['core_protected_rejection']];other=[r for r in latest_reject if not r['core_protected_rejection']]
 assert [len(rr) for rr in (latest_accept,corrected,missing,core,other)]==[7,5,2,4,13]
 for name,rr in (('latest_required_acceptances7',latest_accept),('latest_corrected_cases5',corrected),('latest_remaining_false_rejections2',missing),('latest_core_rejections4',core),('latest_other_rejections13',other)):named[name]=target_metrics(rr)
 assert len(named)==25 and set(named)==set(stored['named_regressions'])
 for k,v in named.items():old.compare_metric(stored['named_regressions'][k],v)
 cases=[]
 for target in accept+reject:
  r,i=lookup[target['candidate_id']];assert r['actual_lut4'][i]==target['actual_lut4'] and r['formulas'][i]==target['formula'];cases.append({**{k:target[k] for k in ('candidate_id','formula','actual_lut4','cap')},'expected':'accept' if target in accept else 'reject','predictions':{n:r['models'][n][i] for n in CANDIDATES}})
 assert cases==stored['evaluation_cases'] and len(accept)==50 and len(reject)==23
 gates={}
 for n in CANDIDATES:
  g={'all_twenty_two_panels_pass':all(passed(m['checks'][n]) for m in computed.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_required_acceptances_pass':all(r['predictions'][n]<=r['cap'] for r in cases if r['expected']=='accept'),'all_required_rejections_pass':all(r['predictions'][n]>r['cap'] for r in cases if r['expected']=='reject')};g['development_gate_passed']=all(g.values());gates[n]=g
 selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None);assert stored['gates']==gates and stored['selected_candidate']==selected and stored['evaluated_candidate']==(selected or CANDIDATES[0]) and stored['retained_metric_rows']==1049 and stored['retained_circuit_records']==1017 and stored['shared_controls']==32 and stored['no_pooled_metric']
 return {'gates':gates,'selected_candidate':selected,'evaluated_candidate':selected or CANDIDATES[0],'named_subsets':list(named),'evaluation_cases':cases,'retained_metric_rows':1049,'retained_circuit_records':1017,'shared_controls':32,'no_pooled_metric':True,'development_predictions_replayed':1049*12,'per_case_no_new_FA_FR_checks_replayed':True}


def raw_audit(folder):
    rows=read(folder/'candidates.json');labels=read(folder/'labels.json');features=read(folder/'features.json')
    assert len(rows)==len(labels) and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
    manifest=read(folder/'raw-evidence-manifest.json');archive=folder/manifest['archive']
    assert sha(archive)==manifest['archive_sha256'];members={r['path']:r for r in manifest['files']}
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)
        for name,row in members.items():
            body=z.read(name);assert digest(body)==row['sha256'] and len(body)==row['bytes']
        get=lambda n:z.read('raw/'+n)
        kind='test'
        feature_jobs=[j for j in read(TEST/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind]
        label_jobs=read(folder/'completion.json')['native_worker_jobs']
        for job in feature_jobs+label_jobs:
            phase=job['stage'];directory='verification' if phase=='verify' else phase+'s/'+str(job['index'])
            assert json.loads(get(directory+'/worker.json'))==job
            assert digest(get(directory+'/worker.log'))==job['log_sha256']
        proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148
        assert proof['random_seed']==read(TEST/'plan.json')['proof_random_seed']
        assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256']
        assert proof['total_comparisons']==2148*len(rows)
        boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1];rng=random.Random(proof['random_seed'])
        expected=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        parsed=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()]
        assert len(parsed)==2148 and [(r[0],r[1]) for r in parsed]==expected
        trees=[old.parse(r['formula']) for r in rows]
        for a,b,*targets in parsed:assert [old.evaluate(t,a,b) for t in trees]==targets
        assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
        for i,(row,label) in enumerate(zip(rows,labels)):
            assert label['status']=='complete' and label['formula']==row['formula']
            assert json.loads(get(f'labels/{i}/result.json'))==label
            net=get(f'labels/{i}/ice40-netlist.json');assert digest(net)==label['netlist_sha256']
            counts=Counter(c['type'] for c in json.loads(net)['modules']['candidate']['cells'].values())
            assert counts['SB_LUT4']==label['lut4'] and counts['SB_CARRY']==label['carry']
            source=get(f'labels/{i}/candidate.v').decode();assert digest(source.encode())==label['rtl_sha256']
            assert source.replace('module candidate(',f'module candidate_{i}(') in rtl
            body=get(f'labels/{i}/metrics.json');assert digest(body)==label['metrics_sha256']
            m=json.loads(body);assert m['ice40_lut4_count']==label['lut4'] and m['ice40_carry_count']==label['carry'] and m['measurement_source']=='rtl_synthesis'
            assert 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
            assert features['records'][i]==read(folder/'pool-features.json')['records'][read(folder/'selection.json')['selected_pool_indices'][i]]
        pool=read(folder/'pool-features.json');assert len(pool['records'])==128
        for i,record in enumerate(pool['records']):assert json.loads(get(f'features/{i}/result.json'))==record
    return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'all_pool_feature_results_authenticated':128,'independent_RV32_vector_comparisons':2148*len(rows),'native_job_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}


def authorization_review():
 psha=sha(OUT/'protocol.json');a=read(TEST/'feature-parent-authorization-at-audit.json');assert a['status']=='approved' and a['approved_by']=='parent' and a['plan_sha256']==sha(TEST/'plan.json') and a['protocol_sha256']==psha
 f=read(OUT/'execution-authorization.json');assert f['authorizer']=='parent' and f['protocol_sha256']==psha and f['allow_two_classifier_fits'] is True
 return {'native_feature_authorization_sha256':sha(TEST/'feature-parent-authorization-at-audit.json'),'fit_authorization_sha256':sha(OUT/'execution-authorization.json'),'native_authorized_stages':a['authorized_stages'],'exact_protocol_and_plan_bound':True}


def chronology(final=False):
 from datetime import datetime
 feature_report=read(TEST/'feature-completion.json');reports=[feature_report];assert old.job_audit(feature_report)['jobs']==128 and Counter(j['stage'] for j in feature_report['native_worker_jobs'])=={'feature':128}
 assert read(TEST/'preflight-audit.json')['audited_at_utc']<read(TEST/'feature-attempt.json')['started_at_utc'];authorization_review()
 if final:
  label_report=read(TEST/'completion.json');reports.append(label_report);n=len(read(TEST/'candidates.json'));assert old.job_audit(label_report)['jobs']==n+1 and Counter(j['stage'] for j in label_report['native_worker_jobs'])=={'verify':1,'label':n}
  assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc'] and read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in label_report['native_worker_jobs'])
  assert max(j['finished_at_utc'] for j in label_report['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in label_report['native_worker_jobs'] if j['stage']=='label')
  assert read(OUT/'model-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in label_report['native_worker_jobs'])
  label_auth=read(TEST/'parent-authorization.json');assert 'labels' in label_auth['authorized_stages'] and label_auth['status']=='approved' and label_auth['approved_by']=='parent' and label_auth['protocol_sha256']==sha(OUT/'protocol.json') and label_auth['plan_sha256']==sha(TEST/'plan.json')
 total=0;wall=0
 for report in reports:
  assert report['complete'] and not report['failures'];summed=sum(j['native_elapsed_seconds'] for j in report['native_worker_jobs']);assert math.isclose(summed,report['native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(summed,report['summed_worker_native_seconds'],abs_tol=1e-9)
  for j in report['native_worker_jobs']:
   interval=(datetime.fromisoformat(j['finished_at_utc'])-datetime.fromisoformat(j['started_at_utc'])).total_seconds();assert 0<j['native_elapsed_seconds']<=j['job_wall_elapsed_seconds']+1e-9<=interval+0.01
  budget=300-total;assert math.isclose(report['native_budget_seconds'],budget,abs_tol=1e-9) and math.isclose(report['stage_wall_budget_seconds'],(budget-1)/2,abs_tol=1e-9)
  total+=summed;wall+=report['stage_wall_elapsed_seconds'];assert math.isclose(total,report['total_native_elapsed_seconds'],abs_tol=1e-9) and math.isclose(total,report['total_summed_worker_native_seconds'],abs_tol=1e-9)
 assert total<=300
 events=[event for r in reports for j in r['native_worker_jobs'] for event in ((j['started_at_utc'],1),(j['finished_at_utc'],-1))];active=peak=0
 for _,d in sorted(events,key=lambda e:(e[0],e[1])):active+=d;peak=max(peak,active)
 assert active==0 and peak<=2
 return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'summed_worker_native_seconds':total,'stage_wall_seconds_separately':wall,'recorded_worker_peak':peak,'native_budget_unit':'summed_worker_process_seconds','new_fits':2,'new_training_labels':0}


def select(pool,values,fresh,evaluated):
 groups={c:[i for i,r in enumerate(pool) if r['cohort']==c] for c in ('general','sharing','legacy')};fixed=groups['general']+groups['sharing']+groups['legacy'];controls=[i for i,r in enumerate(pool) if r['reserved_control']];reps={k:r['pool_cluster_representatives'] for k,r in fresh['representations'].items()};history=set().union(*(r['pool_historical_or_training_matches'] for r in fresh['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()}
 raw=[i for i,r in enumerate(pool) if r['cohort']=='challenge' and any(values[evaluated][i]<=c<values[PREVIOUS][i] for c in CAPS)];collision=[i for i in raw if any(reps[k][i] in seen[k] for k in reps)];eligible=[i for i in raw if i not in history and i not in collision];queues={}
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
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[PREVIOUS][i] for i in active) for c in CAPS};legacy=[i for i in groups['legacy'] if values[ABSTENTION][i]<=64<values[evaluated][i]];sharing=[i for i in groups['sharing'] if values[LEARNED][i]<=128<values[evaluated][i]]
 checks.update({'at_least_four_new_acceptances':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1,'at_least_one_legacy64_veto':len(legacy)>=1,'at_least_one_sharing128_veto':len(sharing)>=1})
 coverage={'pool_count':128,'general_count':32,'sharing_count':8,'legacy_count':8,'shared_control_count':8,'raw_active_count':len(raw),'eligible_active_count':len(eligible),'selected_active_count':len(active),'selected_templates':templates,'acceptance_caps':caps,'legacy64_veto_count':len(legacy),'legacy64_veto_pool_indices':legacy,'sharing128_veto_count':len(sharing),'sharing128_veto_pool_indices':sharing,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}
 return selection,coverage


def fresh_points():
 authenticate();dev=development();pool=read(TEST/'pool-candidates.json');f=read(TEST/'pool-features.json');stored=read(OUT/'pool-predictions.json');row={'formulas':[r['formula'] for r in pool]};values,routes,details=points(row,f)
 assert stored['models']==values and stored['routes']==routes and stored['candidate_ids']==[r['candidate_id'] for r in pool] and stored['formulas']==row['formulas'] and stored['templates']==[r['template'] for r in pool]
 for k,v in details.items():assert stored[k]==v,k
 fresh=feature_freshness();assert fresh==read(OUT/'feature-freshness.json');selection,coverage=select(pool,values,fresh,dev['evaluated_candidate']);s=read(TEST/'selection.json')
 for k,v in selection.items():assert s[k]==v,k
 assert s['coverage']==coverage and s['labels_present'] is False and s['pool_predictions_sha256']==sha(OUT/'pool-predictions.json') and s['evaluated_candidate']==dev['evaluated_candidate']
 ix=selection['selected_pool_indices'];saved=read(OUT/'fresh-predictions.json');assert read(TEST/'candidates.json')==[pool[i] for i in ix] and read(TEST/'features.json')=={'columns':f['columns'],'records':[f['records'][i] for i in ix]}
 for k in ('candidate_ids','formulas','templates','routes',*details):
  if isinstance(stored[k],dict):assert saved[k]=={n:[v[i] for i in ix] for n,v in stored[k].items()},k
  else:assert saved[k]==[stored[k][i] for i in ix],k
 assert saved['models']=={n:[v[i] for i in ix] for n,v in values.items()} and saved['general_selected_indices']==list(range(32)) and saved['sharing_selected_indices']==list(range(32,40)) and saved['legacy_selected_indices']==list(range(40,48)) and saved['active_selected_indices']==list(range(48,len(ix))) and saved['shared_control_selected_indices']==list(range(24,32)) and saved['conditional_selected_indices']==list(range(48,len(ix)))+list(range(24,32))
 assert saved['selection_coverage']==coverage and saved['selected_candidate']==stored['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==stored['evaluated_candidate']==dev['evaluated_candidate']
 seal=read(OUT/'fresh-point-freeze.json');bridge=read(TEST/'point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0 and bridge['target_label_jobs']==0;check_bindings(seal['bindings']);check_bindings(bridge['bindings'])
 assert read(OUT/'model-freeze.json')['frozen_at_utc']<stored['created_at_utc']<s['frozen_at_utc']<seal['frozen_at_utc']
 return saved,dev,fresh


def cached_inference(saved):
 c=read(OUT/'cached-inference-check.json');assert c['model']==saved['evaluated_candidate'] and c['selected_candidate']==saved['selected_candidate'] and c['fits']==c['native_jobs']==0 and c['calibration_status']=='uncalibrated' and c['upper_lut4'] is None
 fields=('candidate_ids','formulas','models','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap','learning_scope','learned_raw_lut4','learned_supported_caps_lut4','coverage_guard','pipeline_cells','pipeline_covered','corroboration_raw_lut4','corroborated_caps_lut4','proposal_provenance','feasibility_cells','feasibility_covered','feasibility_probabilities','feasibility_supported_caps')
 for k in fields:assert c[k]==saved[k],k
 assert c['predicted_lut4']==saved['models'][saved['evaluated_candidate']] and c['protocol_sha256']==sha(OUT/'protocol.json') and c['features_sha256']==sha(TEST/'features.json') and c['candidates_sha256']==sha(TEST/'candidates.json')
 return {'artifact_sha256':sha(OUT/'cached-inference-check.json'),'twelve_model_points_and_raw_probabilities_replayed':12*len(saved['candidate_ids']),'uncalibrated':True,'fits':0,'native_jobs':0}


def prelabel(write=False):
 authenticate();count=preserved();preflight(False);jobs=chronology();saved,dev,fresh=fresh_points();_,proof=classifier_models()
 if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 files=[OUT/n for n in ('execution-authorization.json','feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-point-freeze.json','fresh-predictions.json','cached-inference-check.json')]+[TEST/n for n in ('feature-parent-authorization-at-audit.json','feature-audit.json','feature-completion.json','selection.json','candidates.json','features.json','point-freeze.json','pool-features.json')]
 return receipt(TEST/'prelabel-audit.json',{'bindings':{**bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in files}},'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,'fresh_policy_points_replayed':12*len(saved['candidate_ids']),'all128_pool_policy_points_replayed':1536,'all_raw_classifier_probability_columns_replayed':128*3*2,'feature_freshness':fresh,'selection_coverage':saved['selection_coverage'],'development':dev,'matched_classifier_training_and_leaf_probability_proof':proof,'cached_inference':cached_inference(saved),'native_accounting_to_date':jobs,'native_feature_evidence':feature_native_review(),'parent_execution_authorization':authorization_review(),'fixed0_5_tie_acceptance_no_probability_repair':True,'class_mapping_nested_leaf_probabilities_and_all_predictions_independently_verified':True,'all128_points_probabilities_and_selection_before_labels':True,'fixed48_general_sharing_legacy_before_predictions':True,'shared_controls_not_independent':True,'no_pooled_metric':True,'new_training_labels':0},write)


def feature_native_review():
 report=read(TEST/'feature-completion.json');f=read(TEST/'pool-features.json');rows=read(TEST/'pool-candidates.json');assert len(f['columns'])==336 and len(f['records'])==128
 archive=None
 if (TEST/'raw').exists():get=lambda n:(TEST/'raw'/n).read_bytes()
 else:
  archive=zipfile.ZipFile(TEST/read(TEST/'raw-evidence-manifest.json')['archive']);get=lambda n:archive.read('raw/'+n)
 try:
  for j in report['native_worker_jobs']:
   i=j['index'];prefix=f'features/{i}/';record=json.loads(get(prefix+'result.json'));assert record==f['records'][i] and record['formula']==rows[i]['formula'] and len(record['values'])==336 and record['status']=='complete'
   assert json.loads(get(prefix+'worker.json'))==j and digest(get(prefix+'worker.log'))==j['log_sha256']
 finally:
  if archive is not None:archive.close()
 return {'raw_feature_results_authenticated':128,'raw_feature_worker_records_and_log_hashes_authenticated':128,'columns':336}


def final_audit(write=False):
 authenticate();count=preserved();prelabel(False);jobs=chronology(True);saved,dev,fresh=fresh_points();_,proof=classifier_models();rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels];y=[r['lut4'] for r in labels];scored=read(OUT/'fresh-metrics.json')
 def sub(ix):return metrics([y[i] for i in ix],{n:[v[i] for i in ix] for n,v in saved['models'].items()},{n:[v[i] for i in ix] for n,v in saved['feasibility_probabilities'].items()})
 general=sub(saved['general_selected_indices']);sharing=sub(saved['sharing_selected_indices']);legacy=sub(saved['legacy_selected_indices']);conditional=sub(saved['conditional_selected_indices']);active=sub(saved['active_selected_indices']) if saved['active_selected_indices'] else None
 fields=sum(old.compare_metric(scored[k],m) for k,m in (('models',general),('sharing_models',sharing),('legacy_models',legacy),('conditional_models',conditional)))
 if active:fields+=old.compare_metric(scored['active_subgroup'],active)
 else:assert scored['active_subgroup'] is None
 gates={}
 for n in CANDIDATES:
  ix=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=c<saved['models'][PREVIOUS][i] for c in CAPS)];activity={'acceptances':len(ix),'templates':len({saved['templates'][i] for i in ix}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][PREVIOUS][i] for i in ix),'legacy64_veto':sum(saved['models'][ABSTENTION][i]<=64<saved['models'][n][i] for i in saved['legacy_selected_indices']),'sharing128_veto':sum(saved['models'][LEARNED][i]<=128<saved['models'][n][i] for i in saved['sharing_selected_indices'])}
  activity_ok=activity['acceptances']>=4 and activity['templates']>=2 and activity['cap128']>=1 and activity['legacy64_veto']>=1 and activity['sharing128_veto']>=1
  checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_ok,'general_no_loss':passed(general['checks'][n]),'general_strict_signed':feature.accuracy(general[CURRENT],general[n],True),'general_strict_fa_gain_signed':sum(general[n]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),'sharing_passes':passed(sharing['checks'][n]),'legacy_passes':passed(legacy['checks'][n]),'conditional_full_passes':passed(conditional['checks'][n]),'active_subset_passes':bool(active and passed(active['checks'][n]))}
  ok=checks['coverage']['passed'] and activity_ok and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['sharing_passes'] and checks['legacy_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes'];gates[n]={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':ok and dev['selected_candidate']==n}
 chosen=dev['selected_candidate'];evaluated=dev['evaluated_candidate'];eligible=bool(chosen and gates[chosen]['eligible']);assert scored['gates']==gates and scored['scoped_experimental_eligibility']==eligible and scored['selected_candidate']==chosen and scored['evaluated_candidate']==evaluated
 assert scored['selection_coverage']==saved['selection_coverage'] and scored['general_count']==32 and scored['sharing_count']==scored['legacy_count']==8 and scored['active_count']==len(saved['active_selected_indices']) and scored['conditional_count']==len(saved['conditional_selected_indices']) and scored['shared_controls']==8 and scored['unique_label_count']==len(y) and scored['fits']==2 and scored['native_jobs']==0 and scored['no_pooled_metric'] and scored['fresh_labels_sha256']==sha(TEST/'labels.json')
 def decisions(ix):
  result={}
  for ref in (CURRENT,*REFERENCES):
   caps={}
   for c in CAPS:
    events=[]
    for i in ix:
     before=saved['models'][ref][i];after=saved['models'][evaluated][i]
     if (before<=c)==(after<=c):continue
     event=('corrected_false_reject' if y[i]<=c else 'new_false_accept') if after<=c else ('new_false_reject' if y[i]<=c else 'corrected_false_accept')
     events.append({'selected_index':i,'pool_index':read(TEST/'selection.json')['selected_pool_indices'][i],'candidate_id':rows[i]['candidate_id'],'template':rows[i]['template'],'formula':rows[i]['formula'],'actual_lut4':y[i],'reference_lut4':before,'prediction_lut4':after,'feasibility_probability':saved['feasibility_probabilities'][evaluated][i][CAPS.index(c)],'event':event})
    feasible=sum(y[i]<=c for i in ix);caps[str(c)]={'actual_feasible':feasible,'actual_infeasible':len(ix)-feasible,'changed_decisions':events}
   result[ref]=caps
  return result
 c=gates[evaluated]['checks'];d=dev['gates'][evaluated];scientific={'development_selected_candidate_exists':chosen is not None,'all22_retained1049_metric_rows1017_records_preserved':d['all_twenty_two_panels_pass'],'all25_named_subgroups_preserved':d['all_named_subgroups_preserved'],'all50_required_acceptances_original125_all_prior_repairs_latest_targets':d['all_required_acceptances_pass'],'all23_required_rejections_including_core10_and107_113_159':d['all_required_rejections_pass'],'fresh_general_strict_signed_MAE_MAPE_FA_gains':all(c['general_strict_signed'].values()) and c['general_strict_fa_gain_signed'],'fresh_general_no_loss_six_comparators_tail_FA_FR_and_no_new_cases':c['general_no_loss'],'all_prospective_activity_and_feature_novelty_requirements':c['coverage']['passed'] and c['model_specific_activity_passes'],'fixed_sharing8_no_loss_and_cap_gates':c['sharing_passes'],'fixed_legacy8_no_loss_and_cap_gates':c['legacy_passes'],'conditional_full_no_loss_and_cap_gates':c['conditional_full_passes'],'active_only_no_loss_and_cap_gates':c['active_subset_passes'],'same1889_training_membership_and_no_consumed_evaluation_labels':proof['consumed_evaluation_labels_fitted']==0,'native_shared_tree_joint_outputs_and_class_mapping_leaf_probabilities_verified':True,'nested_probabilities_without_sorting_or_calibration_and_exact_half_tie':True,'source_cohort_targets_policy_gates_fixed_before_features_fits_or_labels':True,'both_classifiers_and_all128_probabilities_selection_frozen_before_labels':True,'summed_native_worker_seconds_at_most300_peak2_and_two_one_thread_fits':jobs['summed_worker_native_seconds']<=300 and jobs['recorded_worker_peak']<=2 and jobs['new_fits']==2,'all935_prior_scientific_files_preserved_goal_status_only_exception':count==935,'independent_native_RTL_netlist_cached_inference_chronology_verified':True,'separate_populations_shared_controls_no_pooled_or_universal_safety_claim':True}
 assert all(scientific.values())==eligible
 native=raw_audit(TEST);templates={t:sub([i for i,r in enumerate(rows) if r['template']==t]) for t in sorted({r['template'] for r in rows})}
 body={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'original_goal_ledger_status_only_mutable':True,'current_goal_clarification_fully_preserved':True,'fits':2,'new_training_labels':0,'training_rows':1889,'matched_classifier_training_and_leaf_probability_proof':proof,'old_regressor_leaf_forensics_reused_by_immutable_hash_not_repeated':True,'native_accounting':jobs,'parent_native_label_authorization_sha256':sha(TEST/'parent-authorization.json'),'parent_fit_authorization_sha256':sha(OUT/'execution-authorization.json'),'identity_and_modular_novelty_audit':identity_audit(),'analytical_target_and_bound_limitations_review':analytical_review(),'feature_freshness':fresh,'native_raw_evidence':native,'cached_inference':cached_inference(saved),'descriptive_diagnostics':diagnostics_review(saved,y),'development':dev,'fresh_general32':general,'fresh_sharing8':sharing,'fresh_legacy8':legacy,'fresh_conditional_full':conditional,'fresh_active_only':active,'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':chosen,'evaluated_candidate':evaluated,'scoped_experimental_eligibility':eligible,'selection_coverage':saved['selection_coverage'],'pool_count':128,'selected_unique_label_count':len(y),'all_unselected_pool_rows_features_probabilities_retained':True,'shared_control_count':8,'shared_control_selected_indices':saved['shared_control_selected_indices'],'shared_controls_not_independent':True,'general_cap_decision_cases':decisions(saved['general_selected_indices']),'sharing_cap_decision_cases':decisions(saved['sharing_selected_indices']),'legacy_cap_decision_cases':decisions(saved['legacy_selected_indices']),'conditional_full_cap_decision_cases':decisions(saved['conditional_selected_indices']),'active_only_cap_decision_cases':decisions(saved['active_selected_indices']),'selected_numeric_fields_compared':fields,'development_policy_points_replayed':1049*12,'all_pool_policy_points_replayed':128*12,'selected_policy_points_replayed':len(y)*12,'all_development_and_pool_raw_probability_values_replayed':(1049+128)*3*2,'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':all(scientific.values()),'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,'false_acceptance_sum_unit':'Circuit-budget events, not unique circuits. Per-cap actual feasible/infeasible denominators and changed-case identities are reported for each population.','mape_definition':'100*mean(abs(actual-prediction)/actual) over actual>0; zero targets remain in MAE, cap and tail metrics and are excluded only from MAPE.','mathematical_bounds':'signed<=candidate<=release: release false acceptances and signed false rejections cannot be corrected. No-worse separate counts therefore imply no new per-case mistakes against those references; six known bound-limited errors remain disclosed.','limitations':['Native shared-tree nested feasibility probabilities are uncalibrated class-frequency estimates, not certified risk or hardware safety.','Both matched classifiers use exactly the frozen1889 fitted rows. The217/233 comparison isolates the16-column block within classification; regression comparison changes learning objective.','Allfour structural input-support cells occur in training, so that guard is inactive within the matching root-chain scope.','The modular novelty screen adds two sound rewrites and preserves the rejected36-row finding; it is not exhaustive semantic independence.','The fixed general/sharing/legacy and prediction-selected conditional/active populations are separately gated with8shared controls and no pooled or independence claim.','OriginalRTL proof uses finite2148 vectors per selected case; mapped-cell recounts are not universal equivalence, mappednetlist functional proof, timing, power or CPU-performance evidence.']}
 return receipt(OUT/'audit.json',body,write)


def diagnostics_review(saved,y):
 d=read(OUT/'failure-diagnostics.json');assert d['status']=='postlabel_descriptive_only' and d['policy_changed'] is False and d['new_fits']==d['new_native_jobs']==0 and d['calibration_claim'] is False;check_bindings(d['bindings'])
 panels=read(OUT/'development-predictions.json');lookup={cid:(r,i) for r in panels.values() for i,cid in enumerate(r['candidate_ids'])};lookup.update({cid:({**saved,'actual_lut4':y},i) for i,cid in enumerate(saved['candidate_ids'])});selection=read(TEST/'selection.json');rows=read(TEST/'candidates.json');count=0
 def walk(v):
  nonlocal count
  if isinstance(v,dict):
   if 'candidate_id' in v:
    r,i=lookup[v['candidate_id']];assert v['formula']==r['formulas'][i] and v['actual_lut4']==r['actual_lut4'][i]
    for key in ('predictions_lut4','predictions'):
     if key in v:assert all(p==r['models'][n][i] for n,p in v[key].items())
    for key in ('feasibility_probabilities','probabilities'):
     if key in v:assert all(p==r['feasibility_probabilities'][n][i] for n,p in v[key].items())
    if 'corroboration_raw_lut4' in v:assert all(p==r['corroboration_raw_lut4'][n][i] for n,p in v['corroboration_raw_lut4'].items())
    if 'cells' in v:assert v['cells']==r['feasibility_cells'][i]
    if 'selected_index' in v:assert v['selected_index']==i and v['pool_index']==selection['selected_pool_indices'][i] and v['template']==rows[i]['template']
    count+=1
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(d)
 for group,key in (('general','general_selected_indices'),('sharing','sharing_selected_indices'),('legacy','legacy_selected_indices'),('conditional_full','conditional_selected_indices'),('active','active_selected_indices')):
  for n in CANDIDATES:
   fa={(saved['candidate_ids'][i],c) for i in saved[key] for c in CAPS if saved['models'][n][i]<=c<saved['models'][RELEASE][i] and y[i]>c};fr={(saved['candidate_ids'][i],c) for i in saved[key] for c in CAPS if saved['models'][CURRENT][i]<=c<saved['models'][n][i] and y[i]<=c};dd=d['fresh_failures'][group][n]
   assert {(r['candidate_id'],r['cap']) for r in dd['new_false_acceptances_vs_release']}==fa and {(r['candidate_id'],r['cap']) for r in dd['new_false_rejections_vs_signed']}==fr
 assert len(d['all_eight_active_outcomes'])==len(saved['active_selected_indices'])==8 and len(d['mandatory_veto_outcomes'])==2
 assert d['fresh_policy_predictions_identical']==(saved['models'][CANDIDATES[0]]==saved['models'][CANDIDATES[1]])
 return {'sha256':sha(OUT/'failure-diagnostics.json'),'descriptive_case_instances_numerically_replayed':count,'all_five_population_new_error_identity_sets_verified':True,'all_eight_active_and_both_veto_truths_verified':True,'no_policy_or_threshold_change':True}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=('modular-rules','preflight','prelabel','final'),default='final',nargs='?');p.add_argument('--write-receipt',action='store_true');a=p.parse_args();r=modular_rules_check() if a.command=='modular-rules' else globals()[{'final':'final_audit'}.get(a.command,a.command)](a.write_receipt);print(json.dumps({k:r[k] for k in ('status','selected_candidate','scoped_experimental_eligibility','native_accounting','audit_fits','audit_native_jobs') if k in r},indent=2) if a.command!='modular-rules' else json.dumps(r,indent=2))

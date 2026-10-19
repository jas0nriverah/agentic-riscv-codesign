"""Focused independent V8 point-freeze audit: never fit, predict, or read fresh targets."""
from pathlib import Path
import hashlib,json,math,subprocess,sys
repo=(Path(__file__).resolve().parent.parent/'agentic-riscv-codesign').resolve();sys.path[:0]=[str(repo),str(repo/'scripts')]
import numpy as np
import measure_v8_applications as collector
from isaforge import area_model_v8 as v8
root=repo/'results/2026-10-15-v8-application-transfer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def need(v,m):
 if not v:raise AssertionError(m)
point,inputs,rows,bindings=collector.freeze_records(root)
before={p:sha(p) for p in bindings}
start=read(root/'training-start.json');review=read(root/'parent-fit-review.json');prep=read(root/'training/preparation.json')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
need(review['status']=='approved-fixed-two-fits' and review['input_seal_sha256']==sha(root/'input-seal.json') and review['training_preparation_sha256']==sha(root/'training/preparation.json') and review['training_runner_sha256']==sha(repo/'scripts/train_v8_applications.py'),'Parent fit release mismatch')
need(collector.utc(review['reviewed_at_utc'])<=collector.utc(start['started_at_utc'])<=collector.utc(point['frozen_at_utc']),'Review/start/point chronology mismatch')
need(start['planned_fits']==list(v8.TRAINED_VIEWS) and start['maximum_fits']==2 and start['mapping_control_refitted'] is False and start['fresh_application_labels_read'] is False,'Exactly2 planned new fits required')
need(start['configuration']==v8.FIXED_PARAMETERS and prep['fixed_parameters']==v8.FIXED_PARAMETERS and prep['training_formula_count']==1665,'Fixed recipe mismatch')
# Every source/input bound before fitting must match committed HEAD bytes.
committed={}
for base,entries in [(root,start['files']),(root,inputs['files']),(root/'training',prep['files']),(root,review['evidence'])]:
 for e in entries:
  p=(base/e['path']).resolve();need(p.is_relative_to(repo) and sha(p)==e['sha256'],'Invalid source/input/review binding')
  original=subprocess.check_output(['git','show',head+':'+p.relative_to(repo).as_posix()],cwd=repo)
  need(hashlib.sha256(original).hexdigest()==e['sha256'],'Pre-fit input differs from committed HEAD');committed[p]=e['sha256']
for p in [root/'input-seal.json',root/'training/preparation.json',root/'parent-fit-review.json']:
 need(hashlib.sha256(subprocess.check_output(['git','show',head+':'+p.relative_to(repo).as_posix()],cwd=repo)).hexdigest()==sha(p),'Pre-fit manifest differs from HEAD')
attempts=sorted((root/'fit-attempts').glob('*'));need([p.name for p in attempts]==sorted(v+'.json' for v in v8.TRAINED_VIEWS),'Exactly2 attempt files required')
for i,view in enumerate(v8.TRAINED_VIEWS,1):
 p=root/'fit-attempts'/(view+'.json');a=read(p)
 need(set(a)=={'fit_index','view','started_at_utc','training_start_sha256'} and a['fit_index']==i and a['view']==view and a['training_start_sha256']==sha(root/'training-start.json'),'Attempt identity mismatch')
 need(collector.utc(start['started_at_utc'])<=collector.utc(a['started_at_utc'])<=collector.utc(point['frozen_at_utc']),'Attempt chronology mismatch')
 need(p in bindings,'Attempt missing point freeze binding')
training_path=collector.checked(prep['training_data'],root/'training');training=read(training_path);x=np.asarray(training['values'],dtype=float)
need(x.shape==(1665,455) and np.isfinite(x).all() and (x>=0).all(),'Invalid stored training inputs')
models={};predictions={}
for name,entry in point['models'].items():
 records=read(collector.checked(entry['predictions'],root));need(len(records)==152,'Prediction coverage mismatch')
 seen={}
 for row,p in zip(rows,records):
  need(all(row[k]==p[k] for k in ['benchmark','candidate_id','formula']) and p['model']==name and p['calibration_status']=='point_only_application_pilot','Prediction alignment/status mismatch')
  need(type(p['predicted_lut4']) in (int,float) and math.isfinite(p['predicted_lut4']) and p['predicted_lut4']>=0 and p['upper_lut4'] is None,'Invalid point')
  spread=p['tree_disagreement_lut4'];outside=p['outside_training_feature_ranges']
  need(spread is None or (type(spread) in (int,float) and math.isfinite(spread) and spread>=0),'Invalid spread')
  need(outside is None or (type(outside) is int and outside>=0),'Invalid range count')
  value=(p['predicted_lut4'],spread,outside);need(row['formula'] not in seen or seen[row['formula']]==value,'Shared formula predictions/diagnostics differ');seen[row['formula']]=value
 predictions[name]={'sha256':sha(collector.checked(entry['predictions'],root)),'aligned_rows':len(records),'unique_formulas':len(seen),'point_only':True}
 if name in v8.TRAINED_VIEWS:
  artifact=collector.checked(entry['artifact'],root);schema=read(collector.checked(entry['schema'],root));model=v8.load_model(artifact)
  need(model.view==name and model.estimator.n_features_in_==336 and len(model.estimator.estimators_)==300,'Forest/view mismatch')
  need(model.feature_minimum==x.min(axis=0).tolist() and model.feature_maximum==x.max(axis=0).tolist(),'Stored training ranges mismatch')
  need(model.training_environment==start['environment'] and model.audited_compatibility==start['compatibility'],'Fitting environment mismatch')
  need(all(t.tree_.n_node_samples[0]==1665 for t in model.estimator.estimators_),'Tree training rows mismatch')
  models[name]={'artifact_sha256':sha(artifact),'schema_sha256':sha(artifact.with_suffix('.json')),'estimator_fingerprint':schema['estimator_fingerprint'],'tree_count':300,'each_tree_root_training_rows':1665,'selected_features':336,'fixed_parameters':model.estimator.get_params(),'feature_ranges_exact_training_minmax':True}
 else:
  for kind in ['artifact','schema']:
   p=collector.checked(entry[kind],root);need(hashlib.sha256(subprocess.check_output(['git','show',head+':'+p.relative_to(repo).as_posix()],cwd=repo)).hexdigest()==sha(p),'Existing control differs from HEAD')
  models[name]={'artifact_sha256':entry['artifact']['sha256'],'schema_sha256':entry['schema']['sha256'],'existing_control_unchanged':True}
need(not any((root/n).exists() for n in ['label-approval.json','label-release.json','measurements','evaluation.json']),'Fresh target stage unexpectedly exists')
need(not (repo/collector.PREFIX).exists(),'Fresh target scratch unexpectedly exists')
need(all(sha(p)==h for p,h in before.items()),'Frozen bytes changed during audit')
result={'schema':'isaforge-v8-independent-point-freeze-review-v1','status':'pass','decision':'GO for parent commit and separately approved target release','head_at_review':head,'point_freeze_sha256':sha(root/'point-freeze.json'),'input_seal_sha256':sha(root/'input-seal.json'),'training_start_sha256':sha(root/'training-start.json'),'training_preparation_sha256':sha(root/'training/preparation.json'),'parent_fit_review_sha256':sha(root/'parent-fit-review.json'),'collector_freeze_records_validated':True,'total_frozen_bindings':len(bindings),'committed_prefit_bindings_verified':len(committed),'fit_attempt_count':len(attempts),'models':models,'predictions':predictions,'audit_performed_refits':0,'audit_recomputed_predictions':False,'fresh_target_files_read':False,'fresh_target_stage_or_scratch_present':False,'scope':'Validates fixed fit recording, forest/schema/source/input identity and six aligned point files. Independent CLI inference replay is reviewed separately. Does not release labels or make accuracy claims.'}
out=Path(__file__).with_name('point-freeze-review.json');need(not out.exists(),'Audit report exists');out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))

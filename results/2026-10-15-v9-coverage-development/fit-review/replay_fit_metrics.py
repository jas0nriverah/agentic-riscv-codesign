"""Independent standard-library replay of fixed V9 coverage development metrics."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,math,re,statistics


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(v,m):
 if not v:raise AssertionError(m)
def quantile(values,q):
 values=sorted(values);position=(len(values)-1)*q;lo=math.floor(position);hi=math.ceil(position)
 return values[lo]+(values[hi]-values[lo])*(position-lo)
def metrics(actual,predicted):
 need(len(actual)==len(predicted)>0,'Complete nonempty metric vectors required')
 need(all(type(y) in (int,float) and math.isfinite(y) and y>=0 and y==int(y) for y in actual),'Invalid integer target')
 need(all(type(p) in (int,float) and math.isfinite(p) and p>=0 for p in predicted),'Invalid frozen point')
 actual=[int(y) for y in actual];res=[p-y for y,p in zip(actual,predicted)];errors=[abs(e) for e in res]
 positive=[e/y for y,e in zip(actual,errors) if y>0];zero=[e for y,e in zip(actual,errors) if y==0]
 return {'count':len(actual),'mae_lut4':sum(errors)/len(errors),'signed_bias_lut4':sum(res)/len(res),
 'rmsle':math.sqrt(sum((math.log1p(p)-math.log1p(y))**2 for y,p in zip(actual,predicted))/len(actual)),
 'positive_target_count':len(positive),'positive_mape_percent':sum(positive)/len(positive)*100 if positive else None,
 'zero_target_count':len(zero),'zero_mae_lut4':sum(zero)/len(zero) if zero else None,
 'p95_absolute_error_lut4':quantile(errors,.95),'p99_absolute_error_lut4':quantile(errors,.99),
 'worst_absolute_error_lut4':max(errors),'maximum_underprediction_lut4':max([0]+[-r for r in res]),
 'underprediction_count':sum(r<0 for r in res),'overprediction_count':sum(r>0 for r in res),'exact_prediction_count':sum(r==0 for r in res),
 'caps':{str(c):{'false_accept_count':sum(p<=c<y for y,p in zip(actual,predicted)),
 'false_reject_count':sum(y<=c<p for y,p in zip(actual,predicted)),'predicted_feasible_count':sum(p<=c for p in predicted),
 'actually_feasible_count':sum(y<=c for y in actual),'count':len(actual)} for c in [32,64,128]}}
def paired(rows,targets,points):
 need(set(points)=={'frozen','augmented'},'Exactly frozen/augmented predictors required')
 need(all(len(v)==len(rows) and [r['formula'] for r in rows]==[p['formula'] for p in v] for v in points.values()),'Frozen point order/coverage mismatch')
 return {m:metrics([targets[r['formula']] for r in rows],[p['predicted_lut4'] for p in values]) for m,values in points.items()}
def subset(rows,points,positions):
 return [rows[i] for i in positions],{m:[v[i] for i in positions] for m,v in points.items()}
def compare(expected,actual,path='',mismatches=None,roundoff=None):
 mismatches=[] if mismatches is None else mismatches;roundoff=[] if roundoff is None else roundoff
 if isinstance(expected,dict):
  if not isinstance(actual,dict) or set(expected)!=set(actual):mismatches.append({'path':path,'reason':'dictionary keys'})
  else:
   for k in expected:compare(expected[k],actual[k],path+'/'+k,mismatches,roundoff)
 elif isinstance(expected,list):
  if not isinstance(actual,list) or len(expected)!=len(actual):mismatches.append({'path':path,'reason':'list size'})
  else:
   for i,(a,b) in enumerate(zip(expected,actual)):compare(a,b,path+'/'+str(i),mismatches,roundoff)
 elif path.endswith('/maximum_underprediction_lut4') and type(expected) in (int,float) and type(actual) in (int,float) and expected==actual==0:
  pass  # Engine max() can represent this real-valued zero as int0 or float-0.0.
 elif type(expected) is float:
  if type(actual) is not float or not math.isfinite(actual) or not math.isclose(expected,actual,rel_tol=1e-11,abs_tol=1e-10):mismatches.append({'path':path,'expected':expected,'actual':actual})
  elif expected!=actual:roundoff.append({'path':path,'absolute_difference':abs(expected-actual)})
 elif type(expected) is not type(actual) or expected!=actual:mismatches.append({'path':path,'expected':expected,'actual':actual})
 return mismatches,roundoff

def run(repo,root,fit,output):
 # This guard must precede every evaluation-target read.
 freeze=read(fit/'point-freeze.json');need(freeze['new_fits']==1 and freeze['training_rows']==1713 and freeze['evaluation_target_files_opened'] is False,'Completed one-fit pretarget freeze required')
 need(sha(fit/'point-predictions.json')==freeze['predictions_sha256'],'Point digest mismatch')
 need(sha(fit/'models/mapping-coverage.joblib')==freeze['artifact_sha256'] and sha(fit/'models/mapping-coverage.json')==freeze['schema_sha256'],'Artifact/schema digest mismatch')
 need(sha(root/'preparation.json')==freeze['preparation_sha256'],'Preparation changed')
 start=read(fit/'training-start.json');attempt_record=read(fit/'fit-attempt.json')
 need(start['maximum_fits']==1 and attempt_record['fit_index']==1 and attempt_record['rows']==1713,'One fixed1713-row fit required')
 need(sha(root/'measurements/completion.json')==start['measurement_completion_sha256'],'Fitted measurement completion changed')
 official=read(fit/'evaluation.json');need(official['point_freeze_sha256']==sha(fit/'point-freeze.json'),'Evaluation point freeze binding mismatch')
 recipe=read(root/'recipe.json');predictions=read(fit/'point-predictions.json')
 need(set(predictions)=={'applications','v6_test_regression','original_training_in_sample','coverage_training_in_sample'},'Complete four-cohort predictions required')
 targetpaths=[]
 def targets(entry):
  p=repo/entry['path'];need(sha(p)==entry['sha256'],'Consumed target SHA mismatch');targetpaths.append(p);rows=read(p)
  result={r['formula']:r['lut4_count'] for r in rows};need(len(result)==len(rows),'Duplicate scoring originals');return result
 v8=repo/'results/2026-10-15-v8-application-transfer';v6=repo/'results/2026-10-14-v6'
 rows=read(v8/'rows.json');programs=read(v8/'programs.json');actual=targets(recipe['evaluation']['v8']['labels']);points=predictions['applications']
 need(len(rows)==152 and len(actual)==146 and len(programs)==5,'Complete V8 application pool required')
 by_program={}
 for p in programs:
  sub,pts=subset(rows,points,[i for i,r in enumerate(rows) if r['benchmark']==p['benchmark']]);by_program[p['benchmark']]=paired(sub,actual,pts)
 family_programs=defaultdict(list)
 for p in programs:
  if p['primary_family']:family_programs[p['family']].append(p['benchmark'])
 need(len(family_programs)==4,'Four primary source families required')
 family={f:{m:sum(by_program[n][m]['mae_lut4'] for n in names)/len(names) for m in ['frozen','augmented']} for f,names in family_programs.items()}
 macro={m:sum(family[f][m] for f in family)/len(family) for m in ['frozen','augmented']}
 app={'by_program':by_program,'primary_family_mae_lut4':family,'primary_family_macro_mae_lut4':macro,'augmented_minus_frozen_mae_lut4':macro['augmented']-macro['frozen'],'paired_family_differences_lut4':{f:family[f]['augmented']-family[f]['frozen'] for f in family}}
 positions=[i for i,r in enumerate(rows) if r['primary_family']];sub,pts=subset(rows,points,positions);app['pooled_primary']=paired(sub,actual,pts)
 constant=[i for i in positions if 'mul(' in rows[i]['formula'] and any(k in rows[i]['formula'] for k in ['addi(0,54)','addi(0,2025)','addi(lui(4096),-640)'])]
 signed=[i for i in positions if rows[i]['formula']=='sub(srai(add(in0,in1),5),srai(in1,31))'];need(len(constant)==6 and len(signed)==1,'Fixed diagnosed identity subsets differ')
 app['diagnosed_subsets']={}
 for name,pos in [('constant_multiply_six',constant),('signed_shift_cap_case',signed)]:
  sub,pts=subset(rows,points,pos);app['diagnosed_subsets'][name]={'formulas':[r['formula'] for r in sub],'scores':paired(sub,actual,pts)}
 regression_rows=read(v6/'corpus/test/candidates.json');regression=targets(recipe['evaluation']['v6_test']['labels']);need(len(regression_rows)==len(regression)==192,'Complete V6 regression pool required')
 original=read(root/'original-training.json');candidates=read(root/'candidates.json');completion=read(root/'measurements/completion.json')
 need(isinstance(completion['attempt'],str) and re.fullmatch('attempt-[0-9]{4}',completion['attempt']) is not None,'Owned coverage attempt required')
 labels_path=root/'measurements'/completion['attempt']/'labels.json';need(sha(labels_path)==completion['labels_sha256']==attempt_record['labels_sha256'],'New fitting label digest differs');targetpaths.append(labels_path);new_labels=read(labels_path);new={r['formula']:r['lut4_count'] for r in new_labels};need(len(new_labels)==48,'Exactly48 new training labels required')
 need(len(new)==len(candidates)==48 and len(original['rows'])==1665,'Complete original and new training pools required')
 expected={'primary':app,'v6_test_regression':paired(regression_rows,regression,predictions['v6_test_regression']),
 'original_training_in_sample':paired(original['rows'],{r['formula']:r['lut4_count'] for r in original['rows']},predictions['original_training_in_sample']),
 'coverage_training_in_sample':paired(candidates,new,predictions['coverage_training_in_sample'])}
 mismatches=[];roundoff=[]
 for key in expected:compare(expected[key],official[key],'/'+key,mismatches,roundoff)
 result={'schema':'isaforge-v9-independent-fit-metric-replay-v1','status':'pass' if not mismatches else 'fail','point_freeze_sha256':sha(fit/'point-freeze.json'),'evaluation_sha256':sha(fit/'evaluation.json'),'audit_source_sha256':sha(Path(__file__)),'cohort_rows':{'applications':152,'v6_test_regression':192,'original_training_in_sample':1665,'coverage_training_in_sample':48},'model_count':2,'primary_families':4,'metrics':expected,'mismatches':mismatches,'roundoff_comparison':{'absolute_tolerance':1e-10,'relative_tolerance':1e-11,'zero_type_policy':'Integer0/float signed0 are the same mathematical zero only for maximum_underprediction_lut4; counts and all other integer types remain strict.','nonexact_float_fields':len(roundoff),'maximum_absolute_difference':max((r['absolute_difference'] for r in roundoff),default=0.)},'target_file_hashes':{str(p.relative_to(repo)):sha(p) for p in targetpaths},'new_fits_predictions_or_native_calls':0,'independence':'No experiment imports, model loading, fitting, predicting or native tools. Standard-library metric formulas independently recalculate all published two-model cohort/stratum metrics and program/family weighting.'}
 with output.open('x') as stream:stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
 need(not mismatches,'Independent metric mismatches: '+json.dumps(mismatches[:10]));print(json.dumps({k:v for k,v in result.items() if k not in ['metrics','target_file_hashes']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ['repo','root','fit','output']:p.add_argument('--'+key,type=Path,required=True)
 args=p.parse_args();run(args.repo.resolve(),args.root.resolve(),args.fit.resolve(),args.output.resolve())

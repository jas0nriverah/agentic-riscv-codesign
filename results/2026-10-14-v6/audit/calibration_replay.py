"""Independent calibrated-tree/point/margin replay before test label release."""
from pathlib import Path
import hashlib,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/2026-10-14-v6';OUT=BASE/'audit'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import evaluate_v6 as evaluator
from isaforge import area_model_v6 as model_api
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,what):
 if not ok:raise AssertionError(what)
def path(record):
 p=(BASE/record['path']).resolve();need(sha(p)==record['sha256'],'Frozen record bytes');return p
def arrays_equal(a,b):
 if a.dtype.names:
  return a.shape==b.shape and a.dtype.names==b.dtype.names and all(np.array_equal(a[n],b[n]) for n in a.dtype.names)
 return a.shape==b.shape and a.dtype==b.dtype and np.array_equal(a,b,equal_nan=True)
def forest_equal(a,b):
 need(a.get_params()==b.get_params(),'Estimator parameters unchanged')
 need(a.n_features_in_==b.n_features_in_ and a.n_outputs_==b.n_outputs_ and len(a.estimators_)==len(b.estimators_)==300,'Forest shape unchanged')
 for one,two in zip(a.estimators_,b.estimators_):
  need(one.get_params()==two.get_params(),'Tree parameters unchanged')
  x,y=one.tree_.__getstate__(),two.tree_.__getstate__();need(set(x)==set(y),'Tree state fields')
  for key in x:
   need(arrays_equal(x[key],y[key]) if isinstance(x[key],np.ndarray) else x[key]==y[key],'All named tree state/values unchanged')

need(not(BASE/'corpus/test/label-release.json').exists() and not(BASE/'corpus/test/completion.json').exists(),'Test labels must remain sealed')
point,rows,features,groups,predictions=evaluator.validate_point_freeze(BASE)
calibrated,upper=evaluator.validate_calibration_freeze(BASE)
done=read(BASE/'corpus/calibration/completion.json');labels=read(BASE/'corpus/calibration'/done['attempt']/'dataset.json')
lookup={(r['benchmark'],r['candidate_id']):r['lut4_count'] for r in labels}
results={}
for name,entry in calibrated['models'].items():
 original=model_api.load_model(path(point['models'][name]['artifact']));updated=model_api.load_model(path(entry['artifact']))
 forest_equal(original.estimator,updated.estimator)
 if original.semantic_expert is not None:forest_equal(original.semantic_expert.estimator,updated.semantic_expert.estimator)
 scores={}
 for row,prediction in zip(rows['calibration'],predictions[name]['calibration']):
  group=groups['calibration'][row['formula']];residual=lookup[(row['benchmark'],row['candidate_id'])]-prediction['predicted_lut4']
  scores[group]=max(scores.get(group,-float('inf')),residual)
 ordered=sorted(scores.values());rank=math.ceil((len(scores)+1)*.9);margin=None if rank>len(scores) else max(0.,ordered[rank-1])
 need(rank==88 and len(scores)==96,'96 complete groups/rank88')
 need(entry['calibration']['rank']==rank and entry['calibration']['group_count']==len(scores) and entry['calibration']['upper_margin_lut4']==margin,'Independent complete-group maximum residual quantile')
 results[name]={'group_count':len(scores),'rank':rank,'margin_lut4':margin,'named_tree_arrays_unchanged':True,'scopes':{}}
 for scope in ('calibration','test'):
  x=np.asarray([r['values'] for r in features[scope]['records']]);actual=updated.predict_features(rows[scope],x)
  need(actual==upper[name][scope],'Exact calibrated artifact replay')
  need([r['predicted_lut4'] for r in actual]==[r['predicted_lut4'] for r in predictions[name][scope]],'Point values unchanged from committed pointfreeze')
  need(all(r['upper_lut4']==r['predicted_lut4']+margin for r in actual),'Fixed fresh calibration upper bounds')
  results[name]['scopes'][scope]={'rows':len(actual),'all_fields_replayed':True,'point_values_unchanged':True}
for record in [*calibrated['files'],*[entry[k] for entry in calibrated['models'].values() for k in ('artifact','schema','calibration_predictions','test_predictions')]]:path(record)
need(not(BASE/'corpus/test/label-release.json').exists() and not(BASE/'corpus/test/completion.json').exists(),'Test label seal retained')
report={'status':'pass','phase':'Fresh calibration released; test targets never read','point_freeze_sha256':sha(BASE/'point-freeze.json'),
        'calibration_freeze_sha256':sha(BASE/'calibration-freeze.json'),'models':results,'new_estimator_fits':0,
        'state_comparison':'Every named tree field and value compared independently, excluding unused structured-array padding only.',
        'test_release_absent_at_completion':True,'audit_source_sha256':sha(Path(__file__))}
(OUT/'calibration-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

"""Independent prelabel artifact replay; never read fresh calibration/test targets."""
from pathlib import Path
from collections import Counter
import hashlib,json,shutil,subprocess,sys,time
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/2026-10-14-v6';OUT=BASE/'audit'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import evaluate_v6 as evaluator
from isaforge import area_model_v6 as v6,area_model_v5 as v5,area_model_v4 as v4,masterrtl_baseline as master,graph_features_v5 as graph
from isaforge.structural_features_v4 import normalize_formula
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,what):
 if not ok:raise AssertionError(what)
def checked(r):
 p=(BASE/r['path']).resolve();need(sha(p)==r['sha256'],'Frozen bytes '+str(p));return p
def forbidden(*a,**k):raise RuntimeError('Independent prelabel replay forbids native process invocation')
need(not any((BASE/'corpus'/s/n).exists() for s in ('calibration','test') for n in ('label-release.json','completion.json')),'Fresh labels must remain sealed')
point,rows,features,groups,predictions=evaluator.validate_point_freeze(BASE)
records=[evaluator.record(BASE/'point-freeze.json',BASE),*point['files']]
records += [entry[k] for entry in point['models'].values() for k in ('artifact','schema','calibration_predictions','test_predictions')]
hashes={str(checked(r)):r['sha256'] for r in records}
need(len(rows['calibration'])==len(rows['test'])==192,'192/192 cohorts')
need(not(set(groups['calibration'].values())&set(groups['test'].values())),'Disjoint complete components')
need(all(len({groups[s][r['formula']] for r in rows[s] if r['stratum']==name})==12 for s in rows for name in {r['stratum'] for r in rows[s]}),'Twelve groups per stratum')
old_root=checked(point['source_v5_freeze']).parent;old=read(old_root/'freeze.json')
need(point['models']['dual_graph']['artifact']['sha256']==old['models']['dual_graph']['artifact']['sha256'],'Unchanged primary comparator')
cache=ROOT.parent/'v6-independent-audit-cache';need(not cache.exists(),'Isolated audit cache begins absent');cache.mkdir()
allrows=rows['calibration']+rows['test']
schemas={name:read(checked(entry['schema'])) for name,entry in point['models'].items()}
def copy_sog(source,destination,formulas,tool):
 extractor=master.SOGExtractor(destination,frozen_tool=tool)
 for formula in formulas:
  _,key=extractor.key(formula);target=destination/key
  if not target.exists():
   need((source/key/'features.json').is_file(),'Referenced SOG cache exists');shutil.copytree(source/key,target)
master_cache=cache/'master';old_cache=cache/'v4'
copy_sog(ROOT/'generated/v5-features/sog',master_cache,[r['formula'] for r in allrows],schemas['masterrtl_fixed']['tool'])
copy_sog(ROOT/'generated/v5-features/v4',old_cache,[normalize_formula(r['formula']) for r in allrows],schemas['v4_frozen']['frozen_tool'])
master.tool_identity=forbidden;graph.tool_identity=forbidden
subprocess.run=forbidden;subprocess.Popen=forbidden;subprocess.check_output=forbidden
results={}
for name,entry in point['models'].items():
 model=v6.load_model(checked(entry['artifact'])) if name in v6.KINDS else v5.load_model(checked(entry['artifact'])) if name in v5.VIEWS else master.load_model(checked(entry['artifact']),master_cache) if name=='masterrtl_fixed' else v4.load_model(checked(entry['artifact']),old_cache)
 results[name]={}
 for scope in ('calibration','test'):
  x=np.asarray([r['values'] for r in features[scope]['records']]);t=time.perf_counter()
  actual=model.predict_features(rows[scope],x) if name in v6.KINDS else model.predict_features(rows[scope],x[:,:313]) if name in v5.VIEWS else model.predict(rows[scope])
  elapsed=time.perf_counter()-t
  need(actual==predictions[name][scope],f'Exact artifact prediction replay {name}/{scope}')
  poisoned=[{**r,'lut4_count':999999,'carry_count':-1,'correctness_verified':False,'target':{'lut4_count':0}} for r in rows[scope]]
  poison=model.predict_features(poisoned,x) if name in v6.KINDS else model.predict_features(poisoned,x[:,:313]) if name in v5.VIEWS else model.predict(poisoned)
  need(poison==actual,'Outcome metadata ignored')
  results[name][scope]={'rows':len(actual),'exact_all_fields':True,'outcome_metadata_ignored':True,'replay_seconds':elapsed}
for file,digest in hashes.items():need(sha(file)==digest,'Frozen bytes unchanged')
need(not any((BASE/'corpus'/s/n).exists() for s in ('calibration','test') for n in ('label-release.json','completion.json')),'Fresh label seal retained')
summary={'status':'pass','phase':'Prelabel artifact replay; no fresh calibration/test target read','point_freeze_sha256':sha(BASE/'point-freeze.json'),
 'models':results,'unique_frozen_files_verified':len(hashes),'manifest_files':len(point['files']),'point_prediction_records':8*384,
 'input_counts':{s:len(r) for s,r in rows.items()},'components_per_scope':{s:len(set(g.values())) for s,g in groups.items()},
 'native_process_calls':0,'new_estimator_fits':0,'input_feature_scope':'Stored336-feature matrix replay for new models and V5 controls; actual isolated SOG extraction for MasterRTL and V4.',
 'timing_scope':'No cold timing claim; old graph caches copied into separate writable audit directory.'}
(OUT/'point-replay.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

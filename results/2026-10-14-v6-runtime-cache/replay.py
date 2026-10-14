"""Input/prediction-only exact cache replay; deliberately never reads labels."""
from pathlib import Path
import hashlib,json,subprocess,sys
import numpy as np
REPO=Path(__file__).resolve().parent.parent/'agentic-riscv-codesign'
sys.path.insert(0,str(REPO))
from isaforge import area_model_v6 as v6
from isaforge import cached_mapping_inference_v6 as cached
OUT=Path(__file__).resolve().parent;ROOT=REPO/'results/2026-10-14-v6'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def prohibited(*a,**k):raise AssertionError('Native processes forbidden in exact warm-cache replay')
if (OUT/'replay.json').exists():raise ValueError('Audit immutable')
cache=OUT/'mapping-blocks'
if cache.exists():raise ValueError('First mapping-block cache must be absent')
point=read(ROOT/'point-freeze.json');cal=read(ROOT/'calibration-freeze.json')
rows=[];values=[]
for scope in ('calibration','test'):
 rows.extend(read(ROOT/'corpus'/scope/'candidates.json'))
 values.extend(r['values'] for r in read(ROOT/'corpus'/scope/'features.json')['records'])
artifacts=[ROOT/freeze['models'][name]['artifact']['path'] for freeze in (point,cal) for name in v6.KINDS]
bound=[REPO/'isaforge'/n for n in v6.source_hashes()]+[REPO/'isaforge/cached_mapping_inference_v6.py',ROOT/'point-freeze.json',ROOT/'calibration-freeze.json']
for artifact in artifacts:bound.extend((artifact,artifact.with_suffix('.json')))
before={str(p.relative_to(REPO)):sha(p) for p in bound}
write(OUT/'replay-plan.json',{'source_sha256':before,'rows':384,'feature_columns':336,'native_processes_allowed':False,
 'target_labels_read':False,'cases':['point/mapping_v6','point/router_v6','calibrated/mapping_v6','calibrated/router_v6'],
 'purpose':'Exact existing point/upper output preservation; no accuracy or latency selection'})
for name in ('Popen','run','check_output','check_call','call'):setattr(subprocess,name,prohibited)
model=v6.load_model(artifacts[0],REPO/'generated/v5-features')
extractor=cached.FeatureExtractor(REPO/'generated/v5-features',cache,frozen_tool=model.frozen_tool)
x,records=extractor.matrix(rows,workers=1)
assert np.array_equal(x,np.asarray(values,dtype=float))
assert extractor.last_cache_counts=={'hits':0,'misses':384}
# A valid hit must never recompute the cut/reuse/area-flow descriptors.
cached.feature_vector=prohibited
second,again=extractor.matrix(rows,workers=1)
assert np.array_equal(x,second) and records==again
assert extractor.last_cache_counts=={'hits':384,'misses':0}
poison=[{**r,'lut4_count':-999999,'predicted_lut4':999999,'upper_lut4':-1,'carry_count':999999,
 'stratum':'poison','correctness_verified':False} for r in rows]
cases=[]
for stage,freeze in (('point',point),('calibrated',cal)):
 for name in v6.KINDS:
  artifact=ROOT/freeze['models'][name]['artifact']['path']
  expected=sum((read(ROOT/freeze['models'][name][scope+'_predictions']['path']) for scope in ('calibration','test')),[])
  predictor=cached.load_model(artifact,REPO/'generated/v5-features',cache)
  for mode,data in (('ordinary',rows),('poisoned',poison)):
   actual=predictor.predict(data)
   assert actual==expected,(stage,name,mode)
   assert predictor.extractor.last_cache_counts=={'hits':384,'misses':0}
   cases.append({'stage':stage,'model':name,'mode':mode,'rows':384,'all_fields_identical':True,'mapping_cache_hits':384})
  print(stage,name,'ordinary+poisoned all384/allfields exact',flush=True)
assert before=={str(p.relative_to(REPO)):sha(p) for p in bound}
write(OUT/'replay.json',{'complete':True,'source_sha256':before,'exact_features':[384,336],
 'first_pass_misses':384,'second_pass_hits':384,'hit_mapping_recomputation_forbidden':True,'cases':cases,
 'native_process_calls':0,'target_labels_read':False,'frozen_sources_models_schemas_unchanged':True})
print('COMPLETE cache exact-output audit',flush=True)

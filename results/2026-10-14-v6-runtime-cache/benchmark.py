"""Fixed isolated warm inference latency comparison; execute only at parent CPU-idle gate."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time,statistics
import numpy as np
REPO=Path(__file__).resolve().parent.parent/'agentic-riscv-codesign'
sys.path.insert(0,str(REPO))
from isaforge import area_model_v6 as v6
from isaforge import cached_mapping_inference_v6 as cached
OUT=Path(__file__).resolve().parent;ROOT=REPO/'results/2026-10-14-v6'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def prohibited(*a,**k):raise AssertionError('Native processes forbidden in warm comparison')
if not (OUT/'parent-cpu-idle.json').exists():raise ValueError('Parent must explicitly report target synthesis idle before comparison')
if (OUT/'timings.json').exists():raise ValueError('Comparison immutable')
point=read(ROOT/'point-freeze.json');idle=read(OUT/'parent-cpu-idle.json')
if idle.get('target_synthesis_idle') is not True or idle.get('point_freeze_sha256')!=sha(ROOT/'point-freeze.json'):
 raise ValueError('Current point freeze requires explicit parent target-synthesis-idle evidence')
rows=[];records=[]
for scope in ('calibration','test'):
 rows.extend(read(ROOT/'corpus'/scope/'candidates.json'));records.extend(read(ROOT/'corpus'/scope/'features.json')['records'])
expected=sum((read(ROOT/point['models']['mapping_v6'][s+'_predictions']['path']) for s in ('calibration','test')),[])
model=v6.load_model(ROOT/point['models']['mapping_v6']['artifact']['path'],REPO/'generated/v5-features')
folders={('generic',r[k]) for r in records for k in ('original_cache_key','normalized_cache_key')}
folders.update(('sog',r['sog_cache_key']) for r in records)
# Each side gets byte-identical, independent files; no shared generic/native-cache writes.
cache_hashes={}
for side in ('baseline','cached'):
 destination=OUT/('timing-'+side+'-generic')
 if destination.exists():raise ValueError('Timing generic caches must start absent')
 for kind,key in sorted(folders):shutil.copytree(REPO/'generated/v5-features'/kind/key,destination/kind/key)
 for path in sorted(destination.rglob('*')):
  if path.is_file():
   relative=str(path.relative_to(destination));h=sha(path)
   if side=='baseline':cache_hashes[relative]=h
   elif cache_hashes[relative]!=h:raise ValueError('Isolated generic caches differ')
block=OUT/'timing-mapping-blocks'
if block.exists():raise ValueError('Timing mapping cache must start absent')
plan={'protocol':'three alternating matched pairs after one untimed warm-up per side',
 'rows':384,'model':'mapping_v6','point_freeze_sha256':sha(ROOT/'point-freeze.json'),
 'wrapper_source_sha256':sha(Path(cached.__file__)),'runtime_source_sha256':v6.source_hashes(),
 'generic_cache_files_sha256':cache_hashes,'new_mapping_cache_initially_absent':True,
 'native_processes_allowed':False,'target_labels_read':False,'load_time_included':False,
 'timed_work':'336-feature extraction and unchanged mapping_v6.predict_features; retained extractors; workers=1',
 'parent_cpu_idle_evidence':read(OUT/'parent-cpu-idle.json'),
 'order':[['baseline','cached'],['cached','baseline'],['baseline','cached']]}
write(OUT/'timing-plan.json',plan)
for name in ('Popen','run','check_output','check_call','call'):setattr(subprocess,name,prohibited)
extractors={'baseline':v6.FeatureExtractor(OUT/'timing-baseline-generic',frozen_tool=model.frozen_tool),
 'cached':cached.FeatureExtractor(OUT/'timing-cached-generic',block,frozen_tool=model.frozen_tool)}
def run(side):
 started=time.perf_counter();x,_=extractors[side].matrix(rows,workers=1)
 actual=model.predict_features(rows,x);elapsed=time.perf_counter()-started
 assert np.array_equal(x,np.asarray([r['values'] for r in records])) and actual==expected
 return elapsed
warm={side:run(side) for side in ('baseline','cached')}
assert extractors['cached'].last_cache_counts=={'hits':0,'misses':384}
cached.feature_vector=prohibited
observations=[]
for pair,order in enumerate(plan['order']):
 for side in order:
  elapsed=run(side);observations.append({'pair':pair,'side':side,'seconds':elapsed})
  if side=='cached':assert extractors[side].last_cache_counts=={'hits':384,'misses':0}
  print(pair,side,round(elapsed,6),flush=True)
medians={s:statistics.median(r['seconds'] for r in observations if r['side']==s) for s in extractors}
assert v6.source_hashes()==plan['runtime_source_sha256'] and sha(Path(cached.__file__))==plan['wrapper_source_sha256']
for side in extractors:
 base=OUT/('timing-'+side+'-generic')
 assert cache_hashes=={str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()}
write(OUT/'timings.json',{'complete':True,'plan_sha256':sha(OUT/'timing-plan.json'),'warmup_seconds':warm,
 'observations':observations,'median_seconds':medians,'median_speedup':medians['baseline']/medians['cached'],
 'median_seconds_saved':medians['baseline']-medians['cached'],'all_384_features_predictions_identical':True,
 'native_calls':0,'target_labels_read':False,'generic_caches_unchanged':True,
 'limits':'One host and fixed 384-row input corpus; 3 deterministic pairs, no distributional speed guarantee; excludes model loading and cold native extraction. Both sides retain extractors.'})
print('COMPLETE fixed latency comparison',flush=True)

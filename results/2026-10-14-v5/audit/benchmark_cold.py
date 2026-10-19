"""Time one frozen V5 artifact in a verified absent isolated feature cache."""
from pathlib import Path
from collections import Counter
import hashlib,json,statistics,subprocess,sys,time
from datetime import datetime,timezone
REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
BASE=REPO/'results/2026-10-14-v5';OUT=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/v5-independent-audit');CACHE=OUT/'cold-cache'
sys.path.insert(0,str(REPO))
from isaforge.area_model_v5 import load_model
from isaforge.graph_features_v5 import GraphExtractor
from isaforge.masterrtl_baseline import SOGExtractor
require=lambda ok,message:None if ok else (_ for _ in ()).throw(ValueError(message))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
require(not CACHE.exists(),'Cold cache must be absent; no clearing/reusing an existing cache')
absent_before=True;artifact=BASE/'models/dual_semantics.joblib';inputs=BASE/'corpus/test/candidates.json';frozen=BASE/'predictions/dual_semantics.json'
rows=json.loads(inputs.read_text());expected=json.loads(frozen.read_text());freeze_sha=sha(BASE/'freeze.json')
t=time.perf_counter();model=load_model(artifact,CACHE);loading=time.perf_counter()-t
require(not CACHE.exists(),'Model load unexpectedly populated feature cache')
active='cold';stats={};native_run=subprocess.run;channel=GraphExtractor._channel;sog=SOGExtractor.extract

def instrument_run(args,*a,**kw):
 if isinstance(args,(list,tuple)) and Path(str(args[0])).name=='yosys':
  kind='yosys_version_queries' if '-V' in args else 'yosys_extractions'
  stats[active][kind]+=1
 return native_run(args,*a,**kw)

def instrument_channel(self,formula):
 result=channel(self,formula)
 stats[active]['generic_cache_hits' if result['cache_hit'] else 'generic_cache_misses']+=1
 return result

def instrument_sog(self,formula):
 result=sog(self,formula)
 stats[active]['sog_cache_hits' if result[1] else 'sog_cache_misses']+=1
 return result

subprocess.run=instrument_run;GraphExtractor._channel=instrument_channel;SOGExtractor.extract=instrument_sog
runs=[]
for i in range(4):
 active='cold' if i==0 else f'warm_{i}';stats[active]=Counter()
 t=time.perf_counter();predictions=model.predict(rows);elapsed=time.perf_counter()-t
 require(predictions==expected,'Cold/warm predictions differ from frozen list')
 runs.append({'phase':active,'feature_and_prediction_seconds':elapsed,'exact_frozen_prediction_match':True,'calls':dict(stats[active])})
 print(json.dumps(runs[-1]),flush=True)
subprocess.run=native_run;GraphExtractor._channel=channel;SOGExtractor.extract=sog
counts={name:len(list((CACHE/name).glob('*/features.json'))) for name in ('generic','sog')}
require(all(r['calls'].get('yosys_extractions',0)==0 for r in runs[1:]),'Warm repeat invoked Yosys extraction')
# A separate already-warm CLI process includes startup, imports, loading and IO.
cli_output=OUT/'runtime-cli-warm-predictions.json'
t=time.perf_counter();process=native_run([sys.executable,'-m','isaforge.area_model_v5','--model',str(artifact),'--candidates',str(inputs),'--cache-root',str(CACHE),'--output',str(cli_output)],cwd=REPO,capture_output=True,text=True,check=True);cli_elapsed=time.perf_counter()-t
require(json.loads(cli_output.read_text())==expected,'Warm CLI predictions differ')
completion=json.loads((BASE/'corpus/test/completion.json').read_text());measurement=completion['elapsed_seconds']
require(sha(BASE/'freeze.json')==freeze_sha,'Frozen manifest changed during benchmark')
result={'artifact':'dual_semantics','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'candidate_count':len(rows),'candidate_sha256':sha(inputs),'artifact_sha256':sha(artifact),'freeze_sha256':freeze_sha,
 'cache_root':str(CACHE),'cache_absent_before':absent_before,'cache_empty_after_model_load':True,'worker_count':1,'model_load_seconds':loading,'runs':runs,
 'cold_feature_and_prediction_seconds':runs[0]['feature_and_prediction_seconds'],'median_three_warm_feature_and_prediction_seconds':statistics.median(r['feature_and_prediction_seconds'] for r in runs[1:]),
 'cache_entry_counts_after_runs':counts,'warm_cli_elapsed_seconds':cli_elapsed,'warm_cli_exact_frozen_prediction_match':True,
 'api_timing_scope':'In-memory full original/normalized generic graph plus original SOG plus semantic feature extraction and estimator prediction. Model load separately timed. Excludes interpreter startup, input/output JSON and cache copying. Cold cache was absent; cold includes native Yosys.',
 'cli_timing_scope':'Separate warm-cache process wall time includes interpreter startup, imports, model loading, candidate/prediction JSON IO and inference. This is not cold CLI inference.',
 'completed_test_measurement_wall_seconds':measurement,'cold_inference_divided_by_completed_test_measurement_wall':runs[0]['feature_and_prediction_seconds']/measurement,
 'comparison_limits':['Test measurement wall time includes sampled RTL verification/compiler builds and target synthesis with four mapping workers; inference uses one feature worker and performs different work.',
 'This is one same-machine descriptive cold run and three immediate warm repeats for dual_semantics only. No latency result is asserted for other V5 views.',
 'Feature overhead ratio is not an end-to-end speedup or measurement savings result; training, development/calibration measurements and historical costs are excluded.',
 'Recorded timing varies with machine load, filesystem cache and native tool behavior; no runtime confidence interval is estimated.']}
(OUT/'runtime-cost.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print('COLD/WARM BENCHMARK PASSED',flush=True)

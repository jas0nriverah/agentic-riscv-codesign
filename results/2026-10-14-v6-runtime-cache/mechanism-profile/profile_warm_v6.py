"""Mechanism profile only: frozen point model, inputs, warm caches, no labels."""
from pathlib import Path
import cProfile,hashlib,json,pstats,subprocess,sys,time
REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from isaforge.area_model_v6 import load_model,source_hashes
root=REPO/'results/2026-10-14-v6';rows=[];expected=[]
for scope in ('calibration','test'):
 rows.extend(json.loads((root/'corpus'/scope/'candidates.json').read_text()))
 expected.extend(json.loads((root/'point-predictions'/f'mapping_v6-{scope}.json').read_text()))
model=load_model(root/'models/mapping_v6.joblib',REPO/'generated/v5-features')
native=[]
def forbidden(*args,**kwargs):native.append(str(args));raise RuntimeError('Profile must use existing warm native caches only')
subprocess.run=forbidden;subprocess.Popen=forbidden;subprocess.check_output=forbidden
source_before=source_hashes()
(OUT/'plan.json').write_text(json.dumps({'scope':'Mechanism-only profile;384 input rows,pointmodel,existingwarmcache,no newlabels',
 'runtime_sources':source_before,'implement_cache_if_mapping_analyze_cumulative_fraction_at_least':.15,
 'native_tools_prohibited':True,'comparative_timing':False},indent=2)+'\n')
profile=cProfile.Profile();started=time.perf_counter();profile.enable();observed=model.predict(rows);profile.disable()
elapsed=time.perf_counter()-started
if observed!=expected:raise ValueError('Profile changed frozen point predictions')
if source_hashes()!=source_before:raise ValueError('Frozen source changed')
profile.dump_stats(str(OUT/'warm-inference.prof'));stats=pstats.Stats(profile)
with (OUT/'profile.txt').open('w') as stream:pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(55)
analyze=[(key,value) for key,value in stats.stats.items() if key[0].endswith('/mapping_features_v6.py') and key[2]=='analyze']
assert len(analyze)==1
entry=analyze[0][1]
report={'rows':len(rows),'all_fields_identical':True,'native_calls':native,'profiled_wall_seconds':elapsed,
 'total_profile_seconds':stats.total_tt,'mapping_analyze_cumulative_seconds':entry[3],
 'mapping_analyze_fraction':entry[3]/stats.total_tt,'mapping_analyze_calls':entry[1],
 'cache_implementation_threshold':.15,'worth_implementing':entry[3]/stats.total_tt>=.15,
 'limits':'cProfile overhead and possible concurrent target work; mechanism attribution only, not comparative latency.'}
(OUT/'profile.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)

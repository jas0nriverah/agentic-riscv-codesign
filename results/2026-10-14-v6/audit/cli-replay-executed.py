"""Actual prelabel CLI replay, including separately absent cold caches."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time
REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from evaluate_v6 import validate_point_freeze
from isaforge.area_model_v6 import source_hashes

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
root=REPO/'results/2026-10-14-v6'
point,rows,_,_,expected=validate_point_freeze(root)
if (OUT/'completion.json').exists():raise ValueError('Existing replay immutable')
for scope in ('calibration','test'):
 if (root/'corpus'/scope/'label-release.json').exists():raise ValueError('Replay must precede every new label release')
before=source_hashes();freeze_hash=sha(root/'point-freeze.json')
write(OUT/'plan.json',{'point_freeze_sha256':freeze_hash,'runtime_source_sha256':before,
 'cases':['mapping_v6/calibration','mapping_v6/test','router_v6/calibration','router_v6/test'],
 'modes':['cold','warm','poisoned-warm'],'cold_caches':'Each model/scope starts in a separately absent cache directory',
 'command':'python -m isaforge.area_model_v6','target_labels_read':False})
results=[]
for model in ('mapping_v6','router_v6'):
 for scope in ('calibration','test'):
  folder=OUT/f'{model}-{scope}'
  if folder.exists():raise ValueError('Existing CLI case directory cannot be overwritten')
  folder.mkdir();cache=folder/'cache'
  artifact=(root/point['models'][model]['artifact']['path']).resolve()
  artifact_before=sha(artifact);schema_before=sha(artifact.with_suffix('.json'))
  candidate=root/'corpus'/scope/'candidates.json'
  poisoned=[{**r,'lut4_count':-123456789,'carry_count':999999999,'correctness_verified':False,
   'predicted_lut4':987654321,'upper_lut4':0,'stratum':'poisoned-outcome-metadata','speedup':-42} for r in rows[scope]]
  write(folder/'poisoned-candidates.json',poisoned)
  case={'model':model,'scope':scope,'cache_absent_before_cold':not cache.exists(),'artifact_sha256':artifact_before,'modes':{}}
  for mode in ('cold','warm','poisoned-warm'):
   source=folder/'poisoned-candidates.json' if mode=='poisoned-warm' else candidate
   output=folder/(mode+'.json');command=[sys.executable,'-m','isaforge.area_model_v6','--model',str(artifact),
    '--candidates',str(source),'--output',str(output),'--cache-root',str(cache)]
   started=time.perf_counter()
   with (folder/(mode+'.log')).open('wb') as log:
    p=subprocess.Popen(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
     code=p.wait(timeout=600)
     if code:raise RuntimeError(f'CLI {model}/{scope}/{mode} exit {code}')
    finally:
     try:os.killpg(p.pid,signal.SIGKILL)
     except ProcessLookupError:pass
     p.wait()
   seconds=time.perf_counter()-started;observed=read(output)
   if observed!=expected[model][scope]:raise ValueError(f'CLI all-field replay differs: {model}/{scope}/{mode}')
   if sha(artifact)!=artifact_before or sha(artifact.with_suffix('.json'))!=schema_before:raise ValueError('CLI changed model/schema')
   case['modes'][mode]={'seconds':seconds,'prediction_count':len(observed),'all_fields_identical':True,
    'predictions_sha256':sha(output),'command':command}
   print(model,scope,mode,round(seconds,3),'seconds, all192 predictions/allfields exact',flush=True)
  results.append(case);write(OUT/'progress.json',results)
if source_hashes()!=before or sha(root/'point-freeze.json')!=freeze_hash:raise ValueError('Frozen runtime/bundle changed')
validate_point_freeze(root)
for scope in ('calibration','test'):
 if (root/'corpus'/scope/'label-release.json').exists():raise ValueError('Labels released during prelabel replay')
write(OUT/'completion.json',{'complete':True,'point_freeze_sha256':freeze_hash,'runtime_source_sha256':before,
 'cases':results,'new_target_labels_read':False,'model_schema_unchanged':True,
 'limits':'Single sequential cold/warm pair per model/scope, includes CLI startup/loading/extraction/prediction, no population runtime claim.'})
print('COMPLETE prelabel all-field CLI cold/warm/metadata replay',flush=True)

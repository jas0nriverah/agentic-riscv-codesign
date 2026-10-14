"""Actual optional-wrapper CLI checks; candidates and predictions only."""
from pathlib import Path
import json,subprocess,sys,hashlib
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';ROOT=REPO/'results/2026-10-14-v6'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
if (OUT/'cli.json').exists():raise ValueError('Immutable CLI evidence exists')
freeze=read(ROOT/'calibration-freeze.json')
rows=sum((read(ROOT/'corpus'/s/'candidates.json') for s in ('calibration','test')),[])
write(OUT/'cli-candidates.json',rows)
cases=[]
for model in ('mapping_v6','router_v6'):
 output=OUT/f'cli-{model}.json'
 command=[sys.executable,'-m','isaforge.cached_mapping_inference_v6','--model',str(ROOT/freeze['models'][model]['artifact']['path']),
 '--candidates',str(OUT/'cli-candidates.json'),'--cache-root',str(REPO/'generated/v5-features'),
 '--mapping-cache-root',str(OUT/'mapping-blocks'),'--output',str(output)]
 result=subprocess.run(command,cwd=REPO,check=True,capture_output=True,text=True,timeout=300)
 expected=sum((read(ROOT/freeze['models'][model][s+'_predictions']['path']) for s in ('calibration','test')),[])
 assert read(output)==expected
 cases.append({'model':model,'rows':384,'all_fields_identical':True,'output_sha256':sha(output),'command':command,'stdout':result.stdout})
 print(model,'CLI all384 upper predictions exact',flush=True)
write(OUT/'cli.json',{'complete':True,'cases':cases,'target_labels_read':False,'wrapper_source_sha256':sha(REPO/'isaforge/cached_mapping_inference_v6.py')})

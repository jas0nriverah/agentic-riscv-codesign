"""Input-only all-ROI companion. Reuse already validated traces, no program retrace."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,sys
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';ROOT=REPO/'generated/application-input-feasibility'
sys.path[:0]=[str(REPO),str(REPO/'src')]
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates
from isaforge.features import parse_formula
from isaforge.structural_features_v5 import normalize_formula
OBJDUMP=OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
if (OUT/'all-roi-companion.json').exists():raise ValueError('Immutable prior evidence')
source=OUT/'runtime-feasibility.json';prior=read(source)
paths=[REPO/'results/2026-10-14-v6/corpus/consumed-features.json',REPO/'results/2026-10-14-v6/corpus/calibration/features.json',REPO/'results/2026-10-14-v6/corpus/test/features.json']
consumed=sum((read(p)['records'] for p in paths),[]);exact={parse_formula(r['formula']).canonical() for r in consumed};norm={r['normalized_formula'] for r in consumed};records={}
for n,r in prior['records'].items():
 folder=ROOT/n;elf=folder/'O2'/(n+'.elf');assert sha(elf)==r['build']['elf_sha256'];trace=folder/(n+'.jsonl.gz');runs=Counter();starts=set();previous=None
 with gzip.open(trace,'rt') as f:
  for line in f:
   pc=int(json.loads(line)['pc'],16);runs[pc]+=1
   if previous is None or pc!=previous+4:starts.add(pc)
   previous=pc
 if previous is not None:starts.add(previous+4)
 assert r['trace']['validated'] and sum(runs.values())==r['trace']['trace_instructions']
 program=readProgram(elf,str(OBJDUMP));previous=None
 for pc in sorted(program):
  symbol=program[pc].get('symbol')
  if symbol!=previous:starts.add(pc)
  previous=symbol
 candidates=extractCandidates(program,runs,starts,maxSize=4,limit=None);cdir=folder/'candidates-all-roi';cdir.mkdir();write(cdir/(n+'.json'),candidates)
 verification=verify_candidates(cdir,folder/'programs',str(OBJDUMP),vectors=16,seed=2026101507);assert verification['passed'] and all(x['skipped_opaque_block_occurrences']==0 for x in verification['benchmarks']);write(folder/'fusion-all-roi.json',verification)
 kernel=read(folder/'candidates'/(n+'.json'));kernel_keys={x['formula'] for x in kernel};assert kernel_keys<={x['formula'] for x in candidates}
 features=[]
 for row in candidates:
  key=parse_formula(row['formula']).canonical();normal=normalize_formula(key)
  features.append({'formula':key,'normalized_v5_formula':normal,'kernel_present':row['formula'] in kernel_keys,'exact_consumed':key in exact,'normalized_consumed':normal in norm,'sizeVariants':row['sizeVariants'],'occurrence_symbols':[x['symbols'] for x in row['occurrences']]})
 records[n]={'candidate_count':len(candidates),'kernel_candidate_count':len(kernel),'helper_only_count':len(candidates)-len(kernel),'retired_instructions':sum(runs.values()),'trace_sha256':sha(trace),'candidate_sha256':sha(cdir/(n+'.json')),'fusion_verification':verification,'input_only_overlap':features}
 print(n,len(candidates),len(kernel),sum(x['exact_consumed'] for x in features),sum(x['normalized_consumed'] for x in features),flush=True)
write(OUT/'all-roi-companion.json',{'status':'unsealed-input-only','scope':'Complete declared benchmark computation region; initialization, upstream status and snapshot probes excluded. Every called helper retained. Kernel attribution is secondary.','source_runtime_feasibility_sha256':sha(source),'script_sha256':sha(__file__),'consumed_input_sha256':{str(p.relative_to(REPO)):sha(p) for p in paths},'consumed_formula_count':len(exact),'records':records,'no_new_target_labels_models_predictions_fits_protocol_seal':True})

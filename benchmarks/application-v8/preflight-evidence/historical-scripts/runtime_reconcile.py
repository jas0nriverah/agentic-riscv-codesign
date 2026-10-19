"""Retain firstattempt/helper bugs; recover completed traces and finish original isqrt window once."""
from pathlib import Path
import collections,gzip,hashlib,json,math,os,sys
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';ROOT=REPO/'generated/application-input-feasibility'
sys.path[:0]=[str(REPO),str(REPO/'scripts'),str(REPO/'src')]
from collect_external_v5 import collect_trace_external
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates
SPIKE=OUT.parent/'toolchains/spike/bin/spike';OBJDUMP=OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def selected(s,allowed):return bool(s) and any(s==a or s.startswith(a+'.') for a in allowed)
def output(p):return [json.loads(x) for x in p.read_text().splitlines() if x.startswith('{')][0]['values']
if (OUT/'runtime-feasibility.json').exists():raise ValueError('Existing feasibility immutable')
prior=read(OUT/'runtime-preflight.json');records={}
for name,r in prior['records'].items():
 folder=ROOT/name;elf=folder/'O2'/(name+'.elf');assert sha(elf)==r['build']['elf_sha256']
 if name=='isqrt':
  actual=r['captured_outputs'];inputs=[0,1,2,3,4,15,16,17,65535,65536,0x7fffffff,0x80000000,0xffffffff,0x3fed0169,0x10000,0xffff0000]
  as_signed=lambda n:n-(1<<32) if n>=1<<31 else n
  expected=[as_signed(math.isqrt(x<<32)) for x in inputs]
  mismatches=[{'input':x,'actual':a,'ideal_mathematical':b,'signed_difference':a-b} for x,a,b in zip(inputs,actual[4:],expected) if a!=b]
  x=0x3fed0169;word=math.isqrt(x<<32)
  assert actual[:4]==[sum(math.isqrt(t<<32)>>16 for t in [*range(1,1001),x]),word&65535,word>>16,x]
  r['oracle']={'original_application_aggregate_and_captured_final_word_match_independent_math':True,
   'complete_u32_mathematical_oracle_pass':False,'supplemental_outside_window_boundary_mismatches':mismatches,
   'scope':'Original1001inputaggregate/finalq pass independentmath; supplementaryfullu32 functioncontractfails by2or3LSBs at4highinputs. Originalsource/dataunchanged. DoNOTclaim exactsqrtalluint32; probesareoutsidewindow.'}
  summary,runs,starts=collect_trace_external(str(SPIKE),elf,folder/(name+'.jsonl.gz'),folder/'trace.log',300);r['trace']=summary
  assert output(Path(summary['program_output']))==actual
 program=readProgram(elf,str(OBJDUMP));runs=collections.Counter();starts=set();previous=None
 with gzip.open(folder/(name+'.jsonl.gz'),'rt') as f:
  for line in f:
   pc=int(json.loads(line)['pc'],16);runs[pc]+=1
   if previous is None or pc!=previous+4:starts.add(pc)
   previous=pc
 if previous is not None:starts.add(previous+4)
 previous=None
 for pc in sorted(program):
  symbol=program[pc].get('symbol')
  if symbol!=previous:starts.add(pc)
  previous=symbol
 scoped=collections.Counter({pc:n for pc,n in runs.items() if selected(program[pc].get('symbol'),r['kernel_symbols'])})
 candidates=extractCandidates(program,scoped,starts,maxSize=4,limit=None)
 cdir=folder/'candidates';cdir.mkdir(exist_ok=True);cpath=cdir/(name+'.json')
 if cpath.exists():assert read(cpath)==candidates
 else:write(cpath,candidates)
 pdir=folder/'programs';pdir.mkdir(exist_ok=True)
 if not (pdir/(name+'.elf')).exists():os.link(elf,pdir/(name+'.elf'))
 verification=verify_candidates(cdir,pdir,str(OBJDUMP),vectors=16,seed=2026101507)
 assert verification['passed'] and all(b['skipped_opaque_block_occurrences']==0 for b in verification['benchmarks'])
 write(folder/'fusion.json',verification)
 assert r['trace']['validated'] and r['trace']['trace_instructions']==sum(runs.values())
 records[name]={**r,'status':'input-feasibility-complete-with-oracle-limit' if name=='isqrt' else 'input-feasibility-complete',
  'prior_attempt_status':r['status'],'prior_attempt_error':r.get('error'),'candidate_count':len(candidates),
  'kernel_retired_instructions':sum(scoped.values()),'all_measured_retired_instructions':sum(runs.values()),
  'candidate_sha256':sha(cpath),'fusion_verification':verification}
 print(name,len(candidates),sum(scoped.values()),sum(runs.values()),verification['benchmarks'][0],flush=True)
write(OUT/'runtime-feasibility.json',{'status':'unsealed-input-feasibility-not-test-assignment','records':records,
 'prior_attempt_sha256':sha(OUT/'runtime-preflight.json'),'reconcile_script_sha256':sha(__file__),
 'changes':'Firstattempt usedwrongverificationJSONkey; alreadycompleted3tracesreused/revalidated, notretraced. Isqrtmathprobe discrepanciesretained; originalfullinputwindownewlytraced unchanged.',
 'no_target_labels_models_fits_protocol_seal':True,'limits':'Full fixedsourcebenchmarkwindows only. No cycles/FPGAresources/selectionutility measured. Fusionissampledstatecomparison. FFT/NDES lackindependentcompletealgorithmoracles; isqrtfullu32mathematicalprobe failuresretained.'})

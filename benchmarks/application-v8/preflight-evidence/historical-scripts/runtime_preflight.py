"""Unsealed input feasibility: complete upstream runs/selfchecks/traces/fusion; no target labels/models."""
from pathlib import Path
import hashlib,json,math,os,signal,subprocess,sys,time
from collections import Counter
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench'
sys.path[:0]=[str(REPO),str(REPO/'scripts'),str(REPO/'src')]
from collect_external_v5 import collect_trace_external,command
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates
ROOT=REPO/'generated/application-input-feasibility';ROOT.mkdir(parents=True,exist_ok=True)
TOOL=OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin';CC=TOOL/'riscv-none-elf-gcc';OBJDUMP=TOOL/'riscv-none-elf-objdump';SPIKE=OUT.parent/'toolchains/spike/bin/spike'
SPECS={
 'bitcount':('kernel',['bitcount.c','bitcnt_1.c','bitcnt_2.c','bitcnt_3.c','bitcnt_4.c'],['bitcount_bit_count','bitcount_bitcount','bitcount_bit_shifter','bitcount_ntbl_bitcnt','bitcount_btbl_bitcnt','bitcount_ntbl_bitcount','bitcount_BW_btbl_bitcount','bitcount_AR_btbl_bitcount']),
 'isqrt':('kernel',['isqrt.c','basicmath_libc.c'],['isqrt_usqrt','isqrt_main']),
 'fft':('kernel',['fft.c','fft_input.c'],['fft_bit_reduct']),
 'ndes':('sequential',['ndes.c'],['ndes_des','ndes_cyfun','ndes_getbit','ndes_ks'])}
BOUNDARY=[0,1,2,3,4,15,16,17,65535,65536,0x7fffffff,0x80000000,0xffffffff,0x3fed0169,0x10000,0xffff0000]
BIT_BOUNDARY=[0,1,2,3,7,127,255,65535,0x55555555,0x7fffffff]
ADAPTERS={
'bitcount':'''#include "bitops.h"
extern unsigned long bitcount_n,bitcount_randseed,bitcount_seed;extern int bitcount_res;
extern int bitcount_bit_shifter(long);
unsigned external_snapshot(int32_t *v){v[0]=bitcount_n;v[1]=bitcount_res;v[2]=bitcount_randseed;v[3]=bitcount_seed;
 const unsigned long inputs[]={0,1,2,3,7,127,255,65535,0x55555555,0x7fffffff};
 for(unsigned a=0;a<8;a++){uint32_t h=2166136261u;for(unsigned i=0;i<10;i++){int n=0;long x=inputs[i];
 switch(a){case0:n=bitcount_bit_count(x);break;case1:n=bitcount_bitcount(x);break;case2:n=bitcount_ntbl_bitcnt(x);break;
 case3:n=bitcount_btbl_bitcnt(x);break;case4:n=bitcount_ntbl_bitcount(x);break;case5:n=bitcount_BW_btbl_bitcount(x);break;
 case6:n=bitcount_AR_btbl_bitcount(x);break;case7:n=bitcount_bit_shifter(x);break;}h=(h^(uint32_t)n)*16777619u;}v[4+a]=(int32_t)h;}return12;}'''.replace('case','case ').replace('return12','return 12'),
'isqrt':'''#include "snipmath.h"
extern unsigned long isqrt_checksum,isqrt_l;extern struct int_sqrt isqrt_q;extern void isqrt_usqrt(unsigned long,struct int_sqrt*);
unsigned external_snapshot(int32_t*v){v[0]=isqrt_checksum;v[1]=isqrt_q.sqrt;v[2]=isqrt_q.frac;v[3]=isqrt_l;
 const unsigned long inputs[]={0,1,2,3,4,15,16,17,65535,65536,0x7fffffff,0x80000000,0xffffffff,0x3fed0169,0x10000,0xffff0000};
 for(unsigned i=0;i<16;i++){struct int_sqrt q;isqrt_usqrt(inputs[i],&q);v[4+i]=(int32_t)((uint32_t)q.sqrt|((uint32_t)q.frac<<16));}return 20;}''',
'fft':'''extern int fft_input_data[2048];unsigned external_snapshot(int32_t*v){uint32_t h=2166136261u;for(unsigned i=0;i<2048;i++)h=(h^(uint32_t)fft_input_data[i])*16777619u;v[0]=(int32_t)h;for(unsigned i=0;i<8;i++){v[1+i]=fft_input_data[i];v[9+i]=fft_input_data[2040+i];}return 17;}''',
'ndes':'''struct NDES_IMMENSE{unsigned long l,r;};extern struct NDES_IMMENSE ndes_out,ndes_inp,ndes_key;unsigned external_snapshot(int32_t*v){v[0]=ndes_out.l;v[1]=ndes_out.r;v[2]=ndes_inp.l;v[3]=ndes_inp.r;v[4]=ndes_key.l;v[5]=ndes_key.r;return 6;}'''}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def signed(n):return n-(1<<32) if n>=1<<31 else n
def fnv(values):
 h=2166136261
 for n in values:h=((h^n)*16777619)&0xffffffff
 return signed(h)
def selected(s,n,allowed):return bool(s) and any(s==a or s.startswith(a+'.') for a in allowed)
def build(n,g,files,folder,opt):
 source=REF/'bench'/g/n;folder.mkdir(parents=True)
 adapter=folder/'snapshot.c';adapter.write_text('#include <stdint.h>\n'+ADAPTERS[n])
 common=['-march=rv32im','-mabi=ilp32',opt,'-std=gnu17','-Wno-unknown-pragmas','-I',str(source)]
 objects=[];commands=[]
 for p in [source/f for f in files]:
  obj=folder/(p.stem+'.o');args=[str(CC),*common,'-Dmain=tacle_original_main','-c',str(p),'-o',str(obj)]
  r,_=command(args,folder/(p.stem+'.build.log'),60);commands.append(r);objects.append(str(obj))
 args=[str(CC),*common,f'-DUPSTREAM_INIT={n}_init',f'-DUPSTREAM_RUN={n}_main',f'-DUPSTREAM_RETURN={n}_return',
 '-DANAGRAM_PHRASE=-1','-DPARTIAL_DIJKSTRA=0','-nostartfiles','-T',str(REPO/'src/spike-setup/memory-layout.ld'),
 str(REPO/'src/spike-setup/startup.S'),str(REPO/'benchmarks/embench-hooks.c'),str(REPO/'benchmarks/external-v5/runtime.c'),
 str(REPO/'benchmarks/external-v5/wrapper.c'),str(adapter),*objects,'-o',str(folder/(n+'.elf'))]
 r,_=command(args,folder/'link.log',60);commands.append(r)
 return folder/(n+'.elf'),{'commands':commands,'adapter_sha256':sha(adapter),'elf_sha256':sha(folder/(n+'.elf'))}
def output(text):
 rows=[json.loads(line) for line in text.splitlines() if line.startswith('{')]
 assert len(rows)==1 and rows[0]['kind']=='external-output' and rows[0]['upstream_status']==0
 return rows[0]['values']
def oracle(n,values):
 if n=='bitcount':
  seed=1;total=0;last=0
  for _ in range(8):
   seed=seed*16807%2147483647
   for j in range(10):last=(seed+j*13).bit_count();total+=last
  expected=[total,last,seed,seed+130]+[fnv([x.bit_count() for x in BIT_BOUNDARY])]*8
  assert values==expected,(n,values,expected)
  return {'independent':'Python integer Park-Miller +popcount, actualmeasuredaggregate/res/seed and8algorithms×10positivemasks probes','expected':expected,'probe_inputs':BIT_BOUNDARY,'scope':'Completeoriginalfixedinputaggregate plus outside-marker probes; not allinputsformalproof'}
 if n=='isqrt':
  x=0x3fed0169;word=math.isqrt(x<<32)
  expected=[sum(math.isqrt(y<<32)>>16 for y in [*range(1,1001),x]),word&65535,word>>16,x]+[signed(math.isqrt(y<<32)) for y in BOUNDARY]
  assert values==expected,(n,values,expected)
  return {'independent':'Pythonmath.isqrt exactinteger fixed-point/packedRV32word; capturedmeasuredfinalqbeforeprobes','expected':expected,'probe_inputs':BOUNDARY,'scope':'Original1001inputchecksum +actualfinalword +16outside-markerboundaryoutputs, not wholefunctionformalproof'}
 return {'independent_complete_oracle':False,'scope':'Upstreamselfcheck +capturedpost-measuredoutput; O0/O2exactoutputcontrol, doesNOTestablishindependentwholealgorithmoracle'}
if (OUT/'runtime-preflight.json').exists():raise ValueError('Existing runtimefeasibility evidence immutable')
records={};baseline_sources={}
for n,(g,files,allowed) in SPECS.items():
 folder=ROOT/n
 if folder.exists():raise ValueError('Existing familyattempt mustnot beoverwritten')
 r={'status':'pending','trace_deadline_seconds':300,'max_candidate_ops':4,'upstream_algorithm_changes':False,'protocol_sealed':False,'kernel_symbols':allowed}
 try:
  source=REF/'bench'/g/n;r['upstream_source_sha256']={str(p.relative_to(REF)):sha(p) for p in source.iterdir() if p.is_file()}
  elf,build_record=build(n,g,files,folder/'O2','-O2');r['build']=build_record
  control,control_record=build(n,g,files,folder/'O0','-O0');r['control_build']=control_record
  _,o2=command([str(SPIKE),'--isa=rv32im_zicntr','-m16',str(elf)],folder/'O2-selfcheck.log',60)
  _,o0=command([str(SPIKE),'--isa=rv32im_zicntr','-m16',str(control)],folder/'O0-selfcheck.log',60)
  v2=output(o2);v0=output(o0);assert v2==v0,(n,v2,v0)
  r['captured_outputs']=v2;r['O0_O2_output_identical']=True;r['oracle']=oracle(n,v2)
  summary,runs,starts=collect_trace_external(str(SPIKE),elf,folder/(n+'.jsonl.gz'),folder/'trace.log',300);r['trace']=summary
  traced_output=output(Path(summary['program_output']).read_text());assert traced_output==v2
  program=readProgram(elf,str(OBJDUMP));previous=None;boundaries=set(starts)
  for pc in sorted(program):
   symbol=program[pc].get('symbol')
   if symbol!=previous:boundaries.add(pc)
   previous=symbol
  scoped=Counter({pc:count for pc,count in runs.items() if selected(program[pc].get('symbol'),n,allowed)})
  candidates=extractCandidates(program,scoped,boundaries,maxSize=4,limit=None)
  cdir=folder/'candidates';cdir.mkdir();write(cdir/(n+'.json'),candidates)
  pdir=folder/'programs';pdir.mkdir();os.link(elf,pdir/(n+'.elf'))
  verification=verify_candidates(cdir,pdir,str(OBJDUMP),vectors=16,seed=2026101507)
  r['fusion_verification']=verification
  assert verification['verified'] and verification['skipped_opaque_occurrences']==0
  write(folder/'fusion.json',verification)
  r.update(status='complete-input-feasibility',candidate_count=len(candidates),kernel_retired_instructions=sum(scoped.values()),
    all_measured_retired_instructions=sum(runs.values()),candidate_sha256=sha(cdir/(n+'.json')))
 except Exception as error:r.update(status='failure-retained',error=repr(error))
 records[n]=r;write(OUT/'runtime-progress.json',records)
 print(n,r['status'],r.get('candidate_count'),r.get('error'),flush=True)
write(OUT/'runtime-preflight.json',{'status':'unsealed-input-feasibility','script_sha256':sha(__file__),'records':records,
 'source_reference_commit':'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08','no_target_labels_models_fits_protocol_seal':True,
 'compiler_sha256':sha(CC),'objdump_sha256':sha(OBJDUMP),'spike_sha256':sha(SPIKE),
 'frozen_helpers_sha256':{str(p.relative_to(REPO)):sha(p) for p in [REPO/'scripts/collect_external_v5.py',REPO/'src/candidates.py',REPO/'src/tracing.py',REPO/'src/verify_candidate_fusions.py',REPO/'benchmarks/external-v5/wrapper.c',REPO/'benchmarks/external-v5/runtime.c']},
 'limits':'Inputfeasibility, not application performance/FPGA mapping. Allfullupstream_main windows retained; helpers excluded onlyviafixedkernelsymbolfilter; no candidatecap ormodelranking. Fusion is sampledarchitecturalstatecomparison, notformalCPUcorrectness. Probeoraclechecks outsidewindow distinctlyattributed.'})

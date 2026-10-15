"""Parent-approved bounded video input feasibility; no labels/models/protocol seal."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,sys
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench';ROOT=REPO/'generated/application-input-feasibility'
sys.path[:0]=[str(REPO),str(REPO/'scripts'),str(REPO/'src')]
from collect_external_v5 import command,collect_trace_external
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates
TOOL=OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin';CC=TOOL/'riscv-none-elf-gcc';OBJDUMP=TOOL/'riscv-none-elf-objdump';SPIKE=OUT.parent/'toolchains/spike/bin/spike'
SPECS={'mpeg2':(['mpeg2.c'],['mpeg2_']), 'h264_dec':(['h264_dec.c','h264_decinput.c'],['h264_dec_decode_one_macroblock'])}
ADAPTERS={'mpeg2':'''extern int mpeg2_return(void);int feasibility_status(void){return mpeg2_return()!=-116;}unsigned external_snapshot(int32_t*v){v[0]=mpeg2_return();return 1;}''',
'h264_dec':'''extern signed char h264_dec_img_mpr[7][7],h264_dec_dec_picture_imgUV[2][64][54];unsigned external_snapshot(int32_t*v){uint32_t a=2166136261u,b=a;for(unsigned i=0;i<49;i++)a=(a^(uint8_t)((signed char*)h264_dec_img_mpr)[i])*16777619u;for(unsigned i=0;i<6912;i++)b=(b^(uint8_t)((signed char*)h264_dec_dec_picture_imgUV)[i])*16777619u;v[0]=(int32_t)a;v[1]=(int32_t)b;v[2]=h264_dec_img_mpr[0][0];v[3]=h264_dec_dec_picture_imgUV[0][0][0];return 4;}'''}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def output(text):
 rows=[json.loads(x) for x in text.splitlines() if x.startswith('{')];assert len(rows)==1 and rows[0]['upstream_status']==0;return rows[0]['values']
def selected(s,n,allowed):return bool(s) and any(s==a or s.startswith(a+'.') or (a.endswith('_') and s.startswith(a)) for a in allowed) and s not in {n+'_init',n+'_return',n+'_main'}
def build(n,files,folder,opt):
 folder.mkdir(parents=True);source=REF/'bench/sequential'/n;adapter=folder/'snapshot.c';adapter.write_text('#include <stdint.h>\n'+ADAPTERS[n])
 flags=['-march=rv32im','-mabi=ilp32',opt,'-std=gnu17','-Wno-unknown-pragmas','-I',str(source)];objects=[];commands=[]
 for filename in files:
  p=source/filename;obj=folder/(p.stem+'.o');args=[str(CC),*flags,'-Dmain=tacle_original_main','-c',str(p),'-o',str(obj)];r,_=command(args,folder/(p.stem+'.build.log'),60);commands.append(r);objects.append(str(obj))
 status='feasibility_status' if n=='mpeg2' else n+'_return'
 args=[str(CC),*flags,f'-DUPSTREAM_INIT={n}_init',f'-DUPSTREAM_RUN={n}_main',f'-DUPSTREAM_RETURN={status}','-DANAGRAM_PHRASE=-1','-DPARTIAL_DIJKSTRA=0','-nostartfiles','-T',str(REPO/'src/spike-setup/memory-layout.ld'),str(REPO/'src/spike-setup/startup.S'),str(REPO/'benchmarks/embench-hooks.c'),str(REPO/'benchmarks/external-v5/runtime.c'),str(REPO/'benchmarks/external-v5/wrapper.c'),str(adapter),*objects,'-o',str(folder/(n+'.elf'))]
 r,_=command(args,folder/'link.log',60);commands.append(r)
 return folder/(n+'.elf'),{'commands':commands,'adapter_sha256':sha(adapter),'elf_sha256':sha(folder/(n+'.elf'))}
if (OUT/'video-runtime-feasibility.json').exists():raise ValueError('Existing evidence immutable')
write(OUT/'mpeg2-wrapper-compatibility.json',{'status':'generic-status-contract-incompatibility-detected-before-execution','program_executed_under_bad_contract':False,'original_main_selfcheck':'return(mpeg2_return()-(-116)!=0);','problem':'ExistinggenericwrapperexpectsUPSTREAM_RETURN()==0 but MPEG2returnisrawchecksum-116.','parent_approved_adapter':'feasibility_status returns(mpeg2_return()!=-116); captureoriginalrawchecksum; noupstreamalgorithm/inputchange','source':'bench/sequential/mpeg2/mpeg2.c:13211'})
records={}
for n,(files,allowed) in SPECS.items():
 folder=ROOT/n
 if folder.exists():raise ValueError('Family attempt immutable')
 r={'status':'pending','trace_deadline_seconds':300,'scope':'Complete declared '+n+'_main computation; init/selfcheck/outputprobes excluded; allcalledhelpersretained inallROI','kernel_symbols':allowed}
 try:
  source=REF/'bench/sequential'/n;before={str(p.relative_to(REF)):sha(p) for p in source.iterdir() if p.is_file()};r['upstream_source_sha256']=before
  elf,b=build(n,files,folder/'O2','-O2');r['build']=b;control,b=build(n,files,folder/'O0','-O0');r['control_build']=b
  _,text=command([str(SPIKE),'--isa=rv32im_zicntr','-m16',str(elf)],folder/'O2-selfcheck.log',60);actual=output(text)
  _,text=command([str(SPIKE),'--isa=rv32im_zicntr','-m16',str(control)],folder/'O0-selfcheck.log',60);assert actual==output(text)
  if n=='mpeg2':assert actual==[-116]
  r['captured_outputs']=actual;r['O0_O2_output_identical']=True;r['independent_complete_algorithm_oracle']=False
  summary,runs,starts=collect_trace_external(str(SPIKE),elf,folder/(n+'.jsonl.gz'),folder/'trace.log',300);r['trace']=summary
  assert actual==output(Path(summary['program_output']).read_text())
  program=readProgram(elf,str(OBJDUMP));previous=None
  for pc in sorted(program):
   symbol=program[pc].get('symbol')
   if symbol!=previous:starts.add(pc)
   previous=symbol
  scoped=Counter({pc:count for pc,count in runs.items() if selected(program[pc].get('symbol'),n,allowed)})
  r['all_roi_candidate_count']=None
  pdir=folder/'programs';pdir.mkdir();os.link(elf,pdir/(n+'.elf'))
  for scope,counts in [('all-roi',runs),('kernel',scoped)]:
   candidates=extractCandidates(program,counts,starts,maxSize=4,limit=None);cdir=folder/('candidates-'+scope);cdir.mkdir();write(cdir/(n+'.json'),candidates)
   verification=verify_candidates(cdir,pdir,str(OBJDUMP),vectors=16,seed=2026101507);write(folder/('fusion-'+scope+'.json'),verification)
   assert verification['passed'] and all(x['skipped_opaque_block_occurrences']==0 for x in verification['benchmarks'])
   r[scope]={'candidate_count':len(candidates),'retired_instructions':sum(counts.values()),'candidate_sha256':sha(cdir/(n+'.json')),'fusion_verification':verification}
  assert before=={str(p.relative_to(REF)):sha(p) for p in source.iterdir() if p.is_file()}
  r['status']='complete-input-feasibility'
 except Exception as error:r.update(status='failure-retained',error=repr(error))
 records[n]=r;write(OUT/'video-runtime-progress.json',records);print(n,r['status'],r.get('all-roi',{}).get('candidate_count'),r.get('error'),flush=True)
write(OUT/'video-runtime-feasibility.json',{'status':'unsealed-input-feasibility','script_sha256':sha(__file__),'records':records,'no_target_labels_models_fits_protocol_seal':True,'source_reference_commit':'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08','limits':'Video kernels, not completevideo codecs/applications; oneconservativevideo family. Noindependentcompletealgorithmoracle, norewrittenalgorithm, no targetmapping/performanceclaims. Thin MPEGstatusadapterexactlymatchesupstreammain declaredselfcheck.'})

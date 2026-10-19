"""Unsealed input-feasibility only: compile, disassemble, static legality; no execution/labels."""
from pathlib import Path
import collections,hashlib,json,os,signal,subprocess,sys,time
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench'
sys.path[:0]=[str(REPO/'src'),str(REPO)]
from candidates import readProgram,extractCandidates,ELIGIBLE
from isaforge.features import parse_formula
TOOL=OUT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin';CC=TOOL/'riscv-none-elf-gcc';OBJDUMP=TOOL/'riscv-none-elf-objdump';SIZE=TOOL/'riscv-none-elf-size'
SPECS={
 'bitcount':('kernel',['bitcount.c','bitcnt_1.c','bitcnt_2.c','bitcnt_3.c','bitcnt_4.c'],['bitcount_bit_count','bitcount_bitcount','bitcount_bit_shifter','bitcount_ntbl_bitcnt','bitcount_btbl_bitcnt','bitcount_ntbl_bitcount','bitcount_BW_btbl_bitcount','bitcount_AR_btbl_bitcount']),
 'isqrt':('kernel',['isqrt.c','basicmath_libc.c'],['isqrt_usqrt','isqrt_main']),
 'fft':('kernel',['fft.c','fft_input.c'],['fft_bit_reduct']),
 'ndes':('sequential',['ndes.c'],['ndes_des','ndes_cyfun','ndes_getbit','ndes_ks']),
 'mpeg2':('sequential',['mpeg2.c'],['mpeg2_']),
 'h264_dec':('sequential',['h264_dec.c','h264_decinput.c'],['h264_dec_decode_one_macroblock']),
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def run(command,folder,name,timeout=60):
 with (folder/(name+'.log')).open('wb') as log:
  p=subprocess.Popen([str(c) for c in command],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=p.wait(timeout=timeout)
  finally:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   p.wait()
 if code:raise ValueError(name+' failed')
def selected(symbol,name,allowed):
 return bool(symbol) and any(symbol==x or symbol.startswith(x+'.') or (x.endswith('_') and symbol.startswith(x)) for x in allowed) and symbol not in {name+'_init',name+'_return',name+'_main'}
def matches(node):
 counts=collections.Counter()
 def literal(n):return isinstance(n.value,int) and not n.children
 def masked(n,ops):
  if n.children and n.value in ops:
   a,b=n.children
   if literal(b):return a
   if literal(a):return b
  return None
 if node.value=='sub':
  a,b=node.children
  if masked(a,('or','ori'))==b:counts['or_sub_exact']+=1
  if masked(b,('and','andi'))==a:counts['sub_and_exact']+=1
 if node.value in ('mulh','mulhu','mulhsu'):counts[str(node.value)]+=1
 for c in node.children:counts.update(matches(c))
 return counts
if (OUT/'static-preflight.json').exists():raise ValueError('Existing exploratory evidence immutable')
flags=['-march=rv32im','-mabi=ilp32','-O2','-std=gnu17','-Wno-unknown-pragmas','-nostartfiles','-Wl,-e,main']
records={}
for name,(group,files,allowed) in SPECS.items():
 source=REF/'bench'/group/name;folder=OUT/('static-'+name);folder.mkdir()
 inputs=[source/f for f in files];all_inputs=[p for p in source.iterdir() if p.is_file()]
 before={str(p.relative_to(REF)):sha(p) for p in all_inputs}
 record={'source_sha256':before,'source_files':[str(p.relative_to(REF)) for p in inputs], 'kernel_symbol_filter':allowed,'source_binary_executed':False,'dynamic_trace_collected':False}
 try:
  command=[CC,*flags,'-I',source,*inputs,'-o',folder/(name+'.elf')];record['compile_command']=[str(c) for c in command]
  run(command,folder,'build');elf=folder/(name+'.elf');record['elf_sha256']=sha(elf)
  program=readProgram(elf,str(OBJDUMP));starts={pc for pc,r in program.items() if pc==min(p for p,v in program.items() if v.get('symbol')==r.get('symbol'))}
  patterns=extractCandidates(program,collections.Counter({pc:1 for pc in program}),starts,maxSize=4,limit=None)
  kept=[]
  for p in patterns:
   occurrences=[o for o in p['occurrences'] if all(selected(s,name,allowed) for s in o['symbols'])]
   if occurrences:
    kept.append({'formula':p['formula'],'sizes':p['sizeVariants'],'static_occurrences':len(occurrences),'kernel_symbols':sorted({s for o in occurrences for s in o['symbols']})})
  opcounts=collections.Counter(r['op'] for r in program.values() if selected(r.get('symbol'),name,allowed))
  mechanism=collections.Counter()
  for p in kept:mechanism.update(matches(parse_formula(p['formula'])))
  record.update({'status':'compiled-static-legality-only','all_program_static_unique_formulas':len(patterns),'kernel_static_unique_formulas':len(kept),
    'kernel_instruction_opcodes':dict(opcounts),'kernel_eligible_static_instructions':sum(n for op,n in opcounts.items() if op in ELIGIBLE),
    'mechanism_formula_counts':dict(mechanism),'kernel_static_formulas':kept})
  record['size_output']=subprocess.check_output([str(SIZE),str(elf)],text=True)
 except Exception as error:record.update({'status':'failure','error':str(error)})
 assert before=={str(p.relative_to(REF)):sha(p) for p in all_inputs}
 records[name]=record;write(OUT/'static-progress.json',records)
 print(name,record['status'],record.get('kernel_static_unique_formulas'),record.get('mechanism_formula_counts'),flush=True)
write(OUT/'static-preflight.json',{'status':'exploratory-input-feasibility-not-sealed','reference_commit':subprocess.check_output(['git','-C',str(REF),'rev-parse','HEAD'],text=True).strip(),
 'compiler_sha256':sha(CC),'objdump_sha256':sha(OBJDUMP),'compiler_version':subprocess.check_output([str(CC),'--version'],text=True).splitlines()[0],
 'extractor_sha256':sha(REPO/'src/candidates.py'),'decoder_sha256':sha(REPO/'src/tracing.py'),'script_sha256':sha(__file__),
 'records':records,'limits':'No program execution, trace, occurrence frequency, input correctness, targetmapping/labels or model prediction. Unit-weight staticblocks only test existing legality; no savings from syntheticweights retained. Helper/init exclusions are declared above; unusedcode mayremain. No family assignment issealed.'})

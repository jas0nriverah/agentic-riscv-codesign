#!/usr/bin/env python3
"""Input-only, full-ROI collection for the prospectively reserved six programs.

No model, ML feature extractor, area mapper or target label is used. Every
program attempt remains visible, including failures and empty candidate pools.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
from collect_external_v5 import command, collect_trace_external
from candidates import readProgram, extractCandidates
from verify_candidate_fusions import verify_candidates

PIN = 'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
RESERVATION_COMMIT = 'b6f1549'
SPECS = {
    'ammunition': ('sequential', 'arbitrary-precision-bit-strings', ('ammunition.c', 'ammunition_libc.c', 'arithm.c', 'bits.c')),
    'audiobeam': ('sequential', 'audio-beamforming', ('audiobeam.c', 'audiobeaminput.c', 'audiobeamlibm.c', 'audiobeamlibmalloc.c')),
    'pm': ('kernel', 'numeric-template-matching', ('pm.c', 'pm_input.c', 'pm_libm.c', 'pm_stdlib.c')),
    'fmref': ('sequential', 'fm-reception', ('fmref.c', 'wcclibm.c')),
    'fac': ('kernel', 'integer-recurrences', ('fac.c',)),
    'recursion': ('kernel', 'integer-recurrences', ('recursion.c',)),
}
MAIN_SHA = dict(zip(SPECS, (
    '91275ca49deabae23b979ee2e8b72d6d8089d66df68992485f33b1abc26ff1ba',
    '932d0a606e9acbb23dd29295825b276a39e35989fa9cce5f1cb6e6ae9767f4ad',
    '956e60a5a93e2e057df3c0a0c56e648bd10c1c08942411e7af05264ac84f5f70',
    '5a64ade837ad3e059a851f47385e5db4b514f4e21432f464f5f721d71b55356d',
    'bec4ca75a8653b5893cf0c47d0abdd82181f7d54e80750f7d904edacec7f4d40',
    'de88f42686816d10ded0ccc9f06c549d563284927732107d17ec12e2cc0ba1df')))
PREAMBLE = '''#include <stdint.h>
static int32_t word(float x) { union {float f; int32_t i;} u={.f=x};return u.i; }
static uint32_t digest(const void *p,unsigned n) {
 const unsigned char *s=p;uint32_t h=2166136261u;
 for(unsigned i=0;i<n;i++) h=(h^s[i])*16777619u;return h;
}
'''


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def now(): return datetime.now(timezone.utc).isoformat()
def f32(x): return struct.unpack('<f', struct.pack('<f', x))[0]
def bits_float(x): return struct.unpack('<f', struct.pack('<I', x & 0xffffffff))[0]
def signed(x): return x - (1 << 32) if x >= (1 << 31) else x


def array_values(path, name, expected):
    """Read only a declared C numeric initializer, reject missing/extra values."""
    text = Path(path).read_text()
    match = re.search(r'\b' + re.escape(name) + r'\s*(?:\[[^\]]*\]\s*)+=\s*\{', text)
    if not match: raise ValueError('Missing source initializer: ' + name)
    tail = text[match.end():]; body = tail[:tail.index('};')]
    body = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S)
    tokens = re.findall(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?[fF]?', body)
    values = [f32(float(t.rstrip('fF'))) for t in tokens]
    if len(values) != expected: raise ValueError('Unexpected initializer length: ' + name)
    return values


def adapters(name):
    """Snapshot code runs only after stop_trigger; upstream C bytes unchanged.

    PM includes its original translation unit to observe private result arrays.
    Audiobeam's malloc TU gets a separate read-only getter after its unchanged
    source, so the measured main TU does not gain allocator visibility/inlining.
    """
    if name == 'ammunition':
        body = '''#include "arithm.h"
#include "bits.h"
extern int ammunition_result;
unsigned external_snapshot(int32_t*v) {
 v[0]=ammunition_result;v[1]=ammunition_overflow_bit;
 unsigned char a[4]={0x7f,0xff,0xff,0xff},b[4]={0,0,0,2},r[4],s[8]={0};
 ammunition_multiply_unsigned_integer(4,a,b,r);
 for(unsigned i=0;i<4;i++)v[2+i]=r[i];v[6]=ammunition_overflow_bit;
 ammunition_bit_string_set(s,13,1,35);
 for(unsigned i=0;i<8;i++)v[7+i]=s[i];return 15;
}'''
    elif name == 'audiobeam':
        body = '''extern int audiobeam_checksum,audiobeam_input_pos;
extern unsigned v11_audio_heap_snapshot(int32_t*);
unsigned external_snapshot(int32_t*v) {
 v[0]=audiobeam_checksum;v[1]=audiobeam_input_pos;
 return 2+v11_audio_heap_snapshot(v+2);
}'''
        heap = PREAMBLE + '''#include "audiobeamlibmalloc.c"
unsigned v11_audio_heap_snapshot(int32_t*v) {
 /* Original ILP32 allocator: delays8->12, ptr4->8, values60->64,
    beam pointer4->8, then384 floats. Output starts at byte92. */
 float *out=(float*)(audiobeam_simulated_heap+92);
 v[0]=audiobeam_freeHeapPos;v[1]=(int32_t)digest(out,384*4);
 for(unsigned i=0;i<16;i++)v[2+i]=word(out[i]);
 unsigned finite=0;for(unsigned i=0;i<371;i++)
  finite+=(((uint32_t)word(out[i])&0x7f800000u)!=0x7f800000u);
 v[18]=finite;return 19;
}'''
        return PREAMBLE + body, heap
    elif name == 'pm':
        body = '''#define main tacle_original_main
#include "pm.c"
#undef main
unsigned external_snapshot(int32_t*v) {
 v[0]=pm_result;v[1]=pm_data.profile_size;v[2]=pm_data.num_templates;
 unsigned bad=0;int argmin=0;
 for(unsigned i=0;i<60;i++) {
  uint32_t b=(uint32_t)word(pm_init_array_7[i]);
  bad+=((b&0x7f800000u)==0x7f800000u || pm_init_array_7[i]<0);
  if(pm_init_array_7[i]<pm_init_array_7[argmin])argmin=i;
 }
 v[3]=argmin;v[4]=bad;v[5]=(int32_t)digest(pm_init_array_7,60*4);
 const unsigned ix[]={0,1,2,10,11,12,13,59};
 for(unsigned i=0;i<8;i++)v[6+i]=word(pm_init_array_7[ix[i]]);
 return 14;
}'''
    elif name == 'fmref':
        body = '''#define main tacle_original_main
#include "fmref.c"
#undef main
unsigned external_snapshot(int32_t*v) {
 FloatBuffer *bs[]={&fmref_fb1,&fmref_fb2,&fmref_fb3,&fmref_fb4};
 for(unsigned i=0;i<4;i++){v[2*i]=bs[i]->rpos;v[2*i+1]=bs[i]->rlen;
  v[9+i]=(int32_t)digest(bs[i]->buff,800);}
 v[8]=fmref_numiters;
 for(unsigned i=0;i<8;i++)v[13+i]=word(fmref_lpf_data.coeff[i]);
 for(unsigned i=0;i<2;i++) {v[21+i]=word(fmref_fb4.buff[i]);
  v[23+i]=word(fmref_fb2.buff[i]);v[25+i]=word(fmref_fb3.buff[i]);}
 return 27;
}'''
    elif name == 'fac':
        body = '''extern int fac_s;extern volatile int fac_n;
unsigned external_snapshot(int32_t*v){v[0]=fac_s;v[1]=fac_n;return 2;}'''
    elif name == 'recursion':
        body = '''extern int recursion_result,recursion_input;
unsigned external_snapshot(int32_t*v){v[0]=recursion_result;v[1]=recursion_input;return 2;}'''
    else: raise ValueError('Not a reserved program')
    return PREAMBLE + body, None


def audio_oracle(source):
    """Independent binary32 delay/interpolation/weight simulation of fixed input."""
    values = array_values(source / 'audiobeaminput.c', 'audiobeam_input', 5760)
    xyz = array_values(source / 'audiobeaminput.c', 'audiobeam_mic_locations', 45)
    target = array_values(source / 'audiobeaminput.c', 'audiobeam_source_location', 3)
    distances = []
    for m in range(15):
        d = [f32(xyz[3*m+j] - target[j]) for j in range(3)]
        square = f32(f32(f32(d[0]*d[0]) + f32(d[1]*d[1])) + f32(d[2]*d[2]))
        distances.append(f32(math.sqrt(square)))
    delays = [f32(f32(x / f32(342)) * f32(16000)) for x in distances]
    minimum = math.floor(min(delays)) - 1
    delays = [f32(x - minimum) for x in delays]
    maximum = math.ceil(max(delays))
    weights = [f32(0.54 + 0.46 * f32(math.cos(f32(math.pi*y/7)))) for y in range(-7, 8)]
    queue = [[0.0]*15 for _ in range(maximum+1)]; head=0; pos=0
    def fill():
        nonlocal pos, head
        queue[head] = values[pos:pos+15]; pos += 15
    for _ in range(maximum-1): fill(); head=(head+1)%(maximum+1)
    out=[]
    while pos < len(values):
        fill(); total=f32(0); readhead=(head+1)%(maximum+1)
        for m,delay in enumerate(delays):
            lo=math.floor(delay); hi=math.ceil(delay); offset=f32(delay-lo)
            low=queue[(readhead+lo)%(maximum+1)][m]
            high=queue[(readhead+hi)%(maximum+1)][m]
            interpolated=f32(f32(f32(high-low)*offset)+low)
            total=f32(total+f32(interpolated*weights[m]))
        out.append(f32(total/f32(15))); head=(head+1)%(maximum+1)
    return {'outputs':out,'input_position':pos,'maximum_delay':maximum,
            'checksum':int(f32(out[0]*f32(1000)))}


class FloatBuffer:
    def __init__(self): self.data=bytearray(800); self.pos=0; self.length=0
    def get(self,i): return struct.unpack_from('<f',self.data,i*4)[0]
    def put(self,i,x): struct.pack_into('<f',self.data,i*4,f32(x))
    def compact(self):
        # Preserve upstream's byte-count copy, not an idealized float memmove.
        count=self.length-self.pos
        self.data[:count]=self.data[4*self.pos:4*self.pos+count]
        self.length-=self.pos; self.pos=0
    def append(self,x):
        if self.length==200:self.compact()
        self.put(self.length,x);self.length+=1


def fm_oracle(source):
    """Independent source-contract pipeline, binary32 arithmetic + host libm.

    Transcendentals are approximations to the pinned software libm; explicit
    numeric bounds are checked, while O0/O2 and trace snapshots must be bit exact.
    """
    cutoffs=array_values(source/'fmref.c','fmref_eq_cutoffs',11)
    def coeff(freq):
        w=f32(2*math.pi*freq/250000000)
        out=[]
        for i in range(64):
            delta=f32(i-f32(63/2)); angle=f32(w*delta)
            cosine=f32(math.cos(f32(2*math.pi*i/63)))
            window=f32(f32(.54)-f32(f32(.46)*cosine))
            out.append(f32(f32(math.sin(angle))/math.pi/delta*window))
        return out
    primary=coeff(f32(108000000)); eq=[coeff(x) for x in cutoffs]
    b1,b2,b3,b4=[FloatBuffer() for _ in range(4)]; x=0
    def fill():
        nonlocal x
        b1.compact()
        while b1.length<200:b1.append(x);x+=1
    def lpf(inp,out,cs,dec):
        total=f32(0)
        for i,c in enumerate(cs):total=f32(total+f32(inp.get(inp.pos+i)*c))
        inp.pos+=dec+1;out.append(total)
    gain=f32(27000*250000000/(10000*math.pi))
    def demod():
        temp=f32(b2.get(b2.pos)*b2.get(b2.pos+1)); b2.pos+=1
        b3.append(f32(gain*f32(math.atan(temp))))
    fill();lpf(b1,b2,primary,4)
    for _ in range(64):
        if b1.length-b1.pos<65:fill()
        lpf(b1,b2,primary,4);demod()
    for _ in range(2):
        if b1.length-b1.pos<65:fill()
        lpf(b1,b2,primary,4);demod();start=b3.pos;total=f32(0);lowpass=[]
        for cs in eq:
            b3.pos=start;temp=FloatBuffer();lpf(b3,temp,cs,0);lowpass.append(temp.get(0))
        for i in range(10):
            val=f32(f32(i-f32(9/2))/f32(5)); weight=f32(2-abs(val))
            total=f32(total+f32(f32(lowpass[i+1]-lowpass[i])*weight))
        b4.append(total)
    return {'positions':[v for b in (b1,b2,b3,b4) for v in (b.pos,b.length)]+[-1],
            'samples':primary[:8]+[b4.get(i) for i in range(2)]+[b2.get(i) for i in range(2)]+[b3.get(i) for i in range(2)],
            'transcendental_policy':{'relative':1e-4,'absolute':1e-6,
              'scope':'numeric snapshots only; all O0/O2/trace words and full buffer hashes exact'}}


def validate_output(name, values, source):
    if not isinstance(values,list) or any(type(x) is not int or not -(1<<31)<=x<(1<<31) for x in values):
        raise ValueError('Invalid signed32 snapshot')
    report={'name':name,'snapshot':values,'full_algorithm_independent_oracle':False}
    if name=='fac':
        expected=[sum(math.factorial(i) for i in range(6)),5]
        if values!=expected:raise ValueError('Factorial oracle mismatch')
        report.update(full_algorithm_independent_oracle=True,expected=expected)
    elif name=='recursion':
        a=b=1
        for _ in range(10):a,b=b,a+b
        if values!=[a,10]:raise ValueError('Fibonacci oracle mismatch')
        report.update(full_algorithm_independent_oracle=True,expected=[a,10])
    elif name=='ammunition':
        bitstring=((1<<35)-1) << (64-13-35)
        expected=[0,None,255,255,255,254,0,*bitstring.to_bytes(8,'big')]
        if len(values)!=15 or values[0]!=0 or values[1] not in (0,1) or values[2:]!=expected[2:]:
            raise ValueError('AMMUNITION selfcheck/integer/bit-string oracle mismatch')
        report.update(expected=expected,scope='Original aggregate selfcheck; independent postmarker unsigned-product/bit-string probes, not whole package proof')
    elif name=='pm':
        if len(values)!=14 or values[:5]!=[12,64,60,12,0]:raise ValueError('Pattern matching selfcheck/score invariants mismatch')
        scores=[bits_float(x) for x in values[6:]]
        if not all(math.isfinite(x) and x>=0 for x in scores) or scores[5]>min(scores):
            raise ValueError('Pattern matching captured score ordering mismatch')
        report.update(scope='Original expected match12 plus all60 score finite/nonnegative/argmin invariants and full-array digest; no independent complete HPEC implementation')
    elif name=='audiobeam':
        expected=audio_oracle(source)
        if len(values)!=21 or values[0]!=expected['checksum'] or values[1]!=5760 or values[20]!=len(expected['outputs']):
            raise ValueError('Beamforming selfcheck/output-count mismatch')
        observed=[bits_float(x) for x in values[4:20]]
        errors=[abs(a-b) for a,b in zip(observed,expected['outputs'][:16])]
        if any(not math.isfinite(a) or not math.isclose(a,b,rel_tol=1e-4,abs_tol=1e-7) for a,b in zip(observed,expected['outputs'][:16])):
            raise ValueError('Independent beamforming numeric oracle mismatch')
        report.update(independent_first16=expected['outputs'][:16],max_first16_abs_error=max(errors),
                      numeric_policy={'relative':1e-4,'absolute':1e-7},scope='Independent binary32 geometry/interpolation/Hamming first16 outputs; full384 buffer digest exact O0/O2, all371 actual outputs finite')
    elif name=='fmref':
        expected=fm_oracle(source)
        if len(values)!=27 or values[:9]!=expected['positions']:raise ValueError('FM buffer progress oracle mismatch')
        observed=[bits_float(x) for x in values[13:]]
        if any(not math.isfinite(a) or not math.isclose(a,b,rel_tol=1e-4,abs_tol=1e-6) for a,b in zip(observed,expected['samples'])):
            raise ValueError('Independent FM numeric oracle mismatch')
        if not all(abs(bits_float(x))>1e-6 for x in values[21:23]):raise ValueError('FM produced null outputs')
        report.update(independent_numeric_snapshots=expected,scope='Independent binary32 FM pipeline retaining upstream byte compaction; approximate host transcendental math, not bitexact full algorithm proof')
    else:raise ValueError('Not reserved')
    return report


def output(text):
    rows=[json.loads(x) for x in text.splitlines() if x.startswith('{')]
    if len(rows)!=1 or rows[0].get('kind')!='external-output' or rows[0].get('upstream_status')!=0:
        raise ValueError('Missing/duplicate/failed upstream output')
    return rows[0]['values']


def inventory(folder):
    return [{'path':str(p.relative_to(folder)),'sha256':sha(p),'bytes':p.stat().st_size}
            for p in sorted(folder.rglob('*')) if p.is_file()]


def create_plan(reference, tools):
    pin=subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()
    if pin!=PIN:raise ValueError('Wrong TACLe source commit')
    reserved=ROOT/'docs/v9-reserved-transfer-direction.md'
    committed=subprocess.check_output(['git','-C',str(ROOT),'show',RESERVATION_COMMIT+':docs/v9-reserved-transfer-direction.md'])
    if hashlib.sha256(committed).hexdigest()!=sha(reserved):raise ValueError('Reserved plan differs from pre-trace commit')
    v8=read(ROOT/'benchmarks/application-v8/cohort-preflight.json')
    for name,p in tools.items():
        if sha(p)!=v8['tools'][name]['sha256']:raise ValueError('Changed pinned tool: '+name)
    records={}
    for name,(group,family,files) in SPECS.items():
        directory=reference/'bench'/group/name
        if sha(directory/(name+'.c'))!=MAIN_SHA[name]:raise ValueError('Changed reserved main source')
        tracked=subprocess.check_output(['git','-C',str(reference),'ls-tree','-r','--name-only',PIN,'--',str(directory.relative_to(reference))],text=True).splitlines()
        actual=[str(p.relative_to(reference)) for p in sorted(directory.rglob('*')) if p.is_file()]
        if sorted(tracked)!=actual:raise ValueError('Missing/extra reserved source/input file')
        for path in actual:
            original=subprocess.check_output(['git','-C',str(reference),'show',PIN+':'+path])
            if hashlib.sha256(original).hexdigest()!=sha(reference/path):raise ValueError('Dirty pinned source: '+path)
        records[name]={'family':family,'directory':str(directory.relative_to(reference)),
                       'compiled_c_files':list(files),'files':{p:sha(reference/p) for p in actual}}
    dependencies=set(v8['runtime_dependencies'])
    dependencies.update(['scripts/collect_v11_reserved.py','tests/test_collect_v11_reserved.py','docs/v9-reserved-transfer-direction.md','scripts/collect_external_v5.py'])
    return {'schema':'isaforge-v11-reserved-input-plan-v1','prepared_at_utc':now(),
            'reservation_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse',RESERVATION_COMMIT],text=True).strip(),
            'upstream_commit':pin,'programs':records,'tools':{n:{'path':str(p),'sha256':sha(p)} for n,p in tools.items()},
            'runtime_source_sha256':{p:sha(ROOT/p) for p in sorted(dependencies)},
            'limits':{'build_seconds':60,'selfcheck_seconds':60,'trace_seconds':300,'maxSize':4,'limit':None,'fusion_vectors':16,'fusion_seed':2026101507},
            'pool':'Every eligible canonical original formula in complete computation ROI, including called helpers; no ranking/cuts/replacements',
            'no_models_features_area_labels_fits':True}


def authenticate(plan, reference):
    if tuple(plan['programs'])!=tuple(SPECS):raise ValueError('Reserved cohort/order changed')
    for name, record in plan['programs'].items():
        group,family,files=SPECS[name]
        if record['family']!=family or record['directory']!='bench/'+group+'/'+name or record['compiled_c_files']!=list(files):
            raise ValueError('Changed reserved family/source contract')
        actual={str(p.relative_to(reference)):sha(p) for p in sorted((reference/record['directory']).rglob('*')) if p.is_file()}
        if actual!=record['files']:raise ValueError('Changed/extra/missing source input')
    for name,digest in plan['runtime_source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Changed collector/runtime source')
    for r in plan['tools'].values():
        if sha(r['path'])!=r['sha256']:raise ValueError('Changed executable')


def build(name, record, reference, folder, optimization, cc):
    folder.mkdir(parents=True)
    source=reference/record['directory']; code,heap=adapters(name)
    adapter=folder/'snapshot.c';adapter.write_text(code)
    flags=['-march=rv32im','-mabi=ilp32',optimization,'-std=gnu17','-Wno-unknown-pragmas','-I',str(source)]
    units=[]
    for filename in record['compiled_c_files']:
        if name in ('pm','fmref') and filename==name+'.c':continue
        if name=='audiobeam' and filename=='audiobeamlibmalloc.c':
            hp=folder/'heap-snapshot.c';hp.write_text(heap);units.append(hp)
        else:units.append(source/filename)
    units.append(adapter);objects=[];commands=[]
    for i,p in enumerate(units):
        obj=folder/(str(i)+'-'+p.stem+'.o')
        cmd=[cc,*flags,'-Dmain=tacle_original_main','-c',str(p),'-o',str(obj)]
        record_cmd,_=command(cmd,folder/(str(i)+'-build.log'),60);commands.append(record_cmd);objects.append(str(obj))
    elf=folder/(name+'.elf')
    cmd=[cc,*flags,f'-DUPSTREAM_INIT={name}_init',f'-DUPSTREAM_RUN={name}_main',f'-DUPSTREAM_RETURN={name}_return',
         '-DANAGRAM_PHRASE=-1','-DPARTIAL_DIJKSTRA=0','-nostartfiles','-T',str(ROOT/'src/spike-setup/memory-layout.ld'),
         str(ROOT/'src/spike-setup/startup.S'),str(ROOT/'benchmarks/embench-hooks.c'),str(ROOT/'benchmarks/external-v5/runtime.c'),
         str(ROOT/'benchmarks/external-v5/wrapper.c'),*objects,'-o',str(elf)]
    r,_=command(cmd,folder/'link.log',60);commands.append(r)
    return elf,{'commands':commands,'elf_sha256':sha(elf),'snapshot_sha256':sha(adapter)}


def collect(reference, destination, plan):
    # Existing or partially failed attempts are never resumed/overwritten.
    destination.mkdir(parents=True)
    write(destination/'input-plan.json',plan)
    for name,record in plan['programs'].items():
        for p,digest in record['files'].items():
            target=destination/'upstream'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((reference/p).read_bytes())
            if sha(target)!=digest:raise ValueError('Source snapshot mismatch')
    for p,digest in plan['runtime_source_sha256'].items():
        target=destination/'frozen-sources'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/p).read_bytes())
        if sha(target)!=digest:raise ValueError('Runtime snapshot mismatch')
    report={'schema':'isaforge-v11-reserved-input-report-v1','status':'running','started_at_utc':now(),
            'input_plan_sha256':sha(destination/'input-plan.json'),'records':{},'no_models_features_area_labels_fits':True}
    write(destination/'input-report.json',report)
    tools={n:r['path'] for n,r in plan['tools'].items()}
    for name,r in plan['programs'].items():
        folder=destination/name;entry={'status':'running','family':r['family']};report['records'][name]=entry
        write(destination/'input-report.json',report)
        try:
            authenticate(plan,reference)
            captured={}
            for opt in ('O2','O0'):
                elf,build_record=build(name,r,reference,folder/opt,'-'+opt,tools['cc']);entry[opt+'_build']=build_record
                _,text=command([tools['spike'],'--isa=rv32im_zicntr','-m16',str(elf)],folder/(opt+'-selfcheck.log'),60)
                captured[opt]=output(text)
                oracle=validate_output(name,captured[opt],reference/r['directory']);write(folder/(opt+'-oracle.json'),oracle)
            if captured['O2']!=captured['O0']:raise ValueError('O0/O2 complete snapshot/digest mismatch')
            entry['captured_outputs']=captured['O2'];entry['O0_O2_snapshot_bitexact']=True
            elf=folder/'O2'/(name+'.elf')
            summary,runs,starts=collect_trace_external(tools['spike'],elf,folder/(name+'.jsonl.gz'),folder/'trace.log',300)
            if not summary['validated'] or output(Path(summary['program_output']).read_text())!=captured['O2']:
                raise ValueError('Incomplete trace or captured output mismatch')
            program=readProgram(elf,tools['objdump']);previous=None
            for pc in sorted(program):
                symbol=program[pc].get('symbol')
                if symbol!=previous:starts.add(pc)
                previous=symbol
            rows=extractCandidates(program,runs,starts,maxSize=4,limit=None)
            cdir=folder/'candidates-all-roi';write(cdir/(name+'.json'),rows)
            pdir=folder/'programs';pdir.mkdir();os.link(elf,pdir/(name+'.elf'))
            fusion=verify_candidates(cdir,pdir,tools['objdump'],vectors=16,seed=2026101507);write(folder/'fusion-all-roi.json',fusion)
            if not fusion['passed'] or any(x['skipped_opaque_block_occurrences'] for x in fusion['benchmarks']):
                raise ValueError('Incomplete fusion coverage')
            authenticate(plan,reference)
            entry.update(status='complete' if rows else 'empty',trace_instructions=summary['trace_instructions'],
                         all_roi_count=len(rows),candidate_sha256=sha(cdir/(name+'.json')),fusion_passed=True)
        except Exception as error:
            entry.update(status='failure-retained',error=repr(error))
        write(destination/'input-report.json',report)
        print(name,entry['status'],entry.get('all_roi_count'),entry.get('error',''),flush=True)
    authenticate(plan,reference)
    report.update(status='input-only-attempt-complete',completed_at_utc=now(),
                  successful_programs=sum(r['status'] in ('complete','empty') for r in report['records'].values()),
                  nonempty_families=sorted({r['family'] for r in report['records'].values() if r['status']=='complete'}),
                  all_roi_program_formula_rows=sum(r.get('all_roi_count',0) for r in report['records'].values()))
    write(destination/'input-report.json',report)
    write(destination/'evidence-inventory.json',{'schema':'isaforge-v11-input-evidence-files-v1','files':inventory(destination)})
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-dir',type=Path,default=ROOT.parent/'references/tacle-bench')
    p.add_argument('--output',type=Path,required=True)
    for name in ('cc','objdump','spike'):p.add_argument('--'+name)
    args=p.parse_args();reference=args.reference_dir.resolve();destination=args.output.resolve()
    if destination.exists():raise FileExistsError('Existing attempt is immutable')
    if not destination.is_relative_to(ROOT):raise ValueError('Evidence attempt must be inside repository')
    v8=read(ROOT/'benchmarks/application-v8/cohort-preflight.json')
    tools={n:str(Path(getattr(args,n) or r['path']).resolve()) for n,r in v8['tools'].items()}
    plan=create_plan(reference,tools);authenticate(plan,reference)
    report=collect(reference,destination,plan)
    print(json.dumps({'status':report['status'],'output':str(destination),'rows':report['all_roi_program_formula_rows']}))
if __name__=='__main__':main()

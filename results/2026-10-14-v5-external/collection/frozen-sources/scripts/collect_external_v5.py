#!/usr/bin/env python3
"""Freeze and collect three external RV32 application families without target labels."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import heapq
import json
import gzip
import os
import signal
import threading
import time
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))
from candidates import extractCandidates, readProgram
from run_holdout_benchmarks import CountedTrace
from tracing import parse_trace
from verify_candidate_fusions import verify_candidates
from isaforge.dataset import build_dataset
from isaforge.features import parse_formula

FIXTURE = ROOT/'benchmarks/external-v5'
PROGRAMS = ('dijkstra', 'adpcm_dec', 'anagram')
FLAGS = ('-march=rv32im', '-mabi=ilp32', '-O2', '-std=gnu17', '-Wno-unknown-pragmas')
SEED = 2026101503
MAX_SIZE = 4
PER_PROGRAM = 200


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def read(path):
    return json.loads(Path(path).read_text())


def now():
    return datetime.now(timezone.utc).isoformat()


def source_files(manifest):
    if tuple(manifest['programs']) != PROGRAMS:
        raise ValueError('External program cohort changed')
    result = {}
    for spec in manifest['programs'].values():
        for name, digest in spec['files_sha256'].items():
            if not name.startswith(spec['directory']+'/') or '..' in Path(name).parts:
                raise ValueError('Unsafe upstream path')
            if not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Invalid upstream hash')
            result[name] = digest
    return result


def fetch_sources(manifest, destination, reference=None):
    for name, expected in source_files(manifest).items():
        target = destination/name
        if not target.exists():
            if reference is None:
                url = f"https://raw.githubusercontent.com/tacle/tacle-bench/{manifest['commit']}/{name}"
                with urllib.request.urlopen(url, timeout=30) as response:
                    content = response.read()
            else:
                content = (reference/name).read_bytes()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError(f'Upstream source mismatch: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        if sha(target) != expected:
            raise ValueError(f'Retained upstream source mismatch: {name}')


def independent_dijkstra(source):
    text = Path(source).read_text()
    values = list(map(int, re.findall(r'\b\d+\b', text[text.index('{'):])) )
    if len(values) != 10000:
        raise ValueError('Expected fixed100x100 adjacency matrix')
    matrix = [values[i:i+100] for i in range(0,10000,100)]
    answers = []
    for start in range(20):
        distances = [9999]*100
        distances[start] = 0
        queue = [(0,start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != distances[node]:
                continue
            for target, weight in enumerate(matrix[node]):
                if weight != 9999 and cost+weight < distances[target]:
                    distances[target] = cost+weight
                    heapq.heappush(queue,(cost+weight,target))
        answers.append(distances[start+50])
    if sum(answers) != 25:
        raise ValueError('Independent graph oracle differs from pinned upstream check')
    return answers


def independent_adpcm_two_code():
    """Mathematical oracle for ONLY the pinned initial two-code execution.

    Inputs0,253; initial low/high scales32,8; all predictor delays zero.
    First low reconstruction is floor(32*-136/32768)=-1, high=-2.
    At the second code the low predictor remainszero. High zero/pole
    prediction each equal-1, quantized difference0, reconstructing-2 again.
    The QMF's first two tap pairs then determine all four output samples.
    This is not an independently implemented general G.722 decoder.
    """
    low = (32*(-136))//32768
    high = (8*(-7408))//32768
    first = (low-high, low+high)
    high_zero = (128*high)//16384
    high_pole = (192*(2*high))//32768
    high_second = high_zero+high_pole+(8*1616)//32768
    second = (low-high_second, low+high_second)
    taps = ((12,-44),(-44,212))
    return [first[0]*taps[0][0]//16384, first[1]*taps[0][1]//16384,
            (second[0]*taps[0][0]+first[0]*taps[1][0])//16384,
            (second[1]*taps[0][1]+first[1]*taps[1][1])//16384]


def anagram_inputs(source):
    text = Path(source).read_text()
    phrases = re.findall(r'"([^"\\]*)"', text.split('anagram_achPhrase[ 3 ] =',1)[1].split('};',1)[0])
    dictionary = re.findall(r'"([^"\\]*)"', text.split('anagram_dictionary[ 2279 ] =',1)[1].split('};',1)[0])
    if len(phrases)!=3 or len(dictionary)!=2279:
        raise ValueError('Anagram fixed inputs changed')
    return phrases,set(dictionary)


def anagram_witness(values, phrase, dictionary):
    if len(values)!=30 or any(not 0<=value<=255 for value in values) or 0 not in values:
        raise ValueError('Invalid anagram buffer/termination')
    answer = bytes(values[:values.index(0)]).decode('ascii')
    words = answer.split()
    if not words or any(word not in dictionary for word in words):
        raise ValueError('Anagram answer contains a word outside the pinned dictionary')
    letters = lambda text: Counter(character.lower() for character in text if character.isalpha())
    if letters(answer) != letters(phrase):
        raise ValueError('Anagram answer does not preserve the input letter multiset')
    return answer


def parse_output(log):
    outputs = []
    for line in log.splitlines():
        if line.startswith('{'):
            record = json.loads(line)
            if record.get('kind') == 'external-output':
                outputs.append(record)
    if len(outputs)!=1:
        raise ValueError(f'Expected one HTIF output record, got {len(outputs)}')
    return outputs[0]


def command(args, log, timeout):
    try:
        run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b''
        stderr = exc.stderr or b''
        log.write_bytes((stdout.encode() if isinstance(stdout,str) else stdout)+
                        (stderr.encode() if isinstance(stderr,str) else stderr))
        raise
    log.write_text(run.stdout+run.stderr)
    record = {'command':args,'exit_code':run.returncode,'log':str(log.relative_to(ROOT))}
    if run.returncode:
        raise RuntimeError(f'Command exit{run.returncode}; see {log}')
    return record,run.stdout


def snapshot_source(name, upstream):
    if name=='anagram':
        return f'''/* Upstream included unchanged to inspect its file-local buffer. */
#define main tacle_original_main
#include "{upstream/(name+'.c')}"
#undef main
#include <stdint.h>
unsigned external_snapshot(int32_t *values) {{
    for(unsigned i=0;i<30;i++) values[i]=(unsigned char)anagram_buffer[i];
    return 30;
}}
/* Correctness-only single-phrase probe, never a scored/traced workload variant. */
void external_anagram_phrase(unsigned i) {{
    anagram_Reset(); anagram_BuildMask(anagram_achPhrase[i]); anagram_AddWords();
    if(anagram_cpwCand && anagram_cchPhraseLength) {{
        anagram_cpwLast=0; anagram_SortCandidates();
        anagram_FindAnagram(anagram_aqMainMask,anagram_apwCand,0);
    }}
}}
'''
    if name=='adpcm_dec':
        return '''#include <stdint.h>
extern int adpcm_dec_result[];
unsigned external_snapshot(int32_t *values) {
    for(unsigned i=0;i<4;i++)values[i]=adpcm_dec_result[i]; return 4;
}
'''
    return '''#include <stdint.h>
extern void dijkstra_init(void);
extern int dijkstra_find(int,int),dijkstra_queueNext;
int external_dijkstra_path(void) { return dijkstra_find(0,50); }
extern struct { int dist; int prev; } dijkstra_rgnNodes[];
unsigned external_snapshot(int32_t *values) {
    dijkstra_init();
    for(int i=0;i<20;i++) {
        if(dijkstra_find(i,i+50)!=0) { values[i]=-9999; return 20; }
        values[i]=dijkstra_rgnNodes[i+50].dist; dijkstra_queueNext=0;
    }
    return 20;
}
'''


def build(name, spec, sources, folder, cc, optimization='-O2', phrase=-1):
    folder.mkdir(parents=True,exist_ok=True)
    upstream = sources/spec['directory']
    adapter = folder/'snapshot.c'
    adapter.write_text(snapshot_source(name, upstream))
    flags = [optimization if flag=='-O2' else flag for flag in FLAGS]
    commands,objects = [],[]
    for source in sorted(upstream.glob('*.c')):
        if name=='anagram' and source.name=='anagram.c':
            continue
        obj = folder/(source.stem+'.o')
        args = [cc,*flags,'-Dmain=tacle_original_main','-I',str(upstream),'-c',str(source),'-o',str(obj)]
        record,_=command(args,folder/(source.stem+'.build.log'),120)
        commands.append(record);objects.append(str(obj))
    adapter_obj=folder/'snapshot.o'
    record,_=command([cc,*flags,'-I',str(upstream),'-c',str(adapter),'-o',str(adapter_obj)],folder/'snapshot.build.log',120)
    commands.append(record);objects.append(str(adapter_obj))
    elf=folder/(name+'.elf')
    args=[cc,*flags,f'-DUPSTREAM_INIT={name}_init',f'-DUPSTREAM_RUN={name}_main',
          f'-DUPSTREAM_RETURN={name}_return',f'-DANAGRAM_PHRASE={phrase}',
          f'-DPARTIAL_DIJKSTRA={int(name=="dijkstra")}', '-nostartfiles',
          '-T',str(ROOT/'src/spike-setup/memory-layout.ld'),str(ROOT/'src/spike-setup/startup.S'),
          str(ROOT/'benchmarks/embench-hooks.c'),str(FIXTURE/'runtime.c'),str(FIXTURE/'wrapper.c'),
          *objects,'-o',str(elf)]
    record,_=command(args,folder/'link.log',120);commands.append(record)
    return elf,{'commands':commands,'elf_sha256':sha(elf),'elf_bytes':elf.stat().st_size,
                'adapter_sha256':sha(adapter),'optimization':optimization,'phrase_probe':phrase}


def collect_trace_external(spike, elf, trace, log, timeout):
    """Separate commit stream from HTIF stdout; retain incomplete streams on failure.

    Spike handles SIGTERM interactively, so a deadline kills only this collector's
    process group with SIGKILL. This leaves completed prior evidence untouched.
    """
    read_fd, write_fd = os.pipe()
    program_output = log.with_suffix('.stdout.log')
    partial = trace.with_suffix(trace.suffix+'.partial')
    started = time.monotonic()
    args = [spike,'--isa=rv32im_zicntr','-m16','--log-commits',
            f'--log=/dev/fd/{write_fd}',str(elf)]
    process = None
    timer = None
    try:
        with os.fdopen(read_fd,'r') as commits, program_output.open('w') as stdout, log.open('w') as stderr:
            process = subprocess.Popen(args,cwd=ROOT,stdout=stdout,stderr=stderr,
                                       pass_fds=(write_fd,),start_new_session=True)
            os.close(write_fd)
            write_fd = None
            def terminate():
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
            timer = threading.Timer(timeout,terminate)
            timer.start()
            with gzip.open(partial,'wt',compresslevel=1) as output:
                sink = CountedTrace(output)
                summary = parse_trace(commits,sink)
                sink.finish()
            code = process.wait(timeout=30)
            if code:
                raise RuntimeError(f'Spike trace exit{code}; see{log}')
        partial.replace(trace)
    except BaseException:
        if process is not None:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)
        raise
    finally:
        if timer is not None:
            timer.cancel()
        if write_fd is not None:
            os.close(write_fd)
    summary.update(command=args,exit_code=code,wall_seconds=time.monotonic()-started,
                   trace_path=str(trace.relative_to(ROOT)),trace_encoding='gzip JSONL; complete measured window',
                   trace_bytes=trace.stat().st_size,trace_sha256=sha(trace),
                   program_output=str(program_output),program_output_sha256=sha(program_output),
                   log=str(log.relative_to(ROOT)),stream_separation='Commit pipe independent of HTIF stdout')
    write(trace.with_suffix('.summary.json'),summary)
    return summary,sink.runs,sink.starts


def filtered_counts(program, runs, starts, name):
    prefix=name+'_'
    scoped=Counter({pc:count for pc,count in runs.items() if (program[pc].get('symbol') or '').startswith(prefix)})
    boundaries=set(starts)
    previous=None
    for pc in sorted(program):
        symbol=program[pc].get('symbol')
        if symbol!=previous:
            boundaries.add(pc)
        previous=symbol
    return scoped,boundaries


def downselect(rows, seed=SEED, limit=PER_PROGRAM):
    def key(row):
        formula=parse_formula(row['formula']).canonical()
        return hashlib.sha256(f'{seed}:{formula}'.encode()).hexdigest(),formula
    return sorted(rows,key=key)[:limit]


def frozen_plan(manifest, cc, objdump, spike, reference, timeout):
    tracked=[Path(__file__),ROOT/'docs/external-v5-protocol.md',ROOT/'src/tracing.py',
             ROOT/'src/candidates.py',ROOT/'src/verify_candidate_fusions.py',ROOT/'src/run_holdout_benchmarks.py',
             ROOT/'src/spike-setup/startup.S',ROOT/'src/spike-setup/memory-layout.ld',ROOT/'benchmarks/embench-hooks.c',
             ROOT/'isaforge/features.py',ROOT/'isaforge/dataset.py',*sorted(FIXTURE.rglob('*'))]
    return {'schema':'isaforge-external-input-plan-v2','upstream':manifest,'programs':list(PROGRAMS),
            'families':{name:manifest['programs'][name]['family'] for name in PROGRAMS},
            'compiler_flags':list(FLAGS),'spike_flags':['--isa=rv32im_zicntr','-m16'],
            'tools':{label:{'path':path,'sha256':sha(path)} for label,path in [('cc',cc),('objdump',objdump),('spike',spike)]},
            'source_sha256':{str(path.relative_to(ROOT)):sha(path) for path in tracked if path.is_file()},
            'max_size':MAX_SIZE,'per_program_limit':PER_PROGRAM,'downselection_seed':SEED,
            'downselection':'SHA256(seed:canonical_formula), first200 perprogram, no labels/predictions',
            'inclusion':'Only functions with program_ namespace; split at symbol boundaries. Init/output/check helpers excluded by markers.',
            'controls':'Same pinned sources, RV32 ILP32 atO0 andO2; anagram single-phrase witness probes outside scored cohort',
            'target_labels_allowed':False,'model_predictions_allowed':False,
            'timeout_seconds':timeout,
            'measured_scope':{'dijkstra':'One shortest-path search (0,50) on original100x100 graph; full20-path self-check before markers and replay afterward',
                              'adpcm_dec':'Original two-code core','anagram':'Original three-phrase core'},
            'scope_amendment':'Cohort01 retained after trace infrastructure failure; Dijkstra partial-workload trace explicitly selected on input/runtime evidence only',
            'commit_stream':'Separate inherited pipe; HTIF stdout and commit logger never share descriptor'}


def collect(args):
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'generated/external-v5'):
        raise ValueError('Output must be under generated/external-v5')
    if (output/'completion.json').exists():
        raise ValueError('Completed collection is immutable; use a fresh subdirectory')
    output.mkdir(parents=True,exist_ok=True)
    manifest=read(FIXTURE/'fetch.json')
    fetch_sources(manifest,output/'sources',args.reference_dir)
    plan=frozen_plan(manifest,args.cc,args.objdump,args.spike,args.reference_dir,args.timeout)
    plan_path=output/'input-plan.json'
    if plan_path.exists():
        old=read(plan_path);old.pop('frozen_at_utc',None)
        if old!=plan:
            raise ValueError('Frozen source/plan changed; preserve this run and use a new subdirectory')
    else:
        write(plan_path,{**plan,'frozen_at_utc':now()})
    for directory in ('programs','controls','logs','traces','candidates','selected'):
        (output/directory).mkdir(exist_ok=True)
    sources=output/'sources'
    oracle={'dijkstra':independent_dijkstra(sources/'bench/sequential/dijkstra/input.c'),
            'adpcm_dec':independent_adpcm_two_code()}
    phrases,dictionary=anagram_inputs(sources/'bench/sequential/anagram/anagram_input.c')
    report={'input_plan_sha256':sha(plan_path),'started_at_utc':now(),'programs':[],
            'oracle_scope':{'dijkstra':'Independent heap shortest paths on all20 selected pairs',
                            'adpcm_dec':'Independent mathematical derivation for pinned2codes/4samples only; not general G722 proof',
                            'anagram':'Independent dictionary membership/letter-multiset witness checks; not solution-completeness proof'},
            'target_labels_collected':False,'models_loaded':False}
    for name in PROGRAMS:
        record={'program':name,'family':manifest['programs'][name]['family'],'status':'started'}
        report['programs'].append(record);write(output/'report.json',report)
        try:
            spec=manifest['programs'][name]
            built_elf,build_record=build(name,spec,sources,output/'programs'/name,args.cc)
            elf=output/'programs'/f'{name}.elf'
            elf.write_bytes(built_elf.read_bytes())
            record['build']=build_record
            run_record,text=command([args.spike,'--isa=rv32im_zicntr','-m16',str(elf)],output/'logs'/f'{name}.self-check.log',args.timeout)
            observed=parse_output(text)
            if name in oracle:
                if observed['values']!=oracle[name]:
                    raise ValueError(f'{name}: full output differs from independent oracle')
            else:
                record['anagram_answer']=anagram_witness(observed['values'],phrases[2],dictionary)
            if observed['upstream_status']!=0:
                raise ValueError('Upstream self-check failed')
            record['self_check']={**run_record,'output':observed,'strong_check_passed':True}
            control_elf,control_build=build(name,spec,sources,output/'controls'/name,args.cc,'-O0')
            control_run,control_text=command([args.spike,'--isa=rv32im_zicntr','-m16',str(control_elf)],output/'logs'/f'{name}.O0-control.log',args.timeout)
            control=parse_output(control_text)
            if control!=observed:
                raise ValueError(f'{name}: O0/O2 output mismatch')
            record['compiler_control']={'build':control_build,'run':control_run,'matches_primary_output':True}
            if name=='anagram':
                record['phrase_probes']=[]
                for index,phrase in enumerate(phrases):
                    probe_elf,probe_build=build(name,spec,sources,output/'controls'/f'anagram-phrase{index}',args.cc,'-O0',index)
                    probe_run,probe_text=command([args.spike,'--isa=rv32im_zicntr','-m16',str(probe_elf)],output/'logs'/f'anagram-phrase{index}.log',args.timeout)
                    probe=parse_output(probe_text)
                    answer=anagram_witness(probe['values'],phrase,dictionary)
                    record['phrase_probes'].append({'phrase':phrase,'answer':answer,'build':probe_build,'run':probe_run,'witness_check_passed':True})
            summary,runs,starts=collect_trace_external(args.spike,elf,output/'traces'/f'{name}.jsonl.gz',output/'logs'/f'{name}.trace.log',args.timeout)
            traced_output=parse_output(Path(summary['program_output']).read_text())
            if traced_output!=observed:
                raise ValueError('Traced ELF output differs from self-checked output')
            if sha(elf)!=build_record['elf_sha256']:
                raise ValueError('Self-checked ELF changed before trace completion')
            program=readProgram(elf,args.objdump)
            scoped,boundaries=filtered_counts(program,runs,starts,name)
            rows=extractCandidates(program,scoped,boundaries,MAX_SIZE,None)
            write(output/'candidates'/f'{name}.json',rows)
            selected=downselect(rows)
            write(output/'selected'/f'{name}.json',selected)
            record.update(status='passed' if rows else 'empty',trace=summary,
                          application_instruction_count=sum(scoped.values()),candidate_count=len(rows),
                          selected_count=len(selected),candidates_sha256=sha(output/'candidates'/f'{name}.json'))
        except Exception as exc:
            record.update(status='failed',error=f'{type(exc).__name__}: {exc}')
            write(output/'candidates'/f'{name}.json',[])
            write(output/'selected'/f'{name}.json',[])
        write(output/'report.json',report)
        print(name,record['status'],record.get('candidate_count'),record.get('error',''),flush=True)
    equivalence=verify_candidates(output/'candidates',output/'programs',args.objdump,vectors=16,seed=SEED)
    write(output/'extraction-equivalence.json',equivalence)
    candidates=[];full=[]
    for record in report['programs']:
        name=record['program'];family=record['family']
        for folder,destination in [('selected',candidates),('candidates',full)]:
            rows=build_dataset('external_v5_'+name,read(output/folder/f'{name}.json'))
            destination.extend({**row,'family':family,'cohort':'external_v5_input_only',
                                'provenance':'Pinned TACLeBench RV32IM execution; no target-resource labels'} for row in rows)
    write(output/'candidates.json',candidates);write(output/'full-candidates.json',full)
    fetch_sources(manifest,sources,args.reference_dir)
    if plan != frozen_plan(manifest,args.cc,args.objdump,args.spike,args.reference_dir,args.timeout):
        raise ValueError('Sources changed during collection')
    report.update(finished_at_utc=now(),all_families_present=True,
                  all_self_checks_passed=all(row['status'] in ('passed','empty') for row in report['programs']),
                  selected_formula_occurrences=len(candidates),full_formula_occurrences=len(full),
                  unique_selected_formulas=len({row['formula'] for row in candidates}),
                  unique_full_formulas=len({row['formula'] for row in full}),
                  candidate_sha256=sha(output/'candidates.json'))
    write(output/'report.json',report)
    write(output/'completion.json',{'completed_at_utc':now(),'input_plan_sha256':sha(plan_path),
                                    'report_sha256':sha(output/'report.json'),'candidate_sha256':sha(output/'candidates.json'),
                                    'resource_labels_released':False,'models_loaded':False})
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'generated/external-v5/cohort-02')
    parser.add_argument('--reference-dir',type=Path,help='Reviewed pinned checkout; every file hash is verified')
    parser.add_argument('--cc',default=str(ROOT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc'))
    parser.add_argument('--objdump',default=str(ROOT.parent/'toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump'))
    parser.add_argument('--spike',default=str(ROOT.parent/'toolchains/spike/bin/spike'))
    parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    for name in ('cc','objdump','spike'):
        setattr(args,name,str(Path(getattr(args,name)).resolve()))
    report=collect(args)
    return 0 if report['all_self_checks_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

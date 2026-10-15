"""Verify/reproduce admitted input-only application pools. Never maps circuits or fits.

Historical attempts are immutable. --reproduce requires a fresh output directory,
exact reviewed tool/source bytes, and executes only the five admitted programs.
MPEG2's incomplete attempt remains evidence, not an implicit retry target.
"""
from __future__ import annotations
import argparse
import hashlib
import gzip
from collections import Counter
import time
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
from collect_external_v5 import command,collect_trace_external
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates

DEFAULT=ROOT/'benchmarks/application-v8/cohort-preflight.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def checked_path(record):
    path=(ROOT/record['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()) or sha(path)!=record['sha256']:
        raise ValueError(f'Changed/missing evidence: {record["path"]}')
    return path

def validate(manifest,manifest_path=DEFAULT):
    if manifest['schema']!='isaforge-v8-application-input-preflight-v1':raise ValueError('Wrong manifest')
    if manifest['primary_programs']!=['bitcount','fft','ndes','h264_dec'] or manifest['related_source_secondary_programs']!=['isqrt'] or manifest['failed_not_admitted']!=['mpeg2']:
        raise ValueError('Changed admitted cohort')
    families={'bitcount':'bitcount','fft':'fft','ndes':'des','h264_dec':'video','isqrt':'related-basicmath','mpeg2':'video'}
    if set(manifest['programs'])!=set(families):raise ValueError('Changed attempted programs')
    for name,family in families.items():
        expected='related-source-secondary' if name=='isqrt' else 'failed-not-admitted' if name=='mpeg2' else 'primary'
        if manifest['programs'][name]['family']!=family or manifest['programs'][name]['role']!=expected:raise ValueError('Changed family/role assignment')
    amendment=read(DEFAULT.parent/'provenance-amendment.json')
    if amendment['schema']!='isaforge-v8-input-provenance-amendment-v1' or amendment['original_preflight_sha256']!=sha(manifest_path):raise ValueError('Unbound provenance amendment')
    for path,digest in {**manifest['runtime_dependencies'],**manifest['evidence_files'],**amendment['additional_runtime_dependencies']}.items():
        checked_path({'path':path,'sha256':digest})
    for name,r in manifest['programs'].items():
        for key in ('snapshot_adapter','O2_elf','O0_elf'):checked_path(r[key])
        for record in r['selfcheck_logs'].values():checked_path(record)
        if name=='mpeg2':
            partial=ROOT/r['partial_trace']['path'];policy=amendment['failed_partial_publication_policy']
            if partial.exists():checked_path(r['partial_trace'])
            elif not(policy['allow_absent_failed_partial_on_relocation'] and policy['program']==name and policy['path']==r['partial_trace']['path'] and policy['sha256']==r['partial_trace']['sha256']):raise ValueError('Unexplained missing failure partial')
            continue
        for key in ('trace','trace_summary','all_roi_candidates','kernel_candidates','fusion_all_roi','fusion_kernel'):checked_path(r[key])
        summary=read(checked_path(r['trace_summary']));fusion=read(checked_path(r['fusion_all_roi']))
        if not summary['validated'] or summary['trace_instructions']!=r['trace_instruction_count'] or summary['trace_sha256']!=r['trace']['sha256']:raise ValueError('Incomplete/unbound trace')
        if not fusion['passed'] or any(x['skipped_opaque_block_occurrences'] for x in fusion['benchmarks']):raise ValueError('Incomplete fusion coverage')
        if len(read(checked_path(r['all_roi_candidates'])))!=r['all_roi_count']:raise ValueError('Candidate count')
    total=sum(manifest['programs'][n]['all_roi_count'] for n in manifest['primary_programs'])
    if total!=150 or manifest['primary_program_formula_rows']!=total:raise ValueError('Changed primary pool')
    return manifest

def output(text):
    rows=[json.loads(line) for line in text.splitlines() if line.startswith('{')]
    if len(rows)!=1 or rows[0].get('kind')!='external-output' or rows[0].get('upstream_status')!=0:raise ValueError('Upstream output failed')
    return rows[0]['values']

def sources(reference,r):
    reference=reference.resolve()
    directory=(reference/r['upstream_directory']).resolve()
    if not directory.is_relative_to(reference.resolve()):raise ValueError('Unsafe source directory')
    actual={str(p.relative_to(reference)):sha(p) for p in directory.iterdir() if p.is_file()}
    if actual!=r['upstream_source_sha256']:raise ValueError('Upstream source/input/notice bytes changed, missing, or extra')
    return directory

def build(reference,r,name,folder,opt,cc):
    source=sources(reference,r);folder.mkdir(parents=True);adapter=checked_path(r['snapshot_adapter'])
    flags=['-march=rv32im','-mabi=ilp32',opt,'-std=gnu17','-Wno-unknown-pragmas','-I',str(source)]
    objects=[]
    for filename in r['compiled_c_files']:
        if Path(filename).name!=filename or not filename.endswith('.c'):raise ValueError('Unsafe C whitelist')
        obj=folder/(Path(filename).stem+'.o')
        command([cc,*flags,'-Dmain=tacle_original_main','-c',str(source/filename),'-o',str(obj)],folder/(filename+'.build.log'),60)
        objects.append(str(obj))
    elf=folder/(name+'.elf')
    command([cc,*flags,f'-DUPSTREAM_INIT={name}_init',f'-DUPSTREAM_RUN={name}_main',f'-DUPSTREAM_RETURN={name}_return','-DANAGRAM_PHRASE=-1','-DPARTIAL_DIJKSTRA=0','-nostartfiles','-T',str(ROOT/'src/spike-setup/memory-layout.ld'),str(ROOT/'src/spike-setup/startup.S'),str(ROOT/'benchmarks/embench-hooks.c'),str(ROOT/'benchmarks/external-v5/runtime.c'),str(ROOT/'benchmarks/external-v5/wrapper.c'),str(adapter),*objects,'-o',str(elf)],folder/'link.log',60)
    return elf

def reproduce(manifest,reference,destination,tools):
    # mkdir without exist_ok prevents overwriting logs, partial traces or evidence.
    destination.mkdir(parents=True)
    report={'schema':'isaforge-v8-input-reproduction-v1','status':'running','records':{},'no_target_mapping_models_predictions_fits':True}
    for name in [*manifest['primary_programs'],*manifest['related_source_secondary_programs']]:
        r=manifest['programs'][name];folder=destination/name;entry={'status':'running'}
        try:
            elf=build(reference,r,name,folder/'O2','-O2',tools['cc']);control=build(reference,r,name,folder/'O0','-O0',tools['cc'])
            for opt,program in [('O2',elf),('O0',control)]:
                _,text=command([tools['spike'],'--isa=rv32im_zicntr','-m16',str(program)],folder/(opt+'-selfcheck.log'),60)
                if output(text)!=r['captured_outputs']:raise ValueError('Changed captured declared inputs/outputs')
            summary,runs,starts=collect_trace_external(tools['spike'],elf,folder/(name+'.jsonl.gz'),folder/'trace.log',300)
            if output(Path(summary['program_output']).read_text())!=r['captured_outputs']:raise ValueError('Traced output mismatch')
            program=readProgram(elf,tools['objdump']);previous=None
            for pc in sorted(program):
                symbol=program[pc].get('symbol')
                if symbol!=previous:starts.add(pc)
                previous=symbol
            rows=extractCandidates(program,runs,starts,maxSize=4,limit=None);cdir=folder/'candidates-all-roi';write(cdir/(name+'.json'),rows)
            pdir=folder/'programs';pdir.mkdir();os.link(elf,pdir/(name+'.elf'))
            fusion=verify_candidates(cdir,pdir,tools['objdump'],vectors=16,seed=2026101507);write(folder/'fusion-all-roi.json',fusion)
            if not summary['validated'] or not fusion['passed'] or any(x['skipped_opaque_block_occurrences'] for x in fusion['benchmarks']):raise ValueError('Incomplete trace/fusion')
            if {x['formula'] for x in rows}!={x['formula'] for x in read(checked_path(r['all_roi_candidates']))}:raise ValueError('Historical admitted formula pool mismatch')
            sources(reference,r)
            entry.update(status='complete',trace_instructions=summary['trace_instructions'],all_roi_count=len(rows),elf_sha256=sha(elf),candidates_sha256=sha(cdir/(name+'.json')))
        except BaseException as error:
            entry.update(status='failure-retained',error=repr(error));report['records'][name]=entry;report['status']='failure-retained';write(destination/'reproduction.json',report)
            raise
        report['records'][name]=entry;write(destination/'reproduction.json',report)
    validate(manifest)
    report['status']='complete-input-only';write(destination/'reproduction.json',report)
    return report

def verify_runtime(manifest,reference,objdump,report_path,manifest_path=DEFAULT):
    if report_path.exists():raise FileExistsError('Never overwrite a replay report')
    if sha(objdump)!=manifest['tools']['objdump']['sha256']:raise ValueError('Changed objdump')
    report={'schema':'isaforge-v8-input-runtime-replay-v1','status':'running','collector_sha256':sha(__file__),'records':{},'no_builds_program_execution_target_mapping_models_or_labels':True}
    for name in [*manifest['primary_programs'],*manifest['related_source_secondary_programs']]:
        started=time.monotonic();r=manifest['programs'][name];entry={}
        try:
            sources(reference,r)
            runs=Counter();starts=set();previous=None
            with gzip.open(checked_path(r['trace']),'rt') as stream:
                for line in stream:
                    pc=int(json.loads(line)['pc'],16);runs[pc]+=1
                    if previous is None or pc!=previous+4:starts.add(pc)
                    previous=pc
            if previous is not None:starts.add(previous+4)
            if sum(runs.values())!=r['trace_instruction_count']:raise ValueError('Trace count mismatch')
            program=readProgram(checked_path(r['O2_elf']),objdump);previous=None
            for pc in sorted(program):
                symbol=program[pc].get('symbol')
                if symbol!=previous:starts.add(pc)
                previous=symbol
            allrows=extractCandidates(program,runs,starts,maxSize=4,limit=None)
            if allrows!=read(checked_path(r['all_roi_candidates'])):raise ValueError('All-ROI extraction or overlapSafeSaved mismatch')
            allowed=r['roi']['kernel_symbols_secondary']
            def selected(symbol):
                return bool(symbol) and any(symbol==a or symbol.startswith(a+'.') or (a.endswith('_') and symbol.startswith(a)) for a in allowed) and (name=='isqrt' or symbol not in {name+'_init',name+'_return',name+'_main'})
            kernel=Counter({pc:n for pc,n in runs.items() if selected(program[pc].get('symbol'))})
            if extractCandidates(program,kernel,starts,maxSize=4,limit=None)!=read(checked_path(r['kernel_candidates'])):raise ValueError('Secondary kernel extraction mismatch')
            folder=checked_path(r['O2_elf']).parent.parent
            fusion=verify_candidates(checked_path(r['all_roi_candidates']).parent,folder/'programs',objdump,vectors=16,seed=2026101507)
            if fusion!=read(checked_path(r['fusion_all_roi'])):raise ValueError('Fusion replay mismatch')
            if not fusion['passed'] or any(x['skipped_opaque_block_occurrences'] for x in fusion['benchmarks']):raise ValueError('Incomplete fusion replay')
            entry={'status':'passed','all_roi_rows':len(allrows),'trace_instructions':sum(runs.values()),'exact_full_candidate_metadata_replay':True,'overlapSafeSaved_exact_replay':True,'kernel_secondary_exact_replay':True,'fusion_exact_replay':True,'wall_seconds':time.monotonic()-started}
        except BaseException as error:
            report['records'][name]={'status':'failure-retained','error':repr(error)};report['status']='failure-retained';write(report_path,report);raise
        report['records'][name]=entry
        write(report_path,report)
    validate(manifest)
    report.update(status='passed',manifest_sha256=sha(manifest_path),provenance_amendment_sha256=sha(DEFAULT.parent/'provenance-amendment.json'),runtime_dependency_sha256=manifest['runtime_dependencies'],objdump_sha256=sha(objdump))
    write(report_path,report)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,default=DEFAULT);parser.add_argument('--reproduce',action='store_true');parser.add_argument('--verify-runtime',action='store_true');parser.add_argument('--reference-dir',type=Path);parser.add_argument('--output',type=Path)
    for name in ('cc','objdump','spike'):parser.add_argument('--'+name)
    args=parser.parse_args();manifest=validate(read(args.manifest),args.manifest)
    if args.reproduce and args.verify_runtime:parser.error('Choose one execution mode')
    if args.verify_runtime:
        if not args.output:parser.error('--verify-runtime requires fresh --output report path')
        verify_runtime(manifest,(args.reference_dir or ROOT.parent/'references/tacle-bench').resolve(),args.objdump or manifest['tools']['objdump']['path'],args.output.resolve(),args.manifest)
        print(json.dumps({'status':'runtime-replay-passed','output':str(args.output)}));return
    if not args.reproduce:print(json.dumps({'status':'validated-input-evidence','admitted_programs':5,'primary_rows':150}));return
    if not args.reference_dir or not args.output:parser.error('--reproduce requires --reference-dir and fresh --output')
    tools={n:getattr(args,n) or r['path'] for n,r in manifest['tools'].items()}
    for name,path in tools.items():
        if sha(path)!=manifest['tools'][name]['sha256']:raise ValueError('Changed reviewed tool: '+name)
    reproduce(manifest,args.reference_dir.resolve(),args.output.resolve(),tools)
    print(json.dumps({'status':'complete-input-only','output':str(args.output)}))
if __name__=='__main__':main()

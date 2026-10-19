#!/usr/bin/env python3
"""Separately approved input-only V11b recovery; never predict, fit or label.

The original six-program reservation is retained. Only AMMUNITION and PM get
one new capture each, in order. Large gzip payloads are referenced in place;
metadata ZIPs never duplicate them. Every failed single attempt is retained.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT)]
import capture_v11_spooled as spool
import collect_v11_reserved as original
from candidates import readProgram,extractCandidates
from verify_candidate_fusions import verify_candidates

OLD='results/2026-10-15-v11-reserved-transfer'
PREFIX='generated/v11-spooled-recovery/attempt-0000'
RECOVER=('ammunition','pm')
REUSE=('audiobeam','fmref','fac','recursion')
PROGRAMS=tuple(original.SPECS)
OLD_PLAN_SHA='533fb31680e29cf3173c2bc93821a3a8d27063e96100ffd670a804be9a71d74c'
OLD_REPORT_SHA='1aa550c818ab07f65b5fc46c85a2ee658b03be8ad040af6714b8e8c9070c1dca'
OLD_ARCHIVES_SHA='2639044e9019e49740da2746db8b8e19f69e83e137aa5a11310a453f0e5b400d'
ENDPOINT_SHA='aef3c6952b399d98804f873d3d8514bf21c49715de074993c4914b57237976ad'
PROTOCOL_SHA='72f5aa9053ebd6505243a67744cd36944c88114098e45aad4ee4c090c18c4c59'
class AbortRun(ValueError):pass
POLICY={**spool.POLICY,'extraction_seconds':300,'maxSize':4,'limit':None,'fusion_vectors':16,'fusion_seed':2026101507,
        'metadata_archive_bytes':2*spool.GIB,'static_objdump_calls_per_recovered_program':3,'recover':list(RECOVER),'reuse':list(REUSE),'programs':list(PROGRAMS),'new_features':0,'new_predictions':0,'new_labels':0,'new_fits':0}
need,sha,write=spool.need,spool.sha,spool.write


def now():return datetime.now(timezone.utc).isoformat()
def progress(program,phase,event):print(f'{now()} program={program} phase={phase} event={event}',flush=True)
def utc(v):
    d=datetime.fromisoformat(v);need(d.tzinfo is not None and d.utcoffset().total_seconds()==0,'UTC timestamp required');return d
def read(path):
    def unique(items):
        d={}
        for k,v in items:need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def identical(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def record(p,base):return {'path':os.path.relpath(Path(p).resolve(),Path(base).resolve()),'sha256':sha(p),'bytes':Path(p).stat().st_size}
def check_hashes(bindings):
    if not all(p.is_file() and not p.is_symlink() and sha(p)==h for p,h in bindings.items()):raise AbortRun('Sealed source/input bytes changed')
def sources():
    names=['scripts/recover_v11_transfer.py','tests/test_recover_v11_transfer.py','scripts/capture_v11_spooled.py','tests/test_capture_v11_spooled.py',
        'scripts/audit_v11_recovery.py','tests/test_audit_v11_recovery.py','docs/v11-transfer-recovery-plan.md','docs/v11b-transfer-protocol.md']
    old=read(ROOT/OLD/'input-plan.json');names+=list(old['runtime_source_sha256'])
    names += [e['path'] for e in read(ROOT/OLD/'input-provenance-amendment.json')['added_runtime_sources']]
    return sorted({ROOT/n for n in names})

def safe_member(name):
    p=PurePosixPath(name);need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and str(p)==name,'Unsafe archive member');return p

def old_evidence():
    root=ROOT/OLD
    for n,h in [('input-plan.json',OLD_PLAN_SHA),('input-report.json',OLD_REPORT_SHA),('raw-evidence-manifest.json',OLD_ARCHIVES_SHA)]:need(sha(root/n)==h,'Historical V11 lineage differs: '+n)
    plan,report,archives=read(root/'input-plan.json'),read(root/'input-report.json'),read(root/'raw-evidence-manifest.json')
    need(tuple(plan['programs'])==PROGRAMS and tuple(report['records'])==PROGRAMS,'Exact six original programs required')
    paths=[root/n for n in ('input-plan.json','input-report.json','input-summary.json','raw-evidence-manifest.json','input-provenance-amendment.json',
        'completed-rows.json','input-review/partial-volume-diagnosis.json','input-review/input-package-review.json','implementation-review/test-portability-amendment.json')]
    members={}
    for a in archives['archives']:
        p=root/a['path'];need(sha(p)==a['sha256'] and p.stat().st_size==a['bytes'],'Historical ZIP changed');paths.append(p)
        entries={e['path']:e for e in a['members']};need(len(entries)==len(a['members']),'Duplicate old manifest member')
        with zipfile.ZipFile(p) as z:
            need(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(entries),'Historical ZIP inventory differs')
            for n,e in entries.items():
                safe_member(n);h=hashlib.sha256();size=0
                with z.open(n) as stream:
                    for b in iter(lambda:stream.read(1024**2),b''):h.update(b);size+=len(b)
                need(h.hexdigest()==e['sha256'] and size==e['bytes'],'Historical archived member differs')
                need(n not in members,'Duplicate historical archive path');members[n]={'archive':p,'member':n,**e}
    need(len(archives['archives'])==7,'All seven original archives required')
    for e in archives['omitted_local_failed_partials']:
        p=ROOT/'generated/v11-reserved-inputs/attempt-0000'/e['path'];need(sha(p)==e['sha256'] and p.stat().st_size==e['bytes'],'Original partial changed');paths.append(p)
    need(len(archives['omitted_local_failed_partials'])==2,'Both failed partials retained')
    portability=read(root/'implementation-review/test-portability-amendment.json')
    need(portability['schema']=='isaforge-v11-test-portability-amendment-v1' and portability['production_collector_unchanged'] is True and portability['original_input_plan_unchanged'] is True and portability['source_input_tool_oracle_candidate_data_unchanged'] is True,'Explicit test portability amendment required')
    for p,h in plan['runtime_source_sha256'].items():
        if p==portability['path']:
            need(h==portability['original_sha256'] and members['frozen-sources/'+p]['sha256']==h and sha(ROOT/p)==portability['amended_sha256'],'Historical/amended test identity differs')
        else:need(sha(ROOT/p)==h,'Original runtime changed')
    amendment=read(root/'input-provenance-amendment.json');need(amendment['original_input_plan_sha256']==OLD_PLAN_SHA,'Original provenance amendment differs')
    for e in amendment['added_runtime_sources']:need(sha(ROOT/e['path'])==e['sha256'],'Amended original source changed')
    for name in PROGRAMS:
        r=report['records'][name];need(r['family']==plan['programs'][name]['family'] and r['O0_O2_snapshot_bitexact'] is True,'Old family/correctness differs')
        need(r['status']==('failure-retained' if name in RECOVER else 'empty' if name=='recursion' else 'complete'),'Original outcomes changed')
        need(members[f'{name}/O2/{name}.elf']['sha256']==r['O2_build']['elf_sha256'],'Exact original O2 ELF required')
    return plan,report,members,paths

def archive_bytes(entry):
    with zipfile.ZipFile(entry['archive']) as z:return z.read(entry['member'])

def dependencies(executable):
    command=['/usr/bin/otool','-L',str(executable)] if sys.platform=='darwin' else ['ldd',str(executable)]
    r=subprocess.run(command,capture_output=True,text=True)
    need(r.returncode==0,'Native dependency inventory unavailable')
    paths=sorted(set(re.findall(r'(/[^\s()]+)',r.stdout)))
    return {'command':command,'listing':r.stdout,'files':[{'path':str(Path(p).resolve()),'sha256':sha(p)} for p in paths if Path(p).is_file()],
            'boundary':'Available direct dependency files only; shared-cache/system/OS and unresolved transitive libraries are not hermetic.'}

def tools_inventory(old):
    tools={'schema':'isaforge-v11b-recovery-tools-v1','executables':{k:dict(v) for k,v in old['tools'].items()},'platform':platform.platform(),'python_version':sys.version}
    gzip=Path(shutil.which('gzip') or '/unavailable').resolve();need(gzip.is_file(),'Native gzip required')
    version=subprocess.run([str(gzip),'--version'],capture_output=True,text=True);need(version.returncode==0 and (version.stdout+version.stderr).strip(),'Native gzip version unavailable')
    tools['executables']['gzip']={'path':str(gzip),'sha256':sha(gzip),'version':(version.stdout+version.stderr).strip(),'version_stdout':version.stdout,'version_stderr':version.stderr}
    tools['executables']['python']={'path':str(Path(sys.executable).resolve()),'sha256':sha(Path(sys.executable).resolve())}
    tools['dependencies']={k:dependencies(tools['executables'][k]['path']) for k in ('gzip','spike','objdump')}
    parents=sorted({str(Path(e['path']).resolve().parent) for e in tools['executables'].values()})
    tools['environment']={'PATH':os.pathsep.join([*parents,'/usr/bin','/bin']),'LANG':'C','LC_ALL':'C','TZ':'UTC'}
    validate_tools(tools,old);return tools

def validate_tools(tools,old):
    need(tools['schema']=='isaforge-v11b-recovery-tools-v1' and tools['platform']==platform.platform() and tools['python_version']==sys.version,'Executing runtime differs')
    need(set(tools['executables'])=={'cc','objdump','spike','gzip','python'} and all(tools['executables'][k]==v for k,v in old['tools'].items()),'Original native tool changed')
    for e in tools['executables'].values():need(Path(e['path']).is_absolute() and sha(e['path'])==e['sha256'],'Native executable changed')
    need(tools['executables']['python']['path']==str(Path(sys.executable).resolve()),'Python executable differs')
    for d in tools['dependencies'].values():
        for e in d['files']:need(sha(e['path'])==e['sha256'],'Native dependency changed')
    parents=sorted({str(Path(e['path']).resolve().parent) for e in tools['executables'].values()})
    need(tools['environment']=={'PATH':os.pathsep.join([*parents,'/usr/bin','/bin']),'LANG':'C','LC_ALL':'C','TZ':'UTC'},'Sanitized execution environment differs')

def prepare(root):
    root=Path(root).resolve();need(root.is_relative_to(ROOT/'results') and root.is_dir() and {p.name for p in root.iterdir()}=={'endpoint-adoption.json'},'Root must contain only endpoint adoption before preparation')
    adoption=read(root/'endpoint-adoption.json');need(sha(root/'endpoint-adoption.json')==ENDPOINT_SHA and adoption['schema']=='isaforge-v11b-endpoint-adoption-v1' and adoption['amendment']=='V11b-E1' and sha(ROOT/'docs/v11b-transfer-protocol.md')==PROTOCOL_SHA,'Exact prelabel endpoint adoption required')
    old,report,members,paths=old_evidence();bindings={p:sha(p) for p in [*paths,*sources()]};tools=tools_inventory(old)
    bindings[root/'endpoint-adoption.json']=sha(root/'endpoint-adoption.json')
    try:
        programs={}
        for name in PROGRAMS:
            elf=root/'inputs/elfs'/(name+'.elf');elf.parent.mkdir(parents=True,exist_ok=True);elf.write_bytes(archive_bytes(members[f'{name}/O2/{name}.elf']))
            programs[name]={'family':old['programs'][name]['family'],'elf':record(elf,root),'original_record':report['records'][name],
                'upstream_directory':old['programs'][name]['directory'],'mode':'recovered' if name in RECOVER else 'reused'}
            for opt in ('O0','O2'):
                p=root/'inputs/oracles'/name/(opt+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive_bytes(members[f'{name}/{opt}-oracle.json']))
            if name in REUSE:
                for output,source in [('candidates.json',f'{name}/candidates-all-roi/{name}.json'),('trace-summary.json',f'{name}/{name}.jsonl.summary.json'),('fusion.json',f'{name}/fusion-all-roi.json')]:
                    p=root/'inputs/reused'/name/output;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive_bytes(members[source]));programs[name][output.removesuffix('.json').replace('-','_')]=record(p,root)
        for name,r in old['programs'].items():
            for p,h in r['files'].items():
                source='upstream/'+p;out=root/'inputs'/source;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(archive_bytes(members[source]));need(sha(out)==h,'Upstream source differs')
        write(root/'tools.json',tools);write(root/'plan.json',{'schema':'isaforge-v11b-recovery-plan-v1','policy':POLICY,'programs':programs,
            'endpoint_adoption':record(root/'endpoint-adoption.json',root),'old_root':OLD,'upstream_commit':old['upstream_commit'],'reservation_commit':old['reservation_commit'],
            'original_primary':'undefined: empty recursion MAE; never zero','endpoint_amendment':'Input stage only. Requires separate prelabel endpoint/predictor/prediction/label approval after all six input outcomes.',
            'features_predictions_labels_fits_released':False})
        check_hashes(bindings);produced=sorted(p for p in root.rglob('*') if p.is_file());paths=[*bindings,*produced]
        result={'schema':'isaforge-v11b-recovery-preparation-v1','status':'prepared-inputs-only','prepared_at_utc':now(),'files':[{**record(p,root),'git_required':p not in local_payloads()} for p in dict.fromkeys(paths)],
                'policy':POLICY,'original_programs':6,'recovery_programs':2,'reused_programs':4,'native_trace_jobs':0,'feature_jobs':0,'predictions':0,'labels':0,'fits':0}
        write(root/'preparation.json',result);return result
    except BaseException as e:write(root/'preparation-failure.json',{'error':repr(e),'at_utc':now(),'new_labels':0});raise

def validate_preparation(root):
    root=Path(root).resolve();m=read(root/'preparation.json');need(m['schema']=='isaforge-v11b-recovery-preparation-v1' and m['status']=='prepared-inputs-only' and not(root/'preparation-failure.json').exists(),'Complete input preparation required')
    bindings={}
    for e in m['files']:
        p=(root/e['path']).resolve();need(p.is_relative_to(ROOT) and p not in bindings,'Unique repository binding required');bindings[p]=e['sha256'];need(p.stat().st_size==e['bytes'],'Input size changed')
    check_hashes(bindings);old,report,members,paths=old_evidence();plan,tools=read(root/'plan.json'),read(root/'tools.json');validate_tools(tools,old)
    need(plan['schema']=='isaforge-v11b-recovery-plan-v1' and identical(plan['policy'],POLICY) and identical(m['policy'],POLICY) and tuple(plan['programs'])==PROGRAMS,'Exact six-program recovery policy required')
    need(sha(root/'endpoint-adoption.json')==ENDPOINT_SHA and sha(ROOT/'docs/v11b-transfer-protocol.md')==PROTOCOL_SHA and plan['endpoint_adoption']==record(root/'endpoint-adoption.json',root),'Endpoint adoption/protocol differs')
    need(all(type(e['git_required']) is bool and e['git_required']==((root/e['path']).resolve() not in local_payloads()) for e in m['files']),'Only exact declared historical partials may be local-only')
    produced={root/'endpoint-adoption.json',root/'tools.json',root/'plan.json'}|{p for p in (root/'inputs').rglob('*') if p.is_file()}
    need(set(bindings)==set(paths)|set(sources())|produced,'Exact preparation source/input closure required')
    expected_files=set()
    for name in PROGRAMS:
        r=plan['programs'][name];need(identical(r['original_record'],report['records'][name]) and r['family']==old['programs'][name]['family'] and r['mode']==('recovered' if name in RECOVER else 'reused') and r['upstream_directory']==old['programs'][name]['directory'],'Original program identity differs')
        p=root/'inputs/elfs'/(name+'.elf');expected_files.add(p);need(r['elf']==record(p,root) and sha(p)==report['records'][name]['O2_build']['elf_sha256'],'Prepared ELF differs')
        for opt in ('O0','O2'):
            p=root/'inputs/oracles'/name/(opt+'.json');expected_files.add(p);need(sha(p)==members[f'{name}/{opt}-oracle.json']['sha256'],'Original oracle differs')
        if name in REUSE:
            for output,source in [('candidates.json',f'{name}/candidates-all-roi/{name}.json'),('trace-summary.json',f'{name}/{name}.jsonl.summary.json'),('fusion.json',f'{name}/fusion-all-roi.json')]:
                p=root/'inputs/reused'/name/output;expected_files.add(p);need(sha(p)==members[source]['sha256'] and r[output.removesuffix('.json').replace('-','_')]==record(p,root),'Reused evidence bytes differ')
        for p,h in old['programs'][name]['files'].items():q=root/'inputs/upstream'/p;expected_files.add(q);need(sha(q)==h,'Prepared upstream source differs')
    need(expected_files=={p for p in (root/'inputs').rglob('*') if p.is_file()},'Exact no-extra prepared files required')
    bindings[root/'preparation.json']=sha(root/'preparation.json');return m,plan,tools,bindings

def validate_approval(root,approval):
    root=Path(root).resolve();need(Path(approval).resolve()==root/'recovery-approval.json','Exact recovery approval path required');m,plan,tools,bindings=validate_preparation(root);a=read(approval)
    expected={'status':'approved-v11b-input-only-recovery','preparation_sha256':sha(root/'preparation.json'),'plan_sha256':sha(root/'plan.json'),'tools_sha256':sha(root/'tools.json'),'runner_sha256':sha(__file__),'maximum_new_captures':2,'maximum_labels':0}
    need(all(k in a and identical(a[k],v) for k,v in expected.items()) and type(a.get('freeze_commit')) is str and re.fullmatch('[0-9a-f]{40}',a['freeze_commit']) and utc(a['reviewed_at_utc'])>=utc(m['prepared_at_utc']),'Exact reviewed commit-bound input-only approval required')
    for p,h in bindings.items():
        if p in local_payloads():continue
        b=subprocess.check_output(['git','show',a['freeze_commit']+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT);need(hashlib.sha256(b).hexdigest()==h,'Frozen Git bytes differ')
    bindings[Path(approval).resolve()]=sha(approval);return m,plan,tools,a,bindings


def local_payloads():
    manifest=read(ROOT/OLD/'raw-evidence-manifest.json')
    return {ROOT/'generated/v11-reserved-inputs/attempt-0000'/e['path'] for e in manifest['omitted_local_failed_partials']}

def resource_guard(root,attempt):
    try:
        spool.check_resources(attempt)
        total=0
        for folder in (Path(root),Path(attempt)):
            for p in folder.rglob('*'):
                need(not p.is_symlink(),'Symlink in owned attempt')
                if not p.is_file():continue
                size=p.stat().st_size;total+=size
                cap=POLICY['raw_gzip_bytes_per_program'] if '.gz' in p.name else POLICY['metadata_archive_bytes'] if p.name=='metadata.zip' else POLICY['metadata_log_bytes_per_file']
                need(size<=cap,'Stage/file byte budget reached: '+str(p))
        need(total<=POLICY['attempt_bytes'],'Whole-attempt byte budget reached including result metadata')
    except ValueError as e:raise AbortRun(str(e)) from e

def provenance_guard(bindings,tools):
    check_hashes(bindings)
    try:validate_tools(tools,read(ROOT/OLD/'input-plan.json'))
    except Exception as e:raise AbortRun('Native tool/runtime changed: '+repr(e)) from e


def stage_paths(root,name,phase):
    need(name in RECOVER and phase in ('decode','extract'),'Fixed recovery program/stage required');base=ROOT/PREFIX/name
    return base,base/(phase+'-worker.json'),base/(phase+'-worker.log')

def worker(root,name,phase,claim_sha256):
    root=Path(root).resolve();claim=read(root/'recovery-claim.json');need(claim_sha256==sha(root/'recovery-claim.json') and claim['runner_sha256']==sha(__file__) and claim['preparation_sha256']==sha(root/'preparation.json'),'Owned worker claim/source differs')
    plan,tools=read(root/'plan.json'),read(root/'tools.json');base,_,_=stage_paths(root,name,phase);entry=plan['programs'][name];elf=(root/entry['elf']['path']).resolve();need(sha(elf)==entry['elf']['sha256'],'Worker ELF changed')
    capture=read(base/'capture/capture.json');raw=base/'capture/raw-spike.log.gz';need(capture['status']=='captured-not-validated' and sha(raw)==capture['raw_sha256'],'Complete captured raw bytes required')
    if phase=='decode':spool.decode_raw(raw,base/'decode');return
    decoded=read(base/'decode/decode.json');need(decoded['validated'] is True and sha(raw)==decoded['raw_sha256'] and sha(base/'decode/decoded.jsonl.gz')==decoded['decoded_sha256'],'Validated decoder bytes required')
    counts=decoded['pc_counts'];need(len({pc for pc,n in counts})==len(counts) and all(type(pc) is int and pc>=0 and type(n) is int and n>0 for pc,n in counts) and sum(n for pc,n in counts)==decoded['trace_instructions'],'Complete measured PC counts required')
    folder=base/'extract';need(not folder.exists(),'Fresh extraction required');folder.mkdir()
    values=original.output((base/'capture/htif.stdout.log').read_text());need(values==entry['original_record']['captured_outputs'],'Exact retained O0/O2 snapshot mismatch')
    oracle=original.validate_output(name,values,root/'inputs/upstream'/entry['upstream_directory']);write(folder/'oracle.json',oracle)
    program=readProgram(elf,tools['executables']['objdump']['path']);write(folder/'program.json',{str(pc):r for pc,r in program.items()})
    disassembly=subprocess.run([tools['executables']['objdump']['path'],'-d',str(elf)],capture_output=True,text=True,check=True)
    (folder/'disassembly.txt').write_text(disassembly.stdout);(folder/'disassembly.stderr.log').write_text(disassembly.stderr)
    runs=Counter(dict(counts));starts=set(decoded['block_starts']);previous=None
    for pc in sorted(program):
        symbol=program[pc].get('symbol')
        if symbol!=previous:starts.add(pc)
        previous=symbol
    rows=extractCandidates(program,runs,starts,maxSize=4,limit=None);cdir=folder/'candidates-all-roi';write(cdir/(name+'.json'),rows)
    pdir=folder/'programs';pdir.mkdir();shutil.copyfile(elf,pdir/(name+'.elf'))
    fusion=verify_candidates(cdir,pdir,tools['executables']['objdump']['path'],vectors=16,seed=2026101507);write(folder/'fusion-all-roi.json',fusion)
    need(fusion['passed'] is True and fusion['seed']==2026101507 and len(fusion['benchmarks'])==1 and fusion['benchmarks'][0]['benchmark']==name and fusion['benchmarks'][0]['vectors_per_occurrence']==16
         and fusion['benchmarks'][0]['skipped_opaque_block_occurrences']==0,'Full original fusion coverage required')
    need(fusion['benchmarks'][0]['checked_occurrences']==sum(len(r['occurrences']) for r in rows),'Fusion occurrence coverage differs')
    write(folder/'extraction.json',{'schema':'isaforge-v11b-extraction-v1','program':name,'candidate_count':len(rows),'candidate_sha256':sha(cdir/(name+'.json')),
        'fusion_sha256':sha(folder/'fusion-all-roi.json'),'oracle_sha256':sha(folder/'oracle.json'),'elf_sha256':sha(elf),'decode_sha256':sha(base/'decode/decode.json'),
        'program_sha256':sha(folder/'program.json'),'disassembly_sha256':sha(folder/'disassembly.txt'),'static_objdump_calls':3,'maxSize':4,'limit':None,'fusion_vectors':16,'fusion_seed':2026101507,'complete':True})


def run_worker(root,name,phase,attempt,tools):
    base,record_path,log=stage_paths(root,name,phase);need(not record_path.exists() and not log.exists(),'Single fresh worker per stage required')
    command=[sys.executable,str(Path(__file__).resolve()),'worker','--root',str(root),'--program',name,'--phase',phase,'--claim-sha256',sha(root/'recovery-claim.json')]
    timeout=POLICY['offline_seconds' if phase=='decode' else 'extraction_seconds'];started=now();began=time.monotonic();process=None;primary=None;errors=[];remaining=[]
    try:
        with log.open('xb') as stream:
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=tools['environment'],start_new_session=True)
            while process.poll() is None:
                resource_guard(root,attempt)
                if time.monotonic()-began>timeout:raise TimeoutError('Owned '+phase+' deadline')
                time.sleep(POLICY['poll_seconds'])
            resource_guard(root,attempt)
            need(process.returncode==0,'Owned '+phase+' failed; log retained')
            need(time.monotonic()-began<=timeout,'Owned worker completed after fixed deadline')
    except BaseException as e:primary=e
    finally:
        if process is not None:errors,remaining=spool.cleanup([(phase,process)])
    result={'schema':'isaforge-v11b-owned-worker-v1','program':name,'phase':phase,'command':command,'started_at_utc':started,'completed_at_utc':now(),
        'elapsed_seconds':time.monotonic()-began,'timeout_seconds':timeout,'returncode':process.returncode if process else None,'primary_error':repr(primary) if primary else None,
        'cleanup_errors':errors,'remaining_owned_children':remaining,'log_sha256':sha(log) if log.exists() else None,'runner_sha256':sha(__file__),
        'claim_sha256':sha(root/'recovery-claim.json'),'complete':primary is None and not errors and not remaining}
    write(record_path,result)
    if primary is not None:raise primary
    need(result['complete'],'Owned worker cleanup incomplete');return result


def pack(root,stage,attempt,done):
    # No raw/decoded gzip (including partial) is written into this archive.
    paths=sorted({*sources(),*(p for p in root.rglob('*') if p.is_file() and not p.is_relative_to(stage)),
                  *(p for p in attempt.rglob('*') if p.is_file()),stage/'programs.json',stage/'completed-rows.json',stage/'completion.json'})
    records=[];archive=stage/'metadata.zip';members=[]
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:
            need(not p.is_symlink(),'Symlink evidence forbidden');large='.gz' in p.name
            r={'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size,'packaged':not large};records.append(r)
            if not large:
                with p.open('rb') as incoming,z.open(r['path'],'w',force_zip64=True) as outgoing:
                    for b in iter(lambda:incoming.read(1024**2),b''):outgoing.write(b);resource_guard(root,attempt)
                members.append({k:r[k] for k in ('path','sha256','bytes')})
            resource_guard(root,attempt)
    resource_guard(root,attempt)
    write(stage/'evidence-manifest.json',{'schema':'isaforge-v11b-recovery-evidence-v1','complete':done['complete'],'files':records,
        'archive':{'path':'metadata.zip','sha256':sha(archive),'bytes':archive.stat().st_size,'members':members},'completion_sha256':sha(stage/'completion.json'),
        'compressed_payloads_duplicated':False,'historical_archives_reused_by_reference':True})


def collect(root,approval):
    root=Path(root).resolve();m,plan,tools,review,bindings=validate_approval(root,approval);stage=root/'run/attempt-0000';attempt=ROOT/PREFIX
    need(not(root/'run').exists() and not(root/'recovery-claim.json').exists() and not attempt.exists(),'Single fresh recovery attempt required; no retry')
    need(spool.free_bytes(ROOT)>=POLICY['startup_free_bytes'],'Startup needs26GiB free')
    stage.mkdir(parents=True);attempt.mkdir(parents=True)
    claim={'schema':'isaforge-v11b-recovery-claim-v1','claimed_at_utc':now(),'preparation_sha256':sha(root/'preparation.json'),'approval_sha256':sha(approval),'runner_sha256':sha(__file__),'maximum_new_captures':2,'new_labels':0}
    need(utc(claim['claimed_at_utc'])>=utc(review['reviewed_at_utc']),'Claim precedes reviewed release');write(root/'recovery-claim.json',claim);bindings[root/'recovery-claim.json']=sha(root/'recovery-claim.json')
    records={};failures=[];interruption=None
    for name in PROGRAMS:
        e=plan['programs'][name];records[name]={'status':e['original_record']['status'] if name in REUSE else 'not-attempted','mode':e['mode'],'family':e['family'],'original_record':e['original_record']}
        if name in REUSE:records[name].update(candidate_file=e['candidates'],candidate_count=e['original_record']['all_roi_count'],trace_summary=e['trace_summary'],fusion=e['fusion'])
    try:
        for i,name in enumerate(RECOVER):
            provenance_guard(bindings,tools);resource_guard(root,attempt)
            base=attempt/name;elf=(root/plan['programs'][name]['elf']['path']).resolve()
            try:
                phase='capture';progress(name,phase,'start')
                capture_started=now();capture_error=None
                try:capture=spool.capture_raw(lambda fd:spool.spike_command(tools['executables']['spike']['path'],elf,fd),base/'capture',attempt,
                    compressor=tools['executables']['gzip']['path'],compressor_sha256=tools['executables']['gzip']['sha256'],environment=tools['environment'],first_program=i==0)
                except BaseException as e:capture_error=e
                finally:
                    base.mkdir(parents=True,exist_ok=True);write(base/'capture-worker.json',{'schema':'isaforge-v11b-capture-worker-v1','program':name,'started_at_utc':capture_started,'completed_at_utc':now(),'runner_sha256':sha(__file__),'claim_sha256':sha(root/'recovery-claim.json'),'capture_sha256':sha(base/'capture/capture.json') if (base/'capture/capture.json').exists() else None,'primary_error':repr(capture_error) if capture_error else None})
                if capture_error is not None:
                    if isinstance(capture_error,ValueError) and str(capture_error).startswith(('Free-space floor','Whole-attempt byte budget','Stage/file byte budget','Startup needs','Symlink in owned')):raise AbortRun(str(capture_error)) from capture_error
                    raise capture_error
                progress(name,phase,'complete')
                provenance_guard(bindings,tools);resource_guard(root,attempt)
                for phase in ('decode','extract'):
                    progress(name,phase,'start');run_worker(root,name,phase,attempt,tools);progress(name,phase,'complete')
                    provenance_guard(bindings,tools);resource_guard(root,attempt)
                x=read(base/'extract/extraction.json');decoded=read(base/'decode/decode.json')
                need(x['complete'] is True and x['elf_sha256']==plan['programs'][name]['elf']['sha256'],'Complete unchanged original input required')
                records[name].update(status='complete' if x['candidate_count'] else 'empty',candidate_count=x['candidate_count'],candidate_file=record(base/'extract/candidates-all-roi'/(name+'.json'),root),
                    capture=record(base/'capture/capture.json',root),decode=record(base/'decode/decode.json',root),extraction=record(base/'extract/extraction.json',root),
                    oracle=record(base/'extract/oracle.json',root),fusion=record(base/'extract/fusion-all-roi.json',root),trace_instructions=decoded['trace_instructions'])
            except BaseException as e:
                progress(name,phase,'failure-retained')
                records[name].update(status='failure-retained',error=repr(e));failures.append({'program':name,'error':repr(e)})
                if not isinstance(e,Exception) or isinstance(e,AbortRun):raise
            provenance_guard(bindings,tools);resource_guard(root,attempt)
    except BaseException as e:
        failures.append({'stage':'stop','error':repr(e)})
        if not isinstance(e,Exception):interruption=e
    completed=[]
    for name,r in records.items():
        if r['status'] in ('complete','empty'):
            for row in read(root/r['candidate_file']['path']):completed.append({**row,'benchmark':name,'family':r['family']})
    write(stage/'programs.json',records);write(stage/'completed-rows.json',completed)
    done={'schema':'isaforge-v11b-recovery-completion-v1','complete':not failures and all(r['status'] in ('complete','empty') for r in records.values()),'failures':failures,
        'preparation_sha256':sha(root/'preparation.json'),'plan_sha256':sha(root/'plan.json'),'tools_sha256':sha(root/'tools.json'),'approval_sha256':sha(approval),
        'claim_sha256':sha(root/'recovery-claim.json'),'runner_sha256':sha(__file__),'freeze_commit':review['freeze_commit'],'program_count':6,'reused_program_count':4,
        'recovery_program_count':2,'capture_records':len(list(attempt.glob('*/capture/capture.json'))),'programs_sha256':sha(stage/'programs.json'),'completed_rows_sha256':sha(stage/'completed-rows.json'),
        'completed_program_formula_rows':len(completed),'original_primary':'undefined: empty recursion MAE; never zero','completed_at_utc':now(),
        'new_features':0,'new_predictions':0,'new_labels':0,'new_fits':0}
    try:provenance_guard(bindings,tools);resource_guard(root,attempt)
    except BaseException as e:done={**done,'complete':False,'failures':[*failures,{'stage':'final-provenance-resource','error':repr(e)}]}
    write(stage/'completion.json',done)
    try:pack(root,stage,attempt,done);resource_guard(root,attempt);provenance_guard(bindings,tools)
    except BaseException as e:done={**done,'complete':False,'failures':[*done['failures'],{'stage':'archive-final','error':repr(e)}]}
    write(root/'completion.json',done)
    if interruption is not None:raise interruption
    need(done['complete'],'Incomplete V11b input attempt retained; no features/predictions/labels released');return done


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','validate','collect','worker'));p.add_argument('--root',type=Path,required=True);p.add_argument('--approval',type=Path);p.add_argument('--program',choices=RECOVER);p.add_argument('--phase',choices=('decode','extract'));p.add_argument('--claim-sha256')
    a=p.parse_args()
    if a.action=='worker':worker(a.root,a.program,a.phase,a.claim_sha256);sys.exit(0)
    if a.action=='collect':
        if a.approval is None:p.error('collect requires exact root/recovery-approval.json')
        r=collect(a.root,a.approval)
    elif a.action=='prepare':r=prepare(a.root)
    else:
        m,plan,tools,b=validate_preparation(a.root);r={'status':'valid','bound_files':len(b),'new_labels':0}
    print(json.dumps(r,indent=2,allow_nan=False))

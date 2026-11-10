#!/usr/bin/env python3
"""Stage-specific reviewed V6 original-RTL measurement and portable evidence."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import signal
import subprocess
import sys
import threading
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluate_v6 import read,write,sha,now,validate_point_freeze,validate_review,SCOPES
from isaforge.rtl import generate_rtl
PREFIX='generated/v6-measurements/'
WORKER='''import json,sys
from pathlib import Path
p=json.loads(sys.argv[1])
if p['kind']=='verify':
 from isaforge.v4_validation import verify_wrapping
 result=verify_wrapping(p['formulas'],Path(p['folder']),seed=p['seed'],random_vectors=2048,timeout=300)
else:
 from isaforge.v4_corpus import _ice40
 result=_ice40(p['formula'],Path(p['folder']),p['executable'],p['version'])
Path(p['result']).write_text(json.dumps(result,allow_nan=False))
'''

class OwnedWorkers:
    def __init__(self):self.lock=threading.Lock();self.active=set();self.cancelled=False
    def launch(self,command,stream):
        with self.lock:
            if self.cancelled:raise RuntimeError('V6 measurement attempt canceled')
            process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            self.active.add(process.pid);return process
    def cancel(self):
        with self.lock:
            self.cancelled=True
            for pid in self.active:
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass
    def finished(self,pid):
        with self.lock:self.active.discard(pid)

def run_owned(payload,log,owner=None,timeout=360):
    owner=owner or OwnedWorkers();log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    result=log.with_suffix('.result.json');payload={**payload,'result':str(result)}
    with log.open('wb') as stream:
        process=owner.launch([sys.executable,'-c',WORKER,json.dumps(payload)],stream)
        try:
            if process.wait(timeout=timeout):raise RuntimeError(f"Owned {payload['kind']} worker failed; see {log}")
        finally:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();owner.finished(process.pid)
    return read(result)

def collect(root,scope,review_path,generated=None,workers=2):
    root,review_path=Path(root).resolve(),Path(review_path).resolve()
    if scope not in SCOPES or not 1<=workers<=4:raise ValueError('Known stage and one through four workers required')
    if scope=='calibration' and ((root/'calibration-freeze.json').exists() or (root/'corpus/test/label-release.json').exists()):raise ValueError('Calibration labels are immutable after calibration freeze or test release')
    point,rows,_,_,_=validate_point_freeze(root)
    review=validate_review(root,scope,review_path);directory=root/'corpus'/scope
    if review_path!=directory/'label-approval.json':raise ValueError('Keep stage approval inside the exact cohort')
    if (directory/'completion.json').exists() and read(directory/'completion.json').get('complete') is True:raise ValueError('Completed original measurements are immutable')
    generated=(ROOT/PREFIX/scope) if generated is None else Path(generated).resolve()
    if not generated.resolve().is_relative_to(ROOT/PREFIX/scope):raise ValueError('Use owned generated V6 stage directory')
    executable=shutil.which('yosys')
    if executable is None:raise RuntimeError('Yosys required')
    version=subprocess.check_output([executable,'-V'],text=True).strip();tool_sha=sha(executable)
    if version!=point['frozen_tool']['version'] or tool_sha!=point['frozen_tool']['executable_sha256']:raise ValueError('Frozen target tool identity differs')
    approval={'scope':scope,'freeze_sha256':review['freeze_sha256'],'freeze_commit':review['freeze_commit'],
              'point_freeze_sha256':sha(root/'point-freeze.json'),'candidate_sha256':sha(directory/'candidates.json'),
              'parent_review':review,'review_sha256':sha(review_path),'authorized_after_parent_review':True}
    release_path=directory/'label-release.json'
    if release_path.exists():
        release=read(release_path)
        if any(release.get(k)!=v for k,v in approval.items()):raise ValueError('Existing release differs from this approved stage')
    else:release={**approval,'released_at_utc':now()};write(release_path,release)
    index=0
    while (directory/f'attempt-{index:04d}').exists() or (generated/f'attempt-{index:04d}').exists():index+=1
    attempt=f'attempt-{index:04d}';output=directory/attempt;scratch=generated/attempt
    output.mkdir(parents=True);scratch.mkdir(parents=True)
    formulas=sorted({r['formula'] for r in rows[scope]})
    if len(formulas)!=192:raise ValueError('Exactly192 original stage formulas required')
    owner=OwnedWorkers();failures=[];proofs=[];measured={};interruption=None
    for offset in range(0,len(formulas),128):
        batch=formulas[offset:offset+128]
        try:
            proof=run_owned({'kind':'verify','formulas':batch,'folder':str(scratch/'verification'/f'batch-{offset:04d}'),
                             'seed':2026101520+(scope=='test')},scratch/f'verification-{offset:04d}-worker.log',owner)
            if (proof.get('verified') is not True or proof.get('formula_count')!=len(batch)
                    or proof.get('vectors_per_formula')!=2148 or proof.get('total_comparisons')!=len(batch)*2148):raise ValueError('Incomplete original RTL verification')
            proofs.append(proof)
        except BaseException as error:
            failures.append({'stage':'verification','batch_start':offset,'error':f'{type(error).__name__}: {error}'})
            if not isinstance(error,Exception):owner.cancel();interruption=error
            break
    write(output/'verification.json',proofs)

    def measure(formula):
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        # Every attempt starts in a fresh directory. No consumed label cache,
        # prior attempt metric, or source-cohort measurement may substitute.
        if folder.exists():raise ValueError('Fresh target directory already exists')
        metric=run_owned({'kind':'map','formula':formula,'folder':str(folder),'executable':executable,'version':version},folder/'worker.log',owner)
        metric['tool_sha256']=tool_sha
        if metric['rtl_sha256']!=hashlib.sha256(generate_rtl(formula).encode()).hexdigest():raise ValueError('Original RTL changed')
        write(folder/'metrics.json',metric);return metric
    if not failures:
        pool=ThreadPoolExecutor(max_workers=workers)
        try:
            futures={pool.submit(measure,f):f for f in formulas}
            for future in as_completed(futures):
                formula=futures[future]
                try:measured[formula]=future.result()
                except Exception as error:failures.append({'stage':'synthesis','formula':formula,'error':f'{type(error).__name__}: {error}'})
                write(output/'progress.json',{'unique_completed':len(measured),'unique_total':192,'failures':failures})
        except BaseException as error:
            owner.cancel();interruption=error;failures.append({'stage':'cancellation','error':f'{type(error).__name__}: {error}'})
        finally:pool.shutdown(wait=True,cancel_futures=True)
    unique=[measured[f] for f in formulas if f in measured]
    labels=[{**row,'lut4_count':measured[row['formula']]['ice40_lut4_count'],'carry_count':measured[row['formula']]['ice40_carry_count'],
             'rtl_sha256':measured[row['formula']]['rtl_sha256'],'measurement_source':'rtl_synthesis','correctness_verified':True,'synthesis_tool':version}
            for row in rows[scope] if row['formula'] in measured]
    write(output/'unique-measurements.json',unique);write(output/'dataset.json',labels)
    done={'complete':not failures and len(unique)==192 and len(labels)==192,'failures':failures,'scope':scope,'attempt':attempt,
          'unique_formula_count':len(unique),'weighted_row_count':len(labels),'release':release,
          'dataset_sha256':sha(output/'dataset.json'),'verification_sha256':sha(output/'verification.json'),
          'unique_measurements_sha256':sha(output/'unique-measurements.json'),'collector_sha256':sha(__file__),
          'tool':version,'tool_sha256':tool_sha,'original_rtl_only':True,'legacy_measurements_reused':False,
          'scratch_directory':os.path.relpath(scratch,root),'completed_at_utc':now()}
    write(output/'completion.json',done);write(directory/'completion.json',done)
    if interruption is not None:raise interruption
    if not done['complete']:raise RuntimeError('Incomplete V6 measurements retained; calibration/scoring blocked')
    pack(root,scope);return done

def destination(name,root,scope):
    prefix=PREFIX+scope+'/';path=PurePosixPath(name);root=Path(root).resolve()
    if scope not in SCOPES or not name.startswith(prefix) or path.is_absolute() or '..' in path.parts or '\\' in name:raise ValueError('Unexpected V6 archive path')
    allowed=(root/prefix).resolve();target=root.joinpath(*path.parts)
    if not allowed.is_relative_to(root) or not target.resolve().is_relative_to(allowed):raise ValueError('V6 archive escapes owned stage')
    return target

def pack(root,scope):
    root=Path(root).resolve();directory=root/'corpus'/scope;done=read(directory/'completion.json')
    if done.get('complete') is not True or done['failures']:raise ValueError('Only complete original evidence can be archived')
    scratch=(root/done['scratch_directory']).resolve()
    if not scratch.is_relative_to(ROOT/PREFIX/scope):raise ValueError('Unexpected original evidence directory')
    archive=directory/'raw-evidence.zip';manifest_path=directory/'raw-evidence.json'
    if archive.exists() or manifest_path.exists():raise ValueError('Completed evidence archive is immutable')
    records=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(scratch.rglob('*')):
            if not path.is_file() or {'obj_dir','obj_dir_wrapv'}.intersection(path.parts):continue
            name=path.relative_to(ROOT).as_posix();destination(name,ROOT,scope);data=path.read_bytes()
            info=zipfile.ZipInfo(name,date_time=(2026,10,14,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data,compresslevel=9);records.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    result={'schema':'isaforge-v6-evidence-v1','scope':scope,'archive':archive.name,'archive_sha256':sha(archive),'files':records,
            'completion_sha256':sha(directory/'completion.json'),'compiler_objects_included':False}
    write(manifest_path,result);return result

def restore(root,scope,repository=ROOT):
    root,repository=Path(root).resolve(),Path(repository).resolve();directory=root/'corpus'/scope
    manifest=read(directory/'raw-evidence.json');archive=directory/'raw-evidence.zip'
    if (manifest.get('schema')!='isaforge-v6-evidence-v1' or manifest.get('scope')!=scope or manifest['archive']!=archive.name
            or sha(archive)!=manifest['archive_sha256'] or sha(directory/'completion.json')!=manifest['completion_sha256']):raise ValueError('V6 evidence archive identity differs')
    records={r['path']:r for r in manifest['files']}
    if len(records)!=len(manifest['files']):raise ValueError('Duplicate archive paths')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(records):raise ValueError('V6 archive inventory differs')
        for name in names:
            target=destination(name,repository,scope);data=z.read(name)
            if len(data)!=records[name]['size'] or hashlib.sha256(data).hexdigest()!=records[name]['sha256']:raise ValueError('Changed V6 archived evidence')
            if target.exists() and sha(target)!=records[name]['sha256']:raise ValueError('Existing V6 evidence differs; refusing overwrite')
        for name in names:
            target=destination(name,repository,scope)
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:stream.write(z.read(name))
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('collect','pack','restore'));parser.add_argument('--scope',choices=SCOPES,required=True)
    parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v6');parser.add_argument('--review',type=Path);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.action=='collect':
        if args.review is None:parser.error('collect requires --review')
        result=collect(args.root,args.scope,args.review,workers=args.workers)
    else:result=(pack if args.action=='pack' else restore)(args.root,args.scope)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

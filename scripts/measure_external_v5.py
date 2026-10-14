#!/usr/bin/env python3
"""Measure original external RTL only after an explicitly reviewed Git freeze."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_external_v5 import read,write,sha,now,validate_committed_review
from isaforge.rtl import generate_rtl

# Audited helpers run inside a separately owned process group, including all
# Verilator/compiler/ABC descendants. Always clean the group, even on success.
WORKER='''import json,sys
from pathlib import Path
p=json.loads(sys.argv[1])
if p['kind']=='verify':
 from isaforge.v4_validation import verify_wrapping
 result=verify_wrapping(p['formulas'],Path(p['folder']),seed=2026101507,random_vectors=2048,timeout=300)
else:
 from isaforge.v4_corpus import _ice40
 result=_ice40(p['formula'],Path(p['folder']),p['executable'],p['version'])
Path(p['result']).write_text(json.dumps(result,allow_nan=False))
'''


class OwnedWorkers:
    def __init__(self):
        self.lock=threading.Lock();self.active=set();self.cancelled=False

    def launch(self,command,stream):
        with self.lock:
            if self.cancelled:raise RuntimeError('Measurement attempt canceled')
            process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            self.active.add(process.pid)
            return process

    def cancel(self):
        with self.lock:
            self.cancelled=True
            for pid in self.active:
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass

    def finished(self,pid):
        with self.lock:self.active.discard(pid)


def run_owned(payload,log,timeout=360,owner=None):
    owner=owner or OwnedWorkers()
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    result=log.with_suffix('.result.json');payload={**payload,'result':str(result)}
    with log.open('wb') as stream:
        process=owner.launch([sys.executable,'-c',WORKER,json.dumps(payload)],stream)
        try:
            code=process.wait(timeout=timeout)
            if code:raise RuntimeError(f"Owned {payload['kind']} worker failed ({code}); see {log}")
        finally:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();owner.finished(process.pid)
    return read(result)


def validate_cached(formula,folder,version,tool_sha):
    folder=Path(folder);old=read(folder/'metrics.json')
    if (old.get('formula')!=formula or old.get('tool')!=version or old.get('tool_sha256')!=tool_sha
            or old.get('measurement_source')!='rtl_synthesis'
            or old.get('rtl_sha256')!=hashlib.sha256(generate_rtl(formula).encode()).hexdigest()
            or any(sha(folder/name)!=old[key] for name,key in
                   [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),
                    ('ice40.ys','script_sha256'),('ice40.log','log_sha256')])):
        raise ValueError('Existing original-circuit cache has changed or unbound provenance')
    return old


def collect(root,generated,review_path,workers=2):
    root,generated,review_path=map(lambda p:Path(p).resolve(),(root,generated,review_path))
    manifest,rows,_,_,review=validate_committed_review(root,review_path)
    if review_path!=root/'label-approval.json':raise ValueError('Keep explicit parent approval at bundle/label-approval.json')
    executable=shutil.which('yosys')
    if executable is None:raise RuntimeError('Yosys required')
    version=subprocess.check_output([executable,'-V'],text=True).strip();tool_sha=sha(executable)
    expected=manifest['measurement_tool']
    if version!=expected['version'] or tool_sha!=expected['executable_sha256']:
        raise ValueError('Target measurement tool differs from frozen identity')
    directory=root/'measurements'
    if (directory/'completion.json').exists() and read(directory/'completion.json').get('complete'):
        raise ValueError('Completed external measurement is immutable')
    approval={'freeze_sha256':sha(root/'freeze.json'),'candidate_sha256':manifest['candidate_sha256'],
              'freeze_commit':review['freeze_commit'],'review_sha256':sha(review_path),
              'parent_review':review,'authorized_after_parent_review':True}
    release_path=root/'label-release.json'
    if release_path.exists():
        release=read(release_path)
        if any(release.get(key)!=value for key,value in approval.items()):
            raise ValueError('Existing release belongs to another reviewed freeze')
    else:
        release={**approval,'released_at_utc':now()};write(release_path,release)
    # Each retry retains separate verification, logs, circuits and partial labels.
    index=0
    while (directory/f'attempt-{index:04d}').exists() or (generated/f'attempt-{index:04d}').exists():index+=1
    attempt=f'attempt-{index:04d}';output=directory/attempt;scratch=generated/attempt
    output.mkdir(parents=True);scratch.mkdir(parents=True)
    formulas=sorted({r['formula'] for r in rows});failures=[];measured={};verification=[]
    owner=OwnedWorkers();interruption=None
    try:
        proof=run_owned({'kind':'verify','formulas':formulas,'folder':str(scratch/'verification')},scratch/'verification-worker.log',owner=owner)
        if (proof.get('verified') is not True or proof.get('formula_count')!=79
                or proof.get('vectors_per_formula')!=2148 or proof.get('total_comparisons')!=79*2148):
            raise ValueError('RTL verification coverage did not pass')
        verification.append(proof)
    except BaseException as error:
        failures.append({'stage':'rtl_verification','error':f'{type(error).__name__}: {error}'})
        if not isinstance(error,Exception):owner.cancel();interruption=error
    write(output/'verification.json',verification)

    def measure(formula):
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        if (folder/'metrics.json').exists():return validate_cached(formula,folder,version,tool_sha)
        metrics=run_owned({'kind':'map','formula':formula,'folder':str(folder),'executable':executable,'version':version},folder/'worker.log',owner=owner)
        metrics['tool_sha256']=tool_sha;write(folder/'metrics.json',metrics)
        return validate_cached(formula,folder,version,tool_sha)

    if not failures:
        pool=ThreadPoolExecutor(max_workers=workers)
        try:
            futures={pool.submit(measure,formula):formula for formula in formulas}
            for future in as_completed(futures):
                formula=futures[future]
                try:measured[formula]=future.result()
                except Exception as error:failures.append({'stage':'synthesis','formula':formula,'error':f'{type(error).__name__}: {error}'})
                write(output/'progress.json',{'unique_completed':len(measured),'unique_total':79,'failures':failures})
        except BaseException as error:
            owner.cancel();interruption=error
            failures.append({'stage':'cancellation','error':f'{type(error).__name__}: {error}'})
        finally:pool.shutdown(wait=True,cancel_futures=True)
    unique=[{'formula':formula,**measured[formula]} for formula in formulas if formula in measured]
    labels=[{**row,'lut4_count':measured[row['formula']]['ice40_lut4_count'],
             'carry_count':measured[row['formula']]['ice40_carry_count'],'measurement_source':'rtl_synthesis',
             'correctness_verified':True,'rtl_sha256':measured[row['formula']]['rtl_sha256'],'synthesis_tool':version}
            for row in rows if row['formula'] in measured]
    write(output/'unique-measurements.json',unique);write(output/'dataset.json',labels)
    completion={'complete':not failures and len(unique)==79 and len(labels)==80,'failures':failures,'attempt':attempt,
                'unique_formula_count':len(unique),'program_formula_count':len(labels),'release':release,
                'dataset_sha256':sha(output/'dataset.json'),'verification_sha256':sha(output/'verification.json'),
                'unique_measurements_sha256':sha(output/'unique-measurements.json'),'collector_sha256':sha(__file__),
                'tool':version,'tool_sha256':tool_sha,'original_rtl_only':True,'scratch_directory':os.path.relpath(scratch,root)}
    write(output/'completion.json',completion);write(directory/'completion.json',completion)
    if interruption is not None:raise interruption
    if not completion['complete']:raise RuntimeError('Incomplete measurement; failures retained and scoring blocked')
    return completion


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5-external')
    parser.add_argument('--generated',type=Path,default=ROOT/'generated/external-v5/target-measurements')
    parser.add_argument('--review',type=Path,required=True,help='Parent approval naming the committed freeze SHA')
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.workers<1:parser.error('workers must be positive')
    result=collect(args.root,args.generated,args.review,args.workers)
    print({'unique_original_circuits':result['unique_formula_count'],'weighted_program_rows':result['program_formula_count']})


if __name__=='__main__':main()

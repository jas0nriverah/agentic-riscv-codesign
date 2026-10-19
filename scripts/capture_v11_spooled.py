#!/usr/bin/env python3
"""Unreleased V11 streaming-capture engineering helpers, not a cohort runner.

No default workload, CLI capture, model, extractor or area-label action exists.
A future reviewed collector must authenticate inputs/approval and call these
helpers for the two fixed missing programs. Tests use tiny synthetic producers.
"""
from __future__ import annotations
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]
from tracing import parse_trace
from run_holdout_benchmarks import CountedTrace

GIB=1024**3
POLICY={'workers':1,'capture_seconds':300,'compressor_drain_seconds':30,'offline_seconds':1800,
        'cleanup_seconds_per_child':5,'poll_seconds':0.25,'startup_free_bytes':26*GIB,
        'later_program_startup_free_bytes':18*GIB,'minimum_free_bytes':8*GIB,'raw_gzip_bytes_per_program':4*GIB,
        'decoded_gzip_bytes_per_program':4*GIB,'attempt_bytes':18*GIB,
        'metadata_log_bytes_per_file':16*1024**2,'retries':0}


def need(value,message):
    if not value:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def free_bytes(path):
    v=os.statvfs(path);return v.f_bavail*v.f_frsize

def check_resources(attempt,*,files=()):
    need(free_bytes(attempt)>=POLICY['minimum_free_bytes'],'Free-space floor reached')
    total=0
    for p in Path(attempt).rglob('*'):
        need(not p.is_symlink(),'Symlink in owned attempt')
        if p.is_file():total+=p.stat().st_size
    need(total<=POLICY['attempt_bytes'],'Whole-attempt byte budget reached')
    for p,cap in files:
        if Path(p).exists():need(Path(p).stat().st_size<=cap,'Stage/file byte budget reached: '+str(p))

def cleanup(processes):
    """Return every cleanup error; never replace the primary failure."""
    errors=[];remaining=[]
    for name,p in processes:
        deadline=time.monotonic()+POLICY['cleanup_seconds_per_child'];kill_failed=False
        # A reaped leader does not imply its owned process group is empty:
        # descendants can still hold the commit pipe. Never gate killpg on poll().
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        except BaseException as e:
            kill_failed=True;errors.append({'process':name,'operation':'killpg','error':repr(e)})
        try:p.wait(timeout=max(0,deadline-time.monotonic()))
        except BaseException as e:errors.append({'process':name,'operation':'wait','error':repr(e)})
        group_alive=False
        if not kill_failed:
            while True:
                try:os.killpg(p.pid,0)
                except ProcessLookupError:break
                except BaseException as e:
                    errors.append({'process':name,'operation':'group-probe','error':repr(e)});group_alive=True;break
                if time.monotonic()>=deadline:group_alive=True;break
                time.sleep(min(.01,max(0,deadline-time.monotonic())))
        if p.poll() is None:remaining.append({'process':name,'pid':p.pid})
        elif group_alive or kill_failed:remaining.append({'process':name,'pid':p.pid,'scope':'owned-process-group'})
    return errors,remaining

def spike_command(spike,elf,commit_fd):
    return [str(spike),'--isa=rv32im_zicntr','-m16','--log-commits',f'--log=/dev/fd/{commit_fd}',str(elf)]

def capture_raw(command_factory,folder,attempt,*,compressor,compressor_sha256,environment,first_program=True):
    """Direct producer FD -> native gzip; Python only supervises, never decodes.

    command_factory is explicit to allow deterministic tiny producer fixtures.
    It is NOT a scientific input authorization; a sealed cohort adapter must use
    exactly spike_command with the already-built authenticated original O2 ELF.
    Byte/disk guards poll0.25s and can overshoot by bytes written between polls.
    """
    folder,attempt=Path(folder).resolve(),Path(attempt).resolve()
    need(folder.is_relative_to(attempt) and folder!=attempt and not folder.exists(),'Fresh child directory in owned attempt required')
    need(attempt.is_relative_to(ROOT/'generated/v11-spooled-recovery'),'Dedicated recovery attempt required')
    need(sha(compressor)==compressor_sha256,'Pinned native compressor differs')
    need(type(first_program) is bool,'Explicit first/later program flag required')
    threshold=POLICY['startup_free_bytes' if first_program else 'later_program_startup_free_bytes']
    need(free_bytes(attempt)>=threshold,'Startup needs26GiB free initially or18GiB before second program')
    folder.mkdir(parents=True);read_fd,write_fd=os.pipe();processes=[];primary=None;cleanup_errors=[];remaining=[]
    raw=folder/'raw-spike.log.gz.partial';stdout=folder/'htif.stdout.log';stderr=folder/'spike.stderr.log';ziplog=folder/'compressor.stderr.log'
    started=time.monotonic();spike_done_at=None
    compressor_command=[str(compressor),'-1','-n','-c'];producer_command=None
    try:
        with raw.open('xb') as compressed,stdout.open('xb') as out,stderr.open('xb') as err,ziplog.open('xb') as zerr:
            zipper=subprocess.Popen(compressor_command,stdin=read_fd,stdout=compressed,stderr=zerr,env=environment,start_new_session=True)
            processes.append(('compressor',zipper));os.close(read_fd);read_fd=None
            producer_command=list(command_factory(write_fd));producer=subprocess.Popen(producer_command,stdout=out,stderr=err,
                env=environment,pass_fds=(write_fd,),start_new_session=True)
            processes.append(('producer',producer));os.close(write_fd);write_fd=None
            while True:
                p,z=producer.poll(),zipper.poll();elapsed=time.monotonic()-started
                check_resources(attempt,files=[(raw,POLICY['raw_gzip_bytes_per_program']),
                    *[(x,POLICY['metadata_log_bytes_per_file']) for x in (stdout,stderr,ziplog)]])
                if z is not None and z!=0:raise RuntimeError('Native compressor failed: '+str(z))
                if p is not None:
                    if p!=0:raise RuntimeError('Trace producer failed: '+str(p))
                    if spike_done_at is None:
                        if elapsed>POLICY['capture_seconds']:raise TimeoutError('Producer completion observed after capture deadline')
                        spike_done_at=time.monotonic()
                    if z==0:break
                    if time.monotonic()-spike_done_at>POLICY['compressor_drain_seconds']:raise TimeoutError('Compressor drain deadline')
                elif elapsed>POLICY['capture_seconds']:raise TimeoutError('Trace capture deadline')
                time.sleep(POLICY['poll_seconds'])
    except BaseException as e:primary=e
    finally:
        for fd in (read_fd,write_fd):
            if fd is not None:
                try:os.close(fd)
                except BaseException as e:cleanup_errors.append({'operation':'close-parent-fd','error':repr(e)})
        errors,remaining=cleanup(processes);cleanup_errors+=errors
    captured=primary is None and not cleanup_errors and not remaining
    final=folder/'raw-spike.log.gz'
    if captured:raw.rename(final)
    result={'schema':'isaforge-v11-spooled-capture-v1','status':'captured-not-validated' if captured else 'failure-retained',
        'producer_command':producer_command,'compressor_command':compressor_command,'compressor_sha256':compressor_sha256,
        'environment':dict(environment),'capture_and_drain_wall_seconds':time.monotonic()-started,
        'producer_returncode':next((p.returncode for n,p in processes if n=='producer'),None),
        'compressor_returncode':next((p.returncode for n,p in processes if n=='compressor'),None),
        'primary_error':repr(primary) if primary else None,'cleanup_errors':cleanup_errors,'remaining_owned_children':remaining,
        'raw_path':(final if captured else raw).name,'raw_sha256':sha(final if captured else raw) if (final if captured else raw).exists() else None,
        'raw_bytes':(final if captured else raw).stat().st_size if (final if captured else raw).exists() else 0,
        'scope':'Byte capture only; no marker/CRC/ROI/output validation, extraction, model prediction or target label.'}
    write(folder/'capture.json',result)
    if primary is not None:raise primary
    need(captured,'Capture cleanup failed; retained partial is not valid')
    return result


def decode_raw(raw,folder):
    """Unchanged parser/counter, gzip streamed through EOF with strict UTF8.

    Must run in one separately owned1800s child with external disk monitoring;
    this synchronous helper does not itself enforce an execution deadline.
    No candidate extraction occurs here. Full HTIF/oracle checks and exact ELF
    identity remain the future cohort adapter's mandatory separate gate.
    """
    raw,folder=Path(raw),Path(folder);folder.mkdir(parents=True,exist_ok=True)
    partial=folder/'decoded.jsonl.gz.partial';final=folder/'decoded.jsonl.gz'
    need(not partial.exists() and not final.exists(),'Fresh offline decode, no resume/retry')
    with gzip.open(raw,'rt',encoding='utf-8',errors='strict') as commits,gzip.open(partial,'xt',encoding='utf-8',compresslevel=1) as out:
        sink=CountedTrace(out);summary=parse_trace(commits,sink);sink.finish()
    partial.rename(final)
    result={**summary,'raw_sha256':sha(raw),'decoded_sha256':sha(final),'decoded_bytes':final.stat().st_size,
        'parser_sha256':sha(ROOT/'src/tracing.py'),'counter_source_sha256':sha(ROOT/'src/run_holdout_benchmarks.py'),
        'pc_counts':[[pc,n] for pc,n in sorted(sink.runs.items())],'block_starts':sorted(sink.starts),
        'scope':'Validated full-stream marker/decoder/count invariants only; not independent algorithm correctness or admission.'}
    write(folder/'decode.json',result);return result,Counter(sink.runs),set(sink.starts)

"""One blocking subprocess with separately observed UTC and monotonic endpoints.

This module has no workload or model dependencies. Arguments are hash-bound,
not printed or included in error messages. A started receipt precedes dispatch;
terminal receipts preserve failed dispatches, timeouts and interruptions. No
record reconstructs a child end instant from a duration measured elsewhere.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

SCHEMA = 'isaforge-observed-command-v1'
MAX_TIMEOUT_SECONDS = 3600.0
CLEANUP_SECONDS = 5.0


def _json(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode('utf-8')


def _seal(path, value):
    data = json.dumps(value,indent=2,allow_nan=False).encode('utf-8')+b'\n'
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    checksum = hashlib.sha256(data).hexdigest()
    temporary_hash = path.with_name(path.name+'.sha256.tmp')
    with temporary_hash.open('x') as stream:
        stream.write(checksum+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary_hash.replace(path.with_name(path.name+'.sha256'))


def _endpoint():
    before = time.monotonic_ns()
    utc = time.time_ns()
    after = time.monotonic_ns()
    seconds,nanoseconds = divmod(utc,1_000_000_000)
    iso = datetime.fromtimestamp(seconds,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{nanoseconds:09d}+00:00'
    return dict(utc_ns=utc,utc_iso=iso,monotonic_before_ns=before,monotonic_after_ns=after)


def _clock_info():
    result = {}
    for name in ('time','monotonic'):
        clock = time.get_clock_info(name)
        result[name] = dict(implementation=clock.implementation,resolution_seconds=clock.resolution,
            adjustable=clock.adjustable,monotonic=clock.monotonic)
    return result


def _durations(start,end):
    utc = end['utc_ns']-start['utc_ns']
    monotonic = end['monotonic_after_ns']-start['monotonic_after_ns']
    low = end['monotonic_before_ns']-start['monotonic_after_ns']
    high = end['monotonic_after_ns']-start['monotonic_before_ns']
    ordered = (start['monotonic_before_ns'] <= start['monotonic_after_ns'] <=
               end['monotonic_before_ns'] <= end['monotonic_after_ns'])
    return dict(utc_elapsed_ns=utc,monotonic_elapsed_ns=monotonic,
        utc_elapsed_seconds=utc/1_000_000_000,monotonic_elapsed_seconds=monotonic/1_000_000_000,
        monotonic_elapsed_bracket_ns=[low,high],monotonic_endpoints_ordered=ordered,
        utc_minus_monotonic_elapsed_ns=utc-monotonic,
        clock_disagreement_detected=not (ordered and low <= utc <= high),
        disagreement_rule='UTC delta outside the observed monotonic capture bracket; no tolerance or clock correction.',
        uninterrupted_calendar_wall_time_established=False,
        cause='Unresolved; endpoint observations do not distinguish clock adjustment, suspension or other clock behavior.')


def _error(error):
    # Exception repr/str can contain the complete command, including credentials.
    result = dict(type=type(error).__name__)
    if isinstance(error,OSError):
        result['errno'] = error.errno
    return result


def _stop(process):
    """Terminate the new session's process group and reap its direct child."""
    actions = []
    def send(sig):
        try:
            os.killpg(process.pid,sig)
            actions.append(dict(signal=int(sig),result='sent'))
        except ProcessLookupError:
            actions.append(dict(signal=int(sig),result='group absent'))
        except OSError as error:
            actions.append(dict(signal=int(sig),result='failed',error=_error(error)))
            # Still attempt to terminate/reap the direct child if group signaling failed.
            try:
                process.kill()
            except BaseException as child_error:
                actions.append(dict(direct_child_kill_error=_error(child_error)))
    send(signal.SIGTERM)
    try:
        process.wait(timeout=CLEANUP_SECONDS)
    except BaseException as error:
        actions.append(dict(grace_wait_error=_error(error)))
    # The leader may have exited while descendants ignored SIGTERM. Always
    # signal the group again, rather than assuming leader exit implies cleanup.
    send(signal.SIGKILL)
    try:
        process.wait(timeout=CLEANUP_SECONDS)
        reaped = True
    except BaseException as error:
        actions.append(dict(final_wait_error=_error(error)))
        reaped = False
    return dict(actions=actions,direct_child_reaped=reaped,
        scope='New subprocess session/process group; independently detached descendants are outside this proof.')


def run(argv, output: Path, *, cwd, metadata, timeout_seconds=MAX_TIMEOUT_SECONDS):
    """Run once; return terminal records for ordinary failures and nonzero exits.

    KeyboardInterrupt/SystemExit are re-raised after terminal sealing and child
    cleanup. Invalid arguments and existing output paths fail before dispatch.
    The timeout bounds the wait; process-group cleanup may add up to ten seconds.
    """
    if not isinstance(argv,(list,tuple)) or not argv or any(not isinstance(arg,str) or '\x00' in arg for arg in argv):
        raise ValueError('A nonempty argument vector of strings is required')
    if not argv[0]:
        raise ValueError('A nonempty executable is required')
    if not isinstance(metadata,dict):
        raise ValueError('Caller-bound JSON object metadata required')
    if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError('Timeout must be positive, finite and at most 3600 seconds')
    arguments = list(argv)
    # Serialization both validates caller metadata and detaches nested mutable values.
    metadata_copy = json.loads(_json(metadata))
    cwd = Path(cwd).resolve()
    if not cwd.is_dir():
        raise ValueError('Existing working directory required')
    output = Path(output).resolve()
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    stdout = (output/'stdout.txt').open('xb')
    try:
        stderr = (output/'stderr.txt').open('xb')
    except BaseException:
        stdout.close()
        raise
    try:
        observer_os_session = os.getsid(0)
    except (AttributeError,OSError):
        observer_os_session = None
    record = dict(schema=SCHEMA,status='started',returncode=None,
        argv_sha256=hashlib.sha256(_json(arguments)).hexdigest(),argv_count=len(arguments),
        cwd=str(cwd),metadata=metadata_copy,metadata_sha256=hashlib.sha256(_json(metadata_copy)).hexdigest(),
        observer_pid=os.getpid(),observer_session_id=str(uuid.uuid4()),observer_os_session_id=observer_os_session,
        child_pid=None,clock_info=_clock_info(),timeout_seconds=float(timeout_seconds),
        stdout_file='stdout.txt',stderr_file='stderr.txt',start=_endpoint(),end=None,
        scope='Started receipt before dispatch through direct-child reap and stream close; excludes terminal receipt serialization.',
        cross_process_monotonic_origin_verified=False)
    process = None
    interrupted = None
    # Started evidence is immutable even when record.json later becomes terminal.
    try:
        _seal(output/'started.json',record)
        _seal(output/'record.json',record)
        try:
            process = subprocess.Popen(arguments,cwd=str(cwd),stdout=stdout,stderr=stderr,start_new_session=True)
            record['child_pid'] = process.pid
            record['returncode'] = process.wait(timeout=timeout_seconds)
            record['status'] = 'success' if record['returncode'] == 0 else 'nonzero_exit'
        except subprocess.TimeoutExpired as error:
            record.update(status='timed_out',error=_error(error),cleanup=_stop(process))
            record['returncode'] = process.returncode
        except (KeyboardInterrupt,SystemExit) as error:
            record.update(status='interrupted',error=_error(error))
            if process is not None:
                record['cleanup'] = _stop(process)
                record['returncode'] = process.returncode
            interrupted = error
        except Exception as error:
            record.update(status='startup_failed' if process is None else 'failed',error=_error(error))
            if process is not None:
                record['cleanup'] = _stop(process)
                record['returncode'] = process.returncode
    finally:
        stdout.close()
        stderr.close()
        record['end'] = _endpoint()
        record['durations'] = _durations(record['start'],record['end'])
        record['stdout_sha256'] = hashlib.sha256((output/'stdout.txt').read_bytes()).hexdigest()
        record['stderr_sha256'] = hashlib.sha256((output/'stderr.txt').read_bytes()).hexdigest()
        _seal(output/'record.json',record)
    if interrupted is not None:
        raise interrupted
    return record

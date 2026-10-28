"""Tiny synthetic text/process fixtures; no Spike, benchmark, labels or models."""
import gzip
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capture_v11_spooled',ROOT/'scripts/capture_v11_spooled.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture_text():
    return ('startup noncommit\ncore 0: 3 0x80000000 (0xc0202573) x10 0xfffffffe\n'
            'core 0: 3 0x80000004 (0x00150513) x10 0x00000001\n'
            'core 0: 3 0x80000010 (0x00150513) x10 0x00000002\n'
            'core 0: 3 0x80000014 (0xc0202573) x10 0x00000001\npoststop noncommit\n')

def assert_only_permission_race_uncertainty(record):
    """Accept a conservative group marker only for the recorded EPERM race."""
    for child in record['remaining_owned_children']:
        assert child['scope']=='owned-process-group'
        assert any(error['process']==child['process'] and error['operation']=='killpg'
                   and 'PermissionError' in error['error'] for error in record['cleanup_errors'])

def test_fixture_decode_identical_to_unchanged_parser_and_counter(tmp_path):
    raw=tmp_path/'raw.gz';raw.write_bytes(gzip.compress(fixture_text().encode()))
    sink=m.CountedTrace(io.StringIO());expected=m.parse_trace(io.StringIO(fixture_text()),sink);sink.finish()
    result,runs,starts=m.decode_raw(raw,tmp_path/'decode')
    assert all(result[k]==v for k,v in expected.items()) and result['instret_delta']==3
    assert runs==sink.runs and starts==sink.starts=={0x80000004,0x80000010,0x80000014}
    with gzip.open(tmp_path/'decode/decoded.jsonl.gz','rt') as f:assert f.read()==sink.output.getvalue()
    assert [json.loads(s)['seq'] for s in sink.output.getvalue().splitlines()]==[2,3]

@pytest.mark.parametrize('poison',['missing','third','register','delta','unknown','malformed_after_stop','truncated','crc'])
def test_invalid_complete_stream_keeps_partial(tmp_path,poison):
    text=fixture_text()
    if poison=='missing':text=text.replace('0xc0202573','0x00150513',1)
    elif poison=='third':text+='core 0: 3 0x80000018 (0xc0202573) x10 0x00000001\n'
    elif poison=='register':text=text.replace('x10 0xfffffffe','x11 0xfffffffe')
    elif poison=='delta':text=text.replace('x10 0x00000001\npoststop','x10 0x00000002\npoststop')
    elif poison=='unknown':text=text.replace('(0x00150513)','(0xffffffff)',1)
    elif poison=='malformed_after_stop':text+='core malformed\n'
    data=gzip.compress(text.encode())
    if poison=='truncated':data=data[:-4]
    elif poison=='crc':data=data[:-8]+bytes([data[-8]^1])+data[-7:]
    raw=tmp_path/'raw.gz';raw.write_bytes(data)
    with pytest.raises((ValueError,OSError,EOFError)):m.decode_raw(raw,tmp_path/'decode')
    assert (tmp_path/'decode/decoded.jsonl.gz.partial').exists() and not (tmp_path/'decode/decoded.jsonl.gz').exists()


def test_cleanup_preserves_permission_error_and_primary():
    class Child:
        pid=123;returncode=None
        def poll(self):return None
        def wait(self,timeout):raise TimeoutError('unreaped')
    with patch.object(m.os,'killpg',side_effect=PermissionError('injected')):errors,remaining=m.cleanup([('producer',Child())])
    assert [r['operation'] for r in errors]==['killpg','wait'] and remaining==[{'process':'producer','pid':123}]


def test_native_gzip_tiny_synthetic_producer_separates_stdout(tmp_path,monkeypatch):
    """Engineering fixture only: Python emits synthetic bytes; never launches Spike."""
    compressor=shutil.which('gzip')
    if compressor is None:pytest.skip('Native gzip unavailable for tiny transport fixture')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:64*m.GIB)
    monkeypatch.setitem(m.POLICY,'poll_seconds',0.01)
    attempt=tmp_path/'generated/v11-spooled-recovery/fixture';attempt.mkdir(parents=True);folder=attempt/'transport'
    text=fixture_text();factory=lambda fd:[sys.executable,'-c',f'import os;os.write({fd},{text.encode()!r});print("HTIF-ONLY")']
    r=m.capture_raw(factory,folder,attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={'PATH':'/usr/bin:/bin'})
    assert r['status']=='captured-not-validated' and r['producer_returncode']==r['compressor_returncode']==0
    with gzip.open(folder/'raw-spike.log.gz','rt') as f:assert f.read()==text
    assert (folder/'htif.stdout.log').read_text()=='HTIF-ONLY\n'
    assert r['remaining_owned_children']==[]


def test_startup_guard_no_native_before_space(tmp_path,monkeypatch):
    compressor=tmp_path/'gzip';compressor.write_bytes(b'synthetic')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:25*m.GIB)
    attempt=tmp_path/'generated/v11-spooled-recovery/a';attempt.mkdir(parents=True)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('No native before guard'))
    with pytest.raises(ValueError,match='26GiB'):m.capture_raw(lambda fd:[],attempt/'p',attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={})
    assert not (attempt/'p').exists()

@pytest.mark.parametrize('failure',['producer','compressor','deadline','disk','bytes','interrupt'])
def test_tiny_transport_failures_retained_with_reported_cleanup_state(tmp_path,monkeypatch,failure):
    compressor=shutil.which('gzip')
    if compressor is None:pytest.skip('Native gzip unavailable for tiny transport fixture')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:64*m.GIB)
    monkeypatch.setitem(m.POLICY,'poll_seconds',0.01)
    attempt=tmp_path/'generated/v11-spooled-recovery/fixture';attempt.mkdir(parents=True);folder=attempt/'transport'
    factory=lambda fd:[sys.executable,'-c',f'import os;os.write({fd},{fixture_text().encode()!r})']
    if failure=='producer':factory=lambda fd:[sys.executable,'-c','raise SystemExit(9)']
    elif failure=='compressor':
        compressor=tmp_path/'bad-compressor';compressor.write_text('#!'+sys.executable+'\nraise SystemExit(7)\n');compressor.chmod(0o700)
    elif failure=='deadline':
        monkeypatch.setitem(m.POLICY,'capture_seconds',0.03);factory=lambda fd:[sys.executable,'-c','import time;time.sleep(1)']
    elif failure=='disk':
        counts=[0]
        def free(p):counts[0]+=1;return 64*m.GIB if counts[0]==1 else 0
        monkeypatch.setattr(m,'free_bytes',free)
    elif failure=='bytes':monkeypatch.setitem(m.POLICY,'raw_gzip_bytes_per_program',0)
    else:
        def factory(fd):raise KeyboardInterrupt('synthetic interruption')
    with pytest.raises((RuntimeError,TimeoutError,ValueError,KeyboardInterrupt)):
        m.capture_raw(factory,folder,attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={'PATH':'/usr/bin:/bin'})
    record=json.loads((folder/'capture.json').read_text())
    assert record['status']=='failure-retained' and record['primary_error']
    assert_only_permission_race_uncertainty(record)
    assert (folder/'raw-spike.log.gz.partial').exists() and not (folder/'raw-spike.log.gz').exists()


def test_second_program_has_declared18gib_startup_not26(tmp_path,monkeypatch):
    compressor=shutil.which('gzip')
    if compressor is None:pytest.skip('Native gzip unavailable for tiny transport fixture')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:20*m.GIB);monkeypatch.setitem(m.POLICY,'poll_seconds',0.01)
    attempt=tmp_path/'generated/v11-spooled-recovery/fixture';attempt.mkdir(parents=True)
    factory=lambda fd:[sys.executable,'-c',f'import os;os.write({fd},{fixture_text().encode()!r})']
    r=m.capture_raw(factory,attempt/'second',attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={'PATH':'/usr/bin:/bin'},first_program=False)
    assert r['status']=='captured-not-validated'

@pytest.mark.parametrize('blocked',['pipe','drain'])
def test_blocked_pipe_or_compressor_drain_has_finite_cleanup(tmp_path,monkeypatch,blocked):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:64*m.GIB)
    monkeypatch.setitem(m.POLICY,'poll_seconds',0.01);monkeypatch.setitem(m.POLICY,'capture_seconds',0.1);monkeypatch.setitem(m.POLICY,'compressor_drain_seconds',0.03)
    attempt=tmp_path/'generated/v11-spooled-recovery/fixture';attempt.mkdir(parents=True);compressor=tmp_path/'blocked-compressor'
    code='import time;time.sleep(2)' if blocked=='pipe' else 'import sys,time;sys.stdin.buffer.read();time.sleep(2)'
    compressor.write_text('#!'+sys.executable+'\n'+code+'\n');compressor.chmod(0o700)
    factory=lambda fd:[sys.executable,'-c',f'import os;os.write({fd},'+("b'x'*(1024*1024)" if blocked=='pipe' else "b'x'")+')']
    with pytest.raises(TimeoutError):m.capture_raw(factory,attempt/'p',attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={'PATH':'/usr/bin:/bin'})
    record=json.loads((attempt/'p/capture.json').read_text())
    assert record['status']=='failure-retained'
    cleanup_bound=(m.POLICY['capture_seconds']+m.POLICY['compressor_drain_seconds']+
                   2*m.POLICY['cleanup_seconds_per_child']+2)
    assert record['capture_and_drain_wall_seconds']<=cleanup_bound
    assert_only_permission_race_uncertainty(record)


def test_exited_producer_descendant_holding_commit_pipe_is_terminated(tmp_path,monkeypatch):
    """Leader exits0; descendant remains in its owned session with commit FD."""
    import os
    import time
    compressor=shutil.which('gzip')
    if compressor is None:pytest.skip('Native gzip unavailable for tiny transport fixture')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'free_bytes',lambda p:64*m.GIB)
    monkeypatch.setitem(m.POLICY,'poll_seconds',0.01);monkeypatch.setitem(m.POLICY,'compressor_drain_seconds',0.03)
    attempt=tmp_path/'generated/v11-spooled-recovery/fixture';attempt.mkdir(parents=True);folder=attempt/'transport';pidfile=attempt/'descendant.pid'
    child='import os,time;open('+repr(str(pidfile))+',"w").write(str(os.getpid()));time.sleep(30)'
    def factory(fd):
        code=('import subprocess,sys,time,pathlib;'
              'subprocess.Popen([sys.executable,"-c",'+repr(child)+'],pass_fds=('+str(fd)+',));'
              'p=pathlib.Path('+repr(str(pidfile))+');'
              '\nwhile not p.exists():time.sleep(.005)\n')
        return [sys.executable,'-c',code]
    try:
        with pytest.raises(TimeoutError,match='drain'):
            m.capture_raw(factory,folder,attempt,compressor=compressor,compressor_sha256=m.sha(compressor),environment={'PATH':'/usr/bin:/bin'})
        record=json.loads((folder/'capture.json').read_text());pid=int(pidfile.read_text())
        assert record['producer_returncode']==0 and record['status']=='failure-retained'
        assert record['cleanup_errors']==[]
        assert (folder/'raw-spike.log.gz.partial').exists() and not (folder/'raw-spike.log.gz').exists()
        # Linux PID1/container reaping can lag after SIGKILL. A zombie has no
        # live thread/FD but remains visible to kill(pid,0)/killpg(group,0).
        # Accept ONLY explicit /proc Z, and require the runtime's conservative
        # remaining-owned-group failure record; never accept a live descendant.
        status=None
        if sys.platform.startswith('linux'):
            try:status=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
            except FileNotFoundError:pass
        if status is not None:
            assert status[0]=='Z', 'Descendant still live after owned group cleanup'
            assert record['remaining_owned_children']==[{'process':'producer','pid':int(status[2]),'scope':'owned-process-group'}]
        else:
            assert record['remaining_owned_children']==[]
            with pytest.raises(ProcessLookupError):os.kill(pid,0)
    finally:
        # Keep the fixture safe if a future regression restores the original leak.
        if pidfile.exists():
            try:os.kill(int(pidfile.read_text()),m.signal.SIGKILL)
            except ProcessLookupError:pass

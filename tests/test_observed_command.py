"""Paired-clock command tests use fake children only; no native tools are run."""
import copy
import hashlib
import json
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
import pytest
from isaforge import observed_command as r


def unseal(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == Path(str(path)+'.sha256').read_text().strip()
    return json.loads(path.read_text())


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monos=iter([100,102,200,202]);utcs=iter([1_000_000_000,1_000_000_100])
    monkeypatch.setattr(r.time,'monotonic_ns',lambda:next(monos))
    monkeypatch.setattr(r.time,'time_ns',lambda:next(utcs))
    signs=[];monkeypatch.setattr(r.os,'killpg',lambda pid,sig:signs.append((pid,sig)))
    value=SimpleNamespace(output=tmp_path/'command',cwd=tmp_path,metadata=dict(source=dict(sha256='source'),context_id='ctx',candidate_id='candidate',release_sha256='release'),
        calls=[],signals=signs,waits=[],code=0,error=None,start_error=None)
    class Child:
        pid=123456789
        returncode=None
        def wait(self,timeout=None):
            value.waits.append(timeout)
            if value.error is not None:
                error=value.error;value.error=None;raise error
            self.returncode=value.code
            return self.returncode
        def kill(self):value.signals.append(('direct','kill'))
    def popen(argv,**kwargs):
        value.calls.append((copy.deepcopy(argv),kwargs))
        started=unseal(value.output/'started.json')
        assert started['status']=='started' and started['end'] is None
        assert unseal(value.output/'record.json')==started
        assert kwargs['cwd']==str(tmp_path) and kwargs['start_new_session'] is True
        kwargs['stdout'].write(b'child stdout\n');kwargs['stderr'].write(b'child stderr\n')
        if value.start_error is not None:raise value.start_error
        return Child()
    monkeypatch.setattr(r.subprocess,'Popen',popen)
    return value


def run(fixture,**kwargs):
    return r.run(['fake-tool','--candidate','candidate'],fixture.output,cwd=fixture.cwd,metadata=fixture.metadata,**kwargs)


def test_success_started_receipt_precedes_dispatch_and_terminal_has_both_clocks(fixture):
    f=fixture;record=run(f)
    assert record==unseal(f.output/'record.json')
    assert unseal(f.output/'started.json')['status']=='started'
    assert record['status']=='success' and record['returncode']==0
    assert record['start']['monotonic_before_ns']==100 and record['start']['monotonic_after_ns']==102
    assert record['end']['monotonic_before_ns']==200 and record['end']['monotonic_after_ns']==202
    assert record['durations']['utc_elapsed_ns']==record['durations']['monotonic_elapsed_ns']==100
    assert record['durations']['monotonic_elapsed_bracket_ns']==[98,102]
    assert record['durations']['clock_disagreement_detected'] is False
    assert record['durations']['uninterrupted_calendar_wall_time_established'] is False
    assert record['clock_info']['monotonic']['monotonic'] is True
    assert record['observer_pid']>0 and record['observer_session_id'] and record['child_pid']==123456789
    assert (f.output/'stdout.txt').read_text()=='child stdout\n'
    assert (f.output/'stderr.txt').read_text()=='child stderr\n'
    assert record['stdout_sha256']==hashlib.sha256((f.output/'stdout.txt').read_bytes()).hexdigest()
    assert len(f.calls)==1 and f.waits==[3600.0] and f.signals==[]


def test_nonzero_exit_returns_once_without_retry(fixture):
    f=fixture;f.code=23;record=run(f)
    assert record['status']=='nonzero_exit' and record['returncode']==23
    assert len(f.calls)==1 and f.signals==[]


def test_failed_startup_keeps_elapsed_stdout_and_safe_error(fixture):
    f=fixture;f.start_error=FileNotFoundError(2,'secret command must not be recorded')
    record=run(f)
    assert record['status']=='startup_failed' and record['returncode'] is None
    assert record['error']==dict(type='FileNotFoundError',errno=2)
    assert record['end'] is not None and record['durations']['monotonic_elapsed_ns']==100
    assert 'secret' not in (f.output/'record.json').read_text()
    assert len(f.calls)==1 and f.signals==[]


@pytest.mark.parametrize('error',[KeyboardInterrupt(),SystemExit(7)])
def test_interruption_seals_terminal_reaps_group_and_rethrows(fixture,error):
    f=fixture;f.error=error
    with pytest.raises(type(error)):run(f)
    record=unseal(f.output/'record.json')
    assert record['status']=='interrupted' and record['error']['type']==type(error).__name__
    assert record['cleanup']['direct_child_reaped'] is True
    assert f.signals==[(123456789,signal.SIGTERM),(123456789,signal.SIGKILL)]
    assert f.waits==[3600.0,r.CLEANUP_SECONDS,r.CLEANUP_SECONDS]
    assert len(f.calls)==1 and record['end'] is not None


def test_timeout_terminates_descendants_even_when_leader_already_exits(fixture):
    f=fixture;f.error=subprocess.TimeoutExpired(['secret-argument'],3)
    record=run(f,timeout_seconds=3)
    assert record['status']=='timed_out' and record['error']==dict(type='TimeoutExpired')
    assert 'secret-argument' not in (f.output/'record.json').read_text()
    assert f.signals==[(123456789,signal.SIGTERM),(123456789,signal.SIGKILL)]
    assert record['cleanup']['direct_child_reaped'] is True and len(f.calls)==1


def test_metadata_and_argv_are_copied_and_only_argv_hash_is_recorded(fixture,monkeypatch):
    f=fixture;argv=['fake','secret-token'];original=copy.deepcopy(f.metadata)
    existing=r.subprocess.Popen
    def mutate(arguments,**kwargs):
        f.metadata['source']['sha256']='changed';argv.append('extra')
        return existing(arguments,**kwargs)
    monkeypatch.setattr(r.subprocess,'Popen',mutate)
    record=r.run(argv,f.output,cwd=f.cwd,metadata=f.metadata)
    assert record['metadata']==original and record['argv_count']==2
    assert record['argv_sha256']==hashlib.sha256(r._json(['fake','secret-token'])).hexdigest()
    assert 'secret-token' not in (f.output/'record.json').read_text()


@pytest.mark.parametrize('delta',[1000,-1000])
def test_clock_disagreement_keeps_raw_clock_values_without_tolerance(fixture,monkeypatch,delta):
    values=iter([1_000_000_000,1_000_000_000+delta]);monkeypatch.setattr(r.time,'time_ns',lambda:next(values))
    record=run(fixture)
    assert record['durations']['utc_elapsed_ns']==delta
    assert record['durations']['monotonic_elapsed_ns']==100
    assert record['durations']['utc_minus_monotonic_elapsed_ns']==delta-100
    assert record['durations']['clock_disagreement_detected'] is True
    assert record['status']=='success'


def test_nonmonotonic_endpoint_observation_is_flagged_not_rewritten(fixture,monkeypatch):
    values=iter([100,102,90,92]);monkeypatch.setattr(r.time,'monotonic_ns',lambda:next(values))
    record=run(fixture)
    assert record['durations']['monotonic_endpoints_ordered'] is False
    assert record['durations']['monotonic_elapsed_ns']==-10
    assert record['durations']['clock_disagreement_detected'] is True


def test_existing_output_is_never_overwritten(fixture):
    f=fixture;f.output.mkdir();(f.output/'keep').write_text('preserved')
    with pytest.raises(FileExistsError):run(f)
    assert f.calls==[] and (f.output/'keep').read_text()=='preserved'


@pytest.mark.parametrize('timeout',[0,-1,3601,True,None,float('nan'),float('inf')])
def test_invalid_timeout_rejected_before_output_or_launch(fixture,timeout):
    with pytest.raises(ValueError,match='Timeout'):run(fixture,timeout_seconds=timeout)
    assert fixture.calls==[] and not fixture.output.exists()


@pytest.mark.parametrize('argv',[[],[''],['tool','bad\x00argument'],'shell command',[1]])
def test_invalid_argument_vector_never_dispatches(fixture,argv):
    with pytest.raises(ValueError):r.run(argv,fixture.output,cwd=fixture.cwd,metadata={})
    assert fixture.calls==[] and not fixture.output.exists()


def test_non_json_metadata_rejected_before_dispatch(fixture):
    fixture.metadata['bad']=object()
    with pytest.raises(TypeError):run(fixture)
    assert fixture.calls==[] and not fixture.output.exists()


def test_cleanup_failure_does_not_hide_original_interruption(fixture,monkeypatch):
    f=fixture;f.error=KeyboardInterrupt()
    def denied(pid,sig):raise PermissionError(1,'not allowed')
    monkeypatch.setattr(r.os,'killpg',denied)
    with pytest.raises(KeyboardInterrupt):run(f)
    record=unseal(f.output/'record.json')
    assert record['status']=='interrupted' and record['cleanup']['direct_child_reaped'] is True
    assert ('direct','kill') in f.signals
    assert record['cleanup']['actions'][0]['result']=='failed'

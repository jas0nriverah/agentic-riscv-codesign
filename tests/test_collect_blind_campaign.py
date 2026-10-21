"""Serial collection boundary tests; subprocesses and every native stage are mocked."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from isaforge import codesign as c
from scripts import collect_blind_campaign as r


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    prereg, release, output = tmp_path/'prereg',tmp_path/'release.json',tmp_path/'collection'
    c.seal(prereg/'manifest.json',{})
    c.seal(release,dict(prelabel_commit='a'*40))
    roots = {group:tmp_path/group for group in ('beebs-a','beebs-b','beebs-c')}
    cohort = dict(targets={group:dict(original_root=str(root),native_order=['candidate_0','candidate_1']) for group,root in roots.items()},historical_costs=dict(total_candidate_attempts=48))
    seen = []
    monkeypatch.setattr(r.campaign,'check_preregistration',lambda path:(seen.append('prereg') or cohort))
    monkeypatch.setattr(r.campaign,'check_git_checkpoint',lambda *args:seen.append('git'))
    monkeypatch.setattr(r.campaign,'check_release',lambda *args,**kwargs:seen.append('release'))
    monkeypatch.setattr(r.campaign,'check_baseline',lambda prereg,group,root:seen.append('baseline:'+group))
    def zero(root):
        seen.append('zero:'+root.name)
        c.require(not list((root/'attempt-ledger').glob('candidate_*.json')),'Candidate attempt already charged')
    monkeypatch.setattr(r.campaign,'_zero',zero)
    ticks = iter(range(100))
    monkeypatch.setattr(r.time,'monotonic',lambda:float(next(ticks)))
    calls = []
    def run(argv,**kwargs):
        assert kwargs == dict(cwd=tmp_path,capture_output=True,text=True,check=False)
        assert [value for value in seen if value.startswith('zero:')] == ['zero:'+group for group in roots]
        assert len([value for value in seen if value.startswith('baseline:')]) == 3
        assert argv[1:4] == ['-m','isaforge.blind_workload','measure']
        root = Path(argv[argv.index('--root')+1]); name = argv[argv.index('--candidate')+1]
        assert not (root/'attempt-ledger'/(name+'.json')).exists()
        calls.append((root.name,name))
        status = 'failed' if (root.name,name) == ('beebs-b','candidate_0') else 'success'
        c.seal(root/'attempt-ledger'/(name+'.json'),dict(status=status,elapsed_seconds=.25))
        return SimpleNamespace(returncode=1 if status == 'failed' else 0,stdout='native stdout',stderr='native stderr')
    monkeypatch.setattr(r.subprocess,'run',run)
    return SimpleNamespace(prereg=prereg,release=release,output=output,roots=roots,cohort=cohort,seen=seen,calls=calls,run=run)


def test_preflight_all_sources_then_collects_once_serially_and_charges_failures(fixture):
    f = fixture
    result = r.collect(f.prereg,f.release,f.output)
    assert f.calls == [(group,name) for group in f.roots for name in ('candidate_0','candidate_1')]
    assert result['attempted_candidates'] == 6 and result['successful'] == 5 and result['failed'] == 1
    assert result['complete_subprocess_seconds'] == 6.0 and result['ledger_seconds'] == 1.5
    assert result['historical_costs']['total_candidate_attempts'] == 48
    commands = c.unseal(f.output/'commands.json')
    assert all(row['elapsed_seconds'] >= row['ledger_seconds'] for row in commands)
    assert c.unseal(f.output/'protocol.json')['workers'] == 1
    assert len(r.campaign._manifest(f.output)) > 12
    assert f.seen[-1] == 'release'


def test_existing_attempt_in_last_source_blocks_every_subprocess(fixture):
    f = fixture
    c.seal(f.roots['beebs-c']/'attempt-ledger/candidate_1.json',dict(status='failed'))
    with pytest.raises(ValueError,match='already charged'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [] and not f.output.exists()


def test_existing_output_blocks_all_validation_and_subprocesses(fixture):
    f = fixture; f.output.mkdir()
    with pytest.raises(ValueError,match='Fresh'): r.collect(f.prereg,f.release,f.output)
    assert f.seen == [] and f.calls == []


@pytest.mark.parametrize('boundary',['prereg','git','release','baseline'])
def test_failed_release_or_integrity_gate_never_starts_native_work(fixture,monkeypatch,boundary):
    f = fixture
    name = dict(prereg='check_preregistration',git='check_git_checkpoint',release='check_release',baseline='check_baseline')[boundary]
    def reject(*args,**kwargs): raise ValueError('synthetic invalid checkpoint')
    monkeypatch.setattr(r.campaign,name,reject)
    with pytest.raises(ValueError,match='invalid checkpoint'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [] and not f.output.exists()


@pytest.mark.parametrize('status,returncode',[('interrupted',1),('started',1),('success',1),('failed',0)])
def test_interrupted_or_inconsistent_attempt_stops_without_retry_and_keeps_command(fixture,monkeypatch,status,returncode):
    f = fixture
    def run(argv,**kwargs):
        root = Path(argv[argv.index('--root')+1]); name = argv[argv.index('--candidate')+1]
        f.calls.append((root.name,name))
        c.seal(root/'attempt-ledger'/(name+'.json'),dict(status=status,elapsed_seconds=.25))
        return SimpleNamespace(returncode=returncode,stdout='preserved stdout',stderr='preserved stderr')
    monkeypatch.setattr(r.subprocess,'run',run)
    with pytest.raises(ValueError,match='Interrupted or inconsistent'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [('beebs-a','candidate_0')]
    commands = c.unseal(f.output/'commands.json')
    assert commands[0]['attempt_status'] == status and commands[0]['elapsed_seconds'] == 1.0
    assert (f.output/'beebs-a/candidate_0.stdout.txt').read_text() == 'preserved stdout'
    assert not (f.output/'summary.json').exists() and not (f.output/'manifest.json').exists()


def test_attempt_added_after_preflight_is_rejected_without_second_invocation(fixture,monkeypatch):
    f = fixture
    def run(argv,**kwargs):
        result = f.run(argv,**kwargs)
        c.seal(f.roots['beebs-a']/'attempt-ledger/candidate_1.json',dict(status='failed',elapsed_seconds=.25))
        return result
    monkeypatch.setattr(r.subprocess,'run',run)
    with pytest.raises(ValueError,match='already charged'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [('beebs-a','candidate_0')]
    assert len(c.unseal(f.output/'commands.json')) == 1


@pytest.mark.parametrize('kind',['missing','corrupt'])
def test_dispatch_without_authenticated_ledger_keeps_subprocess_cost_before_stop(fixture,monkeypatch,kind):
    f = fixture
    def run(argv,**kwargs):
        root = Path(argv[argv.index('--root')+1]); name = argv[argv.index('--candidate')+1]
        f.calls.append((root.name,name))
        if kind == 'corrupt':
            c.seal(root/'attempt-ledger'/(name+'.json'),dict(status='failed',elapsed_seconds=.25))
            (root/'attempt-ledger'/(name+'.json')).write_text('truncated')
        return SimpleNamespace(returncode=1,stdout='startup stdout',stderr='dispatch failed')
    monkeypatch.setattr(r.subprocess,'run',run)
    with pytest.raises(ValueError,match='subprocess cost preserved'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [('beebs-a','candidate_0')]
    row = c.unseal(f.output/'commands.json')[0]
    assert row['elapsed_seconds'] == 1.0 and row['attempt_status'] is None and row['ledger_seconds'] is None and row['ledger_error']
    assert (f.output/'beebs-a/candidate_0.stderr.txt').read_text() == 'dispatch failed'
    assert not (f.output/'summary.json').exists()


@pytest.mark.parametrize('elapsed',[None,-1.0,2.0,True,999.0])
def test_invalid_or_unenclosed_ledger_duration_stops_with_cost_preserved(fixture,monkeypatch,elapsed):
    f = fixture
    def run(argv,**kwargs):
        root = Path(argv[argv.index('--root')+1]); name = argv[argv.index('--candidate')+1]
        f.calls.append((root.name,name))
        c.seal(root/'attempt-ledger'/(name+'.json'),dict(status='success',elapsed_seconds=elapsed))
        return SimpleNamespace(returncode=0,stdout='stdout',stderr='stderr')
    monkeypatch.setattr(r.subprocess,'run',run)
    with pytest.raises(ValueError,match='Interrupted or inconsistent'): r.collect(f.prereg,f.release,f.output)
    assert f.calls == [('beebs-a','candidate_0')]
    assert c.unseal(f.output/'commands.json')[0]['elapsed_seconds'] == 1.0

"""Boundary tests for the blind cohort; no models or native tools are run."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import hashlib
import subprocess
import pytest

from isaforge import codesign as c
from scripts import blind_campaign as r


def _manifest(root):
    r._seal_manifest(root)


def test_complete_preserved_history_without_fitting():
    corpus = r.historical_corpus(r.HISTORY)
    assert (len(corpus['rows']),len(corpus['failed_attempts']),len(corpus['contexts'])) == (45,3,8)
    assert r.historical_costs(corpus,r.HISTORY)['total_candidate_attempts'] == 48


def test_target_keys_canonicalize_and_alias_duplicates_fail(tmp_path):
    root = tmp_path/'native'
    c.seal(root/'plan.json',dict(workload='compress',workload_group='beebs-compress'))
    other = tmp_path/'other'
    result = r._targets({'compress':root,'beebs-other':other})
    assert result == {'beebs-compress':root,'beebs-other':other}
    with pytest.raises(ValueError,match='Duplicate source group'):
        r._targets({'compress':root,'beebs-compress':root})
    with pytest.raises(ValueError,match='Safe unique'):
        r._targets({'../escape':root,'beebs-other':other})


@pytest.fixture
def timers(tmp_path):
    raw = tmp_path/'native'
    start = datetime(2026,10,22,tzinfo=timezone.utc)
    c.seal(raw/'outer-timing/000-baseline.json',dict(started_at_utc=start.isoformat(),elapsed_seconds=2.0))
    prefix = {path.name:c.sha(path) for path in (raw/'outer-timing').iterdir()}
    def create(size):
        public, names = [], []
        for index in range(size):
            name = f'candidate_{index:03d}'; identity = 'id-'+str(index)
            stamp = start+timedelta(seconds=10*(index+1))
            names.append(name); public.append(dict(candidate_id=identity))
            c.seal(raw/'attempt-ledger'/(name+'.json'),dict(status='failed',elapsed_seconds=2.0,
                started_at_utc=(stamp+timedelta(seconds=1)).isoformat()))
            c.seal(raw/'outer-timing'/f'{index+1:03d}-measure.json',dict(schema='isaforge-wrapper-outer-time-v1',
                command='measure',candidate=name,status='failed',elapsed_seconds=4.0,
                started_at_utc=stamp.isoformat(),scope='Complete CLI operation through lock close; synthetic fixture'))
        return raw,dict(pool_names=names,public=public),prefix
    return create


@pytest.mark.parametrize('size',[12,18])
def test_larger_pool_timers_complete_and_failed_attempts_stay_charged(timers,size):
    raw,audit,prefix = timers(size)
    result = r.candidate_outer_times(raw,audit,prefix)
    assert len(result) == size and sum(result.values()) == 4*size


@pytest.mark.parametrize('change,error',[
    ('duplicate','Duplicate'),('missing','Complete unique'),('unpaired','Unpaired'),
    ('short','enclose'),('overlap','Serial'),('status','terminal'),('scope','timer scope'),
    ('outside','Only declared'),('prefix','Artifact checksum')])
def test_bad_larger_pool_timer_proof_fails_closed(timers,change,error):
    raw,audit,prefix = timers(12)
    path = raw/'outer-timing/002-measure.json'; row = c.unseal(path)
    if change == 'duplicate': c.seal(raw/'outer-timing/013-measure.json',row)
    elif change == 'missing':
        path.unlink(); Path(str(path)+'.sha256').unlink()
    elif change == 'unpaired': (raw/'outer-timing/extra.txt').write_text('unpaired')
    elif change == 'prefix': c.seal(raw/'outer-timing/000-baseline.json',dict(changed=True))
    else:
        if change == 'short': row['elapsed_seconds'] = 1
        elif change == 'overlap':
            row['started_at_utc'] = '2026-10-22T00:00:10+00:00'
            ledger = raw/'attempt-ledger/candidate_001.json'
            value = c.unseal(ledger); value['started_at_utc'] = '2026-10-22T00:00:11+00:00'; c.seal(ledger,value)
        elif change == 'status': row['status'] = 'success'
        elif change == 'scope': row['scope'] = 'inner ledger only'
        elif change == 'outside': row['candidate'] = 'not-in-pool'
        c.seal(path,row)
    with pytest.raises(ValueError,match=error): r.candidate_outer_times(raw,audit,prefix)


@pytest.fixture
def release_fixture(tmp_path):
    prereg = tmp_path/'prereg'; targets = {}
    for group in ('beebs-a','beebs-b','beebs-c'):
        c.seal(prereg/'targets'/group/'baseline/evaluation-protocol.json',dict(context_id=group))
        targets[group] = dict(context_id=group,native_order=['candidate_0'],pool_size=1)
    c.seal(prereg/'cohort.json',dict(targets=targets)); _manifest(prereg)
    record = dict(schema=r.SCHEMA+'-release',prelabel_commit='a'*40,remote_commit='a'*40,
        pushed_branch='ai-guided-ml',remote='origin',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        zero_candidate_attempts=True,target_labels_observed=0,released_at_utc='2026-10-22T00:00:00+00:00',
        targets={group:dict(context_id=value['context_id'],native_order=value['native_order'],
            evaluation_protocol_sha256=c.sha(prereg/'targets'/group/'baseline/evaluation-protocol.json'))
            for group,value in targets.items()})
    path = tmp_path/'release.json'; c.seal(path,record)
    return prereg,path,record


def test_release_binds_all_targets_and_requires_integer_zero(release_fixture):
    prereg,path,row = release_fixture
    assert r.check_release(path,prereg,'a'*40) == row
    row['target_labels_observed'] = False; c.seal(path,row)
    with pytest.raises(ValueError,match='cohort release'): r.check_release(path,prereg,'a'*40)


@pytest.mark.parametrize('what',['ledger','outer'])
def test_release_precedes_every_target_attempt(release_fixture,tmp_path,what):
    prereg,path,row = release_fixture; raws = {}
    for group in row['targets']:
        root = tmp_path/group; raws[group] = root
        c.seal(root/'release.json',row)
        c.seal(root/'attempt-ledger/candidate_0.json',dict(started_at_utc='2026-10-22T00:00:10+00:00'))
        c.seal(root/'outer-timing/001-measure.json',dict(command='measure',started_at_utc='2026-10-22T00:00:09+00:00'))
    assert r.check_release(path,prereg,'a'*40,raws=raws) == row
    root = raws['beebs-c']
    bad = root/('attempt-ledger/candidate_0.json' if what == 'ledger' else 'outer-timing/001-measure.json')
    value = c.unseal(bad); value['started_at_utc'] = row['released_at_utc']; c.seal(bad,value)
    with pytest.raises(ValueError,match='Release must precede'): r.check_release(path,prereg,'a'*40,raws=raws)


def test_git_checkpoint_authenticates_every_file_and_not_only_manifest(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    prereg = tmp_path/'prereg'; source = tmp_path/'source.py'; source.write_text('bound source\n')
    history = tmp_path/'history.json'; history.write_text('history bytes\n')
    c.seal(prereg/'cohort.json',dict(source_bindings={'source.py':c.sha(source)},
        source_history='history.json',historical_costs=dict(source_corpus_sha256=c.sha(history))))
    (prereg/'model.json').write_text('frozen model\n'); _manifest(prereg)
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True)
    subprocess.run(['git','add','.'],cwd=tmp_path,check=True)
    subprocess.run(['git','-c','user.email=test@example.invalid','-c','user.name=Test','commit','-qm','prelabel'],cwd=tmp_path,check=True)
    commit = subprocess.run(['git','rev-parse','HEAD'],cwd=tmp_path,capture_output=True,text=True,check=True).stdout.strip()
    r.check_git_checkpoint(prereg,commit)
    # A resealed manifest with a replaced model still fails against the actual commit.
    (prereg/'model.json').write_text('different model\n'); _manifest(prereg)
    with pytest.raises(ValueError,match='Committed prelabel artifact differs'): r.check_git_checkpoint(prereg,commit)


@pytest.fixture
def freeze_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path); monkeypatch.setattr(r,'SOURCES',())
    history_path = tmp_path/'history/corpus.json'; history_path.parent.mkdir(); history_path.write_text('history')
    history = [dict(candidate_id='h0',workload_group='old0',formula='add(in0,in1)'),
               dict(candidate_id='h1',workload_group='old1',formula='sub(in0,in1)')]
    corpus = dict(rows=history,failed_attempts=[dict(reference_censored=False,workload_group='old0'),dict(reference_censored=False,workload_group='old0'),dict(reference_censored=True,workload_group='old1')],
                  contexts={},total_candidate_attempt_wall_seconds=200.0)
    monkeypatch.setattr(r,'historical_corpus',lambda path:corpus)
    targets, snapshots = {}, {}
    for index in range(3):
        group = 'beebs-new'+str(index); raw = tmp_path/('native'+str(index)); targets[group] = raw
        public = [dict(candidate_id=f'p{index}-{j}',benchmark=group+':ctx'+str(index),formula='xor(in0,in1)') for j in range(12)]
        context = dict(workload_group=group,context_id='ctx'+str(index),baseline_provenance=dict(seconds=2))
        before = dict(workload=group,pool_names=[f'candidate_{j}' for j in range(12)])
        snapshots[raw] = (public,context,before)
        for name in r.BASELINES:
            value = {}
            if name == 'plan.json': value = dict(workload_group=group,workload='new'+str(index),pool_size=12)
            elif name == 'public.json': value = public
            elif name == 'context.json': value = context
            elif name == 'before.json': value = before
            c.seal(raw/name,value)
        c.seal(raw/'outer-timing/000-baseline.json',dict(elapsed_seconds=2))
    monkeypatch.setattr(r,'qualification_evidence',lambda path:dict(
        accepted={group:snapshots[root][1]['context_id'] for group,root in targets.items()},
        original_roots={group:root.relative_to(tmp_path).as_posix() for group,root in targets.items()}))
    calls = []
    native = SimpleNamespace(baseline_public=lambda root:snapshots[root])
    monkeypatch.setattr(r,'workload',lambda:native)
    monkeypatch.setattr(r.evidence,'_calibration',lambda root:dict(native_command_seconds=3.0))
    def fake_freeze(history,public,contexts,output,**kwargs):
        # Every source has already been validated and is still unattempted.
        assert all(not list((root/'attempt-ledger').glob('candidate_*.json')) for root in targets.values())
        calls.append(kwargs['target_workload'])
        value = dict(historical_training_ids=['h0','h1'],historical_postfilter_groups=['old0','old1'])
        c.seal(output/'protocol.json',value)
        return value
    monkeypatch.setattr(r.experiment,'freeze',fake_freeze)
    return tmp_path,targets,snapshots,history_path,calls,native


def test_all_three_baselines_checked_before_first_fit_and_rechecked_after_all(freeze_fixture,monkeypatch):
    tmp,targets,snapshots,history,calls,native = freeze_fixture
    seen = []
    native.baseline_public = lambda root:(seen.append(root) or snapshots[root])
    original = r.experiment.freeze
    def fit(*args,**kwargs):
        assert len(seen) >= 3
        return original(*args,**kwargs)
    monkeypatch.setattr(r.experiment,'freeze',fit)
    result = r.freeze(targets,tmp/'prereg',history=history)
    assert list(result['targets']) == calls == list(targets)
    assert seen == list(targets.values())*2
    assert result['historical_costs']['total_candidate_attempts'] == 48
    manifest = r._manifest(tmp/'prereg')
    assert all('targets/'+group+'/selection/protocol.json' in manifest for group in targets)
    contexts = c.unseal(tmp/'prereg/inputs/contexts.json')
    assert set(contexts) == {snapshots[root][0][0]['benchmark'] for root in targets.values()}


def test_late_third_source_attempt_invalidates_whole_cohort(freeze_fixture,monkeypatch):
    tmp,targets,snapshots,history,calls,native = freeze_fixture
    original = r.experiment.freeze
    def fit(*args,**kwargs):
        result = original(*args,**kwargs)
        if len(calls) == 3:
            c.seal(list(targets.values())[-1]/'attempt-ledger/candidate_0.json',dict(status='started'))
        return result
    monkeypatch.setattr(r.experiment,'freeze',fit)
    with pytest.raises(ValueError,match='Candidate attempt'): r.freeze(targets,tmp/'prereg',history=history)
    assert not (tmp/'prereg/manifest.json').exists()


def test_any_preexisting_target_attempt_blocks_all_model_fits(freeze_fixture):
    tmp,targets,snapshots,history,calls,native = freeze_fixture
    c.seal(list(targets.values())[-1]/'attempt-ledger/candidate_0.json',dict(status='failed'))
    with pytest.raises(ValueError,match='Candidate attempt'): r.freeze(targets,tmp/'prereg',history=history)
    assert calls == [] and not (tmp/'prereg').exists()


def test_historical_target_source_blocks_before_any_fit(freeze_fixture,monkeypatch):
    tmp,targets,snapshots,history,calls,native = freeze_fixture
    corpus = r.historical_corpus(history)
    corpus['rows'][0]['workload_group'] = next(iter(targets))
    with pytest.raises(ValueError,match='absent from history'): r.freeze(targets,tmp/'prereg',history=history)
    assert calls == []


def test_pack_evaluates_copies_and_retains_every_native_attempt(tmp_path,monkeypatch):
    prereg, output = tmp_path/'prereg',tmp_path/'campaign'
    targets = {group:tmp_path/group for group in ('beebs-a','beebs-b','beebs-c')}
    for group in targets:
        c.seal(prereg/'targets'/group/'selection/protocol.json',dict(frozen=True))
        c.seal(prereg/'targets'/group/'public.json',[dict(candidate_id=group)])
    cohort = dict(targets={group:dict(baseline_outer_files={}) for group in targets},source_bindings={})
    c.seal(prereg/'manifest.json',{})
    release = tmp_path/'release.json'; c.seal(release,dict(test=True))
    monkeypatch.setattr(r,'check_preregistration',lambda path:cohort)
    monkeypatch.setattr(r,'check_git_checkpoint',lambda *args:None)
    monkeypatch.setattr(r,'check_release',lambda *args,**kwargs:None)
    monkeypatch.setattr(r,'check_baseline',lambda *args:None)
    monkeypatch.setattr(r,'candidate_outer_times',lambda *args:{'id':4})
    monkeypatch.setattr(r,'verify_refits',lambda *args:None)
    audited = []
    def audit(raw):
        group = raw.name; audited.append(group)
        return dict(public=[dict(candidate_id=group)],outcomes=[dict(candidate_id=group)],charged_candidate_attempts=12,candidate_wall_seconds=24)
    def native_pack(raw,snapshot,**kwargs):
        assert kwargs == dict(prelabel_commit=None)
        c.seal(snapshot/'audit.json',dict(archived=True))
    monkeypatch.setattr(r,'workload',lambda:SimpleNamespace(audit=audit,pack=native_pack))
    checked = []
    monkeypatch.setattr(r.experiment,'checked_outcomes',lambda public,outcomes,audit:checked.append(public[0]['candidate_id']))
    evaluated = []
    def evaluate(root,outcomes,**kwargs):
        assert root.is_relative_to(output) and not root.is_relative_to(prereg)
        assert len(audited) == len(checked) == 3
        evaluated.append(root)
        c.seal(root/'report.json',dict(test=True))
        return dict(trajectories=180,endpoints=540)
    monkeypatch.setattr(r.experiment,'evaluate',evaluate)
    result = r.pack(prereg,targets,output,commit='a'*40,release_path=release)
    assert set(result) == set(targets) and len(evaluated) == 3
    assert all(not (prereg/'targets'/group/'selection/report.json').exists() for group in targets)
    assert sum(value['charged_candidate_attempts'] for value in result.values()) == 36
    assert r._manifest(output)


def test_pack_refuses_incomplete_outcomes_before_creating_package(tmp_path,monkeypatch):
    prereg, output = tmp_path/'prereg',tmp_path/'campaign'
    targets = {'beebs-a':tmp_path/'a','beebs-b':tmp_path/'b'}
    cohort = dict(targets={group:{} for group in targets})
    monkeypatch.setattr(r,'check_preregistration',lambda path:cohort)
    monkeypatch.setattr(r,'check_git_checkpoint',lambda *args:None)
    monkeypatch.setattr(r,'check_release',lambda *args,**kwargs:None)
    monkeypatch.setattr(r,'check_baseline',lambda *args:None)
    monkeypatch.setattr(r,'workload',lambda:SimpleNamespace(audit=lambda raw:dict(public=[],outcomes=[])))
    def fail(*args): raise ValueError('Complete native attempt audit required')
    monkeypatch.setattr(r.experiment,'checked_outcomes',fail)
    with pytest.raises(ValueError,match='Complete native'): r.pack(prereg,targets,output,commit='a'*40,release_path=tmp_path/'release')
    assert not output.exists()


@pytest.fixture
def qualification_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    folder = tmp_path/'qualification'
    protocol = dict(schema='isaforge-blind-qualification-v1',order=['rejected','a','b','c'],
        stop_after_successful_sources=3,phases=['prepare','discover','baseline','public','freeze'],source_bindings={})
    c.seal(folder/'protocol.json',protocol)
    records, accepted = [], {}
    for name in protocol['order']:
        if name == 'rejected':
            row = dict(workload=name,status='rejected',failed_phase='discover',root='native/'+name,
                commands=[dict(phase='prepare',returncode=0,elapsed_seconds=1.0),dict(phase='discover',returncode=1,elapsed_seconds=2.0)])
        else:
            row = dict(workload=name,status='accepted',context_id='context-'+name,root='native/'+name,
                commands=[dict(phase=phase,returncode=0,elapsed_seconds=1.0) for phase in protocol['phases']])
            accepted[name] = row['root']
        records.append(row)
    value = dict(protocol_sha256=c.sha(folder/'protocol.json'),records=records,accepted=accepted,
        successful_sources=3,target_candidate_attempts=0,complete_subprocess_seconds=18.0)
    c.seal(folder/'qualification.json',value); _manifest(folder)
    return folder,value


def test_qualification_keeps_rejected_source_cost_and_exact_first_three(qualification_fixture):
    folder,value = qualification_fixture
    result = r.qualification_evidence(folder)
    assert result['setup_subprocess_seconds'] == 18.0
    assert result['accepted'] == {group:'context-'+group.removeprefix('beebs-') for group in ('beebs-a','beebs-b','beebs-c')}


@pytest.mark.parametrize('change',['order','cost','failure','attempt'])
def test_resealed_qualification_protocol_cannot_hide_bad_evidence(qualification_fixture,change):
    folder,value = qualification_fixture
    if change == 'order': value['records'][1],value['records'][2] = value['records'][2],value['records'][1]
    elif change == 'cost': value['complete_subprocess_seconds'] = 15.0
    elif change == 'failure': value['records'][0]['commands'][-1]['returncode'] = 0
    else: value['target_candidate_attempts'] = 1
    c.seal(folder/'qualification.json',value); _manifest(folder)
    with pytest.raises(ValueError): r.qualification_evidence(folder)


def test_git_checkpoint_requires_native_runtime_source_committed(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    prereg = tmp_path/'prereg'; runtime = tmp_path/'untracked-benchmark.c'; runtime.write_text('int benchmark(void){return 1;}\n')
    history = tmp_path/'history.json'; history.write_text('history\n')
    c.seal(prereg/'cohort.json',dict(targets={'beebs-a':{}},source_bindings={},
        source_history='history.json',historical_costs=dict(source_corpus_sha256=c.sha(history))))
    c.seal(prereg/'targets/beebs-a/baseline/plan.json',dict(source_bindings={'untracked-benchmark.c':c.sha(runtime)}))
    _manifest(prereg)
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True)
    subprocess.run(['git','add','prereg','history.json'],cwd=tmp_path,check=True)
    subprocess.run(['git','-c','user.email=test@example.invalid','-c','user.name=Test','commit','-qm','incomplete prelabel'],cwd=tmp_path,check=True)
    commit = subprocess.run(['git','rev-parse','HEAD'],cwd=tmp_path,capture_output=True,text=True,check=True).stdout.strip()
    with pytest.raises(ValueError,match='Committed preregistration artifact missing: untracked-benchmark.c'):
        r.check_git_checkpoint(prereg,commit)


def test_release_refuses_a_different_remote_even_when_commit_matches(release_fixture):
    prereg,path,row = release_fixture
    row['remote'] = 'untrusted-fork'; c.seal(path,row)
    with pytest.raises(ValueError,match='cohort release'): r.check_release(path,prereg,'a'*40)

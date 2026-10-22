"""Mixed-clock diagnostics preserve strict failures without relaxing integrity."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import shutil
import pytest
from isaforge import codesign as c
from scripts import reproduce_blind_campaign as r


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    prereg,collection,release = tmp_path/'prereg',tmp_path/'collection',tmp_path/'release.json'
    roots,audits,targets,commands = {},{},{},[]
    origin = datetime(2026,10,22,tzinfo=timezone.utc)
    for gi,group in enumerate(('beebs-a','beebs-b')):
        root = tmp_path/group; roots[group] = root
        names = ['candidate_0','candidate_1']
        baseline = [dict(log='baseline/command.log',elapsed_seconds=1.0)]
        native = list(baseline)
        c.seal(root/'outer-timing/000-baseline.json',dict(started_at_utc=(origin-timedelta(seconds=10)).isoformat(),elapsed_seconds=1.0))
        prefix = {path.name:c.sha(path) for path in (root/'outer-timing').iterdir()}
        target = dict(native_order=names,pool_size=2,original_root=str(root),context_id=group,baseline_outer_files=prefix)
        targets[group] = target
        public = [dict(candidate_id=group+'-'+name) for name in names]
        audits[group] = dict(pool_names=names,public=public,context_id=group,outcomes=[])
        for index,name in enumerate(names):
            stamp = origin+timedelta(seconds=(gi*2+index)*100)
            outer_start = stamp+timedelta(seconds=1)
            # Only b/candidate_1 combines a long UTC offset with short monotonic duration.
            ledger_start = stamp+timedelta(seconds=20 if gi==1 and index==1 else 2)
            ledger = dict(status='success',elapsed_seconds=5.0,started_at_utc=ledger_start.isoformat(),receipt_start=len(native),receipt_end=len(native)+1)
            native.append(dict(log='measurements/'+name+'/native.log',elapsed_seconds=4.0))
            c.seal(root/'attempt-ledger'/(name+'.json'),ledger)
            c.seal(root/'outer-timing'/f'{index+1:03d}-measure.json',dict(schema='isaforge-wrapper-outer-time-v1',
                command='measure',candidate=name,status='success',elapsed_seconds=8.0,started_at_utc=outer_start.isoformat(),
                scope='Complete CLI operation through lock close; fixture'))
            commands.append(dict(workload_group=group,candidate=name,argv=['python','-m','isaforge.blind_workload','measure','--root',str(root),'--candidate',name],
                started_at_utc=stamp.isoformat(),elapsed_seconds=10.0,returncode=0,attempt_status='success',ledger_seconds=5.0))
            (collection/group).mkdir(parents=True,exist_ok=True)
            (collection/group/(name+'.stdout.txt')).write_text('stdout'); (collection/group/(name+'.stderr.txt')).write_text('stderr')
        protocol = dict(baseline_receipts=baseline,pool_names=names)
        c.seal(root/'evaluation-protocol.json',protocol); c.seal(root/'commands.json',native)
        c.seal(prereg/'targets'/group/'baseline/evaluation-protocol.json',protocol)
    cohort = dict(targets=targets,source_bindings={r.COLLECTOR:c.sha(r.ROOT/r.COLLECTOR)},historical_costs=dict(total_candidate_attempts=48))
    c.seal(prereg/'cohort.json',cohort); r.frozen._seal_manifest(prereg)
    record = dict(schema=r.frozen.SCHEMA+'-release',prelabel_commit='a'*40,remote_commit='a'*40,
        remote='origin',pushed_branch='ai-guided-ml',zero_candidate_attempts=True,target_labels_observed=0,
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),released_at_utc=(origin-timedelta(seconds=20)).isoformat(),
        targets={group:dict(context_id=value['context_id'],native_order=value['native_order'],evaluation_protocol_sha256=c.sha(prereg/'targets'/group/'baseline/evaluation-protocol.json')) for group,value in targets.items()})
    c.seal(release,record)
    for root in roots.values(): c.seal(root/'release.json',record)
    c.seal(collection/'protocol.json',dict(schema='isaforge-blind-collection-v1',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        release_sha256=c.sha(release),prelabel_commit='a'*40,source_sha256=c.sha(r.ROOT/r.COLLECTOR),
        order={group:value['native_order'] for group,value in targets.items()},workers=1,build_workers=2,attempts_per_candidate=1))
    c.seal(collection/'commands.json',commands)
    c.seal(collection/'summary.json',dict(attempted_candidates=4,successful=4,failed=0,complete_subprocess_seconds=40.0,
        ledger_seconds=20.0,historical_costs=cohort['historical_costs']))
    r.frozen._seal_manifest(collection)
    monkeypatch.setattr(r.frozen.experiment,'checked_outcomes',lambda *args:False)
    return dict(prereg=prereg,collection=collection,release_path=release,roots=roots,audits=audits,commit='a'*40)


def call(fixture):
    return r.clock_audits(fixture['prereg'],fixture['roots'],fixture['audits'],fixture['collection'],commit=fixture['commit'],release_path=fixture['release_path'])


def test_mixed_clock_failure_is_preserved_and_durations_are_unchanged(fixture):
    clocks,binding = call(fixture)
    assert clocks['beebs-a']['frozen_strict_checker']['passed'] is True
    b = clocks['beebs-b']
    assert b['phase'] == 'post-collection accounting amendment'
    assert b['frozen_strict_checker'] == dict(passed=False,error_type='ValueError',error='Outer timestamps must enclose attempt ledger')
    assert b['mixed_clock_violation_counts']['cli_encloses_ledger_derived_end'] == 1
    assert b['rows'][1]['cli_minus_ledger_derived_end_seconds'] == -16.0
    assert list(b['outer_times'].values()) == [8.0,8.0]
    assert b['actual_calendar_wall_seconds'] is None
    assert b['independent_proof']['contiguous_scoped_native_receipts'] is True
    assert binding['manifest_sha256'] == c.sha(fixture['collection']/'manifest.json')


@pytest.mark.parametrize('change,error',[
    ('missing_collector','No such file'),('collector_source','collector source'),('collector_order','command order'),
    ('collector_duration','scope ordering'),('ledger_status','terminal status'),('receipt_gap','Contiguous'),
    ('receipt_scope','receipt scope'),('extra_receipt','Uncharged'),('missing_log','output logs'),
    ('outer_status','terminal status'),('outer_missing','Complete frozen timer order'),
    ('bad_scope','timer scope'),('UTC_backwards','UTC starts'),('summary_cost','cost totals')])
def test_accounting_does_not_suppress_real_integrity_errors(fixture,change,error):
    f = fixture; root = f['roots']['beebs-b']; collection = f['collection']
    if change == 'missing_collector':
        (collection/'manifest.json').unlink()
    elif change.startswith('collector_'):
        name = 'protocol.json' if change=='collector_source' else 'commands.json'; value = c.unseal(collection/name)
        if change=='collector_source': value['source_sha256'] = 'bad'
        elif change=='collector_order': value[0],value[1] = value[1],value[0]
        else: value[-1]['elapsed_seconds'] = 1.0
        c.seal(collection/name,value); r.frozen._seal_manifest(collection)
    elif change=='missing_log':
        (collection/'beebs-b/candidate_1.stdout.txt').unlink(); r.frozen._seal_manifest(collection)
    elif change=='summary_cost':
        value = c.unseal(collection/'summary.json');value['complete_subprocess_seconds'] = 39.0
        c.seal(collection/'summary.json',value);r.frozen._seal_manifest(collection)
    elif change=='extra_receipt':
        value = c.unseal(root/'commands.json');value.append(dict(log='uncharged',elapsed_seconds=1.0));c.seal(root/'commands.json',value)
    elif change.startswith('receipt_') or change=='ledger_status':
        path=root/'attempt-ledger/candidate_1.json';value=c.unseal(path)
        if change=='receipt_gap': value['receipt_start'] += 1
        elif change=='ledger_status': value['status']='failed'
        else:
            receipts=c.unseal(root/'commands.json');receipts[-1]['log']='measurements/other/native.log';c.seal(root/'commands.json',receipts)
        c.seal(path,value)
    else:
        path=root/'outer-timing/002-measure.json';value=c.unseal(path)
        if change=='outer_missing': path.unlink();Path(str(path)+'.sha256').unlink()
        else:
            if change=='outer_status':value['status']='failed'
            elif change=='bad_scope':value['scope']='inner only'
            elif change=='UTC_backwards':value['started_at_utc']='2026-10-22T00:00:01+00:00'
            c.seal(path,value)
    with pytest.raises((ValueError,FileNotFoundError),match=error): call(f)


def test_unexpected_original_strict_error_is_never_accepted(fixture,monkeypatch):
    def invalid(*args): raise ValueError('Lowered source changed')
    monkeypatch.setattr(r.frozen,'candidate_outer_times',invalid)
    with pytest.raises(ValueError,match='Unexpected frozen strict checker failure'): call(fixture)


def test_claimed_mixed_clock_failure_requires_observed_diagnostic(fixture,monkeypatch):
    def invalid(*args): raise ValueError('Outer timestamps must enclose attempt ledger')
    monkeypatch.setattr(r.frozen,'candidate_outer_times',invalid)
    with pytest.raises(ValueError,match='lacks a preserved mixed-clock'): call(fixture)


def test_identical_collector_can_be_relocated_with_explicit_logical_identity(fixture,tmp_path):
    original,_ = call(fixture)
    moved = tmp_path/'moved-collection'
    shutil.copytree(fixture['collection'],moved)
    original_path = original['beebs-a']['collection']['path']
    clocks,binding = r.clock_audits(fixture['prereg'],fixture['roots'],fixture['audits'],moved,
        commit=fixture['commit'],release_path=fixture['release_path'],logical_collection_path=original_path)
    assert clocks == original and binding == original['beebs-a']['collection']


def test_boolean_worker_protocol_is_not_an_integer_contract(fixture):
    path = fixture['collection']/'protocol.json'
    value = c.unseal(path);value['workers'] = True;c.seal(path,value);r.frozen._seal_manifest(fixture['collection'])
    with pytest.raises(ValueError,match='collector source/protocol'): call(fixture)


@pytest.fixture
def orchestration(tmp_path,monkeypatch):
    prereg,release,collection = tmp_path/'prereg',tmp_path/'release.json',tmp_path/'collection'
    groups = ('beebs-a','beebs-b'); roots = {group:tmp_path/'raw'/group for group in groups}
    cohort = dict(targets={group:dict(native_order=['candidate_0'],original_root=str(root),pool_size=1) for group,root in roots.items()},source_bindings={})
    for group in groups:
        c.seal(prereg/'targets'/group/'selection/protocol.json',dict(frozen=True))
        c.seal(prereg/'targets'/group/'public.json',[dict(candidate_id=group)])
    c.seal(prereg/'manifest.json',{});c.seal(release,dict(test=True))
    for name in ('protocol.json','commands.json','summary.json'):c.seal(collection/name,{})
    r.frozen._seal_manifest(collection)
    audits = {group:dict(context_id=group,public=[dict(candidate_id=group)],outcomes=[],charged_candidate_attempts=1,candidate_wall_seconds=5.0) for group in groups}
    clocks = {group:dict(schema=r.CONTRACT,outer_times={group:8.0},frozen_strict_checker=dict(passed=True,error=None)) for group in groups}
    bindings = r.collection_binding(collection)
    monkeypatch.setattr(r.frozen,'check_preregistration',lambda path:cohort)
    monkeypatch.setattr(r.frozen,'check_git_checkpoint',lambda *args:None)
    monkeypatch.setattr(r.frozen,'check_baseline',lambda *args:None)
    monkeypatch.setattr(r,'clock_audits',lambda *args,**kwargs:(clocks,bindings))
    monkeypatch.setattr(r.frozen,'required_selection',lambda path:({'protocol.json','protocol.json.sha256'},{}))
    refits = []
    monkeypatch.setattr(r.frozen,'verify_refits',lambda path:(refits.append(path) or dict(exact_refits=True)))
    def evaluate(path,outcomes,**kwargs):
        if not kwargs.get('verify'):
            for name in r.frozen.FINAL_REPORTS:
                if name.endswith('.json'):c.seal(path/name,dict(test=True))
        return dict(trajectories=180,endpoints=540,new_native_jobs=0)
    monkeypatch.setattr(r.frozen.experiment,'evaluate',evaluate)
    class Native:
        def audit(self,raw):return audits[raw.name]
        def pack(self,raw,snapshot,**kwargs):c.seal(snapshot/'manifest.json',{})
        def replay(self,snapshot,output):
            output.mkdir(parents=True)
            return audits[snapshot.parent.name]
    monkeypatch.setattr(r.frozen,'workload',lambda:Native())
    return dict(prereg=prereg,release=release,collection=collection,roots=roots,cohort=cohort,audits=audits,clocks=clocks,refits=refits)


def test_pack_replay_uses_frozen_models_without_mutating_prereg_and_binds_amendment(orchestration,tmp_path):
    f=orchestration;campaign=tmp_path/'campaign';reproduced=tmp_path/'reproduced'
    r.pack(f['prereg'],f['roots'],campaign,commit='a'*40,release_path=f['release'],collection=f['collection'])
    provenance=c.unseal(campaign/'provenance.json')
    assert provenance['accounting_phase'] == 'post-collection accounting amendment'
    assert provenance['adapter_source_bindings'] == {r.SOURCE:c.sha(r.ROOT/r.SOURCE)}
    assert set(provenance['clock_audits']) == set(f['roots'])
    assert all(not (f['prereg']/'targets'/group/'selection/report.json').exists() for group in f['roots'])
    result=r.replay(campaign,reproduced,prereg=f['prereg'],collection=f['collection'])
    assert result['new_native_jobs'] == 0 and result['accounting_contract'] == r.CONTRACT
    assert all(value['exact_refits'] for value in result['targets'].values())
    assert len(f['refits']) == 4


def test_resealed_changed_clock_audit_is_rejected_on_replay(orchestration,tmp_path):
    f=orchestration;campaign=tmp_path/'campaign'
    r.pack(f['prereg'],f['roots'],campaign,commit='a'*40,release_path=f['release'],collection=f['collection'])
    path=campaign/'targets/beebs-a/clock-audit.json';value=c.unseal(path);value['outer_times']['beebs-a']=7.0;c.seal(path,value)
    r.frozen._seal_manifest(campaign)
    with pytest.raises(ValueError,match='Clock/duration audit replay differs'):
        r.replay(campaign,tmp_path/'out',prereg=f['prereg'],collection=f['collection'])

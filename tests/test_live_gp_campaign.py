"""Live dispatch and proof tests; every child, native evaluator and GP is fake."""
import copy
from datetime import datetime,timezone
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from isaforge import codesign as c
from scripts import live_gp_campaign as r


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    prereg,native,output=tmp_path/'prereg',tmp_path/'native',tmp_path/'collection'
    group='beebs-expint';public=[dict(candidate_id='id'+str(i),benchmark=group+':ctx') for i in range(6)]
    names=['candidate_'+str(i) for i in range(6)]
    target=dict(context_id='ctx',native_order=names,pool_size=6,original_root=str(native))
    cohort=dict(targets={group:target},python_executable='/fake/python',source_history='history/corpus.json',
        qualification=dict(path='qualification'),historical_costs=dict(total_candidate_attempts=84))
    case=dict(public=public,history=[dict(candidate_id='historical')])
    c.seal(prereg/'cohort.json',cohort);r.prior._seal_manifest(prereg)
    c.seal(native/'evaluation-protocol.json',dict(pool_names=names))
    c.seal(prereg/'targets'/group/'baseline/evaluation-protocol.json',dict(pool_names=names))
    r.prior._seal_manifest(prereg)
    c.seal(native/'commands.json',[dict(log='baseline',elapsed_seconds=1.0)])
    c.seal(native/'outer-timing/000-baseline.json',dict(command='baseline'))
    release=tmp_path/'release.json'
    released=dict(schema=r.prior.SCHEMA+'-release',prelabel_commit='a'*40,remote_commit='a'*40,remote='origin',
        pushed_branch='ai-guided-ml',zero_candidate_attempts=True,target_labels_observed=0,
        released_at_utc='2026-10-21T00:00:00+00:00',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        targets={group:dict(context_id='ctx',native_order=names,evaluation_protocol_sha256=c.sha(native/'evaluation-protocol.json'))})
    c.seal(release,released);c.seal(native/'release.json',released)
    monkeypatch.setattr(r,'authenticate',lambda path:(copy.deepcopy(cohort),group,copy.deepcopy(target),copy.deepcopy(case)))
    checks=[]
    monkeypatch.setattr(r,'check_baseline',lambda *args:checks.append('baseline'))
    monkeypatch.setattr(r.prior,'check_git_checkpoint',lambda *args:checks.append('git'))
    monkeypatch.setattr(r.b,'validate_outcome',lambda row,public=None:row.get('status','success')=='success')
    tick=[0]
    def endpoint():
        tick[0]+=10_000_000_000;mono=tick[0];utc=1_792_627_200_000_000_000+mono
        return dict(utc_ns=utc,utc_iso=datetime.fromtimestamp(utc/1e9,timezone.utc).isoformat(),
            monotonic_before_ns=mono,monotonic_after_ns=mono+10)
    monkeypatch.setattr(r.observed,'_endpoint',endpoint)
    outcomes={};dispatch=[];failure=set();spawn_error=[None]
    def audit(root):
        receipts=c.unseal(native/'commands.json')
        ordered=[copy.deepcopy(outcomes[row['candidate_id']]) for row in public if row['candidate_id'] in outcomes]
        return dict(context_id='ctx',public=copy.deepcopy(public),outcomes=ordered,pool_names=names,
            charged_candidate_attempts=len(outcomes),candidate_wall_seconds_complete=True,
            native_command_count=len(receipts),native_command_seconds=sum(row['elapsed_seconds'] for row in receipts),
            successful=[row for row in ordered if row.get('status','success')=='success'],
            attempt_collection_complete=len(outcomes)==6,unattempted=[])
    monkeypatch.setattr(r,'workload',lambda:SimpleNamespace(audit=audit))
    def checked(public,outcomes,audited):
        c.require(audited['attempt_collection_complete'] and len(outcomes)==6,'Complete native attempt audit required')
    monkeypatch.setattr(r.experiment,'checked_outcomes',checked)
    def search(case,provider):
        values=[];curve=[]
        for index in (0,2,1):
            value=provider(copy.deepcopy(case['public'][index]));values.append(value)
            curve.append(dict(budget=len(values),attempted_ids=[row['candidate_id'] for row in values],
                failed_attempts=sum(row.get('status')=='failed' for row in values)))
        return dict(curve=curve,events=[dict(paid=value) for value in values])
    monkeypatch.setattr(r,'run_search',search)
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        assert cwd==tmp_path and timeout_seconds==3600
        index=len(dispatch);identity=metadata['candidate_id'];name=metadata['native_name']
        assert metadata['paid_ids_before']==dispatch
        assert (output/'live.json').exists()==(index>=3)
        assert metadata['mode']==('adaptive' if index<3 else 'oracle-reference')
        folder.mkdir(parents=True)
        start=endpoint()
        immutable=dict(schema=r.observed.SCHEMA,argv_count=len(argv),argv_sha256=hashlib.sha256(r.observed._json(argv)).hexdigest(),
            cwd=str(cwd),metadata=copy.deepcopy(metadata),metadata_sha256=hashlib.sha256(r.observed._json(metadata)).hexdigest(),
            observer_pid=os.getpid(),observer_session_id='session-'+str(index),observer_os_session_id=1,
            clock_info=dict(fixture=True),timeout_seconds=3600.,stdout_file='stdout.txt',stderr_file='stderr.txt',
            start=start,scope='fixture',cross_process_monotonic_origin_verified=False)
        c.seal(folder/'started.json',dict(immutable,status='started',returncode=None,child_pid=None,end=None))
        if spawn_error[0] is not None:
            error=spawn_error[0]
            c.seal(folder/'record.json',dict(immutable,status='interrupted',returncode=None,child_pid=None,end=endpoint()))
            raise error
        status='failed' if identity in failure else 'success'
        value=dict(public[int(identity[2:])],measurement_seconds=2.0,status=status)
        if status=='failed':value.update(error='recorded failure',failure_class='infrastructure_unknown',reference_censored=True)
        outcomes[identity]=value
        receipts=c.unseal(native/'commands.json');begin=len(receipts)
        receipts.append(dict(log='measurements/'+name+'/native.log',elapsed_seconds=1.0));c.seal(native/'commands.json',receipts)
        c.seal(native/'attempt-ledger'/(name+'.json'),dict(status=status,elapsed_seconds=2.0,receipt_start=begin,receipt_end=len(receipts),started_at_utc=start['utc_iso']))
        c.seal(native/'outer-timing'/f'{index+1:03d}-measure.json',dict(command='measure',candidate=name,elapsed_seconds=3.0,started_at_utc=start['utc_iso']))
        (folder/'stdout.txt').write_text('stdout');(folder/'stderr.txt').write_text('stderr')
        end=endpoint();record=dict(immutable,status='success' if status=='success' else 'nonzero_exit',
            returncode=0 if status=='success' else 1,child_pid=123,end=end,durations=r.observed._durations(start,end),
            stdout_sha256=c.sha(folder/'stdout.txt'),stderr_sha256=c.sha(folder/'stderr.txt'))
        c.seal(folder/'record.json',record);dispatch.append(identity)
        return record
    monkeypatch.setattr(r.observed,'run',observe)
    return SimpleNamespace(prereg=prereg,native=native,output=output,release=release,case=case,cohort=cohort,
        dispatch=dispatch,failure=failure,spawn_error=spawn_error,checks=checks,search=search)


def collect(f):return r.collect(f.prereg,f.native,f.release,f.output)
def verify(f):return r.check_collection(f.prereg,f.native,f.output,f.release)


def test_live_three_queries_finish_before_oracle_then_exact_paid_replay(fixture):
    f=fixture;result=collect(f)
    assert f.dispatch==['id0','id2','id1','id3','id4','id5']
    assert result['status']=='complete' and result['paid_ids']==f.dispatch
    assert c.unseal(f.output/'live.json')['attempted_ids']==f.dispatch[:3]
    assert c.unseal(f.output/'queries/03/decision.json')['completed_live_trace_sha256']==c.sha(f.output/'live.json')
    audit,times,live,whole=verify(f)
    assert audit['charged_candidate_attempts']==6 and set(times)==set(f.dispatch)
    assert live['search']['curve'][-1]['budget']==3 and whole==result
    assert f.checks==['baseline','git']


def test_terminal_failed_attempt_remains_paid_and_does_not_retry(fixture):
    f=fixture;f.failure.add('id2');collect(f)
    audit,times,live,whole=verify(f)
    assert f.dispatch.count('id2')==1
    assert live['search']['curve'][-1]['failed_attempts']==1
    assert len(audit['successful'])==5 and len(times)==6


def test_interruption_preserves_terminal_collection_and_never_opens_oracle(fixture):
    f=fixture;f.spawn_error[0]=KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):collect(f)
    overall=c.unseal(f.output/'collection.json')
    assert overall['status']=='interrupted' and overall['end'] and overall['paid_ids']==[]
    assert not (f.output/'live.json').exists() and not f.dispatch
    assert (f.output/'queries/00/command/record.json').exists()
    assert r.prior._manifest(f.output)
    with pytest.raises(ValueError,match='Fresh output'):collect(f)


@pytest.mark.parametrize('gate',['git','release'])
def test_integrity_failure_precedes_any_native_dispatch(fixture,monkeypatch,gate):
    f=fixture
    def fail(*args,**kwargs):raise ValueError('invalid prelabel proof')
    monkeypatch.setattr(r.prior,'check_git_checkpoint' if gate=='git' else 'check_release',fail)
    with pytest.raises(ValueError,match='prelabel proof'):collect(f)
    assert not f.dispatch and not f.output.exists()


def test_existing_native_attempt_blocks_collection_even_with_fresh_output(fixture):
    f=fixture;c.seal(f.native/'attempt-ledger/candidate_0.json',dict(status='failed'))
    with pytest.raises(ValueError,match='Candidate attempt'):collect(f)
    assert not f.output.exists() and not f.dispatch


@pytest.mark.parametrize('where',['prereg','native','history','qualification','ancestor'])
def test_output_guard_rejects_frozen_nested_and_ancestor_locations(fixture,where):
    f=fixture
    path=dict(prereg=f.prereg/'new',native=f.native/'new',history=f.prereg.parent/'history/new',
        qualification=f.prereg.parent/'qualification/new',ancestor=f.prereg.parent)[where]
    with pytest.raises(ValueError,match='Fresh output'):r.fresh_output(path,prereg=f.prereg,native=f.native,cohort=f.cohort)
    assert not f.dispatch


def test_wrong_active_native_root_rejected_before_dispatch(fixture,tmp_path):
    f=fixture
    with pytest.raises(ValueError,match='Original frozen native root'):r.collect(f.prereg,tmp_path/'another',f.release,f.output)
    assert not f.dispatch and not f.output.exists()


@pytest.mark.parametrize('change,error',[
    ('exit','Observer exit status'),('metadata_hash','Immutable paired'),('started_clock','Immutable paired'),
    ('partial_prefix','Paid partial audit'),('partial_digest','Paid partial audit'),('receipt_count','Paid partial audit'),
    ('output','Subprocess output hash'),('decision','dispatch receipts'),('oracle_first','dispatch receipts'),
    ('model_choice','Live adaptive choice'),('paired_duration','paired endpoints')])
def test_resealed_collection_tampering_is_rejected(fixture,monkeypatch,change,error):
    f=fixture;collect(f);folder=f.output/'queries/01'
    if change=='output':(folder/'command/stdout.txt').write_text('changed')
    elif change=='model_choice':
        def different(case,provider):return provider(case['public'][4])
        monkeypatch.setattr(r,'run_search',different)
    else:
        if change in ('exit','metadata_hash','paired_duration'):path=folder/'command/record.json'
        elif change=='started_clock':path=folder/'command/started.json'
        elif change in ('partial_prefix','receipt_count'):path=folder/'partial-audit.json'
        elif change=='partial_digest':path=folder/'completed.json'
        else:path=folder/'decision.json'
        value=c.unseal(path)
        if change=='exit':value['returncode']=17
        elif change=='metadata_hash':value['metadata_sha256']='wrong'
        elif change=='started_clock':value['clock_info']={'changed':True}
        elif change=='paired_duration':value['durations']['monotonic_elapsed_ns']+=1
        elif change=='partial_prefix':value['outcomes'].append(dict(candidate_id='unpaid'))
        elif change=='receipt_count':value['native_command_count']+=1
        elif change=='partial_digest':value['partial_audit_digest']='changed'
        elif change=='decision':value['paid_ids_before']=[]
        else:value['mode']='oracle-reference'
        c.seal(path,value)
    r.prior._seal_manifest(f.output)
    with pytest.raises((ValueError,KeyError),match=error):verify(f)


def test_run_search_uses_exact_frozen_seed_zero_and_fixed_three_query_settings(tmp_path,monkeypatch):
    root=tmp_path/'selection';predictions=[dict(seed=seed,fixture=True) for seed in range(5)]
    c.seal(root/'controls11/model/predictions.json',predictions)
    case=dict(public=['public'],history=['history'],selection_root=root);provider=lambda row:row
    def fake(public,history,callback,**kwargs):
        assert public==['public'] and history==['history'] and callback is provider
        assert kwargs==dict(predictions=predictions[0],**r.LIVE)
        return {'fixed':True}
    monkeypatch.setattr(r.b,'search',fake)
    # Restore the real wrapper; no real GP .fit is invoked.
    assert r.run_search(case,provider)=={'fixed':True}


def test_fresh_source_history_leak_rejected_before_any_model_fit(fixture,tmp_path,monkeypatch):
    f=fixture;group='beebs-expint';context=dict(workload_group=group,context_id='ctx');before=dict(workload=group,pool_names=f.cohort['targets'][group]['native_order'])
    c.seal(f.native/'plan.json',dict(pool_size=6))
    for name,value in [('public',f.case['public']),('context',context),('before',before)]:c.seal(f.native/(name+'.json'),value)
    monkeypatch.setattr(r,'workload',lambda:SimpleNamespace(baseline_public=lambda root:(f.case['public'],context,before)))
    monkeypatch.setattr(r,'qualification',lambda *args:{})
    monkeypatch.setattr(r,'history',lambda path:dict(rows=[dict(workload_group=group)],failed_attempts=[]))
    def forbidden(*args,**kwargs):raise AssertionError('Model fit must not start')
    monkeypatch.setattr(r.experiment,'freeze',forbidden)
    with pytest.raises(ValueError,match='Entire fresh target source'):r.freeze(f.native,tmp_path/'new-prereg',qualification_path=tmp_path/'qualification',history_path=tmp_path/'history/corpus.json')
    assert not (tmp_path/'new-prereg').exists()


def test_authentication_rejects_uninventoried_model_before_loading_or_fitting(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    group='beebs-expint';prereg=tmp_path/'prereg';folder=prereg/'targets'/group
    history_path=tmp_path/'history/corpus.json';c.seal(history_path,dict(test=True))
    corpus=dict(rows=[],failed_attempts=[],contexts={})
    target=dict(context_id='ctx',original_root=str(tmp_path/'native'))
    cohort=dict(schema=r.SCHEMA,live=r.LIVE,target_labels_observed=0,target_labels_read=0,
        targets={group:target},policies=list(r.POLICY_LABELS),seeds=list(r.experiment.SEEDS),area_caps=[32,64,128],budgets=[1,2,3],
        source_bindings={},source_history='history/corpus.json',historical_costs=dict(source_corpus_sha256=c.sha(history_path)),
        qualification=dict(path='qualification',manifest_sha256='filled'))
    qualification=tmp_path/'qualification';c.seal(qualification/'proof.json',dict(test=True));r.prior._seal_manifest(qualification)
    cohort['qualification']['manifest_sha256']=c.sha(qualification/'manifest.json')
    c.seal(prereg/'cohort.json',cohort);c.seal(folder/'baseline/plan.json',{})
    c.seal(prereg/'inputs/history.json',[]);c.seal(prereg/'inputs/historical-failures.json',[])
    c.seal(folder/'selection/protocol.json',dict(schema=r.experiment.SCHEMA,scope='prospective source holdout',
        target_labels_observed=0,target_labels_read=0,artifacts={}))
    c.seal(folder/'selection/hidden-model.json',dict(uninventoried=True));r.prior._seal_manifest(prereg)
    monkeypatch.setattr(r,'history',lambda path:corpus)
    monkeypatch.setattr(r,'sources',lambda plan:{})
    monkeypatch.setattr(r,'workload',lambda:SimpleNamespace(check_plan=lambda plan:None))
    def forbidden(*args,**kwargs):raise AssertionError('Model loading/fitting must not begin')
    monkeypatch.setattr(r.experiment,'authenticate',forbidden)
    with pytest.raises(ValueError,match='Complete frozen model inventory'):r.authenticate(prereg)


def test_source_inventory_binds_qualifier_observer_and_all_fixed_model_sources():
    bindings=r.sources(dict(source_bindings={}))
    assert bindings['scripts/qualify_integer_workload.py']==c.sha(r.ROOT/'scripts/qualify_integer_workload.py')
    assert bindings['isaforge/observed_command.py']==c.sha(r.ROOT/'isaforge/observed_command.py')
    assert set(r.experiment.SOURCES)<=set(bindings)

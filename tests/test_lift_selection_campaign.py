"""Synthetic release/scheduling/one-attempt contracts; no native jobs or target labels."""
import copy
import fcntl
import hashlib
import json
import shutil
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from isaforge import codesign as c
from scripts import lift_selection_campaign as t
from test_budgeted_selection import public, measured, history
from test_g723_selection_campaign import FakeModel, FakePosterior, fake_search


@pytest.fixture
def case():
    rows = history()
    pool = [public(f'candidate-id-{i}', 'add(in0,in1)', t.w.GROUP+':fixture', saved_cycles=100+i)
            for i in range(12)]
    return dict(public=pool,history=rows,posterior=FakePosterior(rows,pool),
        fantasies={seed:dict(metadata={'seed':seed,'fixed':True}) for seed in range(5)})


def outcome(row,*,failed=False):
    if failed:
        return dict(row,status='failed',measurement_seconds=7.,error='Synthetic infrastructure failure',
            failure_class='infrastructure_unknown',reference_censored=True)
    return measured(row,savings=row['latency_features']['estimated_saved_cycles'])


def paid_three(case):
    return [outcome(row) for row in case['public'][3:6]]


def test_next_acquisition_reconstructs_only_exact_paid_prefix(case,fake_search):
    proof,trace = t.next_live(case,[])
    assert trace is None and proof['event']['candidate_id'] == case['public'][3]['candidate_id']
    values = paid_three(case)
    proof,_ = t.next_live(case,values[:1])
    assert proof['successful_paid_ids'] == [values[0]['candidate_id']]
    assert proof['event']['candidate_id'] == values[1]['candidate_id']
    proof,trace = t.next_live(case,values)
    assert proof is None and trace['final_posterior_snapshot']['paid_ids'] == [r['candidate_id'] for r in values]
    values[0] = outcome(case['public'][0])
    with pytest.raises(ValueError,match='Paid prefix differs'):
        t.next_live(case,values)


def test_failure_counts_toward_prefix_without_gaussian_label(case,fake_search):
    values = paid_three(case)
    values[0] = outcome(case['public'][3],failed=True)
    proof,_ = t.next_live(case,values[:2])
    assert proof['event']['charged_before_query'] == 2
    assert proof['successful_paid_ids'] == [values[1]['candidate_id']]
    _,trace = t.next_live(case,values)
    assert trace['final_posterior_snapshot']['paid_ids'] == [v['candidate_id'] for v in values[1:]]


def test_reference_requires_live_seal_and_frozen_remainder_order(case,fake_search):
    first = case['public'][0]['candidate_id']
    with pytest.raises(ValueError,match='Only exact next live'):
        t.choose_dispatch(case,[],candidate_id=first,mode='oracle-reference')
    values = paid_three(case)
    with pytest.raises(ValueError,match='Seal complete live'):
        t.choose_dispatch(case,values,candidate_id=first,mode='oracle-reference')
    _,trace = t.next_live(case,values)
    proof,_ = t.choose_dispatch(case,values,candidate_id=first,mode='oracle-reference',live_trace=trace)
    assert proof is None
    wrong = copy.deepcopy(trace); wrong['curve'][0]['best_speedup'] = 100.
    with pytest.raises(ValueError,match='Sealed live trace'):
        t.choose_dispatch(case,values,candidate_id=first,mode='oracle-reference',live_trace=wrong)
    with pytest.raises(ValueError,match='Reference remainder'):
        t.choose_dispatch(case,values,candidate_id=case['public'][1]['candidate_id'],mode='oracle-reference',live_trace=trace)
    with pytest.raises(ValueError,match='already charged'):
        t.choose_dispatch(case,values,candidate_id=values[0]['candidate_id'],mode='oracle-reference',live_trace=trace)


@pytest.fixture
def release_gate(tmp_path,monkeypatch):
    monkeypatch.setattr(t,'ROOT',tmp_path)
    prereg,native = tmp_path/'prereg',tmp_path/'native'
    target = dict(context_id='context',original_root=str(native))
    c.seal(prereg/'cohort.json',dict(targets={t.w.GROUP:target}))
    c.seal(prereg/'manifest.json',{})
    c.seal(prereg/'targets'/t.w.GROUP/'baseline/evaluation-protocol.json',{})
    record = dict(schema=t.w.PROTOCOL['schema']+'-release',manifest_sha256=c.sha(prereg/'manifest.json'),
        cohort_sha256=c.sha(prereg/'cohort.json'),context_id='context',preregistration_root='prereg',
        evaluation_protocol_sha256=c.sha(prereg/'targets'/t.w.GROUP/'baseline/evaluation-protocol.json'),
        pushed_remote_head='0'*40,prelabel_commit='0'*40,pushed_branch='ai-guided-ml',remote='origin',
        zero_candidate_attempts=True,target_labels_observed=0)
    c.seal(native/'release.json',record)
    calls = []
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:dict(context_id='context'))
    monkeypatch.setattr(t,'authenticate',lambda root:({},t.w.GROUP,target,{}))
    monkeypatch.setattr(t.prior,'check_git_checkpoint',lambda *args:calls.append('git blobs'))
    monkeypatch.setattr(t,'check_baseline',lambda *args:calls.append('baseline'))
    monkeypatch.setattr(t.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(stdout='0'*40+'\trefs/heads/ai-guided-ml\n'))
    return dict(native=native,prereg=prereg,record=record,calls=calls)


@pytest.mark.parametrize('change',[
    {'target_labels_observed':True},{'target_labels_observed':1},{'zero_candidate_attempts':False},
    {'pushed_branch':'main'},{'remote':'other'},{'pushed_remote_head':'1'*40},
    {'context_id':'changed'},{'manifest_sha256':'changed'},
])
def test_release_rejects_label_context_push_or_package_mismatch(release_gate,change):
    fixture = release_gate
    c.seal(fixture['native']/'release.json',dict(fixture['record'],**change))
    with pytest.raises(ValueError,match='Exact complete pushed'):
        t.check_native_release(fixture['native'])
    assert fixture['calls'] == []


def test_actual_remote_and_complete_model_package_rechecked(release_gate,monkeypatch):
    fixture = release_gate
    assert t.check_native_release(fixture['native']) == (fixture['prereg'],fixture['record'])
    monkeypatch.setattr(t.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(stdout='1'*40+'\trefs/heads/ai-guided-ml\n'))
    with pytest.raises(ValueError,match='Actual origin'):
        t.check_native_release(fixture['native'])
    def reject(root): raise ValueError('Missing complete models')
    monkeypatch.setattr(t,'authenticate',reject)
    with pytest.raises(ValueError,match='Missing complete models'):
        t.check_native_release(fixture['native'])


@pytest.fixture
def adapter(tmp_path,monkeypatch,case,fake_search):
    native,prereg = tmp_path/'native',tmp_path/'prereg'
    target = dict(native_order=[f'candidate_{i:02d}' for i in range(12)])
    c.seal(prereg/'manifest.json',{})
    c.seal(native/'release.json',dict(manifest_sha256=c.sha(prereg/'manifest.json')))
    evaluator = object.__new__(t.ReleasedEvaluator)
    evaluator.root = native
    evaluator._inside_dispatch = False
    monkeypatch.setattr(t,'check_native_release',lambda root:(prereg,{}))
    monkeypatch.setattr(t,'authenticate',lambda root:({},t.w.GROUP,target,case))
    monkeypatch.setattr(t.w,'registration',lambda root:nullcontext())
    seen,calls,control = [],[],dict(fail=False,interrupt=False)
    def measure(evaluator,name):
        index = len(calls)
        calls.append(name)
        folder = native/'selection-controller/attempts'/f'{index:02d}'
        decision = c.unseal(folder/'decision.json')
        assert decision['native_name'] == name and decision['chosen_before_dispatch'] is True
        if index < 3:
            proof = c.unseal(folder/'acquisition.json')
            assert proof['event']['candidate_id'] == decision['candidate_id']
            assert decision['acquisition_sha256'] == c.sha(folder/'acquisition.json')
        else:
            assert decision['completed_live_trace_sha256'] == c.sha(native/'selection-controller/live.json')
        row = case['public'][target['native_order'].index(name)]
        c.seal(native/'attempt-ledger'/(name+'.json'),dict(status='interrupted' if control['interrupt'] else
            'failed' if control['fail'] else 'success'))
        if control['interrupt']:
            raise KeyboardInterrupt('preserve')
        seen.append(outcome(row,failed=control['fail']))
        if control['fail']:
            raise ValueError('Synthetic infrastructure failure')
    monkeypatch.setattr(t.g.Evaluator,'measure',measure)
    monkeypatch.setattr(t,'audit',lambda root,**kwargs:dict(outcomes=copy.deepcopy(seen),
        charged_candidate_attempts=len(seen),candidate_wall_seconds_complete=True))
    return dict(native=native,evaluator=evaluator,target=target,case=case,calls=calls,seen=seen,control=control)


def test_adapter_seals_before_dispatch_and_never_retries_success_or_failure(adapter):
    fixture = adapter
    row = fixture['evaluator'].measure('candidate_03')
    assert row['candidate_id'] == fixture['case']['public'][3]['candidate_id']
    with pytest.raises(ValueError,match='already charged'):
        fixture['evaluator'].measure('candidate_03')
    fixture['control']['fail'] = True
    failed = fixture['evaluator'].measure('candidate_04')
    assert failed['status'] == 'failed' and failed['measurement_seconds'] == 7.
    completed = c.unseal(fixture['native']/'selection-controller/attempts/01/completed.json')
    assert completed['terminal_status'] == 'failed'
    with pytest.raises(ValueError,match='already charged'):
        fixture['evaluator'].measure('candidate_04')
    assert fixture['calls'] == ['candidate_03','candidate_04']


def test_adapter_gates_reference_after_three_terminal_attempts(adapter):
    fixture = adapter
    with pytest.raises(ValueError,match='Only exact next live'):
        fixture['evaluator'].measure('candidate_00',mode='oracle-reference')
    assert fixture['calls'] == []
    for name in ('candidate_03','candidate_04','candidate_05'):
        fixture['evaluator'].measure(name)
    fixture['evaluator'].measure('candidate_00',mode='oracle-reference')
    assert fixture['calls'] == ['candidate_03','candidate_04','candidate_05','candidate_00']
    assert (fixture['native']/'selection-controller/live.json').is_file()


def test_interrupted_reservation_forbids_any_automatic_continuation(adapter):
    fixture = adapter
    fixture['control']['interrupt'] = True
    with pytest.raises(KeyboardInterrupt):
        fixture['evaluator'].measure('candidate_03')
    assert not (fixture['native']/'selection-controller/attempts/00/completed.json').exists()
    for name in ('candidate_03','candidate_04'):
        with pytest.raises(ValueError,match='unobserved or interrupted'):
            fixture['evaluator'].measure(name)
    assert fixture['calls'] == ['candidate_03']


def test_qualification_evaluator_block_is_preserved(tmp_path):
    evaluator = object.__new__(t.w.Evaluator)
    evaluator.root = tmp_path
    with pytest.raises(ValueError,match='Candidate dispatch disabled'):
        evaluator.measure('candidate_00')


@pytest.fixture
def frozen(tmp_path,monkeypatch,case):
    """Synthetic source-bound freeze with deterministic fake estimators."""
    actual_rows = [dict(history()[i%3],candidate_id=f'h{i}',workload_group=f'old{i%13}',
                        benchmark=f'old{i%13}:ctx') for i in range(110)]
    actual = dict(rows=actual_rows,failed_attempts=[dict(candidate_id=f'f{i}') for i in range(4)],
        total_candidate_attempt_wall_seconds=300.,clock_accounting={'qualified':True},contexts={})
    monkeypatch.setattr(t,'ROOT',tmp_path)
    monkeypatch.setattr(t,'HISTORY',tmp_path/'history/corpus.json')
    c.seal(t.HISTORY,actual)
    monkeypatch.setattr(t,'history',lambda path:copy.deepcopy(actual))
    native,output,qualified = tmp_path/'native',tmp_path/'prereg',tmp_path/'qualified'
    qualified.mkdir(); t.prior._seal_manifest(qualified)
    qual = dict(path='qualified',manifest_sha256=c.sha(qualified/'manifest.json'),transitive_manifest_bindings={})
    monkeypatch.setattr(t,'qualification',lambda *args:qual)
    pool = copy.deepcopy(case['public'])
    context = dict(context_id='fixture',workload_group=t.w.GROUP,baseline_provenance={'fixture':True})
    before = dict(workload=t.w.GROUP,pool_names=[f'candidate_{i:02d}' for i in range(12)])
    plan = dict(context_id='fixture',source_bindings={})
    for name in t.prior.BASELINES:
        value = {'fixture':name}
        if name == 'public.json': value = pool
        if name == 'context.json': value = context
        if name == 'before.json': value = before
        if name == 'plan.json': value = plan
        if name == 'measurements/baseline/measurement.json':
            value = dict(name='baseline',routes=[dict(seed=s,internal_timing_pass=True,device_fits=True) for s in (1,2,3)],
                performance={'cycles':1000},resources={'lut4_count':1})
        if name == 'evaluation-protocol.json': value = dict(pool_names=before['pool_names'])
        c.seal(native/name,value)
    monkeypatch.setattr(t.w,'opportunity_gate',lambda public:dict(accepted=True))
    c.seal(native/'opportunity.json',t.w.opportunity_gate(pool))
    c.seal(native/'outer-timing/000-prepare.json',{'fixture':True})
    monkeypatch.setattr(t.w,'baseline_public',lambda root:(copy.deepcopy(pool),copy.deepcopy(context),copy.deepcopy(before)))
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:copy.deepcopy(plan))
    monkeypatch.setattr(t.w,'check_plan',lambda value:None)
    monkeypatch.setattr(t.prior.evidence,'_calibration',lambda root:{'native_command_seconds':0.})
    monkeypatch.setattr(t,'sources',lambda plan:{'fixture-controller':'bound'})
    monkeypatch.setattr(t.semantic,'SemanticHardwareSurrogate',FakeModel)
    monkeypatch.setattr(t.j.JointHardwarePosterior,'from_fitted',lambda model,training,public:FakePosterior(training,public))
    fitting = [r for r in actual_rows if t.family(r['formula']) not in {t.family(p['formula']) for p in pool}]
    def freeze(history,features,contexts,destination,**kwargs):
        assert kwargs['scope'] == 'consumed-data development'
        c.seal(destination/'controls11/model/history.json',fitting)
        c.seal(destination/'controls11/model/predictions.json',{'old-controls':True})
        protocol = dict(schema=t.experiment.SCHEMA,scope=kwargs['scope'],target_workload=t.w.GROUP,
            target_labels_observed=0,target_labels_read=0,
            policies=[*t.b.POLICIES,t.experiment.controls.POLICY,t.experiment.POLICY],
            artifacts={p.relative_to(destination).as_posix():c.sha(p) for p in destination.rglob('*') if p.is_file()},
            historical_training_ids=[r['candidate_id'] for r in fitting],
            historical_postfilter_groups=sorted({r['workload_group'] for r in fitting}),
            contexts_digest=c.digest(contexts),source_history_digest=c.digest(history),
            cost_provenance=kwargs['cost_provenance'],input_bindings=kwargs['input_bindings'])
        c.seal(destination/'protocol.json',protocol)
        return protocol
    monkeypatch.setattr(t.experiment,'freeze',freeze)
    monkeypatch.setattr(t.experiment,'authenticate',lambda root:dict(public=pool,history=fitting))
    t.freeze(native,output,qualification_path=qualified)
    return dict(output=output,native=native,training=fitting)


def test_complete_freeze_retains_17_policies_114_attempt_costs_and_myopic(frozen):
    cohort,_,target,case = t.authenticate(frozen['output'])
    assert cohort['policies'] == t.OLD_POLICIES+list(t.f.POLICIES)
    assert len(cohort['policies']) == len(set(cohort['policies'])) == 17
    assert cohort['historical_costs']['successful_labels'] == 110
    assert cohort['historical_costs']['failed_attempts'] == 4
    assert cohort['historical_costs']['total_candidate_attempts'] == 114
    assert cohort['scope'] == 'consumed-data development'
    assert cohort['live']['policy'] == t.f.MYOPIC
    assert cohort['primary'] == dict(area_delta_lut4=64,budget=3,clock_mhz=12.)
    assert case['history'] == frozen['training']


@pytest.mark.parametrize('field,value',[
    ('policies',[]),('live',dict(t.LIVE,policy=t.f.LOOKAHEAD)),('target_labels_read',True),
    ('scope','prospective source holdout'),('budgets',[3]),('area_caps',[64]),
])
def test_resealed_protocol_drift_rejected(frozen,field,value):
    path = frozen['output']/'cohort.json'
    cohort = c.unseal(path); cohort[field] = value
    c.seal(path,cohort); t.prior._seal_manifest(frozen['output'])
    with pytest.raises(ValueError,match='Complete fixed seventeen-policy'):
        t.authenticate(frozen['output'])


@pytest.mark.parametrize('artifact',['joint/joint.json','semantic/snapshot.json','selection/controls11/model/predictions.json'])
def test_incomplete_model_package_cannot_be_resealed_for_release(frozen,artifact):
    path = frozen['output']/'targets'/t.w.GROUP/artifact
    path.unlink(); Path(str(path)+'.sha256').unlink()
    t.prior._seal_manifest(frozen['output'])
    with pytest.raises((ValueError,FileNotFoundError)):
        t.authenticate(frozen['output'])


@pytest.fixture
def nested_manifests(tmp_path,monkeypatch):
    monkeypatch.setattr(t,'ROOT',tmp_path)
    path = tmp_path/'results/2026-10-25-lift-cfg-tail-qualification'
    for rejection in (t.w.ORIGINAL_REJECTION,t.w.PRIOR_CFG_REJECTION):
        c.seal(tmp_path/rejection/'manifest.json',{'canonical':rejection})
        copied = path/'sources'/rejection/'manifest.json'
        copied.parent.mkdir(parents=True,exist_ok=True)
        copied.write_bytes((tmp_path/rejection/'manifest.json').read_bytes())
    c.seal(path/'marker.json',{'bound':True})
    entries = {name:c.sha(path/name) for name in ('marker.json','marker.json.sha256')}
    c.seal(path/'manifest.json',entries)
    calls = []
    monkeypatch.setattr(t.qualifier,'validate_original_rejection',lambda:calls.append('original'))
    monkeypatch.setattr(t.qualifier,'validate_prior_cfg_rejection',lambda:calls.append('v1'))
    return path,calls


def test_exact_two_nested_manifest_omissions_authenticated_transitively(nested_manifests):
    path,calls = nested_manifests
    bindings = t.qualification_manifest(path)
    assert len(bindings) == 2 and calls == ['original','v1']
    for name,digest in bindings.items():
        assert c.sha(path/name) == digest


@pytest.mark.parametrize('change',['extra','changed-copy','missing-listed'])
def test_manifest_exception_cannot_hide_other_artifact_changes(nested_manifests,change):
    path,calls = nested_manifests
    if change == 'extra':
        (path/'unlisted.txt').write_text('not allowed')
    elif change == 'changed-copy':
        (path/'sources'/t.w.ORIGINAL_REJECTION/'manifest.json').write_text('{}')
    else:
        (path/'marker.json').unlink()
    with pytest.raises(ValueError):
        t.qualification_manifest(path)


def test_resealed_paid_acquisition_drift_blocks_next_native_attempt(adapter):
    fixture = adapter
    fixture['evaluator'].measure('candidate_03')
    folder = fixture['native']/'selection-controller/attempts/00'
    proof = c.unseal(folder/'acquisition.json')
    proof['event']['candidate_id'] = 'unpaid'
    c.seal(folder/'acquisition.json',proof)
    decision = c.unseal(folder/'decision.json'); decision['acquisition_sha256'] = c.sha(folder/'acquisition.json')
    c.seal(folder/'decision.json',decision)
    completed = c.unseal(folder/'completed.json'); completed['decision_sha256'] = c.sha(folder/'decision.json')
    c.seal(folder/'completed.json',completed)
    with pytest.raises(ValueError,match='Exact sealed prior acquisition'):
        fixture['evaluator'].measure('candidate_04')
    assert fixture['calls'] == ['candidate_03']


def test_constructor_checks_release_before_guarded_runner(tmp_path,monkeypatch):
    called = []
    def reject(root): raise ValueError('No complete release')
    monkeypatch.setattr(t,'check_native_release',reject)
    monkeypatch.setattr(t.g.Evaluator,'__init__',lambda self,root:called.append('runner'))
    with pytest.raises(ValueError,match='No complete release'):
        t.ReleasedEvaluator(tmp_path)
    assert called == []


def test_measure_records_complete_cli_operation_even_on_failure(tmp_path,monkeypatch):
    lock = SimpleNamespace(close=lambda:None)
    state = {'fail':False,'terminal_failure':False}
    class FakeEvaluator:
        def __init__(self,root): self.runner = SimpleNamespace(lock=lock)
        def measure(self,name,*,mode,acquisition_proof=None):
            if state['fail']: raise RuntimeError('synthetic failure')
            if state['terminal_failure']: return {'candidate':name,'status':'failed'}
            return {'candidate':name,'mode':mode}
    monkeypatch.setattr(t,'ReleasedEvaluator',FakeEvaluator)
    native = tmp_path/'native'; native.mkdir()
    assert t.measure(native,'candidate-0',mode='oracle-reference') == {
        'candidate':'candidate-0','mode':'oracle-reference'}
    state['terminal_failure'] = True
    assert t.measure(native,'candidate-terminal-failure')['status'] == 'failed'
    state['fail'] = True
    with pytest.raises(RuntimeError,match='synthetic failure'):
        t.measure(native,'candidate-1',mode='oracle-reference')
    records = sorted((native/'outer-timing').glob('*-measure.json'))
    assert len(records) == 3
    assert [c.unseal(path)['status'] for path in records] == ['success','failed','failed']
    assert all(c.unseal(path)['elapsed_seconds'] >= 0 for path in records)


def test_measure_cli_exits_nonzero_after_sealing_terminal_failure(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(t,'measure',lambda *args,**kwargs:{'candidate_id':'candidate-0','status':'failed'})
    with pytest.raises(SystemExit) as error:
        t.main(['measure','--root',str(tmp_path),'--candidate','candidate-0'])
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'


def test_adaptive_argv_keeps_original_collection_root_after_archive_move(tmp_path):
    original = tmp_path/'original'/'collection'
    archived = tmp_path/'replayed'/'collection'
    source = original/'acquisitions'/'00.json'
    c.seal(source,{'sealed-choice':'candidate-0'})
    source_digest = c.sha(source)
    archived.parent.mkdir(parents=True)
    shutil.copytree(original,archived)
    shutil.rmtree(original.parent)
    argv = t._measure_argv('/pinned/python','/frozen/native',str(original),
        'candidate_0','adaptive',0)
    expected = hashlib.sha256(json.dumps(argv,sort_keys=True,allow_nan=False,
        separators=(',',':')).encode()).hexdigest()
    assert argv[-1] == str(original/'acquisitions'/'00.json')
    assert c.sha(archived/'acquisitions'/'00.json') == source_digest
    changed = t._measure_argv('/pinned/python','/frozen/native',str(archived),
        'candidate_0','adaptive',0)
    changed_hash = hashlib.sha256(json.dumps(changed,sort_keys=True,allow_nan=False,
        separators=(',',':')).encode()).hexdigest()
    assert expected != changed_hash


def test_restore_native_snapshot_binds_verification_to_restored_root(tmp_path,monkeypatch):
    snapshot,destination = tmp_path/'snapshot',tmp_path/'restored'/'native'
    snapshot.mkdir()
    calls = []
    @contextmanager
    def registration(root=None):
        calls.append(('registration',Path(root).resolve() if root is not None else None))
        yield
    def replay(source,target):
        calls.append(('replay',Path(source).resolve(),Path(target).resolve()))
        Path(target).mkdir(parents=True)
        return {'charged_candidate_attempts':0}
    monkeypatch.setattr(t.w,'registration',registration)
    monkeypatch.setattr(t.guarded_evidence,'replay',replay)
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:calls.append(('validate',Path(root).resolve())))
    monkeypatch.setattr(t,'audit',lambda root:{'charged_candidate_attempts':0})
    assert t.restore_native_snapshot(snapshot,destination) == {'charged_candidate_attempts':0}
    assert calls[0] == ('registration',destination.resolve())
    assert calls[1] == ('replay',snapshot.resolve(),destination.resolve())
    assert ('validate',destination.resolve()) in calls
    assert calls[-1] == ('registration',destination.resolve())


def test_frozen_selection_verification_binds_inventory_hashes_and_refits(tmp_path,monkeypatch):
    prereg,selection = tmp_path/'prereg',tmp_path/'campaign'/'selection'
    source = prereg/'targets'/t.w.GROUP/'selection'
    source.mkdir(parents=True); selection.mkdir(parents=True)
    (source/'model.json').write_text('{"model":"frozen"}')
    shutil.copyfile(source/'model.json',selection/'model.json')
    monkeypatch.setattr(t,'required_selection',lambda root:({'model.json'},{}))
    monkeypatch.setattr(t.prior,'_inventory',lambda root:{p.relative_to(root).as_posix() for p in Path(root).rglob('*') if p.is_file()})
    monkeypatch.setattr(t.prior,'verify_refits',lambda root:{'refitted':True})
    verified = t.verify_frozen_selection(prereg,selection)
    assert verified['refitted'] is True and verified['model_validation_refit_host_seconds'] >= 0
    assert 'model_validation_refit_host_seconds' not in t.stable(verified)
    for name in ('report.json','controls11/report.json','controls11/model/report.json'):
        c.seal(selection/name,{'derived_report':name})
    assert t.verify_frozen_selection(prereg,selection,reports_required=True)['refitted'] is True
    (selection/'unexpected.json').write_text('{}')
    with pytest.raises(ValueError,match='exact optional/final report inventory'):
        t.verify_frozen_selection(prereg,selection,reports_required=True)
    (selection/'unexpected.json').unlink()
    (selection/'model.json').write_text('{"model":"replacement"}')
    with pytest.raises(ValueError,match='Frozen model changed after labels'):
        t.verify_frozen_selection(prereg,selection,reports_required=True)


def test_in_lock_audit_uses_existing_exclusive_lock_without_reopening_shared_lock(tmp_path,monkeypatch):
    native=tmp_path/'native'; native.mkdir()
    lock_path=native/'.native.lock'; lock_path.touch()
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:None)
    monkeypatch.setattr(t.w,'check_opportunity',lambda root:None)
    monkeypatch.setattr(t.w,'registration',lambda root:nullcontext())
    monkeypatch.setattr(t.guarded_evidence,'_audit',lambda root:{'lock':'held','root':str(Path(root).resolve())})
    with lock_path.open('r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            assert t.audit(native,native_lock_held=True)=={'lock':'held','root':str(native.resolve())}
            with pytest.raises(ValueError,match='Native evaluator is active'):
                t.audit(native)
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)


def _endpoint_runs(public,outcomes):
    labels = {row['candidate_id']:row for row in outcomes}
    outer = {row['candidate_id']:max(3.,labels[row['candidate_id']]['measurement_seconds']+1.) for row in public}
    runs = []
    for policy in t.POLICIES:
        budgets = (1,2,3) if policy in t.f.POLICIES else (3,)
        for budget in budgets:
            for cap in (32,64,128):
                for seed in range(5):
                    ids = [row['candidate_id'] for row in public]
                    shift = seed % len(ids)
                    ids = ids[shift:]+ids[:shift]
                    curve = []
                    for count in range(1,budget+1):
                        attempted = ids[:count]
                        measured_rows = [labels[identity] for identity in attempted]
                        best = max([1.]+[row['speedup'] for row in measured_rows
                            if t.b._feasible(row,cap,t.LIVE['clock_mhz'])])
                        curve.append(dict(budget=count,attempted_ids=attempted,best_speedup=best,
                            target_measurement_seconds=sum(row['measurement_seconds'] for row in measured_rows),
                            target_outer_operation_seconds=sum(outer[identity] for identity in attempted),
                            known_infeasible_attempts=sum(row.get('status','success') == 'success' and
                                not t.b._feasible(row,cap,t.LIVE['clock_mhz']) for row in measured_rows),
                            unknown_attempts=sum(row.get('status') == 'failed' and row['reference_censored']
                                for row in measured_rows),inference_seconds=0.))
                    runs.append(dict(policy=policy,cap=cap,seed=seed,planned_budget=budget,
                        candidate_outer_operation_seconds=outer,curve=curve))
    return runs


def test_all_policy_endpoints_retain_finite_horizons_and_censored_regret(case):
    outcomes = [outcome(row) for row in case['public']]
    runs = _endpoint_runs(case['public'],outcomes)
    result = t._endpoints(case['public'],outcomes,runs,False)
    assert len(result) == 180
    assert sum(row['endpoint_kind'] == 'B3-prefix' for row in result) == 153
    assert sum(row['endpoint_kind'] == 'horizon-aware-terminal' for row in result) == 27
    assert all(row['reference_complete'] and not row['regret_is_lower_bound'] for row in result)
    outcomes[0] = dict(case['public'][0],status='failed',measurement_seconds=7.,
        error='synthetic infrastructure failure',failure_class='infrastructure_unknown',reference_censored=True)
    censored = t._endpoints(case['public'],outcomes,_endpoint_runs(case['public'],outcomes),True)
    assert all(not row['reference_complete'] and row['regret_is_lower_bound'] for row in censored)


def test_release_requires_zero_native_attempts_before_writing_record(release_gate,monkeypatch,tmp_path):
    fixture = release_gate
    (fixture['native']/'release.json').unlink()
    Path(str(fixture['native']/'release.json')+'.sha256').unlink()
    target = dict(context_id='context',original_root=str(fixture['native']))
    monkeypatch.setattr(t,'authenticate',lambda root:(dict(qualification={'path':'qualified'}),t.w.GROUP,target,{}))
    monkeypatch.setattr(t,'fresh',lambda *args:None)
    def charged(root): raise ValueError('Candidate attempt before cohort release')
    monkeypatch.setattr(t.prior,'_zero',charged)
    output = tmp_path/'new-release.json'
    with pytest.raises(ValueError,match='Candidate attempt before'):
        t.release(fixture['prereg'],fixture['native'],'0'*40,output)
    assert not output.exists() and not (fixture['native']/'release.json').exists()

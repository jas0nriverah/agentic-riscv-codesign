"""Paid-prefix/model/release tests; use consumed fixtures, never new native jobs."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from isaforge import codesign as c, semantic_selection as semantic
from scripts import tacle_selection_campaign as t


@pytest.fixture
def case(tmp_path):
    root = c.ROOT/'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes'
    public = c.unseal(root/'controls11/model/public.json')
    training = c.unseal(root/'controls11/model/history.json')
    prediction = c.unseal(root/'controls11/model/predictions.json')
    state = semantic.SemanticHardwareSurrogate().fit(training)
    selection = tmp_path/'selection'
    c.seal(selection/'controls11/model/predictions.json',prediction)
    # Known consumed outcomes are used only by the provider below.
    audit = c.unseal(c.ROOT/'results/2026-10-21-blind-campaign/targets/beebs-ndes/audit.json')
    assert audit['public'] == public
    return dict(public=public,history=training,selection_root=selection,
        semantic_predictions=state.predict(public),semantic_snapshot=state.snapshot(),
        semantic_cost={'host_monotonic_seconds':0.},labels={row['candidate_id']:row for row in audit['outcomes']})


def test_semantic_search_seals_exact_successful_paid_prefix(case):
    released,proofs = [],[]
    historical = [row['candidate_id'] for row in case['history']]
    def acquire(proof):
        assert proof['event']['attempted_ids_before_query'] == released
        assert proof['training_ids'] == historical+released
        assert proof['model_state_sha256']
        proofs.append(copy.deepcopy(proof))
    def provider(row):
        assert proofs[-1]['event']['candidate_id'] == row['candidate_id']
        assert len(proofs) == len(released)+1
        released.append(row['candidate_id'])
        return copy.deepcopy(case['labels'][row['candidate_id']])
    result = t.run_search(case,provider,on_acquire=acquire)
    assert len(set(released)) == len(proofs) == 3
    assert result['curve'][-1]['attempted_ids'] == released
    assert result['acquisition_proofs'] == proofs
    assert result['policy'] == t.LIVE['policy']


def test_semantic_training_id_tampering_fails_before_provider(case):
    case['semantic_snapshot']['training_ids'].append(case['public'][0]['candidate_id'])
    called = []
    with pytest.raises(ValueError,match='successful paid prefix'):
        t.run_search(case,lambda row:called.append(row))
    assert called == []


def test_count_control_uses_same_information_and_spends_three_attempts(case):
    released = []
    def provider(row):
        released.append(row['candidate_id'])
        return copy.deepcopy(case['labels'][row['candidate_id']])
    result = t.count_search(case,provider,policy=t.count.POLICY,seed=0,area_cap=64)
    assert len(set(released)) == len(result['acquisition_proofs']) == 3
    assert result['curve'][-1]['target_measurement_seconds'] == sum(case['labels'][i]['measurement_seconds'] for i in released)


def test_baseline_checks_tacle_plan_and_exact_prefix_without_blind_adapter(tmp_path,monkeypatch):
    native,prereg = tmp_path/'native',tmp_path/'prereg'
    baseline = prereg/'targets'/t.w.GROUP/'baseline'
    target = dict(context_id='tacle',native_order=['candidate_00'],pool_size=1,baseline_outer_files={})
    c.seal(prereg/'cohort.json',{'targets':{t.w.GROUP:target}})
    for name in (*t.prior.BASELINES,'opportunity.json'):
        value = {'same':name}
        if name == 'commands.json': value = [{'baseline':True}]
        if name == 'evaluation-protocol.json':
            value = dict(baseline_receipts=[{'baseline':True}],pool_names=['candidate_00'],maximum_candidate_attempts=1)
        c.seal(native/name,value); c.seal(baseline/name,value)
    checked = []
    monkeypatch.setattr(t.w,'validate_inputs',lambda path:checked.append(Path(path)) or {'context_id':'tacle'})
    monkeypatch.setattr(t.prior,'workload',lambda:(_ for _ in ()).throw(AssertionError('Wrong BEEBS adapter')))
    t.check_baseline(prereg,native)
    assert checked == [native]
    c.seal(native/'commands.json',[{'baseline':False}])
    with pytest.raises(ValueError,match='receipt prefix'):
        t.check_baseline(prereg,native)


@pytest.fixture
def release_gate(tmp_path,monkeypatch):
    w = t.w
    native,prereg = tmp_path/'native',tmp_path/'prereg'
    monkeypatch.setattr(c,'ROOT',tmp_path)
    controller = tmp_path/w.SELECTION_CONTROLLER
    controller.parent.mkdir(parents=True); controller.write_text('bound controller')
    plan = dict(context_id='tacle',source_bindings={'sentinel':'value'})
    target = dict(context_id='tacle',native_order=[f'candidate_{i:02d}' for i in range(12)],pool_size=12)
    cohort = dict(schema=w.SELECTION_SCHEMA,policies=list(w.POLICIES),seeds=[0,1,2,3,4],
        area_caps=[32,64,128],budgets=[1,2,3],clock_mhz=12.,target_labels_observed=0,target_labels_read=0,
        targets={w.GROUP:target},source_bindings={**plan['source_bindings'],w.SELECTION_CONTROLLER:c.sha(controller)})
    c.seal(prereg/'cohort.json',cohort); c.seal(prereg/'manifest.json',{})
    c.seal(native/'evaluation-protocol.json',{'pool_names':target['native_order']})
    record = dict(schema=w.PROTOCOL['schema']+'-release',preregistration_root='prereg',zero_candidate_attempts=True,
        target_labels_observed=0,context_id='tacle',cohort_sha256=c.sha(prereg/'cohort.json'),
        manifest_sha256=c.sha(prereg/'manifest.json'),evaluation_protocol_sha256=c.sha(native/'evaluation-protocol.json'),
        prelabel_commit='0'*40,pushed_remote_head='0'*40)
    c.seal(native/'release.json',record)
    calls = []
    monkeypatch.setattr(w,'validate_inputs',lambda root:plan)
    monkeypatch.setattr(t.prior,'_manifest',lambda root:calls.append('manifest'))
    monkeypatch.setattr(t.prior,'check_git_checkpoint',lambda root,commit:calls.append('git blobs'))
    monkeypatch.setattr(t,'authenticate',lambda root:calls.append('complete models'))
    def remote(*args,**kwargs):
        calls.append('actual remote')
        return SimpleNamespace(stdout='0'*40+'\trefs/heads/ai-guided-ml\n')
    monkeypatch.setattr(w.subprocess,'run',remote)
    return native,record,calls


def test_release_requires_complete_models_then_actual_remote_head(release_gate):
    native,record,calls = release_gate
    assert t.w.check_release(native) == record
    assert calls == ['manifest','git blobs','complete models','actual remote']


def test_asserted_pushed_head_does_not_bypass_actual_remote(release_gate,monkeypatch):
    native,_,calls = release_gate
    monkeypatch.setattr(t.w.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(
        stdout='1'*40+'\trefs/heads/ai-guided-ml\n'))
    with pytest.raises(ValueError,match='Actual origin'):
        t.w.check_release(native)
    assert 'complete models' in calls


def test_metadata_only_release_cannot_bypass_missing_models(release_gate,monkeypatch):
    native,_,calls = release_gate
    def missing(root): raise ValueError('Missing complete models')
    monkeypatch.setattr(t,'authenticate',missing)
    with pytest.raises(ValueError,match='Missing complete models'):
        t.w.check_release(native)
    assert 'actual remote' not in calls


def test_annotation_distinguishes_unknown_infrastructure_from_known_invalid():
    public = {'device_fits':True,'area_delta_lut4':20,'routed_fmax_min_mhz':60,'speedup':1.01}
    labels = {'ok':public,'large':{**public,'area_delta_lut4':70},
        'bad':{'status':'failed','reference_censored':False},
        'unknown':{'status':'failed','reference_censored':True}}
    run = {'curve':[{'attempted_ids':list(labels)}]}
    outer = dict.fromkeys(labels,2.)
    t.annotate(run,labels,outer,64)
    assert run['curve'][0]['known_infeasible_attempts'] == 2
    assert run['curve'][0]['unknown_attempts'] == 1
    assert run['curve'][0]['target_outer_operation_seconds'] == 8.


def test_scientific_comparison_excludes_only_named_host_timers():
    left = {'speedup':1.1,'measurement_seconds':30.,'inference_seconds':2.,'mean_inference_seconds':3.}
    right = {**left,'inference_seconds':3.,'mean_inference_seconds':4.}
    assert t.stable(left) == t.stable(right)
    right['measurement_seconds'] += .01
    assert t.stable(left) != t.stable(right)


@pytest.fixture
def collector(tmp_path,monkeypatch,case):
    native,prereg,output = tmp_path/'native',tmp_path/'prereg',tmp_path/'collection'
    native.mkdir(); prereg.mkdir()
    target = dict(original_root=str(native),native_order=[f'candidate_{i:02d}' for i in range(12)])
    cohort = dict(qualification={'path':'results/2026-10-22-bitcount-qualification'},python_executable='python')
    c.seal(prereg/'manifest.json',{})
    released = tmp_path/'release.json'; c.seal(released,{})
    monkeypatch.setattr(t,'authenticate',lambda root:(cohort,t.w.GROUP,target,case))
    monkeypatch.setattr(t.prior,'_zero',lambda root:None)
    monkeypatch.setattr(t,'check_baseline',lambda *args:None)
    monkeypatch.setattr(t,'checked_release',lambda *args,**kwargs:{})
    monkeypatch.setattr(t.w,'check_release',lambda root:None)
    seen,calls = [],[]
    control = {'interrupt':None}
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        index = len(calls)
        calls.append(metadata['candidate_id'])
        assert metadata['index'] == index
        assert (output/'live.json').exists() == (index >= 3)
        if index < 3:
            proof = c.unseal(output/'acquisitions'/f'{index:02d}.json')
            assert proof['event']['candidate_id'] == metadata['candidate_id']
            assert proof['training_ids'][-index:] == seen if index else True
        if index == control['interrupt']:
            raise KeyboardInterrupt('No retry')
        seen.append(metadata['candidate_id'])
        c.seal(native/'outer-timing'/f'{index:03d}-measure.json',{'command':'measure'})
        c.seal(native/'attempt-ledger'/(metadata['native_name']+'.json'),{'status':'success'})
        return {'status':'success','returncode':0}
    monkeypatch.setattr(t.observed,'run',observe)
    def audit(root):
        return dict(charged_candidate_attempts=len(seen),outcomes=[case['labels'][i] for i in seen],candidate_wall_seconds_complete=True)
    monkeypatch.setattr(t.w,'audit',audit)
    return dict(native=native,prereg=prereg,output=output,release=released,calls=calls,seen=seen,control=control,case=case)


def test_native_controller_finishes_live_prefix_before_reference_collection(collector):
    f = collector
    result = t.collect(f['prereg'],f['native'],f['release'],f['output'])
    trace = c.unseal(f['output']/'live.json')
    assert result['status'] == 'complete'
    assert len(set(f['calls'])) == len(f['seen']) == 12
    assert trace['attempted_ids'] == f['calls'][:3]
    assert f['calls'][3:] == [row['candidate_id'] for row in f['case']['public'] if row['candidate_id'] not in f['calls'][:3]]
    assert c.unseal(f['output']/'manifest.json')['live.json'] == c.sha(f['output']/'live.json')


def test_interrupted_controller_preserves_prefix_and_cannot_silently_restart(collector):
    f = collector
    f['control']['interrupt'] = 1
    with pytest.raises(KeyboardInterrupt):
        t.collect(f['prereg'],f['native'],f['release'],f['output'])
    record = c.unseal(f['output']/'collection.json')
    assert record['status'] == 'interrupted' and record['paid_ids'] == f['calls'][:1]
    assert len(f['calls']) == 2 and not (f['output']/'live.json').exists()
    assert (f['output']/'manifest.json').exists()
    with pytest.raises(ValueError,match='Fresh output'):
        t.collect(f['prereg'],f['native'],f['release'],f['output'])

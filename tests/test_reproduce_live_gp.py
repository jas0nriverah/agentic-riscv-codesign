"""Only one host inference timer may differ; every scientific value stays exact."""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from isaforge import codesign as c
from scripts import reproduce_live_gp as r


def rows():
    return [dict(workload_group='beebs-expint',policy='hybrid_gp_adapt',cap=64,budget=budget,
        mean_verified_cycle_reduction=.01*budget,mean_target_measurement_seconds=40.*budget,
        mean_target_outer_operation_seconds=42.*budget,mean_charged_attempts=budget,
        mean_inference_seconds=.1*budget) for budget in (1,2,3)]


def test_only_host_mean_is_descriptive_and_both_values_are_preserved():
    archived=rows();fresh=copy.deepcopy(archived);fresh[1]['mean_inference_seconds']=.999
    result=r.endpoint_comparison(archived,fresh)
    assert result['endpoint_count']==3 and result['changed_host_timer_rows']==1
    assert result['observations'][1]['archived_mean_inference_seconds']==.2
    assert result['observations'][1]['replayed_mean_inference_seconds']==.999
    assert result['scientific_fields_exact'] and result['paid_measurement_costs_exact']
    assert result['tolerance_used'] is False
    assert archived[1]['mean_inference_seconds']==.2


@pytest.mark.parametrize('key',['mean_verified_cycle_reduction','mean_target_measurement_seconds',
    'mean_target_outer_operation_seconds','mean_charged_attempts'])
def test_no_tolerance_for_changed_scientific_or_paid_values(key):
    archived=rows();fresh=copy.deepcopy(archived);fresh[0][key]+=1e-10
    with pytest.raises(ValueError,match='Scientific endpoint'):r.endpoint_comparison(archived,fresh)


@pytest.mark.parametrize('change',['missing_row','duplicate_row','order','missing_host','extra_field','bool_value'])
def test_membership_types_and_inventory_cannot_hide_behind_host_timer_exception(change):
    archived=rows();fresh=copy.deepcopy(archived)
    if change=='missing_row':fresh.pop()
    elif change=='duplicate_row':fresh[1]=copy.deepcopy(fresh[0])
    elif change=='order':fresh.reverse()
    elif change=='missing_host':fresh[0].pop(r.HOST_FIELD)
    elif change=='extra_field':fresh[0]['ignored']=True
    else:fresh[0]['mean_charged_attempts']=True
    with pytest.raises(ValueError):r.endpoint_comparison(archived,fresh)


@pytest.mark.parametrize('value',[-1,float('nan'),float('inf'),True])
def test_host_timer_must_still_be_finite_numeric_nonnegative(value):
    archived=rows();fresh=copy.deepcopy(archived);fresh[0][r.HOST_FIELD]=value
    with pytest.raises(ValueError):r.endpoint_comparison(archived,fresh)


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    (tmp_path/'scripts').mkdir()
    (tmp_path/r.SOURCE).write_text('adapter source fixture')
    (tmp_path/r.frozen.SOURCE).write_text('frozen runtime fixture')
    campaign,prereg,failure,output=(tmp_path/name for name in ('campaign','prereg','failure','replayed'))
    target=dict(original_root=str(tmp_path/'original-native'))
    cohort=dict(source_bindings={'fixed':'source'},source_history='history/corpus.json',qualification=dict(path='qualification'))
    c.seal(prereg/'manifest.json',{})
    c.seal(prereg/'targets/beebs-expint/selection/protocol.json',{'frozen':True})
    for name in ('protocol.json','protocol.json.sha256'):
        dest=campaign/'selection'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((prereg/'targets/beebs-expint/selection'/name).read_bytes())
    for name in r.frozen.prior.FINAL_REPORTS:
        if name.endswith('.json'):c.seal(campaign/'selection'/name,dict(test=True))
    archived=rows();fresh=copy.deepcopy(archived);fresh[1][r.HOST_FIELD]+=.5
    audit=dict(outcomes=[],charged_candidate_attempts=6)
    live=dict(search=dict(curve=[dict(best_speedup=1.01,inference_seconds=.1)]));whole=dict(durations=dict(monotonic_elapsed_ns=10))
    provenance=dict(schema=r.frozen.SCHEMA+'-campaign',source_bindings=cohort['source_bindings'],
        preregistration='prereg',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),prelabel_commit='a'*40,
        live_best=copy.deepcopy(live['search']['curve'][-1]),collection_paired_durations=whole['durations'])
    for name,value in [('provenance',provenance),('audit',audit),('outer-times',{'candidate':42.}),('endpoints',archived),('release',{'test':True})]:
        c.seal(campaign/(name+'.json'),value)
    r.frozen.prior._seal_manifest(campaign)
    failure.mkdir();(failure/'strict-replay.log').write_text('ValueError: Final campaign decisions or costs differ\n')
    f=dict(schema='isaforge-live-gp-strict-replay-failure-v1',prelabel_commit='a'*40,
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'),frozen_runtime_sha256=c.sha(tmp_path/r.frozen.SOURCE),
        strict_log_sha256=c.sha(failure/'strict-replay.log'),error='Final campaign decisions or costs differ',
        source_changed=False,raw_or_model_artifacts_changed=False)
    c.seal(failure/'failure.json',f);r.frozen.prior._seal_manifest(failure)
    calls=[]
    monkeypatch.setattr(r.frozen,'authenticate',lambda path:(cohort,'beebs-expint',target,{}))
    monkeypatch.setattr(r.frozen.prior,'check_git_checkpoint',lambda *args:calls.append('git'))
    monkeypatch.setattr(r.frozen,'check_baseline',lambda *args:calls.append('baseline'))
    monkeypatch.setattr(r.frozen.prior,'check_release',lambda *args,**kwargs:calls.append('release'))
    def restore(snapshot,destination):destination.mkdir(parents=True);calls.append('native');return audit
    monkeypatch.setattr(r.frozen,'workload',lambda:SimpleNamespace(replay=restore))
    monkeypatch.setattr(r.frozen,'check_collection',lambda *args:(audit,{'candidate':42.},live,whole))
    monkeypatch.setattr(r.frozen.prior,'required_selection',lambda path:({'protocol.json','protocol.json.sha256'},{}))
    monkeypatch.setattr(r.frozen.prior,'verify_refits',lambda path:(calls.append('refits') or dict(exact_refits=True)))
    def evaluate(*args,**kwargs):
        assert kwargs['verify'] is True;calls.append('fixed-policy-replay')
        return dict(trajectories=180,endpoints=540,new_native_jobs=0)
    monkeypatch.setattr(r.frozen.experiment,'evaluate',evaluate)
    monkeypatch.setattr(r.frozen,'endpoints_for_source',lambda *args:fresh)
    return SimpleNamespace(campaign=campaign,prereg=prereg,failure=failure,output=output,archived=archived,fresh=fresh,calls=calls)


def test_explicit_replay_keeps_all_original_guards_and_records_amendment(fixture):
    f=fixture;before=c.sha(f.campaign/'endpoints.json')
    result=r.replay(f.campaign,f.output,failure_path=f.failure)
    assert f.calls==['git','native','baseline','release','refits','fixed-policy-replay']
    assert result['new_native_jobs']==0 and result['exact_refits'] is True
    assert result['phase']=='post-collection host-inference accounting amendment'
    assert result['changed_host_timer_rows']==1
    assert c.unseal(f.output/'archived-endpoints.json')==f.archived
    assert c.unseal(f.output/'replayed-endpoints.json')==f.fresh
    assert c.sha(f.campaign/'endpoints.json')==before
    assert (f.output/'strict-replay-failure.log').read_bytes()==(f.failure/'strict-replay.log').read_bytes()
    assert result['preserved_strict_failure']['log_sha256']==c.sha(f.failure/'strict-replay.log')


def test_replay_rejects_changed_paid_duration_before_amendment(fixture):
    f=fixture;f.fresh[0]['mean_target_measurement_seconds']+=.001
    with pytest.raises(ValueError,match='Scientific endpoint'):r.replay(f.campaign,f.output,failure_path=f.failure)
    assert not (f.output/'host-inference-amendment.json').exists()


def test_resealed_strict_failure_log_change_rejected_before_model_refits(fixture):
    f=fixture;(f.failure/'strict-replay.log').write_text('different error')
    r.frozen.prior._seal_manifest(f.failure)
    with pytest.raises(ValueError,match='preserved frozen strict'):r.replay(f.campaign,f.output,failure_path=f.failure)
    assert f.calls==[]

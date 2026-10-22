"""One acquisition change, strict provider budgets and successful-paid GP fits."""
import copy
import math

import pytest

from isaforge import codesign as c,count_selection as count
from scripts import evaluate_count_acquisition as study


@pytest.fixture
def case():
    package=study.LIVE/'selection/controls11/model'
    public=c.unseal(package/'public.json');history=c.unseal(package/'history.json')
    predictions=c.unseal(package/'predictions.json')[0]
    labels={row['candidate_id']:row for row in c.unseal(study.LIVE/'audit.json')['outcomes']}
    return public,history,predictions,labels


def factory_fixture(predictions,paid,history):
    fits=[];initial={row['candidate_id']:row for row in predictions['hardware']}
    class Fake:
        def fit(self,rows):
            ids=[row['candidate_id'] for row in rows]
            assert ids==[row['candidate_id'] for row in history]+[row['candidate_id'] for row in paid if row.get('status','success')=='success']
            assert all(row.get('status','success')=='success' for row in rows)
            fits.append(ids)
            return self
        def predict(self,public):
            assert all(set(row)==set(count.b.PUBLIC_KEYS) for row in public)
            return [copy.deepcopy(initial[row['candidate_id']]) for row in public]
    return Fake,fits


def test_score_removes_only_inverse_time_and_preserves_benefit_units(case):
    public,_,prediction,_=case
    row=public[0];hardware=prediction['hardware'][0]
    inverse=math.exp(-hardware['log_measurement_seconds_mean']+.5*hardware['log_measurement_seconds_std']**2)
    assert count.count_score(row,hardware,1.,64,12)*inverse==count.b.hybrid_score(row,hardware,1.,64,12)
    changed=dict(hardware,log_measurement_seconds_mean=100.,log_measurement_seconds_std=20.)
    assert count.count_score(row,changed,1.,64,12)==count.count_score(row,hardware,1.,64,12)
    assert count.count_score(row,hardware,row['latency_features']['estimated_speedup'],64,12)==0


def test_provider_only_paid_updates_and_pre_release_observer(case,monkeypatch):
    public,history,prediction,labels=case;paid=[];events=[];original=copy.deepcopy(prediction)
    factory,fits=factory_fixture(prediction,paid,history)
    clock=iter([0.,.25,.25,.75]);monkeypatch.setattr(count.time,'monotonic',lambda:next(clock))
    def acquire(event):
        assert event['charged_before_query']==len(paid)
        assert event['attempted_ids_before_query']==[row['candidate_id'] for row in paid]
        assert event['paid_target_ids_before_query']==[row['candidate_id'] for row in paid]
        events.append(copy.deepcopy(event))
        # Observer cannot mutate actual policy state.
        event['hardware_predictions'].clear()
    def provider(row):
        assert len(events)==len(paid)+1
        assert set(row)==set(count.b.PUBLIC_KEYS)
        assert row['candidate_id']==events[-1]['candidate_id']
        assert row['candidate_id'] not in {value['candidate_id'] for value in paid}
        outcome=copy.deepcopy(labels[row['candidate_id']]);paid.append(outcome);return outcome
    result=count.search(public,history,provider,area_cap=64,seed=0,budget=3,predictions=prediction,
                        surrogate_factory=factory,on_acquire=acquire)
    assert len(paid)==3 and len(fits)==2 and result['paid_update_calls']==2
    assert result['curve'][-1]['attempted_ids']==[row['candidate_id'] for row in paid]
    assert result['curve'][-1]['target_measurement_seconds']==sum(row['measurement_seconds'] for row in paid)
    assert result['paid_update_host_seconds']==.75
    assert [point['inference_seconds']-result['cached_initial_inference_seconds'] for point in result['curve']]==pytest.approx([0.,.25,.75])
    assert result['cached_initial_predictions_reused'] is True and prediction==original


def test_failed_query_is_charged_unknown_and_never_enters_gp(case):
    public,history,prediction,labels=case;paid=[]
    factory,fits=factory_fixture(prediction,paid,history)
    def provider(row):
        outcome=copy.deepcopy(labels[row['candidate_id']]) if paid else dict(row,status='failed',error='fixture infrastructure failure',
            failure_class='infrastructure_unknown',reference_censored=True,measurement_seconds=3.)
        paid.append(outcome);return outcome
    result=count.search(public,history,provider,area_cap=64,seed=0,budget=3,predictions=prediction,surrogate_factory=factory)
    assert len(paid)==3 and len(fits)==1 and result['paid_update_calls']==1
    assert [point['failed_attempts'] for point in result['curve']]==[1,1,1]
    assert result['curve'][0]['best_speedup']==1.
    assert result['curve'][-1]['target_measurement_seconds']==sum(row['measurement_seconds'] for row in paid)
    assert paid[0]['candidate_id'] not in fits[0]


def test_first_query_uses_cache_without_initial_fit_and_matches_counterfactual(case):
    public,history,prediction,labels=case
    def forbidden():raise AssertionError('No initial model fit is allowed')
    result=count.search(public,history,lambda row:labels[row['candidate_id']],area_cap=64,seed=0,budget=1,
                        predictions=prediction,surrogate_factory=forbidden)
    chosen=next(row for row in public if row['candidate_id']==result['curve'][0]['attempted_ids'][0])
    assert chosen['formula']=='addi(andi(sub(0,sltiu(in0,1)),998),2)'
    assert result['paid_update_calls']==0 and result['paid_update_host_seconds']==0
    assert result['curve'][0]['best_speedup']==31843/31832


@pytest.mark.parametrize('budget',[0,7,True])
def test_invalid_budget_never_calls_provider(case,budget):
    public,history,prediction,_=case
    def forbidden(row):raise AssertionError('No outcome release for invalid budget')
    with pytest.raises(ValueError,match='budget'):
        count.search(public,history,forbidden,area_cap=64,seed=0,budget=budget,predictions=prediction)


def test_hidden_target_labels_in_public_or_incomplete_cache_rejected(case):
    public,history,prediction,_=case
    polluted=copy.deepcopy(public);polluted[0]['candidate_cycles']=1
    with pytest.raises(ValueError,match='non-public'):
        count.search(polluted,history,lambda _:None,area_cap=64,seed=0,budget=3,predictions=prediction)
    missing=copy.deepcopy(prediction);missing['hardware'].pop()
    with pytest.raises(ValueError,match='Complete unique cached'):
        count.search(public,history,lambda _:None,area_cap=64,seed=0,budget=3,predictions=missing)


def test_provider_exception_stops_without_retry(case):
    public,history,prediction,_=case;called=[];observed=[]
    def provider(row):called.append(row['candidate_id']);raise OSError('fixture failure')
    with pytest.raises(OSError,match='fixture failure'):
        count.search(public,history,provider,area_cap=64,seed=0,budget=3,predictions=prediction,on_acquire=observed.append)
    assert len(called)==len(observed)==1


def test_prepare_seals_all_nine_caches_before_any_target_scoring(tmp_path,monkeypatch):
    original=study.c.unseal
    forbidden_paths={spec['audit'] for spec in study.specs()}|{study.CORPUS}
    def unseal(path):
        assert path not in forbidden_paths,'prepare must not deserialize target outcomes'
        return original(path)
    monkeypatch.setattr(study.c,'unseal',unseal)
    protocol=study.prepare(tmp_path/'prepared')
    assert len(protocol['cases'])==9 and protocol['policies']==list(study.POLICIES)
    assert protocol['surrogate_factory']=='isaforge.budgeted_selection.HardwareSurrogate'
    assert protocol['feature_columns']==list(count.b.STRUCTURAL_COLUMNS)
    assert [case['fitting_rows'] for case in protocol['cases']]==[44,33,29,38,68,55,50,71,67]
    release=original(tmp_path/'prepared/prediction-release.json')
    assert len(release['initial_prediction_files'])==72 and release['target_scoring_started'] is False
    assert release['initial_model_refits']==release['initial_model_predictions']==0
    assert study.authenticate(tmp_path/'prepared')==protocol


def test_changed_protocol_or_omitted_cached_file_fails_before_search(tmp_path,monkeypatch):
    root=tmp_path/'prepared';study.prepare(root)
    called=[];monkeypatch.setattr(study.count,'search',lambda *_a,**_k:called.append('search'))
    protocol=c.unseal(root/'protocol.json');protocol['gp_settings']['alpha']=.1;c.seal(root/'protocol.json',protocol)
    with pytest.raises(ValueError,match='Prepared source'):study.run(root)
    assert not called
    second=tmp_path/'other';study.prepare(second)
    file=next((second/'inputs').rglob('predictions.json'));file.unlink()
    with pytest.raises(ValueError,match='Complete exact initial prediction inventory'):study.run(second)
    assert not called


def test_full_orchestration_and_replay_keep_all_controls_and_shared_costs(tmp_path,monkeypatch):
    """Fake update predictions exercise all outputs; no scientific fit is run."""
    original=count.search
    def fake_search(public,history,provider,**kwargs):
        predictions=kwargs['predictions'];hardware={row['candidate_id']:row for row in predictions['hardware']}
        class Fake:
            def fit(self,rows):
                assert len(rows)>len(history) and all(row.get('status','success')=='success' for row in rows)
                return self
            def predict(self,remaining):return [copy.deepcopy(hardware[row['candidate_id']]) for row in remaining]
        assert kwargs['surrogate_factory'] is count.b.HardwareSurrogate
        kwargs['surrogate_factory']=Fake
        return original(public,history,provider,**kwargs)
    monkeypatch.setattr(study.count,'search',fake_search)
    root=tmp_path/'prepared';study.prepare(root);result=study.run(root)
    assert result['new_policy_trajectories']==135 and result['new_policy_seed_endpoints']==405
    assert len(result['policies'])==13 and len(result['endpoints'])==1053
    assert result['archived_control_seed_endpoints']==4860
    assert result['costs']['unique_charged_attempts']==90 and len(result['costs']['preserved_failures'])==3
    assert result['costs']['actual_calendar_wall_seconds'] is None
    assert len(result['first_query_comparisons'])==135
    assert all(row['source_count']==3 for row in result['primary'])
    for spec in study.specs():
        assert c.sha(root/'controls'/spec['case_id']/'report.json')==c.sha(spec['package']/'report.json')
    repeated=study.replay(root,tmp_path/'replay')
    assert study.stable(repeated)==study.stable(result)
    assert c.unseal(tmp_path/'replay/replay-verification.json')['compared_new_trajectories']==135
    with pytest.raises(ValueError,match='Fresh prepared run'):study.run(root)

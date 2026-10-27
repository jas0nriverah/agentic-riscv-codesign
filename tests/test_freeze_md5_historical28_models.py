"""Synthetic guard/order tests: no training corpus, target outcomes or model fits."""
import copy
from pathlib import Path
import subprocess

import pytest

from scripts import freeze_md5_historical28_models as w


@pytest.fixture(autouse=True)
def forbid_native_and_all_fits(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('No fitting/native/outcome operation in synthetic tests')
    monkeypatch.setattr(subprocess,'run',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
    from isaforge import budgeted_selection as b,semantic_selection as s
    from isaforge.model import SpeedupPredictor
    from isaforge.ranking import SpeedupRanker
    from isaforge.feasible_benefit import FeasibleBenefitPredictor
    from isaforge.feasibility_selection import FeasibilitySelectionPredictor
    for cls in (SpeedupPredictor,SpeedupRanker,b.NormalizedSpeedupPredictor,b.HardwareSurrogate,
                FeasibleBenefitPredictor,FeasibilitySelectionPredictor,s.SemanticHardwareSurrogate):
        monkeypatch.setattr(cls,'fit',forbidden)
    original=Path.open
    def guarded(path,*a,**k):
        require=not path.resolve().is_relative_to(w.ROOT/'results') and not path.resolve().is_relative_to(w.ROOT/'generated')
        assert require,'No historical or target artifact reads in synthetic tests'
        return original(path,*a,**k)
    monkeypatch.setattr(Path,'open',guarded)


def test_adapter_pin_stops_before_any_history_or_fit(monkeypatch):
    monkeypatch.setattr(w,'sha',lambda path:'changed')
    monkeypatch.setattr(w.identity,'load_public_pool',lambda *a:pytest.fail('Pin must precede pool/history reads'))
    with pytest.raises(ValueError,match='Reviewed adapter changed'):w.preflight()


def test_bound_source_changes_rejected_before_fit(tmp_path,monkeypatch):
    monkeypatch.setattr(w,'ROOT',tmp_path)
    path=tmp_path/'bound.py';path.write_text('bound')
    class Pool:
        def validate(self):return []
    data={'pool':Pool(),'source_bindings':{'bound.py':w.sha(path)}}
    w.revalidate(data);path.write_text('changed')
    with pytest.raises(ValueError,match='Bound input changed'):w.revalidate(data)


def test_framing_deserializes_only_allowlisted_records(tmp_path):
    # Reuse the audited pure function; importing its main-guarded module launches nothing.
    module=w.load_source_module(w.ROOT/w.AUDIT.parent/'audit.py','synthetic_frame_test')
    allowed='a'*64;excluded='b'*64
    payload=('[{"candidate_id":"'+allowed+'","value":1},'
             '{"candidate_id":"'+excluded+'","uninterpreted":NaN}]').encode()
    rows,skipped=module.frame_allowlisted(payload,{allowed})
    assert rows==[{'candidate_id':allowed,'value':1}] and skipped==[excluded]


def test_finite_initial_stops_in_observer_before_provider(monkeypatch):
    from isaforge import finite_selection as f
    called=[]
    def search(public,training,provider,**kwargs):
        proof={'event':{'charged_before_query':0,'planned_budget':kwargs['budget']},'successful_paid_ids':[]}
        kwargs['on_acquire'](proof)
        called.append('after-observer')
        provider(None)
    monkeypatch.setattr(f,'search',search)
    for budget in (1,2,3):
        result=w.finite_initial([],[],None,policy=f.LOOKAHEAD,seed=0,budget=budget)
        assert result['planned_budget']==budget and result['paid_target_queries']==0
        assert result['realized_trajectory'] is None
    assert called==[]


def test_static_orders_are_separate_from_incumbent_dependent_initial_scores():
    policies=['frequency','merit','calibrated_latency','latency_cost_heuristic','random','raw_regression',
        'ranking','normalized_xgb','hybrid_gp_zero_shot','hybrid_gp_adapt','feasible_benefit_xgb',
        'factorized_feasibility_xgb','hybrid_gp_adapt_count','hybrid_gp_adapt_count_semantic']
    public=[dict(candidate_id=f'public{i}',runs=i+1,saved=3-i,tree_op_count=2,
        latency_features={'estimated_speedup':1.01+i*.01}) for i in range(3)]
    training=[dict(area_delta_lut4=20,tree_op_count=2,routed_fmax_min_mhz=60)]
    rows=[dict(candidate_id=r['candidate_id'],mean=1.,rank_score=i,mean_fractional_cycle_savings=.1,
        decision_score=.1,area_delta_lut4_mean=20.,area_delta_lut4_std=1.,routed_fmax_min_mhz_mean=60.,
        routed_fmax_min_mhz_std=1.,log_measurement_seconds_mean=1.,log_measurement_seconds_std=.1,
        device_fit_probability=.9) for i,r in enumerate(public)]
    predictions={key:copy.deepcopy(rows) for key in ('raw','ranking','normalized','hardware','utility','feasibility')}
    orders=w.initial_controls(public,training,predictions,rows,0,policies)
    assert len(orders)==14
    for row in orders:
        assert (row['full_static_order'] is not None)==(row['policy'] in w.STATIC)
        assert row['paid_prefix']==[] and row['target_labels_read']==0
    assert next(r for r in orders if r['policy']=='frequency')['chosen_id']=='public2'
    assert next(r for r in orders if r['policy']=='merit')['chosen_id']=='public0'


def test_fresh_output_gate_precedes_metadata_or_fit(tmp_path,monkeypatch):
    monkeypatch.setattr(w,'ROOT',tmp_path)
    monkeypatch.setattr(w,'preflight',lambda:pytest.fail('Must stop before metadata or fits'))
    with pytest.raises(ValueError,match='Fresh direct'):w.build(tmp_path/'outside')
    output=tmp_path/w.PREREG/'already';output.mkdir(parents=True)
    with pytest.raises(ValueError,match='Fresh direct'):w.build(output)

"""Decision utility, candidate-level bootstrap, and paid final acceptance."""
import copy
from pathlib import Path
import numpy as np
import pytest

from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasible_benefit import (FeasibleBenefitPredictor, decision_utility,
                                     search, AREA_CAPS)
from isaforge.prospective_selection import PUBLIC_KEYS

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def rows():
    history=c.unseal(ROOT/'results/2026-10-21-sha256-selection/model/history.json')
    result=copy.deepcopy(history[:2])
    for index,row in enumerate(result):
        row['area_delta_lut4']=(20,90)[index]
    return result

def public(rows):
    return [{key:copy.deepcopy(row[key]) for key in PUBLIC_KEYS} for row in rows]

def test_utility_conditions_and_boundary(rows):
    row=rows[0]; row['area_delta_lut4']=64
    expected=(row['baseline_cycles']-row['candidate_cycles'])/b.occurrence_count(row)
    assert expected>0 and decision_utility(row,64)==expected
    assert decision_utility(row,32)==0
    row['device_fits']=False
    assert decision_utility(row,128)==0
    row['device_fits']=True;row['routed_fmax_min_mhz']=11.999
    assert decision_utility(row,128)==0
    row['routed_fmax_min_mhz']=12
    assert decision_utility(row,128)==expected

def test_slowdowns_remain_signed_and_failures_unknown(rows):
    row=rows[0]
    row['candidate_cycles']=row['baseline_cycles']+b.occurrence_count(row)
    row['speedup']=row['baseline_cycles']/row['candidate_cycles']
    assert decision_utility(row,64)==-1
    failed={**public([row])[0], 'status':'failed','measurement_seconds':1.0,'error':'unknown'}
    with pytest.raises(ValueError,match='unknown decision utility'):decision_utility(failed,64)

def test_candidate_bootstrap_caps_share_draw_and_total_weight(rows,monkeypatch):
    import xgboost
    captured=[]
    class Spy:
        def __init__(self,**kwargs): self.settings=kwargs
        def fit(self,x,y,sample_weight):
            captured.append((x.copy(),y.copy(),sample_weight.copy(),self.settings))
    monkeypatch.setattr(xgboost,'XGBRegressor',Spy)
    model=FeasibleBenefitPredictor(seed=3).fit(rows)
    assert len(model.models)==len(captured)==20
    for x,y,weights,settings in captured:
        assert x.shape==(len(rows)*3,len(b.STRUCTURAL_COLUMNS)+1)
        assert weights.sum()==pytest.approx(len(rows))
        assert np.all(weights==1/3)
        for offset in range(0,len(x),3):
            assert np.array_equal(x[offset,:-1],x[offset+1,:-1])
            assert np.array_equal(x[offset,:-1],x[offset+2,:-1])
            assert x[offset+1,-1]==2*x[offset,-1]
            assert x[offset+2,-1]==4*x[offset,-1]
        assert settings['n_estimators']==80 and settings['max_depth']==2
        assert settings['objective']=='reg:squarederror'

def test_constant_zero_utility_is_not_speedup(rows):
    for row in rows: row['area_delta_lut4']=1000
    model=FeasibleBenefitPredictor().fit(rows)
    predictions=model.predict(public(rows),area_cap=64)
    assert model.constant==0 and model.models==[]
    assert all(p['mean_fractional_cycle_savings']==0 for p in predictions)
    assert all(p['std_saved_cycles_per_occurrence']==0 for p in predictions)
    assert all('speedup' not in p and p['uncertainty_calibrated'] is False for p in predictions)
    with pytest.raises(ValueError,match='non-public'):model.predict(rows,area_cap=64)

def test_model_is_seed_reproducible_and_saves_fraction_units(rows):
    a=FeasibleBenefitPredictor(7).fit(rows).predict(public(rows),area_cap=64)
    other=FeasibleBenefitPredictor(7).fit(rows).predict(public(rows),area_cap=64)
    assert a==other
    for prediction,row in zip(a,rows):
        assert prediction['mean_fractional_cycle_savings']==pytest.approx(
            prediction['mean_saved_cycles_per_occurrence']*b.occurrence_count(row)/row['baseline_cycles'])

def test_model_does_not_mutate_training(rows):
    original=copy.deepcopy(rows)
    FeasibleBenefitPredictor().fit(rows)
    assert rows==original

def test_duplicate_candidates_rejected(rows):
    with pytest.raises(ValueError,match='Unique measured candidates'):
        FeasibleBenefitPredictor().fit([rows[0],rows[0]])

@pytest.mark.parametrize('cap',[0,True,65,129])
def test_invalid_caps_rejected(rows,cap):
    model=FeasibleBenefitPredictor().fit(rows)
    with pytest.raises(ValueError,match='area cap'):model.predict(public(rows),area_cap=cap)

def test_paid_search_charges_failures_and_uses_actual_acceptance(rows):
    pool=public(rows); identities=[r['candidate_id'] for r in pool]
    predictions=[dict(candidate_id=identity,area_cap=64,mean_fractional_cycle_savings=2-index)
                 for index,identity in enumerate(identities)]
    # Highest predicted utility fails. The second candidate is measured over cap.
    failed={**pool[0],'status':'failed','measurement_seconds':5.0,'error':'unknown correctness'}
    lookup={identities[0]:failed,identities[1]:rows[1]};calls=[]
    def provider(row):calls.append(row['candidate_id']);return lookup[row['candidate_id']]
    result=search(pool,provider,area_cap=64,seed=0,budget=2,predictions=predictions)
    assert calls==identities
    assert result['curve'][0]['failed_attempts']==1
    assert result['curve'][-1]['best_speedup']==1 and result['curve'][-1]['selected_id'] is None
    assert result['curve'][-1]['attempted_ids']==identities
    assert result['curve'][-1]['target_measurement_seconds']==5+rows[1]['measurement_seconds']
    assert [e['charged'] for e in result['events'] if 'observation' in e]==[1,2]

def test_verified_feasible_search_wins_and_rejects_bad_predictions(rows):
    pool=public(rows)
    predictions=[dict(candidate_id=r['candidate_id'],area_cap=64,mean_fractional_cycle_savings=2-i)
                 for i,r in enumerate(pool)]
    lookup={r['candidate_id']:r for r in rows}
    result=search(pool,lambda row:lookup[row['candidate_id']],area_cap=64,seed=0,budget=2,predictions=predictions)
    assert result['curve'][-1]['best_speedup']==rows[0]['speedup']
    assert result['curve'][-1]['selected_id']==rows[0]['candidate_id']
    with pytest.raises(ValueError,match='Complete unique'):
        search(pool,lambda row:None,area_cap=64,seed=0,budget=1,predictions=predictions[:1])
    predictions[0]['area_cap']=32
    with pytest.raises(ValueError,match='budget differs'):
        search(pool,lambda row:None,area_cap=64,seed=0,budget=1,predictions=predictions)

def test_unfitted_empty_and_invalid_seed(rows):
    with pytest.raises(ValueError,match='Fit feasible'):FeasibleBenefitPredictor().predict([],area_cap=64)
    with pytest.raises(ValueError,match='seed'):FeasibleBenefitPredictor(True)
    assert FeasibleBenefitPredictor().fit(rows).predict([],area_cap=64)==[]


def test_portable_json_model_roundtrip(rows,tmp_path):
    model=FeasibleBenefitPredictor(4).fit(rows)
    expected={cap:model.predict(public(rows),area_cap=cap) for cap in AREA_CAPS}
    schema=model.save(tmp_path/'model')
    assert len(schema['model_artifacts'])==20
    restored=FeasibleBenefitPredictor.load(tmp_path/'model')
    assert restored.training_ids==model.training_ids
    assert restored.area_per_op==model.area_per_op
    assert {cap:restored.predict(public(rows),area_cap=cap) for cap in AREA_CAPS}==expected
    with pytest.raises(ValueError,match='Fresh exported'):model.save(tmp_path/'model')


def test_constant_model_roundtrip(rows,tmp_path):
    for row in rows: row['area_delta_lut4']=1000
    model=FeasibleBenefitPredictor().fit(rows)
    schema=model.save(tmp_path/'constant')
    assert schema['constant']==0 and schema['model_artifacts']=={}
    restored=FeasibleBenefitPredictor.load(tmp_path/'constant')
    assert restored.predict(public(rows),area_cap=64)==model.predict(public(rows),area_cap=64)


@pytest.mark.parametrize('change',['booster','source','package','settings','ensemble_count'])
def test_portable_model_rejects_tampering(rows,tmp_path,change):
    folder=tmp_path/'model'
    FeasibleBenefitPredictor().fit(rows).save(folder)
    schema=c.unseal(folder/'schema.json')
    if change=='booster':
        with (folder/'member-00.json').open('a') as stream:stream.write(' ')
    elif change=='source':schema['source_bindings']['isaforge/feasible_benefit.py']='0'*64
    elif change=='package':schema['packages']['xgboost']='0.0.0'
    elif change=='settings':schema['settings']['n_estimators']=81
    else:del schema['model_artifacts']['member-00.json']
    c.seal(folder/'schema.json',schema)
    with pytest.raises(ValueError):FeasibleBenefitPredictor.load(folder)

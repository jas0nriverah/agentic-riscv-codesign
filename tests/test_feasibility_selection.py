"""Fixed factorization: binary targets, candidate bootstrap, strict portable inputs."""
import copy
from pathlib import Path

import numpy as np
import pytest

from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasibility_selection import (
    AREA_CAPS, MODEL_SETTINGS, FeasibilitySelectionPredictor, feasibility_label)
from isaforge.prospective_selection import PUBLIC_KEYS

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def rows():
    history=c.unseal(ROOT/'results/2026-10-21-sha256-selection/model/history.json')
    result=copy.deepcopy(history[:2])
    result[0]['area_delta_lut4']=16
    result[1]['area_delta_lut4']=200
    return result


def public(rows):
    return [{key:copy.deepcopy(row[key]) for key in PUBLIC_KEYS} for row in rows]


def test_binary_hardware_targets_are_not_speedup_or_utility(rows):
    row=rows[0]
    assert [feasibility_label(row,cap) for cap in AREA_CAPS]==[1,1,1]
    row['area_delta_lut4']=64
    assert [feasibility_label(row,cap) for cap in AREA_CAPS]==[0,1,1]
    row['routed_fmax_min_mhz']=11.999
    assert feasibility_label(row,128)==0
    row['routed_fmax_min_mhz']=12;row['device_fits']=False
    assert feasibility_label(row,128)==0
    row['device_fits']=True
    row['candidate_cycles']=row['baseline_cycles']+b.occurrence_count(row)
    row['speedup']=row['baseline_cycles']/row['candidate_cycles']
    assert row['speedup']<1 and feasibility_label(row,128)==1
    assert feasibility_label(rows[1],128)==0


def test_failures_are_unknown_not_zero_class(rows):
    failed=dict(public(rows)[0],status='failed',measurement_seconds=2,error='unknown hardware outcome')
    with pytest.raises(ValueError,match='unknown feasibility'):feasibility_label(failed,64)
    with pytest.raises(ValueError,match='cannot train feasibility'):FeasibilitySelectionPredictor().fit([failed])


def test_candidate_bootstrap_preserves_caps_weights_and_rng_even_for_constant_members(rows,monkeypatch):
    import xgboost
    fits=[]
    class Spy:
        def __init__(self,**settings):self.settings=settings
        def fit(self,x,y,sample_weight):
            assert set(y)=={0,1}  # Single-class bootstraps must never reach XGBoost.
            fits.append((x.copy(),y.copy(),sample_weight.copy(),self.settings))
    monkeypatch.setattr(xgboost,'XGBClassifier',Spy)
    model=FeasibilitySelectionPredictor(seed=9).fit(rows)
    rng=np.random.default_rng(9);expected=[];constant=[]
    for _ in range(20):
        sampled=rng.integers(0,2,size=2)
        expected.append(int(rng.integers(0,2**31-1)))
        constant.append(float(1-sampled[0]) if sampled[0]==sampled[1] else None)
    assert model.member_seeds==expected and model.constants==constant
    assert any(value==0 for value in constant) and any(value==1 for value in constant)
    assert len(fits)==sum(value is None for value in constant)
    assert [settings['random_state'] for *_,settings in fits]==[
        seed for seed,value in zip(expected,constant) if value is None]
    for x,y,weight,settings in fits:
        assert x.shape==(6,len(b.STRUCTURAL_COLUMNS)+1)
        assert weight.sum()==pytest.approx(2) and np.all(weight==1/3)
        for offset in (0,3):
            assert np.array_equal(x[offset,:-1],x[offset+1,:-1])
            assert np.array_equal(x[offset,:-1],x[offset+2,:-1])
            assert x[offset+1,-1]==2*x[offset,-1]
            assert x[offset+2,-1]==4*x[offset,-1]
            assert y[offset]==y[offset+1]==y[offset+2]
        assert settings['objective']=='binary:logistic'
        assert settings['n_estimators']==80 and settings['max_depth']==2
        assert settings['learning_rate']==.05 and settings['reg_lambda']==1


@pytest.mark.parametrize('label',[0,1])
def test_all_single_class_members_fall_back_exactly_without_confidence_claim(rows,label,monkeypatch):
    import xgboost
    for row in rows:row['area_delta_lut4']=16 if label else 200
    def must_not_fit(**kwargs):raise AssertionError('Single class should not fit a classifier')
    monkeypatch.setattr(xgboost,'XGBClassifier',must_not_fit)
    model=FeasibilitySelectionPredictor(seed=0).fit(rows)
    assert model.constants==[float(label)]*20 and model.models==[None]*20
    for prediction,row in zip(model.predict(public(rows),area_cap=64),rows):
        benefit=max(0,row['latency_features']['estimated_saved_cycles']/row['latency_features']['baseline_cycles'])
        assert prediction['feasibility_scores']==[float(label)]*20
        assert prediction['feasibility_score_mean']==label and prediction['feasibility_score_std']==0
        assert prediction['decision_score']==label*benefit
        assert prediction['calibrated'] is False
        assert prediction['uncertainty_kind']=='bootstrap estimator disagreement'
        assert 'speedup' not in prediction


@pytest.mark.parametrize('saved',[0,-100])
def test_zero_and_negative_analytic_gain_clamped_without_changing_feasibility(rows,saved):
    for row in rows:row['area_delta_lut4']=16
    model=FeasibilitySelectionPredictor().fit(rows)
    pool=public(rows)
    for row in pool:row['latency_features']['estimated_saved_cycles']=saved
    predictions=model.predict(pool,area_cap=64)
    assert all(p['feasibility_score_mean']==1 and p['decision_score']==0 and
               p['analytic_fractional_cycle_savings']==0 for p in predictions)


def test_real_classifier_repeatability_and_fixed_factorization(rows):
    a=FeasibilitySelectionPredictor(3).fit(rows)
    other=FeasibilitySelectionPredictor(3).fit(rows)
    assert a.predict(public(rows),area_cap=64)==other.predict(public(rows),area_cap=64)
    for prediction,row in zip(a.predict(public(rows),area_cap=64),rows):
        assert len(prediction['feasibility_scores'])==20
        assert prediction['feasibility_score_mean']==pytest.approx(np.mean(prediction['feasibility_scores']))
        assert prediction['feasibility_score_std']==pytest.approx(np.std(prediction['feasibility_scores']))
        benefit=max(0,row['latency_features']['estimated_saved_cycles']/row['latency_features']['baseline_cycles'])
        assert prediction['decision_score']==prediction['feasibility_score_mean']*benefit


def test_fit_and_predict_do_not_mutate_rows(rows):
    before=copy.deepcopy(rows);pool=public(rows);original=copy.deepcopy(pool)
    FeasibilitySelectionPredictor().fit(rows).predict(pool,area_cap=64)
    assert rows==before and pool==original


@pytest.mark.parametrize('leak',['speedup','nested_outcome'])
def test_target_labels_rejected_by_public_prediction_boundary(rows,leak):
    model=FeasibilitySelectionPredictor().fit(rows);pool=public(rows)
    if leak=='speedup':pool[0]['speedup']=1.1
    else:pool[0]['latency_features']['area_delta_lut4']=20
    with pytest.raises(ValueError,match='non-public|Non-public'):model.predict(pool,area_cap=64)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,None])
def test_bad_analytic_benefit_rejected(rows,bad):
    model=FeasibilitySelectionPredictor().fit(rows);pool=public(rows)
    pool[0]['latency_features']['estimated_saved_cycles']=bad
    with pytest.raises(ValueError):model.predict(pool,area_cap=64)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),0,True])
def test_bad_training_features_rejected(rows,bad):
    rows[0]['tree_op_count']=bad
    with pytest.raises(ValueError):FeasibilitySelectionPredictor().fit(rows)


def test_duplicate_candidates_and_nonpositive_area_proxy_rejected(rows):
    with pytest.raises(ValueError,match='Unique nonempty'):FeasibilitySelectionPredictor().fit([rows[0],rows[0]])
    for row in rows:row['area_delta_lut4']=0
    with pytest.raises(ValueError,match='historical LUT4'):FeasibilitySelectionPredictor().fit(rows)


@pytest.mark.parametrize('cap',[True,0,65,float('nan')])
def test_unsupported_caps_rejected(rows,cap):
    model=FeasibilitySelectionPredictor().fit(rows)
    with pytest.raises(ValueError,match='Unsupported area cap'):model.predict(public(rows),area_cap=cap)


def test_unfitted_empty_and_seed_validation(rows):
    with pytest.raises(ValueError,match='Fit feasibility'):FeasibilitySelectionPredictor().predict([],area_cap=64)
    with pytest.raises(ValueError,match='Invalid model seed'):FeasibilitySelectionPredictor(True)
    assert FeasibilitySelectionPredictor().fit(rows).predict([],area_cap=64)==[]


def test_mixed_constant_classifier_export_roundtrip_exactly(rows,tmp_path):
    model=FeasibilitySelectionPredictor(9).fit(rows)
    folder=tmp_path/'model';schema=model.save(folder)
    assert len(schema['members'])==20 and 0<len(schema['model_artifacts'])<20
    assert {entry['constant'] for entry in schema['members'] if 'constant' in entry}=={0,1}
    restored=FeasibilitySelectionPredictor.load(folder)
    assert restored.training_ids==model.training_ids and restored.area_per_op==model.area_per_op
    assert restored.member_seeds==model.member_seeds and restored.constants==model.constants
    for cap in AREA_CAPS:assert restored.predict(public(rows),area_cap=cap)==model.predict(public(rows),area_cap=cap)
    # Portable re-export preserves exact booster bytes and schema metadata.
    assert restored.save(tmp_path/'reexport')==schema
    with pytest.raises(ValueError,match='Fresh exported'):model.save(folder)


@pytest.mark.parametrize('label',[0,1])
def test_all_constant_model_export_reload(rows,tmp_path,label):
    for row in rows:row['area_delta_lut4']=16 if label else 200
    model=FeasibilitySelectionPredictor(1).fit(rows)
    schema=model.save(tmp_path/'constant')
    assert schema['model_artifacts']=={}
    restored=FeasibilitySelectionPredictor.load(tmp_path/'constant')
    assert restored.predict(public(rows),area_cap=64)==model.predict(public(rows),area_cap=64)


@pytest.mark.parametrize('change',['booster','source','package','settings','constant','missing_member','extra_artifact','path_escape'])
def test_export_tampering_rejected_even_if_schema_resealed(rows,tmp_path,change):
    folder=tmp_path/'model';FeasibilitySelectionPredictor(9).fit(rows).save(folder)
    schema=c.unseal(folder/'schema.json')
    if change=='booster':
        name=next(iter(schema['model_artifacts']))
        with (folder/name).open('a') as stream:stream.write(' ')
    elif change=='source':schema['source_bindings']['isaforge/feasibility_selection.py']='0'*64
    elif change=='package':schema['packages']['xgboost']='0.0.0'
    elif change=='settings':schema['settings']['max_depth']=3
    elif change=='constant':next(entry for entry in schema['members'] if 'constant' in entry)['constant']=.5
    elif change=='missing_member':schema['members'].pop()
    elif change=='extra_artifact':schema['model_artifacts']['extra.json']='0'*64
    else:next(entry for entry in schema['members'] if 'artifact' in entry)['artifact']='../escape.json'
    c.seal(folder/'schema.json',schema)
    with pytest.raises(ValueError):FeasibilitySelectionPredictor.load(folder)

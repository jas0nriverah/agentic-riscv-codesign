"""Synthetic integrity tests for the fixed coverage fit; no native tools."""
import copy
from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import train_v9_coverage as runner


def fixture():
    rows = [{'formula': f'old-{i}', 'lut4_count': float(i % 100)} for i in range(1665)]
    original = {'columns': list(runner.v8.columns()), 'rows': rows, 'values': np.zeros((1665,455)).tolist()}
    candidates = [{'formula': f'new-{i}'} for i in range(48)]
    features = {'columns': list(runner.v6.columns()), 'records': [{'formula': r['formula'], 'values': [float(i)]*336} for i,r in enumerate(candidates)]}
    labels = [{'formula': r['formula'], 'lut4_count': i} for i,r in enumerate(candidates)]
    return original,candidates,features,labels


def test_one_complete_augmented_training_matrix():
    original, candidates, features, labels = fixture()
    x,y,old = runner.training_arrays(original,candidates,features,list(reversed(labels)))
    assert x.shape == (1713,336) and old.shape == (1665,336)
    assert np.array_equal(y[-48:],np.arange(48))
    assert np.array_equal(x[-48:,0],np.arange(48))
    assert np.array_equal(x[:1665],old)


@pytest.mark.parametrize('mutation', ['missing_label','duplicate_label','negative','fractional','bool','nan','original_duplicate','column_order','missing_feature','feature_nan','feature_negative','extra_candidate'])
def test_invalid_coverage_evidence_rejected(mutation):
    original,candidates,features,labels=fixture()
    if mutation=='missing_label':labels.pop()
    elif mutation=='duplicate_label':labels[-1]=labels[0]
    elif mutation=='negative':labels[0]['lut4_count']=-1
    elif mutation=='fractional':labels[0]['lut4_count']=1.5
    elif mutation=='bool':labels[0]['lut4_count']=True
    elif mutation=='nan':labels[0]['lut4_count']=float('nan')
    elif mutation=='original_duplicate':candidates[0]['formula']=original['rows'][0]['formula']
    elif mutation=='column_order':features['columns'].reverse()
    elif mutation=='missing_feature':features['records'].pop()
    elif mutation=='feature_nan':features['records'][0]['values'][0]=float('nan')
    elif mutation=='feature_negative':features['records'][0]['values'][0]=-1
    elif mutation=='extra_candidate':candidates.append({'formula':'new-49'})
    with pytest.raises(ValueError):runner.training_arrays(original,candidates,features,labels)


def test_identity_order_is_required_for_paired_metrics():
    rows=[{'formula':'a'},{'formula':'b'}]
    with pytest.raises(ValueError):runner.paired_metrics(rows,{'a':1,'b':2},{'frozen':[{'formula':'b','predicted_lut4':1},{'formula':'a','predicted_lut4':2}]})


@pytest.mark.parametrize('value', [-1,1.5,float('nan'),True])
def test_invalid_scoring_targets_rejected(value):
    with pytest.raises(ValueError):runner.paired_metrics([{'formula':'a'}],{'a':value},{'frozen':[{'formula':'a','predicted_lut4':1}]})


def test_family_weighting_not_row_weighting_and_zero_mape():
    rows=[{'formula':'a','benchmark':'p'},{'formula':'b','benchmark':'p'},{'formula':'c','benchmark':'q'}]
    programs=[{'benchmark':'p','family':'f','primary_family':True},{'benchmark':'q','family':'g','primary_family':True}]
    points={'frozen':[{**r,'predicted_lut4':v} for r,v in zip(rows,[0,2,10])],
            'augmented':[{**r,'predicted_lut4':v} for r,v in zip(rows,[0,2,6])]}
    scores=runner.application_metrics(rows,programs,{'a':0,'b':0,'c':0},points)
    assert scores['primary_family_macro_mae_lut4']=={'frozen':5.5,'augmented':3.5}
    assert scores['augmented_minus_frozen_mae_lut4']==-2
    assert scores['by_program']['p']['frozen']['positive_mape_percent'] is None
    assert scores['by_program']['p']['frozen']['zero_target_count']==2
    with pytest.raises(ValueError):runner.application_metrics(rows[:2],programs,{'a':0,'b':0,'c':0},points)

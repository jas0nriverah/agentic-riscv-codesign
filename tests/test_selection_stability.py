"""Predeclared gate and schema/zero-override fixtures; no forest fits."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('stability',Path(__file__).parents[1]/'scripts/test_selection_stability.py')
stability=importlib.util.module_from_spec(spec);spec.loader.exec_module(stability)


def fixture_metrics():
    return {str(seed):{view:{'group_macro_mae_lut4':9 if view=='selected128' else 10,
        'maximum_underprediction_lut4':20,'caps':{str(cap):{'false_safe_count':1,'false_rejection_count':2}
        for cap in (32,64,128)}} for view in stability.VIEWS} for seed in stability.SEEDS}


def test_gate_requires_every_seed_and_each_cap_error_and_tail():
    data=fixture_metrics();assert stability.eligibility(data)['strictly_eligible']
    data[str(stability.SEEDS[1])]['selected128']['group_macro_mae_lut4']=10
    assert not stability.eligibility(data)['mean_error_promising']
    data=fixture_metrics();data[str(stability.SEEDS[1])]['selected128']['caps']['64']['false_rejection_count']=3
    result=stability.eligibility(data)
    assert result['mean_error_promising'] and not result['strictly_eligible']
    assert not result['aggregate_budget_errors_not_worse']['64']['false_rejection_count']
    data=fixture_metrics();data[str(stability.SEEDS[2])]['selected128']['maximum_underprediction_lut4']=21
    assert not stability.eligibility(data)['maximum_underprediction_not_worse']


def test_stability_reports_within_seed_and_across_seeds_without_pseudoreplication():
    entries=[{'seed':seed,'fold':fold,'selected_indices':list(range(128))}
             for seed in stability.SEEDS for fold in range(5)]
    result=stability.selection_stability(entries)
    assert result['all_pairs']['pair_count']==105
    assert result['all_pairs']['mean_jaccard']==1
    assert result['across_seeds_same_fold']['pair_count']==15
    assert result['across_seeds_all_folds']['pair_count']==75
    assert result['always_selected_count']==128


class ConstantEstimator:
    def predict(self,x): return np.full(len(x),7.)


def test_inference_requires_explicit_schema_and_original_graph_zero():
    names=['original_gate_count']+[f'f{i}' for i in range(335)]
    model=stability.FrozenPredictor(ConstantEstimator(),{'source_columns':names,'selected_indices':[0,1],
        'zero_override':{'source_column_index':0},'full455_columns':[f'x{i}' for i in range(455)],
        'full455_to_original336_indices':list(range(336))})
    x=np.ones((2,336));x[0,0]=0
    assert model.predict_features(x,names).tolist()==[0,7]
    with pytest.raises(ValueError,match='schema'): model.predict_features(x,list(reversed(names)))
    with pytest.raises(ValueError,match='zero override'): model.predict_features(x,names,[False,False])
    bad=x.copy();bad[0,1]=float('nan')
    with pytest.raises(ValueError,match='matrix'):model.predict_features(bad,names)
    with pytest.raises(ValueError,match='schema'):model.predict_full455(np.ones((1,455)),list(reversed(model.metadata['full455_columns'])))

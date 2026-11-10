"""Small fixtures protect leakage controls and metric definitions; no forest fits."""
import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('compare_features',Path(__file__).parents[1]/'scripts/compare_features.py')
comparison=importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_equivalence_and_collision_union_is_transitive_and_label_independent():
    rows=[{'formula':f,'normalized_formulas':{'combined':n},'lut4_count':y}
          for f,n,y in [('add(add(in0,in1),0)','add(in0,in1)',4),('add(in0,in1)','add(in0,in1)',0),('xor(in0,in1)','xor(in0,in1)',32)]]
    prior={r['formula']:i for i,r in enumerate(rows)}
    semantic=comparison.merged_components(rows,prior)
    assert semantic[0]==semantic[1] and semantic[1]!=semantic[2]
    vectors=np.array([[1,2],[3,4],[3,4]])
    merged=comparison.merged_components(rows,prior,vectors)
    assert len(set(merged))==1
    for r in rows:r['lut4_count']=-999
    assert np.array_equal(merged,comparison.merged_components(rows,prior,vectors))


def test_selection_stably_breaks_ties_and_restores_schema_order():
    assert comparison.selected_indices([.1,.4,.4,0],2).tolist()==[1,2]
    assert comparison.selected_indices([.4,.4,.4,0],2).tolist()==[0,1]
    assert comparison.selected_indices([.2,.1,.8,.4],2).tolist()==[2,3]


def test_metrics_macro_weighting_zero_mape_and_cap_equality():
    m=comparison.metrics([0,32,128],[4,32,64],[0,0,1])
    assert m['pooled_mae_lut4']==68/3
    assert m['group_macro_mae_lut4']==33
    assert m['positive_mape_percent']==25
    assert m['zero_mae_lut4']==4
    assert m['maximum_underprediction_lut4']==64
    assert m['caps']['32']['false_safe_count']==0
    assert m['caps']['64']['false_safe_count']==1
    assert m['caps']['128']['false_rejection_count']==0


def test_all_zero_metrics_avoid_invalid_mape():
    m=comparison.metrics([0,0],[0,4],[0,1])
    assert m['positive_mape_percent'] is None
    assert m['zero_mae_lut4']==2
    assert m['maximum_underprediction_lut4']==0

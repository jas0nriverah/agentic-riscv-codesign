"""Gate failures must remain visible even when average accuracy improves."""
import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('targeted',Path(__file__).parents[1]/'scripts/train_targeted_coverage.py')
t=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(t)


def test_route_is_original_ast_variable_control_or_mixed_xor_without_products():
    assert t.route('sll(in0,andi(in1,31))')['source_model']=='augmented217'
    assert t.route('sll(in0,addi(0,7))')['source_model']=='base'
    assert t.route('xor(add(in0,in1),srli(in0,3))')['source_model']=='augmented217'
    assert t.route('add(mul(in0,addi(0,53)),xor(in1,srli(in0,7)))')['source_model']=='base'
    assert t.route('add(mul(in0,in1),srl(in0,in1))')['source_model']=='augmented217'
    assert t.route('xor(in0,in1)')['source_model']=='base'


def test_gate_rejects_new_false_accept_despite_better_mean_error():
    base=t.model_metrics([40.],[33.]); candidate=t.model_metrics([32.],[33.])
    checks=t.compare(base,candidate)
    assert checks['mae_strictly_improved'] and checks['positive_mape_strictly_improved']
    assert not checks['all_cap_directions_no_worse']


def test_development_gate_never_pools_away_one_panels_budget_or_tail_regression():
    panels={name:{'models':{'base':[40.],'augmented217':[35.],'scoped_augmented217':[35.]},
                   'actual_lut4':[33.]} for name in t.PANELS}
    panels['arithmetic-stress']={'models':{'base':[40.],'augmented217':[32.],'scoped_augmented217':[40.]},'actual_lut4':[33.]}
    result=t.development_metrics(panels)
    assert not result['gates']['augmented217']['development_gate_passed']
    assert result['gates']['scoped_augmented217']['development_gate_passed']
    panels['arithmetic-stress']={'models':{'base':[100.],'augmented217':[80.],'scoped_augmented217':[100.]},'actual_lut4':[120.]}
    assert not t.development_metrics(panels)['gates']['augmented217']['development_gate_passed']


def test_labels_require_complete_success_and_exact_order():
    rows=[{'candidate_id':'one','formula':'add(in0,in1)'}]
    labels=[{**rows[0],'status':'complete','lut4':31}]
    assert t.labels_for(rows,labels)==[31]
    for changed in ({**labels[0],'status':'failed'},{**labels[0],'candidate_id':'two'},{**labels[0],'lut4':-1}):
        with pytest.raises(ValueError):t.labels_for(rows,[changed])


def test_feature_matrix_requires_explicit_ordered_full336_schema():
    rows=[{'candidate_id':'one','formula':'add(in0,in1)'}]
    payload={'columns':list(t.v6.columns()),'records':[{**rows[0],'values':[0.]*336}]}
    assert t.feature_matrix(rows,payload).shape==(1,336)
    payload['columns']=payload['columns'][::-1]
    with pytest.raises(ValueError):t.feature_matrix(rows,payload)

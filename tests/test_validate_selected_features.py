"""Exercise the predeclared complete-cohort and per-cap evaluation contract."""
import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('validation',Path(__file__).parents[1]/'scripts/validate_selected_features.py')
v=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(v)


def test_fresh_inputs_cover_exactly_five_unique_templates():
    rows=v.candidates()
    assert len(rows)==len({r['formula'] for r in rows})==40
    assert {n:sum(r['template']==n for r in rows) for n,_,_ in v.TEMPLATES}=={n:8 for n,_,_ in v.TEMPLATES}


def test_metrics_reject_any_missing_label_and_count_each_cap_direction():
    rows=v.candidates();labels=[{**r,'status':'complete','lut4':40} for r in rows]
    base=[35.]*40;selected=[31.]*40
    result=v.metrics(rows,{'mapping217':base,'original336':base,'selected128':selected},labels)
    assert result['models']['mapping217']['caps']['32']['false_accept']==0
    assert result['models']['selected128']['caps']['32']['false_accept']==40
    assert not result['all_cap_error_counts_no_worse']
    labels[0]['status']='failed'
    with pytest.raises(ValueError,match='Full successful cohort'):v.metrics(rows,{'mapping217':base,'selected128':selected},labels)


def test_accuracy_improvement_does_not_override_new_budget_error():
    rows=v.candidates();labels=[{**r,'status':'complete','lut4':33} for r in rows]
    result=v.metrics(rows,{'mapping217':[40.]*40,'selected128':[32.]*40},labels)
    assert result['accuracy_improved']
    assert not result['predeclared_success']

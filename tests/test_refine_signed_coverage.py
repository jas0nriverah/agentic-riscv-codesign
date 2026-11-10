"""Original-data-operand routes, frozen fallback and guarded preservation."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

SPEC=importlib.util.spec_from_file_location('refinement',Path(__file__).parents[1]/'scripts/refine_signed_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


def test_compound_matches_data_subtree_and_input_bearing_shift_only():
    assert r.route('sub(sra(addi(xori(in0,13),37),andi(in1,31)),in0)')['compound']
    assert r.route('xor(sra(xori(addi(in0,13),37),in1),in0)')['compound']
    assert not r.route('sub(sra(in0,addi(xori(in1,13),37)),in0)')['compound']
    assert not r.route('sub(sra(addi(xori(in0,13),37),15),in0)')['compound']
    assert not r.route('sub(srl(addi(xori(in0,13),37),in1),in0)')['compound']


def test_add_boolean_matches_semantic_class_without_sub_multiply_or_unsigned():
    for op in ('and','or'):
        assert r.route(f'xor(add(in0,sra(in1,andi(in0,15))),{op}(in0,in1))')['add_boolean']
    for formula in ('xor(sub(in0,sra(in1,in0)),and(in0,in1))',
                    'xor(add(in0,srl(in1,in0)),and(in0,in1))',
                    'xor(add(mul(in0,in1),sra(in1,in0)),and(in0,in1))'):
        assert not r.route(formula)['add_boolean']


class Model:
    def __init__(self,value):self.value=value
    def predict_features(self,rows,x):return [{'predicted_lut4':self.value} for _ in rows]


def test_new_route_preserves_current_elsewhere_and_single_fallback_precedence():
    formulas=['sub(sra(addi(xori(in0,13),37),in1),in0)',
              'xor(add(in0,sra(in1,in0)),and(in0,in1))',
              'xor(sub(in0,sra(in1,in0)),add(in0,in1))',
              'and(in0,in1)']
    rows=[{'formula':f} for f in formulas]
    values,_=r.points(rows,np.zeros((4,336)),Model(60),Model(40),Model(50),Model(55))
    assert values[r.CURRENT]==[55.,50.,55.,40.]
    assert values[r.PRIMARY]==[60.,60.,55.,40.]
    assert values[r.FALLBACK]==[50.,60.,55.,40.]
    for n in r.CANDIDATES:assert r.guard.passed(r.guard.invariants(values['base'],values[n]))


def test_both_fresh_accuracy_metrics_require_strict_improvement():
    m={'mae_lut4':1.,'positive_mape_percent':2.}
    assert all(r.accuracy(m,m).values())
    assert not any(r.accuracy(m,m,True).values())
    assert not r.accuracy(m,{'mae_lut4':.8,'positive_mape_percent':None})['positive_mape_percent']

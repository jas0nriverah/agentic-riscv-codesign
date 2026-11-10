"""Frozen structural repair, fallback and strict regression gates."""
import importlib.util
from pathlib import Path
import numpy as np

SPEC=importlib.util.spec_from_file_location('revision',Path(__file__).parents[1]/'scripts/revise_guarded_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


def test_original_ast_repair_covers_signed_failures_without_matching_ids_or_constants():
    for formula in ('sub(srai(xor(in0,in1),12),srai(in1,31))',
                    'xor(sub(in0,sra(in1,andi(in0,15))),add(in0,in1))',
                    'xor(sub(in0,sra(in1,andi(in0,5))),add(in0,in1))'):
        assert r.routes(formula)['signed_arithmetic_repair']
    for formula in ('xor(sra(addi(in0,5),in1),and(in0,in1))',
                    'xor(sub(in0,srl(in1,in0)),add(in0,in1))',
                    'sub(srai(and(in0,in1),12),srai(in1,31))'):
        assert not r.routes(formula)['signed_arithmetic_repair']


def test_fallback_abstains_static_signed_but_retains_variable_signed():
    assert r.routes('sub(srai(xor(in0,in1),12),srai(in1,31))')['signed_static_abstention']
    assert not r.routes('xor(sub(in0,sra(in1,andi(in0,15))),add(in0,in1))')['signed_static_abstention']
    assert not r.routes('xor(add(in0,in1),srli(in0,3))')['signed_static_abstention']


class Model:
    def __init__(self,value):self.value=value
    def predict_features(self,rows,x):return [{'predicted_lut4':self.value} for _ in rows]


def test_narrow_repair_preserves_incumbent_elsewhere_and_guard_decisions():
    rows=[{'formula':f} for f in ('xor(sra(addi(in0,5),in1),and(in0,in1))',
        'sub(srai(xor(in0,in1),12),srai(in1,31))',
        'xor(sub(in0,sra(in1,andi(in0,15))),add(in0,in1))','and(in0,in1)')]
    p,_=r.points(rows,np.zeros((4,336)),Model(60),Model(40),Model(50))
    assert p['incumbent_guard']==[50.,50.,50.,40.]
    assert p[r.PRIMARY]==[50.,60.,60.,40.]
    assert p[r.FALLBACK]==[50.,40.,60.,40.]
    for name in r.CANDIDATES:assert r.incumbent.passed(r.incumbent.invariants(p['base'],p[name]))


def test_accuracy_gate_distinguishes_equality_from_strict_improvement():
    base={'mae_lut4':1.,'positive_mape_percent':2.}
    assert all(r.accuracy_no_worse(base,base).values())
    assert not any(r.accuracy_no_worse(base,base,True).values())
    assert not r.accuracy_no_worse(base,{'mae_lut4':.9,'positive_mape_percent':None})['positive_mape_percent']

import importlib.util
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('guarded_measure',Path(__file__).parents[1]/'scripts/measure_guarded_revision.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)

def test_joint_cohorts_cover_regressions_and_controls_with_distinct_compositions():
    train,test=m.candidates('train'),m.candidates('test')
    assert len(train)==len({r['formula'] for r in train})==32
    assert len(test)==len({r['formula'] for r in test})==40
    assert len({m.skeleton(r['formula']) for r in train})==8
    assert len({m.skeleton(r['formula']) for r in test})==10
    assert not {m.skeleton(r['formula']) for r in train}&{m.skeleton(r['formula']) for r in test}
    assert sum(r['template'].startswith('control_') for r in test)==16
    assert sum(r['template'].startswith('heldout_signed_variable_') for r in test)==16
    assert sum(r['template'].startswith('heldout_static_signed_') for r in test)==8

def test_predeclared_budget_is_shared_and_bounded():
    assert m.POLICY['total_native_seconds']==300
    assert m.POLICY['training_native_seconds']==180
    assert m.POLICY['workers']==2
    assert m.POLICY['fits']==m.POLICY['retries']==m.POLICY['replacement_candidates']==0
    assert m.POLICY['vectors_per_formula']==2148

def test_constant_erasure_preserves_operator_structure():
    assert m.skeleton('add(in0,addi(in1,5))')==m.skeleton('add(in0,addi(in1,7))')
    assert m.skeleton('add(in0,addi(in1,5))')!=m.skeleton('sub(in0,addi(in1,5))')

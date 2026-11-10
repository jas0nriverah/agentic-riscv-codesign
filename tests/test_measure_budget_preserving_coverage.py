import importlib.util
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('budget_measure',Path(__file__).parents[1]/'scripts/measure_budget_preserving_coverage.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
def test_exact32_distinct_compositions_and_controls():
 rows=m.candidates();assert len(rows)==len({r['formula'] for r in rows})==32
 assert len({m.skeleton(r['formula']) for r in rows})==8
 assert sum(r['template'].startswith('control_') for r in rows)==12
def test_constant_erasure_preserves_composition():
 assert m.skeleton('add(in0,addi(in1,3))')==m.skeleton('add(in0,addi(in1,7))')
 assert m.skeleton('add(in0,addi(in1,3))')!=m.skeleton('sub(in0,addi(in1,3))')
def test_native_bound():
 assert m.POLICY['total_native_seconds']==120 and m.POLICY['workers']==2
 assert m.POLICY['fits']==m.POLICY['retries']==m.POLICY['replacement_candidates']==0

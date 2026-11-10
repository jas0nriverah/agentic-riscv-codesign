"""Targeted coverage cohort and chronology contracts."""
import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('coverage_measure',Path(__file__).parents[1]/'scripts/measure_targeted_coverage.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
def test_exact_cohorts_and_holdouts():
 a=m.candidates('train');b=m.candidates('test')
 assert len(a)==64 and len(b)==40 and len({r['formula'] for r in a+b})==104
 assert {r['template'] for r in a}.isdisjoint({r['template'] for r in b})
 assert sum(r['template'].startswith('heldout_') for r in b)==24
 assert sum(r['template'].startswith('control_') for r in b)==16
def test_test_freeze_requires_no_test_labels(tmp_path,monkeypatch):
 monkeypatch.setattr(m,'TEST',tmp_path);m.write(tmp_path/'point-freeze.json',{'target_label_jobs':1,'bindings':{}})
 with pytest.raises(ValueError,match='after labels'):m.verify_point_freeze()
def test_native_contract():
 assert m.POLICY['total_native_seconds']==1200 and m.POLICY['training_native_seconds']==600 and m.POLICY['workers']==2
 assert m.POLICY['fits']==m.POLICY['retries']==m.POLICY['replacement_candidates']==0
 assert len(m.v6.columns())==336

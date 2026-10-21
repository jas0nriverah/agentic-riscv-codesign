"""Disjoint pool registration tests; no native measurement jobs."""
import copy
from pathlib import Path
import pytest
from isaforge import codesign as c, guarded_workload as g, training_workload as t


def test_excludes_only_declared_literals_before_shared_extraction(monkeypatch):
    rows = [{'formula': formula} for formula in (*t.EXCLUDED_FORMULAS, 'add(in0,in1)')]
    raw = {'executable_candidates': rows, 'pool': rows[:6]}
    monkeypatch.setattr(t, 'BASE_EXTRACT', lambda *args: copy.deepcopy(raw))
    first = t.extract_disjoint({}, {}, {}, 6)
    assert first == t.extract_disjoint({}, {}, {}, 6)
    assert first['executable_candidates'] == [{'formula': 'add(in0,in1)'}]
    assert len(raw['executable_candidates']) == 7
    assert first['excluded_historical_formulas'] == list(t.EXCLUDED_FORMULAS)


def test_registration_restores_frozen_globals_even_after_exception():
    previous = g.SOURCE, g.POOL_RULE, g.ORIGINAL_EXTRACT
    with pytest.raises(RuntimeError):
        with t.registration():
            assert g.SOURCE == t.SOURCE
            assert g.ORIGINAL_EXTRACT == t.extract_disjoint
            with t.registration():
                assert g.SOURCE == t.SOURCE
            raise RuntimeError('test')
    assert (g.SOURCE, g.POOL_RULE, g.ORIGINAL_EXTRACT) == previous


def test_real_new_plan_rejects_old_entrypoint_and_preserves_historical_context():
    root = c.ROOT/'generated/disjoint-sha256-2026-10-21'
    if not root.exists(): pytest.skip('native development context not installed')
    old = c.ROOT/'generated/guarded-sha256-2026-10-21/plan.json'
    old_hash = c.sha(old)
    plan = c.unseal(root/'plan.json')
    t.check_plan(plan)
    with pytest.raises(ValueError): g.check_plan(plan)
    assert plan['source_bindings'][t.SOURCE] == c.sha(c.ROOT/t.SOURCE)
    assert plan['source_bindings'][t.GUARDED_SOURCE] == c.sha(c.ROOT/t.GUARDED_SOURCE)
    assert plan['memory_partition'] == g.q.partition_spec(7488,7616)
    for file in ('program.c','embench_firmware.c','soc_top.v','picorv32.v','soc_link.ld'):
        assert c.sha(root/'inputs'/file) == c.sha(old.parent/'inputs'/file)
    assert c.sha(old) == old_hash


def test_audit_runs_with_disjoint_registration(monkeypatch, tmp_path):
    monkeypatch.setattr(c, 'unseal', lambda path: {})
    monkeypatch.setattr(t, 'check_plan', lambda plan: None)
    def audit(root):
        assert g.SOURCE == t.SOURCE
        assert g.POOL_RULE == t.POOL_RULE
        assert g.ORIGINAL_EXTRACT == t.extract_disjoint
        return {'checked': True}
    monkeypatch.setattr(g, 'audit', audit)
    assert t.audit(tmp_path) == {'checked': True}


def test_discovery_pool_is_disjoint_and_rederived():
    root = c.ROOT/'generated/disjoint-sha256-2026-10-21'
    if not (root/'discovery/discovery.json').exists(): pytest.skip('native discovery not installed')
    with t.registration():
        discovery = g.authenticate_discovery(root)
    assert len(discovery['pool']) == 6
    assert discovery['eligible_formula_count'] == 50
    assert {row['formula'] for row in discovery['pool']}.isdisjoint(t.EXCLUDED_FORMULAS)

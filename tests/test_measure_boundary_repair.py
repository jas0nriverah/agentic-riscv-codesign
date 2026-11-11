import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('boundary_measure',Path(__file__).parents[1]/'scripts/measure_boundary_repair.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_fresh40_contains_declared_width_and_mask_challenges_plus_controls():
    import refine_signed_coverage as signed
    rows=m.candidates()
    assert len(rows)==len({r['formula'] for r in rows})==40
    assert len({m.skeleton(r['formula']) for r in rows})==10
    target=[r for r in rows if r['template'].startswith('boundary_')]
    control=[r for r in rows if r['template'].startswith('control_')]
    assert len(target)==32 and len(control)==8
    assert sum(r['template'].startswith('boundary_full_') for r in rows)==16
    assert sum(r['template'].startswith(('boundary_low','boundary_signed')) for r in rows)==16
    assert all(signed.route(r['formula'])['compound'] for r in target)
    assert not any(signed.route(r['formula'])['new_coverage'] for r in control)
    assert {r['parameter'] for r in target}=={1,3,7,31}
    for r in target:
        if r['template'].startswith(('boundary_low8','boundary_signed8')):assert '255' in r['formula']
        if r['template'].startswith(('boundary_low16','boundary_signed16')):assert '65535' in r['formula']


def test_private_runner_keeps_historical_sources_and_policy_unchanged():
    import measure_guarded_revision as old
    old_path,old_train,old_test=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==(old_path,old_train,old_test)
    assert runner.TRAIN==runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEED==2026111003


def test_inventory_includes_latest72_and_every_saved_alias():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=9366
    for name in ('budget-release-data','budget-release-validation'):
        for row in m.read(m.ROOT/'results'/name/'candidates.json'):assert row['formula'] in history
        for row in m.read(m.ROOT/'results'/name/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_label_attempt_cannot_start_without_prelabel_prediction_freeze(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    monkeypatch.setattr(m,'validate',lambda:{})
    m.write(tmp_path/'preflight-audit.json',{'status':'pass'})
    m.write(tmp_path/'prelabel-audit.json',{'status':'pass'})
    m.write(tmp_path/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('labels')
    assert not (tmp_path/'label-attempt.json').exists()

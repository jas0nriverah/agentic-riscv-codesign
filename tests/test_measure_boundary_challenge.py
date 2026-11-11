import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('challenge_measure',Path(__file__).parents[1]/'scripts/measure_boundary_challenge.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_fixed200pool_has_declared_lowmask_structure_controls_and_parameter_order():
    import refine_signed_coverage as signed
    rows=m.pool_candidates();targets=[r for r in rows if not r['reserved_control']];controls=[r for r in rows if r['reserved_control']]
    assert len(rows)==len({r['formula'] for r in rows})==200
    assert len(targets)==192 and len(controls)==8
    assert len({r['template'] for r in targets})==24
    assert len({m.skeleton(r['formula']) for r in rows})==26
    assert [r['pool_index'] for r in rows]==list(range(200))
    assert all(signed.route(r['formula'])['compound'] for r in targets)
    assert not any(signed.route(r['formula'])['new_coverage'] for r in controls)
    for name in {r['template'] for r in targets}:
        assert [r['parameter'] for r in targets if r['template']==name]==[list(p) for p in m.PARAMETERS]
    assert {r['parameter'][2] for r in targets}=={1,3}
    assert sum('xordata' in r['template'] for r in targets)>=96


def test_private_runner_keeps_historical_sources_unchanged():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEED==2026111101


def test_inventory_includes_latest40_and_every_saved_alias():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=9442
    folder=m.ROOT/'results/boundary-repair-validation'
    for row in m.read(folder/'candidates.json'):assert row['formula'] in history
    for row in m.read(folder/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_selected_mapping_requires_exact_pool_feature_subset_and_all_controls(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    pool=m.pool_candidates();features={'columns':['example'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    indices=[0,8,16,24,*range(192,200)]
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices})
    m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]}
    m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()


def test_labels_cannot_start_without_prelabel_selection_point_freeze(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(tmp_path/'preflight-audit.json',{'status':'pass'});m.write(tmp_path/'prelabel-audit.json',{'status':'pass'})
    m.write(tmp_path/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('labels')
    assert not (tmp_path/'label-attempt.json').exists()

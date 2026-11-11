import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('refinement_measure',Path(__file__).parents[1]/'scripts/measure_boundary_refinement.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def structural(formula):
    root=m.parse_formula(formula)
    return root.value=='xor' and any(c.value=='add' and any(s.value=='sra' for s in c.children) for c in root.children)


def test_fixed128pool_general_and_challenge_compositions_controls_order():
    import refine_signed_coverage as signed
    rows=m.pool_candidates();general=rows[:32];challenge=rows[32:]
    assert len(rows)==len({r['formula'] for r in rows})==128
    assert all(r['cohort']=='general' for r in general)
    assert all(r['cohort']=='challenge' and not r['reserved_control'] for r in challenge)
    assert sum(r['reserved_control'] for r in general)==8
    assert len({r['template'] for r in general if not r['reserved_control']})==6
    assert len({r['template'] for r in challenge})==12
    a={m.skeleton(r['formula']) for r in general};b={m.skeleton(r['formula']) for r in challenge}
    assert len(a)==10 and len(b)==12 and not a&b
    assert [r['pool_index'] for r in rows]==list(range(128))
    assert all(structural(r['formula']) and signed.route(r['formula'])['compound'] for r in rows if not r['reserved_control'])
    assert not any(structural(r['formula']) for r in rows if r['reserved_control'])
    for name in {r['template'] for r in challenge}:
        assert [r['parameter'] for r in challenge if r['template']==name]==[list(p) for p in m.PARAMETERS]
    assert {r['parameter'][2] for r in challenge}=={1,3}
    assert {r['parameter'] for r in general if not r['reserved_control']}=={1,3,7,31}


def test_private_runner_keeps_historical_sources_unchanged():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEED==2026111102


def test_inventory_includes_all_latest200_even_unlabelled_and_saved_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=9834
    folder=m.ROOT/'results/boundary-challenge-validation'
    pool=m.read(folder/'pool-candidates.json');selected=m.read(folder/'candidates.json')
    assert len(pool)==200 and len(selected)==18
    assert all(row['formula'] in history for row in pool)
    for row in m.read(folder/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_selected_mapping_requires_all_general32_and_exact_pool_feature_subset(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    pool=m.pool_candidates();features={'columns':['example'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    indices=[*range(32),32,40,48,56]
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices})
    m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]}
    m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()
    m.write(tmp_path/'selection.json',{'selected_pool_indices':[1,0,*indices[2:]]})
    with pytest.raises(ValueError,match='general32'):m.selected()


def test_labels_cannot_start_without_prelabel_selection_point_freeze(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(tmp_path/'preflight-audit.json',{'status':'pass'});m.write(tmp_path/'prelabel-audit.json',{'status':'pass'})
    m.write(tmp_path/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('labels')
    assert not (tmp_path/'label-attempt.json').exists()

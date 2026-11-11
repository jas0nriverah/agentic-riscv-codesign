import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('abstention_measure',Path(__file__).parents[1]/'scripts/measure_boundary_abstention.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def cells(formula):
    import boundary_coverage_features as block
    return [(block.unknown_shape(data)[0]<=16,bool(block.nonleaf_subtrees(data)&block.nonleaf_subtrees(post)))
            for data,control,post,outer in block.chains(formula)
            if outer.value in ('and','or','xor') or block.unknown_shape(data)[0]<=16]


def test_fixed128_has_general32_unsupported8_challenge88_and_all_profiles():
    rows=m.pool_candidates()
    assert len(rows)==len({r['formula'] for r in rows})==128
    assert [r['pool_index'] for r in rows]==list(range(128))
    assert all(r['cohort']=='general' for r in rows[:32])
    assert all(r['cohort']=='unsupported' for r in rows[32:40])
    assert all(r['cohort']=='challenge' for r in rows[40:])
    assert sum(r['reserved_control'] for r in rows)==8
    assert not any(r['reserved_control'] for r in rows[32:])
    for name in {r['template'] for r in rows[32:40]}:
        assert [r['parameter'] for r in rows[32:40] if r['template']==name]==[[5,29,1],[41,131,3]]
    assert len({r['template'] for r in rows[40:]})==11
    assert len({m.skeleton(r['formula']) for r in rows})==29
    for name in {r['template'] for r in rows[40:]}:
        assert [r['parameter'] for r in rows[40:] if r['template']==name]==[list(p) for p in m.PARAMETERS]
    assert sum('plain_' in r['template'] for r in rows[:16])==4
    assert sum('signed8_' in r['template'] for r in rows[:16])==4
    assert sum('signed16_' in r['template'] for r in rows[:16])==4


def test_fixed_unsupported_cell_and_supported_profiles_match_training_input_coverage():
    rows=m.pool_candidates();train=m.read(m.ROOT/'results/boundary-coverage-data/candidates.json')
    covered={cell for r in train for cell in cells(r['formula'])}
    assert covered=={(False,False),(True,False),(True,True)}
    assert all(cells(r['formula']) and all(c in covered for c in cells(r['formula'])) for r in [*rows[:16],*rows[40:]])
    assert not any(cells(r['formula']) for r in rows[16:32])
    assert all(cells(r['formula'])==[(False,True)] for r in rows[32:40])


def test_private_runner_preserves_old_sources_and_zero_fit_native_contract():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEED==2026111105


def test_history_includes_latest_training32_pool128_unlabelled_and_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=10410
    for folder,file,count in [('boundary-coverage-data','candidates.json',32),('boundary-coverage-validation','pool-candidates.json',128)]:
        out=m.ROOT/'results'/folder;rows=m.read(out/file)
        assert len(rows)==count and all(r['formula'] in history for r in rows)
        for row in m.read(out/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_selected_mapping_requires_all_fixed40_and_exact_feature_subset(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    pool=m.pool_candidates();features={'columns':['example'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    indices=[*range(40),40,48,56,64]
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices});m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]};m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()
    m.write(tmp_path/'selection.json',{'selected_pool_indices':[1,0,*indices[2:]]})
    with pytest.raises(ValueError,match='fixedgeneral32'):m.selected()


def test_labels_cannot_start_without_prelabel_prediction_selection_freeze(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(tmp_path/'preflight-audit.json',{'status':'pass'});m.write(tmp_path/'prelabel-audit.json',{'status':'pass'})
    m.write(tmp_path/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('labels')
    assert not (tmp_path/'label-attempt.json').exists()

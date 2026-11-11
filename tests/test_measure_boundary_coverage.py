import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('coverage_measure',Path(__file__).parents[1]/'scripts/measure_boundary_coverage.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def structural(formula):
    root=m.parse_formula(formula)
    return root.value=='xor' and any(c.value=='add' and any(s.value=='sra' for s in c.children) for c in root.children)


def test_joint_training32_test128_compositions_and_wide_cost_contrasts():
    import refine_signed_coverage as signed
    import boundary_coverage_features as block
    train,pool=m.training_candidates(),m.pool_candidates()
    assert len(train)==len({r['formula'] for r in train})==32
    assert len(pool)==len({r['formula'] for r in pool})==128
    a={m.skeleton(r['formula']) for r in train};b={m.skeleton(r['formula']) for r in pool}
    assert len(a)==8 and len(b)==22 and not a&b
    assert sum(r['template'].startswith('sharing_') for r in train)==16
    assert sum(r['template'].startswith('narrow_') for r in train)==16
    assert sum(r['template']=='sharing_plain_input_orroot' for r in train)==4
    assert all(block.learning_scope(r['formula']) for r in train)
    assert all(block.learning_scope(r['formula']) for r in pool if r['cohort']=='challenge')
    assert sum(block.learning_scope(r['formula']) for r in pool if r['cohort']=='general')==16
    assert all(len(block.features(r['formula']))==16 for r in [*train,*pool])
    assert sum(r['parameter'] in (7,31) for r in train)==16
    assert all(structural(r['formula']) and signed.route(r['formula'])['compound'] for r in train)
    assert len([r for r in pool if r['cohort']=='general'])==32
    assert len([r for r in pool if r['cohort']=='challenge'])==96
    assert sum(r['reserved_control'] for r in pool)==8
    assert all(structural(r['formula']) for r in pool if not r['reserved_control'])
    assert not any(structural(r['formula']) for r in pool if r['reserved_control'])
    assert [r['pool_index'] for r in pool]==list(range(128))


def test_private_runner_preserves_historical_sources_and_joint_native_limits():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==m.TRAIN and runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEEDS=={'train':2026111103,'test':2026111104}


def test_inventory_includes_latest128_unlabelled_and_all_earlier200():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=10090
    for name,count in [('boundary-refinement-validation',128),('boundary-challenge-validation',200)]:
        folder=m.ROOT/'results'/name;pool=m.read(folder/'pool-candidates.json')
        assert len(pool)==count and all(r['formula'] in history for r in pool)
        for row in m.read(folder/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_selected_mapping_requires_all_general32_and_exact_pool_feature_subset(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    pool=m.pool_candidates();features={'columns':['example'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    indices=[*range(32),32,40,48,56]
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices});m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]};m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()


def test_training_labels_need_independent_pretrain_receipt(tmp_path,monkeypatch):
    train=tmp_path/'train';fresh=tmp_path/'test'
    monkeypatch.setattr(m,'TRAIN',train);monkeypatch.setattr(m,'OUT',fresh);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(train/'preflight-audit.json',{'status':'pass'});m.write(train/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('train-labels')
    assert not (train/'label-attempt.json').exists()


def test_fresh_labels_need_complete_training_and_prelabel_prediction_freeze(tmp_path,monkeypatch):
    train=tmp_path/'train';fresh=tmp_path/'test'
    monkeypatch.setattr(m,'TRAIN',train);monkeypatch.setattr(m,'OUT',fresh);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(train/'preflight-audit.json',{'status':'pass'});m.write(train/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    m.write(train/'completion.json',{'complete':True,'total_native_elapsed_seconds':10});m.write(fresh/'prelabel-audit.json',{'status':'pass'})
    with pytest.raises(FileNotFoundError):m.run('test-labels')
    assert not (fresh/'label-attempt.json').exists()


def test_training_covers_shared_boolean_and_disjoint_single_input_profiles():
    import boundary_coverage_features as block
    rows=m.training_candidates()
    profiles={tuple(block.features(r['formula'])[:10]) for r in rows}
    assert (1,2,1,2,1,2,1,0,0,0) in profiles
    assert (1,0,0,1,1,1,1,0,0,0) in profiles
    for row in rows:
        if row['template'] in ('sharing_plain_input_orroot','narrow_signed8_orroot'):
            assert tuple(block.features(row['formula'])[:10])==(1,0,0,1,1,1,1,0,0,0)

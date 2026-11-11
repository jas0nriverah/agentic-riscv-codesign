import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('corroboration_measure',Path(__file__).parents[1]/'scripts/measure_boundary_corroboration.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_joint32_training128_pool_have_fixed_splits_novel_shapes_and_highmask_contrasts():
    train,pool=m.training_candidates(),m.pool_candidates()
    assert len(train)==len({r['formula'] for r in train})==32
    assert len(pool)==len({r['formula'] for r in pool})==128
    a={m.skeleton(r['formula']) for r in train};b={m.skeleton(r['formula']) for r in pool}
    assert len(a)==9 and len(b)==28 and not a&b
    assert sum(r['parameter'] in (7,31) for r in train)==16
    assert [r['parameter'] for r in train if r['template']=='sharing_plain_boolean_outer']==[1,31]
    assert [r['parameter'] for r in train if r['template']=='sharing_plain_outerinput']==[3,31]
    assert [r['pool_index'] for r in pool]==list(range(128))
    assert [r['cohort'] for r in pool]==['general']*32+['sharing']*8+['legacy']*8+['challenge']*80
    assert sum(r['reserved_control'] for r in pool)==8
    for name in {r['template'] for r in pool[48:]}:
        assert [r['parameter'] for r in pool[48:] if r['template']==name]==[list(p) for p in m.PARAMETERS]


def test_new_carry_scope_includes_outer_inputs_and_recovers_presign_add_width():
    from collections import Counter
    import boundary_carry_features as new
    import boundary_coverage_features as old
    train=m.training_candidates();pool=m.pool_candidates()
    assert all(new.learning_scope(r['formula']) for r in train)
    assert all(new.learning_scope(r['formula']) for r in pool if not r['reserved_control'])
    assert not any(new.learning_scope(r['formula']) for r in pool if r['reserved_control'])
    recovered=[r for r in train if new.features(r['formula'])[10]<old.features(r['formula'])[10]]
    assert len(recovered)==4 and all(old.features(r['formula'])[10]==32 and new.features(r['formula'])[10]==8 for r in recovered)
    cells=Counter((new.features(r['formula'])[10]<=16,new.features(r['formula'])[7]>0) for r in train)
    assert cells=={(False,False):12,(False,True):4,(True,False):12,(True,True):4}


def test_fixed_legacy_rows_cover_both_repeated_sharing_failure_mechanisms():
    import boundary_carry_features as local
    rows=[r for r in m.pool_candidates() if r['cohort']=='legacy']
    for name,width,join in [('legacy_signed16_and_repeat',16,13),('legacy_signed8_preadd_xor_repeat',8,15)]:
        selected=[r for r in rows if r['template']==name]
        assert len(selected)==2 and [r['parameter'] for r in selected]==[list(p) for p in m.FIXED_PARAMETERS]
        for row in selected:
            v=local.features(row['formula']);assert v[7]>=1 and v[10]==width and v[join]>=1


def test_profile_matrix_retains_all_targets_and_reports_formula_only_coverage():
    p=m.read(m.ROOT/'results/boundary-corroboration/measurement-input-profile-audit.json')
    assert p['old_training_count']==1857 and p['new_training_count']==32
    assert p['required_acceptances_count']==43 and p['required_rejections_count']==6
    assert len(p['matrix'])==49
    assert all(r['matches']['new32']['full16']>=1 for r in p['matrix'] if r['target_group']=='remaining_fr_targets')
    assert not ({r['formula'] for r in p['matrix']}&{r['formula'] for r in m.training_candidates()})


def test_history_contains_all_latest128_even_unlabelled_and_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=10666
    folder=m.ROOT/'results/boundary-abstention-validation';pool=m.read(folder/'pool-candidates.json')
    assert len(pool)==128 and all(r['formula'] in history for r in pool)
    for row in m.read(folder/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_private_runner_preserves_old_sources_and_joint_native_contract():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==m.TRAIN and runner.TEST==m.OUT
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert m.POLICY=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEEDS=={'train':2026111106,'test':2026111107}


def test_selected_mapping_requires_fixed48_and_exact_pool_feature_subset(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);pool=m.pool_candidates()
    features={'columns':['example'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]};indices=[*range(48),48,56,64,72]
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices});m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]};m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()
    m.write(tmp_path/'selection.json',{'selected_pool_indices':[1,0,*indices[2:]]})
    with pytest.raises(ValueError,match='fixedgeneral32'):m.selected()


def test_training_and_fresh_labels_need_independent_receipts_and_prediction_freeze(tmp_path,monkeypatch):
    train=tmp_path/'train';fresh=tmp_path/'test'
    monkeypatch.setattr(m,'TRAIN',train);monkeypatch.setattr(m,'OUT',fresh);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(train/'preflight-audit.json',{'status':'pass'});m.write(train/'feature-completion.json',{'complete':True,'total_native_elapsed_seconds':5})
    with pytest.raises(FileNotFoundError):m.run('train-labels')
    assert not (train/'label-attempt.json').exists()
    m.write(train/'completion.json',{'complete':True,'total_native_elapsed_seconds':10});m.write(fresh/'prelabel-audit.json',{'status':'pass'})
    with pytest.raises(FileNotFoundError):m.run('test-labels')
    assert not (fresh/'label-attempt.json').exists()


def test_profile_audit_replay_preserves_frozen_artifact_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'TRAIN',tmp_path/'train')
    m.write(m.TRAIN/'plan.json',{'frozen':True})
    target=m.ROOT/'results/boundary-corroboration/measurement-input-profile-audit.json'
    before=target.read_bytes();result=m.profile_audit()
    assert result['new_training_count']==32 and target.read_bytes()==before

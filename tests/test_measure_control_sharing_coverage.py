import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('control_sharing_measure',Path(__file__).parents[1]/'scripts/measure_control_sharing_coverage.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_fixed32_training_and96_pool_splits_masks_and_true_profiles():
    import boundary_carry_features as local
    train,pool=m.training_candidates(),m.pool_candidates()
    assert len(train)==len({r['formula'] for r in train})==32
    assert len(pool)==len({r['formula'] for r in pool})==96
    assert len({m.skeleton(r['formula']) for r in train})==8
    assert not {m.skeleton(r['formula']) for r in train}&{m.skeleton(r['formula']) for r in pool}
    assert [r['pool_index'] for r in pool]==list(range(96))
    assert [r['cohort'] for r in pool]==['general']*32+['sharing']*8+['legacy']*8+['challenge']*48
    assert sum(r['reserved_control'] for r in pool)==8
    for prefix in ('and_control_','shared_and_'):
        group=[r for r in train if r['template'].startswith(prefix)]
        assert len(group)==16
        assert sum(local.features(r['formula'])[10]==32 for r in group)==8
        assert sum(local.features(r['formula'])[10] in (8,16) for r in group)==8
        assert {r['parameter'][2] for r in group}=={1,3,7,31}
    assert all(local.learning_scope(r['formula']) for r in train)
    assert all(local.learning_scope(r['formula']) for r in pool if not r['reserved_control'])
    assert not any(local.learning_scope(r['formula']) for r in pool if r['reserved_control'])


def test_input_audit_covers_actual_four_same_chain_profiles_without_target_labels():
    p=m.read(m.ROOT/'results/control-sharing-coverage/measurement-input-profile-audit.json')
    assert p['old_training_count']==1889 and p['new_training_count']==32
    assert p['group_counts']=={'both_input_and_control':16,'repeated_and_data_post_outer':16}
    assert len(p['consumed_target_profiles'])==4
    assert all(r['matches']['new32']['full16']==2 for r in p['consumed_target_profiles'])
    for row in p['new_training']:
        profiles=row['profiles'];assert len(profiles)==1
        q=profiles[0]
        if row['template'].startswith('and_control_'):
            assert q['both_input_and_control'] and not q['repeated_and_data_post_outer']
        else:
            assert q['repeated_and_data_post_outer'] and not q['both_input_and_control']
            assert q['post']==q['outer']=='and(in0,in1)'
    assert not ({r['formula'] for r in p['new_training']}&{r['formula'] for r in p['consumed_target_profiles']})


def test_history_includes_all_latest128_pool_even72_unlabelled_and_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=11288
    out=m.ROOT/'results/boundary-feasibility-validation';rows=m.read(out/'pool-candidates.json')
    assert len(rows)==128 and len(m.read(out/'candidates.json'))==56
    assert all(r['formula'] in history for r in rows)
    for row in m.read(out/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_modular_rules_sound_and_joint_modular_skeleton_novelty():
    from isaforge.rtl import evaluate_formula
    examples=('andi(addi(in0,2),1)','addi(addi(in0,9),2)','andi(addi(xori(in1,15),2),1)','andi(addi(in0,-4),3)')
    count=0
    for f in examples:
        a,b=m.parse_formula(f),m.parse_formula(m.modular_formula(f))
        for x in [*range(256),0x7fffffff,0x80000000,0xffffffff]:
            for y in (0,1,3,0xffffffff):assert evaluate_formula(a,x,y)==evaluate_formula(b,x,y);count+=1
    assert count==4144
    assert m.modular_formula('andi(addi(in0,2),3)')=='andi(addi(in0,2),3)'
    known={m.skeleton(m.modular_formula(f)) for f in m.inventory()[0]}
    assert not [r for r in [*m.training_candidates(),*m.pool_candidates()] if m.skeleton(m.modular_formula(r['formula'])) in known]


def test_private_runner_keeps_prior_sources_and_native_budget_contract():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST;runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==m.TRAIN and runner.TEST==m.OUT
    assert m.POLICY['total_native_seconds']==300 and m.POLICY['workers']==2
    assert m.POLICY['fits']==m.POLICY['retries']==m.POLICY['replacement_candidates']==0
    assert m.POLICY['budget_accounting']=='summed_worker_process_seconds'
    assert m.PROOF_SEEDS=={'train':2026111109,'test':2026111110}


def authorization(tmp_path,monkeypatch,stages=('features','train-labels','test-labels')):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'TRAIN',tmp_path/'results/control-sharing-coverage-data');monkeypatch.setattr(m,'OUT',tmp_path/'results/control-sharing-coverage-validation')
    protocol=tmp_path/'results/control-sharing-coverage/protocol.json'
    m.write(protocol,{'frozen':True});m.write(m.TRAIN/'plan.json',{'frozen':True})
    r={'status':'approved','approved_by':'parent','authorized_stages':list(stages),'plan_sha256':m.sha(m.TRAIN/'plan.json'),'protocol_sha256':m.sha(protocol)}
    m.write(m.TRAIN/'parent-authorization.json',r);return r


def test_parent_gate_and_independent_receipts_precede_attempts(tmp_path,monkeypatch):
    r=authorization(tmp_path,monkeypatch,('features',));monkeypatch.setattr(m,'validate',lambda:{})
    assert m.parent_authorization('features')==r
    with pytest.raises(ValueError,match='stage'):m.run('train-labels')
    assert not (m.TRAIN/'label-attempt.json').exists()
    m.write(m.ROOT/'results/control-sharing-coverage/protocol.json',{'changed':True})
    with pytest.raises(ValueError,match='protocol'):m.run('features')
    assert not (m.TRAIN/'feature-attempt.json').exists()


def test_fixed48_and_exact_selected_feature_mapping(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);pool=m.pool_candidates();indices=[*range(48),48,56,64,72]
    full={'columns':['sample'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',full)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices});m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':full['columns'],'records':[full['records'][i] for i in indices]};m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()


def test_joint_completion_sums_worker_intervals_separately_from_wall(tmp_path,monkeypatch):
    authorization(tmp_path,monkeypatch);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(m.TRAIN/'preflight-audit.json',{'status':'pass'})
    monkeypatch.setattr(m,'training_candidates',lambda:[{'candidate_id':'a','formula':'in0'}])
    monkeypatch.setattr(m,'pool_candidates',lambda:[{'candidate_id':'b','formula':'in1'}])
    t=[0.0]
    def tick():t[0]+=0.1;return t[0]
    monkeypatch.setattr(m.time,'monotonic',tick);monkeypatch.setattr(m.os,'killpg',lambda *args:None)
    waits=[]
    class Process:
        pid=987654321
        def wait(self,timeout=None):
            if timeout is not None:waits.append(timeout)
            return 0
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:Process())
    class Pool:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def map(self,fn,values):return [fn(v) for v in values]
    monkeypatch.setattr(m,'ThreadPoolExecutor',Pool)
    result=m.run('features');summed=sum(r['native_elapsed_seconds'] for r in result['native_worker_jobs'])
    assert summed>0 and result['native_elapsed_seconds']==result['total_summed_worker_native_seconds']==summed
    assert result['stage_wall_elapsed_seconds']!=summed and result['stage_wall_budget_seconds']==149.5
    assert all(0<t<=149.5 for t in waits)


def test_profile_audit_replay_preserves_frozen_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'TRAIN',tmp_path/'train');m.write(m.TRAIN/'plan.json',{'frozen':True})
    target=m.ROOT/'results/control-sharing-coverage/measurement-input-profile-audit.json';before=target.read_bytes()
    result=m.profile_audit();assert result['new_training_count']==32 and target.read_bytes()==before


def test_lowbit_family_normalizer_is_sound_on_all128_joint_formulas():
    import random
    from isaforge.rtl import evaluate_formula
    rng=random.Random(2026111101)
    pairs=[(0,0),(0xffffffff,0),(0x80000000,0xffffffff),(0x7fffffff,1),(1,0x80000000)]
    pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(95))
    comparisons=0
    for row in [*m.training_candidates(),*m.pool_candidates()]:
        original=m.parse_formula(row['formula'])
        reduced=m.parse_formula(m.formula_string(m.lowbit_normalize(m.modular_normalize(m.formula_tree(row['formula'])))))
        for a,b in pairs:
            assert evaluate_formula(original,a,b)==evaluate_formula(reduced,a,b)
            comparisons+=1
    assert comparisons==12800
    assert m.family_key('sra(in0,andi(srai(in1,1),3))')==m.family_key('sra(in1,andi(srli(in0,1),3))')
    assert m.family_key('srai(in0,1)')!=m.family_key('srli(in0,1)')


def test_stronger_family_screen_rejects_no_revised_inputs_and_preserves_revision():
    train,pool=m.training_candidates(),m.pool_candidates()
    known={m.family_key(f) for f in m.inventory()[0]}
    tk={m.family_key(r['formula']) for r in train}
    assert not [r for r in [*train,*pool] if m.family_key(r['formula']) in known]
    assert not [r for r in pool if m.family_key(r['formula']) in tk]
    r=m.read(m.ROOT/'results/control-sharing-coverage/input-family-revision-v1.json')
    assert r['training_unchanged'] and r['training_before_sha256']==r['training_after_sha256']
    assert r['changed_pool_indices']==[*range(48,56),*range(64,72)]
    assert r['native_jobs']==r['fits']==0 and not r['new_predictions_or_labels_used']

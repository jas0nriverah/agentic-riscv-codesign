import importlib.util
from pathlib import Path
import pytest
SPEC=importlib.util.spec_from_file_location('feasibility_measure',Path(__file__).parents[1]/'scripts/measure_boundary_feasibility.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_fixed128_manifest_has_all_mandatory_populations_and_profile_classes():
    import boundary_carry_features as local
    rows=m.pool_candidates()
    assert len(rows)==len({r['formula'] for r in rows})==128
    assert [r['pool_index'] for r in rows]==list(range(128))
    assert [r['cohort'] for r in rows]==['general']*32+['sharing']*8+['legacy']*8+['challenge']*80
    assert sum(r['reserved_control'] for r in rows)==8
    assert all(local.learning_scope(r['formula']) for r in rows if not r['reserved_control'])
    assert not any(local.learning_scope(r['formula']) for r in rows if r['reserved_control'])
    for name,width,join in [('legacy_signed16_and_repeat',16,13),('legacy_signed8_preadd_xor_repeat',8,15)]:
        group=[r for r in rows if r['template']==name]
        assert len(group)==2
        for row in group:
            v=local.features(row['formula']);assert v[7]>=1 and v[10]==width and v[join]>=1


def test_historical_inventory_includes_latest32_training_and_all128_pool_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=10986
    for folder,file,count in [('boundary-corroboration-data','candidates.json',32),('boundary-corroboration-validation','pool-candidates.json',128)]:
        out=m.ROOT/'results'/folder;rows=m.read(out/file)
        assert len(rows)==count and all(r['formula'] in history for r in rows)
        for row in m.read(out/'novelty.json')['comparisons']:assert set(row['forms'])<=history


def test_private_runner_preserves_prior_sources_and_summed_native_policy():
    import measure_guarded_revision as old
    state=old.__file__,old.TRAIN,old.TEST
    runner=m.configure_runner()
    assert runner is not old and (old.__file__,old.TRAIN,old.TEST)==state
    assert runner.TRAIN==runner.TEST==m.OUT
    assert m.POLICY['total_native_seconds']==300 and m.POLICY['workers']==2
    assert m.POLICY['fits']==m.POLICY['retries']==m.POLICY['replacement_candidates']==0
    assert m.POLICY['budget_accounting']=='summed_worker_process_seconds'


def authorization(tmp_path,monkeypatch,stages=('features','labels')):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'OUT',tmp_path/'results/boundary-feasibility-validation')
    protocol=tmp_path/'results/boundary-feasibility/protocol.json'
    m.write(protocol,{'frozen':True});m.write(m.OUT/'plan.json',{'frozen':True})
    receipt={'status':'approved','approved_by':'parent','authorized_stages':list(stages),'plan_sha256':m.sha(m.OUT/'plan.json'),'protocol_sha256':m.sha(protocol)}
    m.write(m.OUT/'parent-authorization.json',receipt)
    return receipt


def test_parent_authorization_requires_exact_stage_plan_and_protocol(tmp_path,monkeypatch):
    r=authorization(tmp_path,monkeypatch,('features',))
    assert m.parent_authorization('features')==r
    with pytest.raises(ValueError,match='stage'):m.parent_authorization('labels')
    m.write(m.ROOT/'results/boundary-feasibility/protocol.json',{'changed':True})
    with pytest.raises(ValueError,match='protocol'):m.parent_authorization('features')


def test_run_without_parent_authorization_cannot_create_attempt(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);monkeypatch.setattr(m,'validate',lambda:{})
    with pytest.raises(FileNotFoundError):m.run('features')
    assert not (tmp_path/'feature-attempt.json').exists()


def test_selected_subset_requires_fixed48_and_exact_feature_records(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path);pool=m.pool_candidates();indices=[*range(48),48,56,64,72]
    features={'columns':['sample'],'records':[{**r,'values':[i]} for i,r in enumerate(pool)]}
    m.write(tmp_path/'pool-candidates.json',pool);m.write(tmp_path/'pool-features.json',features)
    m.write(tmp_path/'selection.json',{'selected_pool_indices':indices});m.write(tmp_path/'candidates.json',[pool[i] for i in indices])
    subset={'columns':features['columns'],'records':[features['records'][i] for i in indices]};m.write(tmp_path/'features.json',subset)
    assert m.selected()==[pool[i] for i in indices]
    subset['records'][0]['values']=[-1];m.write(tmp_path/'features.json',subset)
    with pytest.raises(ValueError,match='exact pool subset'):m.selected()


def test_completion_accounts_sum_of_worker_intervals_separately_from_wall(tmp_path,monkeypatch):
    authorization(tmp_path,monkeypatch);monkeypatch.setattr(m,'validate',lambda:{})
    m.write(m.OUT/'preflight-audit.json',{'status':'pass'})
    monkeypatch.setattr(m,'pool_candidates',lambda:[{'candidate_id':'a','formula':'in0'},{'candidate_id':'b','formula':'in1'}])
    counter=[0.0]
    def tick():counter[0]+=0.1;return counter[0]
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
    result=m.run('features')
    expected=sum(j['native_elapsed_seconds'] for j in result['native_worker_jobs'])
    assert expected>0 and result['native_elapsed_seconds']==expected
    assert result['total_summed_worker_native_seconds']==expected
    assert result['stage_wall_elapsed_seconds']!=expected
    assert result['stage_wall_budget_seconds']==149.5
    assert all(0<t<=149.5 for t in waits)


def test_copied_modular_rules_are_sound_and_do_not_erase_real_mask3_carry():
    from isaforge.rtl import evaluate_formula
    examples=('andi(addi(in0,2),1)','addi(addi(in0,9),2)','andi(addi(xori(in1,15),2),1)','andi(addi(in0,-4),3)')
    values=[*range(256),0x7fffffff,0x80000000,0xffffffff]
    count=0
    for f in examples:
        original=m.parse_formula(f);reduced=m.parse_formula(m.modular_formula(f))
        for a in values:
            for b in (0,1,3,0xffffffff):
                assert evaluate_formula(original,a,b)==evaluate_formula(reduced,a,b)
                count+=1
    assert count==4144
    assert m.modular_formula(examples[0])=='andi(in0,1)'
    assert m.modular_formula(examples[1])=='addi(in0,11)'
    assert m.modular_formula('andi(addi(in0,2),3)')=='andi(addi(in0,2),3)'


def test_revised_pool_has_no_modular_reduced_historical_skeleton_collisions():
    history,paths=m.inventory()
    known={m.skeleton(m.modular_formula(f)) for f in history}
    assert not [(r['pool_index'],r['template']) for r in m.pool_candidates() if m.skeleton(m.modular_formula(r['formula'])) in known]

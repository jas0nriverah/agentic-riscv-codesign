import importlib.util
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('budget_measure',Path(__file__).parents[1]/'scripts/measure_budget_release.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def test_joint_cohorts_have_distinct_compositions_and_required_coverage():
    import refine_signed_coverage as model
    train,test=m.candidates('train'),m.candidates('test')
    assert len(train)==len({r['formula'] for r in train})==32
    assert len(test)==len({r['formula'] for r in test})==40
    a={m.skeleton(r['formula']) for r in train};b={m.skeleton(r['formula']) for r in test}
    assert len(a)==8 and len(b)==10 and not a&b
    assert sum(r['template'].startswith('compound_') for r in train)==16
    assert sum(r['template'].startswith('signed_add_boolean_') for r in train)==16
    assert sum(r['template'].startswith('heldout_compound_') for r in test)==16
    assert sum(r['template'].startswith('heldout_signed_add_boolean_') for r in test)==16
    assert sum(r['template'].startswith('control_') for r in test)==8
    assert sum(r['template']=='heldout_compound_signed_add_xor' for r in test)==4
    assert all(model.route(r['formula'])['new_coverage'] for r in train)
    assert all(model.route(r['formula'])['new_coverage'] for r in test if not r['template'].startswith('control_'))
    assert not any(model.route(r['formula'])['new_coverage'] for r in test if r['template'].startswith('control_'))


def test_private_runner_uses_new_child_entry_and_preserves_native_contract():
    import measure_guarded_revision as old
    old_path=old.__file__;old_train=old.TRAIN;old_worker=old.worker
    runner=m.configure_runner()
    assert runner is not old and old.__file__==old_path and old.TRAIN==old_train and old.worker==old_worker
    assert Path(runner.__file__).resolve()==Path(m.__file__).resolve()
    assert runner.TRAIN==m.TRAIN and runner.TEST==m.TEST
    assert runner.candidates('test')==m.candidates('test')
    assert runner.worker==m.worker and m.ORIGINAL_WORKER!=m.worker
    assert runner.POLICY=={'total_native_seconds':300,'training_native_seconds':180,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    assert m.PROOF_SEEDS=={'train':2026111001,'test':2026111002}


def test_prior_inventory_includes_latest72_and_all_saved_aliases():
    history,paths=m.inventory();history=set(history)
    assert len(history)>=9238
    for name in ('signed-refinement-data','signed-refinement-validation'):
        for row in m.read(m.ROOT/'results'/name/'candidates.json'):assert row['formula'] in history
        for row in m.read(m.ROOT/'results'/name/'novelty.json')['comparisons']:assert set(row['forms'])<=history

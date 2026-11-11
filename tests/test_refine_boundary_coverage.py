"""Original-dataflow scope, exact five-model routing and fixed fresh populations."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('refinement',Path(__file__).parents[1]/'scripts/refine_boundary_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
SHIFT='sra(addi(xori(xor(in0,in1),23),61),andi(and(in0,in1),1))'


def test_all_commutative_xor_and_add_positions_and_no_constant_specific_routing():
    for a in (f'add({SHIFT},in0)',f'add(in0,{SHIFT})'):
        for f in (f'xor({a},in1)',f'xor(in1,{a})'):
            assert r.structural_route(f)
    assert r.structural_route('xor(add(sra(xori(addi(or(in0,in1),307),109),xor(in0,in1)),and(in0,in1)),in0)')


def test_same_direct_compound_shift_required_not_an_unrelated_shift_elsewhere():
    for f in (f'xor({SHIFT},add(in0,in1))',f'add({SHIFT},xor(in0,in1))',
              f'xor(add(sra(in0,in1),in0),{SHIFT})',
              f'xor(add(srai(addi(xori(in0,23),61),3),in0),{SHIFT})',
              f'xor(add(xori({SHIFT},7),in0),in1)',
              'xor(add(sra(addi(xori(in0,23),61),3),in0),in1)'):
        assert not r.structural_route(f)


def test_points_preserve_five_comparators_and_use_release_outside_scope(monkeypatch):
    rows=[{'formula':f} for f in (f'xor(add({SHIFT},in0),in1)',f'xor({SHIFT},add(in0,in1))')]
    old={'base':[120.,60.],r.CURRENT:[126.,64.],r.BUDGET:[129.,73.28],r.BROAD:[128.,64.]}
    monkeypatch.setattr(r.boundary,'points',lambda *args:(old,[{'compound':True}]*2,{'forest_medians_lut4':[128.,63.],'qualifying_caps_lut4':[[128],[64]]}))
    models,_,details=r.points(rows,np.zeros((2,336)),object())
    assert models[r.NAME]==[128.,73.28] and models[r.BROAD]==[128.,64.]
    assert details['structural_scope']==[True,False]
    assert details['applied_qualifying_caps_lut4']==[[128],[]]


def fixture():
    rows=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
    rows += [{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(96)]
    models={n:[129.]*128 for n in r.NAMES}
    for i in range(32,40):models[r.NAME][i]=128.
    freshness={'pool_feature_cluster_representatives':list(range(128)),'historical_match_pool_indices':[]}
    return rows,models,freshness


def test_general32_fixed_and_challenge_features_cannot_reuse_general_or_history():
    pool,models,freshness=fixture();freshness['historical_match_pool_indices']=[32]
    freshness['pool_feature_cluster_representatives'][33]=0
    s=r.choose(pool,models,freshness);cov=r.coverage(pool,models,s,freshness)
    assert s['selected_pool_indices'][:32]==list(range(32))
    assert s['historical_collision_active_pool_indices']==[32]
    assert s['general_feature_collision_active_pool_indices']==[33]
    assert s['selected_active_pool_indices']==[34,35,36,37,38,39]
    assert cov['passed'] and cov['conditional_shared_control_count']==8


def test_general_collision_blocks_without_replacing_fixed_rows():
    pool,models,freshness=fixture();freshness['historical_match_pool_indices']=[0]
    s=r.choose(pool,models,freshness);cov=r.coverage(pool,models,s,freshness)
    assert s['general_pool_indices']==list(range(32))
    assert not cov['checks']['general_feature_novel'] and not cov['passed']


def test_active_gate_rejects_new_false_accept_even_if_general_is_better():
    pool,models,freshness=fixture();s=r.choose(pool,models,freshness);cov=r.coverage(pool,models,s,freshness)
    indices=s['selected_pool_indices'];m={n:[models[n][i] for i in indices] for n in r.NAMES}
    # General signed points are128, release/refined129, actual150: strict gain.
    m[r.CURRENT][:32]=[128.]*32
    y=[150.]*32+[150.]*8
    saved={'models':m,'general_selected_indices':list(range(32)),'active_selected_indices':list(range(32,40)),
        'conditional_selected_indices':list(range(32,40))+list(range(24,32)),
        'selection_coverage':cov,'structural_scope':[True]*40}
    dev={'selected_candidate':r.NAME,'gates':{r.NAME:{'development_gate_passed':True}}}
    general,_,_,gates,eligible=r.score_values(saved,y,dev)
    assert gates[r.NAME]['checks']['general_passes']
    assert not gates[r.NAME]['checks']['active_subset_passes'] and not eligible

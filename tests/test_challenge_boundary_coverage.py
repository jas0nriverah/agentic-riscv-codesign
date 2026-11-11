"""Prospective selection uses frozen points and preserves active-only safeguards."""
import importlib.util
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('challenge',Path(__file__).parents[1]/'scripts/challenge_boundary_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


def fixture(active_by_template):
    pool=[{'template':'inactive','reserved_control':False} for _ in range(192)]+[{'template':'control','reserved_control':True} for _ in range(8)]
    models={n:[129.]*200 for n in r.NAMES};models[r.NAME]=[129.]*200
    for template,indices in active_by_template.items():
        for i in indices:pool[i]['template']=template;models[r.NAME][i]=128.
    return pool,models,{'pool_feature_cluster_representatives':list(range(200)),'historical_match_pool_indices':[]}


def test_round_robin_is_template_sorted_and_original_order_with_fixed_controls():
    pool,models,freshness=fixture({'zeta':list(range(20)),'alpha':list(range(20,40))})
    selected=r.choose(pool,models,freshness)
    assert selected['selected_active_pool_indices']==[v for pair in zip(range(20,28),range(8)) for v in pair]
    assert selected['selected_pool_indices'][-8:]==list(range(192,200))
    assert len(selected['selected_active_pool_indices'])==16 and len(selected['eligible_active_pool_indices'])==40
    cov=r.coverage(pool,models,selected,freshness)
    assert cov['passed'] and cov['selected_active_clamp_caps']['128']==16


def test_no_filling_or_replacements_when_activity_or_template_coverage_insufficient():
    pool,models,freshness=fixture({'single':[2,4,6]})
    selected=r.choose(pool,models,freshness);cov=r.coverage(pool,models,selected,freshness)
    assert selected['selected_active_pool_indices']==[2,4,6]
    assert len(selected['selected_pool_indices'])==11
    assert not cov['passed'] and not cov['checks']['at_least_four_active'] and not cov['checks']['at_least_two_active_templates']


def test_qualifying_higher_cap_does_not_count_as_actual_cap128_clamp():
    pool,models,freshness=fixture({'a':[1,2],'b':[3,4]})
    for i in (1,2,3,4):models[r.NAME][i]=64.
    cov=r.coverage(pool,models,r.choose(pool,models,freshness),freshness)
    assert cov['checks']['at_least_four_active'] and cov['checks']['at_least_two_active_templates']
    assert not cov['checks']['at_least_one_cap128_clamp'] and not cov['passed']


def test_active_subset_cannot_be_hidden_by_controls():
    pool,models,freshness=fixture({'a':[0,1],'b':[2,3]})
    selection=r.choose(pool,models,freshness);cov=r.coverage(pool,models,selection,freshness)
    # One active false acceptance invalidates the challenge despite safe controls.
    saved={'models':{n:[models[n][i] for i in selection['selected_pool_indices']] for n in r.NAMES},
        'active_selected_indices':[0,1,2,3],'selection_coverage':cov}
    dev={'selected_candidate':r.NAME,'gates':{r.NAME:{'development_gate_passed':True,'separate_broad40_metric_criteria_pass':True}}}
    y=[150.,125.,125.,125.]+[129.]*8
    _,active,gates,eligible=r.score_values(saved,y,dev)
    assert active and not gates[r.NAME]['checks']['active_subset_passes']
    assert not eligible


def test_historical_matches_excluded_and_within_pool_clusters_selected_once():
    pool,models,freshness=fixture({'a':[0,1,2],'b':[3,4]})
    freshness['historical_match_pool_indices']=[0]
    freshness['pool_feature_cluster_representatives'][3]=freshness['pool_feature_cluster_representatives'][1]
    selected=r.choose(pool,models,freshness)
    assert selected['raw_active_pool_indices']==[0,1,2,3,4]
    assert selected['historical_collision_active_pool_indices']==[0]
    assert selected['selected_active_pool_indices']==[1,4,2]
    assert selected['skipped_duplicate_active_pool_indices']==[3]
    cov=r.coverage(pool,models,selected,freshness)
    assert cov['raw_active_count']==5 and cov['eligible_active_count']==4 and cov['eligible_unique_active_count']==3
    assert not cov['passed']


def test_fixed_controls_are_not_replaced_when_feature_freshness_fails():
    pool,models,freshness=fixture({'a':[0,1],'b':[2,3]})
    freshness['historical_match_pool_indices']=[192]
    freshness['pool_feature_cluster_representatives'][193]=freshness['pool_feature_cluster_representatives'][0]
    selected=r.choose(pool,models,freshness);cov=r.coverage(pool,models,selected,freshness)
    assert selected['reserved_control_pool_indices']==list(range(192,200))
    assert not cov['checks']['reserved_controls_feature_novel'] and not cov['checks']['selected_feature_keys_unique']
    assert not cov['passed']

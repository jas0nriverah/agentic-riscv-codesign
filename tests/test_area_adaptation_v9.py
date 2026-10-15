"""Synthetic label-budget tests; no real application labels or fitting."""
from copy import deepcopy
import math

import numpy as np
import pytest

from isaforge import area_adaptation_v9 as a


def fixture(count=8, programs=None):
    programs = programs or [{'benchmark': 'app', 'family': 'F', 'primary_family': True,
                             'traceTotalInstructions': 1000}]
    rows, predictions, records, zero = [], [], [], {}
    for p_index, program in enumerate(programs):
        for index in range(count):
            formula = f'addi(in0,{p_index * 100 + index + 1})'
            row = {**program, 'candidate_id': str(index), 'formula': formula,
                   'overlapSafeSaved': 100 - index, 'runs': 10}
            rows.append(row)
            predictions.append({'benchmark': program['benchmark'], 'candidate_id': str(index),
                                'formula': formula, 'predicted_lut4': 50., 'upper_lut4': None})
            records.append({'formula': formula, 'v7_modes': {}})
            zero[formula] = False
    leaves = [[1, 2] for _ in sorted(zero)]
    return rows, programs, predictions, records, leaves, zero


def prepared(count=8):
    return a.prepare(*fixture(count))


def accepted(original, normalized, status='accepted'):
    return {'original_formula': original, 'normalized_formula': normalized,
            'metadata': {'status': status, 'certificate': 'synthetic'}}


def snapshot(replayed, budget, family='F'):
    return next(r for r in replayed['snapshots'] if r['family'] == family and r['budget'] == budget)


def test_kernel_uses_corresponding_tree_positions_without_labels():
    kernel = a.leaf_kernel([[1, 2], [2, 1], [1, 1]])
    assert kernel.tolist() == [[1., 0., .5], [0., 1., .5], [.5, .5, 1.]]
    assert np.linalg.eigvalsh(kernel).min() >= -1e-12
    for bad in ([[1., 2.]], [[True, False]], [[-1]], [[]], []):
        with pytest.raises(ValueError):
            a.leaf_kernel(bad)


def test_fixed_shrinkage_formula_bounds_and_no_monotonic_improvement_claim():
    p = prepared()
    targets = {f: 70 for f in p['formulas']}
    out = a.replay(p, lambda _family, formula: targets[formula])
    for budget in a.BUDGETS:
        state = snapshot(out, budget)
        for r in state['forecasts']:
            assert r['local_correction_lut4'] == pytest.approx(20 * budget / (1 + budget))
            assert r['predictions']['local_residual'] == r['predictions']['global_residual']
            assert abs(r['predictions']['local_residual'] - 50) <= 20 * budget / (1 + budget) + 1e-12
    # A wrong-sign residual can make a formerly exact unqueried prediction worse.
    support = p['episodes'][0]['schedule'][0]['formula']
    targets = {f: 50 for f in p['formulas']}
    targets[support] = 70
    scores = a.score(p, a.replay(p, lambda _, f: targets[f]), targets)
    assert scores['by_budget']['1']['local_minus_frozen_mae_lut4'] > 0


def test_no_support_effect_at_zero_proximity_clamping_and_original_zero_override():
    args = fixture()
    query_formula = args[0][0]['formula']
    victim = args[0][-1]['formula']
    zero_formula = args[0][-2]['formula']
    args[5][zero_formula] = True
    for row in args[2]:
        if row['formula'] == zero_formula:
            row['predicted_lut4'] = 0.
        elif row['formula'] == victim:
            row['predicted_lut4'] = 1.
    p = a.prepare(*args)
    state = a.forecast(p, p['episodes'][0], 1, {query_formula: 0})
    by_formula = {r['formula']: r for r in state['forecasts']}
    assert by_formula[victim]['predictions']['local_residual'] == 0
    assert set(by_formula[zero_formula]['predictions'].values()) == {0.}
    # Compare same tree positions with no support leaf overlap.
    p['kernel'] = a.leaf_kernel([[i, i] for i in range(len(p['formulas']))]).tolist()
    state = a.forecast(p, p['episodes'][0], 1, {query_formula: 90})
    assert all(r['predictions']['local_residual'] == r['predictions']['frozen'] for r in state['forecasts'])


def test_transitive_identity_groups_retain_fallback_and_exclude_all_memberships():
    args = fixture()
    f1, f2, f3, f4 = [r['formula'] for r in args[3][:4]]
    args[3][0]['v7_modes']['bit'] = accepted(f1, f2)
    args[3][2]['v7_modes']['affine'] = accepted(f3, f2)
    args[3][3]['v7_modes']['combined'] = accepted(f4, f3, 'fallback')
    p = a.prepare(*args)
    assert p['formula_group'][f1] == p['formula_group'][f2] == p['formula_group'][f3]
    assert p['formula_group'][f4] != p['formula_group'][f3]
    state = p['episodes'][0]['prefixes']['1']
    assert state['charged_unique_original_queries'] == 1
    assert state['excluded_unique_formulas'] == 3
    assert state['excluded_identity_group_count'] == 1
    assert not {f1, f2, f3} & set(state['retained_formulas'])
    assert f4 in state['retained_formulas']
    reversed_args = deepcopy(args)
    for index in (0, 2, 3):
        reversed_args[index].reverse()
    # Leaf rows are explicitly sorted by formula, independent of record order.
    assert a.prepare(*reversed_args) == p


def test_row_and_feature_outcome_metadata_never_enter_public_payload():
    args = fixture()
    before = a.prepare(*args)
    for row in args[0]:
        row.update(lut4_count=-999, target={'poison': True}, measured_lut4=math.inf)
    for record in args[3]:
        record.update(target='do not read', outcomes={'lut4_count': -999})
    after = a.prepare(*args)
    assert before == after
    assert all(set(r) == {'benchmark', 'family', 'primary_family', 'traceTotalInstructions',
                           'candidate_id', 'formula', 'overlapSafeSaved', 'runs'} for r in after['rows'])


def test_unrevealed_outcome_poison_cannot_change_queries_or_any_forecast():
    p = prepared()
    schedule = p['episodes'][0]['schedule']
    queried = {r['formula'] for r in schedule}
    targets = {f: 60 for f in p['formulas']}
    poisoned = {f: (value if f in queried else 999999) for f, value in targets.items()}
    calls = []
    first = a.replay(p, lambda family, f: calls.append((family, f)) or targets[f])
    second = a.replay(p, lambda _, f: poisoned[f])
    assert first == second
    assert calls == [('F', r['formula']) for r in schedule]
    assert a.score(p, first, targets) != a.score(p, second, poisoned)
    # Even a later *queried* label cannot leak backward to earlier budgets.
    poisoned = dict(targets)
    for request in schedule[3:]:
        poisoned[request['formula']] = 999999
    third = a.replay(p, lambda _, f: poisoned[f])
    assert snapshot(first, 1) == snapshot(third, 1)
    assert snapshot(first, 3) == snapshot(third, 3)
    assert snapshot(first, 5) != snapshot(third, 5)


def test_hidden_or_other_episode_labels_rejected_by_correction_boundary():
    p = prepared()
    episode = p['episodes'][0]
    prefix = episode['schedule'][0]['formula']
    hidden = episode['schedule'][1]['formula']
    with pytest.raises(ValueError, match='prefix exactly'):
        a.forecast(p, episode, 1, {prefix: 60, hidden: 60})
    with pytest.raises(ValueError, match='prefix exactly'):
        a.forecast(p, episode, 1, {})


def test_multi_program_family_round_robin_unique_queries_and_shared_exclusion():
    programs = [{'benchmark': n, 'family': 'F', 'primary_family': True, 'traceTotalInstructions': 1000}
                for n in ('a', 'b')]
    args = fixture(programs=programs)
    # The two first program memberships share the same original formula.
    old = args[0][8]['formula']
    shared = args[0][0]['formula']
    args[0][8]['formula'] = shared
    args[2][8]['formula'] = shared
    args[3].pop(8)
    del args[5][old]
    args = (*args[:4], [[1, 2] for _ in args[5]], args[5])
    p = a.prepare(*args)
    schedule = p['episodes'][0]['schedule']
    assert [r['benchmark'] for r in schedule] == ['a', 'b', 'a', 'b', 'a']
    assert len({r['formula'] for r in schedule}) == 5
    assert p['episodes'][0]['prefixes']['1']['excluded_membership_rows'] == 2
    assert p['episodes'][0]['prefixes']['1']['charged_unique_original_queries'] == 1


def test_failures_cost_one_supply_no_residual_and_are_not_replaced():
    p = prepared()
    calls = []
    out = a.replay(p, lambda _, f: calls.append(f))
    assert len(calls) == 5
    for budget in a.BUDGETS:
        state = snapshot(out, budget)
        assert state['successful_query_count'] == 0
        assert state['failed_query_count'] == budget
        assert all(r['predictions']['local_residual'] == r['predictions']['frozen'] for r in state['forecasts'])


def test_empty_programs_make_primary_macro_unavailable_not_zero():
    programs = [{'benchmark': n, 'family': f, 'primary_family': primary, 'traceTotalInstructions': 1000}
                for n, f, primary in (('a', 'A', True), ('b', 'B', True), ('related', 'related', False))]
    p = a.prepare(*fixture(count=2, programs=programs))
    targets = {f: 60 for f in p['formulas']}
    out = a.score(p, a.replay(p, lambda _, f: targets[f]), targets)
    assert out['by_budget']['1']['complete_primary_family_count'] == 2
    assert out['primary']['complete_primary_family_count'] == 0
    assert out['primary']['missing_primary_families'] == ['A', 'B']
    assert out['primary']['local_minus_frozen_mae_lut4'] is None
    related = next(r for r in out['family_results'] if r['family'] == 'related' and r['budget'] == 3)
    assert related['family_mae_lut4']['frozen'] is None
    assert related['exclusion']['budget_shortfall'] == 1


def test_identity_groups_exclude_but_do_not_reweight_formula_rows():
    args = fixture(count=4)
    f1, f2, f3, f4 = [r['formula'] for r in args[3]]
    args[3][1]['v7_modes']['combined'] = accepted(f2, f3)
    p = a.prepare(*args)
    targets = {f: 50 for f in p['formulas']}
    targets[f4] = 59
    out = a.score(p, a.replay(p, lambda _, f: targets[f]), targets)
    assert out['by_budget']['1']['family_macro_mae_lut4']['frozen'] == 3
    assert snapshot(a.replay(p, lambda _, f: targets[f]), 1)['exclusion']['unqueried_unique_original_formulas'] == 3


def test_metrics_keep_zero_mape_denominators_bias_and_cap64_errors():
    result = a.metrics([0, 64, 65], [2., 65., 64.])
    assert result['count'] == 3 and result['positive_target_count'] == 2
    assert result['zero_target_count'] == 1 and result['zero_mae_lut4'] == 2
    assert result['positive_mape_percent'] == pytest.approx(50 * (1/64 + 1/65))
    assert result['signed_bias_lut4'] == pytest.approx(2/3)
    assert result['cap64_false_accept_count'] == result['cap64_false_reject_count'] == 1
    assert a.metrics([], []) is None


@pytest.mark.parametrize('fault', ['duplicate_snapshot', 'missing_snapshot', 'extra_snapshot',
                                  'duplicate_forecast', 'missing_forecast', 'extra_adapter',
                                  'missing_adapter', 'changed_forecast', 'changed_query'])
def test_scorer_rejects_snapshot_coverage_and_forecast_or_query_mutations(fault):
    p = prepared()
    targets = {f: 60 for f in p['formulas']}
    result = a.replay(p, lambda _, f: targets[f])
    if fault == 'duplicate_snapshot':
        result['snapshots'].append(deepcopy(result['snapshots'][0]))
    elif fault == 'missing_snapshot':
        result['snapshots'].pop()
    elif fault == 'extra_snapshot':
        extra = deepcopy(result['snapshots'][0]);extra['family'] = 'unknown'
        result['snapshots'].append(extra)
    elif fault == 'duplicate_forecast':
        result['snapshots'][0]['forecasts'].append(deepcopy(result['snapshots'][0]['forecasts'][0]))
    elif fault == 'missing_forecast':
        result['snapshots'][0]['forecasts'].pop()
    elif fault == 'extra_adapter':
        result['snapshots'][0]['forecasts'][0]['predictions']['extra'] = 1.
    elif fault == 'missing_adapter':
        del result['snapshots'][0]['forecasts'][0]['predictions']['frozen']
    elif fault == 'changed_forecast':
        result['snapshots'][0]['forecasts'][0]['predictions']['local_residual'] += 1.
    elif fault == 'changed_query':
        result['query_log'][0]['target_lut4'] += 1
    with pytest.raises(ValueError):
        a.score(p, result, targets)


def test_equal_program_then_family_weights_and_secondary_exclusion():
    programs = [{'benchmark': n, 'family': family, 'primary_family': primary, 'traceTotalInstructions': 1000}
                for n, family, primary in (('a', 'A', True), ('b1', 'B', True),
                                           ('b2', 'B', True), ('related', 'related', False))]
    p = a.prepare(*fixture(count=8, programs=programs))
    errors = {'a': 10, 'b1': 20, 'b2': 60, 'related': 999}
    targets = {r['formula']: 50 + errors[r['benchmark']] for r in p['rows']}
    result = a.score(p, a.replay(p, lambda _, f: targets[f]), targets)
    assert result['primary']['family_macro_mae_lut4']['frozen'] == 25
    assert result['primary']['primary_family_count'] == 2


@pytest.mark.parametrize('target', [True, -1, .5, math.inf])
def test_invalid_revealed_target_rejected(target):
    p = prepared()
    with pytest.raises(ValueError):
        a.replay(p, lambda _, f: target)

"""Synthetic finite-pool decision contracts; no target scoring or native jobs."""
import copy
from dataclasses import replace
import math
from unittest.mock import patch

import numpy as np
import pytest
from scipy.stats import norm

from isaforge import codesign as c, finite_selection as f, joint_hardware as j
from test_budgeted_selection import history, measured, public


def pool():
    return [public('t1', 'add(in0,slli(in1,1))', saved_cycles=200),
            public('t2', 'sub(in0,in1)', saved_cycles=190),
            public('t3', 'xor(in0,in1)', saved_cycles=180),
            public('t4', 'or(in0,in1)', saved_cycles=80)]


@pytest.fixture(scope='module')
def initial():
    rows, targets = history(), pool()
    return rows, targets, j.JointHardwarePosterior.fit(rows, targets)


def synthetic(initial, *, diagonal=False, timing_boundary=False, equal_benefit=False):
    """A real adapter with declared synthetic Gaussian/Beta test parameters."""
    rows, targets, fitted = initial
    targets = copy.deepcopy(targets)
    if equal_benefit:
        targets = [public(r['candidate_id'], r['formula'], saved_cycles=100) for r in targets]
    direction = np.asarray([10., 10., -10., 0.])
    covariance = np.outer(direction, direction)+np.eye(4)*4
    if diagonal:
        covariance = np.diag(np.diag(covariance))
    outputs = {
        'area_delta_lut4': j._Output(j._array([64., 64., 64., 64. if equal_benefit else 25.]),
                                    j._array(covariance), 25.),
        'routed_fmax_min_mhz': j._Output(
            j._array([12.3, 12., 13., 15.] if timing_boundary else [20.]*4),
            j._array(np.eye(4)*2+np.ones((4, 4))*.5), .75),
        'log_measurement_seconds': j._Output(j._array([0., 1., 2., 3.]),
                                            j._array(np.eye(4)), .2),
    }
    state = j.JointHardwarePosterior(tuple(copy.deepcopy(targets)), outputs,
        copy.deepcopy(fitted._initial_snapshot), copy.deepcopy(fitted._source_bindings),
        _device_successes=1, _device_total=3)
    return rows, targets, state


def scalar_probability(mean, variance, threshold, *, above=False):
    if variance == 0:
        return float(mean >= threshold if above else mean <= threshold)
    z = (threshold-mean)/math.sqrt(variance)
    return float(norm.sf(z) if above else norm.cdf(z))


def explicit_actions(state, targets, draws, incumbent, cap=64., clock=12.):
    """Slow branch enumeration through the actual immutable fantasy updater.

    First-observation integration uses the declared normal table. The immediate
    term is an analytic Gaussian probability, deliberately not its sample mean.
    Second-query constraints include fresh observation noise after conditioning.
    """
    ids = [r['candidate_id'] for r in targets]
    joint = state.joint(ids)
    gains = [1-1/r['latency_features']['estimated_speedup'] for r in targets]
    device = joint['device_fit_probability']
    result = []
    for i, identity in enumerate(ids):
        first_probabilities = []
        for key, bound, above in [('area_delta_lut4', cap, False),
                                  ('routed_fmax_min_mhz', clock, True)]:
            output = joint['outputs'][key]
            first_probabilities.append(scalar_probability(output['mean'][i],
                output['observation_covariance'][i, i], bound, above=above))
        immediate = max(0., gains[i]-incumbent)*math.prod(first_probabilities)*device
        branch_maxima, branch_values = [], []
        for normal in draws:
            values = {}
            for dimension, key in enumerate(('area_delta_lut4', 'routed_fmax_min_mhz')):
                output = joint['outputs'][key]
                values[key] = float(output['mean'][i]+math.sqrt(
                    output['observation_covariance'][i, i])*normal[dimension])
            weighted_maximum, weighted_values = 0., np.zeros(len(ids)-1)
            for fits, weight in [(True, device), (False, 1-device)]:
                branch = state.fantasize(identity, values, device_fits=fits)
                feasible = fits and values['area_delta_lut4'] <= cap and values['routed_fmax_min_mhz'] >= clock
                next_incumbent = max(incumbent, gains[i]) if feasible else incumbent
                others = [k for k in range(len(ids)) if k != i]
                posterior = branch.joint([ids[k] for k in others])
                second_values = []
                for position, k in enumerate(others):
                    feasibility = posterior['device_fit_probability']
                    for key, bound, above in [('area_delta_lut4', cap, False),
                                              ('routed_fmax_min_mhz', clock, True)]:
                        output = posterior['outputs'][key]
                        feasibility *= scalar_probability(output['mean'][position],
                            output['observation_covariance'][position, position], bound, above=above)
                    second_values.append(max(0., gains[k]-next_incumbent)*feasibility)
                weighted_maximum += weight*max(second_values)
                weighted_values += weight*np.asarray(second_values)
            branch_maxima.append(weighted_maximum)
            branch_values.append(weighted_values)
        result.append((immediate, float(np.mean(branch_maxima)),
                       float(np.max(np.mean(branch_values, axis=0)))))
    return result


@pytest.mark.parametrize('incumbent', [0., .12])
@pytest.mark.parametrize('diagonal', [False, True])
def test_two_step_matches_128_explicit_real_updater_branches(initial, incumbent, diagonal):
    _, targets, state = synthetic(initial, diagonal=diagonal, timing_boundary=True)
    draws, _ = f.normal_draws(3)
    before = state.snapshot()
    actual = f.acquisition(state, targets, incumbent=incumbent, area_cap=64,
                           clock_mhz=12, remaining_queries=2, draws=draws)
    expected = explicit_actions(state, targets, draws, incumbent)
    for value, (immediate, future, fixed) in zip(actual, expected):
        assert value['immediate_expected_gain'] == pytest.approx(immediate, abs=1e-14)
        assert value['expected_adaptive_second_gain'] == pytest.approx(future, abs=1e-13)
        assert value['expected_fixed_second_gain'] == pytest.approx(fixed, abs=1e-13)
        assert value['two_step_expected_gain'] == pytest.approx(immediate+future, abs=1e-13)
        assert value['estimated_second_adaptation_value'] == pytest.approx(max(0., future-fixed), abs=1e-13)
        assert future >= fixed-1e-14
    assert state.snapshot() == before


def test_two_step_matches_explicit_branches_on_fitted_semantic_posterior(initial):
    _, targets, state = initial
    draws, _ = f.normal_draws(2)
    actual = f.acquisition(state, targets, incumbent=0., area_cap=40,
                           clock_mhz=15, remaining_queries=2, draws=draws)
    expected = explicit_actions(state, targets, draws, 0., cap=40, clock=15.)
    for value, (immediate, future, fixed) in zip(actual, expected):
        np.testing.assert_allclose([value['immediate_expected_gain'],
                                   value['expected_adaptive_second_gain'],
                                   value['expected_fixed_second_gain']],
                                  [immediate, future, fixed], rtol=1e-11, atol=1e-13)


def test_first_immediate_is_analytic_and_uses_observation_noise(initial):
    _, targets, state = synthetic(initial, timing_boundary=True)
    draws, _ = f.normal_draws(0)
    actual = f.acquisition(state, targets, incumbent=0., area_cap=67,
                           clock_mhz=12, remaining_queries=2, draws=draws)
    joint = state.joint()
    a, t = (joint['outputs'][key] for key in ('area_delta_lut4', 'routed_fmax_min_mhz'))
    gain = 1-1/targets[0]['latency_features']['estimated_speedup']
    observed = gain*norm.cdf((67-a['mean'][0])/math.sqrt(a['observation_covariance'][0, 0]))
    observed *= norm.sf((12-t['mean'][0])/math.sqrt(t['observation_covariance'][0, 0]))*state.device_fit_probability
    latent = gain*norm.cdf((67-a['mean'][0])/math.sqrt(a['covariance'][0, 0]))
    latent *= norm.sf((12-t['mean'][0])/math.sqrt(t['covariance'][0, 0]))*state.device_fit_probability
    sampled = gain*state.device_fit_probability*np.mean(
        (a['mean'][0]+math.sqrt(a['observation_covariance'][0, 0])*draws[:, 0] <= 67) &
        (t['mean'][0]+math.sqrt(t['observation_covariance'][0, 0])*draws[:, 1] >= 12))
    assert actual[0]['immediate_expected_gain'] == pytest.approx(observed, abs=1e-15)
    assert abs(observed-latent) > 1e-4
    assert abs(observed-sampled) > 1e-5


def test_correlated_information_has_adaptive_value_and_diagonal_control_does_not(initial):
    _, targets, correlated = synthetic(initial, equal_benefit=True)
    _, _, diagonal = synthetic(initial, equal_benefit=True, diagonal=True)
    draws, _ = f.normal_draws(4)
    def values(state):
        return f.acquisition(state, targets, incumbent=0., area_cap=64,
                             clock_mhz=12, remaining_queries=2, draws=draws)
    informed, independent = values(correlated), values(diagonal)
    assert informed[0]['estimated_second_adaptation_value'] > 1e-3
    assert independent[0]['estimated_second_adaptation_value'] == pytest.approx(0., abs=1e-14)
    assert informed[0]['expected_adaptive_second_gain'] != pytest.approx(independent[0]['expected_adaptive_second_gain'])


def test_normal_table_fixed_finite_reproducible_and_returned_metadata_copied():
    before = copy.deepcopy(f.SETTINGS)
    a, metadata = f.normal_draws(0)
    b, again = f.normal_draws(0)
    other, _ = f.normal_draws(1)
    assert a.shape == (128, 2) and np.isfinite(a).all()
    np.testing.assert_array_equal(a, b)
    assert metadata == again
    assert metadata['normals_sha256'] == c.digest(a.tolist())
    assert not np.array_equal(a, other)
    a[:] = 99
    metadata['settings'].clear()
    assert f.SETTINGS == before
    np.testing.assert_array_equal(f.normal_draws(0)[0], b)


def run_synthetic(initial, *, policy=f.MYOPIC, budget=3, provider=None, on_acquire=None, state=None):
    rows, targets, default = synthetic(initial)
    if state is not None:
        targets = list(state._public)
    return f.search(targets, rows, provider or (lambda row: measured(row, area=80)),
                    posterior=state or default, policy=policy, area_cap=64,
                    seed=0, budget=budget, on_acquire=on_acquire)


def test_last_query_lookahead_and_myopic_are_identical(initial):
    myopic = run_synthetic(initial, budget=1)
    lookahead = run_synthetic(initial, policy=f.LOOKAHEAD, budget=1)
    for key in ('candidate_id', 'score', 'action_values', 'posterior_state_sha256'):
        assert myopic['events'][0][key] == lookahead['events'][0][key]
    for value in lookahead['events'][0]['action_values']:
        assert value['expected_adaptive_second_gain'] == 0
        assert value['two_step_expected_gain'] == value['immediate_expected_gain']


def test_single_remaining_candidate_has_no_invented_second_query(initial):
    _, targets, state = synthetic(initial)
    draws, _ = f.normal_draws(0)
    actual = f.acquisition(state, targets[:1], incumbent=0., area_cap=64,
                           clock_mhz=12, remaining_queries=3, draws=draws)
    assert len(actual) == 1
    assert actual[0]['expected_adaptive_second_gain'] == 0
    assert actual[0]['expected_fixed_second_gain'] == 0
    assert actual[0]['two_step_expected_gain'] == actual[0]['immediate_expected_gain']


def test_planned_horizons_and_b1_fallback_cannot_be_b3_prefixes(initial):
    myopic = run_synthetic(initial, budget=1)
    single = run_synthetic(initial, policy=f.FALLBACK, budget=1)
    triple = run_synthetic(initial, policy=f.FALLBACK, budget=3)
    assert single['events'][0]['fallback_used']
    assert single['events'][0]['candidate_id'] == 't2'
    assert myopic['events'][0]['candidate_id'] == 't1'
    assert triple['events'][0]['candidate_id'] == myopic['events'][0]['candidate_id']
    proofs = [p['event'] for p in triple['acquisition_proofs']]
    assert [p['fallback_used'] for p in proofs] == [False, False, True]
    assert [p['remaining_queries'] for p in proofs] == [3, 2, 1]
    assert all(p['planned_budget'] == 3 for p in proofs)
    for budget in (1, 2, 3):
        run = run_synthetic(initial, policy=f.LOOKAHEAD, budget=budget)
        assert len(run['curve']) == budget
        assert [p['event']['remaining_queries'] for p in run['acquisition_proofs']] == list(range(budget, 0, -1))
        assert all(v['expected_adaptive_second_gain'] == 0 for v in run['acquisition_proofs'][-1]['event']['action_values'])
        if budget > 1:
            assert any(v['expected_adaptive_second_gain'] > 0 for v in run['acquisition_proofs'][0]['event']['action_values'])


def test_verified_incumbent_disables_final_fallback(initial):
    run = run_synthetic(initial, policy=f.FALLBACK, budget=2,
                        provider=lambda row: measured(row, area=20, savings=100))
    last = run['acquisition_proofs'][-1]['event']
    assert last['incumbent_verified_cycle_reduction'] == pytest.approx(.1)
    assert not last['fallback_used']


def test_duration_distribution_and_paid_duration_never_enter_decision(initial):
    _, _, base = synthetic(initial)
    outputs = dict(base._outputs)
    outputs['log_measurement_seconds'] = j._Output(j._array([100., -100., 30., -30.]),
                                                   j._array(np.eye(4)*1e6), 999.)
    other = replace(base, _outputs=outputs)
    original = run_synthetic(initial, policy=f.LOOKAHEAD, state=base,
                             provider=lambda r: measured(r, area=80, seconds=.01))
    changed = run_synthetic(initial, policy=f.LOOKAHEAD, state=other,
                            provider=lambda r: measured(r, area=80, seconds=999.))
    assert original['curve'][-1]['attempted_ids'] == changed['curve'][-1]['attempted_ids']
    for left, right in zip(original['acquisition_proofs'], changed['acquisition_proofs']):
        assert left['event']['action_values'] == right['event']['action_values']
        assert left['event']['score'] == right['event']['score']
    assert original['curve'][-1]['target_measurement_seconds'] != changed['curve'][-1]['target_measurement_seconds']


def test_proof_precedes_provider_callbacks_are_copies_and_initial_state_unchanged(initial):
    _, _, state = synthetic(initial)
    before = state.snapshot()
    order, sent = [], []
    def acquired(proof):
        order.append(('proof', proof['event']['candidate_id']))
        sent.append(copy.deepcopy(proof))
        proof['event']['candidate_id'] = 'callback-corruption'
        proof['posterior_snapshot'].clear()
        proof['fantasy_table']['settings'].clear()
    def provider(candidate):
        assert order[-1] == ('proof', candidate['candidate_id'])
        assert sent[-1]['event']['charged_before_query'] == len([x for x in order if x[0] == 'provider'])
        order.append(('provider', candidate['candidate_id']))
        outcome = measured(candidate, area=80)
        candidate['formula'] = 'provider-corruption'
        return outcome
    with patch.object(j.JointHardwarePosterior, 'fit', side_effect=AssertionError('No fit in search')):
        run = run_synthetic(initial, policy=f.LOOKAHEAD, state=state, provider=provider, on_acquire=acquired)
    assert state.snapshot() == before
    assert order == [(kind, p['event']['candidate_id']) for p in sent for kind in ('proof', 'provider')]
    assert run['acquisition_proofs'] == sent
    assert len(set(run['curve'][-1]['attempted_ids'])) == 3
    assert run['conditional_updates'] == 3 and run['initial_model_fits_in_search'] == 0


def test_repeated_search_exact_decisions_states_and_copied_provider_outcomes(initial):
    _, _, state = synthetic(initial)
    external = []
    def provider(candidate):
        result = measured(candidate, area=80)
        external.append(result)
        return result
    def acquired(_):
        for earlier in external:
            earlier['area_delta_lut4'] = -999
            earlier['latency_features']['estimated_speedup'] = 999
    first = run_synthetic(initial, policy=f.LOOKAHEAD, state=state,
                          provider=provider, on_acquire=acquired)
    second = run_synthetic(initial, policy=f.LOOKAHEAD, state=state)
    assert first['acquisition_proofs'] == second['acquisition_proofs']
    assert first['final_posterior_snapshot'] == second['final_posterior_snapshot']
    assert first['curve'][-1]['attempted_ids'] == second['curve'][-1]['attempted_ids']
    assert all(event['observation']['area_delta_lut4'] == 80 for event in first['events']
               if 'observation' in event)


def test_failed_attempt_charged_without_update_then_success_updates_same_real_state(initial):
    _, _, state = synthetic(initial)
    before = state.snapshot()
    outcomes = []
    def provider(row):
        outcome = (dict(**row, status='failed', measurement_seconds=7., error='infrastructure')
                   if not outcomes else measured(row, area=80, seconds=3.))
        outcomes.append(copy.deepcopy(outcome))
        return outcome
    run = run_synthetic(initial, budget=2, state=state, provider=provider)
    assert run['curve'][0]['failed_attempts'] == 1
    assert run['curve'][0]['measured_ids'] == []
    assert run['curve'][-1]['target_measurement_seconds'] == 10
    assert run['conditional_updates'] == 1
    assert run['acquisition_proofs'][1]['event']['charged_before_query'] == 1
    assert run['acquisition_proofs'][1]['event']['attempted_ids_before_query'] == [outcomes[0]['candidate_id']]
    assert run['acquisition_proofs'][1]['successful_paid_ids'] == []
    assert run['acquisition_proofs'][1]['posterior_snapshot'] == before
    actual = state.condition(outcomes[1], queried_id=outcomes[1]['candidate_id'])
    assert run['final_posterior_snapshot'] == actual.snapshot()
    assert state.snapshot() == before


@pytest.mark.parametrize('kind', ['public-label', 'nested-label', 'duplicate', 'history-change',
                                  'wrong-pool', 'paid-posterior', 'fantasy-posterior'])
def test_invalid_inputs_rejected_before_provider(initial, kind):
    rows, targets, state = synthetic(initial)
    if kind == 'public-label':
        targets[0]['area_delta_lut4'] = 1
    elif kind == 'nested-label':
        targets[0]['latency_features']['target_area'] = 1
    elif kind == 'duplicate':
        targets[1] = targets[0]
    elif kind == 'history-change':
        rows = copy.deepcopy(rows)
        rows[0]['area_delta_lut4'] += 1
    elif kind == 'wrong-pool':
        targets[0]['candidate_id'] = 'unknown'
    elif kind == 'paid-posterior':
        state = state.condition(measured(targets[0]), queried_id='t1')
    else:
        state = state.fantasize('t1', {'area_delta_lut4': 10})
    with pytest.raises((ValueError, KeyError)):
        f.search(targets, rows, lambda _: pytest.fail('Provider called on invalid input'),
                 posterior=state, policy=f.MYOPIC, area_cap=64, seed=0, budget=1)


@pytest.mark.parametrize('kind', ['wrong-id', 'wrong-formula', 'unverified', 'invalid-cycles',
                                  'failed-with-label', 'duplicate-result'])
def test_invalid_provider_outcomes_stop_without_retry(initial, kind):
    _, _, state = synthetic(initial)
    before, calls = state.snapshot(), []
    def provider(row):
        calls.append(row['candidate_id'])
        outcome = measured(row)
        if kind == 'wrong-id':
            outcome['candidate_id'] = 'unknown'
        elif kind == 'wrong-formula':
            outcome['formula'] = 'and(in0,in1)'
        elif kind == 'unverified':
            outcome['correctness_verified'] = False
        elif kind == 'invalid-cycles':
            outcome['candidate_cycles'] += 1
        elif kind == 'failed-with-label':
            outcome = dict(**row, status='failed', measurement_seconds=1., error='unknown', area_delta_lut4=0)
        elif len(calls) > 1:
            outcome = measured(next(r for r in state._public if r['candidate_id'] == calls[0]))
        return outcome
    with pytest.raises((ValueError, KeyError)):
        run_synthetic(initial, budget=3, provider=provider, state=state)
    assert len(calls) == (2 if kind == 'duplicate-result' else 1)
    assert len(set(calls)) == len(calls)
    assert state.snapshot() == before


@pytest.mark.parametrize('seed', [-1, True, 1.5])
def test_invalid_normal_seed_rejected(seed):
    with pytest.raises(ValueError):
        f.normal_draws(seed)


@pytest.mark.parametrize('kind', ['short-draws', 'nan-draws', 'zero-horizon', 'invalid-incumbent'])
def test_invalid_acquisition_contract_rejected(initial, kind):
    _, targets, state = synthetic(initial)
    draws, _ = f.normal_draws(0)
    if kind == 'short-draws':
        draws = draws[:64]
    elif kind == 'nan-draws':
        draws[0, 0] = float('nan')
    with pytest.raises(ValueError):
        f.acquisition(state, targets, incumbent=1. if kind == 'invalid-incumbent' else 0.,
                      area_cap=64, clock_mhz=12, remaining_queries=0 if kind == 'zero-horizon' else 2,
                      draws=draws)


def test_zero_variance_probabilities_include_equality_and_reject_negative_variance():
    np.testing.assert_array_equal(f.below(np.asarray([1., 2., 3.]), np.zeros(3), 2.), [1., 1., 0.])
    with pytest.raises(ValueError):
        f.below(0., -1., 0.)

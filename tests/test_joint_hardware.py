"""Synthetic posterior/update contracts; no measured selection/transfer claim."""
import copy
from dataclasses import FrozenInstanceError
import math
from unittest.mock import patch

import numpy as np
import pytest
from sklearn.gaussian_process import GaussianProcessRegressor

from isaforge import budgeted_selection as b, codesign as c
from isaforge import semantic_selection as s
from isaforge import joint_hardware as j
from test_budgeted_selection import history, measured, public


def pool():
    # Identical/related formulas deliberately ensure substantial covariance, so
    # observing one point must move another instead of testing a zero-covariance case.
    return [public('t1', 'xor(in0,slli(in1,1))'),
            public('t2', 'xor(in0,slli(in1,2))'),
            public('t3', 'or(in0,slli(in1,1))'),
            public('t4', 'sub(in0,in1)')]


def setup():
    rows = history()
    rows[0]['measurement_seconds'] = .7
    rows[1]['measurement_seconds'] = 2.3
    rows[2]['measurement_seconds'] = 8.
    rows[0]['routed_fmax_min_mhz'] = 15.
    rows[1]['routed_fmax_min_mhz'] = 25.
    rows[2]['routed_fmax_min_mhz'] = 45.
    source = s.SemanticHardwareSurrogate().fit(rows)
    return rows, source, j.JointHardwarePosterior.from_fitted(source, rows, pool())


def reference(source, rows, paid, targets):
    """Direct GP fit using exactly the INITIAL x/y preprocessing and fixed kernel."""
    matrix = s.semantic_matrix([{key: row[key] for key in b.PUBLIC_KEYS} for row in rows+paid])
    x = source.scaler.transform(matrix)
    query = source.scaler.transform(s.semantic_matrix(targets))
    result = {}
    for key, (initial, center, scale) in source.models.items():
        y = np.asarray([math.log(r['measurement_seconds']) if key == 'log_measurement_seconds'
                        else r[key] for r in rows+paid], dtype=float)
        direct = GaussianProcessRegressor(kernel=copy.deepcopy(initial.kernel_),
            alpha=initial.alpha, optimizer=None, normalize_y=False).fit(x, (y-center)/scale)
        mean, covariance = direct.predict(query, return_cov=True)
        result[key] = (mean*scale+center, covariance*scale**2)
    return result


def test_initial_matches_frozen_semantic_predict_without_any_adapter_fit():
    rows, source, _ = setup()
    expected = source.predict(pool())
    before = source.snapshot()
    forbidden = AssertionError('Adapter must not refit any estimator')
    with patch.object(GaussianProcessRegressor, 'fit', side_effect=forbidden), \
         patch.object(s.SemanticHardwareSurrogate, 'fit', side_effect=forbidden):
        adapter = j.JointHardwarePosterior.from_fitted(source, rows, pool())
        actual = adapter.predict()
    assert [r['candidate_id'] for r in actual] == [r['candidate_id'] for r in expected]
    for a, e in zip(actual, expected):
        for key in e:
            if key != 'candidate_id':
                assert a[key] == pytest.approx(e[key], abs=1e-12, rel=1e-12)
    assert source.snapshot() == before


def test_latent_covariance_scale_squared_noise_units_and_observation_diagonal():
    _, source, adapter = setup()
    x = source.scaler.transform(s.semantic_matrix(pool()))
    joint = adapter.joint()
    for key, output in joint['outputs'].items():
        gp, center, scale = source.models[key]
        raw_mean, raw_covariance = gp.predict(x, return_cov=True)
        np.testing.assert_array_equal(output['mean'], raw_mean*scale+center)
        np.testing.assert_array_equal(output['covariance'], raw_covariance*scale**2)
        assert output['observation_noise_variance'] == gp.alpha*scale**2
        np.testing.assert_allclose(output['observation_covariance']-output['covariance'],
                                   np.eye(len(pool()))*gp.alpha*scale**2, atol=1e-14)
        # This observed-at-initial-history point retains noise-scale latent variance.
        assert 0 < output['covariance'][0, 0] < 2*output['observation_noise_variance']
        assert output['covariance'][1, 1] > output['covariance'][0, 0]
    assert joint['outputs']['area_delta_lut4']['observation_noise_variance'] == .0064
    assert 'assumed noise' in adapter.snapshot()['noise_interpretation']


@pytest.mark.parametrize('paid_count', [1, 2, 3])
def test_conditions_match_direct_fit_with_fixed_initial_normalization(paid_count):
    rows, source, adapter = setup()
    paid = [measured(pool()[0], area=95, fmax=19, seconds=12),
            measured(pool()[1], area=75, fmax=14, seconds=.9),
            measured(pool()[2], area=-3, fmax=49, seconds=3.1)][:paid_count]
    initial = adapter.snapshot()
    forbidden = AssertionError('Conditioning must not fit/recenter/restandardize')
    with patch.object(GaussianProcessRegressor, 'fit', side_effect=forbidden), \
         patch.object(s.SemanticHardwareSurrogate, 'fit', side_effect=forbidden):
        conditioned = adapter
        for outcome in paid:
            conditioned = conditioned.condition(outcome, queried_id=outcome['candidate_id'])
    expected = reference(source, rows, paid, pool())
    for key, (means, covariance) in expected.items():
        output = conditioned.joint()['outputs'][key]
        np.testing.assert_allclose(output['mean'], means, rtol=1e-10, atol=1e-9)
        np.testing.assert_allclose(output['covariance'], covariance, rtol=1e-9, atol=1e-10)
    assert conditioned.snapshot()['initial_snapshot'] == initial['initial_snapshot']
    assert adapter.snapshot() == initial
    assert conditioned.observed_ids == tuple(r['candidate_id'] for r in paid)


def test_fixed_conditional_update_is_distinct_from_old_dynamic_refit():
    rows, source, adapter = setup()
    paid = measured(pool()[1], area=151, fmax=4, seconds=50.)
    fixed = adapter.condition(paid, queried_id='t2').predict()
    dynamic = s.SemanticHardwareSurrogate().fit(rows+[paid]).predict(pool())
    assert max(abs(a['area_delta_lut4_mean']-z['area_delta_lut4_mean'])
               for a, z in zip(fixed, dynamic)) > 1.
    assert adapter.snapshot()['initial_snapshot']['scaler'] == source.snapshot()['scaler']


def test_covariance_symmetric_psd_and_information_moves_unobserved_points():
    _, _, adapter = setup()
    before = adapter.joint()
    after = adapter.condition(measured(pool()[1], area=123), queried_id='t2').joint()
    for key in j.OUTPUTS:
        a, z = before['outputs'][key], after['outputs'][key]
        np.testing.assert_allclose(z['covariance'], z['covariance'].T, atol=1e-14)
        assert np.linalg.eigvalsh(z['covariance']).min() >= -1e-10
        assert np.linalg.eigvalsh(a['covariance']-z['covariance']).min() >= -1e-10
        assert np.all(np.diag(z['covariance']) <= np.diag(a['covariance'])+1e-12)
        assert 0 < z['covariance'][1, 1] < z['observation_noise_variance']
    # A related unobserved point actually moves; diagonal marginal fantasies fail this.
    assert abs(after['outputs']['area_delta_lut4']['mean'][0]-
               before['outputs']['area_delta_lut4']['mean'][0]) > 1e-4


def test_snapshot_exact_ids_initial_scaler_sources_and_paid_proof():
    rows, source, adapter = setup()
    before = adapter.snapshot()
    assert before['initial_snapshot'] == source.snapshot()
    assert before['initial_training_ids'] == [r['candidate_id'] for r in rows]
    assert before['initial_snapshot']['training_rows_sha256'] == c.digest(rows)
    assert before['source_bindings'] == j.source_bindings()
    assert before['public_pool_sha256'] == c.digest(pool())
    assert len(before['posterior_state_sha256']) == 64
    paid = measured(pool()[0])
    after = adapter.condition(paid, queried_id='t1').snapshot()
    assert after['initial_snapshot'] == before['initial_snapshot']
    assert after['paid_ids'] == ['t1']
    assert after['paid_outcomes_sha256'] == c.digest([paid])
    assert after['posterior_state_sha256'] != before['posterior_state_sha256']
    assert not after['hypothetical']


def test_device_probability_and_beta_counts_update_with_successful_nonfitting_outcome():
    _, _, adapter = setup()
    paid = measured(pool()[0], area=9999)
    paid['device_fits'] = False
    after = adapter.condition(paid, queried_id='t1')
    assert adapter.device_fit_probability == 4/5
    assert after.device_fit_probability == 4/6
    assert after.joint()['device_fit_alpha'] == 4
    assert after.joint()['device_fit_beta'] == 2
    assert after.snapshot()['device_fit_alpha'] == 4
    assert after.snapshot()['device_fit_beta'] == 2
    # Outside-cap and device-nonfit successful hardware values are retained.
    assert after.observed_ids == ('t1',)


def test_clone_and_all_public_returns_are_independent_of_source_and_caller_mutation():
    rows, source, adapter = setup()
    before = adapter.snapshot()
    clone = adapter.clone()
    rows[0]['area_delta_lut4'] = 9000
    source.models['area_delta_lut4'][0].alpha_[0] += 500
    source.scaler.mean_[0] += 100
    joint = adapter.joint()
    joint['outputs']['area_delta_lut4']['mean'][:] = -900
    joint['outputs']['area_delta_lut4']['covariance'][:] = -900
    snapshot = adapter.snapshot()
    snapshot['initial_snapshot']['scaler']['mean'].clear()
    assert adapter.snapshot() == clone.snapshot() == before
    outcome = measured(pool()[0])
    updated = clone.condition(outcome, queried_id='t1')
    updated_snapshot = updated.snapshot()
    outcome['area_delta_lut4'] += 1
    assert updated.snapshot() == updated_snapshot
    assert adapter.snapshot() == before
    with pytest.raises(FrozenInstanceError):
        adapter._device_total = 100


def test_fantasy_exactly_matches_paid_gaussian_update_but_marks_hypothetical():
    _, _, adapter = setup()
    outcome = measured(pool()[1], area=71, fmax=7, seconds=1.3)
    values = {key: math.log(outcome['measurement_seconds']) if key == 'log_measurement_seconds'
              else outcome[key] for key in j.OUTPUTS}
    real = adapter.condition(outcome, queried_id='t2')
    fantasy = adapter.fantasize('t2', values, device_fits=True)
    for key in j.OUTPUTS:
        for array in ('mean', 'covariance', 'observation_covariance'):
            np.testing.assert_array_equal(real.joint()['outputs'][key][array],
                                          fantasy.joint()['outputs'][key][array])
    assert fantasy.snapshot()['hypothetical']
    assert fantasy.observed_ids == () and fantasy.conditioned_ids == ('t2',)
    assert fantasy.snapshot()['paid_ids'] == []
    with pytest.raises(ValueError, match='Hypothetical'):
        fantasy.condition(measured(pool()[2]), queried_id='t3')


def test_partial_fantasies_do_not_fabricate_duration_and_gaussian_tails_are_allowed():
    _, _, adapter = setup()
    before = adapter.snapshot()
    fantasy = adapter.fantasize('t2', dict(area_delta_lut4=-100, routed_fmax_min_mhz=-5),
                                device_fits=False)
    for array in ('mean', 'covariance'):
        np.testing.assert_array_equal(adapter.joint()['outputs']['log_measurement_seconds'][array],
                                      fantasy.joint()['outputs']['log_measurement_seconds'][array])
    assert fantasy.device_fit_probability == 4/6
    assert adapter.snapshot() == before
    assert fantasy.fantasize('t3', dict(area_delta_lut4=50)).conditioned_ids == ('t2', 't3')


@pytest.mark.parametrize('bad_values', [{}, {'unknown': 5}, {'area_delta_lut4': float('nan')},
                                       {'routed_fmax_min_mhz': float('inf')}])
def test_invalid_fantasies_are_rejected_without_mutation(bad_values):
    _, _, adapter = setup()
    before = adapter.snapshot()
    with pytest.raises(ValueError):
        adapter.fantasize('t1', bad_values)
    assert adapter.snapshot() == before


def test_repeated_or_unqueried_or_mismatched_observations_are_rejected():
    _, _, adapter = setup()
    paid = measured(pool()[0])
    after = adapter.condition(paid, queried_id='t1')
    for call in (lambda: after.condition(paid, queried_id='t1'),
                 lambda: after.fantasize('t1', {'area_delta_lut4': 1}),
                 lambda: adapter.condition(paid, queried_id='t2'),
                 lambda: adapter.condition(paid, queried_id='not-in-pool'),
                 lambda: adapter.fantasize('not-in-pool', {'area_delta_lut4': 1})):
        with pytest.raises(ValueError):
            call()
    changed = measured(pool()[0])
    changed['formula'] = 'sub(in0,in1)'
    with pytest.raises(ValueError):
        adapter.condition(changed, queried_id='t1')


@pytest.mark.parametrize('kind', ['failed', 'failed-with-label', 'incomplete', 'unverified',
                                  'invalid-cycles', 'nonfinite', 'zero-seconds', 'hidden-label'])
def test_failed_incomplete_invalid_outcomes_cannot_fabricate_labels(kind):
    _, _, adapter = setup()
    before = adapter.snapshot()
    outcome = measured(pool()[0])
    if kind.startswith('failed'):
        outcome = dict(**pool()[0], status='failed', measurement_seconds=2., error='infrastructure')
        if kind == 'failed-with-label':
            outcome['area_delta_lut4'] = 0
    elif kind == 'incomplete':
        del outcome['routed_fmax_min_mhz']
    elif kind == 'unverified':
        outcome['correctness_verified'] = False
    elif kind == 'invalid-cycles':
        outcome['candidate_cycles'] += 1
    elif kind == 'nonfinite':
        outcome['area_delta_lut4'] = float('nan')
    elif kind == 'zero-seconds':
        outcome['measurement_seconds'] = 0
    elif kind == 'hidden-label':
        outcome['latency_features']['hidden_area_label'] = 2
    with pytest.raises((ValueError, KeyError)):
        adapter.condition(outcome, queried_id='t1')
    assert adapter.snapshot() == before


def test_history_and_public_label_leakage_or_fitted_cohort_mismatch_rejected():
    rows, source, adapter = setup()
    with pytest.raises(ValueError):
        j.JointHardwarePosterior.from_fitted(source, rows, [measured(pool()[0])])
    leaked_pool = [public('h1')]
    with pytest.raises(ValueError, match='Target identity'):
        j.JointHardwarePosterior.from_fitted(source, rows, leaked_pool)
    changed = copy.deepcopy(rows)
    changed[0]['area_delta_lut4'] += 1
    with pytest.raises(ValueError, match='history differs'):
        j.JointHardwarePosterior.from_fitted(source, changed, pool())
    with pytest.raises(ValueError):
        j.JointHardwarePosterior.fit(rows+[rows[0]], pool())
    with pytest.raises(ValueError):
        j.JointHardwarePosterior.fit([], pool())
    with pytest.raises(ValueError):
        j.JointHardwarePosterior.from_fitted(s.SemanticHardwareSurrogate(), rows, pool())
    with pytest.raises(ValueError):
        j.JointHardwarePosterior.from_fitted(b.HardwareSurrogate().fit(rows), rows, pool())


def test_current_scaler_drift_is_detected_before_reading_predictions():
    rows, source, _ = setup()
    source.scaler.scale_[0] += 1
    with pytest.raises(ValueError, match='scaler differs'):
        j.JointHardwarePosterior.from_fitted(source, rows, pool())


def test_factory_initial_fit_is_the_unchanged_semantic_model():
    rows, source, _ = setup()
    adapter = j.JointHardwarePosterior.fit(rows, pool())
    assert adapter.snapshot()['initial_snapshot'] == source.snapshot()
    assert adapter.snapshot()['source_bindings'] == j.source_bindings()


def test_subset_order_empty_and_prediction_pool_boundary():
    _, _, adapter = setup()
    joint = adapter.joint(['t3', 't1'])
    assert joint['candidate_ids'] == ['t3', 't1']
    original = adapter.joint()['outputs']['area_delta_lut4']
    subset = joint['outputs']['area_delta_lut4']
    np.testing.assert_array_equal(subset['mean'], original['mean'][[2, 0]])
    np.testing.assert_array_equal(subset['covariance'], original['covariance'][np.ix_([2, 0], [2, 0])])
    assert adapter.joint([])['outputs']['area_delta_lut4']['covariance'].shape == (0, 0)
    assert adapter.predict([]) == []
    assert [r['candidate_id'] for r in adapter.predict([pool()[2], pool()[0]])] == ['t3', 't1']
    for ids in (['t1', 't1'], ['unknown']):
        with pytest.raises(ValueError):
            adapter.joint(ids)
    with pytest.raises(ValueError):
        adapter.predict([public('t1', 'add(in0,in1)')])

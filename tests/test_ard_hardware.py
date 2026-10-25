"""Synthetic, train-only ARD initializer checks; no research outcome/scoring."""
import copy
from dataclasses import FrozenInstanceError
import json
import math
from unittest.mock import patch
import warnings

import numpy as np
import pytest
from scipy.optimize import OptimizeResult
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF

from isaforge import ard_hardware as a, budgeted_selection as b, codesign as c
from isaforge import joint_hardware as j, semantic_selection as s
from test_budgeted_selection import history, measured, public


def training():
    rows = history()
    rows += [measured(public('h4', 'add(in0,in1)', 'old3:ctx'), area=17, fmax=30, seconds=.5),
             measured(public('h5', 'sub(in0,slli(in1,2))', 'old3:ctx'), area=88, fmax=17, seconds=10),
             measured(public('h6', 'add(in0,slli(in1,2))', 'old4:ctx'), area=57, fmax=24, seconds=3.1)]
    return rows


def pool():
    return [public('t1', 'xor(in0,slli(in1,1))'),
            public('t2', 'xor(in0,slli(in1,2))'),
            public('t3', 'add(in0,slli(in1,2))'),
            public('t4', 'or(in0,in1)')]


@pytest.fixture(scope='module')
def initialized():
    return a.initialize(training(), pool())


def initial_record(initialized):
    return initialized.posterior.snapshot()['initial_snapshot']


def direct(initialized, paid=()):
    source = s.SemanticHardwareSurrogate().fit(training())
    record = initial_record(initialized)
    kernel = record['selected_kernel']
    area = source.models[a.AREA]
    rows = training()+list(paid)
    public_rows = [{key: row[key] for key in b.PUBLIC_KEYS} for row in rows]
    x = source.scaler.transform(s.semantic_matrix(public_rows))
    y = (np.asarray([row[a.AREA] for row in rows])-area[1])/area[2]
    model = GaussianProcessRegressor(kernel=ConstantKernel(kernel['amplitude'], a.AMPLITUDE_BOUNDS)*
        RBF(np.asarray(kernel['length_scales']), a.LENGTH_SCALE_BOUNDS),
        alpha=1e-4, optimizer=None, normalize_y=False).fit(x, y)
    mean, covariance = model.predict(source.scaler.transform(s.semantic_matrix(pool())), return_cov=True)
    return source, model, mean*area[2]+area[1], covariance*area[2]**2


def test_exact_predeclared_single_procedure_and_three_starts():
    assert a.DIMENSIONS == len(s.COLUMNS) == 37
    assert a.AMPLITUDE_BOUNDS == (.01, 100.)
    assert a.LENGTH_SCALE_BOUNDS == (.1, 100.)
    assert a.START_LENGTH_SCALES == (1., math.sqrt(37), 10.)
    assert a.OPTIMIZER_OPTIONS == dict(maxiter=200, maxfun=1000, ftol=1e-9, gtol=1e-5)
    assert a.SETTINGS['alpha'] == 1e-4 and a.SETTINGS['normalize_y'] is False
    assert [start['length_scales'] for start in a.SETTINGS['starts']] == [[v]*37 for v in a.START_LENGTH_SCALES]


def test_actual_optimizer_calls_have_fixed_starts_bounds_analytic_gradient_and_all_six_fits():
    optimizer_calls, fits = [], []
    original_minimize, original_fit = a.minimize, GaussianProcessRegressor.fit
    def minimize(fun, theta, *, method, jac, bounds, options):
        optimizer_calls.append(dict(theta=theta.copy(), method=method, jac=jac,
                                    bounds=np.array(bounds), options=copy.deepcopy(options)))
        value, gradient = fun(theta)
        assert math.isfinite(value) and gradient.shape == (38,) and np.isfinite(gradient).all()
        return original_minimize(fun, theta, method=method, jac=jac, bounds=bounds, options=options)
    def fit(self, x, y):
        fits.append((copy.deepcopy(self.kernel), np.array(x), np.array(y), self.alpha))
        return original_fit(self, x, y)
    with patch.object(a, 'minimize', side_effect=minimize), patch.object(GaussianProcessRegressor, 'fit', fit):
        result = a.initialize(training(), pool())
    assert len(fits) == 6 and len(optimizer_calls) == 3
    assert all(isinstance(kernel, type(fits[0][0])) for kernel, _, _, _ in fits[:3])
    for i, call in enumerate(optimizer_calls):
        assert call['method'] == 'L-BFGS-B' and call['jac'] is True
        assert call['options'] == a.OPTIMIZER_OPTIONS
        np.testing.assert_allclose(call['theta'], [0.]+[math.log(a.START_LENGTH_SCALES[i])]*37)
        np.testing.assert_array_equal(call['bounds'], np.log([a.AMPLITUDE_BOUNDS]+[a.LENGTH_SCALE_BOUNDS]*37))
    for kernel, x, y, alpha in fits[3:]:
        assert isinstance(kernel.k1, ConstantKernel) and isinstance(kernel.k2, RBF)
        np.testing.assert_array_equal(x, fits[0][1])
        np.testing.assert_array_equal(y, fits[0][2])
        assert alpha == 1e-4
    assert result.costs['total_scalar_gp_fit_attempts'] == 6


def test_new_schema_keeps_authenticated_original_initial_preprocessing_and_exact_other_outputs(initialized):
    source = s.SemanticHardwareSurrogate().fit(training())
    original = j.JointHardwarePosterior.from_fitted(source, training(), pool())
    record = initial_record(initialized)
    assert record['schema'] == a.SCHEMA != source.snapshot()['schema']
    assert record['original_semantic_snapshot'] == source.snapshot()
    assert record['training_ids'] == [r['candidate_id'] for r in training()]
    assert record['training_rows_sha256'] == c.digest(training())
    assert record['scaler'] == source.snapshot()['scaler']
    assert record['outputs'] == source.snapshot()['outputs']
    assert type(initialized.posterior) is j.JointHardwarePosterior
    assert initialized.posterior.observed_ids == initialized.posterior.conditioned_ids == ()
    for key in ('routed_fmax_min_mhz', 'log_measurement_seconds'):
        for field in ('mean', 'covariance', 'observation_covariance'):
            np.testing.assert_array_equal(initialized.posterior.joint()['outputs'][key][field],
                                          original.joint()['outputs'][key][field])
        assert initialized.posterior.joint()['outputs'][key]['observation_noise_variance'] == \
               original.joint()['outputs'][key]['observation_noise_variance']
    for field in ('device_fit_alpha', 'device_fit_beta', 'device_fit_probability'):
        assert initialized.posterior.joint()[field] == original.joint()[field]
    assert 'private' in a.__doc__.lower()
    assert record['source_bindings'] == initialized.posterior.snapshot()['source_bindings'] == a.source_bindings()
    assert 'isaforge/ard_hardware.py' in a.SOURCES and set(j.SOURCES) <= set(a.SOURCES)


def test_selected_area_matches_direct_ard_kernel_covariance_noise_and_physical_scaling(initialized):
    source, model, mean, covariance = direct(initialized)
    output = initialized.posterior.joint()['outputs'][a.AREA]
    np.testing.assert_allclose(output['mean'], mean, rtol=0, atol=1e-12)
    np.testing.assert_allclose(output['covariance'], covariance, rtol=0, atol=1e-12)
    scale = source.models[a.AREA][2]
    assert output['observation_noise_variance'] == model.alpha*scale**2
    np.testing.assert_allclose(output['observation_covariance']-output['covariance'],
                               np.eye(len(pool()))*model.alpha*scale**2, atol=1e-13)
    assert np.linalg.eigvalsh(output['covariance']).min() >= -1e-10
    np.testing.assert_allclose(output['covariance'], output['covariance'].T, atol=1e-13)


@pytest.mark.parametrize('count', [1, 2])
def test_fixed_paid_conditioning_matches_direct_fit_with_same_selected_ard_and_initial_scaling(initialized, count):
    paid = [measured(pool()[0], area=120, fmax=19, seconds=8),
            measured(pool()[1], area=3, fmax=27, seconds=.7)][:count]
    source, _, mean, covariance = direct(initialized, paid)
    original = j.JointHardwarePosterior.from_fitted(source, training(), pool())
    updated, original_updated = initialized.posterior, original
    with patch.object(GaussianProcessRegressor, 'fit', side_effect=AssertionError('Paid updates never refit')):
        for row in paid:
            updated = updated.condition(row, queried_id=row['candidate_id'])
            original_updated = original_updated.condition(row, queried_id=row['candidate_id'])
    output = updated.joint()['outputs'][a.AREA]
    np.testing.assert_allclose(output['mean'], mean, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(output['covariance'], covariance, rtol=1e-8, atol=1e-9)
    assert np.linalg.eigvalsh(output['covariance']).min() >= -1e-9
    assert updated.snapshot()['initial_snapshot'] == initial_record(initialized)
    for key in ('routed_fmax_min_mhz', 'log_measurement_seconds'):
        for field in ('mean', 'covariance'):
            np.testing.assert_array_equal(updated.joint()['outputs'][key][field],
                                          original_updated.joint()['outputs'][key][field])
    assert updated.device_fit_probability == original_updated.device_fit_probability


def test_three_optimizer_records_all_statuses_evaluation_counts_bound_hits_and_best_objective(initialized):
    record = initial_record(initialized)
    attempts = record['optimizer_attempts']
    assert [r['start_index'] for r in attempts] == [0, 1, 2]
    for attempt in attempts:
        assert attempt['fit_completed'] and attempt['eligible'] and attempt['objective_is_finite']
        assert type(attempt['optimizer_status']) is int and type(attempt['optimizer_success']) is bool
        assert attempt['function_evaluations'] > 0 and attempt['gradient_evaluations'] > 0
        assert attempt['objective_calls'] == attempt['function_evaluations']+1
        assert attempt['gradient_calls'] == attempt['gradient_evaluations']
        assert attempt['post_optimizer_objective_evaluations'] == 1
        assert attempt['optimizer_message'] and len(attempt['optimized_log_parameters']) == 38
        expected_hits = a._bound_hits(attempt['optimized_log_parameters'],
                                     np.log([a.AMPLITUDE_BOUNDS]+[a.LENGTH_SCALE_BOUNDS]*37))
        assert attempt['bound_hits'] == expected_hits
        assert all(set(warning) == {'category', 'message'} for warning in attempt['warnings'])
    best = min(range(3), key=lambda i:(attempts[i]['negative_log_marginal_likelihood'], i))
    assert record['selected_start_index'] == best
    assert record['selected_kernel'] == attempts[best]['selected_kernel']
    assert record['selected_negative_log_marginal_likelihood'] == attempts[best]['negative_log_marginal_likelihood']
    assert len(record['model_state_sha256']) == 64
    json.dumps(record, allow_nan=False)


def test_deterministic_source_state_proof_and_independent_raw_host_costs(initialized):
    repeated = a.initialize(training(), pool())
    assert repeated.posterior.snapshot() == initialized.posterior.snapshot()
    counts = ('semantic_surrogate_fits', 'semantic_scalar_gp_fits', 'unused_original_semantic_area_scalar_fits',
              'ard_scalar_gp_fit_attempts', 'ard_scalar_gp_fits_completed', 'total_scalar_gp_fit_attempts')
    assert {key: repeated.costs[key] for key in counts} == initial_record(initialized)['fit_accounting']
    assert repeated.costs['semantic_scalar_gp_fits'] == 3
    assert repeated.costs['unused_original_semantic_area_scalar_fits'] == 1
    assert repeated.costs['ard_scalar_gp_fit_attempts'] == 3
    assert repeated.costs['total_scalar_gp_fit_attempts'] == 6
    times = repeated.costs['ard_start_fit_host_seconds']
    assert len(times) == 3 and all(value >= 0 for value in times)
    assert repeated.costs['ard_fit_host_seconds'] == sum(times)
    assert repeated.costs['initialize_host_seconds'] >= repeated.costs['semantic_fit_host_seconds'] + \
        repeated.costs['joint_construction_host_seconds']+sum(times)
    assert 'host_seconds' not in json.dumps(initial_record(initialized))


def test_target_public_features_cannot_affect_training_likelihood_or_selected_parameters(initialized):
    other = [public('different', 'sub(in0,in1)', benchmark='unrelated:ctx', saved_cycles=2)]
    changed = a.initialize(training(), other)
    assert initial_record(changed) == initial_record(initialized)
    assert changed.posterior.snapshot()['public_pool_sha256'] != initialized.posterior.snapshot()['public_pool_sha256']


@pytest.mark.parametrize('kind', ['outer-label', 'nested-label', 'target-in-history', 'failed-history', 'duplicate-history'])
def test_train_only_boundaries_reject_leakage_and_invalid_history_before_any_estimator_fit(kind):
    rows, targets = training(), pool()
    if kind == 'outer-label':
        targets[0]['area_delta_lut4'] = 12
    elif kind == 'nested-label':
        targets[0]['latency_features']['hidden_area'] = 12
    elif kind == 'target-in-history':
        targets[0]['candidate_id'] = rows[0]['candidate_id']
    elif kind == 'failed-history':
        rows[0] = dict(**{key:rows[0][key] for key in b.PUBLIC_KEYS}, status='failed',
                       measurement_seconds=2., error='synthetic unknown')
    else:
        rows.append(copy.deepcopy(rows[0]))
    with patch.object(s.SemanticHardwareSurrogate, 'fit', side_effect=AssertionError('No fit before valid inputs')):
        with pytest.raises(ValueError):
            a.initialize(rows, targets)


def test_finite_nonconverged_starts_remain_eligible_and_all_warnings_preserved():
    actual = a.minimize
    def limited(*args, **kwargs):
        result = actual(*args, **kwargs)
        result.success, result.status, result.message = False, 1, 'synthetic iteration limit'
        warnings.warn('additional synthetic solver warning', RuntimeWarning)
        return result
    with patch.object(a, 'minimize', side_effect=limited):
        result = a.initialize(training(), pool())
    record = initial_record(result)
    assert record['nonconverged_start_indices'] == [0, 1, 2]
    assert record['selected_optimizer_converged'] is False
    assert result.costs['ard_scalar_gp_fits_completed'] == 3
    for attempt in record['optimizer_attempts']:
        assert attempt['eligible'] and attempt['optimizer_status'] == 1
        assert {'category':'RuntimeWarning', 'message':'additional synthetic solver warning'} in attempt['warnings']
        assert any(w['category'] == 'ConvergenceWarning' and 'did not converge' in w['message']
                   for w in attempt['warnings'])


def test_one_optimizer_exception_preserved_and_other_prespecified_starts_still_run():
    actual, calls = a.minimize, []
    def first_raises(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            warnings.warn('synthetic first-start warning', RuntimeWarning)
            raise ArithmeticError('synthetic first-start failure')
        return actual(*args, **kwargs)
    with patch.object(a, 'minimize', side_effect=first_raises):
        result = a.initialize(training(), pool())
    attempts = initial_record(result)['optimizer_attempts']
    assert len(calls) == 3 and [r['start_index'] for r in attempts] == [0, 1, 2]
    assert not attempts[0]['eligible'] and not attempts[0]['fit_completed']
    assert 'synthetic first-start failure' in attempts[0]['optimizer_exception']
    assert 'synthetic first-start failure' in attempts[0]['fit_exception']
    assert {'category':'RuntimeWarning', 'message':'synthetic first-start warning'} in attempts[0]['warnings']
    assert result.costs['ard_scalar_gp_fit_attempts'] == 3
    assert result.costs['ard_scalar_gp_fits_completed'] == 2
    assert initial_record(result)['selected_start_index'] in (1, 2)


@pytest.mark.parametrize('mode', ['nonfinite', 'exception'])
def test_all_unusable_starts_fail_with_complete_serializable_records_and_all_six_attempts_charged(mode):
    calls = []
    def bad(fun, theta, **kwargs):
        calls.append(True)
        if mode == 'exception':
            raise ArithmeticError('synthetic failure')
        return OptimizeResult(x=theta, fun=float('nan'), success=False, status=2,
                              message='synthetic nonfinite objective', nit=0, nfev=0, njev=0)
    with patch.object(a, 'minimize', side_effect=bad):
        with pytest.raises(a.ARDInitializationError) as caught:
            a.initialize(training(), pool())
    error = caught.value
    assert len(calls) == len(error.attempts) == 3
    assert all(not attempt['eligible'] for attempt in error.attempts)
    assert error.costs['total_scalar_gp_fit_attempts'] == 6
    assert error.costs['ard_scalar_gp_fit_attempts'] == 3
    assert error.costs['ard_scalar_gp_fits_completed'] == 0
    assert error.record['source_bindings'] == a.source_bindings()
    assert error.record['fit_accounting']['total_scalar_gp_fit_attempts'] == 6
    json.dumps(error.record, allow_nan=False)
    json.dumps(error.costs, allow_nan=False)


def _identical_minimum(fun, theta, *, bounds, **kwargs):
    chosen = np.zeros_like(theta)
    value, _ = fun(chosen)
    return OptimizeResult(x=chosen, fun=value, success=True, status=0, message='synthetic exact tie',
                          nit=1, nfev=1, njev=1)


def test_exact_objective_ties_select_earliest_prespecified_start():
    with patch.object(a, 'minimize', side_effect=_identical_minimum):
        result = a.initialize(training(), pool())
    record = initial_record(result)
    values = [r['negative_log_marginal_likelihood'] for r in record['optimizer_attempts']]
    assert values[0] == values[1] == values[2]
    assert record['selected_start_index'] == 0


def test_all_kernel_bound_hits_and_sklearn_bound_warnings_are_retained():
    def at_bounds(fun, theta, *, bounds, **kwargs):
        chosen = np.asarray(bounds)[:, 0].copy()
        value, _ = fun(chosen)
        return OptimizeResult(x=chosen, fun=value, success=True, status=0,
                              message='synthetic lower bounds', nit=1, nfev=1, njev=1)
    with patch.object(a, 'minimize', side_effect=at_bounds):
        result = a.initialize(training(), pool())
    for attempt in initial_record(result)['optimizer_attempts']:
        assert len(attempt['bound_hits']) == 38
        assert all(hit['side'] == 'lower' for hit in attempt['bound_hits'])
        assert {hit['dimension'] for hit in attempt['bound_hits'] if hit['parameter'] == 'length_scale'} == set(range(37))
        assert len(attempt['warnings']) >= 38


def test_caller_snapshots_and_costs_do_not_mutate_joint_state_or_frozen_sources(initialized):
    before = initialized.posterior.snapshot()
    hashes = {name:c.sha(a.ROOT/name) for name in j.SOURCES}
    snapshot = initialized.posterior.snapshot()
    snapshot['initial_snapshot']['optimizer_attempts'].clear()
    snapshot['initial_snapshot']['scaler']['mean'].clear()
    clone = initialized.posterior.clone()
    clone.joint()['outputs'][a.AREA]['mean'][:] = -1
    assert clone.snapshot() == initialized.posterior.snapshot() == before
    assert {name:c.sha(a.ROOT/name) for name in j.SOURCES} == hashes
    with pytest.raises(FrozenInstanceError):
        initialized.posterior = clone


def test_frozen_semantic_constructor_guard_remains_exact_and_unchanged():
    class Pretend(s.SemanticHardwareSurrogate):
        pass
    fitted = Pretend().fit(training())
    with pytest.raises(ValueError, match='Exact fitted'):
        j.JointHardwarePosterior.from_fitted(fitted, training(), pool())

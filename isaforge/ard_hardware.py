"""One train-only ARD area initializer for the fixed joint-update control.

This new procedure fits ConstantKernel*RBF on the same 37 semantic columns and
initial historical preprocessing. It is not an original SemanticHardwareSurrogate
fit or a faithful full-paper reproduction. Timing, log-duration and device state
are copied exactly from an authenticated semantic joint initialization. Every
paid update uses the unchanged fixed Gaussian conditioner. Alpha remains assumed
observation noise, not calibrated uncertainty. No target performance tunes this
initializer; source/family exclusions remain the caller's responsibility.

Private frozen coupling is deliberate: dataclasses.replace changes only the
joint state's _outputs['area_delta_lut4'], _initial_snapshot and _source_bindings.
The exact JointHardwarePosterior type/field contract and source hashes are bound;
none of its guards or update implementation is changed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, fields, is_dataclass, replace
import math
from pathlib import Path
import time
import warnings

import numpy as np
from scipy.optimize import minimize
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF

from . import codesign as c, semantic_selection as s, joint_hardware as j

SCHEMA = 'isaforge-ard-area-initializer-v1'
AREA = 'area_delta_lut4'
DIMENSIONS = 37
AMPLITUDE_BOUNDS = (.01, 100.)
LENGTH_SCALE_BOUNDS = (.1, 100.)
START_LENGTH_SCALES = (1., math.sqrt(DIMENSIONS), 10.)
OPTIMIZER_OPTIONS = dict(maxiter=200, maxfun=1000, ftol=1e-9, gtol=1e-5)
BOUND_HIT_ATOL = 1e-8
SETTINGS = dict(kernel='ConstantKernel * ARD RBF', dimensions=DIMENSIONS,
    amplitude_parameter='ConstantKernel.constant_value; normalized covariance variance multiplier',
    amplitude_bounds=list(AMPLITUDE_BOUNDS), length_scale_bounds=list(LENGTH_SCALE_BOUNDS),
    starts=[dict(amplitude=1., length_scales=[value]*DIMENSIONS) for value in START_LENGTH_SCALES],
    optimizer='scipy.optimize.minimize L-BFGS-B with analytic marginal-likelihood gradient',
    optimizer_options=copy.deepcopy(OPTIMIZER_OPTIONS), alpha=1e-4,
    normalize_y=False, output='area only; same initial semantic output center and scale',
    selection='lowest finite completed-fit negative historical log marginal likelihood; earliest exact tie',
    accept_nonconvergence='finite completed fits remain eligible; all statuses/warnings retained',
    failure='all three starts always attempted; no eligible finite fit raises ARDInitializationError',
    bound_hit_log_parameter_atol=BOUND_HIT_ATOL,
    post_optimizer_validation='one extra likelihood evaluation at the returned parameters; separately counted',
    target_usage='public prediction only; no target labels or target-conditioned optimization',
    private_joint_fields=['_outputs', '_initial_snapshot', '_source_bindings'])
SOURCES = ('isaforge/ard_hardware.py', 'docs/ard-area-experiment.md', *j.SOURCES)
ROOT = Path(__file__).resolve().parents[1]


def source_bindings():
    return {name: c.sha(ROOT/name) for name in SOURCES}


@dataclass(frozen=True)
class Initialization:
    posterior: j.JointHardwarePosterior
    costs: dict


class ARDInitializationError(ValueError):
    """No usable posterior; all attempted fits and raw cost receipts survive."""
    def __init__(self, record, costs):
        super().__init__('All three ARD starts lack an eligible finite fitted objective')
        self.record = copy.deepcopy(record)
        self.attempts = copy.deepcopy(record['optimizer_attempts'])
        self.costs = copy.deepcopy(costs)


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _bound_hits(theta, bounds):
    hits = []
    for index, (value, limits) in enumerate(zip(theta, bounds)):
        for side, limit in zip(('lower', 'upper'), limits):
            if abs(float(value)-float(limit)) <= BOUND_HIT_ATOL:
                hits.append(dict(parameter='amplitude' if index == 0 else 'length_scale',
                                 dimension=None if index == 0 else index-1, side=side))
    return hits


def _attempt(x, y, start_index, start_length):
    record = dict(start_index=start_index, initial_amplitude=1.,
        initial_length_scales=[start_length]*DIMENSIONS, fit_completed=False, eligible=False,
        optimizer_success=None, optimizer_status=None, optimizer_message=None, iterations=None,
        function_evaluations=None, gradient_evaluations=None, objective_calls=0, gradient_calls=0,
        post_optimizer_objective_evaluations=0, optimizer_reported_objective=None,
        negative_log_marginal_likelihood=None, objective_is_finite=False,
        optimized_log_parameters=None, selected_kernel=None, bound_hits=[],
        optimizer_exception=None, fit_exception=None, warnings=[])

    def optimizer(objective, initial_theta, bounds):
        def counted(theta):
            record['objective_calls'] += 1
            record['gradient_calls'] += 1
            return objective(theta, eval_gradient=True)
        try:
            result = minimize(counted, initial_theta, method='L-BFGS-B', jac=True,
                              bounds=bounds, options=copy.deepcopy(OPTIMIZER_OPTIONS))
            record.update(optimizer_success=bool(result.success), optimizer_status=int(result.status),
                optimizer_message=str(result.message), iterations=int(result.nit),
                function_evaluations=int(result.nfev), gradient_evaluations=int(result.njev),
                optimizer_reported_objective=_finite(result.fun))
            theta = np.asarray(result.x, dtype=float)
            c.require(theta.shape == initial_theta.shape and np.isfinite(theta).all() and
                      np.all(theta >= bounds[:, 0]-1e-12) and np.all(theta <= bounds[:, 1]+1e-12),
                      'Finite bounded optimized ARD parameters required')
            record['optimized_log_parameters'] = theta.tolist()
            record['bound_hits'] = _bound_hits(theta, bounds)
            # Validate actual historical likelihood rather than trusting a solver's
            # reported objective. This extra evaluation is accounted separately.
            record['objective_calls'] += 1
            record['post_optimizer_objective_evaluations'] += 1
            value = _finite(objective(theta, eval_gradient=False))
            record['negative_log_marginal_likelihood'] = value
            record['objective_is_finite'] = value is not None
            if not result.success:
                warnings.warn('ARD start '+str(start_index)+' did not converge: '+str(result.message),
                              ConvergenceWarning)
            c.require(value is not None and record['optimizer_reported_objective'] is not None,
                      'Finite optimizer and validated historical marginal likelihood required')
            return theta, value
        except Exception as error:
            record['optimizer_exception'] = repr(error)
            raise

    model = GaussianProcessRegressor(kernel=ConstantKernel(1., AMPLITUDE_BOUNDS)*
        RBF(np.full(DIMENSIONS, start_length), LENGTH_SCALE_BOUNDS),
        alpha=SETTINGS['alpha'], optimizer=optimizer, n_restarts_optimizer=0, normalize_y=False)
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        try:
            model.fit(x, y)
            c.require(np.isfinite(model.L_).all() and np.isfinite(model.alpha_).all() and
                      math.isfinite(model.log_marginal_likelihood_value_), 'Finite fitted ARD state required')
            record.update(fit_completed=True, eligible=True,
                selected_kernel=dict(amplitude=float(model.kernel_.k1.constant_value),
                                     length_scales=model.kernel_.k2.length_scale.tolist()))
        except Exception as error:
            record['fit_exception'] = repr(error)
            model = None
    elapsed = time.monotonic()-began
    record['warnings'] = [dict(category=item.category.__name__, message=str(item.message)) for item in captured]
    c.digest(record)  # Nonfinite solver states must never leak into a sealed proof.
    return model, record, elapsed


def initialize(training, public):
    """One semantic fit plus exactly three prespecified train-only ARD attempts.

    Returns Initialization(posterior, costs). Deterministic proof/optimizer records
    live in posterior.snapshot()['initial_snapshot']; raw host timers are separate
    in costs. All three starts run even if another raises or reaches a limit.
    """
    began_all = time.monotonic()
    training = copy.deepcopy(list(training))
    public = j._public(public)
    j.JointHardwarePosterior._validate_history(training, public)
    c.require(len(s.COLUMNS) == DIMENSIONS == 37,
              'Exact frozen 37-column semantic representation required')
    c.require(is_dataclass(j.JointHardwarePosterior) and j.JointHardwarePosterior.__dataclass_params__.frozen and
              set(SETTINGS['private_joint_fields']) <= {field.name for field in fields(j.JointHardwarePosterior)},
              'Frozen joint private replacement contract changed')
    began = time.monotonic()
    semantic = s.SemanticHardwareSurrogate().fit(training)
    semantic_seconds = time.monotonic()-began
    began = time.monotonic()
    base = j.JointHardwarePosterior.from_fitted(semantic, training, public)
    joint_seconds = time.monotonic()-began
    original = semantic.snapshot()
    initial_gp, center, scale = semantic.models[AREA]
    # Training arrays, centers and scales are the original semantic model's own
    # arrays. Neither target inputs nor labels enter the likelihood optimization.
    x, y = initial_gp.X_train_.copy(), initial_gp.y_train_.copy()
    models, attempts, seconds = [], [], []
    for index, start in enumerate(START_LENGTH_SCALES):
        model, record, elapsed = _attempt(x, y, index, start)
        models.append(model); attempts.append(record); seconds.append(elapsed)
    costs = dict(semantic_surrogate_fits=1, semantic_scalar_gp_fits=3,
        unused_original_semantic_area_scalar_fits=1, ard_scalar_gp_fit_attempts=3,
        ard_scalar_gp_fits_completed=sum(record['fit_completed'] for record in attempts),
        total_scalar_gp_fit_attempts=6, semantic_fit_host_seconds=semantic_seconds,
        joint_construction_host_seconds=joint_seconds, ard_start_fit_host_seconds=seconds,
        ard_fit_host_seconds=sum(seconds), initialize_host_seconds=time.monotonic()-began_all,
        scope='Semantic fit includes its unused area GP; three ARD starts each attempted once. '
              'Component timers overlap initialize_host_seconds; do not add the envelope twice.')
    record = dict(schema=SCHEMA, columns=list(s.COLUMNS), training_ids=list(original['training_ids']),
        training_rows_sha256=original['training_rows_sha256'],
        public_training_rows_sha256=original['public_training_rows_sha256'],
        feature_matrix_sha256=original['feature_matrix_sha256'],
        scaler=copy.deepcopy(original['scaler']), outputs=copy.deepcopy(original['outputs']),
        original_semantic_snapshot=copy.deepcopy(original), packages=copy.deepcopy(original['packages']),
        settings=copy.deepcopy(SETTINGS), optimizer_attempts=attempts,
        nonconverged_start_indices=[i for i, attempt in enumerate(attempts) if attempt['optimizer_success'] is not True],
        fit_accounting={key:costs[key] for key in ('semantic_surrogate_fits', 'semantic_scalar_gp_fits',
            'unused_original_semantic_area_scalar_fits', 'ard_scalar_gp_fit_attempts',
            'ard_scalar_gp_fits_completed', 'total_scalar_gp_fit_attempts')},
        noise_interpretation=j.NOISE_ASSUMPTION, update_rule=j.UPDATE_RULE,
        private_coupling='dataclasses.replace authenticated empty JointHardwarePosterior; '
                        '_outputs[area_delta_lut4], _initial_snapshot and _source_bindings only',
        source_bindings=source_bindings())
    eligible = [i for i, attempt in enumerate(attempts) if attempt['eligible'] and
                attempt['negative_log_marginal_likelihood'] is not None]
    if not eligible:
        raise ARDInitializationError(record, costs)
    selected = min(eligible, key=lambda i:(attempts[i]['negative_log_marginal_likelihood'], i))
    model = models[selected]
    target_x = semantic.scaler.transform(s.semantic_matrix(public))
    means, covariance = model.predict(target_x, return_cov=True)
    replacement = j._Output(j._array(means*scale+center), j._array(covariance*scale**2),
                            float(model.alpha)*scale**2)
    record.update(selected_start_index=selected, selected_kernel=copy.deepcopy(attempts[selected]['selected_kernel']),
        selected_optimizer_converged=attempts[selected]['optimizer_success'],
        selected_negative_log_marginal_likelihood=attempts[selected]['negative_log_marginal_likelihood'])
    numerical = dict(kernel=model.kernel_.get_params(), x_sha256=c.digest(model.X_train_.tolist()),
        y_sha256=c.digest(model.y_train_.tolist()), cholesky_sha256=c.digest(model.L_.tolist()),
        alpha_sha256=c.digest(model.alpha_.tolist()))
    # Kernel objects in get_params are not JSON; bind only explicit scalar/vector
    # parameters and exact numerical factors, as the declared kernel type is fixed.
    numerical['kernel'] = copy.deepcopy(record['selected_kernel'])
    record['model_state_sha256'] = c.digest(dict(provenance=record, numerical=numerical))
    outputs = dict(base._outputs); outputs[AREA] = replacement
    posterior = replace(base, _outputs=outputs, _initial_snapshot=record, _source_bindings=source_bindings())
    c.require(type(posterior) is j.JointHardwarePosterior and not posterior.observed_ids and
              not posterior.conditioned_ids, 'Exact unchanged empty joint state required')
    costs['initialize_host_seconds'] = time.monotonic()-began_all
    return Initialization(posterior, copy.deepcopy(costs))

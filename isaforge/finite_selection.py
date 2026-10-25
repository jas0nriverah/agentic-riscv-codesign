"""Finite-pool constrained selection with an explicit fixed posterior update.

Known calibrated cycle benefit, observed noisy hardware constraints, independent
area/timing GPs and a common Beta device-fit model are assumptions. Correctness
and infrastructure failures have no learned probability: real failures are still
charged and provide no fabricated Gaussian observations. This is a finite-pool
adaptation of constrained EI/two-step terminal utility, not a new BO algorithm.
"""
from __future__ import annotations

import copy
import importlib.metadata
import random
import statistics
import time

import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import qmc

from . import budgeted_selection as b, codesign as c
from . import joint_hardware as j

MYOPIC = 'fixed_joint_myopic'
LOOKAHEAD = 'fixed_joint_lookahead'
FALLBACK = 'fixed_joint_heuristic_fallback'
POLICIES = (MYOPIC, LOOKAHEAD, FALLBACK)
SETTINGS = dict(fantasy_draws=128, sobol_log2_draws=7, dimensions=2,
    scrambled=True, normal_clip=2**-53,
    utility='positive improvement in verified whole-program cycle reduction',
    update='fixed initial preprocessing and kernel; noisy-observation Gaussian conditioning',
    device='common Beta(1,1) fit rate updated on complete successful paid/fantasy flags',
    horizon='two-step receding horizon; exact myopic acquisition on final query',
    unknown_failure_probability='unmodeled; actual attempts charged without numerical update',
    tie='acquisition, immediate expected gain, analytic cycle reduction, seeded public order',
    fallback='only on final query with no improving verified feasible incumbent; original latency/cost tuple')
SOURCES = ('isaforge/finite_selection.py', *j.SOURCES)


def normal_draws(seed):
    c.require(type(seed) is int and seed >= 0, 'Nonnegative integer seed required')
    uniform = qmc.Sobol(d=2, scramble=True, seed=seed).random_base2(7)
    draws = ndtri(np.clip(uniform, SETTINGS['normal_clip'], 1-SETTINGS['normal_clip']))
    metadata = dict(seed=seed, settings=copy.deepcopy(SETTINGS),
        scipy_version=importlib.metadata.version('scipy'), normals_sha256=c.digest(draws.tolist()))
    return draws, metadata


def benefit(row):
    speedup = b._number(row['latency_features']['estimated_speedup'], 'analytic speedup', positive=True)
    return 1-1/speedup


def below(mean, variance, bound):
    """Gaussian marginal probability, including deterministic zero variance."""
    mean, variance = np.asarray(mean, float), np.asarray(variance, float)
    c.require(np.isfinite(mean).all() and np.isfinite(variance).all() and
              (variance >= 0).all(), 'Finite nonnegative observation variance required')
    std = np.sqrt(variance)
    z = np.divide(bound-mean, std, out=np.zeros(np.broadcast_shapes(mean.shape, std.shape)), where=std > 0)
    return np.where(std > 0, ndtr(z), (mean <= bound).astype(float))


def acquisition(state, public, *, incumbent, area_cap, clock_mhz, remaining_queries, draws):
    """All myopic/two-step action values without reading outcomes.

    Analytic immediate gain avoids Monte Carlo error in the first-query term.
    The second-query maximum is inside both Gaussian and device-flag branches.
    The vectorized conditional equations equal JointHardwarePosterior.fantasize;
    tests compare them against explicit immutable fantasy branches.
    """
    c.require(type(remaining_queries) is int and remaining_queries > 0, 'Positive remaining horizon required')
    c.require(0 <= incumbent < 1, 'Verified cycle-reduction incumbent required')
    public = list(public)
    c.require(public, 'Nonempty remaining pool required')
    draws = np.asarray(draws, float)
    c.require(draws.shape == (SETTINGS['fantasy_draws'], 2) and np.isfinite(draws).all(),
              'Exact declared finite normal table required')
    ids = [r['candidate_id'] for r in public]
    joint = state.joint(ids)
    c.require(joint['candidate_ids'] == ids, 'Ordered public/joint identities differ')
    outputs = [joint['outputs'][key] for key in ('area_delta_lut4', 'routed_fmax_min_mhz')]
    means = [np.asarray(o['mean'], float) for o in outputs]
    covariances = [np.asarray(o['covariance'], float) for o in outputs]
    noises = [float(o['observation_noise_variance']) for o in outputs]
    variances = [np.maximum(0., np.diag(o))+noise for o, noise in zip(covariances, noises)]
    gains = np.asarray([benefit(row) for row in public])
    alpha, beta = joint['device_fit_alpha'], joint['device_fit_beta']
    c.require(alpha > 0 and beta > 0, 'Positive Beta device-fit parameters required')
    device = alpha/(alpha+beta)
    marginal = below(means[0], variances[0], area_cap)*below(-means[1], variances[1], -clock_mhz)
    immediate = np.maximum(0., gains-incumbent)*marginal*device
    result = []
    for i, row in enumerate(public):
        future, fixed_future = 0., 0.
        if remaining_queries > 1 and len(public) > 1:
            others = [k for k in range(len(public)) if k != i]
            observed = [mean[i]+np.sqrt(var[i])*draws[:, k]
                        for k, (mean, var) in enumerate(zip(means, variances))]
            probabilities = []
            for k, (mean, covariance, noise) in enumerate(zip(means, covariances, noises)):
                denominator = variances[k][i]
                cross = covariance[others, i]
                if denominator > 0:
                    conditional_mean = mean[others][None, :]+(
                        observed[k]-mean[i])[:, None]*cross[None, :]/denominator
                    conditional_variance = np.maximum(0., np.diag(covariance)[others]-cross**2/denominator)+noise
                else:
                    c.require(np.all(cross == 0), 'Zero-variance point has nonzero cross covariance')
                    conditional_mean = np.broadcast_to(mean[others], (len(draws), len(others)))
                    conditional_variance = np.diag(covariance)[others]+noise
                probabilities.append(below(conditional_mean if k == 0 else -conditional_mean,
                    conditional_variance, area_cap if k == 0 else -clock_mhz))
            remaining_feasibility = probabilities[0]*probabilities[1]
            first_numeric_feasible = (observed[0] <= area_cap) & (observed[1] >= clock_mhz)
            success_incumbent = np.where(first_numeric_feasible, max(incumbent, gains[i]), incumbent)
            q_success, q_failure = (alpha+1)/(alpha+beta+1), alpha/(alpha+beta+1)
            success_gain = np.maximum(0., gains[others][None, :]-success_incumbent[:, None])
            failure_gain = np.maximum(0., gains[others]-incumbent)[None, :]
            success_future = success_gain*remaining_feasibility*q_success
            failure_future = failure_gain*remaining_feasibility*q_failure
            future = float(np.mean(device*success_future.max(axis=1)+(1-device)*failure_future.max(axis=1)))
            fixed_future = float(np.max(np.mean(device*success_future+(1-device)*failure_future, axis=0)))
        result.append(dict(candidate_id=row['candidate_id'], analytic_cycle_reduction=float(gains[i]),
            modeled_observation_feasibility_probability=float(marginal[i]*device),
            immediate_expected_gain=float(immediate[i]), expected_adaptive_second_gain=future,
            expected_fixed_second_gain=fixed_future,
            estimated_second_adaptation_value=max(0., future-fixed_future),
            two_step_expected_gain=float(immediate[i])+future))
    c.digest(result)
    return result


def search(public, training, provider, *, posterior, policy, area_cap, clock_mhz=12.,
           seed, budget, on_acquire=None):
    """Bounded charged search; only provider can release a target observation."""
    c.require(policy in POLICIES, 'Unknown finite selection policy')
    public = b.public_rows(public)
    c.require(type(budget) is int and 0 < budget <= len(public), 'Valid planned budget required')
    c.require(type(seed) is int and seed >= 0, 'Nonnegative integer seed required')
    c.require(b._number(area_cap, 'area cap') >= 0, 'Nonnegative area cap required')
    b._number(clock_mhz, 'clock MHz', positive=True)
    training = copy.deepcopy(list(training))
    c.require(training and all(b.validate_outcome(row) for row in training), 'Verified measured history required')
    initial = posterior.snapshot()
    c.require(not initial['hypothetical'] and not initial['paid_ids'] and
        initial['candidate_ids'] == [r['candidate_id'] for r in public] and
        initial['public_pool_sha256'] == c.digest(public) and
        initial['initial_snapshot']['training_rows_sha256'] == c.digest(training),
        'Exact unpaid initial posterior/history/public pool required')
    c.require(on_acquire is None or callable(on_acquire), 'Callable acquisition observer required')
    state = posterior.clone()
    ordered = copy.deepcopy(public)
    random.Random(seed).shuffle(ordered)
    draws, table = normal_draws(seed)
    per_op = statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in training)
    simple_clock = min(r['routed_fmax_min_mhz'] for r in training)
    attempts, observations, events, proofs, curve = [], [], [], [], []
    acquisition_seconds, conditioning_seconds = 0., 0.
    while len(attempts) < budget:
        feasible = [r for r in observations if b._feasible(r, area_cap, clock_mhz) and r['speedup'] > 1]
        incumbent_speedup = max([1.]+[r['speedup'] for r in feasible])
        incumbent = 1-1/incumbent_speedup
        remaining = budget-len(attempts)
        began = time.monotonic()
        values = acquisition(state, ordered, incumbent=incumbent, area_cap=area_cap,
            clock_mhz=clock_mhz, remaining_queries=remaining if policy == LOOKAHEAD else 1, draws=draws)
        by_id = {r['candidate_id']: r for r in values}
        fallback = policy == FALLBACK and remaining == 1 and incumbent == 0
        def score(row):
            value = by_id[row['candidate_id']]
            if fallback:
                area = per_op*row['tree_op_count']
                return (int(area <= area_cap and simple_clock >= clock_mhz),
                    max(0., row['latency_features']['estimated_speedup']-incumbent_speedup)/max(1., area),
                    row['latency_features']['estimated_speedup'])
            return (value['two_step_expected_gain'] if policy == LOOKAHEAD else value['immediate_expected_gain'],
                value['immediate_expected_gain'], value['analytic_cycle_reduction'])
        chosen = max(ordered, key=score)
        acquisition_seconds += time.monotonic()-began
        snapshot = state.snapshot()
        event = dict(action='acquire', policy=policy, candidate_id=chosen['candidate_id'],
            planned_budget=budget, remaining_queries=remaining, charged_before_query=len(attempts),
            attempted_ids_before_query=list(attempts), paid_target_ids_before_query=list(state.observed_ids),
            incumbent_verified_cycle_reduction=incumbent, fallback_used=fallback,
            score=list(score(chosen)), action_values=values,
            posterior_state_sha256=snapshot['posterior_state_sha256'], fantasy_table_sha256=table['normals_sha256'])
        proof = dict(event=copy.deepcopy(event), posterior_snapshot=snapshot,
            snapshot_sha256=c.digest(snapshot), initial_training_ids=initial['initial_training_ids'],
            successful_paid_ids=list(state.observed_ids), fantasy_table=table)
        c.digest(proof)
        if on_acquire is not None:
            on_acquire(copy.deepcopy(proof))
        events.append(event)
        proofs.append(proof)
        attempts.append(chosen['candidate_id'])  # Charge BEFORE dispatch; no retry.
        try:
            outcome = copy.deepcopy(provider(copy.deepcopy(chosen)))
            success = b.validate_outcome(outcome, chosen)
        except BaseException as error:
            events.append(dict(action='measure-exception', candidate_id=chosen['candidate_id'],
                charged=len(attempts), error=repr(error)))
            raise
        residual = (outcome['baseline_cycles']-outcome['candidate_cycles']-
            chosen['latency_features']['estimated_saved_cycles']) if success else None
        events.append(dict(action='measure-complete' if success else 'measure-failed',
            candidate_id=chosen['candidate_id'], charged=len(attempts), observation=outcome,
            measured_minus_calibrated_saved_cycles=residual,
            calibrated_benefit_assumption_violated=residual is not None and residual != 0))
        if success:
            observations.append(outcome)
            began = time.monotonic()
            state = state.condition(outcome, queried_id=chosen['candidate_id'])
            conditioning_seconds += time.monotonic()-began
        ordered = [r for r in ordered if r['candidate_id'] != chosen['candidate_id']]
        feasible = [r for r in observations if b._feasible(r, area_cap, clock_mhz) and r['speedup'] > 1]
        best = min(feasible, key=lambda r: (-r['speedup'], r['area_delta_lut4'], r['candidate_id'])) if feasible else None
        curve.append(dict(budget=len(attempts), planned_budget=budget,
            best_speedup=best['speedup'] if best else 1., selected_id=best['candidate_id'] if best else None,
            attempted_ids=list(attempts), measured_ids=[r['candidate_id'] for r in observations],
            failed_attempts=len(attempts)-len(observations),
            target_measurement_seconds=sum(e['observation']['measurement_seconds'] for e in events if 'observation' in e),
            inference_seconds=acquisition_seconds+conditioning_seconds))
    return dict(policy=policy, planned_budget=budget, curve=curve, events=events,
        acquisition_proofs=proofs, initial_posterior_state_sha256=initial['posterior_state_sha256'],
        final_posterior_snapshot=state.snapshot(), fantasy_table=table,
        acquisition_host_seconds=acquisition_seconds, conditioning_host_seconds=conditioning_seconds,
        initial_model_fits_in_search=0, conditional_updates=len(observations),
        calibrated_benefit_assumption_violations=sum(
            bool(e.get('calibrated_benefit_assumption_violated')) for e in events))

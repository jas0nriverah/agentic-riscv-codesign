"""Fixed, bounded single-instruction comparison with paid target observations.

The latency anchor is independently calibrated, not learned from target labels.
Hardware GPs model integrated LUT increments, routed timing and query duration.
Their independent Gaussian probabilities are assumptions, not calibrated claims.
This interface isolates cooperative replay; it is not an external-agent sandbox.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import math
from pathlib import Path
import random
import statistics
import time

from . import codesign as c
from .features import FEATURE_COLUMNS
from .model import SpeedupPredictor, _number, feature_matrix, validate_training_rows
from .prospective_selection import PUBLIC_KEYS, EXECUTION_COLUMNS
from .ranking import SpeedupRanker
from .speedup_corpus import family

POLICIES = ('frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic',
            'random', 'raw_regression', 'ranking', 'normalized_xgb',
            'hybrid_gp_zero_shot', 'hybrid_gp_adapt')
STRUCTURAL_COLUMNS = tuple(k for k in FEATURE_COLUMNS
                           if k not in ('runs', 'places', 'saved', 'saved_percent'))
LATENCY_KEYS = ('baseline_cycles', 'baseline_instructions', 'baseline_cpi',
                'replacement_execution_fraction', 'occurrence_size_min',
                'occurrence_size_max', 'dynamic_software_cycles',
                'dynamic_custom_cycles', 'dynamic_shift_extra_cycles',
                'estimated_saved_cycles', 'estimated_cycle_reduction', 'estimated_speedup',
                'region_custom_instructions')
SOURCES = ('isaforge/budgeted_selection.py', 'isaforge/model.py', 'isaforge/ranking.py',
           'isaforge/features.py', 'isaforge/prospective_selection.py',
           'isaforge/speedup_corpus.py', 'isaforge/codesign.py')
GP_SETTINGS = dict(kernel='isotropic Matern nu=1.5', length_scale=1.0,
                   optimizer=None, alpha=1e-4, standardize_inputs=True,
                   output_scale_floors=dict(area_delta_lut4=8.0,
                       routed_fmax_min_mhz=1.0, log_measurement_seconds=.25))


def occurrence_count(row):
    """Exact timed-region replacements, never the measured whole-program counter.

    The baseline discovery count is preferred. Historical latency archives can
    recover it exactly from dynamic custom cycles and the independently measured
    five-cycle PCPI latency; the fraction is only a consistency check.
    """
    values = row['latency_features']
    total = _number(values['baseline_instructions'], 'baseline instructions', positive=True)
    fraction = _number(values['replacement_execution_fraction'], 'replacement fraction', positive=True)
    cycles = values['dynamic_custom_cycles']
    c.require(type(cycles) is int and cycles > 0 and cycles % 5 == 0, 'Invalid calibrated dynamic custom cycles')
    count = values.get('region_custom_instructions', cycles//5)
    c.require(type(count) is int and count > 0 and count*5 == cycles,
              'Exact discovery replacement count differs from calibrated latency')
    c.require(math.isclose(count, total*fraction, rel_tol=1e-12, abs_tol=1e-7),
              'Replacement execution fraction differs')
    c.require(count == row['runs'], 'Latency/public occurrence counts differ')
    return count


def public_rows(rows):
    """Reject target labels, including labels hidden inside nested features."""
    c.require(rows and len({r['candidate_id'] for r in rows}) == len(rows), 'Unique nonempty public pool required')
    result = []
    for row in rows:
        c.require(set(row) == set(PUBLIC_KEYS), 'Public input has missing or non-public fields')
        values = row['latency_features']
        c.require(set(values) <= set(LATENCY_KEYS), 'Non-public latency feature')
        for key in (*EXECUTION_COLUMNS, 'baseline_cycles', 'baseline_instructions', 'estimated_speedup'):
            _number(values[key], key)
        c.require(_number(values['baseline_cycles'], 'baseline cycles', positive=True) > 0, 'Invalid baseline')
        c.require(_number(values['estimated_speedup'], 'analytic speedup', positive=True) > 0, 'Invalid analytic speedup')
        family(row['formula']); occurrence_count(row)
        c.require(isinstance(row['benchmark'], str) and row['benchmark'], 'Explicit benchmark required')
        result.append(copy.deepcopy(row))
    feature_matrix(result)
    return result


def structural_matrix(rows):
    return [[_number(r[k], k) for k in STRUCTURAL_COLUMNS] for r in rows]


class NormalizedSpeedupPredictor:
    """One direct target transform: saved cycles per executed replacement.

    Signed labels retain slowdowns. Fixed XGBoost settings match the raw
    comparator. The physical minimum denominator is one whole-program cycle;
    any prediction requiring that floor is disclosed, not silently called valid.
    """
    def __init__(self, seed=0):
        c.require(type(seed) is int and seed >= 0, 'Invalid model seed')
        self.seed, self.models, self.constant = seed, None, None

    def fit(self, rows):
        import numpy as np
        from xgboost import XGBRegressor
        validate_training_rows(rows)
        x = np.asarray(structural_matrix(rows), dtype=float)
        labels = []
        for row in rows:
            baseline = _number(row['baseline_cycles'], 'baseline cycles', positive=True)
            candidate = _number(row['candidate_cycles'], 'candidate cycles', positive=True)
            c.require(baseline == row['latency_features']['baseline_cycles'], 'Training baseline differs')
            c.require(math.isclose(baseline/candidate, row['speedup'], rel_tol=1e-12), 'Cycle/speedup label differs')
            labels.append((baseline-candidate)/occurrence_count(row))
        y = np.asarray(labels, dtype=float)
        self.models = []
        if np.all(y == y[0]):
            self.constant = float(y[0])
        else:
            self.constant = None
            rng = np.random.default_rng(self.seed)
            for _ in range(20):
                indices = rng.integers(0, len(rows), size=len(rows))
                model = XGBRegressor(objective='reg:squarederror', n_estimators=80,
                    max_depth=2, learning_rate=.05, min_child_weight=1, reg_lambda=1.0,
                    subsample=1.0, colsample_bytree=1.0, tree_method='hist', n_jobs=1,
                    random_state=int(rng.integers(0, 2**31-1)), verbosity=0)
                model.fit(x[indices], y[indices]); self.models.append(model)
        return self

    def predict(self, rows):
        import numpy as np
        c.require(self.models is not None, 'Fit normalized model first')
        if not rows: return []
        x = structural_matrix(rows)
        samples = (np.full((20, len(rows)), self.constant) if self.constant is not None
                   else np.stack([m.predict(x) for m in self.models]))
        c.require(np.isfinite(samples).all(), 'Nonfinite normalized prediction')
        result = []
        for i, row in enumerate(rows):
            baseline = row['latency_features']['baseline_cycles']
            denominator = baseline - samples[:, i]*occurrence_count(row)
            speedups = baseline / np.maximum(1.0, denominator)
            low, high = np.quantile(speedups, [.05, .95])
            result.append(dict(candidate_id=row['candidate_id'], mean=float(speedups.mean()),
                lower=float(low), upper=float(high), std=float(speedups.std()),
                saved_cycles_per_occurrence_mean=float(samples[:, i].mean()),
                one_cycle_floor_members=int((denominator < 1).sum())))
        return result


def validate_outcome(row, public=None):
    if public is not None:
        c.require(all(row[k] == public[k] for k in PUBLIC_KEYS), 'Outcome/public identity differs')
    _number(row['measurement_seconds'], 'measurement seconds', positive=True)
    status = row.get('status', 'success')
    c.require(status in ('success', 'failed'), 'Unknown measurement status')
    if status == 'failed':
        c.require(isinstance(row.get('error'), str) and row['error'], 'Failure needs a reason')
        c.require(not any(k in row for k in ('speedup', 'candidate_cycles', 'area_delta_lut4',
                    'routed_fmax_min_mhz')), 'Failed attempt must not include successful labels')
        return False
    _number(row['speedup'], 'speedup', positive=True)
    _number(row['baseline_cycles'], 'baseline cycles', positive=True)
    _number(row['candidate_cycles'], 'candidate cycles', positive=True)
    c.require(row['baseline_cycles'] == row['latency_features']['baseline_cycles'], 'Baseline differs')
    c.require(math.isclose(row['baseline_cycles']/row['candidate_cycles'], row['speedup'], rel_tol=1e-12),
              'Speedup does not match measured cycles')
    _number(row['area_delta_lut4'], 'integrated area increment')
    _number(row['routed_fmax_min_mhz'], 'routed minimum Fmax', positive=True)
    c.require(type(row['device_fits']) is bool and row.get('correctness_verified') is True,
              'Measured device fit and verified correctness required')
    return True


class HardwareSurrogate:
    """Fixed independent GPs. They are neither calibrated nor fitted to test labels."""
    def fit(self, rows):
        import numpy as np
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import Matern
        from sklearn.preprocessing import StandardScaler
        c.require(rows, 'Hardware surrogate needs paid history')
        self.scaler = StandardScaler().fit(structural_matrix(rows))
        x = self.scaler.transform(structural_matrix(rows))
        self.models = {}
        for key, floor in GP_SETTINGS['output_scale_floors'].items():
            y = np.asarray([math.log(r['measurement_seconds']) if key == 'log_measurement_seconds'
                            else r[key] for r in rows], dtype=float)
            center, scale = float(y.mean()), max(float(y.std()), floor)
            model = GaussianProcessRegressor(kernel=Matern(length_scale=1.0,
                length_scale_bounds='fixed', nu=1.5), alpha=1e-4, optimizer=None,
                normalize_y=False)
            model.fit(x, (y-center)/scale)
            self.models[key] = model, center, scale
        # No candidate-specific device-fit model is supported by this tiny corpus.
        # A common smoothed rate cancels in rankings, but remains visible.
        self.device_fit_probability = (1+sum(r['device_fits'] for r in rows))/(len(rows)+2)
        return self

    def predict(self, rows):
        if not rows: return []
        x = self.scaler.transform(structural_matrix(rows))
        values = {}
        for key, (model, center, scale) in self.models.items():
            means, stds = model.predict(x, return_std=True)
            values[key] = (means*scale+center, stds*scale)
        result = []
        for i, row in enumerate(rows):
            item = dict(candidate_id=row['candidate_id'], device_fit_probability=self.device_fit_probability)
            for key, (means, stds) in values.items():
                item[key+'_mean'], item[key+'_std'] = float(means[i]), float(stds[i])
            result.append(item)
        return result


def _cdf(value):
    return .5*math.erfc(-value/math.sqrt(2))


def _probability_below(mean, std, bound):
    return float(mean <= bound) if std <= 1e-12 else _cdf((bound-mean)/std)


def hybrid_score(row, estimate, incumbent, area_cap, clock_mhz):
    """Analytic improvement × independent feasibility × expected inverse time."""
    gain = max(0.0, row['latency_features']['estimated_speedup']-incumbent)
    area = _probability_below(estimate['area_delta_lut4_mean'], estimate['area_delta_lut4_std'], area_cap)
    timing = _probability_below(-estimate['routed_fmax_min_mhz_mean'],
                              estimate['routed_fmax_min_mhz_std'], -clock_mhz)
    # Clamping the exponent protects finite floating-point arithmetic; it is fixed.
    inverse_time = math.exp(max(-700, min(700, -estimate['log_measurement_seconds_mean']
                                       + .5*estimate['log_measurement_seconds_std']**2)))
    return gain*area*timing*estimate['device_fit_probability']*inverse_time


def zero_shot(training, public, seed):
    began = time.monotonic()
    raw = SpeedupPredictor(seed=seed).fit(training).predict(public)
    raw_seconds = time.monotonic()-began
    began = time.monotonic()
    ranking = SpeedupRanker(seed=seed).fit(training).predict(public)
    ranking_seconds = time.monotonic()-began
    began = time.monotonic()
    normalized = NormalizedSpeedupPredictor(seed).fit(training).predict(public)
    normalized_seconds = time.monotonic()-began
    began = time.monotonic()
    hardware = HardwareSurrogate().fit(training).predict(public)
    hardware_seconds = time.monotonic()-began
    return dict(seed=seed, raw=raw, ranking=ranking, normalized=normalized, hardware=hardware,
        inference_seconds=dict(raw_regression=raw_seconds, ranking=ranking_seconds,
            normalized_xgb=normalized_seconds, hybrid_gp_zero_shot=hardware_seconds,
            hybrid_gp_adapt=hardware_seconds))


def _feasible(row, area_cap, clock_mhz):
    return (row.get('status', 'success') == 'success' and row['device_fits']
            and row['area_delta_lut4'] <= area_cap and row['routed_fmax_min_mhz'] >= clock_mhz)


def search(public, training, provider, *, area_cap, clock_mhz, policy, seed, budget, predictions):
    """Provider is the only target-label access; failures consume queries and time."""
    c.require(policy in POLICIES, 'Unknown policy')
    public = public_rows(public)
    c.require(type(budget) is int and 0 < budget <= len(public), 'Invalid query budget')
    c.require(type(seed) is int and seed >= 0, 'Invalid seed')
    c.require(_number(area_cap, 'area cap') >= 0, 'Negative area cap')
    _number(clock_mhz, 'clock MHz', positive=True)
    ordered = copy.deepcopy(public); random.Random(seed).shuffle(ordered)
    fixed = {key: {p['candidate_id']: p for p in predictions[key]}
             for key in ('raw', 'ranking', 'normalized', 'hardware')}
    area_per_op = statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in training)
    simple_clock = min(r['routed_fmax_min_mhz'] for r in training)
    observations, attempts, events, curve = [], [], [], []
    inference = predictions['inference_seconds'].get(policy, 0.0)
    while len(attempts) < budget:
        feasible = [r for r in observations if _feasible(r, area_cap, clock_mhz) and r['speedup'] > 1]
        incumbent = max([1.0]+[r['speedup'] for r in feasible])
        estimates = fixed['hardware']
        if policy == 'hybrid_gp_adapt' and observations:
            began = time.monotonic()
            values = HardwareSurrogate().fit(training+observations).predict(ordered)
            inference += time.monotonic()-began
            estimates = {v['candidate_id']: v for v in values}
        def score(row):
            identity = row['candidate_id']; analytic = row['latency_features']['estimated_speedup']
            if policy == 'frequency': return (row['runs'],)
            if policy == 'merit': return (row['saved'],)
            if policy == 'calibrated_latency': return (analytic,)
            if policy == 'latency_cost_heuristic':
                area = area_per_op*row['tree_op_count']
                # Hard feasibility first, then analytic improvement per proxy LUT.
                return (int(area <= area_cap and simple_clock >= clock_mhz),
                        max(0.0, analytic-incumbent)/max(1.0, area), analytic)
            if policy == 'raw_regression': return (fixed['raw'][identity]['mean'],)
            if policy == 'ranking': return (fixed['ranking'][identity]['rank_score'],)
            if policy == 'normalized_xgb': return (fixed['normalized'][identity]['mean'],)
            if policy.startswith('hybrid_gp'):
                return (hybrid_score(row, estimates[identity], incumbent, area_cap, clock_mhz), analytic)
            return (0,)
        chosen = max(ordered, key=score)
        events.append(dict(action='acquire', candidate_id=chosen['candidate_id'], policy=policy,
            charged_before_query=len(attempts), paid_target_ids_before_query=[r['candidate_id'] for r in observations],
            score=score(chosen), hardware_predictions=list(estimates.values()) if policy.startswith('hybrid_gp') else []))
        # Charge before calling provider. A raised exception is recorded and the
        # comparison stops because its elapsed native cost is unknown; it is not free.
        attempts.append(chosen['candidate_id'])
        try:
            outcome = copy.deepcopy(provider(copy.deepcopy(chosen)))
            success = validate_outcome(outcome, chosen)
        except BaseException as error:
            events.append(dict(action='measure-exception', candidate_id=chosen['candidate_id'],
                               charged=len(attempts), error=repr(error)))
            raise
        events.append(dict(action='measure-complete' if success else 'measure-failed',
                           candidate_id=chosen['candidate_id'], charged=len(attempts), observation=outcome))
        if success: observations.append(outcome)
        ordered = [r for r in ordered if r['candidate_id'] != chosen['candidate_id']]
        feasible = [r for r in observations if _feasible(r, area_cap, clock_mhz) and r['speedup'] > 1]
        best = min(feasible, key=lambda r: (-r['speedup'], r['area_delta_lut4'], r['candidate_id'])) if feasible else None
        seconds = sum(e['observation']['measurement_seconds'] for e in events if 'observation' in e)
        curve.append(dict(budget=len(attempts), best_speedup=best['speedup'] if best else 1.0,
            selected_id=best['candidate_id'] if best else None, attempted_ids=list(attempts),
            measured_ids=[r['candidate_id'] for r in observations],
            failed_attempts=len(attempts)-len(observations), target_measurement_seconds=seconds,
            inference_seconds=inference))
    return dict(curve=curve, events=events)


def freeze(history, target, contexts, output, *, target_workload, calibration_cost_seconds,
           cost_provenance=None, area_caps=(32, 64, 128), clock_mhz=12.0,
           seeds=(0, 1, 2, 3, 4), budgets=(1, 2, 3), scope='prospective'):
    output = Path(output)
    c.require(not output.exists(), 'Use a fresh comparison directory')
    public = public_rows(target)
    c.require(len({r['benchmark'] for r in public}) == 1, 'One target context required')
    c.require(isinstance(target_workload, str) and target_workload, 'Target workload required')
    c.require(scope in ('prospective', 'consumed-data development'), 'Explicit experiment scope required')
    c.require(all(type(v) is int and v >= 0 for v in seeds) and seeds and len(set(seeds)) == len(seeds), 'Invalid seeds')
    c.require(all(type(v) is int and 0 < v <= len(public) for v in budgets) and budgets and len(set(budgets)) == len(budgets), 'Invalid budgets')
    c.require(area_caps and len(set(area_caps)) == len(area_caps) and all(_number(v,'cap') >= 0 for v in area_caps), 'Invalid caps')
    _number(clock_mhz, 'clock MHz', positive=True)
    c.require(_number(calibration_cost_seconds, 'calibration seconds') >= 0, 'Negative calibration cost')
    validate_training_rows(history)
    c.require(len({r['workload_group'] for r in history}) >= 2, 'Independent historical workload groups required')
    c.require(all(r['workload_group'] != target_workload and r['benchmark'] != public[0]['benchmark'] for r in history), 'Target in history')
    for row in history: validate_outcome(row)
    c.require({r['benchmark'] for r in history+public} <= set(contexts), 'Explicit provenance contexts required')
    target_families = {family(r['formula']) for r in public}
    training = [copy.deepcopy(r) for r in history if family(r['formula']) not in target_families]
    c.require(len(training) >= 2, 'Insufficient unrelated historical labels')
    predictions = [zero_shot(training, public, seed) for seed in seeds]
    protocol = dict(schema='isaforge-budgeted-selection-v1', scope=scope, target_workload=target_workload,
        target_labels_read=0, seeds=list(seeds), budgets=list(budgets), area_caps=list(area_caps),
        clock_mhz=clock_mhz, primary_endpoint=dict(area_delta_lut4=64, budget=3, clock_mhz=12.0),
        policies=list(POLICIES), historical_available_rows=len(history), historical_fit_rows=len(training),
        historical_training_ids=[r['candidate_id'] for r in training],
        excluded_related_ids=[r['candidate_id'] for r in history if family(r['formula']) in target_families],
        historical_candidate_wall_seconds=sum(r['measurement_seconds'] for r in history),
        calibration_command_seconds=calibration_cost_seconds, cost_provenance=cost_provenance or {},
        contexts=contexts, gp_settings=GP_SETTINGS, normalized_features=list(STRUCTURAL_COLUMNS),
        normalized_target='(baseline_cycles-candidate_cycles)/region_custom_instructions; exact baseline discovery count or dynamic_custom_cycles/independently calibrated 5; count must equal public runs',
        normalized_xgb=dict(ensemble_size=20, n_estimators=80, max_depth=2, learning_rate=.05,
            objective='reg:squarederror', bootstrap='n rows with replacement', reconstruction_floor_cycles=1),
        simple_cost='median historical deltaLUT/tree_op_count times tree_op_count; minimum historical routed Fmax; hard feasibility then analytic improvement/proxyLUT',
        acquisition='positive analytic speedup improvement × independent Gaussian P(area) × P(clock) × smoothed global device-fit rate × E[1/duration]',
        source_bindings={p:c.sha(c.ROOT/p) for p in SOURCES},
        packages={p:importlib.metadata.version(p) for p in ('numpy','scipy','xgboost','scikit-learn')},
        limitations=['GP probabilities and bootstrap intervals are not calibrated confidence.',
            'Area, timing, device fit and duration independence is an approximation.',
            'No candidate-specific device-fit model; a smoothed global rate is reported.',
            'Five model/tie seeds are dependent repetitions, not independent workloads.',
            'No cross-target adaptation; only this target paid successes update its hardware model.',
            'Single instructions only; combined sets require joint measurement.',
            'Offline replay is cooperative isolation, not an external-agent security boundary.',
            'All policies receive the same historical data; report shared-history and target-only costs separately.',
            'Historical candidate wall, baseline/setup command time, calibration and inference are separate timer scopes.'])
    output.mkdir(parents=True)
    for name, value in (('public.json',public),('history.json',training),('predictions.json',predictions)):
        c.seal(output/name, value)
    protocol['artifacts'] = {n:c.sha(output/n) for n in ('public.json','history.json','predictions.json')}
    c.seal(output/'protocol.json', protocol)
    return protocol


def stable(value):
    if isinstance(value, (list, tuple)): return [stable(v) for v in value]
    if isinstance(value, dict): return {k:stable(v) for k,v in value.items() if k != 'inference_seconds'}
    return value


def evaluate(root, outcomes, *, verify=False):
    """Privileged scorer owns complete outcomes; policies only see paid releases."""
    root = Path(root); protocol = c.unseal(root/'protocol.json')
    for name, expected in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == expected, 'Frozen source changed: '+name)
    for name, expected in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == expected, 'Frozen dependency changed: '+name)
    for name, expected in protocol['artifacts'].items():
        c.require(c.sha(root/name) == expected, 'Frozen artifact changed: '+name)
    c.require(verify or not (root/'report.json').exists(), 'Preserve prior report')
    public, training = c.unseal(root/'public.json'), c.unseal(root/'history.json')
    predictions = c.unseal(root/'predictions.json')
    labels = {r['candidate_id']:r for r in outcomes}
    c.require(len(labels) == len(outcomes) and set(labels) == {r['candidate_id'] for r in public}, 'Complete attempted oracle pool required')
    for row in public: validate_outcome(labels[row['candidate_id']], row)
    runs, diagnostics, oracles = [], [], []
    for cap in protocol['area_caps']:
        feasible = [r for r in outcomes if _feasible(r, cap, protocol['clock_mhz'])]
        oracle = max([1.0]+[r['speedup'] for r in feasible])
        oracles.append(dict(area_delta_lut4_cap=cap, speedup=oracle,
            feasible_candidates=len(feasible), oracle_attempts=len(outcomes),
            oracle_candidate_wall_seconds=sum(r['measurement_seconds'] for r in outcomes)))
        for prediction in predictions:
            for policy in protocol['policies']:
                result = search(public, training, lambda r:copy.deepcopy(labels[r['candidate_id']]),
                    area_cap=cap, clock_mhz=protocol['clock_mhz'], policy=policy,
                    seed=prediction['seed'], budget=max(protocol['budgets']), predictions=prediction)
                for point in result['curve']:
                    point.update(regret=oracle-point['best_speedup'],
                        historical_available_labels=protocol['historical_available_rows'],
                        historical_candidate_wall_seconds=protocol['historical_candidate_wall_seconds'],
                        history_plus_target_candidate_wall_seconds=protocol['historical_candidate_wall_seconds']+point['target_measurement_seconds'])
                result['curve'] = [p for p in result['curve'] if p['budget'] in protocol['budgets']]
                runs.append(dict(policy=policy, seed=prediction['seed'], area_delta_lut4_cap=cap, **result))
    successful = {k:v for k,v in labels.items() if v.get('status','success') == 'success'}
    for prediction in predictions:
        for key in ('raw','normalized'):
            values = [v for v in prediction[key] if v['candidate_id'] in successful]
            diagnostics.append(dict(seed=prediction['seed'], model=key,
                mae=statistics.mean(abs(v['mean']-successful[v['candidate_id']]['speedup']) for v in values) if values else None,
                interval_coverage=statistics.mean(v['lower'] <= successful[v['candidate_id']]['speedup'] <= v['upper'] for v in values) if values else None,
                one_cycle_floor_members=sum(v.get('one_cycle_floor_members',0) for v in values),
                calibrated_confidence=False))
        hardware = [v for v in prediction['hardware'] if v['candidate_id'] in successful]
        if hardware:
            errors = {}
            for key in ('area_delta_lut4', 'routed_fmax_min_mhz', 'log_measurement_seconds'):
                errors[key+'_mae'] = statistics.mean(abs(v[key+'_mean'] -
                    (math.log(successful[v['candidate_id']]['measurement_seconds'])
                     if key == 'log_measurement_seconds' else successful[v['candidate_id']][key]))
                    for v in hardware)
            brier = []
            for cap in protocol['area_caps']:
                squared_errors = []
                for v in hardware:
                    probability = (_probability_below(v['area_delta_lut4_mean'], v['area_delta_lut4_std'], cap)
                        * _probability_below(-v['routed_fmax_min_mhz_mean'], v['routed_fmax_min_mhz_std'], -protocol['clock_mhz'])
                        * v['device_fit_probability'])
                    actual = _feasible(successful[v['candidate_id']], cap, protocol['clock_mhz'])
                    squared_errors.append((probability-float(actual))**2)
                brier.append(dict(area_delta_lut4_cap=cap,mean_squared_feasibility_probability_error=statistics.mean(squared_errors)))
            diagnostics.append(dict(seed=prediction['seed'],model='hardware_gp_zero_shot',
                **errors,feasibility_brier=brier,calibrated_confidence=False,
                note='Descriptive target diagnostics; dependent pool points do not establish calibration.'))
    summary = []
    for cap in protocol['area_caps']:
        for policy in protocol['policies']:
            for budget in protocol['budgets']:
                points = [p for r in runs if r['policy']==policy and r['area_delta_lut4_cap']==cap for p in r['curve'] if p['budget']==budget]
                summary.append(dict(area_delta_lut4_cap=cap, policy=policy, budget=budget,
                    mean_best_speedup=statistics.mean(p['best_speedup'] for p in points),
                    mean_regret=statistics.mean(p['regret'] for p in points),
                    oracle_hits=sum(p['regret']==0 for p in points),
                    mean_target_measurement_seconds=statistics.mean(p['target_measurement_seconds'] for p in points),
                    mean_failed_attempts=statistics.mean(p['failed_attempts'] for p in points)))
    report = dict(protocol_sha256=c.sha(root/'protocol.json'), outcomes_sha256=c.digest(outcomes),
        scope=protocol['scope'], oracles=oracles, runs=runs, summary=summary, diagnostics=diagnostics,
        policy_seed_cap_budget_outcomes=len(summary)*len(protocol['seeds']), new_native_jobs=0,
        broad_generalization_established=False, limitations=protocol['limitations'])
    if verify: c.require(stable(report)==stable(c.unseal(root/'report.json')), 'Budgeted replay differs')
    else: c.seal(root/'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze','evaluate','verify'))
    parser.add_argument('--root', type=Path, required=True)
    for key in ('history','target-public','contexts','outcomes'): parser.add_argument('--'+key,type=Path)
    parser.add_argument('--target-workload')
    parser.add_argument('--calibration-cost-seconds',type=float)
    parser.add_argument('--scope',choices=('prospective','consumed-data development'),default='prospective')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        c.require(all((args.history,args.target_public,args.contexts,args.target_workload,
                       args.calibration_cost_seconds is not None)), 'Missing freeze inputs')
        result = freeze(c.unseal(args.history),c.unseal(args.target_public),c.unseal(args.contexts),args.root,
            target_workload=args.target_workload,calibration_cost_seconds=args.calibration_cost_seconds,scope=args.scope)
        print(dict(target_labels_read=result['target_labels_read'],historical_fit_rows=result['historical_fit_rows']))
    else:
        c.require(args.outcomes is not None, 'Outcomes required')
        result = evaluate(args.root,c.unseal(args.outcomes),verify=args.command=='verify')
        print(dict(policy_seed_cap_budget_outcomes=result['policy_seed_cap_budget_outcomes']))


if __name__ == '__main__': main()

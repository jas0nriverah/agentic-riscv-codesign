"""Budget-conditioned decision utility; measured speedup remains a separate label.

This single development model predicts feasible normalized cycle savings, not
speedup or calibrated feasibility. Cap replicas share each candidate bootstrap
sample and divide its weight. It deliberately reuses fixed XGBoost settings.
"""
from __future__ import annotations

import copy
import math
import random
import statistics
import time

from . import budgeted_selection as b
from . import codesign as c
from .model import _number, validate_training_rows

AREA_CAPS = (32, 64, 128)
CLOCK_MHZ = 12.0
MODEL_SETTINGS = dict(ensemble_size=20, n_estimators=80, max_depth=2,
    learning_rate=.05, min_child_weight=1, reg_lambda=1.0, subsample=1.0,
    colsample_bytree=1.0, tree_method='hist', n_jobs=1, objective='reg:squarederror',
    bootstrap='n measured candidates with replacement; every draw expands all caps',
    cap_replica_sample_weight=1/3, interval=.90)
BUDGET_FEATURE = 'area_cap / (training_median_lut4_per_tree_op * tree_op_count)'


def decision_utility(row, area_cap):
    """Signed measured savings when feasible; zero decision utility otherwise.

    Failures have unknown utility and are rejected, not relabeled as zero.
    """
    c.require(area_cap in AREA_CAPS and not isinstance(area_cap, bool), 'Unsupported area cap')
    c.require(b.validate_outcome(row), 'Failed attempts have unknown decision utility')
    if not b._feasible(row, area_cap, CLOCK_MHZ):
        return 0.0
    return (row['baseline_cycles']-row['candidate_cycles'])/b.occurrence_count(row)


class FeasibleBenefitPredictor:
    """Fixed candidate-bootstrap ensemble of budget-conditioned utility regressors."""
    def __init__(self, seed=0):
        c.require(type(seed) is int and seed >= 0, 'Invalid model seed')
        self.seed = seed
        self.models = None
        self.constant = None
        self.area_per_op = None

    def _matrix(self, rows, area_cap):
        c.require(area_cap in AREA_CAPS and not isinstance(area_cap, bool), 'Unsupported area cap')
        c.require(self.area_per_op is not None, 'Fit feasible benefit model first')
        result = []
        for row, base in zip(rows, b.structural_matrix(rows)):
            ops = _number(row['tree_op_count'], 'tree operations', positive=True)
            result.append(base+[area_cap/(self.area_per_op*ops)])
        return result

    def fit(self, rows):
        import numpy as np
        from xgboost import XGBRegressor
        rows = list(rows)
        validate_training_rows(rows)
        c.require(len({r['candidate_id'] for r in rows}) == len(rows), 'Unique measured candidates required')
        for row in rows:
            c.require(b.validate_outcome(row), 'Failed attempts cannot train decision utility')
        self.area_per_op = statistics.median(
            r['area_delta_lut4']/_number(r['tree_op_count'], 'tree operations', positive=True) for r in rows)
        c.require(self.area_per_op > 0, 'Positive historical area proxy required')
        # Candidate-major ordering keeps all cap replicas together during bootstrap.
        matrices = {cap:self._matrix(rows, cap) for cap in AREA_CAPS}
        x = np.asarray([matrices[cap][i] for i in range(len(rows)) for cap in AREA_CAPS], dtype=float)
        y = np.asarray([decision_utility(row, cap) for row in rows for cap in AREA_CAPS], dtype=float)
        self.training_ids = [r['candidate_id'] for r in rows]
        self.models = []
        self.constant = None
        if np.all(y == y[0]):
            self.constant = float(y[0])
        else:
            rng = np.random.default_rng(self.seed)
            for _ in range(MODEL_SETTINGS['ensemble_size']):
                candidates = rng.integers(0, len(rows), size=len(rows))
                indices = np.asarray([int(i)*len(AREA_CAPS)+j for i in candidates for j in range(len(AREA_CAPS))])
                model = XGBRegressor(objective='reg:squarederror', n_estimators=80,
                    max_depth=2, learning_rate=.05, min_child_weight=1, reg_lambda=1.0,
                    subsample=1.0, colsample_bytree=1.0, tree_method='hist', n_jobs=1,
                    random_state=int(rng.integers(0, 2**31-1)), verbosity=0)
                model.fit(x[indices], y[indices], sample_weight=np.full(len(indices), 1/len(AREA_CAPS)))
                self.models.append(model)
        return self

    def predict(self, rows, *, area_cap):
        """Public rows only: utility/spread and expected feasible saved fraction."""
        import numpy as np
        c.require(self.models is not None, 'Fit feasible benefit model first')
        c.require(area_cap in AREA_CAPS and not isinstance(area_cap, bool), 'Unsupported area cap')
        if not rows: return []
        rows = b.public_rows(rows)
        x = self._matrix(rows, area_cap)
        samples = (np.full((20, len(rows)), self.constant) if self.constant is not None
                   else np.stack([model.predict(x) for model in self.models]))
        c.require(np.isfinite(samples).all(), 'Nonfinite feasible utility prediction')
        result = []
        for i, row in enumerate(rows):
            low, high = np.quantile(samples[:, i], [.05, .95])
            conversion = b.occurrence_count(row)/row['latency_features']['baseline_cycles']
            result.append(dict(candidate_id=row['candidate_id'], area_cap=area_cap,
                mean_saved_cycles_per_occurrence=float(samples[:, i].mean()),
                lower_saved_cycles_per_occurrence=float(low), upper_saved_cycles_per_occurrence=float(high),
                std_saved_cycles_per_occurrence=float(samples[:, i].std()),
                mean_fractional_cycle_savings=float(samples[:, i].mean())*conversion,
                uncertainty_calibrated=False))
        return result


def search(public, provider, *, area_cap, seed, budget, predictions):
    """Fixed utility ranking; only paid provider releases outcomes for acceptance."""
    public = b.public_rows(public)
    c.require(type(seed) is int and seed >= 0, 'Invalid tie seed')
    c.require(type(budget) is int and 0 < budget <= len(public), 'Invalid budget')
    c.require(area_cap in AREA_CAPS and not isinstance(area_cap, bool), 'Unsupported area cap')
    estimates = {r['candidate_id']:r for r in predictions}
    c.require(len(estimates) == len(predictions) and set(estimates) == {r['candidate_id'] for r in public},
              'Complete unique utility predictions required')
    for estimate in predictions:
        c.require(estimate['area_cap'] == area_cap, 'Prediction budget differs')
        _number(estimate['mean_fractional_cycle_savings'], 'feasible benefit score')
    ordered = copy.deepcopy(public); random.Random(seed).shuffle(ordered)
    attempts, observations, events, curve = [], [], [], []
    began = time.monotonic()
    while len(attempts) < budget:
        chosen = max(ordered, key=lambda r:estimates[r['candidate_id']]['mean_fractional_cycle_savings'])
        identity = chosen['candidate_id']
        events.append(dict(action='acquire', candidate_id=identity, charged_before_query=len(attempts),
                           utility_prediction=estimates[identity]))
        attempts.append(identity)  # Charge before the provider, including failures.
        try:
            outcome = copy.deepcopy(provider(copy.deepcopy(chosen)))
            success = b.validate_outcome(outcome, chosen)
        except BaseException as error:
            events.append(dict(action='measure-exception', candidate_id=identity, charged=len(attempts),error=repr(error)))
            raise
        events.append(dict(action='measure-complete' if success else 'measure-failed',
                           candidate_id=identity, charged=len(attempts), observation=outcome))
        if success: observations.append(outcome)
        ordered = [r for r in ordered if r['candidate_id'] != identity]
        feasible = [r for r in observations if b._feasible(r, area_cap, CLOCK_MHZ) and r['speedup'] > 1]
        best = min(feasible, key=lambda r:(-r['speedup'],r['area_delta_lut4'],r['candidate_id'])) if feasible else None
        curve.append(dict(budget=len(attempts), best_speedup=best['speedup'] if best else 1.0,
            selected_id=best['candidate_id'] if best else None, attempted_ids=list(attempts),
            measured_ids=[r['candidate_id'] for r in observations], failed_attempts=len(attempts)-len(observations),
            target_measurement_seconds=sum(e['observation']['measurement_seconds'] for e in events if 'observation' in e)))
    return dict(curve=curve, events=events, replay_search_host_seconds=time.monotonic()-began)

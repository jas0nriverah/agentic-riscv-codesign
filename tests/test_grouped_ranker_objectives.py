"""Contracts for the post-hoc workload-grouped XGBoost objective evaluator."""
import pytest

from scripts import evaluate_grouped_ranker_objectives as t
from test_budgeted_selection import measured, public


def test_static_order_budget_counts_infeasible_attempt_and_uses_measured_oracle():
    over_area = measured(public('large', saved_cycles=100), area=65, savings=100, seconds=3)
    feasible = measured(public('small', saved_cycles=40), area=27, savings=40, seconds=4)
    oracle = feasible['speedup']

    first = t._selection_row('target', 'target:ctx', 'xgb_rank_pairwise', 0, 1,
        [over_area, feasible], oracle)
    second = t._selection_row('target', 'target:ctx', 'xgb_rank_pairwise', 0, 2,
        [over_area, feasible], oracle)

    assert first['best_speedup'] == 1.0
    assert first['known_infeasible_attempts'] == 1
    assert first['cycle_reduction_regret'] == pytest.approx(t._cycle_reduction(oracle))
    assert second['best_speedup'] == oracle
    assert second['cycle_reduction_regret'] == 0
    assert second['measurement_seconds'] == 7


def test_group_bootstrap_resamples_workloads_and_positive_is_improvement():
    report = t._paired_bootstrap({'workload-a': .01, 'workload-b': 0.0,
        'workload-c': -.01}, draws=1000)
    assert report['workload_groups'] == 3
    assert report['wins'] == 1 and report['ties'] == 1 and report['losses'] == 1
    assert report['mean'] == 0
    assert report['lower_95'] <= 0 <= report['upper_95']

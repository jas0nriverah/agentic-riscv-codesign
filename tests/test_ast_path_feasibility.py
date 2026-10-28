"""Fixed structural challenger boundaries; no native hardware or target corpus."""
import copy

import pytest

from isaforge.feasibility_selection import FeasibilitySelectionPredictor
from isaforge.features import extract_features
from scripts.evaluate_ast_path_feasibility import (
    AST_COLUMNS, AstPathFeasibilityPredictor, MODELS, OUTPUT, ROOT, folds,
    operator_path_vector, probability_metrics, score_orders, simulate, verify)


def row(identity, formula='add(in0,slli(in1,2))', *, area=40, speedup=1.1):
    return dict(candidate_id=identity, workload_group='fixture', benchmark='fixture:context',
        formula=formula, **extract_features(dict(formula=formula, size=3,
            runs=10, places=1, saved=20, savedPercent=1.0)),
        status='success', correctness_verified=True, device_fits=True,
        area_delta_lut4=area, routed_fmax_min_mhz=65.0, speedup=speedup,
        measurement_seconds=2.0,
        latency_features=dict(estimated_saved_cycles=100, baseline_cycles=1000,
                              estimated_speedup=1.1))


def test_fixed_operator_vocabulary_resolves_parent_order_without_label_features():
    before = operator_path_vector('add(in0,slli(in1,2))')
    after = operator_path_vector('slli(add(in0,in1),2)')
    assert len(before) == len(after) == 168 == len(AST_COLUMNS)
    assert before != after
    assert before[AST_COLUMNS.index('ast_root_add')] == 1
    assert before[AST_COLUMNS.index('ast_1_slli')] == 1
    assert after[AST_COLUMNS.index('ast_root_slli')] == 1
    assert after[AST_COLUMNS.index('ast_0_add')] == 1
    # No additional immediate memorization or input-identity categories.
    assert before == operator_path_vector('add(in1,slli(in0,31))')
    assert all(value in (0, 1) for value in before)


def test_challenger_preserves_numeric_prefix_bootstrap_and_learner_settings():
    original, challenger = FeasibilitySelectionPredictor(), AstPathFeasibilityPredictor()
    original.area_per_op = challenger.area_per_op = 20.0
    example = row('a')
    base = original._matrix([example], 64)[0]
    augmented = challenger._matrix([example], 64)[0]
    assert augmented[:len(base)] == base
    assert augmented[len(base):] == operator_path_vector(example['formula'])
    assert AstPathFeasibilityPredictor.fit is FeasibilitySelectionPredictor.fit
    assert AstPathFeasibilityPredictor.predict is FeasibilitySelectionPredictor.predict
    changed = copy.deepcopy(example)
    changed['area_delta_lut4'], changed['speedup'] = 1000, 0.5
    assert challenger._matrix([example], 64) == challenger._matrix([changed], 64)


def test_probability_metrics_keep_single_class_auc_and_ap_undefined():
    result = probability_metrics([1, 1], [.8, .9])
    assert result['brier'] == pytest.approx(.025)
    assert result['roc_auc'] is None and result['average_precision'] is None
    assert not result['ranking_metrics_defined']
    with pytest.raises(ValueError, match='Invalid feasibility'):
        probability_metrics([1, 0], [.2, float('nan')])


def test_failed_query_is_charged_and_unresolved_oracle_remains_null():
    success = row('success')
    failure = row('failed')
    failure.update(status='failed', reference_censored=True, measurement_seconds=3)
    failure.pop('area_delta_lut4')
    failure.pop('speedup')
    # A separate public fixture proves orders do not need target outcome fields.
    public = [{key: value for key, value in candidate.items()
               if key in ('candidate_id', 'saved', 'runs', 'latency_features')}
              for candidate in (success, failure)]
    predictions = {name: {'success': .1, 'failed': .9} for name in MODELS}
    orders, runs = simulate('fixture:context', public, [success, failure], predictions)
    assert orders[MODELS[0]] == ['failed', 'success']
    first = next(point for point in runs if point['policy'] == MODELS[0] and point['budget'] == 1)
    assert first['failed_or_unresolved_attempts'] == 1
    assert first['best_speedup'] == 1.0
    assert first['measurement_seconds'] == 3
    assert first['cycle_reduction_regret'] is None
    assert score_orders(public, predictions) == orders


def test_invalid_common_budget_fold_fails_instead_of_shrinking_the_pool():
    rows = [row('target', 'add(in0,in1)')]
    for group, formula in (('history-a', 'sub(in0,in1)'), ('history-b', 'xor(in0,in1)')):
        for index in range(2):
            item = row(group + str(index), formula)
            item.update(workload_group=group, benchmark=group + ':context')
            rows.append(item)
    with pytest.raises(ValueError, match='pool is smaller than the common maximum budget'):
        folds(dict(rows=rows, failed_attempts=[]))


def test_frozen_exact_report_reproduction_never_refits(monkeypatch):
    def forbidden_fit(*args, **kwargs):
        raise AssertionError('Report verification must preserve frozen predictions and timers')
    monkeypatch.setattr(FeasibilitySelectionPredictor, 'fit', forbidden_fit)
    verify(ROOT / OUTPUT)

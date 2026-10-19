"""Check budgeted selection, oracle accounting, and hidden-label isolation."""
from copy import deepcopy

import pytest

from isaforge.area_selection import OUTER_METHOD, STRATEGIES, evaluate_area_selection


def fixture_rows():
    return [dict(benchmark='program', candidate_id=identity, runs=runs,
                 overlap_safe_saved=saved, lut4_count=actual,
                 measurement_source='rtl_synthesis', correctness_verified=True)
            for identity, runs, saved, actual in [
                ('expensive', 100, 1000, 200),
                ('best', 40, 800, 60),
                ('small', 60, 300, 20),
                ('bad_prediction', 80, 900, 100)]]


def fixture_report():
    return dict(method=OUTER_METHOD, row_count=4,
                folds=[dict(held_out_benchmark='program', status='evaluated', train_benchmarks=['other'],
                            predictions=[dict(candidate_id=identity, predicted_lut4=estimate, measured_lut4=-999)
                                         for identity, estimate in [('expensive', 180), ('best', 50),
                                                                    ('small', 18), ('bad_prediction', 40)]])])


def run(rows=None, report=None, caps=(64,), budgets=(1, 3), seeds=(0,)):
    return evaluate_area_selection(rows or fixture_rows(), report or fixture_report(), caps, budgets, seeds)


def detail(report, strategy, budget):
    return next(item for item in report['details'] if item['strategy'] == strategy and item['measurement_budget'] == budget)


def test_measured_feasibility_retry_and_oracle_retention():
    report = run()
    first = detail(report, 'predicted_area_feasible_merit', 1)
    assert first['attempted'][0]['candidate_id'] == 'bad_prediction'
    assert first['first_proposed_actual_area_violation']
    assert first['selected_candidate_id'] is None
    assert first['selected_overlap_safe_saved'] == 0
    retry = detail(report, 'predicted_area_feasible_merit', 3)
    assert retry['selected_candidate_id'] == 'best'
    assert retry['candidate_measurements'] == 3
    assert retry['attempted_actual_area_violations'] == 1
    assert retry['oracle_overlap_safe_saved'] == 800
    assert retry['retained_oracle_instruction_saving_fraction'] == 1
    assert detail(report, 'frequency', 1)['selected_candidate_id'] is None
    assert detail(report, 'merit', 1)['selected_candidate_id'] is None


def test_actual_area_labels_cannot_change_acquisition_order():
    original = run(budgets=(4,), seeds=(0, 1))
    altered_rows = fixture_rows()
    for row in altered_rows:
        row['lut4_count'] = 1 if row['lut4_count'] > 64 else 10000
    altered = run(rows=altered_rows, budgets=(4,), seeds=(0, 1))
    for before, after in zip(original['details'], altered['details']):
        assert [item['candidate_id'] for item in before['attempted']] == [item['candidate_id'] for item in after['attempted']]
    assert detail(original, 'merit', 4)['selected_candidate_id'] != detail(altered, 'merit', 4)['selected_candidate_id']


def test_report_measurement_fields_are_not_acquisition_inputs():
    report = fixture_report()
    for prediction in report['folds'][0]['predictions']:
        prediction['measured_lut4'] = 123456
        prediction['actual_lut4'] = 654321
    assert run(report=report)['details'] == run()['details']


def test_budget_larger_than_pool_and_random_reproducibility():
    report = run(budgets=(10,), seeds=(0, 1))
    assert all(item['candidate_measurements'] == 4 for item in report['details'])
    assert all(item['selected_candidate_id'] == 'best' for item in report['details'])
    assert report == run(budgets=(10,), seeds=(0, 1))
    random_orders = [item['attempted'] for item in report['details'] if item['strategy'] == 'random']
    assert random_orders[0] != random_orders[1]


def test_infeasible_pool_retention_is_undefined():
    report = run(caps=(0,), budgets=(1,))
    assert all(item['selected_overlap_safe_saved'] == 0 for item in report['details'])
    assert all(item['retained_oracle_instruction_saving_fraction'] is None for item in report['details'])
    assert all(item['positive_oracle_cases'] == 0 for item in report['aggregates'])


@pytest.mark.parametrize('change,message', [
    ('missing', 'entire pool'), ('extra', 'entire pool'),
    ('duplicate', 'duplicate outer'), ('in_sample', 'outer benchmark'),
    ('leaked_benchmark', 'leaked'), ('wrong_count', 'row_count'),
    ('nonfinite', 'finite nonnegative'), ('skipped_fold', 'not evaluated')])
def test_invalid_prediction_reports_fail(change, message):
    report = deepcopy(fixture_report())
    fold = report['folds'][0]
    if change == 'missing': fold['predictions'].pop()
    if change == 'extra': fold['predictions'].append(dict(candidate_id='new', predicted_lut4=1))
    if change == 'duplicate': fold['predictions'].append(fold['predictions'][0])
    if change == 'in_sample': report['method'] = 'final refit'
    if change == 'leaked_benchmark': fold['train_benchmarks'].append('program')
    if change == 'wrong_count': report['row_count'] = 3
    if change == 'nonfinite': fold['predictions'][0]['predicted_lut4'] = float('nan')
    if change == 'skipped_fold': fold['status'] = 'skipped'
    with pytest.raises(ValueError, match=message):
        run(report=report)


@pytest.mark.parametrize('field,value,message', [('lut4_count', -1, 'actual LUT4'),
    ('overlap_safe_saved', float('inf'), 'overlap-safe'),
    ('runs', True, 'runs'), ('measurement_source', 'synthetic', 'actual rtl_synthesis'),
    ('correctness_verified', False, 'correctness-verified')])
def test_invalid_measured_rows_fail(field, value, message):
    rows = fixture_rows()
    rows[0][field] = value
    with pytest.raises(ValueError, match=message):
        run(rows=rows)


def test_default_grid_and_aggregate_accounting():
    report = evaluate_area_selection(fixture_rows(), fixture_report())
    assert len(report['details']) == len(STRATEGIES) * 3 * 3 * 5
    assert len(report['aggregates']) == len(STRATEGIES) * 3 * 3
    for aggregate in report['aggregates']:
        group = [item for item in report['details'] if item['strategy'] == aggregate['strategy'] and
                 item['lut4_cap'] == aggregate['lut4_cap'] and item['measurement_budget'] == aggregate['measurement_budget']]
        assert aggregate['candidate_measurements'] == sum(item['candidate_measurements'] for item in group)
        assert aggregate['attempted_actual_area_violations'] == sum(item['attempted_actual_area_violations'] for item in group)

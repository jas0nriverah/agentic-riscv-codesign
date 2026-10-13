from copy import deepcopy

import pytest

from isaforge.fresh_evaluation import evaluate_frozen, operation_count


def fixtures():
    def row(b, i, f, area, saved):
        return dict(benchmark=b, candidate_id=i, formula=f, lut4_count=area,
                    runs=10, overlap_safe_saved=saved, measurement_source='rtl_synthesis', correctness_verified=True)
    train = [row('train', 'a', 'add(in0,in1)', 32, 1)]
    test = [row('fresh', 'x', 'add(in0,in1)', 32, 10),
            row('fresh', 'y', 'xor(in0,in1)', 32, 20),
            row('fresh', 'z', 'mul(in0,in1)', 1000, 30)]
    predictions = {'fixed': [dict(benchmark=r['benchmark'], candidate_id=r['candidate_id'],
                                  formula=r['formula'], predicted_lut4=r['lut4_count']) for r in test]}
    return train, test, predictions


def run(train, test, predictions):
    return evaluate_frozen(train, test, predictions, caps=(64,), budgets=(1, 3), random_seeds=range(5))


def test_fresh_novel_subset_and_program_seed_aggregation():
    report = run(*fixtures())
    assert report['novel_formula_count'] == 2
    assert report['accuracy']['fixed']['distinct_novel_formulas']['mae_lut4'] == 0
    assert report['accuracy']['fixed']['all_rows']['sample_count'] == 3
    outcomes = report['selection']['program_results']
    model = next(x for x in outcomes if x['strategy'] == 'model:fixed' and x['budget'] == 1)
    assert model['retention'] == 1
    assert model['seed_count'] == 1
    random = next(x for x in outcomes if x['strategy'] == 'random' and x['budget'] == 1)
    assert random['seed_count'] == 5
    summary = next(x for x in report['selection']['summaries'] if x['strategy'] == 'model:fixed' and x['budget'] == 1)
    assert summary['paired_retention_difference_vs_merit']['mean'] == 1
    assert summary['retention']['program_count'] == 1


def test_labels_cannot_change_frozen_acquisition():
    train, test, pred = fixtures()
    first = run(train, test, pred)
    changed = deepcopy(test)
    for r in changed:
        r['lut4_count'] = 0
    second = run(train, changed, pred)
    orders = lambda r: [[a['candidate_id'] for a in x['attempted']] for x in r['selection']['details']]
    assert orders(first) == orders(second)


@pytest.mark.parametrize('fault', ['same_benchmark', 'wrong_formula', 'missing', 'duplicate', 'negative', 'unverified'])
def test_rejects_invalid_comparisons(fault):
    train, test, pred = fixtures()
    if fault == 'same_benchmark': train[0]['benchmark'] = 'fresh'
    if fault == 'wrong_formula': pred['fixed'][0]['formula'] = 'sub(in0,in1)'
    if fault == 'missing': pred['fixed'].pop()
    if fault == 'duplicate': pred['fixed'].append(pred['fixed'][0])
    if fault == 'negative': pred['fixed'][0]['predicted_lut4'] = -1
    if fault == 'unverified': test[0]['correctness_verified'] = False
    with pytest.raises(ValueError): run(train, test, pred)


def test_shared_expression_cost_counts_distinct_operations():
    assert operation_count('add(xor(in0,in1),xor(in0,in1))') == 2


def test_zero_oracle_is_undefined_not_perfect():
    train, test, pred = fixtures()
    for row in test: row['overlap_safe_saved'] = 0
    report = run(train, test, pred)
    assert all(s['retention'] is None for s in report['selection']['summaries'])


def test_zero_candidate_declared_program_is_retained_in_coverage():
    report = evaluate_frozen(*fixtures(), caps=(64,), budgets=(1,), random_seeds=(0,),
                             declared_benchmarks=['fresh', 'empty'])
    assert report['zero_candidate_benchmarks'] == ['empty']
    assert all(s['retention']['program_count'] == 1 for s in report['selection']['summaries'])
    assert all('empty' in s['excluded_programs_from_retention'] for s in report['selection']['summaries'])
    assert report['selection']['details'][0]['absolute_savings_regret'] >= 0


def test_policy_scores_are_not_regression_predictions_and_calibration_is_seen():
    train, test, pred = fixtures()
    calibration = [{**test[1], 'benchmark': 'calibration'}]
    policies = {'discounted': [{**r, 'predicted_lut4': 0} for r in pred['fixed']]}
    report = evaluate_frozen(train, test, pred, caps=(64,), budgets=(1,), random_seeds=(0,),
                             calibration_rows=calibration, policy_predictions=policies)
    assert report['novel_formula_count'] == 1
    assert report['training_formula_count'] == 1
    assert report['calibration_formula_count'] == 1
    assert set(report['accuracy']) == {'fixed'}
    assert any(r['strategy'] == 'model:discounted' for r in report['selection']['summaries'])

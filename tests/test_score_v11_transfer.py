"""Synthetic-only endpoint arithmetic and fail-closed input-contract checks."""
import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'score_v11_transfer', Path(__file__).resolve().parents[1] / 'scripts/score_v11_transfer.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture():
    members = {'ammunition': ['shared', 'a'], 'audiobeam': ['b'], 'pm': ['shared'],
               'fmref': ['d'], 'fac': ['e'], 'recursion': []}
    outcomes = [{'program': p, 'family': f, 'status': 'complete' if members[p] else 'empty',
                 'canonical_count': len(members[p])} for p, f in m.PROGRAM_FAMILIES.items()]
    membership = [{'program': p, 'canonical_ids': ids} for p, ids in members.items()]
    labels = [{'id': i, 'lut4': y} for i, y in {'shared': 64, 'a': 0, 'b': 33, 'd': 129, 'e': 10}.items()]
    predictions = {model: [{'id': i, 'prediction': p} for i, p in values.items()] for model, values in {
        'V6': {'shared': 32, 'a': 10, 'b': 64, 'd': 128, 'e': 20},
        'V9': {'shared': 65, 'a': 0, 'b': 32, 'd': 130, 'e': 0}}.items()}
    return outcomes, membership, labels, predictions


def test_primary_hand_calculation_and_undefined_original():
    result = m.score(*fixture())
    assert result['primary']['scores'] == pytest.approx({'V6': 19, 'V9': 2.7, 'delta_v9_minus_v6': -16.3})
    assert result['original_equal_all_program_endpoint'] == {
        'available': False, 'undefined_programs': ['recursion'], 'scores': None}
    empty = result['per_program']['recursion']
    assert empty['status'] == 'empty' and empty['canonical_count'] == 0
    assert empty['metrics'] == {'V6': None, 'V9': None, 'mae_delta_v9_minus_v6': None}
    family = result['per_family']['integer-recurrences']
    assert family['eligible_programs'] == ['fac'] and family['empty_programs'] == ['recursion']
    assert family['equal_eligible_program_mae'] == {'V6': 10, 'V9': 10, 'delta_v9_minus_v6': 0}


def test_membership_pooled_weighting_shared_labels_and_all_counts():
    result = m.score(*fixture())
    assert result['coverage'] == {'complete_program_outcomes': 6, 'nonempty_programs': 5,
        'empty_programs': ['recursion'], 'nonempty_families': 5,
        'program_formula_rows': 6, 'unique_canonical_originals': 5}
    pooled = result['pooled_membership_metrics']
    assert pooled['V6']['n'] == pooled['V9']['n'] == 6
    assert pooled['V6']['mae'] == pytest.approx(116 / 6)
    assert pooled['V9']['mae'] == pytest.approx(14 / 6)
    assert pooled['mae_delta_v9_minus_v6'] == pytest.approx(-17)
    assert sum(x['canonical_count'] for x in result['per_program'].values()) == 6


def test_all_three_caps_inclusive_boundaries_and_explicit_denominators():
    result = m.score(*fixture())['pooled_membership_metrics']
    assert set(result['V6']['cap_decisions']) == {'32', '64', '128'}
    assert result['V6']['cap_decisions']['32'] == {
        'false_accept_count': 2, 'false_reject_count': 0, 'all_rows_denominator': 6,
        'predicted_feasible_denominator': 4, 'predicted_infeasible_denominator': 2,
        'truly_feasible_denominator': 2, 'truly_infeasible_denominator': 4}
    assert result['V9']['cap_decisions']['64'] == {
        'false_accept_count': 0, 'false_reject_count': 2, 'all_rows_denominator': 6,
        'predicted_feasible_denominator': 3, 'predicted_infeasible_denominator': 3,
        'truly_feasible_denominator': 5, 'truly_infeasible_denominator': 1}
    assert result['V6']['cap_decisions']['128']['false_accept_count'] == 1
    assert result['V9']['cap_decisions']['32']['false_accept_count'] == 1


def test_bias_rmsle_zeros_tails_independent_arithmetic():
    result = m.score(*fixture())['pooled_membership_metrics']['V6']
    actual, predictions = [0, 64, 33, 64, 129, 10], [10, 32, 64, 32, 128, 20]
    errors = [p - y for y, p in zip(actual, predictions)]
    logs = [(math.log1p(p) - math.log1p(y)) ** 2 for y, p in zip(actual, predictions)]
    assert result['bias_prediction_minus_actual'] == pytest.approx(sum(errors) / 6)
    assert result['rmsle'] == pytest.approx(math.sqrt(sum(logs) / 6))
    assert result['zero_area_count'] == 1 and result['zero_area_mae'] == 10
    assert result['maximum_underprediction'] == result['maximum_absolute_error'] == 32
    assert result['absolute_error_p90'] == result['absolute_error_p95'] == result['absolute_error_p99'] == 32


def test_quantiles_type7_and_singleton_no_rounding():
    assert m.quantile([0, 10, 20, 100], .9) == pytest.approx(76)
    assert m.quantile([0, 10, 20, 100], .95) == pytest.approx(88)
    assert m.quantile([0, 10, 20, 100], .99) == pytest.approx(97.6)
    for p in [0, .9, .95, .99, 1]: assert m.quantile([7], p) == 7


def test_equal_program_then_family_not_formula_count_weighting():
    outcomes, membership, labels, predictions = fixture()
    outcomes[-1].update(status='complete', canonical_count=2)
    membership[-1]['canonical_ids'] = ['r1', 'r2']
    labels.extend([{'id': 'r1', 'lut4': 10}, {'id': 'r2', 'lut4': 10}])
    for model in m.MODELS:
        predictions[model].extend([{'id': 'r1', 'prediction': 0}, {'id': 'r2', 'prediction': 0}])
        next(x for x in predictions[model] if x['id'] == 'e')['prediction'] = 100
    result = m.score(outcomes, membership, labels, predictions)
    family = result['per_family']['integer-recurrences']
    assert family['equal_eligible_program_mae']['V6'] == 50
    assert family['pooled_membership_metrics']['V6']['mae'] == pytest.approx(110 / 3)
    assert result['primary']['scores']['V6'] == pytest.approx((21 + 31 + 32 + 1 + 50) / 5)
    assert result['original_equal_all_program_endpoint']['available'] is True
    assert result['original_equal_all_program_endpoint']['scores'] == result['primary']['scores']


@pytest.mark.parametrize('status', ['failure-retained', 'running', 'timeout', 'not-attempted', None])
def test_partial_outcomes_rejected(status):
    args = fixture(); args[0][0]['status'] = status
    with pytest.raises(ValueError, match='partial outcomes'): m.score(*args)


def test_no_eligible_family_rejected_instead_of_renormalizing():
    args = fixture(); args[0][0].update(status='empty', canonical_count=0); args[1][0]['canonical_ids'] = []
    with pytest.raises(ValueError, match='All five families'): m.score(*args)


@pytest.mark.parametrize('which', ['outcome', 'membership', 'label', 'V6', 'V9'])
@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate'])
def test_exact_record_membership_poison(which, change):
    args = fixture()
    records = {'outcome': args[0], 'membership': args[1], 'label': args[2],
               'V6': args[3]['V6'], 'V9': args[3]['V9']}[which]
    if change == 'missing': records.pop()
    elif change == 'duplicate':
        if which in ('outcome', 'membership'): records[-1] = copy.deepcopy(records[0])
        else: records.append(copy.deepcopy(records[0]))
    elif which == 'outcome': records.append({'program': 'swapped', 'family': 'new', 'status': 'complete', 'canonical_count': 1})
    elif which == 'membership': records.append({'program': 'swapped', 'canonical_ids': ['extra']})
    else: records.append({'id': 'extra', 'lut4' if which == 'label' else 'prediction': 1})
    with pytest.raises(ValueError): m.score(*args)


@pytest.mark.parametrize('value', [True, False, -1, 1.0, float('nan'), float('inf'), '2', None, 10**1000])
def test_label_count_strict(value):
    args = fixture(); args[2][0]['lut4'] = value
    with pytest.raises(ValueError): m.score(*args)


@pytest.mark.parametrize('value', [True, False, -1, float('nan'), float('inf'), -float('inf'), '2', None, 10**1000])
def test_prediction_value_strict(value):
    args = fixture(); args[3]['V9'][0]['prediction'] = value
    with pytest.raises(ValueError): m.score(*args)


@pytest.mark.parametrize('poison', ['count', 'bool_count', 'family', 'empty_nonzero', 'complete_zero',
                                  'duplicate_member', 'id', 'extra_field', 'model', 'label_set', 'forecast_set'])
def test_contract_poison(poison):
    args = fixture()
    if poison == 'count': args[0][0]['canonical_count'] += 1
    elif poison == 'bool_count': args[0][0]['canonical_count'] = True
    elif poison == 'family': args[0][0]['family'] = 'wrong'
    elif poison == 'empty_nonzero': args[0][0]['status'] = 'empty'
    elif poison == 'complete_zero': args[0][-1]['status'] = 'complete'
    elif poison == 'duplicate_member': args[1][0]['canonical_ids'][1] = 'shared'
    elif poison == 'id': args[2][0]['id'] = ' padded '
    elif poison == 'extra_field': args[1][0]['chosen_only'] = True
    elif poison == 'model': args[3]['chosen'] = args[3]['V6']
    elif poison == 'label_set': args[2][0]['id'] = 'not-in-pool'
    elif poison == 'forecast_set': args[3]['V6'][0]['id'] = 'not-in-pool'
    with pytest.raises(ValueError): m.score(*args)


def test_order_invariance_no_mutation_or_io(monkeypatch):
    args = fixture(); saved = copy.deepcopy(args)
    def forbidden(*a, **k): raise AssertionError('Metric engine attempted file/process access')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr('subprocess.Popen', forbidden)
    first = m.score(*args)
    assert args == saved
    for records in args[:3]: records.reverse()
    for entry in args[1]: entry['canonical_ids'].reverse()
    for records in args[3].values(): records.reverse()
    assert first == m.score(*args)
    assert first['endpoint_reference']['amendment'] == 'V11b-E1'
    assert first['endpoint_reference']['adoption']['sha256'] == 'aef3c6952b399d98804f873d3d8514bf21c49715de074993c4914b57237976ad'
    json.dumps(first, allow_nan=False)


def test_all_exact_no_zeros_and_no_underprediction():
    args = fixture()
    for label in args[2]: label['lut4'] = 1
    for records in args[3].values():
        for record in records: record['prediction'] = 1
    result = m.score(*args)['pooled_membership_metrics']
    for model in m.MODELS:
        assert result[model]['mae'] == result[model]['rmsle'] == result[model]['maximum_underprediction'] == 0
        assert result[model]['zero_area_count'] == 0 and result[model]['zero_area_mae'] is None
        assert result[model]['cap_decisions']['32']['truly_infeasible_denominator'] == 0

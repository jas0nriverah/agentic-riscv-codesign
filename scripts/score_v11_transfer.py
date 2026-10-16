"""Pure paired V11b-E1 metrics; no file access, models, native jobs or cohort CLI.

score() accepts complete, already authenticated inputs. It checks their internal
membership/count consistency, not extraction completeness or artifact provenance.
An eventual released adapter must authenticate those scientific facts separately.
Pooled metrics count each distinct program/formula membership once; a formula
shared by programs keeps every membership but requires only one label/prediction.
Quantiles use linear interpolation at (n-1)*p (Hyndman--Fan type 7).
"""
from __future__ import annotations

import hashlib
import json
import math


PROGRAM_FAMILIES = {
    'ammunition': 'arbitrary-precision-bit-strings',
    'audiobeam': 'audio-beamforming',
    'pm': 'numeric-template-matching',
    'fmref': 'fm-reception',
    'fac': 'integer-recurrences',
    'recursion': 'integer-recurrences',
}
MODELS = ('V6', 'V9')
CAPS = (32, 64, 128)
REFERENCE = {
    'amendment': 'V11b-E1',
    'protocol': {'path': 'docs/v11b-transfer-protocol.md',
                 'sha256': '72f5aa9053ebd6505243a67744cd36944c88114098e45aad4ee4c090c18c4c59'},
    'adoption': {'path': 'results/2026-10-16-v11b-transfer-recovery/endpoint-adoption.json',
                 'sha256': 'aef3c6952b399d98804f873d3d8514bf21c49715de074993c4914b57237976ad'},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def keys(record, expected, name):
    need(type(record) is dict and set(record) == set(expected), name + ' fields differ')


def identifier(value):
    need(type(value) is str and bool(value) and value.strip() == value,
         'Nonempty, unpadded canonical ID required')
    return value


def count(value):
    need(type(value) is int and value >= 0, 'Nonnegative integer count required')
    return value


def prediction(value):
    need(type(value) in (int, float), 'Prediction must be an int/float, not bool')
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError('Finite nonnegative prediction required') from error
    need(math.isfinite(result) and result >= 0, 'Finite nonnegative prediction required')
    return result


def quantile(values, probability):
    """Type-7 quantile of a nonempty finite sample (no rounding)."""
    need(values and 0 <= probability <= 1, 'Nonempty quantile sample required')
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def mean(values):
    # Divide before summing so finite nonnegative samples do not overflow merely
    # because the intermediate total exceeds the float range.
    return math.fsum(value / len(values) for value in values)


def metrics(actual, predicted):
    n = len(actual)
    need(n > 0 and len(predicted) == n, 'Nonempty aligned metric vectors required')
    errors = [p - y for y, p in zip(actual, predicted)]
    absolute = [abs(e) for e in errors]
    log_errors = [math.log1p(p) - math.log1p(y) for y, p in zip(actual, predicted)]
    zeros = [i for i, y in enumerate(actual) if y == 0]
    caps = {}
    for cap in CAPS:
        truly_feasible = sum(y <= cap for y in actual)
        predicted_feasible = sum(p <= cap for p in predicted)
        caps[str(cap)] = {
            'false_accept_count': sum(p <= cap < y for y, p in zip(actual, predicted)),
            'false_reject_count': sum(y <= cap < p for y, p in zip(actual, predicted)),
            'all_rows_denominator': n,
            'predicted_feasible_denominator': predicted_feasible,
            'predicted_infeasible_denominator': n - predicted_feasible,
            'truly_feasible_denominator': truly_feasible,
            'truly_infeasible_denominator': n - truly_feasible,
        }
    result = {
        'n': n, 'mae': mean(absolute), 'bias_prediction_minus_actual': mean(errors),
        'rmsle': math.sqrt(mean([e * e for e in log_errors])),
        'absolute_error_p90': quantile(absolute, .90),
        'absolute_error_p95': quantile(absolute, .95),
        'absolute_error_p99': quantile(absolute, .99),
        'maximum_absolute_error': max(absolute),
        'maximum_underprediction': max(0.0, max(-e for e in errors)),
        'zero_area_count': len(zeros),
        'zero_area_mae': mean([absolute[i] for i in zeros]) if zeros else None,
        'cap_decisions': caps,
    }
    return result


def paired(ids, labels, predictions):
    if not ids:
        return {'V6': None, 'V9': None, 'mae_delta_v9_minus_v6': None}
    actual = [labels[i] for i in ids]
    result = {model: metrics(actual, [predictions[model][i] for i in ids]) for model in MODELS}
    result['mae_delta_v9_minus_v6'] = result['V9']['mae'] - result['V6']['mae']
    return result


def pair_values(v6, v9):
    return {'V6': v6, 'V9': v9, 'delta_v9_minus_v6': v9 - v6}


def score(outcomes, membership, labels, predictions):
    """Return descriptive metrics for the single adopted endpoint definition.

    outcomes: six {program, family, status, canonical_count} records; status is
      'complete' for nonempty pools or 'empty' for a complete zero-candidate pool.
    membership: six {program, canonical_ids} records (IDs unique within program).
    labels: one {id, lut4} record per global ID, with nonnegative integer LUT4.
    predictions: exactly {'V6': [{id, prediction}, ...], 'V9': [...]}.

    Partial outcomes, absent eligible families and incomplete/extra/duplicate
    labels or predictions raise ValueError. Empty programs retain None metrics.
    This function performs no file reads and does not release a cohort analysis.
    """
    need(type(outcomes) is list and len(outcomes) == 6, 'Exactly six program outcomes required')
    by_program = {}
    for entry in outcomes:
        keys(entry, ('program', 'family', 'status', 'canonical_count'), 'Outcome')
        name = identifier(entry['program'])
        need(name in PROGRAM_FAMILIES and name not in by_program, 'Unknown/duplicate outcome program')
        need(entry['family'] == PROGRAM_FAMILIES[name], 'Reserved family differs')
        n = count(entry['canonical_count'])
        need((entry['status'] == 'complete' and n > 0) or (entry['status'] == 'empty' and n == 0),
             'Complete nonempty or complete empty outcome required; partial outcomes forbidden')
        by_program[name] = dict(entry)
    need(set(by_program) == set(PROGRAM_FAMILIES), 'Exact reserved program set required')
    need(type(membership) is list and len(membership) == 6, 'Exactly six memberships required')
    members = {}
    for entry in membership:
        keys(entry, ('program', 'canonical_ids'), 'Membership')
        name = identifier(entry['program'])
        need(name in by_program and name not in members, 'Unknown/duplicate membership program')
        need(type(entry['canonical_ids']) is list, 'Canonical IDs must be a list')
        ids = [identifier(i) for i in entry['canonical_ids']]
        need(len(set(ids)) == len(ids), 'Duplicate ID within program')
        need(len(ids) == by_program[name]['canonical_count'], 'Full outcome/membership count mismatch')
        members[name] = sorted(ids)
    need(set(members) == set(by_program), 'Exact reserved membership set required')
    families = sorted(set(PROGRAM_FAMILIES.values()))
    need(all(any(members[p] for p in members if PROGRAM_FAMILIES[p] == f) for f in families),
         'All five families require an eligible program')
    ids = sorted({i for program_ids in members.values() for i in program_ids})
    need(type(labels) is list, 'Labels must be a list of unique records')
    y = {}
    for entry in labels:
        keys(entry, ('id', 'lut4'), 'Label')
        i = identifier(entry['id'])
        need(i not in y, 'Duplicate label ID')
        value = count(entry['lut4'])
        # Integer labels must also be representable for the floating metrics.
        prediction(value)
        y[i] = value
    need(set(y) == set(ids), 'Exactly one label per unique member required')
    keys(predictions, MODELS, 'Predictions')
    forecast = {}
    for model in MODELS:
        need(type(predictions[model]) is list, 'Prediction records must be a list')
        forecast[model] = {}
        for entry in predictions[model]:
            keys(entry, ('id', 'prediction'), 'Prediction')
            i = identifier(entry['id'])
            need(i not in forecast[model], 'Duplicate prediction ID')
            forecast[model][i] = prediction(entry['prediction'])
        need(set(forecast[model]) == set(ids), 'Exactly one prediction per unique member required')

    per_program = {}
    for name, family in PROGRAM_FAMILIES.items():
        per_program[name] = {
            'family': family, 'status': by_program[name]['status'],
            'canonical_count': len(members[name]), 'metrics': paired(members[name], y, forecast),
        }
    per_family = {}
    for family in families:
        programs = [p for p in PROGRAM_FAMILIES if PROGRAM_FAMILIES[p] == family]
        eligible = [p for p in programs if members[p]]
        family_ids = [i for p in programs for i in members[p]]
        maes = {model: mean([per_program[p]['metrics'][model]['mae'] for p in eligible]) for model in MODELS}
        per_family[family] = {
            'programs': programs, 'eligible_programs': eligible,
            'empty_programs': [p for p in programs if not members[p]],
            'program_formula_rows': len(family_ids), 'unique_canonical_originals': len(set(family_ids)),
            'equal_eligible_program_mae': pair_values(maes['V6'], maes['V9']),
            'pooled_membership_metrics': paired(family_ids, y, forecast),
        }
    macro = {model: mean([per_family[f]['equal_eligible_program_mae'][model] for f in families]) for model in MODELS}
    empty = [p for p in PROGRAM_FAMILIES if not members[p]]
    original = {'available': not empty, 'undefined_programs': empty, 'scores': None}
    if not empty:
        old = {model: mean([mean([per_program[p]['metrics'][model]['mae'] for p in PROGRAM_FAMILIES
                                 if PROGRAM_FAMILIES[p] == f]) for f in families]) for model in MODELS}
        original['scores'] = pair_values(old['V6'], old['V9'])
    # Normalized input digest is independent of incoming record/list order.
    normalized = {
        'outcomes': [by_program[p] for p in PROGRAM_FAMILIES],
        'membership': [{'program': p, 'canonical_ids': members[p]} for p in PROGRAM_FAMILIES],
        'labels': [{'id': i, 'lut4': y[i]} for i in ids],
        'predictions': {model: [{'id': i, 'prediction': forecast[model][i]} for i in ids] for model in MODELS},
    }
    result = {
        'schema': 'isaforge-v11b-e1-paired-metrics-v1',
        'scope': 'Pure supplied-data metrics; no input authentication, cohort release or new execution.',
        'endpoint_reference': json.loads(json.dumps(REFERENCE)),
        'normalized_inputs_sha256': hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        'quantile_definition': 'Hyndman-Fan type 7: linear interpolation at (n-1)*p of sorted absolute errors',
        'pooled_weighting': 'One row per distinct program/canonical-formula membership; shared formulas retain every program membership.',
        'coverage': {'complete_program_outcomes': 6, 'nonempty_programs': 6 - len(empty),
                     'empty_programs': empty, 'nonempty_families': 5,
                     'program_formula_rows': sum(map(len, members.values())), 'unique_canonical_originals': len(ids)},
        'primary': {'name': 'V11b-E1 equal-five-family/equal-eligible-program MAE',
                    'scores': pair_values(macro['V6'], macro['V9']), 'negative_delta_favors': 'V9'},
        'original_equal_all_program_endpoint': original,
        'per_program': per_program, 'per_family': per_family,
        'pooled_membership_metrics': paired([i for p in PROGRAM_FAMILIES for i in members[p]], y, forecast),
    }
    # Reject any arithmetic overflow rather than serializing invalid metrics.
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, OverflowError) as error:
        raise ValueError('Nonfinite metric arithmetic') from error
    return result


if __name__ == '__main__':
    raise SystemExit('Library only: no released V11 cohort scoring CLI.')

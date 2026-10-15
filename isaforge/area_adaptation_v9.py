"""Fixed, bounded residual adaptation on consumed application data.

No file I/O, training, feature extraction, normalization, or target acquisition.
Identity groups control exclusion; original formula rows retain their weights.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import statistics

import numpy as np

from .features import parse_formula

BUDGETS = (1, 3, 5)
ADAPTERS = ('frozen', 'global_residual', 'local_residual')
PROTOCOL = {
    'status': 'consumed-V8-development-not-independent-confirmation',
    'budgets': list(BUDGETS), 'primary_budget': 3, 'cap_lut4': 64,
    'query_policy': 'frozen-mapping-predicted-feasible-merit',
    'query_ties': 'saved-descending/formula/candidate-id; infeasible-first-key=point-minus-cap',
    'family_schedule': 'lexicographic-program-round-robin; unique-original-formula attempts',
    'adapter_names': list(ADAPTERS), 'pseudo_observation_weight': 1,
    'local_correction': 'sum(K*(y-p0))/(1+sum(K)); same-tree leaf proximity',
    'global_correction': 'sum(y-p0)/(1+successful-original-query-count)',
    'identity_groups': 'transitive canonical + stored accepted V7 bit/affine/combined normalized identities',
    'identity_scope': 'within-cohort; group exclusion does not copy labels between RTL representations',
    'exclusion': 'all memberships of every queried identity group within its family episode',
    'weighting': 'equal original-formula rows within program; equal programs within family; equal primary families',
    'primary': 'local_residual minus frozen unqueried MAE at budget3 on identical cases',
    'missing_policy': 'null complete-family macro if any declared primary program is exhausted',
    'zero_rule': 'public original generic gate count zero forces all adapter outputs zero',
    'bounds': 'nonnegative points only; no calibrated upper bounds or population CI',
    'new_fits': 0, 'new_labels': 0, 'dynamic_acquisition': False,
}


def canonical(value):
    return parse_formula(value).canonical()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('Nonnegative integer required: ' + name)
    return value


def point(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('Finite nonnegative point required')
    return float(value)


def identity_groups(records):
    """Union shared originals/accepted identities; never rerun normalization."""
    by_formula = {}
    tokens = {}
    evidence = {}
    for record in records:
        formula = canonical(record['formula'])
        if formula in by_formula:
            raise ValueError('Duplicate feature formula')
        by_formula[formula] = record
        tokens[formula] = {formula}
        evidence[formula] = []
        for mode in ('bit', 'affine', 'combined'):
            value = record.get('v7_modes', {}).get(mode)
            if value is None:
                continue
            if canonical(value['original_formula']) != formula:
                raise ValueError('Stored normalization original differs')
            status = value['metadata']['status']
            # A timeout/fallback supplies no accepted equivalence, even if an
            # unused normalized field happens to match another original.
            if status == 'accepted':
                normalized = canonical(value['normalized_formula'])
                tokens[formula].add(normalized)
                evidence[formula].append({'mode': mode, 'normalized_formula': normalized,
                                          'stored_mode_sha256': digest_json(value)})
    parent = {formula: formula for formula in by_formula}

    def find(formula):
        while parent[formula] != formula:
            parent[formula] = parent[parent[formula]]
            formula = parent[formula]
        return formula

    owner = {}
    for formula in sorted(by_formula):
        for token in sorted(tokens[formula]):
            if token in owner:
                a, b = find(formula), find(owner[token])
                parent[max(a, b)] = min(a, b)
            else:
                owner[token] = formula
    members = defaultdict(list)
    for formula in sorted(by_formula):
        members[find(formula)].append(formula)
    ledger, index = [], {}
    for formulas in sorted(members.values()):
        group = digest_json(formulas)
        ledger.append({'group_id': group, 'formulas': formulas,
                       'accepted_normalization_evidence': {f: evidence[f] for f in formulas}})
        index.update({formula: group for formula in formulas})
    return index, ledger


def leaf_kernel(leaf_ids):
    """Compare leaf IDs only at the same tree position; no labels/scaling."""
    leaves = np.asarray(leaf_ids)
    if (leaves.ndim != 2 or min(leaves.shape) < 1 or leaves.dtype.kind not in 'iu'
            or np.any(leaves < 0)):
        raise ValueError('Nonempty nonnegative integer leaf matrix required')
    # Row-pair loop avoids materializing an N x N x tree_count tensor.
    return np.asarray([[float(np.mean(a == b)) for b in leaves] for a in leaves])


def public_rows(rows, programs, predictions):
    declared = {}
    for program in programs:
        name, family = program['benchmark'], program['family']
        if not isinstance(name, str) or not name or not isinstance(family, str) or not family or name in declared:
            raise ValueError('Unique named programs/families required')
        if type(program['primary_family']) is not bool:
            raise ValueError('Boolean primary-family role required')
        trace = integer(program['traceTotalInstructions'], 'trace instructions')
        if trace == 0:
            raise ValueError('Positive complete trace denominator required')
        declared[name] = {'benchmark': name, 'family': family,
                          'primary_family': program['primary_family'], 'traceTotalInstructions': trace}
    roles = defaultdict(set)
    for program in declared.values():
        roles[program['family']].add(program['primary_family'])
    if any(len(role) != 1 for role in roles.values()) or not any(p['primary_family'] for p in declared.values()):
        raise ValueError('Consistent family roles and primary families required')
    points, identities = {}, set()
    for prediction in predictions:
        identity = prediction['benchmark'], prediction['candidate_id']
        if identity in identities or prediction.get('upper_lut4') is not None:
            raise ValueError('Unique point-only predictions required')
        identities.add(identity)
        points[identity] = (canonical(prediction['formula']), point(prediction['predicted_lut4']))
    clean, seen, formula_points, program_formulas = [], set(), {}, set()
    for row in rows:
        name, candidate = row['benchmark'], row['candidate_id']
        if name not in declared or not isinstance(candidate, str) or not candidate:
            raise ValueError('Declared candidate identity required')
        program = declared[name]
        if (any(row[k] != program[k] for k in ('family', 'primary_family', 'traceTotalInstructions'))
                or type(row['primary_family']) is not bool or type(row['traceTotalInstructions']) is not int):
            raise ValueError('Row/program metadata differs')
        formula = canonical(row['formula'])
        identity = name, candidate
        if identity in seen or (name, formula) in program_formulas or identity not in points or points[identity][0] != formula:
            raise ValueError('Unique complete candidate/prediction coverage required')
        seen.add(identity)
        program_formulas.add((name, formula))
        p0 = points[identity][1]
        if formula in formula_points and formula_points[formula] != p0:
            raise ValueError('Shared original formula point differs')
        formula_points[formula] = p0
        saved = integer(row['overlapSafeSaved'], 'saved instructions')
        if saved > program['traceTotalInstructions']:
            raise ValueError('Savings exceed trace instructions')
        clean.append({**program, 'candidate_id': candidate, 'formula': formula,
                      'overlapSafeSaved': saved, 'runs': integer(row['runs'], 'runs')})
    if seen != set(points) or {r['benchmark'] for r in clean} != set(declared):
        raise ValueError('Every declared program must have a complete nonempty pool')
    return sorted(clean, key=lambda r: (r['benchmark'], r['formula'], r['candidate_id'])), list(sorted(declared.values(), key=lambda p: p['benchmark'])), formula_points


def query_schedule(rows, base_points):
    """Fixed cap64 feasible-merit, with family-shared unique-original cost."""
    pools = defaultdict(list)
    for row in rows:
        pools[row['benchmark']].append(row)

    def order(row):
        p0 = base_points[row['formula']]
        tail = (-row['overlapSafeSaved'], row['formula'], row['candidate_id'])
        return (0, *tail) if p0 <= 64 else (1, p0 - 64, *tail)

    pools = {name: sorted(pool, key=order) for name, pool in pools.items()}
    schedule, attempted = [], set()
    while len(schedule) < max(BUDGETS):
        changed = False
        for name in sorted(pools):
            remaining = [r for r in pools[name] if r['formula'] not in attempted]
            if not remaining:
                continue
            chosen = remaining[0]
            attempted.add(chosen['formula'])
            schedule.append({'query_index': len(schedule) + 1, 'benchmark': name,
                             'candidate_id': chosen['candidate_id'], 'formula': chosen['formula']})
            changed = True
            if len(schedule) == max(BUDGETS):
                break
        if not changed:
            break
    return schedule


def exclusion(prepared, episode, budget):
    if budget not in BUDGETS:
        raise ValueError('Only budgets1/3/5 are declared')
    prefix = episode['schedule'][:budget]
    queried = {r['formula'] for r in prefix}
    groups = {prepared['formula_group'][f] for f in queried}
    pool = [r for r in prepared['rows'] if r['family'] == episode['family']]
    retained = [r for r in pool if prepared['formula_group'][r['formula']] not in groups]
    by_program = {}
    for name in episode['programs']:
        before = [r for r in pool if r['benchmark'] == name]
        after = [r for r in retained if r['benchmark'] == name]
        by_program[name] = {'original_formula_rows': len(before), 'unqueried_formula_rows': len(after),
                            'excluded_formula_rows': len(before) - len(after),
                            'unqueried_identity_groups': len({prepared['formula_group'][r['formula']] for r in after})}
    return {'budget': budget, 'charged_unique_original_queries': len(prefix),
            'budget_shortfall': budget - len(prefix), 'queried_formulas': sorted(queried),
            'excluded_group_ids': sorted(groups), 'excluded_identity_group_count': len(groups),
            'retained_formulas': sorted({r['formula'] for r in retained}),
            'original_membership_rows': len(pool), 'unqueried_membership_rows': len(retained),
            'excluded_membership_rows': len(pool) - len(retained),
            'original_unique_formulas': len({r['formula'] for r in pool}),
            'excluded_unique_formulas': len({r['formula'] for r in pool}) - len({r['formula'] for r in retained}),
            'unqueried_unique_original_formulas': len({r['formula'] for r in retained}),
            'unqueried_program_count': sum(v['unqueried_formula_rows'] > 0 for v in by_program.values()),
            'by_program': by_program,
            'missing_programs': sorted(n for n, counts in by_program.items() if counts['unqueried_formula_rows'] == 0),
            'family_complete': all(counts['unqueried_formula_rows'] > 0 for counts in by_program.values())}


def prepare(rows, programs, predictions, feature_records, leaf_ids, original_zero):
    clean, declared, base = public_rows(rows, programs, predictions)
    formulas = sorted(base)
    index, ledger = identity_groups(feature_records)
    if set(index) != set(formulas) or set(original_zero) != set(formulas) or any(type(v) is not bool for v in original_zero.values()):
        raise ValueError('Exact feature/group/zero coverage required')
    if any(original_zero[f] and base[f] != 0 for f in formulas):
        raise ValueError('Frozen original-zero point must be zero')
    if len(leaf_ids) != len(formulas):
        raise ValueError('Sorted formula/leaf alignment required')
    kernel = leaf_kernel(leaf_ids)
    value = {'schema': 'isaforge-v9-adaptation-public-v1', 'protocol': PROTOCOL,
             'formulas': formulas, 'rows': clean, 'programs': declared, 'base_points': base,
             'original_zero': dict(original_zero), 'formula_group': index, 'identity_groups': ledger,
             'leaf_ids': np.asarray(leaf_ids).tolist(), 'kernel': kernel.tolist(), 'episodes': []}
    for family in sorted({p['family'] for p in declared}):
        names = [p['benchmark'] for p in declared if p['family'] == family]
        episode = {'family': family, 'primary_family': next(p['primary_family'] for p in declared if p['family'] == family),
                   'programs': names, 'schedule': query_schedule([r for r in clean if r['family'] == family], base)}
        episode['prefixes'] = {str(b): exclusion(value, episode, b) for b in BUDGETS}
        value['episodes'].append(episode)
    return value


def forecast(prepared, episode, budget, revealed):
    """Only the charged prefix's revealed targets may enter this calculation."""
    state = exclusion(prepared, episode, budget)
    if set(revealed) != set(state['queried_formulas']):
        raise ValueError('Revealed labels must equal this episode/budget prefix exactly')
    indices = {f: i for i, f in enumerate(prepared['formulas'])}
    residuals = {}
    for formula, target in revealed.items():
        if target is not None:  # An attempted failure costs one but supplies no residual.
            residuals[formula] = integer(target, 'revealed original target') - prepared['base_points'][formula]
    global_delta = math.fsum(residuals.values()) / (1 + len(residuals))
    records = []
    for formula in state['retained_formulas']:
        weights = {f: prepared['kernel'][indices[formula]][indices[f]] for f in residuals}
        local_delta = math.fsum(weights[f] * residuals[f] for f in residuals) / (1 + math.fsum(weights.values()))
        p0 = prepared['base_points'][formula]
        zero = prepared['original_zero'][formula]
        records.append({'formula': formula, 'identity_group': prepared['formula_group'][formula],
                        'predictions': {'frozen': p0,
                                        'global_residual': 0. if zero else max(0., p0 + global_delta),
                                        'local_residual': 0. if zero else max(0., p0 + local_delta)},
                        'local_weight_sum': math.fsum(weights.values()),
                        'local_correction_lut4': local_delta, 'global_correction_lut4': global_delta})
    return {'family': episode['family'], 'primary_family': episode['primary_family'], 'budget': budget,
            'exclusion': state, 'successful_query_count': len(residuals),
            'failed_query_count': len(revealed) - len(residuals), 'forecasts': records}


def replay(prepared, query):
    """Sequential episode-local reveals; freeze lower-budget forecasts first."""
    snapshots, logs = [], []
    for episode in prepared['episodes']:
        revealed = {}
        for budget in BUDGETS:
            for request in episode['schedule'][len(revealed):budget]:
                formula = request['formula']
                target = query(episode['family'], formula)
                if target is not None:
                    integer(target, 'queried original target')
                revealed[formula] = target
                logs.append({'family': episode['family'], **request, 'target_lut4': target,
                             'status': 'failed' if target is None else 'revealed'})
            snapshots.append(forecast(prepared, episode, budget, revealed))
    return {'schema': 'isaforge-v9-adaptation-forecast-v1', 'snapshots': snapshots, 'query_log': logs}


def metrics(actual, predicted):
    if len(actual) != len(predicted):
        raise ValueError('Complete metric vectors required')
    if not actual:
        return None
    residual = [point(p) - integer(y, 'scoring target') for y, p in zip(actual, predicted)]
    positive = [(y, abs(e)) for y, e in zip(actual, residual) if y > 0]
    zero = [abs(e) for y, e in zip(actual, residual) if y == 0]
    return {'count': len(actual), 'mae_lut4': statistics.fmean(abs(e) for e in residual),
            'signed_bias_lut4': statistics.fmean(residual),
            'positive_target_count': len(positive),
            'positive_mape_percent': 100 * statistics.fmean(error / y for y, error in positive) if positive else None,
            'zero_target_count': len(zero), 'zero_mae_lut4': statistics.fmean(zero) if zero else None,
            'cap64_false_accept_count': sum(p <= 64 < y for y, p in zip(actual, predicted)),
            'cap64_false_reject_count': sum(y <= 64 < p for y, p in zip(actual, predicted))}


def validate_replay(prepared, replayed):
    """Authenticate every snapshot from exactly its own recorded reveal prefix."""
    expected_pairs = {(e['family'], b) for e in prepared['episodes'] for b in BUDGETS}
    snapshots = replayed.get('snapshots', [])
    pairs = [(s['family'], s['budget']) for s in snapshots]
    if len(pairs) != len(set(pairs)) or set(pairs) != expected_pairs:
        raise ValueError('Exactly one snapshot per declared family/budget required')
    expected_log_length = sum(len(e['schedule']) for e in prepared['episodes'])
    if len(replayed.get('query_log', [])) != expected_log_length:
        raise ValueError('Exact complete original query log required')
    indexed = {pair: s for pair, s in zip(pairs, snapshots)}
    for episode in prepared['episodes']:
        logs = [q for q in replayed['query_log'] if q['family'] == episode['family']]
        if len(logs) != len(episode['schedule']):
            raise ValueError('Exact family query schedule coverage required')
        for log, request in zip(logs, episode['schedule']):
            target = log['target_lut4']
            if target is not None:
                integer(target, 'logged target')
            expected = {'family': episode['family'], **request, 'target_lut4': target,
                        'status': 'failed' if target is None else 'revealed'}
            if log != expected:
                raise ValueError('Query log differs from frozen original schedule')
        for budget in BUDGETS:
            value = indexed[episode['family'], budget]
            formulas = [r['formula'] for r in value['forecasts']]
            if len(formulas) != len(set(formulas)):
                raise ValueError('Unique unqueried forecast rows required')
            for row in value['forecasts']:
                if set(row['predictions']) != set(ADAPTERS):
                    raise ValueError('Exactly the three fixed adapter predictions required')
                for prediction in row['predictions'].values():
                    point(prediction)
            revealed = {q['formula']: q['target_lut4'] for q in logs[:budget]}
            if value != forecast(prepared, episode, budget, revealed):
                raise ValueError('Unqueried forecast differs from its charged residual prefix')


def score(prepared, replayed, targets):
    """Full targets enter only after replay's unqueried forecasts are sealed."""
    validate_replay(prepared, replayed)
    if set(targets) != set(prepared['formulas']):
        raise ValueError('Complete exact original scoring-target coverage required')
    for value in targets.values():
        integer(value, 'scoring original target')
    if any(log['target_lut4'] is not None and targets[log['formula']] != log['target_lut4'] for log in replayed['query_log']):
        raise ValueError('Revealed query target differs from completed scoring target')
    output = []
    for snapshot in replayed['snapshots']:
        family, budget = snapshot['family'], snapshot['budget']
        episode = next(e for e in prepared['episodes'] if e['family'] == family)
        expected = exclusion(prepared, episode, budget)
        if snapshot['exclusion'] != expected:
            raise ValueError('Frozen group exclusion differs')
        forecasts = {r['formula']: r['predictions'] for r in snapshot['forecasts']}
        if set(forecasts) != set(expected['retained_formulas']):
            raise ValueError('Complete identical unqueried prediction coverage required')
        by_program, program_metrics = {}, {}
        for name in episode['programs']:
            formulas = [r['formula'] for r in prepared['rows'] if r['benchmark'] == name and r['formula'] in forecasts]
            program_metrics[name] = {adapter: metrics([targets[f] for f in formulas], [forecasts[f][adapter] for f in formulas])
                                      for adapter in ADAPTERS}
            by_program[name] = {adapter: program_metrics[name][adapter]['mae_lut4'] if formulas else None for adapter in ADAPTERS}
        complete = expected['family_complete']
        means = {adapter: statistics.fmean(by_program[n][adapter] for n in episode['programs']) if complete else None for adapter in ADAPTERS}
        output.append({'family': family, 'primary_family': episode['primary_family'], 'budget': budget,
                       'exclusion': expected, 'by_program_mae_lut4': by_program,
                       'by_program_metrics': program_metrics, 'family_mae_lut4': means,
                       'successful_query_count': snapshot['successful_query_count'],
                       'query_failures': snapshot['failed_query_count']})
    primary_families = sorted(e['family'] for e in prepared['episodes'] if e['primary_family'])
    aggregates = {}
    for budget in BUDGETS:
        selected = [r for r in output if r['primary_family'] and r['budget'] == budget]
        missing = sorted(set(primary_families) - {r['family'] for r in selected if r['exclusion']['family_complete']})
        means = {a: statistics.fmean(r['family_mae_lut4'][a] for r in selected) if not missing else None for a in ADAPTERS}
        paired = {r['family']: r['family_mae_lut4']['local_residual'] - r['family_mae_lut4']['frozen']
                  if r['exclusion']['family_complete'] else None for r in selected}
        aggregates[str(budget)] = {'primary_family_count': len(primary_families),
            'complete_primary_family_count': len(primary_families) - len(missing), 'missing_primary_families': missing,
            'family_macro_mae_lut4': means,
            'local_minus_frozen_mae_lut4': means['local_residual'] - means['frozen'] if not missing else None,
            'paired_family_differences_lut4': paired,
            'leave_one_family_out_difference_lut4': {f: statistics.fmean(paired[g] for g in primary_families if g != f)
                if not missing and len(primary_families) > 1 else None for f in primary_families}}
    return {'schema': 'isaforge-v9-consumed-development-evaluation-v1', 'protocol': PROTOCOL,
            'primary': aggregates['3'], 'by_budget': aggregates, 'family_results': output,
            'limitations': ['V8 is consumed development evidence; no independent confirmation.',
                           'Grouping controls exclusion, not metric weighting.',
                           'More paid labels do not guarantee improved MAE; no calibrated bound or population CI.',
                           'Acquisition is frozen; no dynamic selection benefit is tested.']}

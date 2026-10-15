#!/usr/bin/env python3
"""Independent V9 arithmetic audit; never imports the V9 implementation."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values)


def metric(actual, points):
    if not actual:
        return None
    residuals = [p-y for y, p in zip(actual, points)]
    positive = [(y, abs(e)) for y, e in zip(actual, residuals) if y > 0]
    zero = [abs(e) for y, e in zip(actual, residuals) if y == 0]
    return {'count': len(actual), 'mae_lut4': mean(abs(e) for e in residuals),
            'signed_bias_lut4': mean(residuals), 'positive_target_count': len(positive),
            'positive_mape_percent': 100 * mean(e/y for y, e in positive) if positive else None,
            'zero_target_count': len(zero), 'zero_mae_lut4': mean(zero) if zero else None,
            'cap64_false_accept_count': sum(p <= 64 < y for y, p in zip(actual, points)),
            'cap64_false_reject_count': sum(y <= 64 < p for y, p in zip(actual, points))}


def run(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    prep_dir, eval_dir = root/'prepared-attempt-0000', root/'evaluation-attempt-0000'
    manifest = load(prep_dir/'preparation.json')
    prepared = load(prep_dir/'public-prepared.json')
    evaluated = load(eval_dir/'evaluation.json')
    replay = load(eval_dir/'unqueried-forecasts.json')
    completion = load(eval_dir/'completion.json')
    bound = {str(p): sha(p) for p in [prep_dir/'preparation.json', prep_dir/'public-prepared.json',
             eval_dir/'evaluation.json', eval_dir/'unqueried-forecasts.json', eval_dir/'completion.json',
             eval_dir/'evaluation-start.json', Path(__file__).resolve()]}
    assert completion['complete'] is True
    assert sha(eval_dir/'evaluation.json') == completion['evaluation_sha256']
    assert sha(eval_dir/'unqueried-forecasts.json') == completion['forecast_sha256']
    for entry in manifest['files']:
        path = (prep_dir/entry['path']).resolve()
        assert sha(path) == entry['sha256'], path
        bound[str(path)] = entry['sha256']
    assert sha(prep_dir/'public-prepared.json') == manifest['public_payload']['sha256']
    for path, digest in completion['source_and_input_sha256'].items():
        assert sha(path) == digest, path
        bound[path] = digest
    labels_path = next(Path(p) for p in bound if Path(p).name == 'labels.json')
    labels = {r['formula']: r['lut4_count'] for r in load(labels_path)}
    assert set(labels) == set(prepared['formulas'])
    leaves = np.asarray(prepared['leaf_ids'])
    assert leaves.shape == (146, 300)
    # Corresponding tree columns only; no production leaf-kernel routine.
    kernel = np.asarray([np.count_nonzero(leaves == row, axis=1)/leaves.shape[1] for row in leaves])
    assert np.array_equal(kernel, np.asarray(prepared['kernel']))
    indices = {f: i for i, f in enumerate(prepared['formulas'])}
    base = prepared['base_points']
    snapshot_index = {(s['family'], s['budget']): s for s in replay['snapshots']}
    assert len(snapshot_index) == len(replay['snapshots']) == len(prepared['episodes'])*3
    family_metrics, influence, forecasts_checked = {}, [], 0
    for episode in prepared['episodes']:
        family = episode['family']
        rows = [r for r in prepared['rows'] if r['family'] == family]
        # Independently rebuild the fixed round-robin schedule from public data.
        pools = {name: [r for r in rows if r['benchmark'] == name] for name in episode['programs']}
        for name in pools:
            pools[name].sort(key=lambda r: (0, -r['overlapSafeSaved'], r['formula'], r['candidate_id'])
                if base[r['formula']] <= 64 else (1, base[r['formula']]-64, -r['overlapSafeSaved'], r['formula'], r['candidate_id']))
        schedule, seen = [], set()
        while len(schedule) < 5:
            added = False
            for name in sorted(pools):
                available = [r for r in pools[name] if r['formula'] not in seen]
                if not available:
                    continue
                row = available[0];seen.add(row['formula'])
                schedule.append({'query_index': len(schedule)+1, 'benchmark': name,
                                 'candidate_id': row['candidate_id'], 'formula': row['formula']})
                added = True
                if len(schedule) == 5:
                    break
            if not added:
                break
        assert schedule == episode['schedule']
        logs = [q for q in replay['query_log'] if q['family'] == family]
        assert len(logs) == len(schedule)
        for log, request in zip(logs, schedule):
            assert {k: log[k] for k in request} == request
            assert log['status'] == 'revealed' and log['target_lut4'] == labels[log['formula']]
        for budget in (1, 3, 5):
            support = logs[:budget]
            group_ids = {prepared['formula_group'][q['formula']] for q in support}
            remaining = [r for r in rows if prepared['formula_group'][r['formula']] not in group_ids]
            remaining_formulas = sorted({r['formula'] for r in remaining})
            snapshot = snapshot_index[family, budget]
            assert snapshot['exclusion'] == episode['prefixes'][str(budget)]
            assert snapshot['exclusion']['retained_formulas'] == remaining_formulas
            assert snapshot['exclusion']['charged_unique_original_queries'] == len(support)
            assert snapshot['exclusion']['unqueried_membership_rows'] == len(remaining)
            actual_forecasts = {r['formula']: r for r in snapshot['forecasts']}
            assert len(actual_forecasts) == len(snapshot['forecasts'])
            assert set(actual_forecasts) == set(remaining_formulas)
            predicted = {}
            residuals = [q['target_lut4']-base[q['formula']] for q in support]
            global_delta = math.fsum(residuals)/(1+len(residuals))
            for formula in remaining_formulas:
                weights = [float(kernel[indices[formula], indices[q['formula']]]) for q in support]
                denominator = 1+math.fsum(weights)
                local_delta = math.fsum(k*r for k, r in zip(weights, residuals))/denominator
                zero = prepared['original_zero'][formula]
                values = {'frozen': base[formula],
                          'global_residual': 0. if zero else max(0., base[formula]+global_delta),
                          'local_residual': 0. if zero else max(0., base[formula]+local_delta)}
                assert actual_forecasts[formula]['predictions'] == values
                assert actual_forecasts[formula]['local_correction_lut4'] == local_delta
                assert actual_forecasts[formula]['global_correction_lut4'] == global_delta
                assert actual_forecasts[formula]['local_weight_sum'] == math.fsum(weights)
                predicted[formula] = values;forecasts_checked += 1
                if budget == 3:
                    influence.append({'family': family, 'formula': formula, 'actual_lut4': labels[formula],
                        'predictions': values, 'original_zero': zero, 'local_correction_lut4': local_delta,
                        'effective_point_change_lut4': values['local_residual']-base[formula],
                        'query_influence': [{'formula': q['formula'], 'residual_lut4': r, 'same_tree_proximity': k,
                                            'contribution_lut4': k*r/denominator} for q, r, k in zip(support, residuals, weights)]})
            published = next(v for v in evaluated['family_results'] if v['family'] == family and v['budget'] == budget)
            program_metrics = {}
            for name in episode['programs']:
                formulas = [r['formula'] for r in remaining if r['benchmark'] == name]
                program_metrics[name] = {adapter: metric([labels[f] for f in formulas], [predicted[f][adapter] for f in formulas])
                                         for adapter in ('frozen', 'global_residual', 'local_residual')}
            assert program_metrics == published['by_program_metrics']
            complete = all(v['frozen'] is not None for v in program_metrics.values())
            means = {adapter: mean(v[adapter]['mae_lut4'] for v in program_metrics.values()) if complete else None
                     for adapter in ('frozen', 'global_residual', 'local_residual')}
            assert means == published['family_mae_lut4']
            family_metrics[family, budget] = means
    aggregates = {}
    primary = sorted(e['family'] for e in prepared['episodes'] if e['primary_family'])
    for budget in (1, 3, 5):
        means = {adapter: mean(family_metrics[f, budget][adapter] for f in primary)
                 for adapter in ('frozen', 'global_residual', 'local_residual')}
        differences = {f: family_metrics[f, budget]['local_residual']-family_metrics[f, budget]['frozen'] for f in primary}
        assert means == evaluated['by_budget'][str(budget)]['family_macro_mae_lut4']
        assert differences == evaluated['by_budget'][str(budget)]['paired_family_differences_lut4']
        assert means['local_residual']-means['frozen'] == evaluated['by_budget'][str(budget)]['local_minus_frozen_mae_lut4']
        assert {f: mean(differences[g] for g in primary if g != f) for f in primary} == evaluated['by_budget'][str(budget)]['leave_one_family_out_difference_lut4']
        aggregates[str(budget)] = means
    assert evaluated['primary'] == evaluated['by_budget']['3']
    worst = sorted(influence, key=lambda r: -abs(r['predictions']['frozen']-r['actual_lut4']))[:12]
    for path, expected in bound.items():
        assert sha(path) == expected, path
    report = {'schema': 'independent-v9-development-audit-v1', 'status': 'passed',
        'auditor_source_sha256': sha(__file__), 'source_and_input_sha256': bound,
        'same_tree_kernel_shape': list(kernel.shape), 'kernel_exact_match': True,
        'forecasts_independently_recomputed': forecasts_checked,
        'forecast_values_and_diagnostics_exact_match': True, 'all_program_metrics_exact_match': True,
        'all_family_and_budget_metrics_exact_match': True, 'comparison_tolerance': 0,
        'all_completion_bindings_unchanged': True, 'primary_budget': 3,
        'family_macro_mae_lut4_by_budget': aggregates, 'charged_query_log': replay['query_log'],
        'primary_query_influence': influence, 'largest_primary_frozen_errors_at_budget3': worst,
        'new_fits': 0, 'new_measurements': 0, 'new_feature_extractions': 0,
        'scope': 'Independent arithmetic recomputation of consumed development evidence, not independent confirmation.'}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False);stream.write('\n')
    print(json.dumps({'status': report['status'], 'forecasts_checked': forecasts_checked, 'report': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)

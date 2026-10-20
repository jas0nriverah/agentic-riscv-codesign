"""Replay the existing bounded selector on a verified automatic workload.

No new model, native jobs, or cross-workload claims. The evaluator keeps the
oracle labels; policies receive features and only their charged observations.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics

from . import codesign as c
from .codesign_audit import stable
from .workload_audit import import_automatic


def compare(root):
    root = Path(root)
    imported = import_automatic(root)
    rows = imported['rows']
    plan = c.unseal(root / 'plan.json')
    c.require(len(rows) == 6, 'This checkpoint uses the frozen six-candidate comparison')
    c.require(all(r['correctness_verified'] for r in rows), 'Unverified candidate')
    c.require(len({r['area_cap'] for r in rows}) == 1, 'Inconsistent area cap')
    for key in ('comparison_budgets', 'comparison_seeds', 'bootstrap', 'max_added_lut4'):
        c.require(plan['configuration'][key] == c.CONFIG[key], 'Comparison protocol changed')
    # Explicitly strip names, oracle ranks, costs, and all other target outcomes
    # before constructing any policy interface.
    keys = {'candidate_id', 'benchmark', 'formula', *c.FEATURE_COLUMNS}
    public = [{k: r[k] for k in keys} for r in rows]
    report = c.comparison(public, rows, rows[0]['area_cap'])
    report['context_id'] = plan['context_id']
    report['protocol_status'] = 'Development replay after collection; policy parameters and pool were fixed in the collection plan. Not a prospective held-out test.'
    report['baseline_setup_seconds'] = c.unseal(root / 'measurements/baseline/measurement.json')['elapsed_seconds']
    report['oracle_candidate_seconds'] = sum(r['measurement_seconds'] for r in rows)
    report['historical_speedup_training_seconds'] = 0.0
    report['collection_native_commands'] = imported['audit']['native_commands']
    report['collection_native_seconds'] = imported['audit']['native_seconds']
    report['new_native_evaluations_in_replay'] = 0
    report['missing_comparators'] = ['PicoRV32 latency/timing-aware merit', 'constrained expected improvement',
                                     'cost-aware acquisition', 'held-out-workload regression/ranking', 'LLM selection agent']
    labels = {r['candidate_id']: r for r in rows}
    for result in report['results']:
        best, elapsed, curve = 1.0, 0.0, []
        for index, identity in enumerate(result['measured_candidate_ids'], 1):
            row = labels[identity]
            elapsed += row['measurement_seconds']
            if row['area'] <= row['area_cap'] and row['timing_feasible']:
                best = max(best, row['speedup'])
            curve.append({'paid_evaluations': index, 'candidate_id': identity,
                          'recorded_measurement_seconds': elapsed, 'best_feasible_speedup': best,
                          'regret': report['oracle_speedup'] - best})
        c.require(best == result['best_speedup'] and elapsed == result['measured_cost_seconds'], 'Cost/endpoint mismatch')
        result['measurement_cost_curve'] = curve
        result['model_fit_and_predict_seconds'] = sum(e['fit_and_predict_seconds'] for e in result['prediction_events'])
    report['summary'] = []
    for budget in c.CONFIG['comparison_budgets']:
        for policy in c.POLICIES:
            subset = [r for r in report['results'] if r['budget'] == budget and r['policy'] == policy]
            report['summary'].append({'budget': budget, 'policy': policy, 'seeds': len(subset),
                                      'mean_best_speedup': statistics.mean(r['best_speedup'] for r in subset),
                                      'mean_regret': statistics.mean(r['regret'] for r in subset),
                                      'oracle_hits': sum(r['regret'] == 0 for r in subset),
                                      'mean_recorded_measurement_seconds': statistics.mean(r['measured_cost_seconds'] for r in subset)})
    report['limitations'] += ['The six candidates were shortlisted by instruction-saving merit; results do not cover the other 15 executable formulas.',
                              'A time curve reuses recorded serial evaluation durations; it is not a fresh policy wall-clock experiment.',
                              'All six pass the declared +128 LUT4 and 12 MHz limits. This pool does not test difficult feasibility prediction.',
                              'No historical training labels were supplied. Neither zero-shot transfer nor workload generalization was tested.']
    return report


def stable_report(report):
    # Timing is reported, but recomputation cannot reproduce host scheduling.
    result = stable(report)
    for row in result['results']:
        row.pop('model_fit_and_predict_seconds', None)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args(argv)
    output = args.root / 'selection-report.json'
    result = compare(args.root)
    if args.verify:
        c.require(stable_report(result) == stable_report(c.unseal(output)), 'Selection replay differs')
    else:
        c.require(not output.exists(), 'Preserve the previous replay; use --verify or a new run directory')
        c.seal(output, result)
    print({'policy_seed_budget_outcomes': len(result['results']), 'new_native_jobs': 0,
           'budget_three': [r for r in result['summary'] if r['budget'] == 3]})


if __name__ == '__main__': main()

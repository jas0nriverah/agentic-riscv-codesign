"""Diagnose consumed measurements and frozen predictions without fitting models.

Factor reweighting is analysis only. Observed-area rankings are privileged
diagnostics and are omitted whenever a target has unknown hardware outcomes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import itertools
import math
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge.features import FEATURE_COLUMNS

SOURCE = 'scripts/analyze_model_readiness.py'
COLUMNS = tuple(k for k in FEATURE_COLUMNS if k not in ('runs', 'places', 'saved', 'saved_percent'))
CORPUS = 'results/2026-10-21-six-workload-corpus/corpus.json'
INPUT_ROOTS = ('results/2026-10-21-six-workload-corpus',
               'results/2026-10-20-budget-campaign/selection',
               'results/2026-10-21-sha256-selection')
TARGETS = dict(edn='results/2026-10-20-budget-campaign/selection/embench-edn',
               ud='results/2026-10-20-budget-campaign/selection/embench-ud',
               sha256='results/2026-10-21-sha256-selection/model')
ORIGINAL = tuple('embench-'+s for s in ('crc32', 'aha-mont64', 'edn', 'huffbench',
                                      'matmult-int', 'nettle-aes', 'nettle-sha256', 'wikisort'))
MODES = ('full', 'no_duration', 'no_duration_variance', 'no_timing', 'oracle_area_diagnostic')


def probability_below(mean, std, bound):
    return float(mean <= bound) if std <= 1e-12 else .5*math.erfc(-(bound-mean)/std/math.sqrt(2))


def describe(row):
    return {k: row[k] for k in ('candidate_id', 'formula')}


def known_hardware(row):
    return (row.get('status', 'success') == 'success'
            and all(row.get(k) is not None for k in
                    ('area_delta_lut4', 'routed_fmax_min_mhz', 'device_fits')))


def first_query_rankings(public, estimates, labels, cap):
    """Reweight the original seed-zero first query; never simulate paid updates."""
    ordered = list(public)
    random.Random(0).shuffle(ordered)
    missing = [r['candidate_id'] for r in public if not known_hardware(labels[r['candidate_id']])]
    result = {}
    for mode in MODES:
        if mode == 'oracle_area_diagnostic' and missing:
            result[mode] = dict(ranking=None, unavailable_candidate_ids=missing,
                               reason='Unknown hardware outcomes; missing area is not infeasibility.')
            continue
        def score(row):
            p = estimates[row['candidate_id']]
            area = probability_below(p['area_delta_lut4_mean'], p['area_delta_lut4_std'], cap)
            timing = probability_below(-p['routed_fmax_min_mhz_mean'], p['routed_fmax_min_mhz_std'], -12)
            variance = 0 if mode == 'no_duration_variance' else .5*p['log_measurement_seconds_std']**2
            duration = 1 if mode == 'no_duration' else math.exp(max(-700, min(700, -p['log_measurement_seconds_mean']+variance)))
            if mode == 'no_timing': timing = 1
            if mode == 'oracle_area_diagnostic': area = float(labels[row['candidate_id']]['area_delta_lut4'] <= cap)
            analytic = row['latency_features']['estimated_speedup']
            return (max(0, analytic-1)*area*timing*p['device_fit_probability']*duration, analytic)
        result[mode] = dict(ranking=[describe(r) | dict(score=list(score(r)))
                                    for r in sorted(ordered, key=score, reverse=True)])
    return result


def corpus_metrics(corpus):
    rows = corpus['rows']; groups = defaultdict(list); formulas = defaultdict(list)
    for row in rows:
        groups[row['workload_group']].append(row); formulas[row['formula']].append(row)
    result = dict(successful_rows=len(rows), workload_groups=len(groups),
        group_counts=dict(sorted(Counter(r['workload_group'] for r in rows).items())),
        failed_classes=dict(sorted(Counter(r['failure_class'] for r in corpus['failed_attempts']).items())),
        failed_attempts=len(corpus['failed_attempts']),
        reference_censored_attempts=sum(r['reference_censored'] for r in corpus['failed_attempts']),
        original_named_programs=list(ORIGINAL), measured_original_programs=sorted(set(groups) & set(ORIGINAL)),
        measured_added_programs=sorted(set(groups)-set(ORIGINAL)), unmeasured_original_programs=sorted(set(ORIGINAL)-set(groups)),
        cycle_delta_equals_analytic_rows=sum(r['baseline_cycles']-r['candidate_cycles'] == r['latency_features']['estimated_saved_cycles'] for r in rows),
        all_speedups_above_one=all(r['speedup'] > 1 for r in rows),
        all_device_fit=all(r['device_fits'] for r in rows), all_timing_feasible=all(r['timing_feasible'] for r in rows),
        minimum_routed_fmax_mhz=min(r['routed_fmax_min_mhz'] for r in rows),
        baseline_lut4_values=sorted({r['area']-r['area_delta_lut4'] for r in rows}),
        hardware_features=list(COLUMNS), constant_hardware_fields=[k for k in COLUMNS if len({r[k] for r in rows}) == 1],
        nonzero_operation_types=[k for k in COLUMNS if k.startswith('op_') and any(r[k] != 0 for r in rows)],
        exact_descriptor_collisions_different_formulas=[], same_formula_cross_context=[], group_summary=[])
    for a, b in itertools.combinations(rows, 2):
        if a['formula'] != b['formula'] and all(a[k] == b[k] for k in COLUMNS):
            result['exact_descriptor_collisions_different_formulas'].append({key: describe(r) | dict(workload=r['workload_group'], area_delta_lut4=r['area_delta_lut4']) for key, r in (('a', a), ('b', b))})
    for formula, group in formulas.items():
        if len({r['benchmark'] for r in group}) > 1:
            result['same_formula_cross_context'].append(dict(formula=formula,
                rows=[describe(r) | {k: r[k] for k in ('workload_group', 'area_delta_lut4', 'routed_fmax_min_mhz', 'measurement_seconds')} for r in group],
                area_delta_range=[min(r['area_delta_lut4'] for r in group), max(r['area_delta_lut4'] for r in group)]))
    for workload, group in sorted(groups.items()):
        context = corpus['contexts'][group[0]['benchmark']]
        result['group_summary'].append(dict(workload=workload, rows=len(group), baseline_cycles=group[0]['baseline_cycles'],
            compiler_flags=context['compiler_flags'], stack_bytes=context['stack_bytes'],
            area_delta_range=[min(r['area_delta_lut4'] for r in group), max(r['area_delta_lut4'] for r in group)],
            duration_range=[min(r['measurement_seconds'] for r in group), max(r['measurement_seconds'] for r in group)],
            timer_scope_values=sorted({r['measurement_timer_scope'] for r in group})))
    return result


def target_metrics(public, history, predictions, report):
    pred = next(p for p in predictions if p['seed'] == 0)
    labels = {e['candidate_id']: e['observation'] for run in report['runs'] for e in run['events'] if 'observation' in e}
    c.require(set(labels) == {r['candidate_id'] for r in public}, 'Complete recorded attempted pool required')
    estimates = {p['candidate_id']: p for p in pred['hardware']}
    scales = {k: statistics.pstdev(r[k] for r in history) or 1 for k in COLUMNS}
    proxy = statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in history)
    result = dict(historical_fit_rows=len(history), history_max_abs_constant_std=scales['max_abs_constant'],
        heuristic_median_lut_per_tree_op=proxy, public_candidates=[], first_query_factor_rankings={},
        actual_seed0_paths={}, paid_area_updates=[], diagnostics=report['diagnostics'])
    for row in public:
        identity = row['candidate_id']; p = estimates[identity]; actual = labels[identity]
        distance = lambda other: math.sqrt(sum(((row[k]-other[k])/scales[k])**2 for k in COLUMNS))
        nearest = min(history, key=distance)
        result['public_candidates'].append(describe(row) | dict(actual_area_delta_lut4=actual.get('area_delta_lut4'),
            actual_speedup=actual.get('speedup'), actual_seconds=actual['measurement_seconds'],
            gp_area_mean=p['area_delta_lut4_mean'], gp_area_std=p['area_delta_lut4_std'],
            gp_area_probability_at64=probability_below(p['area_delta_lut4_mean'], p['area_delta_lut4_std'], 64),
            gp_duration_median_seconds=math.exp(p['log_measurement_seconds_mean']),
            heuristic_area=proxy*row['tree_op_count'], nearest_history=describe(nearest) | dict(
                area_delta_lut4=nearest['area_delta_lut4'], standardized_distance=distance(nearest))))
    for cap in (32, 64, 128):
        result['first_query_factor_rankings'][str(cap)] = first_query_rankings(public, estimates, labels, cap)
        runs = [r for r in report['runs'] if r['seed'] == 0 and r['area_delta_lut4_cap'] == cap]
        result['actual_seed0_paths'][str(cap)] = {r['policy']: r['curve'] for r in runs}
        for run in runs:
            if run['policy'] != 'hybrid_gp_adapt': continue
            for event in run['events']:
                if event['action'] != 'acquire': continue
                values = []
                for p in event['hardware_predictions']:
                    actual = labels[p['candidate_id']]; std = p['area_delta_lut4_std']
                    error = actual.get('area_delta_lut4')
                    error = None if error is None else error-p['area_delta_lut4_mean']
                    values.append(describe(actual) | dict(gp_area_mean=p['area_delta_lut4_mean'], gp_area_std=std,
                        actual_area_delta_lut4=actual.get('area_delta_lut4'), area_error=error,
                        standardized_area_error=error/std if error is not None and std > 0 else None,
                        standardized_error_note='Unknown area or zero predictive standard deviation.' if error is None or std == 0 else None))
                result['paid_area_updates'].append(dict(area_cap=cap, charged_before_query=event['charged_before_query'],
                    chosen_id=event['candidate_id'], acquisition_score=event['score'], estimates=values))
    return result


def analyze(output):
    output = Path(output).resolve()
    c.require(not output.exists(), 'Use a fresh analysis output directory')
    c.require(not any(output.is_relative_to(ROOT/p) for p in INPUT_ROOTS),
              'Keep analysis outside frozen selector inputs')
    inputs = {}
    def load(name):
        value = c.unseal(ROOT/name); inputs[name] = c.sha(ROOT/name)
        return value
    corpus = load(CORPUS)
    metrics = dict(schema='isaforge-model-readiness-analysis-v1',
        scope='Consumed-data diagnosis only; no new selector, fitting, native measurement or prospective validation.',
        factor_note='Seed-zero initial ranking reweighting only. Paid updates are recorded events, not counterfactual refits.',
        corpus=corpus_metrics(corpus), targets={}, new_native_jobs=0, model_fits=0)
    for target, folder in TARGETS.items():
        values = [load(folder+'/'+name+'.json') for name in ('public', 'history', 'predictions', 'report')]
        metrics['targets'][target] = dict(frozen_folder=folder, **target_metrics(*values))
    rankings = [cap for target in metrics['targets'].values() for cap in target['first_query_factor_rankings'].values()]
    ids = lambda cap, mode: [r['candidate_id'] for r in cap[mode]['ranking']]
    metrics['arithmetic_ablation_summary'] = {mode+'_complete_initial_ranking_unchanged': all(ids(cap, 'full') == ids(cap, mode) for cap in rankings)
                                            for mode in ('no_duration', 'no_duration_variance', 'no_timing')}
    metrics['provenance'] = dict(input_sha256=inputs, source_bindings={name: c.sha(ROOT/name) for name in
        (SOURCE, 'isaforge/codesign.py', 'isaforge/features.py')})
    output.mkdir(parents=True)
    c.seal(output/'metrics.json', metrics)
    c.seal(output/'manifest.json', {p.name: c.sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze(args.output)
    print(dict(successful_rows=result['corpus']['successful_rows'], targets=list(result['targets']), model_fits=0, new_native_jobs=0))


if __name__ == '__main__': main()

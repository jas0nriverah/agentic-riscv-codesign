"""Read-only diagnosis of consumed labels and the sealed bitcount GP.

Reconstructs an existing posterior; never fits an estimator, changes a policy,
or launches native work. Outputs must be fresh and outside sealed results.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import runpy
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    return json.loads((ROOT / path).read_text())


def cut(row):
    return (row['baseline_cycles'] - row['candidate_cycles']) / row['baseline_cycles']


def summarize(rows, failures):
    caps = {}
    for cap in (32, 64, 128):
        feasible = [r for r in rows if r['correctness_verified'] and r['device_fits']
                    and r['routed_fmax_min_mhz'] >= 12 and r['area_delta_lut4'] <= cap]
        caps[str(cap)] = dict(verified_feasible=len(feasible),
            best_verified_cycle_reduction_percent=100 * max([0.] + [cut(r) for r in feasible]),
            at_least_half_percent_candidates=sum(cut(r) >= .005 for r in feasible))
    return dict(verified_rows=len(rows), caps=caps,
        reference_censored=any(f.get('reference_censored', False) for f in failures),
        source_groups=sorted({r['workload_group'] for r in rows}),
        contexts=sorted({r['benchmark'] for r in rows}))


def analyze():
    import numpy as np

    bindings = json.loads((HERE / 'input-bindings.json').read_text())
    for name, expected in bindings.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound input/source differs: ' + name)
    # The original independent diagnostic uses repository-relative inputs.
    if Path.cwd().resolve() != ROOT:
        raise ValueError('Run from the repository root')
    stream = io.StringIO()
    with redirect_stdout(stream):
        gp = runpy.run_path(str(HERE / 'posterior-diagnostic.py'))
    assert gp['digest'](gp['matrix'](gp['train']).tolist()) == gp['s']['feature_matrix_sha256']
    mean_error = max(abs(gp['mu'][i] - gp['pred'][r['candidate_id']]['area_delta_lut4_mean'])
                     for i, r in enumerate(gp['public']))
    std_error = max(abs(gp['std'][i] - gp['pred'][r['candidate_id']]['area_delta_lut4_std'])
                    for i, r in enumerate(gp['public']))
    assert mean_error < 1e-10 and std_error < 1e-10
    assert np.linalg.eigvalsh(gp['cov']).min() > -1e-10
    # Numerical reconstruction tolerance is not an exclusion/tolerance on any
    # frozen scientific endpoint, paid outcome, prediction or native duration.
    corpus = load('results/2026-10-22-twelve-source-corpus/corpus.json')
    rows, failures = corpus['rows'], corpus['failed_attempts']
    assert len(rows) == 99 and len(failures) == 3 and corpus['total_candidate_attempts'] == 102
    assert all(r['baseline_cycles'] - r['candidate_cycles'] ==
               r['latency_features']['estimated_saved_cycles'] for r in rows)
    sources, contexts = defaultdict(list), defaultdict(list)
    for row in rows:
        sources[row['workload_group']].append(row)
        contexts[row['benchmark']].append(row)
    source_summary = {name: summarize(rs, [f for f in failures if f['workload_group'] == name])
                      for name, rs in sorted(sources.items())}
    context_summary = {name: summarize(rs, [f for f in failures if f['benchmark'] == name])
                       for name, rs in sorted(contexts.items())}
    families = Counter(r['candidate_family'] for r in rows)
    cross_source_families = defaultdict(set)
    for row in rows:
        cross_source_families[row['candidate_family']].add(row['workload_group'])
    names = [gp['names'][r['candidate_id']] for r in gp['public']]
    posterior = dict(feature_dimensions=len(gp['s']['columns']), training_rows=len(gp['train']),
        initial_mean_reconstruction_max_abs_lut=float(mean_error),
        initial_std_reconstruction_max_abs_lut=float(std_error),
        area_prior_mean=gp['area']['mean'], area_prior_scale=gp['area']['scale'],
        observation_alpha=1e-4, alpha_times_output_scale_std=float(np.sqrt(gp['noise'])),
        candidates=names, correlation=gp['corr'].tolist(),
        prior_variance_fraction=np.diag(gp['cov']).tolist(),
        nearest_history_kernel_similarity=gp['ks'].max(axis=1).tolist(),
        initial_area_mae_lut=float(abs(gp['err']).mean()),
        initial_area_signed_residual_mean_lut=float(gp['err'].mean()),
        initial_area_residual_range_lut=[float(gp['err'].min()), float(gp['err'].max())],
        qualification='Analytic reconstruction of the already sealed model, not a new estimator fit or selector trajectory. Conditional comparisons are diagnostics, not a proposed policy evaluation.')
    primary = list(csv.DictReader((ROOT / 'results/2026-10-22-bitcount-report/primary.csv').open()))
    primary = [r for r in primary if r['budget'] == '3']
    assert len(primary) == 14
    baseline = load('results/2026-10-22-bitcount-report/baseline.json')
    candidates = list(csv.DictReader((ROOT / 'results/2026-10-22-bitcount-report/candidates.csv').open()))
    conditional_timing = [dict(candidate=r['candidate'], added_lut4=int(r['added_lut4']),
        primary_fixed_clock_speedup=float(r['speedup']),
        conditional_baseline_fmax_penalized_speedup=float(r['speedup']) * min(1.,
            float(r['min_fmax_mhz']) / baseline['min_fmax_mhz'])) for r in candidates]
    data = dict(schema='isaforge-oct25-consumed-selection-diagnosis-v1',
        measured_input_commit='c4bca4b0ecc7314067e49b490995997e4c4b987b',
        input_sha256=bindings, corpus=summarize(rows, failures),
        independent_source_count=len(sources), context_count=len(contexts),
        charged_attempts=corpus['total_candidate_attempts'],
        candidate_ledger_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_summary=source_summary, context_summary=context_summary,
        literal_formulas=len({r['formula'] for r in rows}), normalized_families=len(families),
        singleton_families=sum(v == 1 for v in families.values()),
        families_spanning_sources=sum(len(v) > 1 for v in cross_source_families.values()),
        cycle_reduction_median_percent=statistics.median(100 * cut(r) for r in rows),
        benefit_at_least_half_percent=sum(cut(r) >= .005 for r in rows),
        primary_sources_below_half_percent=sum(v['caps']['64']['best_verified_cycle_reduction_percent'] < .5
                                              for v in source_summary.values()),
        runs_median=statistics.median(r['runs'] for r in rows),
        runs_once=sum(r['runs'] == 1 for r in rows), runs_at_most_ten=sum(r['runs'] <= 10 for r in rows),
        all99_latency_residual_max=0,
        minimum_routed_fmax_mhz=min(r['routed_fmax_min_mhz'] for r in rows),
        timing_failure_labels_at_12mhz=sum(not r['timing_feasible'] for r in rows),
        device_failure_labels=sum(not r['device_fits'] for r in rows),
        bitcount_primary_three_query=primary, initial_gp=posterior,
        conditional_timing_diagnostic=conditional_timing,
        conditional_timing_note='Consumed-data arithmetic under a hypothetical baseline-Fmax clock: speedup multiplied by min(1,candidate_min_Fmax/baseline_min_Fmax). Routed estimates are not measured execution at that clock. No frequency increase is credited. Primary 12MHz outcomes are unchanged; this is not a new native experiment or policy result.',
        all_sources_consumed=True, new_native_jobs=0, new_estimator_fit_calls=0,
        new_selector_trajectories=0, model_promoted=False)
    return data, stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT / 'results'):
        parser.error('Fresh output outside sealed results/ required')
    data, transcript = analyze()
    output.mkdir(parents=True)
    (output / 'analysis.json').write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')
    (output / 'posterior.txt').write_text(transcript)
    print(json.dumps(dict(output=str(output), labels=99, sources=12,
        exact_calibrated_cycle_deltas=99, initial_gp_dimensions=37,
        new_native_jobs=0, new_estimator_fit_calls=0, new_selector_trajectories=0)))


if __name__ == '__main__':
    main()

"""Render the fixed twelve-policy fresh-source experiment from audited results."""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge import factorized_selection_experiment as e
from scripts.report_budget_campaign import LABELS, table, write_csv
from scripts.report_guarded_selection import candidate_rows
from scripts.report_feasible_benefit import first_reference_points

CAMPAIGN = ROOT/'results/2026-10-21-jfdctint-campaign'
SELECTION = ROOT/'results/2026-10-21-jfdctint-selection'
PREREG = ROOT/'results/2026-10-21-jfdctint-preregistration'


def build(campaign, selection, prereg, output):
    campaign, selection, prereg, output = map(lambda path: Path(path).resolve(), (campaign, selection, prereg, output))
    c.require(not output.exists() and not any(output.is_relative_to(path) for path in (campaign, selection, prereg)),
              'Fresh report outside frozen evidence required')
    case = e.authenticate(selection)
    report, audit = c.unseal(selection/'report.json'), c.unseal(campaign/'audit.json')
    outcomes = c.unseal(campaign/'outcomes.json')
    c.require(report['protocol_sha256'] == c.sha(selection/'protocol.json') and
              report['outcomes_sha256'] == c.digest(outcomes) and report['native_audit_digest'] == c.digest(audit),
              'Report/evidence bindings differ')
    e.checked_outcomes(case['public'], outcomes, audit)
    labels = {**LABELS, e.controls.POLICY: 'Feasible-benefit XGBoost', e.POLICY: 'Factorized feasibility XGBoost'}
    c.require(set(labels) == set(case['protocol']['policies']), 'All twelve policies required')
    references = {cap: max([1.0]+[row['speedup'] for row in outcomes if b._feasible(row, cap, 12)]) for cap in e.AREA_CAPS}
    endpoints = []
    for row in report['summary']:
        points = [run['curve'][row['budget']-1] for run in report['runs']
                  if run['cap'] == row['cap'] and run['policy'] == row['policy']]
        c.require(len(points) == 5, 'Five dependent repetitions required')
        reference = references[row['cap']]
        endpoints.append(dict(**row, reference_speedup=reference,
            reference_kind='best verified; full pool censored' if report['reference_censored'] else 'measured fixed-pool oracle',
            reference_hits=sum(point['best_speedup'] == reference for point in points),
            improving_design_discoveries=sum(reference > 1 and point['best_speedup'] == reference for point in points)))
    primary = []
    for policy, label in labels.items():
        runs = [run for run in report['runs'] if run['cap'] == 64 and run['policy'] == policy]
        hits = first_reference_points(runs, references[64])
        points = {row['budget']: row for row in endpoints if row['cap'] == 64 and row['policy'] == policy}
        primary.append(dict(policy=policy, label=label,
            query1_mean_speedup=points[1]['mean_best_speedup'], query2_mean_speedup=points[2]['mean_best_speedup'],
            query3_mean_speedup=points[3]['mean_best_speedup'], query3_mean_gap=points[3]['mean_gap_to_best_verified'],
            query3_mean_ledger_seconds=points[3]['mean_target_measurement_seconds'],
            query3_mean_outer_operation_seconds=points[3]['mean_target_outer_operation_seconds'],
            query3_known_infeasible_attempts=points[3]['mean_known_infeasible_attempts'],
            reference_hits=points[3]['reference_hits'], reference_is_baseline=references[64] == 1,
            first_reference_query_min=min((point['budget'] for point in hits if point is not None), default=None),
            first_reference_query_max=max((point['budget'] for point in hits if point is not None), default=None),
            mean_first_reference_ledger_seconds=statistics.mean(point['target_measurement_seconds'] for point in hits)
                if all(point is not None for point in hits) else None))
    candidates = candidate_rows(audit)
    for row in candidates:
        row['outer_operation_seconds'] = report['candidate_outer_operation_seconds'][row['candidate_id']]
    predictions = [dict(seed=seed['seed'], **row) for seed in case['predictions']
                   for cap in e.AREA_CAPS for row in seed['by_cap'][str(cap)]]
    reliability = []
    gp_report = c.unseal(selection/'controls11/model/report.json')
    for cap in e.AREA_CAPS:
        xgb = [row['feasibility_brier'] for row in report['feasibility_diagnostics'] if row['cap'] == cap]
        gp = [cap_row['mean_squared_feasibility_probability_error']
              for row in gp_report['diagnostics'] if row['model'] == 'hardware_gp_zero_shot'
              for cap_row in row['feasibility_brier'] if cap_row['area_delta_lut4_cap'] == cap]
        reliability.append(dict(cap=cap, factorized_feasibility_brier=statistics.mean(xgb) if xgb and xgb[0] is not None else None,
            unchanged_gp_feasibility_brier=statistics.mean(gp) if gp else None,
            known_candidates=sum(row.get('status', 'success') == 'success' for row in outcomes),
            calibrated=False))
    support = c.unseal(selection/'support-diagnostics.json')
    costs = case['protocol']['cost_provenance']
    fits = c.unseal(selection/'feasibility-costs.json')
    before = c.unseal(prereg/'baseline/before.json')
    baseline_cycles = case['public'][0]['latency_features']['baseline_cycles']
    fmt = lambda value: '' if value is None or value == '' else f'{value:.9f}'
    secs = lambda value: '' if value is None or value == '' else f'{value:.3f}'
    text = ['# Held-out BEEBS DCT: factorized selection test',
        'The complete models, public features and predictions were pushed at '
        '`a2004f9540a2355c7b2fec31cacfa8fe8f153bb4` before six serial one-attempt measurements. '
        'This source had no earlier candidate outcomes. The original full input and all64 coefficient checks are unchanged. '
        'It is BEEBS, not Embench. The fixed primary endpoint is best verified feasible speedup at three attempts, +64LUT4 and12MHz.',
        '## Actual processor outcomes',
        f'Baseline:{baseline_cycles:,} cycles,1,653 LUT4, minimum routed Fmax68.493149MHz. '
        'PicoRV32 RV32I/ILP32, original8KiB synchronous RAM, checked3072-byte program limit,128-byte guard and4992-byte stack reservation. '
        'All area/Fmax results are integrated synthesis and three routing seeds, not physical-board measurements.',
        table([['Candidate', 'Cycles', 'Speedup', 'Added LUT4', 'Minimum Fmax MHz', 'Correctness', 'Ledger s', 'Outer operation s'], ['---']*8]+
            [[row['candidate'], row['cycles'], fmt(row['speedup']), row['added_lut4'], fmt(row['min_fmax_mhz']),
              row['correctness'], secs(row['charged_wall_seconds']), secs(row['outer_operation_seconds'])] for row in candidates]),
        'Measured cycles remain distinct from public analytic estimates. The candidates.csv file contains both and their residuals. '
        'The fixed pool contains six rank-stratified candidates from29 eligible formulas; its oracle does not cover every legal formula.',
        '## Equal-budget primary comparison',
        table([['Policy', 'Query1 speedup', 'Query2', 'Query3', 'Gap at3', 'Ledger s at3', 'Outer s at3', 'Optimum hits /5'], ['---']*8]+
            [[row['label'], fmt(row['query1_mean_speedup']), fmt(row['query2_mean_speedup']), fmt(row['query3_mean_speedup']),
              fmt(row['query3_mean_gap']), secs(row['query3_mean_ledger_seconds']), secs(row['query3_mean_outer_operation_seconds']),
              row['reference_hits']] for row in primary]),
        'All policies see the same historical information and candidate pool, and pay for every attempted query before receiving its outcome. '
        'Five seeds repeat bootstrap/tie choices; they are dependent, not five independent workloads. '
        'The complete physical pool is collected for a separate oracle and cooperative paid replay. '
        'This is not a live adaptive hardware search. Three-query policies still spend all three attempts after finding the optimum. '
        'A baseline-only reference is available at query0/time0, not an improved-design discovery. Full caps32/64/128 and all budgets are in endpoints.csv.',
        table([['Added LUT4 cap', 'Best verified speedup', 'Complete declared-pool reference'], ['---']*3]+
            [[cap, fmt(reference), not report['reference_censored']] for cap, reference in references.items()]),
        '## What changed in the model',
        f"{case['protocol']['historical_available_rows']} historical labels are available; "
        f"{case['protocol']['historical_fitting_rows']} candidates from "
        f"{len(case['protocol']['historical_postfilter_groups'])} sources remain after identical family exclusions. "
        'One fixed20-member XGBoost binary ensemble predicts hardware feasibility conditional on verified successful execution. '
        'Its score multiplies nonnegative public calibrated cycle savings divided by baseline cycles. '
        'It does not relearn the already exact historical cycle deltas, predict correctness, or replace paid acceptance checks. '
        'Features, cap replicas,80trees/depth2 and seeds remain fixed; the changed objective/target is the declared experiment. '
        'No setting was chosen using these new outcomes.',
        'This follows the separation of objective and constraints in '
        '[Gardner et al.,2014,§3.1–3.2](https://proceedings.mlr.press/v32/gardner14.pdf). '
        'It is not a reproduction of constrained expected improvement: there is no GP objective posterior or expected-improvement acquisition in the new static policy.',
        table([['Cap', 'New feasibility Brier', 'Existing GP Brier', 'Known candidates'], ['---']*4]+
            [[row['cap'], fmt(row['factorized_feasibility_brier']), fmt(row['unchanged_gp_feasibility_brier']), row['known_candidates']]
             for row in reliability]),
        'Brier error measures hardware feasibility only on successfully verified candidates. '
        'Unknown failures are excluded from that denominator and remain charged. Bootstrap spread is estimator disagreement; '
        'scores are uncalibrated. Comparing binary labels to score quantiles would not establish90% predictive coverage. '
        'Cap-monotonicity violations and training-range flags are diagnostics, with no abstention threshold or post-label reranking.',
        '## Cost accounting and limits',
        f"Historical cost:{costs['historical_training_available']['total_candidate_attempts']} attempts / "
        f"{costs['historical_training_available']['total_candidate_wall_seconds']:.3f} recorded candidate seconds, "
        'including two recorded invalid executions and one infrastructure-censored unknown. All three remain outside fitting. '
        f"New pool:{audit['charged_candidate_attempts']} attempts / {audit['candidate_wall_seconds']:.3f}ledger seconds; "
        f"{sum(report['candidate_outer_operation_seconds'].values()):.3f}outer-operation seconds. "
        f"Baseline ledger:{audit['baseline_wall_seconds']:.3f}s. "
        f"{audit['native_command_count']} native commands:{audit['native_command_seconds']:.3f}s. These scopes overlap and must not be summed. "
        'Outer-operation time includes evaluator creation, discovery authentication, hardware work and lock close, excluding interpreter startup; '
        'the raw collection-driver records also retain complete subprocess wall time. All policy times are sums of observed paid operations, not a measured adaptive-search lifetime.',
        'New model fitting / all-cap prediction seconds by seed: '+', '.join(
            f"{row['fitting_seconds']:.6f}/{row['all_cap_prediction_seconds']:.6f}" for row in fits)+'. '
        'Eleven-control fitting, setup/calibration, failed qualification and report/replay host time remain separate. '
        'Previous duration scopes and shared-history costs preclude an unqualified end-to-end time claim.',
        'One additional source is a useful transfer test, not evidence of broad ML superiority. '
        'The short DCT workload and restricted candidate shapes limit absolute improvements and architectural diversity. '
        'Preserve heuristic wins, ties, regressions and poor calibration. No further variant is selected from these now-consumed labels. '
        'Joint instruction sets and an independent-source reliability test remain future work.']
    output.mkdir(parents=True)
    for name, rows in (('candidates.csv', candidates), ('primary.csv', primary), ('endpoints.csv', endpoints),
                       ('feasibility.csv', reliability), ('predictions.csv', predictions)):
        write_csv(output/name, rows)
    c.seal(output/'summary.json', dict(primary=primary, references=references, feasibility=reliability,
        support=support, classifier_fit_prediction_costs=fits, superiority_established=False))
    (output/'results.md').write_text('\n\n'.join(text)+'\n')
    c.seal(output/'provenance.json', dict(source_sha256=c.sha(Path(__file__)), report_sha256=c.sha(selection/'report.json'),
        audit_sha256=c.sha(campaign/'audit.json'), new_native_jobs=0))
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(candidates=len(candidates), policies=len(primary), endpoint_summaries=len(endpoints), new_native_jobs=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=CAMPAIGN)
    parser.add_argument('--selection', type=Path, default=SELECTION)
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from scripts.reproduce_jfdctint import replay
    replay(campaign=args.campaign, selection=args.selection, prereg=args.preregistration)
    print(build(args.campaign, args.selection, args.preregistration, args.output))


if __name__ == '__main__':
    main()

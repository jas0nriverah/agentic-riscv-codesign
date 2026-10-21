"""Report the frozen model comparison on the disjoint measured SHA256 pool."""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasible_benefit_experiment import POLICY, authenticate
from isaforge.feasible_benefit import decision_utility
from isaforge.speedup_corpus import family
from scripts.report_budget_campaign import LABELS, table, write_csv
from scripts.report_guarded_selection import candidate_rows

CAMPAIGN = ROOT/'results/2026-10-21-disjoint-sha256-campaign'
SELECTION = ROOT/'results/2026-10-21-disjoint-sha256-selection'


def first_reference_points(runs, reference):
    if reference == 1.0:
        return [dict(budget=0,target_measurement_seconds=0.0) for _ in runs]
    return [next((point for point in run['curve'] if point['best_speedup']==reference),None)
            for run in runs]


def build(campaign, selection, output):
    campaign, selection, output = map(lambda p:Path(p).resolve(), (campaign,selection,output))
    c.require(not output.exists(), 'Fresh derived report directory required')
    c.require(not output.is_relative_to(selection), 'Keep derived report outside frozen selection')
    case = authenticate(selection)
    report = c.unseal(selection/'report.json')
    c.require(report['protocol_sha256'] == c.sha(selection/'protocol.json'), 'Report protocol differs')
    audit = c.unseal(campaign/'audit.json')
    outcomes = c.unseal(campaign/'outcomes.json')
    c.require(outcomes == audit['outcomes'] and report['outcomes_sha256'] == c.digest(outcomes),
              'Measured outcomes/report differ')
    c.require(audit['attempt_collection_complete'] and not audit['unattempted'], 'Complete charged pool required')
    candidates = candidate_rows(audit)
    labels = dict(LABELS, **{POLICY:'Feasible-benefit XGBoost'})
    c.require(set(labels) == {run['policy'] for run in report['runs']}, 'All eleven policies required')
    endpoints = []
    for row in report['summary']:
        cap, policy, budget = row['cap'],row['policy'],row['budget']
        reference = max([1.0]+[r['speedup'] for r in outcomes if b._feasible(r,cap,12)])
        runs = [run for run in report['runs'] if run['cap']==cap and run['policy']==policy]
        c.require(len(runs)==5 and {run['seed'] for run in runs}==set(range(5)), 'Five dependent repetitions required')
        points = [run['curve'][budget-1] for run in runs]
        endpoints.append(dict(**row,reference_speedup=reference,
            reference_kind='best verified; full pool censored' if report['reference_censored'] else 'measured declared-pool oracle',
            reference_hits=sum(p['best_speedup']==reference for p in points),
            discovery_hits=sum(reference>1 and p['best_speedup']==reference for p in points)))
    primary = []
    for policy, label in labels.items():
        runs = [run for run in report['runs'] if run['cap']==64 and run['policy']==policy]
        reference = next(row['reference_speedup'] for row in endpoints if row['cap']==64)
        hits = first_reference_points(runs,reference)
        values = {row['budget']:row for row in endpoints if row['cap']==64 and row['policy']==policy}
        primary.append(dict(policy=policy,label=label,
            query1_mean_speedup=values[1]['mean_best_speedup'],
            query2_mean_speedup=values[2]['mean_best_speedup'],
            query3_mean_speedup=values[3]['mean_best_speedup'],
            query3_mean_gap=values[3]['mean_gap_to_best_verified'],
            query3_mean_measurement_seconds=values[3]['mean_target_measurement_seconds'],
            query3_reference_hits=values[3]['reference_hits'],
            query3_improving_design_discoveries=values[3]['discovery_hits'],
            reference_is_baseline=reference==1.0,
            first_reference_query_min=min((p['budget'] for p in hits if p),default=None),
            first_reference_query_max=max((p['budget'] for p in hits if p),default=None),
            mean_first_reference_seconds=statistics.mean(p['target_measurement_seconds'] for p in hits if p)
                if all(hits) else None,
            all_seeds_find_reference=all(p is not None for p in hits)))
    costs = case['protocol']['cost_provenance']
    original_corpus=c.unseal(ROOT/'results/2026-10-21-six-workload-corpus/corpus.json')
    old_sha=[row for row in original_corpus['rows'] if row['workload_group']=='embench-nettle-sha256']
    structural=lambda row:tuple(row[key] for key in b.STRUCTURAL_COLUMNS)
    diversity=dict(new_candidates=len(case['public']),new_source_workloads=0,
        distinct_new_pool_families=len({family(row['formula']) for row in case['public']}),
        candidates_with_family_seen_in_old_sha=sum(family(row['formula']) in
            {family(old['formula']) for old in old_sha} for row in case['public']),
        candidates_with_structural_vector_seen_in_old_sha=sum(structural(row) in
            {structural(old) for old in old_sha} for row in case['public']),
        original_corpus_families=len({family(row['formula']) for row in original_corpus['rows']}))
    utility_costs = c.unseal(selection/'utility-inference-costs.json')
    uncertainty=[]
    known=[row for row in outcomes if row.get('status','success')=='success']
    for cap in (32,64,128):
        per_seed=[]
        for prediction in case['predictions']:
            values={row['candidate_id']:row for row in prediction['by_cap'][str(cap)]}
            if known:
                per_seed.append(statistics.mean(
                    values[row['candidate_id']]['lower_saved_cycles_per_occurrence'] <= decision_utility(row,cap)
                    <= values[row['candidate_id']]['upper_saved_cycles_per_occurrence'] for row in known))
        uncertainty.append(dict(cap=cap,known_candidates=len(known),unknown_candidates=len(outcomes)-len(known),
            dependent_seed_count=len(case['predictions']),nominal_bootstrap_quantile_mass=.90,
            mean_observed_utility_coverage=statistics.mean(per_seed) if per_seed else None,
            calibrated_confidence=False))
    references = [dict(cap=cap,best_verified_speedup=max([1.0]+[
        r['speedup'] for r in outcomes if b._feasible(r,cap,12)]),
        complete=not report['reference_censored']) for cap in (32,64,128)]
    n = lambda value: '' if value is None else f'{value:.9f}'
    seconds = lambda value: '' if value is None else f'{value:.3f}'
    text = ['# Fresh-candidate test of budget-conditioned XGBoost',
        'Predictions, source-bound JSON ensembles and every control were committed before the six candidate attempts. '
        '**Scope: new candidates from consumed SHA256 source/input. This is not unseen-workload generalization.** '
        'The primary endpoint is best verified feasible speedup at three attempts, +64 LUT4 and12MHz. '
        'Five seeds repeat bootstrap/tie choices; they are not five independent workloads.',
        '## Actual processor measurements',
        'Baseline:26,135,630cycles,1,653LUT4. Correctness covers the recorded original full SHA input. '
        'Resources and Fmax are integrated synthesis/routing results, not board measurements.',
        table([['Candidate','Cycles','Speedup','Added LUT4','Minimum Fmax MHz','Correctness','Charged seconds'],['---']*7]+
            [[row['candidate'],row['cycles'],n(row['speedup']) if row['speedup']!='' else '',
              row['added_lut4'],seconds(row['min_fmax_mhz']) if row['min_fmax_mhz']!='' else '',
              row['correctness'],seconds(row['charged_wall_seconds'])] for row in candidates]),
        '## Equal-budget selection at +64 LUT4',
        table([['Policy','Query1 speedup','Query2','Query3','Query3 gap','Seconds at3','Reference hits /5'],['---']*7]+
            [[row['label'],n(row['query1_mean_speedup']),n(row['query2_mean_speedup']),
              n(row['query3_mean_speedup']),n(row['query3_mean_gap']),seconds(row['query3_mean_measurement_seconds']),
              row['query3_reference_hits']] for row in primary]),
        'All table entries average the same five dependent seeds. Full caps32/64/128 and budgets1/2/3 are in endpoints.csv. '
        'A baseline-only reference is already available at query0/time0; retaining it is not discovery of an improved design. '
        'Measured outcomes reach each policy only through its charged replay queries. The exhaustive reference is separate; '
        'the complete physical pool was collected serially, so these are prospective predictions followed by cooperative replay, not live adaptive native search.',
        f"Pool diversity: six new literal formulas cover{diversity['distinct_new_pool_families']} families, "
        f"and all{diversity['candidates_with_family_seen_in_old_sha']} candidates have a family already seen in the consumed SHA pool. "
        f"{diversity['candidates_with_structural_vector_seen_in_old_sha']} reproduce an old SHA31-feature vector exactly. "
        'Related families are excluded from fitting, but model development already consumed the old target families. '
        'New literal/feature values do not establish independent-family transfer.',
        table([['Added LUT4 cap','Best verified speedup','Complete declared pool'],['---']*3]+
            [[row['cap'],n(row['best_verified_speedup']),row['complete']] for row in references]),
        '## What the learned output means',
        'One fixed XGBoost ensemble predicts signed saved cycles per executed replacement when measured hardware is feasible under '
        'the cap/clock, and zero decision utility when it is not. A cap-relative historical area proxy is its one new context feature. '
        'Utility times public replacements divided by baseline cycles ranks feasible program savings. '
        'This output is distinct from measured speedup, calibrated feasibility probability and confidence. '
        'Candidate-level bootstrap cap replicas retain one candidate of weight, and related families are excluded identically across learned policies. '
        'The original speedup/ranking models remain unchanged. Negative outcomes and heuristic wins remain valid.',
        table([['Added LUT4 cap','Known candidates','Mean utility coverage of90% bootstrap range','Calibrated confidence'],['---']*4]+
            [[row['cap'],row['known_candidates'],n(row['mean_observed_utility_coverage']),False] for row in uncertainty]),
        'Coverage is for the signed feasible-utility target, averaged over dependent model seeds; '
        'it is not coverage of whole-program speedup and is not directly comparable with the old speedup intervals. '
        'Unknown failures are excluded from this diagnostic rather than assigned zero utility.',
        '## Costs and limits',
        f"Training availability:27 successful non-SHA labels plus3 failed historical attempts, "
        f"{costs['historical_training_available']['total_candidate_wall_seconds']:.3f} recorded candidate seconds; "
        f"{case['protocol']['historical_fitting_rows']} rows fit after family exclusions. "
        f"All36 previously consumed development attempts cost{costs['consumed_development']['candidate_wall_seconds']:.3f}seconds, "
        'including six old SHA labels excluded from fitting. Neither excluded labels nor model development are free.',
        f"The new native pool used{audit['charged_candidate_attempts']} charged attempts and{audit['candidate_wall_seconds']:.3f}ledger seconds. "
        f"Baseline ledger time:{audit['baseline_wall_seconds']:.3f}seconds. The native command timer overlaps these scopes. "
        f"Utility fit plus all-cap prediction time by seed:"+
        ', '.join(f"{row['fit_and_all_caps_prediction_seconds']:.6f}s" for row in utility_costs)+'. '
        'It is reported separately, not imputed as zero from a missing inference field. Replay host time is not native search lifetime. '
        'Old/new duration scopes and shared-history costs preclude an unqualified end-to-end time claim.',
        'Hardware cost is context dependent. Bootstrap intervals are uncalibrated; this experiment does not repair calibration or demonstrate broad ML superiority. '
        'Single-instruction results do not add across a selected set. Joint lowering/execution/area/timing must be measured together.']
    output.mkdir(parents=True)
    write_csv(output/'candidates.csv',candidates)
    write_csv(output/'endpoints.csv',endpoints)
    write_csv(output/'primary.csv',primary)
    write_csv(output/'utility-uncertainty.csv',uncertainty)
    c.seal(output/'summary.json',dict(scope=report['scope'],primary=primary,references=references,
        pool_diversity=diversity,utility_uncertainty=uncertainty,
        utility_fit_and_prediction_costs=utility_costs,superiority_established=False))
    (output/'results.md').write_text('\n\n'.join(text)+'\n')
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(Path(__file__)),
        report_sha256=c.sha(selection/'report.json'),audit_sha256=c.sha(campaign/'audit.json'),new_native_jobs=0))
    c.seal(output/'manifest.json',{path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(candidate_rows=len(candidates),endpoint_rows=len(endpoints),policies=len(primary),new_native_jobs=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--selection',type=Path,default=SELECTION)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from scripts.reproduce_disjoint_sha256 import replay
    replay(campaign=args.campaign,selection=args.selection)
    print(build(args.campaign,args.selection,args.output))


if __name__=='__main__':
    main()

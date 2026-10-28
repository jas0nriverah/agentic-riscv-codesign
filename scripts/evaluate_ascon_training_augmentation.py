#!/usr/bin/env python3
"""Retrospective, leakage-safe ablation of the three-row Ascon supplement.

The existing pairwise XGBoost ranker and factorized feasibility model are
unchanged. The only treatment is adding eligible, authenticated Ascon rows to
each target's historical fitting cohort. Predictions are sealed before the
script reopens private target outcomes for scoring. No native jobs are run.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b, codesign as c
from isaforge.ascon_training_supplement import OUTPUT as SUPPLEMENT, load as load_supplement
from isaforge.current_grouped_predictions import fit_current_grouped_predictions
from isaforge.grouped_agent_case import list_grouped_agent_targets, load_grouped_agent_case
from isaforge.speedup_corpus import family

AREA_CAP = 64
CLOCK_MHZ = 12.0
MODEL_SEED = 0
SCHEMA = 'isaforge-ascon-training-augmentation-ablation-v1'
MODEL_SOURCES = (
    'isaforge/current_grouped_predictions.py',
    'isaforge/grouped_agent_case.py',
    'isaforge/ascon_training_supplement.py',
    'isaforge/ranking.py',
    'isaforge/factorized_selection_experiment.py',
    'isaforge/feasibility_selection.py',
    'isaforge/model.py',
    'isaforge/features.py',
    'isaforge/budgeted_selection.py',
    'isaforge/codesign.py',
)


def _order(bundle, policy):
    rows = bundle['rows']
    if policy == 'pairwise_rank':
        return [row['candidate_id'] for row in sorted(rows, key=lambda row:
            (row['pairwise_rank_position'], row['candidate_id']))]
    return [row['candidate_id'] for row in sorted(rows, key=lambda row:
        (-row['factorized_decision_score'], row['candidate_id']))]


def _complete_prefix_result(order, outcomes, *, budget, area_cap, clock_mhz):
    attempted = order[:budget]
    feasible = [outcomes[identity] for identity in attempted
        if identity in outcomes and outcomes[identity].get('status', 'success') == 'success' and
        b._feasible(outcomes[identity], area_cap, clock_mhz) and
        outcomes[identity]['speedup'] > 1.0]
    best = min(feasible, key=lambda row: (-row['speedup'], row['area_delta_lut4'],
                                          row['candidate_id'])) if feasible else None
    return dict(budget=budget, attempted_ids=attempted,
        best_candidate_id=best['candidate_id'] if best else None,
        best_speedup=best['speedup'] if best else 1.0,
        best_cycle_reduction=(1.0-1.0/best['speedup']) if best else 0.0,
        best_area_delta_lut4=best['area_delta_lut4'] if best else None,
        best_routed_fmax_min_mhz=best['routed_fmax_min_mhz'] if best else None,
        correctness_verified=best['correctness_verified'] if best else None,
        failed_or_unresolved_attempts=sum(outcomes.get(identity, {}).get('status') == 'failed'
                                          for identity in attempted),
        infeasible_attempts=sum(identity in outcomes and
            outcomes[identity].get('status', 'success') == 'success' and
            not b._feasible(outcomes[identity], area_cap, clock_mhz) for identity in attempted))


def _aggregate_scored(scored, policy, budget):
    eligible = []
    for row in scored:
        if row['policy'] != policy or row['oracle_cycle_reduction'] is None:
            continue
        index = budget-1
        eligible.append(dict(target_workload_group=row['target_workload_group'],
            base={'cycle_reduction_regret':row['base']['curve'][index]['cycle_reduction_regret']},
            plus_ascon={'cycle_reduction_regret':row['plus_ascon']['curve'][index]['cycle_reduction_regret']}))
    by_group = defaultdict(list)
    for row in eligible:
        by_group[row['target_workload_group']].append(row)
    base = {group: sum(row['base']['cycle_reduction_regret'] for row in rows)/len(rows)
            for group, rows in by_group.items()}
    augmented = {group: sum(row['plus_ascon']['cycle_reduction_regret'] for row in rows)/len(rows)
                 for group, rows in by_group.items()}
    paired = sorted(set(base) & set(augmented))
    deltas = [augmented[group]-base[group] for group in paired]
    return dict(policy=policy, budget=budget, complete_contexts=len(eligible),
        independent_workload_groups=len(paired),
        context_macro_base_mean_regret=(sum(row['base']['cycle_reduction_regret'] for row in eligible)/len(eligible)
                                        if eligible else None),
        context_macro_augmented_mean_regret=(sum(row['plus_ascon']['cycle_reduction_regret'] for row in eligible)/len(eligible)
                                             if eligible else None),
        workload_macro_base_mean_regret=(sum(base.values())/len(base) if base else None),
        workload_macro_augmented_mean_regret=(sum(augmented.values())/len(augmented) if augmented else None),
        workload_macro_regret_delta_augmented_minus_base=(sum(deltas)/len(deltas) if deltas else None),
        workload_group_wins=sum(delta < -1e-12 for delta in deltas),
        workload_group_ties=sum(abs(delta) <= 1e-12 for delta in deltas),
        workload_group_losses=sum(delta > 1e-12 for delta in deltas),
        note='Consumed-data descriptive paired aggregates; correlated contexts within a workload are averaged before group comparison.')


def evaluate(output: Path):
    output = Path(output).resolve()
    c.require(not output.exists(), 'Use a fresh output directory; preserve prior evidence')
    supplement_rows = load_supplement(SUPPLEMENT, purpose='training')
    targets = list_grouped_agent_targets()
    output.mkdir(parents=True)
    protocol = dict(schema=SCHEMA,
        scope='retrospective consumed-data training augmentation ablation; no prospective claim',
        corpus_path='results/2026-10-26-lift-selection-corpus/corpus.json',
        corpus_sha256='901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef',
        screen_protocol_sha256='7eff9339c71619fdf55dd24b2681314ac0740906f8ffdd36c452b645f810de5c',
        ascon_supplement_path='results/2026-10-28-ascon-training-supplement-r1',
        ascon_supplement_sha256=c.sha(SUPPLEMENT/'supplement.json'),
        target_contexts=[dict(target_workload_group=row['target_workload_group'],
            target_benchmark=row['target_benchmark'], public_sha256=row['public_sha256'],
            candidate_count=row['candidate_count']) for row in targets],
        target_context_count=len(targets),
        target_workload_groups=sorted({row['target_workload_group'] for row in targets}),
        model_seed=MODEL_SEED, area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
        model_recipes=['XGBRanker objective=rank:pairwise', 'factorized feasibility XGBoost'],
        policies=['pairwise_rank', 'factorized_decision'], budgets=[1,2,3],
        augmentation_rule=('Append only authenticated supplement rows from a different target workload '
            'whose expression family is absent from the full held-out workload roster.'),
        historical_complete_failures_and_target_exclusions_preserved=True,
        target_outcome_access_during_fit=False, new_native_jobs=0, new_target_labels=0,
        promoted_model_versions=0,
        source_bindings={name:c.sha(ROOT/name) for name in MODEL_SOURCES})
    c.seal(output/'protocol.json', protocol)

    prepared = []
    prediction_artifact = []
    for target in targets:
        group, benchmark = target['target_workload_group'], target['target_benchmark']
        case = load_grouped_agent_case(group, benchmark)
        target_families = set(case['metadata']['target_formula_families'])
        eligible = [row for row in supplement_rows
                    if row['workload_group'] != group and family(row['formula']) not in target_families]
        arms = {}
        for arm, training in (('base', case['training']),
                              ('plus_ascon', case['training']+eligible)):
            bundle, metadata = fit_current_grouped_predictions(training, case['public'],
                target_workload_group=group,
                target_formula_families=case['metadata']['target_formula_families'],
                seed=MODEL_SEED, area_cap_lut4=AREA_CAP)
            arms[arm] = dict(bundle=bundle, metadata=metadata,
                training_rows=len(training), eligible_ascon_row_ids=[row['candidate_id'] for row in eligible],
                order_by_policy={policy:_order(bundle, policy)
                                 for policy in ('pairwise_rank','factorized_decision')})
        prepared.append(dict(target_workload_group=group, target_benchmark=benchmark,
            case_metadata=case['public_metadata'], arms=arms))
        prediction_artifact.append(dict(target_workload_group=group, target_benchmark=benchmark,
            public_sha256=case['public_metadata']['public_sha256'],
            training_ids_sha256=case['public_metadata']['training_ids_sha256'],
            target_formula_families=case['public_metadata']['target_formula_families'],
            eligible_ascon_row_ids=[row['candidate_id'] for row in eligible],
            arms={arm:dict(bundle=value['bundle'], metadata=value['metadata'],
                training_rows=value['training_rows'], eligible_ascon_row_ids=value['eligible_ascon_row_ids'],
                order_by_policy=value['order_by_policy']) for arm,value in arms.items()}))
    c.seal(output/'predictions.json', dict(schema=SCHEMA+'-predictions',
        protocol_sha256=c.sha(output/'protocol.json'), predictions=prediction_artifact,
        outcome_rows_in_prediction_artifact=0))

    # Only after every model output is durably sealed are private target outcomes
    # reloaded and used for the deterministic retrospective scorecard.
    scored = []
    for item in prepared:
        case = load_grouped_agent_case(item['target_workload_group'],item['target_benchmark'])
        reference_complete=case['metadata']['reference_complete'] is True
        feasible=[row for row in case['outcomes'].values()
            if row.get('status','success')=='success' and b._feasible(row,AREA_CAP,CLOCK_MHZ)
            and row['speedup']>1]
        oracle=max([1.0,*[row['speedup'] for row in feasible]]) if reference_complete else None
        oracle_reduction=(1.0-1.0/oracle) if oracle is not None else None
        for policy in ('pairwise_rank','factorized_decision'):
            result=dict(target_workload_group=item['target_workload_group'],
                target_benchmark=item['target_benchmark'],policy=policy,
                reference_complete=reference_complete,oracle_speedup=oracle,
                oracle_cycle_reduction=oracle_reduction)
            for arm,values in item['arms'].items():
                points=[]
                for budget in (1,2,3):
                    point=_complete_prefix_result(values['order_by_policy'][policy],case['outcomes'],
                        budget=budget,area_cap=AREA_CAP,clock_mhz=CLOCK_MHZ)
                    point['cycle_reduction_regret']=(max(0.,oracle_reduction-point['best_cycle_reduction'])
                        if oracle_reduction is not None else None)
                    points.append(point)
                result[arm]=dict(training_rows=values['training_rows'],
                    eligible_ascon_rows=values['eligible_ascon_row_ids'],curve=points,
                    model_fit_and_prediction_seconds=values['metadata']['model_fit_and_prediction_seconds'])
            scored.append(result)
    summary=[_aggregate_scored(scored,policy,budget)
             for policy in ('pairwise_rank','factorized_decision') for budget in (1,2,3)]
    report=dict(schema=SCHEMA+'-report',scope=protocol['scope'],
        protocol_sha256=c.sha(output/'protocol.json'),predictions_sha256=c.sha(output/'predictions.json'),
        scored_contexts=len(targets), independent_workload_groups=len(protocol['target_workload_groups']),
        supplement_training_rows=len(supplement_rows),
        target_outcome_reads='Only after the prediction artifact was sealed.',
        scorecard=scored,summary=summary,new_native_jobs=0,new_target_labels=0,
        limitations=[
            'All 122 historical outcomes were already consumed before this ablation; the report is retrospective.',
            'The three Ascon rows share one same-domain cryptographic source and add zero independent expression families.',
            'The nine unmeasured Ascon candidates remain unknown and are not used as negatives or an oracle.',
            'Context-level repeats within a workload are correlated; workload groups, not candidate rows, are the paired units.',
            'No external HLS area/latency labels are transferred to PicoRV32 whole-program outcomes.',
            'No model is promoted and the production/current grouped adapter continues to use the 122-label corpus.'])
    c.seal(output/'report.json',report)
    readme=_render_readme(protocol,report)
    (output/'README.md').write_text(readme)
    c.seal(output/'manifest.json',{path.relative_to(output).as_posix():c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()})
    print(dict(output=str(output),contexts=len(targets),workload_groups=len(protocol['target_workload_groups']),
        supplement_rows=len(supplement_rows),new_native_jobs=0,report_sha256=c.sha(output/'report.json')))
    return report


def _render_readme(protocol, report):
    lines=['# Ascon training augmentation ablation', '',
        'Consumed-data development analysis. It changes only the historical training cohort for two existing grouped XGBoost recipes; no model family, feature set, target, or hardware label changes.', '',
        f"- Target contexts: {report['scored_contexts']} across {report['independent_workload_groups']} workload groups.",
        f"- Authenticated Ascon training rows: {report['supplement_training_rows']} (three measured, nine unmeasured remain excluded).",
        '- Target holdout: full workload plus every expression family in that workload roster.',
        '- Area/timing decision constraint: +64 LUT4 and at least 12 MHz.',
        '- No native jobs, new target labels, or promoted model versions.', '',
        '| Model policy | Budget | Contexts | Base workload-macro regret | + Ascon regret | Paired workload wins / ties / losses |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in report['summary']:
        lines.append(f"| {row['policy']} | {row['budget']} | {row['complete_contexts']} | "
            f"{row['workload_macro_base_mean_regret']:.8f} | "
            f"{row['workload_macro_augmented_mean_regret']:.8f} | "
            f"{row['workload_group_wins']} / {row['workload_group_ties']} / {row['workload_group_losses']} |")
    lines.extend(['','The Ascon supplement does not change factorized-feasibility regret at any tested budget. Pairwise ranking changes one correlated context at B1 (a loss) and one at B3 (a win); other comparisons tie. These retrospective folds do not justify promotion or a claim that added data improves generalization.', '',
        'Reproduce with:', '', '```sh',
        '../work/audit-venv/bin/python scripts/evaluate_ascon_training_augmentation.py --output results/2026-10-28-ascon-training-ablation-reproduction',
        '```', '',
        'Predictions are sealed before target outcomes are reopened for scoring. The separate Ascon supplement remains training-only and cannot be loaded as a test pool or oracle.'])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    evaluate(args.output)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

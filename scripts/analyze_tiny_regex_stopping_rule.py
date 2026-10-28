#!/usr/bin/env python3
"""Retrospective shared-stopping diagnostic over the immutable tiny-regex r2 study.

No predictor, policy, model provider or hardware evaluator is imported or run.
The simulated decision sees only the prelabel public roster and outcomes from
its archived paid prefix. Oracle and residual audits happen after that decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
STUDY = 'results/2026-10-28-tiny-regex-c-selection-r2'
PREREG = 'results/2026-10-28-tiny-regex-c-selector-prereg-r5'
STUDY_MANIFEST_SHA256 = '61418b0f56626bd831223a9249159744d364996e3cfadf4a28510a041c368e37'
PREREG_MANIFEST_SHA256 = '5d65ad1a28490f3d30f8b8d5f7b07e0a0a2805f9b7e252cae9a545981247d6a0'
DEFAULT_OUTPUT = 'reports/2026-10-28-tiny-regex-stopping-rule-r1'
SOURCE = 'scripts/analyze_tiny_regex_stopping_rule.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def read(path):
    return json.loads(Path(path).read_text())


def authenticate(root, expected):
    root = Path(root).resolve()
    require(sha(root / 'manifest.json') == expected, 'Pinned evidence manifest changed')
    require((root / 'manifest.json.sha256').read_text().strip() == expected,
            'Manifest sidecar mismatch')
    inventory = read(root / 'manifest.json')
    require(isinstance(inventory, dict) and inventory, 'Nonempty evidence inventory required')
    for name, expected_file in inventory.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'Invalid evidence member: ' + name)
        require(sha(path) == expected_file, 'Evidence member hash mismatch: ' + name)
    return inventory


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Finite numeric value required')
    return value


def is_feasible(row, cap=64, clock=12):
    return (row.get('status', 'success') == 'success' and
            row.get('correctness_verified') is True and row.get('device_fits') is True and
            number(row['area_delta_lut4']) <= cap and
            number(row['routed_fmax_min_mhz']) >= clock)


def best_paid(rows, baseline, cap=64, clock=12):
    feasible = [row for row in rows if is_feasible(row, cap, clock) and
                row['baseline_cycles'] - row['candidate_cycles'] > 0]
    best = min(feasible, key=lambda row: (row['candidate_cycles'],
        row['area_delta_lut4'], row['candidate_id'])) if feasible else None
    saved = baseline - best['candidate_cycles'] if best else 0
    return dict(candidate_id=best['candidate_id'] if best else None,
        saved_cycles=saved, cycle_reduction=saved / baseline,
        speedup=baseline / (baseline - saved))


def simulate(public, order, release, *, budget, cap=64, clock=12):
    """Decide without inspecting outcomes outside the charged prefix.

    ``release`` is invoked only for the next archived action. Even its timing
    data stay hidden until dispatch. No oracle or remaining measured result is
    an input. Equal-benefit ties are safe only for the cycle-benefit objective,
    not for choosing the lowest-area design among tied speedups.
    """
    require(type(budget) is int and 1 <= budget <= 3, 'Use a one-to-three query allowance')
    identities = [row['candidate_id'] for row in public]
    require(len(set(identities)) == len(identities) and identities, 'Unique public roster required')
    require(len(set(order)) == len(order) and set(order) <= set(identities),
            'Archived order must contain unique public identities')
    baseline_values = {number(row['latency_features']['baseline_cycles']) for row in public}
    require(len(baseline_values) == 1, 'Common baseline required')
    baseline = next(iter(baseline_values))
    require(baseline > 0, 'Positive baseline required')
    estimates = {row['candidate_id']: number(row['latency_features']['estimated_saved_cycles'])
                 for row in public}
    paid, attempted, violations, snapshots = [], [], [], []
    horizon = min(budget, len(order))
    while True:
        incumbent = best_paid(paid, baseline, cap, clock)
        remaining = [identity for identity in identities if identity not in attempted]
        best_remaining = max((max(0, estimates[identity]) for identity in remaining), default=0)
        conditional = incumbent['saved_cycles'] >= best_remaining
        accepted = conditional and not violations
        snapshots.append(dict(charged_attempts=len(attempted),
            attempted_candidate_ids=list(attempted), incumbent=incumbent,
            remaining_candidate_ids=remaining,
            remaining_estimated_saved_cycles={identity: estimates[identity] for identity in remaining},
            maximum_remaining_estimated_saved_cycles=best_remaining,
            conditional_remaining_cycle_reduction_headroom=max(
                0, best_remaining - incumbent['saved_cycles']) / baseline,
            paid_assumption_violation_count=len(violations),
            conditional_dominance=conditional, stop=accepted,
            information_scope='frozen public estimates + this paid prefix only'))
        if accepted or len(attempted) == horizon:
            break
        identity = order[len(attempted)]
        attempted.append(identity)  # charge before the release callback
        row = release(identity)
        require(row['candidate_id'] == identity, 'Outcome identity mismatch')
        number(row['measurement_seconds'])
        require(row['measurement_seconds'] >= 0, 'Negative evaluation time')
        if row.get('status', 'success') == 'success':
            require(row['baseline_cycles'] == baseline, 'Outcome baseline differs')
            require(number(row['candidate_cycles']) > 0, 'Positive measured cycles required')
            residual = baseline - row['candidate_cycles'] - estimates[identity]
            if residual != 0:
                violations.append(dict(candidate_id=identity,
                    measured_minus_estimated_saved_cycles=residual))
        paid.append(row)
    return dict(actual_archived_queries_available=len(order), allowed_budget=budget,
        simulated_queries=len(attempted), attempted_candidate_ids=attempted,
        stopped_by_shared_rule=accepted,
        terminal_reason=('conditional_analytic_dominance' if accepted else
            'archived_agent_episode_ended' if horizon < budget else 'budget_exhausted'),
        incumbent=incumbent, snapshots=snapshots,
        paid_assumption_violations=violations,
        simulated_evaluation_seconds=sum(row['measurement_seconds'] for row in paid))


def analyze(root=ROOT):
    root = Path(root).resolve()
    study, prereg = root / STUDY, root / PREREG
    inventory = authenticate(study, STUDY_MANIFEST_SHA256)
    pre_inventory = authenticate(prereg, PREREG_MANIFEST_SHA256)
    require({'outcomes.json', 'study-report.json', 'factorized-policy-report.json',
             'agent/ledger.json'} <= inventory.keys(), 'Missing study input')
    require('inputs/public.json' in pre_inventory, 'Missing prelabel public features')
    public = read(prereg / 'inputs/public.json')
    before = read(prereg / 'preregistration.json')
    report = read(study / 'study-report.json')
    policies = read(study / 'factorized-policy-report.json')
    ledger = read(study / 'agent/ledger.json')
    require(report['preregistration_manifest_sha256'] == PREREG_MANIFEST_SHA256,
            'Study does not bind the pinned prelabel package')
    require(before['target_labels_read'] == before['target_labels_observed'] == 0 and
            before['candidate_attempts_before_fit'] == 0, 'Expected zero-label package')
    require(report['complete_measured_reference_pool'] is True and
            not report['reference_censored_candidates'], 'Complete uncensored oracle required')
    outcomes = {row['candidate_id']: row for row in read(study / 'outcomes.json')}
    require(len(outcomes) == len(public) == 12 and
            set(outcomes) == {row['candidate_id'] for row in public}, 'Exact twelve-candidate pool required')
    baseline = public[0]['latency_features']['baseline_cycles']
    public_by_id = {row['candidate_id']: row for row in public}
    outer = policies['candidate_outer_operation_seconds']
    runs = []
    for run in policies['runs']:
        if run['cap'] != 64:
            continue
        curve = run['curve']
        require([point['budget'] for point in curve] == [1, 2, 3], 'Complete archived B3 prefix required')
        order = curve[-1]['attempted_ids']
        require(len(order) == 3 and all(point['attempted_ids'] == order[:point['budget']]
                for point in curve), 'Archived curve is not one query-order prefix')
        acquisitions = [event['candidate_id'] for event in run['events'] if event['action'] == 'acquire']
        require(acquisitions == order, 'Acquisition events disagree with the archived query order')
        for point in curve:
            paid = [outcomes[identity] for identity in point['attempted_ids']]
            require(best_paid(paid, baseline)['speedup'] == point['best_speedup'],
                    'Archived best-so-far differs from measured outcomes')
            require(math.isclose(sum(row['measurement_seconds'] for row in paid),
                point['target_measurement_seconds'], rel_tol=1e-12, abs_tol=1e-9),
                'Archived evaluation duration differs')
        runs.append(dict(policy=run['policy'], seed=run['seed'],
            role='archived fixed-budget non-agent policy replay', order=order,
            source='factorized-policy-report.json'))
    require(len(runs) == 60 and len({(r['policy'], r['seed']) for r in runs}) == 60,
            'Expected twelve frozen policies across five dependent seeds')
    agent_events = [event for event in ledger['events'] if 'charged_attempt' in event]
    agent_order = [event['candidate_id'] for event in agent_events]
    require(len(agent_order) == 2 and agent_order == report['agent']['attempted_ids'] and
            ledger['status'] == 'finalized', 'Expected actual two-query agent episode')
    for event in agent_events:
        require(event['observation'] == outcomes[event['candidate_id']], 'Agent paid observation differs')
    # Authenticate the public estimates actually visible before agent outcomes.
    require(ledger['model_events'][0]['public_context']['candidates'] == public,
            'Agent initial public roster differs from preregistered estimates')
    runs.append(dict(policy='codex_chat_hybrid_agent', seed=0,
        role='one actual live relay episode; no third action is inferred',
        order=agent_order, source='agent/ledger.json'))

    analyses = []
    for run in runs:
        for budget in (1, 2, 3):
            released = []
            def release(identity):
                released.append(identity)
                return outcomes[identity]
            result = simulate(public, run['order'], release, budget=budget)
            require(released == result['attempted_candidate_ids'], 'Callback release escaped paid prefix')
            # The following retrospective scoring has no influence on stop decisions.
            original_ids = run['order'][:budget]
            original = best_paid([outcomes[identity] for identity in original_ids], baseline)
            oracle = best_paid(list(outcomes.values()), baseline)
            retained = result['incumbent']
            skipped = original_ids[result['simulated_queries']:]
            result.update(policy=run['policy'], seed=run['seed'], role=run['role'],
                action_source=STUDY + '/' + run['source'],
                archived_query_order=run['order'], actual_archived_prefix=original_ids,
                actual_prefix_queries=len(original_ids),
                actual_prefix_incumbent=original,
                actual_prefix_evaluation_seconds=sum(outcomes[i]['measurement_seconds'] for i in original_ids),
                measurements_saved_vs_actual_prefix=len(skipped),
                skipped_archived_candidate_ids=skipped,
                evaluation_seconds_saved_vs_actual_prefix=sum(outcomes[i]['measurement_seconds'] for i in skipped),
                outer_operation_seconds_saved_vs_actual_prefix=sum(outer[i] for i in skipped),
                actual_prefix_oracle_regret=oracle['cycle_reduction']-original['cycle_reduction'],
                simulated_oracle_regret=oracle['cycle_reduction']-retained['cycle_reduction'],
                missed_oracle_cycle_reduction=max(0, oracle['cycle_reduction']-retained['cycle_reduction']),
                stopping_induced_cycle_reduction_loss=max(
                    0, original['cycle_reduction']-retained['cycle_reduction']),
                missed_improvement_due_to_stopping=original['saved_cycles'] > retained['saved_cycles'],
                unmeasured_better_feasible_candidates_after_stop=[identity for identity, row in outcomes.items()
                    if result['stopped_by_shared_rule'] and
                    identity not in result['attempted_candidate_ids'] and is_feasible(row) and
                    baseline-row['candidate_cycles'] > retained['saved_cycles']],
                oracle_scoring_scope='complete measured pool opened only after simulated decision')
            analyses.append(result)

    summaries = []
    for policy in sorted({run['policy'] for run in runs}):
        for budget in (1, 2, 3):
            rows = [row for row in analyses if row['policy'] == policy and row['allowed_budget'] == budget]
            summaries.append(dict(policy=policy, allowed_budget=budget,
                dependent_seed_count=len(rows),
                mean_actual_queries=statistics.mean(row['actual_prefix_queries'] for row in rows),
                mean_simulated_queries=statistics.mean(row['simulated_queries'] for row in rows),
                mean_measurements_saved=statistics.mean(row['measurements_saved_vs_actual_prefix'] for row in rows),
                mean_evaluation_seconds_saved=statistics.mean(row['evaluation_seconds_saved_vs_actual_prefix'] for row in rows),
                mean_outer_operation_seconds_saved=statistics.mean(row['outer_operation_seconds_saved_vs_actual_prefix'] for row in rows),
                mean_simulated_cycle_reduction_regret=statistics.mean(row['simulated_oracle_regret'] for row in rows),
                missed_improvement_due_to_stopping_runs=sum(row['missed_improvement_due_to_stopping'] for row in rows),
                oracle_missed_runs=sum(row['missed_oracle_cycle_reduction'] > 0 for row in rows)))
    residuals = []
    for identity, row in outcomes.items():
        require(row.get('status', 'success') == 'success', 'This diagnostic expects successful measured outcomes')
        estimated = public_by_id[identity]['latency_features']['estimated_saved_cycles']
        actual = row['baseline_cycles']-row['candidate_cycles']
        residuals.append(dict(candidate_id=identity, prelabel_estimated_saved_cycles=estimated,
            retrospectively_measured_saved_cycles=actual,
            measured_minus_estimated_saved_cycles=actual-estimated,
            estimate_upper_bound_violated=actual > estimated))
    return dict(schema='isaforge-tiny-regex-shared-stopping-development-v1',
        scope='retrospective consumed-data development; not prospective evidence',
        source_sha256=sha(root / SOURCE),
        inputs=dict(study=STUDY, study_manifest_sha256=STUDY_MANIFEST_SHA256,
            preregistration=PREREG, preregistration_manifest_sha256=PREREG_MANIFEST_SHA256,
            prelabel_commit=report['prelabel_commit'],
            study_members_authenticated=len(inventory), preregistration_members_authenticated=len(pre_inventory)),
        primary_constraint=dict(added_lut4_cap=64, minimum_routed_fmax_mhz=12),
        rule=dict(condition='paid feasible incumbent saved cycles >= max(0, every unattempted frozen estimated saved cycles)',
            objective='whole-program cycle benefit; equal-speedup area/timing tie improvements are outside the stopping objective',
            remaining_scope='entire twelve-candidate roster, not just remaining actions in the archived order',
            observed_paid_mismatch='disable stopping after any measured-versus-estimated benefit mismatch',
            guarantee='conditional on unmeasured candidates not exceeding the public analytic estimates; not a proved hardware bound',
            numerical_comparison='cycle units with no speedup rounding or tolerance'),
        complete_measured_oracle=best_paid(list(outcomes.values()), baseline),
        all_pool_assumption_audit=dict(scoring_scope='post-decision only; never supplied to the rule',
            candidates=len(residuals), exact_benefit_mismatches=sum(row['measured_minus_estimated_saved_cycles'] != 0 for row in residuals),
            estimate_upper_bound_violations=sum(row['estimate_upper_bound_violated'] for row in residuals), rows=residuals),
        full_pool_collection=report['actual_dataset_collection'], summaries=summaries, runs=analyses,
        costs=dict(scope='sums of recorded candidate evaluation durations; counterfactual skipped costs, not newly saved wall time',
            overlapping_timers='evaluation and outer-operation durations are separate and must not be added',
            excluded='model calls/tokens, human relay, host inference/refit and future protocol overhead; no total-cost claim',
            agent='B3 carries the actual two-query episode forward; no third action or third-query saving is manufactured'),
        limitations=['Rule was motivated after seeing this completed study; all diagnostics are retrospective.',
            'One related-domain workload and five dependent seeds cannot establish generalization or policy superiority.',
            'An analytic estimate is not an unconditional bound; an unseen positive residual can make stopping miss an improvement.',
            'The archived source policies and original fixed-budget reports remain unchanged.',
            'This does not evaluate changed query orders or use target outcomes for fitting.',
            'Future use requires a new source-bound preregistration and prospective release.'],
        new_native_jobs=0, new_model_calls=0, new_model_fits=0, training_rows_added=0,
        superiority_established=False)


def render_readme(summary):
    lines = ['# tiny-regex-c shared-stopping development diagnostic', '',
        'This is a retrospective analysis of the completed, consumed tiny-regex r2 study. '
        'It changes no policy, native result, model, or prospective claim.', '',
        'The shared rule compares the paid feasible incumbent with the maximum frozen analytic '
        'saved-cycle estimate over every unattempted candidate. It cannot read an unqueried '
        'outcome. Paid benefit mismatches disable stopping. The oracle and all-pool residual '
        'audit are computed after decisions. The estimates are conditional assumptions, '
        'not proved upper bounds.', '',
        'The table uses the original B3 action order, shortened only by that rule. '
        'Five non-agent seeds are dependent runs on one workload. The agent is its single '
        'actual two-measurement episode, with no inferred third action.', '',
        '| Policy | Actual queries | Shared-stop queries | Queries saved | Evaluation seconds saved | New missed improvements |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in summary['summaries']:
        if row['allowed_budget'] == 3:
            lines.append(f"| {row['policy']} | {row['mean_actual_queries']:.2f} | {row['mean_simulated_queries']:.2f} | "
                f"{row['mean_measurements_saved']:.2f} | {row['mean_evaluation_seconds_saved']:.6f} | "
                f"{row['missed_improvement_due_to_stopping_runs']} |")
    audit = summary['all_pool_assumption_audit']
    lines += ['', f"All-pool post-decision audit: {audit['exact_benefit_mismatches']} exact-benefit mismatches; "
        f"{audit['estimate_upper_bound_violations']} positive residuals among {audit['candidates']} candidates.", '',
        'The agent and several deterministic policies reach the same oracle by B2. '
        'Any saved third evaluation is explained by the shared conditional stopping rule; '
        'this is no LLM selection or total-cost advantage. Some policies still miss the '
        'oracle within their original budget: `summary.json` separates their pre-existing '
        'regret from loss caused by stopping.', '',
        'Saved evaluation durations are counterfactual sums from the archived candidates. '
        'No hardware time was actually saved by this analysis. Full-pool collection still '
        'cost twelve measurements. Evaluation and outer-operation timers overlap and are '
        'reported separately; model, relay, human and inference costs are excluded.', '',
        'Reproduce into a fresh directory, or verify the committed artifact byte-for-byte:', '',
        '```sh',
        '../work/audit-venv/bin/python scripts/analyze_tiny_regex_stopping_rule.py --output generated/tiny-regex-stopping-replay',
        '../work/audit-venv/bin/python scripts/analyze_tiny_regex_stopping_rule.py --verify reports/2026-10-28-tiny-regex-stopping-rule-r1',
        '```', '',
        'The script authenticates both complete pinned input manifests and its output '
        'manifest. No model or hardware evaluator is imported. `summary.json` retains '
        'every prefix decision, conditional remaining-benefit bound, paid mismatch, '
        'original action order, cost difference and post-decision oracle comparison. '
        'Future prospective use requires a separate source-bound release.', '']
    return '\n'.join(lines).encode()


def artifacts(summary):
    content = {'summary.json': encoded(summary), 'README.md': render_readme(summary)}
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in content.items()}
    content['manifest.json'] = encoded(manifest)
    content['manifest.json.sha256'] = (hashlib.sha256(content['manifest.json']).hexdigest() + '\n').encode()
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--output', type=Path)
    choice.add_argument('--verify', type=Path)
    args = parser.parse_args()
    summary = analyze()
    content = artifacts(summary)
    destination = (args.verify or args.output or ROOT / DEFAULT_OUTPUT).resolve()
    # Never write into or replace completed source evidence.
    require(not destination.is_relative_to((ROOT / 'results').resolve()), 'Output cannot be sealed input evidence')
    if args.verify:
        require(destination.is_dir() and {p.name for p in destination.iterdir()} == set(content),
                'Output artifact inventory differs')
        for name, value in content.items():
            require((destination / name).read_bytes() == value, 'Reproduction mismatch: ' + name)
        print('Verified all input hashes and exact output reproduction.')
    else:
        require(not destination.exists(), 'Use a fresh output directory')
        destination.mkdir(parents=True)
        for name, value in content.items():
            (destination / name).write_bytes(value)
        print(f'Wrote {len(summary["runs"])} prefix comparisons to {destination}')


if __name__ == '__main__':
    main()

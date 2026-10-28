#!/usr/bin/env python3
"""Replay matched controls or run a bounded remote selector on consumed evidence.

The remote model gets four JSON functions only. Complete outcomes stay in this
privileged evaluator; reports/oracles are never attached to model requests.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b
from isaforge import codesign as c
from isaforge.bounded_selector import (PROMPT, MatchedBaselinePolicy,
                                      ReplaySelectionSession, run_selector)
from isaforge.selection_provider import ResponsesSelectionProvider, tool_definitions
from isaforge.agent_memory import MemoryAugmentedPolicy, MODES
from isaforge.routed_selection import RoutedSelectionProvider, summarize_model_events

TARGETS = dict(edn='results/2026-10-20-budget-campaign/selection/embench-edn',
               ud='results/2026-10-20-budget-campaign/selection/embench-ud',
               sha256='results/2026-10-21-sha256-selection/model')
SOURCES = ('scripts/run_bounded_selector.py', 'isaforge/bounded_selector.py',
           'isaforge/selection_provider.py', 'isaforge/routed_selection.py', 'isaforge/agent_memory.py', 'isaforge/budgeted_selection.py')


def complete_frontier(result, budget):
    """Retain ALL episodes, including zero-query failures and early stopping.

    A budget is an allowance, not a claim of additional measurements. Carry the
    best paid feasible outcome/cost forward and disclose actual charged attempts.
    The agent's finalized choice remains separate from best performance found.
    """
    points = []
    empty = dict(budget=0, selected_id=None, best_speedup=1.0,
                 attempted_ids=[], measured_ids=[], replayed_target_measurement_seconds=0.0)
    for allocated in range(1, budget+1):
        available = [point for point in result['curve'] if point['budget'] <= allocated]
        point = copy.deepcopy(available[-1] if available else empty)
        actual = point['budget']
        point.update(budget=allocated, actual_charged_attempts=actual,
                     carried_forward=actual < allocated,
                     stopped_early=result['charged_attempts'] < allocated,
                     termination=result['status'], finalized_selected_id=result['selected_id'],
                     finalized_speedup=result['best_speedup'])
        points.append(point)
    return points


def load_case(folder):
    folder = Path(folder)
    protocol = c.unseal(folder/'protocol.json')
    c.require(protocol['schema'] == 'isaforge-budgeted-selection-v1' and
              protocol['target_labels_read'] == 0, 'Expected frozen label-free protocol')
    for name, expected in protocol['source_bindings'].items():
        c.require(c.sha(ROOT/name) == expected, 'Frozen model source changed: '+name)
    for name, expected in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == expected, 'Frozen model dependency changed: '+name)
    for name, expected in protocol['artifacts'].items():
        path = (folder/name).resolve()
        c.require(not Path(name).is_absolute() and path.is_relative_to(folder.resolve()), 'Artifact escapes input root')
        c.require(c.sha(path) == expected, 'Frozen artifact changed')
    public, history = c.unseal(folder/'public.json'), c.unseal(folder/'history.json')
    predictions, report = c.unseal(folder/'predictions.json'), c.unseal(folder/'report.json')
    b.public_rows(public)
    c.require(report['protocol_sha256'] == c.sha(folder/'protocol.json'), 'Report/protocol binding differs')
    outcomes = {}
    for run in report['runs']:
        for event in run['events']:
            if 'observation' in event:
                observation = event['observation']; identity = observation['candidate_id']
                c.require(identity not in outcomes or outcomes[identity] == observation, 'Conflicting recorded outcomes')
                outcomes[identity] = observation
    c.require(set(outcomes) == {r['candidate_id'] for r in public}, 'Complete recorded attempted pool required')
    for row in public:
        b.validate_outcome(outcomes[row['candidate_id']], row)
    c.require(c.digest([outcomes[r['candidate_id']] for r in public]) == report['outcomes_sha256'],
              'Frozen outcome binding differs')
    costs = protocol.get('cost_provenance', {})
    historical_seconds = costs.get('total_candidate_wall_seconds', protocol['historical_candidate_wall_seconds'])
    return dict(public=public, history=history, predictions=predictions, report=report,
                protocol=protocol, outcomes=outcomes, historical_seconds=historical_seconds)


def run(output, *, provider='controls', model=None, targets=None,
        seeds=None, caps=None, budget=3, max_model_calls=12, escalation_model=None, memory_mode="none"):
    run_started = time.monotonic()
    c.require(provider in ('controls', 'responses'), 'Unknown provider')
    if provider == 'responses':
        c.require(model and os.environ.get('OPENAI_API_KEY'),
                  'Live run requires explicit --model and OPENAI_API_KEY; no model call was made.')
    c.require(escalation_model is None or provider == 'responses', 'Routing requires responses provider')
    c.require(type(max_model_calls) is int and 0 < max_model_calls <= 100, 'Invalid model limit')
    c.require(memory_mode in MODES, 'Invalid memory mode')
    output = Path(output).resolve()
    c.require(not output.exists(), 'Use a fresh output directory')
    target_names = list(TARGETS) if targets is None else list(targets)
    c.require(target_names and len(set(target_names)) == len(target_names) and
              set(target_names) <= TARGETS.keys(), 'Unknown or duplicate targets')
    cases = {name: load_case(ROOT/TARGETS[name]) for name in target_names}
    c.require(type(budget) is int and 0 < budget <= 3, 'Budget must be one to three')
    selected_seeds = list(range(5)) if seeds is None else list(seeds)
    selected_caps = [32, 64, 128] if caps is None else list(caps)
    c.require(selected_seeds and len(set(selected_seeds)) == len(selected_seeds) and
              all(type(seed) is int and seed in range(5) for seed in selected_seeds), 'Invalid frozen seeds')
    c.require(selected_caps and len(set(selected_caps)) == len(selected_caps) and
              all(cap in (32, 64, 128) for cap in selected_caps), 'Invalid frozen caps')
    policies = list(b.POLICIES) if provider == 'controls' else ['llm_selector']
    protocol = dict(schema='isaforge-bounded-selector-development-v1',
        scope='Consumed-data engineering replay; not prospective source generalization.',
        provider=provider, model=model, escalation_model=escalation_model, memory_mode=memory_mode,
        routing_rule="one schema-error escalation; shared model-call budget", policies=policies, targets=target_names,
        seeds=selected_seeds, area_caps=selected_caps, budget=budget, clock_mhz=12,
        max_model_calls=max_model_calls, max_tool_calls=20,
        max_output_tokens_per_call=512 if provider == 'responses' else None,
        prompt=PROMPT, prompt_sha256=c.digest(PROMPT), tools=tool_definitions(),
        source_bindings={name: c.sha(ROOT/name) for name in SOURCES},
        input_bindings={name: {file: c.sha(ROOT/TARGETS[name]/file) for file in
            ('protocol.json', 'public.json', 'history.json', 'predictions.json', 'report.json')} for name in target_names},
        fallback='best paid verified feasible improvement, else baseline',
        invalid_measurements='Every submitted measure, including invalid IDs/repeats, charges before lookup while budget remains.',
        historical_cost_note='All historical available attempts are charged, including failed/excluded rows. Setup/calibration separate.',
        timer_note='Target durations are archived record/ledger durations, not live search time; these scopes differ and overlap with command timing.',
        isolation='External Responses model has only serialized allowlisted JSON and four strict functions; no shell, files, MCP or oracle; optional retrieval only from approved public history.',
        uncertainty_calibrated=False, joint_sets_supported=False, new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'protocol.json', protocol)  # Saved before the first policy episode.
    started = time.monotonic()
    runs, endpoint_rows = [], []
    for name, case in cases.items():
        original = case['protocol']
        for cap in selected_caps:
            feasible = [row for row in case['outcomes'].values() if b._feasible(row, cap, 12)]
            reference = max([1.0]+[row['speedup'] for row in feasible])
            unknown = name == 'ud'
            for seed in selected_seeds:
                prediction = next(p for p in case['predictions'] if p['seed'] == seed)
                for policy_name in policies:
                    ledger = output/'private-ledgers'/name/str(cap)/str(seed)/(policy_name+'.json')
                    def measure(row, outcomes=case['outcomes']):
                        return copy.deepcopy(outcomes[row['candidate_id']])
                    session = ReplaySelectionSession(case['public'], case['history'], prediction,
                        measure, area_cap=cap, budget=budget, max_tool_calls=20, ledger_path=ledger,
                        historical_available_rows=original['historical_available_rows'],
                        historical_attempt_seconds=case['historical_seconds'])
                    policy = (MatchedBaselinePolicy(policy_name) if provider == 'controls' else
                              ResponsesSelectionProvider(model, max_calls=max_model_calls, max_output_tokens=512))
                    if provider == 'responses':
                        secondary = (ResponsesSelectionProvider(escalation_model, max_calls=max_model_calls,
                                     max_output_tokens=512) if escalation_model else None)
                        policy = RoutedSelectionProvider(policy, secondary, max_calls=max_model_calls)
                    if memory_mode != "none":
                        policy = MemoryAugmentedPolicy(policy, mode=memory_mode)
                    result = run_selector(session, policy, max_model_calls=max_model_calls)
                    # Only the privileged scorer uses oracle values, after policy execution.
                    for point in complete_frontier(result, budget):
                        endpoint_rows.append(dict(target=name, policy=policy_name, cap=cap, seed=seed,
                            **point, regret_to_verified_reference=reference-point['best_speedup'],
                            reference_kind='best verified; full pool censored' if unknown else 'measured pool oracle'))
                    matched = None
                    if provider == 'controls':
                        archived = next(run for run in case['report']['runs'] if run['policy'] == policy_name and
                                        run['seed'] == seed and run['area_delta_lut4_cap'] == cap)
                        for point in result['curve']:
                            previous = next(p for p in archived['curve'] if p['budget'] == point['budget'])
                            for key in ('best_speedup', 'selected_id', 'attempted_ids', 'measured_ids'):
                                c.require(point[key] == previous[key], 'Matched baseline differs: '+policy_name+'/'+key)
                            c.require(point['replayed_target_measurement_seconds'] == previous['target_measurement_seconds'],
                                      'Matched baseline cost differs')
                        c.require(result['charged_attempts'] == budget and result['status'] == 'finalized',
                                  'Control failed to complete its fixed budget')
                        matched = True
                    runs.append(dict(target=name, policy=policy_name, cap=cap, seed=seed,
                        status=result['status'], charged_attempts=result['charged_attempts'],
                        selected_id=result['selected_id'], speedup=result['best_speedup'],
                        best_verified_speedup=result['curve'][-1]['best_speedup'] if result['curve'] else 1.0,
                        regret_to_verified_reference=reference-(result['curve'][-1]['best_speedup'] if result['curve'] else 1.0),
                        finalized_regret_to_verified_reference=reference-result['best_speedup'],
                        original_trajectory_matches=matched, ledger=str(ledger.relative_to(output)),
                        ledger_sha256=c.sha(ledger), decision_calls=result['model_calls'],
                        llm_calls=summarize_model_events(result['model_events'])['dispatched_calls'],
                        reserved_model_calls=policy.calls if provider == 'responses' else 0,
                        model_accounting=summarize_model_events(result['model_events']),
                        replayed_target_seconds=result['replayed_target_measurement_seconds'],
                        historical_attempt_seconds=case['historical_seconds'],
                        new_native_jobs=0))
    summaries = []
    for name in target_names:
        for cap in selected_caps:
            for policy in policies:
                for step in range(1, budget+1):
                    values = [r for r in endpoint_rows if r['target'] == name and r['cap'] == cap and
                              r['policy'] == policy and r['budget'] == step]
                    if values:
                        summaries.append(dict(target=name, cap=cap, policy=policy, budget=step,
                            completed_trajectories=len(values),
                            mean_best_speedup=statistics.mean(r['best_speedup'] for r in values),
                            mean_regret_to_verified_reference=statistics.mean(r['regret_to_verified_reference'] for r in values),
                            mean_replayed_target_seconds=statistics.mean(r['replayed_target_measurement_seconds'] for r in values)))
    report = dict(schema=protocol['schema'], scope=protocol['scope'], protocol_sha256=c.sha(output/'protocol.json'),
        trajectories=len(runs), endpoints=len(endpoint_rows), runs=runs, endpoints_detail=endpoint_rows,
        summary=summaries, all_controls_match=all(r['original_trajectory_matches'] for r in runs) if provider == 'controls' else None,
        llm_calls=sum(r['llm_calls'] for r in runs), new_native_jobs=0,
        replay_host_elapsed_seconds=time.monotonic()-started,
        host_total_until_report_seconds=time.monotonic()-run_started,
        superiority_established=False,
        limitations=['Consumed evidence; model/feature development cannot establish new-workload generalization.',
                     'Dependent seed/cap/budget prefixes are not independent experiments.',
                     'No live target evaluation or joint instruction set is implemented by this adapter.',
                     'Model spreads are uncalibrated. A remote model is not itself a numeric calibration fix.',
                     'HTTP timeout is a network-operation timeout, not an absolute process deadline.',
                     'No model price is inferred; token usage is retained in private ledgers.',
                     'The oracle and full outcomes are privileged scoring data; private ledgers/reports stay outside policy inputs.'])
    c.seal(output/'report.json', report)
    c.seal(output/'manifest.json', {str(path.relative_to(output)): c.sha(path)
                                  for path in sorted(output.rglob('*')) if path.is_file()})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--provider', choices=('controls', 'responses'), default='controls')
    parser.add_argument('--model')
    parser.add_argument('--memory-mode', choices=MODES, default='none')
    parser.add_argument('--escalation-model')
    parser.add_argument('--max-model-calls', type=int, default=12)
    parser.add_argument('--target', choices=tuple(TARGETS), action='append')
    parser.add_argument('--seed', type=int, action='append')
    parser.add_argument('--cap', type=int, action='append')
    parser.add_argument('--budget', type=int, default=3)
    args = parser.parse_args(argv)
    result = run(args.output, provider=args.provider, model=args.model,
                 targets=args.target, seeds=args.seed, caps=args.cap, budget=args.budget,
                 escalation_model=args.escalation_model, max_model_calls=args.max_model_calls, memory_mode=args.memory_mode)
    print({key:result[key] for key in ('trajectories', 'endpoints', 'all_controls_match', 'llm_calls', 'new_native_jobs')})


if __name__ == '__main__': main()

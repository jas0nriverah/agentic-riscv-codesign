#!/usr/bin/env python3
"""Run a bounded agent against the current workload-held-out ML predictions.

This is a consumed-data development replay. Target outcomes remain inside the
host evaluator and are returned only after a charged `measure` action.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b, codesign as c
from isaforge.agent_memory import MODES, MemoryAugmentedPolicy
from isaforge.bounded_selector import ReplaySelectionSession, run_selector
from isaforge.codex_chat_selector import CodexChatSelectionProvider
from isaforge.current_grouped_predictions import fit_current_grouped_predictions
from isaforge.grouped_agent_case import list_grouped_agent_targets, load_grouped_agent_case
from isaforge.selection_provider import ResponsesSelectionProvider, tool_definitions
from isaforge.routed_selection import RoutedSelectionProvider
from isaforge.routed_selection import summarize_model_events

ROOT_CORPUS = 'results/2026-10-26-lift-selection-corpus/corpus.json'
SCREEN = ROOT/'results/2026-10-26-feasibility-model-screen'
CONTROL_POLICIES = (
    'frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic',
    'random', 'xgb_pairwise_ranker', 'factorized_feasibility_xgb',
)


def _screen_report():
    protocol = c.unseal(SCREEN/'protocol.json')
    c.require(protocol.get('schema') == 'isaforge-feasibility-model-family-screen-v1',
              'Expected current grouped model screen')
    c.require(protocol.get('corpus_path') == ROOT_CORPUS and
              c.sha(ROOT/ROOT_CORPUS) == protocol.get('corpus_sha256'),
              'Current 122-label corpus differs from the screen input')
    for name, expected in protocol.get('source_bindings', {}).items():
        c.require(c.sha(ROOT/name) == expected, 'Grouped screen source changed: '+name)
    artifacts = c.unseal(SCREEN/'manifest.json')
    for name, expected in artifacts.items():
        path = (SCREEN/name).resolve()
        c.require(path.is_relative_to(SCREEN.resolve()) and c.sha(path) == expected,
                  'Screen artifact hash mismatch: '+name)
    c.require(c.sha(SCREEN/'protocol.json') == artifacts.get('protocol.json'),
              'Screen protocol is not bound by its manifest')
    return c.unseal(SCREEN/'report.json'), protocol


def _feasible(row, area_cap, clock_mhz):
    return row.get('status', 'success') == 'success' and b._feasible(row, area_cap, clock_mhz)


def _score_ordered_ids(candidate_ids, outcomes, *, area_cap, clock_mhz):
    successes = [outcomes[identity] for identity in candidate_ids
                 if identity in outcomes and _feasible(outcomes[identity], area_cap, clock_mhz)
                 and outcomes[identity]['speedup'] > 1.]
    best = min(successes, key=lambda row: (-row['speedup'], row['area_delta_lut4'],
                                           row['candidate_id'])) if successes else None
    return dict(best_verified_speedup=best['speedup'] if best else 1.,
        best_verified_candidate_id=best['candidate_id'] if best else None,
        best_verified_outcome=(dict(candidate_id=best['candidate_id'],
            speedup=best['speedup'], baseline_cycles=best['baseline_cycles'],
            candidate_cycles=best['candidate_cycles'], area_delta_lut4=best['area_delta_lut4'],
            routed_fmax_min_mhz=best['routed_fmax_min_mhz'],
            correctness_verified=best['correctness_verified']) if best else None),
        failed_or_unresolved_attempts=sum(
            outcomes.get(identity, {}).get('status') == 'failed' for identity in candidate_ids),
        infeasible_successful_attempts=sum(
            identity in outcomes and outcomes[identity].get('status', 'success') == 'success' and
            not b._feasible(outcomes[identity], area_cap, clock_mhz) for identity in candidate_ids),
        archived_measurement_seconds=sum(
            outcomes[identity]['measurement_seconds'] for identity in candidate_ids if identity in outcomes))


def _matched_controls(screen, metadata, outcomes, *, seed, area_cap, clock_mhz):
    rows = [row for row in screen['runs']
            if row['workload_group'] == metadata['target_workload_group'] and
            row['benchmark'] == metadata['target_benchmark'] and row['seed'] == seed and
            row['policy'] in CONTROL_POLICIES]
    result = {}
    for row in rows:
        identity = row['policy']
        if identity not in result:
            result[identity] = {}
        result[identity][str(row['budget'])] = dict(
            attempted_candidate_ids=list(row['attempted_candidate_ids']),
            **_score_ordered_ids(row['attempted_candidate_ids'], outcomes,
                                 area_cap=area_cap, clock_mhz=clock_mhz),
            reference_censored=row['reference_censored'],
            cycle_reduction_regret=row['cycle_reduction_regret'],
            reference_kind=row['reference_kind'])
    c.require(set(result) == set(CONTROL_POLICIES),
              'Matched current-screen controls are incomplete for target context')
    return result


def run(*, target_group: str, benchmark: str, output: Path, provider: str = 'codex-chat',
        model: str | None = None, escalation_model: str | None = None,
        model_label: str = 'current Codex chat model; exact deployment ID unavailable',
        seed: int = 0, budget: int = 3, area_cap: int = 64,
        memory_mode: str = 'none', max_model_calls: int = 12):
    c.require(provider in ('codex-chat', 'responses'), 'Unknown provider')
    c.require(memory_mode in MODES, 'Unknown memory mode')
    c.require(type(seed) is int and 0 <= seed < 5, 'Use one of the screen policy seeds')
    c.require(type(budget) is int and 0 < budget <= 3, 'Budget must be one to three attempts')
    c.require(area_cap == 64, 'This agent integration is frozen to the screen primary +64 LUT4 cap')
    c.require(type(max_model_calls) is int and 0 < max_model_calls <= 100,
              'Invalid model-call limit')
    c.require(escalation_model is None or provider == 'responses',
              'Model routing requires the Responses provider')
    if provider == 'responses':
        c.require(bool(model) and bool(__import__('os').environ.get('OPENAI_API_KEY')),
                  'Live Responses selection requires OPENAI_API_KEY and an explicit model')
    output = Path(output).resolve()
    c.require(not output.exists(), 'Use a new output directory; prior evidence is immutable')

    case = load_grouped_agent_case(target_group, benchmark)
    metadata = case['metadata']
    public_metadata = case['public_metadata']
    c.require(metadata['target_workload_group'] == target_group and
              metadata['target_benchmark'] == benchmark,
              'Loaded grouped case disagrees with requested target')
    c.require(len(case['public']) >= budget, 'Budget exceeds the target candidate pool')
    bundle, model_metadata = fit_current_grouped_predictions(
        case['training'], case['public'], target_workload_group=target_group,
        target_formula_families=metadata['target_formula_families'], seed=0,
        area_cap_lut4=area_cap)
    model_metadata['target_benchmark'] = benchmark
    model_metadata['input_evidence_fingerprint'] = c.digest(public_metadata['input_bindings'])
    model_metadata['screen_protocol_sha256'] = public_metadata[
        'input_bindings']['screen_protocol_sha256']
    model_metadata['historical_training_measurements'] = len(case['training'])
    model_metadata['historical_attempt_seconds'] = metadata['historical_attempt_seconds']

    output.mkdir(parents=True)
    if provider == 'codex-chat':
        policy = CodexChatSelectionProvider(model_label=model_label,
            request_directory=output/'public-requests')
    else:
        policy = ResponsesSelectionProvider(model, max_calls=max_model_calls,
            max_output_tokens=512)
        if escalation_model:
            policy = RoutedSelectionProvider(policy, ResponsesSelectionProvider(
                escalation_model, max_calls=max_model_calls, max_output_tokens=512),
                max_calls=max_model_calls)
    if memory_mode != 'none':
        policy = MemoryAugmentedPolicy(policy, mode=memory_mode)

    protocol = dict(schema='isaforge-grouped-current-model-agent-v1',
        scope='consumed-data workload-held-out agent engineering replay; not independent confirmation',
        target_workload_group=target_group, target_benchmark=benchmark,
        target_candidate_ids=[row['candidate_id'] for row in case['public']],
        target_labels_in_model_request=0,
        target_outcomes_disclosed_only_after_charged_measure=True,
        reference_complete=metadata['reference_complete'],
        area_cap_lut4=area_cap, minimum_routed_fmax_mhz=12.0,
        budget=budget, seed=seed, model_seed=0, provider=provider,
        model=model, escalation_model=escalation_model, model_label=model_label,
        memory_mode=memory_mode, max_model_calls=max_model_calls,
        max_tool_calls=20, max_output_tokens=512 if provider == 'responses' else None,
        model_bundle_metadata=model_metadata, model_predictions_sha256=c.digest(bundle),
        public_case_metadata=public_metadata,
        sources={name: c.sha(ROOT/name) for name in (
            'scripts/run_grouped_agent_selector.py',
            'isaforge/grouped_agent_case.py',
            'isaforge/current_grouped_predictions.py',
            'isaforge/bounded_selector.py',
            'isaforge/budgeted_selection.py',
            'isaforge/selection_provider.py',
            'isaforge/codex_chat_selector.py',
            'isaforge/routed_selection.py',
            'isaforge/agent_memory.py')},
        tools=tool_definitions(), token_usage='Unavailable for Codex chat relay; API usage retained when using Responses.',
        new_native_jobs=0)
    c.seal(output/'protocol.json', protocol)

    session = ReplaySelectionSession(case['public'], case['training'], None,
        lambda row: case['outcomes'][row['candidate_id']], area_cap=area_cap,
        clock_mhz=12.0, budget=budget, max_tool_calls=20,
        ledger_path=output/'ledger.json',
        historical_available_rows=metadata['historical_available_rows'],
        historical_attempt_seconds=metadata['historical_attempt_seconds'],
        grouped_predictions=bundle, grouped_model_metadata=model_metadata)
    result = run_selector(session, policy, max_model_calls=max_model_calls)

    # Only after selector completion do we open complete candidate outcomes and
    # the sealed retrospective policy screen for scoring.
    screen, screen_protocol = _screen_report()
    controls = _matched_controls(screen, metadata, case['outcomes'], seed=seed,
                                 area_cap=area_cap, clock_mhz=12.0)
    successes = [row for row in case['outcomes'].values()
                 if row.get('status', 'success') == 'success' and
                 b._feasible(row, area_cap, 12.0) and row['speedup'] > 1.0]
    best_reference = min(successes, key=lambda row: (-row['speedup'],
        row['area_delta_lut4'], row['candidate_id'])) if successes else None
    complete = metadata['reference_complete'] is True
    oracle_speedup = best_reference['speedup'] if complete and best_reference else (1.0 if complete else None)
    cycle_reduction = 1.0 - 1.0/result['best_speedup']
    oracle_cycle_reduction = (1.0 - 1.0/oracle_speedup) if oracle_speedup is not None else None
    regret = (max(0.0, oracle_cycle_reduction-cycle_reduction)
              if complete and oracle_cycle_reduction is not None else None)
    selected = next((row for row in session.observations
                     if row['candidate_id'] == result['selected_id']), None)
    report = dict(schema='isaforge-grouped-current-model-agent-report-v1',
        scope=protocol['scope'], protocol_sha256=c.sha(output/'protocol.json'),
        screen_protocol_sha256=c.sha(SCREEN/'protocol.json'),
        screen_report_sha256=c.sha(SCREEN/'report.json'),
        target_workload_group=target_group, target_benchmark=benchmark,
        public_candidate_count=len(case['public']),
        reference_complete=complete,
        reference_kind=('complete verified candidate-pool oracle' if complete
                        else 'best verified measured outcome; full oracle censored'),
        best_verified_reference_speedup=oracle_speedup,
        best_verified_reference_candidate_id=best_reference['candidate_id'] if best_reference else None,
        provider=policy.identity, memory_mode=memory_mode,
        area_cap_lut4=area_cap, minimum_routed_fmax_mhz=12.0,
        seed=seed, budget=budget,
        status=result['status'], charged_attempts=result['charged_attempts'],
        tool_calls=result['tool_calls'], model_turns=result['model_calls'],
        selected_id=result['selected_id'], selected_speedup=result['best_speedup'],
        selected_measured_outcome=selected,
        best_paid_verified_id=(result['curve'][-1]['selected_id'] if result['curve'] else None),
        best_paid_verified_speedup=(result['curve'][-1]['best_speedup'] if result['curve'] else 1.0),
        regret_to_complete_measured_pool_oracle=regret,
        archived_measurement_seconds=sum(event.get('replayed_measurement_seconds', 0)
            for event in session.ledger['events']),
        verified_cycle_reduction=cycle_reduction,
        oracle_cycle_reduction=oracle_cycle_reduction,
        cycle_reduction_regret=regret,
        current_model_bundle=model_metadata,
        matched_controls=controls,
        decisions=[dict(sequence=event.get('sequence'), tool=event.get('tool'),
                        candidate_id=event.get('candidate_id'), status=event.get('status'),
                        public_result=event.get('public_result'))
                   for event in session.ledger['events']],
        curve=session.ledger['curve'], ledger_sha256=c.sha(output/'ledger.json'),
        interactive_elapsed_seconds=result.get('host_elapsed_seconds'),
        timing_note='Codex chat elapsed time includes relay/waiting and is not inference latency; archived native record durations are not live-agent wall time.',
        token_usage=(None if provider == 'codex-chat' else
                     summarize_model_events(session.ledger['model_events'])),
        new_native_jobs=0,
        limitations=[
            'All target candidate outcomes were previously consumed and are replayed; no new hardware jobs or labels were created.',
            'Training is whole-workload and target-family excluded; this is not a prospective unseen-source test.',
            'Pairwise scores are ordering scores; factorized feasibility scores and disagreement are uncalibrated.',
            'Only single-instruction choices are supported; candidate speedups/areas are not additive.',
            'For censored target contexts, oracle speedup and regret are intentionally null.',
            'A Codex chat relay is instruction-bounded, not sandboxed; exact deployed model identity and model-only latency/tokens are unavailable.'
                if provider == 'codex-chat' else
            'The Responses provider has no repository or oracle tools; this remains consumed-data development and not a fresh hardware result.'])
    c.seal(output/'report.json', report)
    manifest = {path.relative_to(output).as_posix(): c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()}
    c.seal(output/'manifest.json', manifest)
    print(json.dumps(dict(status=result['status'], charged_attempts=result['charged_attempts'],
        selected_id=result['selected_id'], best_paid_verified_speedup=report['best_paid_verified_speedup'],
        oracle_speedup=oracle_speedup, regret=regret, target_group=target_group,
        benchmark=benchmark, new_native_jobs=0, output=str(output)), indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-targets', action='store_true')
    parser.add_argument('--target-group')
    parser.add_argument('--benchmark')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--provider', choices=('codex-chat', 'responses'), default='codex-chat')
    parser.add_argument('--model')
    parser.add_argument('--escalation-model')
    parser.add_argument('--model-label', default='current Codex chat model; exact deployment ID unavailable')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--budget', type=int, default=3)
    parser.add_argument('--area-cap', type=int, default=64)
    parser.add_argument('--memory-mode', choices=MODES, default='none')
    parser.add_argument('--max-model-calls', type=int, default=12)
    args = parser.parse_args(argv)
    if args.list_targets:
        print(json.dumps(list_grouped_agent_targets(), indent=2))
        return 0
    c.require(args.target_group and args.benchmark and args.output,
              '--target-group, --benchmark and --output are required')
    run(target_group=args.target_group, benchmark=args.benchmark,
        output=args.output, provider=args.provider, model=args.model,
        escalation_model=args.escalation_model, model_label=args.model_label,
        seed=args.seed, budget=args.budget, area_cap=args.area_cap,
        memory_mode=args.memory_mode, max_model_calls=args.max_model_calls)
    return 0


if __name__ == '__main__':
    main()

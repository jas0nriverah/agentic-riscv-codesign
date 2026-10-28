#!/usr/bin/env python3
"""Run one bounded replay episode with the active Codex chat as selector.

The local process owns the evaluator and emits one public JSON request at a
time. The active Codex model replies with one allowlisted action JSON line.
This is a consumed-data, interactive development pilot; it is not a live API
experiment, blinded benchmark, or new native hardware measurement.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))

from isaforge import budgeted_selection as b
from isaforge import codesign as c
from isaforge.bounded_selector import PROMPT, ReplaySelectionSession, run_selector
from isaforge.agent_memory import MemoryAugmentedPolicy, MODES
from isaforge.codex_chat_selector import CodexChatSelectionProvider
from isaforge.selection_provider import tool_definitions
from run_bounded_selector import TARGETS, load_case


def run(*, target: str, cap: int, seed: int, budget: int, output: Path,
        model_label: str = 'current Codex chat model; deployment ID unavailable',
        memory_mode='none', request_files=False):
    c.require(memory_mode in MODES, 'Invalid memory mode')
    c.require(target in TARGETS, 'Unknown target')
    c.require(cap in (32, 64, 128), 'Area cap must be 32, 64 or 128 LUT4')
    c.require(type(seed) is int and seed in range(5), 'Seed must be one of the five frozen seeds')
    c.require(type(budget) is int and 0 < budget <= 3, 'Budget must be one to three attempts')
    output = output.resolve()
    c.require(not output.exists(), 'Use a fresh output directory; prior evidence is immutable')

    case = load_case(ROOT/TARGETS[target])
    prediction = next(row for row in case['predictions'] if row['seed'] == seed)
    protocol = dict(schema='isaforge-codex-chat-selector-development-v1',
        scope='Consumed-data interactive development replay; no source generalization claim.',
        provider='codex-chat-bridge', model_label=model_label, memory_mode=memory_mode,
        request_files=request_files,
        exact_model_id_available=False,
        objective='Best paid, verified, correct whole-program speedup subject to measured area/timing and a fixed attempt budget.',
        target=target, area_cap_lut4=cap, clock_floor_mhz=12.0, seed=seed,
        budget=budget, max_model_calls=min(12, budget*2+4), max_tool_calls=20,
        max_output_tokens=None, prompt=PROMPT,
        prompt_sha256=c.digest(PROMPT), tools=tool_definitions(),
        input_bindings={name: c.sha(ROOT/TARGETS[target]/name) for name in
                        ('protocol.json', 'public.json', 'history.json', 'predictions.json', 'report.json')},
        source_bindings={name: c.sha(ROOT/name) for name in
                        ('scripts/run_codex_chat_selector.py', 'isaforge/codex_chat_selector.py',
                         'isaforge/bounded_selector.py', 'isaforge/budgeted_selection.py',
                         'isaforge/selection_provider.py', 'isaforge/agent_memory.py')},
        historical_cost_note='Archived attempt costs retain original timer scopes; no project-time savings are inferred.',
        chat_boundary='The request/output channel contains allowlisted JSON; the active Codex session itself also has broader workspace tools.',
        token_usage='Unavailable for in-chat orchestration.',
        new_native_jobs=0,
        uncertainty_calibrated=False,
        joint_sets_supported=False)
    output.mkdir(parents=True)
    c.seal(output/'protocol.json', protocol)

    def replay_measure(public_row):
        return case['outcomes'][public_row['candidate_id']]

    session = ReplaySelectionSession(case['public'], case['history'], prediction,
        replay_measure, area_cap=cap, budget=budget,
        max_tool_calls=protocol['max_tool_calls'], ledger_path=output/'ledger.json',
        historical_available_rows=case['protocol']['historical_available_rows'],
        historical_attempt_seconds=case['historical_seconds'])
    agent = CodexChatSelectionProvider(model_label=model_label,
        request_directory=output/'public-requests' if request_files else None)
    if memory_mode != 'none':
        agent = MemoryAugmentedPolicy(agent, mode=memory_mode)
    result = run_selector(session, agent, max_model_calls=protocol['max_model_calls'])

    feasible_outcomes = [row for row in case['outcomes'].values()
                         if b._feasible(row, cap, 12.0) and row['speedup'] > 1]
    oracle = max([dict(candidate_id=None, speedup=1.0), *feasible_outcomes],
                 key=lambda row: row['speedup'])
    matched_controls = []
    for policy_name in ('frequency', 'merit', 'random', 'raw_regression', 'ranking',
                        'latency_cost_heuristic', 'hybrid_gp_adapt'):
        match = next((row for row in case['report']['runs']
                      if row['policy'] == policy_name and row['seed'] == seed and
                      row['area_delta_lut4_cap'] == cap), None)
        if match is None:
            continue
        points = [point for point in match['curve'] if point['budget'] <= budget]
        if points:
            point = points[-1]
            matched_controls.append(dict(policy=policy_name,
                charged_attempts=point['budget'], selected_id=point['selected_id'],
                best_speedup=point['best_speedup'],
                regret_to_measured_pool_oracle=oracle['speedup']-point['best_speedup']))
    selected = next((row for row in session.observations
                     if row['candidate_id'] == result['selected_id']), None)
    report = dict(schema='isaforge-codex-chat-selector-report-v1',
        scope=protocol['scope'], protocol_sha256=c.sha(output/'protocol.json'),
        provider=agent.identity, target=target, area_cap_lut4=cap,
        clock_floor_mhz=12.0, seed=seed, budget=budget,
        status=result['status'], charged_attempts=result['charged_attempts'],
        tool_calls=result['tool_calls'], model_turns=result['model_calls'],
        selected_id=result['selected_id'], selected_speedup=result['best_speedup'],
        selected_measured_outcome=selected,
        best_paid_verified_id=(result['curve'][-1]['selected_id'] if result['curve'] else None),
        best_paid_verified_speedup=(result['curve'][-1]['best_speedup'] if result['curve'] else 1.0),
        measured_pool_oracle=dict(candidate_id=oracle['candidate_id'], speedup=oracle['speedup']),
        regret_to_measured_pool_oracle=oracle['speedup']-result['best_speedup'],
        matched_controls=matched_controls,
        decisions=[dict(sequence=event.get('sequence'), tool=event.get('tool'),
                        candidate_id=event.get('candidate_id'),
                        status=event.get('status'), public_result=event.get('public_result'))
                   for event in result['events']],
        interactive_elapsed_seconds=result.get('host_elapsed_seconds'),
        timing_note='Interactive wall time includes waiting/reading the active chat reply; it is not model inference latency or a live-search time measurement.',
        token_usage=None, api_calls=0, new_native_jobs=0,
        private_data_note='Unqueried target outcomes are used only after the agent finishes to compute the oracle and matched controls; they were not added to public requests.',
        limitations=['Consumed historical candidate pool and previously inspected workload.',
                     'The current Codex conversation has broader context and workspace tools; this is not blinded or equivalent to the isolated Responses API provider.',
                     'Exact deployed model ID, token usage and model-only latency are unavailable.',
                     'One interactive trajectory is a demonstration, not an estimate of stochastic LLM performance.',
                     'No new native hardware evaluations; measurements are charged replays.',
                     'Only single-instruction selection is supported.'])
    c.seal(output/'report.json', report)
    c.seal(output/'manifest.json', {str(path.relative_to(output)): c.sha(path)
                                  for path in sorted(output.rglob('*')) if path.is_file()})
    print('\nISAForge CODEX SELECTOR RESULT')
    print(canonical_json(dict(status=result['status'], charged_attempts=result['charged_attempts'],
        selected_id=result['selected_id'], best_speedup=result['best_speedup'],
        oracle_speedup=oracle['speedup'], regret=report['regret_to_measured_pool_oracle'],
        new_native_jobs=0, report=str(output/'report.json'), ledger=str(output/'ledger.json'))))
    return report


def canonical_json(value):
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=tuple(TARGETS), required=True)
    parser.add_argument('--cap', type=int, choices=(32, 64, 128), required=True)
    parser.add_argument('--seed', type=int, choices=range(5), default=0)
    parser.add_argument('--budget', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--memory-mode', choices=MODES, default='none')
    parser.add_argument('--request-files', action='store_true')
    parser.add_argument('--model-label', default='current Codex chat model; deployment ID unavailable')
    args = parser.parse_args(argv)
    run(target=args.target, cap=args.cap, seed=args.seed, budget=args.budget,
        output=args.output, model_label=args.model_label,
        memory_mode=args.memory_mode, request_files=args.request_files)


if __name__ == '__main__':
    main()

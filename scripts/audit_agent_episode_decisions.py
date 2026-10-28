"""Deterministic post-episode audit of advice, probe reasons and paid outcomes.

Existing decision-board/rationale ledgers already record this evidence. This
report validates their temporal/hash links and turns them into readable probe
explanations. It never invents reasoning or opens the complete-pool outcome file.
No controller changes, policy feedback, model fits or native jobs are performed.
"""
from __future__ import annotations
import argparse
import shlex
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge import selector_decision_support as support

RESULTS = ROOT / 'results/2026-10-28-nanocobs-v2-selection-r1'
OUTPUT = ROOT / 'reports/2026-10-28-nanocobs-decision-audit-r1'
SOURCE = 'scripts/audit_agent_episode_decisions.py'


def authenticated_episode(results):
    """Validate sealed result/agent inventories; decode only the agent episode."""
    results = Path(results).resolve()
    manifest = c.unseal(results / 'manifest.json')
    for name, digest in manifest.items():
        path = (results / name).resolve()
        c.require(path.is_relative_to(results) and path.is_file() and c.sha(path) == digest,
                  'Sealed result artifact differs: ' + name)
    for name, digest in c.unseal(results / 'agent/manifest.json').items():
        path = (results / 'agent' / name).resolve()
        c.require(path.is_relative_to(results / 'agent') and c.sha(path) == digest,
                  'Sealed episode artifact differs: ' + name)
    ledger = c.unseal(results / 'agent/ledger.json')
    report = c.unseal(results / 'agent-report.json')
    c.require(report['ledger_sha256'] == c.sha(results / 'agent/ledger.json') and
              report['decision_rationale'] == ledger['decision_rationale'] and
              report['status'] == ledger['status'] and report['selected_id'] == ledger['selected_id'],
              'Episode report and authoritative ledger differ')
    return ledger, dict(result_manifest_sha256=c.sha(results / 'manifest.json'),
        agent_manifest_sha256=c.sha(results / 'agent/manifest.json'),
        ledger_sha256=c.sha(results / 'agent/ledger.json'),
        agent_report_sha256=c.sha(results / 'agent-report.json'))


def greatest(rows, field):
    """Descriptive ties from the pre-measure board, not an inferred agent reason."""
    rows = [r for r in rows if not r['attempted']]
    if not rows:
        return []
    best = max(r[field] for r in rows)
    return sorted(r['candidate_id'] for r in rows if r[field] == best)


def audit_ledger(ledger):
    charged = [e for e in ledger['events'] if 'charged_attempt' in e]
    c.require([e['charged_attempt'] for e in charged] == list(range(1,len(charged)+1)) and
              ledger['charged_attempts'] == len(charged), 'Charged probe count/sequence differs')
    c.require(len(charged) <= ledger['limits']['measurement_attempts'], 'Episode exceeded paid budget')
    rationale = ledger['decision_rationale']
    decisions = {d['tool_sequence']:d for d in rationale['selection_decisions']}
    measurements = {m['tool_sequence']:m for m in rationale['measurements']}
    c.require(len(decisions) == len(rationale['selection_decisions']) == len(charged) and
              len(measurements) == len(rationale['measurements']) == len(charged),
              'One unique decision and measurement link required per charged probe')
    model_events = {m['tool_sequence']:m for m in ledger['model_events'] if m.get('tool_sequence') is not None}
    previous, rows = [], []
    for event in charged:
        sequence = event['sequence']
        c.require(sequence in decisions and sequence in measurements and sequence in model_events,
                  'Charged probe lacks decision/measurement/model provenance')
        decision, measurement, call = decisions[sequence], measurements[sequence], model_events[sequence]
        identity = event.get('candidate_id')
        c.require(decision['candidate_id'] == measurement.get('candidate_id') == identity and
                  decision['charged_attempt'] == event['charged_attempt'] and
                  decision['decision_summary'] == event.get('decision_summary'),
                  'Logged reason or candidate/probe identity differs')
        c.require(decision.get('verified') is False and decision['author'] in ('model','policy'),
                  'Decision note must retain its unverified author attribution')
        context = (decision.get('action_context') or call.get('action_context') or
                   call.get('public_context'))
        digest = c.digest(context)
        c.require((decision.get('action_context_sha256') or decision['public_context_sha256']) == digest and
                  decision['public_context_sha256'] == digest and
                  (call.get('action_context') or call.get('public_context')) == context and
                  (call.get('action_context_sha256') or call.get('public_context_sha256')) == digest,
                  'Pre-measurement context hash/provenance differs')
        c.require(context['attempted_candidate_ids'] == previous and
                  event['charged_before'] == len(previous), 'Pre-measurement paid prefix differs')
        observed_ids = [r['candidate_id'] for r in context['observations']]
        c.require(len(set(observed_ids)) == len(observed_ids) and set(observed_ids) <= set(previous),
                  'Pre-measurement snapshot exposes an uncharged/current outcome')
        for observation in context['observations']:
            source = next(e['observation'] for e in charged
                          if e.get('candidate_id') == observation['candidate_id'] and e['sequence'] < sequence)
            c.require(all(source.get(k, 'success' if k == 'status' else None) == v
                          for k,v in observation.items()),
                      'Snapshot prior observation differs from its earlier paid outcome')
        board = context.get('selection_board')
        candidate = None
        if board:
            candidates = board['rows']
            c.require({r['candidate_id'] for r in candidates} ==
                      {r['candidate_id'] for r in context['candidates']}, 'Advice board roster differs')
            c.require(all(r['attempted'] == (r['candidate_id'] in previous) and
                          (r.get('paid_verification') is None or r['candidate_id'] in previous)
                          for r in candidates), 'Board exposes uncharged verification')
            predictions = {}
            for prior_event in ledger['events']:
                if prior_event['sequence'] < sequence and prior_event.get('tool') == 'predict':
                    for value in prior_event.get('public_result', {}).get('predictions', []):
                        if 'current_grouped_ml' in value:
                            predictions[value['candidate_id']] = value['current_grouped_ml']
            reconstructed = support.build_grouped_decision_board(context['candidates'], predictions,
                previous, [e['observation'] for e in charged
                           if e['sequence'] < sequence and 'observation' in e],
                area_cap=ledger['constraints']['area_delta_lut4_cap'],
                clock_mhz=ledger['constraints']['clock_mhz'])
            if board.get('schema') == support.SCHEMA:
                c.require(reconstructed == board, 'Advice board differs from pre-probe public predictions/features')
            else:
                c.require(board.get('schema') == 'isaforge-grouped-decision-board-v1',
                          'Unsupported historical advice-board schema')
                # v1 did not recommend utility or log action_context explicitly.
                # Validate its recorded rows against recomputed public fields;
                # never retrofit a v2 recommendation into the historical advice.
                rebuilt = {r['candidate_id']:r for r in reconstructed['rows']}
                c.require(all(all(rebuilt[r['candidate_id']].get(k) == v for k,v in r.items())
                              for r in board['rows']) and
                          board['advisory_default_candidate_id'] == reconstructed['advisory_default_candidate_id'],
                          'Historical advice board differs from pre-probe public predictions/features')
            candidate = next((r for r in candidates if r['candidate_id'] == identity), None)
            c.require(candidate is not None and not candidate['attempted'], 'Probe absent/already paid in board')
            c.require(decision['advisory_default_candidate_id'] == board['advisory_default_candidate_id'] and
                      decision.get('utility_recommendation_candidate_id') == board.get('utility_recommendation_candidate_id'),
                      'Advice IDs differ from pre-measurement board')
        outcome = event.get('observation')
        verification = None
        if outcome is not None:
            c.require(measurement['ledger_observation_sha256'] == c.digest(outcome),
                      'Paid ledger observation hash differs')
            public_outcome = measurement['public_observation']
            c.require(measurement['public_observation_sha256'] == c.digest(public_outcome) and
                      all(outcome.get(k, 'success' if k == 'status' else None) == v
                          for k,v in public_outcome.items()), 'Public paid observation hash/projection differs')
            verification = support._paid_status(outcome,
                area_cap=ledger['constraints']['area_delta_lut4_cap'],
                clock_mhz=ledger['constraints']['clock_mhz'])
            c.require(decision['paid_verification'] == verification,
                      'Recorded paid feasibility differs from measured fields')
        rows.append(dict(probe=event['charged_attempt'], tool_sequence=sequence, candidate_id=identity,
            formula=candidate.get('formula') if candidate else None,
            logged_reason=dict(text=decision.get('decision_summary'), author=decision['author'],
                verified=False, interpretation='Recorded decision note; not validated reasoning or chain of thought.'),
            public_advice=(dict(pairwise_rank=candidate['pairwise_rank_position'],
                pairwise_recommendation_id=board['advisory_default_candidate_id'],
                utility_rank=candidate.get('factorized_decision_rank'),
                utility_recommendation_id=board.get('utility_recommendation_candidate_id'),
                utility_score_ratio=candidate.get('decision_score_ratio_to_recommendation'),
                feasibility_score=candidate['factorized_feasibility_score'],
                analytic_cycle_reduction=candidate['analytic_cycle_reduction'],
                frequency_max_ids=greatest(board['rows'],'frequency_count'),
                merit_max_ids=greatest(board['rows'],'merit_saved_cycles'),
                analytic_max_ids=greatest(board['rows'],'analytic_cycle_reduction'),
                uncertainty_calibrated=False) if candidate else None),
            host_descriptive_comparison=(dict(
                followed_pairwise_advice=identity == board['advisory_default_candidate_id'],
                followed_utility_advice=(identity == board['utility_recommendation_candidate_id']
                    if board.get('utility_recommendation_candidate_id') else None),
                interpretation='Post-episode comparison of public fields; not an inferred agent intention.')
                if candidate else dict(interpretation='Pre-measurement board unavailable; no advice explanation inferred.')),
            observed_verification=verification,
            measurement_seconds=outcome.get('measurement_seconds') if outcome else None,
            provenance=dict(action_context_sha256=digest,
                model_decision_call=call['call'], action_context_role=decision.get('action_context_role'),
                action_context_provider_call=decision.get('action_context_provider_call'),
                measurement_id=measurement.get('measurement_id'),
                ledger_observation_sha256=measurement.get('ledger_observation_sha256'),
                training_sha256=ledger.get('training_sha256'),
                grouped_predictions_sha256=ledger.get('grouped_predictions_sha256'))))
        previous.append(identity)
    return dict(schema='isaforge-postepisode-decision-audit-v1',
        scope='Post-episode deterministic explanation audit; no feedback to policies or hidden-pool outcome decoding.',
        charged_probes=len(charged), paid_budget=ledger['limits']['measurement_attempts'],
        unused_budget=ledger['limits']['measurement_attempts']-len(charged),
        model_decisions=len(ledger['model_events']), provider_calls=ledger['provider_calls'],
        provider_calls_semantics='Bridge API telemetry; not model decision count.',
        selected_id=ledger['selected_id'], episode_status=ledger['status'], probes=rows,
        limitations=['Logged reasons are unverified model/policy notes; no hidden chain of thought is inferred.',
            'Scores and ensemble spread are uncalibrated advice, not feasibility labels.',
            'Historical v1 boards did not log utility recommendations; missing advice remains unavailable rather than retroactively inferred.',
            'Observed outcomes are checked only against this episode’s paid ledger projection; full native replay is separate.',
            'One episode cannot establish that explanation or reviewer support improves decision quality.'])


def build(results=RESULTS, output=OUTPUT):
    ledger, provenance = authenticated_episode(results)
    report = audit_ledger(ledger)
    report['provenance'] = dict(provenance, script_sha256=c.sha(__file__))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    c.seal(output / 'decision-audit.json', report)
    lines = ['# Agent decision explanation audit', '',
        f"Paid probes: **{report['charged_probes']}/{report['paid_budget']}**, unused budget: **{report['unused_budget']}**. "
        f"Logged model decisions: **{report['model_decisions']}**; API-provider telemetry: **{report['provider_calls']}**.", '',
        'This report validates existing board/rationale evidence. It adds no controller intervention and infers no hidden reasoning. '
        'Public advice below precedes its probe; the feasibility observation appears afterward.', '']
    for row in report['probes']:
        advice, paid = row['public_advice'], row['observed_verification']
        lines += [f"## Probe {row['probe']}: `{row['formula'] or row['candidate_id']}`", '',
            f"Recorded {row['logged_reason']['author']} note (unverified):", '',
            '> ' + (row['logged_reason']['text'] or '(No reason recorded.)').replace('\n','\n> '), '']
        if advice:
            lines += [f"Public advice: pairwise rank **{advice['pairwise_rank']}**, utility rank **{advice['utility_rank'] if advice['utility_rank'] is not None else 'not logged'}**, "
                f"utility-score ratio **{advice['utility_score_ratio'] if advice['utility_score_ratio'] is not None else 'not logged'}**. "
                f"Followed pairwise/utility advice: **{row['host_descriptive_comparison']['followed_pairwise_advice']} / "
                f"{row['host_descriptive_comparison']['followed_utility_advice'] if row['host_descriptive_comparison']['followed_utility_advice'] is not None else 'not logged'}**. "
                f"Uncalibrated feasibility score **{advice['feasibility_score']:.6f}**; analytic cycle reduction "
                f"**{100*advice['analytic_cycle_reduction']:.6f}%**.", '']
        else:
            lines += ['Public advice board unavailable; no advice explanation inferred.', '']
        lines += [f"Observed host result: **{paid['status'] if paid else 'unavailable'}**. "
            f"Charged measurement seconds: **{row['measurement_seconds']}**.", '',
            f"Pre-measurement context SHA256: `{row['provenance']['action_context_sha256']}`. "
            f"Model decision call: `{row['provenance']['model_decision_call']}`.", '']
    lines += ['## Interpretation and reproduction', '', *['- '+x for x in report['limitations']], '',
        '```sh', '.venv/bin/python ' + SOURCE + ' --results ' +
        shlex.quote(str(Path(results).resolve().relative_to(ROOT)) if Path(results).resolve().is_relative_to(ROOT)
                    else str(Path(results).resolve())) + ' --output ' +
        shlex.quote(str(output.resolve().relative_to(ROOT)) if output.resolve().is_relative_to(ROOT)
                    else str(output.resolve())), '```', '',
        'Machine-readable advice, heuristic ties, hashes and measured feasibility: [decision-audit.json](decision-audit.json).']
    (output / 'README.md').write_text('\n'.join(lines)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=RESULTS)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.results,args.output)
    print(dict(probes=result['charged_probes'], unused_budget=result['unused_budget'], output=str(args.output)))

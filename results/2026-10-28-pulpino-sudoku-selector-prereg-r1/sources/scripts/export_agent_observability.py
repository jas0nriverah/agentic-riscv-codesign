#!/usr/bin/env python3
"""Verify sealed replay artifacts and export a local SQLite experiment view.

Read-only with respect to source runs. The derived database is not the ledger.
No telemetry is uploaded. Release identity binds the frozen run protocol.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c


def export(run_dir, output):
    run_dir, output = Path(run_dir).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(run_dir):
        raise ValueError('use a fresh output outside the sealed run')
    manifest = c.unseal(run_dir/'manifest.json')
    for name, expected in manifest.items():
        path = (run_dir/name).resolve()
        if not path.is_relative_to(run_dir) or c.sha(path) != expected:
            raise ValueError('artifact integrity failure')
    protocol, report = c.unseal(run_dir/'protocol.json'), c.unseal(run_dir/'report.json')
    release = c.sha(run_dir/'protocol.json')
    if report['protocol_sha256'] != release:
        raise ValueError('protocol binding mismatch')
    runs = report.get('runs')
    if runs is None and report.get('schema') == 'isaforge-codex-chat-selector-report-v1':
        runs = [dict(target=report['target'], policy='live-codex-subagent',
            status=report['status'], speedup=report['selected_speedup'],
            charged_attempts=report['charged_attempts'], ledger='ledger.json',
            ledger_sha256=manifest['ledger.json'])]
    if runs is None and report.get('schema') == 'isaforge-grouped-current-model-agent-report-v1':
        provider = report.get('provider') or {}
        policy = provider.get('provider', 'unknown') if isinstance(provider, dict) else str(provider)
        runs = [dict(target=report['target_benchmark'], policy=policy,
            status=report['status'], speedup=report['selected_speedup'],
            charged_attempts=report['charged_attempts'], ledger='ledger.json',
            ledger_sha256=manifest['ledger.json'])]
    if runs is None:
        raise ValueError('unsupported report schema')
    ledgers = []
    for run in runs:
        path = (run_dir/run['ledger']).resolve()
        if not path.is_relative_to(run_dir) or c.sha(path) != run['ledger_sha256']:
            raise ValueError('ledger binding mismatch')
        ledgers.append(c.unseal(path))
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output)
    try:
        db.executescript('''
        CREATE TABLE releases (release_id TEXT PRIMARY KEY, protocol_json TEXT NOT NULL);
        CREATE TABLE episodes (episode INTEGER PRIMARY KEY, release_id TEXT, target TEXT,
          policy TEXT, status TEXT, speedup REAL, charged_attempts INTEGER, ledger_sha256 TEXT);
        CREATE TABLE decisions (episode INTEGER, decision INTEGER, status TEXT,
          tool_sequence INTEGER, elapsed_seconds REAL, PRIMARY KEY(episode,decision));
        CREATE TABLE model_calls (episode INTEGER, decision INTEGER, call INTEGER, role TEXT,
          trigger_reason TEXT, model TEXT, status TEXT, input_tokens INTEGER, output_tokens INTEGER,
          total_tokens INTEGER, usage_complete INTEGER, elapsed_seconds REAL);
        CREATE TABLE retrievals (episode INTEGER, decision INTEGER, mode TEXT,
          corpus_sha256 TEXT, query TEXT, returned_ids TEXT, elapsed_seconds REAL);
        CREATE TABLE context_windows (episode INTEGER, decision INTEGER, context_sha256 TEXT,
          serialized_bytes INTEGER, source_training_rows INTEGER, exposed_training_rows INTEGER,
          retrieved_memory_bytes INTEGER, max_memory_bytes INTEGER,
          context_policy TEXT, selection_policy TEXT, exposed_records_json TEXT,
          compact_byte_ceiling INTEGER, compact_payload_bytes INTEGER,
          compact_serialization_format TEXT, serialized_public_context_bytes INTEGER,
          serialized_history_bytes INTEGER, serialized_retrieved_object_bytes INTEGER,
          serialization_format TEXT,
          PRIMARY KEY(episode,decision));
        CREATE TABLE tools (episode INTEGER, sequence INTEGER, tool TEXT, status TEXT,
          charged_attempt INTEGER, evidence_json TEXT);
        CREATE TABLE host_events (episode INTEGER, sequence INTEGER, type TEXT,
          reason TEXT, error_type TEXT, candidate_id TEXT, model_calls INTEGER,
          provider_calls INTEGER, tool_calls INTEGER, charged_attempts INTEGER);
        CREATE TABLE decision_rationales (episode INTEGER PRIMARY KEY,
          finalization_source TEXT, decision_call INTEGER, tool_sequence INTEGER,
          public_context_sha256 TEXT, summary TEXT, summary_author TEXT,
          summary_verified INTEGER, context_json TEXT, host_facts_json TEXT,
          policy_identity_json TEXT, model_call_references_json TEXT, rationale_json TEXT);
        CREATE TABLE rationale_measurements (episode INTEGER, measurement_id TEXT,
          candidate_id TEXT, tool_sequence INTEGER, charged_attempt INTEGER, status TEXT,
          public_observation_sha256 TEXT, ledger_observation_sha256 TEXT,
          evidence_json TEXT, PRIMARY KEY(episode,measurement_id));
        CREATE TABLE rationale_selection_decisions (episode INTEGER, tool_sequence INTEGER,
          charged_attempt INTEGER, candidate_id TEXT, decision_summary TEXT, author TEXT,
          verified INTEGER, public_context_sha256 TEXT, pairwise_rank_position INTEGER,
          advisory_default_candidate_id TEXT, deviation_from_advisory INTEGER,
          paid_verification_json TEXT, PRIMARY KEY(episode,tool_sequence));
        ''')
        db.execute('INSERT INTO releases VALUES (?,?)', (release, json.dumps(protocol, sort_keys=True)))
        for index, (run, ledger) in enumerate(zip(runs, ledgers)):
            db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?)',
                (index, release, run['target'], run['policy'], run['status'],
                 run['speedup'], run['charged_attempts'], run['ledger_sha256']))
            for event in ledger['model_events']:
                decision = event['call']
                db.execute('INSERT INTO decisions VALUES (?,?,?,?,?)',
                    (index, decision, event['status'], event.get('tool_sequence'), event['elapsed_seconds']))
                for call in event.get('provider_trace', []):
                    usage = call['usage']
                    db.execute('INSERT INTO model_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (index, decision, call['call'], call['role'], call.get('trigger'),
                         call['identity'].get('model'), call['status'], usage.get('input_tokens'), usage.get('output_tokens'),
                         usage.get('total_tokens'), call['usage_complete'], call['elapsed_seconds']))
                if (not event.get('provider_trace') and
                        protocol.get('provider') in ('codex-chat-bridge', 'codex-chat')):
                    db.execute('INSERT INTO model_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (index, decision, decision, 'interactive-subagent',
                         None, protocol['model_label'], event['status'], None, None, None,
                         False, event['elapsed_seconds']))
                memory = event.get('memory_trace')
                if memory:
                    db.execute('INSERT INTO retrievals VALUES (?,?,?,?,?,?,?)',
                        (index, decision, memory['mode'], memory['manifest']['corpus_sha256'],
                         memory['query'], json.dumps(memory['returned_ids']), memory['elapsed_seconds']))
                context = event.get('public_context')
                if isinstance(context, dict):
                    serialized_bytes = len(json.dumps(context, sort_keys=True,
                        ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8'))
                    # These are exact JSON byte counts, separate from provider
                    # tokens. Retain the historical compact count and expose
                    # explicitly named counts using Responses-style JSON.
                    json_bytes = lambda value: len(json.dumps(value, sort_keys=True,
                        allow_nan=False).encode('utf-8'))
                    public_context_bytes = json_bytes(context)
                    history_bytes = (json_bytes(context['historical_measurements'])
                                     if 'historical_measurements' in context else None)
                    retrieved_bytes = (json_bytes(context['retrieved_memory'])
                                       if 'retrieved_memory' in context else 0)
                    compact_payload_bytes = (len(json.dumps(context['retrieved_memory'],
                        sort_keys=True, allow_nan=False, separators=(',', ':')).encode('utf-8'))
                        if 'retrieved_memory' in context else 0)
                    if memory:
                        for key, expected in (
                                ('serialized_request_bytes', public_context_bytes),
                                ('serialized_history_bytes', history_bytes),
                                ('serialized_retrieved_memory_bytes', retrieved_bytes)):
                            if key in memory and memory[key] != expected:
                                raise ValueError('context byte accounting mismatch: '+key)
                    exposed_records = memory.get('exposed_records') if memory else None
                    db.execute('INSERT INTO context_windows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (index, decision, event.get('public_context_sha256'), serialized_bytes,
                         memory.get('source_training_rows') if memory else None,
                         memory.get('exposed_training_rows') if memory else None,
                         memory.get('retrieved_memory_bytes') if memory else None,
                         memory.get('max_memory_bytes') if memory else None,
                         memory.get('context_policy') if memory else None,
                         memory.get('selection_policy') if memory else None,
                         json.dumps(exposed_records, sort_keys=True) if exposed_records is not None else None,
                         memory.get('max_memory_bytes') if memory else None,
                         compact_payload_bytes,
                         memory.get('memory_budget_format') if memory else None,
                         public_context_bytes, history_bytes, retrieved_bytes,
                         'UTF-8 json.dumps(sort_keys=True, allow_nan=False)'))
            for event in ledger['events']:
                db.execute('INSERT INTO tools VALUES (?,?,?,?,?,?)',
                    (index, event['sequence'], event['tool'], event['status'],
                     event.get('charged_attempt'), json.dumps(event, sort_keys=True)))
            for sequence, event in enumerate(ledger.get('host_events', []), start=1):
                db.execute('INSERT INTO host_events VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (index, sequence, event.get('type'), event.get('reason'),
                     event.get('error_type'), event.get('candidate_id'),
                     event.get('model_calls'), event.get('provider_calls'), event.get('tool_calls'),
                     event.get('charged_attempts')))
            rationale = ledger.get('decision_rationale')
            if rationale:
                note = rationale.get('summary') or {}
                db.execute('INSERT INTO decision_rationales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (index, rationale['finalization_source'], rationale['decision_call'],
                     rationale['tool_sequence'], rationale['public_context_sha256'],
                     note.get('text'), note.get('author'), note.get('verified'),
                     json.dumps(rationale['public_context'], sort_keys=True),
                     json.dumps(rationale['host_verified_facts'], sort_keys=True),
                     json.dumps(rationale['policy_identity'], sort_keys=True),
                     json.dumps(rationale['model_call_references'], sort_keys=True),
                     json.dumps(rationale, sort_keys=True)))
                for evidence in rationale['measurements']:
                    db.execute('INSERT INTO rationale_measurements VALUES (?,?,?,?,?,?,?,?,?)',
                        (index, evidence['measurement_id'], evidence.get('candidate_id'),
                         evidence['tool_sequence'], evidence['charged_attempt'], evidence['status'],
                         evidence.get('public_observation_sha256'),
                         evidence.get('ledger_observation_sha256'), json.dumps(evidence, sort_keys=True)))
                for decision in rationale.get('selection_decisions', []):
                    db.execute('INSERT INTO rationale_selection_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (index, decision['tool_sequence'], decision['charged_attempt'],
                         decision.get('candidate_id'), decision.get('decision_summary'),
                         decision.get('author'), decision.get('verified'),
                         decision.get('public_context_sha256'),
                         decision.get('pairwise_rank_position'),
                         decision.get('advisory_default_candidate_id'),
                         decision.get('deviation_from_advisory'),
                         json.dumps(decision.get('paid_verification'), sort_keys=True)))
        db.commit()
        return dict(release_id=release, episodes=len(ledgers),
            decisions=db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],
            retrievals=db.execute('SELECT COUNT(*) FROM retrievals').fetchone()[0],
            model_calls=db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0],
            context_windows=db.execute('SELECT COUNT(*) FROM context_windows').fetchone()[0],
            decision_rationales=db.execute('SELECT COUNT(*) FROM decision_rationales').fetchone()[0],
            rationale_measurements=db.execute('SELECT COUNT(*) FROM rationale_measurements').fetchone()[0],
            rationale_selection_decisions=db.execute('SELECT COUNT(*) FROM rationale_selection_decisions').fetchone()[0],
            host_events=db.execute('SELECT COUNT(*) FROM host_events').fetchone()[0])
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(export(args.run, args.output))

"""Fresh SQLite context views and CLI options; no model or hardware calls."""
import copy
import json
import sqlite3

import pytest

from isaforge import codesign as c
from isaforge.agent_memory import MemoryAugmentedPolicy
from scripts.export_agent_observability import export
from scripts import run_bounded_selector as runner
from test_budgeted_selection import history, public


class InspectingPolicy:
    identity = dict(provider='context-export-fixture')

    def choose(self, request):
        return dict(tool='finalize', arguments=dict(candidate_id=None, summary='Fixture.'))


def sealed_context_run(root, mode, *, wrong_byte_count=False):
    root.mkdir()
    policy = MemoryAugmentedPolicy(InspectingPolicy(), mode=mode,
                                   max_memory_bytes=3500, top_k=3)
    policy.choose(dict(historical_fit_rows=3, historical_measurements=history(),
        candidates=[public('t1')], attempted_candidate_ids=[]))
    context = policy.last_public_request
    trace = copy.deepcopy(policy.last_memory_trace)
    if wrong_byte_count:
        trace['serialized_request_bytes'] += 1
    ledger = dict(model_events=[dict(call=1, status='complete', tool_sequence=1,
        elapsed_seconds=.01, provider_trace=[], public_context=context,
        public_context_sha256=c.digest(context), memory_trace=trace)],
        events=[], host_events=[])
    c.seal(root/'protocol.json', dict(schema='context-export-fixture-v1', provider='controls'))
    c.seal(root/'ledger.json', ledger)
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
        runs=[dict(target='synthetic', policy=mode, status='finalized', speedup=1.,
            charged_attempts=0, ledger='ledger.json', ledger_sha256=c.sha(root/'ledger.json'))]))
    c.seal(root/'manifest.json', {name:c.sha(root/name) for name in
        ('protocol.json', 'ledger.json', 'report.json')})
    return context, trace


@pytest.mark.parametrize('mode', ['none', 'hybrid', 'no_history', 'budget_matched_history'])
def test_fresh_export_exposes_context_controls_and_exact_json_bytes(tmp_path, mode):
    root = tmp_path/'sealed-run'
    context, trace = sealed_context_run(root, mode)
    original_files = {path.name:c.sha(path) for path in root.iterdir()}
    output = tmp_path/'fresh.sqlite'
    counts = export(root, output)
    assert counts['context_windows'] == 1
    assert counts['model_calls'] == 0  # JSON bytes do not populate token accounting.
    with sqlite3.connect(output) as db:
        row = db.execute('''SELECT context_policy, selection_policy, exposed_records_json,
            compact_byte_ceiling, compact_payload_bytes, compact_serialization_format,
            serialized_public_context_bytes, serialized_history_bytes,
            serialized_retrieved_object_bytes, serialization_format
            FROM context_windows''').fetchone()
    assert row[0] == trace['context_policy']
    assert row[1] == trace['selection_policy']
    assert json.loads(row[2]) == trace['exposed_records']
    assert all(set(record) == {'candidate_id', 'record_sha256'} for record in json.loads(row[2]))
    assert row[3] == 3500
    retrieved = context.get('retrieved_memory')
    compact_bytes = (len(json.dumps(retrieved, sort_keys=True, allow_nan=False,
                                   separators=(',', ':')).encode('utf-8'))
                     if retrieved is not None else 0)
    assert row[4] == compact_bytes <= row[3]
    assert row[5] == trace['memory_budget_format']
    assert row[6] == trace['serialized_request_bytes']
    assert row[7] == trace['serialized_history_bytes']
    assert row[8] == trace['serialized_retrieved_memory_bytes']
    assert row[9] == trace['serialized_bytes_format']
    assert {path.name:c.sha(path) for path in root.iterdir()} == original_files
    with pytest.raises(ValueError, match='fresh output'):
        export(root, output)


def test_export_rejects_trace_byte_count_that_differs_from_bound_context(tmp_path):
    root = tmp_path/'sealed-run'
    sealed_context_run(root, 'no_history', wrong_byte_count=True)
    with pytest.raises(ValueError, match='context byte accounting mismatch'):
        export(root, tmp_path/'invalid.sqlite')


@pytest.mark.parametrize('mode', ['none', 'no_history', 'budget_matched_history'])
def test_cli_accepts_explicit_context_controls_and_retains_none_default(tmp_path, monkeypatch, mode):
    seen = []

    def fake_run(output, **kwargs):
        seen.append((output, kwargs))
        return dict(trajectories=0, endpoints=0, all_controls_match=True, llm_calls=0, new_native_jobs=0)

    monkeypatch.setattr(runner, 'run', fake_run)
    arguments = ['--output', str(tmp_path/'new-report'), '--target', 'sha256', '--seed', '0', '--cap', '64']
    if mode != 'none':
        arguments.extend(['--memory-mode', mode])
    runner.main(arguments)
    assert len(seen) == 1
    assert seen[0][1]['memory_mode'] == mode
    assert seen[0][1]['targets'] == ['sha256']
    assert not (tmp_path/'new-report').exists()


@pytest.mark.parametrize('mode', ['no_history', 'budget_matched_history'])
def test_programmatic_runner_accepts_controls_and_preserves_archived_query_prefixes(tmp_path, mode):
    report = runner.run(tmp_path/mode, targets=['sha256'], seeds=[0], caps=[64],
                        budget=1, memory_mode=mode)
    assert report['all_controls_match'] is True
    assert report['trajectories'] == report['endpoints'] == 10
    assert report['llm_calls'] == report['new_native_jobs'] == 0
    protocol = c.unseal(tmp_path/mode/'protocol.json')
    assert protocol['memory_mode'] == mode
    assert protocol['source_bindings']['scripts/run_bounded_selector.py'] == c.sha(c.ROOT/'scripts/run_bounded_selector.py')
    assert all(run['charged_attempts'] == 1 for run in report['runs'])

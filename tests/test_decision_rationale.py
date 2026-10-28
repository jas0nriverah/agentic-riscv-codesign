"""Trace-grounded final notes, entirely offline and without native jobs."""
import copy
import json
import sqlite3

from isaforge import codesign as c
from isaforge.agent_memory import MemoryAugmentedPolicy
from isaforge.bounded_selector import MatchedBaselinePolicy, run_selector
from scripts.export_agent_observability import export
from test_bounded_selector import action, inputs, session


class ModelPolicy:
    identity = dict(provider='openai-responses', model='offline-fixture')
    last_usage = {}

    def __init__(self):
        self.seen = []
        self.last_trace = []
        self.max_calls = 12
        self.calls = 0

    def choose(self, request):
        self.seen.append(copy.deepcopy(request))
        self.calls += 1
        self.last_trace = [dict(call=len(self.seen), role='primary',
            identity=self.identity, request_sha256=c.digest(request), status='complete',
            provider_call_charged=True, usage={}, usage_complete=False,
            elapsed_seconds=0)]
        if not request['observations']:
            return action('measure', candidate_id='t1')
        return action('finalize', candidate_id='t1', summary='Model note: t1 has zero area cost.')


def test_model_note_bound_to_exact_augmented_context_and_host_facts(tmp_path, inputs):
    inputs[3]['t1']['private_path'] = '/private/OUTCOME-CANARY'
    policy = ModelPolicy()
    wrapped = MemoryAugmentedPolicy(policy, mode='hybrid')
    result = run_selector(session(tmp_path, inputs), wrapped)
    note = result['decision_rationale']
    assert result['model_calls'] == result['tool_calls'] == 2
    assert result['charged_attempts'] == 1
    assert note['public_context'] == policy.seen[-1]
    assert note['public_context_sha256'] == c.digest(policy.seen[-1])
    assert 'retrieved_memory' in note['public_context']
    assert 'OUTCOME-CANARY' not in json.dumps(note)
    assert note['summary'] == dict(text='Model note: t1 has zero area cost.',
        author='model', verified=False, purpose='unverified decision note')
    facts = note['host_verified_facts']
    assert facts['selection'] == result['authoritative_selection']
    assert facts['selection']['area_delta_lut4'] == 40
    assert facts['selection']['correctness_verified'] is True
    assert facts['selected_measurement_id'] == 'tool-1'
    assert facts['constraints'] == dict(area_delta_lut4_cap=64, clock_mhz=12)
    evidence = note['measurements'][0]
    assert evidence['measurement_id'] == 'tool-1'
    assert evidence['candidate_id'] == 't1'
    assert evidence['public_observation_sha256'] == c.digest(evidence['public_observation'])
    assert evidence['ledger_observation_sha256'] == c.digest(inputs[3]['t1'])
    assert note['decision_call'] == note['tool_sequence'] == 2
    assert note['policy_identity'] == wrapped.identity
    assert note['policy_identity_sha256'] == c.digest(wrapped.identity)
    assert note['model_call_references'][-1]['provider_calls'][0]['request_sha256'] == note['public_context_sha256']
    saved = c.unseal(tmp_path/'ledger.json')
    assert saved['decision_rationale'] == note


def test_context_hash_deterministic_and_sensitive_to_public_evidence(tmp_path, inputs):
    hashes = []
    for folder in ('one', 'two'):
        result = run_selector(session(tmp_path/folder, inputs), ModelPolicy())
        hashes.append(result['decision_rationale']['public_context_sha256'])
    assert hashes[0] == hashes[1]
    changed = copy.deepcopy(inputs)
    changed[3]['t1']['measurement_seconds'] += 1
    result = run_selector(session(tmp_path/'changed', changed), ModelPolicy())
    assert result['decision_rationale']['public_context_sha256'] != hashes[0]


def test_model_sees_remaining_decision_turns_and_host_records_cap(tmp_path, inputs):
    policy = ModelPolicy()
    result = run_selector(session(tmp_path, inputs), policy, max_model_calls=2)
    assert [request['remaining']['decision_turns_after_this_response']
            for request in policy.seen] == [1, 0]
    assert [request['remaining']['provider_calls_available_including_this_response']
            for request in policy.seen] == [2, 1]
    assert result['limits']['model_decision_turns'] == 2
    assert result['provider_calls'] == 2
    assert result['decision_rationale']['public_context'] == policy.seen[-1]


def test_exhausted_provider_budget_closes_without_empty_decision(tmp_path, inputs):
    class Exhausted:
        identity = dict(provider='openai-responses', model='exhausted-fixture')
        max_calls = calls = 1

        def choose(self, request):
            raise AssertionError('must not make an empty decision after budget exhaustion')

    result = run_selector(session(tmp_path, inputs), Exhausted(), max_model_calls=3)
    assert result['status'] == 'host_fallback'
    assert result['model_calls'] == result['provider_calls'] == 0
    assert result['host_events'][0]['reason'] == 'provider_call_limit'
    assert result['decision_rationale']['summary'] is None


def test_rejected_summary_does_not_create_accepted_rationale(tmp_path, inputs):
    s = session(tmp_path, inputs)
    assert s.call(action('finalize', candidate_id='t1', summary='Invented observation.'))['status'] == 'error'
    assert 'decision_rationale' not in s.ledger
    s.call(action('finalize', candidate_id=None, summary='Baseline.'))
    rationale = s.ledger['decision_rationale']
    assert rationale['host_verified_facts']['selection'] == dict(
        candidate_id=None, status='baseline', speedup=1.0)
    assert rationale['measurements'] == []
    assert rationale['decision_call'] is None
    assert rationale['summary']['verified'] is False


def test_host_fallback_has_deterministic_facts_without_model_explanation(tmp_path, inputs):
    policy = ModelPolicy()
    result = run_selector(session(tmp_path, inputs), policy, max_model_calls=1)
    note = result['decision_rationale']
    assert result['status'] == 'host_fallback'
    assert result['model_calls'] == result['tool_calls'] == result['charged_attempts'] == 1
    assert 'agent_summary' not in result
    assert note['summary'] is None
    assert note['finalization_source'] == 'host'
    assert note['context_source'] == 'host_finalization_state'
    assert note['decision_call'] is note['tool_sequence'] is None
    assert note['host_verified_facts']['selection']['candidate_id'] == 't1'
    assert note['public_context']['incumbent']['candidate_id'] == 't1'
    assert len(note['model_call_references']) == 1
    assert note['public_context_sha256'] == c.digest(note['public_context'])


def test_failed_and_invalid_attempts_remain_evidence_without_success_labels(tmp_path, inputs):
    def failed(row):
        return dict(**row, status='failed', measurement_seconds=7, error='fixture failure')
    s = session(tmp_path, inputs, failed)
    s.call(action('measure', candidate_id='unknown'))
    s.call(action('measure', candidate_id='t1'))
    s.host_finalize('model_call_limit')
    evidence = s.ledger['decision_rationale']['measurements']
    assert [row['status'] for row in evidence] == ['error', 'failed']
    assert 'public_observation_sha256' not in evidence[0]
    assert evidence[1]['public_observation']['status'] == 'failed'
    assert 'speedup' not in evidence[1]['public_observation']
    assert s.ledger['decision_rationale']['host_verified_facts']['selection']['candidate_id'] is None
    assert s.ledger['decision_rationale']['host_verified_facts']['selected_measurement_id'] is None


def test_control_note_is_not_mislabeled_model_authored(tmp_path, inputs):
    result = run_selector(session(tmp_path, inputs), MatchedBaselinePolicy('frequency'))
    assert result['decision_rationale']['summary']['author'] == 'policy'
    assert result['decision_rationale']['summary']['verified'] is False


def test_sqlite_exports_rationale_and_measurement_evidence(tmp_path, inputs):
    root = tmp_path/'run'
    root.mkdir()
    result = run_selector(session(root, inputs), ModelPolicy())
    c.seal(root/'protocol.json', dict(provider='fixture'))
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'), runs=[dict(
        target='fixture', policy='fixture', status=result['status'], speedup=result['best_speedup'],
        charged_attempts=1, ledger='ledger.json', ledger_sha256=c.sha(root/'ledger.json'))]))
    c.seal(root/'manifest.json', {name:c.sha(root/name) for name in
        ('protocol.json', 'report.json', 'ledger.json')})
    counts = export(root, tmp_path/'trace.sqlite')
    assert counts['decision_rationales'] == counts['rationale_measurements'] == 1
    with sqlite3.connect(tmp_path/'trace.sqlite') as db:
        row = db.execute('SELECT finalization_source, summary_author, summary_verified, public_context_sha256, rationale_json FROM decision_rationales').fetchone()
        evidence = db.execute('SELECT measurement_id, candidate_id, public_observation_sha256 FROM rationale_measurements').fetchone()
    assert row[:3] == ('agent', 'model', 0)
    assert row[3] == result['decision_rationale']['public_context_sha256']
    assert json.loads(row[4]) == result['decision_rationale']
    assert evidence == ('tool-1', 't1', result['decision_rationale']['measurements'][0]['public_observation_sha256'])


def test_sqlite_exports_host_fallback_provider_accounting(tmp_path, inputs):
    class Exhausted:
        identity = dict(provider='openai-responses', model='exhausted-fixture')
        max_calls = calls = 1

        def choose(self, request):
            raise AssertionError('provider budget is already exhausted')

    root = tmp_path/'fallback-run'
    root.mkdir()
    result = run_selector(session(root, inputs), Exhausted(), max_model_calls=2)
    c.seal(root/'protocol.json', dict(provider='fixture'))
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'), runs=[dict(
        target='fixture', policy='fixture', status=result['status'], speedup=result['best_speedup'],
        charged_attempts=0, ledger='ledger.json', ledger_sha256=c.sha(root/'ledger.json'))]))
    c.seal(root/'manifest.json', {name:c.sha(root/name) for name in
        ('protocol.json', 'report.json', 'ledger.json')})
    counts = export(root, tmp_path/'fallback.sqlite')
    assert counts['host_events'] == counts['decision_rationales'] == 1
    with sqlite3.connect(tmp_path/'fallback.sqlite') as db:
        row = db.execute('SELECT reason, model_calls, provider_calls, tool_calls, charged_attempts '
                         'FROM host_events').fetchone()
    assert row == ('provider_call_limit', 0, 0, 0, 0)


def test_sqlite_exports_grouped_chat_context_and_retrieval_telemetry(tmp_path):
    root = tmp_path/'grouped-chat-run'
    root.mkdir()
    context = dict(schema='public-state-v1', historical_measurements=[],
                   retrieved_memory=dict(hits=[dict(record=dict(candidate_id='h1'))]))
    ledger = dict(model_events=[dict(call=1, status='complete', tool_sequence=1,
        elapsed_seconds=1.25, provider_trace=[], public_context=context,
        public_context_sha256=c.digest(context), memory_trace=dict(mode='hybrid',
            manifest=dict(corpus_sha256='a'*64), query='xor', returned_ids=['h1'],
            elapsed_seconds=.01, source_training_rows=100, exposed_training_rows=0,
            retrieved_memory_bytes=512, max_memory_bytes=40_000))],
        events=[], host_events=[])
    c.seal(root/'ledger.json', ledger)
    protocol = dict(provider='codex-chat', model_label='GPT-6.1 Sol selector subagent',
                    memory_mode='hybrid')
    c.seal(root/'protocol.json', protocol)
    report = dict(schema='isaforge-grouped-current-model-agent-report-v1',
        protocol_sha256=c.sha(root/'protocol.json'), target_benchmark='embench-crc32:ctx',
        provider=dict(provider='memory-augmented-policy-v1'), status='finalized',
        selected_speedup=1.05, charged_attempts=1)
    c.seal(root/'report.json', report)
    c.seal(root/'manifest.json', {name:c.sha(root/name) for name in
        ('protocol.json','report.json','ledger.json')})

    counts=export(root,tmp_path/'grouped.sqlite')
    assert counts['episodes']==counts['decisions']==counts['model_calls']==counts['retrievals']==1
    assert counts['context_windows']==1
    with sqlite3.connect(tmp_path/'grouped.sqlite') as db:
        assert db.execute('SELECT target,policy,status,charged_attempts FROM episodes').fetchone()==(
            'embench-crc32:ctx','memory-augmented-policy-v1','finalized',1)
        assert db.execute('SELECT role,model,usage_complete FROM model_calls').fetchone()==(
            'interactive-subagent','GPT-6.1 Sol selector subagent',0)
        assert db.execute('SELECT source_training_rows,exposed_training_rows,retrieved_memory_bytes,max_memory_bytes '
                          'FROM context_windows').fetchone()==(100,0,512,40_000)

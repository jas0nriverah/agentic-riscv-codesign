"""Trace-grounded final notes, entirely offline and without native jobs."""
import copy
import json
import sqlite3

import pytest

from isaforge import codesign as c
from isaforge.agent_memory import MemoryAugmentedPolicy
from isaforge.bounded_selector import MatchedBaselinePolicy, run_selector
from scripts.export_agent_observability import export
from test_bounded_selector import action, grouped_session, inputs, session


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


def seal_export_run(root, result):
    root.mkdir(parents=True, exist_ok=True)
    c.seal(root/'protocol.json', dict(provider='fixture'))
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'), runs=[dict(
        target='fixture', policy='fixture', status=result['status'], speedup=result['best_speedup'],
        charged_attempts=result['charged_attempts'], ledger='ledger.json',
        ledger_sha256=c.sha(root/'ledger.json'))]))
    c.seal(root/'manifest.json', {name:c.sha(root/name) for name in
        ('protocol.json', 'report.json', 'ledger.json')})


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
    decision = note['selection_decisions'][0]
    assert decision['decision_summary'] == 'Synthetic policy choice for protocol test.'
    assert decision['author'] == 'model' and decision['verified'] is False
    assert decision['candidate_id'] == 't1'
    assert len(decision['public_context_sha256']) == 64
    assert decision['paid_verification']['status'] == 'verified_feasible_improvement'
    assert decision['paid_verification']['area_delta_lut4'] == 40
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
    decisions = s.ledger['decision_rationale']['selection_decisions']
    assert decisions[0]['paid_verification'] is None
    assert decisions[1]['paid_verification'] == dict(
        status='failed_no_performance_or_hardware_label', measurement_seconds=7)


@pytest.mark.parametrize('outcome_status', [
    'verified_feasible_improvement', 'area_infeasible',
    'failed_no_performance_or_hardware_label',
])
def test_grouped_decision_links_later_outcome_without_changing_pre_attempt_context(
        tmp_path, inputs, outcome_status):
    if outcome_status == 'area_infeasible':
        inputs[3]['t2']['area_delta_lut4'] = 65
    elif outcome_status == 'failed_no_performance_or_hardware_label':
        inputs[3]['t2'] = dict(**inputs[0][1], status='failed',
                              measurement_seconds=7, error='fixture failure')

    class GroupedPolicy(ModelPolicy):
        def choose(self, request):
            self.seen.append(copy.deepcopy(request))
            if 'selection_board' not in request:
                return action('predict', candidate_ids=['t1', 't2', 't3'])
            if not request['attempted_candidate_ids']:
                return action('measure', candidate_id='t2')
            return action('finalize', candidate_id=request['incumbent']['candidate_id'],
                          summary='Use the host-verified incumbent.')

    policy = GroupedPolicy()
    result = run_selector(grouped_session(tmp_path, inputs), policy)
    pre_attempt = policy.seen[1]
    decision = result['decision_rationale']['selection_decisions'][0]
    assert decision['public_context_sha256'] == c.digest(pre_attempt)
    assert decision['pairwise_rank_position'] == 2
    assert decision['advisory_default_candidate_id'] == 't1'
    assert decision['deviation_from_advisory'] is True
    board = pre_attempt['selection_board']
    chosen_board_row = next(row for row in board['rows'] if row['candidate_id'] == 't2')
    assert decision['utility_recommendation_candidate_id'] == \
        board['utility_recommendation_candidate_id']
    assert decision['factorized_decision_rank'] == chosen_board_row['factorized_decision_rank']
    assert decision['decision_score_ratio_to_recommendation'] == \
        chosen_board_row['decision_score_ratio_to_recommendation']
    assert decision['deviation_from_utility_recommendation'] == \
        ('t2' != board['utility_recommendation_candidate_id'])
    assert pre_attempt['selection_board']['rows'][1]['paid_verification'] is None
    assert pre_attempt['observations'] == []
    assert decision['paid_verification']['status'] == outcome_status
    assert decision['verified'] is False
    if outcome_status == 'failed_no_performance_or_hardware_label':
        assert set(decision['paid_verification']) == {'status', 'measurement_seconds'}


def test_repeated_grouped_attempt_does_not_reuse_prior_paid_verification(tmp_path, inputs):
    class RepeatedPolicy(ModelPolicy):
        def choose(self, request):
            self.seen.append(copy.deepcopy(request))
            if 'selection_board' not in request:
                return action('predict', candidate_ids=['t1', 't2', 't3'])
            if len(self.seen) <= 3:
                return action('measure', candidate_id='t2')
            return action('finalize', candidate_id='t2', summary='Use the paid incumbent.')

    result = run_selector(grouped_session(tmp_path, inputs), RepeatedPolicy())
    first, repeated = result['decision_rationale']['selection_decisions']
    assert first['paid_verification']['verified_feasible'] is True
    assert repeated['paid_verification'] is None
    assert result['charged_attempts'] == 2


def test_control_note_is_not_mislabeled_model_authored(tmp_path, inputs):
    result = run_selector(session(tmp_path, inputs), MatchedBaselinePolicy('frequency'))
    assert result['decision_rationale']['summary']['author'] == 'policy'
    assert result['decision_rationale']['summary']['verified'] is False


def test_sqlite_exports_rationale_and_measurement_evidence(tmp_path, inputs):
    root = tmp_path/'run'
    root.mkdir()
    result = run_selector(session(root, inputs), ModelPolicy())
    seal_export_run(root, result)
    counts = export(root, tmp_path/'trace.sqlite')
    assert counts['decision_rationales'] == counts['rationale_measurements'] == 1
    assert counts['rationale_selection_decisions'] == 1
    assert counts['action_contexts'] == len(result['model_events'])
    with sqlite3.connect(tmp_path/'trace.sqlite') as db:
        row = db.execute('SELECT finalization_source, summary_author, summary_verified, public_context_sha256, rationale_json FROM decision_rationales').fetchone()
        evidence = db.execute('SELECT measurement_id, candidate_id, public_observation_sha256 FROM rationale_measurements').fetchone()
        decision = db.execute('SELECT candidate_id, decision_summary, author, verified, paid_verification_json FROM rationale_selection_decisions').fetchone()
        action_context = db.execute('SELECT context_sha256, action_role, context_json '
            'FROM action_contexts WHERE episode=0 AND decision=1').fetchone()
    assert row[:3] == ('agent', 'model', 0)
    assert row[3] == result['decision_rationale']['public_context_sha256']
    assert json.loads(row[4]) == result['decision_rationale']
    assert evidence == ('tool-1', 't1', result['decision_rationale']['measurements'][0]['public_observation_sha256'])
    assert decision[:4] == ('t1', 'Synthetic policy choice for protocol test.', 'model', 0)
    assert json.loads(decision[4]) == result['decision_rationale']['selection_decisions'][0]['paid_verification']
    assert json.loads(decision[4])['status'] == 'verified_feasible_improvement'
    assert action_context[0] == result['model_events'][0]['action_context_sha256']
    assert action_context[1] is None
    assert json.loads(action_context[2]) == result['model_events'][0]['action_context']


def test_sqlite_action_context_export_supports_legacy_ledgers(tmp_path, inputs):
    root = tmp_path/'legacy-run'
    root.mkdir()
    result = run_selector(session(root, inputs), ModelPolicy())
    for event in result['model_events']:
        for field in ('action_context', 'action_context_sha256', 'action_context_role',
                      'action_context_provider_call', 'action_context_trigger',
                      'provider_action_context_sha256'):
            event.pop(field, None)
    c.seal(root/'ledger.json', result)
    seal_export_run(root, result)
    export(root, tmp_path/'legacy.sqlite')
    with sqlite3.connect(tmp_path/'legacy.sqlite') as db:
        saved = db.execute('SELECT context_sha256, context_json, provider_request_sha256, '
            'action_role, provider_call, trigger FROM action_contexts '
            'WHERE episode=0 AND decision=1').fetchone()
    assert saved[0] == c.digest(result['model_events'][0]['public_context'])
    assert json.loads(saved[1]) == result['model_events'][0]['public_context']
    assert saved[2:] == (None, None, None, None)


@pytest.mark.parametrize('field', ['action_context_sha256', 'provider_action_context_sha256'])
def test_sqlite_action_context_export_rejects_hash_mismatch(tmp_path, inputs, field):
    root = tmp_path/field
    root.mkdir()
    result = run_selector(session(root, inputs), ModelPolicy())
    result['model_events'][0][field] = '0' * 64
    c.seal(root/'ledger.json', result)
    seal_export_run(root, result)
    with pytest.raises(ValueError, match='context hash mismatch|provider request hash'):
        export(root, tmp_path/(field+'.sqlite'))


@pytest.mark.parametrize('corruption', [
    'missing_call', 'missing_origin_call', 'duplicate_call', 'role', 'trigger', 'request_hash',
    'status', 'not_dispatched',
])
def test_sqlite_action_context_export_checks_provider_trace_origin(
        tmp_path, inputs, corruption):
    root = tmp_path/'trace-linkage-run'
    root.mkdir()
    result = run_selector(session(root, inputs), ModelPolicy())
    event = result['model_events'][0]
    event.update(action_context_role='primary', action_context_provider_call=1,
                 action_context_trigger='primary',
                 provider_action_context_sha256=event['action_context_sha256'])
    trace = event['provider_trace'][0]
    trace['trigger'] = 'primary'
    if corruption == 'missing_call':
        event['action_context_provider_call'] = 999
    elif corruption == 'missing_origin_call':
        event.pop('action_context_provider_call')
    elif corruption == 'duplicate_call':
        event['provider_trace'].append(copy.deepcopy(trace))
    elif corruption == 'role':
        trace['role'] = 'escalation'
    elif corruption == 'trigger':
        trace['trigger'] = 'utility_override_review'
    elif corruption == 'request_hash':
        trace['request_sha256'] = '0' * 64
    elif corruption == 'status':
        trace['status'] = 'invalid_action'
    else:
        trace['provider_call_charged'] = False
    c.seal(root/'ledger.json', result)
    seal_export_run(root, result)

    with pytest.raises(ValueError, match='provider trace linkage mismatch'):
        export(root, tmp_path/'trace-linkage.sqlite')


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

"""Context ablation contracts; synthetic software checks, no LLM quality claim."""
import copy
import json

import pytest

from isaforge.agent_memory import (
    ABLATION_MODES, MODES, POLICY_MODES, MemoryAugmentedPolicy, digest,
)
from isaforge.bounded_selector import MatchedBaselinePolicy, ReplaySelectionSession, run_selector
from test_budgeted_selection import history, measured, predictions, public


class InspectingPolicy:
    identity = dict(provider='context-control-test')

    def __init__(self):
        self.requests = []

    def choose(self, request):
        self.requests.append(copy.deepcopy(request))
        return dict(tool='finalize', arguments=dict(candidate_id=None, summary='Test only.'))


def request():
    return dict(historical_fit_rows=3, historical_measurements=history(),
        candidates=[public('t1'), public('t2', 'sub(in0,in1)')],
        attempted_candidate_ids=[])


def serialized_bytes(value):
    return len(json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8'))


def test_context_controls_are_opt_in_and_none_preserves_exact_public_request():
    assert ABLATION_MODES == ('no_history', 'budget_matched_history')
    assert not set(ABLATION_MODES) & set(MODES)
    assert set(POLICY_MODES) == set(MODES) | set(ABLATION_MODES)
    original = request()
    before = copy.deepcopy(original)
    sink = InspectingPolicy()
    policy = MemoryAugmentedPolicy(sink, mode='none')
    policy.choose(original)
    assert sink.requests == [before]
    assert original == before
    trace = policy.last_memory_trace
    assert trace['context_policy'] == 'full_history'
    assert trace['exposed_record_count'] == 3
    assert trace['serialized_request_bytes'] == serialized_bytes(before)
    assert trace['serialized_retrieved_memory_bytes'] == 0


def test_no_history_removes_all_historical_examples_and_retains_host_cohort():
    original = request()
    before = copy.deepcopy(original)
    sink = InspectingPolicy()
    policy = MemoryAugmentedPolicy(sink, mode='no_history')
    policy.choose(original)
    visible = sink.requests[-1]
    assert visible['historical_measurements'] == []
    assert 'retrieved_memory' not in visible
    assert visible['historical_context_policy'] == 'no_history'
    assert visible['historical_fit_rows'] == 3
    assert policy.memory.records == before['historical_measurements']
    assert original == before
    trace = policy.last_memory_trace
    assert trace['exposed_records'] == trace['hits'] == trace['returned_ids'] == []
    assert trace['exposed_record_count'] == trace['retrieved_memory_bytes'] == 0
    assert trace['serialized_request_bytes'] == serialized_bytes(visible)
    assert trace['serialized_history_bytes'] == serialized_bytes([])


def test_budget_control_uses_whole_id_ordered_records_without_similarity_scores():
    original = request()
    original['historical_measurements'].reverse()
    sink = InspectingPolicy()
    policy = MemoryAugmentedPolicy(sink, mode='budget_matched_history', top_k=2)
    policy.choose(original)
    visible = sink.requests[-1]
    hits = visible['retrieved_memory']['hits']
    assert [hit['record']['candidate_id'] for hit in hits] == ['h1', 'h2']
    assert all(set(hit) == {'record', 'record_sha256'} for hit in hits)
    assert all(hit['record_sha256'] == digest(hit['record']) for hit in hits)
    assert visible['historical_context_policy'] == 'budget_matched_history'
    assert visible['historical_measurements'] == []
    trace = policy.last_memory_trace
    assert trace['selection_policy'] == 'candidate_id_ascending'
    assert trace['exposed_records'] == [
        dict(candidate_id=hit['record']['candidate_id'], record_sha256=hit['record_sha256'])
        for hit in hits]
    assert trace['serialized_request_bytes'] == serialized_bytes(visible)
    assert trace['serialized_retrieved_memory_bytes'] == serialized_bytes(visible['retrieved_memory'])
    # Query, roster order, and input history order cannot change ID selection.
    other = request()
    other['candidates'].reverse()
    other['attempted_candidate_ids'] = ['t1', 't2']
    second = MemoryAugmentedPolicy(InspectingPolicy(), mode='budget_matched_history', top_k=2)
    second.choose(other)
    assert second.last_memory_trace['exposed_records'] == trace['exposed_records']


@pytest.mark.parametrize('mode', ['hybrid', 'budget_matched_history'])
@pytest.mark.parametrize('ceiling', [256, 512, 3500])
def test_retrieval_and_control_share_explicit_byte_ceiling_with_no_padding(mode, ceiling):
    policy = MemoryAugmentedPolicy(InspectingPolicy(), mode=mode, top_k=3,
                                   max_memory_bytes=ceiling)
    policy.choose(request())
    visible = policy.last_public_request
    payload = visible['retrieved_memory']
    compact_bytes = len(json.dumps(payload, sort_keys=True, allow_nan=False,
                                   separators=(',', ':')).encode('utf-8'))
    assert compact_bytes == policy.last_memory_trace['retrieved_memory_bytes'] <= ceiling
    assert all(hit['record'] in history() for hit in payload['hits'])
    assert 'padding' not in payload and 'padding' not in visible
    assert policy.last_memory_trace['max_memory_bytes'] == ceiling
    assert 'actual whole-record sizes may differ' in policy.last_memory_trace['byte_budget_comparison']


@pytest.mark.parametrize('mode', ABLATION_MODES)
@pytest.mark.parametrize('contamination', ['workload', 'family'])
def test_controls_validate_target_exclusions_before_hiding_history(mode, contamination):
    value = request()
    if contamination == 'workload':
        value['historical_measurements'][0]['workload_group'] = 'target'
    else:
        value['historical_measurements'][0]['formula'] = value['candidates'][0]['formula']
    sink = InspectingPolicy()
    with pytest.raises(ValueError, match='contaminated'):
        MemoryAugmentedPolicy(sink, mode=mode).choose(value)
    assert sink.requests == []


@pytest.mark.parametrize('mode', ABLATION_MODES)
def test_controls_reject_roster_or_training_content_changes(mode):
    value = request()
    sink = InspectingPolicy()
    policy = MemoryAugmentedPolicy(sink, mode=mode)
    policy.choose(value)
    value['historical_measurements'][0]['area_delta_lut4'] += 1
    with pytest.raises(ValueError, match='historical memory changed'):
        policy.choose(value)
    value = request()
    value['candidates'][0]['formula'] = 'and(in0,in1)'
    with pytest.raises(ValueError, match='target candidate roster changed'):
        policy.choose(value)
    assert len(sink.requests) == 1


@pytest.mark.parametrize('mode', ABLATION_MODES)
def test_context_controls_preserve_host_charging_measurements_and_incumbent(tmp_path, mode):
    target = [public('t1'), public('t2', 'sub(in0,in1)')]
    training = history()
    paid = []

    def evaluate(row):
        paid.append(row['candidate_id'])
        return measured(row)

    session = ReplaySelectionSession(target, training, predictions(training, target, 0),
        evaluate, area_cap=64, budget=2, ledger_path=tmp_path/'ledger.json')
    policy = MemoryAugmentedPolicy(MatchedBaselinePolicy('merit'), mode=mode)
    result = run_selector(session, policy)
    assert result['status'] == 'finalized'
    assert result['charged_attempts'] == 2
    assert result['tool_calls'] == result['model_calls'] == 3
    assert set(paid) == {'t1', 't2'}
    assert result['selected_id'] in paid
    assert result['best_speedup'] == 1000/960
    assert result['replayed_target_measurement_seconds'] == 4
    for event in result['model_events']:
        assert event['memory_trace']['context_policy'] == mode
        assert event['public_context']['historical_measurements'] == []

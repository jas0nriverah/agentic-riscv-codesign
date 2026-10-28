"""Offline protocol tests, not live model quality experiments."""
import json
import pytest
from isaforge.selection_provider import (
    ResponsesSelectionProvider, ProviderError, ProviderBudgetError, InvalidActionError,
)
from isaforge.routed_selection import RoutedSelectionProvider


def response(name='measure', candidate_id='c0', summary='Select the leading public candidate.'):
    return dict(status='completed', output=[dict(type='function_call', name=name,
        arguments=json.dumps({'candidate_id': candidate_id,
            'decision_summary': summary}))],
        usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))


def provider(model, result, seen):
    def transport(payload, *args):
        seen.append(payload)
        if isinstance(result, Exception):
            raise result
        return result
    return ResponsesSelectionProvider(model, api_key='offline', transport=transport)


def test_valid_action_uses_primary_only():
    seen = []
    p = RoutedSelectionProvider(provider('small', response(), seen),
                                provider('large', response(), seen))
    assert p.choose({'public': 1})['tool'] == 'measure'
    assert p.calls == len(seen) == 1
    assert p.last_trace[0]['usage_complete'] is True


def _utility_override_request(*, provider_calls=2):
    return dict(remaining={
            'provider_calls_available_including_this_response': provider_calls},
        selection_board=dict(utility_recommendation_candidate_id='c0',
            utility_recommendation=dict(candidate_id='c0', factorized_decision_score=0.01),
            rows=[dict(candidate_id='c0', attempted=False,
                       decision_score_ratio_to_recommendation=1.0),
                  dict(candidate_id='c1', attempted=False,
                       decision_score_ratio_to_recommendation=0.1)]))


def test_utility_override_routes_for_review_before_any_measurement():
    seen = []
    primary = provider('small', response(candidate_id='c1',
        summary='Choose c1 because the public tree pattern is relevant.'), seen)
    stronger = provider('large', response(candidate_id='c0',
        summary='Use the top utility recommendation.'), seen)
    router = RoutedSelectionProvider(primary, stronger, max_calls=2,
        review_utility_overrides=True)

    action = router.choose(_utility_override_request())

    assert action['arguments']['candidate_id'] == 'c0'
    assert [call['model'] for call in seen] == ['small', 'large']
    first_request = json.loads(seen[0]['input'][0]['content'])
    review_request = json.loads(seen[1]['input'][0]['content'])
    assert 'routing_review' not in first_request
    assert review_request['routing_review']['trigger'] == (
        'primary_measurement_overrides_utility_recommendation')
    assert review_request['routing_review']['primary_action']['arguments']['candidate_id'] == 'c1'
    assert review_request['routing_review']['proposed_candidate_score_ratio'] == 0.1
    assert router.last_trace[0]['primary_action']['arguments']['candidate_id'] == 'c1'
    assert router.last_trace[1]['trigger'] == 'utility_override_review'
    assert router.last_trace[1]['reviewed_utility_recommendation_candidate_id'] == 'c0'
    assert router.calls == 2


def test_utility_override_review_is_skipped_when_only_one_call_is_available():
    seen = []
    router = RoutedSelectionProvider(
        provider('small', response(candidate_id='c1'), seen),
        provider('large', response(candidate_id='c0'), seen),
        max_calls=12, review_utility_overrides=True)

    action = router.choose(_utility_override_request(provider_calls=1))

    assert action['arguments']['candidate_id'] == 'c1'
    assert [call['model'] for call in seen] == ['small']
    assert router.last_trace[0]['utility_override_review_skipped'] == 'provider_budget'


def test_utility_recommendation_match_does_not_escalate():
    seen = []
    router = RoutedSelectionProvider(
        provider('small', response(candidate_id='c0'), seen),
        provider('large', response(candidate_id='c1'), seen),
        max_calls=2, review_utility_overrides=True)

    action = router.choose(_utility_override_request())

    assert action['arguments']['candidate_id'] == 'c0'
    assert [call['model'] for call in seen] == ['small']
    assert len(router.last_trace) == 1


def test_failed_utility_override_review_falls_back_to_valid_primary():
    seen = []
    primary = provider('small', response(candidate_id='c1'), seen)
    stronger = provider('large', ProviderError('network'), seen)
    router = RoutedSelectionProvider(primary, stronger, max_calls=2,
        review_utility_overrides=True)

    action = router.choose(_utility_override_request())

    assert action['arguments']['candidate_id'] == 'c1'
    assert [call['model'] for call in seen] == ['small', 'large']
    assert router.last_trace[1]['trigger'] == 'utility_override_review'
    assert router.last_trace[1]['review_fallback'] == dict(
        selected='primary_action', error_type='ProviderError')


def test_escalation_same_public_state_and_aggregate_cost():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response(), seen))
    p.choose({'public': 'only'})
    assert [x['model'] for x in seen] == ['small', 'large']
    assert seen[0]['input'] == seen[1]['input']
    assert p.last_usage['total_tokens'] == 28
    assert [x['status'] for x in p.last_trace] == ['invalid_action', 'complete']
    assert p.last_trace[1]['trigger'] == 'invalid_action'


def test_shared_budget_blocks_escalation():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response(), seen), max_calls=1)
    with pytest.raises(ProviderError, match='shared provider call'):
        p.choose({})
    assert len(seen) == 1


def test_request_budget_blocks_escalation_when_only_one_provider_call_remains():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response(), seen), max_calls=12)
    request = {'remaining': {
        'provider_calls_available_including_this_response': 1,
    }}
    with pytest.raises(ProviderBudgetError, match='shared provider call'):
        p.choose(request)
    assert p.calls == len(seen) == 1
    assert p.last_trace[0]['status'] == 'invalid_action'


def test_transport_failure_never_escalates():
    seen = []
    p = RoutedSelectionProvider(provider('small', ProviderError('network'), seen),
                                provider('large', response(), seen))
    with pytest.raises(ProviderError, match='network'):
        p.choose({})
    assert len(seen) == 1 and p.last_trace[0]['usage_complete'] is False


def test_invalid_secondary_stops_at_two_calls():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response('shell'), seen))
    with pytest.raises(InvalidActionError):
        p.choose({})
    assert p.calls == len(seen) == 2


def test_explicit_incumbent_correction_routes_once_to_secondary():
    seen = []
    primary = provider('small', response(), seen)
    secondary = provider('large', response(), seen)
    p = RoutedSelectionProvider(primary, secondary)
    correction = {'messages': [{'tool': 'finalize', 'result': {
        'status': 'error', 'required_candidate_id': 'c1',
        'allowed_candidate_ids': ['c1']}}]}

    assert p.choose(correction)['tool'] == 'measure'
    assert [call['model'] for call in seen] == ['large']
    assert p.last_trace[0]['trigger'] == 'host_incumbent_correction'
    assert p.last_trace[0]['role'] == 'escalation'

    # The stronger model is a one-shot recovery, not a second policy loop.
    p.choose(correction)
    assert [call['model'] for call in seen] == ['large', 'small']
    assert p.last_trace[0]['trigger'] == 'primary'


@pytest.mark.parametrize('message', [
    {'tool': 'measure', 'result': {'status': 'error', 'error': 'Candidate already attempted.'}},
    {'tool': 'finalize', 'result': {'status': 'error', 'error': 'Malformed arguments.'}},
    {'tool': 'finalize', 'result': {'status': 'failed', 'required_candidate_id': 'c1',
                                   'allowed_candidate_ids': ['c1']}},
])
def test_only_explicit_v2_incumbent_correction_triggers_recovery(message):
    seen = []
    p = RoutedSelectionProvider(provider('small', response(), seen),
                                provider('large', response(), seen))
    p.choose({'messages': [message]})
    assert [call['model'] for call in seen] == ['small']
    assert p.last_trace[0]['trigger'] == 'primary'


def test_missing_usage_is_not_zero_complete_usage():
    seen = []
    result = response(); result.pop('usage')
    p = RoutedSelectionProvider(provider('small', result, seen))
    p.choose({})
    assert p.last_usage == {} and p.last_trace[0]['usage_complete'] is False


def test_failed_preflight_does_not_reuse_stale_usage():
    seen = []
    primary = provider('small', response(), seen)
    p = RoutedSelectionProvider(primary)
    p.choose({})
    primary._api_key = None
    with pytest.raises(ProviderError):
        p.choose({})
    assert p.last_usage == {} and p.last_trace[0]['request_sha256'] is None
    assert not p.last_trace[0]['provider_call_charged']

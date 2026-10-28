"""Offline protocol tests, not live model quality experiments."""
import json
import pytest
from isaforge.selection_provider import ResponsesSelectionProvider, ProviderError, InvalidActionError
from isaforge.routed_selection import RoutedSelectionProvider


def response(name='measure'):
    return dict(status='completed', output=[dict(type='function_call', name=name,
        arguments=json.dumps({'candidate_id': 'c0'}))],
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


def test_escalation_same_public_state_and_aggregate_cost():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response(), seen))
    p.choose({'public': 'only'})
    assert [x['model'] for x in seen] == ['small', 'large']
    assert seen[0]['input'] == seen[1]['input']
    assert p.last_usage['total_tokens'] == 28
    assert [x['status'] for x in p.last_trace] == ['invalid_action', 'complete']


def test_shared_budget_blocks_escalation():
    seen = []
    p = RoutedSelectionProvider(provider('small', response('shell'), seen),
                                provider('large', response(), seen), max_calls=1)
    with pytest.raises(ProviderError, match='shared model call'):
        p.choose({})
    assert len(seen) == 1


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

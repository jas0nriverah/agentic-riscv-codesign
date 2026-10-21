"""Transport contract tests; these mocks are not live model experiments."""
import json
import pytest
from isaforge.selection_provider import ResponsesSelectionProvider, ProviderError


def answer(name='measure', arguments=None, **kwargs):
    return dict(status='completed', output=[dict(type='function_call', name=name,
                arguments=json.dumps(arguments or {'candidate_id': 'c0'}))],
                usage=dict(input_tokens=10, output_tokens=4, total_tokens=14), **kwargs)


def provider(transport, **kwargs):
    return ResponsesSelectionProvider('explicit-model', api_key='test-only', transport=transport, **kwargs)


def test_wire_allowlist_and_stateless_public_input():
    seen = []
    def transport(payload, key, timeout):
        seen.append(payload)
        assert key == 'test-only' and timeout == 3
        return answer()
    p = provider(transport, timeout_seconds=3, max_output_tokens=127)
    public = {'observations': [{'candidate_id': 'c0', 'prediction': 1.01}]}
    assert p.choose(public) == {'tool': 'measure', 'arguments': {'candidate_id': 'c0'}}
    wire = seen[0]
    assert set(wire) == {'model', 'instructions', 'input', 'tools', 'tool_choice',
                         'parallel_tool_calls', 'max_output_tokens', 'store'}
    assert json.loads(wire['input'][0]['content']) == public
    assert [tool['name'] for tool in wire['tools']] == ['list_candidates', 'predict', 'measure', 'finalize']
    assert all(tool['type'] == 'function' and tool['strict'] for tool in wire['tools'])
    assert wire['parallel_tool_calls'] is False and wire['tool_choice'] == 'required'
    assert wire['store'] is False and wire['max_output_tokens'] == 127
    assert p.last_usage == {'input_tokens': 10, 'output_tokens': 4, 'total_tokens': 14}
    assert len(p.last_request_sha256) == 64
    assert p.last_elapsed_seconds >= 0


@pytest.mark.parametrize('result', [
    answer('shell'), answer('measure', {'candidate_id': 'c0', 'path': '/secret'}),
    answer('predict', {'candidate_ids': 'c0'}),
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [dict(type='web_search_call')]},
    {'status': 'completed', 'output': []},
    {'status': 'completed', 'output': answer()['output'] * 2},
])
def test_bad_outputs_rejected_and_charged(result):
    p = provider(lambda *args: result, max_calls=1)
    with pytest.raises(ProviderError):
        p.choose({})
    assert p.calls == 1
    with pytest.raises(ProviderError, match='budget'):
        p.choose({})


def test_transport_failure_is_charged_without_retry():
    seen = []
    def fail(*args):
        seen.append(True)
        raise ProviderError('timeout')
    p = provider(fail)
    with pytest.raises(ProviderError, match='timeout'):
        p.choose({})
    assert p.calls == len(seen) == 1


def test_key_absence_never_calls_transport(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    p = ResponsesSelectionProvider('explicit-model', transport=lambda *args: pytest.fail('network'))
    with pytest.raises(ProviderError, match='no live model call'):
        p.choose({})
    assert p.calls == 0


@pytest.mark.parametrize('public_request', [{'value': float('nan')}, {'value': object()}, []])
def test_invalid_public_input_is_rejected_before_network(public_request):
    p = provider(lambda *args: pytest.fail('network'))
    with pytest.raises(ProviderError):
        p.choose(public_request)
    assert p.calls == 0


def test_public_size_is_bounded():
    p = provider(lambda *args: pytest.fail('network'), max_request_bytes=4)
    with pytest.raises(ProviderError, match='byte limit'):
        p.choose({'long': 'text'})


@pytest.mark.parametrize('name,args', [('list_candidates', {}), ('predict', {'candidate_ids': ['a']}),
    ('finalize', {'candidate_id': None, 'summary': 'baseline'})])
def test_other_valid_actions(name, args):
    response = answer()
    response['output'][0].update(name=name, arguments=json.dumps(args))
    assert provider(lambda *unused: response).choose({}) == dict(tool=name, arguments=args)


def test_server_overbudget_usage_rejected():
    response = answer()
    response['usage']['output_tokens'] = 1000
    with pytest.raises(ProviderError, match='output token budget'):
        provider(lambda *args: response, max_output_tokens=12).choose({})


def test_reasoning_is_opaque_and_never_replayed():
    seen = []
    def transport(payload, *args):
        seen.append(payload)
        response = answer()
        response['output'].insert(0, {'type': 'reasoning', 'id': 'opaque-id', 'summary': []})
        return response
    p = provider(transport)
    p.choose({'round': 1})
    p.choose({'round': 2})
    assert seen[1]['input'] == [{'role': 'user', 'content': '{"round": 2}'}]
    assert 'previous_response_id' not in seen[1]


def test_http_failure_redacts_remote_error(monkeypatch):
    import urllib.error
    from isaforge.selection_provider import _http_post
    def fail(*args, **kwargs):
        raise urllib.error.URLError('secret remote response')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(ProviderError) as exc:
        _http_post({}, 'secret-key', 1)
    assert 'secret' not in str(exc.value)


def test_http_output_byte_limit(monkeypatch):
    from isaforge.selection_provider import _http_post
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            assert size == 2_000_001
            return b'x' * size
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Response())
    with pytest.raises(ProviderError, match='byte limit'):
        _http_post({}, 'test', 1)

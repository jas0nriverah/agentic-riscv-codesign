import io
import json

import pytest

from isaforge.codex_chat_selector import CodexChatBridgeError, CodexChatSelectionProvider


def test_codex_bridge_sends_only_given_request_and_parses_one_tool_action():
    request = {'schema': 'test-public', 'candidates': [{'candidate_id': 'a'}]}
    action = {'tool': 'predict', 'arguments': {'candidate_ids': ['a']}}
    output = io.StringIO()
    provider = CodexChatSelectionProvider(
        input_stream=io.StringIO(json.dumps(action) + '\n'), output_stream=output)

    result = provider.choose(request)

    assert result == action
    assert json.dumps(request, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':')) in output.getvalue()
    assert 'private_outcome' not in output.getvalue()
    assert 'Copy the complete candidate_id exactly; never shorten it.' in output.getvalue()
    assert provider.calls == 1
    assert provider.last_usage == {}
    assert provider.identity['model_id_available'] is False


@pytest.mark.parametrize('action', [
    {'tool': 'shell', 'arguments': {'cmd': 'echo no'}},
    {'tool': 'measure', 'arguments': {'candidate_id': 'a', 'speedup': 3}},
    {'tool': 'finalize', 'arguments': {'candidate_id': None}},
    ['measure', 'a'],
])
def test_codex_bridge_rejects_actions_outside_the_four_tool_schema(action):
    provider = CodexChatSelectionProvider(
        input_stream=io.StringIO(json.dumps(action) + '\n'), output_stream=io.StringIO())

    with pytest.raises(CodexChatBridgeError):
        provider.choose({'schema': 'test'})
    assert provider.calls == 1  # Invalid model action is not retried.


def test_codex_bridge_stops_on_missing_input_without_fallback():
    provider = CodexChatSelectionProvider(input_stream=io.StringIO(), output_stream=io.StringIO())

    with pytest.raises(CodexChatBridgeError, match='no action received'):
        provider.choose({'schema': 'test'})


def test_codex_bridge_enforces_request_and_action_byte_limits():
    provider = CodexChatSelectionProvider(
        input_stream=io.StringIO('{"tool":"list_candidates","arguments":{}}\n'),
        output_stream=io.StringIO(), max_request_bytes=8, max_action_bytes=100)
    with pytest.raises(CodexChatBridgeError, match='request exceeds'):
        provider.choose({'payload': 'too big'})
    assert provider.calls == 0

    provider = CodexChatSelectionProvider(
        input_stream=io.StringIO('{"tool":"list_candidates","arguments":{}}\n'),
        output_stream=io.StringIO(), max_action_bytes=12)
    with pytest.raises(CodexChatBridgeError, match='action exceeds'):
        provider.choose({'schema': 'ok'})
    assert provider.calls == 1

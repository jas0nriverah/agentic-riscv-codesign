"""Stateless model boundary for the bounded selector; never executes model tools.

Only caller-supplied public JSON is sent. No repository, shell, MCP, retrieval,
conversation continuation, or built-in tools are attached to the Responses call.
The caller remains responsible for constructing a label-safe public request.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from typing import Callable

ENDPOINT = 'https://api.openai.com/v1/responses'
PROTOCOL = 'isaforge-four-tools-v3'
INSTRUCTIONS = (
    'Select RISC-V custom instructions using only the supplied public state. '
    'Request one permitted action. Predictions are uncalibrated estimates; only '
    'paid verified measurements establish feasibility. Respect measurement and '
    'action budgets, include failures in costs, and retain baseline when no '
    'verified feasible improvement is available. For every measure action, '
    'include a concise public-evidence decision_summary (at most 320 characters); '
    'do not provide private chain of thought. Finalize only the current '
    'host-computed incumbent.candidate_id; use null only when that incumbent is '
    'null. Your summary is an unverified note; the host return is authoritative. '
    'If routing_review is present, independently review the primary model\'s '
    'proposed measurement against the complete public state and the named '
    'utility recommendation; return the action you support and do not invent '
    'observations.'
)


def _function(name, description, properties, required):
    return dict(type='function', name=name, description=description, strict=True,
                parameters=dict(type='object', properties=properties,
                                required=required, additionalProperties=False))


def tool_definitions():
    """A fresh explicit allowlist; no provider-native tools are enabled."""
    return [
        _function('list_candidates', 'List public candidates and selection constraints.', {}, []),
        _function('predict', 'Query fixed predictors for candidate IDs.',
                  {'candidate_ids': {'type': 'array', 'items': {'type': 'string'}}},
                  ['candidate_ids']),
        _function('measure', 'Pay for one candidate measurement, including failures. Include a short public-evidence decision summary; never provide private chain of thought.',
                  {'candidate_id': {'type': 'string'},
                   'decision_summary': {'type': 'string', 'minLength': 1, 'maxLength': 320}},
                  ['candidate_id', 'decision_summary']),
        _function('finalize', 'Finalize only the current host-computed incumbent.candidate_id; use null only when no measured feasible improvement exists.',
                  {'candidate_id': {'type': ['string', 'null']}, 'summary': {'type': 'string'}},
                  ['candidate_id', 'summary']),
    ]


class ProviderError(RuntimeError):
    """Bound exceeded, unavailable service, or invalid model action."""


class ProviderBudgetError(ProviderError):
    """The shared allowance for actual provider invocations is exhausted."""


class InvalidActionError(ProviderError):
    """Completed response has no usable allowlisted structured action."""


def _http_post(payload, api_key, timeout):
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload, allow_nan=False).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Limit response bytes independently of the server token budget.
            data = response.read(2_000_001)
    except (urllib.error.URLError, TimeoutError) as exc:
        # Do not include response bodies, keys, or arbitrary remote error messages.
        raise ProviderError('Responses request failed: ' + type(exc).__name__) from None
    if len(data) > 2_000_000:
        raise ProviderError('Responses response exceeds byte limit')
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise ProviderError('Responses response is not JSON') from None


class ResponsesSelectionProvider:
    """One fresh Responses request per action, with no automatic retries.

    API credentials come only from an explicit key or OPENAI_API_KEY; saved
    Codex credentials and user configuration are never consulted. Model must be
    specified explicitly so experiments cannot silently change their model.
    transport is injectable for offline protocol tests, not an LLM substitute.
    """
    def __init__(self, model: str, *, api_key: str | None = None,
                 max_calls: int = 12, max_output_tokens: int = 512,
                 timeout_seconds: float = 45, max_request_bytes: int = 200_000,
                 transport: Callable | None = None):
        if not isinstance(model, str) or not model.strip():
            raise ValueError('an explicit model is required')
        for value in (max_calls, max_output_tokens, max_request_bytes):
            if type(value) is not int or value < 1:
                raise ValueError('integer bounds must be positive')
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be finite and positive')
        self.model = model
        self._api_key = api_key if api_key is not None else os.environ.get('OPENAI_API_KEY')
        self.max_calls = max_calls
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_request_bytes = max_request_bytes
        self._transport = transport or _http_post
        self.calls = 0
        self.last_usage = {}
        self.last_elapsed_seconds = 0.0
        self.last_request_sha256 = None
        self.identity = dict(provider='openai-responses', model=model, protocol=PROTOCOL,
                             max_calls=max_calls, max_output_tokens=max_output_tokens,
                             timeout_seconds=timeout_seconds,
                             tools=[tool['name'] for tool in tool_definitions()],
                             isolation='stateless-public-json-function-allowlist')

    def choose(self, request: dict) -> dict:
        if self.calls >= self.max_calls:
            raise ProviderBudgetError('provider call budget exhausted')
        if not self._api_key:
            raise ProviderError('OPENAI_API_KEY is required; no live model call was made')
        if type(request) is not dict:
            raise ProviderError('public request must be a JSON object')
        try:
            public = json.dumps(request, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            raise ProviderError('public request must contain finite JSON values') from None
        if len(public.encode()) > self.max_request_bytes:
            raise ProviderError('public request exceeds byte limit')
        payload = dict(model=self.model, instructions=INSTRUCTIONS,
                       input=[dict(role='user', content=public)], tools=tool_definitions(),
                       tool_choice='required', parallel_tool_calls=False,
                       max_output_tokens=self.max_output_tokens, store=False)
        self.last_request_sha256 = hashlib.sha256(public.encode()).hexdigest()
        self.calls += 1  # Failed requests are charged; no implicit retries.
        self.last_usage = {}
        started = time.monotonic()
        try:
            response = self._transport(payload, self._api_key, self.timeout_seconds)
        finally:
            self.last_elapsed_seconds = time.monotonic() - started
        if not isinstance(response, dict):
            raise ProviderError('invalid Responses envelope')
        usage = response.get('usage') or {}
        if not isinstance(usage, dict):
            raise ProviderError('invalid Responses usage')
        self.last_usage = {key: value for key, value in usage.items()
                           if key in ('input_tokens', 'output_tokens', 'total_tokens')
                           and type(value) is int and value >= 0}
        if self.last_usage.get('output_tokens', 0) > self.max_output_tokens:
            raise ProviderError('model exceeded output token budget')
        if response.get('status') != 'completed':
            raise ProviderError('model response did not complete')
        output = response.get('output', [])
        if not isinstance(output, list):
            raise ProviderError('invalid Responses output')
        if any(not isinstance(item, dict) or item.get('type') not in
               ('reasoning', 'function_call') for item in output):
            raise InvalidActionError('unexpected model output type')
        calls = [item for item in output if isinstance(item, dict)
                 and item.get('type') == 'function_call']
        if len(calls) != 1:
            raise InvalidActionError('expected exactly one function call')
        call = calls[0]
        name = call.get('name')
        try:
            arguments = json.loads(call.get('arguments', ''))
        except (ValueError, TypeError):
            raise InvalidActionError('invalid function arguments') from None
        if not _valid_action(name, arguments):
            raise InvalidActionError('model action violates four-tool schema')
        return dict(tool=name, arguments=arguments)


def _valid_action(name, args):
    if type(args) is not dict:
        return False
    if name == 'list_candidates':
        return args == {}
    if name == 'predict':
        return (set(args) == {'candidate_ids'} and type(args['candidate_ids']) is list
                and all(type(value) is str for value in args['candidate_ids']))
    if name == 'measure':
        return (set(args) == {'candidate_id', 'decision_summary'} and
                type(args['candidate_id']) is str and
                type(args['decision_summary']) is str and
                0 < len(args['decision_summary']) <= 320)
    if name == 'finalize':
        return (set(args) == {'candidate_id', 'summary'}
                and (args['candidate_id'] is None or type(args['candidate_id']) is str)
                and type(args['summary']) is str)
    return False

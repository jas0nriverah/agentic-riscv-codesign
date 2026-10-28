"""Bounded error-recovery routing; no tools or hardware execute here.

This is a software policy, not evidence of improved LLM selection. Both roles
receive identical public state. One escalation is allowed after malformed
structured output or an explicit host correction to the current incumbent.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

from isaforge.selection_provider import ProviderError, InvalidActionError, INSTRUCTIONS, tool_definitions


class RoutedSelectionProvider:
    def __init__(self, primary, escalation=None, *, max_calls=12):
        if type(max_calls) is not int or not 1 <= max_calls <= 100:
            raise ValueError('max_calls must be between 1 and 100')
        self.primary, self.escalation = primary, escalation
        self.max_calls, self.calls = max_calls, 0
        self.escalation_used = False
        self.last_usage, self.last_trace = {}, []
        self.identity = dict(provider='bounded-recovery-router-v2', max_calls=max_calls,
            primary=copy.deepcopy(primary.identity),
            escalation=copy.deepcopy(escalation.identity) if escalation else None,
            routing_rule=('one escalation on InvalidActionError or explicit host incumbent correction; '
                          'no transport retries'),
            prompt_sha256=hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
            tools_sha256=hashlib.sha256(json.dumps(tool_definitions(), sort_keys=True).encode()).hexdigest())

    @staticmethod
    def _needs_incumbent_recovery(request):
        """Recognize only the host's explicit v2 rejected-finalization result."""
        messages = request.get('messages') if isinstance(request, dict) else None
        if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict):
            return False
        message = messages[-1]
        result = message.get('result')
        return (message.get('tool') == 'finalize' and isinstance(result, dict) and
                result.get('status') == 'error' and
                'required_candidate_id' in result and
                isinstance(result.get('allowed_candidate_ids'), list))

    def choose(self, request):
        self.last_usage, self.last_trace = {}, []
        # Snapshot once: an adapter cannot mutate the state seen by the next role.
        public = copy.deepcopy(request)
        host_recovery = (self.escalation is not None and not self.escalation_used and
                         self._needs_incumbent_recovery(public))
        roles = ([('escalation', self.escalation, 'host_incumbent_correction')]
                 if host_recovery else [('primary', self.primary, 'primary')])
        if self.escalation is not None and not self.escalation_used and not host_recovery:
            roles.append(('escalation', self.escalation, 'invalid_action'))
        for role, provider, trigger in roles:
            if self.calls >= self.max_calls:
                raise ProviderError('shared model call budget exhausted')
            if role == 'escalation':
                self.escalation_used = True
            self.calls += 1  # Reserve even a failed provider invocation.
            event = dict(call=self.calls, role=role, identity=copy.deepcopy(provider.identity),
                         trigger=trigger, status='pending', usage={}, usage_complete=False)
            self.last_trace.append(event)
            before = provider.calls
            start = time.monotonic()
            try:
                action = provider.choose(copy.deepcopy(public))
                event['status'] = 'complete'
                return action
            except InvalidActionError:
                event['status'] = 'invalid_action'
                if role == 'escalation' or self.escalation is None or self.escalation_used:
                    raise
            except BaseException:
                event['status'] = 'provider_error_or_interruption'
                raise
            finally:
                dispatched = provider.calls > before
                usage = copy.deepcopy(provider.last_usage) if dispatched else {}
                event.update(elapsed_seconds=time.monotonic()-start,
                             provider_call_charged=dispatched, usage=usage,
                             request_sha256=provider.last_request_sha256 if dispatched else None,
                             usage_complete=all(k in usage for k in
                                                ('input_tokens', 'output_tokens', 'total_tokens')))
                for key, value in usage.items():
                    self.last_usage[key] = self.last_usage.get(key, 0) + value


def summarize_model_events(events):
    """Observed usage is a lower bound whenever a charged call lacks metadata."""
    trace = [call for event in events for call in event.get('provider_trace', [])]
    charged = [call for call in trace if call['provider_call_charged']]
    escalation_triggers = {}
    for call in charged:
        if call['role'] == 'escalation':
            trigger = call.get('trigger', 'unspecified')
            escalation_triggers[trigger] = escalation_triggers.get(trigger, 0) + 1
    return dict(reserved_calls=len(trace), dispatched_calls=len(charged),
        escalation_calls=sum(call['role'] == 'escalation' for call in charged),
        escalation_triggers=escalation_triggers,
        usage_complete=all(call['usage_complete'] for call in charged),
        calls_missing_usage=sum(not call['usage_complete'] for call in charged),
        observed_tokens={key: sum(call['usage'].get(key, 0) for call in charged)
                         for key in ('input_tokens', 'output_tokens', 'total_tokens')},
        provider_elapsed_seconds=sum(call['elapsed_seconds'] for call in trace),
        cost_usd=None)

"""Bounded model routing; no tools or hardware execute here.

This is a software policy, not evidence of improved LLM selection. Recovery
escalations receive the same public snapshot. The opt-in utility-override review
adds the primary's structured action and public evidence note to that snapshot.
One escalation is allowed per episode across all triggers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

from isaforge.selection_provider import (
    ProviderError, ProviderBudgetError, InvalidActionError, INSTRUCTIONS, tool_definitions,
)


class RoutedSelectionProvider:
    def __init__(self, primary, escalation=None, *, max_calls=12,
                 review_utility_overrides=False):
        if type(max_calls) is not int or not 1 <= max_calls <= 100:
            raise ValueError('max_calls must be between 1 and 100')
        if type(review_utility_overrides) is not bool:
            raise ValueError('review_utility_overrides must be a boolean')
        self.primary, self.escalation = primary, escalation
        self.max_calls, self.calls = max_calls, 0
        self.review_utility_overrides = review_utility_overrides
        self.escalation_used = False
        self.last_usage, self.last_trace = {}, []
        self.identity = dict(provider='bounded-recovery-router-v3', max_calls=max_calls,
            primary=copy.deepcopy(primary.identity),
            escalation=copy.deepcopy(escalation.identity) if escalation else None,
            review_utility_overrides=review_utility_overrides,
            routing_rule=('one escalation on malformed action or explicit host incumbent correction; '
                          'optionally review a primary measurement that overrides the ML utility recommendation; '
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

    @staticmethod
    def _utility_override(request, action):
        """Return a review record only for a valid public-board disagreement."""
        if not isinstance(request, dict) or not isinstance(action, dict):
            return None
        if action.get('tool') != 'measure' or not isinstance(action.get('arguments'), dict):
            return None
        chosen = action['arguments'].get('candidate_id')
        board = request.get('selection_board')
        if not isinstance(chosen, str) or not isinstance(board, dict):
            return None
        recommended = board.get('utility_recommendation_candidate_id')
        if not isinstance(recommended, str) or chosen == recommended:
            return None
        rows = board.get('rows')
        if not isinstance(rows, list):
            return None
        selected_row = next((row for row in rows
                             if isinstance(row, dict) and
                             row.get('candidate_id') == chosen and
                             row.get('attempted') is False), None)
        recommendation = board.get('utility_recommendation')
        if selected_row is None or not isinstance(recommendation, dict):
            return None
        ratio = selected_row.get('decision_score_ratio_to_recommendation')
        if (type(ratio) not in (int, float) or isinstance(ratio, bool) or
                not 0 <= ratio <= 1):
            return None
        return dict(schema='isaforge-utility-override-review-v1',
            trigger='primary_measurement_overrides_utility_recommendation',
            primary_action=copy.deepcopy(action),
            utility_recommendation_candidate_id=recommended,
            proposed_candidate_score_ratio=ratio,
            score_semantics='Uncalibrated ordering proxy; review signal only, not expected utility.')

    def _dispatch(self, role, provider, trigger, request, *, action_start,
                  action_budget):
        if (self.calls >= self.max_calls or
                self.calls-action_start >= action_budget):
            raise ProviderBudgetError('shared provider call budget exhausted')
        if role == 'escalation':
            self.escalation_used = True
        self.calls += 1  # Reserve even a failed provider invocation.
        event = dict(call=self.calls, role=role, identity=copy.deepcopy(provider.identity),
                     trigger=trigger, status='pending', usage={})
        self.last_trace.append(event)
        before = provider.calls
        start = time.monotonic()
        try:
            action = provider.choose(copy.deepcopy(request))
            event['status'] = 'complete'
            return action
        except InvalidActionError:
            event['status'] = 'invalid_action'
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

    def _review_override(self, request, primary_action, *, action_start,
                         action_budget):
        review = self._utility_override(request, primary_action)
        if (review is None or not self.review_utility_overrides or
                self.escalation is None or self.escalation_used):
            return primary_action
        self.last_trace[-1]['primary_action'] = copy.deepcopy(primary_action)
        self.last_trace[-1]['utility_override_review'] = copy.deepcopy(review)
        if self.calls >= self.max_calls or self.calls-action_start >= action_budget:
            self.last_trace[-1]['utility_override_review_skipped'] = 'provider_budget'
            return primary_action
        review_request = copy.deepcopy(request)
        review_request['routing_review'] = review
        try:
            reviewed_action = self._dispatch('escalation', self.escalation,
                'utility_override_review', review_request,
                action_start=action_start, action_budget=action_budget)
            self.last_trace[-1]['reviewed_primary_action'] = copy.deepcopy(primary_action)
            self.last_trace[-1]['reviewed_utility_recommendation_candidate_id'] = (
                review['utility_recommendation_candidate_id'])
            return reviewed_action
        except (InvalidActionError, ProviderError) as error:
            # The primary action is already schema-valid. A failed review must
            # not discard it or cause the host to lose a usable decision.
            if self.last_trace:
                self.last_trace[-1]['review_fallback'] = dict(
                    selected='primary_action', error_type=type(error).__name__)
            return primary_action

    def choose(self, request):
        self.last_usage, self.last_trace = {}, []
        # Snapshot once: an adapter cannot mutate the state seen by the next role.
        public = copy.deepcopy(request)
        remaining = public.get('remaining', {}) if isinstance(public, dict) else {}
        action_budget = remaining.get('provider_calls_available_including_this_response')
        if type(action_budget) is not int or action_budget < 0:
            action_budget = self.max_calls-self.calls
        action_start = self.calls
        host_recovery = (self.escalation is not None and not self.escalation_used and
                         self._needs_incumbent_recovery(public))
        if host_recovery:
            return self._dispatch('escalation', self.escalation,
                'host_incumbent_correction', public,
                action_start=action_start, action_budget=action_budget)
        try:
            primary_action = self._dispatch('primary', self.primary, 'primary', public,
                action_start=action_start, action_budget=action_budget)
        except InvalidActionError:
            if self.escalation is None or self.escalation_used:
                raise
            return self._dispatch('escalation', self.escalation, 'invalid_action', public,
                action_start=action_start, action_budget=action_budget)
        return self._review_override(public, primary_action,
            action_start=action_start, action_budget=action_budget)


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

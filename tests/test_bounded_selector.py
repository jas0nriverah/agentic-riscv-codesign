"""Budget, information-boundary and failure tests; no live LLM/hardware jobs."""
import copy
import json
from pathlib import Path

import pytest

from isaforge import budgeted_selection as b
from isaforge import codesign as c
from isaforge.bounded_selector import MatchedBaselinePolicy, ReplaySelectionSession, run_selector
from isaforge.bounded_selector import GROUPED_PREDICTION_SCHEMA, GROUPED_PREDICTION_FIELDS
from test_budgeted_selection import history, measured, predictions, public


@pytest.fixture
def inputs():
    training = history()
    target = [public('t1', saved_cycles=60),
              public('t2', 'sub(in0,slli(in1,1))', saved_cycles=20),
              public('t3', 'add(in0,srli(in1,1))', saved_cycles=30)]
    outcomes = {row['candidate_id']: measured(row, area=40, savings=(60, 20, 30)[i])
                for i, row in enumerate(target)}
    return target, training, predictions(training, target, 0), outcomes


def session(tmp_path, inputs, provider=None, **kwargs):
    target, training, values, outcomes = inputs
    return ReplaySelectionSession(target, training, values,
        provider or (lambda row: outcomes[row['candidate_id']]),
        area_cap=64, ledger_path=tmp_path/'ledger.json', **kwargs)


def action(tool, **arguments):
    if tool == 'measure' and 'decision_summary' not in arguments:
        arguments['decision_summary'] = 'Synthetic policy choice for protocol test.'
    return dict(tool=tool, arguments=arguments)


def grouped_prediction_bundle(target):
    rows = []
    for index, candidate in enumerate(target):
        rows.append(dict(candidate_id=candidate['candidate_id'],
            pairwise_rank_score=float(len(target)-index),
            pairwise_rank_position=index+1,
            factorized_feasibility_probability=.75-index*.1,
            factorized_feasibility_disagreement=.12,
            factorized_decision_score=.01*(len(target)-index)))
    return dict(schema=GROUPED_PREDICTION_SCHEMA, seed=0, rows=rows)


def grouped_metadata():
    return dict(schema=GROUPED_PREDICTION_SCHEMA,
        models=dict(pairwise_ranker='XGBRanker rank:pairwise',
                    feasibility='factorized XGBoost'),
        training_scope='whole-workload and formula-family held out',
        scores_frozen_before_target_measurements=True,
        score_limits=dict(pairwise_rank_score='ordering only',
                          feasibility='uncalibrated score',
                          disagreement='uncalibrated ensemble spread'))


def grouped_session(tmp_path, inputs, *, bundle=None, metadata=None):
    target, training, _, outcomes = inputs
    bundle = bundle or grouped_prediction_bundle(target)
    metadata = metadata or grouped_metadata()
    return ReplaySelectionSession(target, training, None,
        lambda row: outcomes[row['candidate_id']], area_cap=64,
        ledger_path=tmp_path/'grouped-ledger.json',
        grouped_predictions=bundle, grouped_model_metadata=metadata)


def test_unpaid_labels_and_private_paths_absent_and_mutation_isolated(tmp_path, inputs):
    inputs[3]['t1']['private_path'] = '/private/UNPAID-OUTCOME-CANARY'
    s = session(tmp_path, inputs)
    request = s.request()
    assert 'UNPAID-OUTCOME-CANARY' not in json.dumps(request)
    assert 'ledger.json' not in json.dumps(request)
    request['candidates'][0]['runs'] = 99999
    request['constraints']['area_delta_lut4_cap'] = 99999
    assert s.request()['candidates'][0]['runs'] != 99999
    assert s.area_cap == 64
    observed = s.call(action('measure', candidate_id='t1'))
    assert 'UNPAID-OUTCOME-CANARY' not in json.dumps(s.request())
    assert 'private_path' not in observed['observation']
    observed['observation']['speedup'] = 900
    assert s.observations[0]['speedup'] != 900


@pytest.mark.parametrize('where', ['outer', 'nested'])
def test_public_labels_rejected(tmp_path, inputs, where):
    target = inputs[0]
    (target[0] if where == 'outer' else target[0]['latency_features'])['speedup'] = 10
    with pytest.raises(ValueError): session(tmp_path, inputs)


def test_related_families_and_same_workload_rejected(tmp_path, inputs):
    inputs[1][0]['workload_group'] = 'target'
    with pytest.raises(ValueError): session(tmp_path, inputs)


def test_prediction_boundary_and_only_paid_hardware_update(tmp_path, inputs, monkeypatch):
    s = session(tmp_path, inputs)
    seen = []
    original = b.HardwareSurrogate.fit
    def fit(model, rows):
        seen.append([r['candidate_id'] for r in rows])
        return original(model, rows)
    monkeypatch.setattr(b.HardwareSurrogate, 'fit', fit)
    first = s.call(action('predict', candidate_ids=['t1']))
    assert seen == []
    assert first['predictions'][0]['paid_target_ids'] == []
    s.call(action('measure', candidate_id='t1'))
    second = s.call(action('predict', candidate_ids=['t2']))
    assert seen == [['h1', 'h2', 'h3', 't1']]
    assert second['predictions'][0]['paid_target_ids'] == ['t1']
    assert not second['predictions'][0]['uncertainty_calibrated']
    s.call(action('predict', candidate_ids=['t3']))
    assert len(seen) == 1


def test_current_grouped_model_bundle_is_public_only_and_keeps_host_authority(tmp_path, inputs):
    s = grouped_session(tmp_path, inputs)
    request = s.request()
    encoded = json.dumps(request)
    assert request['current_grouped_ml_bundle']['scores_frozen_before_target_measurements']
    assert 'selection_board' not in request
    assert 'uncalibrated ensemble spread' in encoded
    assert not any('current_grouped_ml' in json.dumps(message) for message in request['messages'])
    scored = s.call(action('predict', candidate_ids=['t1', 't2']))
    assert scored['status'] == 'ok'
    prediction = scored['predictions'][0]['current_grouped_ml']
    assert set(prediction) == set(GROUPED_PREDICTION_FIELDS)
    assert prediction['pairwise_rank_position'] == 1
    assert scored['predictions'][0]['uncertainty_calibrated'] is False
    assert 'selection_board' not in s.request()
    s.call(action('predict', candidate_ids=['t3']))
    board = s.request()['selection_board']
    assert board['advisory_default_candidate_id'] == 't1'
    assert board['rows'][0]['pairwise_rank_position'] == 1
    measured_result = s.call(action('measure', candidate_id='t1'))
    assert measured_result['status'] == 'ok'
    assert s.observations[0]['candidate_id'] == 't1'
    assert s.request()['selection_board']['rows'][0]['paid_verification']['status'] == \
        'verified_feasible_improvement'
    s.host_finalize('test_end')
    ledger = c.unseal(tmp_path/'grouped-ledger.json')
    assert ledger['prediction_mode'] == 'current_grouped'
    assert ledger['grouped_model_metadata'] == grouped_metadata()
    assert ledger['grouped_predictions_sha256']


@pytest.mark.parametrize('mutation', ['label', 'missing_candidate', 'bad_probability'])
def test_current_grouped_prediction_bundle_rejects_bad_or_labeled_rows(tmp_path, inputs, mutation):
    target, *_ = inputs
    bundle = grouped_prediction_bundle(target)
    if mutation == 'label':
        bundle['rows'][0]['label'] = 1
    elif mutation == 'missing_candidate':
        bundle['rows'].pop()
    else:
        bundle['rows'][0]['factorized_feasibility_probability'] = 1.1
    with pytest.raises(ValueError):
        grouped_session(tmp_path, inputs, bundle=bundle)


def test_current_grouped_metadata_rejects_target_labels(tmp_path, inputs):
    metadata = grouped_metadata()
    metadata['debug'] = {'nested': {'label': 1}}
    with pytest.raises(ValueError):
        grouped_session(tmp_path, inputs, metadata=metadata)


def test_invalid_repeat_and_failure_charge_without_free_retry(tmp_path, inputs):
    calls = []
    def provider(row):
        calls.append(row['candidate_id'])
        return dict(**row, status='failed', measurement_seconds=7,
                    error='/private/RAW-ERROR-CANARY')
    s = session(tmp_path, inputs, provider)
    assert s.call(action('measure', candidate_id='unknown'))['status'] == 'error'
    failed = s.call(action('measure', candidate_id='t1'))
    assert failed['status'] == 'failed'
    assert 'RAW-ERROR-CANARY' not in json.dumps(s.request())
    assert s.call(action('measure', candidate_id='t1'))['status'] == 'error'
    assert s.charged == 3 and calls == ['t1'] and s.observations == []
    assert s.call(action('measure', candidate_id='t2'))['status'] == 'error'
    assert calls == ['t1'] and s.charged == 3
    s.stop('test_end')
    value = c.unseal(tmp_path/'ledger.json')
    assert value['best_speedup'] == 1.0
    assert value['replayed_target_measurement_seconds'] == 7
    assert [p['budget'] for p in value['curve']] == [1, 2, 3]


def test_malformed_measure_charged_and_unknown_tool_bounded(tmp_path, inputs):
    s = session(tmp_path, inputs, max_tool_calls=2)
    assert s.call({'tool': 'measure', 'arguments': [], 'extra': 'x'})['status'] == 'error'
    assert s.charged == 1
    s.call(action('shell', command='read /private/oracle'))
    s.call(action('measure', candidate_id='t1'))
    assert s.finished and s.ledger['status'] == 'tool_limit'
    assert s.charged == 1


def test_charge_persisted_before_provider_and_exception_stops(tmp_path, inputs):
    def provider(row):
        pending = c.unseal(tmp_path/'ledger.json')
        assert pending['charged_attempts'] == 1
        assert pending['events'][-1]['status'] == 'pending'
        raise RuntimeError('/private/EXCEPTION-CANARY')
    s = session(tmp_path, inputs, provider)
    result = s.call(action('measure', candidate_id='t1'))
    assert 'EXCEPTION-CANARY' not in json.dumps(result)
    assert s.finished and s.ledger['status'] == 'provider_error'
    saved = c.unseal(tmp_path/'ledger.json')
    assert saved['charged_attempts'] == 1
    assert saved['events'][-1]['replayed_measurement_seconds_unknown'] is True
    assert s.call(action('measure', candidate_id='t2'))['status'] == 'error'


def test_interrupt_recorded_and_reraised(tmp_path, inputs):
    def provider(row): raise KeyboardInterrupt()
    s = session(tmp_path, inputs, provider)
    with pytest.raises(KeyboardInterrupt): s.call(action('measure', candidate_id='t1'))
    assert c.unseal(tmp_path/'ledger.json')['status'] == 'interrupted'


def test_finalize_rejects_unpaid_infeasible_and_slowdown(tmp_path, inputs):
    inputs[3]['t1']['area_delta_lut4'] = 65
    inputs[3]['t2'].update(candidate_cycles=1100, speedup=1000/1100)
    s = session(tmp_path, inputs)
    assert s.call(action('finalize', candidate_id='t3', summary='unpaid'))['status'] == 'error'
    s.call(action('measure', candidate_id='t1'))
    assert s.call(action('finalize', candidate_id='t1', summary='over cap'))['status'] == 'error'
    s.call(action('measure', candidate_id='t2'))
    assert s.call(action('finalize', candidate_id='t2', summary='slowdown'))['status'] == 'error'
    assert s.call(action('finalize', candidate_id=None, summary='Keep baseline.'))['status'] == 'ok'
    assert s.ledger['best_speedup'] == 1


def test_finalize_requires_current_best_feasible_incumbent(tmp_path, inputs):
    s = session(tmp_path, inputs)
    state = s.request()
    assert state['finalization']['required_candidate_id'] is None
    assert state['finalization']['allowed_candidate_ids'] == []
    assert s.call(action('measure', candidate_id='t1'))['status'] == 'ok'
    best = s._best()
    assert best is not None
    alternate = next(row['candidate_id'] for row in s.public
                     if row['candidate_id'] != best['candidate_id'])
    state = s.request()
    assert state['finalization']['required_candidate_id'] == best['candidate_id']
    assert state['finalization']['allowed_candidate_ids'] == [best['candidate_id']]

    wrong = s.call(action('finalize', candidate_id=alternate, summary='Stale candidate.'))
    assert wrong == {
        'status': 'error',
        'error': 'Finalize with the current best paid verified feasible improvement; use null only when no such improvement has been measured.',
        'required_candidate_id': best['candidate_id'],
        'allowed_candidate_ids': [best['candidate_id']]}
    assert s.call(action('finalize', candidate_id=None, summary='Drop incumbent.'))['status'] == 'error'
    result = s.call(action('finalize', candidate_id=best['candidate_id'], summary='Keep best.'))
    assert result['status'] == 'ok'
    assert result['selection']['candidate_id'] == best['candidate_id']
    assert result['selection']['correctness_verified'] is True
    assert result['selection']['speedup'] == best['speedup']
    assert s.ledger['selected_id'] == best['candidate_id']
    assert s.ledger['agent_summary'] == 'Keep best.'
    assert s.ledger['decision_rationale']['selection_decisions'][0]['decision_summary'] == \
        'Synthetic policy choice for protocol test.'


def test_model_limit_falls_back_to_best_paid_feasible(tmp_path, inputs):
    class Policy:
        def choose(self, request): return action('measure', candidate_id='t1')
    result = run_selector(session(tmp_path, inputs), Policy(), max_model_calls=1)
    assert result['status'] == 'host_fallback'
    assert result['charged_attempts'] == 1
    assert result['selected_id'] == 't1'
    assert result['finalization_source'] == 'host'
    assert result['fallback_reason'] == 'model_call_limit'
    assert result['authoritative_selection']['candidate_id'] == 't1'
    assert result['host_events'] == [dict(type='fallback_finalize',
        reason='model_call_limit', error_type=None, candidate_id='t1',
        model_calls=1, provider_calls=0, tool_calls=1, charged_attempts=1)]


def test_model_exception_and_private_errors_not_released(tmp_path, inputs):
    class Policy:
        def choose(self, request): raise RuntimeError('/private/MODEL-CANARY')
    s = session(tmp_path, inputs)
    result = run_selector(s, Policy())
    assert result['status'] == 'host_fallback' and result['charged_attempts'] == 0
    assert result['selected_id'] is None
    assert result['authoritative_selection'] == dict(candidate_id=None, status='baseline', speedup=1.0)
    assert result['host_events'][0]['reason'] == 'model_error'
    assert result['host_events'][0]['error_type'] == 'RuntimeError'
    assert 'MODEL-CANARY' not in json.dumps(result)


def test_tool_limit_host_fallback_preserves_incumbent_without_extra_tool(tmp_path, inputs):
    class Policy:
        def choose(self, request):
            if request['remaining']['measurement_attempts']:
                return action('measure', candidate_id='t1')
            return action('list_candidates')
    s = session(tmp_path, inputs, max_tool_calls=2)
    result = run_selector(s, Policy(), max_model_calls=5)
    assert result['status'] == 'host_fallback'
    assert result['fallback_reason'] == 'tool_limit'
    assert result['charged_attempts'] == result['tool_calls'] == 2
    assert result['selected_id'] == 't1'
    assert result['host_events'][0]['candidate_id'] == 't1'


def test_model_interrupt_is_persisted_and_reraised(tmp_path, inputs):
    class Policy:
        def choose(self, request): raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt): run_selector(session(tmp_path, inputs), Policy())
    assert c.unseal(tmp_path/'ledger.json')['status'] == 'interrupted'


@pytest.mark.parametrize('policy', b.POLICIES)
def test_same_tool_boundary_reproduces_existing_baseline(tmp_path, inputs, policy):
    target, training, values, outcomes = inputs
    old = b.search(target, training, lambda row: outcomes[row['candidate_id']],
        area_cap=64, clock_mhz=12, policy=policy, seed=0, budget=3, predictions=values)
    new = run_selector(session(tmp_path, inputs), MatchedBaselinePolicy(policy))
    assert new['status'] == 'finalized'
    assert [p['attempted_ids'] for p in new['curve']] == [p['attempted_ids'] for p in old['curve']]
    assert [p['best_speedup'] for p in new['curve']] == [p['best_speedup'] for p in old['curve']]
    assert new['selected_id'] == old['curve'][-1]['selected_id']


def test_existing_ledger_not_overwritten(tmp_path, inputs):
    session(tmp_path, inputs)
    with pytest.raises(ValueError): session(tmp_path, inputs)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1])
def test_invalid_prediction_spread_rejected(tmp_path, inputs, value):
    inputs[2]['hardware'][0]['area_delta_lut4_std'] = value
    with pytest.raises(ValueError): session(tmp_path, inputs)


def test_routed_errors_spend_model_calls_not_hardware_attempts(tmp_path, inputs):
    from isaforge.selection_provider import ResponsesSelectionProvider
    from isaforge.routed_selection import RoutedSelectionProvider, summarize_model_events
    def transport(payload, *args):
        name = 'shell' if payload['model'] == 'small' else 'measure'
        return dict(status='completed', output=[dict(type='function_call', name=name,
            arguments=json.dumps({'candidate_id': 't1',
                                  'decision_summary': 'Choose the fixture candidate.'}))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))
    small = ResponsesSelectionProvider('small', api_key='test', transport=transport)
    large = ResponsesSelectionProvider('large', api_key='test', transport=transport)
    policy = RoutedSelectionProvider(small, large, max_calls=2)
    result = run_selector(session(tmp_path, inputs), policy)
    assert policy.calls == 2
    assert result['charged_attempts'] == 1
    assert result['selected_id'] == 't1'
    assert result['model_calls'] == 1 and result['provider_calls'] == 2
    assert result['status'] == 'host_fallback'  # Shared LLM budget exhausted; host commits incumbent.
    assert result['finalization_source'] == 'host'
    assert result['fallback_reason'] == 'provider_call_limit'
    assert result['authoritative_selection']['candidate_id'] == 't1'
    accounting = summarize_model_events(result['model_events'])
    assert accounting['dispatched_calls'] == 2
    assert accounting['observed_tokens']['total_tokens'] == 28
    assert accounting['escalation_calls'] == 1 and accounting['usage_complete']
    saved = c.unseal(tmp_path/'ledger.json')
    assert saved['model_events'][0]['provider_trace'][1]['identity']['model'] == 'large'


@pytest.mark.parametrize('provider_allowance', [4, 5])
@pytest.mark.parametrize('review_result', ['accept', 'provider_error', 'invalid_action'])
def test_utility_override_review_completes_before_charging_measurement(
        tmp_path, inputs, provider_allowance, review_result):
    from isaforge.selection_provider import ResponsesSelectionProvider, ProviderError
    from isaforge.routed_selection import RoutedSelectionProvider
    from isaforge.agent_memory import MemoryAugmentedPolicy
    seen = []
    charged_during_calls = []
    session_holder = {}

    def transport(payload, *args):
        request = json.loads(payload['input'][0]['content'])
        charged_during_calls.append(session_holder['session'].charged)
        seen.append((payload['model'], request))
        if 'routing_review' in request:
            if review_result == 'provider_error':
                raise ProviderError('offline review failure')
            name, arguments = 'measure', dict(candidate_id='t1',
                decision_summary='Review supports the displayed utility recommendation.')
            if review_result == 'invalid_action':
                name = 'shell'
        elif payload['model'] == 'small' and not request['messages']:
            name, arguments = 'list_candidates', {}
        elif payload['model'] == 'small' and request['messages'][-1]['tool'] == 'list_candidates':
            name, arguments = 'predict', dict(candidate_ids=['t1', 't2', 't3'])
        elif payload['model'] == 'small' and request['messages'][-1]['tool'] == 'predict':
            assert request['selection_board']['utility_recommendation_candidate_id'] == 't1'
            name, arguments = 'measure', dict(candidate_id='t3',
                decision_summary='Primary prefers t3 based on a competing public feature.')
        else:
            name, arguments = 'finalize', dict(candidate_id=request['incumbent']['candidate_id'],
                summary='Finalize the host-computed measured incumbent.')
        return dict(status='completed', output=[dict(type='function_call', name=name,
            arguments=json.dumps(arguments))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))

    router = RoutedSelectionProvider(
        ResponsesSelectionProvider('small', api_key='test', transport=transport),
        ResponsesSelectionProvider('large', api_key='test', transport=transport),
        max_calls=provider_allowance, review_utility_overrides=True)
    policy = MemoryAugmentedPolicy(router, mode='hybrid')
    test_session = grouped_session(tmp_path, inputs)
    session_holder['session'] = test_session

    result = run_selector(test_session, policy, max_model_calls=5)

    assert result['status'] == ('finalized' if provider_allowance == 5 else 'host_fallback')
    if provider_allowance == 4:
        assert result['fallback_reason'] == 'provider_call_limit'
        assert result['decision_rationale']['summary'] is None
    assert result['selected_id'] == ('t1' if review_result == 'accept' else 't3')
    assert result['charged_attempts'] == 1
    assert [model for model, _ in seen] == (
        ['small', 'small', 'small', 'large'] + ['small'] * (provider_allowance-4))
    assert charged_during_calls == [0, 0, 0, 0] + [1] * (provider_allowance-4)
    review = seen[3][1]['routing_review']
    assert review['primary_action']['arguments']['candidate_id'] == 't3'
    event = next(event for event in test_session.ledger['model_events']
                 if any(call['trigger'] == 'utility_override_review'
                        for call in event['provider_trace']))
    assert [call['trigger'] for call in event['provider_trace']] == [
        'primary', 'utility_override_review']
    assert event['provider_trace'][0]['primary_action']['arguments']['candidate_id'] == 't3'
    assert 'routing_review' not in event['public_context']
    accepted_call = 4 if review_result == 'accept' else 3
    accepted_role = 'escalation' if review_result == 'accept' else 'primary'
    accepted_trigger = 'utility_override_review' if review_result == 'accept' else 'primary'
    assert event['action_context'] == seen[accepted_call-1][1]
    assert event['action_context_sha256'] == c.digest(event['action_context'])
    assert event['provider_action_context_sha256'] == event['action_context_sha256']
    assert event['action_context_role'] == accepted_role
    assert event['action_context_provider_call'] == accepted_call
    assert seen[2][1]['remaining']['provider_calls_available_including_this_response'] == provider_allowance-2
    assert seen[3][1]['remaining']['provider_calls_available_including_this_response'] == provider_allowance-3
    assert event['memory_trace']['serialized_request_bytes'] == len(json.dumps(
        event['public_context'], sort_keys=True, allow_nan=False).encode('utf-8'))
    decision = result['decision_rationale']['selection_decisions'][0]
    assert decision['action_context'] == event['action_context']
    assert decision['action_context_sha256'] == event['action_context_sha256']
    export_root = tmp_path/'review-export-run'
    export_root.mkdir()
    c.seal(export_root/'protocol.json', dict(provider='offline-fixture'))
    c.seal(export_root/'ledger.json', result)
    c.seal(export_root/'report.json', dict(
        protocol_sha256=c.sha(export_root/'protocol.json'),
        runs=[dict(target='fixture', policy='routed', status=result['status'],
            speedup=result['best_speedup'], charged_attempts=result['charged_attempts'],
            ledger='ledger.json', ledger_sha256=c.sha(export_root/'ledger.json'))]))
    c.seal(export_root/'manifest.json', {name:c.sha(export_root/name) for name in
        ('protocol.json', 'report.json', 'ledger.json')})
    from scripts.export_agent_observability import export
    import sqlite3
    exported = tmp_path/'review-export.sqlite'
    counts = export(export_root, exported)
    assert counts['action_contexts'] == result['model_calls']
    with sqlite3.connect(exported) as db:
        row = db.execute('SELECT context_sha256, provider_request_sha256, action_role, '
            'provider_call, trigger, context_json FROM action_contexts '
            'WHERE episode=0 AND decision=?', (event['call'],)).fetchone()
    assert row[:5] == (event['action_context_sha256'],
        event['provider_action_context_sha256'], accepted_role, accepted_call, accepted_trigger)
    assert json.loads(row[5]) == event['action_context']
    from isaforge.routed_selection import summarize_model_events
    accounting = summarize_model_events(test_session.ledger['model_events'])
    assert accounting['escalation_triggers'] == {'utility_override_review': 1}
    assert accounting['dispatched_calls'] == provider_allowance
    assert accounting['utility_override_requests'] == 1
    assert accounting['utility_override_reviews_completed'] == int(review_result == 'accept')
    assert accounting['utility_override_actions_changed'] == int(review_result == 'accept')
    assert accounting['utility_override_candidates_changed'] == int(review_result == 'accept')
    assert accounting['utility_override_review_fallbacks'] == int(review_result != 'accept')


def test_reviewer_finalization_rationale_uses_the_review_context(tmp_path, inputs):
    from isaforge.selection_provider import ResponsesSelectionProvider
    from isaforge.routed_selection import RoutedSelectionProvider
    seen = []

    def transport(payload, *args):
        request = json.loads(payload['input'][0]['content'])
        seen.append((payload['model'], request))
        if 'routing_review' in request:
            name, arguments = 'finalize', dict(candidate_id=None,
                summary='Keep baseline after review of the proposed override.')
        elif not request['messages']:
            name, arguments = 'list_candidates', {}
        elif request['messages'][-1]['tool'] == 'list_candidates':
            name, arguments = 'predict', dict(candidate_ids=['t1', 't2', 't3'])
        else:
            name, arguments = 'measure', dict(candidate_id='t3',
                decision_summary='Primary proposes t3 despite the utility recommendation.')
        return dict(status='completed', output=[dict(type='function_call', name=name,
            arguments=json.dumps(arguments))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))

    policy = RoutedSelectionProvider(
        ResponsesSelectionProvider('small', api_key='test', transport=transport),
        ResponsesSelectionProvider('large', api_key='test', transport=transport),
        max_calls=5, review_utility_overrides=True)
    result = run_selector(grouped_session(tmp_path, inputs), policy, max_model_calls=5)

    assert result['status'] == 'finalized'
    assert result['charged_attempts'] == 0
    assert [model for model, _ in seen] == ['small', 'small', 'small', 'large']
    rationale = result['decision_rationale']
    assert rationale['summary']['text'] == (
        'Keep baseline after review of the proposed override.')
    assert rationale['action_context']['routing_review']['primary_action']['arguments'][
        'candidate_id'] == 't3'
    assert rationale['action_context_role'] == 'escalation'
    assert rationale['action_context_sha256'] == c.digest(rationale['action_context'])
    assert rationale['action_context_sha256'] == \
        rationale['model_call_references'][-1]['provider_calls'][-1]['request_sha256']


def test_host_incumbent_correction_escalates_once_and_finalizes_integration(tmp_path, inputs):
    from isaforge.selection_provider import ResponsesSelectionProvider
    from isaforge.routed_selection import RoutedSelectionProvider, summarize_model_events
    seen = []

    def transport(payload, *args):
        model = payload['model']
        ordinal = sum(row['model'] == model for row in seen)
        if model == 'small' and ordinal == 0:
            name, arguments = 'measure', {'candidate_id': 't1',
                'decision_summary': 'Choose the fixture candidate.'}
        elif model == 'small':
            name, arguments = 'finalize', {'candidate_id': 't2', 'summary': 'Stale choice.'}
        else:
            name, arguments = 'finalize', {'candidate_id': 't1', 'summary': 'Use corrected incumbent.'}
        seen.append(dict(model=model, payload=payload))
        return dict(status='completed', output=[dict(type='function_call', name=name,
            arguments=json.dumps(arguments))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))

    small = ResponsesSelectionProvider('small', api_key='test', transport=transport)
    large = ResponsesSelectionProvider('large', api_key='test', transport=transport)
    policy = RoutedSelectionProvider(small, large, max_calls=5)
    result = run_selector(session(tmp_path, inputs), policy, max_model_calls=5)

    assert result['status'] == 'finalized'
    assert result['selected_id'] == 't1'
    assert result['charged_attempts'] == 1
    assert [row['model'] for row in seen] == ['small', 'small', 'large']
    recovery_request = json.loads(seen[-1]['payload']['input'][0]['content'])
    correction = recovery_request['messages'][-1]['result']
    assert correction['required_candidate_id'] == 't1'
    assert correction['allowed_candidate_ids'] == ['t1']
    assert result['model_events'][-1]['provider_trace'][0]['trigger'] == 'host_incumbent_correction'
    assert summarize_model_events(result['model_events'])['escalation_triggers'] == {
        'host_incumbent_correction': 1}


def test_failed_stronger_recovery_closes_on_host_incumbent(tmp_path, inputs):
    from isaforge.selection_provider import ResponsesSelectionProvider
    from isaforge.routed_selection import RoutedSelectionProvider
    small_calls = 0
    seen = []

    def transport(payload, *args):
        nonlocal small_calls
        seen.append(payload['model'])
        if payload['model'] == 'small':
            small_calls += 1
            if small_calls == 1:
                name, arguments = 'measure', {'candidate_id': 't1',
                    'decision_summary': 'Choose the fixture candidate.'}
            else:
                name, arguments = 'finalize', {'candidate_id': 't2', 'summary': 'Stale choice.'}
        else:
            name, arguments = 'not_a_tool', {}
        return dict(status='completed', output=[dict(type='function_call', name=name,
            arguments=json.dumps(arguments))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))

    primary = ResponsesSelectionProvider('small', api_key='test', transport=transport)
    stronger = ResponsesSelectionProvider('strong', api_key='test', transport=transport)
    router = RoutedSelectionProvider(primary, stronger, max_calls=4)
    result = run_selector(session(tmp_path, inputs), router, max_model_calls=4)

    assert seen == ['small', 'small', 'strong']
    assert result['status'] == 'host_fallback'
    assert result['finalization_source'] == 'host'
    assert result['fallback_reason'] == 'model_error'
    assert result['selected_id'] == result['authoritative_selection']['candidate_id'] == 't1'
    assert result['charged_attempts'] == 1
    assert router.calls == result['model_calls'] == 3
    assert result['host_events'][0]['error_type'] == 'InvalidActionError'
    assert result['model_events'][-1]['provider_trace'][-1]['trigger'] == 'host_incumbent_correction'


def test_memory_policy_is_label_safe_and_preserves_paid_loop(tmp_path, inputs):
    from isaforge.agent_memory import MemoryAugmentedPolicy
    class InspectingPolicy(MatchedBaselinePolicy):
        def choose(self, request):
            text = json.dumps(request['retrieved_memory'])
            assert 'UNPAID-CANARY' not in text
            assert all(h['record']['workload_group'] != 'target'
                       for h in request['retrieved_memory']['hits'])
            return super().choose(request)
    inputs[3]['t1']['private_path'] = 'UNPAID-CANARY'
    p = MemoryAugmentedPolicy(InspectingPolicy('merit'))
    result = run_selector(session(tmp_path, inputs), p)
    assert result['charged_attempts'] == 3 and result['status'] == 'finalized'
    assert result['model_events'][0]['memory_trace']['mode'] == 'hybrid'
    assert result['model_events'][0]['tool_sequence'] == 1

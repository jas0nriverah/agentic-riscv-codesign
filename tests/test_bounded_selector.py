"""Budget, information-boundary and failure tests; no live LLM/hardware jobs."""
import copy
import json
from pathlib import Path

import pytest

from isaforge import budgeted_selection as b
from isaforge import codesign as c
from isaforge.bounded_selector import MatchedBaselinePolicy, ReplaySelectionSession, run_selector
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
    return dict(tool=tool, arguments=arguments)


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


def test_model_limit_falls_back_to_best_paid_feasible(tmp_path, inputs):
    class Policy:
        def choose(self, request): return action('measure', candidate_id='t1')
    result = run_selector(session(tmp_path, inputs), Policy(), max_model_calls=1)
    assert result['status'] == 'model_call_limit'
    assert result['charged_attempts'] == 1
    assert result['selected_id'] == 't1'


def test_model_exception_and_private_errors_not_released(tmp_path, inputs):
    class Policy:
        def choose(self, request): raise RuntimeError('/private/MODEL-CANARY')
    s = session(tmp_path, inputs)
    result = run_selector(s, Policy())
    assert result['status'] == 'model_error' and result['charged_attempts'] == 0
    assert 'MODEL-CANARY' not in json.dumps(result)


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
            arguments=json.dumps({'candidate_id': 't1'}))],
            usage=dict(input_tokens=10, output_tokens=4, total_tokens=14))
    small = ResponsesSelectionProvider('small', api_key='test', transport=transport)
    large = ResponsesSelectionProvider('large', api_key='test', transport=transport)
    policy = RoutedSelectionProvider(small, large, max_calls=2)
    result = run_selector(session(tmp_path, inputs), policy)
    assert policy.calls == 2
    assert result['charged_attempts'] == 1
    assert result['selected_id'] == 't1'
    assert result['status'] == 'model_error'  # Shared LLM budget exhausted, incumbent retained.
    accounting = summarize_model_events(result['model_events'])
    assert accounting['dispatched_calls'] == 2
    assert accounting['observed_tokens']['total_tokens'] == 28
    assert accounting['escalation_calls'] == 1 and accounting['usage_complete']
    saved = c.unseal(tmp_path/'ledger.json')
    assert saved['model_events'][0]['provider_trace'][1]['identity']['model'] == 'large'

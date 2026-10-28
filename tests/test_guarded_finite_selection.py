"""Synthetic software contracts only; no measured research outcomes or jobs."""
import copy

import pytest

from isaforge import finite_selection as f, guarded_finite_selection as g, joint_hardware as j
from test_budgeted_selection import history, measured, public


@pytest.fixture
def case():
    training = history()
    pool = [public('t1', saved_cycles=200),
            public('t2', 'sub(in0,in1)', saved_cycles=190),
            public('t3', 'xor(in0,in1)', saved_cycles=180)]
    return training, pool, j.JointHardwarePosterior.fit(training, pool)


def run(case, provider, receiver=None):
    training, pool, posterior = case
    return g.search(pool, training, provider, posterior=posterior,
        policy=f.LOOKAHEAD, area_cap=64, seed=0, budget=3, on_event=receiver)


def assert_no_oracle_claim(receipt):
    assert receipt['reference_complete'] is False
    assert receipt['oracle'] is receipt['regret'] is None
    assert receipt['endpoints'] == []
    assert receipt['new_preregistration_required'] and not receipt['dispatch_authorized']


def test_zero_residual_completes_full_budget_and_journals_proofs_before_calls(case):
    events, calls = [], []
    before = case[2].snapshot()
    def provider(row):
        assert events[-1]['kind'] == 'dispatch'
        assert events[-2]['kind'] == 'acquisition_proof'
        assert events[-2]['payload']['event']['candidate_id'] == row['candidate_id']
        calls.append(row['candidate_id'])
        return measured(row, savings=row['latency_features']['estimated_saved_cycles'])
    receipt = run(case, provider, events.append)
    assert receipt['status'] == 'completed' and receipt['stop_reason'] is None
    assert receipt['actual_charged_count'] == 3
    assert receipt['charged_candidate_ids'] == calls and len(set(calls)) == 3
    assert len(receipt['completed_search']['curve']) == 3
    assert receipt['paid_measurement_seconds'] == 6
    assert receipt['journal'] == events
    assert [entry['sequence'] for entry in events] == list(range(len(events)))
    assert case[2].snapshot() == before
    assert_no_oracle_claim(receipt)


@pytest.mark.parametrize('residual', [-1, 1])
def test_first_violation_preserves_paid_label_and_blocks_second_provider(case, residual):
    calls, returned = [], []
    def provider(row):
        calls.append(row['candidate_id'])
        value = measured(row,
            savings=row['latency_features']['estimated_saved_cycles']+residual, seconds=7.)
        returned.append(copy.deepcopy(value))
        return value
    receipt = run(case, provider)
    assert receipt['status'] == 'assumption_violation_stopped'
    assert receipt['actual_charged_count'] == len(calls) == 1
    assert receipt['charged_candidate_ids'] == calls
    assert receipt['paid_outcomes'] == returned
    assert receipt['paid_measurement_seconds'] == 7
    assert receipt['measured_incumbent'] == returned[0]
    assert receipt['best_verified_speedup'] == returned[0]['speedup']
    assert receipt['stop_reason']['measured_minus_calibrated_saved_cycles'] == residual
    assert receipt['completed_search'] is None
    kinds = [event['kind'] for event in receipt['journal']]
    assert kinds == ['acquisition_proof', 'dispatch', 'paid_outcome',
                     'assumption_violation', 'dispatch_blocked', 'trajectory_closed']
    assert_no_oracle_claim(receipt)


def test_final_query_violation_is_stopped_even_after_underlying_return(case):
    calls = []
    def provider(row):
        calls.append(row['candidate_id'])
        return measured(row, savings=row['latency_features']['estimated_saved_cycles']-
                        int(len(calls) == 3))
    receipt = run(case, provider)
    assert receipt['status'] == 'assumption_violation_stopped'
    assert receipt['actual_charged_count'] == 3
    assert receipt['stop_reason']['charged_attempt'] == 3
    assert receipt['stop_reason']['measured_minus_calibrated_saved_cycles'] == -1
    assert receipt['completed_search'] is None
    assert not any(event['kind'] == 'dispatch_blocked' for event in receipt['journal'])
    assert_no_oracle_claim(receipt)


def test_exact_integer_comparison_does_not_round_away_one_cycle():
    saved = 2**53+1
    training = history()
    pool = [public('large-counter', baseline=10*saved, saved_cycles=saved)]
    posterior = j.JointHardwarePosterior.fit(training, pool)
    receipt = g.search(pool, training, lambda row: measured(row, savings=saved-1),
        posterior=posterior, policy=f.MYOPIC, area_cap=64, seed=0, budget=1)
    assert receipt['status'] == 'assumption_violation_stopped'
    assert receipt['stop_reason']['calibrated_estimated_saved_cycles'] == saved
    assert receipt['stop_reason']['measured_minus_calibrated_saved_cycles'] == -1


def test_receiver_and_provider_cannot_mutate_preserved_journal(case):
    external, originals = [], []
    def receiver(entry):
        external.append(copy.deepcopy(entry))
        entry.clear()
    def provider(row):
        for value in originals:
            value.clear()
        value = measured(row, savings=row['latency_features']['estimated_saved_cycles'])
        originals.append(value)
        row.clear()
        return value
    receipt = run(case, provider, receiver)
    assert receipt['journal'] == external
    assert all(row['correctness_verified'] for row in receipt['paid_outcomes'])
    assert all(row['measurement_seconds'] == 2 for row in receipt['paid_outcomes'])


def test_unknown_failure_is_charged_without_fabricated_residual_or_incumbent(case):
    calls = []
    def provider(row):
        calls.append(row['candidate_id'])
        if len(calls) == 1:
            return dict(row, status='failed', error='synthetic infrastructure failure',
                        measurement_seconds=7.)
        return measured(row, savings=row['latency_features']['estimated_saved_cycles'])
    receipt = run(case, provider)
    assert receipt['status'] == 'completed' and len(calls) == 3
    assert receipt['paid_measurement_seconds'] == 11
    assert receipt['paid_outcomes'][0]['status'] == 'failed'
    assert 'speedup' not in receipt['paid_outcomes'][0]
    assert not any(event['kind'] == 'assumption_violation' for event in receipt['journal'])


def test_receiver_failure_before_dispatch_does_not_call_provider(case):
    def reject(_):
        raise RuntimeError('synthetic receiver unavailable')
    with pytest.raises(RuntimeError, match='receiver unavailable'):
        run(case, lambda _: pytest.fail('Provider called before proof receiver accepted'), reject)

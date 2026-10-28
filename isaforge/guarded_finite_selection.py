"""Opt-in prospective stop guard around the frozen finite-pool search.

This adapter changes no estimator or historical campaign. A new preregistration
must bind it before paid outcomes. Its journal is cooperative Python evidence,
not durable storage or a native-dispatch authorization mechanism.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import budgeted_selection as b, codesign as c, finite_selection as f

SOURCES = tuple(dict.fromkeys(('isaforge/guarded_finite_selection.py', *f.SOURCES)))


def source_bindings():
    root = Path(__file__).resolve().parents[1]
    return {name: c.sha(root/name) for name in SOURCES}


class _AssumptionStop(Exception):
    """Internal control flow; unrelated provider/callback errors propagate."""


def search(public, training, provider, *, posterior, policy, area_cap,
           clock_mhz=12., seed, budget, on_event=None):
    """Journal paid evidence and stop before another dispatch after a mismatch.

    ``on_event`` receives independent copies in append order. A receiver should
    persist them before returning if durable evidence is needed. Unexpected
    provider, validation or receiver exceptions propagate rather than becoming
    successful, failed-hardware, or completed-trajectory receipts.
    """
    c.require(callable(provider), 'Callable target provider required')
    c.require(on_event is None or callable(on_event), 'Callable journal receiver required')
    journal, attempts, outcomes = [], [], []
    stop_reason = None
    authorized_id = None
    underlying = None

    def record(kind, payload):
        entry = dict(sequence=len(journal), kind=kind, payload=copy.deepcopy(payload))
        journal.append(entry)
        if on_event is not None:
            on_event(copy.deepcopy(entry))

    def acquire(proof):
        nonlocal authorized_id
        if stop_reason is not None:
            record('dispatch_blocked', dict(stop_reason=stop_reason,
                blocked_candidate_id=proof['event']['candidate_id'],
                charged_attempts=len(attempts)))
            raise _AssumptionStop()
        c.require(authorized_id is None, 'Previous authorized query has not returned')
        record('acquisition_proof', proof)
        authorized_id = proof['event']['candidate_id']

    def paid(candidate):
        nonlocal authorized_id, stop_reason
        identity = candidate['candidate_id']
        c.require(stop_reason is None and identity == authorized_id and
                  identity not in attempts, 'Unblocked unique pre-proven query required')
        attempts.append(identity)  # Charge before the only target-provider call.
        record('dispatch', dict(candidate_id=identity, charged_attempts=len(attempts)))
        outcome = copy.deepcopy(provider(copy.deepcopy(candidate)))
        outcomes.append(outcome)
        record('paid_outcome', dict(candidate_id=identity, outcome=outcome))
        successful = b.validate_outcome(outcome, candidate)
        authorized_id = None
        if successful:
            expected = candidate['latency_features']['estimated_saved_cycles']
            b._number(expected, 'calibrated estimated saved cycles')
            actual = outcome['baseline_cycles']-outcome['candidate_cycles']
            if actual != expected:
                stop_reason = dict(code='calibrated_benefit_mismatch',
                    candidate_id=identity, charged_attempt=len(attempts),
                    measured_saved_cycles=actual, calibrated_estimated_saved_cycles=expected,
                    measured_minus_calibrated_saved_cycles=actual-expected)
                record('assumption_violation', stop_reason)
        return copy.deepcopy(outcome)

    try:
        underlying = f.search(public, training, paid, posterior=posterior,
            policy=policy, area_cap=area_cap, clock_mhz=clock_mhz,
            seed=seed, budget=budget, on_acquire=acquire)
    except _AssumptionStop:
        c.require(stop_reason is not None, 'Assumption stop requires a paid mismatch')

    stopped = stop_reason is not None
    feasible = [row for row in outcomes if b._feasible(row, area_cap, clock_mhz)
                and row['speedup'] > 1.]
    incumbent = min(feasible, key=lambda row: (-row['speedup'],
        row['area_delta_lut4'], row['candidate_id'])) if feasible else None
    c.require(stopped or len(attempts) == budget, 'Completed guard must exhaust planned budget')
    status = 'assumption_violation_stopped' if stopped else 'completed'
    record('trajectory_closed', dict(status=status, planned_budget=budget,
        actual_charged_count=len(attempts), stop_reason=stop_reason))
    return dict(schema='isaforge-prospective-finite-guard-v1', status=status,
        policy=policy, seed=seed, planned_budget=budget,
        actual_charged_count=len(attempts), charged_candidate_ids=list(attempts),
        paid_outcomes=copy.deepcopy(outcomes), paid_outcome_sha256=[c.digest(row) for row in outcomes],
        paid_measurement_seconds=sum(row['measurement_seconds'] for row in outcomes),
        measured_incumbent=copy.deepcopy(incumbent),
        best_verified_speedup=incumbent['speedup'] if incumbent else 1.,
        stop_reason=copy.deepcopy(stop_reason), reference_complete=False,
        oracle=None, regret=None, endpoints=[],
        completed_search=None if stopped else underlying,
        journal=copy.deepcopy(journal), source_bindings=source_bindings(),
        new_preregistration_required=True, dispatch_authorized=False)

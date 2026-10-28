"""Stopping-rule evidence boundaries; synthetic fixtures, no models or hardware."""
import json

import pytest

from scripts.analyze_tiny_regex_stopping_rule import analyze, authenticate, sha, simulate


def public(identity, estimate):
    return dict(candidate_id=identity, latency_features=dict(
        baseline_cycles=1000, estimated_saved_cycles=estimate))


def measured(identity, saved, *, area=40, correct=True):
    return dict(candidate_id=identity, baseline_cycles=1000,
        candidate_cycles=1000-saved, correctness_verified=correct,
        device_fits=True, area_delta_lut4=area, routed_fmax_min_mhz=65,
        measurement_seconds=10)


def test_stop_does_not_read_remaining_outcomes_and_equality_is_allowed():
    pool = [public('fast', 100), public('other', 100)]
    seen = []
    def release(identity):
        seen.append(identity)
        assert identity == 'fast', 'Unqueried outcome must stay hidden'
        return measured(identity, 100)
    result = simulate(pool, ['fast', 'other'], release, budget=3)
    assert seen == ['fast']
    assert result['simulated_queries'] == 1
    assert result['stopped_by_shared_rule']
    assert result['snapshots'][-1]['maximum_remaining_estimated_saved_cycles'] == 100
    assert result['incumbent']['saved_cycles'] == 100


def test_remaining_bound_covers_whole_roster_not_only_archived_next_actions():
    pool = [public('paid', 100), public('next', 50), public('not_in_order', 200)]
    outcomes = {'paid': measured('paid', 100), 'next': measured('next', 50)}
    result = simulate(pool, ['paid', 'next'], outcomes.__getitem__, budget=3)
    assert result['simulated_queries'] == 2
    assert not result['stopped_by_shared_rule']
    assert result['terminal_reason'] == 'archived_agent_episode_ended'
    assert result['snapshots'][-1]['maximum_remaining_estimated_saved_cycles'] == 200


@pytest.mark.parametrize('area,correct', [(65, True), (40, False)])
def test_infeasible_or_incorrect_measurement_cannot_support_stopping(area, correct):
    pool = [public('paid', 100), public('next', 50)]
    outcomes = {'paid': measured('paid', 100, area=area, correct=correct),
                'next': measured('next', 50)}
    result = simulate(pool, ['paid', 'next'], outcomes.__getitem__, budget=2)
    assert result['simulated_queries'] == 2
    assert result['snapshots'][1]['incumbent']['candidate_id'] is None
    assert not result['snapshots'][1]['stop']


def test_paid_assumption_mismatch_disables_an_apparently_valid_stop():
    pool = [public('paid', 90), public('next', 50)]
    outcomes = {'paid': measured('paid', 100), 'next': measured('next', 50)}
    result = simulate(pool, ['paid', 'next'], outcomes.__getitem__, budget=2)
    assert result['simulated_queries'] == 2
    assert not result['stopped_by_shared_rule']
    assert result['snapshots'][1]['conditional_dominance']
    assert not result['snapshots'][1]['stop']
    assert result['paid_assumption_violations'] == [dict(
        candidate_id='paid', measured_minus_estimated_saved_cycles=10)]


def test_authentication_rejects_changed_member_and_changed_manifest(tmp_path):
    member = tmp_path / 'evidence.json'
    member.write_text('{}\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'evidence.json': sha(member)}))
    expected = sha(manifest)
    (tmp_path / 'manifest.json.sha256').write_text(expected + '\n')
    authenticate(tmp_path, expected)
    member.write_text('{"changed":true}\n')
    with pytest.raises(ValueError, match='member hash mismatch'):
        authenticate(tmp_path, expected)
    manifest.write_text(json.dumps({'evidence.json': sha(member)}))
    with pytest.raises(ValueError, match='manifest changed'):
        authenticate(tmp_path, expected)


def test_budget_exhaustion_does_not_claim_an_after_stop_audit():
    rows = analyze()['runs']
    exhausted = [row for row in rows if row['terminal_reason'] == 'budget_exhausted'
                 and row['missed_oracle_cycle_reduction'] > 0]
    assert exhausted, 'Exercise a real budget-limited prefix with remaining improvement'
    assert all(not row['stopped_by_shared_rule'] for row in exhausted)
    assert all(row['unmeasured_better_feasible_candidates_after_stop'] == []
               for row in rows if not row['stopped_by_shared_rule'])

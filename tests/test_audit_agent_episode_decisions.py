"""Validate advice/context/outcome links without dispatch or fitting."""
from __future__ import annotations
import copy
import pytest
from isaforge import codesign as c
from scripts import audit_agent_episode_decisions as audit


@pytest.fixture
def ledger():
    return copy.deepcopy(c.unseal(audit.RESULTS / 'agent/ledger.json'))


def reseal_context(ledger):
    decision = ledger['decision_rationale']['selection_decisions'][0]
    context = decision['action_context']
    digest = c.digest(context)
    decision['action_context_sha256'] = decision['public_context_sha256'] = digest
    call = next(m for m in ledger['model_events'] if m.get('tool_sequence') == decision['tool_sequence'])
    call['action_context'] = copy.deepcopy(context)
    call['action_context_sha256'] = digest


def test_authenticated_episode_reports_one_paid_probe_and_does_not_infer_reason():
    ledger, source = audit.authenticated_episode(audit.RESULTS)
    report = audit.audit_ledger(ledger)
    assert report['charged_probes'] == 1 and report['paid_budget'] == 3 and report['unused_budget'] == 2
    assert report['model_decisions'] == 3 and report['provider_calls'] == 0
    probe = report['probes'][0]
    assert probe['logged_reason']['verified'] is False
    assert probe['host_descriptive_comparison']['followed_utility_advice'] is True
    assert probe['observed_verification']['verified_feasible'] is True
    assert source['ledger_sha256'] == c.sha(audit.RESULTS / 'agent/ledger.json')


def test_tampered_reason_does_not_match_authoritative_measure_action(ledger):
    ledger['decision_rationale']['selection_decisions'][0]['decision_summary'] = 'invented reason'
    with pytest.raises(ValueError, match='Logged reason'):
        audit.audit_ledger(ledger)


def test_tampered_preprobe_context_hash_is_rejected(ledger):
    ledger['decision_rationale']['selection_decisions'][0]['action_context_sha256'] = 'changed'
    with pytest.raises(ValueError, match='context hash'):
        audit.audit_ledger(ledger)


def test_current_outcome_in_preprobe_snapshot_rejected_even_with_updated_hashes(ledger):
    event = next(e for e in ledger['events'] if 'charged_attempt' in e)
    context = ledger['decision_rationale']['selection_decisions'][0]['action_context']
    context['observations'] = [copy.deepcopy(event['observation'])]
    reseal_context(ledger)
    with pytest.raises(ValueError, match='uncharged/current outcome'):
        audit.audit_ledger(ledger)


def test_public_prediction_mutation_fails_independent_board_reconstruction(ledger):
    ledger['events'][0]['public_result']['predictions'][0]['current_grouped_ml']['pairwise_rank_score'] += 1
    with pytest.raises(ValueError, match='Advice board differs'):
        audit.audit_ledger(ledger)


def test_tampered_paid_feasibility_projection_is_rejected(ledger):
    ledger['decision_rationale']['selection_decisions'][0]['paid_verification']['verified_feasible'] = False
    with pytest.raises(ValueError, match='paid feasibility differs'):
        audit.audit_ledger(ledger)


def test_duplicate_charged_probe_links_are_rejected(ledger):
    ledger['decision_rationale']['selection_decisions'].append(
        copy.deepcopy(ledger['decision_rationale']['selection_decisions'][0]))
    with pytest.raises(ValueError, match='One unique decision'):
        audit.audit_ledger(ledger)


def test_historical_v1_advice_is_validated_without_inventing_utility_recommendations():
    results = c.ROOT / 'results/2026-10-28-pulpino-sudoku-selection-r4'
    ledger, _ = audit.authenticated_episode(results)
    report = audit.audit_ledger(ledger)
    assert report['charged_probes'] == 3 and report['unused_budget'] == 0
    assert all(p['public_advice']['utility_recommendation_id'] is None for p in report['probes'])
    assert all(p['host_descriptive_comparison']['followed_utility_advice'] is None for p in report['probes'])
    assert all(p['observed_verification']['verified_feasible'] is False for p in report['probes'])
    assert c.digest(report) == c.digest(audit.audit_ledger(copy.deepcopy(ledger)))


def test_prior_paid_observation_change_is_rejected_in_later_snapshot():
    results = c.ROOT / 'results/2026-10-28-pulpino-sudoku-selection-r4'
    ledger, _ = audit.authenticated_episode(results)
    later = ledger['decision_rationale']['selection_decisions'][1]
    call = next(m for m in ledger['model_events'] if m.get('tool_sequence') == later['tool_sequence'])
    call['public_context']['observations'][0]['speedup'] += .1
    # Rebind the altered snapshot so the semantic prefix check, rather than
    # merely the digest check, must detect the changed previously paid result.
    later['public_context_sha256'] = c.digest(call['public_context'])
    call['public_context_sha256'] = later['public_context_sha256']
    with pytest.raises(ValueError, match='earlier paid outcome'):
        audit.audit_ledger(ledger)


def test_reproduction_command_matches_explicit_build_inputs_and_output(tmp_path):
    results = c.ROOT / 'results/2026-10-28-pulpino-sudoku-selection-r4'
    output = tmp_path / 'audit report'
    report = audit.build(results, output)
    text = (output / 'README.md').read_text()
    assert '--results results/2026-10-28-pulpino-sudoku-selection-r4' in text
    assert "--output '" + str(output) + "'" in text
    assert report['provenance']['script_sha256'] == c.sha(audit.__file__)

"""Source identity, closed failure semantics and equal-budget policy integration."""
import copy
from pathlib import Path

import pytest

from isaforge import codesign as c
from isaforge import factorized_selection_experiment as e

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case():
    path = ROOT/'results/2026-10-21-sha256-selection/model'
    protocol = c.unseal(path/'protocol.json')
    public = c.unseal(path/'public.json')
    contexts = copy.deepcopy(protocol['contexts'])
    contexts[public[0]['benchmark']]['workload_group'] = protocol['target_workload']
    report = c.unseal(path/'report.json')
    labels = {event['candidate_id']: event['observation']
              for run in report['runs'] for event in run['events'] if 'observation' in event}
    outcomes = [labels[row['candidate_id']] for row in public]
    audit = dict(attempt_collection_complete=True, candidate_wall_seconds_complete=True, unattempted=[],
        context_id=public[0]['benchmark'].split(':', 1)[1], public=public, outcomes=outcomes,
        pool_names=[f'candidate_{index:02d}' for index in range(len(public))],
        charged_candidate_attempts=len(public), failed_or_interrupted=[], reference_censored_candidates=[])
    return dict(history=c.unseal(path/'history.json'), public=public, contexts=contexts,
                target_workload=protocol['target_workload'], outcomes=outcomes, audit=audit)


def freeze_inputs(case):
    return {key: case[key] for key in ('history', 'public', 'contexts', 'target_workload')}


@pytest.mark.parametrize('observed', [1, True, None, -1])
def test_reject_observed_labels_before_writes(case, tmp_path, observed):
    with pytest.raises(ValueError, match='zero observed'):
        e.freeze(**freeze_inputs(case), output=tmp_path/'freeze', target_labels_observed=observed,
                 calibration_cost_seconds=0)
    assert not (tmp_path/'freeze').exists()


@pytest.mark.parametrize('change', ['public', 'context', 'context_id'])
def test_target_source_aliases_cannot_bypass_holdout(case, tmp_path, change):
    if change == 'public': case['target_workload'] = 'beebs-jfdctint'
    elif change == 'context': case['contexts'][case['public'][0]['benchmark']]['workload_group'] = 'other'
    else: case['contexts'][case['public'][0]['benchmark']]['context_id'] = 'other'
    with pytest.raises(ValueError, match='(disagree|identity)'):
        e.freeze(**freeze_inputs(case), output=tmp_path/'freeze', target_labels_observed=0,
                 calibration_cost_seconds=0)
    assert not (tmp_path/'freeze').exists()


def failed_case(case, failure_class='infrastructure_unknown', censored=True, index=0):
    case = copy.deepcopy(case)
    source = case['outcomes'][index]
    row = dict(case['public'][index], status='failed', measurement_seconds=source['measurement_seconds'],
               error='preserved failure', failure_class=failure_class, reference_censored=censored)
    case['outcomes'][index] = row
    case['audit']['outcomes'] = case['outcomes']
    name = case['audit']['pool_names'][index]
    case['audit']['failed_or_interrupted'] = [dict(name=name, classification=failure_class,
        error=row['error'], elapsed_seconds=row['measurement_seconds'], reference_censored=censored)]
    case['audit']['reference_censored_candidates'] = [name] if censored else []
    return case


def test_classified_native_failure_censors_reference(case):
    case = failed_case(case)
    assert e.checked_outcomes(case['public'], case['outcomes'], case['audit']) is True


@pytest.mark.parametrize('failure_class', sorted(e.INVALID_FAILURES))
def test_recorded_invalid_execution_is_not_infrastructure_censorship(case, failure_class):
    case = failed_case(case, failure_class=failure_class, censored=False)
    assert e.checked_outcomes(case['public'], case['outcomes'], case['audit']) is False


@pytest.mark.parametrize('mutation', ['unclassified', 'missing_flag', 'false_flag', 'wrong_name', 'wrong_context',
                                     'missing_reference_name', 'extra_reference_name', 'wrong_failure_time'])
def test_native_censorship_integrity_rejects_mismatches(case, mutation):
    case = failed_case(case)
    row, audit = case['outcomes'][0], case['audit']
    if mutation == 'unclassified': row.pop('failure_class')
    elif mutation == 'missing_flag': row.pop('reference_censored')
    elif mutation == 'false_flag': row['reference_censored'] = False
    elif mutation == 'wrong_name': audit['failed_or_interrupted'][0]['name'] = 'other'
    elif mutation == 'wrong_context': audit['context_id'] = 'other'
    elif mutation == 'missing_reference_name': audit['reference_censored_candidates'] = []
    elif mutation == 'extra_reference_name': audit['reference_censored_candidates'].append('extra')
    else: audit['failed_or_interrupted'][0]['elapsed_seconds'] += 1
    with pytest.raises(ValueError): e.checked_outcomes(case['public'], case['outcomes'], audit)


def test_factorized_freeze_12_policies_export_replay_and_report_guard(case, tmp_path):
    root = tmp_path/'freeze'
    protocol = e.freeze(**freeze_inputs(case), output=root, target_labels_observed=0,
                        calibration_cost_seconds=0, scope='consumed-data development')
    assert protocol['historical_fitting_rows'] == 21
    assert len(protocol['policies']) == 12
    checked = e.authenticate(root)
    assert checked['controls']['history'] == checked['history']
    assert not (root/'report.json').exists()
    outer = {row['candidate_id']: row['measurement_seconds']+1 for row in case['outcomes']}
    result = e.evaluate(root, case['outcomes'], native_audit=case['audit'], outer_times=outer)
    assert result['trajectories'] == 180 and result['endpoints'] == 540
    assert len(result['summary']) == 108
    assert result['reference_censored'] is False
    assert all(point['target_outer_operation_seconds'] > point['target_measurement_seconds']
               for run in result['runs'] for point in run['curve'])
    e.evaluate(root, case['outcomes'], native_audit=case['audit'], outer_times=outer, verify=True)
    with pytest.raises(ValueError, match='Preserve prior'):
        e.evaluate(root, case['outcomes'], native_audit=case['audit'], outer_times=outer)
    protocol['cost_provenance'] = {'unbound': 'changed'}
    c.seal(root/'protocol.json', protocol)
    with pytest.raises(ValueError, match='metadata differs'): e.authenticate(root)


def test_support_diagnostics_are_static_and_never_a_threshold(case):
    result = e.support_diagnostics(case['history'], case['public'])
    assert len(result['candidates']) == len(case['public'])
    assert 'no abstention threshold' in result['use']


def test_cli_prediction_has_no_private_outcomes_argument_requirement(tmp_path):
    with pytest.raises(ValueError, match='Public input'):
        e.main(['predict', '--root', str(tmp_path)])

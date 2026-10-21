"""Disjoint-pool archive integrity; all synthetic orchestration starts no jobs."""
import copy
from pathlib import Path
import shutil
from unittest.mock import Mock

import pytest
from isaforge import codesign as c
from scripts import reproduce_disjoint_sha256 as r


def manifest(root):
    c.seal(root/'manifest.json',{p.relative_to(root).as_posix():c.sha(p)
        for p in sorted(root.rglob('*')) if p.is_file() and
        p.relative_to(root).as_posix() not in ('manifest.json','manifest.json.sha256')})


@pytest.fixture
def package(tmp_path):
    prereg=tmp_path/'prereg';selection=tmp_path/'selection';raw=tmp_path/'raw';campaign=tmp_path/'campaign'
    shutil.copytree(r.PREREG,prereg)
    shutil.copytree(prereg/'selection',selection)
    shutil.copytree(prereg/'baseline',raw)
    outer=c.unseal(prereg/'protocol.json')
    before=c.unseal(raw/'commands.json')
    c.seal(raw/'commands.json',before+[dict(log='synthetic-paid-command',elapsed_seconds=1.0)])
    for name in ('report.json','model/report.json'):c.seal(selection/name,dict(synthetic_fixture=True))
    public=c.unseal(selection/'model/public.json')
    outcomes=[dict(row,status='failed',measurement_seconds=float(index+1),error='synthetic infrastructure failure',
                   failure_class='infrastructure',reference_censored=True) for index,row in enumerate(public)]
    native=dict(context_id=outer['context_id'],protocol_sha256=c.sha(raw/'evaluation-protocol.json'),
        public=public,outcomes=outcomes,attempt_collection_complete=True,candidate_wall_seconds_complete=True,
        charged_candidate_attempts=6,unattempted=[],reference_censored_candidates=list(outer['native_order']),new_native_jobs=0)
    c.seal(campaign/'native/manifest.json',{})
    c.seal(campaign/'audit.json',native);c.seal(campaign/'outcomes.json',outcomes)
    files={p.relative_to(selection).as_posix():c.sha(p) for p in selection.rglob('*') if p.is_file()}
    provenance=dict(schema='isaforge-disjoint-sha256-campaign-provenance-v1',prelabel_commit='1'*40,
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),selection_manifest=files,
        source_bindings={name:c.sha(r.ROOT/name) for name in r.SOURCES},
        context_id=native['context_id'],evaluation_protocol_sha256=native['protocol_sha256'],
        outcomes_sha256=c.sha(campaign/'outcomes.json'))
    c.seal(campaign/'provenance.json',provenance);manifest(campaign)
    return dict(prereg=prereg,selection=selection,raw=raw,campaign=campaign,outer=outer,
                native=native,outcomes=outcomes,provenance=provenance)


def orchestration(package,monkeypatch):
    commit=Mock();native=Mock(return_value=copy.deepcopy(package['native']))
    refits=Mock(return_value=dict(original_control_prediction_refits=5,utility_prediction_and_model_refits=5))
    evaluate=Mock(return_value=dict(trajectories=165,endpoints=495,new_native_jobs=0))
    monkeypatch.setattr(r,'check_prelabel_commit',commit)
    monkeypatch.setattr(r.guarded_evidence,'replay',native)
    monkeypatch.setattr(r,'verify_refits',refits)
    monkeypatch.setattr(r.e,'evaluate',evaluate)
    return commit,native,refits,evaluate


def test_actual_preregistration_inventory_and_exact_prediction_tree_refits():
    assert r.check_prelabel(r.PREREG/'selection',r.PREREG)==c.sha(r.PREREG/'manifest.json')
    assert r.verify_refits(r.PREREG/'selection')==dict(original_control_prediction_refits=5,utility_prediction_and_model_refits=5)


def test_raw_baseline_copy_and_receipt_prefix(package):
    f=package;r.check_baselines(f['prereg'],f['raw'],f['selection'])
    commands=c.unseal(f['raw']/'commands.json');commands[0]['log']='changed baseline receipt'
    c.seal(f['raw']/'commands.json',commands)
    with pytest.raises(ValueError,match='receipt prefix'):r.check_baselines(f['prereg'],f['raw'],f['selection'])


@pytest.mark.parametrize('name',['selection/utility-models/seed-0/member-00.json','selection/model/predictions.json'])
def test_resealed_prereg_cannot_omit_model_or_control_artifact(package,name):
    f=package;(f['prereg']/name).unlink();manifest(f['prereg'])
    with pytest.raises(ValueError,match='complete frozen selection'):r.check_prelabel(f['selection'],f['prereg'])


def test_changed_frozen_model_even_after_child_reseal_is_rejected(package):
    f=package
    path=f['prereg']/'selection/utility-predictions.json';values=c.unseal(path)
    values[0]['by_cap']['64'][0]['mean_fractional_cycle_savings']+=1
    c.seal(path,values);manifest(f['prereg'])
    with pytest.raises(ValueError,match='Changed prelabel selection'):r.check_prelabel(f['selection'],f['prereg'])


def test_source_excluded_history_digest_cannot_be_replaced(package):
    f=package;history=c.unseal(f['prereg']/'inputs/history.json');history.reverse()
    c.seal(f['prereg']/'inputs/history.json',history);manifest(f['prereg'])
    with pytest.raises(ValueError,match='input digest'):r.check_prelabel(f['selection'],f['prereg'])


def test_outer_zero_label_assertion_and_baseline_inventory_are_mandatory(package):
    f=package;protocol=c.unseal(f['prereg']/'protocol.json')
    protocol['target_candidate_labels_observed']=True
    c.seal(f['prereg']/'protocol.json',protocol);manifest(f['prereg'])
    with pytest.raises(ValueError,match='zero-label preregistration'):r.check_prelabel(f['selection'],f['prereg'])
    protocol['target_candidate_labels_observed']=0;protocol['baseline_files'].pop()
    c.seal(f['prereg']/'protocol.json',protocol);manifest(f['prereg'])
    with pytest.raises(ValueError,match='baseline-copy list'):r.check_prelabel(f['selection'],f['prereg'])


def test_raw_rederived_outcomes_must_match_archived_values_and_unknown_classification(package):
    f=package
    assert r.authenticate_outcomes(f['native'],f['outcomes'],f['selection']) is True
    altered=copy.deepcopy(f['outcomes']);altered[0]['measurement_seconds']+=1
    with pytest.raises(ValueError,match='rederived native'):r.authenticate_outcomes(f['native'],altered,f['selection'])
    altered=copy.deepcopy(f['outcomes']);altered[0]['reference_censored']=False
    with pytest.raises(ValueError,match='rederived native'):r.authenticate_outcomes(f['native'],altered,f['selection'])


def test_complete_git_bound_replay_runs_native_registration_and_11_policy_verification(package,monkeypatch):
    f=package;commit,native,refits,evaluate=orchestration(f,monkeypatch)
    original=native.side_effect
    def check_registration(*args):
        assert r.t.g.SOURCE==r.t.SOURCE
        return copy.deepcopy(f['native'])
    native.side_effect=check_registration
    result=r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    assert result['endpoints']==495 and result['new_native_jobs']==0
    commit.assert_called_once_with(f['prereg'],'1'*40)
    native.assert_called_once_with(f['campaign']/'native',f['raw'])
    refits.assert_called_once_with(f['selection'])
    evaluate.assert_called_once_with(f['selection'],f['outcomes'],reference_censored=True,verify=True)
    assert r.t.g.SOURCE==r.t.GUARDED_SOURCE


def test_wrong_git_commit_stops_before_native_or_policy_replay(package,monkeypatch):
    f=package;commit,native,refits,evaluate=orchestration(f,monkeypatch)
    commit.side_effect=ValueError('Git manifest differs')
    with pytest.raises(ValueError,match='Git manifest'):r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called();refits.assert_not_called();evaluate.assert_not_called()


def test_resealed_outcome_file_cannot_hide_tampering_against_native_audit(package,monkeypatch):
    f=package;_,native,refits,evaluate=orchestration(f,monkeypatch)
    outcomes=copy.deepcopy(f['outcomes']);outcomes[0]['measurement_seconds']+=1
    c.seal(f['campaign']/'outcomes.json',outcomes)
    f['provenance']['outcomes_sha256']=c.sha(f['campaign']/'outcomes.json')
    c.seal(f['campaign']/'provenance.json',f['provenance']);manifest(f['campaign'])
    with pytest.raises(ValueError,match='rederived native'):r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_called_once();refits.assert_not_called();evaluate.assert_not_called()


def test_resealed_raw_audit_cannot_hide_tampering_against_native_replay(package,monkeypatch):
    f=package;_,native,refits,evaluate=orchestration(f,monkeypatch)
    audit=copy.deepcopy(f['native']);audit['charged_candidate_attempts']=5
    c.seal(f['campaign']/'audit.json',audit);manifest(f['campaign'])
    with pytest.raises(ValueError,match='raw audit differs'):r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_called_once();refits.assert_not_called();evaluate.assert_not_called()


def test_unlisted_selection_artifact_or_missing_report_stops_before_native(package,monkeypatch):
    f=package;_,native,_,_=orchestration(f,monkeypatch)
    (f['selection']/'unlisted.txt').write_text('unbound')
    with pytest.raises(ValueError,match='Complete final selection inventory'):r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called();(f['selection']/'unlisted.txt').unlink()
    for name in ('report.json','report.json.sha256'):
        (f['selection']/name).unlink();f['provenance']['selection_manifest'].pop(name)
    c.seal(f['campaign']/'provenance.json',f['provenance']);manifest(f['campaign'])
    with pytest.raises(ValueError,match='both sealed reports'):r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called()

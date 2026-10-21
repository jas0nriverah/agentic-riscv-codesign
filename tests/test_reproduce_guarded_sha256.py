"""Preregistration/archive inventory fixtures start no native hardware jobs."""
from pathlib import Path
import shutil

import pytest

from isaforge import codesign as c
from scripts import reproduce_guarded_sha256 as r


def manifest(root):
    c.seal(root/'manifest.json',{p.relative_to(root).as_posix():c.sha(p)
        for p in sorted(root.rglob('*')) if p.is_file() and
        p.relative_to(root).as_posix() not in ('manifest.json','manifest.json.sha256')})


@pytest.fixture
def frozen(tmp_path):
    checkout=tmp_path/'checkout';checkout.mkdir()
    selection=checkout/'selection';selection.mkdir()
    prereg=checkout/'prereg';prereg.mkdir()
    raw=checkout/'raw';raw.mkdir()
    campaign=checkout/'campaign';campaign.mkdir()
    before=[dict(log='measurements/baseline/compile.log',elapsed_seconds=1)]
    for name,value in [('plan.json',dict(context_id='context',workload='nettle-sha256')),
        ('discovery/discovery.json',dict(context_id='context')),
        ('measurements/baseline/measurement.json',dict(context_id='context')),
        ('commands.json',before+[dict(log='measurements/candidate_00/compile.log',elapsed_seconds=2)]),
        ('evaluation-protocol.json',dict(baseline_receipts=before)),
        ('attempt-ledger/baseline.json',dict(status='success'))]:
        c.seal(raw/name,value)
    for name in ('model/public.json','model/predictions.json','baseline.json','historical-corpus.json'):
        c.seal(selection/name,dict(fixture=name))
    protocol=dict(schema='isaforge-guarded-selection-v1',scope='prospective',
        target_workload=r.WORKLOAD,target_labels_read=0,
        evaluation_protocol_sha256=c.sha(raw/'evaluation-protocol.json'),
        source_bindings={'frozen-source.py':'source-hash'},
        artifacts={p.relative_to(selection).as_posix():c.sha(p) for p in selection.rglob('*') if p.is_file()})
    c.seal(selection/'protocol.json',protocol)
    shutil.copytree(selection,prereg/'selection')
    for native,copied in r.BASELINES.items():
        dest=prereg/copied;dest.parent.mkdir(parents=True,exist_ok=True)
        if native=='commands.json':
            c.seal(dest,before)
        else:
            shutil.copyfile(raw/native,dest)
            shutil.copyfile(raw/(native+'.sha256'),prereg/(copied+'.sha256'))
    c.seal(prereg/'protocol.json',dict(schema='isaforge-guarded-preregistration-v1',
        target_labels_read=0,target_workload=r.WORKLOAD,context_id='context',
        baseline_files=dict(r.BASELINES),selection_source_bindings=protocol['source_bindings']))
    manifest(prereg)
    c.seal(selection/'report.json',dict(policy_results='fixture'))
    sources={}
    for name in (r.SOURCE,r.REPORTER):
        path=checkout/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture source '+name)
        sources[name]=c.sha(path)
    files={p.relative_to(selection).as_posix():c.sha(p) for p in selection.rglob('*') if p.is_file()}
    c.seal(campaign/'native/manifest.json',{})
    c.seal(campaign/'selection-manifest.json',files)
    provenance=dict(schema='isaforge-guarded-campaign-provenance-v1',prelabel_commit='1'*40,
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),selection_manifest=files,source_bindings=sources)
    c.seal(campaign/'provenance.json',provenance);manifest(campaign)
    return dict(checkout=checkout,selection=selection,prereg=prereg,raw=raw,
                campaign=campaign,provenance=provenance,before=before)


def test_complete_prelabel_inventory_and_final_receipt_prefix(frozen):
    f=frozen
    assert r.check_prelabel(f['selection'],f['prereg'])==c.sha(f['prereg']/'manifest.json')
    r.check_baselines(f['prereg'],f['raw'],f['selection'])


@pytest.mark.parametrize('omit_all',[False,True])
def test_resealed_manifest_cannot_omit_frozen_selection_files(frozen,omit_all):
    f=frozen;root=f['prereg']
    if omit_all:
        shutil.rmtree(root/'selection')
    else:
        (root/'selection/model/predictions.json').unlink()
    manifest(root)
    with pytest.raises(ValueError,match='complete frozen selection inventory'):
        r.check_prelabel(f['selection'],root)


def test_baseline_mapping_cannot_silently_omit_an_entire_required_copy(frozen):
    f=frozen;path=f['prereg']/'protocol.json';protocol=c.unseal(path)
    copied=protocol['baseline_files'].pop('discovery/discovery.json')
    (f['prereg']/copied).unlink();(f['prereg']/(copied+'.sha256')).unlink()
    c.seal(path,protocol);manifest(f['prereg'])
    with pytest.raises(ValueError,match='baseline-copy mapping'):
        r.check_prelabel(f['selection'],f['prereg'])


def test_changed_copied_selection_bytes_are_rejected_even_after_resealing_prereg(frozen):
    f=frozen;c.seal(f['prereg']/'selection/model/public.json',dict(changed=True));manifest(f['prereg'])
    with pytest.raises(ValueError,match='Changed prelabel selection artifact'):
        r.check_prelabel(f['selection'],f['prereg'])


def test_archived_baseline_copy_and_receipt_prefix_are_both_required(frozen):
    f=frozen;c.seal(f['raw']/'plan.json',dict(context_id='other',workload='nettle-sha256'))
    with pytest.raises(ValueError,match='context differs'):
        r.check_baselines(f['prereg'],f['raw'],f['selection'])
    c.seal(f['raw']/'plan.json',dict(context_id='context',workload='nettle-sha256'))
    c.seal(f['raw']/'commands.json',[dict(log='different')])
    with pytest.raises(ValueError,match='receipt prefix differs'):
        r.check_baselines(f['prereg'],f['raw'],f['selection'])


@pytest.mark.parametrize('path',['../escape','/absolute','model/../protocol.json','model//public.json'])
def test_noncanonical_or_escaping_artifact_names_are_rejected(tmp_path,path):
    with pytest.raises(ValueError):
        r._path(tmp_path,path)


def setup_replay(f,monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(r,'ROOT',f['checkout'])
    commit=Mock();monkeypatch.setattr(r,'check_prelabel_commit',commit)
    native=Mock(return_value=dict(context_id='context',charged_candidate_attempts=6,new_native_jobs=0))
    policy=Mock(return_value=dict(selection=dict(policy_seed_cap_budget_outcomes=450),new_native_jobs=0))
    monkeypatch.setattr(r.guarded_evidence,'replay',native)
    monkeypatch.setattr(r.guarded_selection,'evaluate',policy)
    return commit,native,policy


def test_replay_requires_git_binding_and_uses_portable_history_root(frozen,monkeypatch):
    f=frozen;commit,native,policy=setup_replay(f,monkeypatch)
    result=r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    assert result['policy_seed_cap_budget_outcomes']==450 and result['new_native_jobs']==0
    commit.assert_called_once_with(f['prereg'],'1'*40)
    native.assert_called_once_with(f['campaign']/'native',f['raw'])
    policy.assert_called_once_with(f['selection'],f['raw'],
        history_raw_root=f['checkout']/'generated/reproduction/budget-campaign',verify=True)


def test_wrong_committed_manifest_stops_before_archive_or_policy_replay(frozen,monkeypatch):
    f=frozen;commit,native,policy=setup_replay(f,monkeypatch)
    commit.side_effect=ValueError('Prelabel Git commit manifest differs')
    with pytest.raises(ValueError,match='Git commit manifest differs'):
        r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called();policy.assert_not_called()


def test_omitted_final_report_cannot_be_hidden_by_resealing_all_manifests(frozen,monkeypatch):
    f=frozen;_,native,policy=setup_replay(f,monkeypatch)
    provenance=f['provenance']
    for name in ('report.json','report.json.sha256'):
        (f['selection']/name).unlink();provenance['selection_manifest'].pop(name)
    c.seal(f['campaign']/'selection-manifest.json',provenance['selection_manifest'])
    c.seal(f['campaign']/'provenance.json',provenance);manifest(f['campaign'])
    with pytest.raises(ValueError,match='omits frozen artifacts or report'):
        r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called();policy.assert_not_called()


def test_unlisted_final_selection_artifacts_and_campaign_omissions_fail(frozen,monkeypatch):
    f=frozen;_,native,_=setup_replay(f,monkeypatch)
    (f['selection']/'unlisted.txt').write_text('unlisted')
    with pytest.raises(ValueError,match='Complete final selection inventory'):
        r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called()
    (f['selection']/'unlisted.txt').unlink()
    entries=c.unseal(f['campaign']/'manifest.json');entries.pop('native/manifest.json')
    c.seal(f['campaign']/'manifest.json',entries)
    with pytest.raises(ValueError,match='complete artifact inventory'):
        r.replay(f['campaign'],f['raw'],prereg=f['prereg'],selection=f['selection'])

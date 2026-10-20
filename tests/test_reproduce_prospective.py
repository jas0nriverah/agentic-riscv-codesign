"""Evidence chronology and disjoint accounting; no processor jobs."""
from pathlib import Path

import pytest

from isaforge import codesign as c
from scripts import reproduce_prospective as replay


def prereg_fixture(tmp_path, monkeypatch, *, candidate_before=False, labels=0):
    prereg,target,selection=[tmp_path/name for name in ('prereg','target','selection')]
    for path in (prereg,target,selection): path.mkdir()
    initial=[dict(log='discovery/profile/simulation.json',log_sha256='',elapsed_seconds=2),
             dict(log='measurements/baseline/simulation.json',log_sha256='',elapsed_seconds=3)]
    if candidate_before:
        initial.append(dict(log='measurements/candidate_00/simulation.json',log_sha256='',elapsed_seconds=4))
    for row in initial:
        path=target/row['log']; path.parent.mkdir(parents=True,exist_ok=True)
        c.write(path,{'raw':'baseline'}); row['log_sha256']=c.sha(path)
    c.write(prereg/'baseline-command-receipts.json',initial)
    protocol=dict(target_labels_read=labels,contexts={'fixture:baseline':dict(
        baseline_provenance=dict(artifacts={'commands.json':c.sha(prereg/'baseline-command-receipts.json')}))})
    for name,value in [('protocol.json',protocol),('public.json',[dict(benchmark='fixture:baseline')]),
                       ('predictions.json',[dict(candidate_id='one',score=1.1)])]:
        c.seal(selection/name,value); c.seal(prereg/name,value)
    for before,after in [('target-plan.json','plan.json'),
                         ('target-discovery.json','discovery/discovery.json'),
                         ('target-baseline.json','measurements/baseline/measurement.json')]:
        c.seal(target/after,{'binding':before}); c.seal(prereg/before,{'binding':before})
    final=initial+[dict(log='measurements/candidate_01/simulation.json',elapsed_seconds=5)]
    c.seal(target/'commands.json',final)
    c.seal(prereg/'manifest.json',{p.relative_to(prereg).as_posix():c.sha(p)
                                  for p in prereg.rglob('*') if p.is_file()})
    monkeypatch.setattr(replay,'PREREG_MANIFEST_SHA256',c.sha(prereg/'manifest.json'))
    return prereg,target,selection


def test_preregistration_exact_prefix_and_frozen_predictions(tmp_path,monkeypatch):
    roots=prereg_fixture(tmp_path,monkeypatch)
    result=replay.check_preregistration(*roots)
    assert result['baseline_receipt_count']==2
    assert result['final_receipt_count']==3
    assert result['target_labels_at_freeze']==0


def test_changed_native_prefix_rejected(tmp_path,monkeypatch):
    prereg,target,selection=prereg_fixture(tmp_path,monkeypatch)
    final=c.unseal(target/'commands.json'); final[0]['elapsed_seconds']+=1
    c.seal(target/'commands.json',final)
    with pytest.raises(ValueError,match='prefix'):
        replay.check_preregistration(prereg,target,selection)


def test_candidate_attempt_before_freeze_rejected(tmp_path,monkeypatch):
    roots=prereg_fixture(tmp_path,monkeypatch,candidate_before=True)
    with pytest.raises(ValueError,match='preceded preregistration'):
        replay.check_preregistration(*roots)


def test_resealed_public_change_rejected(tmp_path,monkeypatch):
    prereg,target,selection=prereg_fixture(tmp_path,monkeypatch)
    c.seal(selection/'public.json',[dict(benchmark='fixture:other')])
    with pytest.raises(ValueError,match='Prelabel artifact changed'):
        replay.check_preregistration(prereg,target,selection)


@pytest.mark.parametrize('name',['../outside.json','/tmp/outside.json'])
def test_manifest_rejects_escape(tmp_path,name):
    root=tmp_path/'snapshot'; root.mkdir()
    c.seal(root/'manifest.json',{name:'0'*64})
    with pytest.raises(ValueError,match='Unsafe/missing'):
        replay.authenticate_files(root,'manifest.json')


def test_manifest_rejects_symlink_escape(tmp_path):
    root=tmp_path/'snapshot'; root.mkdir()
    outside=tmp_path/'outside.json'; c.write(outside,{})
    (root/'link.json').symlink_to(outside)
    c.seal(root/'manifest.json',{'link.json':c.sha(outside)})
    with pytest.raises(ValueError,match='Unsafe/missing'):
        replay.authenticate_files(root,'manifest.json')


def test_cost_buckets_are_disjoint_and_wall_scopes_separate(tmp_path,monkeypatch):
    calls=[]
    def project(root, *, incomplete):
        calls.append((root,incomplete))
        return dict(failures=[dict(reason='synthetic compile failure')],measurements=[])
    monkeypatch.setattr(replay.ledger,'project',project)
    target=tmp_path/'target'; failed=tmp_path/'failed'
    commands=[dict(log=log,elapsed_seconds=seconds) for log,seconds in [
        ('guard-controls/stack/build.log',1.0),('discovery/compile.log',2.0),
        ('measurements/baseline/compile.log',3.0),
        ('measurements/candidate_00/compile.log',4.0),
        ('measurements/candidate_01/compile.log',5.0)]]
    c.seal(target/'commands.json',commands)
    c.seal(failed/'commands.json',[dict(log='compile.log',elapsed_seconds=6.0)])
    for name,seconds in [('baseline',10.0),('candidate_00',11.0),('candidate_01',12.0)]:
        c.seal(target/'measurements'/name/'measurement.json',dict(name=name,elapsed_seconds=seconds))
    result=replay.measurement_costs(target,failed)
    assert calls==[(failed,True)]
    assert result['actual_native_command_count']==6
    assert result['actual_native_command_seconds']==21.0
    assert result['native_commands']['setup_and_guard_controls']==dict(count=2,seconds=3.0)
    assert result['native_commands']['baseline']==dict(count=1,seconds=3.0)
    assert result['native_commands']['candidates']==dict(count=2,seconds=9.0)
    assert result['baseline_evaluation_wall_seconds']==10.0
    assert result['candidate_evaluation_wall_seconds']==23.0


def test_target_label_consumption_before_freeze_rejected(tmp_path,monkeypatch):
    roots=prereg_fixture(tmp_path,monkeypatch,labels=1)
    with pytest.raises(ValueError,match='labels were used'):
        replay.check_preregistration(*roots)


@pytest.mark.parametrize('name',['../escape.py','/tmp/escape.py'])
def test_source_paths_cannot_escape_checkout(name):
    with pytest.raises(ValueError,match='escapes checkout'):
        replay.source_path(name)


def test_source_path_symlink_cannot_escape_checkout(tmp_path,monkeypatch):
    root=tmp_path/'checkout'; root.mkdir()
    outside=tmp_path/'outside.py'; outside.write_text('pass')
    (root/'source.py').symlink_to(outside)
    monkeypatch.setattr(replay,'ROOT',root)
    with pytest.raises(ValueError,match='escapes checkout'):
        replay.source_path('source.py')


@pytest.mark.parametrize('projection,message',[
    (dict(failures=[],measurements=[]),'Missing preserved'),
    (dict(failures=[{}],measurements=[{}]),'verified labels'),
])
def test_failed_attempt_costs_require_authentic_failure_without_labels(tmp_path,monkeypatch,projection,message):
    monkeypatch.setattr(replay.ledger,'project',lambda *a,**k:projection)
    with pytest.raises(ValueError,match=message):
        replay.measurement_costs(tmp_path/'target',tmp_path/'failed')

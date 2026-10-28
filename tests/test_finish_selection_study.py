"""Subprocess fakes verify ordering, readiness, no retries and exclusive locks."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from isaforge import codesign as c
from scripts import finish_selection_study as finish


def manifest(folder):
    c.seal(folder/'manifest.json',{p.relative_to(folder).as_posix():c.sha(p)
        for p in folder.rglob('*') if p.is_file() and p.name not in ('manifest.json','manifest.json.sha256')})


def closed_agent(study):
    folder=study/'agent'
    rationale={'source':'host-ledger'}
    c.seal(folder/'ledger.json',dict(status='finalized',decision_rationale=rationale))
    c.seal(folder/'report.json',dict(status='finalized',decision_rationale=rationale,
        ledger_sha256=c.sha(folder/'ledger.json')))
    manifest(folder)


def collected(study):
    c.seal(study/'native-audit.json',dict(attempt_collection_complete=True,charged_candidate_attempts=4,
        pool_names=['candidate_00','candidate_01','candidate_03','candidate_04']))
    c.seal(study/'collection-report.json',dict(collection_complete=True,charged_candidate_attempts=4))
    c.seal(study/'collection-operation.json',dict(collection_complete=True,target_attempts=4))


def finalized(results):
    for name in ('study-report.json','native-audit.json','outcomes.json'):
        c.seal(results/name,dict(sealed=True))
    manifest(results)


@pytest.fixture
def paths(tmp_path,monkeypatch):
    monkeypatch.setattr(finish,'ROOT',tmp_path)
    config=finish.STUDIES['countnegative']
    executor=tmp_path/config['executor'];executor.parent.mkdir(parents=True)
    executor.write_text('# frozen fake executor\n')
    study=tmp_path/config['study'];results=tmp_path/config['results']
    closed_agent(study)
    return study,results,tmp_path/'receipts'


def test_collect_exits_and_complete_audit_exists_before_evaluate_then_verify(paths,monkeypatch):
    study,results,receipts=paths
    calls=[]
    def run(argv,**kwargs):
        stage=argv[-1]
        if stage=='collect':
            assert calls==[]
            calls.append('collect entered')
            collected(study)
            calls.append('collect exiting')
        elif stage=='evaluate':
            assert calls[-1]=='collect exiting'
            finish.collection_ready(study)
            calls.append('evaluate exiting')
            finalized(results)
        else:
            assert calls[-1]=='evaluate exiting'
            finish.result_ready(results)
            calls.append('verify exiting')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(finish.subprocess,'run',run)
    record=finish.finish('countnegative',receipts)
    assert record['status']=='success'
    assert [r['stage'] for r in record['stages']]==['collect','evaluate','verify']
    assert all(r['returncode']==0 and r['elapsed_seconds']>=0 and r['log_sha256'] for r in record['stages'])
    assert c.unseal(receipts/'receipt.json')==record


def test_zero_collect_exit_without_sealed_audit_never_starts_evaluate(paths,monkeypatch):
    _,_,receipts=paths
    calls=[]
    monkeypatch.setattr(finish.subprocess,'run',lambda argv,**kwargs:
        (calls.append(argv[-1]) or SimpleNamespace(returncode=0)))
    with pytest.raises(FileNotFoundError):finish.finish('countnegative',receipts)
    assert calls==['collect']
    record=c.unseal(receipts/'receipt.json')
    assert record['status']=='failed' and record['stages'][0]['status']=='failed'
    assert record['stages'][0]['returncode']==0


def test_nonzero_collect_failure_has_no_later_stage_or_retry(paths,monkeypatch):
    _,_,receipts=paths
    calls=[]
    monkeypatch.setattr(finish.subprocess,'run',lambda argv,**kwargs:
        (calls.append(argv[-1]) or SimpleNamespace(returncode=7)))
    with pytest.raises(ValueError,match='no retry or later stage'):finish.finish('countnegative',receipts)
    assert calls==['collect']
    record=c.unseal(receipts/'receipt.json')
    assert record['automatic_retries']==0 and record['stages'][0]['returncode']==7


def test_completed_results_default_to_verify_only(paths,monkeypatch):
    _,results,receipts=paths;finalized(results)
    calls=[]
    monkeypatch.setattr(finish.subprocess,'run',lambda argv,**kwargs:
        (calls.append(argv[-1]) or SimpleNamespace(returncode=0)))
    assert finish.finish('countnegative',receipts)['planned_stages']==['verify']
    assert calls==['verify']


def test_completed_collection_is_not_rerun(paths,monkeypatch):
    study,results,receipts=paths;collected(study)
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv[-1])
        if argv[-1]=='evaluate':finalized(results)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(finish.subprocess,'run',run)
    finish.finish('countnegative',receipts)
    assert calls==['evaluate','verify']


def test_active_study_coordinator_blocks_second_launcher_before_dispatch(paths,monkeypatch):
    _,_,receipts=paths
    monkeypatch.setattr(finish.subprocess,'run',lambda *a,**k:pytest.fail('must not dispatch'))
    with finish.study_lock('countnegative'):
        with pytest.raises(ValueError,match='holds this study lock'):finish.finish('countnegative',receipts)
    assert not receipts.exists()


def test_invalid_study_is_rejected_without_creating_receipts(tmp_path,monkeypatch):
    monkeypatch.setattr(finish,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='countnegative or stringsearch'):finish.finish('unlisted',tmp_path/'receipts')
    assert list(tmp_path.iterdir())==[]


def test_incomplete_agent_or_partial_collection_never_launches_native(paths,monkeypatch):
    study,_,receipts=paths
    monkeypatch.setattr(finish.subprocess,'run',lambda *a,**k:pytest.fail('must not dispatch'))
    (study/'agent/ledger.json').write_text('changed ledger')
    with pytest.raises(ValueError,match='Sealed artifact differs'):finish.finish('countnegative',receipts)
    assert c.unseal(receipts/'receipt.json')['stages']==[]


def test_completed_native_collection_without_wrapper_audit_fails_closed(paths,monkeypatch):
    study,_,receipts=paths
    c.seal(study/'native/collection-report.json',dict(collection_complete=True))
    monkeypatch.setattr(finish.subprocess,'run',lambda *a,**k:pytest.fail('must not recollect'))
    with pytest.raises(FileNotFoundError):finish.finish('countnegative',receipts)
    assert c.unseal(receipts/'receipt.json')['stages']==[]


def test_failed_evaluation_stops_before_verify_and_never_recollects(paths,monkeypatch):
    study,_,receipts=paths;collected(study)
    calls=[]
    monkeypatch.setattr(finish.subprocess,'run',lambda argv,**kwargs:
        (calls.append(argv[-1]) or SimpleNamespace(returncode=9)))
    with pytest.raises(ValueError,match='no retry or later stage'):finish.finish('countnegative',receipts)
    assert calls==['evaluate']
    record=c.unseal(receipts/'receipt.json')
    assert record['planned_stages']==['evaluate','verify'] and len(record['stages'])==1
    assert record['stages'][0]['returncode']==9

"""Packaging-only synthetic fixtures; no native circuits, models or targets."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recover_v11d_feature_archive',ROOT/'scripts/recover_v11d_feature_archive.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture
def saved(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('No native job/model allowed'))
    source=tmp_path/m.RUNNER;source.parent.mkdir();source.write_text('SYNTHETIC frozen runner')
    tests=tmp_path/'tests/test_recover_v11d_feature_archive.py';tests.parent.mkdir();tests.write_text('SYNTHETIC tests')
    monkeypatch.setattr(m,'source_files',lambda:[source,tests]);monkeypatch.setattr(m,'RUNNER_SHA',m.sha(source))
    root=tmp_path/m.ORIGINAL;stage=root/'features/attempt-0000';stage.mkdir(parents=True)
    inputs=tmp_path/'results/inputs';inputs.mkdir();m.write(inputs/'preparation.json',{'SYNTHETIC':True})
    candidates=[{'formula':'SYNTHETIC-'+str(i),'candidate_id':'v11-original:'+str(i).zfill(64)} for i in range(327)]
    m.write(inputs/'candidates.json',candidates)
    source_bindings=[m.record(p) for p in [source,inputs/'preparation.json',inputs/'candidates.json']]
    # Original plan bindings are relative to original result root, unlike recovery records.
    import os
    plan={'schema':'isaforge-v11-transfer-feature-plan-v1','status':'prepared-no-jobs','candidate_count':327,
          'columns':['f'+str(i) for i in range(336)],'selected_columns':['f'+str(i) for i in range(217)],
          'input_root':os.path.relpath(inputs,root),'input_preparation_sha256':m.sha(inputs/'preparation.json'),
          'files':[{**r,'path':os.path.relpath(tmp_path/r['path'],root)} for r in source_bindings],
          'source_paths':[os.path.relpath(source,root)]}
    m.write(root/'feature-plan.json',plan)
    at='2026-10-16T05:00:00+00:00'
    approval={'status':'approved-v11-full-pool-features','runner_sha256':m.RUNNER_SHA,'feature_plan_sha256':m.sha(root/'feature-plan.json'),'reviewed_at_utc':at}
    m.write(root/'feature-approval.json',approval)
    claim={'runner_sha256':m.RUNNER_SHA,'feature_plan_sha256':m.sha(root/'feature-plan.json'),'approval_sha256':m.sha(root/'feature-approval.json'),'maximum_extractions':327,'claimed_at_utc':at}
    m.write(root/'feature-claim.json',claim)
    rows=[]
    def worker(folder,action,payload):
        folder.mkdir(parents=True,exist_ok=True);(folder/'worker.log').write_text('SYNTHETIC log')
        m.write(folder/'worker.json',{'schema':'isaforge-v11-prediction-worker-v1','action':action,'complete':True,'returncode':0,'primary_error':None,'cleanup_errors':[],'remaining_owned_children':[],
              'runner_sha256':m.RUNNER_SHA,'log_sha256':m.sha(folder/'worker.log'),'timeout_seconds':360 if action=='feature-worker' else 300,'elapsed_seconds':0.,'started_at_utc':at,'completed_at_utc':at,
              'command':[sys.executable,str(source),action,'--root',str(root),'--payload',json.dumps(payload)]})
    for i,c in enumerate(candidates):
        key=c['candidate_id'].split(':')[1];folder=stage/'workers'/key
        worker(folder,'feature-worker',{'formula':c['formula'],'cache':str(stage/'cache'/key),'result':str(folder/'result.json'),'claim_sha256':m.sha(root/'feature-claim.json')})
        row={**c,'cache_subdir':key,'values':[0.]*336};m.write(folder/'result.json',row);rows.append(row)
        for j in range(3 if i<152 else 2):
            path=stage/'cache'/key/str(j)/'extract.ys';path.parent.mkdir(parents=True);path.write_text('SYNTHETIC graph channel')
    m.write(stage/'features.json',{'columns':plan['columns'],'records':rows})
    worker(stage/'replay','replay-worker',{'claim_sha256':m.sha(root/'feature-claim.json')})
    m.write(stage/'replay/result.json',{'complete':True,'records':327,'full_columns':336,'native_channels':806,'features_sha256':m.sha(stage/'features.json')})
    with zipfile.ZipFile(stage/'raw-evidence.zip','w') as z:z.writestr('SYNTHETIC-partial-member','SYNTHETIC retained partial')
    done={'schema':'isaforge-v11-transfer-feature-completion-v1','complete':False,'failures':[{'stage':'archive-final','error':"AbortStage('Owned stage deadline')"}],
          'cleanup_failures':[],'candidate_count':327,'completed_extractions':327,'new_predictions':0,'new_labels':0,'new_fits':0,'completed_at_utc':at,
          'feature_plan_sha256':m.sha(root/'feature-plan.json'),'features_sha256':m.sha(stage/'features.json'),'claim_sha256':m.sha(root/'feature-claim.json'),
          'approval_sha256':m.sha(root/'feature-approval.json'),'runner_sha256':m.RUNNER_SHA}
    m.write(root/'features/completion.json',done);m.write(stage/'completion.json',done)
    m.write(root/'tools.json',{'SYNTHETIC':True});m.write(root/'runtime.json',{'files':[{'path':str(Path(sys.executable).resolve()),'sha256':m.sha(Path(sys.executable).resolve())}]})
    plan.update(tools_sha256=m.sha(root/'tools.json'),runtime_sha256=m.sha(root/'runtime.json'));(root/'feature-plan.json').write_text(json.dumps(plan))
    # Update only synthetic seals after creating the runtime files.
    approval['feature_plan_sha256']=m.sha(root/'feature-plan.json');(root/'feature-approval.json').write_text(json.dumps(approval))
    claim.update(feature_plan_sha256=m.sha(root/'feature-plan.json'),approval_sha256=m.sha(root/'feature-approval.json'));(root/'feature-claim.json').write_text(json.dumps(claim))
    for path in (stage/'workers').glob('*/worker.json'):
        d=m.read(path);payload=json.loads(d['command'][-1]);payload['claim_sha256']=m.sha(root/'feature-claim.json');d['command'][-1]=json.dumps(payload);path.write_text(json.dumps(d))
    d=m.read(stage/'replay/worker.json');d['command'][-1]=json.dumps({'claim_sha256':m.sha(root/'feature-claim.json')});(stage/'replay/worker.json').write_text(json.dumps(d))
    done.update(feature_plan_sha256=m.sha(root/'feature-plan.json'),approval_sha256=m.sha(root/'feature-approval.json'),claim_sha256=m.sha(root/'feature-claim.json'))
    for path in (root/'features/completion.json',stage/'completion.json'):path.write_text(json.dumps(done))
    failure=root/'archive-failure';failure.mkdir();(failure/'collector.log').write_text('SYNTHETIC packaging-only deadline')
    paths=[root/n for n in ('features/completion.json','features/attempt-0000/completion.json','features/attempt-0000/features.json','features/attempt-0000/replay/result.json','features/attempt-0000/replay/worker.json','features/attempt-0000/raw-evidence.zip','archive-failure/collector.log')]
    m.write(failure/'terminal-observation.json',{'schema':'isaforge-v11d-archive-terminal-observation-v1','complete':False,'process_exit_code':1,'observed_terminal_at_utc':at,'extractions_completed':327,'raw_channels_replayed':806,'new_predictions':0,'new_labels':0,'new_fits':0,'partial_archive_member_count':1,
        'files':{p.relative_to(tmp_path).as_posix():{'sha256':m.sha(p),'bytes':p.stat().st_size} for p in paths}})
    monkeypatch.setattr(m,'TERMINAL_SHA',m.sha(failure/'terminal-observation.json'))
    return root,stage,tmp_path/'results/recovery'


def release(root,monkeypatch):
    path=root/'packaging-approval.json'
    m.write(path,{'status':'approved-v11d-packaging-only','packaging_plan_sha256':m.sha(root/'packaging-plan.json'),'runner_sha256':m.sha(m.__file__),
        'tests_sha256':m.sha(m.source_files()[1]),'reviewed_at_utc':m.now(),'freeze_commit':'a'*40})
    def git(command,**kw):return (m.ROOT/command[2].split(':',1)[1]).read_bytes()
    monkeypatch.setattr(m.subprocess,'check_output',git)
    return path


def test_complete_packaging_preserves_original_bytes_and_full_member_layout(saved,monkeypatch):
    original,stage,root=saved;before=m.inventory(original);plan=m.prepare(original,root)
    real_inventory=m.inventory;full_walks=[]
    def counted(path, guard=None):full_walks.append(Path(path));return real_inventory(path, guard)
    monkeypatch.setattr(m,'inventory',counted)
    m.collect(root,release(root,monkeypatch))
    # Thousands of members/chunks cause exactly two full original inventories,
    # at admission and final verification, rather than one per member/chunk.
    assert full_walks==[original,original]
    done,features,bindings=m.validate_recovery(root)
    assert done['complete'] and done['original_completion_remains_false'] and len(features['records'])==327
    assert m.inventory(original)==before and m.read(original/'features/completion.json')['complete'] is False
    with zipfile.ZipFile(root/'raw-evidence.zip') as z:
        assert z.read('features.json')==(stage/'features.json').read_bytes()
        assert 'raw-evidence.zip' not in z.namelist() and len([n for n in z.namelist() if n.endswith('extract.ys')])==806
    assert all(n==0 for n in done['calls'].values())
    with pytest.raises(ValueError,match='Single packaging'):m.collect(root,root/'packaging-approval.json')


@pytest.mark.parametrize('poison',['success','featurefailure','partial','cleanup','replay','channel','feature','worker','log','payload'])
def test_prepare_rejects_incomplete_or_nonpackaging_failure(saved,poison):
    original,stage,root=saved;done=m.read(stage/'completion.json')
    if poison=='success':done['complete']=True;done['failures']=[]
    elif poison=='featurefailure':done['failures']=[{'stage':'extract','error':'bad feature'}]
    elif poison=='partial':done['completed_extractions']=326
    elif poison=='cleanup':done['cleanup_failures']=['unconfirmed']
    elif poison=='replay':d=m.read(stage/'replay/result.json');d['native_channels']=805;(stage/'replay/result.json').write_text(json.dumps(d))
    elif poison=='channel':next((stage/'cache').rglob('extract.ys')).unlink()
    elif poison=='feature':(stage/'features.json').write_text('{}')
    else:
        folder=next((stage/'workers').iterdir())
        if poison=='log':(folder/'worker.log').write_text('SYNTHETIC mutation')
        else:
            d=m.read(folder/'worker.json')
            if poison=='worker':d['complete']=False
            else:d['command'][-1]=json.dumps({'claim_sha256':'poison'})
            (folder/'worker.json').write_text(json.dumps(d))
    for path in [stage/'completion.json',original/'features/completion.json']:path.write_text(json.dumps(done))
    with pytest.raises((ValueError,KeyError)):m.prepare(original,root)
    assert not root.exists()


def test_original_added_file_and_filtered_recovery_member_rejected(saved):
    original,stage,root=saved;m.prepare(original,root)
    extra=stage/'unexpected.json';extra.write_text('{}')
    with pytest.raises(ValueError):m.validate(root)
    extra.unlink();plan=m.read(root/'packaging-plan.json');plan['members'].pop();(root/'packaging-plan.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError,match='member closure'):m.validate(root)


def test_missing_release_and_git_mismatch_fail_before_claim(saved,monkeypatch):
    original,stage,root=saved;m.prepare(original,root)
    with pytest.raises(FileNotFoundError):m.collect(root,root/'packaging-approval.json')
    path=release(root,monkeypatch);monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**k:b'POISON')
    with pytest.raises(ValueError,match='Git bytes'):m.collect(root,path)
    assert not (root/'packaging-claim.json').exists()


def test_deadline_failure_retains_recovery_partial_without_mutating_original(saved,monkeypatch):
    original,stage,root=saved;m.prepare(original,root);before=m.inventory(original);path=release(root,monkeypatch)
    times=iter([0.,0.,400.]);monkeypatch.setattr(m.time,'monotonic',lambda:next(times,400.))
    with pytest.raises(ValueError,match='Packaging-only failure retained'):m.collect(root,path)
    done=m.read(root/'completion.json');assert done['complete'] is False and 'deadline' in done['error']
    assert (root/'raw-evidence.zip').exists() and m.inventory(original)==before

@pytest.mark.parametrize('poison',['approval','claimtime','origincompletion','featurelineage','calls','filteredzip'])
def test_recovery_reauthenticated_lineage_or_member_poison_rejected(saved,monkeypatch,poison):
    original,stage,root=saved;m.prepare(original,root);m.collect(root,release(root,monkeypatch))
    path=root/'completion.json';done=m.read(path)
    if poison=='approval':
        p=root/'packaging-approval.json';d=m.read(p);d['status']='not-approved';p.write_text(json.dumps(d));done['approval_sha256']=m.sha(p)
    elif poison=='claimtime':
        p=root/'packaging-claim.json';d=m.read(p);d['claimed_at_utc']='2000-01-01T00:00:00+00:00';p.write_text(json.dumps(d));done['claim_sha256']=m.sha(p)
    elif poison=='origincompletion':done['original_completion_sha256']='f'*64
    elif poison=='featurelineage':done['original_feature_payload_sha256']='f'*64
    elif poison=='calls':done['calls']['new_fits']=False
    else:
        p=root/'raw-evidence.json';d=m.read(p);d['files'].pop();p.write_text(json.dumps(d));done['manifest_sha256']=m.sha(p)
    path.write_text(json.dumps(done))
    with pytest.raises(ValueError):m.validate_recovery(root)


@pytest.mark.parametrize('poison',['disk','wholebytes'])
def test_resource_abort_is_retained_without_original_mutation(saved,monkeypatch,poison):
    from types import SimpleNamespace
    original,stage,root=saved;m.prepare(original,root);before=m.inventory(original);path=release(root,monkeypatch)
    if poison=='disk':monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=0))
    else:monkeypatch.setitem(m.POLICY,'maximum_whole_bytes',1)
    # The changed-policy poison fails validation before a claim; a disk floor
    # violation is an execution failure with a retained completion.
    if poison=='wholebytes':
        with pytest.raises(ValueError):m.collect(root,path)
        assert not (root/'packaging-claim.json').exists()
    else:
        with pytest.raises(ValueError,match='Packaging-only failure retained'):m.collect(root,path)
        assert m.read(root/'completion.json')['complete'] is False
    assert m.inventory(original)==before


def test_terminal_observation_and_python_alias_required(saved):
    original,stage,root=saved
    receipt=original/'archive-failure/terminal-observation.json';receipt.write_text('{}')
    with pytest.raises(ValueError,match='terminal observation'):m.prepare(original,root)
    assert not root.exists()


def test_interpreter_is_hashed_once_per_saved_receipt_validation(saved,monkeypatch):
    original,stage,root=saved
    digest=m.sha; calls=[]
    pinned=Path(sys.executable).resolve()
    def counted(path, guard=None):
        if Path(path).resolve()==pinned: calls.append(Path(path))
        return digest(path, guard)
    monkeypatch.setattr(m,'sha',counted)
    m.original_inputs(original)
    assert len(calls)==1


def test_final_integrity_hashes_obey_collection_guard(saved,monkeypatch):
    original,stage,root=saved;m.prepare(original,root);path=release(root,monkeypatch)
    real_validate=m.validate; final=[]
    def checked(root, guard=None):
        if guard is not None:
            final.append(True)
            def expired(): raise ValueError('SYNTHETIC final-integrity deadline')
            return real_validate(root, expired)
        return real_validate(root)
    monkeypatch.setattr(m,'validate',checked)
    with pytest.raises(ValueError,match='Packaging-only failure retained'):m.collect(root,path)
    assert final==[True]
    done=m.read(root/'completion.json')
    assert done['complete'] is False and 'final-integrity deadline' in done['error']
    assert (root/'raw-evidence.zip').exists() and not (root/'raw-evidence.json').exists()
    assert m.read(original/'features/completion.json')['complete'] is False


def test_source_mutation_during_packaging_retains_failed_receipt(saved,monkeypatch):
    original,stage,root=saved;m.prepare(original,root);path=release(root,monkeypatch)
    original_open=zipfile.ZipFile.open; changed=[]
    target=next((stage/'cache').rglob('extract.ys'))
    def mutate(archive,name,mode='r',*args,**kwargs):
        if mode=='w' and not changed:
            body=target.read_bytes();target.write_bytes(b'X'+body[1:]);changed.append(True)
        return original_open(archive,name,mode,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,'open',mutate)
    with pytest.raises(ValueError,match='Packaging-only failure retained'):m.collect(root,path)
    done=m.read(root/'completion.json')
    assert done['complete'] is False and 'Source changed' in done['error']
    assert m.read(original/'features/completion.json')['complete'] is False

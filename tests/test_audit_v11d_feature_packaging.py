"""Independent archive admission checks with synthetic327×336 data only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('audit_v11d_feature_packaging', ROOT/'scripts/audit_v11d_feature_packaging.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=True)+'\n')


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m.shared.subprocess, 'Popen', lambda *a,**k:pytest.fail('No process permitted'))
    original = tmp_path/'results/original'; stage = original/'features/attempt-0000'
    root = tmp_path/'results/package'; root.mkdir(parents=True)
    inputs = tmp_path/'results/inputs'; inputs.mkdir()
    candidates = [{'candidate_id':f'original:{i}', 'formula':f'SYNTHETIC{i}'} for i in range(327)]
    write(inputs/'candidates.json', candidates)
    columns = [f'f{i}' for i in range(336)]
    features = {'columns':columns, 'records':[{**c,'values':[0]*336} for c in candidates]}
    write(stage/'features.json', features)
    write(original/'feature-plan.json', {'input_root':'../inputs', 'columns':columns,
          'selected_indices':list(range(217)), 'selected_columns':columns[:217]})
    write(original/'features/completion.json', {'complete':False, 'failures':[
        {'stage':'archive-final','error':"AbortStage('Owned stage deadline')"}]})
    write(stage/'replay/result.json', {'complete':True,'records':327,'full_columns':336,
          'native_channels':806,'features_sha256':m.sha(stage/'features.json')})
    (stage/'replay/worker.log').write_bytes(b'')
    write(stage/'replay/worker.json', {'complete':True,'returncode':0,'primary_error':None,
          'cleanup_errors':[],'remaining_owned_children':[],'log_sha256':m.sha(stage/'replay/worker.log')})
    runner = tmp_path/m.shared.RUNNER; runner.parent.mkdir(parents=True); runner.write_text('SYNTHETIC runner')
    tests = tmp_path/'tests/test_audit_v11d_feature_packaging.py';tests.parent.mkdir();tests.write_text('SYNTHETIC tests')
    payload = {name:(stage/name).read_bytes() for name in ['features.json','replay/result.json','replay/worker.json','replay/worker.log']}
    payload.update({f'cache/{i}/extract.ys':b'SYNTHETIC' for i in range(806)})
    plan = {'original_root':'results/original','created_at_utc':'2026-10-16T05:00:00+00:00',
            'original_completion_sha256':m.sha(original/'features/completion.json'),
            'original_feature_payload_sha256':m.sha(stage/'features.json'),
            'members':[{'member':name,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)} for name,body in payload.items()]}
    write(root/'packaging-plan.json',plan)
    approval = {'status':'approved-v11d-packaging-only','packaging_plan_sha256':m.sha(root/'packaging-plan.json'),
                'runner_sha256':m.sha(m.shared.__file__), 'reviewed_at_utc':'2026-10-16T05:01:00+00:00'}
    write(root/'packaging-approval.json',approval)
    claim = {'packaging_plan_sha256':m.sha(root/'packaging-plan.json'),'approval_sha256':m.sha(root/'packaging-approval.json'),
             'runner_sha256':m.sha(m.shared.__file__),'claimed_at_utc':'2026-10-16T05:02:00+00:00'}
    write(root/'packaging-claim.json',claim)
    done = {'complete':True,'runner_sha256':m.sha(m.shared.__file__),
            'original_completion_sha256':plan['original_completion_sha256'],
            'original_feature_payload_sha256':plan['original_feature_payload_sha256'],
            'completed_at_utc':'2026-10-16T05:03:00+00:00','elapsed_seconds':1.,
            'calls':{name:0 for name in ('new_native_jobs','new_feature_extractions','new_replays','new_predictions','new_labels','new_fits')}}
    # Shared old-tree/worker authentication is tested by the owner's separate
    # suite; isolate this auditor's independent semantic/ZIP checks here.
    monkeypatch.setattr(m.shared,'validate_recovery',lambda r:(m.read(r/'completion.json'), m.read(stage/'features.json'), {}))
    def repack(extra=None):
        contents = dict(payload)
        for path in [root/'packaging-plan.json',root/'packaging-approval.json',root/'packaging-claim.json']:
            contents['provenance/recovery/'+path.name] = path.read_bytes()
        with zipfile.ZipFile(root/'raw-evidence.zip','w') as archive:
            for name,body in contents.items():archive.writestr(name,body)
            if extra:archive.writestr(*extra)
        write(root/'raw-evidence.json', {'files':[{'path':n,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)} for n,b in contents.items()]})
        current=copy.deepcopy(done);current['archived_members']=len(contents)
        write(root/'completion.json',current)
    repack()
    return root,original,stage,payload,done,repack


def test_complete_independent_inventory_counts_and_limits(package):
    root,original,stage,payload,done,repack = package
    before = {p:p.read_bytes() for p in original.rglob('*') if p.is_file()}
    report=m.run(root)
    assert report['status']=='pass' and report['complete'] is True
    assert (report['records'],report['full_columns'],report['selected_columns'],report['native_channels'])==(327,336,217,806)
    assert report['archive_members']==813 and report['original_completion_remains_false'] is True
    assert 'shares recovery helper' in report['scope'] and 'does not recompute' in report['scope']
    assert all(p.read_bytes()==body for p,body in before.items())


@pytest.mark.parametrize('poison', ['lineage','claim','approval','chronology','job','booljob','wrongjob','deadline','booltime','recordorder','width','boolvalue','nan','negative','indices','replay','emptylog'])
def test_semantic_poison_rejected_even_with_shared_authentication_stub(package,poison):
    root,original,stage,payload,done,repack=package
    if poison=='lineage':done['original_completion_sha256']='0'*64
    elif poison=='claim':
        p=root/'packaging-claim.json';d=m.read(p);d['approval_sha256']='0'*64;write(p,d)
    elif poison=='approval':
        p=root/'packaging-approval.json';d=m.read(p);d['status']='not-approved';write(p,d)
    elif poison=='chronology':done['completed_at_utc']='2026-10-16T04:59:00+00:00'
    elif poison in ('job','booljob'):done['calls']['new_labels']=1 if poison=='job' else False
    elif poison=='wrongjob':done['calls']['unknown']=done['calls'].pop('new_labels')
    elif poison=='deadline':done['elapsed_seconds']=301.
    elif poison=='booltime':done['elapsed_seconds']=False
    elif poison in ('recordorder','width','boolvalue','nan','negative'):
        p=stage/'features.json';d=m.read(p)
        if poison=='recordorder':d['records'].reverse()
        elif poison=='width':d['records'][0]['values'].pop()
        else:d['records'][0]['values'][0]={'boolvalue':True,'nan':float('nan'),'negative':-1}[poison]
        write(p,d)
    elif poison=='indices':
        p=original/'feature-plan.json';d=m.read(p);d['selected_indices'][0]=True;write(p,d)
    elif poison=='replay':
        p=stage/'replay/result.json';d=m.read(p);d['native_channels']=805;write(p,d)
    elif poison=='emptylog':(stage/'replay/worker.log').write_text('unauthenticated log')
    repack()
    with pytest.raises((ValueError,KeyError)):m.run(root)


@pytest.mark.parametrize('poison',['changedmember','extramember','duplicatemember','missingmember','manifest','channel'])
def test_zip_closure_poison_rejected(package,poison):
    root,original,stage,payload,done,repack=package
    if poison=='changedmember':payload['cache/0/extract.ys']=b'corrupt'
    elif poison=='missingmember':del payload['cache/0/extract.ys']
    elif poison=='channel':
        plan=m.read(root/'packaging-plan.json');plan['members'][-1]['member']='cache/805/other.txt';write(root/'packaging-plan.json',plan)
    repack(('foreign.txt',b'foreign') if poison=='extramember' else ('cache/0/extract.ys',b'duplicate') if poison=='duplicatemember' else None)
    if poison=='manifest':
        p=root/'raw-evidence.json';d=m.read(p);d['files'][0]['bytes']+=1;write(p,d)
    with pytest.raises(ValueError):m.run(root)

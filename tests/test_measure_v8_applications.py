"""Approval/archive/ownership gates only. No FPGA or formula measurement runs."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('measure_v8_applications',ROOT/'scripts/measure_v8_applications.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_measurement_rejects_without_approval_before_any_native_tool(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'validate_approval',lambda *a:(_ for _ in ()).throw(ValueError('No parent approval')))
    monkeypatch.setattr(m.shutil,'which',lambda *_:pytest.fail('No native tool before approval'))
    with pytest.raises(ValueError,match='parent approval'):m.collect(tmp_path,tmp_path/'label-approval.json')
    assert not (tmp_path/'label-release.json').exists()


def test_completed_or_existing_attempt_is_immutable(tmp_path,monkeypatch):
    root=tmp_path/'result';(root/'measurements').mkdir(parents=True);m.write(root/'measurements/completion.json',{'complete':True})
    monkeypatch.setattr(m,'validate_approval',lambda *_:pytest.fail('Completed-stage gate must precede all reads'))
    with pytest.raises(ValueError,match='immutable'):m.collect(root,root/'label-approval.json')


@pytest.mark.parametrize('workers,attempt',[(1,'attempt-0000'),(True,'attempt-0000'),(2,'../old'),(2,'attempt-0')])
def test_fixed_workers_and_owned_attempt_required(tmp_path,workers,attempt):
    with pytest.raises(ValueError):m.collect(tmp_path,tmp_path/'label-approval.json',workers=workers,attempt=attempt)


@pytest.fixture
def approval(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'result';root.mkdir()
    m.write(root/'point-freeze.json',{'frozen_at_utc':'2026-10-15T00:00:00+00:00'});m.write(root/'input-seal.json',{'status':'fixture'})
    evidence=tmp_path/'source.py';evidence.write_bytes(b'bound-source')
    point={'frozen_at_utc':'2026-10-15T00:00:00+00:00'}
    monkeypatch.setattr(m,'freeze_records',lambda *_:(point,{},[],{evidence:m.sha(evidence)}))
    review={'schema':'isaforge-v8-application-label-approval-v1','approved_for_label_release':True,
        'point_freeze_sha256':m.sha(root/'point-freeze.json'),'input_seal_sha256':m.sha(root/'input-seal.json'),
        'freeze_commit':'a'*40,'reviewed_at_utc':'2026-10-15T00:01:00+00:00'}
    path=root/'label-approval.json';m.write(path,review)
    return root,path,review,evidence


def test_approval_requires_exact_committed_bytes(approval,monkeypatch):
    root,path,_,evidence=approval;seen=[]
    def git(command,**kwargs):seen.append(command);return SimpleNamespace(returncode=0,stdout=evidence.read_bytes())
    monkeypatch.setattr(m.subprocess,'run',git);assert m.validate_approval(root,path)[3]['approved_for_label_release'] is True
    assert seen==[['git','show','a'*40+':source.py']]
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'changed'))
    with pytest.raises(ValueError,match='committed bytes'):m.validate_approval(root,path)


@pytest.mark.parametrize('field,value',[('approved_for_label_release',False),('freeze_commit','HEAD'),('point_freeze_sha256','wrong'),('input_seal_sha256','wrong'),('reviewed_at_utc','2026-10-14T23:59:00+00:00')])
def test_unapproved_or_stale_freeze_never_authorizes_release(approval,monkeypatch,field,value):
    root,path,review,_=approval;review[field]=value;m.write(path,review)
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:pytest.fail('Bad review must fail before Git or native workers'))
    with pytest.raises(ValueError):m.validate_approval(root,path)
    assert not (root/'label-release.json').exists()


def archive_fixture(tmp_path,monkeypatch,name='source.txt'):
    monkeypatch.setattr(m,'ROOT',tmp_path);archive=tmp_path/'input.zip';data=b'bound-native-input'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,data)
    manifest=tmp_path/'members.json';m.write(manifest,{'archive':{'path':archive.name,'sha256':m.sha(archive)},
        'files':[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]})
    return manifest,archive


def test_archive_member_hashes_rechecked_before_label_release(tmp_path,monkeypatch):
    manifest,archive=archive_fixture(tmp_path,monkeypatch);assert m.verify_archive_manifest(manifest)==archive
    record=m.read(manifest);record['files'][0]['sha256']='0'*64;m.write(manifest,record)
    with pytest.raises(ValueError,match='member bytes'):m.verify_archive_manifest(manifest)


def test_archive_traversal_and_duplicate_members_rejected(tmp_path,monkeypatch):
    manifest,_=archive_fixture(tmp_path,monkeypatch,'../escape')
    with pytest.raises(ValueError,match='Unsafe'):m.verify_archive_manifest(manifest)


@pytest.mark.parametrize('name',['../escape','/tmp/escape','generated/v8-measurements/../../escape','generated/v6-measurements/a','generated/v8-measurements/a\\b'])
def test_native_restore_paths_confined_to_owned_v8_tree(tmp_path,name):
    with pytest.raises(ValueError):m.destination(name,tmp_path)


@pytest.mark.parametrize('linked_prefix',['generated','generated/v8-measurements'])
def test_native_restore_rejects_owned_prefix_symlink_outside_repository(tmp_path,linked_prefix):
    repository=tmp_path/'repository';repository.mkdir()
    outside=tmp_path/'outside';outside.mkdir()
    link=repository/linked_prefix;link.parent.mkdir(parents=True,exist_ok=True)
    link.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='escapes owned'):
        m.destination('generated/v8-measurements/attempt-0000/member.json',repository)
    assert list(outside.iterdir())==[]

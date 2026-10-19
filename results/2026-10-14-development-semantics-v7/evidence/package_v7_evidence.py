#!/usr/bin/env python3
"""Exact-byte V7 evidence archive, safe restoration and independent saved-score replay.

Uses only the standard library for packaging/verification/restoration. Never fits
models or modifies sealed sources, manifests, reviews, formulas or predictions.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import tarfile

SCHEMA='isaforge-v7-evidence-package-v1'
SEEDS=(2026101421,2026101422,2026101423)
VIEWS=('base','bit','affine','both','legacy_original','legacy_rewritten')


def read(path):return json.loads(Path(path).read_text())
def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def safe_name(name):
    if not isinstance(name,str) or '\\' in name:raise ValueError('Invalid archive member name')
    path=PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('..','.') for p in path.parts) or str(path)!=name:
        raise ValueError('Unsafe archive member name')
    return path


def portable_dependencies(plan,repo_root):
    """Original absolute names remain unchanged; map only hash-bound repo members."""
    repo_root=Path(repo_root).resolve();result=[]
    for original,value in plan['input_sha256'].items():
        source=Path(original).resolve()
        try:relative=source.relative_to(repo_root).as_posix()
        except ValueError:raise ValueError('Plan dependency lies outside the packaging checkout: '+original)
        safe_name(relative)
        if sha(source)!=value:raise ValueError('Sealed dependency changed: '+original)
        result.append({'original_path':original,'repository_path':relative,'sha256':value})
    names=[r['repository_path'] for r in result]
    if len(names)!=len(set(names)):raise ValueError('Ambiguous repository dependency aliases')
    return sorted(result,key=lambda r:r['repository_path'])


def package(prepared,review,audits,repo_root,destination,tests,document,records_extra=()):
    prepared,review,repo_root,destination=map(lambda p:Path(p).resolve(),(prepared,review,repo_root,destination))
    if destination.exists():raise ValueError('Existing package destination is immutable')
    seal_path=prepared/'pre-score-freeze.json';seal=read(seal_path);plan=read(prepared/'plan.json');approval=read(review)
    if approval.get('approved') is not True or approval.get('pre_score_freeze_sha256')!=sha(seal_path):raise ValueError('Reviewed pre-score seal required')
    for name,value in seal['files_sha256'].items():
        safe_name(name)
        if sha(prepared/name)!=value:raise ValueError('Sealed preparation changed: '+name)
    summary_path=prepared/'fit/summary.json';summary=read(summary_path)
    if summary.get('pre_score_freeze_sha256')!=sha(seal_path) or summary.get('fits_completed') not in range(1,91):raise ValueError('Completed matching fit summary required')
    for view in VIEWS:
        for seed in SEEDS:
            for folder in ('predictions','metrics'):
                if not (prepared/'fit'/folder/f'{view}-seed-{seed}.json').is_file():raise ValueError('Incomplete fit evidence')
    members={}
    def add_tree(prefix,root):
        for path in sorted(root.rglob('*')):
            if path.is_symlink():raise ValueError('Symlink evidence is forbidden')
            if path.is_file():members[prefix+'/'+path.relative_to(root).as_posix()]=path
    add_tree('prepared',prepared);members['reviews/parent-fit-review.json']=review
    for name,path in audits:
        safe_name(name)
        if '/' in name:raise ValueError('Audit namespace must be a single name')
        add_tree('audits/'+name,Path(path).resolve())
    members['reproduction/package_v7_evidence.py']=Path(__file__).resolve()
    members['reproduction/REPRODUCE.md']=Path(document).resolve()
    members['reproduction/requirements-research.txt']=repo_root/'requirements-research.txt'
    add_tree('reproduction/tests',Path(tests).resolve())
    for name,path in records_extra:
        safe_name(name)
        if '/' in name:raise ValueError('Record name must be a single name')
        members['records/'+name]=Path(path).resolve()
    if 'audits/preparation/replay_metrics.py' not in members or 'audits/preparation/preparation-audit.json' not in members:
        raise ValueError('Portable independent score and preparation audit sources required')
    prep_audit=read(members['audits/preparation/preparation-audit.json'])
    if prep_audit.get('status')!='pass' or prep_audit.get('prepared_freeze_sha256')!=sha(seal_path):raise ValueError('Matching independent preparation audit required')
    metric_paths=[path for name,path in members.items() if name.endswith('/metrics-audit.json')]
    if len(metric_paths)!=1:raise ValueError('Exactly one completed independent metrics audit required')
    metric_audit=read(metric_paths[0])
    if (metric_audit.get('status')!='pass' or metric_audit.get('prepared_freeze_sha256')!=sha(seal_path)
        or metric_audit.get('summary_sha256')!=sha(summary_path) or metric_audit.get('fits_completed')!=summary['fits_completed']
        or metric_audit.get('prediction_rows_recomputed')!=6*3*1665):
        raise ValueError('Independent completed metrics audit differs')
    dependencies=portable_dependencies(plan,repo_root)
    for relative in ('requirements-research.txt','pyproject.toml'):
        if relative not in {r['repository_path'] for r in dependencies}:
            dependencies.append({'original_path':str(repo_root/relative),'repository_path':relative,'sha256':sha(repo_root/relative),'role':'Package environment documentation; additional to original sealed plan'})
    dependencies.sort(key=lambda r:r['repository_path'])
    records=[{'path':name,'sha256':sha(path),'bytes':path.stat().st_size} for name,path in sorted(members.items())]
    destination.mkdir(parents=True)
    archive=destination/'evidence.tar.gz'
    with archive.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as zipped,tarfile.open(fileobj=zipped,mode='w|') as tar:
        for record in records:
            data=members[record['path']].read_bytes()
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Evidence changed during archive')
            info=tarfile.TarInfo(record['path']);info.size=len(data);info.mode=0o644;info.mtime=0;info.uid=info.gid=0
            tar.addfile(info,io.BytesIO(data))
    manifest={'schema':SCHEMA,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Exact completed fitting-only evidence; archived predictions are not an independent test',
        'archive':{'path':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size},
        'pre_score_freeze_sha256':sha(seal_path),'parent_review_sha256':sha(review),'files':records,
        'repository_dependencies':dependencies,'uncompressed_bytes':sum(r['bytes'] for r in records),
        'file_count':len(records),'fit_count':summary['fits_completed'],
        'replay':'Verify/restore and independent saved-prediction metric reconstruction only; never refits',
        'retraining_limit':'Original runner intentionally binds absolute audited input/review paths. Fresh retraining requires a new local prepare plus separately reviewed seal; this package does not patch validation or reuse approval on another seal.'}
    write(destination/'evidence-manifest.json',manifest)
    shutil.copyfile(__file__,destination/'package_v7_evidence.py')
    shutil.copyfile(document,destination/'REPRODUCE.md')
    shutil.copytree(tests,destination/'tests')
    verify(destination/'evidence-manifest.json',repo_root)
    return manifest


def verify(manifest_path,repo_root):
    manifest_path=Path(manifest_path).resolve();manifest=read(manifest_path);repo_root=Path(repo_root).resolve()
    if manifest.get('schema')!=SCHEMA:raise ValueError('Unsupported evidence package')
    archive=manifest_path.parent/str(safe_name(manifest['archive']['path']))
    if archive.stat().st_size!=manifest['archive']['bytes'] or sha(archive)!=manifest['archive']['sha256']:raise ValueError('Archive digest differs')
    expected={r['path']:r for r in manifest['files']}
    if len(expected)!=len(manifest['files']):raise ValueError('Duplicate manifest member')
    if sum(r['bytes'] for r in expected.values())!=manifest['uncompressed_bytes'] or len(expected)!=manifest['file_count']:raise ValueError('Manifest size/count differs')
    for name,record in expected.items():
        safe_name(name)
        if record['bytes']<0 or record['bytes']>512*1024*1024:raise ValueError('Invalid member size')
    seen=set()
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            safe_name(member.name)
            if member.name in seen or member.name not in expected or not member.isfile():raise ValueError('Unexpected or unsafe archive member')
            seen.add(member.name);record=expected[member.name]
            if member.size!=record['bytes']:raise ValueError('Archived size differs')
            result=hashlib.sha256();stream=tar.extractfile(member)
            for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
            if result.hexdigest()!=record['sha256']:raise ValueError('Archived file digest differs')
    if seen!=set(expected):raise ValueError('Archive does not cover every manifest member')
    names=set()
    for record in manifest['repository_dependencies']:
        relative=str(safe_name(record['repository_path']))
        if relative in names:raise ValueError('Duplicate repository dependency')
        names.add(relative);path=(repo_root/relative).resolve()
        if repo_root not in path.parents or sha(path)!=record['sha256']:raise ValueError('Clean-clone dependency differs: '+relative)
    return manifest


def restore(manifest_path,repo_root,destination):
    manifest=verify(manifest_path,repo_root);destination=Path(destination).resolve();repo_root=Path(repo_root).resolve()
    if destination.exists() or destination==repo_root or repo_root in destination.parents:raise ValueError('Restore into a fresh directory outside the checkout')
    destination.mkdir(parents=True)
    archive=Path(manifest_path).resolve().parent/manifest['archive']['path']
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            # Verification above forbids links/special files and traversal.
            target=destination/str(safe_name(member.name));target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:shutil.copyfileobj(tar.extractfile(member),stream)
    shutil.copyfile(manifest_path,destination/'RESTORE-MANIFEST.json')
    check_restored(destination,repo_root)
    return destination


def check_restored(restored,repo_root):
    restored=Path(restored).resolve();repo_root=Path(repo_root).resolve();manifest=read(restored/'RESTORE-MANIFEST.json')
    if manifest.get('schema')!=SCHEMA:raise ValueError('Invalid restored evidence manifest')
    for record in manifest['files']:
        path=restored/str(safe_name(record['path']))
        if path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:raise ValueError('Restored file differs')
    for record in manifest['repository_dependencies']:
        path=repo_root/str(safe_name(record['repository_path']))
        if sha(path)!=record['sha256']:raise ValueError('Replay checkout dependency differs')
    if sha(restored/'prepared/pre-score-freeze.json')!=manifest['pre_score_freeze_sha256'] or sha(restored/'reviews/parent-fit-review.json')!=manifest['parent_review_sha256']:
        raise ValueError('Original seal/review bytes changed')
    return manifest


def score(restored,repo_root,output,python=None):
    restored,repo_root,output=map(lambda p:Path(p).resolve(),(restored,repo_root,output));check_restored(restored,repo_root)
    if output.exists():raise ValueError('Score replay output must be a fresh path')
    interpreter=Path(python if python is not None else sys.executable).absolute()
    if not interpreter.is_file():raise ValueError('Pass --python with the pinned study environment interpreter')
    script=restored/'audits/preparation/replay_metrics.py'
    command=[str(interpreter),str(script),'--prepared',str(restored/'prepared'),'--review',str(restored/'reviews/parent-fit-review.json'),
             '--repo-root',str(repo_root),'--preparation-audit',str(restored/'audits/preparation/preparation-audit.json'),'--output',str(output)]
    subprocess.run(command,check=True,cwd=repo_root)
    check_restored(restored,repo_root)
    return {'status':'completed','scope':'Independent saved-prediction metric replay; zero new fits','command':command}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('package');p.add_argument('--prepared',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    p.add_argument('--audit',action='append',default=[],help='namespace=directory (include preparation=...)');p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--tests',type=Path,required=True);p.add_argument('--document',type=Path,required=True);p.add_argument('--record',action='append',default=[],help='name=file')
    p=sub.add_parser('verify');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--repo-root',type=Path,required=True)
    p=sub.add_parser('restore');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--restored',type=Path,required=True);p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--python',type=Path)
    a=parser.parse_args()
    if a.command=='package':
        audits=[v.split('=',1) for v in a.audit]
        if any(len(v)!=2 for v in audits) or len({v[0] for v in audits})!=len(audits):raise ValueError('Unique audit namespaces required')
        records=[v.split('=',1) for v in a.record]
        if any(len(v)!=2 for v in records) or len({v[0] for v in records})!=len(records):raise ValueError('Unique record names required')
        result=package(a.prepared,a.review,audits,a.repo_root,a.destination,a.tests,a.document,records)
    elif a.command=='verify':result=verify(a.manifest,a.repo_root)
    elif a.command=='restore':result={'restored':str(restore(a.manifest,a.repo_root,a.destination))}
    else:result=score(a.restored,a.repo_root,a.output,a.python)
    print(json.dumps({k:result[k] for k in ('schema','file_count','fit_count','archive','status','scope','restored') if k in result},indent=2))

if __name__=='__main__':main()

"""Package or authenticate/replay the measured CRC32 co-design checkpoint.

Replay extracts only manifest-listed regular files and runs no native tools.
Full recollection uses isaforge.codesign prepare/pilot/run instead.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from isaforge.codesign_audit import audit


def pack_archive(source,destination):
    source=Path(source).resolve()
    files=[p for p in sorted(source.rglob('*')) if p.is_file() and 'obj_dir' not in p.parts and p.name!='.native.lock']
    entries=[]
    with tarfile.open(destination,'w:gz') as archive:
        for path in files:
            c.require(not path.is_symlink(),'Do not archive symlinks')
            relative=path.relative_to(source).as_posix()
            archive.add(path,arcname=relative,recursive=False)
            entries.append({'path':relative,'bytes':path.stat().st_size,'sha256':c.sha(path)})
    return {'archive':Path(destination).name,'sha256':c.sha(destination),'bytes':Path(destination).stat().st_size,'files':entries}


def restore_archive(snapshot,record,output):
    source=Path(snapshot)/record['archive'];output=Path(output)
    c.require(c.sha(source)==record['sha256'],'Archive checksum mismatch')
    entries={e['path']:e for e in record['files']}
    c.require(len(entries)==len(record['files']) and len(entries)<=5000,'Duplicate/oversized manifest')
    c.require(sum(e['bytes'] for e in entries.values())<=256*1024**2,'Oversized archive')
    if not output.exists():
        with tarfile.open(source,'r:gz') as archive:
            members=archive.getmembers()
            c.require(len(members)==len(entries) and {m.name for m in members}==set(entries),'Archive membership mismatch')
            for member in members:
                path=PurePosixPath(member.name)
                c.require(member.isfile() and not path.is_absolute() and '..' not in path.parts,'Unsafe archive member')
                c.require(member.size==entries[member.name]['bytes'] and member.size<=64*1024**2,'Member size mismatch')
            output.mkdir(parents=True)
            for member in members:
                content=archive.extractfile(member).read()
                c.require(hashlib.sha256(content).hexdigest()==entries[member.name]['sha256'],'Member checksum mismatch')
                target=output/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:stream.write(content)
    c.require({p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}==set(entries),'Restored membership changed')
    for name,entry in entries.items():c.require(c.sha(output/name)==entry['sha256'],'Restored evidence changed: '+name)


def pack(root,probe,failed,output):
    root,output=Path(root),Path(output)
    c.require(not output.exists(),'Create a new checkpoint; never overwrite frozen results')
    verified=audit(root,replay=True)
    output.mkdir(parents=True)
    archives={'experiment':pack_archive(root,output/'raw.tar.gz')}
    if probe:archives['next_workload_probe']=pack_archive(probe,output/'baseline-probe.tar.gz')
    if failed:archives['failed_initial_control']=pack_archive(failed,output/'failed-initial-control.tar.gz')
    c.seal(output/'archive-manifest.json',archives)
    for name in ('plan.json','observations.json','selection-report.json','live-selection.json','live-selection.json.sha256',
                 'live-events.json','speedup-corpus.json','speedup-corpus.json.sha256','setup-cost.json','pilot.json'):
        shutil.copyfile(root/name,output/name)
    if probe:shutil.copyfile(Path(probe)/'probe-report.json',output/'baseline-probe-report.json')
    c.write(output/'independent-audit.json',verified)
    environment={'python':platform.python_version(),'platform':platform.platform(),
                 'packages':{name:importlib.metadata.version(name) for name in
                             ('numpy','scipy','scikit-learn','xgboost','joblib','pytest','matplotlib','z3-solver')}}
    c.write(output/'environment.json',environment)
    plan=c.read(root/'plan.json')
    sources={**plan['source_bindings'],**{str(p.relative_to(ROOT)):c.sha(p) for p in
             (ROOT/'isaforge/codesign_audit.py',ROOT/'isaforge/speedup_corpus.py',ROOT/'isaforge/workload_probe.py',
              ROOT/'hardware/embench_firmware.c',ROOT/'hardware/embench_memory.c',Path(__file__))}}
    for name,expected in sources.items():
        target=output/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target);c.require(c.sha(target)==expected,'Source snapshot mismatch')
    c.seal(output/'source-manifest.json',sources)
    print(json.dumps({'snapshot':str(output),'archives':{k:v['bytes'] for k,v in archives.items()}}))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('pack');create.add_argument('--root',type=Path,required=True)
    create.add_argument('--probe',type=Path);create.add_argument('--failed',type=Path);create.add_argument('--output',type=Path,required=True)
    replay=sub.add_parser('replay');replay.add_argument('--snapshot',type=Path,default=ROOT/'results/2026-10-19-codesign')
    replay.add_argument('--output',type=Path,default=ROOT/'generated/reproduction/codesign')
    args=parser.parse_args(argv)
    if args.command=='pack':pack(args.root,args.probe,args.failed,args.output)
    else:
        archives=c.unseal(args.snapshot/'archive-manifest.json')
        for name,record in archives.items():restore_archive(args.snapshot,record,args.output/name)
        report=audit(args.output/'experiment',replay=True)
        c.require(report==c.read(args.snapshot/'independent-audit.json'),'Frozen audit differs')
        c.write(args.output/'audit.json',report)
        print('Verified raw checksums, seven processor measurements, and all 120 policy/seed/budget outcomes. No native jobs.')


if __name__=='__main__':main()

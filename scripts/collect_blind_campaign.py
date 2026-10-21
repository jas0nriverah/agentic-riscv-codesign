"""Collect each released candidate once, serially, preserving full command costs.

The pool and all model predictions must already be pushed and released. This
collector constructs an oracle dataset; selectors receive paid releases later
through the existing cooperative replay, not direct access to these files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from scripts import blind_campaign as campaign


def collect(prereg, release_path, output):
    prereg, release_path, output=map(lambda p:Path(p).resolve(),(prereg,release_path,output))
    c.require(not output.exists() and output.is_relative_to(ROOT), 'Fresh in-repository collection log required')
    cohort=campaign.check_preregistration(prereg)
    release=c.unseal(release_path)
    commit=release['prelabel_commit']
    campaign.check_git_checkpoint(prereg,commit)
    roots={group:Path(target['original_root']) for group,target in cohort['targets'].items()}
    campaign.check_release(release_path,prereg,commit,raws=roots)
    for group,root in roots.items():
        campaign._zero(root)
        campaign.check_baseline(prereg,group,root)
    output.mkdir(parents=True)
    c.seal(output/'protocol.json',dict(schema='isaforge-blind-collection-v1',
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
        prelabel_commit=commit,source_sha256=c.sha(Path(__file__)),
        order={group:value['native_order'] for group,value in cohort['targets'].items()},
        workers=1,build_workers=2,attempts_per_candidate=1,
        interpretation='Full-pool dataset collection; paid policy replay is separate. No retry of a charged candidate.'))
    commands=[]
    for group,target in cohort['targets'].items():
        for index,name in enumerate(target['native_order']):
            root=roots[group]
            c.require(not (root/'attempt-ledger'/(name+'.json')).exists(), 'Candidate already charged; preserve original attempt')
            argv=[sys.executable,'-m','isaforge.blind_workload','measure','--root',str(root),'--candidate',name]
            stamp=datetime.now(timezone.utc).isoformat(); started=time.monotonic()
            completed=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,check=False)
            elapsed=time.monotonic()-started
            folder=output/group; folder.mkdir(exist_ok=True)
            (folder/(name+'.stdout.txt')).write_text(completed.stdout)
            (folder/(name+'.stderr.txt')).write_text(completed.stderr)
            record=dict(workload_group=group,candidate=name,argv=argv,
                started_at_utc=stamp,elapsed_seconds=elapsed,returncode=completed.returncode,
                attempt_status=None,ledger_seconds=None)
            try:
                ledger=c.unseal(root/'attempt-ledger'/(name+'.json'))
                record.update(attempt_status=ledger['status'],ledger_seconds=ledger['elapsed_seconds'])
            except Exception as error:
                record['ledger_error']=repr(error)
                commands.append(record)
                c.seal(output/'commands.json',commands)
                raise ValueError('Dispatch failed before an authenticated ledger; subprocess cost preserved, stop without retry') from error
            commands.append(record)
            c.seal(output/'commands.json',commands)
            print(f'{group} {index+1}/{len(target["native_order"])} {name}: '
                  f'{ledger["status"]}, subprocess={elapsed:.3f}s',flush=True)
            c.require(ledger['status'] in ('success','failed') and
                      type(ledger['elapsed_seconds']) in (int,float) and 0<=ledger['elapsed_seconds']<=elapsed and
                      (completed.returncode==0)==(ledger['status']=='success'),
                      'Interrupted or inconsistent attempt; stop without retry')
    campaign.check_release(release_path,prereg,commit,raws=roots)
    c.seal(output/'summary.json',dict(attempted_candidates=len(commands),
        successful=sum(row['attempt_status']=='success' for row in commands),
        failed=sum(row['attempt_status']=='failed' for row in commands),
        complete_subprocess_seconds=sum(row['elapsed_seconds'] for row in commands),
        ledger_seconds=sum(row['ledger_seconds'] for row in commands),
        timer_note='Complete subprocess wall includes Python startup and encloses CLI operation and attempt ledger. These scopes overlap.',
        historical_costs=cohort['historical_costs']))
    (output/'README.md').write_text('# Serial native collection\n\n'
        'One subprocess per declared candidate, one charged attempt each, two build workers. '
        'All targets and all fixed model predictions were pushed before the cohort release. '
        'Standard output/error, failed attempts and full subprocess elapsed seconds are retained. '
        'This is full-pool oracle collection followed by paid cooperative policy replay, not live adaptive search.\n')
    c.seal(output/'manifest.json',{path.relative_to(output).as_posix():c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()})
    return c.unseal(output/'summary.json')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preregistration',type=Path,default=ROOT/'results/2026-10-21-blind-preregistration')
    parser.add_argument('--release',type=Path,default=ROOT/'results/2026-10-21-blind-release.json')
    parser.add_argument('--output',type=Path,default=ROOT/'results/2026-10-21-blind-collection')
    args=parser.parse_args(argv)
    print(collect(args.preregistration,args.release,args.output))


if __name__=='__main__':
    main()

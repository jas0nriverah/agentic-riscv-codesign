"""Serial completion coordinator for the two allowlisted selection studies.

Never starts a live agent. Await collection exit AND sealed audit readiness
before evaluation, then require final results before verification. No retries.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
SOURCE='scripts/finish_selection_study.py'
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c

STUDIES={
    'countnegative':dict(executor='scripts/execute_countnegative_v2_selector.py',
        study='generated/countnegative-v2-selection-study-r1',
        results='results/2026-10-28-countnegative-v2-selection-r1'),
    'stringsearch':dict(executor='scripts/execute_mibench_stringsearch_v2_selector.py',
        study='generated/mibench-stringsearch-v2-selection-study-r1',
        results='results/2026-10-28-mibench-stringsearch-v2-selection-r1'),
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def study_lock(key):
    path=ROOT/'generated/selection-finish-locks'/f'{key}.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Another completion coordinator holds this study lock') from error
        try:
            yield
        finally:
            fcntl.flock(handle,fcntl.LOCK_UN)


def sealed_manifest(folder):
    folder=Path(folder).resolve()
    manifest=c.unseal(folder/'manifest.json')
    c.require(isinstance(manifest,dict) and manifest,'Nonempty sealed manifest required')
    for name,digest in manifest.items():
        path=(folder/name).resolve()
        c.require(path.is_relative_to(folder) and path.is_file() and c.sha(path)==digest,
                  'Sealed artifact differs: '+name)
    return manifest


def agent_ready(study):
    folder=study/'agent'
    manifest=sealed_manifest(folder)
    c.require({'ledger.json','report.json'} <= set(manifest),'Sealed agent ledger and report required')
    ledger,report=c.unseal(folder/'ledger.json'),c.unseal(folder/'report.json')
    c.require(report.get('status')==ledger.get('status') and ledger.get('status') in ('finalized','host_fallback') and
              report.get('ledger_sha256')==c.sha(folder/'ledger.json') and
              report.get('decision_rationale')==ledger.get('decision_rationale'),
              'Completed authenticated agent episode required before collection')


def collection_ready(study):
    audit=c.unseal(study/'native-audit.json')
    report=c.unseal(study/'collection-report.json')
    operation=c.unseal(study/'collection-operation.json')
    c.require(audit.get('attempt_collection_complete') is True and report.get('collection_complete') is True and
              operation.get('collection_complete') is True and
              audit.get('charged_candidate_attempts')==report.get('charged_candidate_attempts')==
              operation.get('target_attempts')==len(audit['pool_names']),
              'Collection exit must produce complete sealed audit/report/operation artifacts')


def result_ready(results):
    manifest=sealed_manifest(results)
    c.require({'study-report.json','native-audit.json','outcomes.json'} <= set(manifest),
              'Final sealed study report, audit and outcomes required')


def plan_stages(study,results):
    if results.exists():
        result_ready(results)
        return ['verify']
    agent_ready(study)
    markers=[study/name for name in ('native-audit.json','collection-report.json','collection-operation.json')]
    if any(path.exists() for path in markers) or (study/'native/collection-report.json').exists():
        collection_ready(study)  # Incomplete artifacts fail closed; never rerun native collection.
        c.require(not (study/'scoring').exists(),'Prior evaluation artifacts require review; no automatic retry')
        return ['evaluate','verify']
    c.require(not (study/'scoring').exists(),'Prior evaluation artifacts require review; no automatic retry')
    return ['collect','evaluate','verify']


def finish(key,receipts=None):
    c.require(key in STUDIES,'Study must be countnegative or stringsearch')
    config=STUDIES[key]
    executor,study,results=(ROOT/config[n] for n in ('executor','study','results'))
    receipts=(Path(receipts).resolve() if receipts is not None else
        ROOT/'generated/selection-finish-receipts'/key/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]))
    with study_lock(key):
        c.require(not receipts.exists(),'Fresh completion receipt directory required')
        receipts.mkdir(parents=True)
        record=dict(schema='isaforge-selection-completion-v1',study=key,status='started',
            started_at_utc=stamp(),source_bindings={SOURCE:c.sha(__file__),
            config['executor']:c.sha(executor)},stages=[],automatic_retries=0,
            scope='Orchestration ordering only; no agent launch or model-performance improvement claim.')
        c.seal(receipts/'receipt.json',record)
        active=None
        try:
            stages=plan_stages(study,results)
            record['planned_stages']=stages
            c.seal(receipts/'receipt.json',record)
            for index,stage in enumerate(stages):
                # Recheck readiness immediately before dispatch, not just at planning.
                if stage=='collect':agent_ready(study)
                elif stage=='evaluate':collection_ready(study)
                else:result_ready(results)
                c.require(c.sha(executor)==record['source_bindings'][config['executor']],
                          'Executor source changed during coordination')
                argv=[sys.executable,str(executor),stage]
                active=dict(stage=stage,argv=argv,status='started',started_at_utc=stamp(),
                    returncode=None,elapsed_seconds=None,
                    stdout=f'{index:02d}-{stage}.stdout.txt',stderr=f'{index:02d}-{stage}.stderr.txt')
                record['stages'].append(active)
                c.seal(receipts/'receipt.json',record)
                began=time.monotonic()
                try:
                    with (receipts/active['stdout']).open('wb') as out,(receipts/active['stderr']).open('wb') as err:
                        completed=subprocess.run(argv,cwd=ROOT,stdout=out,stderr=err,check=False)
                    active['returncode']=completed.returncode
                    c.require(completed.returncode==0,'Completion stage failed: '+stage+'; no retry or later stage')
                    # The blocking child has exited. Audit readiness is mandatory
                    # even if a child returned zero prematurely.
                    if stage=='collect':collection_ready(study)
                    elif stage=='evaluate':result_ready(results)
                    active['status']='success'
                except BaseException as error:
                    active.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
                        error=repr(error))
                    raise
                finally:
                    active.update(ended_at_utc=stamp(),elapsed_seconds=time.monotonic()-began)
                    active['log_sha256']={name:c.sha(receipts/active[name]) for name in ('stdout','stderr')
                        if (receipts/active[name]).is_file()}
                    c.seal(receipts/'receipt.json',record)
            record['status']='success'
        except BaseException as error:
            record.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
                error=repr(error))
            raise
        finally:
            record['ended_at_utc']=stamp()
            c.seal(receipts/'receipt.json',record)
        return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',choices=tuple(STUDIES))
    parser.add_argument('--receipts',type=Path)
    args=parser.parse_args()
    result=finish(args.study,args.receipts)
    print(dict(study=result['study'],status=result['status'],stages=[s['stage'] for s in result['stages']]))

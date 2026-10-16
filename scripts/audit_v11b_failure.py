#!/usr/bin/env python3
"""Authenticate the retained V11b startup failure; never accept it as a pool.

Shares the frozen V11b input/hash helpers. No simulator or other subprocess runs.
"""
import argparse
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone
import audit_v11_recovery as base

ROOT = Path(__file__).resolve().parents[1]
need, read, sha, same = base.need, base.read, base.sha, base.same


def inspect(root):
    root = Path(root).resolve(); data = base.inputs(root)
    stage = root/'run/attempt-0000'; done = read(root/'completion.json'); manifest = read(stage/'evidence-manifest.json')
    need(done['schema'] == 'isaforge-v11b-recovery-completion-v1' and done['complete'] is False and same(done, read(stage/'completion.json')), 'Exact failed root/stage completion required')
    for name in ('new_features','new_predictions','new_labels','new_fits'):
        need(type(done[name]) is int and done[name] == 0, 'Failure cannot contain downstream jobs')
    for key,file in [('preparation_sha256','preparation.json'),('plan_sha256','plan.json'),('tools_sha256','tools.json'),('approval_sha256','recovery-approval.json'),('claim_sha256','recovery-claim.json')]:
        need(done[key] == sha(root/file), 'Failure provenance identity changed')
    need(done['runner_sha256'] == sha(ROOT/'scripts/recover_v11_transfer.py'), 'Frozen runner changed')
    need(done['program_count'] == 6 and done['reused_program_count'] == 4 and done['recovery_program_count'] == done['capture_records'] == 2, 'Exact six/two/four outcomes required')
    need(manifest['schema'] == 'isaforge-v11b-recovery-evidence-v1' and manifest['complete'] is False and manifest['completion_sha256'] == sha(stage/'completion.json'), 'Failed package identity changed')
    files = {}
    for record in manifest['files']:
        path = base.verify_record(record)
        need(path not in files, 'Repeated failure evidence'); files[path] = record
    archive = base.verify_record(manifest['archive'],stage); base.verify_zip(archive,manifest['archive']['members'])
    expected = [{k:r[k] for k in ('path','sha256','bytes')} for r in files.values() if r['packaged']]
    need(same(sorted(expected,key=lambda x:x['path']),sorted(manifest['archive']['members'],key=lambda x:x['path'])), 'Failure ZIP/ledger mismatch')
    records = read(stage/'programs.json'); need(tuple(records) == base.NAMES and done['programs_sha256'] == sha(stage/'programs.json'), 'All six named outcomes required')
    reviews = {}; completed = []; failures = []; previous = base.timestamp(read(root/'recovery-claim.json')['claimed_at_utc'])
    payloads = set()
    for name in base.NAMES:
        row = records[name]; entry = data['plan']['programs'][name]
        need(row['mode'] == entry['mode'] and row['family'] == base.FAMILIES[name] and same(row['original_record'],entry['original_record']), 'Original program changed')
        if name in base.REUSE:
            need(row['status'] == entry['original_record']['status'] and row['candidate_count'] == entry['original_record']['all_roi_count'], 'Reused outcome changed')
            for key,original in [('candidate_file','candidates'),('trace_summary','trace_summary'),('fusion','fusion')]:need(same(row[key],entry[original]),'Reused reference changed')
            candidates = base.read(base.relative_record(row['candidate_file'],root))
            need(len(candidates) == row['candidate_count'],'Reused row count changed')
            completed.extend({**r,'benchmark':name,'family':row['family']} for r in candidates)
            reviews[name] = dict(mode='unchanged-historical-reuse',status=row['status'],candidate_count=len(candidates))
            continue
        need(row['status'] == 'failure-retained' and row.get('candidate_file') is None, 'Failed capture must not supply candidates')
        folder = ROOT/'generated/v11-spooled-recovery/attempt-0000'/name
        capture = read(folder/'capture/capture.json'); worker = read(folder/'capture-worker.json')
        need(capture['status'] == 'failure-retained' and type(capture['producer_returncode']) is int and capture['producer_returncode'] == 1 and type(capture['compressor_returncode']) is int and capture['compressor_returncode'] == 0, 'Exact startup failure required')
        need(capture['cleanup_errors'] == [] and capture['remaining_owned_children'] == [], 'Cleanup is not clean')
        need(capture['primary_error'] == row['error'] == worker['primary_error'], 'Failure reason mismatch')
        need(capture['environment'] == data['tools']['environment'] and capture['compressor_sha256'] == data['tools']['executables']['gzip']['sha256'], 'Failure runtime identity changed')
        need(worker['schema'] == 'isaforge-v11b-capture-worker-v1' and worker['program'] == name and worker['runner_sha256'] == done['runner_sha256'] and worker['claim_sha256'] == done['claim_sha256'] and worker['capture_sha256'] == sha(folder/'capture/capture.json'), 'Failure wrapper binding changed')
        start,end=base.timestamp(worker['started_at_utc']),base.timestamp(worker['completed_at_utc'])
        need(previous <= start <= end <= base.timestamp(done['completed_at_utc']),'Startup attempt chronology invalid');previous=end
        raw=folder/'capture/raw-spike.log.gz.partial';payloads.add(raw)
        need(raw in files and raw.stat().st_size == capture['raw_bytes'] == 20 and sha(raw) == capture['raw_sha256'], 'Empty partial identity changed')
        with gzip.open(raw,'rb') as stream:need(stream.read(1) == b'', 'Unexpected commit payload')
        stderr=(folder/'capture/spike.stderr.log').read_text()
        need(stderr == 'Failed to run dtc: No such file or directory\nChild dtc_output process failed\n','Different startup failure')
        need((folder/'capture/htif.stdout.log').read_bytes() == b'' and (folder/'capture/compressor.stderr.log').read_bytes() == b'', 'Unexpected startup output')
        need(not (folder/'decode').exists() and not (folder/'extract').exists() and not (folder/'decode-worker.json').exists() and not (folder/'extract-worker.json').exists(), 'Downstream stage ran after startup failure')
        need(all(p in files for p in folder.rglob('*') if p.is_file()),'Unbound failed attempt evidence')
        failures.append(dict(program=name,error=row['error']))
        reviews[name]=dict(status='failure-retained',producer_exit=1,compressor_exit=0,raw_gzip_bytes=20,uncompressed_commit_bytes=0,htif_outputs=0,cleanup_errors=[],remaining_owned_children=[],reason='dtc absent from controlled PATH; Spike startup failed before ROI',capture_sha256=sha(folder/'capture/capture.json'),stderr_sha256=sha(folder/'capture/spike.stderr.log'))
    need({p for p,r in files.items() if not r['packaged']} == payloads and manifest['compressed_payloads_duplicated'] is False and manifest['historical_archives_reused_by_reference'] is True,'Exact two empty partial payloads required')
    need(same(done['failures'],failures) and same(completed,read(stage/'completed-rows.json')) and len(completed) == done['completed_program_formula_rows'] == 318 and done['completed_rows_sha256'] == sha(stage/'completed-rows.json'),'Failure/pool/reuse summary changed')
    need(records['recursion']['status'] == 'empty' and records['recursion']['candidate_count'] == 0 and done['original_primary'] == 'undefined: empty recursion MAE; never zero','Original undefined endpoint changed')
    return dict(schema='isaforge-v11b-independent-failure-audit-v1',status='pass-for-preserved-failure-only',complete=False,audited_at_utc=datetime.now(timezone.utc).isoformat(),source_sha256=sha(__file__),shared_input_auditor_sha256=sha(ROOT/'scripts/audit_v11_recovery.py'),preparation_sha256=done['preparation_sha256'],completion_sha256=sha(root/'completion.json'),evidence_manifest_sha256=sha(stage/'evidence-manifest.json'),metadata_archive_sha256=sha(archive),evidence_files=len(files),metadata_members=len(manifest['archive']['members']),historical_archive_members=data['old_member_count'],programs=reviews,reused_program_formula_rows=318,new_commit_rows=0,new_candidate_pools=0,new_features=0,new_predictions=0,new_labels=0,new_fits=0,original_primary=None,amended_primary=None,scope='Authenticated two failed startup attempts and exact four historical outcomes. Empty gzip is not a validated trace; neither missing family enters a pool. No success audit or native execution was performed.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    need(not args.output.exists(),'Fresh failure audit output required');report=inspect(args.root)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

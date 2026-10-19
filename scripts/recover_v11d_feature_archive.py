#!/usr/bin/env python3
"""Prospective packaging-only recovery of a retained V11d archive timeout.

No extraction, native command, model, prediction, label or feature replay occurs.
Original files remain immutable. Separate recovery completion never changes the
failed original completion. prepare/validate do not authorize collection.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = 'results/2026-10-16-v11d-frozen-predictions'
RUNNER = 'scripts/predict_v11d_transfer.py'
TERMINAL_SHA = 'f8566bd7bee568022c2e0ad78a14c3c52ea5b7f755590e7acdf64edab932ac3f'
RUNNER_SHA = '2d70ea85b6217281ea76f4616a502f44c984ec5f8ebd0a0de2becabd9a01b7d7'
POLICY = {'archive_seconds':300, 'minimum_free_bytes':8*1024**3,
          'maximum_whole_bytes':4*1024**3, 'maximum_archive_bytes':4*1024**3,
          'chunk_bytes':1024**2, 'candidate_count':327, 'native_channels':806,
          'new_native_jobs':0, 'new_feature_extractions':0, 'new_replays':0,
          'new_predictions':0, 'new_labels':0, 'new_fits':0, 'retries':0}


def need(ok, message):
    if not ok: raise ValueError(message)


def sha(path, guard=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2), b''):
            if guard is not None: guard()
            h.update(b)
    if guard is not None: guard()
    return h.hexdigest()


def read(path):
    def unique(items):
        d = {}
        for k,v in items: need(k not in d, 'Duplicate JSON key'); d[k] = v
        return d
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def write(path, value):
    with Path(path).open('x') as f: json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def now(): return datetime.now(timezone.utc).isoformat()
def utc(value):
    d = datetime.fromisoformat(value)
    need(d.tzinfo is not None and d.utcoffset().total_seconds() == 0, 'UTC timestamp required')
    return d


def record(path, guard=None):
    path = Path(path).resolve(); need(path.is_relative_to(ROOT), 'Repository-local evidence required')
    return {'path':path.relative_to(ROOT).as_posix(), 'sha256':sha(path, guard), 'bytes':path.stat().st_size}


def checked(row, guard=None):
    name = PurePosixPath(row['path']); need(not name.is_absolute() and '..' not in name.parts and str(name) == row['path'], 'Safe repository path required')
    p = ROOT/str(name)
    need(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(ROOT), 'Missing/unsafe evidence')
    need(type(row['bytes']) is int and p.stat().st_size == row['bytes'] and sha(p, guard) == row['sha256'], 'Evidence bytes changed')
    return p


def inventory(directory, guard=None):
    rows = []
    for p in sorted(Path(directory).rglob('*')):
        if guard is not None: guard()
        need(not p.is_symlink(), 'Symlinks forbidden in retained evidence')
        if p.is_file(): rows.append(record(p, guard))
    return rows


def original_inputs(root, guard=None):
    """Authenticate saved successes and the sole terminal packaging failure."""
    digest = lambda path: sha(path, guard)
    snapshot = lambda path: record(path, guard)
    root = Path(root).resolve(); need(root == ROOT/ORIGINAL, 'Exact original V11d cohort required')
    stage = root/'features/attempt-0000'; done = read(root/'features/completion.json')
    need(done == read(stage/'completion.json') and done['schema'] == 'isaforge-v11-transfer-feature-completion-v1'
         and done['complete'] is False and done['cleanup_failures'] == [], 'Retained terminal failed feature attempt required')
    need(done['failures'] == [{'stage':'archive-final', 'error':"AbortStage('Owned stage deadline')"}], 'Only the recorded packaging timeout may be recovered')
    need(all(type(done[k]) is int and done[k] == n for k,n in [('candidate_count',327),('completed_extractions',327),('new_predictions',0),('new_labels',0),('new_fits',0)]), 'Complete327 features and zero later jobs required')
    need(not (root/'predictions').exists() and not (root/'prediction-claim.json').exists(), 'No original inference may precede packaging recovery')
    plan = read(root/'feature-plan.json'); claim = read(root/'feature-claim.json'); approval = read(root/'feature-approval.json')
    need(plan['schema'] == 'isaforge-v11-transfer-feature-plan-v1' and plan['status'] == 'prepared-no-jobs' and plan['candidate_count'] == 327
         and len(plan['columns']) == 336 and len(plan['selected_columns']) == 217, 'Original complete feature recipe required')
    for key,path in [('feature_plan_sha256',root/'feature-plan.json'),('features_sha256',stage/'features.json'),('claim_sha256',root/'feature-claim.json'),('approval_sha256',root/'feature-approval.json'),('runner_sha256',ROOT/RUNNER)]:
        need(done[key] == digest(path), 'Failed completion no longer authenticates saved evidence')
    need(digest(ROOT/RUNNER) == RUNNER_SHA and claim['runner_sha256'] == approval['runner_sha256'] == RUNNER_SHA
         and claim['feature_plan_sha256'] == approval['feature_plan_sha256'] == digest(root/'feature-plan.json')
         and claim['approval_sha256'] == digest(root/'feature-approval.json') and claim['maximum_extractions'] == 327, 'Frozen feature release/claim/source differs')
    need(approval['status'] == 'approved-v11-full-pool-features' and utc(approval['reviewed_at_utc']) <= utc(claim['claimed_at_utc']), 'Claim precedes approval or release differs')
    need(plan['tools_sha256'] == digest(root/'tools.json') and plan['runtime_sha256'] == digest(root/'runtime.json'), 'Original sealed tools/runtime differ')
    input_root = (root/plan['input_root']).resolve(); candidates = read(input_root/'candidates.json')
    need(digest(input_root/'preparation.json') == plan['input_preparation_sha256'] and len(candidates) == 327
         and len({c['candidate_id'] for c in candidates}) == len({c['formula'] for c in candidates}) == 327, 'Complete original candidate identity required')
    features = read(stage/'features.json'); rows = features['records']
    need(features['columns'] == plan['columns'] and len(rows) == 327, 'Complete unchanged336 feature payload required')
    runtime = read(root/'runtime.json')['files'][0]
    interpreter = Path(runtime['path'])
    need(interpreter.is_absolute() and interpreter.is_file() and digest(interpreter) == runtime['sha256'], 'Original pinned interpreter changed')
    end = utc(claim['claimed_at_utc'])
    for c,r in zip(candidates, rows):
        need(c['formula'] == r['formula'] and c['candidate_id'] == r['candidate_id'], 'Feature candidate order/identity changed')
        need(len(r['values']) == 336 and all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in r['values']), 'Finite nonnegative336 features required')
        key = c['candidate_id'].split(':')[1]; folder = stage/'workers'/key
        need(r['cache_subdir'] == key and read(folder/'result.json') == r, 'Exact per-original worker result required')
        worker = read(folder/'worker.json'); end = max(end, receipt(worker, 'feature-worker', folder, claim, c['formula'], runtime=runtime, guard=guard))
    replay = read(stage/'replay/result.json'); worker = read(stage/'replay/worker.json')
    need(replay['complete'] is True and all(type(replay[k]) is int and replay[k] == v for k,v in [('records',327),('full_columns',336),('native_channels',806)])
         and replay['features_sha256'] == digest(stage/'features.json'), 'All327/806 saved raw feature replay required')
    receipt(worker, 'replay-worker', stage/'replay', claim, runtime=runtime, guard=guard)
    need(utc(worker['started_at_utc']) >= end and utc(done['completed_at_utc']) >= utc(worker['completed_at_utc']), 'Replay/completion chronology differs')
    channels = [p for p in (stage/'cache').rglob('*.ys') if p.name in ('extract.ys','sog.ys')]
    need(len(channels) == 806, 'Retained native-channel inventory must equal saved806 replay count')
    partial = stage/'raw-evidence.zip'; need(partial.is_file(), 'Original partial archive must remain retained')
    terminal = root/'archive-failure/terminal-observation.json'; observed = read(terminal)
    need(digest(terminal) == TERMINAL_SHA and observed['schema'] == 'isaforge-v11d-archive-terminal-observation-v1' and observed['complete'] is False
         and type(observed['process_exit_code']) is int and observed['process_exit_code'] == 1, 'Exact retained terminal observation required')
    expected_terminal = [root/n for n in ('features/completion.json','features/attempt-0000/completion.json','features/attempt-0000/features.json','features/attempt-0000/replay/result.json','features/attempt-0000/replay/worker.json','features/attempt-0000/raw-evidence.zip','archive-failure/collector.log')]
    need(set(observed['files']) == {p.relative_to(ROOT).as_posix() for p in expected_terminal}, 'Exact terminal evidence closure required')
    for name,e in observed['files'].items():checked({'path':name,**e}, guard)
    need(all(type(observed[k]) is int and observed[k] == n for k,n in [('extractions_completed',327),('raw_channels_replayed',806),('new_predictions',0),('new_labels',0),('new_fits',0)]), 'Terminal scope differs')
    need(utc(observed['observed_terminal_at_utc']) >= utc(done['completed_at_utc']) >= utc(worker['completed_at_utc']), 'Observed terminal chronology differs')
    with zipfile.ZipFile(partial) as z:need(type(observed['partial_archive_member_count']) is int and len(z.namelist()) == observed['partial_archive_member_count'], 'Retained partial archive count differs')
    bindings = {}
    for e in plan['files']:
        p = (root/e['path']).resolve(); need(p.is_relative_to(ROOT) and p.is_file() and digest(p) == e['sha256'], 'Original plan input/source changed')
        need(p not in bindings, 'Duplicate original input binding'); bindings[p] = snapshot(p)
    source_paths = [(root/name).resolve() for name in plan['source_paths']]
    need(len(source_paths) == len(set(source_paths)) and all(p in bindings for p in source_paths), 'All original source bytes must remain bound')
    return done,features,source_paths,bindings


def receipt(worker, action, folder, claim, formula=None, *, runtime=None, guard=None):
    need(worker['schema'] == 'isaforge-v11-prediction-worker-v1' and worker['action'] == action and worker['complete'] is True
         and type(worker['returncode']) is int and worker['returncode'] == 0 and worker['primary_error'] is None
         and worker['cleanup_errors'] == worker['remaining_owned_children'] == [], 'All original workers must be successful and cleaned')
    need(worker['runner_sha256'] == RUNNER_SHA and worker['log_sha256'] == sha(folder/'worker.log', guard), 'Worker source/log differs')
    need(type(worker['timeout_seconds']) is int and worker['timeout_seconds'] == (360 if action == 'feature-worker' else 300)
         and 0 <= worker['elapsed_seconds'] <= worker['timeout_seconds'], 'Saved worker deadline differs')
    start,end = utc(worker['started_at_utc']),utc(worker['completed_at_utc'])
    need(utc(claim['claimed_at_utc']) <= start <= end, 'Worker precedes claim or reverses chronology')
    command = worker['command']
    need(type(command) is list and len(command) == 7 and command[1] == str(ROOT/RUNNER) and command[2] == action
         and command[3:5] == ['--root', str(ROOT/ORIGINAL)] and command[5] == '--payload', 'Exact original worker command required')
    if runtime is None:
        runtime = read(ROOT/ORIGINAL/'runtime.json')['files'][0]
        need(sha(runtime['path'], guard) == runtime['sha256'], 'Original pinned interpreter changed')
    invoked = Path(command[0]); need(invoked.is_absolute() and str(invoked.resolve()) == runtime['path'], 'Original worker interpreter differs from sealed runtime')
    payload = {'claim_sha256':sha(ROOT/ORIGINAL/'feature-claim.json', guard)}
    if action == 'feature-worker': payload.update(formula=formula,cache=str(ROOT/ORIGINAL/'features/attempt-0000/cache'/folder.name),result=str(folder/'result.json'))
    need(json.loads(command[6]) == payload, 'Exact original worker payload required')
    return end


def source_files(): return [Path(__file__).resolve(), ROOT/'tests/test_recover_v11d_feature_archive.py',
    ROOT/'scripts/audit_v11d_feature_packaging.py', ROOT/'tests/test_audit_v11d_feature_packaging.py']


def member_inventory(original_root, sources, guard=None):
    stage = original_root/'features/attempt-0000'
    members = [{'member':p.relative_to(stage).as_posix(), **record(p, guard)} for p in sorted(stage.rglob('*')) if p.is_file() and p.name not in ('raw-evidence.zip','raw-evidence.json','completion.json')]
    members += [{'member':'sources/'+p.relative_to(ROOT).as_posix(), **record(p, guard)} for p in sources]
    for name in ('feature-plan.json','feature-approval.json','feature-claim.json','tools.json','runtime.json','features/completion.json','features/attempt-0000/completion.json','archive-failure/terminal-observation.json','archive-failure/collector.log'):
        members.append({'member':'provenance/original/'+name, **record(original_root/name, guard)})
    need(len({r['member'] for r in members}) == len(members), 'Unique recovered archive member layout required')
    return members


def prepare(original_root, recovery_root):
    root = Path(recovery_root).resolve(); original_root = Path(original_root).resolve()
    need(root.is_relative_to(ROOT/'results') and not root.exists() and not root.is_relative_to(original_root), 'Fresh separate recovery result root required')
    done,features,sources,bindings = original_inputs(original_root)
    original_inventory = inventory(original_root); stage = original_root/'features/attempt-0000'
    members = member_inventory(original_root, sources)
    root.mkdir(parents=True)
    plan = {'schema':'isaforge-v11d-feature-packaging-plan-v1','status':'prepared-packaging-only','created_at_utc':now(),
            'original_root':ORIGINAL,'terminal_observation':record(original_root/'archive-failure/terminal-observation.json'),'original_completion_sha256':sha(original_root/'features/completion.json'),
            'original_feature_payload_sha256':sha(stage/'features.json'),'original_partial_archive':record(stage/'raw-evidence.zip'),
            'policy':dict(POLICY),'original_inventory':original_inventory,'members':members,
            'input_bindings':list(bindings.values()),'sources':[record(p) for p in source_files()],
            'scope':'Reuse successful saved327/806 receipts; no new feature computation or replay. Original completion remainsfalse. Requires separate approval.'}
    need(utc(plan['created_at_utc']) >= utc(read(original_root/'archive-failure/terminal-observation.json')['observed_terminal_at_utc']), 'Packaging plan precedes observed terminal failure')
    write(root/'packaging-plan.json',plan); return plan


def validate(root, guard=None):
    root = Path(root).resolve(); plan = read(root/'packaging-plan.json')
    need(plan['schema'] == 'isaforge-v11d-feature-packaging-plan-v1' and plan['status'] == 'prepared-packaging-only' and plan['policy'] == POLICY and plan['original_root'] == ORIGINAL, 'Fixed packaging-only recovery plan required')
    need(plan['sources'] == [record(p, guard) for p in source_files()], 'Packaging implementation changed')
    need(plan['terminal_observation'] == record(ROOT/ORIGINAL/'archive-failure/terminal-observation.json', guard), 'Terminal observation identity differs')
    _,_,sources,bindings = original_inputs(ROOT/ORIGINAL, guard)
    need(plan['input_bindings'] == list(bindings.values()) and plan['members'] == member_inventory(ROOT/ORIGINAL,sources, guard), 'Exact original input/member closure required')
    need(inventory(ROOT/ORIGINAL, guard) == plan['original_inventory'], 'Original attempt changed after packaging preparation')
    for e in [*plan['members'], *plan['input_bindings']]: checked(e, guard)
    need(sha(ROOT/ORIGINAL/'features/completion.json', guard) == plan['original_completion_sha256'], 'Original completion changed')
    return plan


def validate_approval(root, path):
    root = Path(root).resolve(); path = Path(path).resolve(); plan = validate(root); review = read(path)
    need(path == root/'packaging-approval.json' and review['status'] == 'approved-v11d-packaging-only'
         and review['packaging_plan_sha256'] == sha(root/'packaging-plan.json')
         and review['runner_sha256'] == sha(__file__) and review['tests_sha256'] == sha(source_files()[1])
         and utc(review['reviewed_at_utc']) >= utc(plan['created_at_utc']), 'Exact prospective packaging approval required')
    commit = review['freeze_commit']; need(type(commit) is str and len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'Exact Git freeze required')
    for p in [*source_files(),root/'packaging-plan.json']:
        body = subprocess.check_output(['git','show',commit+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(body).hexdigest() == sha(p), 'Packaging release Git bytes differ')
    return plan,review


def collect(root, approval_path):
    root = Path(root).resolve(); plan,review = validate_approval(root,approval_path)
    claim = root/'packaging-claim.json'; need(not claim.exists() and not (root/'raw-evidence.zip').exists(), 'Single packaging-only attempt; no retry')
    write(claim,{'claimed_at_utc':now(),'packaging_plan_sha256':sha(root/'packaging-plan.json'),'approval_sha256':sha(approval_path),'runner_sha256':sha(__file__)})
    began = time.monotonic(); archive = root/'raw-evidence.zip'; error = None; rows = []; archive_sha = None
    original_bytes = sum(r['bytes'] for r in plan['original_inventory']); base_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    def guard():
        need(time.monotonic()-began <= POLICY['archive_seconds'], 'Packaging300s deadline')
        need(shutil.disk_usage(ROOT).free >= POLICY['minimum_free_bytes'], 'Packaging8GiB free-space floor')
        size = archive.stat().st_size if archive.exists() else 0
        need(size <= POLICY['maximum_archive_bytes'] and original_bytes+base_bytes+size+8*1024**2 <= POLICY['maximum_whole_bytes'], 'Packaging whole4GiB cap including retained original and new archive')
    try:
        guard()
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for entry in plan['members']:
                guard(); path = ROOT/entry['path']; h = hashlib.sha256(); size = 0
                with path.open('rb') as incoming,z.open(entry['member'],'w',force_zip64=True) as outgoing:
                    for body in iter(lambda:incoming.read(POLICY['chunk_bytes']),b''):
                        need(size+len(body) <= entry['bytes'], 'Original source grew while packaging')
                        outgoing.write(body);h.update(body);size+=len(body);guard()
                need(h.hexdigest() == entry['sha256'] and size == entry['bytes'], 'Source changed while packaging')
                rows.append({'path':entry['member'],'sha256':h.hexdigest(),'bytes':size})
            for path in (root/'packaging-plan.json',Path(approval_path),claim):
                z.write(path,'provenance/recovery/'+path.name)
                rows.append({'path':'provenance/recovery/'+path.name,'sha256':sha(path),'bytes':path.stat().st_size});guard()
        guard(); validate(root, guard); guard()
        archive_sha = sha(archive, guard)
        manifest = {'schema':'isaforge-v11-feature-archive-v1','archive_sha256':archive_sha,'files':rows,
                    'recovery_scope':'Packaging-only; original feature completion remainsfalse.'}
        write(root/'raw-evidence.json',manifest);guard()
    except BaseException as caught: error = caught
    done = {'schema':'isaforge-v11d-feature-packaging-completion-v1','complete':error is None,'error':repr(error) if error else None,
            'packaging_plan_sha256':sha(root/'packaging-plan.json'),'approval_sha256':sha(approval_path),'claim_sha256':sha(claim),
            'runner_sha256':sha(__file__),'original_completion_sha256':plan['original_completion_sha256'],
            'original_feature_payload_sha256':plan['original_feature_payload_sha256'],'original_completion_remains_false':True,
            'archive_sha256':archive_sha or (sha(archive) if archive.exists() else None),'manifest_sha256':sha(root/'raw-evidence.json') if (root/'raw-evidence.json').exists() else None,
            'archived_members':len(rows),'elapsed_seconds':time.monotonic()-began,'completed_at_utc':now(),'calls':{k:POLICY[k] for k in ('new_native_jobs','new_feature_extractions','new_replays','new_predictions','new_labels','new_fits')}}
    write(root/'completion.json',done)
    if error is not None: raise ValueError('Packaging-only failure retained: '+repr(error)) from error
    return done


def validate_recovery(root):
    root = Path(root).resolve(); plan = validate(root); done = read(root/'completion.json'); manifest = read(root/'raw-evidence.json')
    need(done['schema'] == 'isaforge-v11d-feature-packaging-completion-v1' and done['complete'] is True and done['error'] is None
         and done['original_completion_remains_false'] is True and done['packaging_plan_sha256'] == sha(root/'packaging-plan.json')
         and done['archive_sha256'] == manifest['archive_sha256'] == sha(root/'raw-evidence.zip') and done['manifest_sha256'] == sha(root/'raw-evidence.json'), 'Complete separately authenticated packaging recovery required')
    need(type(done['elapsed_seconds']) in (int,float) and math.isfinite(done['elapsed_seconds'])
         and 0 <= done['elapsed_seconds'] <= POLICY['archive_seconds'], 'Packaging elapsed time exceeds frozen deadline')
    review = read(root/'packaging-approval.json'); claim = read(root/'packaging-claim.json')
    need(review['status'] == 'approved-v11d-packaging-only' and review['packaging_plan_sha256'] == sha(root/'packaging-plan.json')
         and review['runner_sha256'] == sha(__file__) and review['tests_sha256'] == sha(source_files()[1]), 'Recovery approval identity differs')
    need(claim['packaging_plan_sha256'] == sha(root/'packaging-plan.json') and claim['approval_sha256'] == sha(root/'packaging-approval.json')
         and claim['runner_sha256'] == sha(__file__), 'Recovery claim identity differs')
    need(utc(plan['created_at_utc']) <= utc(review['reviewed_at_utc']) <= utc(claim['claimed_at_utc']) <= utc(done['completed_at_utc']), 'Recovery approval/claim/completion chronology differs')
    need(done['original_completion_sha256'] == plan['original_completion_sha256'] and done['original_feature_payload_sha256'] == plan['original_feature_payload_sha256'], 'Recovery advertised original lineage differs')
    need(done['approval_sha256'] == sha(root/'packaging-approval.json') and done['claim_sha256'] == sha(root/'packaging-claim.json') and done['runner_sha256'] == sha(__file__), 'Recovery execution/source identities differ')
    expected = [{'path':r['member'],'sha256':r['sha256'],'bytes':r['bytes']} for r in plan['members']]
    expected += [{'path':'provenance/recovery/'+p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in [root/'packaging-plan.json',root/'packaging-approval.json',root/'packaging-claim.json']]
    need(manifest['files'] == expected and done['archived_members'] == len(expected), 'Exact full recovered archive member closure required')
    need(all(type(v) is int for v in done['calls'].values()) and done['calls'] == {k:POLICY[k] for k in ('new_native_jobs','new_feature_extractions','new_replays','new_predictions','new_labels','new_fits')}, 'Packaging-only execution scope differs')
    with zipfile.ZipFile(root/'raw-evidence.zip') as z:
        rows = manifest['files']; need(len(rows) == len({e['path'] for e in rows}) == len(z.namelist()) and set(z.namelist()) == {e['path'] for e in rows}, 'Complete unique recovered member inventory required')
        for e in rows:
            h = hashlib.sha256(); size = 0
            with z.open(e['path']) as f:
                for b in iter(lambda:f.read(1024**2),b''):h.update(b);size+=len(b)
            need(h.hexdigest() == e['sha256'] and size == e['bytes'], 'Recovered archive member changed')
        need(hashlib.sha256(z.read('features.json')).hexdigest() == plan['original_feature_payload_sha256'], 'Recovered feature vectors differ')
    bindings = {checked(e):e['sha256'] for e in [*plan['original_inventory'],*plan['input_bindings'],*plan['sources']]}
    bindings.update({p:sha(p) for p in root.iterdir() if p.is_file()})
    return done,read(ROOT/ORIGINAL/'features/attempt-0000/features.json'),bindings


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','validate','collect','validate-recovery'))
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--original-root',type=Path);parser.add_argument('--approval',type=Path)
    a = parser.parse_args()
    if a.action == 'prepare': need(a.original_root is not None,'Original failed root required'); result = prepare(a.original_root,a.root)
    elif a.action == 'validate': result = {'status':'valid','members':len(validate(a.root)['members'])}
    elif a.action == 'collect': need(a.approval is not None,'Prospective approval required'); result = collect(a.root,a.approval)
    else: result = validate_recovery(a.root)[0]
    print(json.dumps(result,indent=2))

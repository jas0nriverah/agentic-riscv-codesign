#!/usr/bin/env python3
"""Read-only admission of separately released V11d feature packaging.

Shares the packaging helper's saved-worker/source authentication, then directly
recounts and hashes the complete ZIP and checks unchanged ordered feature data.
No process, extraction, model loading, inference, target access or fit API.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recover_v11d_feature_archive as shared

ROOT = Path(__file__).resolve().parents[1]


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def utc(value):
    result = datetime.fromisoformat(value)
    need(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, 'UTC required')
    return result


def run(root):
    root = Path(root).resolve()
    done, authenticated_features, _ = shared.validate_recovery(root)
    plan = read(root/'packaging-plan.json')
    original = ROOT/plan['original_root']
    stage = original/'features/attempt-0000'
    features = read(stage/'features.json')
    feature_plan = read(original/'feature-plan.json')
    candidates = read((original/feature_plan['input_root']).resolve()/'candidates.json')
    old_done = read(original/'features/completion.json')
    approval = read(root/'packaging-approval.json')
    claim = read(root/'packaging-claim.json')
    manifest = read(root/'raw-evidence.json')
    replay = read(stage/'replay/result.json')
    replay_worker = read(stage/'replay/worker.json')

    need(old_done['complete'] is False and old_done['failures'] == [
        {'stage':'archive-final', 'error':"AbortStage('Owned stage deadline')"}], 'Original failure must remain unchanged')
    for key, path in [('original_completion_sha256', original/'features/completion.json'),
                      ('original_feature_payload_sha256', stage/'features.json')]:
        need(done[key] == plan[key] == sha(path), 'Completion original lineage differs')
    need(approval['status'] == 'approved-v11d-packaging-only'
         and approval['packaging_plan_sha256'] == claim['packaging_plan_sha256'] == sha(root/'packaging-plan.json')
         and claim['approval_sha256'] == sha(root/'packaging-approval.json')
         and approval['runner_sha256'] == claim['runner_sha256'] == done['runner_sha256'] == sha(shared.__file__), 'Exact packaging release/claim required')
    need(utc(plan['created_at_utc']) <= utc(approval['reviewed_at_utc']) <= utc(claim['claimed_at_utc']) <= utc(done['completed_at_utc']), 'Packaging chronology differs')
    expected_calls = {name:0 for name in ('new_native_jobs','new_feature_extractions','new_replays','new_predictions','new_labels','new_fits')}
    need(done['calls'] == expected_calls and all(type(v) is int for v in done['calls'].values()), 'Packaging must perform zero scientific jobs')
    need(type(done['elapsed_seconds']) in (int,float) and math.isfinite(done['elapsed_seconds'])
         and 0 <= done['elapsed_seconds'] <= shared.POLICY['archive_seconds'], 'Packaging deadline receipt differs')
    need(features == authenticated_features and len(candidates) == len(features['records']) == 327, 'Complete327 unchanged records required')
    need(len(feature_plan['columns']) == len(set(feature_plan['columns'])) == 336
         and features['columns'] == feature_plan['columns'], 'Exact336 full feature columns required')
    indices = feature_plan['selected_indices']
    need(len(indices) == len(set(indices)) == 217 and all(type(i) is int and 0 <= i < 336 for i in indices)
         and [features['columns'][i] for i in indices] == feature_plan['selected_columns'], 'Fixed217 feature view differs')
    need(len({c['candidate_id'] for c in candidates}) == len({c['formula'] for c in candidates}) == 327, 'Unique complete candidate identities required')
    for row, candidate in zip(features['records'], candidates):
        need((row['candidate_id'], row['formula']) == (candidate['candidate_id'], candidate['formula']), 'Ordered original identity differs')
        need(len(row['values']) == 336 and all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in row['values']), 'Finite nonnegative336 matrix required')
    need(replay['complete'] is True and type(replay['records']) is int and replay['records'] == 327
         and type(replay['full_columns']) is int and replay['full_columns'] == 336
         and type(replay['native_channels']) is int and replay['native_channels'] == 806
         and replay['features_sha256'] == sha(stage/'features.json'), 'Complete saved327/806 arithmetic replay required')
    need(replay_worker['complete'] is True and type(replay_worker['returncode']) is int and replay_worker['returncode'] == 0
         and replay_worker['primary_error'] is None and replay_worker['cleanup_errors'] == replay_worker['remaining_owned_children'] == []
         and replay_worker['log_sha256'] == sha(stage/'replay/worker.log'), 'Saved replay worker/log differs')

    expected = {row['member']:(row['sha256'],row['bytes']) for row in plan['members']}
    need(len(expected) == len(plan['members']), 'Duplicate planned ZIP member')
    for path in [root/'packaging-plan.json', root/'packaging-approval.json', root/'packaging-claim.json']:
        name = 'provenance/recovery/'+path.name
        need(name not in expected, 'Recovery metadata member collision')
        expected[name] = (sha(path), path.stat().st_size)
    declared = {row['path']:(row['sha256'],row['bytes']) for row in manifest['files']}
    need(len(declared) == len(manifest['files']) and declared == expected, 'Exact manifest inventory differs')
    total = 0
    with zipfile.ZipFile(root/'raw-evidence.zip') as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) == len(expected) and set(names) == set(expected), 'Missing/extra/duplicate ZIP member')
        for name in names:
            safe = PurePosixPath(name)
            need(not safe.is_absolute() and '..' not in safe.parts and str(safe) == name, 'Unsafe ZIP member')
            digest = hashlib.sha256(); size = 0
            with archive.open(name) as stream:
                for block in iter(lambda:stream.read(1024**2), b''):
                    digest.update(block); size += len(block)
            need((digest.hexdigest(),size) == expected[name] and type(expected[name][1]) is int, 'ZIP member bytes differ')
            total += size
        for name in ['features.json','replay/result.json','replay/worker.json','replay/worker.log']:
            need(archive.read(name) == (stage/name).read_bytes(), 'Archived saved success evidence differs')
    channels = sum(PurePosixPath(name).name in ('extract.ys','sog.ys') and name.startswith('cache/') for name in expected)
    need(channels == 806 and type(done['archived_members']) is int and done['archived_members'] == len(expected), 'Full806 channel/member count differs')
    return {
        'schema':'isaforge-v11d-independent-feature-packaging-audit-v1', 'status':'pass', 'complete':True,
        'audited_at_utc':datetime.now(timezone.utc).isoformat(),
        'completion_sha256':sha(root/'completion.json'), 'archive_sha256':sha(root/'raw-evidence.zip'),
        'manifest_sha256':sha(root/'raw-evidence.json'), 'original_completion_sha256':sha(original/'features/completion.json'),
        'features_sha256':sha(stage/'features.json'), 'packaging_plan_sha256':sha(root/'packaging-plan.json'),
        'original_feature_plan_sha256':sha(original/'feature-plan.json'), 'replay_sha256':sha(stage/'replay/result.json'),
        'auditor_sha256':sha(__file__), 'tests_sha256':sha(ROOT/'tests/test_audit_v11d_feature_packaging.py'),
        'audit_source':{'path':Path(__file__).resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix(),
                        'sha256':sha(__file__), 'bytes':Path(__file__).stat().st_size},
        'shared_helper_sha256':sha(shared.__file__), 'original_runner_sha256':sha(ROOT/shared.RUNNER),
        'records':327, 'full_columns':336, 'selected_columns':217, 'native_channels':806,
        'archive_members':len(expected), 'uncompressed_member_bytes':total,
        'packaging_elapsed_seconds':done['elapsed_seconds'],
        'original_completion_remains_false':True, 'new_native_jobs':0, 'new_features':0,
        'new_models_loaded':0, 'new_predictions':0, 'new_labels':0, 'new_fits':0,
        'scope':'Independent ZIP member hashing/inventory, ordered feature matrix and saved replay/release checks; shares recovery helper source/old-tree/saved-worker authentication. Same-host validation requires the retained original paths and live pinned Python alias/runtime dependencies. Authenticates the existing graph arithmetic replay; does not recompute features, rerun native commands or infer model predictions. Historical execution/OS provenance is not independently reproduced.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.root)
    with args.output.open('x') as output:
        json.dump(report, output, indent=2, allow_nan=False); output.write('\n')

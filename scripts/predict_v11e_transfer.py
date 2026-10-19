#!/usr/bin/env python3
"""Inference only from separately recovered, unchanged V11d feature bytes.

The failed original remains failed. No extraction, native synthesis, training,
calibration or target-label API is exposed. prepare/validate load no models;
predict needs a separate commit-bound approval after packaging admission.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import predict_v11d_transfer as frozen
import recover_v11d_feature_archive as packaging
from isaforge import area_model_v6 as v6

FROZEN_SHA='2d70ea85b6217281ea76f4616a502f44c984ec5f8ebd0a0de2becabd9a01b7d7'
POLICY={'inference_worker_seconds':300,'poll_seconds':.25,'minimum_free_bytes':8*1024**3,
        'maximum_workspace_bytes':4*1024**3,'maximum_log_bytes':16*1024**2,'maximum_raw_file_bytes':128*1024**2,
        'workers':1,'retries':0,'native_jobs':0,'feature_extractions':0,'fits':0,'calibration_jobs':0,'target_jobs':0}
need,read,sha,equal,record,check_hashes=(getattr(frozen,k) for k in ('need','read','sha','equal','record','check_hashes'))
write,now,utc=(getattr(frozen,k) for k in ('write','now','utc'))
# Read-only downstream collector compatibility; V11e owns its recovery-aware seal.
inputs,tools_bindings,native_tools,Owner=frozen.inputs,frozen.tools_bindings,frozen.native_tools,frozen.Owner
clean,cancel,provenance=frozen.clean,frozen.cancel,frozen.provenance


def integer(n): need(type(n) is int and n>=0,'Nonnegative integer required'); return n

def sources():
    return sorted({*frozen.sources(),*packaging.source_files(),Path(__file__).resolve(),ROOT/'tests/test_predict_v11e_transfer.py'})


def admission(source_root,recovery_root,audit_path,audit_sha):
    """Saved evidence/model hashes only, with explicit independently reviewed seal."""
    source_root=Path(source_root).resolve(); recovery_root=Path(recovery_root).resolve(); audit_path=Path(audit_path).resolve()
    need(source_root.is_relative_to(ROOT/'results') and recovery_root.is_relative_to(ROOT/'results') and audit_path.is_relative_to(ROOT),'Repository evidence roots required')
    need(sha(frozen.__file__)==FROZEN_SHA,'Frozen numerical source changed')
    plan,candidates,models,tools,bindings=frozen.validate(source_root)
    done,data,recovery_bindings=packaging.validate_recovery(recovery_root)
    recovery_plan=read(recovery_root/'packaging-plan.json')
    need((ROOT/recovery_plan['original_root']).resolve()==source_root,'Recovery belongs to a different source stage')
    need(done['original_completion_remains_false'] is True and read(source_root/'features/completion.json')['complete'] is False,'Original failed completion must remain false')
    need(re.fullmatch('[0-9a-f]{64}',audit_sha) and sha(audit_path)==audit_sha,'Explicit reviewed packaging-audit digest required')
    review=read(audit_path); n=len(candidates)
    need(review['schema']=='isaforge-v11d-independent-feature-packaging-audit-v1' and review['status']=='pass' and review['complete'] is True,'Complete independent packaging admission required')
    expected={'completion_sha256':sha(recovery_root/'completion.json'),'archive_sha256':sha(recovery_root/'raw-evidence.zip'),
        'manifest_sha256':sha(recovery_root/'raw-evidence.json'),'original_completion_sha256':sha(source_root/'features/completion.json'),
        'features_sha256':sha(source_root/'features/attempt-0000/features.json'),
        'packaging_plan_sha256':sha(recovery_root/'packaging-plan.json'),
        'original_feature_plan_sha256':sha(source_root/'feature-plan.json'),
        'replay_sha256':sha(source_root/'features/attempt-0000/replay/result.json'),
        'original_runner_sha256':FROZEN_SHA,'original_completion_remains_false':True}
    need(review['original_completion_remains_false'] is True,'Reviewed original completion must remain false')
    need(all(review[k]==v for k,v in expected.items()),'Reviewed packaging audit no longer authenticates source bytes')
    audit_source=frozen.inputs.checked(review['audit_source'],ROOT); audit_tests=ROOT/'tests/test_audit_v11d_feature_packaging.py'
    need(audit_source==ROOT/'scripts/audit_v11d_feature_packaging.py' and review['auditor_sha256']==sha(audit_source)
         and review['tests_sha256']==sha(audit_tests) and review['shared_helper_sha256']==sha(packaging.__file__),'Reviewed packaging auditor/helper source differs')
    packaged_sources={e['path']:e['sha256'] for e in recovery_plan['sources']}
    need(all(packaged_sources.get(path.relative_to(ROOT).as_posix())==sha(path) for path in (audit_source,audit_tests)),'Packaging plan omits reviewed auditor source/tests')
    need(all(type(review[k]) is int and review[k]==0 for k in ('new_native_jobs','new_features','new_models_loaded','new_predictions','new_labels','new_fits')),'Packaging audit scope differs')
    need(integer(review['records'])==n and integer(review['full_columns'])==336 and integer(review['selected_columns'])==217 and integer(review['native_channels'])==integer(read(source_root/'features/attempt-0000/replay/result.json')['native_channels']),'Complete original feature coverage required')
    need(utc(review['audited_at_utc'])>=utc(done['completed_at_utc']),'Packaging audit precedes recovery completion')
    terminal=source_root/'archive-failure/terminal-observation.json'; observation=read(terminal)
    need(observation['schema']=='isaforge-v11d-archive-terminal-observation-v1' and utc(done['completed_at_utc'])>=utc(observation['observed_terminal_at_utc']),'Recovery must follow actual terminal archive failure')
    need(data==read(source_root/'features/attempt-0000/features.json') and len(data['records'])==n and data['columns']==plan['columns'],'Unchanged full original feature payload required')
    for c,r in zip(candidates,data['records']):
        need(c['candidate_id']==r['candidate_id'] and c['formula']==r['formula'] and len(r['values'])==336,'Full original feature order/width required')
        need(all(type(v) in (int,float) and np.isfinite(v) and v>=0 for v in r['values']),'Finite nonnegative original336 matrix required')
    members=read((source_root/plan['input_root']).resolve()/'memberships.json')
    bindings.update(recovery_bindings); bindings.update({audit_path:audit_sha,terminal:sha(terminal)})
    bindings.update({audit_source:sha(audit_source),audit_tests:sha(audit_tests)})
    check_hashes(bindings)
    return plan,candidates,members,models,tools,data,done,review,bindings


def feature_admission(source_root,recovery_root,audit_path,audit_sha,root):
    return {'schema':'isaforge-v11-recovered-feature-admission-v1','source_feature_root':os.path.relpath(source_root,root),
        'recovery_root':os.path.relpath(recovery_root,root),'original_collection_root':str(source_root),
        'source_feature_plan':record(source_root/'feature-plan.json',root),'source_failed_completion':record(source_root/'features/completion.json',root),
        'source_terminal_observation':record(source_root/'archive-failure/terminal-observation.json',root),
        'features':record(source_root/'features/attempt-0000/features.json',root),'recovery_completion':record(recovery_root/'completion.json',root),
        'recovery_archive':record(recovery_root/'raw-evidence.zip',root),'recovery_manifest':record(recovery_root/'raw-evidence.json',root),
        'reviewed_recovery_audit':record(audit_path,root),'reviewed_recovery_audit_sha256':audit_sha,
        'reviewed_recovery_audit_scope':read(audit_path)['scope'],'original_completion_remains_false':True}


def prepare(source_feature_root,recovery_root,audit_path,audit_sha256,root):
    root=Path(root).resolve(); source=Path(source_feature_root).resolve(); recovery=Path(recovery_root).resolve(); audit_path=Path(audit_path).resolve()
    need(root.is_relative_to(ROOT/'results') and not root.exists() and not root.is_relative_to(source) and not root.is_relative_to(recovery),'Fresh separate inference-only root required')
    p,candidates,members,models,tools,data,done,review,bindings=admission(source,recovery,audit_path,audit_sha256)
    native=read(source/'runtime.json'); need(equal(native,frozen.runtime()),'Frozen numerical runtime differs')
    bindings.update({path:sha(path) for path in sources()}); check_hashes(bindings)
    root.mkdir(parents=True); write(root/'tools.json',tools); write(root/'runtime.json',native)
    plan={'schema':'isaforge-v11e-inference-plan-v1','status':'prepared-inference-only','created_at_utc':now(),'policy':dict(POLICY),
        'feature_admission':feature_admission(source,recovery,audit_path,audit_sha256,root),
        'input_root':os.path.relpath((source/p['input_root']).resolve(),root),'input_preparation_sha256':p['input_preparation_sha256'],
        'candidate_count':len(candidates),'program_formula_memberships':sum(r['canonical_count'] for r in members),
        'raw_replay_native_channels':integer(review['native_channels']),
        'columns':p['columns'],'selected_columns':p['selected_columns'],'selected_indices':p['selected_indices'],'frozen_tool':p['frozen_tool'],
        'feature_source_sha256':p['feature_source_sha256'],'tools_sha256':sha(root/'tools.json'),'runtime_sha256':sha(root/'runtime.json'),
        'files':[record(path,root) for path in sorted(bindings)],'source_paths':[os.path.relpath(path,root) for path in sources()],
        'calls':{'native_jobs':0,'feature_extractions':0,'model_artifacts_loaded':0,'predictions':0,'labels':0,'fits':0},
        'scope':'Full original pool, unchanged source336 and internal217 plus original-zero override. Packaging recovery admitted explicitly; original feature completion remains failed. No extraction/refit/calibration/targets.'}
    need(utc(plan['created_at_utc'])>=utc(review['audited_at_utc']),'Inference preparation precedes reviewed recovery')
    write(root/'inference-plan.json',plan); return plan


def validate(root):
    root=Path(root).resolve(); p=read(root/'inference-plan.json')
    need(p['schema']=='isaforge-v11e-inference-plan-v1' and p['status']=='prepared-inference-only' and equal(p['policy'],POLICY),'Exact recovered-feature inference plan required')
    a=p['feature_admission']; source=(root/a['source_feature_root']).resolve(); recovery=(root/a['recovery_root']).resolve(); audit_path=(root/a['reviewed_recovery_audit']['path']).resolve()
    original,candidates,members,models,tools,data,done,review,bindings=admission(source,recovery,audit_path,a['reviewed_recovery_audit_sha256'])
    need(equal(a,feature_admission(source,recovery,audit_path,a['reviewed_recovery_audit_sha256'],root)),'Explicit recovered-feature admission changed')
    need(equal(read(root/'tools.json'),tools) and equal(read(root/'runtime.json'),read(source/'runtime.json')) and equal(read(root/'runtime.json'),frozen.runtime()),'Same frozen tools/numerical runtime required')
    for k in ('columns','selected_columns','selected_indices','frozen_tool','feature_source_sha256','input_preparation_sha256'):
        need(equal(p[k],original[k]),'Original feature/model schema changed')
    need(set(p['calls'])=={'native_jobs','feature_extractions','model_artifacts_loaded','predictions','labels','fits'} and all(type(v) is int and v==0 for v in p['calls'].values()),'Inference preparation scope changed')
    need(integer(p['raw_replay_native_channels'])==review['native_channels'],'Saved original replay coverage changed')
    need(p['candidate_count']==integer(len(candidates)) and type(p['candidate_count']) is int and integer(p['program_formula_memberships'])==sum(r['canonical_count'] for r in members),'Complete pool denominator changed')
    need((root/p['input_root']).resolve()==(source/original['input_root']).resolve(),'Full original input stage changed')
    need(p['tools_sha256']==sha(root/'tools.json') and p['runtime_sha256']==sha(root/'runtime.json') and utc(p['created_at_utc'])>=utc(review['audited_at_utc']),'Runtime/recovery chronology changed')
    expected={**bindings,**{path:sha(path) for path in sources()}}; sealed={}
    for entry in p['files']:
        need(type(entry['path']) is str and not Path(entry['path']).is_absolute(),'Relative inference binding required')
        path=(root/entry['path']).resolve(); need(path not in sealed,'Duplicate inference binding'); sealed[path]=entry['sha256']
        need(path.is_file() and not (root/entry['path']).is_symlink() and sha(path)==entry['sha256'] and path.stat().st_size==integer(entry['bytes']),'Changed inference-bound bytes')
    need(sealed==expected and p['source_paths']==[os.path.relpath(path,root) for path in sources()],'Exact inference source/input closure required')
    sealed.update({root/n:sha(root/n) for n in ('inference-plan.json','tools.json','runtime.json')})
    sealed.update(frozen.tools_bindings(tools)); sealed.update({Path(e['path']):e['sha256'] for e in read(root/'runtime.json')['files']})
    check_hashes(sealed); return p,candidates,members,models,tools,data,sealed


def recovered_local_payloads(root,bindings):
    """Exact ZIP-backed caches/worker receipts and archives; controls stay Git-bound."""
    p=read(root/'inference-plan.json'); a=p['feature_admission']; source=(root/a['source_feature_root']).resolve(); recovery=(root/a['recovery_root']).resolve()
    plan=read(recovery/'packaging-plan.json'); manifest=read(recovery/'raw-evidence.json'); done=read(recovery/'completion.json')
    entries={e['path']:e for e in manifest['files']}; need(len(entries)==len(manifest['files']),'Unique recovered archive inventory required')
    allowed={source/'features/attempt-0000/raw-evidence.zip',recovery/'raw-evidence.zip'}
    need(bindings.get(recovery/'raw-evidence.zip')==done['archive_sha256']==manifest['archive_sha256']==sha(recovery/'raw-evidence.zip'),'Exact recovered archive binding required')
    partial=plan['original_partial_archive']; need(packaging.checked(partial)==source/'features/attempt-0000/raw-evidence.zip','Only the retained original partial ZIP may be local')
    need(bindings.get(source/'features/attempt-0000/raw-evidence.zip')==partial['sha256'],'Original partial ZIP identity differs')
    stage=source/'features/attempt-0000'; cache=stage/'cache'
    candidates=read((source/read(source/'feature-plan.json')['input_root']).resolve()/'candidates.json')
    receipts={stage/'workers'/c['candidate_id'].split(':')[1]/name for c in candidates for name in ('result.json','worker.json','worker.log')}
    for row in plan['members']:
        path=packaging.checked(row)
        if not path.is_relative_to(cache) and path not in receipts: continue
        entry=entries.get(row['member']); need(entry is not None and entry['sha256']==row['sha256']==bindings.get(path) and entry['bytes']==row['bytes'],'Only exact archive-backed original caches/worker receipts may be local')
        allowed.add(path)
    return allowed


def git_freeze(root,bindings,commit):
    need(type(commit) is str and re.fullmatch('[0-9a-f]{40}',commit),'Exact reviewed Git commit required')
    tools=read(root/'tools.json'); installed=frozen.tools_bindings(tools); installed.pop(ROOT/tools['inherited_inventory']['path'],None)
    installed.update({Path(e['path']):e['sha256'] for e in read(root/'runtime.json')['files']})
    need(all(bindings.get(path)==h and sha(path)==h for path,h in installed.items()),'Installed runtime identities changed')
    allowed={*frozen.local_payloads(bindings),*recovered_local_payloads(root,bindings),*installed}
    need(not set(sources())&allowed,'Sources cannot bypass Git')
    need(all(path.is_relative_to(ROOT) or path in installed for path in bindings),'Unrecorded outside-repository binding')
    for path,h in bindings.items():
        if not path.is_relative_to(ROOT) or path in allowed: continue
        body=subprocess.check_output(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(body).hexdigest()==h,'Reviewed inference Git bytes differ')


def validate_approval(root,path):
    root=Path(root).resolve(); path=Path(path).resolve(); p,c,m,models,tools,data,bindings=validate(root); r=read(path)
    need(path==root/'prediction-approval.json' and r['status']=='approved-v11e-recovered-feature-frozen-predictions','Exact recovered-feature inference approval required')
    expected={'inference_plan_sha256':sha(root/'inference-plan.json'),'runner_sha256':sha(__file__),'tests_sha256':sha(ROOT/'tests/test_predict_v11e_transfer.py'),
        'candidate_count':len(c),'maximum_predictions':2*len(c),'recovery_completion_sha256':p['feature_admission']['recovery_completion']['sha256'],'features_sha256':p['feature_admission']['features']['sha256']}
    need(all(k in r and equal(r[k],v) for k,v in expected.items()) and utc(r['reviewed_at_utc'])>=utc(p['created_at_utc']),'Exact prior inference release required')
    git_freeze(root,bindings,r['freeze_commit']); bindings[path]=sha(path)
    return p,c,m,models,tools,data,r,bindings


def guard(root,began=None):
    need(shutil.disk_usage(ROOT).free>=POLICY['minimum_free_bytes'],'Below8GiB free-space floor')
    total=0
    for path in root.rglob('*'):
        need(not path.is_symlink(),'Symlink in owned inference stage')
        if path.is_file():
            size=path.stat().st_size; total+=size
            cap=POLICY['maximum_log_bytes'] if path.suffix=='.log' else POLICY['maximum_raw_file_bytes']
            need(size<=cap,'Owned inference file/log cap reached')
    need(total<=POLICY['maximum_workspace_bytes'],'Owned inference workspace cap reached')
    if began is not None: need(time.monotonic()-began<=POLICY['inference_worker_seconds'],'Owned300s inference deadline')


def check_claim(root,payload):
    p=read(root/'inference-plan.json'); claim=read(root/'prediction-claim.json'); review=read(root/'prediction-approval.json')
    need(payload=={'claim_sha256':sha(root/'prediction-claim.json')} and claim['runner_sha256']==sha(__file__) and claim['inference_plan_sha256']==sha(root/'inference-plan.json')
         and claim['approval_sha256']==sha(root/'prediction-approval.json') and integer(claim['maximum_predictions'])==2*p['candidate_count']
         and utc(p['created_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(claim['claimed_at_utc']),'Exact fresh inference claim/source required')
    return p


def worker_inputs(root,payload):
    """Compact launched-worker gate; the launcher authenticates the full archive/Git closure.

    Avoid hashing the multi-GiB retained tree again inside the 300-second worker.
    The owned command binds the fresh claim; hot provenance covers these exact
    control/source bytes, and every raw graph is replayed before model loading.
    """
    p=check_claim(root,payload); review=read(root/'prediction-approval.json'); a=p['feature_admission']
    need(p['schema']=='isaforge-v11e-inference-plan-v1' and p['status']=='prepared-inference-only' and equal(p['policy'],POLICY),'Exact worker inference plan required')
    expected={'status':'approved-v11e-recovered-feature-frozen-predictions','inference_plan_sha256':sha(root/'inference-plan.json'),
        'runner_sha256':sha(__file__),'tests_sha256':sha(ROOT/'tests/test_predict_v11e_transfer.py'),
        'candidate_count':p['candidate_count'],'maximum_predictions':2*p['candidate_count'],
        'recovery_completion_sha256':a['recovery_completion']['sha256'],'features_sha256':a['features']['sha256']}
    need(all(k in review and equal(review[k],v) for k,v in expected.items()) and re.fullmatch('[0-9a-f]{40}',review['freeze_commit']),'Exact worker inference approval required')
    need(set(p['calls'])=={'native_jobs','feature_extractions','model_artifacts_loaded','predictions','labels','fits'} and all(type(v) is int and v==0 for v in p['calls'].values()),'Worker inference preparation scope differs')
    original=(root/p['input_root']).resolve(); source=(root/a['source_feature_root']).resolve()
    paths=[original/name for name in ('candidates.json','memberships.json','predictors.json')]+[(root/a['features']['path']).resolve(),root/'tools.json',root/'runtime.json',*sources()]
    sealed={(root/e['path']).resolve():e['sha256'] for e in p['files']}
    sealed.update({root/'tools.json':p['tools_sha256'],root/'runtime.json':p['runtime_sha256']})
    bindings={path:sealed[path] for path in paths}; check_hashes(bindings)
    need(equal(read(root/'runtime.json'),frozen.runtime()),'Frozen numerical runtime differs in worker')
    candidates=read(original/'candidates.json'); models=read(original/'predictors.json'); data=read((root/a['features']['path']).resolve())
    need(set(models)=={'V6','V9'} and integer(p['candidate_count'])==len(candidates)==len(data['records']) and data['columns']==p['columns']==list(v6.columns())
         and p['selected_columns']==list(v6.mapping_columns()) and p['selected_indices']==v6.mapping_indices().tolist() and p['feature_source_sha256']==v6.source_hashes(),'Complete unchanged worker model/feature schema required')
    need(all(c['candidate_id']==r['candidate_id'] and c['formula']==r['formula'] for c,r in zip(candidates,data['records'])),'Full ordered worker feature identity required')
    need(a['features']['sha256']==bindings[(root/a['features']['path']).resolve()] and a['original_completion_remains_false'] is True
         and read(source/'features/completion.json')['complete'] is False,'Worker recovered feature admission differs')
    return p,candidates,models,data,bindings


def inference_worker(root,payload):
    p,candidates,models,data,bindings=worker_inputs(root,payload)
    a=p['feature_admission']; source=(root/a['source_feature_root']).resolve(); recovered=(root/a['recovery_archive']['path']).resolve()
    native=set()
    with zipfile.ZipFile(recovered) as z:
        need(z.read('features.json')==(source/'features/attempt-0000/features.json').read_bytes(),'Recovered matrix differs from original')
        for row in data['records']:
            _,channels=frozen.replay.replay_feature_record(z,row,p['frozen_tool'],str(source)); native.update(channels)
    need(len(native)==p['raw_replay_native_channels'] and 2*len(candidates)<=len(native)<=3*len(candidates),'Complete raw336 graph replay required before model loads')
    x=np.asarray([r['values'] for r in data['records']],dtype=float)
    need(x.shape==(len(candidates),336) and np.isfinite(x).all() and np.all(x>=0),'Complete finite nonnegative full336 matrix required')
    points={}
    for name in ('V6','V9'):
        entry=models[name]; path=frozen.inputs.checked(entry['artifact'],ROOT); need(sha(path)==frozen.inputs.MODELS[name][1],'Frozen artifact changed')
        model=v6.load_model(path); need(model.training_formula_count==frozen.inputs.MODELS[name][2] and model.kind=='mapping_v6' and model.frozen_tool==p['frozen_tool'] and model.calibration['status']=='uncalibrated','Exact frozen uncalibrated model required')
        points[name]=model.predict_features([{'candidate_id':c['candidate_id'],'formula':c['formula']} for c in candidates],x)
    check_hashes(bindings)
    result={'schema':'isaforge-v11e-frozen-point-predictions-v1','candidate_count':len(candidates),'models':points,
        'inference_plan_sha256':sha(root/'inference-plan.json'),'features_sha256':a['features']['sha256'],
        'recovery_completion_sha256':a['recovery_completion']['sha256'],'source_failed_completion_sha256':a['source_failed_completion']['sha256'],
        'input_preparation_sha256':p['input_preparation_sha256'],'membership_sha256':sha((root/p['input_root']).resolve()/'memberships.json'),
        'predictor_manifest_sha256':sha((root/p['input_root']).resolve()/'predictors.json'),'runner_sha256':sha(__file__),
        'raw_replay_records':len(candidates),'raw_replay_native_channels':len(native),
        'scope':'Unchanged original336, internal217 and original-zero override; raw uncalibrated frozen V6/V9 points. Failed feature completion preserved, packaging recovery explicit. No extraction/training/calibration/targets.'}
    write(root/'predictions/attempt-0000/result.json',result)


def run_worker(root,bindings,tools):
    stage=root/'predictions/attempt-0000'; stage.mkdir(parents=True); log=stage/'worker.log'; command=[sys.executable,str(Path(__file__).resolve()),'inference-worker','--root',str(root),'--payload',json.dumps({'claim_sha256':sha(root/'prediction-claim.json')})]
    owner=frozen.Owner(tools['environment']); process=None; error=None; errors=[]; remaining=[]; start=now(); began=time.monotonic()
    p=read(root/'inference-plan.json'); source=(root/p['feature_admission']['source_feature_root']).resolve(); cache=source/'features/attempt-0000/cache'
    hot={path:h for path,h in bindings.items() if path.suffix not in ('.gz','.zip') and not path.is_relative_to(ROOT/'generated') and not path.is_relative_to(cache)}
    try:
        frozen.provenance(hot); guard(root)
        with log.open('xb') as stream:
            process=owner.launch(command,stream)
            while process.poll() is None: guard(root,began); time.sleep(POLICY['poll_seconds'])
            guard(root,began); need(process.returncode==0,'Owned inference worker failed')
        frozen.provenance(hot)
    except BaseException as caught: error=caught
    finally:
        if process is not None:
            errors,remaining=frozen.clean([('recovered-feature-inference',process)])
            if not errors and not remaining: owner.remove(process)
    row={'schema':'isaforge-v11e-prediction-worker-v1','action':'inference-worker','command':command,'started_at_utc':start,'completed_at_utc':now(),
        'timeout_seconds':POLICY['inference_worker_seconds'],'elapsed_seconds':time.monotonic()-began,'returncode':process.returncode if process else None,
        'primary_error':repr(error) if error else None,'cleanup_errors':errors,'remaining_owned_children':remaining,'log_sha256':sha(log) if log.exists() else None,
        'runner_sha256':sha(__file__),'complete':error is None and not errors and not remaining}
    write(stage/'worker.json',row)
    if error is not None: raise error
    need(row['complete'],'Owned cleanup unconfirmed'); return read(stage/'result.json')


def validate_points(result,candidates,data):
    n=len(candidates); need(result['schema']=='isaforge-v11e-frozen-point-predictions-v1' and integer(result['candidate_count'])==n and set(result['models'])=={'V6','V9'},'Exact paired original points required')
    x=np.asarray([r['values'] for r in data['records']],dtype=float); need(x.shape==(n,336) and np.isfinite(x).all() and np.all(x>=0),'Full finite nonnegative matrix required')
    zero=v6.v5.original_zero(x[:,:313])
    for rows in result['models'].values():
        need(len(rows)==n and [r['candidate_id'] for r in rows]==[c['candidate_id'] for c in candidates] and [r['formula'] for r in rows]==[c['formula'] for c in candidates],'Every original needs both ordered points')
        need(all(type(r['predicted_lut4']) in (int,float) and np.isfinite(r['predicted_lut4']) and r['predicted_lut4']>=0 and r['upper_lut4'] is None and r['calibration_status']=='uncalibrated' and (not zero[i] or r['predicted_lut4']==0) for i,r in enumerate(rows)),'Finite raw points and unchanged original-zero override required')


def predict(root,approval_path):
    root=Path(root).resolve(); p,c,m,models,tools,data,review,bindings=validate_approval(root,approval_path)
    need(not(root/'predictions').exists() and not(root/'prediction-claim.json').exists() and not(root/'point-freeze.json').exists(),'One fresh inference-only attempt; no retry')
    guard(root)
    with (root/'prediction-claim.json').open('x') as stream:
        json.dump({'claimed_at_utc':now(),'runner_sha256':sha(__file__),'inference_plan_sha256':sha(root/'inference-plan.json'),'approval_sha256':sha(approval_path),'maximum_predictions':2*len(c)},stream,indent=2); stream.write('\n')
    bindings[root/'prediction-claim.json']=sha(root/'prediction-claim.json'); failures=[]; interruption=None
    try:
        result=run_worker(root,bindings,tools); validate_points(result,c,data); check_hashes(bindings); frozen.native_tools.validate_tools(tools); guard(root)
    except BaseException as error:
        failures.append({'error':repr(error)})
        if not isinstance(error,Exception): interruption=error
    stage=root/'predictions/attempt-0000'; stage.mkdir(parents=True,exist_ok=True)
    done={'schema':'isaforge-v11e-frozen-point-completion-v1','complete':not failures,'failures':failures,'candidate_count':len(c),
        'prediction_count':2*len(c) if not failures else None,'inference_plan_sha256':sha(root/'inference-plan.json'),
        'feature_admission':p['feature_admission'],'approval_sha256':sha(approval_path),'claim_sha256':sha(root/'prediction-claim.json'),
        'point_predictions_sha256':sha(stage/'result.json') if (stage/'result.json').exists() else None,'runner_sha256':sha(__file__),
        'worker_receipt_sha256':sha(stage/'worker.json') if (stage/'worker.json').exists() else None,'worker_log_sha256':sha(stage/'worker.log') if (stage/'worker.log').exists() else None,
        'completed_at_utc':now(),'new_native_jobs':0,'new_feature_extractions':0,'new_labels':0,'new_fits':0,'calibration_jobs':0}
    write(stage/'completion.json',done); write(root/'predictions/completion.json',done)
    if interruption is not None: raise interruption
    need(done['complete'],'Incomplete inference-only attempt retained; target gate closed')
    try:
        _,_,_,point_bindings=validate_predictions(root)
        freeze={'schema':'isaforge-v11e-recovered-feature-point-freeze-v1','complete':True,'frozen_at_utc':now(),'candidate_count':len(c),'prediction_count':2*len(c),
            'inference_plan_sha256':sha(root/'inference-plan.json'),'input_preparation_sha256':p['input_preparation_sha256'],'feature_admission':p['feature_admission'],
            'prediction_completion_sha256':sha(root/'predictions/completion.json'),'point_predictions_sha256':sha(stage/'result.json'),
            'columns':p['columns'],'selected_columns':p['selected_columns'],'selected_indices':p['selected_indices'],'frozen_tool':p['frozen_tool'],
            'files':[record(path,root) for path in sorted(point_bindings)],'fits':0,'calibration_jobs':0,'labels_read':0,'native_jobs':0,'feature_extractions':0,
            'scope':'Complete paired frozen points from explicitly admitted packaging recovery. Original feature completion remains false; all originals/memberships retained. Local raw archives/native runtime remain same-host dependencies.'}
        guard(root); check_hashes(point_bindings); write(root/'point-freeze.json',freeze); guard(root); check_hashes(point_bindings)
    except BaseException as error:
        done['complete']=False; done['failures'].append({'stage':'point-freeze-final','error':repr(error)}); write(stage/'completion.json',done); write(root/'predictions/completion.json',done)
        raise
    return done


def validate_predictions(root):
    root=Path(root).resolve(); p,c,m,models,tools,data,bindings=validate(root); stage=root/'predictions/attempt-0000'; done=read(root/'predictions/completion.json'); result=read(stage/'result.json')
    need(equal(done,read(stage/'completion.json')) and done['schema']=='isaforge-v11e-frozen-point-completion-v1' and done['complete'] is True and done['failures']==[],'Complete recovered-feature inference required')
    validate_points(result,c,data)
    # Only the prospective plan closure was frozen before execution. Receipts and
    # points below are later evidence, authenticated separately by their seal.
    prospective_bindings=dict(bindings)
    for k,v in [('candidate_count',len(c)),('prediction_count',2*len(c)),('new_native_jobs',0),('new_feature_extractions',0),('new_labels',0),('new_fits',0),('calibration_jobs',0)]: need(integer(done[k])==v,'Inference count/scope differs')
    for key,path in [('inference_plan_sha256',root/'inference-plan.json'),('approval_sha256',root/'prediction-approval.json'),('claim_sha256',root/'prediction-claim.json'),('point_predictions_sha256',stage/'result.json'),('runner_sha256',Path(__file__).resolve()),('worker_receipt_sha256',stage/'worker.json'),('worker_log_sha256',stage/'worker.log')]: need(done[key]==sha(path),'Inference completion identity differs'); bindings[path]=sha(path)
    a=p['feature_admission']; expected={'inference_plan_sha256':sha(root/'inference-plan.json'),'features_sha256':a['features']['sha256'],'recovery_completion_sha256':a['recovery_completion']['sha256'],'source_failed_completion_sha256':a['source_failed_completion']['sha256'],'input_preparation_sha256':p['input_preparation_sha256'],'membership_sha256':sha((root/p['input_root']).resolve()/'memberships.json'),'predictor_manifest_sha256':sha((root/p['input_root']).resolve()/'predictors.json'),'runner_sha256':sha(__file__)}
    need(equal(done['feature_admission'],a) and all(result[k]==v for k,v in expected.items()),'Explicit recovered-feature point provenance differs')
    need(integer(result['raw_replay_records'])==len(c) and integer(result['raw_replay_native_channels'])==p['raw_replay_native_channels'],'Complete raw replay before model loads required')
    review=read(root/'prediction-approval.json'); claim=read(root/'prediction-claim.json'); worker=read(stage/'worker.json')
    expected_review={'status':'approved-v11e-recovered-feature-frozen-predictions','inference_plan_sha256':sha(root/'inference-plan.json'),'runner_sha256':sha(__file__),
        'tests_sha256':sha(ROOT/'tests/test_predict_v11e_transfer.py'),'candidate_count':len(c),'maximum_predictions':2*len(c),
        'recovery_completion_sha256':a['recovery_completion']['sha256'],'features_sha256':a['features']['sha256']}
    need(all(k in review and equal(review[k],v) for k,v in expected_review.items()) and re.fullmatch('[0-9a-f]{40}',review['freeze_commit']),'Saved exact inference approval required')
    git_freeze(root,prospective_bindings,review['freeze_commit'])
    expected_claim={'runner_sha256':sha(__file__),'inference_plan_sha256':sha(root/'inference-plan.json'),'approval_sha256':sha(root/'prediction-approval.json'),'maximum_predictions':2*len(c)}
    need(all(k in claim and equal(claim[k],v) for k,v in expected_claim.items()),'Saved exact inference claim required')
    need(worker['schema']=='isaforge-v11e-prediction-worker-v1' and worker['complete'] is True and worker['primary_error'] is None and type(worker['returncode']) is int and worker['returncode']==0 and worker['cleanup_errors']==worker['remaining_owned_children']==[],'Successful cleaned owned inference required')
    need(worker['runner_sha256']==sha(__file__) and worker['log_sha256']==sha(stage/'worker.log'),'Inference worker source/log differs')
    command=[sys.executable,str(Path(__file__).resolve()),'inference-worker','--root',str(root),'--payload',json.dumps({'claim_sha256':sha(root/'prediction-claim.json')})]
    need(worker['action']=='inference-worker' and worker['command']==command and type(worker['timeout_seconds']) is int and worker['timeout_seconds']==POLICY['inference_worker_seconds']
         and type(worker['elapsed_seconds']) in (int,float) and np.isfinite(worker['elapsed_seconds']) and 0<=worker['elapsed_seconds']<=POLICY['inference_worker_seconds']+10,'Fixed owned inference command/deadline required')
    need(utc(p['created_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(claim['claimed_at_utc'])<=utc(worker['started_at_utc'])<=utc(worker['completed_at_utc'])<=utc(done['completed_at_utc']),'Inference review/claim/worker chronology differs')
    bindings.update({root/'predictions/completion.json':sha(root/'predictions/completion.json'),stage/'completion.json':sha(stage/'completion.json')}); check_hashes(bindings)
    return done,c,m,bindings


def validate_point_freeze(root):
    root=Path(root).resolve(); done,c,m,bindings=validate_predictions(root); f=read(root/'point-freeze.json'); p=read(root/'inference-plan.json')
    expected={'schema':'isaforge-v11e-recovered-feature-point-freeze-v1','complete':True,'candidate_count':len(c),'prediction_count':2*len(c),'inference_plan_sha256':sha(root/'inference-plan.json'),'input_preparation_sha256':p['input_preparation_sha256'],'feature_admission':p['feature_admission'],'prediction_completion_sha256':sha(root/'predictions/completion.json'),'point_predictions_sha256':sha(root/'predictions/attempt-0000/result.json'),'columns':p['columns'],'selected_columns':p['selected_columns'],'selected_indices':p['selected_indices'],'frozen_tool':p['frozen_tool'],'fits':0,'calibration_jobs':0,'labels_read':0,'native_jobs':0,'feature_extractions':0}
    need(all(k in f and equal(f[k],v) for k,v in expected.items()) and utc(f['frozen_at_utc'])>=utc(done['completed_at_utc']),'Complete explicit recovered-feature point freeze required')
    need(equal(f['files'],[record(path,root) for path in sorted(bindings)]),'Exact point input/source/model/recovery closure required')
    bindings[root/'point-freeze.json']=sha(root/'point-freeze.json'); return f,c,m,bindings


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','validate','predict','validate-points','inference-worker'))
    parser.add_argument('--root',type=Path,required=True); parser.add_argument('--source-feature-root',type=Path); parser.add_argument('--recovery-root',type=Path); parser.add_argument('--recovery-audit',type=Path); parser.add_argument('--recovery-audit-sha256'); parser.add_argument('--approval',type=Path); parser.add_argument('--payload')
    a=parser.parse_args()
    if a.action=='prepare': need(all(v is not None for v in (a.source_feature_root,a.recovery_root,a.recovery_audit,a.recovery_audit_sha256)),'Explicit source/recovery/reviewed audit required'); result=prepare(a.source_feature_root,a.recovery_root,a.recovery_audit,a.recovery_audit_sha256,a.root)
    elif a.action=='predict': need(a.approval is not None,'Separate inference approval required'); result=predict(a.root,a.approval)
    elif a.action=='inference-worker': need(a.payload is not None,'Owned claim payload required'); inference_worker(a.root,json.loads(a.payload)); result={'status':'complete'}
    elif a.action=='validate-points': result={'status':'valid','candidate_count':len(validate_point_freeze(a.root)[1]),'native_jobs':0}
    else: result={'status':'valid','candidate_count':len(validate(a.root)[1]),'native_jobs':0}
    print(json.dumps(result,indent=2,allow_nan=False))

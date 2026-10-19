#!/usr/bin/env python3
"""Separately released full-pool V11 features, then frozen V6/V9 inference.

prepare/validate perform no native work or model loading. extract requires one
committed feature release; predict requires another release after all features.
No fit/calibration/target-measurement entry point exists. Every failure is kept.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
from isaforge import area_model_v6 as v6
import prepare_v11_model_comparison as inputs
import capture_v11_spooled as cleanup_helper
import develop_v13_coverage as replay
import measure_v13b_coverage as native_tools

TOOLS='results/2026-10-15-v13b-coverage-recovery/measurement-tools.json'
POLICY={'workers':2,'feature_worker_seconds':360,'replay_worker_seconds':300,'inference_worker_seconds':300,'archive_seconds':300,
    'poll_seconds':.25,'minimum_free_bytes':8*1024**3,'maximum_workspace_bytes':4*1024**3,
    'maximum_log_bytes':16*1024**2,'maximum_raw_file_bytes':128*1024**2,'retries':0,'fits':0,'calibration_jobs':0,'target_jobs':0}
need,read,sha,equal,record,check_hashes=(getattr(inputs,k) for k in ('need','read','sha','equal','record','check_hashes'))

class AbortStage(ValueError):pass
def provenance(bindings):
    try:check_hashes(bindings)
    except Exception as e:raise AbortStage('Sealed input/source/runtime changed: '+repr(e)) from e
def clean(processes):
    try:return cleanup_helper.cleanup(processes)
    except BaseException as e:return ([{'operation':'cleanup','error':repr(e)}],[{'process':name,'pid':p.pid,'scope':'cleanup-unconfirmed'} for name,p in processes])
def cancel(owner):
    try:return owner.cancel()
    except BaseException as e:return ([{'operation':'owner-cancel','error':repr(e)}],[{'scope':'owned-groups-cleanup-unconfirmed'}])
def now():return datetime.now(timezone.utc).isoformat()
def utc(v):
    d=datetime.fromisoformat(v);need(d.tzinfo is not None and d.utcoffset().total_seconds()==0,'UTC timestamp required');return d
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def write_claim(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def runtime():
    from sklearn.ensemble import _forest
    from sklearn.tree import _tree
    paths=[Path(sys.executable).resolve(),Path(_forest.__file__).resolve(),Path(_tree.__file__).resolve()]
    return {'python':sys.version,'versions':{n:importlib.metadata.version(n) for n in ('numpy','scipy','scikit-learn','xgboost','joblib','threadpoolctl')},
        'files':[{'path':str(p),'sha256':sha(p)} for p in paths],
        'scope':'Same-host numerical runtime plus recorded native binaries/data/SDK. Not a hermetic OS or complete dynamic-library image.'}
def sources():
    return sorted({*inputs.sources(),*replay.source_paths(),ROOT/'scripts/predict_v11_transfer.py',ROOT/'tests/test_predict_v11_transfer.py',
        ROOT/'scripts/capture_v11_spooled.py',ROOT/'tests/test_capture_v11_spooled.py',ROOT/'scripts/measure_v13b_coverage.py',
        ROOT/'scripts/measure_v10_csd_hardware.py',ROOT/'scripts/measure_v6.py',ROOT/'scripts/evaluate_v6.py',ROOT/'scripts/evaluate_v5.py',ROOT/'scripts/evaluate_v4.py',
        *(ROOT/'results/2026-10-16-v11-prediction-review'/name for name in ('compatibility-review.json','predict-source.py','record.json','replay-driver.py','manifest.json','README.md'))})
def tools_bindings(tools):
    result={Path(e['path']).resolve():e['sha256'] for e in tools['executables'].values()}
    for key in ('yosys_data','verilator_include'):
        base=Path(tools[key]['path']);result.update({(base/e['path']).resolve():e['sha256'] for e in tools[key]['files']})
    sdk=tools['sdk'];result[Path(sdk['settings']['path'])]=sdk['settings']['sha256']
    base=Path(sdk['libcxx_include']['path']);result.update({(base/e['path']).resolve():e['sha256'] for e in sdk['libcxx_include']['files']})
    result[ROOT/tools['inherited_inventory']['path']]=tools['inherited_inventory']['sha256'];return result

def staged_inputs(directory):
    directory=Path(directory).resolve();m=read(directory/'preparation.json')
    need(m['schema']=='isaforge-v11-model-comparison-inputs-v1' and m['status']=='prepared-inputs-only' and not(directory/'preparation-failure.json').exists(),'Complete full-pool input stage required')
    need(set(m['calls'])=={'native_jobs','feature_extractions','model_artifacts_loaded','predictions','target_label_files_opened','fits','new_solver_queries'} and all(type(n) is int and n==0 for n in m['calls'].values()),'Input stage scope changed')
    bindings={};entries=m['files'];need(len(entries)==len({e['path'] for e in entries}),'Unique input bindings required')
    for e in entries:
        p=inputs.checked(e,directory);need(p not in bindings,'Repeated resolved binding');bindings[p]=e['sha256']
    required={directory/n for n in ('memberships.json','candidates.json','predictors.json','overlap.json','pre-reservation-reference.json','proposed-budget.json')}
    required|={directory/'original-candidate-files'/(n+'.json') for n in inputs.FAMILIES}
    need(required<=set(bindings),'Missing full-pool stage outputs')
    candidates=read(directory/'candidates.json');members=read(directory/'memberships.json');models=read(directory/'predictors.json')
    source_root=(directory/m['source_root']).resolve();reviewed=m['reviewed_audit'];audit_path=inputs.checked(reviewed,directory)
    recovered,report,recovery_bindings=inputs.authenticate_recovery(source_root,audit_path,reviewed['sha256'])
    expected_members,expected_candidates,copies=inputs.pool(source_root,recovered)
    need(equal(candidates,expected_candidates) and equal(members,expected_members),'Full staged pool must exactly reproduce authenticated recovery')
    need(all((directory/'original-candidate-files'/(name+'.json')).read_bytes()==path.read_bytes() for name,path in copies.items()),'Original candidate copies differ from authenticated recovery')
    need(all(bindings.get(path)==h for path,h in recovery_bindings.items()) and m['audit_independence']==report['independence'],'Authenticated recovery/audit closure omitted or changed')
    aliases,training,expected_models,historical=inputs.historical_inputs()
    need(equal(models,expected_models) and equal(read(directory/'pre-reservation-reference.json'),[{'formula':f,'accepted_forms':sorted(forms)} for f,forms in sorted(aliases.items())])
        and equal(read(directory/'overlap.json'),inputs.overlap(candidates,aliases,training)) and equal(read(directory/'proposed-budget.json'),inputs.budget(len(candidates),sum(r['canonical_count'] for r in members))),'Frozen historical/predictor/overlap outputs do not reproduce')
    expected={*recovery_bindings,*historical,*inputs.sources(),*required}
    need(set(bindings)==expected and all(bindings.get(path)==h for path,h in historical.items()),'Exact staged source/input/output closure required')
    formulas=[inputs.canonical(c['formula']) for c in candidates];need(formulas==sorted(set(formulas)) and len(formulas)==inputs.integer(m['unique_canonical_originals']) and bool(formulas),'Complete sorted unique original pool required')
    ids={c['candidate_id'] for c in candidates};need(len(ids)==len(candidates) and all(c['candidate_id']==inputs.identifier(c['formula']) for c in candidates),'Original IDs differ')
    need(len(members)==6 and {r['program'] for r in members}==set(inputs.FAMILIES),'Exactly six memberships required')
    seen=set();total=0;programs={c['candidate_id']:[] for c in candidates}
    for r in members:
        name=r['program'];n=inputs.integer(r['canonical_count']);rowids=r['canonical_ids']
        need(name not in seen and r['family']==inputs.FAMILIES[name] and r['status']==('complete' if n else 'empty') and type(rowids) is list and len(set(rowids))==len(rowids)==n and set(rowids)<=ids,'Full valid program membership required');seen.add(name);total+=n
        need(name!='recursion' or n==0,'Recursion remains empty')
        for i in rowids:programs[i].append(name)
        original=read(directory/'original-candidate-files'/(name+'.json'));need({inputs.identifier(inputs.canonical(x['formula'])) for x in original}==set(rowids) and len(original)==n,'Original candidate byte-copy membership differs')
    need(total==inputs.integer(m['program_formula_memberships']) and all(programs.values()) and all(any(r['canonical_count'] for r in members if r['family']==f) for f in set(inputs.FAMILIES.values())),'Complete five-family denominator required')
    for c in candidates:need(set(c['programs'])==set(programs[c['candidate_id']]) and c['families']==sorted({inputs.FAMILIES[n] for n in c['programs']}),'Cross-program original membership differs')
    need(set(models)=={'V6','V9'},'Exact adopted predictor pair required')
    metadata={}
    for name,(relative,h,count) in inputs.MODELS.items():
        entry=models[name];artifact=inputs.checked(entry['artifact'],ROOT);schema=inputs.checked(entry['metadata'],ROOT);d=read(schema)
        need(artifact==ROOT/relative and sha(artifact)==h and artifact in bindings and schema in bindings,'Frozen local model artifacts must exist and be input-bound')
        need(d['artifact_sha256']==h and d['training_formula_count']==count and d['kind']=='mapping_v6' and d['calibration']['status']=='uncalibrated','Adopted uncalibrated model identity differs');metadata[name]=d
    need(metadata['V6']['feature_columns']==metadata['V9']['feature_columns']==list(v6.columns()) and metadata['V6']['mapping_columns']==metadata['V9']['mapping_columns']==list(v6.mapping_columns()),'Same frozen336/217 schema required')
    bindings[directory/'preparation.json']=sha(directory/'preparation.json')
    return m,candidates,members,models,metadata,bindings

def prepare(input_root,root):
    root=Path(root).resolve();input_root=Path(input_root).resolve()
    need(root.is_relative_to(ROOT/'results') and not root.exists() and not root.is_relative_to(input_root),'Fresh separate prediction result root required')
    m,candidates,members,models,metadata,bindings=staged_inputs(input_root)
    tools=read(ROOT/TOOLS);native_tools.validate_tools(tools);env=runtime()
    tool={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']}
    need(all(d['frozen_tool']==tool and d['versions']=={n:env['versions'][n] for n in d['versions']} and d['runtime_source_sha256']==v6.source_hashes() for d in metadata.values()),'Both predictors require exact frozen feature tool/numerical/runtime sources')
    source_files=sources();bindings.update({p:sha(p) for p in [*source_files,ROOT/TOOLS]});check_hashes(bindings)
    root.mkdir();write(root/'tools.json',tools);write(root/'runtime.json',env)
    plan={'schema':'isaforge-v11-transfer-feature-plan-v1','status':'prepared-no-jobs','created_at_utc':now(),'policy':dict(POLICY),
        'input_root':os.path.relpath(input_root,root),'input_preparation_sha256':sha(input_root/'preparation.json'),'candidate_count':len(candidates),
        'program_formula_memberships':m['program_formula_memberships'],'frozen_tool':tool,'columns':list(v6.columns()),'selected_columns':list(v6.mapping_columns()),
        'selected_indices':v6.mapping_indices().tolist(),'feature_source_sha256':v6.source_hashes(),'tools_sha256':sha(root/'tools.json'),'runtime_sha256':sha(root/'runtime.json'),
        'files':[record(p,root) for p in sorted(bindings)],'source_paths':[os.path.relpath(p,root) for p in source_files],
        'maximum_candidate_extractions':len(candidates),'maximum_cold_graph_channels':3*len(candidates),
        'calls':{'native_jobs':0,'feature_extractions':0,'model_artifacts_loaded':0,'predictions':0,'labels':0,'fits':0},
        'scope':'All global original formulas; all memberships/familiar/zero cases preserved. Original336 feature pipeline, internal217 view and original generic-zero override unchanged. No refit/calibration/target labels. Source/SDK provenance is same-host, not OS hermeticity.'}
    write(root/'feature-plan.json',plan);return plan

def validate(root):
    root=Path(root).resolve();p=read(root/'feature-plan.json');need(p['schema']=='isaforge-v11-transfer-feature-plan-v1' and p['status']=='prepared-no-jobs' and equal(p['policy'],POLICY),'Exact input-only feature plan required')
    original=(root/p['input_root']).resolve();m,candidates,members,models,metadata,bindings=staged_inputs(original)
    source_files=sources();expected={*bindings,*source_files,ROOT/TOOLS};sealed={}
    for e in p['files']:
        path=inputs.checked(e,root);need(path not in sealed,'Repeated feature binding');sealed[path]=e['sha256']
    need(set(sealed)==expected and p['source_paths']==[os.path.relpath(f,root) for f in source_files],'Exact source/input closure required')
    tools=read(root/'tools.json');env=read(root/'runtime.json');native_tools.validate_tools(tools)
    need(equal(tools,read(ROOT/TOOLS)) and equal(env,runtime()) and p['tools_sha256']==sha(root/'tools.json') and p['runtime_sha256']==sha(root/'runtime.json'),'Tools/runtime changed')
    tool={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']}
    need(p['frozen_tool']==tool and all(d['frozen_tool']==tool and d['versions']=={n:env['versions'][n] for n in d['versions']} for d in metadata.values()),'Both frozen model/tool versions must match')
    need(p['input_preparation_sha256']==sha(original/'preparation.json') and p['candidate_count']==len(candidates) and p['maximum_candidate_extractions']==len(candidates) and p['maximum_cold_graph_channels']==3*len(candidates)
        and p['program_formula_memberships']==m['program_formula_memberships'] and p['columns']==list(v6.columns()) and p['selected_columns']==list(v6.mapping_columns()) and p['selected_indices']==v6.mapping_indices().tolist() and p['feature_source_sha256']==v6.source_hashes(),'Full feature pool/schema changed')
    sealed.update({root/n:sha(root/n) for n in ('feature-plan.json','tools.json','runtime.json')})
    sealed.update(tools_bindings(tools));sealed.update({Path(e['path']):e['sha256'] for e in env['files']})
    check_hashes(sealed);return p,candidates,models,tools,sealed

def local_payloads(bindings):
    generated={p for p in bindings if p.is_relative_to(ROOT/'generated')}
    if not generated:return set()
    manifest=ROOT/'results/2026-10-15-v11-reserved-transfer/raw-evidence-manifest.json'
    need(manifest in bindings and bindings[manifest]==sha(manifest)=='2639044e9019e49740da2746db8b8e19f69e83e137aa5a11310a453f0e5b400d','Exact historical local-payload anchor required')
    allowed={ROOT/'generated/v11-reserved-inputs/attempt-0000'/e['path'] for e in read(manifest)['omitted_local_failed_partials']}
    for name in ('ammunition','pm'):
        allowed.add(ROOT/'generated/v11-spooled-recovery/attempt-0000'/name/'capture/raw-spike.log.gz.partial')
        for phase,file in (('capture','raw-spike.log.gz'),('decode','decoded.jsonl.gz')):allowed.add(ROOT/'generated/v11-spooled-recovery/dtc-attempt-0000'/name/phase/file)
    need(generated<=allowed,'Unreviewed generated source/input cannot bypass Git binding');return generated

def git_freeze(bindings,commit,*,local_archive=None,installed_runtime=None):
    need(type(commit) is str and re.fullmatch('[0-9a-f]{40}',commit),'Exact commit required')
    exempt=local_payloads(bindings)
    installed_runtime=installed_runtime or {}
    need(not set(installed_runtime)&set(sources()) and all(bindings.get(path)==h and sha(path)==h for path,h in installed_runtime.items()),'Only exact validated installed runtime/tool files may be local')
    exempt.update(installed_runtime)
    if local_archive is not None:
        stage=local_archive.parent;completion=stage/'completion.json';manifest=stage/'raw-evidence.json';done=read(completion);raw=read(manifest)
        need(local_archive.name=='raw-evidence.zip' and stage.name=='attempt-0000' and stage.parent.name=='features' and done['complete'] is True
            and completion in bindings and manifest in bindings and local_archive in bindings and done['raw_archive_sha256']==raw['archive_sha256']==bindings[local_archive]==sha(local_archive),'Exact completed hash-bound local feature archive required')
        exempt.add(local_archive)
    for path,h in bindings.items():
        # Large local payloads and installed runtimes are hash-bound through the
        # committed input/tool manifests; they are not fabricated Git objects.
        if not path.is_relative_to(ROOT) or path in exempt:continue
        body=subprocess.check_output(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(body).hexdigest()==h,'Reviewed Git source/input bytes differ')

def guard(root,started=None,seconds=None):
    try:
        need(shutil.disk_usage(ROOT).free>=POLICY['minimum_free_bytes'],'Below8GiB free-space floor')
        total=0
        for path in root.rglob('*'):
            need(not path.is_symlink(),'Symlink in owned prediction stage')
            if path.is_file():
                size=path.stat().st_size;total+=size
                cap=POLICY['maximum_workspace_bytes'] if path.name=='raw-evidence.zip' else POLICY['maximum_log_bytes'] if path.suffix=='.log' else POLICY['maximum_raw_file_bytes']
                need(size<=cap,'Owned file/log byte cap reached')
        need(total<=POLICY['maximum_workspace_bytes'],'Whole-cache4GiB cap reached including archive/metadata')
        if started is not None:need(time.monotonic()-started<=seconds,'Owned stage deadline')
    except ValueError as e:raise AbortStage(str(e)) from e

class Owner:
    def __init__(self,environment):self.environment=dict(environment);self.lock=threading.Lock();self.active={};self.cancelled=False
    def launch(self,command,stream):
        with self.lock:
            need(not self.cancelled,'Owned stage canceled')
            p=subprocess.Popen(command,cwd=ROOT,env=self.environment,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);self.active[p.pid]=p;return p
    def remove(self,p):
        with self.lock:self.active.pop(p.pid,None)
    def cancel(self):
        with self.lock:self.cancelled=True;processes=list(self.active.values())
        return clean([('prediction-worker',p) for p in processes])

def run_worker(root,action,payload,folder,owner,hot,timeout):
    folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log';receipt=folder/'worker.json';result=folder/'result.json'
    need(not log.exists() and not receipt.exists() and not result.exists(),'Single fresh owned worker required')
    command=[sys.executable,str(Path(__file__).resolve()),action,'--root',str(root),'--payload',json.dumps(payload)]
    started=now();began=time.monotonic();process=None;error=None;errors=[];remaining=[]
    try:
        provenance(hot);guard(root)
        with log.open('xb') as stream:
            process=owner.launch(command,stream)
            while process.poll() is None:
                guard(root,began,timeout);time.sleep(POLICY['poll_seconds'])
            guard(root,began,timeout);need(process.returncode==0,'Owned worker failed; raw log retained')
        provenance(hot)
    except BaseException as e:error=e
    finally:
        if process is not None:
            errors,remaining=clean([(action,process)])
            if not errors and not remaining:owner.remove(process)
    r={'schema':'isaforge-v11-prediction-worker-v1','action':action,'command':command,'started_at_utc':started,'completed_at_utc':now(),'timeout_seconds':timeout,
        'returncode':process.returncode if process else None,'elapsed_seconds':time.monotonic()-began,'primary_error':repr(error) if error else None,
        'cleanup_errors':errors,'remaining_owned_children':remaining,'log_sha256':sha(log) if log.exists() else None,'runner_sha256':sha(__file__),
        'complete':error is None and not errors and not remaining}
    write(receipt,r)
    if error is not None:raise error
    need(r['complete'],'Owned process-group cleanup incomplete');return read(result)

def claim_check(root,payload,kind):
    need(kind in ('feature','prediction'),'Known released stage required');p=read(root/'feature-plan.json');claim=root/(kind+'-claim.json');c=read(claim)
    need(payload['claim_sha256']==sha(claim) and c['runner_sha256']==sha(__file__) and c['feature_plan_sha256']==sha(root/'feature-plan.json'),'Owned worker claim/source differs');return p

def feature_worker(root,payload):
    p=claim_check(root,payload,'feature');original=(root/p['input_root']).resolve();candidates=read(original/'candidates.json');c=next((c for c in candidates if c['formula']==payload['formula']),None)
    need(c is not None and c['candidate_id']==inputs.identifier(c['formula']),'Original outside complete released pool')
    key=c['candidate_id'].split(':')[1];stage=root/'features/attempt-0000';cache=stage/'cache'/key;folder=stage/'workers'/key
    need(payload['cache']==str(cache) and payload['result']==str(folder/'result.json') and not cache.exists() and not (folder/'result.json').exists(),'Fresh exact per-original cache/result required')
    x,records=v6.FeatureExtractor(cache,frozen_tool=p['frozen_tool']).matrix([{'formula':c['formula']}],workers=1)
    need(x.shape==(1,336) and len(records)==1 and records[0]['formula']==c['formula'],'Full original336 extraction required')
    write(folder/'result.json',{'candidate_id':c['candidate_id'],'cache_subdir':key,**records[0]})

class DirectoryArchive:
    def __init__(self,stage):self.stage=stage
    def read(self,name):
        p=PurePosixPath(name);need(not p.is_absolute() and '..' not in p.parts and str(p)==name and '\\' not in name,'Safe raw feature member required');return (self.stage/name).read_bytes()

def replay_worker(root,payload):
    p=claim_check(root,payload,'feature');stage=root/'features/attempt-0000';data=read(stage/'features.json');need(data['columns']==p['columns'] and len(data['records'])==p['candidate_count'],'Complete full feature matrix required')
    native=set();archive=DirectoryArchive(stage)
    for r in data['records']:
        _,channels=replay.replay_feature_record(archive,r,p['frozen_tool'],str(root));native.update(channels)
    need(2*p['candidate_count']<=len(native)<=3*p['candidate_count'],'Fresh per-original graph channel count differs')
    write(stage/'replay/result.json',{'complete':True,'records':len(data['records']),'full_columns':336,'native_channels':len(native),'features_sha256':sha(stage/'features.json'),'scope':'Shared frozen V13 graph/SOG/336 arithmetic replay; no second native extraction, solver or target label.'})

def archive(root,stage):
    began=time.monotonic();path=stage/'raw-evidence.zip';need(not path.exists(),'Fresh raw archive required');rows=[]
    paths=sorted(p for p in stage.rglob('*') if p.is_file())+sources()
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:
            guard(root,began,POLICY['archive_seconds']);n=p.relative_to(stage).as_posix() if p.is_relative_to(stage) else 'sources/'+p.relative_to(ROOT).as_posix()
            h=hashlib.sha256();size=0
            with p.open('rb') as incoming,z.open(n,'w',force_zip64=True) as outgoing:
                for b in iter(lambda:incoming.read(1024**2),b''):outgoing.write(b);h.update(b);size+=len(b);guard(root,began,POLICY['archive_seconds'])
            rows.append({'path':n,'sha256':h.hexdigest(),'bytes':size})
    guard(root,began,POLICY['archive_seconds']);write(stage/'raw-evidence.json',{'schema':'isaforge-v11-feature-archive-v1','archive_sha256':sha(path),'files':rows});guard(root,began,POLICY['archive_seconds'])

def approval(root,path,kind,plan,bindings):
    need(Path(path).resolve()==root/(kind+'-approval.json'),'Exact separate release path required');r=read(path)
    expected={'status':'approved-v11-full-pool-'+('features' if kind=='feature' else 'frozen-predictions'),'feature_plan_sha256':sha(root/'feature-plan.json'),'runner_sha256':sha(__file__),'candidate_count':plan['candidate_count']}
    if kind=='prediction':expected['feature_completion_sha256']=sha(root/'features/completion.json')
    need(all(k in r and equal(r[k],v) for k,v in expected.items()) and utc(r['reviewed_at_utc'])>=utc(plan['created_at_utc']),'Exact prior reviewed stage release required')
    tools=read(root/'tools.json');installed=tools_bindings(tools);installed.pop(ROOT/tools['inherited_inventory']['path'],None)
    installed.update({Path(e['path']):e['sha256'] for e in read(root/'runtime.json')['files']})
    git_freeze(bindings,r['freeze_commit'],local_archive=root/'features/attempt-0000/raw-evidence.zip' if kind=='prediction' else None,installed_runtime=installed);bindings[Path(path).resolve()]=sha(path);return r

def hot_bindings(root,bindings):
    # Huge inherited trace payloads are checked before/after each entire stage.
    # Executed sources/runtimes and every input used by inference/extraction are
    # checked before/after each worker; source payloads are never re-extracted.
    return {p:h for p,h in bindings.items() if not p.is_relative_to(ROOT/'generated')}

def extract(root,review_path):
    root=Path(root).resolve();p,candidates,models,tools,bindings=validate(root);review=approval(root,review_path,'feature',p,bindings)
    need(not(root/'feature-claim.json').exists() and not(root/'features').exists(),'One fresh complete-pool feature attempt required; no retry')
    guard(root);claim={'claimed_at_utc':now(),'runner_sha256':sha(__file__),'feature_plan_sha256':sha(root/'feature-plan.json'),'approval_sha256':sha(review_path),'maximum_extractions':len(candidates)}
    need(utc(claim['claimed_at_utc'])>=utc(review['reviewed_at_utc']),'Claim precedes release');write_claim(root/'feature-claim.json',claim);bindings[root/'feature-claim.json']=sha(root/'feature-claim.json')
    stage=root/'features/attempt-0000';stage.mkdir(parents=True);owner=Owner(tools['environment']);hot=hot_bindings(root,bindings);records={};failures=[];interruption=None;cleanup=[]
    def one(c):
        key=c['candidate_id'].split(':')[1];folder=stage/'workers'/key
        payload={'formula':c['formula'],'cache':str(stage/'cache'/key),'result':str(folder/'result.json'),'claim_sha256':sha(root/'feature-claim.json')}
        return run_worker(root,'feature-worker',payload,folder,owner,hot,POLICY['feature_worker_seconds'])
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        futures={pool.submit(one,c):c for c in candidates};pending=set(futures)
        try:
            while pending:
                guard(root);finished,pending=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
                for f in finished:
                    c=futures[f]
                    try:
                        r=f.result();need(r['formula']==c['formula'] and r['candidate_id']==c['candidate_id'],'Worker input identity differs');records[c['formula']]=r
                    except BaseException as e:
                        failures.append({'formula':c['formula'],'error':repr(e)})
                        if isinstance(e,AbortStage) or not isinstance(e,Exception):raise
                write(stage/'progress.json',{'completed':len(records),'total':len(candidates),'failures':failures})
        except BaseException:
            errors,remaining=cancel(owner);cleanup.extend(errors+remaining);raise
        finally:pool.shutdown(wait=True,cancel_futures=True)
        check_hashes(bindings);native_tools.validate_tools(tools);guard(root)
    except BaseException as e:
        errors,remaining=cancel(owner);cleanup.extend(errors+remaining);failures.append({'stage':'stop','error':repr(e)})
        if not isinstance(e,Exception):interruption=e
    ordered=[records[c['formula']] for c in candidates if c['formula'] in records];write(stage/'features.json',{'columns':p['columns'],'records':ordered})
    if not failures and not cleanup and len(ordered)==len(candidates):
        try:run_worker(root,'replay-worker',{'claim_sha256':sha(root/'feature-claim.json')},stage/'replay',owner,hot,POLICY['replay_worker_seconds'])
        except BaseException as e:
            failures.append({'stage':'raw-feature-replay','error':repr(e)})
            if not isinstance(e,Exception):interruption=e
    done={'schema':'isaforge-v11-transfer-feature-completion-v1','complete':not failures and not cleanup and len(ordered)==len(candidates),'failures':failures,'cleanup_failures':cleanup,'candidate_count':len(candidates),'completed_extractions':len(ordered),
        'feature_plan_sha256':sha(root/'feature-plan.json'),'features_sha256':sha(stage/'features.json'),'claim_sha256':sha(root/'feature-claim.json'),'approval_sha256':sha(review_path),'runner_sha256':sha(__file__),'completed_at_utc':now(),'new_predictions':0,'new_labels':0,'new_fits':0}
    try:archive(root,stage);guard(root);check_hashes(bindings);native_tools.validate_tools(tools);done.update(raw_archive_sha256=sha(stage/'raw-evidence.zip'),raw_manifest_sha256=sha(stage/'raw-evidence.json'))
    except BaseException as e:
        done['complete']=False;done['failures'].append({'stage':'archive-final','error':repr(e)})
        if not isinstance(e,Exception):interruption=e
    write(stage/'completion.json',done);write(root/'features/completion.json',done)
    try:guard(root);check_hashes(bindings);native_tools.validate_tools(tools)
    except BaseException as e:
        done['complete']=False;done['failures'].append({'stage':'completion-final','error':repr(e)});write(stage/'completion.json',done);write(root/'features/completion.json',done)
        if not isinstance(e,Exception):interruption=e
    if interruption is not None:raise interruption
    need(done['complete'],'Incomplete full-pool feature attempt retained; predictions blocked');return done

def completed_features(root,p,*,recompute=False):
    stage=root/'features/attempt-0000';d=read(root/'features/completion.json')
    need(equal(d,read(stage/'completion.json')) and d['schema']=='isaforge-v11-transfer-feature-completion-v1' and d['complete'] is True and d['failures']==d['cleanup_failures']==[]
        and inputs.integer(d['completed_extractions'])==inputs.integer(d['candidate_count'])==p['candidate_count'] and all(type(d[k]) is int and d[k]==0 for k in ('new_predictions','new_labels','new_fits')),'Complete all-original feature stage required')
    for key,path in [('feature_plan_sha256',root/'feature-plan.json'),('features_sha256',stage/'features.json'),('claim_sha256',root/'feature-claim.json'),('approval_sha256',root/'feature-approval.json'),('runner_sha256',Path(__file__)),('raw_archive_sha256',stage/'raw-evidence.zip'),('raw_manifest_sha256',stage/'raw-evidence.json')]:need(d[key]==sha(path),'Completed feature bytes differ')
    archive_data=read(stage/'raw-evidence.json');need(archive_data['archive_sha256']==d['raw_archive_sha256'],'Archive identity differs')
    members={e['path']:e for e in archive_data['files']};need(len(members)==len(archive_data['files']),'Duplicate raw archive member')
    with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
        need(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members),'Complete raw archive inventory required')
        for name,e in members.items():
            path=PurePosixPath(name);need(not path.is_absolute() and '..' not in path.parts and str(path)==name,'Safe raw member required')
            h=hashlib.sha256();size=0
            with z.open(name) as stream:
                for body in iter(lambda:stream.read(1024**2),b''):h.update(body);size+=len(body)
            need(h.hexdigest()==e['sha256'] and size==e['bytes'],'Raw feature member changed')
        for name in ('features.json','replay/result.json','replay/worker.json','replay/worker.log'):
            need(name in members and z.read(name)==(stage/name).read_bytes(),'Archived/live feature or replay bytes differ')
        if recompute:
            saved=json.loads(z.read('features.json'));native=set()
            for r in saved['records']:
                _,channels=replay.replay_feature_record(z,r,p['frozen_tool'],str(root));native.update(channels)
            need(2*p['candidate_count']<=len(native)<=3*p['candidate_count'],'Recomputed complete graph channels differ')
    data=read(stage/'features.json');need(data['columns']==p['columns'] and len(data['records'])==p['candidate_count'],'Full saved336 feature records required')
    r=read(stage/'replay/result.json');need(r['complete'] is True and inputs.integer(r['records'])==p['candidate_count'] and r['features_sha256']==d['features_sha256'],'Raw feature replay gate required')
    return d,data,{path:sha(path) for path in [root/'features/completion.json',stage/'completion.json',stage/'features.json',stage/'raw-evidence.json',stage/'raw-evidence.zip',stage/'replay/result.json',root/'feature-claim.json',root/'feature-approval.json']}

def inference_worker(root,payload):
    p=claim_check(root,payload,'prediction');_,data,_=completed_features(root,p,recompute=True);original=(root/p['input_root']).resolve();candidates=read(original/'candidates.json');models=read(original/'predictors.json')
    need([r['formula'] for r in data['records']]==[r['formula'] for r in candidates] and all(r['candidate_id']==c['candidate_id'] for r,c in zip(data['records'],candidates)),'Full ordered original feature identity required')
    x=np.asarray([r['values'] for r in data['records']],dtype=float);need(x.shape==(len(candidates),336) and np.isfinite(x).all() and np.all(x>=0),'Complete finite nonnegative full336 matrix required')
    points={}
    for name in ('V6','V9'):
        entry=models[name];path=inputs.checked(entry['artifact'],ROOT);need(sha(path)==inputs.MODELS[name][1],'Frozen artifact changed')
        model=v6.load_model(path);need(model.training_formula_count==inputs.MODELS[name][2] and model.kind=='mapping_v6' and model.frozen_tool==p['frozen_tool'] and model.calibration['status']=='uncalibrated','Exact frozen uncalibrated model required')
        points[name]=model.predict_features([{'candidate_id':c['candidate_id'],'formula':c['formula']} for c in candidates],x)
    write(root/'predictions/attempt-0000/result.json',{'schema':'isaforge-v11-frozen-point-predictions-v1','candidate_count':len(candidates),'models':points,'feature_plan_sha256':sha(root/'feature-plan.json'),'features_sha256':sha(root/'features/attempt-0000/features.json'),
        'input_preparation_sha256':p['input_preparation_sha256'],'predictor_manifest_sha256':sha(original/'predictors.json'),'membership_sha256':sha(original/'memberships.json'),'runner_sha256':sha(__file__),
        'scope':'Original336 features, unchanged internal217 selection and generic-zero override; raw uncalibrated V6/V9 points. No training/calibration/target reads.'})

def predict(root,review_path):
    root=Path(root).resolve();p,candidates,models,tools,bindings=validate(root);d,data,feature_bindings=completed_features(root,p);bindings.update(feature_bindings)
    review=approval(root,review_path,'prediction',p,bindings);need(utc(review['reviewed_at_utc'])>=utc(d['completed_at_utc']),'Prediction approval precedes complete features')
    need(not(root/'prediction-claim.json').exists() and not(root/'predictions').exists(),'Single fresh inference attempt required; no retry');guard(root)
    write_claim(root/'prediction-claim.json',{'claimed_at_utc':now(),'runner_sha256':sha(__file__),'feature_plan_sha256':sha(root/'feature-plan.json'),'approval_sha256':sha(review_path),'feature_completion_sha256':sha(root/'features/completion.json'),'maximum_predictions':2*len(candidates)})
    bindings[root/'prediction-claim.json']=sha(root/'prediction-claim.json');stage=root/'predictions/attempt-0000';stage.mkdir(parents=True);owner=Owner(tools['environment']);failures=[];interruption=None;result=None
    try:
        result=run_worker(root,'inference-worker',{'claim_sha256':sha(root/'prediction-claim.json')},stage,owner,hot_bindings(root,bindings),POLICY['inference_worker_seconds'])
        original=(root/p['input_root']).resolve()
        expected={'schema':'isaforge-v11-frozen-point-predictions-v1','candidate_count':len(candidates),'feature_plan_sha256':sha(root/'feature-plan.json'),
            'features_sha256':sha(root/'features/attempt-0000/features.json'),'input_preparation_sha256':p['input_preparation_sha256'],
            'predictor_manifest_sha256':sha(original/'predictors.json'),'membership_sha256':sha(original/'memberships.json'),'runner_sha256':sha(__file__)}
        need(all(k in result and equal(result[k],v) for k,v in expected.items()) and set(result['models'])=={'V6','V9'},'Full paired prediction/input gate required')
        for points in result['models'].values():
            need([r['candidate_id'] for r in points]==[c['candidate_id'] for c in candidates] and [r['formula'] for r in points]==[c['formula'] for c in candidates],'Every original needs exactly one ordered point per model')
            need(all(type(r['predicted_lut4']) in (int,float) and np.isfinite(r['predicted_lut4']) and r['predicted_lut4']>=0 and r['upper_lut4'] is None and r['calibration_status']=='uncalibrated' for r in points),'Finite raw uncalibrated points required')
        check_hashes(bindings);native_tools.validate_tools(tools);guard(root)
    except BaseException as e:
        errors,remaining=cancel(owner);failures.append({'error':repr(e),'cleanup_errors':errors,'remaining_owned_children':remaining})
        if not isinstance(e,Exception):interruption=e
    done={'schema':'isaforge-v11-frozen-point-completion-v1','complete':not failures,'failures':failures,'candidate_count':len(candidates),'prediction_count':2*len(candidates) if not failures else None,
        'feature_completion_sha256':sha(root/'features/completion.json'),'feature_plan_sha256':sha(root/'feature-plan.json'),'approval_sha256':sha(review_path),'claim_sha256':sha(root/'prediction-claim.json'),
        'point_predictions_sha256':sha(stage/'result.json') if (stage/'result.json').exists() else None,'runner_sha256':sha(__file__),'completed_at_utc':now(),'new_labels':0,'new_fits':0,'calibration_jobs':0,
        'worker_receipt_sha256':sha(stage/'worker.json') if (stage/'worker.json').exists() else None,'worker_log_sha256':sha(stage/'worker.log') if (stage/'worker.log').exists() else None,
        'input_preparation_sha256':p['input_preparation_sha256'],'tools_sha256':sha(root/'tools.json'),'runtime_sha256':sha(root/'runtime.json'),
        'raw_archive_portability':'Exact completed feature raw-evidence.zip may remain local and hash-bound by committed completion/manifest; Git alone is not a self-contained native-cache replay.',
        'release':'Frozen paired full-pool points only. Separate complete-pool target release remains required.'}
    write(stage/'completion.json',done);write(root/'predictions/completion.json',done)
    try:guard(root);check_hashes(bindings);native_tools.validate_tools(tools)
    except BaseException as e:
        done['complete']=False;done['failures'].append({'stage':'completion-final','error':repr(e)});write(stage/'completion.json',done);write(root/'predictions/completion.json',done)
        if not isinstance(e,Exception):interruption=e
    if interruption is not None:raise interruption
    need(done['complete'],'Incomplete frozen inference attempt retained; target release blocked')
    try:
        sealed,rows,members,point_bindings=validate_predictions(root)
        write(root/'point-freeze.json',{'schema':'isaforge-v11-transfer-point-freeze-v1','complete':True,'frozen_at_utc':now(),'candidate_count':len(rows),'prediction_count':2*len(rows),
            'feature_plan_sha256':sha(root/'feature-plan.json'),'input_preparation_sha256':p['input_preparation_sha256'],'feature_completion_sha256':sha(root/'features/completion.json'),
            'prediction_completion_sha256':sha(root/'predictions/completion.json'),'point_predictions_sha256':sha(stage/'result.json'),
            'columns':p['columns'],'selected_columns':p['selected_columns'],'selected_indices':p['selected_indices'],'frozen_tool':p['frozen_tool'],
            'files':[record(path,root) for path in sorted(point_bindings)],'fits':0,'calibration_jobs':0,'labels_read':0,
            'scope':'Complete paired original-RTL V6/V9 point predictions before target release; same-host installed runtime/local raw-archive dependencies, not self-contained Git replay.'})
        guard(root);check_hashes(point_bindings)
    except BaseException as e:
        done['complete']=False;done['failures'].append({'stage':'point-freeze-final','error':repr(e)});write(stage/'completion.json',done);write(root/'predictions/completion.json',done)
        if not isinstance(e,Exception):raise
        raise ValueError('Incomplete point-freeze retained; target release blocked') from e
    return done

def validate_predictions(root):
    """Authenticate saved complete points; never load models or predict again."""
    root=Path(root).resolve();p,candidates,models,tools,bindings=validate(root);_,data,feature_bindings=completed_features(root,p);bindings.update(feature_bindings)
    original=(root/p['input_root']).resolve();members=read(original/'memberships.json');stage=root/'predictions/attempt-0000';d=read(root/'predictions/completion.json');result=read(stage/'result.json')
    need(equal(d,read(stage/'completion.json')) and d['schema']=='isaforge-v11-frozen-point-completion-v1' and d['complete'] is True and d['failures']==[], 'Complete frozen prediction stage required')
    need(all(type(d[k]) is int and d[k]==n for k,n in [('candidate_count',len(candidates)),('prediction_count',2*len(candidates)),('new_labels',0),('new_fits',0),('calibration_jobs',0)]),'Complete paired prediction count/scope required')
    paths={'feature_completion_sha256':root/'features/completion.json','feature_plan_sha256':root/'feature-plan.json','approval_sha256':root/'prediction-approval.json','claim_sha256':root/'prediction-claim.json',
        'point_predictions_sha256':stage/'result.json','runner_sha256':Path(__file__),'worker_receipt_sha256':stage/'worker.json','worker_log_sha256':stage/'worker.log','tools_sha256':root/'tools.json','runtime_sha256':root/'runtime.json'}
    need(all(d[k]==sha(path) for k,path in paths.items()) and d['input_preparation_sha256']==p['input_preparation_sha256'],'Frozen prediction provenance differs')
    review=read(root/'prediction-approval.json');claim=read(root/'prediction-claim.json');worker=read(stage/'worker.json')
    need(review['status']=='approved-v11-full-pool-frozen-predictions' and review['runner_sha256']==sha(__file__) and review['feature_plan_sha256']==sha(root/'feature-plan.json') and review['feature_completion_sha256']==sha(root/'features/completion.json') and review['candidate_count']==len(candidates),'Frozen inference approval differs')
    need(claim['runner_sha256']==sha(__file__) and claim['feature_plan_sha256']==sha(root/'feature-plan.json') and claim['approval_sha256']==sha(root/'prediction-approval.json') and claim['feature_completion_sha256']==sha(root/'features/completion.json') and claim['maximum_predictions']==2*len(candidates),'Frozen inference claim differs')
    need(worker['schema']=='isaforge-v11-prediction-worker-v1' and worker['action']=='inference-worker' and worker['complete'] is True and type(worker['returncode']) is int and worker['returncode']==0 and worker['primary_error'] is None and worker['cleanup_errors']==worker['remaining_owned_children']==[] and worker['runner_sha256']==sha(__file__) and worker['log_sha256']==sha(stage/'worker.log'),'Successful owned inference receipt required')
    command=[sys.executable,str(Path(__file__).resolve()),'inference-worker','--root',str(root),'--payload',json.dumps({'claim_sha256':sha(root/'prediction-claim.json')})]
    need(worker['command']==command and worker['timeout_seconds']==POLICY['inference_worker_seconds'] and 0<=worker['elapsed_seconds']<=POLICY['inference_worker_seconds']+5,'Fixed owned inference command/deadline required')
    need(utc(read(root/'features/completion.json')['completed_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(claim['claimed_at_utc'])<=utc(worker['started_at_utc'])<=utc(worker['completed_at_utc'])<=utc(d['completed_at_utc']),'Frozen point stage chronology differs')
    expected={'schema':'isaforge-v11-frozen-point-predictions-v1','candidate_count':len(candidates),'feature_plan_sha256':sha(root/'feature-plan.json'),'features_sha256':sha(root/'features/attempt-0000/features.json'),
        'input_preparation_sha256':p['input_preparation_sha256'],'predictor_manifest_sha256':sha(original/'predictors.json'),'membership_sha256':sha(original/'memberships.json'),'runner_sha256':sha(__file__)}
    need(all(k in result and equal(result[k],v) for k,v in expected.items()) and set(result['models'])=={'V6','V9'},'Exact paired point inputs required')
    need([r['formula'] for r in data['records']]==[r['formula'] for r in candidates],'Full original feature order differs')
    x=np.asarray([r['values'] for r in data['records']],dtype=float);need(x.shape==(len(candidates),336) and np.isfinite(x).all() and np.all(x>=0),'Full finite336 features required')
    zero=v6.v5.original_zero(x[:,:313])
    for points in result['models'].values():
        need([r['candidate_id'] for r in points]==[c['candidate_id'] for c in candidates] and [r['formula'] for r in points]==[c['formula'] for c in candidates],'Every original needs one ordered point')
        need(all(type(r['predicted_lut4']) in (int,float) and np.isfinite(r['predicted_lut4']) and r['predicted_lut4']>=0 and r['upper_lut4'] is None and r['calibration_status']=='uncalibrated' and (not zero[i] or r['predicted_lut4']==0) for i,r in enumerate(points)),'Invalid raw point/original-zero override')
    paths_to_bind={*paths.values(),root/'predictions/completion.json',stage/'completion.json'};bindings.update({path:sha(path) for path in paths_to_bind});check_hashes(bindings)
    return d,candidates,members,bindings

def validate_point_freeze(root):
    root=Path(root).resolve();d,candidates,members,bindings=validate_predictions(root);f=read(root/'point-freeze.json');p=read(root/'feature-plan.json')
    expected={'schema':'isaforge-v11-transfer-point-freeze-v1','complete':True,'candidate_count':len(candidates),'prediction_count':2*len(candidates),'feature_plan_sha256':sha(root/'feature-plan.json'),
        'input_preparation_sha256':p['input_preparation_sha256'],'feature_completion_sha256':sha(root/'features/completion.json'),'prediction_completion_sha256':sha(root/'predictions/completion.json'),
        'point_predictions_sha256':sha(root/'predictions/attempt-0000/result.json'),'columns':p['columns'],'selected_columns':p['selected_columns'],'selected_indices':p['selected_indices'],'frozen_tool':p['frozen_tool'],'fits':0,'calibration_jobs':0,'labels_read':0}
    need(all(k in f and equal(f[k],v) for k,v in expected.items()) and utc(f['frozen_at_utc'])>=utc(d['completed_at_utc']),'Complete exact frozen point seal required')
    need(equal(f['files'],[record(path,root) for path in sorted(bindings)]),'Exact point-freeze source/input/feature/model/runtime file closure required')
    bindings[root/'point-freeze.json']=sha(root/'point-freeze.json');return f,candidates,members,bindings

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','validate','validate-points','extract','predict','feature-worker','replay-worker','inference-worker'));p.add_argument('--root',type=Path,required=True);p.add_argument('--input-root',type=Path);p.add_argument('--approval',type=Path);p.add_argument('--payload')
    a=p.parse_args()
    if a.action.endswith('-worker'):
        need(a.payload is not None,'Worker payload required');{'feature-worker':feature_worker,'replay-worker':replay_worker,'inference-worker':inference_worker}[a.action](a.root.resolve(),json.loads(a.payload));sys.exit(0)
    if a.action=='prepare':need(a.input_root is not None,'Input stage required');r=prepare(a.input_root,a.root)
    elif a.action=='validate':r={'status':'valid','candidate_count':validate(a.root)[0]['candidate_count']}
    elif a.action=='validate-points':r={'status':'valid','candidate_count':validate_point_freeze(a.root)[0]['candidate_count']}
    else:need(a.approval is not None,'Separate stage approval required');r=(extract if a.action=='extract' else predict)(a.root,a.approval)
    print(json.dumps(r,indent=2,allow_nan=False))

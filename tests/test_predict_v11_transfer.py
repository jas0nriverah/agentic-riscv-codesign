"""Synthetic full-pool release/worker/inference tests, never real native/models."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import pytest
import numpy as np
REAL_POPEN=subprocess.Popen
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('predict_v11_transfer',ROOT/'scripts/predict_v11_transfer.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture(autouse=True)
def forbidden(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('Unreleased native process forbidden'))
    monkeypatch.setattr(m.v6,'load_model',lambda *a,**k:pytest.fail('Real model loading forbidden'))
    monkeypatch.setattr(m.v6.FeatureExtractor,'matrix',lambda *a,**k:pytest.fail('Real feature extraction forbidden'))
    for name in ('fit','measurement_inputs','old_inputs','extract_features'):
        monkeypatch.setattr(m.replay,name,lambda *a,_name=name,**k:pytest.fail('Forbidden historical job/target path '+_name))
    for name in ('collect','prepare_measurement'):
        monkeypatch.setattr(m.native_tools,name,lambda *a,_name=name,**k:pytest.fail('Forbidden target-job path '+_name))
    monkeypatch.setattr(m.replay.ExtraTreesRegressor,'fit',lambda *a,**k:pytest.fail('Fitting forbidden'))

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m.inputs,'ROOT',tmp_path)
    input_root=tmp_path/'results/inputs';input_root.mkdir(parents=True);source=tmp_path/'scripts/source.py';source.parent.mkdir();source.write_text('SYNTHETIC source')
    tools={'executables':{'yosys':{'path':'SYNTHETIC-yosys','version':'SYNTHETIC','sha256':'SYNTHETIC-sha'}},'environment':{'PATH':'SYNTHETIC','SDKROOT':'SYNTHETIC-sdk'},'inherited_inventory':{'path':'results/native-history.json'}}
    env={'python':'SYNTHETIC','versions':{'numpy':'SYNTHETIC'},'files':[]};tool={'version':'SYNTHETIC','executable_sha256':'SYNTHETIC-sha'}
    monkeypatch.setattr(m,'runtime',lambda:copy.deepcopy(env));monkeypatch.setattr(m.native_tools,'validate_tools',lambda t:None);monkeypatch.setattr(m,'tools_bindings',lambda t:{})
    monkeypatch.setattr(m,'sources',lambda:[source]);m.write(tmp_path/m.TOOLS,tools)
    formulas={'ammunition':'add(in0,in1)','audiobeam':'xor(in0,in1)','pm':'sub(in0,in1)','fmref':'add(in0,in1)','fac':'or(in0,in1)','recursion':None}
    by_formula={};members=[];produced=[]
    for name,family in m.inputs.FAMILIES.items():
        formula=formulas[name];ids=[m.inputs.identifier(formula)] if formula else []
        if formula:by_formula.setdefault(formula,[]).append(name)
        members.append({'program':name,'family':family,'status':'complete' if formula else 'empty','canonical_count':len(ids),'canonical_ids':ids})
        p=input_root/'original-candidate-files'/(name+'.json');m.write(p,[{'formula':formula,'runs':987654321}] if formula else []);produced.append(p)
    candidates=[{'formula':f,'candidate_id':m.inputs.identifier(f),'programs':names,'families':sorted({m.inputs.FAMILIES[n] for n in names})} for f,names in sorted(by_formula.items())]
    recovery=tmp_path/'results/recovery';recovered={};completed=[]
    for r in members:
        name=r['program'];rows=m.read(input_root/'original-candidate-files'/(name+'.json'));path=recovery/'candidates'/(name+'.json');m.write(path,rows)
        recovered[name]={'family':r['family'],'status':r['status'],'candidate_count':r['canonical_count'],'candidate_file':m.record(path,recovery)}
        completed.extend({**x,'benchmark':name,'family':r['family']} for x in rows)
    m.write(recovery/'run/attempt-0000/completed-rows.json',completed);audit=input_root/'independent-result-audit.json';m.write(audit,{'scope':'SYNTHETIC reviewed report'});produced.append(audit)
    monkeypatch.setattr(m.inputs,'authenticate_recovery',lambda source,path,h:(copy.deepcopy(recovered),{'independence':'SYNTHETIC shared helpers'}, {audit:m.sha(audit)}))
    models={};modeldefs={}
    for name,count in [('V6',1665),('V9',1713)]:
        artifact=tmp_path/f'models/{name}.joblib';artifact.parent.mkdir(exist_ok=True);artifact.write_bytes(('SYNTHETIC '+name).encode());modeldefs[name]=(str(artifact.relative_to(tmp_path)),m.sha(artifact),count)
        d={'schema':'isaforge-v6-model-v1','artifact_sha256':m.sha(artifact),'training_formula_count':count,'kind':'mapping_v6','calibration':{'status':'uncalibrated'},
            'feature_columns':list(m.v6.columns()),'mapping_columns':list(m.v6.mapping_columns()),'versions':env['versions'],'frozen_tool':tool,'runtime_source_sha256':m.v6.source_hashes()}
        m.write(artifact.with_suffix('.json'),d);produced.extend([artifact,artifact.with_suffix('.json')])
        models[name]={'artifact':m.record(artifact,tmp_path),'metadata':m.record(artifact.with_suffix('.json'),tmp_path)}
    monkeypatch.setattr(m.inputs,'MODELS',modeldefs)
    historical={p:m.sha(p) for p in produced if p.name.endswith('.joblib') or (p.parent.name=='models' and p.suffix=='.json')}
    monkeypatch.setattr(m.inputs,'sources',lambda:[]);monkeypatch.setattr(m.inputs,'historical_inputs',lambda:({}, {'V6':set(),'V9':set()},copy.deepcopy(models),historical.copy()))
    for name,data in [('candidates.json',candidates),('memberships.json',members),('predictors.json',models),('overlap.json',m.inputs.overlap(candidates,{}, {'V6':set(),'V9':set()})),('pre-reservation-reference.json',[]),('proposed-budget.json',m.inputs.budget(4,5))]:
        p=input_root/name;m.write(p,data);produced.append(p)
    manifest={'schema':'isaforge-v11-model-comparison-inputs-v1','status':'prepared-inputs-only','calls':{k:0 for k in ('native_jobs','feature_extractions','model_artifacts_loaded','predictions','target_label_files_opened','fits','new_solver_queries')},
        'files':[m.record(p,input_root) for p in produced],'unique_canonical_originals':4,'program_formula_memberships':5,
        'source_root':os.path.relpath(recovery,input_root),'reviewed_audit':m.record(audit,input_root),'audit_independence':'SYNTHETIC shared helpers'}
    m.write(input_root/'preparation.json',manifest);root=tmp_path/'results/prediction';plan=m.prepare(input_root,root)
    return input_root,root,plan,candidates,models,tools,source

def test_prepare_validate_is_input_only_shared336_217_and_sdk_environment(prepared):
    input_root,root,p,candidates,models,tools,source=prepared
    plan,rows,_,observed,bindings=m.validate(root)
    assert len(rows)==4 and plan['maximum_cold_graph_channels']==12 and len(plan['columns'])==336 and len(plan['selected_columns'])==217
    assert observed['environment']['SDKROOT']=='SYNTHETIC-sdk' and all(n==0 for n in plan['calls'].values()) and source in bindings
    assert not(root/'features').exists() and not(root/'predictions').exists()
    with pytest.raises(ValueError,match='Fresh separate'):m.prepare(input_root,root)

@pytest.mark.parametrize('poison',['source','candidate','modelmissing','modelbytes','tools','runtime','policy','inputmanifest'])
def test_validate_rejects_mutation(prepared,poison):
    original,root,p,candidates,models,tools,source=prepared
    if poison=='source':source.write_text('POISON')
    elif poison=='candidate':(original/'candidates.json').write_text('[]')
    elif poison=='modelmissing':(m.ROOT/models['V6']['artifact']['path']).unlink()
    elif poison=='modelbytes':(m.ROOT/models['V9']['artifact']['path']).write_bytes(b'POISON')
    elif poison=='tools':(root/'tools.json').write_text('{}')
    elif poison=='runtime':(root/'runtime.json').write_text('{}')
    elif poison=='policy':p['policy']['workers']=3;m.write(root/'feature-plan.json',p)
    else:(original/'preparation.json').write_text('{}')
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):m.validate(root)

def release(root,kind,count,monkeypatch):
    monkeypatch.setattr(m,'git_freeze',lambda *a,**k:None)
    r={'status':'approved-v11-full-pool-'+('features' if kind=='feature' else 'frozen-predictions'),'feature_plan_sha256':m.sha(root/'feature-plan.json'),
        'runner_sha256':m.sha(m.__file__),'candidate_count':count,'reviewed_at_utc':m.now(),'freeze_commit':'a'*40}
    if kind=='prediction':r['feature_completion_sha256']=m.sha(root/'features/completion.json')
    path=root/(kind+'-approval.json');m.write(path,r);return path

def fake_feature_runner(monkeypatch,fail=None):
    state={'calls':[],'active':0,'maximum':0};lock=threading.Lock()
    def run(root,action,payload,folder,owner,hot,timeout):
        folder.mkdir(parents=True,exist_ok=True);(folder/'worker.log').write_text('SYNTHETIC worker');m.write(folder/'worker.json',{'complete':True,'scope':'SYNTHETIC worker'})
        if action=='feature-worker':
            with lock:state['calls'].append(payload['formula']);state['active']+=1;state['maximum']=max(state['maximum'],state['active'])
            try:
                time.sleep(.01)
                if payload['formula']==fail:raise RuntimeError('Synthetic original failure; no retry')
                key=m.inputs.identifier(payload['formula']).split(':')[1]
                return {'formula':payload['formula'],'candidate_id':m.inputs.identifier(payload['formula']),'cache_subdir':key,'values':[0.]*336}
            finally:
                with lock:state['active']-=1
        assert action=='replay-worker';d={'complete':True,'records':len(state['calls']),'features_sha256':m.sha(root/'features/attempt-0000/features.json')};m.write(folder/'result.json',d);return d
    monkeypatch.setattr(m,'run_worker',run);return state

def test_all_original_features_once_then_replay_archive_and_separate_release(prepared,monkeypatch):
    _,root,p,candidates,_,_,_=prepared;state=fake_feature_runner(monkeypatch);review=release(root,'feature',4,monkeypatch)
    done=m.extract(root,review);assert done['complete'] and done['completed_extractions']==4 and len(state['calls'])==len(set(state['calls']))==4 and state['maximum']<=2
    d,data,b=m.completed_features(root,p);assert d['complete'] and len(data['records'])==4 and len(data['columns'])==336 and not(root/'predictions').exists()
    with pytest.raises(ValueError,match='fresh complete-pool'):m.extract(root,review)

def test_single_feature_failure_retained_full_pool_no_replacement_or_inference(prepared,monkeypatch):
    _,root,p,candidates,_,_,_=prepared;state=fake_feature_runner(monkeypatch,fail=candidates[0]['formula']);review=release(root,'feature',4,monkeypatch)
    with pytest.raises(ValueError,match='Incomplete full-pool'):m.extract(root,review)
    d=m.read(root/'features/completion.json');assert d['complete'] is False and d['completed_extractions']==3 and len(state['calls'])==4 and len(set(state['calls']))==4
    assert (root/'features/attempt-0000/raw-evidence.zip').exists() and not(root/'features/attempt-0000/replay').exists()
    with pytest.raises(ValueError,match='Complete all-original'):m.completed_features(root,p)

def test_archive_failure_cannot_publish_feature_success(prepared,monkeypatch):
    _,root,_,_,_,_,_=prepared;fake_feature_runner(monkeypatch);review=release(root,'feature',4,monkeypatch)
    monkeypatch.setattr(m,'archive',lambda *a:(_ for _ in ()).throw(TimeoutError('Synthetic archive deadline')))
    with pytest.raises(ValueError,match='Incomplete full-pool'):m.extract(root,review)
    assert m.read(root/'features/completion.json')['complete'] is False

@pytest.mark.parametrize('poison',['features.json','replay/result.json','replay/worker.json'])
def test_live_feature_changes_cannot_hide_behind_reauthenticated_receipts(prepared,monkeypatch,poison):
    _,root,p,_,_,_,_=prepared;fake_feature_runner(monkeypatch);review=release(root,'feature',4,monkeypatch);m.extract(root,review)
    stage=root/'features/attempt-0000';value=m.read(stage/poison)
    if poison=='features.json':value['records'][0]['values'][0]=123
    elif poison=='replay/result.json':value['extra']='POISON'
    else:value['complete']=False
    m.write(stage/poison,value)
    # Even updating the outer digest cannot make it agree with the sealed ZIP.
    done=m.read(stage/'completion.json')
    if poison=='features.json':done['features_sha256']=m.sha(stage/poison)
    m.write(stage/'completion.json',done);m.write(root/'features/completion.json',done)
    with pytest.raises(ValueError,match='Archived/live'):m.completed_features(root,p)

def test_cancel_failure_does_not_mask_retained_stage_error(prepared,monkeypatch):
    _,root,_,_,_,_,_=prepared;review=release(root,'feature',4,monkeypatch)
    monkeypatch.setattr(m,'run_worker',lambda *a,**k:(_ for _ in ()).throw(m.AbortStage('SYNTHETIC source/resource breach')))
    monkeypatch.setattr(m.Owner,'cancel',lambda self:(_ for _ in ()).throw(PermissionError('SYNTHETIC cancel failure')))
    with pytest.raises(ValueError,match='Incomplete full-pool'):m.extract(root,review)
    d=m.read(root/'features/completion.json');assert not d['complete'] and d['cleanup_failures'] and any('source/resource' in e['error'] for e in d['failures'])

def test_atomic_claim_and_generated_source_cannot_bypass_git(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);path=tmp_path/'claim.json';m.write_claim(path,{'first':True})
    with pytest.raises(FileExistsError):m.write_claim(path,{'second':True})
    assert m.read(path)=={'first':True}
    generated=tmp_path/'generated/evil-source.py';generated.parent.mkdir();generated.write_text('POISON')
    with pytest.raises(ValueError,match='local-payload anchor'):m.git_freeze({generated:m.sha(generated)},'a'*40)

def test_feature_worker_strips_all_outcome_metadata_and_blocks_bad_cache(prepared,monkeypatch):
    _,root,p,candidates,_,_,_=prepared;c=candidates[0];key=c['candidate_id'].split(':')[1];stage=root/'features/attempt-0000';folder=stage/'workers'/key
    m.write(root/'feature-claim.json',{'runner_sha256':m.sha(m.__file__),'feature_plan_sha256':m.sha(root/'feature-plan.json')})
    payload={'formula':c['formula'],'cache':str(stage/'cache'/key),'result':str(folder/'result.json'),'claim_sha256':m.sha(root/'feature-claim.json')};seen=[]
    class Extractor:
        def __init__(self,cache,**kw):assert cache==Path(payload['cache']) and kw['frozen_tool']==p['frozen_tool']
        def matrix(self,rows,workers):seen.append(rows);assert workers==1;return np.zeros((1,336)),[{'formula':c['formula'],'values':[0.]*336}]
    monkeypatch.setattr(m.v6,'FeatureExtractor',Extractor);m.feature_worker(root,payload)
    assert seen==[[{'formula':c['formula']}]]
    with pytest.raises(ValueError,match='Fresh exact'):m.feature_worker(root,payload)

def test_inference_worker_exact_two_frozen_models_full336_no_fit(prepared,monkeypatch):
    original,root,p,candidates,models,_,_=prepared
    m.write(root/'prediction-claim.json',{'runner_sha256':m.sha(m.__file__),'feature_plan_sha256':m.sha(root/'feature-plan.json')})
    values=np.zeros((4,336));values[1,0]=3
    data={'records':[{'formula':c['formula'],'candidate_id':c['candidate_id'],'values':v.tolist()} for c,v in zip(candidates,values)]}
    stage=root/'features/attempt-0000';m.write(stage/'features.json',{'synthetic':'bound feature bytes'})
    def gate(*a,**kwargs):assert kwargs=={'recompute':True};return {},data,{}
    monkeypatch.setattr(m,'completed_features',gate);loaded=[];predicted=[]
    class Model:
        kind='mapping_v6';frozen_tool=p['frozen_tool'];calibration={'status':'uncalibrated'}
        def __init__(self,name):self.name=name;self.training_formula_count=m.inputs.MODELS[name][2]
        def predict_features(self,rows,x):
            assert x.shape==(4,336) and np.array_equal(x,values);predicted.append((self.name,copy.deepcopy(rows)))
            return [{'candidate_id':r['candidate_id'],'formula':r['formula'],'predicted_lut4':0.,'upper_lut4':None,'calibration_status':'uncalibrated'} for r in rows]
    def load(path):
        name=next(n for n in models if Path(m.ROOT/models[n]['artifact']['path'])==path);loaded.append(name);return Model(name)
    monkeypatch.setattr(m.v6,'load_model',load);m.inference_worker(root,{'claim_sha256':m.sha(root/'prediction-claim.json')})
    result=m.read(root/'predictions/attempt-0000/result.json');assert loaded==['V6','V9'] and len(predicted)==2 and len(result['models']['V6'])==len(result['models']['V9'])==4
    assert all(set(r)=={'candidate_id','formula'} for _,rows in predicted for r in rows)

@pytest.mark.parametrize('poison',[None,'missingpoint','badfeaturehash','negativepoint'])
def test_prediction_release_is_after_complete_features_and_checks_every_point(prepared,monkeypatch,poison):
    original,root,p,candidates,models,_,_=prepared;fake_feature_runner(monkeypatch);m.extract(root,release(root,'feature',4,monkeypatch))
    review=release(root,'prediction',4,monkeypatch);calls=[]
    def run(root,action,payload,folder,owner,hot,timeout):
        calls.append(action);assert action=='inference-worker' and timeout==300
        folder.mkdir(parents=True,exist_ok=True);(folder/'worker.log').write_text('SYNTHETIC inference')
        stamp=m.now();m.write(folder/'worker.json',{'schema':'isaforge-v11-prediction-worker-v1','action':action,'complete':True,'returncode':0,'primary_error':None,'cleanup_errors':[],'remaining_owned_children':[],
            'runner_sha256':m.sha(m.__file__),'log_sha256':m.sha(folder/'worker.log'),'started_at_utc':stamp,'completed_at_utc':stamp,
            'command':[sys.executable,str(Path(m.__file__).resolve()),action,'--root',str(root),'--payload',json.dumps(payload)],'timeout_seconds':300,'elapsed_seconds':.01})
        points=[{'candidate_id':c['candidate_id'],'formula':c['formula'],'predicted_lut4':0.,'upper_lut4':None,'calibration_status':'uncalibrated'} for c in candidates]
        r={'schema':'isaforge-v11-frozen-point-predictions-v1','candidate_count':4,'models':{'V6':copy.deepcopy(points),'V9':copy.deepcopy(points)},
            'feature_plan_sha256':m.sha(root/'feature-plan.json'),'features_sha256':m.sha(root/'features/attempt-0000/features.json'),
            'input_preparation_sha256':p['input_preparation_sha256'],'predictor_manifest_sha256':m.sha(original/'predictors.json'),'membership_sha256':m.sha(original/'memberships.json'),'runner_sha256':m.sha(m.__file__)}
        if poison=='missingpoint':r['models']['V9'].pop()
        elif poison=='badfeaturehash':r['features_sha256']='f'*64
        elif poison=='negativepoint':r['models']['V6'][0]['predicted_lut4']=-1
        m.write(folder/'result.json',r);return r
    monkeypatch.setattr(m,'run_worker',run)
    if poison:
        with pytest.raises(ValueError,match='Incomplete frozen inference'):m.predict(root,review)
    else:
        d=m.predict(root,review);assert d['complete'] and d['prediction_count']==8 and d['new_labels']==d['new_fits']==0
        freeze,rows,members,bindings=m.validate_point_freeze(root);assert freeze['complete'] and len(rows)==4 and len(members)==6 and root/'point-freeze.json' in bindings
    assert calls==['inference-worker'] and m.read(root/'predictions/completion.json')['complete'] is (poison is None)
    with pytest.raises(ValueError,match='Single fresh'):m.predict(root,review)

def test_exact_installed_runtime_and_completed_archive_can_be_local(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);source=tmp_path/'scripts/source.py';source.parent.mkdir();source.write_text('SYNTHETIC committed source');monkeypatch.setattr(m,'sources',lambda:[source])
    runtime=tmp_path/'.venv/lib/native.so';runtime.parent.mkdir(parents=True);runtime.write_bytes(b'SYNTHETIC runtime')
    stage=tmp_path/'results/predictions/features/attempt-0000';stage.mkdir(parents=True);archive=stage/'raw-evidence.zip';archive.write_bytes(b'SYNTHETIC archive')
    m.write(stage/'raw-evidence.json',{'archive_sha256':m.sha(archive)});m.write(stage/'completion.json',{'complete':True,'raw_archive_sha256':m.sha(archive)})
    bindings={p:m.sha(p) for p in [source,runtime,archive,stage/'raw-evidence.json',stage/'completion.json']};seen=[]
    def git(command,**kwargs):p=tmp_path/command[2].split(':',1)[1];seen.append(p);return p.read_bytes()
    monkeypatch.setattr(m.subprocess,'check_output',git);m.git_freeze(bindings,'a'*40,local_archive=archive,installed_runtime={runtime:m.sha(runtime)})
    assert set(seen)=={source,stage/'raw-evidence.json',stage/'completion.json'}
    with pytest.raises(ValueError,match='installed runtime'):m.git_freeze(bindings,'a'*40,installed_runtime={source:m.sha(source)})

def test_provenance_manifest_is_git_required_not_installed_runtime(prepared,monkeypatch):
    _,root,p,_,_,tools,_=prepared;path=release(root,'feature',4,monkeypatch)
    manifest=m.ROOT/tools['inherited_inventory']['path'];m.write(manifest,{'SYNTHETIC':'tool provenance'})
    runtime=m.ROOT/'.venv/native.so';runtime.parent.mkdir();runtime.write_bytes(b'SYNTHETIC native')
    bindings={manifest:m.sha(manifest),runtime:m.sha(runtime)}
    monkeypatch.setattr(m,'tools_bindings',lambda t:bindings.copy())
    def freeze(b,commit,**kwargs):assert runtime in kwargs['installed_runtime'] and manifest not in kwargs['installed_runtime']
    monkeypatch.setattr(m,'git_freeze',freeze);m.approval(root,path,'feature',p,bindings)

def test_reauthenticated_different_pool_is_not_accepted(prepared):
    original,root,p,candidates,models,_,_=prepared
    data=m.read(original/'candidates.json');data[0]['formula']='and(in0,in1)';data[0]['candidate_id']=m.inputs.identifier(data[0]['formula']);m.write(original/'candidates.json',data)
    manifest=m.read(original/'preparation.json')
    for e in manifest['files']:
        if e['path']=='candidates.json':e.update(m.record(original/'candidates.json',original))
    m.write(original/'preparation.json',manifest)
    with pytest.raises(ValueError,match='exactly reproduce'):m.staged_inputs(original)

def test_reauthenticated_unexpected_stage_file_rejected(prepared):
    original,_,_,_,_,_,_=prepared;unexpected=original/'unrelated.json';m.write(unexpected,{'POISON':'unrelated data'})
    manifest=m.read(original/'preparation.json');manifest['files'].append(m.record(unexpected,original));m.write(original/'preparation.json',manifest)
    with pytest.raises(ValueError,match='Exact staged'):m.staged_inputs(original)

def test_resource_caps_count_archive_and_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100));monkeypatch.setitem(m.POLICY,'minimum_free_bytes',10)
    monkeypatch.setitem(m.POLICY,'maximum_workspace_bytes',10);monkeypatch.setitem(m.POLICY,'maximum_log_bytes',3)
    (tmp_path/'worker.log').write_bytes(b'1234')
    with pytest.raises(m.AbortStage,match='file/log'):m.guard(tmp_path)
    (tmp_path/'worker.log').write_bytes(b'123');(tmp_path/'raw-evidence.zip').write_bytes(b'12345678')
    with pytest.raises(m.AbortStage,match='Whole-cache'):m.guard(tmp_path)

def test_real_tiny_python_worker_timeout_partial_and_owned_group_cleanup(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'guard',lambda root,started=None,seconds=None:(_ for _ in ()).throw(m.AbortStage('Owned stage deadline')) if started and time.monotonic()-started>seconds else None)
    monkeypatch.setitem(m.POLICY,'poll_seconds',.005);partial=tmp_path/'partial';code=f'from pathlib import Path;import time;Path({str(partial)!r}).write_text("SYNTHETIC");time.sleep(2)'
    processes=[]
    def launch(command,**kwargs):p=REAL_POPEN([sys.executable,'-c',code],**kwargs);processes.append(p);return p
    monkeypatch.setattr(subprocess,'Popen',launch);owner=m.Owner({'PATH':'/usr/bin:/bin'})
    with pytest.raises(m.AbortStage,match='deadline'):m.run_worker(tmp_path,'feature-worker',{},tmp_path/'worker',owner,{},.25)
    r=m.read(tmp_path/'worker/worker.json');assert not r['complete'] and partial.read_text()=='SYNTHETIC' and r['cleanup_errors']==r['remaining_owned_children']==[] and not owner.active
    with pytest.raises(ProcessLookupError):os.killpg(processes[0].pid,0)

def test_cleanup_error_retains_primary_and_forbids_complete(tmp_path,monkeypatch):
    class Process:
        pid=123;returncode=1
        def poll(self):return 1
    monkeypatch.setattr(m,'guard',lambda *a:None);monkeypatch.setattr(m.cleanup_helper,'cleanup',lambda *a:(_ for _ in ()).throw(PermissionError('SYNTHETIC cleanup')))
    owner=SimpleNamespace(launch=lambda *a:Process(),remove=lambda *a:pytest.fail('Unconfirmed cleanup removed'))
    with pytest.raises(ValueError,match='Owned worker failed'):m.run_worker(tmp_path,'feature-worker',{},tmp_path/'worker',owner,{},1)
    r=m.read(tmp_path/'worker/worker.json');assert not r['complete'] and 'Owned worker failed' in r['primary_error'] and r['cleanup_errors'] and r['remaining_owned_children']

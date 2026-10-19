"""Synthetic-only complete-pool orchestration, provenance and raw evidence tests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('measure_v11e_transfer', REPO/'scripts/measure_v11e_transfer.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)
FAMILIES = {'ammunition':'arbitrary-precision-bit-strings','audiobeam':'audio-beamforming',
            'pm':'numeric-template-matching','fmref':'fm-reception','fac':'integer-recurrences','recursion':'integer-recurrences'}


def save(path, data):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,allow_nan=False)+'\n')


def inputs(root, n=5):
    candidates = [{'candidate_id':f'case{i:04d}','formula':f'addi(in0,{i})'} for i in range(n)]
    candidates.sort(key=lambda r:r['formula'])
    members = [{'program':p,'family':f,'status':'empty' if p=='recursion' else 'complete',
                'canonical_count':0 if p=='recursion' else n,
                'canonical_ids':[] if p=='recursion' else [c['candidate_id'] for c in candidates]} for p,f in FAMILIES.items()]
    points = {name:[{**c,'predicted_lut4':1.,'upper_lut4':None,'calibration_status':'uncalibrated'} for c in candidates] for name in ('V6','V9')}
    save(root/'point-freeze.json',{'schema':'isaforge-v11e-recovered-feature-point-freeze-v1'})
    save(root/'predictions/attempt-0000/result.json',{'models':points})
    save(root/'predictions/completion.json',{'complete':True,'failures':[],'prediction_count':2*n,
         'completed_at_utc':'2026-10-16T00:00:00+00:00','new_labels':0,'new_fits':0,'calibration_jobs':0})
    return candidates,members,{root/'point-freeze.json':m.sha(root/'point-freeze.json')}


def harness(tmp_path, monkeypatch, n=5, verify_failure=False, map_failure=None):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    root = tmp_path/'results/points'; candidates,members,bindings = inputs(root,n)
    for name in ('measurement-plan','measurement-tools','measurement-approval'):
        save(root/(name+'.json'),{'synthetic':name})
    source = tmp_path/'scripts/placeholder.py'; source.parent.mkdir(); source.write_text('# synthetic source\n')
    bindings[source]=m.sha(source)
    tools = {'executables':{'yosys':{'path':'/synthetic/yosys','version':'synthetic','sha256':'0'*64}}}
    plan = {'budget':m.budget(n)}
    review = {'freeze_commit':'a'*40,'reviewed_at_utc':'2026-10-16T00:00:01+00:00'}
    monkeypatch.setattr(m,'validate_approval',lambda r,a:(candidates,members,plan,tools,review,bindings))
    monkeypatch.setattr(m,'sources',lambda:[source])
    monkeypatch.setattr(m.native,'validate_tools',lambda t:None)
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*m.GIB))
    monkeypatch.setattr(m,'HardwareWorkers',lambda t:SimpleNamespace(cancel=lambda:([],[])))
    monkeypatch.setattr(m,'validate_verification',lambda p,f,fs:None)
    monkeypatch.setattr(m,'validate_metric',lambda metric,*args:metric)
    calls=[]
    def worker(payload,folder,owner,hot,check):
        check();calls.append((payload['kind'],payload.get('formula'),len(payload.get('formulas',[]))))
        folder.mkdir(parents=True,exist_ok=True); (folder/'worker.log').write_text('synthetic successful worker\n')
        if payload['kind']=='verify':
            if verify_failure: raise RuntimeError('synthetic verify failure')
            save(folder/'synthetic-proof.json',payload)
            return {'formula_count':len(payload['formulas']),'total_comparisons':2148*len(payload['formulas'])}
        assert sum(c[2] for c in calls if c[0]=='verify')==n, 'Mapping started before every original verified'
        (folder/'candidate.v').write_text(m.generate_rtl(payload['formula']))
        if payload['formula']==map_failure: raise RuntimeError('synthetic per-case mapping failure')
        return {'formula':payload['formula'],'ice40_lut4_count':1,'ice40_carry_count':0,'ice40_ff_count':0,
                'ice40_bram_count':0,'rtl_sha256':m.sha(folder/'candidate.v')}
    monkeypatch.setattr(m,'run_worker',worker)
    return root,candidates,calls


def test_derived_pool_130_all_verification_before_every_mapping(tmp_path,monkeypatch):
    root,candidates,calls=harness(tmp_path,monkeypatch,n=130)
    done=m.collect(root,root/'measurement-approval.json')
    assert done['complete'] and done['primary_available']
    assert done['original_endpoint_available'] is False and 'independent measurement admission' in done['primary_availability_scope']
    assert done['candidate_count']==done['new_physical_measurements']==done['mapping_attempts']==130
    assert done['verified_comparisons']==130*2148 and done['verification_batch_sizes']==[128,2]
    assert [c[0] for c in calls[:2]]==['verify','verify']
    assert len([c for c in calls if c[0]=='map'])==130
    labels=m.read(root/'measurements/attempt-0000/labels.json')
    assert [r['candidate_id'] for r in labels]==[r['candidate_id'] for r in candidates]
    raw=m.verify_archive(root); assert raw['complete']
    assert not done['historical_labels_reused'] and done['new_fits']==0
    with pytest.raises(ValueError,match='no retry'):m.collect(root,root/'measurement-approval.json')


def test_verification_failure_never_maps_preserves_archive(tmp_path,monkeypatch):
    root,_,calls=harness(tmp_path,monkeypatch,verify_failure=True)
    with pytest.raises(ValueError,match='primary unavailable'):m.collect(root,root/'measurement-approval.json')
    done=m.read(root/'measurements/completion.json')
    assert not done['complete'] and not done['primary_available']
    assert done['new_physical_measurements']==done['mapping_attempts']==done['verified_comparisons']==0
    assert all(c[0]=='verify' for c in calls)
    assert m.verify_archive(root)['complete'] is False


def test_one_failed_mapping_no_replacement_or_label_reuse(tmp_path,monkeypatch):
    root,candidates,calls=harness(tmp_path,monkeypatch,map_failure='addi(in0,2)')
    with pytest.raises(ValueError,match='primary unavailable'):m.collect(root,root/'measurement-approval.json')
    done=m.read(root/'measurements/completion.json')
    assert done['mapping_attempts']==len(candidates)==len([c for c in calls if c[0]=='map'])
    assert done['new_physical_measurements']==len(candidates)-1
    assert not done['complete'] and not done['primary_available']
    assert any(x['formula']=='addi(in0,2)' for x in done['failures'])
    assert m.verify_archive(root)['complete'] is False


def test_resource_breach_aborts_remaining_cases(tmp_path,monkeypatch):
    root,_,calls=harness(tmp_path,monkeypatch,n=12)
    original=m.run_worker
    def fail(payload,*args):
        if payload['kind']=='map':raise m.AbortStage('synthetic resource floor')
        return original(payload,*args)
    monkeypatch.setattr(m,'run_worker',fail)
    with pytest.raises(ValueError):m.collect(root,root/'measurement-approval.json')
    done=m.read(root/'measurements/completion.json')
    assert not done['complete'] and done['mapping_attempts']<=2 and done['new_physical_measurements']==0
    assert any('resource floor' in f['error'] for f in done['failures'])


def test_archive_reservation_fails_before_any_release(tmp_path,monkeypatch):
    root,_,calls=harness(tmp_path,monkeypatch)
    monkeypatch.setattr(m.AttemptGuard,'reservation',lambda *a:m.POLICY['maximum_archive_bytes']+1)
    with pytest.raises(ValueError,match='reservation'): m.collect(root,root/'measurement-approval.json')
    assert not calls and not (root/'label-release.json').exists()


def test_fresh_start_reserves_floor_plus_whole_attempt(tmp_path,monkeypatch):
    root,_,calls=harness(tmp_path,monkeypatch)
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=16*m.GIB-1))
    with pytest.raises(ValueError,match='16GiB'):m.collect(root,root/'measurement-approval.json')
    assert not calls and not (root/'label-release.json').exists()


def test_guard_whole_logs_and_terminal_deadline(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*m.GIB))
    scratch,output=tmp_path/'scratch',tmp_path/'out';scratch.mkdir();output.mkdir()
    monkeypatch.setitem(m.POLICY,'maximum_log_bytes',4);(scratch/'worker.log').write_bytes(b'12345')
    with pytest.raises(m.AbortStage,match='log byte'):m.guard(scratch,output)
    (scratch/'worker.log').unlink();monkeypatch.setitem(m.POLICY,'maximum_attempt_bytes',4)
    (scratch/'x').write_bytes(b'123');(output/'y').write_bytes(b'12')
    with pytest.raises(m.AbortStage,match='[Ww]hole'):m.guard(scratch,output)
    (scratch/'x').unlink();(output/'y').unlink();monkeypatch.setitem(m.POLICY,'maximum_attempt_bytes',8*m.GIB)
    with pytest.raises(m.AbortStage,match='deadline'):m.guard(scratch,output,began=m.time.monotonic()-5,maximum_seconds=1)


def proof_fixture(tmp_path,formulas):
    folder=tmp_path/'verify';folder.mkdir()
    (folder/'verification.v').write_text(m.verification_source(formulas))
    (folder/'vectors.txt').write_text(''.join(' '.join(f'{v:08x}' for v in (a,b,*[m.evaluate_formula(f,a,b) for f in formulas]))+'\n' for a,b in m.vectors()))
    proof={'verified':True,'formula_count':len(formulas),'vectors_per_formula':2148,'total_comparisons':2148*len(formulas),'random_seed':m.SEED,
           'v4_validation_override_sha256':m.sha(REPO/'isaforge/v4_validation.py'),'rtl_sha256':m.sha(folder/'verification.v'),
           'vectors_sha256':m.sha(folder/'vectors.txt'),'signed_overflow_workaround_applied':False}
    return folder,proof


def test_exact_seed_vectors_and_original_batch_renderer(tmp_path):
    folder,proof=proof_fixture(tmp_path,['addi(in0,1)','mulhsu(in0,in1)'])
    assert len(m.vectors())==2148 and m.vectors()==m.vectors()
    m.validate_verification(proof,folder,['addi(in0,1)','mulhsu(in0,in1)'])
    lines=(folder/'vectors.txt').read_text().splitlines();words=lines[100].split();words[-1]='ffffffff';lines[100]=' '.join(words)
    (folder/'vectors.txt').write_text('\n'.join(lines)+'\n');proof['vectors_sha256']=m.sha(folder/'vectors.txt')
    with pytest.raises(ValueError,match='vector/oracle'):m.validate_verification(proof,folder,['addi(in0,1)','mulhsu(in0,in1)'])


@pytest.mark.parametrize('key,value',[('verified',1),('formula_count',True),('total_comparisons',1),('random_seed',0),('signed_overflow_workaround_applied',1)])
def test_bad_verification_counts_seed_types(tmp_path,key,value):
    folder,proof=proof_fixture(tmp_path,['addi(in0,1)']);proof[key]=value
    with pytest.raises(ValueError):m.validate_verification(proof,folder,['addi(in0,1)'])


def mapped_fixture(tmp_path,monkeypatch,types=None):
    folder=tmp_path/'map';folder.mkdir();formula='addi(in0,1)';types=types or ['SB_LUT4','SB_CARRY','SB_DFFE','SB_RAM40_4K']
    (folder/'candidate.v').write_text(m.generate_rtl(formula));(folder/'ice40.log').write_text('synthetic native log')
    (folder/'ice40.ys').write_text(f'read_verilog "{folder/"candidate.v"}"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{folder/"ice40-netlist.json"}"\nstat\n')
    save(folder/'ice40-netlist.json',{'modules':{'candidate':{'cells':{str(i):{'type':t} for i,t in enumerate(types)}}}})
    tools={'executables':{'yosys':{'path':'/synthetic/yosys','version':'synthetic','sha256':'0'*64}}}
    metric={'formula':formula,'tool':'synthetic','measurement_source':'rtl_synthesis','rtl_sha256':m.sha(folder/'candidate.v'),
            'script_sha256':m.sha(folder/'ice40.ys'),'log_sha256':m.sha(folder/'ice40.log'),'netlist_sha256':m.sha(folder/'ice40-netlist.json'),
            'ice40_cell_types':dict(m.Counter(types)),'ice40_lut4_count':types.count('SB_LUT4'),'ice40_carry_count':types.count('SB_CARRY'),
            'command':['/synthetic/yosys','-s',str(folder/'ice40.ys')]}
    monkeypatch.setattr(m.native,'abc_invocations',lambda *a:[]);monkeypatch.setattr(m.native,'data_invocations',lambda *a:[])
    return folder,formula,tools,metric


def test_separate_lut_carry_ff_bram_recounts(tmp_path,monkeypatch):
    folder,formula,tools,metric=mapped_fixture(tmp_path,monkeypatch)
    result=m.validate_metric(metric,folder,formula,tools)
    assert [result[k] for k in ['ice40_lut4_count','ice40_carry_count','ice40_ff_count','ice40_bram_count']]==[1,1,1,1]


@pytest.mark.parametrize('poison',['rtl','recipe','count','command','primitive','bool_primitive_count'])
def test_bad_mapped_evidence_rejected(tmp_path,monkeypatch,poison):
    folder,formula,tools,metric=mapped_fixture(tmp_path,monkeypatch,['SB_LUT4'] if poison!='primitive' else ['MYSTERY_LUT'])
    if poison=='rtl':(folder/'candidate.v').write_text('wrong RTL');metric['rtl_sha256']=m.sha(folder/'candidate.v')
    elif poison=='recipe':(folder/'ice40.ys').write_text('different recipe');metric['script_sha256']=m.sha(folder/'ice40.ys')
    elif poison=='count':metric['ice40_lut4_count']=True
    elif poison=='bool_primitive_count':metric['ice40_cell_types']['SB_LUT4']=True
    elif poison=='command':metric['command']=['other','-s','x']
    with pytest.raises(ValueError):m.validate_metric(metric,folder,formula,tools)


def fake_prediction_module(monkeypatch,root,n=5):
    import predict_v11e_transfer as p
    candidates,members,bindings=inputs(root,n)
    freeze={'schema':'isaforge-v11e-recovered-feature-point-freeze-v1','complete':True,'frozen_at_utc':'2026-10-16T00:00:00+00:00'}
    monkeypatch.setattr(p,'validate_point_freeze',lambda r:(freeze,candidates,members,bindings),raising=False)
    return p,candidates,members,bindings


def test_point_gate_no_inference_or_native_calls(tmp_path,monkeypatch):
    root=tmp_path/'points';p,candidates,members,bindings=fake_prediction_module(monkeypatch,root)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('native execution')))
    monkeypatch.setattr(p.v6,'load_model',lambda *a:(_ for _ in ()).throw(AssertionError('model load')))
    f,cs,ms,bs=m.prediction_inputs(root)
    assert cs==candidates and ms==members and bs==bindings


@pytest.mark.parametrize('poison',['incomplete','missing_point','extra_model','bool_point','negative_point','nan_point','partial_program','unbound_freeze'])
def test_full_point_gate_poison(tmp_path,monkeypatch,poison):
    root=tmp_path/'points';p,candidates,members,bindings=fake_prediction_module(monkeypatch,root)
    point=root/'predictions/attempt-0000/result.json';result=m.read(point)
    if poison=='incomplete':
        d=m.read(root/'predictions/completion.json');d['complete']=False;save(root/'predictions/completion.json',d)
    elif poison=='missing_point':result['models']['V6'].pop()
    elif poison=='extra_model':result['models']['chosen']=result['models']['V6']
    elif poison=='bool_point':result['models']['V9'][0]['predicted_lut4']=True
    elif poison=='negative_point':result['models']['V9'][0]['predicted_lut4']=-1
    elif poison=='nan_point':result['models']['V9'][0]['predicted_lut4']=float('nan')
    elif poison=='partial_program':members[0]['status']='failure-retained'
    elif poison=='unbound_freeze':bindings.clear()
    point.write_text(json.dumps(result))
    with pytest.raises(ValueError):m.prediction_inputs(root)


def test_approval_checks_frozen_prediction_chronology_and_git(tmp_path,monkeypatch):
    import predict_v11e_transfer as p
    root=tmp_path/'results/points';_,_,bindings=inputs(root)
    for name in ('measurement-plan','measurement-tools','measurement-approval','runtime'):
        save(root/(name+'.json'),{'files':[]} if name=='runtime' else {})
    source=tmp_path/'scripts/measure_v11e_transfer.py';source.parent.mkdir();source.write_text('synthetic')
    test=tmp_path/'tests/test_measure_v11e_transfer.py';test.parent.mkdir();test.write_text('synthetic')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'__file__',str(source))
    candidates,members,_=inputs(root);plan={'created_at_utc':'2026-10-16T00:00:02+00:00'}
    tools={'inherited_inventory':{'path':'base'}}
    monkeypatch.setattr(m,'validate_plan',lambda r:(candidates,members,plan,tools,bindings))
    monkeypatch.setattr(p,'tools_bindings',lambda t:{})
    called=[];monkeypatch.setattr(p,'git_freeze',lambda r,b,c:called.append(c))
    approval={'status':'approved-v11-full-pool-original-targets','candidate_count':5,'maximum_new_labels':5,'expected_rtl_comparisons':5*2148,
              'reviewed_at_utc':'2026-10-16T00:00:03+00:00','freeze_commit':'a'*40,
              **{k:m.sha(root/n) for k,n in [('point_freeze_sha256','point-freeze.json'),('prediction_completion_sha256','predictions/completion.json'),('measurement_plan_sha256','measurement-plan.json'),('tools_sha256','measurement-tools.json')]},
              'collector_sha256':m.sha(source),'collector_tests_sha256':m.sha(test)}
    path=root/'measurement-approval.json';save(path,approval)
    assert m.validate_approval(root,path)[4]==approval and called==['a'*40]
    approval['reviewed_at_utc']='2026-10-16T00:00:01+00:00';save(path,approval)
    with pytest.raises(ValueError,match='precedes'):m.validate_approval(root,path)
    assert called==['a'*40]


def test_worker_cleanup_keeps_primary_failure(tmp_path,monkeypatch):
    class Process:
        pid=123;returncode=1
        def poll(self):return 1
    owner=SimpleNamespace(launch=lambda *a:Process(),remove=lambda p:None)
    monkeypatch.setattr(m.cleanup,'cleanup',lambda ps:([{'operation':'killpg','error':'PermissionError'}],[{'pid':123}]))
    folder=tmp_path/'worker'
    with pytest.raises(m.AbortStage,match='primary='):m.run_worker({'kind':'map'},folder,owner,{},lambda:None)
    receipt=m.read(folder/'worker.json')
    assert 'Owned hardware worker failed' in receipt['primary_error']
    assert receipt['cleanup_errors'] and receipt['remaining_owned_children'] and receipt['complete'] is False


def test_archive_rejects_reauthenticated_stage_mutation(tmp_path,monkeypatch):
    root,_,_=harness(tmp_path,monkeypatch);m.collect(root,root/'measurement-approval.json')
    path=root/'measurements/attempt-0000/labels.json';path.write_text('[]\n')
    with pytest.raises(ValueError,match='stage bytes'):m.verify_archive(root)


def test_installed_tool_bindings_are_hot_large_evidence_only_exempt(tmp_path,monkeypatch):
    repo=tmp_path/'repo';monkeypatch.setattr(m,'ROOT',repo)
    installed=tmp_path/'installed/yosys';source=repo/'scripts/collector.py';payload=repo/'generated/raw.gz';model=repo/'results/model.joblib'
    bindings={installed:'a',source:'b',payload:'c',model:'d'}
    assert m.hot_bindings(bindings)=={installed:'a',source:'b'}


def test_python_invocation_alias_exact_resolved_binary(tmp_path,monkeypatch):
    binary=tmp_path/'python.bin';binary.write_bytes(b'synthetic pinned executable')
    alias=tmp_path/'venv-python';alias.symlink_to(binary)
    tools={'executables':{'python':{'path':str(binary),'sha256':m.sha(binary)},'abc':{'path':'/synthetic/abc'}},'sdk':{'path':'/synthetic/sdk'}}
    monkeypatch.setattr(m.sys,'executable',str(alias));owner=m.HardwareWorkers(tools)
    assert owner.python_identity()=={'invoked':str(alias),'resolved':str(binary),'sha256':m.sha(binary)}
    other=tmp_path/'other.bin';other.write_bytes(b'wrong executable');alias.unlink();alias.symlink_to(other)
    with pytest.raises(ValueError,match='Python alias'):owner.python_identity()


def test_fixed60min_all327_and_unchanged_worker_budget():
    b=m.budget(327)
    assert b['maximum_attempt_seconds']==3600 and b['maximum_mapping_attempts']==327
    assert b['verification_batches']==3 and b['expected_rtl_comparisons']==702396
    assert b['uncapped_serial_batch_worker_bound_seconds']==64020
    assert m.POLICY['mapping_workers']==2 and m.POLICY['worker_seconds']==360 and m.POLICY['retries']==0


def test_incremental_guard_327_completed_cases_scans_only_active(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path); monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*m.GIB))
    scratch,output=tmp_path/'scratch',tmp_path/'out'; scratch.mkdir(); output.mkdir()
    for i in range(327):
        d=scratch/'circuits'/str(i); d.mkdir(parents=True); (d/'candidate.v').write_bytes(b'x'*64)
    guard=m.AttemptGuard(scratch,output); active=scratch/'active'; active.mkdir(); guard.begin(active)
    scans=[]; scan=guard.scan
    monkeypatch.setattr(guard,'scan',lambda path:(scans.append(path),scan(path))[1])
    began=m.time.monotonic()
    for _ in range(20): guard()
    elapsed=m.time.monotonic()-began
    assert scans==[active]*20 and elapsed<2, f'20 synthetic active-only guard calls took {elapsed:.3f}s'
    (active/'worker.log').write_bytes(b'x'*10); guard.end(active)
    assert guard.files[active/'worker.log']==10


def test_archive_chunk_checks_never_enumerate_tree(tmp_path,monkeypatch):
    root,_,_=harness(tmp_path,monkeypatch,n=5)
    original=m.AttemptGuard.scan; scans=[]
    def scan(self,path):
        assert not self.archiving or not (self.output/'raw-evidence.zip').exists(), 'Only final boundary may scan after archive'
        scans.append(path); return original(self,path)
    # Count only archive-time calls directly, allowing final boundary inventory.
    original_inventory=m.AttemptGuard.inventory
    def inventory(self):
        was=self.archiving; self.archiving=False
        try:return original_inventory(self)
        finally:self.archiving=was
    monkeypatch.setattr(m.AttemptGuard,'scan',scan); monkeypatch.setattr(m.AttemptGuard,'inventory',inventory)
    assert m.collect(root,root/'measurement-approval.json')['complete']
    assert scans


def test_closed_feature_cache_is_not_rehashed_per_target(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    cache=tmp_path/'results/original/features/attempt-0000/cache/1/sog.json'
    matrix=tmp_path/'results/original/features/attempt-0000/features.json'
    seal=tmp_path/'results/points/point-freeze.json'; source=tmp_path/'scripts/worker.py'; installed=tmp_path/'outside/yosys'
    assert m.hot_bindings({cache:'a',matrix:'b',seal:'c',source:'d',installed:'e'})=={seal:'c',source:'d',installed:'e'}


def test_archive_guard_does_not_iterate_completed_inventory(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path); monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*m.GIB))
    scratch,output=tmp_path/'scratch',tmp_path/'out'; scratch.mkdir(); output.mkdir()
    (scratch/'closed').write_bytes(b'old'); guard=m.AttemptGuard(scratch,output)
    guard.archive_maximum=guard.reservation(guard.files); guard.archiving=True
    class NoIteration(dict):
        def __iter__(self): raise AssertionError('Closed inventory iteration on ZIP chunk')
        def items(self): raise AssertionError('Closed inventory items on ZIP chunk')
        def values(self): raise AssertionError('Closed inventory sizes on ZIP chunk')
    guard.files=NoIteration(guard.files)
    guard()
    (output/'raw-evidence.zip').write_bytes(b'new archive chunk')
    guard()

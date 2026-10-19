"""Synthetic adapter release/ownership/evidence tests; no real native cohort."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import subprocess
REAL_POPEN=subprocess.Popen
import zipfile
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recover_v11_transfer',ROOT/'scripts/recover_v11_transfer.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('Actual native jobs forbidden'))

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'results/study';root.mkdir(parents=True)
    endpoint={'schema':'isaforge-v11b-endpoint-adoption-v1','amendment':'V11b-E1'};m.write(root/'endpoint-adoption.json',endpoint)
    protocol=tmp_path/'docs/v11b-transfer-protocol.md';protocol.parent.mkdir();protocol.write_text('SYNTHETIC protocol')
    monkeypatch.setattr(m,'ENDPOINT_SHA',m.sha(root/'endpoint-adoption.json'));monkeypatch.setattr(m,'PROTOCOL_SHA',m.sha(protocol))
    source=tmp_path/'source.py';source.write_text('SYNTHETIC source');monkeypatch.setattr(m,'sources',lambda:[source,protocol])
    oldfile=tmp_path/'old.json';m.write(oldfile,{})
    partial=tmp_path/'generated/old.partial';partial.parent.mkdir();partial.write_text('retained partial');monkeypatch.setattr(m,'local_payloads',lambda:{partial})
    old={'programs':{},'upstream_commit':'upstream','reservation_commit':'reserved'};report={'records':{}};members={}
    def member(name,data):members[name]={'data':data,'sha256':m.hashlib.sha256(data).hexdigest()}
    for name in m.PROGRAMS:
        elf=('SYNTHETIC ELF '+name).encode();family=m.original.SPECS[name][1];count=0 if name=='recursion' else 1
        old['programs'][name]={'family':family,'directory':'bench/'+name,'files':{}}
        report['records'][name]={'family':family,'status':'failure-retained' if name in m.RECOVER else 'empty' if name=='recursion' else 'complete',
            'all_roi_count':count,'captured_outputs':[1],'O0_O2_snapshot_bitexact':True,'O2_build':{'elf_sha256':m.hashlib.sha256(elf).hexdigest()}}
        member(f'{name}/O2/{name}.elf',elf)
        for opt in ('O0','O2'):member(f'{name}/{opt}-oracle.json',b'{}\n')
        if name in m.REUSE:
            rows=[] if name=='recursion' else [{'formula':'add(in0,in1)','occurrences':[]}]
            member(f'{name}/candidates-all-roi/{name}.json',(json.dumps(rows)+'\n').encode())
            member(f'{name}/{name}.jsonl.summary.json',b'{"validated":true}\n');member(f'{name}/fusion-all-roi.json',b'{"passed":true}\n')
    monkeypatch.setattr(m,'old_evidence',lambda:(copy.deepcopy(old),copy.deepcopy(report),members,[oldfile,partial]))
    monkeypatch.setattr(m,'archive_bytes',lambda e:e['data'])
    tools={'executables':{'spike':{'path':'synthetic-spike'},'gzip':{'path':'synthetic-gzip','sha256':'gzip'},'objdump':{'path':'synthetic-objdump'}},'environment':{'PATH':'SYNTHETIC'}}
    monkeypatch.setattr(m,'tools_inventory',lambda p:copy.deepcopy(tools));monkeypatch.setattr(m,'validate_tools',lambda *a:None)
    manifest=m.prepare(root)
    return root,source,partial,manifest

def test_preparation_exact6_elfs4_reuse_and_partial_not_git(prepared):
    root,source,partial,manifest=prepared;m0,plan,tools,bindings=m.validate_preparation(root)
    assert len(plan['programs'])==6 and len(list((root/'inputs/elfs').glob('*.elf')))==6
    assert len(list((root/'inputs/reused').glob('*/candidates.json')))==4
    assert all(e['git_required'] is ((root/e['path']).resolve()!=partial) for e in manifest['files'])
    assert m.read(root/'inputs/reused/recursion/candidates.json')==[]
    with pytest.raises(ValueError,match='only endpoint'):m.prepare(root)

@pytest.mark.parametrize('poison',['elf','source','endpoint','extra','localflag'])
def test_preparation_rejects_mutation(prepared,poison):
    root,source,partial,manifest=prepared
    if poison=='elf':(root/'inputs/elfs/pm.elf').write_bytes(b'WRONG')
    elif poison=='source':source.write_text('WRONG')
    elif poison=='endpoint':(root/'endpoint-adoption.json').write_text('{}')
    elif poison=='extra':m.write(root/'inputs/extra.json',{})
    else:
        for e in manifest['files']:e['git_required']=False
        (root/'preparation.json').write_text(json.dumps(manifest))
    with pytest.raises((ValueError,m.AbortRun)):m.validate_preparation(root)


def test_commit_approval_skips_only_manifest_authenticated_partial(prepared,monkeypatch):
    root,source,partial,_=prepared
    a={'status':'approved-v11b-input-only-recovery','preparation_sha256':m.sha(root/'preparation.json'),'plan_sha256':m.sha(root/'plan.json'),'tools_sha256':m.sha(root/'tools.json'),
       'runner_sha256':m.sha(m.__file__),'maximum_new_captures':2,'maximum_labels':0,'freeze_commit':'a'*40,'reviewed_at_utc':m.now()}
    approval=root/'recovery-approval.json';m.write(approval,a);seen=[]
    def git(command,**kwargs):
        p=m.ROOT/command[2].split(':',1)[1];assert p!=partial;seen.append(p);return p.read_bytes()
    monkeypatch.setattr(m.subprocess,'check_output',git);m.validate_approval(root,approval)
    assert root/'preparation.json' in seen and source in seen and partial not in seen
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**k:b'WRONG')
    with pytest.raises(ValueError,match='Git'):m.validate_approval(root,approval)


def released(prepared,monkeypatch):
    root,source,partial,manifest=prepared;m0,plan,tools,bindings=m.validate_preparation(root);approval=root/'recovery-approval.json';m.write(approval,{})
    review={'reviewed_at_utc':'2000-01-01T00:00:00+00:00','freeze_commit':'a'*40}
    monkeypatch.setattr(m,'validate_approval',lambda *a:(m0,plan,tools,review,bindings.copy()))
    monkeypatch.setattr(m.spool,'free_bytes',lambda p:64*m.spool.GIB);monkeypatch.setattr(m,'resource_guard',lambda *a:None);monkeypatch.setattr(m,'provenance_guard',lambda *a:None)
    events=[]
    def capture(factory,folder,attempt,**kwargs):
        name=folder.parent.name;events.append((name,'capture'));folder.mkdir(parents=True)
        for n,v in [('raw-spike.log.gz',b'SYNTHETIC'),('htif.stdout.log',b'HTIF')]: (folder/n).write_bytes(v)
        m.write(folder/'capture.json',{'status':'captured-not-validated'});return {}
    def worker(root,name,phase,attempt,tools):
        events.append((name,phase));base=attempt/name
        if phase=='decode':
            m.write(base/'decode/decode.json',{'trace_instructions':2});(base/'decode/decoded.jsonl.gz').write_bytes(b'SYNTHETIC')
        else:
            m.write(base/'extract/candidates-all-roi'/(name+'.json'),[{'formula':'add(in0,in1)','occurrences':[]}])
            for n in ('oracle.json','fusion-all-roi.json'):m.write(base/'extract'/n,{})
            m.write(base/'extract/extraction.json',{'complete':True,'candidate_count':1,'elf_sha256':plan['programs'][name]['elf']['sha256']})
    monkeypatch.setattr(m.spool,'capture_raw',capture);monkeypatch.setattr(m,'run_worker',worker)
    return root,approval,events,capture


def test_full_synthetic_adapter_exact_order_all6_and_no_gzip_copy(prepared,monkeypatch,capsys):
    root,approval,events,_=released(prepared,monkeypatch);r=m.collect(root,approval)
    assert r['complete'] and events==[(n,p) for n in ('ammunition','pm') for p in ('capture','decode','extract')]
    stage=root/'run/attempt-0000';records=m.read(stage/'programs.json');assert list(records)==list(m.PROGRAMS) and records['recursion']['status']=='empty'
    assert r['new_labels']==r['new_features']==r['new_fits']==r['new_predictions']==0
    lines=capsys.readouterr().out.splitlines()
    assert len(lines)==12 and all('program=' in line and 'phase=' in line and 'event=' in line for line in lines)
    assert [' '.join(line.split()[1:]) for line in lines]==[f'program={n} phase={p} event={e}' for n in ('ammunition','pm') for p in ('capture','decode','extract') for e in ('start','complete')]
    e=m.read(stage/'evidence-manifest.json')
    assert any('.gz' in x['path'] and not x['packaged'] for x in e['files'])
    with zipfile.ZipFile(stage/'metadata.zip') as z:assert all('.gz' not in Path(x).name for x in z.namelist())
    with pytest.raises(ValueError,match='Single fresh'):m.collect(root,approval)


def test_normal_deadline_keeps_all6_and_still_attempts_fixed_pm(prepared,monkeypatch):
    root,approval,events,capture=released(prepared,monkeypatch)
    def fail(factory,folder,attempt,**kw):
        if folder.parent.name=='ammunition':events.append(('ammunition','capture'));raise TimeoutError('synthetic deadline')
        return capture(factory,folder,attempt,**kw)
    monkeypatch.setattr(m.spool,'capture_raw',fail)
    with pytest.raises(ValueError,match='Incomplete'):m.collect(root,approval)
    r=m.read(root/'run/attempt-0000/programs.json');assert len(r)==6 and r['ammunition']['status']=='failure-retained' and r['pm']['status']=='complete'


def test_resource_breach_aborts_before_pm(prepared,monkeypatch):
    root,approval,events,capture=released(prepared,monkeypatch)
    def fail(factory,folder,attempt,**kw):events.append((folder.parent.name,'capture'));raise ValueError('Free-space floor reached')
    monkeypatch.setattr(m.spool,'capture_raw',fail)
    with pytest.raises(ValueError,match='Incomplete'):m.collect(root,approval)
    assert events==[('ammunition','capture')] and m.read(root/'run/attempt-0000/programs.json')['pm']['status']=='not-attempted'


def test_package_failure_cannot_publish_complete(prepared,monkeypatch):
    root,approval,events,_=released(prepared,monkeypatch);monkeypatch.setattr(m,'pack',lambda *a:(_ for _ in ()).throw(OSError('synthetic archive')))
    with pytest.raises(ValueError,match='Incomplete'):m.collect(root,approval)
    assert m.read(root/'completion.json')['complete'] is False


def test_resource_guard_counts_root_metadata_and_perfile(tmp_path,monkeypatch):
    root=tmp_path/'results';attempt=tmp_path/'generated';root.mkdir();attempt.mkdir();monkeypatch.setattr(m.spool,'check_resources',lambda *a,**k:None)
    monkeypatch.setitem(m.POLICY,'metadata_log_bytes_per_file',3);(root/'data.json').write_bytes(b'1234')
    with pytest.raises(m.AbortRun,match='Stage/file'):m.resource_guard(root,attempt)
    (root/'data.json').write_bytes(b'12');(attempt/'other').write_bytes(b'12');monkeypatch.setitem(m.POLICY,'attempt_bytes',3)
    with pytest.raises(m.AbortRun,match='including result'):m.resource_guard(root,attempt)


def test_owned_worker_terminal_resource_guard_and_cleanup_record(prepared,monkeypatch):
    root,_,_,_=prepared;m.write(root/'recovery-claim.json',{});attempt=m.ROOT/m.PREFIX;base=attempt/'ammunition';base.mkdir(parents=True)
    class Process:
        returncode=0;pid=123
        def poll(self):return 0
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:Process());monkeypatch.setattr(m.spool,'cleanup',lambda ps:([],[]))
    monkeypatch.setattr(m,'resource_guard',lambda *a:(_ for _ in ()).throw(m.AbortRun('terminal cap')))
    with pytest.raises(m.AbortRun,match='terminal cap'):m.run_worker(root,'ammunition','decode',attempt,{'environment':{}})
    assert m.read(base/'decode-worker.json')['complete'] is False


def test_extract_worker_unchanged_scope_static_snapshots_and_fusion(prepared,monkeypatch):
    root,_,_,_=prepared;plan=m.read(root/'plan.json');tools=m.read(root/'tools.json');name='ammunition';base=m.ROOT/m.PREFIX/name
    m.write(root/'recovery-claim.json',{'runner_sha256':m.sha(m.__file__),'preparation_sha256':m.sha(root/'preparation.json')})
    raw=base/'capture/raw-spike.log.gz';raw.parent.mkdir(parents=True);raw.write_bytes(b'SYNTHETIC raw')
    m.write(base/'capture/capture.json',{'status':'captured-not-validated','raw_sha256':m.sha(raw)})
    m.write(base/'capture/htif.stdout.log',{})
    decoded=base/'decode/decoded.jsonl.gz';decoded.parent.mkdir();decoded.write_bytes(b'SYNTHETIC decoded')
    m.write(base/'decode/decode.json',{'validated':True,'raw_sha256':m.sha(raw),'decoded_sha256':m.sha(decoded),'pc_counts':[[100,1],[104,1]],'trace_instructions':2,'block_starts':[100,108]})
    monkeypatch.setattr(m.original,'output',lambda text:[1]);monkeypatch.setattr(m.original,'validate_output',lambda *a:{'passed':True})
    program={100:{'symbol':'main'},104:{'symbol':'__helper'}};monkeypatch.setattr(m,'readProgram',lambda *a:program)
    calls=[]
    def extract(p,runs,starts,**kwargs):
        calls.append((p,runs,starts,kwargs));return [{'formula':'add(in0,in1)','occurrences':[{'pcs':['0x64','0x68']}]}]
    monkeypatch.setattr(m,'extractCandidates',extract);monkeypatch.setattr(m.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='SYNTHETIC disassembly',stderr=''))
    monkeypatch.setattr(m,'verify_candidates',lambda *a,**kw:{'passed':True,'seed':2026101507,'benchmarks':[{'benchmark':name,'vectors_per_occurrence':16,'skipped_opaque_block_occurrences':0,'checked_occurrences':1}]})
    m.worker(root,name,'extract',m.sha(root/'recovery-claim.json'))
    assert calls[0][3]=={'maxSize':4,'limit':None} and calls[0][2]=={100,104,108} and dict(calls[0][1])=={100:1,104:1}
    x=m.read(base/'extract/extraction.json');assert x['complete'] and x['static_objdump_calls']==3 and x['elf_sha256']==plan['programs'][name]['elf']['sha256']
    assert m.read(base/'extract/program.json')=={'100':{'symbol':'main'},'104':{'symbol':'__helper'}}
    assert (base/'extract/disassembly.txt').read_text()=='SYNTHETIC disassembly'


def test_worker_rejects_claim_before_native(prepared):
    root,_,_,_=prepared;m.write(root/'recovery-claim.json',{'runner_sha256':'WRONG','preparation_sha256':m.sha(root/'preparation.json')})
    with pytest.raises(ValueError,match='claim/source'):m.worker(root,'ammunition','decode',m.sha(root/'recovery-claim.json'))


def test_pack_resource_failure_downgrades_complete_and_blocks_pm_on_source_change(prepared,monkeypatch):
    root,approval,events,_=released(prepared,monkeypatch)
    checks=[0]
    def provenance(*a):
        checks[0]+=1
        if checks[0]>1:raise m.AbortRun('SYNTHETIC source change')
    monkeypatch.setattr(m,'provenance_guard',provenance)
    with pytest.raises(ValueError,match='Incomplete'):m.collect(root,approval)
    records=m.read(root/'run/attempt-0000/programs.json');assert records['pm']['status']=='not-attempted' and events==[('ammunition','capture')]
    assert m.read(root/'completion.json')['complete'] is False


def test_tools_capture_gzip_stderr_version_without_native(monkeypatch,tmp_path):
    paths={}
    for n in ('cc','objdump','spike','gzip'):
        p=tmp_path/n;p.write_bytes(n.encode());paths[n]={'path':str(p),'sha256':m.sha(p)}
    monkeypatch.setattr(m.shutil,'which',lambda n:paths[n]['path']);monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='',stderr='Apple gzip synthetic\n'))
    monkeypatch.setattr(m,'dependencies',lambda p:{'files':[]})
    r=m.tools_inventory({'tools':{k:paths[k] for k in ('cc','objdump','spike')}})
    assert r['executables']['gzip']['version']=='Apple gzip synthetic' and r['executables']['gzip']['version_stderr']=='Apple gzip synthetic\n'
    assert set(r['environment'])=={'PATH','LANG','LC_ALL','TZ'}


def test_real_tiny_owned_python_worker_deadline_retains_partial_and_reaps(prepared,monkeypatch):
    import os
    root,_,_,_=prepared;m.write(root/'recovery-claim.json',{});attempt=m.ROOT/m.PREFIX;base=attempt/'ammunition';base.mkdir(parents=True)
    partial=base/'decode/decoded.jsonl.gz.partial';partial.parent.mkdir()
    code='from pathlib import Path;import time;Path('+repr(str(partial))+').write_bytes(b"SYNTHETIC partial");time.sleep(2)'
    launched=[]
    def launch(command,**kwargs):
        p=REAL_POPEN([sys.executable,'-c',code],**kwargs);launched.append(p);return p
    monkeypatch.setattr(m.subprocess,'Popen',launch);monkeypatch.setattr(m,'resource_guard',lambda *a:None)
    monkeypatch.setitem(m.POLICY,'offline_seconds',.25);monkeypatch.setitem(m.POLICY,'poll_seconds',.005)
    with pytest.raises(TimeoutError,match='decode deadline'):m.run_worker(root,'ammunition','decode',attempt,{'environment':{'PATH':'/usr/bin:/bin'}})
    receipt=m.read(base/'decode-worker.json')
    assert receipt['complete'] is False and receipt['remaining_owned_children']==receipt['cleanup_errors']==[]
    assert partial.read_bytes()==b'SYNTHETIC partial' and (base/'decode-worker.log').exists()
    assert len(launched)==1 and launched[0].poll() is not None
    with pytest.raises(ProcessLookupError):os.killpg(launched[0].pid,0)


@pytest.mark.parametrize('cleanup_failure',['errors','remaining'])
def test_owned_worker_cleanup_cannot_release_complete(prepared,monkeypatch,cleanup_failure):
    root,_,_,_=prepared;m.write(root/'recovery-claim.json',{});attempt=m.ROOT/m.PREFIX;base=attempt/'ammunition';base.mkdir(parents=True)
    class Process:
        returncode=0;pid=123
        def poll(self):return 0
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:Process());monkeypatch.setattr(m,'resource_guard',lambda *a:None)
    result=([{'operation':'killpg','error':'injected PermissionError'}],[]) if cleanup_failure=='errors' else ([],[{'process':'decode','pid':123,'scope':'owned-process-group'}])
    monkeypatch.setattr(m.spool,'cleanup',lambda ps:result)
    with pytest.raises(ValueError,match='cleanup incomplete'):m.run_worker(root,'ammunition','decode',attempt,{'environment':{}})
    receipt=m.read(base/'decode-worker.json');assert receipt['complete'] is False and (receipt['cleanup_errors'] or receipt['remaining_owned_children'])

"""Synthetic orchestration/provenance poisons; never launch study native jobs."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measure_v10d_timing', ROOT/'scripts/measure_v10d_timing.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('Native study execution forbidden'))


def put(path,value): path.write_text(json.dumps(value,indent=2)+'\n')


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m.area,'ROOT',tmp_path)
    old = tmp_path/'area';old.mkdir();pairs = [];metrics = {}
    for i,(k,c) in enumerate(__import__('itertools').product(m.harness.CONSTANTS,m.harness.CONTEXTS)):
        pair = {'pair_id':'v10-csd:'+format(i,'064x'),'source_candidate_id':'s'+str(i),'constant_u32':k,'context':c,
            'formula':'synthetic-'+str(i),'rewritten_formula':'synthetic-csd-'+str(i),'arms':{}}
        for arm in m.ARMS:
            path = old/'rtl'/format(i,'064x')/arm/'candidate.v';path.parent.mkdir(parents=True);path.write_text('// synthetic '+arm+'\n')
            pair['arms'][arm] = {'formula':pair['formula']+arm,'rtl':m.record(path,old)}
            metrics[pair['pair_id'],arm] = {'lut4_count':100,'carry_count':30}
        pairs.append(pair)
    tools = {'schema':'synthetic','area_tools':{'executables':{'yosys':{'path':'/synthetic/yosys','sha256':'a'*64},'abc':{'path':'/synthetic/abc','sha256':'b'*64}}},
        'nextpnr':{'path':'/synthetic/nextpnr','sha256':'c'*64},'pins':fixture_pins()}
    m.write(old/'tools.json',tools['area_tools']);m.write(old/'preparation.json',{'synthetic':True})
    m.write(old/'measurements/completion.json',{'complete':True});m.write(old/'independent-audit.json',{'status':'pass'})
    inherited = {p:m.sha(p) for p in old.rglob('*') if p.is_file()}
    source = tmp_path/'synthetic-source.py';source.write_text('# synthetic\n')
    monkeypatch.setattr(m,'required_sources',lambda:[source]);monkeypatch.setattr(m,'preflight_inputs',lambda:[])
    monkeypatch.setattr(m,'area_inputs',lambda a,b:({'synthetic':True},pairs,metrics,inherited))
    monkeypatch.setattr(m,'timing_tools',lambda a,p:(tools,[]));monkeypatch.setattr(m,'validate_tools',lambda t:None)
    root = tmp_path/'timing';m.prepare(root,old,old/'independent-audit.json')
    return root,pairs,tools,source,inherited


def rebind(root,path):
    manifest = m.read(root/'preparation.json');entry = m.record(path,root)
    manifest['files'] = [entry if x['path']==entry['path'] else x for x in manifest['files']]
    for key in ('pairs','recipe','tools','wrapper','pcf'):
        if manifest[key]['path']==entry['path']:manifest[key] = entry
    put(root/'preparation.json',manifest)


def test_prepare_copies_exact64_no_native_and_no_overwrite(prepared):
    root,pairs,tools,source,_ = prepared
    manifest,recipe,actual,observed,bindings = m.validate_preparation(root)
    assert len(actual)==32 and sum(len(p['arms']) for p in actual)==64 and observed==tools
    assert recipe['timing']==m.harness.recipe() and manifest['new_native_jobs']==0
    assert m.sha(root/'wrapper.v')==m.digest(m.harness.wrapper_rtl().encode())
    for pair,prior in zip(actual,pairs):
        for arm in m.ARMS:assert pair['arms'][arm]['candidate_rtl']['sha256']==prior['arms'][arm]['rtl']['sha256']
    with pytest.raises(ValueError,match='Fresh'):m.prepare(root)


@pytest.mark.parametrize('poison',['wrapper','clock','seed','pair-filter','RTL','bare','closure','source','duplicate','failed'])
def test_preparation_fail_closed(prepared,poison):
    root,_,_,source,_ = prepared;manifest = m.read(root/'preparation.json')
    if poison=='wrapper':(root/'wrapper.v').write_text('changed');rebind(root,root/'wrapper.v')
    elif poison in ('clock','seed'):
        p=root/'recipe.json';value=m.read(p);value['timing']['target_frequency_mhz' if poison=='clock' else 'paired_route_seeds']=10 if poison=='clock' else [1,2,4];put(p,value);rebind(root,p)
    elif poison in ('pair-filter','RTL','bare'):
        p=root/'pairs.json';value=m.read(p)
        if poison=='pair-filter':value.pop()
        elif poison=='RTL':value[0]['arms']['csd']['candidate_rtl']['sha256']='e'*64
        else:value[0]['arms']['original']['bare_lut4']=1
        put(p,value);rebind(root,p)
    elif poison=='closure':manifest['files']=[e for e in manifest['files'] if not e['path'].endswith('../area/measurements/completion.json')];put(root/'preparation.json',manifest)
    elif poison=='source':source.write_text('changed')
    elif poison=='duplicate':manifest['files'].append(manifest['files'][0]);put(root/'preparation.json',manifest)
    else:m.write(root/'preparation-failure.json',{'error':'poison'})
    with pytest.raises(ValueError):m.validate_preparation(root)


def test_exact_approval_commits_every_binding_and_root(prepared,monkeypatch):
    root,_,_,_,_=prepared;manifest=m.read(root/'preparation.json');approval=root/'measurement-approval.json'
    review={'status':'approved-v10d-timing-measurements','freeze_commit':'c'*40,'reviewed_at_utc':m.now(),
        'preparation_sha256':m.sha(root/'preparation.json'),'recipe_sha256':manifest['recipe']['sha256'],'pairs_sha256':manifest['pairs']['sha256'],
        'collector_sha256':m.sha(m.__file__),'sequential_checker_sha256':m.sha(m.harness.__file__)}
    m.write(approval,review);seen=[];monkeypatch.setattr(m,'committed',lambda p,c:seen.append((p,c)))
    result=m.validate_approval(root,approval);assert len(seen)==len(result[-1])-1
    with pytest.raises(ValueError):m.validate_approval(root,root/'other.json')
    review['freeze_commit']='bad';put(approval,review)
    with pytest.raises(ValueError):m.validate_approval(root,approval)


def native_report(fmax=100):
    return {'fmax':{'clk$global':{'achieved':fmax,'constraint':12}},'utilization':{
        'ICESTORM_LC':{'used':200,'available':7680},'ICESTORM_RAM':{'used':0,'available':32},'ICESTORM_PLL':{'used':0,'available':2},
        'SB_IO':{'used':4,'available':206},'SB_GB':{'used':1,'available':8}},'critical_paths':[],'detailed_net_timings':[]}


def fixture_pins():
    return {name:{'pin':pin,'location':location} for name,pin,location in [('clk','J3',[0,16,1]),('serial_in','L5',[0,6,1]),('capture','T6',[12,0,1]),('serial_out','D8',[14,33,1])]}


def native_packed():
    cells={str(i):{'type':'ICESTORM_LC','parameters':{'DFF_ENABLE':f'{int(i<132):032b}','NEG_CLK':'0'},'connections':{'CLK':[3000]}} for i in range(200)}
    ports = {}
    for i,(name,row) in enumerate(fixture_pins().items()):
        x,y,z=row['location'];ports[name]={'direction':'output' if name=='serial_out' else 'input','bits':[1000+i]}
        cells['io'+str(i)]={'type':'SB_IO','connections':{'PACKAGE_PIN':[1000+i],'D_IN_0':[2000] if name=='clk' else []},'attributes':{'NEXTPNR_BEL':f'X{x}/Y{y}/io{z}'}}
    cells['global']={'type':'SB_GB','connections':{'USER_SIGNAL_TO_GLOBAL_BUFFER':[2000],'GLOBAL_BUFFER_OUTPUT':[3000]}}
    return {'modules':{'top':{'cells':cells,'ports':ports,'netnames':{'clk$global':{'bits':[3000]}},'settings':{'arch.type':'hx8k','arch.package':'ct256',
        'target_freq':'12000000.000000','threads':'00000000000000000000000000000001'}}}}


@pytest.mark.parametrize('poison',['nan','bool','clock','constraint','negative','capacity','ram','io','detail'])
def test_strict_native_report_rejects_invalid_or_changed_target(poison):
    r=native_report()
    if poison in ('nan','bool'):r['fmax']['clk$global']['achieved']=float('nan') if poison=='nan' else True
    elif poison=='clock':r['fmax']['second']={'achieved':12,'constraint':12}
    elif poison=='constraint':r['fmax']['clk$global']['constraint']=10
    elif poison=='negative':r['utilization']['ICESTORM_LC']['used']=-1
    elif poison=='capacity':r['utilization']['ICESTORM_LC']['used']=9000
    elif poison=='ram':r['utilization']['ICESTORM_RAM']['used']=1
    elif poison=='io':r['utilization']['SB_IO']['used']=3
    else:del r['detailed_net_timings']
    with pytest.raises(ValueError):m.report_metrics(r)


def test_exact_commands_fixed_recipe_and_reciprocal_period(tmp_path):
    cmd=m.route_command({'nextpnr':{'path':'/router'}},tmp_path,tmp_path/'map.json',tmp_path/'common.pcf',2)
    assert cmd[-6:]==['--freq','12','--seed','2','--threads','1']
    assert '--detailed-timing-report' in cmd and '--timing-allow-fail' not in cmd and '--pcf-allow-unconstrained' not in cmd
    for s in (0,4,True):
        with pytest.raises(ValueError):m.route_command({'nextpnr':{'path':'/router'}},tmp_path,tmp_path/'x',tmp_path/'p',s)
    assert m.report_metrics(native_report(20))['period_ns']==50
    assert m.report_metrics(native_report(11))['meets_12mhz'] is False
    assert 'stat' not in m.mapping_script(tmp_path) and 'synth_ice40 -top timing_top\ncheck -assert\n' in m.mapping_script(tmp_path)


@pytest.mark.parametrize('mode',['ok','timeout','missing','wrong-result'])
def test_mapping_retains_native_failures_and_actual132FF_inventory(prepared,monkeypatch,mode):
    root,pairs,tools,_,_=prepared;pair=m.read(root/'pairs.json')[0];folder=m.ROOT/'map'
    def run(command,log,owner,timeout):
        assert timeout==360;log.write_text("Parsing Verilog input from `"+str(folder/'candidate.v')+"'\nParsing Verilog input from `"+str(folder/'wrapper.v')+"'\n")
        if mode not in ('timeout','missing'):
            cells={str(i):{'type':'SB_DFF'} for i in range(132 if mode=='ok' else 131)}
            m.write(folder/'ice40-netlist.json',{'modules':{'timing_top':{'cells':cells}}})
        return {'returncode':None if mode=='timeout' else 0,'timed_out':mode=='timeout','elapsed_seconds':0.1}
    monkeypatch.setattr(m,'run_owned',run);monkeypatch.setattr(m.frozen,'data_invocations',lambda *a:{});monkeypatch.setattr(m.frozen,'abc_invocations',lambda *a:[])
    result=m.mapped_arm(root,pair,'original',folder,tools,None)
    assert result['success'] is (mode=='ok') and m.read(folder/'mapping.json')==result
    assert (folder/'ice40.log').exists() and result['candidate_rtl_sha256']==pair['arms']['original']['candidate_rtl']['sha256']


@pytest.mark.parametrize('mode',['ok','timeout','missing','bad-report','early','timing-fail'])
def test_route_raw_outputs_command_and_gate_failure_retention(prepared,monkeypatch,mode):
    root,_,tools,_,_=prepared;pair=m.read(root/'pairs.json')[0];scratch=m.ROOT/'scratch';scratch.mkdir();(scratch/'common.pcf').write_text(m.harness.PCF)
    mapped=scratch/'mapping'/pair['pair_id'].split(':')[1]/'original'/'ice40-netlist.json';m.write(mapped,{'synthetic':True})
    gate={'route_started_at_utc':'2999-01-01T00:00:00+00:00' if mode=='early' else '2000-01-01T00:00:00+00:00'};m.write(scratch/'route-gate.json',gate)
    folder=scratch/'routes'/'case'
    def run(cmd,log,owner,timeout):
        assert timeout==180 and '--threads' in cmd;log.write_text('synthetic route\n')
        if mode not in ('timeout','missing'):
            r=native_report(11 if mode=='timing-fail' else 100);r['fmax']['clk$global']['constraint']=13 if mode=='bad-report' else 12
            m.write(folder/'report.json',r);m.write(folder/'packed.json',native_packed());(folder/'routed.asc').write_text('.comment from next-pnr\n')
        return {'returncode':None if mode=='timeout' else 0,'timed_out':mode=='timeout','elapsed_seconds':0.1}
    monkeypatch.setattr(m,'run_owned',run);monkeypatch.setattr(m.paths,'classify_paths',lambda *a:{'classification':'unknown','reason':'synthetic'})
    result=m.routed_arm(pair,'original',1,folder,tools,None,scratch,gate)
    assert result['success'] is (mode in ('ok','timing-fail')) and m.read(folder/'route.json')==result
    if mode=='early':assert result['execution'] is None and not (folder/'route-command.json').exists()
    else:assert (folder/'route-command.json').exists()


def synthetic_collect(prepared,monkeypatch,mode):
    root,_,tools,_,_=prepared;manifest,r,pairs,tools,bindings=m.validate_preparation(root)
    approval=root/'measurement-approval.json';m.write(approval,{'synthetic':True})
    monkeypatch.setattr(m,'validate_approval',lambda *a:(manifest,r,pairs,tools,{'freeze_commit':'c'*40},bindings))
    monkeypatch.setattr(m.shutil,'disk_usage',lambda p:SimpleNamespace(free=20*1024**3))
    def mapping(root,p,a,folder,t,o):
        folder.mkdir(parents=True);m.write(folder/'ice40-netlist.json',{'synthetic':True})
        return {'pair_id':p['pair_id'],'arm':a,'success':not(mode=='map-fail' and p==pairs[0] and a=='csd'),'status':'complete',
            'error':None,'netlist_sha256':m.sha(folder/'ice40-netlist.json'),'completed_at_utc':m.now(),'primitive_counts':{'SB_DFF':132,'SB_LUT4':100,'SB_CARRY':30},'bare_lut4':100,'bare_carry':30}
    count=[]
    def seq(p,a,mp,scratch):
        count.append((p['pair_id'],a));return {'pair_id':p['pair_id'],'arm':a,'verified':mp['success'] is True,'error':None,'completed_at_utc':m.now()}
    def route(p,a,s,folder,t,o,scratch,gate):
        assert len(count)==64 and all(c['verified'] is True for c in m.read(root/'measurements/attempt-0000/sequential-checks.json'))
        success=not(mode=='route-fail' and p==pairs[0] and a=='csd' and s==2)
        return {'pair_id':p['pair_id'],'arm':a,'seed':s,'success':success,'status':'complete' if success else 'timeout','error':None,
            'path_classification':'unknown',**m.report_metrics(native_report(100 if a=='original' else 200))}
    monkeypatch.setattr(m,'mapped_arm',mapping);monkeypatch.setattr(m,'sequential_check',seq);monkeypatch.setattr(m,'routed_arm',route)
    if mode=='ok':done=m.collect(root,approval)
    else:
        with pytest.raises(ValueError,match='Incomplete'):m.collect(root,approval)
        done=m.read(root/'measurements/completion.json')
    return root,done


@pytest.mark.parametrize('mode',['ok','map-fail','route-fail'])
def test_full_fixed_grid_gate_completeprimary_and_no_retry(prepared,monkeypatch,mode):
    root,done=synthetic_collect(prepared,monkeypatch,mode);stage=root/'measurements/attempt-0000';summary=m.read(stage/'summary.json')
    assert done['mapping_jobs_completed']==done['sequential_checks_completed']==64 and len(summary['failure_matrix'])==192
    assert done['route_jobs_completed']==(0 if mode=='map-fail' else 192)
    assert summary['complete'] is (mode=='ok') and (summary['primary'] is None)==(mode!='ok')
    if mode=='ok':assert len(summary['paired_routes'])==96 and len(summary['per_pair'])==32 and summary['primary']['paired_period_ns']['mean']==-5
    if mode=='route-fail':assert done['successful_routes']==191
    raw=m.read(stage/'raw-evidence.json')
    with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
        assert set(z.namelist())=={x['path'] for x in raw['files']}
        for e in raw['files']:assert m.digest(z.read(e['path']))==e['sha256']
    with pytest.raises(ValueError,match='Single attempt'):m.collect(root,root/'measurement-approval.json')


def test_source_mutation_stops_unsubmitted_jobs_and_cleanup_failure_preserved(tmp_path,monkeypatch):
    scratch,stage=tmp_path/'scratch',tmp_path/'stage';scratch.mkdir();stage.mkdir();calls=[];output={};failures=[]
    owner=SimpleNamespace(cancel=lambda:(_ for _ in ()).throw(PermissionError('cleanup poison')))
    def recheck(*a):
        calls.append(1)
        if len(calls)==3:raise ValueError('source mutation')
    monkeypatch.setattr(m,'recheck',recheck)
    with pytest.raises(ValueError,match='source mutation'):
        m.phase([(str(i),(i,)) for i in range(20)],lambda x:{'success':True},output,'poison',stage,scratch,owner,failures,{}, {})
    assert len(output)<=2 and any(x['phase']=='owned-process-cleanup' for x in failures)


def test_dynamic_dependency_inventory_alias_and_transitive_resolution(tmp_path,monkeypatch):
    binary=tmp_path/'router';lib=tmp_path/'libx.dylib';alias=tmp_path/'lib-alias.dylib';binary.write_bytes(b'router');lib.write_bytes(b'lib');alias.symlink_to(lib)
    def output(cmd,**kwargs):
        if cmd[1]=='-l':return ''
        return str(binary)+':\n\t'+str(alias)+' (compatibility version 1.0.0, current version 1.0.0)\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n' if cmd[-1]==str(binary) else str(lib)+':\n\t'+str(lib)+' (compatibility version 1.0.0)\n'
    monkeypatch.setattr(m.subprocess,'check_output',output)
    result=m.dynamic_dependencies(binary)
    assert {x['path'] for x in result['files']}=={str(binary),str(lib)} and result['edges'][0]['resolved_path']==str(lib)
    monkeypatch.setattr(m.harness,'validate_timing_tools',lambda t:None)
    tools={'nextpnr':{'path':str(binary),'sha256':m.sha(binary)},'nextpnr_dynamic_dependencies':result};m.validate_tools(tools)
    lib.write_bytes(b'changed')
    with pytest.raises(ValueError,match='dependency changed'):m.validate_tools(tools)


@pytest.mark.parametrize('poison',['wrong-pin','duplicate-io','foreign-port','wrong-clock-settings','ff-loss','resource-disagreement','fmax-clock','ff-clock','negative-clock','gb-input'])
def test_packed_actual_pins_and132ff_required_separate_from_optional_attribution(poison):
    p=native_packed();r=native_report();tools={'pins':fixture_pins()}
    if poison=='wrong-pin':p['modules']['top']['cells']['io0']['attributes']['NEXTPNR_BEL']='X1/Y16/io1'
    elif poison=='duplicate-io':p['modules']['top']['cells']['io1']['connections']['PACKAGE_PIN']=[1000]
    elif poison=='foreign-port':p['modules']['top']['ports']['capture']['bits']=[2000]
    elif poison=='wrong-clock-settings':p['modules']['top']['settings']['target_freq']='10000000.000000'
    elif poison=='ff-loss':p['modules']['top']['cells']['0']['parameters']['DFF_ENABLE']='0'
    elif poison=='fmax-clock':r['fmax']={'bogus':{'achieved':100,'constraint':12}}
    elif poison=='ff-clock':p['modules']['top']['cells']['0']['connections']['CLK']=[3001]
    elif poison=='negative-clock':p['modules']['top']['cells']['0']['parameters']['NEG_CLK']='1'
    elif poison=='gb-input':p['modules']['top']['cells']['global']['connections']['USER_SIGNAL_TO_GLOBAL_BUFFER']=[2001]
    else:r['utilization']['ICESTORM_LC']['used']=199
    with pytest.raises(ValueError):m.validate_packed(p,r,tools)


def test_exact_packed_pin_inventory_succeeds():
    result=m.validate_packed(native_packed(),native_report(),{'pins':fixture_pins()})
    assert result['ff_count']==132 and result['pin_assignments']['clk']=={'cell':'io0','package_pin':'J3','location':[0,16,1]}


def area_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);old=tmp_path/m.AREA_ROOT;old.mkdir(parents=True)
    audit_source=tmp_path/'scripts/audit_v10d_hardware.py';audit_source.parent.mkdir();audit_source.write_text('# synthetic area audit')
    m.write(old/'preparation.json',{'synthetic':True});monkeypatch.setattr(m,'AREA_PREPARATION_SHA',m.sha(old/'preparation.json'))
    pair={'pair_id':'synthetic','arms':{}};rows=[{'pair_id':'p'+str(i),'arm':a} for i in range(32) for a in m.ARMS]
    pairs=[{'pair_id':'p'+str(i)} for i in range(32)]
    stage=old/'measurements/attempt-0000';stage.mkdir(parents=True)
    for name in ('frontends.json','algebra-proofs.json','summary.json','measurement-gate.json'):m.write(stage/name,{'synthetic':True})
    m.write(stage/'arm-measurements.json',rows);(stage/'raw-evidence.zip').write_bytes(b'synthetic sealed archive')
    m.write(old/'measurement-approval.json',{'synthetic':True});m.write(old/'label-release.json',{'synthetic':True})
    done={'complete':True,'failures':[],'pair_count':32,'frontend_jobs_completed':64,'successful_frontend_jobs':64,
        'universal_actual_rtl_pairs_proved':32,'proof_records':32,'fresh_synthesis_jobs_completed':64,'attempt':'attempt-0000',
        'approval_sha256':m.sha(old/'measurement-approval.json'),'release_sha256':m.sha(old/'label-release.json'),
        **{k:m.sha(stage/n) for k,n in [('frontends_sha256','frontends.json'),('algebra_proofs_sha256','algebra-proofs.json'),('arm_measurements_sha256','arm-measurements.json'),('summary_sha256','summary.json'),('measurement_gate_sha256','measurement-gate.json')]}}
    m.write(stage/'completion.json',done);m.copy(stage/'completion.json',old/'measurements/completion.json');monkeypatch.setattr(m,'AREA_COMPLETION_SHA',m.sha(stage/'completion.json'))
    audit={'schema':'isaforge-v10d-independent-portable-audit-v1','status':'pass','complete':True,'failures':[],
        'frontend_records_verified':64,'arms_recounted':64,'rtl_pairs_proved_shared_checker':32,
        'audit_source_sha256':m.sha(audit_source),'completion_sha256':m.AREA_COMPLETION_SHA,'preparation_sha256':m.AREA_PREPARATION_SHA,
        'archive_sha256':m.sha(stage/'raw-evidence.zip')}
    m.write(old/'independent-audit.json',audit);m.write(stage/'raw-evidence.json',{'completion_sha256':m.AREA_COMPLETION_SHA,'archive_sha256':audit['archive_sha256']})
    monkeypatch.setattr(m.area,'validate_preparation',lambda r:({'synthetic':True},{},pairs,{},{}))
    return old,stage,done,audit


def test_explicit_complete_v10d_adapter_binds_every_area_stage(tmp_path,monkeypatch):
    old,stage,done,audit=area_fixture(tmp_path,monkeypatch)
    _,pairs,metrics,bindings=m.area_inputs(old,old/'independent-audit.json')
    assert len(pairs)==32 and len(metrics)==64
    assert all(stage/name in bindings for name in ('frontends.json','algebra-proofs.json','measurement-gate.json','summary.json','raw-evidence.zip','raw-evidence.json','completion.json','arm-measurements.json'))


@pytest.mark.parametrize('poison',['partial-frontends','partial-proofs','partial-arms','failed-audit','archive','gate','arm-grid','audit-source'])
def test_adapter_rejects_incomplete_or_changed_prior_evidence(tmp_path,monkeypatch,poison):
    old,stage,done,audit=area_fixture(tmp_path,monkeypatch)
    if poison.startswith('partial-'):
        done[{'partial-frontends':'successful_frontend_jobs','partial-proofs':'universal_actual_rtl_pairs_proved','partial-arms':'fresh_synthesis_jobs_completed'}[poison]]-=1
        put(old/'measurements/completion.json',done);monkeypatch.setattr(m,'AREA_COMPLETION_SHA',m.sha(old/'measurements/completion.json'))
    elif poison=='failed-audit':audit['complete']=False;put(old/'independent-audit.json',audit)
    elif poison=='archive':(stage/'raw-evidence.zip').write_bytes(b'changed')
    elif poison=='gate':put(stage/'measurement-gate.json',{'changed':True})
    elif poison=='arm-grid':
        rows=m.read(stage/'arm-measurements.json');rows[-1]=rows[0];put(stage/'arm-measurements.json',rows)
    else:(tmp_path/'scripts/audit_v10d_hardware.py').write_text('changed')
    with pytest.raises(ValueError):m.area_inputs(old,old/'independent-audit.json')


def test_archive_guard_failure_nulls_primary_even_after_full_routes(prepared,monkeypatch):
    monkeypatch.setattr(m.area,'workspace_bytes',lambda *p:m.MAX_ATTEMPT_BYTES if len(p)==1 else 0)
    root,done=synthetic_collect(prepared,monkeypatch,'archive-fail')
    assert done['successful_routes']==192
    assert done['complete'] is False and m.read(root/'measurements/attempt-0000/summary.json')['primary'] is None


@pytest.mark.parametrize('folder',['','constant-zero'])
def test_packed_validator_replays_tracked_native_toy_evidence_without_native(folder):
    package=ROOT/'results/2026-10-15-v10d-timing-preflight'/folder
    with zipfile.ZipFile(package/'raw-evidence.zip') as archive:
        def item(name):
            paths=[p for p in archive.namelist() if p.endswith('/'+name)]
            assert len(paths)==1
            return json.loads(archive.read(paths[0]))
        report,packed=item('report.json'),item('packed.json')
    result=m.validate_packed(packed,report,{'pins':fixture_pins()})
    assert result['ff_count']==132 and result['clock']==next(iter(report['fmax'])) and len(result['pin_assignments'])==4

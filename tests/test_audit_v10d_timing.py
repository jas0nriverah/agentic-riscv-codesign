"""Synthetic portable timing evidence only; no native tools or study preparation."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_v10d_timing',ROOT/'scripts/audit_v10d_timing.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def report():
    return {'critical_paths':[],'detailed_net_timings':[],'fmax':{'clk$SB_IO_IN_$glb_clk':{'achieved':50.0,'constraint':12}},
        'utilization':{'ICESTORM_LC':{'used':150,'available':7680},'ICESTORM_RAM':{'used':0,'available':32},
            'ICESTORM_PLL':{'used':0,'available':2},'SB_IO':{'used':4,'available':206},'SB_GB':{'used':1,'available':8}}}


def test_report_full_harness_reciprocal_period():
    result=m.report_metrics(report())
    assert result['fmax_mhz']==50 and result['period_ns']==20 and result['meets_12mhz'] is True


@pytest.mark.parametrize('poison', ['bool_fmax','nan','zero','negative','bool_constraint','wrong_constraint','other_clock','missing_clock','bool_count','over_capacity','ram','pll'])
def test_poisoned_native_reports_fail_closed(poison):
    r=report();clock=next(iter(r['fmax'].values()))
    if poison=='bool_fmax':clock['achieved']=True
    elif poison=='nan':clock['achieved']=float('nan')
    elif poison=='zero':clock['achieved']=0
    elif poison=='negative':clock['achieved']=-1
    elif poison=='bool_constraint':clock['constraint']=True
    elif poison=='wrong_constraint':clock['constraint']=13
    elif poison=='other_clock':r['fmax']['second']=dict(clock)
    elif poison=='missing_clock':r['fmax']={}
    elif poison=='bool_count':r['utilization']['ICESTORM_LC']['used']=True
    elif poison=='over_capacity':r['utilization']['ICESTORM_LC']['used']=7681
    elif poison=='ram':r['utilization']['ICESTORM_RAM']['used']=1
    elif poison=='pll':r['utilization']['ICESTORM_PLL']['used']=1
    with pytest.raises(ValueError):m.report_metrics(r)


def rows():
    pairs=[{'pair_id':str(i),'formula':'SYNTHETIC','constant_u32':c,'context':ctx} for i,(c,ctx) in enumerate(__import__('itertools').product(m.independent.CONSTANTS,m.independent.CONTEXTS))]
    routes=[]
    for p in pairs:
        for arm in m.ARMS:
            for seed in m.SEEDS:
                metrics=m.report_metrics(report());metrics['fmax_mhz']=50 if arm=='original' else 40;metrics['period_ns']=1000/metrics['fmax_mhz']
                routes.append({'pair_id':p['pair_id'],'arm':arm,'seed':seed,'success':True,**metrics})
    return pairs,routes


def test_all192_routes_pair_with_matched_seed_and_preserve_losses():
    pairs,routes=rows();points,summary=m.paired_results(pairs,list(reversed(routes)))
    assert len(points)==96 and {p['seed'] for p in points}=={1,2,3}
    assert summary['paired_period_ns']['mean']==5 and summary['paired_period_ns']['higher']==96
    assert summary['paired_fmax_mhz']['mean']==-10
    assert all(p['original_path_classification']=='unknown' for p in points)


@pytest.mark.parametrize('poison',['missing','duplicate','foreign','failed','wrong_seed'])
def test_no_route_filtering_or_unmatched_seed(poison):
    pairs,routes=rows()
    if poison=='missing':routes.pop()
    elif poison=='duplicate':routes[-1]=copy.deepcopy(routes[0])
    elif poison=='foreign':routes[-1]['pair_id']='foreign'
    elif poison=='failed':routes[-1]['success']=False
    else:routes[-1]['seed']=4
    with pytest.raises(ValueError):m.paired_results(pairs,routes)


def test_no_native_or_collector_imports():
    import ast
    tree=ast.parse((ROOT/'scripts/audit_v10d_timing.py').read_text())
    names=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):names.extend(x.name for x in n.names)
        elif isinstance(n,ast.ImportFrom):names.append(n.module or '')
    assert not any('measure_' in n or n in ('subprocess','os') for n in names)


def pin_tools():
    return {'pins':{name:{'pin':pin,'location':loc} for name,pin,loc in [('clk','J3',[0,16,1]),('serial_in','L5',[0,6,1]),('capture','T6',[12,0,1]),('serial_out','D8',[14,33,1])]}}


def route_bytes():
    r=report();r['utilization']['ICESTORM_LC']['used']=132
    cells={f'lc{i}':{'type':'ICESTORM_LC','connections':{'CLK':[3001]},'parameters':{'DFF_ENABLE':'1','NEG_CLK':'0'}} for i in range(132)}
    cells.update({f'io{i}':{'type':'SB_IO','connections':{'PACKAGE_PIN':[1000+i]},'parameters':{},'attributes':{'NEXTPNR_BEL':f"X{v['location'][0]}/Y{v['location'][1]}/io{v['location'][2]}"}} for i,v in enumerate(pin_tools()['pins'].values())});cells['io0']['connections']['D_IN_0']=[3000];cells['gb']={'type':'SB_GB','connections':{'USER_SIGNAL_TO_GLOBAL_BUFFER':[3000],'GLOBAL_BUFFER_OUTPUT':[3001]},'parameters':{}}
    packed={'creator':'Next Generation Place and Route (Version )','modules':{'top':{'cells':cells,'netnames':{'clk$SB_IO_IN_$glb_clk':{'bits':[3001]}},'ports':{name:{'direction':'output' if name=='serial_out' else 'input','bits':[1000+i]} for i,name in enumerate(pin_tools()['pins'])},'settings':{'arch.type':'hx8k','arch.package':'ct256','threads':'00000000000000000000000000000001','target_freq':'12000000.000000'}}}}
    return json.dumps(r).encode(),json.dumps(packed).encode(),b'.comment from next-pnr\n.device 8k\n.io_tile 0 0\n000000000000000000\n',b'Info: Program finished normally.\n'


def test_independent_raw_report_recount_and_retained_asc():
    r,p,a,l=route_bytes();assert m.verify_route_bytes(r,p,a,l,pin_tools())['period_ns']==20


@pytest.mark.parametrize('poison',['packed_count','empty_packed','asc_wrongdevice','asc_missing','log_failure','log_incomplete'])
def test_raw_route_evidence_poison(poison):
    r,p,a,l=route_bytes()
    if poison=='packed_count':
        v=json.loads(p);v['modules']['top']['cells'].pop('lc1');p=json.dumps(v).encode()
    elif poison=='empty_packed':p=b'{"modules":{"top":{"cells":{}}}}'
    elif poison=='asc_wrongdevice':a=a.replace(b'.device 8k',b'.device 1k')
    elif poison=='asc_missing':a=b''
    elif poison=='log_failure':l+=b'ERROR: route failed\n'
    else:l=b'Info: packing\n'
    with pytest.raises(ValueError):m.verify_route_bytes(r,p,a,l,pin_tools())


def test_fixed_commands_have_no_frequency_failure_override_or_clock_division():
    cmd=m.route_command({'nextpnr':{'path':'/SYNTHETIC/nextpnr'}},Path('/old/repo/route'),Path('/old/repo/mapped.json'),Path('/old/repo/common.pcf'),2)
    assert cmd[cmd.index('--seed')+1]=='2' and '--detailed-timing-report' in cmd
    assert '--timing-allow-fail' not in cmd and '--pcf-allow-unconstrained' not in cmd
    assert cmd[cmd.index('--threads')+1]=='1' and cmd[cmd.index('--freq')+1]=='12'
    with pytest.raises(ValueError):m.route_command({'nextpnr':{'path':'x'}},Path('x'),Path('x'),Path('x'),True)


def encoded(value):return json.dumps(value).encode()


def route_fixture():
    pair={'pair_id':'v10-csd:SYNTHETIC','constant_u32':11,'context':'direct_product'}
    folder=Path('/archived/nonexistent/repository/generated/v10d-timing/attempt-0000/routes/SYNTHETIC/original/seed-1')
    mapped=Path('/archived/nonexistent/repository/generated/v10d-timing/attempt-0000/mapping/SYNTHETIC/original')
    tools={'nextpnr':{'path':'/nonexistent/native/nextpnr','sha256':'b'*64},**pin_tools()}
    gate={'route_started_at_utc':'2026-10-15T00:00:02+00:00'};gate_sha=m.sha(encoded(gate))
    stem='routes/SYNTHETIC/original/seed-1/';r,p,a,l=route_bytes()
    content={stem+'report.json':r,stem+'packed.json':p,stem+'routed.asc':a,stem+'route.log':l,
        stem+'common.pcf':m.sequential.PCF.encode(),'mapping/SYNTHETIC/original/ice40-netlist.json':b'{"SYNTHETIC":true}'}
    cmd=m.route_command(tools,folder,mapped/'ice40-netlist.json',folder/'common.pcf',1)
    row={'schema':'isaforge-v10d-timing-route-v1','pair_id':pair['pair_id'],'arm':'original','seed':1,
        'success':True,'status':'complete','error':None,'execution':{'returncode':0,'timed_out':False,'elapsed_seconds':0.1},
        'started_at_utc':'2026-10-15T00:00:03+00:00','completed_at_utc':'2026-10-15T00:00:04+00:00',
        'command':cmd,'nextpnr':tools['nextpnr'],'device':'iCE40HX8K','package':'CT256','target_frequency_mhz':12,'threads':1,
        'route_gate_sha256':gate_sha,'mapped_netlist_sha256':m.sha(content['mapping/SYNTHETIC/original/ice40-netlist.json']),
        **m.verify_route_bytes(r,p,a,l,tools)}
    row['path_audit']=m.paths.classify_paths({},json.loads(p),json.loads(r));row['path_classification']=row['path_audit']['classification']
    content[stem+'route-command.json']=encoded({'command':cmd,'started_at_utc':row['started_at_utc'],'timeout_seconds':180,'route_gate_sha256':gate_sha,'mapped_netlist_sha256':row['mapped_netlist_sha256']})
    def refresh():
        for key,name in [('command_sha256','route-command.json'),('log_sha256','route.log'),('report_sha256','report.json'),('packed_json_sha256','packed.json'),('asc_sha256','routed.asc'),('pcf_sha256','common.pcf')]:row[key]=m.sha(content[stem+name]) if stem+name in content else None
        content[stem+'route.json']=encoded(row)
    refresh()
    return pair,row,content,folder,mapped,tools,gate,gate_sha,{},refresh


def test_route_replay_is_portable_and_keeps_unknown_classification_honest():
    args=route_fixture();result=m.verify_route(args[0],'original',1,*args[1:9])
    assert result['fmax_mhz']==50 and args[1]['path_classification']=='unknown'


@pytest.mark.parametrize('poison',['early_start','wrong_seed','wrong_command','wrong_source','wrong_pcf','changed_report','changed_count','lost_ff','false_classification','negative_elapsed','bool_count'])
def test_reauthenticated_route_poisons_do_not_survive_raw_replay(poison):
    args=route_fixture();pair,row,content,folder,mapped,tools,gate,gate_sha,graph,refresh=args;stem='routes/SYNTHETIC/original/seed-1/'
    if poison=='early_start':
        row['started_at_utc']='2026-10-15T00:00:01+00:00'
        command=json.loads(content[stem+'route-command.json']);command['started_at_utc']=row['started_at_utc'];content[stem+'route-command.json']=encoded(command)
    elif poison=='wrong_seed':row['seed']=True
    elif poison=='wrong_command':
        row['command'][row['command'].index('--freq')+1]='13'
        command=json.loads(content[stem+'route-command.json']);command['command']=row['command'];content[stem+'route-command.json']=encoded(command)
    elif poison=='wrong_source':content['mapping/SYNTHETIC/original/ice40-netlist.json']=b'{"SYNTHETIC":false}'
    elif poison=='wrong_pcf':content[stem+'common.pcf']=b'set_io clk BAD\n'
    elif poison=='changed_report':
        report=json.loads(content[stem+'report.json']);report['fmax']['clk$SB_IO_IN_$glb_clk']['achieved']=60;content[stem+'report.json']=encoded(report)
    elif poison=='clock11':
        report=json.loads(content[stem+'report.json']);report['fmax']['clk$SB_IO_IN_$glb_clk']['achieved']=11;content[stem+'report.json']=encoded(report)
        row.update(m.report_metrics(report))
    elif poison=='changed_count':
        packed=json.loads(content[stem+'packed.json']);packed['modules']['top']['cells'].pop('lc0');content[stem+'packed.json']=encoded(packed)
    elif poison=='lost_ff':
        packed=json.loads(content[stem+'packed.json']);packed['modules']['top']['cells']['lc0']['parameters']['DFF_ENABLE']='0';content[stem+'packed.json']=encoded(packed)
    elif poison=='false_classification':row['path_classification']='datapath-boundary';row['path_audit']['classification']='datapath-boundary'
    elif poison=='negative_elapsed':row['execution']['elapsed_seconds']=-1
    else:
        report=json.loads(content[stem+'report.json']);report['utilization']['SB_GB']['used']=True;content[stem+'report.json']=encoded(report)
    refresh()
    with pytest.raises(ValueError):m.verify_route(args[0],'original',1,*args[1:9])


def test_failed_route_retains_partial_files_and_cannot_become_primary():
    args=route_fixture();row,content,refresh=args[1],args[2],args[-1];stem='routes/SYNTHETIC/original/seed-1/'
    row.update(success=False,status='timeout',error='SYNTHETIC timeout',execution={'returncode':-9,'timed_out':True,'elapsed_seconds':180})
    for name in ('report.json','packed.json','routed.asc'):content.pop(stem+name)
    refresh();assert m.verify_route(args[0],'original',1,*args[1:9]) is None
    pairs,routes=rows();mappings=[{'pair_id':p['pair_id'],'arm':a,'success':True,'primitive_counts':{'SB_DFF':132},'bare_lut4':0,'bare_carry':0} for p in pairs for a in m.ARMS]
    checks=[{'pair_id':r['pair_id'],'arm':r['arm'],'verified':True} for r in mappings]
    for r in routes:r.update(status='complete',error=None,path_classification='unknown')
    routes[0].update(success=False,status='timeout',error='SYNTHETIC timeout')
    summary=m.study_summary(pairs,mappings,checks,routes,[{'phase':'route','error':'SYNTHETIC timeout'}])
    assert summary['complete'] is False and summary['primary'] is None and len(summary['failure_matrix'])==192 and not summary['paired_routes']


def mapping_fixture(monkeypatch):
    spec=importlib.util.spec_from_file_location('timing_fixture',ROOT/'tests/test_prepare_v10_timing.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    netlist=fixture.toy_netlist();netlist['creator']='SYNTHETIC yosys'
    folder=Path('/nonexistent/archived/mapping/SYNTHETIC/original');candidate=b'// SYNTHETIC XOR toy only\n'
    pair={'constant_u32':11,'context':'direct_product','arms':{'original':{'candidate_rtl':{'sha256':m.sha(candidate)}}}}
    yosys={'path':'/nonexistent/tools/yosys','sha256':'a'*64,'version':'SYNTHETIC yosys'};abc={'path':'/nonexistent/tools/yosys-abc','sha256':'b'*64}
    tools={'area_tools':{'executables':{'yosys':yosys,'abc':abc},'yosys_data':{'path':'/nonexistent/share/yosys','files':[{'path':'ice40/cells_sim.v','sha256':'c'*64}]}}}
    alias={'sha256':'c'*64,'resolved_path':'/nonexistent/share/yosys/ice40/cells_sim.v','logged_paths':['/nonexistent/alias/cells_sim.v']}
    provenance={'yosys':yosys,'abc_invocations':[{'path':abc['path'],'sha256':abc['sha256']}], 'yosys_data_invocations':{'ice40/cells_sim.v':alias}}
    log=(f"Parsing Verilog input from `{folder/'candidate.v'}'.\nParsing Verilog input from `{folder/'wrapper.v'}'.\nParsing Verilog input from `/nonexistent/alias/cells_sim.v'.\nRunning ABC command: \"<yosys-exe-dir>/yosys-abc\" -s -f script\n").encode()
    monkeypatch.setattr(m.independent,'expected_values',lambda constant,context,samples:[a^b for a,b in samples])
    return pair,candidate,netlist,folder,tools,provenance,log


def test_shared_sequential_replay_uses_all2148_99edge_frames(monkeypatch):
    pair,candidate,netlist,folder,tools,provenance,log=mapping_fixture(monkeypatch)
    counts,check=m.verify_mapping_bytes(pair,'original',candidate,m.sequential.wrapper_rtl().encode(),m.mapping_script(folder).encode(),log,encoded(netlist),folder,tools,provenance)
    assert counts['SB_DFF']==132 and check['transactions']==2148 and check['edges_per_parallel_frame']==99
    assert check['boundary']['result_capture_edge']==67


@pytest.mark.parametrize('poison',['wrong_wrapper','unknown_primitive','clock','swapped_result','unknown_bit','foreign_read','wrong_abc','creator'])
def test_reauthenticated_wrapped_raw_poisons_fail(monkeypatch,poison):
    pair,candidate,netlist,folder,tools,provenance,log=mapping_fixture(monkeypatch);wrapper=m.sequential.wrapper_rtl().encode()
    cells=netlist['modules']['timing_top']['cells']
    if poison=='wrong_wrapper':wrapper=wrapper.replace(b'result_q[0]',b'result_q[1]')
    elif poison=='unknown_primitive':cells['result_00']['type']='SB_DFFE'
    elif poison=='clock':cells['result_00']['connections']['C']=[3]
    elif poison=='swapped_result':cells['result_00']['connections']['D'],cells['result_01']['connections']['D']=cells['result_01']['connections']['D'],cells['result_00']['connections']['D']
    elif poison=='unknown_bit':cells['result_00']['connections']['D']=['x']
    elif poison=='foreign_read':log+=b"Parsing Verilog input from `/unbound/foreign.v'.\n"
    elif poison=='wrong_abc':log=log.replace(b'<yosys-exe-dir>/yosys-abc',b'/unbound/abc')
    else:netlist['creator']='foreign yosys'
    with pytest.raises(ValueError):m.verify_mapping_bytes(pair,'original',candidate,wrapper,m.mapping_script(folder).encode(),log,encoded(netlist),folder,tools,provenance)


def test_finite_below_target_report_is_retained_as_valid_timing_miss():
    args=route_fixture();row,content,refresh=args[1],args[2],args[-1];stem='routes/SYNTHETIC/original/seed-1/'
    report=json.loads(content[stem+'report.json']);report['fmax']['clk$SB_IO_IN_$glb_clk']['achieved']=11
    content[stem+'report.json']=encoded(report);row.update(m.report_metrics(report));refresh()
    result=m.verify_route(args[0],'original',1,*args[1:9])
    assert result['meets_12mhz'] is False and result['fmax_mhz']==11 and row['success'] is True


@pytest.mark.parametrize('poison',['wrong_bel','duplicate_bel','wrong_io_bit','wrong_direction','bool_port'])
def test_actual_packed_pin_assignment_is_mandatory_even_when_path_unknown(poison):
    r,p,a,l=route_bytes();packed=json.loads(p);top=packed['modules']['top'];io=top['cells']['io0']
    if poison=='wrong_bel':io['attributes']['NEXTPNR_BEL']='X1/Y16/io1'
    elif poison=='duplicate_bel':io['attributes']['NEXTPNR_BEL']=top['cells']['io1']['attributes']['NEXTPNR_BEL']
    elif poison=='wrong_io_bit':io['connections']['PACKAGE_PIN']=[2000]
    elif poison=='wrong_direction':top['ports']['clk']['direction']='output'
    else:top['ports']['clk']['bits']=[True]
    with pytest.raises(ValueError):m.verify_route_bytes(r,encoded(packed),a,l,pin_tools())


@pytest.mark.parametrize('suffix',['','constant-zero'])
def test_portable_replay_of_both_tracked_native_synthetic_shapes(suffix):
    import zipfile
    root=ROOT/'results/2026-10-15-v10d-timing-preflight'/suffix
    with zipfile.ZipFile(root/'raw-evidence.zip') as archive:
        content={Path(name).name:archive.read(name) for name in archive.namelist()}
    result=m.verify_route_bytes(*(content[name] for name in ('report.json','packed.json','routed.asc','routing.log')),pin_tools())
    assert result['packed_inventory']['ff_count']==132 and result['packed_inventory']['primitive_counts']['SB_IO']==4


def test_archive_replay_authenticates_every_member_and_completion(tmp_path):
    import zipfile
    done={'SYNTHETIC':True};(tmp_path/'completion.json').write_bytes(encoded(done))
    member=m.PREFIX+'attempt-0000/SYNTHETIC.txt';body=b'SYNTHETIC ONLY'
    with zipfile.ZipFile(tmp_path/'raw-evidence.zip','w') as archive:archive.writestr(member,body)
    raw={'schema':'isaforge-v10d-timing-raw-evidence-v1','attempt':'attempt-0000','archive':'raw-evidence.zip',
        'completion_sha256':m.sha(encoded(done)),'archive_sha256':m.sha((tmp_path/'raw-evidence.zip').read_bytes()),
        'files':[{'path':member,'size':len(body),'sha256':m.sha(body)}]}
    (tmp_path/'raw-evidence.json').write_bytes(encoded(raw))
    manifest,content=m.archive_content(tmp_path,done,'attempt-0000');assert content=={'SYNTHETIC.txt':body}
    raw['files'][0]['size']=True;(tmp_path/'raw-evidence.json').write_bytes(encoded(raw))
    with pytest.raises(ValueError):m.archive_content(tmp_path,done,'attempt-0000')


@pytest.mark.parametrize('name',['../escape','generated/v10d-timing/attempt-0000/../escape','generated/v10d-timing/attempt-0000/a\\b'])
def test_reauthenticated_unsafe_archive_names_fail(tmp_path,name):
    import zipfile
    done={'SYNTHETIC':True};(tmp_path/'completion.json').write_bytes(encoded(done));body=b'SYNTHETIC'
    with zipfile.ZipFile(tmp_path/'raw-evidence.zip','w') as archive:archive.writestr(name,body)
    raw={'schema':'isaforge-v10d-timing-raw-evidence-v1','attempt':'attempt-0000','archive':'raw-evidence.zip',
        'completion_sha256':m.sha(encoded(done)),'archive_sha256':m.sha((tmp_path/'raw-evidence.zip').read_bytes()),
        'files':[{'path':name,'size':len(body),'sha256':m.sha(body)}]}
    (tmp_path/'raw-evidence.json').write_bytes(encoded(raw))
    with pytest.raises(ValueError):m.archive_content(tmp_path,done,'attempt-0000')


@pytest.mark.parametrize('poison',['bogus_clock','ff_clock','negative_edge','gb_input','clock_alias_bool'])
def test_full_harness_clock_identity_is_mandatory_not_optional_attribution(poison):
    r,p,a,l=route_bytes();report=json.loads(r);packed=json.loads(p);top=packed['modules']['top']
    if poison=='bogus_clock':report['fmax']['bogus']=report['fmax'].pop('clk$SB_IO_IN_$glb_clk')
    elif poison=='ff_clock':top['cells']['lc0']['connections']['CLK']=[3000]
    elif poison=='negative_edge':top['cells']['lc0']['parameters']['NEG_CLK']='1'
    elif poison=='gb_input':top['cells']['gb']['connections']['USER_SIGNAL_TO_GLOBAL_BUFFER']=[3002]
    else:top['netnames']['clk$SB_IO_IN_$glb_clk']['bits']=[True]
    with pytest.raises(ValueError):m.verify_route_bytes(encoded(report),encoded(packed),a,l,pin_tools())


def test_honest_sequential_failure_replays_as_incomplete_evidence(monkeypatch):
    pair,candidate,netlist,folder,tools,provenance,log=mapping_fixture(monkeypatch)
    monkeypatch.setattr(m.independent,'expected_values',lambda constant,context,samples:[0]*len(samples))
    counts,check=m.verify_mapping_bytes(pair,'original',candidate,m.sequential.wrapper_rtl().encode(),m.mapping_script(folder).encode(),log,encoded(netlist),folder,tools,provenance,retain_sequential_failure=True)
    assert counts['SB_DFF']==132 and '_sequential_error' in check
    pair['pair_id']='v10-csd:SYNTHETIC';mapping={'success':True,'netlist_sha256':m.sha(encoded(netlist)),'completed_at_utc':'2026-10-15T00:00:01+00:00'}
    row={'schema':'isaforge-v10d-timing-sequential-record-v1','pair_id':pair['pair_id'],'arm':'original','verified':False,
        'error':check['_sequential_error'],'started_at_utc':'2026-10-15T00:00:02+00:00','completed_at_utc':'2026-10-15T00:00:03+00:00',
        'netlist_sha256':mapping['netlist_sha256'],'sequential_checker_sha256':'SYNTHETIC checker','check':None}
    content={'sequential/SYNTHETIC/original/check.json':encoded(row)}
    m.verify_check(pair,'original',row,mapping,check,content,'SYNTHETIC checker')
    row.update(verified=True,error=None,check={});content['sequential/SYNTHETIC/original/check.json']=encoded(row)
    with pytest.raises(ValueError):m.verify_check(pair,'original',row,mapping,check,content,'SYNTHETIC checker')

"""Synthetic packed connectivity contracts; no native jobs or study inputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import v10d_timing_paths as m

spec = importlib.util.spec_from_file_location('timing_boundary_fixtures', ROOT/'tests/test_prepare_v10_timing.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


@pytest.fixture
def case():
    mapped = fixtures.toy_netlist()
    source = mapped['modules']['timing_top']
    cells, nets = {}, {}
    for index, name in enumerate(m.sequential.FF_NAMES):
        q = source['cells'][name]['connections']['Q'][0] + 1000
        cells['opaque'+str(index)] = {'type':'ICESTORM_LC', 'parameters':{'DFF_ENABLE':'1','NEG_CLK':'0'},
            'attributes':{'NEXTPNR_BEL':f'X{index+1}/Y1/lc0'}, 'connections':{'O':[q],'CLK':[3000], 'I0':[4000]}}
    for group, stem in [('launch','launch_q'),('result','result_q'),('output','output_q')]:
        for index, name in enumerate(m.sequential.GROUPS[group]):
            q = source['cells'][name]['connections']['Q'][0]
            source['netnames'] = source.get('netnames', {})
            nets[f'{stem}[{index}]'] = {'bits':[q+1000]}
        source['netnames'][stem] = {'bits':[source['cells'][name]['connections']['Q'][0] for name in m.sequential.GROUPS[group]]}
    for name, alias in [('serial_sample0','serial_s0'),('serial_sample1','serial_s1'),('capture_sample0','capture_s0'),('capture_sample1','capture_s1')]:
        q = source['cells'][name]['connections']['Q'][0]
        nets[alias] = {'bits':[q+1000]};source['netnames'][alias] = {'bits':[q]}
    ports = {name:{'direction':'output' if name=='serial_out' else 'input','bits':[index+5000]}
             for index,name in enumerate(('clk','serial_in','capture','serial_out'))}
    for name, port in ports.items():
        cells['io_'+name] = {'type':'SB_IO', 'connections':{'PACKAGE_PIN':port['bits'], 'D_IN_0':[2000] if name=='clk' else [2001], 'D_OUT_0':[]}}
    cells['io_serial_out']['connections']['D_OUT_0'] = nets.pop('output_q[0]')['bits']
    cells['buffer'] = {'type':'SB_GB','connections':{'USER_SIGNAL_TO_GLOBAL_BUFFER':[2000],'GLOBAL_BUFFER_OUTPUT':[3000]}}
    nets['actual_clock'] = {'bits':[3000]}
    start, end = 'opaque3', 'opaque100'
    cells[end]['connections']['I0'] = cells[start]['connections']['O']
    def endpoint(name, port):
        return {'cell':name,'port':port,'loc':[int(name[6:])+1,1]}
    a,b = endpoint(start,'O'),endpoint(end,'I0')
    nets['path_wire'] = {'bits':cells[start]['connections']['O']}
    report = {'fmax':{'actual_clock':{'achieved':100.,'constraint':12}},'critical_paths':[
        {'from':'posedge actual_clock','to':'posedge actual_clock','path':[
            {'type':'clk-to-q','from':a,'to':a,'delay':.5},
            {'type':'routing','from':a,'to':b,'delay':1.,'net':'path_wire'},
            {'type':'setup','from':b,'to':b,'delay':.1}]}]}
    packed = {'modules':{'arbitrary_top_name':{'cells':cells,'netnames':nets,'ports':ports}}}
    return mapped,packed,report


def test_boundary_bijection_uses_wires_not_cell_names_and_recovers_missing_output_alias(case):
    result = m.classify_paths(*case)
    assert result['classification']=='wrapper-boundary' and result['boundary_ff_count']==132
    assert result['start']['mapped_cell']=='capture_sample1'
    assert result['end']['mapped_cell']=='output_00'
    assert result['end']['correspondence']=='serial_out PACKAGE_PIN -> SB_IO.D_OUT_0'


def test_actual_launch_to_result_path_attributed_only_to_datapath_boundary(case):
    mapped,packed,report=case;module=next(iter(packed['modules'].values()));cells=module['cells']
    path=report['critical_paths'][0]['path'];a={'cell':'opaque4','port':'O','loc':[5,1]};b={'cell':'opaque68','port':'I0','loc':[69,1]}
    cells['opaque68']['connections']['I0']=cells['opaque4']['connections']['O']
    module['netnames']['path_wire']['bits']=cells['opaque4']['connections']['O']
    path[0].update({'from':a,'to':a});path[1].update({'from':a,'to':b});path[2].update({'from':b,'to':b})
    assert m.classify_paths(*case)['classification']=='datapath-boundary'


@pytest.mark.parametrize('poison',['mapped-alias','packed-alias','alias-collision','missing-alias','bool-bit',
    'clock-io','global-buffer','ff-clock','clock-report','clock-count','negative-edge','ff-enable','extra-ff',
    'output-io','output-alias-conflict','unknown-primitive','endpoint-cell','endpoint-port','endpoint-location','path-net','path-discontinuity','delay','missing-path','double-path'])
def test_unresolved_identity_or_path_never_guesses_arithmetic(case,poison):
    mapped,packed,report=case;module=next(iter(packed['modules'].values()));cells=module['cells'];nets=module['netnames'];path=report['critical_paths'][0]['path']
    if poison=='mapped-alias': mapped['modules']['timing_top']['netnames']['launch_q']['bits'].reverse()
    elif poison=='packed-alias': nets['launch_q[0]']['bits']=[99999]
    elif poison=='alias-collision': nets['launch_q[0]']['bits']=nets['launch_q[1]']['bits']
    elif poison=='missing-alias': del nets['result_q[0]']
    elif poison=='bool-bit': nets['launch_q[0]']['bits']=[True]
    elif poison=='clock-io': cells['io_clk']['connections']['D_IN_0']=[123]
    elif poison=='global-buffer': cells['buffer']['connections']['USER_SIGNAL_TO_GLOBAL_BUFFER']=[123]
    elif poison=='ff-clock': cells['opaque0']['connections']['CLK']=[123]
    elif poison=='clock-report': nets['actual_clock']['bits']=[123]
    elif poison=='clock-count': report['fmax']['second']={'achieved':100,'constraint':12}
    elif poison=='negative-edge': cells['opaque0']['parameters']['NEG_CLK']='1'
    elif poison=='ff-enable': cells['opaque0']['parameters']['DFF_ENABLE']='0'
    elif poison=='extra-ff': cells['extra']=copy.deepcopy(cells['opaque0']);cells['extra']['connections']['O']=[99999]
    elif poison=='output-io': cells['io_serial_out']['connections']['D_OUT_0']=[99999]
    elif poison=='output-alias-conflict': nets['output_q[0]']={'bits':[99999]}
    elif poison=='unknown-primitive': cells['unknown']={'type':'UNKNOWN_FF'}
    elif poison=='endpoint-cell': path[-1]['to']['cell']='missing'
    elif poison=='endpoint-port': path[-1]['to']['port']='CLK'
    elif poison=='endpoint-location': path[-1]['to']['loc']=[0,0]
    elif poison=='path-net': nets['path_wire']['bits']=[99999]
    elif poison=='path-discontinuity': path[1]['from']=copy.deepcopy(path[1]['from']);path[1]['from']['port']='CLK'
    elif poison=='delay': path[1]['delay']=float('nan')
    elif poison=='missing-path': report['critical_paths']=[]
    else: report['critical_paths'].append(copy.deepcopy(report['critical_paths'][0]))
    result=m.classify_paths(*case)
    assert result['classification']=='unknown' and result['reason']


def test_packed_and_mapped_ff_counts_remain_explicit_when_clock_attribution_unknown(case):
    mapped,packed,report=case
    next(iter(packed['modules'].values()))['cells']['opaque0']['connections']['CLK']=[123]
    result=m.classify_paths(*case)
    assert result['classification']=='unknown' and result['mapped_ff_count']==result['packed_ff_count']==132
    next(iter(packed['modules'].values()))['cells']['opaque0']['parameters']['DFF_ENABLE']='0'
    assert m.classify_paths(*case)['packed_ff_count']==131


@pytest.mark.parametrize('suffix', ['', 'constant-zero'])
def test_tracked_native_synthetic_archives_are_mandatory_and_replay_actual_shape(suffix):
    root=ROOT/'results/2026-10-15-v10d-timing-preflight'/suffix
    manifest=json.loads((root/'raw-evidence.json').read_bytes())
    archive_path=root/manifest['archive']
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest()==manifest['archive_sha256']
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist())=={row['path'] for row in manifest['files']}
        for row in manifest['files']:
            raw=archive.read(row['path'])
            assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        graphs=[]
        for name in ('mapped.json','packed.json','report.json'):
            matches=[path for path in archive.namelist() if path.endswith('/'+name)]
            assert len(matches)==1
            graphs.append(json.loads(archive.read(matches[0])))
    result=m.classify_paths(*graphs)
    assert result['classification']=='wrapper-boundary' and result['boundary_ff_count']==132
    assert result['mapped_ff_count']==result['packed_ff_count']==132
    assert result['start']['mapped_cell']=='capture_sample1' and result['end']['mapped_cell']=='output_00'

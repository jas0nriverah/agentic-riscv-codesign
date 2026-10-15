"""Synthetic registered harness/state tests, never a study circuit native run."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_v10_timing', ROOT/'scripts/prepare_v10_timing.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def toy_netlist(zero=False):
    """Build a mapped fixture without compiling or reading the wrapper source."""
    q = {name: i+5 for i, name in enumerate(m.FF_NAMES)};wire = 137;cells = {}
    def ff(name, data):
        cells[name] = {'type': 'SB_DFF', 'parameters': {}, 'attributes': {'keep': '1'},
            'connections': {'C': [2], 'D': [data], 'Q': [q[name]]},
            'port_directions': {'C': 'input', 'D': 'input', 'Q': 'output'}}
    def lut(name, inputs, truth):
        nonlocal wire
        target = wire;wire += 1
        cells[name] = {'type': 'SB_LUT4', 'parameters': {'LUT_INIT': f'{truth:016b}'},
            'connections': {**{f'I{i}': [bit] for i, bit in enumerate(inputs)}, 'O': [target]},
            'port_directions': {**{f'I{i}': 'input' for i in range(4)}, 'O': 'output'}}
        return target
    ff('serial_sample0', 3);ff('serial_sample1', q['serial_sample0'])
    ff('capture_sample0', 4);ff('capture_sample1', q['capture_sample0'])
    for i in range(64): ff(f'launch_{i:02d}', q['serial_sample1'] if i == 0 else q[f'launch_{i-1:02d}'])
    for i in range(32):
        data = '0' if zero else lut(f'candidate_xor_{i}', [q[f'launch_{i:02d}'], q[f'launch_{i+32:02d}'], '0', '0'], 0x6666)
        ff(f'result_{i:02d}', data)
    for i in range(32):
        data = lut(f'serializer_mux_{i}', [q['capture_sample1'], q[f'result_{i:02d}'], q[f'output_{i+1:02d}'] if i < 31 else '0', '0'], 0xd8d8)
        ff(f'output_{i:02d}', data)
    ports = {name: {'direction': direction, 'bits': [bit]} for name, direction, bit in
        [('clk', 'input', 2), ('serial_in', 'input', 3), ('capture', 'input', 4), ('serial_out', 'output', q['output_00'])]}
    return {'modules': {'timing_top': {'ports': ports, 'cells': dict(reversed(list(cells.items())))}}}


def test_wrapper_explicit_fixed_boundary_and_recipe():
    source = m.wrapper_rtl()
    assert source.count('(* keep = 1 *) SB_DFF ') == 132
    assert source.count('.C(clk)') == 132 and 'posedge' not in source
    assert 'candidate datapath' in source and '.D(candidate_result[31])' in source
    assert 'SB_DFFE' not in source and 'reset' not in source and 'always' not in source
    r = m.recipe();assert r['wrapped_synthesis_jobs'] == 64 and r['route_jobs'] == 192 and r['paired_route_seeds'] == [1,2,3]
    assert r['target_frequency_mhz'] == 12 and r['boundary_ff_count'] == 132 and r['new_model_fits'] == 0


@pytest.mark.parametrize('zero', [False, True])
def test_all_unsigned_operands_and_exact99_edge_latency(zero):
    samples = m.vectors();expected = [0 if zero else a ^ b for a, b in samples]
    result = m.check_transactions(toy_netlist(zero), samples, expected)
    assert result['verified'] is True and result['transactions'] == 2148
    assert result['edges_per_parallel_frame'] == 99
    assert (result['launch_complete_edge'], result['result_capture_edge'], result['serializer_load_edge']) == (66,67,68)
    assert result['boundary']['ff_count'] == 132
    assert result['boundary']['mapped_cell_types']['SB_DFF'] == 132


@pytest.mark.parametrize('poison', ['missing-ff', 'extra-ff', 'keep', 'clock-divide', 'bool-wire', 'unknown-cell', 'undriven', 'duplicate-driver',
    'cycle', 'scan-swap', 'input-latency', 'result-foreign', 'result-feedback', 'output-pin', 'capture-order', 'serializer-truth', 'serializer-foreign'])
def test_invalid_boundary_or_primitive_fails_before_transactions(poison):
    graph = toy_netlist();module = graph['modules']['timing_top'];cells = module['cells']
    if poison == 'missing-ff': del cells['launch_63']
    elif poison == 'extra-ff': cells['extra'] = copy.deepcopy(cells['result_00']);cells['extra']['connections']['Q'] = [900]
    elif poison == 'keep': del cells['result_00']['attributes']['keep']
    elif poison == 'clock-divide': cells['result_00']['connections']['C'] = cells['launch_00']['connections']['Q']
    elif poison == 'bool-wire': cells['candidate_xor_0']['connections']['I0'] = [True]
    elif poison == 'unknown-cell': cells['candidate_xor_0']['type'] = 'SB_DSP'
    elif poison == 'undriven': cells['candidate_xor_0']['connections']['I0'] = [999]
    elif poison == 'duplicate-driver': cells['candidate_xor_0']['connections']['O'] = cells['result_00']['connections']['Q']
    elif poison == 'cycle': cells['candidate_xor_0']['connections']['I0'] = cells['candidate_xor_0']['connections']['O']
    elif poison == 'scan-swap': cells['launch_32']['connections']['D'] = cells['launch_30']['connections']['Q']
    elif poison == 'input-latency': cells['serial_sample1']['connections']['D'] = [3]
    elif poison == 'result-foreign': cells['result_00']['connections']['D'] = cells['capture_sample1']['connections']['Q']
    elif poison == 'result-feedback': cells['result_00']['connections']['D'] = cells['result_00']['connections']['Q']
    elif poison == 'output-pin': module['ports']['serial_out']['bits'] = cells['output_01']['connections']['Q']
    elif poison == 'capture-order': cells['serializer_mux_0']['connections']['I0'] = cells['capture_sample0']['connections']['Q']
    elif poison == 'serializer-truth': cells['serializer_mux_0']['parameters']['LUT_INIT'] = f'{0x9696:016b}'
    elif poison == 'serializer-foreign': cells['serializer_mux_0']['connections']['I2'] = cells['result_01']['connections']['Q']
    with pytest.raises(ValueError): m.SequentialNetlist(graph)


def test_wrong_expected_result_rejected_and_zero_result_ff_retained():
    samples = [(0xffffffff, 1), (0x80000000, 17), (1,0)]
    with pytest.raises(ValueError, match='unsigned oracle'): m.check_transactions(toy_netlist(), samples, [0]*3)
    boundary = m.SequentialNetlist(toy_netlist(True)).inventory()
    assert len(boundary['groups']['result']) == 32 and boundary['mapped_cell_types']['SB_DFF'] == 132


def test_only_portless_scope_metadata_is_accepted_and_not_counted_as_hardware():
    graph = toy_netlist();scope = {'type': '$scopeinfo', 'connections': {}, 'port_directions': {}, 'parameters': {'TYPE': 'module'}}
    graph['modules']['timing_top']['cells']['datapath'] = scope
    inventory = m.SequentialNetlist(graph).inventory()
    assert inventory['nonhardware_scope_records'] == ['datapath'] and '$scopeinfo' not in inventory['mapped_cell_types']
    scope['connections'] = {'D': [3]}
    with pytest.raises(ValueError): m.SequentialNetlist(graph)


def test_result_bit_order_error_is_not_hidden_by_serializer():
    graph = toy_netlist();cells = graph['modules']['timing_top']['cells']
    cells['result_00']['connections']['D'], cells['result_31']['connections']['D'] = cells['result_31']['connections']['D'], cells['result_00']['connections']['D']
    samples = [(1,0),(0x80000000,0)]
    with pytest.raises(ValueError): m.check_transactions(graph, samples, [a ^ b for a,b in samples])


@pytest.mark.parametrize('samples,expected', [([], []), ([(0,0)], []), ([(True,0)], [0]), ([(0,0)], [False]), ([(-1,0)], [0])])
def test_transaction_type_and_denominator_contract(samples, expected):
    with pytest.raises(ValueError): m.check_transactions(toy_netlist(), samples, expected)


def test_preparation_blocks_incomplete_prior_study_before_output_or_native(tmp_path, monkeypatch):
    area = tmp_path/'area';(area/'measurements').mkdir(parents=True)
    (area/'measurements/completion.json').write_text(json.dumps({'complete': False, 'failures': ['pending']}))
    audit = tmp_path/'audit.json';audit.write_text(json.dumps({'schema': 'isaforge-v10-independent-portable-audit-v1', 'status': 'pass', 'complete': False}))
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('No native operation during preparation'))
    output = tmp_path/'new-preparation'
    with pytest.raises(ValueError, match='Complete independently audited'): m.prepare(output, area, audit)
    assert not output.exists()


def test_synthetic_smoke_path_gate_does_not_execute_native(tmp_path, monkeypatch):
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('Invalid output must precede native work'))
    with pytest.raises(ValueError): m.synthetic_smoke(tmp_path/'v10-timing-prep-fake')


def test_fixed_pcf_checks_global_clock_and_complete_package_membership():
    text = '.pins ct256\nJ3 0 1 0\nL5 0 2 0\nT6 0 3 0\nD8 0 4 0\n.gbufpin\n0 1 0 7\n'
    assert m.validate_pins(text)['clk']['pin'] == 'J3'
    with pytest.raises(ValueError): m.validate_pins(text.replace('0 1 0 7', '0 5 0 7'))
    with pytest.raises(ValueError): m.validate_pins(text.replace('D8 0 4 0\n', ''))


@pytest.fixture
def prepared_synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    source = tmp_path/'scripts/prepare_v10_timing.py';source.parent.mkdir();source.write_text('SYNTHETIC preparation source')
    monkeypatch.setattr(m, '__file__', str(source))
    audit_source = tmp_path/'scripts/audit_v10_hardware.py';audit_source.write_text('SYNTHETIC independent auditor source')
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_prepare_v10_timing.py').write_text('SYNTHETIC test source')
    (tmp_path/'docs').mkdir();(tmp_path/'docs/v10-timing-direction.md').write_text('SYNTHETIC protocol fixture')
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('No native work during preparation'))
    monkeypatch.setattr(m, 'timing_tools', lambda *_: ({'schema': 'isaforge-v10-timing-tools-v1', 'synthetic': True}, []))
    monkeypatch.setattr(m, 'validate_timing_tools', lambda *_: None)
    area = tmp_path/'area';area.mkdir();pairs = []
    for k in m.CONSTANTS:
        for context in m.CONTEXTS:
            formula = f'SYNTHETIC({k},{context})';identity = m.sha(formula.encode())
            row = {'pair_id': 'v10-csd:'+identity, 'source_candidate_id': 'v9-coverage:'+identity, 'formula': formula,
                'rewritten_formula': formula+'-CSD', 'constant_u32': k, 'context': context, 'arms': {}}
            for arm in ('original', 'csd'):
                path = area/'rtl'/identity/(arm+'.v');path.parent.mkdir(parents=True, exist_ok=True);path.write_text('SYNTHETIC RTL '+arm+identity)
                row['arms'][arm] = {'formula': formula if arm == 'original' else formula+'-CSD', 'rtl': m.record(path,area)}
            pairs.append(row)
    m.write(area/'pairs.json', pairs)
    prep = {'pairs': m.record(area/'pairs.json',area), 'files': [m.record(p,area) for p in area.rglob('*') if p.is_file()]}
    m.write(area/'preparation.json',prep);stage = area/'measurements/attempt-0000';stage.mkdir(parents=True)
    m.write(stage/'arm-measurements.json', {'SYNTHETIC':64});m.write(stage/'rtl-equivalence.json', {'SYNTHETIC':32})
    (stage/'raw-evidence.zip').write_bytes(b'SYNTHETIC archive marker, never a native target')
    done = {'complete':True,'failures':[],'attempt':'attempt-0000','preparation_sha256':m.sha((area/'preparation.json').read_bytes()),
        'arm_measurements_sha256':m.sha((stage/'arm-measurements.json').read_bytes()),
        'rtl_equivalence_sha256':m.sha((stage/'rtl-equivalence.json').read_bytes())}
    m.write(stage/'completion.json',done);m.write(area/'measurements/completion.json',done)
    completion_hash = m.sha((stage/'completion.json').read_bytes());archive_hash = m.sha((stage/'raw-evidence.zip').read_bytes())
    m.write(stage/'raw-evidence.json', {'completion_sha256':completion_hash,'archive_sha256':archive_hash})
    audit = tmp_path/'SYNTHETIC-audit.json';m.write(audit, {'schema':'isaforge-v10-independent-portable-audit-v1',
        'status':'pass','complete':True,'rtl_pairs_proved':32,'arms_recounted':64,'completion_sha256':completion_hash,
        'audit_source_sha256':m.sha(audit_source.read_bytes()),
        'preparation_sha256':done['preparation_sha256'],'archive_sha256':archive_hash,
        'arm_measurements_sha256':done['arm_measurements_sha256'],'rtl_equivalence_sha256':done['rtl_equivalence_sha256']})
    output = tmp_path/'prepared';manifest = m.prepare(output,area,audit)
    return output, manifest


def test_input_only_preparation_retains_all64_exact_sources_and_192_route_recipe(prepared_synthetic):
    output, manifest = prepared_synthetic
    validated, recipe, pairs, tools = m.validate_preparation(output)
    assert validated == manifest and len(pairs) == 32 and len(list((output/'rtl').rglob('candidate.v'))) == 64
    assert recipe['route_jobs'] == 192 and tools['synthetic'] is True
    assert all(manifest[k] == 0 for k in ('study_synthesis_jobs_run','timing_jobs_run','model_fits'))


@pytest.mark.parametrize('poison', ['wrapper', 'pcf', 'recipe', 'pair-drop', 'duplicate-binding', 'candidate'])
def test_preparation_mutation_is_rejected_before_any_runtime(prepared_synthetic, poison):
    output, manifest = prepared_synthetic
    if poison == 'duplicate-binding':
        manifest['files'].append(manifest['files'][0]);(output/'preparation.json').write_text(json.dumps(manifest))
    elif poison == 'candidate': next((output/'rtl').rglob('candidate.v')).write_text('changed')
    elif poison == 'pair-drop': (output/'pairs.json').write_text('[]')
    else: (output/{'wrapper':'wrapper.v','pcf':'common.pcf','recipe':'recipe.json'}[poison]).write_text('changed')
    with pytest.raises(ValueError): m.validate_preparation(output)


def test_reauthenticated_recipe_change_cannot_change_clock_target(prepared_synthetic):
    output, manifest = prepared_synthetic;path = output/'recipe.json';recipe = json.loads(path.read_text());recipe['target_frequency_mhz'] = 13
    path.write_text(json.dumps(recipe));manifest['recipe']['sha256'] = m.sha(path.read_bytes())
    for entry in manifest['files']:
        if (output/entry['path']).resolve() == path: entry['sha256'] = manifest['recipe']['sha256']
    (output/'preparation.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Fixed timing recipe'): m.validate_preparation(output)


def test_boolean_zero_cannot_disguise_measurement_metadata(prepared_synthetic):
    output, manifest = prepared_synthetic;manifest['timing_jobs_run'] = False
    (output/'preparation.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Input-only'): m.validate_preparation(output)

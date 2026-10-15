"""Independent portable audit tests; no collector imports or native tools."""
import ast
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_v10_hardware', ROOT/'scripts/audit_v10_hardware.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def netlist():
    return {'modules': {'candidate': {'ports': {
        'in0': {'direction': 'input', 'bits': list(range(2, 34))},
        'in1': {'direction': 'input', 'bits': list(range(34, 66))},
        'result': {'direction': 'output', 'bits': list(range(2, 34))}}, 'cells': {}}}}


def cell(kind, inputs, target, truth=None):
    names, output = (('I0', 'I1', 'I2', 'I3'), 'O') if kind == 'SB_LUT4' else (('I0', 'I1', 'CI'), 'CO')
    return {'type': kind, 'connections': dict(zip((*names, output), [[i] for i in (*inputs, target)])),
        'port_directions': {**{n: 'input' for n in names}, output: 'output'},
        'parameters': {'LUT_INIT': f'{truth:016b}'} if truth is not None else {}}


def multiply11_netlist():
    """Synthetic ripple-adder circuit, independently assembled for audit tests."""
    graph = netlist();module = graph['modules']['candidate'];cells = module['cells'];next_wire = 66
    def add(left, right):
        nonlocal next_wire
        carry = '0';output = []
        for a, b in zip(left, right):
            total, new_carry = next_wire, next_wire+1;next_wire += 2
            cells[f's{total}'] = cell('SB_LUT4', [a, b, carry, '0'], total, 0x9696)
            cells[f'c{new_carry}'] = cell('SB_CARRY', [a, b, carry], new_carry)
            output.append(total);carry = new_carry
        return output
    x = module['ports']['in0']['bits']
    module['ports']['result']['bits'] = add(add(x, ['0']+x[:31]), ['0']*3+x[:29])
    # Reverse serialization order: interpreter must use dependency topology.
    module['cells'] = dict(reversed(list(cells.items())))
    return graph


def test_interpreter_truth_table_pin_order_and_bit_parallel_planes():
    samples = [(i, 0) for i in range(16)]
    for truth in (0, 0xffff, 0xa235, *(1 << i for i in range(16))):
        graph = netlist();module = graph['modules']['candidate']
        module['cells'] = {'lut': cell('SB_LUT4', [2, 3, 4, 5], 66, truth)}
        module['ports']['result']['bits'] = [66]+['0']*31
        assert m.verify_mapped(graph, samples, [(truth >> i) & 1 for i in range(16)]) == {'SB_LUT4': 1}
    graph = netlist();module = graph['modules']['candidate']
    module['cells'] = {'carry': cell('SB_CARRY', [2, 3, 4], 66)}
    module['ports']['result']['bits'] = [66]+['0']*31
    assert m.verify_mapped(graph, samples, [int((i & 7).bit_count() >= 2) for i in range(16)]) == {'SB_CARRY': 1}
    assert m.bit_planes([0, 1, 0xffffffff])[0] == 6
    assert m.bit_planes([0, 1, 0xffffffff])[31] == 4


def test_port_wire_order_is_little_endian_not_numeric_wire_id_order():
    graph = netlist();ports = graph['modules']['candidate']['ports']
    ports['in0']['bits'].reverse();ports['result']['bits'] = list(ports['in0']['bits'])
    samples = [(1, 0), (0x80000000, 0), (0xa501cc31, 7)]
    assert m.verify_mapped(graph, samples, [a for a, _ in samples]) == {}
    ports['result']['bits'].reverse()
    with pytest.raises(ValueError, match='Mapped outputs'): m.verify_mapped(graph, samples, [a for a, _ in samples])


def test_composed_ripple_adders_overflow_and_unsupported_cyclic_drivers():
    samples = m.vectors();expected = [(11*a) & 0xffffffff for a, b in samples]
    counts = m.verify_mapped(multiply11_netlist(), samples, expected)
    assert counts == {'SB_CARRY': 64, 'SB_LUT4': 64}


@pytest.mark.parametrize('kind', ['unknown', 'x', 'z', 'bool-in', 'bool-out', 'negative', 'duplicate', 'cycle', 'undriven', 'truth', 'extra-port', 'carry-param'])
def test_malformed_mapped_graphs_fail_closed(kind):
    graph = netlist();module = graph['modules']['candidate']
    module['cells'] = {'lut': cell('SB_LUT4', [2, 3, 4, 5], 66, 0xaaaa)}
    module['ports']['result']['bits'] = [66]+['0']*31
    if kind == 'unknown': module['cells']['lut']['type'] = 'SB_DFF'
    elif kind in ('x', 'z'): module['cells']['lut']['connections']['I0'] = [kind]
    elif kind == 'bool-in': module['cells']['lut']['connections']['I0'] = [True]
    elif kind == 'bool-out': module['ports']['result']['bits'][0] = False
    elif kind == 'negative': module['cells']['lut']['connections']['I0'] = [-1]
    elif kind == 'duplicate': module['cells']['duplicate'] = copy.deepcopy(module['cells']['lut'])
    elif kind == 'cycle': module['cells']['lut']['connections']['I0'] = [66]
    elif kind == 'undriven': module['cells']['lut']['connections']['I0'] = [999]
    elif kind == 'truth': module['cells']['lut']['parameters']['LUT_INIT'] = 'x'*16
    elif kind == 'extra-port': module['cells']['lut']['connections']['I4'] = [2]
    elif kind == 'carry-param': module['cells'] = {'c': cell('SB_CARRY', [2, 3, 4], 66)};module['cells']['c']['parameters'] = {'bad': 1}
    with pytest.raises(ValueError): m.verify_mapped(graph, [(0, 0)], [0])


@pytest.mark.parametrize('context', m.CONTEXTS)
def test_unsigned_context_oracle_including_negative_operands_and_overflow(context):
    samples = [(0, 1), (0xffffffff, 0xffffffff), (0x80000000, 31), (0x80000001, 0x7fffffff), (128+7, 9)]
    for constant in m.CONSTANTS:
        expected = []
        for a, b in samples:
            if context == 'direct_product': value = a*constant
            elif context == 'add_after_product': value = a*constant+b
            elif context == 'sub_before_product': value = ((a-b) & 0xffffffff)*constant
            else: value = (((a & 63)-b) & 0xffffffff)*constant
            expected.append(value % (1 << 32))
        assert m.expected_values(constant, context, samples) == expected
    with pytest.raises(ValueError): m.expected_values(True, context, samples)


def test_independent_fixed_csd_formula_and_no_experimental_imports():
    assert m.source_formulas(511, 'direct_product') == ('mul(in0,addi(0,511))', 'sub(slli(in0,9),in0)')
    assert m.source_formulas(11, 'masked_sub_before_product')[1] == 'sub(sub(slli(sub(andi(in0,63),in1),4),slli(sub(andi(in0,63),in1),2)),sub(andi(in0,63),in1))'
    source = Path(m.__file__).read_text();tree = ast.parse(source)
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    modules.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert not any(name and ('isaforge' in name or 'measure_' in name or name in ('subprocess', 'z3', 'numpy')) for name in modules)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    """Complete frozen grid with one synthetic retained arm: primary pending."""
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    root = tmp_path/'results';root.mkdir();stage = root/'measurements/attempt-0000';stage.mkdir(parents=True)
    def dump(path, value):
        path.parent.mkdir(parents=True, exist_ok=True);path.write_text(json.dumps(value, indent=2)+'\n')
    collector = tmp_path/'scripts/measure_v10_csd_hardware.py';collector.parent.mkdir();collector.write_bytes(b'synthetic collector bytes')
    def record(path):
        import os
        return {'path': os.path.relpath(path, root), 'sha256': m.sha(path.read_bytes())}
    tools = {'schema': 'isaforge-v10-csd-tools-v1', 'executables': {
        key: {'path': '/nonexistent/yosys/bin/'+name, 'sha256': str(i)*64, 'version': 'SYNTHETIC'}
        for i, (key, name) in enumerate((('yosys', 'yosys'), ('abc', 'yosys-abc'), ('yosys_config', 'yosys-config')), 1)},
        'yosys_data': {'path': '/nonexistent/yosys/share/yosys', 'files': [{'path': 'ice40/cells_sim.v', 'sha256': 'f'*64, 'bytes': 10}]},
        'solver': {'version': 'SYNTHETIC'}}
    tools['yosys_data']['tree_sha256'] = m.sha((json.dumps(tools['yosys_data']['files'],sort_keys=True,separators=(',',':'))+'\n').encode())
    dump(root/'tools.json', tools)
    pairs = []
    for constant, context in itertools.product(m.CONSTANTS, m.CONTEXTS):
        original, rewritten = m.source_formulas(constant, context);identity = m.sha(original.encode())
        pair = {'pair_id': 'v10-csd:'+identity, 'source_candidate_id': 'v9-coverage:'+identity,
            'constant_u32': constant, 'context': context, 'formula': original, 'rewritten_formula': rewritten, 'arms': {}}
        proof = root/'proofs'/f'{identity}.json'
        dump(proof, {'result': 'unsat', 'original_formula': original, 'rewritten_formula': rewritten,
            'assumptions': [], 'solver_version': 'SYNTHETIC', 'query_smt2': '(assert false)', 'query_sha256': m.sha(b'(assert false)')})
        pair['proof'] = record(proof)
        for arm, formula in [('original', original), ('csd', rewritten)]:
            path = root/'rtl'/identity/(arm+'.v');path.parent.mkdir(parents=True, exist_ok=True);path.write_text('SYNTHETIC '+formula)
            pair['arms'][arm] = {'formula': formula, 'rtl': record(path)}
        path = root/'rtl'/identity/'miter.v';path.write_text('SYNTHETIC actual miter');pair['miter_rtl'] = record(path)
        pairs.append(pair)
    dump(root/'pairs.json', pairs)
    recipe = {'schema': 'isaforge-v10-csd-hardware-recipe-v1', 'constants': list(m.CONSTANTS), 'contexts': list(m.CONTEXTS),
        'arms': ['original', 'csd'], 'pairs': 32, 'fresh_synthesis_jobs': 64, 'model_fits': 0, 'tools': record(root/'tools.json'),
        'rtl_equivalence': {'script_commands': m.RTL_COMMANDS, 'pairs': 32, 'timeout_seconds': 60},
        'measurement': {'workers': 2, 'verification_seed': m.SEED, 'random_vectors': 2048, 'boundary_vectors': 100,
            'vectors_per_arm': 2148, 'timeout_seconds_per_arm': 360, 'synthesis_commands': ['synth_ice40 -top candidate', 'check -assert'], 'dsp': False, 'carry': True}}
    dump(root/'recipe.json', recipe)
    prep = {'schema': 'isaforge-v10-csd-hardware-preparation-v1', 'status': 'prepared-inputs-only', 'new_measurements': 0, 'model_fits': 0,
        'pairs': record(root/'pairs.json'), 'recipe': record(root/'recipe.json'), 'tools': record(root/'tools.json'),
        'files': [record(path) for path in root.rglob('*') if path.is_file()]+[record(collector)]}
    dump(root/'preparation.json', prep)
    approval = {'status': 'approved-v10-csd-hardware-measurements', 'freeze_commit': 'a'*40,
        'preparation_sha256': m.sha((root/'preparation.json').read_bytes()), 'recipe_sha256': prep['recipe']['sha256'],
        'pairs_sha256': prep['pairs']['sha256'], 'collector_sha256': m.sha(collector.read_bytes())}
    dump(root/'measurement-approval.json', approval)
    release = {'schema': 'isaforge-v10-csd-hardware-release-v1', 'attempt': 'attempt-0000', 'freeze_commit': 'a'*40,
        'pair_count': 32, 'planned_fresh_synthesis_jobs': 64, 'verification_seed': m.SEED, 'vectors_per_arm': 2148, 'workers': 2,
        'preparation_sha256': approval['preparation_sha256'], 'approval_sha256': m.sha((root/'measurement-approval.json').read_bytes()),
        'collector_sha256': approval['collector_sha256'], 'collection_repository': '/nonexistent/original machine/repository',
        'tools_sha256': m.sha(json.dumps(tools, sort_keys=True).encode()), 'native_environment': {
            'PATH': '/nonexistent/yosys/bin:/usr/bin:/bin', 'ABC': tools['executables']['abc']['path'], 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC'}}
    dump(root/'label-release.json', release)
    content = {name: (root/name).read_bytes() for name in ('tools.json', 'recipe.json', 'pairs.json', 'preparation.json')}
    content.update({'collector-source.py': collector.read_bytes(), 'approval.json': (root/'measurement-approval.json').read_bytes(), 'release.json': (root/'label-release.json').read_bytes()})
    for pair in pairs: content['source-proofs/'+pair['pair_id'].split(':')[1]+'/proof.json'] = (root/pair['proof']['path']).read_bytes()
    pair = pairs[0];identity = pair['pair_id'].split(':')[1];proof_stem = 'rtl-proofs/'+identity+'/'
    base = m.PurePosixPath(release['collection_repository'])
    content[proof_stem+'actual-rtl-miter.v'] = (root/pair['miter_rtl']['path']).read_bytes()
    content[proof_stem+'prove.ys'] = m.proof_script(base, 'attempt-0000', proof_stem).encode()
    content[proof_stem+'prove.log'] = b'SAT proof finished - no model found: SUCCESS!\n'
    proofs = [{'pair_id': pair['pair_id'], 'returncode': 0, 'timed_out': False, 'elapsed_seconds': .01, 'proved': True, 'status': 'proved',
        **{key: m.sha(content[proof_stem+name]) for name,key in [('actual-rtl-miter.v','miter_sha256'),('prove.ys','script_sha256'),('prove.log','log_sha256')]}}]
    stem = 'circuits/'+identity+'/original/';samples = m.vectors();expected = m.expected_values(11, m.CONTEXTS[0], samples)
    rtl_path = base/'generated/v10-csd-hardware/attempt-0000'/stem/'candidate.v'
    alias = '/nonexistent/yosys/bin/../share/yosys/ice40/cells_sim.v'
    log = ''.join(f"Eval result: \\result = 32'{y:032b}.\n" for y in expected)
    log += 'Running ABC command: "<yosys-exe-dir>/yosys-abc" -s -f <abc-temp-dir>/abc.script 2>&1\n'
    log += f"Parsing Verilog input from `{rtl_path}' to AST representation.\nParsing Verilog input from `{alias}' to AST representation.\n"
    content.update({stem+'candidate.v': (root/pair['arms']['original']['rtl']['path']).read_bytes(),
        stem+'ice40.ys': m.arm_script(base,'attempt-0000',stem,samples).encode(), stem+'ice40.log': log.encode(),
        stem+'ice40-netlist.json': json.dumps(multiply11_netlist()).encode(),
        stem+'vectors.txt': ''.join(f'{a:08x} {b:08x} {y:08x}\n' for (a,b),y in zip(samples,expected)).encode(),
        stem+'observations.txt': ''.join(f'{y:08x} {y:08x}\n' for y in expected).encode()})
    metric = {'pair_id': pair['pair_id'], 'arm': 'original', 'source_candidate_id': pair['source_candidate_id'],
        'formula': pair['formula'], 'original_formula': pair['formula'], 'measurement_source': 'fresh-rtl-synthesis',
        'actual_rtl_verified': True, 'mapped_netlist_verified': True, 'vectors_per_arm': 2148, 'random_seed': m.SEED, 'new_fit': False,
        'lut4_count': 64, 'carry_count': 64, 'ice40_cell_types': {'SB_LUT4': 64, 'SB_CARRY': 64},
        'execution': {'returncode': 0, 'timed_out': False, 'elapsed_seconds': .25}, 'yosys': tools['executables']['yosys'],
        'abc_invocations': [{'path': tools['executables']['abc']['path'], 'sha256': tools['executables']['abc']['sha256']}],
        'yosys_data_invocations': {'ice40/cells_sim.v': {'sha256': 'f'*64, 'resolved_path': '/nonexistent/yosys/share/yosys/ice40/cells_sim.v', 'logged_paths': [alias]}}}
    done = {'schema': 'isaforge-v10-csd-hardware-measurements-v1', 'attempt': 'attempt-0000', 'complete': False,
        'failures': [{'phase': 'SYNTHETIC missing other arms'}], 'pair_count': 32, 'fresh_synthesis_jobs_completed': 1,
        'universal_actual_rtl_pairs_proved': 1, 'planned_fresh_synthesis_jobs': 64, 'vectors_per_arm': 2148,
        'verification_seed': m.SEED, 'workers': 2, 'new_estimator_fits': 0, 'legacy_measurements_reused': False,
        'scratch_directory': 'generated/v10-csd-hardware/attempt-0000', 'preparation_sha256': approval['preparation_sha256'],
        'approval_sha256': release['approval_sha256'], 'release_sha256': m.sha((root/'label-release.json').read_bytes()),
        'collector_sha256': release['collector_sha256'], 'tools_sha256': release['tools_sha256']}
    def persist():
        for name, key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256'),('vectors.txt','vectors_sha256'),('observations.txt','observations_sha256')]:
            metric[key] = m.sha(content[stem+name])
        for name, value, key in [('rtl-equivalence.json', proofs, 'rtl_equivalence_sha256'), ('arm-measurements.json', [metric], 'arm_measurements_sha256')]:
            dump(stage/name, value);done[key] = m.sha((stage/name).read_bytes())
        dump(stage/'completion.json', done);dump(root/'measurements/completion.json', done)
        prefix = 'generated/v10-csd-hardware/attempt-0000/'
        with zipfile.ZipFile(stage/'raw-evidence.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in content.items(): archive.writestr(prefix+name, data)
        dump(stage/'raw-evidence.json', {'schema': 'isaforge-v10-csd-raw-evidence-v1', 'attempt': 'attempt-0000',
            'completion_sha256': m.sha((stage/'completion.json').read_bytes()), 'archive': 'raw-evidence.zip',
            'archive_sha256': m.sha((stage/'raw-evidence.zip').read_bytes()),
            'files': [{'path': prefix+name, 'size': len(data), 'sha256': m.sha(data)} for name,data in content.items()]})
    persist()
    return root, content, metric, done, proofs, stem, proof_stem, persist


def test_portable_partial_archive_audit_needs_no_original_tools_and_keeps_primary_pending(evidence):
    root, *_ = evidence
    result = m.run(root)
    assert result['status'] == 'pass' and result['complete'] is False
    assert result['arms_recounted'] == result['rtl_pairs_proved'] == 1
    assert result['source_and_mapped_sample_comparisons'] == 4296
    assert result['pairs'] == [] and result['summary'] is None


@pytest.mark.parametrize('poison', ['lut-bool', 'carry-bool', 'primitive-bool', 'seed', 'formula', 'verified', 'count-bool', 'fake-complete',
    'script', 'proofscript', 'proof-bool', 'returncode-bool', 'elapsed-bool', 'rtl-log', 'abc-log', 'abc-hash', 'extra-library', 'alias-path', 'unknown-cell', 'mapped-output'])
def test_reauthenticated_archive_and_metadata_corruption_fail_closed(evidence, poison):
    root, content, metric, done, proofs, stem, proof_stem, persist = evidence
    if poison == 'lut-bool': metric['lut4_count'] = True
    elif poison == 'carry-bool': metric['carry_count'] = False
    elif poison == 'primitive-bool': metric['ice40_cell_types']['SB_CARRY'] = True
    elif poison == 'seed': metric['random_seed'] += 1
    elif poison == 'formula': metric['formula'] = 'foreign'
    elif poison == 'verified': metric['actual_rtl_verified'] = 1
    elif poison == 'count-bool': done['fresh_synthesis_jobs_completed'] = True
    elif poison == 'fake-complete': done['complete'] = True;done['failures'] = []
    elif poison == 'script': content[stem+'ice40.ys'] += b'synth_ice40 -dsp\n'
    elif poison == 'proofscript':
        content[proof_stem+'prove.ys'] = content[proof_stem+'prove.ys'].replace(b'-prove trigger 0', b'-prove trigger 1')
        proofs[0]['script_sha256'] = m.sha(content[proof_stem+'prove.ys'])
    elif poison == 'proof-bool': proofs[0]['proved'] = 1
    elif poison == 'returncode-bool': metric['execution']['returncode'] = False
    elif poison == 'elapsed-bool': metric['execution']['elapsed_seconds'] = True
    elif poison == 'rtl-log': content[stem+'ice40.log'] += b"Eval result: \\result = 32'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.\n"
    elif poison == 'abc-log': content[stem+'ice40.log'] = content[stem+'ice40.log'].replace(b'<yosys-exe-dir>/yosys-abc', b'/foreign/abc')
    elif poison == 'abc-hash': metric['abc_invocations'][0]['sha256'] = '0'*64
    elif poison == 'extra-library': content[stem+'ice40.log'] += b"Parsing Verilog input from `/foreign/logic.v'\n"
    elif poison == 'alias-path': metric['yosys_data_invocations']['ice40/cells_sim.v']['resolved_path'] = '/foreign/cells_sim.v'
    elif poison in ('unknown-cell', 'mapped-output'):
        graph = json.loads(content[stem+'ice40-netlist.json'])
        if poison == 'unknown-cell': next(iter(graph['modules']['candidate']['cells'].values()))['type'] = 'SB_DFF'
        else: graph['modules']['candidate']['ports']['result']['bits'] = ['0']*32
        content[stem+'ice40-netlist.json'] = json.dumps(graph).encode()
    persist()
    with pytest.raises(ValueError): m.run(root)


def test_corrupt_zip_or_ledger_is_rejected_before_interpretation(evidence):
    root, *_ = evidence;path = root/'measurements/attempt-0000/raw-evidence.zip'
    path.write_bytes(path.read_bytes()+b'tamper')
    with pytest.raises(ValueError, match='Archive digest'): m.run(root)


@pytest.mark.parametrize('poison', ['duplicate-ledger', 'traversal-member'])
def test_archive_member_contract_rejects_reauthenticated_duplicates_and_traversal(evidence, poison):
    root, content, metric, done, proofs, stem, proof_stem, persist = evidence
    if poison == 'traversal-member':
        content['../escape'] = b'unsafe';persist()
    else:
        path = root/'measurements/attempt-0000/raw-evidence.json';record = json.loads(path.read_text())
        record['files'].append(record['files'][0]);path.write_text(json.dumps(record))
    with pytest.raises(ValueError): m.run(root)

#!/usr/bin/env python3
"""Prepare the fixed V10 timing harness; independently check mapped sequences.

No study synthesis or routing is launched here. The optional synthetic-smoke
action synthesizes only literal XOR/zero toy modules under generated/.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'isaforge-v10-timing-preparation-v1'
CONSTANTS = (11, 44, 85, 340, 341, 511, 1364, 2044)
CONTEXTS = ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')
BOUNDARIES = (0, 1, 2, 31, 32, 33, 0x7fffffff, 0x80000000, 0x80000001, 0xffffffff)
SEED, INITIAL_STATE_SEED = 2026101522, 2026101524
PCF = 'set_io clk J3\nset_io serial_in L5\nset_io capture T6\nset_io serial_out D8\n'
GROUPS = {'sampling': ['serial_sample0', 'serial_sample1', 'capture_sample0', 'capture_sample1'],
    'launch': [f'launch_{i:02d}' for i in range(64)], 'result': [f'result_{i:02d}' for i in range(32)],
    'output': [f'output_{i:02d}' for i in range(32)]}
FF_NAMES = [name for group in GROUPS.values() for name in group]


def need(condition, message):
    if not condition: raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())
def now(): return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')


def record(path, root):
    return {'path': os.path.relpath(Path(path).resolve(), Path(root).resolve()), 'sha256': sha(Path(path).read_bytes())}


def wrapper_rtl():
    lines = ['// Common registered V10 timing harness; no arithmetic implementation here.',
        'module timing_top(input wire clk, serial_in, capture, output wire serial_out);',
        'wire serial_s0, serial_s1, capture_s0, capture_s1;',
        'wire [63:0] launch_q;', 'wire [31:0] candidate_result, result_q, output_q;']
    def ff(name, data, output):
        lines.append(f'(* keep = 1 *) SB_DFF {name} (.C(clk), .D({data}), .Q({output}));')
    for prefix, source in [('serial', 'serial_in'), ('capture', 'capture')]:
        ff(prefix+'_sample0', source, prefix+'_s0');ff(prefix+'_sample1', prefix+'_s0', prefix+'_s1')
    for i, name in enumerate(GROUPS['launch']): ff(name, 'serial_s1' if i == 0 else f'launch_q[{i-1}]', f'launch_q[{i}]')
    lines.append('candidate datapath (.in0(launch_q[31:0]), .in1(launch_q[63:32]), .result(candidate_result));')
    for i, name in enumerate(GROUPS['result']): ff(name, f'candidate_result[{i}]', f'result_q[{i}]')
    for i, name in enumerate(GROUPS['output']):
        shifted = f'output_q[{i+1}]' if i < 31 else "1'b0"
        ff(name, f'capture_s1 ? result_q[{i}] : {shifted}', f'output_q[{i}]')
    return '\n'.join([*lines, 'assign serial_out = output_q[0];', 'endmodule', ''])


def vectors():
    rng = random.Random(SEED)
    return [*itertools.product(BOUNDARIES, repeat=2), *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048))]


def oracle(constant, context, samples):
    need(type(constant) is int and constant in CONSTANTS and context in CONTEXTS, 'Fixed study context required')
    result = []
    for a, b in samples:
        operand = a if context in CONTEXTS[:2] else (a if context == CONTEXTS[2] else a & 63)-b
        result.append((operand*constant+(b if context == CONTEXTS[1] else 0)) & 0xffffffff)
    return result


class SequentialNetlist:
    """Strict SB_DFF state plus independent bit-parallel LUT4/carry evaluation."""
    def __init__(self, netlist):
        module = netlist['modules']['timing_top'];ports = module['ports'];cells = module.get('cells', {})
        need(set(ports) == {'clk', 'serial_in', 'capture', 'serial_out'}, 'Exact four-pin wrapper required')
        for name, port in ports.items():
            need(len(port['bits']) == 1 and port['direction'] == ('output' if name == 'serial_out' else 'input'), 'Exact scalar directions required')
        self.ports = {name: value['bits'][0] for name, value in ports.items()}
        inputs = [self.ports[name] for name in ('clk', 'serial_in', 'capture')]
        need(all(type(bit) is int and bit >= 0 for bit in inputs) and len(set(inputs)) == 3, 'Distinct primary inputs required')
        def valid(bit): return (type(bit) is int and bit >= 0) or (type(bit) is str and bit in ('0', '1'))
        need(valid(self.ports['serial_out']), 'Defined serial output required')
        self.flops = {};self.nodes = {};drivers = set(inputs);pending = []
        self.counts = dict(Counter(cell['type'] for cell in cells.values() if cell['type'] != '$scopeinfo'))
        self.scope_metadata = []
        for name, cell in cells.items():
            kind, conn = cell['type'], cell['connections']
            if kind == '$scopeinfo':
                need(conn == {} and cell['port_directions'] == {} and cell.get('parameters') == {'TYPE': 'module'}, 'Invalid nonhardware hierarchy metadata')
                self.scope_metadata.append(name);continue
            need(kind in ('SB_DFF', 'SB_LUT4', 'SB_CARRY'), 'Unknown sequential/mapped primitive')
            inputs_, output = (('C', 'D'), 'Q') if kind == 'SB_DFF' else (('I0', 'I1', 'I2', 'I3'), 'O') if kind == 'SB_LUT4' else (('I0', 'I1', 'CI'), 'CO')
            need(set(conn) == set((*inputs_, output)) and all(len(bits) == 1 for bits in conn.values())
                and all(valid(bit) for bits in conn.values() for bit in bits), 'Exact defined primitive connections required')
            need(set(cell['port_directions']) == set(conn) and all(cell['port_directions'][p] == 'input' for p in inputs_)
                and cell['port_directions'][output] == 'output', 'Primitive directions differ')
            target = conn[output][0]
            need(type(target) is int and target >= 0 and target not in drivers, 'Multiple or invalid drivers')
            drivers.add(target);parameters = cell.get('parameters', {})
            if kind == 'SB_DFF':
                need(not parameters and conn['C'] == [self.ports['clk']], 'Single direct rising-edge clock required')
                keep = cell.get('attributes', {}).get('keep')
                need((type(keep) is int and keep == 1) or (type(keep) is str and re.fullmatch('0*1', keep)), 'Boundary FF preservation attribute required')
                self.flops[name] = {'D': conn['D'][0], 'Q': target}
            else:
                truth = parameters.get('LUT_INIT')
                if kind == 'SB_LUT4': need(set(parameters) == {'LUT_INIT'} and type(truth) is str and re.fullmatch('[01]{16}', truth), 'Defined LUT truth table required')
                else: need(not parameters, 'Unexpected carry parameters')
                node = (kind, [conn[p][0] for p in inputs_], target, int(truth, 2) if truth is not None else None)
                self.nodes[target] = node;pending.append(node)
        need(set(self.flops) == set(FF_NAMES) and self.counts.get('SB_DFF') == 132, 'Exactly132 named boundary SB_DFFs required')
        known = set(inputs) | {ff['Q'] for ff in self.flops.values()} | {'0', '1'};self.schedule = []
        while pending:
            ready = [node for node in pending if all(bit in known for bit in node[1])]
            need(ready, 'Cyclic, undriven or undefined combinational network')
            self.schedule.extend(ready);known.update(node[2] for node in ready);pending = [node for node in pending if node not in ready]
        need(all(ff['D'] in known for ff in self.flops.values()), 'Undriven FF input')
        self._supports = {};self.validate_boundary()

    def evaluate(self, state, serial, capture, lanes):
        full = (1 << lanes)-1
        values = {'0': 0, '1': full, self.ports['clk']: 0, self.ports['serial_in']: serial, self.ports['capture']: capture}
        values.update({ff['Q']: state[name] for name, ff in self.flops.items()})
        for kind, inputs, target, truth in self.schedule:
            planes = [values[bit] for bit in inputs]
            if kind == 'SB_CARRY':
                a, b, c = planes;value = (a & b) | (a & c) | (b & c)
            else:
                value = 0
                for address in range(16):
                    if (truth >> address) & 1:
                        term = full
                        for i, plane in enumerate(planes): term &= plane if (address >> i) & 1 else full ^ plane
                        value |= term
            values[target] = value
        return values

    def support(self, bit):
        if bit in ('0', '1'): return set()
        if bit not in self.nodes: return {bit}
        if bit not in self._supports:
            self._supports[bit] = set().union(*(self.support(source) for source in self.nodes[bit][1]))
        return self._supports[bit]

    def validate_boundary(self):
        q = {name: ff['Q'] for name, ff in self.flops.items()}
        for prefix, pin in [('serial', 'serial_in'), ('capture', 'capture')]:
            need(self.flops[prefix+'_sample0']['D'] == self.ports[pin]
                and self.flops[prefix+'_sample1']['D'] == q[prefix+'_sample0'], 'Two-stage input sampling differs')
        for i, name in enumerate(GROUPS['launch']):
            need(self.flops[name]['D'] == (q['serial_sample1'] if i == 0 else q[GROUPS['launch'][i-1]]), 'Exact64-bit unconditional launch scan required')
        launch = {q[name] for name in GROUPS['launch']}
        for name in GROUPS['result']:
            need(self.support(self.flops[name]['D']) <= launch, 'Candidate result must depend only on launch FFs/constants')
        need(self.ports['serial_out'] == q['output_00'], 'Output must be serializer bit0')
        # Exhaust every local mux input; the other FFs cannot enter this cone.
        for i, name in enumerate(GROUPS['output']):
            variables = [q['capture_sample1'], q[GROUPS['result'][i]]]
            if i < 31: variables.append(q[GROUPS['output'][i+1]])
            need(self.support(self.flops[name]['D']) <= set(variables), 'Serializer cone contains foreign state/control')
            lanes = 1 << len(variables);state = {key: 0 for key in self.flops};planes = {}
            for position, bit in enumerate(variables): planes[bit] = sum(((row >> position) & 1) << row for row in range(lanes))
            for key, ff in self.flops.items(): state[key] = planes.get(ff['Q'], 0)
            values = self.evaluate(state, 0, 0, lanes);full = (1 << lanes)-1
            expected = (planes[variables[0]] & planes[variables[1]]) | ((full ^ planes[variables[0]]) & (planes[variables[2]] if i < 31 else 0))
            need(values[self.flops[name]['D']] == expected, 'Serializer load/shift truth table differs')

    def inventory(self):
        return {'ff_count': 132, 'clock_wire': self.ports['clk'], 'groups': {
            group: [{'cell': name, **self.flops[name]} for name in names] for group, names in GROUPS.items()},
            'mapped_cell_types': self.counts, 'serial_transaction_edges': 99,
            'nonhardware_scope_records': self.scope_metadata,
            'launch_complete_edge': 66, 'result_capture_edge': 67, 'serializer_load_edge': 68}


def planes(values, width):
    return [sum(((value >> bit) & 1) << lane for lane, value in enumerate(values)) for bit in range(width)]


def check_transactions(netlist, samples, expected):
    need(samples and len(samples) == len(expected) and all(len(row) == 2 for row in samples), 'Matched nonempty transactions required')
    need(all(type(value) is int and 0 <= value <= 0xffffffff for row in samples for value in row)
        and all(type(value) is int and 0 <= value <= 0xffffffff for value in expected), 'Exact unsigned32 operands/results required')
    network = SequentialNetlist(netlist);lanes = len(samples);full = (1 << lanes)-1
    rng = random.Random(INITIAL_STATE_SEED)
    state = {name: rng.getrandbits(lanes) for name in network.flops};edges = 0
    def edge(serial=0, capture=0):
        nonlocal state, edges
        values = network.evaluate(state, serial, capture, lanes)
        state = {name: values[ff['D']] for name, ff in network.flops.items()};edges += 1
        return state['output_00']
    words = [(b << 32) | a for a, b in samples];word_planes = planes(words, 64)
    for position in reversed(range(64)): edge(word_planes[position], 0)
    edge();edge(capture=full)
    need([state[name] for name in GROUPS['launch']] == word_planes, 'Input sampling/frame order or launch latency differs')
    edge();expected_planes = planes(expected, 32)
    need([state[name] for name in GROUPS['result']] == expected_planes, 'One-cycle result differs from unsigned oracle')
    observed = [edge()]
    need([state[name] for name in GROUPS['output']] == expected_planes, 'Serializer load latency/data differs')
    for _ in range(31): observed.append(edge())
    need(observed == expected_planes and edges == 99, 'Complete32-bit serial readout differs')
    return {'schema': 'isaforge-v10-timing-sequential-check-v1', 'verified': True, 'transactions': lanes,
        'initial_state_seed': INITIAL_STATE_SEED, 'edges_per_parallel_frame': edges,
        'launch_complete_edge': 66, 'result_capture_edge': 67, 'serializer_load_edge': 68,
        'scope': 'Independent sampled mapped sequential check, not universal synthesis or board-I/O verification.',
        'boundary': network.inventory()}


def recipe():
    return {'schema': 'isaforge-v10-timing-recipe-v1', 'pairs': 32, 'arms': ['original', 'csd'],
        'wrapped_synthesis_jobs': 64, 'route_jobs': 192, 'paired_route_seeds': [1, 2, 3],
        'device': 'iCE40HX8K', 'package': 'CT256', 'target_frequency_mhz': 12,
        'threads_per_route': 1, 'workers': 2, 'synthesis_timeout_seconds': 360, 'route_timeout_seconds': 180,
        'synthesis_commands': ['synth_ice40 -top timing_top', 'check -assert'],
        'boundary_ff_count': 132, 'allowed_mapped_primitives': ['SB_DFF', 'SB_LUT4', 'SB_CARRY'],
        'nonhardware_metadata': {'$scopeinfo': 'module TYPE only; empty connections and directions; excluded from resources'},
        'retiming': False, 'dsp': False, 'carry': True, 'clock_division': False,
        'verification_seed': SEED, 'transactions_per_arm': 2148, 'initial_state_seed': INITIAL_STATE_SEED,
        'frame_edges': 99, 'timing_failure_override': False, 'new_model_fits': 0}


def validate_pins(text):
    section = '';pins = {};globals_ = set()
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line: continue
        if line.startswith('.'): section = line
        elif section == '.pins ct256':
            pin, x, y, z = line.split();need(pin not in pins, 'Duplicate CT256 pin')
            pins[pin] = (int(x), int(y), int(z))
        elif section == '.gbufpin':
            x, y, z, _ = line.split();globals_.add((int(x), int(y), int(z)))
    need(set(('J3', 'L5', 'T6', 'D8')) <= set(pins) and pins['J3'] in globals_, 'Fixed PCF needs four package pins and global clock J3')
    return {name: {'pin': pin, 'location': list(pins[pin])} for name, pin in
        [('clk', 'J3'), ('serial_in', 'L5'), ('capture', 'T6'), ('serial_out', 'D8')]}


def timing_tools(area_root, area_preparation):
    """Read/hash installed tools; never invoke them during input preparation."""
    area_tools_path = (area_root/area_preparation['tools']['path']).resolve()
    need(sha(area_tools_path.read_bytes()) == area_preparation['tools']['sha256'], 'Area tool ledger changed')
    reference = ROOT/'results/2026-10-13-prospective/soc/routing-protocol.json';routing = read(reference)
    need(routing['device'] == 'iCE40HX8K' and routing['package'] == 'CT256'
        and routing['target_frequency_mhz'] == 12 and routing['seeds'] == [1, 2, 3], 'Historical routing policy differs')
    binary = Path(routing['bootstrap']['command'][0]).resolve();database = Path(routing['chipdb_path']).resolve()
    need(sha(binary.read_bytes()) == routing['nextpnr_binary_sha256']
        and sha(database.read_bytes()) == routing['chipdb_sha256'], 'Installed router/database differs from inherited flow')
    receipt = binary.parent.parent/'INSTALL_RECEIPT.json'
    result = {'schema': 'isaforge-v10-timing-tools-v1', 'area_tools': read(area_tools_path),
        'nextpnr': {'path': str(binary), 'sha256': routing['nextpnr_binary_sha256'], 'version_output': routing['nextpnr_version_output']},
        'chipdb': {'path': str(database), 'sha256': routing['chipdb_sha256']},
        'nextpnr_install_receipt': {'path': str(receipt), 'sha256': sha(receipt.read_bytes()), 'content': read(receipt)},
        'pins': validate_pins(database.read_text()), 'historical_protocol': record(reference, ROOT),
        'limitations': 'Same-host native inventory, including complete prior Yosys/ABC data. Not a hermetic OS image.'}
    validate_timing_tools(result)
    return result, [area_tools_path, reference]


def validate_timing_tools(tools):
    need(tools.get('schema') == 'isaforge-v10-timing-tools-v1', 'Timing tool schema differs')
    area = tools['area_tools']
    for entry in [tools['nextpnr'], tools['chipdb'], tools['nextpnr_install_receipt'],
                  *area['executables'].values(), area['python'], *area['solver']['files']]:
        need(Path(entry['path']).is_absolute() and sha(Path(entry['path']).read_bytes()) == entry['sha256'], 'Native runtime file changed')
    directory = Path(area['yosys_data']['path'])
    actual = [{'path': path.relative_to(directory).as_posix(), 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
        for path in sorted(directory.rglob('*')) if path.is_file()]
    need(actual == area['yosys_data']['files'], 'Complete Yosys data inventory changed')
    need(validate_pins(Path(tools['chipdb']['path']).read_text()) == tools['pins'], 'Fixed package-pin proof differs')


def validate_preparation(root, *, check_runtime=False):
    root = Path(root).resolve();manifest = read(root/'preparation.json')
    need(not (root/'preparation-failure.json').exists() and manifest.get('schema') == SCHEMA
        and manifest.get('status') == 'input-only; awaiting timing release'
        and all(type(manifest.get(key)) is int and manifest[key] == 0 for key in ('study_synthesis_jobs_run', 'timing_jobs_run', 'model_fits'))
        and type(manifest['pair_count']) is int and manifest['pair_count'] == 32, 'Input-only preparation required')
    bindings = {}
    for entry in manifest['files']:
        need(set(entry) == {'path', 'sha256'} and isinstance(entry['path'], str) and not Path(entry['path']).is_absolute(), 'Relative file binding required')
        path = (root/entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in bindings and sha(path.read_bytes()) == entry['sha256'], 'Duplicate, external or changed preparation file')
        bindings[path] = entry['sha256']
    def checked(entry):
        path = (root/entry['path']).resolve();need(bindings.get(path) == entry['sha256'], 'Reference missing from flat preparation bindings')
        return path
    need(json.dumps(read(checked(manifest['recipe'])), sort_keys=True) == json.dumps(recipe(), sort_keys=True), 'Fixed timing recipe changed')
    need(checked(manifest['wrapper']).read_text() == wrapper_rtl() and checked(manifest['pcf']).read_text() == PCF, 'Common wrapper or PCF changed')
    tools = read(checked(manifest['tools']))
    if check_runtime: validate_timing_tools(tools)
    audit = read(checked(manifest['area_audit']));completion = checked(manifest['area_completion'])
    need(audit.get('complete') is True and audit.get('status') == 'pass'
        and audit.get('completion_sha256') == sha(completion.read_bytes()) and read(completion).get('complete') is True, 'Completed prior area audit changed')
    pairs = read(checked(manifest['pairs']))
    need(len(pairs) == 32 and len({p['pair_id'] for p in pairs}) == 32
        and [(p['constant_u32'],p['context']) for p in pairs] == list(itertools.product(CONSTANTS,CONTEXTS)), 'Complete fixed32-pair order required')
    area_root = (root/manifest['area_root']).resolve();area_prep = read(area_root/'preparation.json')
    for entry in area_prep['files']:
        need(bindings.get((area_root/entry['path']).resolve()) == entry['sha256'], 'Prior frozen source binding changed')
    original_path = (area_root/area_prep['pairs']['path']).resolve()
    need(bindings.get(original_path) == area_prep['pairs']['sha256'], 'Prior pair source unbound')
    originals = read(original_path)
    need(len(originals) == 32, 'Complete prior32-pair source required')
    for pair, prior in zip(pairs, originals):
        need(set(pair['arms']) == {'original','csd'} and all(pair[key] == prior[key] for key in
            ('pair_id','source_candidate_id','constant_u32','context','formula','rewritten_formula')), 'Prior pair/formula membership changed')
        for arm in ('original','csd'):
            entry = pair['arms'][arm]
            need(entry['formula'] == prior['arms'][arm]['formula'] and entry['wrapper_rtl'] == manifest['wrapper']
                and checked(entry['candidate_rtl']).is_relative_to(root)
                and entry['candidate_rtl']['sha256'] == prior['arms'][arm]['rtl']['sha256'], 'Exact sealed arm/wrapper identity differs')
    for path in (Path(__file__).resolve(), ROOT/'tests/test_prepare_v10_timing.py', ROOT/'docs/v10-timing-direction.md'):
        need(path in bindings, 'Preparation/checker/test/protocol sources must be bound')
    return manifest, recipe(), pairs, tools


def prepare(root, area_root, audit_path):
    """Input-only preparation, deliberately separate from native collection."""
    root, area_root, audit_path = Path(root).resolve(), Path(area_root).resolve(), Path(audit_path).resolve()
    need(not root.exists(), 'New preparation directory required; preserve earlier attempts')
    audit = read(audit_path);done_path = area_root/'measurements/completion.json';done = read(done_path)
    need(audit.get('schema') == 'isaforge-v10-independent-portable-audit-v1' and audit.get('status') == 'pass'
        and audit.get('complete') is True and audit.get('rtl_pairs_proved') == 32 and audit.get('arms_recounted') == 64
        and audit.get('completion_sha256') == sha(done_path.read_bytes())
        and done.get('complete') is True and done.get('failures') == [], 'Complete independently audited32-pair/64-arm area study required')
    audit_source = ROOT/'scripts/audit_v10_hardware.py'
    need(audit.get('audit_source_sha256') == sha(audit_source.read_bytes()), 'Independent area auditor source changed')
    prep_path = area_root/'preparation.json';prep = read(prep_path);bindings = {}
    need(done['preparation_sha256'] == audit['preparation_sha256'] == sha(prep_path.read_bytes()), 'Prior preparation identity differs')
    for entry in prep['files']:
        path = (area_root/entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in bindings and sha(path.read_bytes()) == entry['sha256'], 'Prior source/input changed')
        bindings[path] = entry['sha256']
    pairs_path = (area_root/prep['pairs']['path']).resolve()
    need(bindings.get(pairs_path) == prep['pairs']['sha256'], 'Prior pair ledger unbound')
    pairs = read(pairs_path)
    need(len(pairs) == 32 and len({pair['pair_id'] for pair in pairs}) == 32
        and [(p['constant_u32'], p['context']) for p in pairs] == list(itertools.product(CONSTANTS, CONTEXTS)), 'Exact complete32 fixed pairs required')
    stage = area_root/'measurements'/done['attempt'];raw_path = stage/'raw-evidence.json';raw = read(raw_path)
    need(sha((stage/'completion.json').read_bytes()) == audit['completion_sha256'] == raw['completion_sha256']
        and sha((stage/'raw-evidence.zip').read_bytes()) == raw['archive_sha256'] == audit['archive_sha256']
        and sha((stage/'arm-measurements.json').read_bytes()) == done['arm_measurements_sha256'] == audit['arm_measurements_sha256']
        and sha((stage/'rtl-equivalence.json').read_bytes()) == done['rtl_equivalence_sha256'] == audit['rtl_equivalence_sha256'], 'Audited area output digests differ')
    guards = {**bindings, prep_path: audit['preparation_sha256'], done_path: audit['completion_sha256'],
        stage/'completion.json': audit['completion_sha256'], stage/'raw-evidence.zip': audit['archive_sha256'],
        stage/'arm-measurements.json': audit['arm_measurements_sha256'], stage/'rtl-equivalence.json': audit['rtl_equivalence_sha256'],
        audit_path: sha(audit_path.read_bytes()), raw_path: sha(raw_path.read_bytes())}
    tools, tool_sources = timing_tools(area_root, prep)
    root.mkdir(parents=True)
    try:
        (root/'wrapper.v').write_text(wrapper_rtl());(root/'common.pcf').write_text(PCF);write(root/'recipe.json', recipe());write(root/'tools.json', tools)
        prepared = []
        for pair in pairs:
            row = {key: pair[key] for key in ('pair_id', 'source_candidate_id', 'constant_u32', 'context', 'formula', 'rewritten_formula')};row['arms'] = {}
            for arm in ('original', 'csd'):
                entry = pair['arms'][arm]['rtl'];source = (area_root/entry['path']).resolve()
                need(bindings.get(source) == entry['sha256'], 'Prior candidate RTL changed')
                path = root/'rtl'/pair['pair_id'].split(':')[1]/arm/'candidate.v';path.parent.mkdir(parents=True)
                path.write_bytes(source.read_bytes());row['arms'][arm] = {'formula': pair['arms'][arm]['formula'], 'candidate_rtl': record(path, root), 'wrapper_rtl': record(root/'wrapper.v', root)}
            prepared.append(row)
        write(root/'pairs.json', prepared)
        need(all(sha(path.read_bytes()) == value for path,value in guards.items()), 'Prior area evidence/source changed during preparation')
        sources = [Path(__file__).resolve(), ROOT/'tests/test_prepare_v10_timing.py', ROOT/'docs/v10-timing-direction.md', audit_source]
        prior = [prep_path, done_path, stage/'completion.json', audit_path, pairs_path, raw_path, stage/'raw-evidence.zip', stage/'arm-measurements.json', stage/'rtl-equivalence.json', *bindings, *tool_sources]
        files = sorted({*sources, *prior, *(p for p in root.rglob('*') if p.is_file())})
        manifest = {'schema': SCHEMA, 'status': 'input-only; awaiting timing release', 'prepared_at_utc': now(),
            'study_synthesis_jobs_run': 0, 'timing_jobs_run': 0, 'model_fits': 0, 'pair_count': 32,
            'area_root': os.path.relpath(area_root, root), 'area_audit': record(audit_path, root),
            'area_completion': record(done_path, root), 'recipe': record(root/'recipe.json', root),
            'pairs': record(root/'pairs.json', root), 'wrapper': record(root/'wrapper.v', root),
            'pcf': record(root/'common.pcf', root), 'tools': record(root/'tools.json', root), 'files': [record(path, root) for path in files]}
        write(root/'preparation.json', manifest)
        validate_preparation(root, check_runtime=True)
        return manifest
    except Exception as error:
        write(root/'preparation-failure.json', {'error': repr(error), 'prepared_at_utc': now(), 'study_synthesis_jobs_run': 0, 'timing_jobs_run': 0})
        raise


def synthetic_smoke(output):
    """Only two literal toy circuits; never consume V10 candidate formulas."""
    output = Path(output).resolve()
    need(output.is_relative_to(ROOT/'generated') and output.name.startswith('v10-timing-prep-') and not output.exists(), 'New generated/v10-timing-prep-* synthetic directory required')
    output.mkdir(parents=True)
    executable = shutil.which('yosys');need(executable is not None, 'Synthetic toy smoke needs Yosys')
    executable = Path(executable).resolve();abc = executable.with_name('yosys-abc')
    environment = {'PATH': str(executable.parent)+':/usr/bin:/bin', 'ABC': str(abc), 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC'}
    report = {'schema': 'isaforge-v10-timing-synthetic-smoke-v1', 'synthetic': True,
        'scope': 'XOR and constant-zero toys only; no study candidates or place-and-route.',
        'yosys_path': str(executable), 'yosys_sha256': sha(executable.read_bytes()), 'results': []}
    for label, expression in [('xor', 'in0 ^ in1'), ('constant_zero', "32'b0")]:
        folder = output/label;folder.mkdir();(folder/'SYNTHETIC.txt').write_text('SYNTHETIC TOY ONLY — NO STUDY CANDIDATE\n')
        (folder/'candidate.v').write_text(f'module candidate(input wire [31:0] in0,in1,output wire [31:0] result); assign result={expression}; endmodule\n')
        (folder/'wrapper.v').write_text(wrapper_rtl())
        (folder/'synth.ys').write_text('read_verilog candidate.v wrapper.v\nsynth_ice40 -top timing_top\ncheck -assert\nwrite_json mapped.json\nstat\n')
        started = time.monotonic()
        with (folder/'synth.log').open('xb') as stream:
            process = subprocess.Popen([str(executable), '-s', 'synth.ys'], cwd=folder, env=environment, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try: code = process.wait(timeout=60)
            finally:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
        need(code == 0, 'Synthetic synthesis failed; raw log retained')
        samples = vectors();expected = [a ^ b if label == 'xor' else 0 for a,b in samples]
        result = check_transactions(read(folder/'mapped.json'), samples, expected)
        report['results'].append({'toy': label, 'elapsed_seconds': time.monotonic()-started, 'check': result,
            'netlist_sha256': sha((folder/'mapped.json').read_bytes()), 'log_sha256': sha((folder/'synth.log').read_bytes())})
        write(folder/'check.json', result)
    report['complete'] = True;write(output/'SYNTHETIC-smoke.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('action', choices=('prepare', 'validate', 'synthetic-smoke', 'check-mapped'))
    parser.add_argument('--root', type=Path);parser.add_argument('--area-root', type=Path);parser.add_argument('--audit', type=Path)
    parser.add_argument('--netlist', type=Path);parser.add_argument('--constant', type=int);parser.add_argument('--context', choices=CONTEXTS)
    parser.add_argument('--check-runtime', action='store_true')
    args = parser.parse_args()
    if args.action == 'synthetic-smoke':
        if args.root is None: parser.error('synthetic-smoke needs --root generated/v10-timing-prep-*')
        result = synthetic_smoke(args.root)
    elif args.action == 'prepare':
        if any(value is None for value in (args.root, args.area_root, args.audit)): parser.error('prepare needs --root --area-root --audit')
        result = prepare(args.root, args.area_root, args.audit)
    elif args.action == 'validate':
        if args.root is None: parser.error('validate needs --root')
        manifest, _, pairs, _ = validate_preparation(args.root, check_runtime=args.check_runtime)
        result = {'schema': manifest['schema'], 'status': 'valid', 'pair_count': len(pairs), 'runtime_checked': args.check_runtime}
    else:
        if any(value is None for value in (args.netlist, args.constant, args.context)): parser.error('check-mapped needs --netlist --constant --context')
        samples = vectors();result = check_transactions(read(args.netlist), samples, oracle(args.constant, args.context, samples))
    if args.action == 'synthetic-smoke':
        result = {key: value for key,value in result.items() if key != 'results'} | {'toys': [
            {'toy': row['toy'], 'mapped_cell_types': row['check']['boundary']['mapped_cell_types'],
                'transactions': row['check']['transactions'], 'frame_edges': row['check']['edges_per_parallel_frame']} for row in result['results']]}
    print(json.dumps(result, indent=2))

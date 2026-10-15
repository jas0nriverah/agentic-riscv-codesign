#!/usr/bin/env python3
"""Independent portable CSD evidence audit; standard library, no native tools.

The bit-parallel primitive interpreter below does not import the collector,
RTL emitter, model, or experimental evaluator. Tool paths in the retained logs
are provenance strings; replay does not require that machine's installation.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import posixpath
import random
import re
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONSTANTS = (11, 44, 85, 340, 341, 511, 1364, 2044)
CONTEXTS = ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')
BOUNDARIES = (0, 1, 2, 31, 32, 33, 0x7fffffff, 0x80000000, 0x80000001, 0xffffffff)
SEED = 2026101522
MASK = 0xffffffff
RTL_COMMANDS = ['prep -top pair_miter -flatten', 'check -assert',
    'sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs']


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())


def integer(value):
    return type(value) is int and value >= 0


def elapsed(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def absolute(value):
    need(isinstance(value, str) and PurePosixPath(value).is_absolute() and '\\' not in value
        and posixpath.normpath(value) == value, 'Canonical absolute provenance path required')
    return PurePosixPath(value)


def source_formulas(constant, context):
    """Independent fixed-grid and deterministic signed-digit reconstruction."""
    operand = 'in0' if context in CONTEXTS[:2] else ('sub(in0,in1)' if context == CONTEXTS[2] else 'sub(andi(in0,63),in1)')
    product = f'mul({operand},addi(0,{constant}))'
    digits = [];n = constant;position = 0
    while n:
        digit = (1 if n == 1 else 2-(n % 4)) if n % 2 else 0
        if digit: digits.append((position, digit))
        n = (n-digit)//2;position += 1
    def term(shift): return operand if shift == 0 else f'slli({operand},{shift})'
    position, sign = digits.pop();need(sign == 1, 'Positive leading digit required')
    rewritten = term(position)
    for position, sign in reversed(digits):
        rewritten = f'{"add" if sign == 1 else "sub"}({rewritten},{term(position)})'
    if context == CONTEXTS[1]:
        product, rewritten = f'add({product},in1)', f'add({rewritten},in1)'
    return product, rewritten


def quoted(path): return '"'+str(path).replace('\\', '\\\\').replace('"', '\\"')+'"'


def proof_script(base, attempt, stem):
    path = base/'generated/v10-csd-hardware'/attempt/stem/'actual-rtl-miter.v'
    return '\n'.join([f'read_verilog {quoted(path)}', *RTL_COMMANDS])+'\n'


def arm_script(base, attempt, stem, samples):
    folder = base/'generated/v10-csd-hardware'/attempt/stem
    rtl = folder/'candidate.v'
    lines = [f'read_verilog {quoted(rtl)}', 'prep -top candidate', 'check -assert']
    lines += [f"eval -set in0 32'h{a:08x} -set in1 32'h{b:08x} -show result" for a, b in samples]
    lines += ['design -reset', f'read_verilog {quoted(rtl)}', 'synth_ice40 -top candidate', 'check -assert',
        f'write_json {quoted(folder/"ice40-netlist.json")}', 'stat']
    return '\n'.join(lines)+'\n'


def verify_provenance(log, metric, tools, rtl):
    """Compare retained path strings and hashes; never stat an old tool path."""
    expected = tools['executables']['abc']
    abc = absolute(expected['path']);yosys = absolute(tools['executables']['yosys']['path'])
    invocations = re.findall(r'Running ABC command:\s*(?:"([^"]+)"|(\S+))', log)
    need(invocations, 'Actual ABC invocation required')
    observed = []
    for quoted_path, plain_path in invocations:
        executable = quoted_path or plain_path
        if executable == '<yosys-exe-dir>/yosys-abc': executable = str(yosys.parent/'yosys-abc')
        elif executable == abc.name: executable = str(abc)
        need(executable == str(abc), 'Actual ABC executable differs from frozen provenance')
        observed.append({'path': str(abc), 'sha256': expected['sha256']})
    need(metric['abc_invocations'] == observed and metric['yosys'] == tools['executables']['yosys'], 'ABC/Yosys identity differs')
    inventory = {e['path']: e['sha256'] for e in tools['yosys_data']['files']}
    need(len(inventory) == len(tools['yosys_data']['files']), 'Duplicate tool-data member')
    aliases = metric['yosys_data_invocations'];directory = absolute(tools['yosys_data']['path'])
    need('ice40/cells_sim.v' in aliases, 'Actual cell library required')
    allowed = {str(rtl)};seen = set()
    for relative, alias in aliases.items():
        path = PurePosixPath(relative)
        need(not path.is_absolute() and '..' not in path.parts and str(path) == relative and '\\' not in relative, 'Unsafe library member')
        need(inventory.get(relative) == alias['sha256'] and alias['resolved_path'] == str(directory/path), 'Library provenance differs')
        logged = alias['logged_paths']
        need(isinstance(logged, list) and logged and all(isinstance(p, str) and p for p in logged)
            and len(set(logged)) == len(logged) and not seen.intersection(logged), 'Invalid or ambiguous library aliases')
        seen.update(logged);allowed.update(logged)
    parsed = re.findall(r"Parsing Verilog input from [`']([^']+)'", log)
    need(set(parsed) == allowed, 'Actual Verilog input log differs from complete source/library aliases')


def vectors():
    rng = random.Random(SEED)
    return [*itertools.product(BOUNDARIES, repeat=2),
            *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048))]


def expected_values(constant, context, samples):
    need(type(constant) is int and constant in CONSTANTS and context in CONTEXTS, 'Fixed constant/context required')
    output = []
    for a, b in samples:
        operand = a if context in CONTEXTS[:2] else (a if context == CONTEXTS[2] else a & 63) - b
        value = operand * constant + (b if context == CONTEXTS[1] else 0)
        output.append(value & MASK)
    return output


def bit_planes(values):
    need(all(type(value) is int and 0 <= value <= MASK for value in values), 'Exact unsigned32 sample values required')
    return [sum(((value >> bit) & 1) << i for i, value in enumerate(values)) for bit in range(32)]


def verify_mapped(netlist, samples, expected):
    """Evaluate every sample simultaneously as bits in Python integers."""
    need(len(samples) > 0 and len(samples) == len(expected) and all(len(row) == 2 for row in samples), 'Matched nonempty samples required')
    module = netlist['modules']['candidate']; ports = module['ports']
    def bit(value): return integer(value) or (type(value) is str and value in ('0', '1'))
    need(set(ports) == {'in0', 'in1', 'result'}, 'Exact mapped interface required')
    for name, port in ports.items():
        need(len(port['bits']) == 32 and port['direction'] == ('output' if name == 'result' else 'input'), 'RV32 port mismatch')
    inputs = ports['in0']['bits'] + ports['in1']['bits']
    need(all(type(bit) is int and bit >= 0 for bit in inputs) and len(set(inputs)) == 64, 'Distinct input wires required')
    need(all(bit(value) for value in ports['result']['bits']), 'Defined output wire required')
    full = (1 << len(samples)) - 1
    values = {'0': 0, '1': full}
    for name, position in [('in0', 0), ('in1', 1)]:
        values.update(zip(ports[name]['bits'], bit_planes([row[position] for row in samples])))
    pending = []; driven = set(inputs); counts = Counter()
    for cell in module.get('cells', {}).values():
        kind = cell['type']; counts[kind] += 1
        need(kind in ('SB_LUT4', 'SB_CARRY'), 'Unknown primitive')
        inp, out = (('I0', 'I1', 'I2', 'I3'), 'O') if kind == 'SB_LUT4' else (('I0', 'I1', 'CI'), 'CO')
        conn = cell['connections']
        need(set(conn) == set((*inp, out)) and all(len(x) == 1 for x in conn.values()), 'Primitive port mismatch')
        need(all(bit(value) for bits in conn.values() for value in bits), 'Defined primitive wire required')
        need(set(cell['port_directions']) == set(conn) and all(cell['port_directions'][p] == 'input' for p in inp)
            and cell['port_directions'][out] == 'output', 'Primitive direction mismatch')
        target = conn[out][0]
        need(type(target) is int and target >= 0 and target not in driven, 'Duplicate or invalid driver')
        driven.add(target)
        truth = cell.get('parameters', {}).get('LUT_INIT')
        if kind == 'SB_LUT4':
            need(set(cell.get('parameters', {})) == {'LUT_INIT'} and isinstance(truth, str) and re.fullmatch('[01]{16}', truth), 'Defined LUT truth table required')
        else:
            need(not cell.get('parameters', {}), 'Unexpected carry parameter')
        pending.append((kind, [conn[p][0] for p in inp], target, int(truth, 2) if truth else None))
    while pending:
        remaining = []
        for kind, inp, target, truth in pending:
            if any(bit not in values for bit in inp):
                remaining.append((kind, inp, target, truth)); continue
            planes = [values[bit] for bit in inp]
            if kind == 'SB_CARRY':
                a, b, c = planes; value = (a & b) | (a & c) | (b & c)
            else:
                value = 0
                for address in range(16):
                    if (truth >> address) & 1:
                        term = full
                        for i, plane in enumerate(planes):
                            term &= plane if (address >> i) & 1 else full ^ plane
                        value |= term
            values[target] = value
        need(len(remaining) < len(pending), 'Cyclic, undriven or undefined netlist')
        pending = remaining
    need(all(bit in values for bit in ports['result']['bits']), 'Undefined result')
    need([values[bit] for bit in ports['result']['bits']] == bit_planes(expected), 'Mapped outputs disagree with independent unsigned oracle')
    return dict(counts)


def run(root):
    root = Path(root).resolve(); prep = read(root/'preparation.json')
    need(not (root/'preparation-failure.json').exists() and prep.get('schema') == 'isaforge-v10-csd-hardware-preparation-v1'
        and prep.get('status') == 'prepared-inputs-only' and type(prep.get('new_measurements')) is int
        and prep['new_measurements'] == 0 and type(prep.get('model_fits')) is int and prep['model_fits'] == 0,
        'Complete input-only preparation required')
    bindings = {}
    for entry in prep['files']:
        need(set(entry) == {'path', 'sha256'} and isinstance(entry['path'], str) and not Path(entry['path']).is_absolute(), 'Relative preparation record required')
        path = (root/entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in bindings and path.is_file(), 'Invalid preparation binding')
        need(sha(path.read_bytes()) == entry['sha256'], 'Prepared file changed')
        bindings[path] = entry['sha256']
    def bound(entry):
        path = (root/entry['path']).resolve()
        need(bindings.get(path) == entry['sha256'], 'Reference absent from preparation')
        return read(path)
    pairs, recipe, tools = bound(prep['pairs']), bound(prep['recipe']), bound(prep['tools'])
    need(recipe.get('schema') == 'isaforge-v10-csd-hardware-recipe-v1'
        and recipe.get('constants') == list(CONSTANTS) and recipe.get('contexts') == list(CONTEXTS)
        and recipe.get('arms') == ['original', 'csd'] and type(recipe.get('pairs')) is int and recipe['pairs'] == 32
        and type(recipe.get('fresh_synthesis_jobs')) is int and recipe['fresh_synthesis_jobs'] == 64
        and type(recipe.get('model_fits')) is int and recipe['model_fits'] == 0
        and recipe['rtl_equivalence']['script_commands'] == RTL_COMMANDS
        and type(recipe['rtl_equivalence']['pairs']) is int and recipe['rtl_equivalence']['pairs'] == 32
        and type(recipe['rtl_equivalence']['timeout_seconds']) is int and recipe['rtl_equivalence']['timeout_seconds'] == 60,
        'Fixed32-pair/64-arm universal RTL recipe required')
    measurement = recipe['measurement']
    required_counts = {'workers': 2, 'verification_seed': SEED, 'random_vectors': 2048, 'boundary_vectors': 100,
        'vectors_per_arm': 2148, 'timeout_seconds_per_arm': 360}
    need(all(type(measurement.get(k)) is int and measurement[k] == value for k, value in required_counts.items())
        and measurement['synthesis_commands'] == ['synth_ice40 -top candidate', 'check -assert']
        and measurement.get('dsp') is False and measurement.get('carry') is True, 'Fixed synthesis/sampling recipe required')
    need(tools.get('schema') == 'isaforge-v10-csd-tools-v1' and set(tools['executables']) == {'yosys', 'abc', 'yosys_config'}, 'Complete tool ledger required')
    need(recipe['tools'] == prep['tools'], 'Recipe tool binding differs')
    for entry in tools['executables'].values():
        absolute(entry['path']);need(re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'Tool SHA256 required')
    data_files = tools['yosys_data']['files']
    need(len({entry['path'] for entry in data_files}) == len(data_files), 'Duplicate tool-data inventory member')
    encoded = (json.dumps(data_files, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    need(sha(encoded) == tools['yosys_data']['tree_sha256'], 'Tool-data inventory digest differs')
    for entry in data_files:
        path = PurePosixPath(entry['path'])
        need(not path.is_absolute() and '..' not in path.parts and str(path) == entry['path'] and '\\' not in entry['path']
            and integer(entry['bytes']) and re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'Invalid tool-data ledger entry')
    need(len(pairs) == 32 and {(p['constant_u32'], p['context']) for p in pairs} == set(itertools.product(CONSTANTS, CONTEXTS)), 'Complete fixed32 grid required')
    need(len({p['pair_id'] for p in pairs}) == 32, 'Duplicate pair')
    for p in pairs:
        need(type(p['constant_u32']) is int and p['constant_u32'] in CONSTANTS and p['context'] in CONTEXTS, 'Fixed pair metadata required')
        original, rewritten = source_formulas(p['constant_u32'], p['context'])
        identity = sha(original.encode())
        need(p['formula'] == original and p['rewritten_formula'] == rewritten
            and p['pair_id'] == 'v10-csd:'+identity and p['source_candidate_id'] == 'v9-coverage:'+identity
            and set(p['arms']) == {'original', 'csd'}, 'Pair identity/formula differs')
        for arm, formula in [('original', original), ('csd', rewritten)]:
            need(p['arms'][arm]['formula'] == formula, 'Arm formula differs')
            path = (root/p['arms'][arm]['rtl']['path']).resolve()
            need(bindings.get(path) == p['arms'][arm]['rtl']['sha256'], 'Arm RTL not bound to preparation')
        bound(p['proof'])
        path = (root/p['miter_rtl']['path']).resolve()
        need(bindings.get(path) == p['miter_rtl']['sha256'], 'Actual RTL miter not bound to preparation')
    done = read(root/'measurements/completion.json'); attempt = done['attempt']
    need(done.get('schema') == 'isaforge-v10-csd-hardware-measurements-v1' and type(done['complete']) is bool
        and all(integer(done[k]) for k in ('pair_count', 'fresh_synthesis_jobs_completed', 'universal_actual_rtl_pairs_proved',
            'planned_fresh_synthesis_jobs', 'vectors_per_arm', 'verification_seed', 'workers', 'new_estimator_fits'))
        and done['pair_count'] == 32 and done['planned_fresh_synthesis_jobs'] == 64 and done['vectors_per_arm'] == 2148
        and done['verification_seed'] == SEED and done['workers'] == 2 and done['new_estimator_fits'] == 0
        and done['legacy_measurements_reused'] is False and isinstance(done['failures'], list), 'Strict complete/cohort/count identity required')
    need(re.fullmatch('attempt-[0-9]{4}', attempt), 'Owned attempt required')
    stage = root/'measurements'/attempt; raw = read(stage/'raw-evidence.json')
    need(raw.get('schema') == 'isaforge-v10-csd-raw-evidence-v1' and raw.get('attempt') == attempt
        and done['scratch_directory'] == f'generated/v10-csd-hardware/{attempt}', 'Raw owned-attempt contract differs')
    need(read(stage/'completion.json') == done and raw['completion_sha256'] == sha((stage/'completion.json').read_bytes()), 'Completion changed')
    need(done['preparation_sha256'] == sha((root/'preparation.json').read_bytes()), 'Preparation changed')
    for name, field in [('measurement-approval.json', 'approval_sha256'), ('label-release.json', 'release_sha256')]:
        need(sha((root/name).read_bytes()) == done[field], 'Release changed')
    release = read(root/'label-release.json');approval = read(root/'measurement-approval.json')
    base = absolute(release['collection_repository'])
    need(release.get('schema') == 'isaforge-v10-csd-hardware-release-v1' and release['attempt'] == attempt
        and release['preparation_sha256'] == done['preparation_sha256'] and release['approval_sha256'] == done['approval_sha256']
        and release['collector_sha256'] == done['collector_sha256']
        and release['freeze_commit'] == approval['freeze_commit']
        and approval['status'] == 'approved-v10-csd-hardware-measurements'
        and approval['preparation_sha256'] == done['preparation_sha256']
        and approval['recipe_sha256'] == prep['recipe']['sha256'] and approval['pairs_sha256'] == prep['pairs']['sha256']
        and approval['collector_sha256'] == done['collector_sha256'], 'Approved release provenance differs')
    need(isinstance(approval['freeze_commit'], str) and re.fullmatch('[0-9a-f]{40}', approval['freeze_commit'])
        and all(type(release.get(k)) is int and release[k] == value for k, value in {
            'pair_count': 32, 'planned_fresh_synthesis_jobs': 64, 'verification_seed': SEED,
            'vectors_per_arm': 2148, 'workers': 2}.items()), 'Strict declared release counts required')
    parents = sorted({str(absolute(e['path']).parent) for e in tools['executables'].values()})
    need(release['native_environment'] == {'PATH': ':'.join([*parents, '/usr/bin', '/bin']),
        'ABC': tools['executables']['abc']['path'], 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC'}, 'Retained native environment differs')
    tool_digest = sha(json.dumps(tools, sort_keys=True).encode())
    need(done['tools_sha256'] == release['tools_sha256'] == tool_digest, 'Tool ledger identity differs')
    need(raw['archive'] == 'raw-evidence.zip' and raw['archive_sha256'] == sha((stage/'raw-evidence.zip').read_bytes()), 'Archive digest differs')
    prefix = f'generated/v10-csd-hardware/{attempt}/'
    index = {f['path']: f for f in raw['files']}; content = {}
    need(len(index) == len(raw['files']), 'Duplicate raw binding')
    with zipfile.ZipFile(stage/'raw-evidence.zip') as archive:
        need(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(index), 'Archive membership differs')
        for info in archive.infolist():
            path = PurePosixPath(info.filename); entry = index[info.filename]
            need(info.filename.startswith(prefix) and not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename and str(path) == info.filename, 'Unsafe archive path')
            need(not info.is_dir() and ((info.external_attr >> 16) & 0o170000) in (0, 0o100000), 'Unsafe archive type')
            data = archive.read(info)
            need(type(entry['size']) is int and len(data) == entry['size'] and sha(data) == entry['sha256'], 'Raw member changed')
            content[info.filename[len(prefix):]] = data
    for name, value in [('pairs.json', pairs), ('tools.json', tools), ('recipe.json', recipe), ('preparation.json', prep),
                        ('approval.json', read(root/'measurement-approval.json')), ('release.json', read(root/'label-release.json'))]:
        need(json.loads(content[name]) == value, 'Archived input differs: '+name)
    need(sha(content['collector-source.py']) == done['collector_sha256'], 'Collector identity differs')
    collector_path = (ROOT/'scripts/measure_v10_csd_hardware.py').resolve()
    need(bindings.get(collector_path) == done['collector_sha256'], 'Collector source absent from preparation')
    for pair in pairs:
        source = content['source-proofs/'+pair['pair_id'].split(':')[1]+'/proof.json']
        need(sha(source) == pair['proof']['sha256'], 'Archived source proof differs from preparation')
        proof = json.loads(source)
        need(proof.get('result') == 'unsat' and proof.get('original_formula') == pair['formula']
            and proof.get('rewritten_formula') == pair['rewritten_formula']
            and proof.get('assumptions') == [] and proof.get('solver_version') == tools['solver']['version']
            and sha(proof['query_smt2'].encode()) == proof['query_sha256'], 'Source proof ledger differs')
    for name, field in [('rtl-equivalence.json', 'rtl_equivalence_sha256'), ('arm-measurements.json', 'arm_measurements_sha256')]:
        need(sha((stage/name).read_bytes()) == done[field], 'Result record changed')
    proofs = read(stage/'rtl-equivalence.json'); records = read(stage/'arm-measurements.json')
    pmap = {p['pair_id']:p for p in pairs}; proved = 0
    need(len({p['pair_id'] for p in proofs}) == len(proofs), 'Duplicate proof')
    for proof in proofs:
        need(proof['pair_id'] in pmap, 'Foreign actual RTL proof')
        pair = pmap[proof['pair_id']]; stem = 'rtl-proofs/'+proof['pair_id'].split(':')[1]+'/'
        for name, key in [('actual-rtl-miter.v', 'miter_sha256'), ('prove.ys', 'script_sha256'), ('prove.log', 'log_sha256')]:
            need(sha(content[stem+name]) == proof[key], 'Raw proof changed')
        need(proof['miter_sha256'] == pair['miter_rtl']['sha256'], 'Proof miter changed')
        need(content[stem+'prove.ys'].decode() == proof_script(base, attempt, stem), 'Actual RTL SAT script differs from fixed recipe')
        log = content[stem+'prove.log'].decode()
        need((type(proof['returncode']) is int or proof['returncode'] is None)
            and type(proof['timed_out']) is bool and type(proof['proved']) is bool
            and elapsed(proof['elapsed_seconds']), 'Strict native proof execution types required')
        success = proof['returncode'] == 0 and proof['timed_out'] is False and log.count('SAT proof finished - no model found: SUCCESS!') == 1
        need(proof['proved'] is success, 'Proof verdict differs from raw log')
        need(proof['status'] in ('proved', 'failed', 'timeout', 'unknown')
            and (proof['status'] == 'proved') is success, 'Actual RTL proof status differs')
        proved += success
    samples = vectors(); by_key = {}; comparisons = 0
    for metric in records:
        key = (metric['pair_id'], metric['arm'])
        need(key not in by_key and key[0] in pmap and key[1] in ('original', 'csd'), 'Invalid arm membership')
        by_key[key] = metric; pair = pmap[key[0]]; stem = 'circuits/'+key[0].split(':')[1]+'/'+key[1]+'/'
        need(metric['source_candidate_id'] == pair['source_candidate_id'] and metric['formula'] == pair['arms'][key[1]]['formula']
            and metric['original_formula'] == pair['formula'] and metric['measurement_source'] == 'fresh-rtl-synthesis'
            and metric['actual_rtl_verified'] is True and metric['mapped_netlist_verified'] is True
            and type(metric['vectors_per_arm']) is int and metric['vectors_per_arm'] == 2148
            and type(metric['random_seed']) is int and metric['random_seed'] == SEED and metric['new_fit'] is False,
            'Fresh arm formula/seed/verification identity differs')
        need(integer(metric['lut4_count']) and integer(metric['carry_count'])
            and set(metric['ice40_cell_types']) <= {'SB_LUT4', 'SB_CARRY'}
            and all(integer(value) and value > 0 for value in metric['ice40_cell_types'].values()), 'Strict primitive label counts required')
        for name, field in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256'),('vectors.txt','vectors_sha256'),('observations.txt','observations_sha256')]:
            need(sha(content[stem+name]) == metric[field], 'Raw arm digest differs')
        need(metric['rtl_sha256'] == pair['arms'][key[1]]['rtl']['sha256'], 'Measured RTL differs from sealed arm')
        need(content[stem+'ice40.ys'].decode() == arm_script(base, attempt, stem, samples), 'Actual arm script differs from fixed recipe')
        expected = expected_values(pair['constant_u32'], pair['context'], samples)
        lines = ''.join(f'{a:08x} {b:08x} {y:08x}\n' for (a,b),y in zip(samples,expected))
        need(content[stem+'vectors.txt'].decode() == lines, 'Saved vectors differ from independent oracle')
        need(content[stem+'observations.txt'].decode() == ''.join(f'{y:08x} {y:08x}\n' for y in expected), 'Saved outputs differ')
        log = content[stem+'ice40.log'].decode()
        observed = re.findall(r"Eval result: \\result = ([^\n]+)\.",log)
        need(len(observed) == log.count('Eval result:') and all(re.fullmatch(r"32'[01]{32}|[0-9]+", x) for x in observed), 'Undefined, malformed or unexpected RTL output')
        observed = [int(x.split("'")[1],2) if "'" in x else int(x) for x in observed]
        need(observed == expected, 'Actual RTL log differs from independent oracle')
        counts = verify_mapped(json.loads(content[stem+'ice40-netlist.json']), samples, expected)
        need(counts == metric['ice40_cell_types'] and counts.get('SB_LUT4',0) == metric['lut4_count'] and counts.get('SB_CARRY',0) == metric['carry_count'], 'Independent primitive recount differs')
        execution = metric['execution']
        need(set(execution) == {'returncode', 'timed_out', 'elapsed_seconds'} and type(execution['returncode']) is int
            and execution['returncode'] == 0 and execution['timed_out'] is False and elapsed(execution['elapsed_seconds']), 'Successful native execution required')
        verify_provenance(log, metric, tools, base/'generated/v10-csd-hardware'/attempt/stem/'candidate.v')
        comparisons += 2*len(samples)
    need(done['fresh_synthesis_jobs_completed'] == len(records) and done['universal_actual_rtl_pairs_proved'] == proved, 'Completion counts differ')
    if done['complete']:
        need(not done['failures'] and proved == len(proofs) == 32 and set(by_key) == {(p['pair_id'],a) for p in pairs for a in ('original','csd')}, 'Complete paired result required')
    changes = []
    if done['complete']:
        for p in pairs:
            a,b = (by_key[p['pair_id'],arm] for arm in ('original','csd'))
            changes.append({'pair_id':p['pair_id'],'constant':p['constant_u32'],'context':p['context'],
                'original_lut4':a['lut4_count'],'csd_lut4':b['lut4_count'],'delta_lut4':b['lut4_count']-a['lut4_count'],
                'original_carry':a['carry_count'],'csd_carry':b['carry_count']})
    delta = [p['delta_lut4'] for p in changes]
    return {'schema':'isaforge-v10-independent-portable-audit-v1','status':'pass','complete':done['complete'],
        'preparation_sha256':sha((root/'preparation.json').read_bytes()),'completion_sha256':sha((stage/'completion.json').read_bytes()),
        'audit_source_sha256':sha(Path(__file__).read_bytes()),'archive_sha256':raw['archive_sha256'],
        'arm_measurements_sha256':done['arm_measurements_sha256'],'rtl_equivalence_sha256':done['rtl_equivalence_sha256'],
        'archive_members_verified':len(content),'rtl_pairs_proved':proved,
        'arms_recounted':len(records),'source_and_mapped_sample_comparisons':comparisons,'pairs':changes,
        'summary':{'mean_delta_lut4':statistics.fmean(delta),'median_delta_lut4':statistics.median(delta),
            'min_delta_lut4':min(delta),'max_delta_lut4':max(delta),'wins':sum(d<0 for d in delta),'ties':delta.count(0),'losses':sum(d>0 for d in delta)} if delta else None,
        'independence':'Standard library only. Independently regenerated vectors, unsigned oracle, raw RTL log parsing and bit-parallel LUT/carry interpretation. No collector imports, native tools, model loads or fits. Proof logs are authenticated and reviewed, not re-solved.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = run(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'pairs'},indent=2))

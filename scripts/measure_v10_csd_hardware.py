#!/usr/bin/env python3
"""Collect all32 original/CSD hardware pairs with owned, retained evidence.

Universal actual-RTL pair miters are distinct from sampled RTL/oracle and
mapped-netlist/oracle checks. No model fits or historical target reuse.
This collector's read-only archive/proof audits require the sealed same-host
runtime and repository paths; they are not a portable replay implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from isaforge.rtl import BOUNDARIES
from isaforge.synthesis import _yosys_quote

PREFIX = 'generated/v10-csd-hardware/'
SEED = 2026101522
VECTORS = 2148
ARMS = ('original', 'csd')
MASK = (1 << 32)-1


def native_environment(tools):
    """Do not inherit ABC, loader, plugin or Yosys overrides from the shell."""
    parents = sorted({str(Path(e['path']).resolve().parent) for e in tools['executables'].values()})
    return {'PATH': os.pathsep.join([*parents, '/usr/bin', '/bin']),
            'ABC': tools['executables']['abc']['path'], 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC'}


class HardwareWorkers:
    """Owned process-group cancellation, following the retained V9 collector."""
    def __init__(self, tools):
        self.lock = threading.Lock();self.active = set();self.cancelled = False
        self.environment = native_environment(tools)

    def launch(self, command, stream):
        with self.lock:
            if self.cancelled:
                raise RuntimeError('Paired hardware attempt cancelled')
            process = subprocess.Popen(command, cwd=ROOT, env=self.environment,
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            self.active.add(process.pid)
            return process

    def cancel(self):
        with self.lock:
            self.cancelled = True
            for pid in self.active:
                try: os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError: pass

    def finished(self, pid):
        with self.lock:
            self.active.discard(pid)


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Nonnegative integer required')
    return value


def oracle(pair, in0, in1):
    """Separate direct u32 oracle for this fixed four-context source cohort."""
    x, y, constant = in0 & MASK, in1 & MASK, integer(pair['constant_u32'])
    if constant > MASK:
        raise ValueError('RV32 constant required')
    context = pair['context']
    if context == 'direct_product': value = x*constant
    elif context == 'add_after_product': value = x*constant+y
    elif context == 'sub_before_product': value = ((x-y) & MASK)*constant
    elif context == 'masked_sub_before_product': value = (((x & 63)-y) & MASK)*constant
    else: raise ValueError('Unknown fixed multiply context')
    return value & MASK


def vectors():
    result = list(itertools.product(BOUNDARIES, repeat=2))
    rng = random.Random(SEED)
    result.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048))
    if len(result) != VECTORS:
        raise ValueError('Fixed boundary/random vector count differs')
    return result


def mapped_evaluator(netlist):
    """Compile strict combinational SB_LUT4/SB_CARRY JSON into a bit evaluator."""
    module = netlist['modules']['candidate']
    ports = module['ports']
    if (set(ports) != {'in0', 'in1', 'result'} or any(len(p['bits']) != 32 for p in ports.values())
            or any(ports[n]['direction'] != 'input' for n in ('in0', 'in1'))
            or ports['result']['direction'] != 'output'):
        raise ValueError('Exact RV32 combinational ports required')
    input_bits = ports['in0']['bits']+ports['in1']['bits']
    if any(type(b) is not int or b < 0 for b in input_bits) or len(set(input_bits)) != 64:
        raise ValueError('Distinct integer input wires required')
    def valid_bit(bit):
        return (type(bit) is int and bit >= 0) or (type(bit) is str and bit in ('0', '1'))
    if any(not valid_bit(b) for b in ports['result']['bits']):
        raise ValueError('Invalid mapped result wire')
    drivers, pending = {}, []
    for name, cell in sorted(module.get('cells', {}).items()):
        kind, connections = cell['type'], cell['connections']
        if kind == 'SB_LUT4':
            inputs, output = ('I0', 'I1', 'I2', 'I3'), 'O'
            value = cell.get('parameters', {}).get('LUT_INIT')
            if not isinstance(value, str) or not re.fullmatch('[01]{16}', value):
                raise ValueError('Exact binary LUT_INIT required')
            parameter = int(value, 2)
        elif kind == 'SB_CARRY':
            inputs, output, parameter = ('I0', 'I1', 'CI'), 'CO', None
        else:
            raise ValueError('Unsupported mapped primitive: '+str(kind))
        if set(connections) != set((*inputs, output)) or any(len(bits) != 1 for bits in connections.values()):
            raise ValueError('Exact single-bit primitive ports required')
        if any(not valid_bit(b) for bits in connections.values() for b in bits):
            raise ValueError('Invalid primitive wire or undefined constant')
        if (any(cell['port_directions'].get(p) != 'input' for p in inputs)
                or cell['port_directions'].get(output) != 'output'):
            raise ValueError('Primitive direction differs')
        bit = connections[output][0]
        if type(bit) is not int or bit < 0 or bit in drivers or bit in input_bits:
            raise ValueError('Multiple or invalid mapped drivers')
        drivers[bit] = name
        pending.append((kind, [connections[p][0] for p in inputs], bit, parameter))
    known = set(input_bits) | {'0', '1'}
    schedule = []
    while pending:
        ready = [operation for operation in pending if all(b in known for b in operation[1])]
        if not ready:
            raise ValueError('Mapped cycle, undriven wire or undefined constant')
        schedule.extend(ready)
        known.update(op[2] for op in ready)
        pending = [operation for operation in pending if operation not in ready]
    if any(bit not in known for bit in ports['result']['bits']):
        raise ValueError('Undefined mapped result bit')

    def evaluate(in0, in1):
        bits = {'0': 0, '1': 1}
        for name, value in (('in0', in0), ('in1', in1)):
            bits.update({b: (value >> i) & 1 for i, b in enumerate(ports[name]['bits'])})
        for kind, inputs, output, parameter in schedule:
            values = [bits[b] for b in inputs]
            if kind == 'SB_LUT4':
                index = sum(v << i for i, v in enumerate(values))
                bits[output] = (parameter >> index) & 1
            else:
                a, b, carry = values
                bits[output] = (a & b) | ((a | b) & carry)
        return sum(bits[b] << i for i, b in enumerate(ports['result']['bits']))
    return evaluate


def run_owned(command, log, owner, timeout):
    """Own the whole Yosys/ABC process group; keep partial output on timeout."""
    log = Path(log);log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log.open('xb') as stream:
        process = owner.launch(command, stream)
        timed_out = False
        try:
            try: code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True;code = None
        finally:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait();owner.finished(process.pid)
    return {'returncode': code, 'timed_out': timed_out, 'elapsed_seconds': time.monotonic()-started}


def proof_commands(miter):
    return [f'read_verilog {_yosys_quote(Path(miter).resolve())}',
            'prep -top pair_miter -flatten', 'check -assert',
            'sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs']


def prove_pair(root, pair, folder, tools, owner):
    folder.mkdir(parents=True)
    source = (root/pair['miter_rtl']['path']).resolve()
    if sha(source) != pair['miter_rtl']['sha256']:
        raise ValueError('Sealed actual-RTL miter changed')
    miter = folder/'actual-rtl-miter.v';miter.write_bytes(source.read_bytes())
    script, log = folder/'prove.ys', folder/'prove.log'
    script.write_text('\n'.join(proof_commands(miter))+'\n')
    execution = run_owned([tools['executables']['yosys']['path'], '-s', str(script)], log, owner, 60)
    text = log.read_text(errors='replace')
    success = text.count('SAT proof finished - no model found: SUCCESS!') == 1
    proved = execution['returncode'] == 0 and not execution['timed_out'] and success
    status = 'proved' if proved else ('timeout' if execution['timed_out'] or 'TIMEOUT' in text.upper() else
                                     'failed' if 'model found: FAIL' in text else 'unknown')
    result = {'pair_id': pair['pair_id'], 'proved': proved, 'status': status,
              **execution, 'miter_sha256': sha(miter), 'script_sha256': sha(script), 'log_sha256': sha(log),
              'scope': 'Universal actual original/CSD RTL equality via flattened Yosys SAT; separate from high-level source QF_BV proof.'}
    write(folder/'proof.json', result)
    return result


def arm_commands(rtl, netlist):
    lines = [f'read_verilog {_yosys_quote(Path(rtl).resolve())}', 'prep -top candidate', 'check -assert']
    lines += [f"eval -set in0 32'h{a:08x} -set in1 32'h{b:08x} -show result" for a, b in vectors()]
    # Discard verification preprocessing before the exact default mapping flow.
    lines += ['design -reset', f'read_verilog {_yosys_quote(Path(rtl).resolve())}',
              'synth_ice40 -top candidate', 'check -assert',
              f'write_json {_yosys_quote(Path(netlist).resolve())}', 'stat']
    return lines


def abc_invocations(text, tools):
    commands = re.findall(r'Running ABC command:\s*(?:"([^"]+)"|(\S+))', text)
    if not commands:
        raise ValueError('Mapped run must record its actual ABC executable')
    expected = tools['executables']['abc']
    observed = []
    for quoted, plain in commands:
        executable = quoted or plain
        if executable.startswith('<yosys-exe-dir>/'):
            if executable != '<yosys-exe-dir>/yosys-abc':
                raise ValueError('Unexpected Yosys ABC placeholder path')
            executable = str(Path(tools['executables']['yosys']['path']).resolve().parent/'yosys-abc')
        if '<' in executable or '>' in executable:
            raise ValueError('Unknown ABC executable placeholder')
        path = Path(executable) if Path(executable).is_absolute() else Path(shutil.which(executable, path=native_environment(tools)['PATH']) or executable)
        if path.resolve() != Path(expected['path']).resolve() or sha(path) != expected['sha256']:
            raise ValueError('Actual mapping ABC differs from frozen tool inventory')
        observed.append({'path': str(path.resolve()), 'sha256': sha(path)})
    return observed


def data_invocations(text, tools, rtl):
    """Authenticate the actual share files reported by the mapping process."""
    directory = Path(tools['yosys_data']['path']).resolve()
    inventory = {entry['path']: entry['sha256'] for entry in tools['yosys_data']['files']}
    observed = {}
    for filename in re.findall(r"Parsing Verilog input from [`']([^']+)'", text):
        path = Path(filename).resolve()
        if path == Path(rtl).resolve():
            continue
        if not path.is_relative_to(directory):
            raise ValueError('Actual synthesis read an unsealed Verilog library')
        relative = path.relative_to(directory).as_posix()
        if relative not in inventory or sha(path) != inventory[relative]:
            raise ValueError('Actual synthesis data differs from sealed inventory')
        entry = observed.setdefault(relative, {'sha256': inventory[relative], 'resolved_path': str(path), 'logged_paths': []})
        if filename not in entry['logged_paths']:
            entry['logged_paths'].append(filename)
    if 'ice40/cells_sim.v' not in observed:
        raise ValueError('Actual iCE40 library path must be recorded')
    return observed


def rtl_observations(text):
    observed = re.findall(r"Eval result: \\result = (32'[01xz]+|[0-9]+)\.", text)
    return [int(v.split("'")[1], 2) if "'" in v and not re.search('[xz]', v) else
            int(v) if "'" not in v else None for v in observed]


def measure_arm(root, pair, arm, folder, tools, owner):
    folder.mkdir(parents=True)
    entry = pair['arms'][arm]['rtl']
    source = (root/entry['path']).resolve()
    if sha(source) != entry['sha256']:
        raise ValueError('Sealed arm RTL changed')
    rtl, script, log, netlist_path = [folder/name for name in ('candidate.v', 'ice40.ys', 'ice40.log', 'ice40-netlist.json')]
    rtl.write_bytes(source.read_bytes())
    inputs = vectors();expected = [oracle(pair, a, b) for a, b in inputs]
    vectors_path = folder/'vectors.txt'
    vectors_path.write_text(''.join(f'{a:08x} {b:08x} {y:08x}\n' for (a, b), y in zip(inputs, expected)))
    script.write_text('\n'.join(arm_commands(rtl, netlist_path))+'\n')
    execution = run_owned([tools['executables']['yosys']['path'], '-s', str(script)], log, owner, 360)
    if execution['returncode'] != 0 or execution['timed_out']:
        write(folder/'execution-failure.json', execution)
        raise RuntimeError('Fresh arm synthesis/evaluation failed; raw log retained')
    text = log.read_text(errors='replace')
    values = rtl_observations(text)
    if len(values) != VECTORS or values != expected:
        write(folder/'rtl-verification-failure.json', {'expected_count': VECTORS, 'observed_count': len(values),
              'mismatches': [{'index': i, 'expected': y, 'observed': value} for i, (y, value) in enumerate(zip(expected, values)) if y != value]})
        raise RuntimeError('Actual arm RTL differs from unsigned contextual oracle')
    netlist = read(netlist_path);evaluate = mapped_evaluator(netlist)
    mapped = [evaluate(a, b) for a, b in inputs]
    observations = folder/'observations.txt'
    observations.write_text(''.join(f'{rtl_value:08x} {mapped_value:08x}\n' for rtl_value, mapped_value in zip(values, mapped)))
    if mapped != expected:
        raise RuntimeError('Mapped netlist differs from unsigned contextual oracle; observations retained')
    cells = Counter(c['type'] for c in netlist['modules']['candidate'].get('cells', {}).values())
    result = {'pair_id': pair['pair_id'], 'source_candidate_id': pair['source_candidate_id'], 'arm': arm,
        'formula': pair['arms'][arm]['formula'], 'original_formula': pair['formula'],
        'measurement_source': 'fresh-rtl-synthesis', 'lut4_count': cells['SB_LUT4'], 'carry_count': cells['SB_CARRY'],
        'ice40_cell_types': dict(cells), 'actual_rtl_verified': True, 'mapped_netlist_verified': True,
        'vectors_per_arm': VECTORS, 'random_seed': SEED, 'new_fit': False,
        'execution': execution,
        'rtl_sha256': sha(rtl), 'script_sha256': sha(script), 'log_sha256': sha(log),
        'netlist_sha256': sha(netlist_path), 'vectors_sha256': sha(vectors_path),
        'observations_sha256': sha(observations), 'abc_invocations': abc_invocations(text, tools),
        'yosys_data_invocations': data_invocations(text, tools, rtl),
        'yosys': tools['executables']['yosys'], 'measured_at_utc': now(),
        'verification_scope': '100 boundary +2048 seeded random vectors per arm, checked at source RTL and mapped netlist; sampled, not universal mapped equivalence.'}
    write(folder/'metrics.json', result)
    return result


def prepared_inputs(root):
    from prepare_v10_csd_hardware import validate_preparation, validate_tools
    root = Path(root).resolve()
    manifest, recipe, pairs = validate_preparation(root)
    if (manifest.get('schema') != 'isaforge-v10-csd-hardware-preparation-v1'
            or len(pairs) != 32 or len({p['pair_id'] for p in pairs}) != 32):
        raise ValueError('Complete32-pair frozen preparation required')
    tools_path = (root/recipe['tools']['path']).resolve()
    if sha(tools_path) != recipe['tools']['sha256']:
        raise ValueError('Frozen tool inventory differs')
    tools = read(tools_path);validate_tools(tools)
    bindings = {root/'preparation.json': sha(root/'preparation.json')}
    for entry in manifest['files']:
        path = (root/entry['path']).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != entry['sha256']:
            raise ValueError('Changed or nonportable prepared input/source')
        bindings[path] = entry['sha256']
    if Path(__file__).resolve() not in bindings or ROOT/'tests/test_measure_v10_csd_hardware.py' not in bindings:
        raise ValueError('Collector source/tests must be frozen before measurements')
    for pair in pairs:
        if not re.fullmatch('v10-csd:[0-9a-f]{64}', pair['pair_id']) or set(pair['arms']) != set(ARMS):
            raise ValueError('Stable pair identity and both arms required')
        for entry in [pair['miter_rtl'], pair['proof'], *(pair['arms'][arm]['rtl'] for arm in ARMS)]:
            path = (root/entry['path']).resolve()
            if not path.is_relative_to(root) or bindings.get(path) != entry['sha256']:
                raise ValueError('Every proof/actual-RTL/miter must be flat-bound inside preparation')
    return manifest, recipe, pairs, tools, bindings


def validate_approval(root, approval):
    root, approval = Path(root).resolve(), Path(approval).resolve()
    if approval != root/'measurement-approval.json':
        raise ValueError('Exact root/measurement-approval.json required')
    manifest, recipe, pairs, tools, bindings = prepared_inputs(root)
    review = read(approval)
    expected = {'status': 'approved-v10-csd-hardware-measurements', 'preparation_sha256': sha(root/'preparation.json'),
                'recipe_sha256': manifest['recipe']['sha256'], 'pairs_sha256': manifest['pairs']['sha256'],
                'collector_sha256': sha(__file__)}
    if any(review.get(k) != v for k, v in expected.items()) or not re.fullmatch('[0-9a-f]{40}', review.get('freeze_commit', '')):
        raise ValueError('Committed parent release must bind the complete V10 input/source freeze')
    if datetime.fromisoformat(review['reviewed_at_utc']) < datetime.fromisoformat(manifest['created_at_utc']):
        raise ValueError('Review must follow preparation')
    for path, value in bindings.items():
        result = subprocess.run(['git', 'show', review['freeze_commit']+':'+path.relative_to(ROOT).as_posix()], cwd=ROOT, capture_output=True)
        if result.returncode or digest(result.stdout) != value:
            raise ValueError('Prepared source/input differs from reviewed committed bytes')
    bindings[approval] = sha(approval)
    return manifest, recipe, pairs, tools, review, bindings


def destination(name, repository, attempt):
    path = PurePosixPath(name);repository = Path(repository).resolve()
    if (not re.fullmatch('attempt-[0-9]{4}', attempt) or not name.startswith(PREFIX+attempt+'/')
            or path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name):
        raise ValueError('Unsafe owned V10 evidence path')
    allowed = (repository/PREFIX/attempt).resolve();target = repository/name
    if not allowed.is_relative_to(repository) or not target.resolve().is_relative_to(allowed):
        raise ValueError('V10 evidence escapes owned attempt')
    return target


def collect(root, approval, *, attempt='attempt-0000', workers=2):
    from prepare_v10_csd_hardware import validate_tools
    root = Path(root).resolve()
    if type(workers) is not int or workers != 2 or not re.fullmatch('attempt-[0-9]{4}', attempt):
        raise ValueError('Fixed2 workers and explicit owned attempt required')
    directory = root/'measurements'
    if (directory/'completion.json').exists() or (root/'label-release.json').exists():
        raise ValueError('Paired release is single-attempt; retain failed outcomes without automatic retries')
    manifest, recipe, pairs, tools, review, bindings = validate_approval(root, approval)
    stage, scratch = directory/attempt, ROOT/PREFIX/attempt
    destination(PREFIX+attempt+'/member', ROOT, attempt)
    if stage.exists() or scratch.exists():
        raise ValueError('Fresh paired attempt required; failed attempts remain retained')
    release = {'schema': 'isaforge-v10-csd-hardware-release-v1', 'attempt': attempt, 'preparation_sha256': sha(root/'preparation.json'),
        'approval_sha256': sha(approval), 'freeze_commit': review['freeze_commit'], 'collector_sha256': sha(__file__),
        'pair_count': 32, 'planned_fresh_synthesis_jobs': 64, 'verification_seed': SEED, 'vectors_per_arm': VECTORS,
        'workers': workers, 'tools_sha256': digest(json.dumps(tools, sort_keys=True).encode()),
        'collection_repository': str(ROOT), 'native_environment': native_environment(tools),
        'archive_audit_scope': 'Same-host sealed tool/data/repository verification; not portable replay.'}
    release_path = root/'label-release.json'
    write(release_path, {**release, 'released_at_utc': now()})
    bindings[release_path] = sha(release_path)
    stage.mkdir(parents=True);scratch.mkdir(parents=True)
    write(scratch/'tools.json', tools);write(scratch/'recipe.json', recipe);write(scratch/'pairs.json', pairs)
    (scratch/'collector-source.py').write_bytes(Path(__file__).read_bytes())
    (scratch/'preparation.json').write_bytes((root/'preparation.json').read_bytes())
    (scratch/'approval.json').write_bytes(Path(approval).read_bytes())
    (scratch/'release.json').write_bytes(release_path.read_bytes())
    for pair in pairs:
        path = scratch/'source-proofs'/pair['pair_id'].split(':')[1]/'proof.json'
        path.parent.mkdir(parents=True)
        path.write_bytes((root/pair['proof']['path']).read_bytes())
    owner, failures, proofs, measured = HardwareWorkers(tools), [], {}, {}
    interruption = None

    def run_jobs(jobs, operation, destination_map, phase):
        nonlocal interruption
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {pool.submit(operation, *arguments): key for key, arguments in jobs}
            for completed, future in enumerate(as_completed(futures), 1):
                key = futures[future]
                try:
                    value = future.result();destination_map[key] = value
                    if phase == 'rtl-equivalence' and not value['proved']:
                        failures.append({'phase': phase, 'job': key, 'status': value['status']})
                except Exception as error:
                    failures.append({'phase': phase, 'job': key, 'error': repr(error)})
                write(stage/f'{phase}-progress-{completed:04d}.json',
                      {'phase': phase, 'completed_records': len(destination_map), 'failures': failures})
        except BaseException as error:
            owner.cancel();interruption = error;failures.append({'phase': phase, 'error': repr(error), 'cancelled': True})
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    proof_jobs = [(p['pair_id'], (root, p, scratch/'rtl-proofs'/p['pair_id'].split(':')[1], tools, owner)) for p in pairs]
    run_jobs(proof_jobs, prove_pair, proofs, 'rtl-equivalence')
    # No pair is filtered: if any actual-RTL proof is unresolved, the complete
    # hardware claim stays pending and the failed32-pair attempt is preserved.
    if not failures and len(proofs) == 32:
        jobs = [(p['pair_id']+'/'+arm, (root, p, arm, scratch/'circuits'/p['pair_id'].split(':')[1]/arm, tools, owner))
                for p in pairs for arm in ARMS]
        run_jobs(jobs, measure_arm, measured, 'fresh-synthesis')
    try:
        if any(sha(path) != value for path, value in bindings.items()):
            raise ValueError('Prepared source/input/release changed during collection')
        validate_tools(tools)
    except Exception as error:
        failures.append({'phase': 'provenance', 'error': repr(error)})
    proof_list = [proofs[p['pair_id']] for p in pairs if p['pair_id'] in proofs]
    arm_list = [measured[p['pair_id']+'/'+arm] for p in pairs for arm in ARMS if p['pair_id']+'/'+arm in measured]
    write(stage/'rtl-equivalence.json', proof_list);write(stage/'arm-measurements.json', arm_list)
    done = {'schema': 'isaforge-v10-csd-hardware-measurements-v1',
        'complete': not failures and len(proof_list) == 32 and len(arm_list) == 64,
        'failures': failures, 'attempt': attempt, 'pair_count': 32, 'universal_actual_rtl_pairs_proved': sum(p['proved'] for p in proof_list),
        'fresh_synthesis_jobs_completed': len(arm_list), 'planned_fresh_synthesis_jobs': 64,
        'vectors_per_arm': VECTORS, 'verification_seed': SEED, 'workers': 2,
        'mapped_verification_scope': 'Sampled 100 boundary+2048 seeded vectors per arm; no universal mapped-equivalence claim.',
        'preparation_sha256': sha(root/'preparation.json'), 'approval_sha256': sha(approval),
        'release_sha256': sha(release_path), 'collector_sha256': sha(__file__),
        'tools_sha256': release['tools_sha256'], 'rtl_equivalence_sha256': sha(stage/'rtl-equivalence.json'),
        'arm_measurements_sha256': sha(stage/'arm-measurements.json'),
        'legacy_measurements_reused': False, 'new_estimator_fits': 0,
        'scratch_directory': scratch.relative_to(ROOT).as_posix(), 'completed_at_utc': now()}
    write(stage/'completion.json', done)
    write(directory/'completion.json', done)
    pack(root, attempt=attempt)
    if interruption is not None:
        raise interruption
    if not done['complete']:
        raise RuntimeError('Incomplete paired attempt retained; primary hardware result unavailable')
    return done


def pack(root, *, attempt):
    root = Path(root).resolve();stage = root/'measurements'/attempt
    done = read(stage/'completion.json')
    if done['attempt'] != attempt or done['scratch_directory'] != PREFIX+attempt:
        raise ValueError('Owned paired completion identity differs')
    scratch = destination(PREFIX+attempt+'/member', ROOT, attempt).parent
    records = []
    with zipfile.ZipFile(stage/'raw-evidence.zip', 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(scratch.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink raw evidence forbidden')
            if not path.is_file():
                continue
            name = path.relative_to(ROOT).as_posix();destination(name, ROOT, attempt)
            data = path.read_bytes();stream.writestr(name, data)
            records.append({'path': name, 'size': len(data), 'sha256': digest(data)})
    write(stage/'raw-evidence.json', {'schema': 'isaforge-v10-csd-raw-evidence-v1',
          'archive': 'raw-evidence.zip', 'archive_sha256': sha(stage/'raw-evidence.zip'),
          'completion_sha256': sha(stage/'completion.json'), 'attempt': attempt, 'files': records})
    return records


def archive_data(root, attempt):
    root = Path(root).resolve();stage = root/'measurements'/attempt
    preparation, recipe, pairs, tools, bindings = prepared_inputs(root)
    done, manifest = read(stage/'completion.json'), read(stage/'raw-evidence.json')
    if (manifest.get('schema') != 'isaforge-v10-csd-raw-evidence-v1' or manifest.get('attempt') != attempt
            or manifest.get('archive') != 'raw-evidence.zip' or done['attempt'] != attempt
            or sha(stage/'completion.json') != manifest['completion_sha256']
            or sha(stage/'raw-evidence.zip') != manifest['archive_sha256']):
        raise ValueError('Paired archive/completion identity differs')
    if (done.get('schema') != 'isaforge-v10-csd-hardware-measurements-v1'
            or type(done['complete']) is not bool
            or any(type(done[key]) is not int or done[key] < 0 for key in
                ('fresh_synthesis_jobs_completed', 'universal_actual_rtl_pairs_proved', 'pair_count'))
            or done['pair_count'] != 32):
        raise ValueError('Strict complete/cohort/count contract required')
    if (read(root/'measurements/completion.json') != done or done['scratch_directory'] != PREFIX+attempt
            or done['preparation_sha256'] != sha(root/'preparation.json')
            or done['collector_sha256'] != sha(__file__)
            or done['approval_sha256'] != sha(root/'measurement-approval.json')
            or done['release_sha256'] != sha(root/'label-release.json')
            or done['tools_sha256'] != digest(json.dumps(tools, sort_keys=True).encode())
            or done['vectors_per_arm'] != VECTORS or done['verification_seed'] != SEED
            or done['workers'] != 2 or done['planned_fresh_synthesis_jobs'] != 64
            or done['legacy_measurements_reused'] is not False or done['new_estimator_fits'] != 0):
        raise ValueError('Completion differs from frozen root/input/tool contract')
    for name, key in (('rtl-equivalence.json', 'rtl_equivalence_sha256'), ('arm-measurements.json', 'arm_measurements_sha256')):
        if sha(stage/name) != done[key]:
            raise ValueError('Completed paired records changed')
    records = {r['path']: r for r in manifest['files']}
    if len(records) != len(manifest['files']):
        raise ValueError('Duplicate raw evidence members')
    content = {}
    with zipfile.ZipFile(stage/'raw-evidence.zip') as stream:
        if len(stream.namelist()) != len(set(stream.namelist())) or set(stream.namelist()) != set(records):
            raise ValueError('Raw archive coverage differs')
        for info in stream.infolist():
            destination(info.filename, ROOT, attempt)
            data = stream.read(info);entry = records[info.filename]
            if (info.is_dir() or ((info.external_attr >> 16) & 0o170000) not in (0, 0o100000)
                    or type(entry['size']) is not int or len(data) != entry['size'] or digest(data) != entry['sha256']):
                raise ValueError('Raw archived paired member differs')
            content[info.filename.removeprefix(PREFIX+attempt+'/')] = data
    expected_files = {'preparation.json': (root/'preparation.json').read_bytes(),
        'approval.json': (root/'measurement-approval.json').read_bytes(),
        'release.json': (root/'label-release.json').read_bytes(), 'collector-source.py': Path(__file__).read_bytes()}
    if any(content.get(name) != value for name, value in expected_files.items()):
        raise ValueError('Archived release/preparation/source differs from immutable root')
    if (json.loads(content['pairs.json']) != pairs or json.loads(content['tools.json']) != tools
            or json.loads(content['recipe.json']) != recipe):
        raise ValueError('Archived cohort/recipe/tools differs from frozen preparation')
    for pair in pairs:
        name = 'source-proofs/'+pair['pair_id'].split(':')[1]+'/proof.json'
        if digest(content[name]) != pair['proof']['sha256']:
            raise ValueError('Archived high-level source proof differs')
    return done, content


def review_proofs(root, *, attempt):
    done, content = archive_data(root, attempt)
    proofs = read(Path(root)/'measurements'/attempt/'rtl-equivalence.json')
    pairs = json.loads(content['pairs.json'])
    expected = {p['pair_id']: p for p in pairs}
    if len(expected) != 32 or len({p['pair_id'] for p in proofs}) != len(proofs):
        raise ValueError('Complete pair identity / unique proof records required')
    if not {p['pair_id'] for p in proofs} <= set(expected) or (done['complete'] and len(proofs) != 32):
        raise ValueError('Proof records must cover the exact fixed cohort')
    for proof in proofs:
        pair = expected[proof['pair_id']];prefix = 'rtl-proofs/'+proof['pair_id'].split(':')[1]+'/'
        for name, key in (('actual-rtl-miter.v', 'miter_sha256'), ('prove.ys', 'script_sha256'), ('prove.log', 'log_sha256')):
            if digest(content[prefix+name]) != proof[key]:
                raise ValueError('Retained universal actual-RTL proof differs')
        if proof['miter_sha256'] != pair['miter_rtl']['sha256']:
            raise ValueError('Proved miter differs from sealed actual arm bytes')
        miter = ROOT/PREFIX/attempt/prefix/'actual-rtl-miter.v'
        if content[prefix+'prove.ys'].decode() != '\n'.join(proof_commands(miter))+'\n':
            raise ValueError('Actual RTL proof script differs from fixed SAT recipe')
        success = content[prefix+'prove.log'].decode(errors='replace').count('SAT proof finished - no model found: SUCCESS!') == 1
        if (type(proof['proved']) is not bool or type(proof['timed_out']) is not bool
                or proof['proved'] != (proof['returncode'] == 0 and not proof['timed_out'] and success)):
            raise ValueError('Proof verdict does not match actual solver log')
    return {'attempt': attempt, 'complete': done['complete'], 'records_reviewed': len(proofs),
            'pairs_proved': sum(p['proved'] for p in proofs), 'scope': 'Same-host read-only retained universal actual-RTL proof review; no native rerun.'}


def audit(root, *, attempt):
    proof_review = review_proofs(root, attempt=attempt)
    done, content = archive_data(root, attempt)
    pairs = json.loads(content['pairs.json']);records = read(Path(root)/'measurements'/attempt/'arm-measurements.json')
    index = {(r['pair_id'], r['arm']): r for r in records}
    expected_keys = {(p['pair_id'], arm) for p in pairs for arm in ARMS}
    if len(index) != len(records) or not set(index) <= expected_keys:
        raise ValueError('Duplicate paired arm metrics')
    if (done['fresh_synthesis_jobs_completed'] != len(index)
            or done['universal_actual_rtl_pairs_proved'] != proof_review['pairs_proved']):
        raise ValueError('Completion counts differ from retained records')
    if done['complete'] and (done['failures'] or set(index) != expected_keys or proof_review['pairs_proved'] != 32):
        raise ValueError('All32 complete pairs required; no filtered primary result')
    comparisons = 0
    for pair in pairs:
        for arm in ARMS:
            if (pair['pair_id'], arm) not in index:
                continue
            metric = index[pair['pair_id'], arm]
            prefix = 'circuits/'+pair['pair_id'].split(':')[1]+'/'+arm+'/'
            for name, key in (('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'), ('ice40.log', 'log_sha256'),
                              ('ice40-netlist.json', 'netlist_sha256'), ('vectors.txt', 'vectors_sha256'), ('observations.txt', 'observations_sha256')):
                if digest(content[prefix+name]) != metric[key]:
                    raise ValueError('Retained arm evidence digest differs')
            if metric['rtl_sha256'] != pair['arms'][arm]['rtl']['sha256']:
                raise ValueError('Measured actual RTL differs from sealed arm')
            if (metric['source_candidate_id'] != pair['source_candidate_id']
                    or metric['formula'] != pair['arms'][arm]['formula'] or metric['original_formula'] != pair['formula']
                    or metric['measurement_source'] != 'fresh-rtl-synthesis'
                    or metric['actual_rtl_verified'] is not True or metric['mapped_netlist_verified'] is not True
                    or metric['vectors_per_arm'] != VECTORS or metric['random_seed'] != SEED or metric['new_fit'] is not False):
                raise ValueError('Arm identity or verification contract differs')
            rtl = ROOT/PREFIX/attempt/prefix/'candidate.v';netlist_path = rtl.with_name('ice40-netlist.json')
            if content[prefix+'ice40.ys'].decode() != '\n'.join(arm_commands(rtl, netlist_path))+'\n':
                raise ValueError('Retained mapping script differs from fixed fresh flow')
            text = content[prefix+'ice40.log'].decode(errors='replace')
            if rtl_observations(text) != [oracle(pair, a, b) for a, b in vectors()]:
                raise ValueError('Raw Yosys RTL evaluation log differs from oracle')
            tools = json.loads(content['tools.json'])
            if (abc_invocations(text, tools) != metric['abc_invocations']
                    or data_invocations(text, tools, rtl) != metric['yosys_data_invocations']
                    or metric['yosys'] != tools['executables']['yosys']):
                raise ValueError('Observed mapping tool/library differs')
            netlist = json.loads(content[prefix+'ice40-netlist.json']);evaluate = mapped_evaluator(netlist)
            cells = Counter(c['type'] for c in netlist['modules']['candidate'].get('cells', {}).values())
            if dict(cells) != metric['ice40_cell_types'] or cells['SB_LUT4'] != metric['lut4_count'] or cells['SB_CARRY'] != metric['carry_count']:
                raise ValueError('Mapped resource recount differs')
            lines = content[prefix+'vectors.txt'].decode().splitlines()
            observations = content[prefix+'observations.txt'].decode().splitlines()
            if len(lines) != VECTORS or len(observations) != VECTORS:
                raise ValueError('Full2148 paired vectors and observations required')
            for line, observed, (a, b) in zip(lines, observations, vectors()):
                expected = oracle(pair, a, b)
                if line != f'{a:08x} {b:08x} {expected:08x}' or observed != f'{expected:08x} {expected:08x}' or evaluate(a, b) != expected:
                    raise ValueError('Sampled RTL/mapped output or unsigned oracle differs')
                comparisons += 2
    changes = [{'pair_id': p['pair_id'], 'formula': p['formula'], 'context': p['context'],
                'original_lut4': index[p['pair_id'], 'original']['lut4_count'], 'csd_lut4': index[p['pair_id'], 'csd']['lut4_count'],
                'csd_minus_original_lut4': index[p['pair_id'], 'csd']['lut4_count']-index[p['pair_id'], 'original']['lut4_count']}
               for p in pairs] if done['complete'] else None
    return {'schema': 'isaforge-v10-paired-hardware-audit-v1', 'complete': done['complete'], 'failures': done['failures'],
            'proof_review': proof_review, 'fresh_arm_records_recounted': len(records),
            'sampled_source_and_mapped_comparisons': comparisons, 'pair_results': changes,
            'mean_csd_minus_original_lut4': statistics.fmean(p['csd_minus_original_lut4'] for p in changes) if changes else None,
            'scope': 'Same-host sealed-runtime archive audit. All32 paired isolated-datapath LUT4 counts; source/mapped sampling is not universal mapped equivalence, ASIC area, CPU timing or speedup.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('collect', 'pack', 'review-proofs', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--attempt', default='attempt-0000')
    parser.add_argument('--output', type=Path, help='Optional new immutable audit/proof-review report')
    args = parser.parse_args()
    if args.action == 'collect':
        if args.approval is None: parser.error('collect requires --approval')
        result = collect(args.root, args.approval, attempt=args.attempt)
    elif args.action == 'pack': result = pack(args.root, attempt=args.attempt)
    elif args.action == 'review-proofs': result = review_proofs(args.root, attempt=args.attempt)
    else: result = audit(args.root, attempt=args.attempt)
    if args.output is not None: write(args.output, result)
    print(json.dumps(result, indent=2))

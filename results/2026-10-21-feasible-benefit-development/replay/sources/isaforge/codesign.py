"""Bounded CRC32 candidate -> firmware -> PicoRV32 -> selection experiment.

This is within-workload adaptation, not held-out-workload generalization.
Historical frozen experiments are read-only. Native measurements, cache hits,
failed attempts, and offline policy charges are recorded separately.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
import fcntl
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import time

from .core_experiment import CORE_COMMIT, crc32_fusion_source, validate_crc32_simulation
from .core_routing import timing_summary
from .features import FEATURE_COLUMNS, extract_features
from .model import SpeedupPredictor
from .rtl import BOUNDARIES, evaluate_formula, generate_rtl
from .selection import POLICIES, _measurement, run_policy
from .soc_experiment import memory_image, validate_netlist

ROOT = Path(__file__).resolve().parents[1]
EMBENCH_COMMIT = '0466a18e4f6b47e19598d7c6ba72916d54b68f65'
MACRO = '#define UPDC32(octet,crc) (crc_32_tab[((crc)^((BYTE)octet)) & 0xff] ^ ((crc) >> 8))'
# Complete supported kernel lowering menu, fixed before any new performance label.
CANDIDATES = {
    'index_offset': ('slli(andi(xor(in0,in1),255),2)', 'offset = ci(crc, octet); entry = *(const DWORD *)((const char *)table + offset);'),
    'index_byte': ('andi(xor(in0,in1),255)', 'entry = table[ci(crc, octet)];'),
    'address_mask': ('add(in0,slli(andi(in1,255),2))', 'entry = *(const DWORD *)ci((DWORD)table, crc ^ (BYTE)octet);'),
    'address': ('add(in0,slli(in1,2))', 'entry = *(const DWORD *)ci((DWORD)table, (crc ^ (BYTE)octet) & 255u);'),
    'mask_offset': ('slli(andi(in0,255),2)', 'offset = ci(crc ^ (BYTE)octet, 0); entry = *(const DWORD *)((const char *)table + offset);'),
    'shift_xor': ('xor(in0,srli(in1,8))', 'entry = table[(crc ^ (BYTE)octet) & 255u]; return ci(entry, crc);'),
}
PINS = {'passed': 'M9', 'report_bit': 'D8', 'fault': 'C8', 'done': 'B9',
        'clk': 'J3', 'trap': 'H2', 'resetn': 'L5', 'report_strobe': 'T6'}
CONFIG = {'workload': 'embench-crc32', 'isa': 'rv32i_zicsr', 'repetitions': 170,
          'updates_per_repetition': 1024, 'ram_bytes': 8192, 'pcpi_response_wait_cycles': 1,
          'frequency_mhz': 12.0, 'route_seeds': [1, 2, 3], 'max_added_lut4': 128,
          'native_workers': 1, 'build_workers': 2, 'command_seconds': 180,
          'total_native_seconds': 2400, 'max_native_commands': 240,
          'live_seed': 0, 'live_budget': 3, 'bootstrap': 2,
          'comparison_seeds': [0, 1, 2, 3, 4], 'comparison_budgets': [1, 2, 3, 4, 5, 6]}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def seal(path, value):
    write(path, value)
    Path(str(path)+'.sha256').write_text(sha(path)+'\n')


def unseal(path):
    require(sha(path) == Path(str(path)+'.sha256').read_text().strip(), 'Cached record changed')
    return read(path)


def lower_crc(original, name):
    require(original.count(MACRO) == 1, 'Pinned CRC macro changed')
    require(name in CANDIDATES, 'Unsupported candidate lowering')
    body = CANDIDATES[name][1]
    return original.replace(MACRO, '''
static inline DWORD ci(DWORD a, DWORD b) {
    DWORD out;
    __asm__ volatile (".insn r 0x0b, 0, 1, %0, %1, %2"
                      : "=r"(out) : "r"(a), "r"(b));
    return out;
}
static inline DWORD codesign_update(DWORD octet, DWORD crc, const DWORD *table) {
    DWORD offset, entry;
    ''' + body + '''
    return entry ^ (crc >> 8);
}
#define UPDC32(octet,crc) codesign_update((octet),(crc),crc_32_tab)
''')


def public_rows(context):
    retained = {r['formula']: r for r in read(ROOT/'results/2026-10-13/candidates/crc32.json')}
    rows = []
    for name, (formula, _) in CANDIDATES.items():
        source = retained[formula]
        require(any('benchmark_body' in r['symbols'] for r in source['occurrences']), 'Not a retained kernel candidate')
        # These are pre-existing RV32IM discovery proxies, including the old
        # instruction-count denominator in saved_percent, NOT new RV32I labels.
        # Actual execution and full-workload cycles are measured independently.
        features = extract_features(source)
        rows.append({'candidate_id': digest([context, name, formula]),
                     'benchmark': 'crc32:' + context, 'formula': formula,
                     'name': name, **features})
    return rows


def prepare(output, core, prefix):
    began = time.monotonic()
    output, core = Path(output).resolve(), Path(core).resolve()
    require(not output.exists(), 'Prepare requires a fresh output directory')
    def git(path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True, timeout=15).strip()
    require(git(core, 'rev-parse', 'HEAD') == CORE_COMMIT and not git(core, 'status', '--porcelain'), 'Clean pinned PicoRV32 required')
    embench = ROOT/'benchmarks/embench'
    require(git(embench, 'rev-parse', 'HEAD') == EMBENCH_COMMIT and not git(embench, 'status', '--porcelain'), 'Clean pinned Embench required')
    tools = {}
    for name, executable, version_arg in [
        *[(n, prefix+n, '--version') for n in ('gcc', 'objcopy', 'objdump', 'nm')],
        ('verilator', 'verilator', '--version'), ('yosys', 'yosys', '-V'),
        ('nextpnr', 'nextpnr-ice40', '--version')]:
        path = shutil.which(executable)
        require(path, 'Missing executable: ' + executable)
        result = subprocess.run([path, version_arg], capture_output=True, text=True, check=True, timeout=15)
        tools[name] = {'path': str(Path(path).resolve()), 'sha256': sha(path),
                       'version': (result.stdout + result.stderr).strip().splitlines()[0]}
    source_paths = [Path(__file__), ROOT/'isaforge/model.py', ROOT/'isaforge/selection.py',
                    ROOT/'isaforge/features.py', ROOT/'isaforge/dataset.py', ROOT/'isaforge/rtl.py', ROOT/'isaforge/core_experiment.py',
                    ROOT/'isaforge/soc_experiment.py', ROOT/'isaforge/core_routing.py',
                    ROOT/'results/2026-10-13/candidates/crc32.json',
                    *[ROOT/'hardware'/n for n in ('pcpi_single.v', 'soc_top.v', 'soc_sim.cpp',
                        'soc_start.S', 'soc_link.ld', 'core_crc_firmware.c', 'candidate_sim.cpp')]]
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    output.mkdir(parents=True)
    inputs = output/'inputs'
    inputs.mkdir()
    for name in ('soc_top.v', 'soc_sim.cpp', 'soc_start.S', 'soc_link.ld', 'core_crc_firmware.c', 'pcpi_single.v', 'candidate_sim.cpp'):
        shutil.copyfile(ROOT/'hardware'/name, inputs/name)
    for name in ('picorv32.v', 'COPYING'):
        shutil.copyfile(core/name, inputs/name)
    for p in (embench/'support').glob('*.h'):
        shutil.copyfile(p, inputs/p.name)
    shutil.copyfile(embench/'support/beebsc.c', inputs/'beebsc.c')
    shutil.copyfile(embench/'src/crc32/crc_32.c', inputs/'crc32.c')
    (inputs/'common.pcf').write_text(''.join(f'set_io {p} {pin}\n' for p, pin in sorted(PINS.items())))
    plan = {'schema': 'isaforge-codesign-crc32-v1', 'configuration': CONFIG,
            'core_commit': CORE_COMMIT, 'embench_commit': EMBENCH_COMMIT,
            'tools': tools, 'source_bindings': bindings,
            'inputs': {p.name: sha(p) for p in inputs.iterdir()},
            'pool': {k: v[0] for k, v in CANDIDATES.items()},
            'measurement': 'RTL-simulated full benchmark; measured iCE40 SoC mapping/routing. No board runtime.',
            'selection': 'Within-workload adaptation, two charged random observations then bootstrap-XGBoost upper-disagreement acquisition; no historical speedup labels.',
            'frozen_before_new_labels': True}
    plan['context_id'] = digest(plan)
    plan['candidates'] = public_rows(plan['context_id'])
    write(output/'plan.json', plan)
    write(output/'setup-cost.json', {'seconds': time.monotonic()-began,
          'historical_speedup_training_rows': 0,
          'discovery': 'Reused frozen RV32IM trace/features; historical collection cost not reconstructed. Common sunk input to all four policies.'})
    return plan


class NativeRunner:
    """One native process group at a time, with persistent cumulative charges."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = (self.root/'.native.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise ValueError('Another evaluator owns this experiment') from None
        self.plan = read(self.root/'plan.json')
        self.receipts = unseal(self.root/'commands.json') if (self.root/'commands.json').exists() else []
        self.check()

    def check(self):
        plan = copy.deepcopy(self.plan)
        context = plan.pop('context_id'); rows = plan.pop('candidates')
        require(digest(plan) == context and rows == public_rows(context), 'Experiment plan changed')
        require(plan['configuration'] == CONFIG, 'Unsupported experiment configuration')
        for path, expected in plan['source_bindings'].items():
            require(sha(ROOT/path) == expected, 'Experiment source changed: ' + path)
        for name, expected in plan['inputs'].items():
            require(sha(self.root/'inputs'/name) == expected, 'Frozen input changed: ' + name)
        for tool in plan['tools'].values():
            require(sha(tool['path']) == tool['sha256'], 'Native tool changed')

    def run(self, args, log, *, expected=0, timeout=None):
        self.check()
        elapsed = sum(r['elapsed_seconds'] for r in self.receipts)
        remaining = CONFIG['total_native_seconds'] - elapsed
        require(remaining > 0 and len(self.receipts) < CONFIG['max_native_commands'], 'Cumulative native budget exhausted')
        require(shutil.disk_usage(self.root).free > 2*1024**3, 'Less than 2 GiB free')
        log = Path(log); log.parent.mkdir(parents=True, exist_ok=True)
        require(not log.exists(), 'Native log already exists; preserve the previous attempt')
        args = list(map(str, args)); began = time.monotonic(); process = None
        failure = None
        try:
            with log.open('w') as stream:
                process = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                           cwd=self.root, start_new_session=True)
                process.wait(timeout=min(remaining, timeout or CONFIG['command_seconds']))
            require(process.returncode == expected, f'Command exited {process.returncode}; see {log}')
        except BaseException as error:
            failure = repr(error)
            if process is not None:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
            raise
        finally:
            self.receipts.append({'argv': args, 'cwd': str(self.root),
                                  'elapsed_seconds': time.monotonic()-began,
                                  'returncode': process.returncode if process else None,
                                  'expected_returncode': expected, 'failure': failure,
                                  'log': str(log.relative_to(self.root)), 'log_sha256': sha(log)})
            seal(self.root/'commands.json', self.receipts)
        return log.read_text()


def validate_execution(raw, custom):
    require(raw.get('fault') == 0 and raw.get('partial_report_bits') == 0, 'Memory/report fault')
    measured = validate_crc32_simulation(raw, 1 if custom else 0)
    count = measured['protocol_statistics']['pcpi_handshakes']
    require(raw.get('pcpi_valid_cycles') == 2*count and raw.get('pcpi_wait_cycles') == count,
            'One-wait-cycle PCPI contract violated')
    return measured


class ProcessorEvaluator:
    """Evaluate only the declared lowering menu; arbitrary RTL uses a proof gate."""
    def __init__(self, root):
        self.runner = NativeRunner(root)
        self.root = self.runner.root
        self.plan = self.runner.plan
        self.inputs = self.root/'inputs'
        self.tools = {k: v['path'] for k, v in self.plan['tools'].items()}
        self.cache_hits = 0

    def verify_datapath(self, folder, datapath, formula):
        """Independent Python RV32 oracle, in addition to universal RTL proof."""
        folder.mkdir(parents=True, exist_ok=True)
        rng = random.Random(20261019)
        vectors = list(itertools.product(BOUNDARIES, repeat=2))
        vectors += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(128)]
        vector_path = folder/'vectors.txt'
        vector_path.write_text(''.join(f'{a} {b} {evaluate_formula(formula,a,b)}\n' for a,b in vectors))
        self.runner.run([self.tools['verilator'], '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal',
                         '--top-module', 'candidate', '--Mdir', folder/'obj_dir', datapath,
                         self.inputs/'candidate_sim.cpp'], folder/'build.log')
        self.runner.run([folder/'obj_dir/Vcandidate', vector_path], folder/'verification.log')
        return {'oracle': 'Independent Python RV32 integer semantics', 'vectors': len(vectors), 'seed': 20261019}

    def compile(self, folder, program, custom):
        folder.mkdir(parents=True, exist_ok=True)
        source = folder/'crc32.c'; source.write_text(program)
        elf, binary = folder/'firmware.elf', folder/'firmware.bin'
        self.runner.run([self.tools['gcc'], '-march=rv32i_zicsr', '-mabi=ilp32', '-O2', '-std=gnu17',
            '-nostdlib', '-nostartfiles', '-ffreestanding', '-fno-builtin', '-ffunction-sections',
            '-fdata-sections', '-msmall-data-limit=0', '-mno-relax', '-DCPU_MHZ=1', '-DFUSION_MASK=0',
            '-I', self.inputs, '-Wl,--no-relax', '-Wl,--gc-sections', '-Wl,-T,'+str(self.inputs/'soc_link.ld'),
            self.inputs/'soc_start.S', self.inputs/'core_crc_firmware.c', source,
            self.inputs/'beebsc.c', '-lgcc', '-o', elf], folder/'compile.log')
        self.runner.run([self.tools['objcopy'], '-O', 'binary', elf, binary], folder/'objcopy.log')
        assembly = self.runner.run([self.tools['objdump'], '-d', elf], folder/'disassembly.txt')
        symbols = self.runner.run([self.tools['nm'], '-n', elf], folder/'symbols.txt')
        end = next(int(r.split()[0],16) for r in symbols.splitlines() if r.split()[-1] == '_program_end')
        require(end <= 4096, 'Firmware exceeds stack reservation')
        data = binary.read_bytes()
        words = re.findall(r'^\s*[0-9a-f]+:\s+([0-9a-f]{8})\s', assembly, re.M)
        occurrences = [w for w in words if int(w,16) & 0xfe00707f == 0x0200000b]
        require(bool(occurrences) == custom, 'Custom opcode presence differs from lowering')
        image = folder/'firmware.hex'; image.write_text(memory_image(data))
        return image

    def simulate(self, folder, image, datapath, custom, *, expected=0):
        folder.mkdir(parents=True, exist_ok=True)
        top = folder/'soc_top.v'
        text = (self.inputs/'soc_top.v').read_text()
        require(text.count('.LATENCY(0)') == 1, 'SoC integration source changed')
        text = text.replace('.LATENCY(0)', '.LATENCY(1)').replace('"firmware.hex"', '"'+str(image)+'"')
        top.write_text(text)
        rtl = [self.inputs/'picorv32.v', self.inputs/'pcpi_single.v', datapath, top]
        self.runner.run([self.tools['verilator'], '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal',
                        '--top-module', 'soc_top', '--Mdir', folder/'obj_dir',
                        f'-GEXTENSION_MASK={int(custom)}', *rtl, self.inputs/'soc_sim.cpp'], folder/'build.log')
        raw = self.runner.run([folder/'obj_dir/Vsoc_top'], folder/'simulation.json', expected=expected)
        return (json.loads(raw) if expected == 0 else None), rtl

    def synthesize(self, folder, rtl, custom):
        folder.mkdir(parents=True, exist_ok=True)
        def quote(p): return '"'+str(p).replace('\\','\\\\').replace('"','\\"')+'"'
        script, netlist = folder/'ice40.ys', folder/'ice40-netlist.json'
        script.write_text('read_verilog '+' '.join(map(quote, rtl))+
                          f'\nchparam -set EXTENSION_MASK {int(custom)} soc_top\n'
                          'synth_ice40 -top soc_top\ncheck -assert\nwrite_json '+quote(netlist)+'\nstat\n')
        self.runner.run([self.tools['yosys'], '-s', script], folder/'synthesis.log')
        resources = validate_netlist(read(netlist))
        routes = []
        for seed in CONFIG['route_seeds']:
            report = folder/f'route-{seed}.json'
            self.runner.run([self.tools['nextpnr'], '--hx8k', '--package', 'ct256', '--json', netlist,
                            '--pcf', self.inputs/'common.pcf', '--freq', '12', '--seed', str(seed),
                            '--threads', '1', '--report', report, '--timing-allow-fail'], folder/f'route-{seed}.log')
            routes.append({'seed': seed, **timing_summary(read(report), 12.0)})
        return resources, routes

    def unit_resources(self, folder, datapath):
        folder.mkdir(parents=True, exist_ok=True)
        script, netlist = folder/'unit.ys', folder/'unit.json'
        script.write_text(f'read_verilog "{datapath}"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{netlist}"\n')
        self.runner.run([self.tools['yosys'], '-s', script], folder/'synthesis.log')
        types = Counter(c['type'] for c in read(netlist)['modules']['candidate']['cells'].values())
        return {'cell_types': dict(sorted(types.items())), 'lut4_count': types['SB_LUT4'],
                'carry_count': types['SB_CARRY'], 'flip_flop_count': sum(n for t,n in types.items() if t.startswith('SB_DFF')),
                'scope': 'Isolated combinational datapath; integrated delta also includes PCPI registers, decode and synthesis interactions.'}

    def measure(self, name, *, implementation=None):
        require(name == 'baseline' or name in CANDIDATES, 'Unknown candidate')
        self.runner.check()
        custom = name != 'baseline'
        original_rtl = generate_rtl(CANDIDATES[name][0]) if custom else generate_rtl('add(in0,in1)')
        datapath_text = original_rtl if implementation is None else implementation
        identity = digest([self.plan['context_id'], name, datapath_text])
        base = self.root/'measurements'/identity
        if (base/'measurement.json').exists():
            record = unseal(base/'measurement.json')
            require(record['evaluation_id'] == identity and record['name'] == name, 'Cached identity changed')
            for relative, expected in record['artifacts'].items():
                require(sha(base/relative) == expected, 'Cached evidence changed: '+relative)
            self.cache_hits += 1
            return record
        # Resume reuses complete designs. An interrupted/failed design gets a new
        # charged attempt, preserving every prior command, artifact and failure.
        base.mkdir(parents=True, exist_ok=True)
        folder = base/f'attempt-{len(list(base.glob("attempt-*"))):03d}'
        folder.mkdir(parents=True)
        began = time.monotonic()
        write(folder/'started.json', {'evaluation_id': identity, 'context_id': self.plan['context_id'], 'name': name})
        try:
            datapath = folder/'candidate.v'; datapath.write_text(datapath_text)
            # Universal combinational equivalence against a separately generated
            # reference. Neither the PCPI wrapper nor the scorer is editable.
            reference = folder/'reference.v'; reference.write_text(original_rtl.replace('module candidate(', 'module reference('))
            proof = folder/'equivalence.ys'
            proof.write_text(f'read_verilog "{reference}" "{datapath}"\n'
                             'proc\nopt\nequiv_make reference candidate equiv\nhierarchy -top equiv\n'
                             'equiv_simple\nequiv_status -assert\n')
            self.runner.run([self.tools['yosys'], '-s', proof], folder/'equivalence.log')
            oracle = self.verify_datapath(folder/'integer-oracle', datapath,
                                         CANDIDATES[name][0] if custom else 'add(in0,in1)')
            program = (self.inputs/'crc32.c').read_text()
            if custom: program = lower_crc(program, name)
            image = self.compile(folder/'firmware', program, custom)
            raw, rtl = self.simulate(folder/'simulation', image, datapath, custom)
            measured = validate_execution(raw, custom)
            resources, routes = self.synthesize(folder/'synthesis', rtl, custom)
            isolated = self.unit_resources(folder/'unit', datapath) if custom else None
            controls = {}
            if not custom:
                control_image = self.compile(folder/'source-control', crc32_fusion_source(program), False)
                control, _ = self.simulate(folder/'source-control-simulation', control_image, datapath, False)
                control_measurement = validate_execution(control, False)
                require(all(control_measurement[k] == measured[k] for k in
                            ('cycles','instructions','full_checksum','benchmark_result')),
                        'Source wrapper changed baseline execution')
                controls = {'source_wrapper_binary_identical': sha(control_image) == sha(image),
                            'source_wrapper_execution_identical': True,
                            'source_wrapper_performance': control_measurement}
            else:
                baseline = self.measure('baseline')
                baseline_image = self.root/baseline['firmware_image']
                stock, _ = self.simulate(folder/'stock-on-extension', baseline_image, datapath, True)
                stock_measurement = validate_execution(stock, False)
                require(all(stock_measurement[k] == baseline['performance'][k]
                            for k in ('cycles','instructions','full_checksum','benchmark_result')), 'Extension changed stock execution')
                self.simulate(folder/'illegal-on-baseline', image, datapath, False, expected=6)
                controls = {'stock_on_extension_matches_baseline': True, 'custom_on_baseline_traps': True}
            record = {'evaluation_id': identity, 'context_id': self.plan['context_id'], 'name': name,
                      'formula': CANDIDATES[name][0] if custom else None, 'implementation_sha256': sha(datapath),
                      'firmware_image': str(image.relative_to(self.root)), 'performance': measured,
                      'resources': resources, 'unit_resources': isolated, 'routes': routes, 'controls': controls,
                      'integer_oracle': oracle,
                      'correctness': 'Full benchmark checksum and self-check; universal datapath equivalence to generated RV32 reference; wrapper execution/count controls.',
                      'elapsed_seconds': time.monotonic()-began,
                      'artifacts': {str(p.relative_to(base)): sha(p) for p in sorted(base.rglob('*'))
                                    if p.is_file() and 'obj_dir' not in p.parts}}
            seal(base/'measurement.json', record)
            print(json.dumps({'candidate': name, 'cycles': measured['cycles'], 'lut4': resources['lut4_count'],
                              'seconds': record['elapsed_seconds']}), flush=True)
            return record
        except BaseException as error:
            write(folder/'failure.json', {'evaluation_id': identity, 'error': repr(error),
                                         'elapsed_seconds': time.monotonic()-began})
            raise

    def observation(self, candidate):
        baseline = self.measure('baseline')
        measured = self.measure(candidate['name'])
        period = 1000/CONFIG['frequency_mhz']
        return {**candidate, 'measurement_source': 'synthesis_estimate',
                'measurement_detail': 'Measured RTL cycles at common routed 12 MHz; not board measurements.',
                'baseline_cycles': baseline['performance']['cycles'], 'candidate_cycles': measured['performance']['cycles'],
                'baseline_period_ns': period, 'candidate_period_ns': period,
                'speedup': baseline['performance']['cycles']/measured['performance']['cycles'],
                'area': measured['resources']['lut4_count'],
                'timing_feasible': all(r['internal_timing_pass'] and r['device_fits'] for r in measured['routes']),
                'evaluation_id': measured['evaluation_id'], 'measurement_seconds': measured['elapsed_seconds']}


class LiveSelectionTools:
    """Only observations bought by this policy reach its learner.

    Native/cache results are evaluator-owned; the policy receives an allowlist.
    This object is not an OS sandbox for an external LLM.
    """
    def __init__(self, candidates, measure, budget, area_cap, seed=0, journal=None):
        require(type(budget) is int and budget >= 0, 'Invalid budget')
        require(type(seed) is int and seed >= 0, 'Invalid seed')
        require(type(area_cap) in (int, float) and math.isfinite(area_cap) and area_cap >= 0, 'Invalid area cap')
        self.rows = {r['candidate_id']: copy.deepcopy(r) for r in candidates}
        require(len(self.rows) == len(candidates) and len(self.rows) > 0, 'Unique nonempty candidate pool required')
        self.provider, self.budget, self.area_cap, self.seed = measure, budget, area_cap, seed
        self.observations, self.attempts, self.events = {}, [], []
        self.journal = journal

    @property
    def measurements_used(self): return len(self.attempts)
    @property
    def remaining_budget(self): return self.budget - self.measurements_used
    @property
    def training_size(self): return len(self.observations)
    @property
    def measured_candidate_ids(self): return list(self.observations)

    def record(self, event):
        self.events.append(event)
        if self.journal: write(self.journal, self.events)

    def list_candidates(self):
        keys = {'candidate_id', 'benchmark', 'formula', *FEATURE_COLUMNS}
        return [{k: copy.deepcopy(v) for k, v in r.items() if k in keys} for r in self.rows.values()]

    def measure(self, identity):
        require(identity in self.rows, 'Unknown candidate')
        if identity in self.observations: return [copy.deepcopy(self.observations[identity])]
        require(identity not in self.attempts and self.remaining_budget > 0, 'Measurement budget exhausted or failed attempt repeated')
        self.attempts.append(identity)
        self.record({'action': 'measure-start', 'candidate_id': identity, 'charged': self.measurements_used})
        try:
            row = self.provider(copy.deepcopy(self.rows[identity]))
            require(row['candidate_id'] == identity and row['benchmark'] == self.rows[identity]['benchmark']
                    and row['formula'] == self.rows[identity]['formula'], 'Measurement identity changed')
            require(all(row[k] == self.rows[identity][k] for k in FEATURE_COLUMNS), 'Measurement changed public features')
            _measurement(row)
            require(type(row.get('timing_feasible')) is bool, 'Missing measured timing feasibility')
            self.observations[identity] = copy.deepcopy(row)
            self.record({'action': 'measure-complete', 'candidate_id': identity, 'observation': row})
            return [copy.deepcopy(row)]
        except BaseException as error:
            self.record({'action': 'measure-failed', 'candidate_id': identity, 'error': repr(error)})
            raise

    def predict(self, ids):
        require(self.training_size > 0 and all(i in self.rows for i in ids), 'Prediction needs observations and known candidates')
        public = {r['candidate_id']: r for r in self.list_candidates()}
        began = time.monotonic()
        model = SpeedupPredictor(seed=self.seed).fit(list(self.observations.values()))
        predictions = model.predict([public[i] for i in ids])
        self.record({'action': 'predict', 'training_ids': self.measured_candidate_ids,
                     'predictions': predictions, 'warnings': model.warnings,
                     'fit_and_predict_seconds': time.monotonic()-began})
        return predictions

    def choose_final(self):
        feasible = [r for r in self.observations.values() if r['area'] <= self.area_cap and r['timing_feasible'] and r['speedup'] > 1]
        return copy.deepcopy(min(feasible, key=lambda r: (-r['speedup'], r['area'], r['candidate_id']))) if feasible else None


def comparison(candidates, observations, area_cap):
    labels = {r['candidate_id']: r for r in observations}
    require(set(labels) == {r['candidate_id'] for r in candidates} and len(labels) == len(observations), 'Complete oracle pool required')
    feasible = [r for r in observations if r['area'] <= area_cap and r['timing_feasible']]
    oracle = max([1.0] + [r['speedup'] for r in feasible])
    results = []
    for budget in CONFIG['comparison_budgets']:
        for seed in CONFIG['comparison_seeds']:
            for policy in POLICIES:
                tools = LiveSelectionTools(candidates, lambda r: copy.deepcopy(labels[r['candidate_id']]), budget, area_cap, seed)
                result = run_policy(tools, policy, bootstrap=CONFIG['bootstrap'])
                result.update(seed=seed, budget=budget, regret=oracle-result['best_speedup'],
                              measured_cost_seconds=sum(labels[i]['measurement_seconds'] for i in tools.attempts),
                              prediction_events=[e for e in tools.events if e['action'] == 'predict'])
                results.append(result)
    return {'scope': 'Offline equal-budget replay of an exhaustively measured six-candidate pool; within-workload adaptation only.',
            'oracle_speedup': oracle, 'oracle_physical_evaluations': len(labels), 'historical_speedup_training_rows': 0,
            'area_cap_integrated_lut4': area_cap, 'results': results,
            'limitations': ['One consumed workload/input configuration; no held-out-workload ranking claim.',
                           'Disagreement is not calibrated confidence. Two bootstrap measurements are charged.',
                           'Equal frequency ties are seeded; merit uses retained discovery sizes, not measured cycles.',
                           'Oracle and baseline setup cost are reported separately; replay calls are not new physical jobs.']}


def experiment(root, pilot=None):
    evaluator = ProcessorEvaluator(root)
    baseline = evaluator.measure('baseline')
    require(all(r['internal_timing_pass'] for r in baseline['routes']), 'Baseline fails common clock')
    if pilot:
        result = evaluator.measure(pilot)
        write(evaluator.root/'pilot.json', {'baseline': baseline['evaluation_id'], 'candidate': result['evaluation_id'],
                                          'estimated_remaining_seconds': result['elapsed_seconds']*(len(CANDIDATES)-1),
                                          'configuration': CONFIG})
        return result
    candidates = evaluator.plan['candidates']
    cap = baseline['resources']['lut4_count'] + CONFIG['max_added_lut4']
    live_path = evaluator.root/'live-selection.json'
    if not live_path.exists():
        tools = LiveSelectionTools(candidates, evaluator.observation, CONFIG['live_budget'], cap,
                                   CONFIG['live_seed'], evaluator.root/'live-events.json')
        live = run_policy(tools, 'active_learning', bootstrap=CONFIG['bootstrap'])
        seal(live_path, {'context_id': evaluator.plan['context_id'], **live})
    observations = [evaluator.observation(c) for c in candidates]
    write(evaluator.root/'observations.json', observations)
    report = comparison(candidates, observations, cap)
    report['live_selection'] = unseal(live_path)
    require(report['live_selection']['context_id'] == evaluator.plan['context_id'], 'Live selection context changed')
    report['baseline_setup_seconds'] = baseline['elapsed_seconds']
    report['setup_cost'] = read(evaluator.root/'setup-cost.json')
    report['native_command_seconds'] = sum(r['elapsed_seconds'] for r in evaluator.runner.receipts)
    report['native_commands'] = len(evaluator.runner.receipts)
    report['cache_hits_this_invocation'] = evaluator.cache_hits
    write(evaluator.root/'selection-report.json', report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--core-dir', type=Path, required=True); prep.add_argument('--toolchain-prefix', default='riscv-none-elf-')
    for name in ('pilot', 'run'):
        parser = sub.add_parser(name); parser.add_argument('--root', type=Path, required=True)
        if name == 'pilot': parser.add_argument('--candidate', choices=CANDIDATES, default='index_byte')
    args = p.parse_args(argv)
    if args.command == 'prepare':
        value = prepare(args.output, args.core_dir, args.toolchain_prefix)
        print(json.dumps({'prepared': str(args.output), 'context_id': value['context_id']}))
    else:
        experiment(args.root, args.candidate if args.command == 'pilot' else None)


if __name__ == '__main__':
    main()

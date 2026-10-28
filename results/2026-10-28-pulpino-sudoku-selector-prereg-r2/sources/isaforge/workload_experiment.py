"""Automatic extraction -> assembly lowering -> measured PicoRV32 speedup.

This extends the frozen CRC32 evaluator. The first cohort is a bounded, fully
enumerated pool on aha-mont64; it is not a held-out ML evaluation or LLM agent.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import time

from . import assembly_lowering as lowering
from . import codesign as c
from .codesign_audit import audit
from .speedup_corpus import validate_isa
from .workload_probe import validate_baseline

WORKLOADS = {'aha-mont64': 'aha-mont64/mont64.c', 'crc32': 'crc32/crc_32.c',
             'edn': 'edn/libedn.c', 'huffbench': 'huffbench/libhuffbench.c',
             'nettle-aes': 'nettle-aes/nettle-aes.c', 'nettle-sha256': 'nettle-sha256/nettle-sha256.c',
             'matmult-int': 'matmult-int/matmult-int.c', 'wikisort': 'wikisort/libwikisort.c'}
FLAGS = ['-march=rv32i_zicsr', '-mabi=ilp32', '-O2', '-std=gnu17', '-nostdlib', '-nostartfiles',
         '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
         '-msmall-data-limit=0', '-mno-relax', '-DCPU_MHZ=1']


def prepare(reference, output, workload, pool_size):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    c.require(workload in WORKLOADS and 1 <= pool_size <= 30, 'Invalid workload/pool size')
    c.require(not output.exists(), 'Prepare requires a new output directory')
    audit(reference)
    old = c.read(reference / 'plan.json')
    source = c.ROOT / 'benchmarks/embench/src' / WORKLOADS[workload]
    extras = ['isaforge/workload_experiment.py', 'isaforge/assembly_lowering.py',
              'isaforge/workload_probe.py', 'isaforge/speedup_corpus.py',
              'src/candidates.py', 'src/tracing.py', 'src/verify_candidate_fusions.py',
              'hardware/profile_sim.cpp', 'hardware/embench_firmware.c', 'hardware/embench_memory.c',
              str(source.relative_to(c.ROOT))]
    bindings = {**old['source_bindings'], **{p: c.sha(c.ROOT / p) for p in extras}}
    output.mkdir(parents=True)
    shutil.copytree(reference / 'inputs', output / 'inputs')
    for name in ('embench_firmware.c', 'embench_memory.c', 'profile_sim.cpp'):
        shutil.copyfile(c.ROOT / 'hardware' / name, output / 'inputs' / name)
    shutil.copyfile(source, output / 'inputs/program.c')
    plan = {'schema': 'isaforge-automatic-workload-v1', 'workload': workload,
            'reference_context': old['context_id'], 'core_commit': old['core_commit'],
            'embench_commit': old['embench_commit'], 'tools': old['tools'], 'source_bindings': bindings,
            'inputs': {p.name: c.sha(p) for p in (output / 'inputs').iterdir()},
            'compiler_flags': FLAGS, 'pool_size': pool_size, 'maximum_candidate_operations': 4,
            'pool_rule': 'Top executable overlap-safe instruction savings before any candidate performance labels; deterministic formula tie-break.',
            'configuration': {**c.CONFIG, 'workload': workload},
            'profile': 'Actual pinned PicoRV32 counter increments and PC, between rdinstret markers; baseline binary and counters independently checked.',
            'measurement': 'Full benchmark invocation including software helper routines; startup, warmup and verification excluded; fixed common 12 MHz.',
            'selection_scope': 'Exhaustive oracle over this restricted, predeclared single-instruction pool; no claim about all possible instructions.',
            'native_limits': {'commands': 240, 'seconds': 2400, 'command_seconds': 180, 'workers': 1, 'build_workers': 2}}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    for path in extras:
        target = output / 'sources' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / path, target)
    return plan


class Runner(c.NativeRunner):
    def check(self):
        plan = copy.deepcopy(self.plan)
        identity = plan.pop('context_id')
        c.require(c.digest(plan) == identity, 'Experiment plan changed')
        c.require(c.unseal(self.root / 'plan.json') == self.plan, 'Plan on disk changed')
        c.require(plan['native_limits'] == {'commands': 240, 'seconds': 2400, 'command_seconds': 180,
                                           'workers': 1, 'build_workers': 2}, 'Unsupported budget')
        for path, expected in plan['source_bindings'].items():
            c.require(c.sha(c.ROOT / path) == expected, 'Source changed: ' + path)
        for path, expected in plan['inputs'].items():
            c.require(c.sha(self.root / 'inputs' / path) == expected, 'Input changed: ' + path)
        for tool in plan['tools'].values():
            c.require(c.sha(tool['path']) == tool['sha256'], 'Tool changed')


def artifact_hashes(folder):
    return {str(p.relative_to(folder)): c.sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and 'obj_dir' not in p.parts}


def verify_cache(folder, name):
    record = c.unseal(folder / name)
    for path, expected in record['artifacts'].items():
        c.require(c.sha(folder / path) == expected, 'Cached evidence changed: ' + path)
    return record


def validate_execution(raw, candidate=None):
    expected = candidate['total_custom_instructions'] if candidate else 0
    c.require(raw.get('pcpi_handshakes') == expected, 'Custom execution count differs from profile')
    c.require(raw.get('pcpi_valid_cycles') == 2 * expected and raw.get('pcpi_wait_cycles') == expected,
              'PCPI handshake latency mismatch')
    # Use the common upstream benchmark check after separately validating PCPI.
    clean = {**raw, **{k: 0 for k in ('pcpi_handshakes', 'pcpi_valid_cycles', 'pcpi_wait_cycles')}}
    result = validate_baseline(clean)
    result['custom_instructions'] = expected
    result['region_custom_instructions'] = candidate['region_custom_instructions'] if candidate else 0
    return result


class Evaluator(c.ProcessorEvaluator):
    def __init__(self, root):
        self.runner = Runner(root)
        self.root, self.plan = self.runner.root, self.runner.plan
        self.inputs = self.root / 'inputs'
        self.tools = {k: v['path'] for k, v in self.plan['tools'].items()}
        self.cache_hits = 0

    def compile_program(self, folder, source, expected_sites=0):
        folder.mkdir(parents=True)
        elf, binary = folder / 'firmware.elf', folder / 'firmware.bin'
        self.runner.run([self.tools['gcc'], *FLAGS, '-I', self.inputs, '-Wl,--no-relax', '-Wl,--gc-sections',
                         '-Wl,-T,' + str(self.inputs / 'soc_link.ld'), self.inputs / 'soc_start.S',
                         self.inputs / 'embench_firmware.c', self.inputs / 'embench_memory.c', source,
                         self.inputs / 'beebsc.c', '-lgcc', '-o', elf], folder / 'compile.log')
        self.runner.run([self.tools['objcopy'], '-O', 'binary', elf, binary], folder / 'objcopy.log')
        disassembly = self.runner.run([self.tools['objdump'], '-d', elf], folder / 'disassembly.txt')
        isa = validate_isa(disassembly)
        c.require(isa['custom_static_sites'] == expected_sites, 'Unexpected custom instruction sites')
        symbols = self.runner.run([self.tools['nm'], '-n', elf], folder / 'symbols.txt')
        end = next(int(row.split()[0], 16) for row in symbols.splitlines() if row.split()[-1] == '_program_end')
        c.require(end <= 4096, 'Program violates 4 KiB stack reservation')
        image = folder / 'firmware.hex'
        image.write_text(c.memory_image(binary.read_bytes()))
        c.write(folder / 'validation.json', {'isa': isa, 'program_and_bss_end': end})
        return image

    def discover(self):
        self.runner.check()
        base = self.root / 'discovery'
        if (base / 'discovery.json').exists():
            self.cache_hits += 1
            return verify_cache(base, 'discovery.json')
        base.mkdir(exist_ok=True)
        folder = base / f'attempt-{len(list(base.glob("attempt-*"))):03d}'
        folder.mkdir()
        original = self.compile_program(folder / 'original', self.inputs / 'program.c')
        assembly = folder / 'program.s'
        self.runner.run([self.tools['gcc'], *FLAGS, '-I', self.inputs, '-S', self.inputs / 'program.c',
                         '-o', assembly], folder / 'assembly.log')
        marked, sites = lowering.mark_assembly(assembly.read_text())
        marked_path = folder / 'marked.S'; marked_path.write_text(marked)
        image = self.compile_program(folder / 'marked', marked_path)
        c.require(c.sha(original) == c.sha(image), 'Assembly markers changed baseline bytes')
        site_map = lowering.map_sites(sites, (image.parent / 'symbols.txt').read_text())
        # Expose two existing registers for simulator observation only. The
        # synthesized core is the original pinned input, without these comments.
        core = (self.inputs / 'picorv32.v').read_text()
        old = 'reg [63:0] count_cycle, count_instr;'
        c.require(core.count(old) == 1, 'Pinned counter declaration changed')
        core = core.replace(old, 'reg [63:0] count_cycle; reg [63:0] count_instr /* verilator public_flat_rd */;')
        old = 'reg [31:0] reg_pc, reg_next_pc, reg_op1, reg_op2, reg_out;'
        c.require(core.count(old) == 1, 'Pinned PC declaration changed')
        core = core.replace(old, 'reg [31:0] reg_pc /* verilator public_flat_rd */; reg [31:0] reg_next_pc, reg_op1, reg_op2, reg_out;')
        profile_core = folder / 'profile_core.v'; profile_core.write_text(core)
        top = folder / 'soc_top.v'
        top.write_text((self.inputs / 'soc_top.v').read_text().replace('"firmware.hex"', '"' + str(image) + '"'))
        datapath = folder / 'candidate.v'; datapath.write_text(c.generate_rtl('add(in0,in1)'))
        self.runner.run([self.tools['verilator'], '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal',
                         '--top-module', 'soc_top', '--Mdir', folder / 'obj_dir', '-GEXTENSION_MASK=0',
                         profile_core, self.inputs / 'pcpi_single.v', datapath, top,
                         self.inputs / 'profile_sim.cpp'], folder / 'profile-build.log')
        raw = json.loads(self.runner.run([folder / 'obj_dir/Vsoc_top', image.parent / 'firmware.bin'], folder / 'profile.json'))
        performance = validate_execution(raw)
        c.require(raw['markers'] == 2 and sum(raw['region_counts'].values()) + 1 == performance['instructions'],
                  'Profile instruction counts do not reconcile')
        program = lowering.read_program((image.parent / 'disassembly.txt').read_text())
        result = lowering.extract(program, raw, site_map, self.plan['pool_size'])
        c.require(len(result['pool']) == self.plan['pool_size'], 'Too few executable candidates for declared pool')
        for candidate in result['pool']:
            candidate['candidate_id'] = c.digest([self.plan['context_id'], candidate['formula']])
            candidate['lowering_check'] = lowering.verify_lowering(candidate, program, result['block_starts'])
            lowered = folder / (candidate['name'] + '.S')
            lowered.write_text(lowering.lower(marked, candidate))
            candidate['assembly'] = str(lowered.relative_to(self.root))
            candidate['assembly_sha256'] = c.sha(lowered)
        result.update(context_id=self.plan['context_id'], workload=self.plan['workload'],
                      baseline_performance=performance, baseline_image=str(image.relative_to(self.root)),
                      baseline_binary_identical=True, mapped_statements=len(site_map),
                      profile=str((folder / 'profile.json').relative_to(self.root)), artifacts=artifact_hashes(base))
        c.seal(base / 'discovery.json', result)
        print(json.dumps({'discovery': self.plan['workload'], 'raw_formulas': result['raw_formula_count'],
                          'executable_formulas': result['executable_formula_count'],
                          'frozen_pool': [(p['name'], p['formula'], p['expected_instruction_reduction']) for p in result['pool']]}), flush=True)
        return result

    def measure(self, name):
        discovery = self.discover()
        candidate = next((row for row in discovery['pool'] if row['name'] == name), None)
        c.require(name == 'baseline' or candidate is not None, 'Candidate outside frozen pool')
        identity = c.digest([self.plan['context_id'], c.sha(self.root / 'discovery/discovery.json'), name])
        base = self.root / 'measurements' / name
        if (base / 'measurement.json').exists():
            record = verify_cache(base, 'measurement.json')
            c.require(record['evaluation_id'] == identity, 'Measurement identity changed')
            self.cache_hits += 1
            return record
        baseline = self.measure('baseline') if candidate else None
        base.mkdir(parents=True, exist_ok=True)
        folder = base / f'attempt-{len(list(base.glob("attempt-*"))):03d}'
        folder.mkdir(); began = time.monotonic()
        try:
            datapath = folder / 'candidate.v'
            datapath.write_text(c.generate_rtl(candidate['formula'] if candidate else 'add(in0,in1)'))
            oracle = self.verify_datapath(folder / 'integer-oracle', datapath, candidate['formula']) if candidate else None
            image = (self.compile_program(folder / 'firmware', self.root / candidate['assembly'], len(candidate['occurrences']))
                     if candidate else self.root / discovery['baseline_image'])
            raw, rtl = self.simulate(folder / 'simulation', image, datapath, bool(candidate))
            measured = validate_execution(raw, candidate)
            if candidate:
                c.require(measured['benchmark_result_u32'] == baseline['performance']['benchmark_result_u32'], 'Program result changed')
                c.require(baseline['performance']['instructions'] - measured['instructions'] == candidate['expected_instruction_reduction'],
                          'Measured instruction reduction differs from actual removed operations')
                stock, _ = self.simulate(folder / 'stock-on-extension', self.root / baseline['firmware_image'], datapath, True)
                c.require(validate_execution(stock) == baseline['performance'], 'Extension changed stock program execution')
                self.simulate(folder / 'illegal-on-baseline', image, datapath, False, expected=6)
                controls = {'stock_on_extension_identical': True, 'custom_on_baseline_traps': True,
                            'instruction_reduction_matches_profile': True}
            else:
                c.require(measured == discovery['baseline_performance'], 'Profiling changed program performance')
                controls = {'profile_and_unobserved_execution_identical': True, 'assembly_labels_binary_identical': True}
            resources, routes = self.synthesize(folder / 'synthesis', rtl, bool(candidate))
            unit = self.unit_resources(folder / 'unit', datapath) if candidate else None
            record = {'evaluation_id': identity, 'context_id': self.plan['context_id'], 'workload': self.plan['workload'],
                      'name': name, 'formula': candidate['formula'] if candidate else None,
                      'candidate_id': candidate['candidate_id'] if candidate else None,
                      'features': candidate['features'] if candidate else None,
                      'performance': measured, 'resources': resources, 'routes': routes, 'unit_resources': unit,
                      'firmware_image': str(image.relative_to(self.root)), 'firmware_sha256': c.sha(image),
                      'integer_oracle': oracle, 'controls': controls,
                      'correctness': 'Upstream full-program self-check, sampled independent integer and block semantics, exact dynamic execution counts, stock/custom processor controls.',
                      'speedup': baseline['performance']['cycles'] / measured['cycles'] if candidate else 1.0,
                      'added_lut4': resources['lut4_count'] - baseline['resources']['lut4_count'] if candidate else 0,
                      'timing_feasible': all(r['internal_timing_pass'] and r['device_fits'] for r in routes),
                      'frequency_mhz': 12.0, 'elapsed_seconds': time.monotonic() - began,
                      'artifacts': artifact_hashes(base)}
            c.seal(base / 'measurement.json', record)
            print(json.dumps({k: record[k] for k in ('name', 'speedup', 'added_lut4', 'timing_feasible', 'elapsed_seconds')}), flush=True)
            return record
        except BaseException as error:
            c.write(folder / 'failure.json', {'error': repr(error), 'elapsed_seconds': time.monotonic() - began})
            raise

    def collect(self):
        discovery = self.discover()
        baseline = self.measure('baseline')
        measurements = [self.measure(row['name']) for row in discovery['pool']]
        report = {'schema': 'isaforge-automatic-workload-results-v1', 'context_id': self.plan['context_id'],
                  'workload': self.plan['workload'], 'baseline': baseline, 'measurements': measurements,
                  'candidate_pool': discovery['pool'], 'native_commands': len(self.runner.receipts),
                  'native_seconds': sum(r['elapsed_seconds'] for r in self.runner.receipts),
                  'limitations': ['One fixed benchmark input per workload; no independent input generalization.',
                                  'RV32I, bounded 8 KiB RAM, two-input one-output integer instructions only.',
                                  'Single instructions measured separately; speedups must not be added for combinations.',
                                  'FPGA synthesis/routing and RTL simulation, not physical board measurements.',
                                  'Top-merit extraction shortlist is not an oracle over all legal instructions.',
                                  'No new ML generalization or LLM-agent advantage claimed by this collection.']}
        c.seal(self.root / 'report.json', report)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'collect'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=WORKLOADS, default='aha-mont64')
    parser.add_argument('--pool-size', type=int, default=6)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root is required')
        prepare(args.reference_root, args.root, args.workload, args.pool_size)
    else:
        evaluator = Evaluator(args.root)
        try:
            getattr(evaluator, args.command)()
        finally:
            evaluator.runner.lock.close()


if __name__ == '__main__':
    main()

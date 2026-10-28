"""Checked SLRE memory partition, reusing the frozen processor evaluator.

Only the linker partition changes: original 8 KiB SoC/core/PCPI RTL is retained.
Passive simulator observation checks every stack-pointer update and RAM write.
Candidate pools sample the full executable, calibrated pool by merit rank before
candidate labels, rather than taking only its highest-merit members.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from . import assembly_lowering as lowering
from . import codesign as c
from . import compact_workload as compact
from . import latency_features as latency
from . import workload_audit as old_audit
from . import workload_experiment as w
from .speedup_corpus import validate_isa

SOURCE = 'isaforge/partitioned_workload.py'
PARTITION = {'ram_bytes': 8192, 'program_limit': 4224, 'stack_floor': 4352,
             'stack_bytes': 3840, 'minimum_guard_bytes': 128}
POOL_RULE = ('Evenly spaced rank indices round(i*(N-1)/(K-1)) across all executable '
             'calibrated formulas sorted by instruction savings then formula; '
             'K fixed before discovery, no candidate performance labels.')
EXTRACT = lowering.extract


def prepare(reference, output, pool_size=6):
    from scripts.prepare_slre_runtime import prepare as prepare_runtime
    from scripts.analyze_speedup_model import authenticated_calibration
    output = Path(output)
    c.require(type(pool_size) is int and 2 <= pool_size <= 12, 'Pool size must be 2..12')
    calibration_root = c.ROOT / 'results/2026-10-20-latency-calibration'
    calibration, _ = authenticated_calibration(calibration_root)
    plan = prepare_runtime(reference, output)
    plan.pop('context_id')
    plan['pool_size'] = pool_size
    plan['pool_rule'] = POOL_RULE
    plan['memory_partition'] = dict(PARTITION)
    plan['configuration']['stack_bytes'] = PARTITION['stack_bytes']
    plan['runtime_support'] = 'Unmodified upstream SLRE with recorded C-locale runtime and explicit checked memory partition.'
    plan['build_variant']['required_entrypoint'] = SOURCE
    plan['calibration_compatibility'] = {
        'context_id': calibration['context_id'],
        'report_sha256': c.sha(calibration_root / 'report.json'),
        'scope': 'Same core, synchronous 8 KiB RAM and one-wait PCPI. Compiler -Os and linker partition differ explicitly; analytic transfer remains an assumption tested by measured labels.'}
    for name in ('picorv32.v', 'soc_top.v', 'pcpi_single.v'):
        c.require(c.sha(output / 'inputs' / name) == c.sha(calibration_root / 'inputs' / name),
                  'Calibration hardware differs: ' + name)
    link = output / 'inputs/soc_link.ld'
    text = link.read_text()
    c.require(text.count('ASSERT(_program_end <= 4096,') == 1, 'Unexpected linker contract')
    c.require(text.count('.data : {') == 1, 'Unexpected writable section')
    text = text.replace('.data : {', '.data : { _writable_start = .;')
    text = text.replace('ASSERT(_program_end <= 4096, "firmware must leave at least 4 KiB for the stack")',
                        'ASSERT(_program_end <= 4224, "firmware must leave the declared guard and 3840-byte stack")')
    link.write_text(text)
    for name in ('checked_sim.cpp', 'stack_monitor.hpp'):
        shutil.copyfile(c.ROOT / 'hardware' / name, output / 'inputs' / name)
    c.write(output / 'inputs/latency-calibration.json', calibration)
    extras = (SOURCE, 'hardware/checked_sim.cpp', 'hardware/stack_monitor.hpp',
              'isaforge/latency_features.py', 'isaforge/workload_audit.py')
    for name in extras:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        target = output / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    plan['inputs'] = {p.name: c.sha(p) for p in (output / 'inputs').iterdir()}
    plan['guard_controls'] = ['SP below stack floor must fail with exit10',
                              'RAM write in guard must fail with exit10']
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    return plan


def memory_symbols(image):
    rows = (Path(image).parent / 'symbols.txt').read_text().splitlines()
    symbols = {r.split()[-1]: int(r.split()[0], 16) for r in rows if len(r.split()) == 3}
    end, start = symbols['_program_end'], symbols['_writable_start']
    c.require(0 <= start <= end <= PARTITION['program_limit'], 'Program violates checked partition')
    return end, start


def memory_image(binary):
    c.require(isinstance(binary, bytes) and 0 < len(binary) <= PARTITION['program_limit'],
              'Program image exceeds checked partition')
    image = binary + bytes(PARTITION['ram_bytes'] - len(binary))
    return ''.join(f"{int.from_bytes(image[i:i+4], 'little'):08x}\n"
                   for i in range(0, PARTITION['ram_bytes'], 4))


def validate_memory(raw, *, trapped=False):
    c.require(raw.get('stack_initialized') is True and raw.get('stack_violations') == 0,
              'Stack initialization/guard check failed')
    c.require(type(raw.get('min_sp')) is int and PARTITION['stack_floor'] <= raw['min_sp'] <= 8192,
              'Invalid minimum stack pointer')
    c.require(raw.get('max_stack_bytes') == 8192 - raw['min_sp'] and
              type(raw.get('stack_checked_cycles')) is int and raw['stack_checked_cycles'] > 0,
              'Missing continuous stack observations')
    c.require(raw.get('first_violation') == {'kind': 'none', 'pc': 0, 'address': 0}, 'Memory violation recorded')
    c.require(raw.get('trapped') is trapped, 'Unexpected trap status')
    return {'min_sp': raw['min_sp'], 'max_stack_bytes': raw['max_stack_bytes'],
            'stack_headroom_bytes': raw['min_sp'] - PARTITION['stack_floor'],
            'checked_cycles': raw['stack_checked_cycles']}


def observer_sources(inputs, folder, image):
    """Only Verilator visibility comments differ; synthesized RTL stays original."""
    core = (inputs / 'picorv32.v').read_text()
    replacements = {
        'reg [63:0] count_cycle, count_instr;': 'reg [63:0] count_cycle; reg [63:0] count_instr /* verilator public_flat_rd */;',
        'reg [31:0] reg_pc, reg_next_pc, reg_op1, reg_op2, reg_out;': 'reg [31:0] reg_pc /* verilator public_flat_rd */; reg [31:0] reg_next_pc, reg_op1, reg_op2, reg_out;',
        'reg [31:0] cpuregs [0:regfile_size-1];': 'reg [31:0] cpuregs [0:regfile_size-1] /* verilator public_flat_rd */;'}
    for old, new in replacements.items():
        c.require(core.count(old) == 1, 'Pinned observer declaration changed')
        core = core.replace(old, new)
    core_path = folder / 'observer_core.v'; core_path.write_text(core)
    top = (inputs / 'soc_top.v').read_text()
    c.require(top.count('.LATENCY(0)') == 1, 'PCPI latency interface changed')
    top = top.replace('.LATENCY(0)', '.LATENCY(1)').replace('"firmware.hex"', '"' + str(image) + '"')
    synthesis_top = folder / 'soc_top.v'; synthesis_top.write_text(top)
    replacements = {'wire mem_valid, mem_instr;': 'wire mem_valid /* verilator public_flat_rd */, mem_instr;',
                    'wire [31:0] mem_addr, mem_wdata;': 'wire [31:0] mem_addr /* verilator public_flat_rd */, mem_wdata;',
                    'wire [3:0] mem_wstrb;': 'wire [3:0] mem_wstrb /* verilator public_flat_rd */;',
                    'reg mem_ready;': 'reg mem_ready /* verilator public_flat_rd */;'}
    for old, new in replacements.items():
        c.require(top.count(old) == 1, 'Pinned memory declaration changed')
        top = top.replace(old, new)
    top_path = folder / 'observer_top.v'; top_path.write_text(top)
    return core_path, top_path, synthesis_top


def extract_pool(program, profile, sites, pool_size, calibration):
    result = EXTRACT(program, profile, sites, pool_size)
    table = latency.latency_table(calibration)
    eligible, excluded = [], []
    for candidate in result['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency.instruction_latency(program[int(pc, 16)], table)
        except ValueError:
            excluded.append(candidate['formula'])
        else:
            eligible.append(candidate)
    c.require(len(eligible) >= pool_size, 'Too few calibrated executable candidates')
    indices = [round(i * (len(eligible) - 1) / (pool_size - 1)) for i in range(pool_size)]
    c.require(len(set(indices)) == pool_size, 'Duplicate stratified indices')
    result.update(pool=[eligible[i] for i in indices], pool_rule=POOL_RULE,
                  eligible_formula_count=len(eligible), excluded_uncalibrated_formulas=excluded,
                  selected_rank_indices=indices)
    return result


@contextmanager
def pool_for_audit(calibration):
    original = lowering.extract
    lowering.extract = lambda program, profile, sites, size: extract_pool(program, profile, sites, size, calibration)
    try:
        yield
    finally:
        lowering.extract = original


class Evaluator(w.Evaluator):
    def __init__(self, root):
        super().__init__(root)
        c.require(self.plan.get('memory_partition') == PARTITION, 'Different partition protocol')
        c.require(self.plan['compiler_flags'] == list(compact.FLAGS), 'Different compiler protocol')

    def compile_program(self, folder, source, expected_sites=0, *, fixture=False):
        folder.mkdir(parents=True)
        elf, binary = folder / 'firmware.elf', folder / 'firmware.bin'
        files = [source] if fixture else [self.inputs / 'soc_start.S', self.inputs / 'embench_firmware.c',
                 self.inputs / 'embench_memory.c', source, self.inputs / 'beebsc.c']
        self.runner.run([self.tools['gcc'], *self.plan['compiler_flags'], '-I', self.inputs,
                         '-Wl,--no-relax', '-Wl,--gc-sections', '-Wl,-T,' + str(self.inputs / 'soc_link.ld'),
                         *files, '-lgcc', '-o', elf], folder / 'compile.log')
        self.runner.run([self.tools['objcopy'], '-O', 'binary', elf, binary], folder / 'objcopy.log')
        disassembly = self.runner.run([self.tools['objdump'], '-d', elf], folder / 'disassembly.txt')
        isa = validate_isa(disassembly)
        c.require(isa['custom_static_sites'] == expected_sites, 'Unexpected custom instruction sites')
        self.runner.run([self.tools['nm'], '-n', elf], folder / 'symbols.txt')
        image = folder / 'firmware.hex'
        end, start = memory_symbols(image)
        image.write_text(memory_image(binary.read_bytes()))
        c.write(folder / 'validation.json', {'isa': isa, 'program_and_bss_end': end,
                 'writable_start': start, 'stack_floor': PARTITION['stack_floor'], 'guard_bytes': 4352 - end})
        return image

    def simulate(self, folder, image, datapath, custom, *, expected=0):
        folder.mkdir(parents=True, exist_ok=True)
        core, top, synthesis_top = observer_sources(self.inputs, folder, image)
        self.runner.run([self.tools['verilator'], '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal',
                         '--top-module', 'soc_top', '--Mdir', folder / 'obj_dir', f'-GEXTENSION_MASK={int(custom)}',
                         core, self.inputs / 'pcpi_single.v', datapath, top, self.inputs / 'checked_sim.cpp'], folder / 'build.log')
        end, start = memory_symbols(image)
        raw = json.loads(self.runner.run([folder / 'obj_dir/Vsoc_top', image.parent / 'firmware.bin',
                         str(end), str(start), '4352'], folder / 'simulation.json', expected=expected))
        if expected != 10:
            validate_memory(raw, trapped=expected == 6)
        if folder.name == 'simulation' and not custom and expected == 0:
            plain, _ = c.ProcessorEvaluator.simulate(self, folder.parent / 'unobserved-control', image, datapath, False)
            c.require(w.validate_execution(raw) == w.validate_execution(plain), 'Observer changes execution')
        return raw, [self.inputs / 'picorv32.v', self.inputs / 'pcpi_single.v', datapath, synthesis_top]

    def guard_controls(self):
        self.runner.check()
        base = self.root / 'guard-controls'
        if (base / 'controls.json').exists():
            return w.verify_cache(base, 'controls.json')
        base.mkdir(exist_ok=True)
        results = []
        for name, code, kind in [('stack-underflow', 'li sp,4096', 'stack-pointer'),
                                 ('guard-write', 'li t0,4224\nsw zero,0(t0)', 'ram-write')]:
            folder = base / name
            folder.mkdir()
            source = folder / 'fixture.S'
            source.write_text('.section .text.start\n.global _start\n_start:\nli sp,8192\n' + code + '\nebreak\n')
            image = self.compile_program(folder / 'firmware', source, fixture=True)
            datapath = folder / 'candidate.v'; datapath.write_text(c.generate_rtl('add(in0,in1)'))
            raw, _ = self.simulate(folder / 'guard-simulation', image, datapath, False, expected=10)
            c.require(raw['stack_initialized'] and raw['stack_violations'] > 0 and
                      raw['first_violation']['kind'] == kind, 'Guard control did not detect expected violation')
            results.append({'name': name, 'detected_kind': kind, 'raw': raw})
        record = {'controls': results, 'artifacts': w.artifact_hashes(base)}
        c.seal(base / 'controls.json', record)
        return record

    def discover(self):
        self.runner.check()
        self.guard_controls()
        base = self.root / 'discovery'
        if (base / 'discovery.json').exists():
            self.cache_hits += 1
            return w.verify_cache(base, 'discovery.json')
        base.mkdir(exist_ok=True)
        folder = base / f'attempt-{len(list(base.glob("attempt-*"))):03d}'
        folder.mkdir()
        original = self.compile_program(folder / 'original', self.inputs / 'program.c')
        assembly = folder / 'program.s'
        self.runner.run([self.tools['gcc'], *self.plan['compiler_flags'], '-I', self.inputs,
                         '-S', self.inputs / 'program.c', '-o', assembly], folder / 'assembly.log')
        marked, sites = lowering.mark_assembly(assembly.read_text())
        marked_path = folder / 'marked.S'; marked_path.write_text(marked)
        image = self.compile_program(folder / 'marked', marked_path)
        c.require(c.sha(original) == c.sha(image), 'Assembly markers changed baseline bytes')
        site_map = lowering.map_sites(sites, (image.parent / 'symbols.txt').read_text())
        datapath = folder / 'candidate.v'; datapath.write_text(c.generate_rtl('add(in0,in1)'))
        raw, _ = self.simulate(folder / 'profile', image, datapath, False)
        performance = w.validate_execution(raw)
        c.require(raw['markers'] == 2 and sum(raw['region_counts'].values()) + 1 == performance['instructions'],
                  'Profile instruction counts do not reconcile')
        program = lowering.read_program((image.parent / 'disassembly.txt').read_text())
        result = extract_pool(program, raw, site_map, self.plan['pool_size'], c.read(self.inputs / 'latency-calibration.json'))
        for candidate in result['pool']:
            candidate['candidate_id'] = c.digest([self.plan['context_id'], candidate['formula']])
            candidate['lowering_check'] = lowering.verify_lowering(candidate, program, result['block_starts'])
            lowered = folder / (candidate['name'] + '.S'); lowered.write_text(lowering.lower(marked, candidate))
            candidate['assembly'] = str(lowered.relative_to(self.root)); candidate['assembly_sha256'] = c.sha(lowered)
        result.update(context_id=self.plan['context_id'], workload=self.plan['workload'],
                      baseline_performance=performance, baseline_image=str(image.relative_to(self.root)),
                      baseline_binary_identical=True, mapped_statements=len(site_map),
                      memory_check=validate_memory(raw), profile=str((folder / 'profile/simulation.json').relative_to(self.root)),
                      artifacts=w.artifact_hashes(base))
        c.seal(base / 'discovery.json', result)
        print(json.dumps({'workload': 'slre', 'eligible_formulas': result['eligible_formula_count'],
                          'pool': [(x['name'], x['formula']) for x in result['pool']],
                          'memory_check': result['memory_check']}), flush=True)
        return result

    def collect(self):
        result = super().collect()
        result['memory_partition'] = dict(PARTITION)
        result['pool_rule'] = POOL_RULE
        result['limitations'] = [item for item in result['limitations'] if not item.startswith('Top-merit')]
        result['limitations'] += ['Rank-stratified subset of calibrated executable candidates; the measured oracle covers only that subset.',
                                  'The -Os compiler and checked 4352/3840 partition differ explicitly from historical -O2 contexts.',
                                  'Memory safety is observed for this fixed input; not a universal stack bound.']
        c.seal(self.root / 'report.json', result)
        return result


def portable_binary(root, recorded):
    parts = Path(recorded).parts
    starts = [parts.index(name) for name in ('guard-controls', 'discovery', 'measurements') if name in parts]
    c.require(len(starts) == 1, 'Unknown simulation firmware path')
    return Path(root).joinpath(*parts[starts[0]:])


def audit(root):
    root = Path(root).resolve()
    plan = c.unseal(root / 'plan.json')
    c.require(plan.get('memory_partition') == PARTITION and plan['compiler_flags'] == list(compact.FLAGS), 'Wrong memory/compiler protocol')
    with pool_for_audit(c.read(root / 'inputs/latency-calibration.json')):
        checked = old_audit.audit(root)
    guards = w.verify_cache(root / 'guard-controls', 'controls.json')
    c.require([(r['name'], r['detected_kind']) for r in guards['controls']] ==
              [('stack-underflow', 'stack-pointer'), ('guard-write', 'ram-write')], 'Guard controls missing')
    for row in guards['controls']:
        raw = c.read(root / 'guard-controls' / row['name'] / 'guard-simulation/simulation.json')
        c.require(raw == row['raw'] and raw['stack_initialized'] is True and raw['stack_violations'] > 0 and
                  raw['first_violation']['kind'] == row['detected_kind'], 'Guard control raw evidence differs')
    commands = c.unseal(root / 'commands.json')
    memory = {}
    for receipt in commands:
        if receipt['argv'][0] == plan['tools']['gcc']['path']:
            c.require(receipt['argv'][1:1+len(compact.FLAGS)] == list(compact.FLAGS), 'Compiler flags differ')
        if receipt['log'].endswith('/simulation.json') and 'unobserved-control' not in receipt['log']:
            raw = c.read(root / receipt['log'])
            if receipt['expected_returncode'] == 10:
                c.require(raw['stack_violations'] > 0 and raw['stack_initialized'], 'Guard control missing violation')
            else:
                memory[receipt['log']] = validate_memory(raw, trapped=receipt['expected_returncode'] == 6)
            c.require(len(receipt['argv']) == 5 and receipt['argv'][-1] == '4352', 'Observer invocation differs')
            # Never read the original machine's absolute path during replay.
            binary = portable_binary(root, receipt['argv'][1])
            end, start = memory_symbols(binary.with_suffix('.hex'))
            c.require(receipt['argv'][-3:-1] == [str(end), str(start)], 'Observer bounds differ from ELF symbols')
            c.require(binary.with_suffix('.hex').read_text() == memory_image(binary.read_bytes()),
                      'RAM image differs from binary and zero-fill contract')
    baseline = c.unseal(root / 'measurements/baseline/measurement.json')
    folder = root / 'measurements/baseline'
    plain = [folder / p for p in baseline['artifacts'] if p.endswith('/unobserved-control/simulation.json')]
    c.require(len(plain) == 1 and w.validate_execution(c.read(plain[0])) == baseline['performance'], 'Unobserved baseline control missing')
    checked['memory_partition'] = PARTITION
    checked['memory_checks'] = memory
    checked['guard_negative_controls'] = 2
    return checked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'collect', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--pool-size', type=int, default=6)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        print(prepare(args.reference_root, args.root, args.pool_size)['context_id'])
    elif args.command == 'audit':
        print(json.dumps(audit(args.root), indent=2))
    else:
        evaluator = Evaluator(args.root)
        try:
            result = evaluator.measure('baseline') if args.command == 'baseline' else getattr(evaluator, args.command)()
            if args.command == 'collect':
                print(json.dumps({'measurements': len(result['measurements']), 'native_commands': result['native_commands']}))
        finally:
            evaluator.runner.lock.close()


if __name__ == '__main__':
    main()

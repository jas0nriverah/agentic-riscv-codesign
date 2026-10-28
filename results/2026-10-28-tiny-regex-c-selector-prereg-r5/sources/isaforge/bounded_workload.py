"""Fresh checked 6400/6528 partition on the unchanged synchronous 8 KiB SoC.

Reuses the frozen extraction, lowering and processor evaluator. The reduced
stack is an observed fixed-input bound, never a universal memory-safety claim.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from . import codesign as c, compact_workload as compact
from . import partitioned_workload as partition, workload_campaign as campaign
from . import workload_experiment as w
from .speedup_corpus import validate_isa

SOURCE = 'isaforge/bounded_workload.py'
PARTITION = dict(ram_bytes=8192, program_limit=6400, stack_floor=6528,
                 stack_bytes=1664, minimum_guard_bytes=128)
WORKLOADS = {'ud': 'ud/libud.c', 'edn': 'edn/libedn.c',
             'nettle-sha256': 'nettle-sha256/nettle-sha256.c'}
POOL_SIZE = campaign.POOL_SIZE
extract_pool = partition.extract_pool
pool_for_audit = partition.pool_for_audit
observer_sources = partition.observer_sources


@contextmanager
def partition_context():
    """Scoped constants for reused, serial frozen discovery/memory helpers."""
    previous = partition.PARTITION
    partition.PARTITION = PARTITION
    try:
        yield
    finally:
        partition.PARTITION = previous


def memory_symbols(image):
    with partition_context():
        return partition.memory_symbols(image)


def memory_image(binary):
    with partition_context():
        return partition.memory_image(binary)


def validate_memory(raw, *, trapped=False):
    with partition_context():
        return partition.validate_memory(raw, trapped=trapped)


def monitor_source():
    original = (c.ROOT / 'hardware/stack_monitor.hpp').read_text()
    old = 'return floor==4352 && writable_start<=program_end && program_end<=4224;'
    c.require(original.count(old) == 1, 'Pinned stack monitor configuration changed')
    return original.replace(old, 'return floor==6528 && writable_start<=program_end && program_end<=6400;')


def prepare(reference, output, workload, pool_size=POOL_SIZE):
    c.require(workload in WORKLOADS and type(pool_size) is int and pool_size == POOL_SIZE,
              'Bounded campaign requires registered workload and six-candidate pool')
    previous = campaign.WORKLOADS
    campaign.WORKLOADS = WORKLOADS
    try:
        plan = campaign.prepare(reference, output, workload, pool_size)
    finally:
        campaign.WORKLOADS = previous
    plan.pop('context_id')
    output = Path(output)
    inputs = output / 'inputs'
    link = inputs / 'soc_link.ld'
    old = 'ASSERT(_program_end <= 4224, "firmware must leave the declared guard and 3840-byte stack")'
    text = link.read_text()
    c.require(text.count(old) == 1, 'Unexpected campaign linker contract')
    link.write_text(text.replace(old, 'ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")'))
    (inputs / 'stack_monitor.hpp').write_text(monitor_source())
    plan['memory_partition'] = dict(PARTITION)
    plan['configuration']['stack_bytes'] = PARTITION['stack_bytes']
    plan['build_variant']['required_entrypoint'] = SOURCE
    plan['partition_amendment'] = 'Prelabel fallback after 4224-byte qualification failures; unchanged 8 KiB hardware, explicit 6400-byte program limit, 128-byte guard, 1664-byte observed stack.'
    plan['monitor_derivation'] = 'Exact replacement of the frozen monitor configuration predicate only; observation logic unchanged.'
    plan['source_bindings'][SOURCE] = c.sha(c.ROOT / SOURCE)
    target = output / 'sources' / SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(c.ROOT / SOURCE, target)
    plan['inputs'] = {p.name: c.sha(p) for p in inputs.iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    return plan


def check_plan(plan):
    c.require(plan.get('memory_partition') == PARTITION and
              plan['compiler_flags'] == list(compact.FLAGS), 'Different memory/compiler protocol')
    c.require(plan['workload'] in WORKLOADS and plan['pool_size'] == POOL_SIZE and
              plan.get('build_variant', {}).get('required_entrypoint') == SOURCE,
              'Not a six-candidate bounded campaign context')


class Evaluator(partition.Evaluator):
    def __init__(self, root):
        w.Evaluator.__init__(self, root)
        check_plan(self.plan)
        c.require((self.inputs / 'stack_monitor.hpp').read_text() == monitor_source(),
                  'Bounded stack monitor differs from pinned derivation')

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
        c.write(folder / 'validation.json', dict(isa=isa, program_and_bss_end=end,
                writable_start=start, stack_floor=PARTITION['stack_floor'],
                guard_bytes=PARTITION['stack_floor'] - end))
        return image

    def simulate(self, folder, image, datapath, custom, *, expected=0):
        folder.mkdir(parents=True, exist_ok=True)
        core, top, synthesis_top = observer_sources(self.inputs, folder, image)
        self.runner.run([self.tools['verilator'], '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal',
                         '--top-module', 'soc_top', '--Mdir', folder / 'obj_dir', f'-GEXTENSION_MASK={int(custom)}',
                         core, self.inputs / 'pcpi_single.v', datapath, top, self.inputs / 'checked_sim.cpp'], folder / 'build.log')
        end, start = memory_symbols(image)
        raw = json.loads(self.runner.run([folder / 'obj_dir/Vsoc_top', image.parent / 'firmware.bin',
                         str(end), str(start), str(PARTITION['stack_floor'])], folder / 'simulation.json', expected=expected))
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
        for name, code, kind in [('stack-underflow', 'li sp,6524', 'stack-pointer'),
                                 ('guard-write', 'li t0,6400\nsw zero,0(t0)', 'ram-write')]:
            folder = base / name
            folder.mkdir()
            source = folder / 'fixture.S'
            source.write_text('.section .text.start\n.global _start\n_start:\nli sp,8192\n' + code + '\nebreak\n')
            image = self.compile_program(folder / 'firmware', source, fixture=True)
            datapath = folder / 'candidate.v'
            datapath.write_text(c.generate_rtl('add(in0,in1)'))
            raw, _ = self.simulate(folder / 'guard-simulation', image, datapath, False, expected=10)
            c.require(raw['stack_initialized'] and raw['stack_violations'] > 0 and
                      raw['first_violation']['kind'] == kind, 'Guard control did not detect expected violation')
            results.append(dict(name=name, detected_kind=kind, raw=raw))
        record = dict(controls=results, artifacts=w.artifact_hashes(base))
        c.seal(base / 'controls.json', record)
        return record

    def discover(self):
        with partition_context():
            return super().discover()

    def collect(self):
        result = w.Evaluator.collect(self)
        result['memory_partition'] = dict(PARTITION)
        result['pool_rule'] = partition.POOL_RULE
        result['limitations'] = [item for item in result['limitations'] if not item.startswith('Top-merit')]
        result['limitations'] += ['Rank-stratified six-candidate subset; oracle covers only this subset.',
                'Explicit -Os compiler, 6400-byte program limit and 1664-byte observed stack differ from historical contexts.',
                'Memory safety is observed only for the recorded fixed input; no universal stack bound.']
        c.seal(self.root / 'report.json', result)
        return result


def audit(root):
    root = Path(root).resolve()
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    c.require((root / 'inputs/stack_monitor.hpp').read_text() == monitor_source(), 'Monitor derivation differs')
    with pool_for_audit(c.read(root / 'inputs/latency-calibration.json')):
        checked = partition.old_audit.audit(root)
    guards = w.verify_cache(root / 'guard-controls', 'controls.json')
    c.require([(r['name'], r['detected_kind']) for r in guards['controls']] ==
              [('stack-underflow', 'stack-pointer'), ('guard-write', 'ram-write')], 'Guard controls missing')
    for row in guards['controls']:
        raw = c.read(root / 'guard-controls' / row['name'] / 'guard-simulation/simulation.json')
        c.require(raw == row['raw'] and raw['stack_initialized'] is True and raw['stack_violations'] > 0 and
                  raw['first_violation']['kind'] == row['detected_kind'], 'Guard raw evidence differs')
    memory = {}
    for receipt in c.unseal(root / 'commands.json'):
        if receipt['argv'][0] == plan['tools']['gcc']['path']:
            c.require(receipt['argv'][1:1+len(compact.FLAGS)] == list(compact.FLAGS), 'Compiler flags differ')
        if receipt['log'].endswith('/simulation.json') and 'unobserved-control' not in receipt['log']:
            raw = c.read(root / receipt['log'])
            if receipt['expected_returncode'] == 10:
                c.require(raw['stack_violations'] > 0 and raw['stack_initialized'], 'Guard control missing violation')
            else:
                memory[receipt['log']] = validate_memory(raw, trapped=receipt['expected_returncode'] == 6)
            c.require(len(receipt['argv']) == 5 and receipt['argv'][-1] == str(PARTITION['stack_floor']), 'Observer invocation differs')
            binary = partition.portable_binary(root, receipt['argv'][1])
            end, start = memory_symbols(binary.with_suffix('.hex'))
            c.require(receipt['argv'][-3:-1] == [str(end), str(start)], 'Observer bounds differ from symbols')
            c.require(binary.with_suffix('.hex').read_text() == memory_image(binary.read_bytes()), 'RAM image differs')
    baseline = c.unseal(root / 'measurements/baseline/measurement.json')
    folder = root / 'measurements/baseline'
    plain = [folder / p for p in baseline['artifacts'] if p.endswith('/unobserved-control/simulation.json')]
    c.require(len(plain) == 1 and w.validate_execution(c.read(plain[0])) == baseline['performance'], 'Unobserved baseline control missing')
    checked.update(memory_partition=dict(PARTITION), memory_checks=memory, guard_negative_controls=2)
    return checked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'collect', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=WORKLOADS, default='ud')
    parser.add_argument('--pool-size', type=int, default=POOL_SIZE)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        print(prepare(args.reference_root, args.root, args.workload, args.pool_size)['context_id'])
    elif args.command == 'audit':
        print(json.dumps(audit(args.root), indent=2))
    else:
        evaluator = Evaluator(args.root)
        try:
            result = evaluator.measure('baseline') if args.command == 'baseline' else getattr(evaluator, args.command)()
            print(json.dumps(dict(workload=evaluator.plan['workload'], command=args.command, context_id=result['context_id'])))
        finally:
            evaluator.runner.lock.close()


if __name__ == '__main__':
    main()

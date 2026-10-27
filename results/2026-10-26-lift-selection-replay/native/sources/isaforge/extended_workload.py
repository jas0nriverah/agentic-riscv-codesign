"""Longer fixed-input runs on a checked 6656/6784 partition of 8 KiB RAM.

The simulation-driver ceilings extend from 200 to 800 million cycles. The
monitor's declared partition changes; its observation logic stays fixed.
Command deadlines, build workers, processor, RAM and candidate pool stay fixed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from . import bounded_workload as bounded, codesign as c, workload_experiment as w

SOURCE = 'isaforge/extended_workload.py'
PARTITION = dict(ram_bytes=8192, program_limit=6656, stack_floor=6784,
                 stack_bytes=1408, minimum_guard_bytes=128)
WORKLOADS = {'edn': 'edn/libedn.c', 'statemate': 'statemate/libstatemate.c'}
POOL_SIZE = bounded.POOL_SIZE
CYCLE_LIMIT = 800000000
DRIVERS = ('checked_sim.cpp', 'soc_sim.cpp')
extract_pool = bounded.extract_pool
pool_for_audit = bounded.pool_for_audit
observer_sources = bounded.observer_sources


@contextmanager
def registration(*, entrypoint=False):
    previous, source = bounded.WORKLOADS, bounded.SOURCE
    previous_partition, previous_monitor = bounded.PARTITION, bounded.monitor_source
    bounded.WORKLOADS = WORKLOADS
    if entrypoint:
        bounded.SOURCE = SOURCE
        bounded.PARTITION = PARTITION
        bounded.monitor_source = monitor_source
    try:
        yield
    finally:
        bounded.WORKLOADS, bounded.SOURCE = previous, source
        bounded.PARTITION, bounded.monitor_source = previous_partition, previous_monitor


def memory_symbols(image):
    with registration(entrypoint=True):
        return bounded.memory_symbols(image)


def memory_image(binary):
    with registration(entrypoint=True):
        return bounded.memory_image(binary)


def validate_memory(raw, *, trapped=False):
    with registration(entrypoint=True):
        return bounded.validate_memory(raw, trapped=trapped)


def monitor_source():
    original = (c.ROOT / 'hardware/stack_monitor.hpp').read_text()
    old = 'return floor==4352 && writable_start<=program_end && program_end<=4224;'
    c.require(original.count(old) == 1, 'Pinned stack monitor configuration changed')
    return original.replace(old, 'return floor==6784 && writable_start<=program_end && program_end<=6656;')


def driver_source(name):
    c.require(name in DRIVERS, 'Unknown simulation driver')
    original = (c.ROOT / 'hardware' / name).read_text()
    old = 'cycle<200000000'
    c.require(original.count(old) == 1, 'Pinned simulation cycle ceiling changed')
    return original.replace(old, 'cycle<800000000')


def validate_runtime_inputs(root):
    inputs = Path(root) / 'inputs'
    c.require((inputs / 'stack_monitor.hpp').read_text() == monitor_source(), 'Monitor derivation differs')
    for name in DRIVERS:
        c.require((inputs / name).read_text() == driver_source(name), 'Extended simulation driver differs: ' + name)


def check_plan(plan):
    with registration(entrypoint=True):
        bounded.check_plan(plan)
    c.require(plan.get('simulation_cycle_limit') == CYCLE_LIMIT, 'Different simulation cycle limit')


def prepare(reference, output, workload, pool_size=POOL_SIZE):
    c.require(workload in WORKLOADS and type(pool_size) is int and pool_size == POOL_SIZE,
              'Extended campaign requires EDN/statemate and six-candidate pool')
    with registration():
        plan = bounded.prepare(reference, output, workload, pool_size)
    plan.pop('context_id')
    output = Path(output)
    link = output / 'inputs/soc_link.ld'
    old_assert = 'ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")'
    text = link.read_text()
    c.require(text.count(old_assert) == 1, 'Unexpected bounded linker contract')
    link.write_text(text.replace(old_assert, 'ASSERT(_program_end <= 6656, "firmware must leave the declared guard and 1408-byte stack")'))
    (output / 'inputs/stack_monitor.hpp').write_text(monitor_source())
    for name in DRIVERS:
        (output / 'inputs' / name).write_text(driver_source(name))
    plan['memory_partition'] = dict(PARTITION)
    plan['configuration']['stack_bytes'] = PARTITION['stack_bytes']
    plan['partition_amendment'] = 'Prelabel qualification using link-map evidence: statemate program/data/BSS end 6420 exceeds the earlier 6400 guard by 20 bytes; EDN observed stack use 1040 bytes at the earlier simulator ceiling. Shared 6656 program limit, 128-byte guard, 1408-byte stack; unchanged 8 KiB hardware. Full-run stack fit still requires observation.'
    plan['simulation_cycle_limit'] = CYCLE_LIMIT
    plan['simulation_limit_amendment'] = 'Prelabel extension after EDN reached the 200-million-cycle simulator ceiling with no observed guard violation; both observed and unobserved drivers now allow 800 million cycles. Native deadlines and workers unchanged.'
    plan['driver_derivation'] = 'Exact cycle<200000000 to cycle<800000000 replacement only in both frozen hardware simulation drivers.'
    plan['build_variant']['required_entrypoint'] = SOURCE
    plan['source_bindings'][SOURCE] = c.sha(c.ROOT / SOURCE)
    target = output / 'sources' / SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(c.ROOT / SOURCE, target)
    plan['inputs'] = {p.name:c.sha(p) for p in (output / 'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_runtime_inputs(output)
    return plan


class Evaluator(bounded.Evaluator):
    def __init__(self, root):
        with registration(entrypoint=True):
            super().__init__(root)
        check_plan(self.plan)
        validate_runtime_inputs(self.root)

    def compile_program(self, *args, **kwargs):
        with registration(entrypoint=True):
            return super().compile_program(*args, **kwargs)

    def simulate(self, *args, **kwargs):
        with registration(entrypoint=True):
            return super().simulate(*args, **kwargs)

    def discover(self):
        with registration(entrypoint=True):
            return super().discover()

    def guard_controls(self):
        self.runner.check()
        base = self.root / 'guard-controls'
        if (base / 'controls.json').exists():
            return w.verify_cache(base, 'controls.json')
        base.mkdir(exist_ok=True)
        results = []
        for name, code, kind, address in [('stack-underflow','li sp,6780','stack-pointer',6780),
                ('guard-write','li t0,6656\nsw zero,0(t0)','ram-write',6656)]:
            folder = base / name
            folder.mkdir()
            source = folder / 'fixture.S'
            source.write_text('.section .text.start\n.global _start\n_start:\nli sp,8192\n' + code + '\nebreak\n')
            image = self.compile_program(folder / 'firmware',source,fixture=True)
            datapath = folder / 'candidate.v'
            datapath.write_text(c.generate_rtl('add(in0,in1)'))
            raw,_ = self.simulate(folder / 'guard-simulation',image,datapath,False,expected=10)
            c.require(raw['stack_initialized'] and raw['stack_violations']>0 and
                      raw['first_violation']['kind']==kind and raw['first_violation']['address']==address,
                      'Guard control did not detect expected violation')
            results.append(dict(name=name,detected_kind=kind,raw=raw))
        record = dict(controls=results,artifacts=w.artifact_hashes(base))
        c.seal(base / 'controls.json',record)
        return record

    def collect(self):
        with registration(entrypoint=True):
            result = super().collect()
        result['simulation_cycle_limit'] = CYCLE_LIMIT
        result['limitations'] = [item.replace('6400-byte program limit and 1664-byte observed stack',
                '6656-byte program limit and 1408-byte observed stack') for item in result['limitations']]
        c.seal(self.root / 'report.json',result)
        return result


def audit(root):
    check_plan(c.unseal(Path(root) / 'plan.json'))
    validate_runtime_inputs(root)
    with registration(entrypoint=True):
        result = bounded.audit(root)
    result['simulation_cycle_limit'] = CYCLE_LIMIT
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','discover','baseline','collect','audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=WORKLOADS, default='edn')
    parser.add_argument('--pool-size', type=int, default=POOL_SIZE)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        print(prepare(args.reference_root,args.root,args.workload,args.pool_size)['context_id'])
    elif args.command == 'audit':
        print(json.dumps(audit(args.root),indent=2))
    else:
        evaluator = Evaluator(args.root)
        try:
            result = evaluator.measure('baseline') if args.command=='baseline' else getattr(evaluator,args.command)()
            print(json.dumps(dict(workload=evaluator.plan['workload'],command=args.command,context_id=result['context_id'])))
        finally:
            evaluator.runner.lock.close()


if __name__ == '__main__':
    main()

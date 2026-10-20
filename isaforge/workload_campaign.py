"""Label-free qualification of additional integer workloads on checked 8 KiB RAM.

The frozen SLRE evaluator supplies extraction, lowering, processor controls,
stack observation and measurement. Only fresh plans/inputs are prepared here;
the upstream benchmark sources and all historical evidence stay unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from . import codesign as c
from . import compact_workload as compact
from . import partitioned_workload as partition
from . import workload_experiment as w

SOURCE = 'isaforge/workload_campaign.py'
# Qualification order is fixed before any new candidate outcome is collected.
WORKLOADS = {'ud': 'ud/libud.c', 'nettle-sha256': 'nettle-sha256/nettle-sha256.c',
             'statemate': 'statemate/libstatemate.c'}
POOL_SIZE = 6
EXIT_SUPPORT = '''
// Freestanding assertion failure: terminate the SoC with a failing status.
__attribute__((noreturn)) void exit(int status) {
    (void)status;
    *(volatile unsigned int *)0x10000004 = 0xdead0005;
    for (;;) { }
}
'''
SHA256_CHECK = '''
    // FIPS SHA-256 fixed-message digest, checked in full outside the timed window.
    // Upstream verify_benchmark checks only its first eight bytes.
    extern unsigned char buffer[32];
    static const unsigned char expected_sha256[32] = {
        0x24,0x8d,0x6a,0x61,0xd2,0x06,0x38,0xb8,
        0xe5,0xc0,0x26,0x93,0x0c,0x3e,0x60,0x39,
        0xa3,0x3c,0xe4,0x59,0x64,0xff,0x21,0x67,
        0xf6,0xec,0xed,0xd4,0x19,0xdb,0x06,0xc1
    };
    for (unsigned int byte=0; byte<sizeof(expected_sha256); ++byte)
        if (buffer[byte] != expected_sha256[byte]) correct=0;
'''


@contextmanager
def registration():
    """Scope registration; never change the historical workload registry."""
    previous = dict(w.WORKLOADS)
    c.require(all(name not in previous or previous[name] == source for name, source in WORKLOADS.items()),
              'Conflicting workload registration')
    w.WORKLOADS.update(WORKLOADS)
    try:
        yield
    finally:
        w.WORKLOADS.clear()
        w.WORKLOADS.update(previous)


def prepare(reference, output, workload, pool_size=POOL_SIZE):
    c.require(workload in WORKLOADS and type(pool_size) is int and pool_size == POOL_SIZE,
              'Campaign requires a registered workload and six-candidate pool')
    from scripts.analyze_speedup_model import authenticated_calibration
    calibration_root = c.ROOT / 'results/2026-10-20-latency-calibration'
    calibration, _ = authenticated_calibration(calibration_root)
    output = Path(output)
    with registration():
        plan = compact.prepare(reference, output, workload, pool_size)
    plan.pop('context_id')
    inputs = output / 'inputs'
    link = inputs / 'soc_link.ld'
    text = link.read_text()
    old_assert = 'ASSERT(_program_end <= 4096, "firmware must leave at least 4 KiB for the stack")'
    c.require(text.count(old_assert) == text.count('.data : {') == 1, 'Unexpected linker contract')
    text = text.replace('.data : {', '.data : { _writable_start = .;')
    text = text.replace(old_assert, 'ASSERT(_program_end <= 4224, "firmware must leave the declared guard and 3840-byte stack")')
    link.write_text(text)
    memory = inputs / 'embench_memory.c'
    memory.write_text(memory.read_text() + EXIT_SUPPORT)
    if workload == 'nettle-sha256':
        harness = inputs / 'embench_firmware.c'
        original = harness.read_text()
        marker = '    int correct=verify_benchmark(result);'
        c.require(original.count(marker) == 1, 'Unexpected benchmark harness')
        harness.write_text(original.replace(marker, marker + SHA256_CHECK))
    for name in ('checked_sim.cpp', 'stack_monitor.hpp'):
        shutil.copyfile(c.ROOT / 'hardware' / name, inputs / name)
    c.write(inputs / 'latency-calibration.json', calibration)
    for name in ('picorv32.v', 'soc_top.v', 'pcpi_single.v'):
        c.require(c.sha(inputs / name) == c.sha(calibration_root / 'inputs' / name),
                  'Calibration hardware differs: ' + name)
    extras = (SOURCE, partition.SOURCE, 'hardware/checked_sim.cpp',
              'hardware/stack_monitor.hpp', 'isaforge/latency_features.py', 'isaforge/workload_audit.py')
    for name in extras:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        target = output / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    plan.update(memory_partition=dict(partition.PARTITION), pool_rule=partition.POOL_RULE,
                qualification_order=list(WORKLOADS),
                qualification_rule='Unmodified benchmark; successful checked baseline and at least six calibrated executable formulas; no candidate outcomes used.',
                runtime_support='Existing freestanding byte-memory routines plus fail-closed assertion exit; upstream source unchanged.',
                output_check=('Upstream self-check plus independent full 32-byte fixed-message SHA-256 digest in the recorded harness.'
                              if workload == 'nettle-sha256' else 'Unmodified upstream self-check.'),
                guard_controls=['SP below stack floor must fail with exit10', 'RAM write in guard must fail with exit10'],
                calibration_compatibility=dict(context_id=calibration['context_id'],
                    report_sha256=c.sha(calibration_root / 'report.json'),
                    scope='Identical core, synchronous 8 KiB RAM and one-wait PCPI; explicit -Os and checked partition. Analytic transfer is tested by measured labels.'))
    plan['configuration']['stack_bytes'] = partition.PARTITION['stack_bytes']
    plan['build_variant']['required_entrypoint'] = SOURCE
    plan['inputs'] = {p.name: c.sha(p) for p in inputs.iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    return plan


class Evaluator(partition.Evaluator):
    def __init__(self, root):
        # The inherited evaluator is workload-independent; avoid SLRE's entrypoint
        # constructor so that the campaign's own sealed plan is checked here.
        w.Evaluator.__init__(self, root)
        c.require(self.plan.get('memory_partition') == partition.PARTITION and
                  self.plan['compiler_flags'] == list(compact.FLAGS), 'Different memory/compiler protocol')
        c.require(self.plan['workload'] in WORKLOADS and self.plan['pool_size'] == POOL_SIZE and
                  self.plan.get('build_variant', {}).get('required_entrypoint') == SOURCE,
                  'Not a six-candidate campaign context')


def audit(root):
    plan = c.unseal(Path(root) / 'plan.json')
    c.require(plan.get('build_variant', {}).get('required_entrypoint') == SOURCE and
              plan['workload'] in WORKLOADS and plan['pool_size'] == POOL_SIZE, 'Not a campaign context')
    return partition.audit(root)


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
            print(json.dumps({'workload': evaluator.plan['workload'], 'command': args.command,
                              'context_id': result['context_id']}))
        finally:
            evaluator.runner.lock.close()


if __name__ == '__main__':
    main()

"""Explicit strlen ABI extension for the unchanged pinned Levenshtein source.

The failed original context is preserved. This new context appends a standard
freestanding strlen only to the external firmware translation unit; benchmark
arithmetic, inputs, verifier, processor, partition and pool size stay unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import time

from . import blind_workload as bw, codesign as c

SOURCE = 'isaforge/string_workload.py'
ORIGINAL_BLIND_SOURCE = bw.SOURCE
ORIGINAL_HARNESS = bw.harness_source
GUARDED_SOURCE = bw.GUARDED_SOURCE
UPSTREAM_COMMIT = bw.UPSTREAM_COMMIT
LICENSE = bw.LICENSE
WORKLOAD = 'levenshtein'
PROGRAM = bw.program(WORKLOAD)
PROGRAM_SHA256 = bw.WORKLOADS[WORKLOAD][1]
POOL_SIZE = bw.POOL_SIZE
PARTITION = dict(bw.PARTITION)
STRLEN_ABI = '''
/* Explicit freestanding standard strlen ABI support; outside benchmark source. */
#include <stddef.h>
size_t strlen(const char *text) {
    const char *end = text;
    while (*end) ++end;
    return (size_t)(end - text);
}
'''
HELPER_SHA256 = hashlib.sha256(STRLEN_ABI.encode()).hexdigest()


def harness_source(workload):
    c.require(workload == WORKLOAD, 'Only original Levenshtein is supported by the strlen extension')
    return ORIGINAL_HARNESS(workload) + STRLEN_ABI


@contextmanager
def registration():
    previous = bw.SOURCE, bw.harness_source
    bw.SOURCE, bw.harness_source = SOURCE, harness_source
    try:
        yield
    finally:
        bw.SOURCE, bw.harness_source = previous


def abi_extension():
    return dict(schema='isaforge-freestanding-strlen-v1', helper_sha256=HELPER_SHA256,
                original_blind_source=ORIGINAL_BLIND_SOURCE,
                original_blind_sha256=c.sha(c.ROOT / ORIGINAL_BLIND_SOURCE),
                harness_sha256=hashlib.sha256(harness_source(WORKLOAD).encode()).hexdigest(),
                benchmark_source_unchanged=True)


def check_plan(plan):
    c.require(isinstance(plan, dict) and plan.get('workload') == WORKLOAD,
              'Original Levenshtein workload required')
    with registration():
        bw.check_plan(plan)
    c.require(plan.get('abi_extension') == abi_extension() and
              plan['inputs'].get('embench_firmware.c') == abi_extension()['harness_sha256'],
              'Exact declared strlen ABI extension required')
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE):
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT / name),
                  'Original blind adapter and strlen adapter must both be bound')
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) == plan['context_id'],
              'Invalid strlen context identity')


def validate_inputs(root):
    root = Path(root)
    with registration():
        plan = bw.validate_inputs(root)
    check_plan(plan)
    c.require((root / 'inputs/embench_firmware.c').read_text() == harness_source(WORKLOAD),
              'Exact external strlen harness derivation required')
    return plan


def prepare(reference, output):
    output = Path(output)
    with registration():
        plan = bw.prepare(reference, output, WORKLOAD)
    plan.pop('context_id')
    plan['abi_extension'] = abi_extension()
    plan['runtime_support'] = 'Original full BEEBS Levenshtein source/input/verifier; generic external firmware plus original no-op warmup and explicit standard freestanding strlen.'
    plan['harness_derivation'] = 'Captured original blind_workload.harness_source(levenshtein) plus exact STRLEN_ABI from the bound string_workload module.'
    plan['context_amendment'] = 'New ABI-support context after the preserved undefined-strlen qualification rejection; no source, input, pool, partition, ISA or processor changes.'
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE):
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        target = output / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    plan['inputs'] = {path.name: c.sha(path) for path in (output / 'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


class Evaluator(bw.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            return super().discover()

    def measure(self, name):
        with registration():
            return super().measure(name)

    def collect(self):
        with registration():
            return super().collect()


def baseline_public(root):
    validate_inputs(root)
    with registration():
        rows, context, before = bw.baseline_public(root)
    context['context_transfer'] = 'Pinned original BEEBS Levenshtein in the unchanged checked 8 KiB RV32I context, with explicit external freestanding strlen ABI support.'
    return rows, context, before


def audit(root):
    validate_inputs(root)
    with registration():
        return bw.audit(root)


def pack(root, snapshot, *, prelabel_commit=None):
    validate_inputs(root)
    with registration():
        return bw.pack(root, snapshot, prelabel_commit=prelabel_commit)


def replay(snapshot, output):
    snapshot = Path(snapshot)
    manifest = c.unseal(snapshot / 'archive-manifest.json')
    with tarfile.open(snapshot / manifest['archive'], 'r:gz') as stream:
        plans = [member for member in stream.getmembers() if member.name == 'plan.json' and member.isfile()]
        c.require(len(plans) == 1 and plans[0].size <= 1024 * 1024, 'Unique bounded archived plan required')
        check_plan(json.load(stream.extractfile(plans[0])))
    with registration():
        result = bw.replay(snapshot, output)
    validate_inputs(output)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'public', 'freeze', 'measure', 'collect', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=(WORKLOAD,), default=WORKLOAD)
    parser.add_argument('--candidate')
    args = parser.parse_args(argv)
    started, status = time.monotonic(), 'interrupted'
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        if args.command == 'prepare':
            c.require(args.reference_root is not None, 'Reference required')
            result = prepare(args.reference_root, args.root)
        elif args.command == 'public':
            rows, context, before = baseline_public(args.root)
            for name, value in [('public.json', rows), ('context.json', context), ('before.json', before)]:
                c.seal(args.root / name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        elif args.command == 'audit':
            result = audit(args.root)
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    with registration(), bw.registration(evaluator.plan):
                        result = bw.g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command in ('baseline', 'measure'):
                    name = 'baseline' if args.command == 'baseline' else args.candidate
                    c.require(name is not None, 'Candidate required')
                    result = evaluator.measure(name)
                else:
                    result = getattr(evaluator, args.command)()
            finally:
                evaluator.runner.lock.close()
        status = 'success'
        print(json.dumps(result, indent=2))
    except Exception:
        status = 'failed'
        raise
    finally:
        if args.root.exists():
            folder = args.root / 'outer-timing'
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder / f'{sequence:03d}-{args.command}.json', dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command,
                candidate=args.candidate, started_at_utc=stamp, status=status,
                elapsed_seconds=time.monotonic() - started,
                scope='Complete CLI operation through lock close; recorded monotonic elapsed. Separate paired observer establishes UTC endpoints; mixed-clock ends are not inferred.'))


if __name__ == '__main__':
    main()

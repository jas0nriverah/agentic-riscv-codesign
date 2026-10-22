"""New fixed-six source protocol, preserving every earlier twelve-pool rejection."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tarfile
import time

from . import blind_workload as bw, codesign as c

SOURCE = 'isaforge/integer_workload.py'
ORIGINAL_BLIND_SOURCE = bw.SOURCE
GUARDED_SOURCE = bw.GUARDED_SOURCE
UPSTREAM_COMMIT = bw.UPSTREAM_COMMIT
LICENSE = bw.LICENSE
POOL_SIZE = 6
PARTITION = dict(bw.PARTITION)
WORKLOADS = {
    'expint': ('libexpint.c', '4dff051261026af2ac420ca3e8eb76b01855bec7784ac456896361513b8d3571'),
    'bubblesort': ('libbubblesort.c', 'd4a9c32096ebe287ac83d50c69d4ec7cab1c253c6a7e383415b7db521e1b6f9a'),
}


def program(workload):
    c.require(workload in WORKLOADS, 'Only the declared next integer sources are supported')
    return 'benchmarks/beebs/' + workload + '/' + WORKLOADS[workload][0]


@contextmanager
def registration():
    previous = bw.SOURCE, bw.POOL_SIZE, bw.WORKLOADS
    bw.SOURCE, bw.POOL_SIZE, bw.WORKLOADS = SOURCE, POOL_SIZE, WORKLOADS
    try:
        yield
    finally:
        bw.SOURCE, bw.POOL_SIZE, bw.WORKLOADS = previous


def check_plan(plan):
    c.require(isinstance(plan, dict) and plan.get('workload') in WORKLOADS,
              'Declared untouched integer source required')
    with registration():
        bw.check_plan(plan)
    c.require(plan.get('integer_source_protocol') == dict(
        schema='isaforge-integer-six-v1', order=list(WORKLOADS), pool_size=6,
        unchanged_input=True, unchanged_partition=True), 'Fixed-six source protocol differs')
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE):
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT / name),
                  'Both original blind runtime and fixed-six adapter must be bound')
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) == plan['context_id'],
              'Invalid fixed-six context identity')


def validate_inputs(root):
    with registration():
        plan = bw.validate_inputs(root)
    check_plan(plan)
    return plan


def prepare(reference, output, workload):
    c.require(workload in WORKLOADS, 'Declared untouched integer source required')
    output = Path(output)
    with registration():
        plan = bw.prepare(reference, output, workload)
    plan.pop('context_id')
    plan['integer_source_protocol'] = dict(schema='isaforge-integer-six-v1', order=list(WORKLOADS),
                                         pool_size=6, unchanged_input=True, unchanged_partition=True)
    plan['qualification_order'] = list(WORKLOADS)
    plan['qualification_rule'] = 'First of expint then bubblesort passing original input/verifier, checked baseline and six legal calibrated formulas; declaration precedes either discovery. No earlier rejected source is retried.'
    plan['runtime_support'] = 'Unmodified pinned BEEBS integer source, complete original inputs/verifier and original external no-op warmup ABI adapter.'
    plan['context_amendment'] = 'New six-candidate source protocol after preserved twelve-pool Levenshtein rejections; unchanged 6400/6528 partition, RV32I/ILP32 -Os and original processor.'
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE):
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


class Evaluator(bw.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration(): super().__init__(root)

    def discover(self):
        with registration(): return super().discover()

    def measure(self, name):
        with registration(): return super().measure(name)

    def collect(self):
        with registration(): return super().collect()


def baseline_public(root):
    validate_inputs(root)
    with registration():
        rows, context, before = bw.baseline_public(root)
    context['context_transfer'] = 'New original-input BEEBS integer source, predeclared six-candidate pool and unchanged checked 8 KiB RV32I context.'
    return rows, context, before


def audit(root):
    validate_inputs(root)
    with registration(): return bw.audit(root)


def pack(root, snapshot, *, prelabel_commit=None):
    validate_inputs(root)
    with registration(): return bw.pack(root, snapshot, prelabel_commit=prelabel_commit)


def replay(snapshot, output):
    snapshot = Path(snapshot)
    manifest = c.unseal(snapshot / 'archive-manifest.json')
    with tarfile.open(snapshot / manifest['archive'], 'r:gz') as stream:
        plans = [member for member in stream.getmembers() if member.name == 'plan.json' and member.isfile()]
        c.require(len(plans) == 1 and plans[0].size <= 1024 * 1024, 'Unique bounded archived plan required')
        check_plan(json.load(stream.extractfile(plans[0])))
    with registration(): result = bw.replay(snapshot, output)
    validate_inputs(output)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'public', 'freeze', 'measure', 'collect', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=WORKLOADS)
    parser.add_argument('--candidate')
    args = parser.parse_args(argv)
    started, status = time.monotonic(), 'interrupted'
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        if args.command == 'prepare':
            c.require(args.reference_root is not None and args.workload is not None, 'Reference/workload required')
            result = prepare(args.reference_root, args.root, args.workload)
        elif args.command == 'public':
            rows, context, before = baseline_public(args.root)
            for name, value in [('public.json', rows), ('context.json', context), ('before.json', before)]:
                c.seal(args.root / name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        elif args.command == 'audit': result = audit(args.root)
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
                else: result = getattr(evaluator, args.command)()
            finally: evaluator.runner.lock.close()
        status = 'success'
        print(json.dumps(result, indent=2))
    except Exception:
        status = 'failed'
        raise
    finally:
        if args.root.exists():
            folder = args.root / 'outer-timing'; folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder / f'{sequence:03d}-{args.command}.json', dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command, candidate=args.candidate,
                started_at_utc=stamp, status=status, elapsed_seconds=time.monotonic() - started,
                scope='Complete CLI operation through lock close; recorded monotonic elapsed. Independent paired observer records UTC endpoints; mixed-clock ends are not inferred.'))


if __name__ == '__main__': main()

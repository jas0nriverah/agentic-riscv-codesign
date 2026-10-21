"""Pinned BEEBS integer DCT on the existing guarded 8 KiB RV32I evaluator.

The upstream program/input/verifier are byte-identical. Only a no-op harness
warmup supplies the missing Embench ABI function. No source is called Embench.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from . import codesign as c, guarded_workload as g, campaign_evidence as evidence

SOURCE = 'isaforge/beebs_workload.py'
GUARDED_SOURCE = g.SOURCE
PROGRAM = 'benchmarks/beebs/jfdctint/libjfdctint.c'
LICENSE = 'benchmarks/beebs/COPYING'
UPSTREAM_COMMIT = '049ded9f3aeb5591f553879d3a0376b8614e9422'
PROGRAM_SHA256 = '2fb8b63b4e0da2012da6d63617e99b4f7ef263899ad01f0426d1277466a79c5e'
WORKLOAD = 'jfdctint'
GROUP = 'beebs-jfdctint'
PARTITION = g.q.partition_spec(3072, 3200)
WARMUP = '\n/* BEEBS ABI adapter only: upstream has no warmup entrypoint. */\nvoid warm_caches(int heat) { (void)heat; }\n'
PUBLIC = evidence._public


def public_projection(root, plan, discovery, baseline, calibration):
    rows = PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-jfdctint:' + plan['context_id'], 'Different BEEBS projection')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


@contextmanager
def registration():
    previous = g.SOURCE, g.WORKLOADS, evidence._public
    g.SOURCE = SOURCE
    # The reused generic preparer resolves sources under benchmarks/embench/src.
    # The final plan canonicalizes this path before any native command executes.
    g.WORKLOADS = {WORKLOAD: '../../beebs/jfdctint/libjfdctint.c'}
    evidence._public = public_projection
    try:
        yield
    finally:
        g.SOURCE, g.WORKLOADS, evidence._public = previous


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan['workload'] == WORKLOAD and plan['memory_partition'] == PARTITION and
              plan.get('upstream') == dict(suite='BEEBS', commit=UPSTREAM_COMMIT, source=PROGRAM,
                                           source_sha256=PROGRAM_SHA256) and
              all(name in plan['source_bindings'] for name in (GUARDED_SOURCE, PROGRAM, LICENSE)),
              'Different pinned BEEBS protocol')
    c.require(plan['inputs']['program.c'] == PROGRAM_SHA256 and c.sha(c.ROOT/PROGRAM) == PROGRAM_SHA256,
              'Upstream BEEBS source differs')


def prepare(reference, output):
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, 6, program_limit=3072, stack_floor=3200)
    output = Path(output)
    plan.pop('context_id')
    harness = output/'inputs/embench_firmware.c'
    c.require(harness.read_text() == (c.ROOT/'hardware/embench_firmware.c').read_text(), 'Generic harness differs')
    harness.write_text(harness.read_text() + WARMUP)
    plan['source_bindings'] = {str((c.ROOT/name).resolve().relative_to(c.ROOT)): digest
                               for name, digest in plan['source_bindings'].items()}
    plan['upstream'] = dict(suite='BEEBS', commit=UPSTREAM_COMMIT, source=PROGRAM, source_sha256=PROGRAM_SHA256)
    plan['workload_group'] = GROUP
    plan['runtime_support'] = 'Original full BEEBS source and all 64 coefficient checks; generic harness plus declared no-op warm_caches ABI adapter.'
    plan['output_check'] = 'Unchanged upstream verifier checks every one of 64 integer DCT coefficients.'
    plan['harness_derivation'] = 'Exact original hardware/embench_firmware.c plus WARMUP constant from bound BEEBS wrapper; no benchmark/input arithmetic edits.'
    plan['selection_evidence_scope'] = 'New whole-processor source group BEEBS jfdctint; distinct from Embench sources.'
    plan['outer_timer_scope'] = 'CLI wall clock includes evaluator creation, cached discovery authentication, guarded native work and lock close; separate from overlapping attempt/native timers.'
    for name in (SOURCE, GUARDED_SOURCE, PROGRAM, LICENSE):
        plan['source_bindings'][name] = c.sha(c.ROOT/name)
        target = output/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT/name, target)
    plan['inputs'] = {path.name: c.sha(path) for path in (output/'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output/'plan.json', plan)
    check_plan(plan)
    return plan


class Evaluator(g.Evaluator):
    def __init__(self, root):
        check_plan(c.unseal(Path(root)/'plan.json'))
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            return super().discover()

    def measure(self, name):
        with registration():
            return super().measure(name)


def baseline_public(root):
    check_plan(c.unseal(Path(root)/'plan.json'))
    with registration():
        rows, context, before = g.baseline_public(root)
    context['workload_group'] = GROUP
    context['context_transfer'] = 'Pinned BEEBS source, full original seed/input, no-op warmup ABI adapter, checked 8 KiB RV32I context.'
    before['workload'] = GROUP
    return rows, context, before


def audit(root):
    from . import guarded_evidence
    check_plan(c.unseal(Path(root)/'plan.json'))
    with registration():
        return guarded_evidence.audit(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'public', 'freeze', 'measure', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--candidate')
    args = parser.parse_args(argv)
    started = time.monotonic()
    stamp = datetime.now(timezone.utc).isoformat()
    status = 'interrupted'
    try:
        if args.command == 'prepare':
            c.require(args.reference_root is not None, 'Reference required')
            result = prepare(args.reference_root, args.root)
        elif args.command == 'public':
            rows, context, before = baseline_public(args.root)
            for name, value in [('public.json', rows), ('context.json', context), ('before.json', before)]:
                c.seal(args.root/name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        elif args.command == 'audit':
            result = audit(args.root)
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    with registration():
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command == 'baseline':
                    result = evaluator.measure('baseline')
                elif args.command == 'measure':
                    c.require(args.candidate is not None, 'Candidate required')
                    result = evaluator.measure(args.candidate)
                else:
                    result = evaluator.discover()
            finally:
                evaluator.runner.lock.close()
        status = 'success'
        print(json.dumps(result, indent=2))
    except Exception:
        status = 'failed'
        raise
    finally:
        if args.root.exists():
            folder = args.root/'outer-timing'
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder/f'{sequence:03d}-{args.command}.json', dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command,
                candidate=args.candidate, started_at_utc=stamp, status=status,
                elapsed_seconds=time.monotonic()-started,
                scope='Complete CLI operation through lock close and JSON formatting; excludes final timing record write. Overlaps inner ledger/native scopes.'))


if __name__ == '__main__':
    main()

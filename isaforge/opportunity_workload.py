"""Original-input BEEBS sources with a fixed useful-opportunity gate.

Reuse the guarded extractor, lowering, memory checks and measured PCPI pipeline.
Only source registration and a baseline-only acceptance gate are added. Earlier
fixed-six/twelve contexts and rejected qualifications remain unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time

from . import blind_workload as bw, budgeted_selection as b, codesign as c

SOURCE = 'isaforge/opportunity_workload.py'
ORIGINAL_BLIND_SOURCE = bw.SOURCE
GUARDED_SOURCE = bw.GUARDED_SOURCE
UPSTREAM_COMMIT = bw.UPSTREAM_COMMIT
LICENSE = bw.LICENSE
POOL_SIZE = 12
PARTITION = dict(bw.PARTITION)
GATE_SOURCES = tuple(dict.fromkeys((*b.SOURCES, 'isaforge/latency_features.py')))
WORKLOADS = {
    'cnt': ('cnt.c', '0c6b201ccb8f25a7ee7741206422c237580e053d9e7cc71a989753413887fe04'),
    'bubblesort': ('libbubblesort.c', 'd4a9c32096ebe287ac83d50c69d4ec7cab1c253c6a7e383415b7db521e1b6f9a'),
    'prime': ('libprime.c', '2515479b9d94630e01aa294a5e1870a0fcb68020b34da93f1240616babf49735'),
    'insertsort': ('libinsertsort.c', 'd25e603246fd509ae4dc972770e98fed8d20d386979870596af8cfc9b1ae0d0e'),
    'tarai': ('libtarai.c', 'ff5dcf69f4adca26a61c14f1f725c2523d9c12deb45b77627126b169dab8d7fc'),
    'recursion': ('librecursion.c', 'bc0572c7bab5ec43c1afb645f836d8fd4f86ffb83763800f10f2cd8ea8d9d98a'),
    'janne_complex': ('libjanne_complex.c', 'dfb9adb3959064de1541f4a469ea0389558c85d1a350cc371207646554c1483c'),
    'cover': ('libcover.c', '80ac586a7aec55ae9ce1ad3266b94f530ce06c09108531544f2183da21e2f1d9'),
}
FAMILIES = {name: ('sorting' if name in ('bubblesort', 'insertsort') else name) for name in WORKLOADS}
PROTOCOL = dict(schema='isaforge-useful-opportunity-v1', order=list(WORKLOADS),
    source_families=FAMILIES, stop_after_successful_families=3, pool_size=12,
    minimum_calibrated_cycle_reduction=.005, minimum_timed_replacements=10,
    joint_gate='At least one selected formula satisfies both numeric minima.',
    unchanged_input=True, unchanged_verifier=True, unchanged_partition=True)
STATIC_REJECTIONS = {'janne_complex':
    'The kernel unconditionally returns1 and the verifier only checks that return; no meaningful kernel-output check is available in this unchanged-source protocol.'}


def program(workload):
    c.require(workload in WORKLOADS, 'Declared opportunity source required')
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
              'Declared opportunity workload required')
    with registration():
        bw.check_plan(plan)
    c.require(plan.get('opportunity_source_protocol') == PROTOCOL,
              'Fixed opportunity protocol differs')
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE, *GATE_SOURCES):
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT/name),
                  'Original runtime and opportunity adapter must be bound')
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) == plan['context_id'],
              'Invalid opportunity context identity')


def validate_inputs(root):
    with registration():
        plan = bw.validate_inputs(root)
    check_plan(plan)
    return plan


def prepare(reference, output, workload):
    c.require(workload not in STATIC_REJECTIONS, 'Source has no meaningful unchanged verifier')
    with registration():
        plan = bw.prepare(reference, output, workload)
    plan.pop('context_id')
    plan['opportunity_source_protocol'] = PROTOCOL
    plan['qualification_order'] = list(WORKLOADS)
    plan['qualification_rule'] = ('First three independent declared source families passing the original input/verifier, '
        'twelve legal calibrated formulas and a baseline-only joint0.5%-gain/ten-replacement gate; no hidden candidate outcomes.')
    plan['context_amendment'] = 'New source qualification protocol; original RV32I/ILP32-Os, PCPI, integrated8KiB and6400/6528 partition retained.'
    output = Path(output)
    for name in (SOURCE, ORIGINAL_BLIND_SOURCE, *GATE_SOURCES):
        plan['source_bindings'][name] = c.sha(c.ROOT/name)
        destination = output/'sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT/name, destination)
    plan['context_id'] = c.digest(plan)
    c.seal(output/'plan.json', plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    """One declared joint condition on public data, never target measurements."""
    public = b.public_rows(public)
    c.require(len(public) == POOL_SIZE, 'Exactly twelve public formulas required')
    passing = [row['candidate_id'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >= PROTOCOL['minimum_calibrated_cycle_reduction']
        and b.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    return dict(schema=PROTOCOL['schema']+'-gate', protocol=PROTOCOL, passed=bool(passing),
        qualifying_candidate_ids=passing, public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(row['latency_features']['estimated_cycle_reduction'] for row in public),
        maximum_timed_replacements=max(b.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def discovery_public(root):
    root = Path(root)
    plan = validate_inputs(root)
    with registration(), bw.registration(plan):
        discovery = bw.g.authenticate_discovery(root)
        calibration = bw.evidence._calibration(root)
        public = bw.public_projection(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return b.public_rows(public)


def opportunity(root):
    root = Path(root)
    c.require(not (root/'opportunity.json').exists(), 'Preserve prior opportunity gate')
    result = opportunity_gate(discovery_public(root))
    c.seal(root/'opportunity.json', result)
    c.require(result['passed'], 'Declared public useful-opportunity gate rejected this source')
    return result


def check_opportunity(root):
    root = Path(root)
    recorded = c.unseal(root/'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'], 'Accepted unchanged public opportunity gate required')
    return recorded


class Evaluator(bw.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            return super().discover()

    def measure(self, name):
        check_opportunity(self.root)
        if name != 'baseline':
            release = c.unseal(self.root/'release.json')
            c.require(release.get('opportunity_source_protocol') == PROTOCOL,
                      'Released opportunity cohort required before candidate work')
        with registration():
            return super().measure(name)


def baseline_public(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = bw.baseline_public(root)
    c.require(opportunity_gate(rows) == c.unseal(Path(root)/'opportunity.json'),
              'Baseline and discovery-only public projections differ')
    context['context_transfer'] = 'Untouched original-input BEEBS source accepted by the fixed twelve-formula useful-opportunity protocol.'
    return rows, context, before


def audit(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        return bw.audit(root)


def pack(root, snapshot, *, prelabel_commit=None):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        return bw.pack(root, snapshot, prelabel_commit=prelabel_commit)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','discover','opportunity','baseline','public','freeze','measure','audit'))
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
        elif args.command == 'opportunity':
            result = opportunity(args.root)
        elif args.command == 'public':
            rows, context, before = baseline_public(args.root)
            for name, value in [('public.json',rows),('context.json',context),('before.json',before)]:
                c.seal(args.root/name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        elif args.command == 'audit':
            result = audit(args.root)
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    check_opportunity(args.root)
                    with registration(), bw.registration(evaluator.plan):
                        result = bw.g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command in ('baseline','measure'):
                    name = 'baseline' if args.command == 'baseline' else args.candidate
                    c.require(name is not None, 'Candidate required')
                    result = evaluator.measure(name)
                else:
                    result = getattr(evaluator,args.command)()
            finally:
                evaluator.runner.lock.close()
        status = 'success'
        import json
        print(json.dumps(result,indent=2))
    except Exception:
        status = 'failed'
        raise
    finally:
        if args.root.exists():
            folder = args.root/'outer-timing'
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder/f'{sequence:03d}-{args.command}.json',dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command, candidate=args.candidate,
                started_at_utc=stamp, status=status, elapsed_seconds=time.monotonic()-started,
                scope='Complete CLI operation through lock close; separate paired observer retains actual UTC and monotonic endpoints.'))


if __name__ == '__main__':
    main()

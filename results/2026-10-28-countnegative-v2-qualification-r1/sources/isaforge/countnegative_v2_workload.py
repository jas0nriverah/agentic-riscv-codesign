"""Original countnegative with variable-pool, baseline-only admission.

Reuse the frozen source contract and the existing v2 guarded extraction and
independent discovery authenticator. No candidate labels or model work here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from . import codesign as c, guarded_workload as g, campaign_evidence as evidence
from . import nanocobs_v2_workload as variable
from . import tacle_countnegative_workload as original

SOURCE = 'isaforge/countnegative_v2_workload.py'
QUALIFIER = 'scripts/qualify_countnegative_v2.py'
TEST = 'tests/test_countnegative_v2_workload.py'
CONTRACT = 'docs/countnegative-v2-adapter-contract-2026-10-28.md'
WORKLOAD, GROUP = original.WORKLOAD, original.GROUP
PROGRAM, BASE, PROVENANCE = original.PROGRAM, original.BASE, original.PROVENANCE
PARTITION = dict(original.PARTITION)
POOL_SIZE = 30  # Computational ceiling; never an admission minimum.
NATIVE_LIMITS = dict(original.NATIVE_LIMITS)
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
ADAPTER_SHA256 = '1112f314eabf9ea6bac53040f3e924c9c24f2a1bdb619582e532e82b4aa5575a'
PROVENANCE_SHA256 = '5905d06e6b7e5c10d6091551807d7ef5e99e717cf00e0ca95e346368b026eccb'
WORKLOADS = {WORKLOAD: str(c.ROOT / PROGRAM)}
PUBLIC = original.prior.PUBLIC
PROTOCOL = dict(schema='isaforge-countnegative-variable-pool-v2', workload_group=GROUP,
    pool_cap=POOL_SIZE, minimum_legal_candidates=1,
    admission_rule='Any nonempty calibrated relocation-safe pool under the existing four-operation extractor; no benefit or occurrence admission minima.',
    technical_calibration_limit='Existing public latency feature API requires calibrated source instruction latencies. Unsupported latency formulas remain excluded; this is a runtime coverage limit, not a benefit threshold.',
    unchanged_input=True, unchanged_upstream_source=True, unchanged_verifier=True,
    correctness=original.PROTOCOL['correctness'],
    build_context=original.PROTOCOL['build_context'],
    compiler_flags=list(g.q.bounded.compact.FLAGS), isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    memory_partition=PARTITION, clock_mhz=12, route_seeds=[1,2,3],
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    historical_status='Previously screened under fixed-size v1 gates; this is a separately authorized variable-pool context, not an untouched-source claim.')
GATE_SOURCES = tuple(dict.fromkeys((SOURCE, QUALIFIER, TEST, CONTRACT,
    original.SOURCE, variable.SOURCE, HISTORY, 'scripts/qualify_nanocobs_v2.py',
    *original.GATE_SOURCES, *g.AUTHENTICATION_SOURCES,
    'isaforge/guarded_attempts.py', 'isaforge/guarded_evidence.py',
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
    'hardware/checked_sim.cpp', 'scripts/reproduce_codesign.py')))


def source_record():
    c.require(c.sha(c.ROOT / PROGRAM) == ADAPTER_SHA256 and
              c.sha(c.ROOT / PROVENANCE) == PROVENANCE_SHA256,
              'Pinned countnegative adapter/provenance differs')
    for name, digest in original.UPSTREAM.items():
        c.require(c.sha(c.ROOT / BASE / name) == digest, 'Pinned countnegative source differs: ' + name)
    return original.upstream_record()


@contextmanager
def registration():
    q, bounded = g.q, g.q.bounded
    campaign = bounded.campaign
    names = ('SOURCE', 'WORKLOADS', 'POOL_SIZE', 'NATIVE_LIMITS', 'POOL_RULE',
             'authenticate_discovery', 'audit')
    previous = {name:getattr(g, name) for name in names}
    others = (q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE,
              g.partition.extract_pool, evidence._public)
    g.SOURCE, g.WORKLOADS, g.POOL_SIZE = SOURCE, dict(WORKLOADS), POOL_SIZE
    g.NATIVE_LIMITS, g.POOL_RULE = dict(NATIVE_LIMITS), variable.VARIABLE_POOL_RULE
    g.authenticate_discovery, g.audit = variable.authenticate_discovery, audit
    q.WORKLOADS = dict(WORKLOADS)
    q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.partition.extract_pool, evidence._public = variable.variable_extract_pool, public_projection
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(g, name, value)
        (q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE,
         g.partition.extract_pool, evidence._public) = others


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan.get('workload_group') == GROUP and plan.get('upstream') == source_record() and
              plan.get('countnegative_v2_protocol') == PROTOCOL and
              plan.get('memory_partition') == PARTITION and
              plan.get('computational_pool_cap') == POOL_SIZE,
              'Different original-input countnegative v2 context')
    expected = {'program.c':c.sha(c.ROOT / PROGRAM), **original.UPSTREAM}
    for name, digest in expected.items():
        c.require(plan['inputs'].get(name) == digest, 'Pinned countnegative input differs: ' + name)
    for name in GATE_SOURCES:
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT / name),
                  'Countnegative v2 source binding differs: ' + name)
    c.require(c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == plan['context_id'],
              'Invalid countnegative v2 context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest, 'Bound countnegative v2 input differs: ' + name)
    with registration():
        g.validate_runtime_inputs(root, PARTITION)
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh countnegative v2 root required')
    upstream = source_record()
    history = c.unseal(c.ROOT / HISTORY)
    c.require(GROUP not in {r.get('workload_group') for r in history['rows']},
              'Countnegative target labels must be absent from historical fitting corpus')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'], stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    plan['source_bindings'] = {str((c.ROOT/name).resolve().relative_to(c.ROOT)):digest
                               for name,digest in plan['source_bindings'].items()}
    for name in original.UPSTREAM:
        shutil.copyfile(c.ROOT / BASE / name, output / 'inputs' / name)
    plan.update(upstream=upstream, workload_group=GROUP, countnegative_v2_protocol=PROTOCOL,
        historical_corpus_sha256=c.sha(c.ROOT / HISTORY),
        computational_pool_cap=POOL_SIZE,
        pool_size_semantics='Immutable computational cap; discovery actual_pool_size is independently authenticated.',
        runtime_support='Exact original deterministic 20x20 matrix and checksum0x1778de; unchanged ABI adapter.',
        selection_evidence_scope=PROTOCOL['historical_status'])
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        target = output / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, target)
    plan['inputs'] = {p.name:c.sha(p) for p in (output / 'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


require_zero_candidates = variable.require_zero_candidates


def public_projection(root, plan, discovery, baseline, calibration):
    count = len(discovery['pool'])
    c.require(1 <= count <= plan['pool_size'], 'Nonempty pool within computational cap required')
    rows = PUBLIC(root, dict(plan, pool_size=count), discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-' + WORKLOAD + ':' + plan['context_id'],
                  'Different countnegative v2 public identity')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


def discovery_public(root):
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        rows = public_projection(root, plan, discovery,
            dict(performance=discovery['baseline_performance']), evidence._calibration(root))
    return original.prior.b.public_rows(rows)


def opportunity_gate(public):
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(public), actual_pool_size=len(public), computational_pool_cap=POOL_SIZE,
        public_digest=c.digest(public), qualifying_candidate_ids=[r['candidate_id'] for r in public],
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def opportunity(root):
    path = Path(root) / 'opportunity.json'
    c.require(not path.exists(), 'Preserve prior opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(path, result)
    c.require(result['passed'], 'Nonempty legal pool required')
    return result


def check_opportunity(root):
    result = c.unseal(Path(root) / 'opportunity.json')
    c.require(result == opportunity_gate(discovery_public(root)) and result['passed'],
              'Authenticated nonempty countnegative pool required')
    return result


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        require_zero_candidates(self.root)
        try:
            with registration():
                result = super().discover()
        except variable.NoLegalCandidates as error:
            c.seal(self.root / 'discovery-rejection.json', dict(
                schema=PROTOCOL['schema'] + '-discovery-rejection', context_id=self.plan['context_id'],
                passed=False, source_level_rejection=True, target_candidate_attempts=0,
                extraction=error.extraction, reason=str(error), plan_sha256=c.sha(self.root / 'plan.json')))
            raise
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == 'baseline', 'Candidate dispatch disabled during countnegative v2 qualification')
        require_zero_candidates(self.root)
        check_opportunity(self.root)
        with registration():
            result = super().measure(name)
        require_zero_candidates(self.root)
        return result


def baseline_public(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = g.baseline_public(root)
    c.require(opportunity_gate(rows) == c.unseal(Path(root) / 'opportunity.json'),
              'Discovery and routed public pool differ')
    context['workload_group'] = before['workload'] = GROUP
    context['context_transfer'] = PROTOCOL['historical_status']
    return rows, context, before


def audit(root):
    rows, context, before = baseline_public(root)
    state = g.attempts.read_attempt(root, 'baseline')
    c.require(state['status'] == 'success', 'Successful baseline ledger required')
    return dict(schema=PROTOCOL['schema'] + '-baseline-audit', context_id=context['context_id'],
        actual_pool_size=len(rows), computational_pool_cap=POOL_SIZE, baseline=before,
        baseline_ledger_status=state['status'], target_candidate_attempts=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','discover','opportunity','baseline','public','freeze','audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        result = prepare(args.reference_root, args.root)
    elif args.command == 'opportunity':
        result = opportunity(args.root)
    elif args.command == 'public':
        rows, context, before = baseline_public(args.root)
        for name, value in [('public.json',rows), ('context.json',context), ('before.json',before)]:
            c.seal(args.root / name, value)
        result = dict(candidates=len(rows), context_id=context['context_id'])
    elif args.command == 'audit':
        result = audit(args.root)
    else:
        evaluator = Evaluator(args.root)
        try:
            if args.command == 'freeze':
                check_opportunity(args.root)
                with registration():
                    result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
            else:
                result = evaluator.measure('baseline') if args.command == 'baseline' else evaluator.discover()
        finally:
            evaluator.runner.lock.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

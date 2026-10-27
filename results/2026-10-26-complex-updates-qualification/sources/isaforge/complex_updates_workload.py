"""Label-free original-input complex_updates qualification on the guarded processor.

Reuse the frozen guarded evaluator and TACLe public gate; adapt only source/ABI
registration and provenance. Candidate dispatch is deliberately unavailable until
an independently frozen complete model/controller release is implemented.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import shutil
import time

from . import codesign as c, guarded_workload as g, campaign_evidence as evidence
from . import tacle_workload as prior

SOURCE = 'isaforge/complex_updates_workload.py'
WORKLOAD = 'complex_updates'
GROUP = 'tacle-complex-updates'
BASE = 'benchmarks/tacle/complex_updates/'
PROGRAM = BASE+'isaforge_adapter.c'
PROVENANCE = 'benchmarks/tacle/COMPLEX_UPDATES_SOURCES.json'
UPSTREAM_COMMIT = 'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
UPSTREAM = {'complex_updates.c': '81176182997abd6ee1107fc671252b7c32a15750e4b01b509817706206d1b88a', 'ChangeLog.txt': '0ff0889790c2bdd81429f8c8680ca3bba4116f573269713b5fe5d3a1974ba9ee'}

POOL_SIZE = prior.POOL_SIZE
PARTITION = g.q.partition_spec(6400, 6528)
NATIVE_LIMITS = dict(prior.NATIVE_LIMITS)
COMPILER_FLAGS = tuple(g.q.bounded.compact.FLAGS)
PROTOCOL = dict(schema='isaforge-tacle-complex-updates-v1', workload_group=GROUP,
    pool_size=POOL_SIZE, minimum_calibrated_cycle_reduction=.005,
    minimum_timed_replacements=10,
    joint_gate='At least one selected formula satisfies both numeric minima.',
    unchanged_input=True, unchanged_upstream_source=True, unchanged_verifier=True,
    build_context='Single unchanged upstream translation unit; rename original main only; ILP32 asserted.',
    correctness='Original complex_updates_return requires exact float checksum144.0f over first16 of32 D elements.',
    verifier_limitation='Original checksum covers only first16 D elements, not all32 outputs or intermediate results.',
    original_input='N16; four32-float arrays; original pinned initialization A(2,1), B(2,5), C(3,4), D(0,0).',
    grammar='Unchanged integer-only2-4-operation, two-input/one-output guarded extraction; no floating instructions or linked-helper rewriting.',
    runtime_arithmetic='Unchanged original C float operations; GCC RV32I ILP32 software-float helpers; no fast-math.',
    compiler_flags=list(COMPILER_FLAGS), software_arithmetic_library='-lgcc',
    clock_mhz=12, route_seeds=[1,2,3], candidate_dispatch_enabled=False,
    target_candidate_attempts=0, candidate_dispatch='Disabled in qualification-only adapter.')
GATE_SOURCES = tuple(dict.fromkeys((SOURCE, prior.SOURCE, g.SOURCE,
    'scripts/blind_campaign.py', *prior.semantic.SOURCES,
    'isaforge/latency_features.py', PROGRAM, PROVENANCE,
    *(BASE+name for name in UPSTREAM))))


def public_projection(root, plan, discovery, baseline, calibration):
    rows = prior.PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-'+WORKLOAD+':'+plan['context_id'],
                  'Different next TACLeBench projection')
        row['benchmark'] = GROUP+':'+plan['context_id']
    return rows


@contextmanager
def registration():
    """Use the existing scoped registration contract; restore even when nested."""
    q, bounded, campaign = g.q, g.q.bounded, g.q.bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
                q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public)
    g.SOURCE = SOURCE
    g.WORKLOADS = {WORKLOAD: '../../tacle/complex_updates/isaforge_adapter.c'}
    g.POOL_SIZE = q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public) = previous


def upstream_record():
    provenance = json.loads((c.ROOT/PROVENANCE).read_text())
    c.require(provenance.get('suite') == 'TACLeBench' and
              provenance.get('commit') == UPSTREAM_COMMIT and
              provenance.get('directory') == 'bench/kernel/complex_updates' and
              set(provenance.get('files', {})) == set(UPSTREAM),
              'Pinned complex_updates provenance differs')
    for name, digest in UPSTREAM.items():
        raw = (c.ROOT/BASE/name).read_bytes()
        expected = dict(sha256=digest, bytes=len(raw), git_blob_sha1=hashlib.sha1(
            b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest())
        c.require(provenance['files'][name] == expected and c.sha(c.ROOT/BASE/name) == digest,
                  'Pinned complex_updates source differs: '+name)
    return dict(suite='TACLeBench', commit=UPSTREAM_COMMIT,
        directory='bench/kernel/complex_updates', files=dict(UPSTREAM),
        provenance=PROVENANCE, provenance_sha256=c.sha(c.ROOT/PROVENANCE),
        adapter=PROGRAM, adapter_sha256=c.sha(c.ROOT/PROGRAM))


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan.get('compiler_flags') == list(COMPILER_FLAGS) and
              c.CONFIG['frequency_mhz'] == 12.0 and c.CONFIG['route_seeds'] == [1,2,3],
              'Fixed compiler, software-float and clock protocol required')
    c.require(plan.get('workload') == WORKLOAD and plan.get('workload_group') == GROUP and
              plan.get('memory_partition') == PARTITION and plan.get('upstream') == upstream_record() and
              plan.get('opportunity_source_protocol') == PROTOCOL,
              'Fixed original-input complex_updates context required')
    c.require(plan['inputs']['program.c'] == c.sha(c.ROOT/PROGRAM), 'External ABI adapter changed')
    for name, digest in UPSTREAM.items():
        c.require(c.sha(c.ROOT/BASE/name) == digest and plan['inputs'].get(name) == digest,
                  'Unchanged upstream file required: '+name)
    for name in GATE_SOURCES:
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT/name),
                  'Next TACLeBench source or runtime binding differs: '+name)
    c.require(c.digest({key:value for key,value in plan.items() if key != 'context_id'}) == plan['context_id'],
              'Invalid next TACLeBench context identity')


def require_zero_candidates(root):
    root = Path(root)
    c.require(not list((root/'attempt-ledger').glob('candidate_*')) and
              not list((root/'measurements').glob('candidate_*')),
              'Qualification requires zero candidate attempts')


def validate_inputs(root):
    root = Path(root)
    require_zero_candidates(root)
    plan = c.unseal(root/'plan.json')
    check_plan(plan)
    c.require((root/'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT/'hardware/embench_firmware.c').read_bytes(), 'Generic benchmark harness changed')
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name) == digest, 'Bound input changed: '+name)
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh complex_updates qualification root required')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'], stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    plan['source_bindings'] = {str((c.ROOT/name).resolve().relative_to(c.ROOT)):digest
                               for name,digest in plan['source_bindings'].items()}
    for name, digest in UPSTREAM.items():
        c.require(c.sha(c.ROOT/BASE/name) == digest, 'Pinned upstream bytes changed: '+name)
        shutil.copyfile(c.ROOT/BASE/name, output/'inputs'/name)
    plan.update(upstream=upstream_record(), workload_group=GROUP,
        opportunity_source_protocol=PROTOCOL,
        runtime_support='Original N16 float arithmetic/input/checksum144.0f; unchanged GCC software-float helpers; external ABI adapter only.',
        output_check=PROTOCOL['correctness'],
        harness_derivation='Exact hardware/embench_firmware.c; ABI wrappers in bound external program.c.',
        selection_evidence_scope='Source-inspected, candidate-unmeasured qualification only; source-family independence and eligible pool not established.',
        context_amendment='Original guarded RV32I_zicsr/ILP32-Os, PCPI, 8KiB integrated SoC and6400/6528 partition retained.')
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT/name)
        destination = output/'sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT/name, destination)
    plan['inputs'] = {p.name:c.sha(p) for p in (output/'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output/'plan.json', plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    # Reuse the exact public-only, same-candidate numeric rule, not its old source
    # identity. This function never opens measurements or changes the old module.
    result = prior.opportunity_gate(public)
    return dict(result, schema=PROTOCOL['schema']+'-gate', protocol=PROTOCOL)


def discovery_public(root):
    root = Path(root)
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {'performance':discovery['baseline_performance']}, calibration)
    return prior.b.public_rows(rows)


def opportunity(root):
    root = Path(root)
    c.require(not (root/'opportunity.json').exists(), 'Preserve prior opportunity gate')
    result = opportunity_gate(discovery_public(root))
    c.seal(root/'opportunity.json', result)
    c.require(result['passed'], 'Declared public useful-opportunity gate rejected this source')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root)/'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'], 'Accepted unchanged opportunity gate required')
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            return super().discover()

    def measure(self, name):
        c.require(name == 'baseline', 'Candidate dispatch disabled during zero-label qualification')
        require_zero_candidates(self.root)
        check_opportunity(self.root)
        with registration():
            return super().measure(name)


def baseline_public(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = g.baseline_public(root)
    c.require(opportunity_gate(rows) == c.unseal(Path(root)/'opportunity.json'),
              'Discovery and routed-baseline public projections differ')
    context['workload_group'] = before['workload'] = GROUP
    context['context_transfer'] = 'Original-input TACLeBench complex_updates; unchanged guarded8KiB RV32I context.'
    return rows, context, before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','discover','opportunity','baseline','public','freeze'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    args = parser.parse_args(argv)
    began, status = time.monotonic(), 'interrupted'
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        if args.command == 'prepare':
            c.require(args.reference_root is not None, 'Preserved reference required')
            result = prepare(args.reference_root, args.root)
        elif args.command == 'opportunity':
            result = opportunity(args.root)
        elif args.command == 'public':
            rows, context, before = baseline_public(args.root)
            for name,value in [('public.json',rows),('context.json',context),('before.json',before)]:
                c.seal(args.root/name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    check_opportunity(args.root)
                    with registration():
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command == 'baseline':
                    result = evaluator.measure('baseline')
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
                candidate=None, started_at_utc=stamp, status=status,
                elapsed_seconds=time.monotonic()-began,
                scope='Complete CLI operation through lock close; excludes Python startup/final timer write; overlaps inner scopes.'))


if __name__ == '__main__':
    main()

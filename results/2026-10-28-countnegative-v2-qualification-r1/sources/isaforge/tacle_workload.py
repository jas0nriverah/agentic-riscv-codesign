"""Original-input TACLeBench bitcount on the existing guarded RV32I processor.

Only source registration and an explicit multi-file ABI/amalgamation adapter are
new. Extraction, relocation checks, lowering, memory observation, one-attempt
accounting, processor controls and integrated routing are reused unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time

from . import codesign as c, guarded_workload as g, campaign_evidence as evidence
from . import budgeted_selection as b, semantic_selection as semantic

SOURCE = 'isaforge/tacle_workload.py'
GUARDED_SOURCE = g.SOURCE
WORKLOAD = 'bitcount'
GROUP = 'tacle-bitcount'
BASE = 'benchmarks/tacle/bitcount/'
PROGRAM = BASE+'isaforge_adapter.c'
UPSTREAM_COMMIT = 'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
UPSTREAM = {
    'bitcount.c': '7b0a5eccbf18e81cae1bcc948f0f0f47143cd177cf46de10b2d676e5b0d8d2fa',
    'bitcnt_1.c': '8e22f9e70f40539484151d17b18fd31002fcb0106ef4fb0b70ed239b2ff9228c',
    'bitcnt_2.c': '853c233e8d51db3f26b4e7e12491b4c4ef8633b49beda32f542c97dd2e240f33',
    'bitcnt_3.c': '9f9735c11c5f0f88a6a8206359a4d771bf5cd0f53e52229dfb44b74b3ac02a9f',
    'bitcnt_4.c': '11b07b004c24843b44d203c7be2dc5e6cae930909f5b49752c5e592ec18582c4',
    'bitops.h': '8877c5de289c0e1f4fe17836db60fe0468b999f0ddefbfbf7f0e610d6d927f6c',
    'LICENSE': 'd5433a2f12b96fb7dd1ec0e09f8268ce220a93859fa2c6441ac11724169dad95',
    'ChangeLog.txt': '350b8e0b014bf5768693527e4aa003315d043113e634763b4fe4ba4fa1b57ee6',
}
POOL_SIZE = 12
PARTITION = g.q.partition_spec(6400, 6528)
NATIVE_LIMITS = dict(commands=480, seconds=3600, command_seconds=180,
                     workers=1, build_workers=2, candidate_attempts=1)
SELECTION_SCHEMA = 'isaforge-tacle-selection-v1'
SELECTION_CONTROLLER = 'scripts/tacle_selection_campaign.py'
POLICIES = (*b.POLICIES, 'feasible_benefit_xgb', 'factorized_feasibility_xgb',
            'hybrid_gp_adapt_count', 'hybrid_gp_adapt_count_semantic')
PROTOCOL = dict(schema='isaforge-tacle-bitcount-v1', workload_group=GROUP,
    pool_size=POOL_SIZE, minimum_calibrated_cycle_reduction=.005,
    minimum_timed_replacements=10,
    joint_gate='At least one selected formula satisfies both numeric minima.',
    unchanged_input=True, unchanged_upstream_source=True, unchanged_verifier=True,
    build_context='Declared single translation unit; rename original main and the two private arrays only.',
    correctness='Original bitcount_return requires aggregate1095; every candidate must pass it.',
    no_native_candidate_before_pushed_model_release=True)
GATE_SOURCES = tuple(dict.fromkeys((SOURCE, GUARDED_SOURCE, 'scripts/blind_campaign.py',
    *semantic.SOURCES, 'isaforge/latency_features.py', PROGRAM, 'benchmarks/tacle/SOURCES.json',
    *(BASE+name for name in UPSTREAM))))
PUBLIC = evidence._public


def public_projection(root, plan, discovery, baseline, calibration):
    rows = PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-'+WORKLOAD+':'+plan['context_id'],
                  'Different TACLeBench projection')
        row['benchmark'] = GROUP+':'+plan['context_id']
    return rows


@contextmanager
def registration():
    q, bounded, campaign = g.q, g.q.bounded, g.q.bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
                q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public)
    g.SOURCE = SOURCE
    g.WORKLOADS = {WORKLOAD: '../../tacle/bitcount/isaforge_adapter.c'}
    g.POOL_SIZE = q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public) = previous


def upstream_record():
    return dict(suite='TACLeBench', commit=UPSTREAM_COMMIT,
        directory='bench/kernel/bitcount', files=dict(UPSTREAM),
        adapter=PROGRAM, adapter_sha256=c.sha(c.ROOT/PROGRAM))


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan.get('workload') == WORKLOAD and plan.get('workload_group') == GROUP and
              plan.get('memory_partition') == PARTITION and plan.get('upstream') == upstream_record() and
              plan.get('opportunity_source_protocol') == PROTOCOL,
              'Fixed original-input TACLeBench context required')
    c.require(plan['inputs']['program.c'] == c.sha(c.ROOT/PROGRAM), 'External ABI adapter changed')
    for name, digest in UPSTREAM.items():
        c.require(c.sha(c.ROOT/BASE/name) == digest and plan['inputs'].get(name) == digest,
                  'Unchanged upstream file required: '+name)
    for name in GATE_SOURCES:
        c.require(plan['source_bindings'].get(name) == c.sha(c.ROOT/name),
                  'TACLeBench adapter, model or runtime binding differs: '+name)
    c.require(c.digest({key:value for key,value in plan.items() if key != 'context_id'}) == plan['context_id'],
              'Invalid TACLeBench context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root/'plan.json')
    check_plan(plan)
    c.require((root/'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT/'hardware/embench_firmware.c').read_bytes(), 'Generic benchmark harness changed')
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name) == digest, 'Bound input changed: '+name)
    return plan


def prepare(reference, output):
    output = Path(output)
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
        runtime_support='Unchanged five TACLeBench C files and header, explicit ILP32 amalgamation/ABI adapter; unchanged input, eight algorithms, ten iterations, original1095 verifier.',
        output_check=PROTOCOL['correctness'],
        harness_derivation='Exact hardware/embench_firmware.c; ABI wrappers in bound external program.c.',
        selection_evidence_scope='Untouched TACLeBench source; historical exact/related formula exclusions still required.',
        context_amendment='Declared amalgamation context; original RV32I_zicsr/ILP32-Os, PCPI, 8KiB integrated SoC and6400/6528 partition retained.')
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
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {'performance':discovery['baseline_performance']}, calibration)
    return b.public_rows(rows)


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


def check_release(root):
    """Authenticate the committed full model package before any candidate work."""
    from scripts import blind_campaign as prior
    root = Path(root)
    plan = validate_inputs(root)
    release = c.unseal(root/'release.json')
    prereg = (c.ROOT/release['preregistration_root']).resolve()
    c.require(prereg.is_relative_to(c.ROOT) and not prereg.is_relative_to(root.resolve()),
              'Separate repository-local preregistration required')
    cohort = c.unseal(prereg/'cohort.json')
    target = cohort['targets'].get(GROUP, {})
    c.require(release.get('schema') == PROTOCOL['schema']+'-release' and
              release.get('zero_candidate_attempts') is True and
              type(release.get('target_labels_observed')) is int and release['target_labels_observed'] == 0 and
              release.get('context_id') == target.get('context_id') == plan['context_id'] and
              release.get('cohort_sha256') == c.sha(prereg/'cohort.json') and
              release.get('manifest_sha256') == c.sha(prereg/'manifest.json') and
              release.get('evaluation_protocol_sha256') == c.sha(root/'evaluation-protocol.json') and
              target.get('native_order') == c.unseal(root/'evaluation-protocol.json')['pool_names'] and
              cohort.get('schema') == SELECTION_SCHEMA and cohort.get('policies') == list(POLICIES) and
              cohort.get('seeds') == [0,1,2,3,4] and cohort.get('area_caps') == [32,64,128] and
              cohort.get('budgets') == [1,2,3] and cohort.get('clock_mhz') == 12. and
              all(type(cohort.get(key)) is int and cohort[key] == 0
                  for key in ('target_labels_observed','target_labels_read')) and
              set(cohort['targets']) == {GROUP} and target.get('pool_size') == POOL_SIZE and
              cohort['source_bindings'].get(SELECTION_CONTROLLER) == c.sha(c.ROOT/SELECTION_CONTROLLER) and
              all(cohort['source_bindings'].get(name) == digest for name,digest in plan['source_bindings'].items()),
              'Pushed complete zero-label TACLeBench model/cohort release required')
    prior._manifest(prereg)
    prior.check_git_checkpoint(prereg, release['prelabel_commit'])
    c.require(release.get('pushed_remote_head') == release['prelabel_commit'], 'Pushed checkpoint proof required')
    # Metadata and a committed inventory alone do not establish complete models
    # or that the checkpoint was pushed. Recheck both before native dispatch.
    from scripts.tacle_selection_campaign import authenticate
    authenticate(prereg)
    remote = subprocess.run(['git','ls-remote','origin','refs/heads/ai-guided-ml'],
        cwd=c.ROOT, capture_output=True, text=True, check=True, timeout=30)
    c.require(remote.stdout.strip().split() ==
              [release['prelabel_commit'],'refs/heads/ai-guided-ml'],
              'Actual origin/ai-guided-ml head must equal the prelabel checkpoint')
    return release


class Evaluator(g.Evaluator):
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
            check_release(self.root)
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
    context['context_transfer'] = 'Untouched TACLeBench bitcount with unchanged inputs/verifier; declared multi-file amalgamation and original guarded8KiB RV32I context.'
    return rows, context, before


def audit(root):
    from . import guarded_evidence
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        return guarded_evidence.audit(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','discover','opportunity','baseline','public','freeze','measure','audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--candidate')
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
        elif args.command == 'audit':
            result = audit(args.root)
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    check_opportunity(args.root)
                    with registration():
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command in ('baseline','measure'):
                    name = 'baseline' if args.command == 'baseline' else args.candidate
                    c.require(name is not None, 'Candidate required')
                    result = evaluator.measure(name)
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
                elapsed_seconds=time.monotonic()-began,
                scope='Complete CLI operation through lock close; excludes Python startup/final timer write; overlaps inner scopes.'))


if __name__ == '__main__':
    main()

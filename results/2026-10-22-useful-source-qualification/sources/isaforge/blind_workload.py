"""Larger blind BEEBS pools on the unchanged guarded RV32I processor.

Only source registration, a declared pool/budget and the external benchmark ABI
adapter differ. Extraction, lowering, continuous memory checks, one-attempt
accounting, processor controls and integrated hardware measurement are reused.
All legacy globals are scoped and restored, including on failure.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tarfile
import time

from . import codesign as c, guarded_workload as g, campaign_evidence as evidence

SOURCE = 'isaforge/blind_workload.py'
GUARDED_SOURCE = g.SOURCE
UPSTREAM_COMMIT = '049ded9f3aeb5591f553879d3a0376b8614e9422'
LICENSE = 'benchmarks/beebs/COPYING'
WORKLOADS = {
    'aha-compress': ('compress_test.c', '1e9e7929e0466968e1bc069f406597aa7bb1c7e1eeaeb7f4bc593be4510d4af8'),
    'ndes': ('libndes.c', '78d92b71cc0edd3a26ef1a49e2904ac7d6b6dc5ab33d172ab17cb68fdb92d071'),
    'nettle-arcfour': ('arcfour.c', '1efb711913921a574cb6092a4e2f996f8514cd1d2fade3c19c9aef6d5787cff7'),
    'nettle-md5': ('md5.c', '7b8b50fc6ffe75a6e6fa9067a79f502d8cf4a3e5701bfc0ed94de1347b830b2f'),
    'levenshtein': ('liblevenshtein.c', 'fd1ee0e23bab6db0182b32618bc3622a3ce0399714b662076d053d98fb7193f6'),
}
POOL_SIZE = 12
PARTITION = g.q.partition_spec(6400, 6528)
NATIVE_LIMITS = dict(commands=480, seconds=3600, command_seconds=180,
                     workers=1, build_workers=2, candidate_attempts=1)
WARMUP = '\n/* BEEBS ABI adapter only: upstream has no warmup entrypoint. */\nvoid warm_caches(int heat) { (void)heat; }\n'
ARCFOUR_CHECK = '''
/* Independent fixed ciphertext check, outside the benchmark counters.
 * Same upstream key/plaintext; expected bytes come from the separately
 * recorded byte-oriented Python RC4 reference, not this C implementation.
 */
struct arcfour_ctx { unsigned char S[256], i, j; };
extern void arcfour_set_key(struct arcfour_ctx *, int, const unsigned char *);
extern void arcfour_crypt(struct arcfour_ctx *, int, unsigned char *, const unsigned char *);
static int isaforge_arcfour_check(void) {
    struct arcfour_ctx ctx;
    const unsigned char key[16] = {15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0};
    const unsigned char plain[16] = {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15};
    const unsigned char expected[16] = {0x08,0x47,0x73,0xcb,0x87,0x5b,0xee,0xfe,0x01,0xa1,0xbe,0x84,0x71,0xdf,0x1b,0xbc};
    unsigned char output[16];
    arcfour_set_key(&ctx, 16, key);
    arcfour_crypt(&ctx, 16, output, plain);
    for (unsigned i = 0; i < 16; ++i) if (output[i] != expected[i]) return 0;
    return 1;
}
'''
PUBLIC = evidence._public


def program(workload):
    c.require(workload in WORKLOADS, 'Unregistered blind workload')
    return 'benchmarks/beebs/' + workload + '/' + WORKLOADS[workload][0]


def group(workload):
    c.require(workload in WORKLOADS, 'Unregistered blind workload')
    return 'beebs-' + workload


def harness_source(workload):
    text = (c.ROOT/'hardware/embench_firmware.c').read_text()
    if workload == 'nettle-arcfour':
        marker = '    int correct=verify_benchmark(result);'
        c.require(text.count(marker) == 1, 'Benchmark verification marker differs')
        text = text.replace('int main(void) {', ARCFOUR_CHECK + '\nint main(void) {')
        text = text.replace(marker, marker + '\n    if (!isaforge_arcfour_check()) correct=0;')
    return text + WARMUP


def public_projection(root, plan, discovery, baseline, calibration):
    rows = PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-' + plan['workload'] + ':' + plan['context_id'],
                  'Different blind projection')
        row['benchmark'] = group(plan['workload']) + ':' + plan['context_id']
    return rows


@contextmanager
def registration(plan):
    """Serial scoped adapter; accepts a sealed plan or a registered source name."""
    workload = plan['workload'] if isinstance(plan, dict) else plan
    c.require(workload in WORKLOADS, 'Unregistered blind workload')
    q, bounded, campaign = g.q, g.q.bounded, g.q.bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
                q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public)
    g.SOURCE = SOURCE
    g.WORKLOADS = {workload: '../../beebs/' + workload + '/' + WORKLOADS[workload][0]}
    g.POOL_SIZE = q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.POOL_SIZE, bounded.POOL_SIZE, campaign.POOL_SIZE, evidence._public) = previous


def check_plan(plan):
    with registration(plan):
        g.check_plan(plan)
    workload = plan['workload']
    digest = WORKLOADS[workload][1]
    c.require(plan['pool_size'] == POOL_SIZE and plan['memory_partition'] == PARTITION and
              plan.get('workload_group') == group(workload) and
              plan.get('upstream') == dict(suite='BEEBS', commit=UPSTREAM_COMMIT,
                  source=program(workload), source_sha256=digest),
              'Different blind source/pool/partition protocol')
    c.require(plan['inputs']['program.c'] == digest and c.sha(c.ROOT/program(workload)) == digest,
              'Pinned benchmark source differs')
    c.require(all(name in plan['source_bindings'] for name in
                  (SOURCE, GUARDED_SOURCE, program(workload), LICENSE)),
              'Blind source/adapter/license bindings missing')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root/'plan.json')
    check_plan(plan)
    c.require((root/'inputs/embench_firmware.c').read_text() == harness_source(plan['workload']),
              'Exact bound benchmark harness derivation required')
    c.require(c.sha(root/'inputs/program.c') == WORKLOADS[plan['workload']][1],
              'Unchanged full benchmark source required')
    return plan


def prepare(reference, output, workload):
    output = Path(output)
    with registration(workload):
        plan = g.prepare(reference, output, workload, POOL_SIZE,
                         program_limit=PARTITION['program_limit'], stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    harness = output/'inputs/embench_firmware.c'
    c.require(harness.read_text() == (c.ROOT/'hardware/embench_firmware.c').read_text(),
              'Generic benchmark harness differs')
    harness.write_text(harness_source(workload))
    plan['source_bindings'] = {str((c.ROOT/name).resolve().relative_to(c.ROOT)): digest
                               for name, digest in plan['source_bindings'].items()}
    plan.update(upstream=dict(suite='BEEBS', commit=UPSTREAM_COMMIT,
                             source=program(workload), source_sha256=WORKLOADS[workload][1]),
        workload_group=group(workload),
        qualification_order=list(WORKLOADS),
        qualification_rule='Original source/input/verifier, checked baseline and twelve legal calibrated formulas; no candidate outcomes used.',
        runtime_support='Unchanged full BEEBS program and input; exact generic harness plus declared no-op warm_caches ABI adapter.',
        output_check=('Original full roundtrip verifier plus independent sixteen-byte ciphertext check outside counters.'
                      if workload == 'nettle-arcfour' else 'Unmodified upstream full benchmark verifier.'),
        harness_derivation='Exact hardware/embench_firmware.c plus WARMUP; ARCFOUR additionally applies the bound ARCFOUR_CHECK outside counters.',
        selection_evidence_scope='Independent held-out BEEBS source; all candidate labels hidden until paid replay queries.',
        partition_amendment='Common declared 6400-byte program, 128-byte guard and 1664-byte stack on original 8 KiB SoC; unchanged benchmark arithmetic/input.',
        outer_timer_scope='Complete CLI operation through lock close; excludes Python startup and final timing record write; overlaps inner scopes.')
    for name in (SOURCE, GUARDED_SOURCE, program(workload), LICENSE):
        plan['source_bindings'][name] = c.sha(c.ROOT/name)
        target = output/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT/name, target)
    plan['inputs'] = {path.name: c.sha(path) for path in (output/'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output/'plan.json', plan)
    validate_inputs(output)
    return plan


class Evaluator(g.Evaluator):
    def __init__(self, root):
        plan = validate_inputs(root)
        with registration(plan):
            super().__init__(root)

    def discover(self):
        with registration(self.plan):
            return super().discover()

    def measure(self, name):
        if name != 'baseline':
            release = c.unseal(self.root/'release.json')
            target = release.get('targets', {}).get(group(self.plan['workload']), {})
            c.require(release.get('schema') == 'isaforge-blind-cohort-v1-release' and
                      release.get('zero_candidate_attempts') is True and
                      type(release.get('target_labels_observed')) is int and release['target_labels_observed'] == 0 and
                      target.get('context_id') == self.plan['context_id'] and
                      target.get('evaluation_protocol_sha256') == c.sha(self.root/'evaluation-protocol.json') and
                      target.get('native_order') == c.unseal(self.root/'evaluation-protocol.json')['pool_names'],
                      'Pushed zero-attempt cohort release required before candidate work')
        with registration(self.plan):
            return super().measure(name)

    def collect(self):
        with registration(self.plan):
            return super().collect()


def baseline_public(root):
    plan = validate_inputs(root)
    with registration(plan):
        rows, context, before = g.baseline_public(root)
    context['workload_group'] = group(plan['workload'])
    context['context_transfer'] = 'Pinned full-input BEEBS source with common checked 8 KiB RV32I context and twelve-candidate pool.'
    before['workload'] = group(plan['workload'])
    return rows, context, before


def audit(root):
    from . import guarded_evidence
    plan = validate_inputs(root)
    with registration(plan):
        return guarded_evidence.audit(root)


def pack(root, snapshot, *, prelabel_commit=None):
    from . import guarded_evidence
    plan = validate_inputs(root)
    with registration(plan):
        return guarded_evidence.pack(root, snapshot, prelabel_commit=prelabel_commit)


def replay(snapshot, output):
    from . import guarded_evidence
    # Read only a regular plan member; the existing restore authenticates and
    # safely extracts the complete archive before any evidence audit.
    archive = c.unseal(Path(snapshot)/'archive-manifest.json')
    with tarfile.open(Path(snapshot)/archive['archive'], 'r:gz') as stream:
        members = [member for member in stream.getmembers() if member.name == 'plan.json' and member.isfile()]
        c.require(len(members) == 1 and members[0].size <= 1024*1024, 'Unique bounded archive plan required')
        plan = json.load(stream.extractfile(members[0]))
    check_plan(plan)
    with registration(plan):
        result = guarded_evidence.replay(snapshot, output)
    validate_inputs(output)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'public', 'freeze', 'measure', 'audit'))
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
                c.seal(args.root/name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        elif args.command == 'audit':
            result = audit(args.root)
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    with registration(evaluator.plan):
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
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
            folder = args.root/'outer-timing'
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder/f'{sequence:03d}-{args.command}.json', dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command,
                candidate=args.candidate, started_at_utc=stamp, status=status,
                elapsed_seconds=time.monotonic()-started,
                scope='Complete CLI operation through lock close; excludes final timing record write and Python startup; overlaps ledger/native scopes.'))


if __name__ == '__main__':
    main()

"""Baseline-only Fannkuch-redux qualification on the guarded PicoRV32 flow.

This module adapts the reviewed N=7 ABI wrapper and reuses the frozen legal
candidate extractor, lowering verifier, integrated processor and public-only
opportunity gate. Candidate dispatch is deliberately unavailable here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

from . import budgeted_selection as b
from . import codesign as c, guarded_workload as g, campaign_evidence as evidence

SOURCE = 'isaforge/fannkuch_workload.py'
QUALIFIER = 'scripts/qualify_fannkuch.py'
WORKLOAD = 'fannkuch-redux'
GROUP = 'benchmarksgame-fannkuchredux'
BASE = 'benchmarks/fannkuch/'
PROGRAM = BASE + 'fannkuchredux_isaforge.c'
MANIFEST = BASE + 'FANNKUCH_REDUX_PIN.json'
UPSTREAM_COMMIT = '40296663ed350d5fe4a6ab5e367bab61cb77c219'
HTML = BASE + 'upstream/fannkuchredux-gcc-1.html'
ORACLE = BASE + 'upstream/fannkuchredux-output.txt'
EXTRACTED = BASE + 'fannkuchredux_upstream.c'
LICENSE = BASE + 'LICENSE.md'
EXPECTED_RESULT_U32 = ((228 + 32768) << 15) | 16
EXPECTED_OUTPUT = '228\nPfannkuchen(7) = 16\n'
PINNED_SHA256 = {
    HTML: '8e51f6bd3129220c8dd996467fa5c6171eb6dcdcb13900cd84d2b51f925a57a0',
    EXTRACTED: 'd109b20a1ef2dcc601d3fc3dca2b7d06f423b72d3a0fa650afb4cef5fa8e9a18',
    PROGRAM: 'b51a5b22d42c94a3a63efff2261713e3e41ad13f51b0ccff987bd245302382e6',
    ORACLE: '2dc0a3cd4a547ba69389f97f3b447bd4d487fe6216c3cacd2f9bf8c908dc127f',
    LICENSE: 'e5dd0024dd43d92434808c8e1df3c09870a2832744283232aa1dc16c737237b1',
}
PINNED_GIT_BLOB_SHA1 = {
    HTML: '148f0df3e006573e90bd9215efb6df1a2fc42251',
    ORACLE: '2f77272e15fe97d6ad63c2467a404591c6a2772e',
    LICENSE: '4040e702531699ae11fc64337a2b6f43ef33e93f',
}

POOL_SIZE = 12
PARTITION = g.q.partition_spec(6400, 6528)
NATIVE_LIMITS = dict(commands=480, seconds=3600, command_seconds=180,
                     workers=1, build_workers=2, candidate_attempts=1)
PROTOCOL = dict(
    schema='isaforge-benchmarksgame-fannkuchredux-v1', workload_group=GROUP,
    pool_size=POOL_SIZE, minimum_calibrated_cycle_reduction=.005,
    minimum_timed_replacements=10,
    joint_gate='At least one same candidate meets both public numeric thresholds.',
    unchanged_input=True, unchanged_algorithm=True, unchanged_upstream_source=False,
    source_change='Reviewed freestanding ABI/output adapter only; full pinned N=7 algorithm retained.',
    correctness='Full N=7 checksum228 and maximum-flips16; packed return equals the exact oracle-derived value.',
    original_input='N=7; complete 5040-permutation fannkuch-redux execution.',
    verifier='Adapter decodes the result and checks both pinned upstream oracle outputs.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    candidate_dispatch='Disabled in baseline-only qualification.',
    model_fit_during_qualification=False)

RAW_PUBLIC = evidence._public
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER,
    'scripts/extract_fannkuch_source.py', 'scripts/build_fannkuch_adapter.py',
    'tests/test_fannkuch_host_adapter.py', 'tests/test_fannkuch_workload.py',
    'docs/fannkuch-adapter-contract-2026-10-26.md',
    MANIFEST, HTML, ORACLE, EXTRACTED, PROGRAM, LICENSE,
    g.SOURCE, g.QUALIFIED_SOURCE, g.guard.SOURCE, g.attempts.SOURCE,
    g.EVIDENCE_SOURCE, *g.AUTHENTICATION_SOURCES,
    'isaforge/bounded_workload.py', 'isaforge/partitioned_workload.py',
    'isaforge/workload_experiment.py', 'isaforge/assembly_lowering.py',
    'isaforge/relocation_guard.py', 'isaforge/latency_features.py',
    *b.SOURCES, 'scripts/blind_campaign.py',
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
)))


def _blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def verify_source_pins():
    """Authenticate upstream provenance and every deterministic source artifact."""
    manifest = json.loads((c.ROOT / MANIFEST).read_text())
    c.require(manifest.get('schema') == 'isaforge-workload-source-pin-v1' and
              manifest.get('upstream', {}).get('commit') == UPSTREAM_COMMIT,
              'Pinned Fannkuch upstream identity differs')
    c.require(manifest['program'].get('sha256') == PINNED_SHA256[HTML] and
              manifest['program'].get('git_blob_sha1') == PINNED_GIT_BLOB_SHA1[HTML] and
              manifest['extracted_source'].get('sha256') == PINNED_SHA256[EXTRACTED] and
              manifest['adapted_source'].get('sha256') == PINNED_SHA256[PROGRAM] and
              manifest['license'].get('sha256') == PINNED_SHA256[LICENSE] and
              manifest['license'].get('git_blob_sha1') == PINNED_GIT_BLOB_SHA1[LICENSE] and
              manifest['correctness_reference'].get('sha256') == PINNED_SHA256[ORACLE] and
              manifest['correctness_reference'].get('git_blob_sha1') == PINNED_GIT_BLOB_SHA1[ORACLE],
              'Manifest differs from independently approved Fannkuch source pins')
    checks = (
        (HTML, PINNED_SHA256[HTML], PINNED_GIT_BLOB_SHA1[HTML]),
        (LICENSE, PINNED_SHA256[LICENSE], PINNED_GIT_BLOB_SHA1[LICENSE]),
        (ORACLE, PINNED_SHA256[ORACLE], PINNED_GIT_BLOB_SHA1[ORACLE]),
        (EXTRACTED, PINNED_SHA256[EXTRACTED], None),
        (PROGRAM, PINNED_SHA256[PROGRAM], None),
    )
    for name, expected_sha, expected_blob in checks:
        path = c.ROOT / name
        raw = path.read_bytes()
        c.require(c.sha(path) == expected_sha, 'Pinned Fannkuch bytes changed: ' + name)
        if expected_blob is not None:
            c.require(_blob_sha1(raw) == expected_blob,
                      'Pinned Fannkuch Git blob differs: ' + name)
    reference = manifest['correctness_reference']
    c.require(reference.get('input_n') == 7 and reference.get('permutations') == 5040 and
              reference.get('expected_output') == EXPECTED_OUTPUT and
              (c.ROOT / ORACLE).read_text() == EXPECTED_OUTPUT,
              'Pinned Fannkuch N=7 oracle differs')
    return dict(commit=UPSTREAM_COMMIT, manifest_sha256=c.sha(c.ROOT / MANIFEST),
        html_sha256=c.sha(c.ROOT / HTML), extracted_sha256=c.sha(c.ROOT / EXTRACTED),
        adapter_sha256=c.sha(c.ROOT / PROGRAM), oracle_sha256=c.sha(c.ROOT / ORACLE),
        license_sha256=c.sha(c.ROOT / LICENSE))


def upstream_record():
    pins = verify_source_pins()
    return dict(suite='Computer Language Benchmarks Game', commit=UPSTREAM_COMMIT,
        repository='https://salsa.debian.org/benchmarksgame-team/benchmarksgame.git',
        program=HTML, html_sha256=pins['html_sha256'],
        extracted_source=EXTRACTED, extracted_source_sha256=pins['extracted_sha256'],
        adapter=PROGRAM, adapter_sha256=pins['adapter_sha256'],
        oracle=ORACLE, oracle_sha256=pins['oracle_sha256'],
        license=LICENSE, license_sha256=pins['license_sha256'],
        manifest=MANIFEST, manifest_sha256=pins['manifest_sha256'],
        input_n=7, permutations=5040, expected_output=EXPECTED_OUTPUT,
        expected_result_u32=EXPECTED_RESULT_U32)


def public_projection(root, plan, discovery, baseline, calibration):
    rows = RAW_PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-' + WORKLOAD + ':' + plan['context_id'],
                  'Unexpected Fannkuch public projection')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


@contextmanager
def registration():
    """Temporarily register Fannkuch and restore globals under nesting/errors."""
    q, bounded, campaign = g.q, g.q.bounded, g.q.bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
        q.SOURCE, q.WORKLOADS, q.POOL_SIZE,
        bounded.SOURCE, bounded.WORKLOADS, bounded.POOL_SIZE,
        campaign.WORKLOADS, campaign.POOL_SIZE, evidence._public)
    g.SOURCE = SOURCE
    g.WORKLOADS = {WORKLOAD: '../../fannkuch/fannkuchredux_isaforge.c'}
    g.POOL_SIZE = q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    q.WORKLOADS = bounded.WORKLOADS = campaign.WORKLOADS = dict(g.WORKLOADS)
    q.SOURCE = 'isaforge/qualified_workload.py'
    bounded.SOURCE = 'isaforge/bounded_workload.py'
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.SOURCE, q.WORKLOADS, q.POOL_SIZE,
         bounded.SOURCE, bounded.WORKLOADS, bounded.POOL_SIZE,
         campaign.WORKLOADS, campaign.POOL_SIZE, evidence._public) = previous


def check_plan(plan):
    verify_source_pins()
    with registration():
        g.check_plan(plan)
    c.require(plan.get('workload') == WORKLOAD and plan.get('workload_group') == GROUP and
              plan.get('pool_size') == POOL_SIZE and
              plan.get('memory_partition') == PARTITION and
              plan.get('native_limits') == NATIVE_LIMITS and
              plan.get('opportunity_source_protocol') == PROTOCOL and
              plan.get('upstream') == upstream_record(),
              'Fixed pinned Fannkuch context required')
    c.require(plan.get('compiler_flags') == list(g.q.bounded.compact.FLAGS) and
              plan.get('configuration', {}).get('frequency_mhz') == 12.0 and
              plan.get('configuration', {}).get('route_seeds') == [1, 2, 3],
              'Fannkuch compiler and integrated measurement protocol changed')
    c.require(plan.get('inputs', {}).get('program.c') == c.sha(c.ROOT / PROGRAM),
              'External Fannkuch ABI adapter changed')
    bindings = plan.get('source_bindings', {})
    for name in GATE_SOURCES:
        c.require(bindings.get(name) == c.sha(c.ROOT / name),
                  'Fannkuch qualification/runtime source binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) ==
              plan.get('context_id'), 'Invalid Fannkuch context identity')


def require_zero_candidates(root):
    root = Path(root)
    ledger = list((root / 'attempt-ledger').glob('candidate_*.json'))
    artifacts = list((root / 'measurements').glob('candidate_*'))
    c.require(not ledger and not artifacts,
              'Fannkuch qualification requires zero candidate attempts and artifacts')


def validate_inputs(root):
    root = Path(root)
    require_zero_candidates(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic benchmark harness changed')
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest, 'Bound input changed: ' + name)
    c.require(c.sha(root / 'inputs/program.c') == c.sha(c.ROOT / PROGRAM),
              'Compiled Fannkuch translation unit differs from approved adapter')
    return plan


def prepare(reference, output):
    verify_source_pins()
    output = Path(output)
    c.require(not output.exists(), 'Fresh Fannkuch qualification root required')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'], stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    plan['source_bindings'] = {
        str((c.ROOT / name).resolve().relative_to(c.ROOT)): digest
        for name, digest in plan['source_bindings'].items()}
    plan.update(upstream=upstream_record(), workload_group=GROUP,
        opportunity_source_protocol=PROTOCOL,
        runtime_support='One pinned, freestanding N=7 C translation unit with the reviewed result ABI adapter; no algorithm change.',
        output_check=PROTOCOL['correctness'],
        harness_derivation='Exact hardware/embench_firmware.c and existing cycle/profile markers; benchmark and verifier wrappers live in bound program.c.',
        selection_evidence_scope='Baseline-only public candidate opportunity check; no candidate measurements, model fitting, or speedup labels.',
        context_amendment='Original guarded RV32I_zicsr/ILP32-Os, PCPI interface, integrated 8 KiB SoC and 6400/6528 memory partition retained.')
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan['inputs'] = {path.name: c.sha(path) for path in (output / 'inputs').iterdir()}
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    public = b.public_rows(public)
    c.require(len(public) == POOL_SIZE, 'Exactly twelve public formulas required')
    passing = [row['candidate_id'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >=
           PROTOCOL['minimum_calibrated_cycle_reduction'] and
           b.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(passing), qualifying_candidate_ids=passing,
        public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(
            row['latency_features']['estimated_cycle_reduction'] for row in public),
        maximum_timed_replacements=max(b.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def discovery_public(root):
    root = Path(root)
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        c.require(discovery['baseline_performance']['benchmark_result_u32'] == EXPECTED_RESULT_U32,
                  'Baseline profile does not match both pinned Fannkuch oracle outputs')
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return b.public_rows(rows)


def opportunity(root):
    root = Path(root)
    c.require(not (root / 'opportunity.json').exists(), 'Preserve prior Fannkuch opportunity result')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Fannkuch public useful-opportunity gate rejected this source')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged Fannkuch opportunity gate required')
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            result = super().discover()
        c.require(result['baseline_performance']['benchmark_result_u32'] == EXPECTED_RESULT_U32,
                  'Baseline profile does not match both pinned Fannkuch oracle outputs')
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == 'baseline', 'Fannkuch candidate dispatch disabled during qualification')
        require_zero_candidates(self.root)
        check_opportunity(self.root)
        with registration():
            result = super().measure(name)
        c.require(result['performance']['benchmark_result_u32'] == EXPECTED_RESULT_U32,
                  'Routed Fannkuch baseline differs from both pinned oracle outputs')
        require_zero_candidates(self.root)
        return result


def baseline_public(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = g.baseline_public(root)
    before['workload'] = GROUP
    context['workload_group'] = GROUP
    c.require(before['workload'] == GROUP and
              before.get('public_sha256') == c.digest(rows) and
              opportunity_gate(rows) == c.unseal(Path(root) / 'opportunity.json'),
              'Fannkuch public discovery and routed-baseline projections differ')
    c.require(rows and rows[0]['latency_features']['baseline_cycles'] > 0,
              'Fannkuch public baseline counters missing')
    context['context_transfer'] = 'Original pinned N=7 Fannkuch-redux algorithm with reviewed freestanding ABI adapter; guarded RV32I context unchanged.'
    return rows, context, before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'opportunity',
        'baseline', 'public', 'freeze'))
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
            for name, value in [('public.json', rows), ('context.json', context), ('before.json', before)]:
                c.seal(args.root / name, value)
            result = dict(context_id=context['context_id'], candidates=len(rows))
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    check_opportunity(args.root)
                    with registration():
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                    require_zero_candidates(args.root)
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
            folder = args.root / 'outer-timing'
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder / f'{sequence:03d}-{args.command}.json', dict(
                schema='isaforge-wrapper-outer-time-v1', command=args.command,
                candidate=None, started_at_utc=stamp, status=status,
                elapsed_seconds=time.monotonic() - began,
                scope='Complete qualification CLI operation through lock close; excludes Python startup/final timer write and overlaps inner scopes.'))


if __name__ == '__main__':
    main()

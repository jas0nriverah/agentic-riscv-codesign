"""Pinned PULPino Tower of Hanoi workload on the guarded PicoRV32 pipeline.

Qualification is baseline-only. It reuses the existing extraction, RV32I
lowering, stack checks, cycle simulator, and integrated area/routing evaluator;
candidate dispatch stays disabled until a separate frozen release is reviewed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil

from . import budgeted_selection as budget
from . import blind_workload as bw
from . import campaign_evidence as evidence
from . import codesign as c
from . import guarded_workload as g
from .speedup_corpus import family

SOURCE = 'isaforge/pulpino_hanoi_workload.py'
QUALIFIER = 'scripts/qualify_pulpino_hanoi.py'
TEST = 'tests/test_pulpino_hanoi_workload.py'
CONTRACT = 'docs/pulpino-hanoi-adapter-contract-2026-10-28.md'
PIN = 'benchmarks/pulpino-hanoi/SOURCE_PIN.json'
ADAPTER = 'benchmarks/pulpino-hanoi/adapter.c'
ALGORITHM = 'benchmarks/pulpino-hanoi/algorithm.c'
UPSTREAM_C = 'benchmarks/pulpino-hanoi/upstream/towerofhanoi.c'
LICENSE = 'benchmarks/pulpino-hanoi/LICENSE'

WORKLOAD = 'pulpino-hanoi'
GROUP = 'pulpino-hanoi'
REPOSITORY = 'https://github.com/pulp-platform/pulpino'
UPSTREAM_COMMIT = '6631c49ba38a9258da44d6b120d902f7b81f9233'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
POOL_SIZE = 12
# Match the project's original 8 KiB program/stack split. The 12-level Hanoi
# recursion must pass this bound; the split is never widened after a failure.
PARTITION = dict(g.q.partition_spec(6400, 6528))
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
WORKLOADS = {WORKLOAD: str(c.ROOT / ADAPTER)}
FILE_BINDINGS = {
    UPSTREAM_C: ('d1f2951cca657e3cdd1974ad445549094b370e817aeae09987d317dbd32f06f2',
                 '8faf367c9f2215efa9e70543c9942f55d462dab7', 1847),
}
LICENSE_SHA256 = 'b41106a9d0de1cf6ab4ea56bedf677503085c0570248f37fe2cdf657a5e72601'
ADAPTER_SHA256 = '4657fe4667bd63d32270c55d18e6567ac96f633930fdd0d0776d9bdd808693d1'
ALGORITHM_SHA256 = 'eddbddd02ada2574c018defa35e09d2f7071e04b7ca181fbcaba616787f93d00'

PROTOCOL = dict(
    schema='isaforge-pulpino-hanoi-v1', workload_group=GROUP,
    upstream_suite='PULPino sequential tests Tower of Hanoi',
    upstream_repository=REPOSITORY, upstream_commit=UPSTREAM_COMMIT,
    pool_size=POOL_SIZE, plate_count=12,
    minimum_calibrated_cycle_reduction=.005,
    minimum_timed_replacements=10,
    joint_gate='At least one same candidate meets both unchanged public opportunity minima.',
    unchanged_upstream_algorithm_and_fixed_input=True,
    output_adapter='Freestanding ISAForge benchmark ABI; upstream suite registration, timer callbacks, and formatted output are omitted.',
    correctness='Require benchmark completion and equality of every destination B[i] to i for i in [0,12), matching the pinned upstream check.',
    correctness_limitation='One fixed twelve-plate input and destination-array oracle; no generalized parameter sweep.',
    library_runtime='No target libc or formatted output is linked; only the pinned recursive solver and ABI adapter are used.',
    timing_limitation='Includes deterministic array initialization and the recursive solver; excludes host verification.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    family_status='Fixed-input recursive transfer workload; source/operator-family overlap must be audited before any independence claim.',
)

PUBLIC = evidence._public
GUARDED_SOURCE = g.SOURCE
AUTHENTICATION_SOURCES = tuple(g.AUTHENTICATION_SOURCES)
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, ADAPTER, ALGORITHM, UPSTREAM_C,
    LICENSE, HISTORY, GUARDED_SOURCE, *AUTHENTICATION_SOURCES,
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
    'hardware/checked_sim.cpp', 'scripts/reproduce_codesign.py',
    'scripts/qualify_opportunity_sources.py',
)))


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def source_record():
    files = {}
    for path, (expected_sha, expected_blob, expected_size) in FILE_BINDINGS.items():
        raw = (c.ROOT / path).read_bytes()
        c.require(c.sha(c.ROOT / path) == expected_sha and
                  _git_blob_sha1(raw) == expected_blob and len(raw) == expected_size,
                  'Pinned PULPino Hanoi upstream bytes differ: ' + path)
        files[path] = dict(bytes=len(raw), sha256=expected_sha,
                           git_blob_sha1=expected_blob)
    c.require(c.sha(c.ROOT / LICENSE) == LICENSE_SHA256 and
              c.sha(c.ROOT / ADAPTER) == ADAPTER_SHA256 and
              c.sha(c.ROOT / ALGORITHM) == ALGORITHM_SHA256,
              'Pinned PULPino Hanoi license or adapter differs')
    upstream = (c.ROOT / UPSTREAM_C).read_text()
    algorithm = (c.ROOT / ALGORITHM).read_text()
    upstream_body = upstream[upstream.index('void computeGold(int n,'):].strip()
    algorithm_body = algorithm[algorithm.index('void computeGold(int n,'):].strip()
    c.require(upstream_body == algorithm_body,
              'Extracted Tower of Hanoi algorithm differs from pinned upstream bodies')
    pin = json.loads((c.ROOT / PIN).read_text())
    expected_pin = dict(schema='isaforge-workload-source-pin-v1',
        suite='PULPino sequential tests Tower of Hanoi', repository=REPOSITORY,
        commit=UPSTREAM_COMMIT,
        license=dict(path=LICENSE, sha256=LICENSE_SHA256,
            status='Exact upstream Solderpad Hardware License, Version 0.51'),
        files=files,
        fixed_workload=dict(input='The original twelve plates initialized A[i]=i, B[i]=C[i]=0',
            repetitions=1, maximum_source_recursion_depth=12,
            oracle='The original check requires B[i] == i for every i in [0, 12)'),
        adapter_sha256=ADAPTER_SHA256,
        algorithm_extraction_sha256=ALGORITHM_SHA256)
    c.require(pin == expected_pin, 'Pinned PULPino Hanoi source manifest differs')
    return pin


@contextmanager
def registration():
    q = g.q
    bounded = q.bounded
    campaign = bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
                q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE,
                campaign.POOL_SIZE, evidence._public)
    g.SOURCE = SOURCE
    g.WORKLOADS = dict(WORKLOADS)
    g.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    q.WORKLOADS = dict(WORKLOADS)
    q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE,
         campaign.POOL_SIZE, evidence._public) = previous


def check_plan(plan):
    c.require(plan.get('workload') == WORKLOAD and
              plan.get('pool_size') == POOL_SIZE and
              plan.get('memory_partition') == PARTITION and
              plan.get('compiler_flags') == list(PROTOCOL['compiler_flags']),
              'Different PULPino Hanoi workload/compiler/memory/pool contract')
    c.require(plan.get('upstream') == source_record() and
              plan.get('pulpino_hanoi_protocol') == PROTOCOL,
              'Pinned PULPino Hanoi source/protocol differs')
    c.require(plan.get('inputs', {}).get('program.c') == ADAPTER_SHA256 and
              plan.get('inputs', {}).get('algorithm.c') == ALGORITHM_SHA256,
              'PULPino Hanoi adapter/algorithm input differs')
    for name in GATE_SOURCES:
        c.require(plan.get('source_bindings', {}).get(name) == c.sha(c.ROOT / name),
                  'PULPino Hanoi source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items()
                        if key != 'context_id'}) == plan.get('context_id'),
              'Invalid PULPino Hanoi context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound PULPino Hanoi input differs: ' + name)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic freestanding harness changed')
    c.require((root / 'inputs/upstream/towerofhanoi.c').read_bytes() ==
              (c.ROOT / UPSTREAM_C).read_bytes(),
              'Pinned upstream Hanoi source copy differs')
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh PULPino Hanoi qualification root required')
    upstream = source_record()
    history = c.unseal(c.ROOT / HISTORY)
    prior_groups = {row.get('workload_group') for row in history.get('rows', [])}
    c.require(GROUP not in prior_groups,
              'PULPino Hanoi workload group already exists in historical corpus')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'],
            stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    inputs = output / 'inputs'
    shutil.copyfile(c.ROOT / ALGORITHM, inputs / 'algorithm.c')
    upstream_target = inputs / 'upstream' / 'towerofhanoi.c'
    upstream_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(c.ROOT / UPSTREAM_C, upstream_target)
    shutil.copyfile(c.ROOT / LICENSE, inputs / 'upstream' / 'LICENSE')
    plan['inputs'] = {path.relative_to(inputs).as_posix(): c.sha(path)
                      for path in sorted(inputs.rglob('*')) if path.is_file()}
    plan.update(upstream=upstream, workload_group=GROUP,
        qualification_order=[WORKLOAD],
        qualification_rule='One pinned twelve-plate Tower of Hanoi input on guarded RV32I/Zicsr PicoRV32; require twelve legal executable formulas and the unchanged joint 0.5%-plus-10-replacement opportunity gate. No candidate labels, retries, or gate changes.',
        runtime_support='Pinned upstream recursive ToH and computeGold bodies are byte-for-byte extracted into the ABI adapter; only suite registration, timing callbacks, formatted output, and compatibility headers are removed.',
        source_family_review='Recursive Hanoi source; exact extracted formula families must be compared with the historical corpus before claiming independence.',
        qualification_context='Original shared 8-KiB RAM split: 6400-byte program/data limit, 6528-byte stack floor, RV32I/ILP32 -Os, same PicoRV32/PCPI and 12-MHz three-route evaluator.',
        pulpino_hanoi_protocol=PROTOCOL,
        historical_corpus_sha256=c.sha(c.ROOT / HISTORY))
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


def require_zero_candidates(root):
    root = Path(root)
    c.require(not list((root / 'attempt-ledger').glob('candidate_*')) and
              not list((root / 'measurements').glob('candidate_*')),
              'Qualification requires zero candidate attempts')


def public_projection(root, plan, discovery, baseline, calibration):
    rows = PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-' + WORKLOAD + ':' + plan['context_id'],
                  'Unexpected PULPino Hanoi public projection identity')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


def discovery_public(root):
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return budget.public_rows(rows)


def source_family_audit(public):
    history = c.unseal(c.ROOT / HISTORY)
    c.require(len(history.get('rows', [])) == 122 and
              len({row.get('workload_group') for row in history['rows']}) == 14,
              'Expected authenticated 122-label/14-group family history')
    historic = {}
    for row in history['rows']:
        key = row.get('candidate_family') or family(row['formula'])
        historic.setdefault(key, []).append(row['formula'])
    target = {}
    for row in public:
        key = family(row['formula'])
        target.setdefault(key, []).append(row['candidate_id'])
    overlap = sorted(set(target) & set(historic))
    novel = sorted(set(target) - set(historic))
    return dict(schema=PROTOCOL['schema'] + '-source-family-audit',
        historical_corpus_sha256=c.sha(c.ROOT / HISTORY),
        historical_workload_groups=14, historical_verified_labels=122,
        target_candidate_count=len(public),
        target_operation_family_count=len(target),
        historical_operation_family_count=len(historic),
        overlapping_operation_families=overlap,
        novel_operation_families=novel,
        overlap_candidate_ids=sorted(identity for key in overlap
            for identity in target[key]),
        novel_candidate_ids=sorted(identity for key in novel
            for identity in target[key]),
        interpretation='Descriptive formula-tree overlap only. A different benchmark name does not establish source-family independence; family-held-out evaluation must exclude every overlapping target operation family.')


def opportunity_gate(public):
    passing = [row['candidate_id'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >=
           PROTOCOL['minimum_calibrated_cycle_reduction'] and
           budget.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    c.require(public, 'Nonempty public PULPino Hanoi candidate set required')
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(passing), qualifying_candidate_ids=passing,
        source_family_audit=source_family_audit(public),
        public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(
            row['latency_features']['estimated_cycle_reduction'] for row in public),
        maximum_timed_replacements=max(budget.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def opportunity(root):
    root = Path(root)
    c.require(not (root / 'opportunity.json').exists(),
              'Preserve prior PULPino Hanoi opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged PULPino Hanoi opportunity gate rejected workload')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged PULPino Hanoi opportunity gate required')
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        require_zero_candidates(self.root)
        with registration():
            result = super().discover()
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == 'baseline',
                  'Candidate dispatch disabled during PULPino Hanoi qualification')
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
    context['workload_group'] = before['workload'] = GROUP
    context['context_transfer'] = 'Pinned PULPino twelve-plate recursive Hanoi input on the guarded PicoRV32 processor.'
    c.require(opportunity_gate(rows) == c.unseal(Path(root) / 'opportunity.json'),
              'Discovery and routed-baseline public projections differ')
    return rows, context, before


def audit(root):
    validate_inputs(root)
    with registration():
        return g.audit(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'opportunity',
        'baseline', 'public', 'freeze', 'audit'))
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
        for name, value in [('public.json', rows), ('context.json', context),
                            ('before.json', before)]:
            c.seal(args.root / name, value)
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
            elif args.command == 'baseline':
                result = evaluator.measure('baseline')
            else:
                result = evaluator.discover()
        finally:
            evaluator.runner.lock.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

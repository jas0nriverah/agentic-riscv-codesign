"""Pinned PULPino Sudoku workload on the existing guarded PicoRV32 pipeline.

Qualification reuses the existing extraction, lowering, continuous stack checks, and
whole-SoC evaluator. It is baseline-only; candidate dispatch is disabled.
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

SOURCE = 'isaforge/pulpino_sudoku_workload.py'
QUALIFIER = 'scripts/qualify_pulpino_sudoku.py'
TEST = 'tests/test_pulpino_sudoku_workload.py'
CONTRACT = 'docs/pulpino-sudoku-adapter-contract-2026-10-28.md'
PIN = 'benchmarks/pulpino-sudoku/SOURCE_PIN.json'
ADAPTER = 'benchmarks/pulpino-sudoku/adapter.c'
UPSTREAM_C = 'benchmarks/pulpino-sudoku/upstream/sudokusolver.c'
UPSTREAM_H = 'benchmarks/pulpino-sudoku/upstream/sudokusolver.h'
LICENSE = 'benchmarks/pulpino-sudoku/LICENSE'
ADAPTER_BUILDER = 'scripts/build_pulpino_sudoku_adapter.py'

WORKLOAD = 'pulpino-sudoku'
GROUP = 'pulpino-sudoku'
REPOSITORY = 'https://github.com/pulp-platform/pulpino'
UPSTREAM_COMMIT = '6631c49ba38a9258da44d6b120d902f7b81f9233'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
POOL_SIZE = 12
PARTITION = dict(bw.g.q.partition_spec(2304, 2432))
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
WORKLOADS = {WORKLOAD: str(c.ROOT / ADAPTER)}
FILE_BINDINGS = {
    UPSTREAM_C: ('9963bea3b49e367593b630a56c422ae3d5c5bf60dead03bf7a67a5110d498fb3',
                 '4895121a922b61c00a6cde00c3d38112c3101c3a', 5326),
    UPSTREAM_H: ('e78838129782eb11a05e086c4df6d81b24adf88c2bfbb5fbc8cd7246458be6af',
                 '3f6111cc5ababfa0cf732643c11c90ded0c60cab', 1096),
}
LICENSE_SHA256 = 'b41106a9d0de1cf6ab4ea56bedf677503085c0570248f37fe2cdf657a5e72601'

PROTOCOL = dict(
    schema='isaforge-pulpino-sudoku-v1', workload_group=GROUP,
    upstream_suite='PULPino sequential tests Sudoku solver', upstream_repository=REPOSITORY,
    upstream_commit=UPSTREAM_COMMIT, pool_size=POOL_SIZE,
    puzzle_dimensions='9x9', fixed_solves=2, maximum_solver_recursion_depth=82,
    minimum_calibrated_cycle_reduction=.005, minimum_timed_replacements=10,
    joint_gate='At least one same candidate satisfies both public opportunity minima.',
    unchanged_upstream_solver_and_fixed_puzzle=True,
    output_adapter='Freestanding ISAForge benchmark ABI; source test-suite registration, function-pointer timer harness and formatted output are removed.',
    correctness='Require solver completion and equality of every one of the 81 final grid cells to the pinned SUDOKUSOLVED array.',
    correctness_limitation='One fixed upstream puzzle, run twice as upstream does; no arbitrary puzzle or uniqueness verification.',
    library_runtime='No target libc or formatted output is linked; only original integer solver code and the pinned oracle are used.',
    timing_limitation='Includes fixed puzzle initialization, two resets and two solver calls; excludes generic harness warmup and post-run 81-cell verification.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    family_status='Recursive backtracking workload; no independent-family claim before source lineage and extracted formula-family review.',
)

PUBLIC = evidence._public
GUARDED_SOURCE = g.SOURCE
AUTHENTICATION_SOURCES = tuple(g.AUTHENTICATION_SOURCES)
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, ADAPTER, ADAPTER_BUILDER,
    UPSTREAM_C, UPSTREAM_H, LICENSE, HISTORY, GUARDED_SOURCE,
    *AUTHENTICATION_SOURCES, 'hardware/embench_firmware.c',
    'hardware/embench_memory.c', 'hardware/checked_sim.cpp',
    'scripts/reproduce_codesign.py', 'scripts/qualify_opportunity_sources.py',
)))


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def source_record():
    files = {}
    for path, (expected_sha, expected_blob, expected_size) in FILE_BINDINGS.items():
        raw = (c.ROOT / path).read_bytes()
        c.require(c.sha(c.ROOT / path) == expected_sha and
                  _git_blob_sha1(raw) == expected_blob and len(raw) == expected_size,
                  'Pinned PULPino Sudoku upstream bytes differ: ' + path)
        files[path] = dict(bytes=len(raw), sha256=expected_sha,
                           git_blob_sha1=expected_blob)
    c.require(c.sha(c.ROOT / LICENSE) == LICENSE_SHA256,
              'Pinned PULPino Solderpad license differs')
    header = (c.ROOT / UPSTREAM_H).read_text()
    c.require('#define SUDOKUSIZE 9' in header and 'SUDOKUSOLVED[SUDOKUSIZE*SUDOKUSIZE]' in header,
              'Pinned Sudoku dimensions/oracle declaration differs')
    pin = json.loads((c.ROOT / PIN).read_text())
    c.require(pin == dict(schema='isaforge-workload-source-pin-v1',
        suite='PULPino sequential tests Sudoku solver', repository=REPOSITORY,
        commit=UPSTREAM_COMMIT,
        license=dict(path=LICENSE, sha256=LICENSE_SHA256,
            status='Exact upstream Solderpad Hardware License, Version 0.51'),
        files=files,
        fixed_workload=dict(input='One fixed 9x9 puzzle in the upstream check() routine',
            repetitions=2, maximum_source_recursion_depth=82,
            oracle='Solver completion flag and every final cell match upstream SUDOKUSOLVED[81]'),
        adapter_sha256=c.sha(c.ROOT / ADAPTER)),
        'Pinned PULPino Sudoku source manifest differs')
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
              'Different PULPino Sudoku workload/compiler/memory/pool contract')
    c.require(plan.get('upstream') == source_record() and
              plan.get('pulpino_sudoku_protocol') == PROTOCOL,
              'Pinned PULPino Sudoku source/protocol differs')
    c.require(plan.get('inputs', {}).get('program.c') == c.sha(c.ROOT / ADAPTER),
              'PULPino Sudoku adapter input differs')
    for name in GATE_SOURCES:
        c.require(plan.get('source_bindings', {}).get(name) == c.sha(c.ROOT / name),
                  'PULPino Sudoku source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items()
                        if key != 'context_id'}) == plan.get('context_id'),
              'Invalid PULPino Sudoku context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound PULPino Sudoku input differs: ' + name)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic freestanding harness changed')
    for path, (expected_sha, _, _) in FILE_BINDINGS.items():
        target = root / 'inputs/upstream' / Path(path).relative_to('benchmarks/pulpino-sudoku/upstream')
        c.require(c.sha(target) == expected_sha,
                  'Upstream PULPino Sudoku input changed: ' + path)
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh PULPino Sudoku qualification root required')
    upstream = source_record()
    history = c.unseal(c.ROOT / HISTORY)
    prior_groups = {row.get('workload_group') for row in history.get('rows', [])}
    c.require(GROUP not in prior_groups,
              'PULPino Sudoku workload group already exists in the historical corpus')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'],
            stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    inputs = output / 'inputs'
    for source in FILE_BINDINGS:
        relative = Path(source).relative_to('benchmarks/pulpino-sudoku/upstream')
        destination = inputs / 'upstream' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / source, destination)
    plan['inputs'] = {path.name: c.sha(path) for path in sorted(inputs.iterdir())
                      if path.is_file()}
    # Hash nested test inputs separately; the generic plan uses flat input names.
    for path in sorted((inputs / 'upstream').rglob('*')):
        if path.is_file():
            plan['inputs']['upstream/' + path.relative_to(inputs / 'upstream').as_posix()] = c.sha(path)
    plan.update(upstream=upstream, workload_group=GROUP,
        qualification_order=[WORKLOAD],
        qualification_rule='One pinned 9x9 puzzle, run exactly twice on guarded RV32I/Zicsr PicoRV32; require 12 legal executable formulas and the unchanged joint 0.5%-plus-10-replacement opportunity gate. No candidate labels, retries or gate changes.',
        runtime_support='Original solve/safe/sudokusolver implementation and fixed puzzle are pinned; only the PULP test-suite harness/output are replaced by the freestanding ABI adapter.',
        source_family_review='Recursive backtracking workload; compare candidate expression families against historical measurements before claiming an independent family.',
        qualification_context='Unchanged PicoRV32/PCPI, RV32I/ILP32 -Os, synchronous 8 KiB RAM, 2304-byte program/data limit, 2432-byte stack floor, 5760-byte stack and three-route 12 MHz target. Partition bound by preflight link size and continuous runtime stack monitor.',
        pulpino_sudoku_protocol=PROTOCOL,
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
                  'Unexpected PULPino Sudoku public projection identity')
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
    c.require(public, 'Nonempty public PULPino Sudoku candidate set required')
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
              'Preserve prior PULPino Sudoku opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged PULPino Sudoku opportunity gate rejected workload')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged PULPino Sudoku opportunity gate required')
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
                  'Candidate dispatch disabled during PULPino Sudoku qualification')
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
    context['context_transfer'] = 'Pinned PULPino Sudoku fixed two-solve workload on the guarded PicoRV32 processor.'
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

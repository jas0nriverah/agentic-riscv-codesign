"""Pinned tiny-regex-c fixed tests on the existing guarded PicoRV32 pipeline.

Qualification reuses the existing extraction, lowering, stack checks, and
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

SOURCE = 'isaforge/tiny_regex_workload.py'
QUALIFIER = 'scripts/qualify_tiny_regex.py'
TEST = 'tests/test_tiny_regex_workload.py'
CONTRACT = 'docs/tiny-regex-adapter-contract-2026-10-28.md'
PIN = 'benchmarks/tiny-regex/SOURCE_PIN.json'
ADAPTER = 'benchmarks/tiny-regex/adapter.c'
UPSTREAM_C = 'benchmarks/tiny-regex/upstream/re.c'
UPSTREAM_H = 'benchmarks/tiny-regex/upstream/re.h'
UPSTREAM_TEST = 'benchmarks/tiny-regex/upstream/tests/test1.c'
LICENSE = 'benchmarks/tiny-regex/LICENSE'
CTYPE = 'benchmarks/tiny-regex/include/ctype.h'
STDIO = 'benchmarks/tiny-regex/include/stdio.h'
WORKLOAD = 'tiny-regex-fixed-suite'
GROUP = 'tiny-regex-fixed-suite'
REPOSITORY = 'https://github.com/kokke/tiny-regex-c'
UPSTREAM_COMMIT = 'f2632c6d9ed25272987471cdb8b70395c2460bdb'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
POOL_SIZE = 12
PARTITION = dict(bw.g.q.partition_spec(6400, 6528))
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
WORKLOADS = {WORKLOAD: str(c.ROOT / ADAPTER)}
FILE_BINDINGS = {
    UPSTREAM_C: ('846f87cd2527d7e1cdacddbcfed973cf953e50ba5d3ef50b69f592ed8622a34e',
                 '20d1474a16c4b2432433678c72f46ffc7a96c83f', 13850),
    UPSTREAM_H: ('8ba52081ac279e7e8cf9a60165e5ca9ff84f417f49c921dda7dd8635c2f720bd',
                 '69facc683f07b51309b1ece3bd6a7b2d172fee5a', 1721),
    UPSTREAM_TEST: ('216a4f2bbaa6bd097ea2a2cee8b1cdb0245bec5e503c1c49b50203ed834a6447',
                    '665c6cbe6b5de49ce351a00ea2c467e7a78b6785', 8053),
}
LICENSE_SHA256 = '88d9b4eb60579c191ec391ca04c16130572d7eedc4a86daa58bf28c6e14c9bcd'
SUITE_SHA256 = FILE_BINDINGS[UPSTREAM_TEST][0]

PROTOCOL = dict(
    schema='isaforge-tiny-regex-fixed-suite-v1', workload_group=GROUP,
    upstream_suite='tiny-regex-c', upstream_repository=REPOSITORY,
    upstream_commit=UPSTREAM_COMMIT, pool_size=POOL_SIZE, fixed_cases=76,
    minimum_calibrated_cycle_reduction=.005, minimum_timed_replacements=10,
    joint_gate='At least one same candidate satisfies both public opportunity minima.',
    unchanged_upstream_regex_and_test_vectors=True,
    output_adapter='Call renamed upstream test main; suppress printf/fprintf; retain upstream test expectations and failure-count result.',
    correctness='The unchanged test1.c checks expected match/failure and match length for 76 fixed regex/text pairs; nonzero upstream failure count fails verify_benchmark.',
    correctness_limitation='This is fixed-suite correctness only; it does not establish arbitrary-pattern or arbitrary-input correctness.',
    library_runtime='Freestanding C-locale ASCII isdigit/isalpha/isspace; the pinned input strings are ASCII; no host libc is linked.',
    timing_limitation='The measured region is the complete fixed 76-case suite, including the upstream test loop and a small adapter call; print calls are no-ops.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    family_status='Regex/text-processing source; not independent confirmation until exact extracted formula families are audited against historical pools.',
)

PUBLIC = evidence._public
GUARDED_SOURCE = g.SOURCE
AUTHENTICATION_SOURCES = tuple(g.AUTHENTICATION_SOURCES)
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, ADAPTER, UPSTREAM_C, UPSTREAM_H,
    UPSTREAM_TEST, LICENSE, CTYPE, STDIO, HISTORY, GUARDED_SOURCE,
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
                  'Pinned tiny-regex-c upstream bytes differ: ' + path)
        files[path] = dict(bytes=len(raw), sha256=expected_sha,
                           git_blob_sha1=expected_blob)
    c.require(c.sha(c.ROOT / LICENSE) == LICENSE_SHA256,
              'Pinned tiny-regex-c Unlicense differs')
    pin = json.loads((c.ROOT / PIN).read_text())
    expected_pin = dict(schema='isaforge-workload-source-pin-v1',
        suite='tiny-regex-c', repository=REPOSITORY, commit=UPSTREAM_COMMIT,
        license=dict(path=LICENSE, sha256=LICENSE_SHA256,
                     status='Unlicense; exact upstream file preserved'),
        files=files, fixed_suite=dict(cases=76,
            input_oracle='Every original regex, input string, expected match/failure, and expected match length remains in upstream/tests/test1.c',
            host_result='76/76 upstream assertions passed with the ISAForge freestanding adapter',
            case_set_sha256=SUITE_SHA256))
    c.require(pin == expected_pin, 'Pinned tiny-regex-c source manifest differs')
    return dict(suite='tiny-regex-c', repository=REPOSITORY,
        commit=UPSTREAM_COMMIT, files=files, license=LICENSE,
        license_sha256=LICENSE_SHA256, fixed_cases=76,
        fixed_suite_sha256=SUITE_SHA256)


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
              'Different tiny-regex workload/compiler/memory/pool contract')
    c.require(plan.get('upstream') == source_record() and
              plan.get('tiny_regex_protocol') == PROTOCOL,
              'Pinned tiny-regex source/protocol differs')
    c.require(plan.get('inputs', {}).get('program.c') == c.sha(c.ROOT / ADAPTER),
              'Tiny-regex adapter input differs')
    for name in GATE_SOURCES:
        c.require(plan.get('source_bindings', {}).get(name) == c.sha(c.ROOT / name),
                  'Tiny-regex source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items()
                        if key != 'context_id'}) == plan.get('context_id'),
              'Invalid tiny-regex context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound tiny-regex input differs: ' + name)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic freestanding harness changed')
    for path, (expected_sha, _, _) in FILE_BINDINGS.items():
        target = root / 'inputs/upstream' / Path(path).relative_to('benchmarks/tiny-regex/upstream')
        c.require(c.sha(target) == expected_sha,
                  'Upstream tiny-regex input changed: ' + path)
    c.require(c.sha(root / 'inputs/re.h') == FILE_BINDINGS[UPSTREAM_H][0],
              'Test-suite include copy differs from pinned upstream header')
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh tiny-regex qualification root required')
    upstream = source_record()
    history = c.unseal(c.ROOT / HISTORY)
    prior_groups = {row.get('workload_group') for row in history.get('rows', [])}
    c.require(GROUP not in prior_groups,
              'Tiny-regex fixed-suite workload group already exists in the historical corpus')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'],
            stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    inputs = output / 'inputs'
    for source in (UPSTREAM_C, UPSTREAM_H, UPSTREAM_TEST):
        relative = Path(source).relative_to('benchmarks/tiny-regex/upstream')
        destination = inputs / 'upstream' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / source, destination)
    shutil.copyfile(c.ROOT / UPSTREAM_H, inputs / 're.h')
    shutil.copyfile(c.ROOT / CTYPE, inputs / 'ctype.h')
    shutil.copyfile(c.ROOT / STDIO, inputs / 'stdio.h')
    plan['inputs'] = {path.name: c.sha(path) for path in sorted(inputs.iterdir())
                      if path.is_file()}
    # Hash nested test inputs separately; the generic plan uses flat input names.
    for path in sorted((inputs / 'upstream').rglob('*')):
        if path.is_file():
            plan['inputs']['upstream/' + path.relative_to(inputs / 'upstream').as_posix()] = c.sha(path)
    plan.update(upstream=upstream, workload_group=GROUP,
        qualification_order=[WORKLOAD],
        qualification_rule='One pinned original 76-case suite on guarded RV32I/Zicsr PicoRV32; require 12 legal executable formulas and the unchanged joint 0.5%-plus-10-replacement opportunity gate. No candidate labels, retries or gate changes.',
        runtime_support='Original regex implementation and test vectors are copied unchanged. Only output is suppressed and ASCII C-locale ctype functions are supplied freestanding.',
        source_family_review='Regex/text-processing lead; extracted operation-tree overlap must be audited before any independent-family claim.',
        qualification_context='Unchanged PicoRV32/PCPI, RV32I/ILP32 -Os, synchronous 8 KiB RAM, 6400-byte program/data limit, 6528-byte stack floor and three-route 12 MHz target.',
        tiny_regex_protocol=PROTOCOL,
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
                  'Unexpected tiny-regex public projection identity')
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
        interpretation='Descriptive formula-tree overlap only. This regex/text-processing fixed-suite workload is not counted as an independent source family; family-held-out evaluation must exclude every overlapping target operation family.')


def opportunity_gate(public):
    passing = [row['candidate_id'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >=
           PROTOCOL['minimum_calibrated_cycle_reduction'] and
           budget.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    c.require(public, 'Nonempty public tiny-regex candidate set required')
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
              'Preserve prior tiny-regex opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged tiny-regex opportunity gate rejected workload')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged tiny-regex opportunity gate required')
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
                  'Candidate dispatch disabled during tiny-regex qualification')
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
    context['context_transfer'] = 'Pinned tiny-regex-c 76-case fixed test suite on the guarded PicoRV32 processor.'
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

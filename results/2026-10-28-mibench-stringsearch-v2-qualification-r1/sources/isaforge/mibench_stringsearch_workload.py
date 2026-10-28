"""Pinned MiBench Boyer-Moore workload on the guarded PicoRV32 pipeline.

Qualification is baseline-only. Candidate dispatch remains unavailable until
an independently reviewed zero-label release is frozen and pushed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil

from . import blind_workload as bw
from . import budgeted_selection as budget
from . import campaign_evidence as evidence
from . import codesign as c
from . import guarded_workload as g

SOURCE = 'isaforge/mibench_stringsearch_workload.py'
QUALIFIER = 'scripts/qualify_mibench_stringsearch.py'
TEST = 'tests/test_mibench_stringsearch_workload.py'
CONTRACT = 'docs/mibench-stringsearch-adapter-contract-2026-10-27.md'
PIN = 'benchmarks/mibench/stringsearch/MIBENCH_SOURCE_PIN.json'
ADAPTER = 'benchmarks/mibench/stringsearch/adapter.c'
PROGRAM = 'benchmarks/mibench/stringsearch/pbmsrch_small.c'
LICENSE = 'benchmarks/mibench/stringsearch/LICENSE'
WORKLOAD = 'mibench-stringsearch-small'
GROUP = 'mibench-stringsearch-pbm'
UPSTREAM_COMMIT = '092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57'
SOURCE_SHA256 = 'e2bd846a0ae52e2a340c3885379dd06582dca26daf2b691aae0ab6f0d45fc4bb'
SOURCE_BLOB_SHA1 = '78be8b228a7351eeab54adee72024b1da8842790'
LICENSE_SHA256 = 'b43faa73aa52be87b3121a49495c833d728f10df7652b30d02a9d8578c56f819'
ORACLE_OFFSETS_SHA256 = 'dde521d64680496b747ec7a8dbbd61fa37c0b77c8c19175e6edeca9b2a5c299d'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
POOL_SIZE = 12
PARTITION = dict(bw.PARTITION)
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
WORKLOADS = {WORKLOAD: str(c.ROOT / ADAPTER)}
PROTOCOL = dict(
    schema='isaforge-mibench-stringsearch-v1', workload_group=GROUP,
    upstream_suite='MiBench', pool_size=POOL_SIZE,
    minimum_calibrated_cycle_reduction=.005, minimum_timed_replacements=10,
    joint_gate='At least one same candidate satisfies both public opportunity minima.',
    unchanged_search_source=True, unchanged_fixed_inputs=True,
    output_adapter='Renamed upstream main; printf/putchar map to a bounded offset-capture shim; only benchmark ABI functions are added.',
    correctness='The shim records actual hit/miss and returned pointer offset for all 57 upstream cases; verify_benchmark compares these with independently derived Python str.find offsets after the cycle counter stops.',
    correctness_limitation='Offset checks use a pinned independent oracle over the fixed literal input; this does not establish general-input correctness.',
    timing_limitation='The small output-capture shim runs inside benchmark() and contributes constant bookkeeping overhead to measured cycles.',
    library_runtime='Freestanding bytewise strlen/strncmp implementations are part of the source-bound adapter; no host libc is linked.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    family_status='Provisional Pratt-Boyer-Moore implementation in text search; exact target formula families must be audited against historical pools before this can count as independent confirmation.',
)

PUBLIC = evidence._public
GUARDED_SOURCE = g.SOURCE
AUTHENTICATION_SOURCES = tuple(g.AUTHENTICATION_SOURCES)
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, ADAPTER, PROGRAM, LICENSE,
    HISTORY, GUARDED_SOURCE, *AUTHENTICATION_SOURCES,
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
    'hardware/checked_sim.cpp', 'scripts/reproduce_codesign.py',
    'scripts/qualify_opportunity_sources.py',
)))


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


def source_record():
    source = c.ROOT / PROGRAM
    raw = source.read_bytes()
    blob_sha1 = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    c.require(c.sha(source) == SOURCE_SHA256 and blob_sha1 == SOURCE_BLOB_SHA1,
              'Pinned MiBench stringsearch source bytes differ')
    c.require(c.sha(c.ROOT / LICENSE) == LICENSE_SHA256,
              'Pinned MiBench stringsearch license notice differs')
    manifest = json.loads((c.ROOT / PIN).read_text())
    expected = dict(
        schema='isaforge-workload-source-pin-v1', suite='MiBench',
        repository='https://github.com/embecosm/mibench',
        commit=UPSTREAM_COMMIT, source='office/stringsearch/pbmsrch_small.c',
        vendored_path=PROGRAM,
        program=dict(sha256=SOURCE_SHA256, git_blob_sha1=SOURCE_BLOB_SHA1,
                    bytes=len(raw)),
        license=dict(path=LICENSE, sha256=LICENSE_SHA256,
            status='Ambiguous upstream notices preserved verbatim: source claims public domain; directory says assume GPL, without a version. Treat conservatively as GPL; do not assert a specific GPL version.'),
        oracle=dict(method='Independent Python str.find offsets for the 57 fixed pattern/text pairs parsed from the pinned source',
            cases=57, hits=29, misses=28, offsets_sha256=ORACLE_OFFSETS_SHA256))
    c.require(manifest == expected, 'Pinned MiBench source manifest differs')
    return dict(suite='MiBench', repository=manifest['repository'],
        commit=UPSTREAM_COMMIT, source=PROGRAM, source_sha256=SOURCE_SHA256,
        source_git_blob_sha1=SOURCE_BLOB_SHA1, license=LICENSE,
        license_sha256=LICENSE_SHA256, oracle_offsets_sha256=ORACLE_OFFSETS_SHA256)


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan.get('workload') == WORKLOAD and
              plan.get('workload_group') == GROUP and
              plan.get('pool_size') == POOL_SIZE and
              plan.get('memory_partition') == PARTITION and
              plan.get('compiler_flags') == list(g.q.bounded.compact.FLAGS),
              'Different MiBench stringsearch architecture/pool contract')
    c.require(plan.get('upstream') == source_record() and
              plan.get('mibench_stringsearch_protocol') == PROTOCOL,
              'Pinned MiBench stringsearch protocol differs')
    c.require(plan.get('inputs', {}).get('program.c') == c.sha(c.ROOT / ADAPTER) and
              plan.get('inputs', {}).get('pbmsrch_small.c') == SOURCE_SHA256,
              'Adapter or upstream workload input hash differs')
    for name in GATE_SOURCES:
        c.require(plan.get('source_bindings', {}).get(name) == c.sha(c.ROOT / name),
                  'MiBench stringsearch source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) ==
              plan['context_id'], 'Invalid MiBench stringsearch context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound MiBench stringsearch input differs: ' + name)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic freestanding firmware harness must remain unchanged')
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh MiBench stringsearch qualification root required')
    source_record()
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'],
            stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    shutil.copyfile(c.ROOT / PROGRAM, output / 'inputs/pbmsrch_small.c')
    plan['inputs'] = {path.name: c.sha(path) for path in
                      sorted((output / 'inputs').iterdir()) if path.is_file()}
    plan.update(
        upstream=source_record(), workload_group=GROUP,
        qualification_order=[WORKLOAD],
        qualification_rule='One pinned MiBench small stringsearch binary on the unchanged guarded RV32I pipeline; require 12 legal executable formulas and the existing joint 0.5%/10-replacement opportunity gate. No fallback, gate changes, retries, or candidate labels.',
        runtime_support='Original pbmsrch_small.c and its literal 57 test pairs; adapter only renames main, maps console output to offset capture, and supplies freestanding strlen/strncmp.',
        source_family_review='Provisional text-search transfer. The upstream algorithm differs from previously screened BEEBS strstr, but exact emitted formula-tree overlap must be sealed before any confirmation claim.',
        qualification_context='Unchanged PicoRV32/PCPI, RV32I/ILP32 -Os, synchronous 8 KiB RAM, 6400-byte program/data cap, 6528-byte stack floor and existing three-route 12 MHz policy.',
        mibench_stringsearch_protocol=PROTOCOL,
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
                  'Unexpected MiBench public projection identity')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


def discovery_public(root):
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = PUBLIC(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return budget.public_rows(rows)


def opportunity_gate(public):
    passing = [row['name'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >=
           PROTOCOL['minimum_calibrated_cycle_reduction'] and
           budget.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    c.require(public, 'Nonempty public MiBench candidate set required')
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(passing), qualifying_candidate_ids=passing,
        public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(
            row['latency_features']['estimated_cycle_reduction'] for row in public),
        maximum_timed_replacements=max(budget.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def opportunity(root):
    root = Path(root)
    c.require(not (root / 'opportunity.json').exists(),
              'Preserve prior MiBench opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged MiBench opportunity gate rejected workload')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged MiBench opportunity gate required')
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
                  'Candidate dispatch disabled during MiBench qualification')
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
    context['context_transfer'] = 'Pinned MiBench Pratt-Boyer-Moore fixed-input workload on the unchanged guarded PicoRV32 processor.'
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
        c.require(args.reference_root is not None, 'Preserved reference required')
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

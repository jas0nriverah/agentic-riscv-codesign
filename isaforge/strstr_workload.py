"""Baseline-only qualification adapter for the pinned BEEBS strstr workload.

The upstream C source, fixed input, repeated-search wrapper and scalar verifier
remain byte-identical. This module reuses the guarded RV32I BEEBS pipeline and
adds only source registration, provenance, and a dispatch-disabled opportunity
gate. It never measures a custom candidate.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import time

from . import blind_workload as bw
from . import budgeted_selection as budget
from . import campaign_evidence as evidence
from . import codesign as c
from . import guarded_workload as g

SOURCE = 'isaforge/strstr_workload.py'
QUALIFIER = 'scripts/qualify_strstr.py'
TEST = 'tests/test_strstr_workload.py'
CONTRACT = 'docs/strstr-adapter-contract-2026-10-26.md'
PIN = 'benchmarks/beebs/strstr/STRSTR_SOURCE_PIN.json'
WORKLOAD = 'strstr'
GROUP = 'beebs-strstr'
PROGRAM = 'benchmarks/beebs/strstr/libstrstr.c'
UPSTREAM_COMMIT = '049ded9f3aeb5591f553879d3a0376b8614e9422'
SOURCE_SHA256 = 'faf4975fe43599156ca3befe8bba914d8db14de80f54ff24dba3ca60c4d0e974'
SOURCE_BLOB_SHA1 = '22a3773c4375e87d724ecd420a381f1130f000dc'
LICENSE_SHA256 = '8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903'
LICENSE = 'benchmarks/beebs/COPYING'
POOL_SIZE = 12
PARTITION = bw.PARTITION
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
WORKLOADS = {WORKLOAD: ('libstrstr.c', SOURCE_SHA256)}
PROTOCOL = dict(
    schema='isaforge-beebs-strstr-v1', workload_group=GROUP,
    pool_size=POOL_SIZE, minimum_calibrated_cycle_reduction=.005,
    minimum_timed_replacements=10,
    joint_gate='At least one same candidate satisfies both public opportunity minima.',
    unchanged_source=True, unchanged_input=True, unchanged_wrapper=True,
    unchanged_verifier=True,
    correctness='Original BEEBS scalar verifier requires eight calls; host preflight independently checks seven returned offsets and the final miss.',
    verifier_limitation='The upstream target verifier checks only the count, not individual match locations. Host preflight checks locations for this fixed input; this does not strengthen or replace the target verifier.',
    original_input='text="abbaabbaababadcsdabbacasdaabbbaabbadabbacbbbaabbadabbacasdaabbbaabba"; needle="abba"; original repeated strstr(f+1,needle) wrapper.',
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1, 2, 3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    candidate_dispatch='Disabled by the workload evaluator and CLI during qualification.',
    family_status='Provisional distinct implementation within text processing; not counted as an independent confirmatory family until the source taxonomy and formula-family audit pass.',
)
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, PROGRAM, LICENSE, HISTORY,
    bw.SOURCE, bw.GUARDED_SOURCE, 'hardware/embench_firmware.c',
    'scripts/reproduce_codesign.py', 'scripts/blind_campaign.py',
    'isaforge/observed_command.py', *g.AUTHENTICATION_SOURCES,
)))


def source_record():
    path = c.ROOT / PROGRAM
    raw = path.read_bytes()
    blob_sha1 = hashlib.sha1(
        b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    c.require(c.sha(path) == SOURCE_SHA256 and blob_sha1 == SOURCE_BLOB_SHA1,
              'Pinned BEEBS strstr source bytes differ')
    c.require(c.sha(c.ROOT / LICENSE) == LICENSE_SHA256,
              'Pinned BEEBS GPL license differs')
    manifest = json.loads((c.ROOT / PIN).read_text())
    c.require(manifest == dict(schema='isaforge-workload-source-pin-v1',
        suite='BEEBS', repository='https://github.com/mageec/beebs',
        commit=UPSTREAM_COMMIT, source='src/strstr/libstrstr.c',
        vendored_path=PROGRAM,
        program=dict(sha256=SOURCE_SHA256, git_blob_sha1=SOURCE_BLOB_SHA1,
                     bytes=len(raw)),
        license=dict(path=LICENSE, sha256=LICENSE_SHA256,
                     license='GPL-3.0-or-later')),
        'Pinned BEEBS strstr source manifest differs')
    return dict(suite='BEEBS', commit=UPSTREAM_COMMIT, source=PROGRAM,
                source_sha256=SOURCE_SHA256, source_git_blob_sha1=SOURCE_BLOB_SHA1,
                license=LICENSE, license_sha256=LICENSE_SHA256)


@contextmanager
def registration():
    previous = bw.SOURCE, bw.WORKLOADS, bw.POOL_SIZE
    bw.SOURCE, bw.WORKLOADS, bw.POOL_SIZE = SOURCE, WORKLOADS, POOL_SIZE
    try:
        with bw.registration(WORKLOAD):
            previous_public = evidence._public
            try:
                yield
            finally:
                evidence._public = previous_public
    finally:
        bw.SOURCE, bw.WORKLOADS, bw.POOL_SIZE = previous


def check_plan(plan):
    with registration():
        bw.check_plan(plan)
    c.require(plan.get('workload') == WORKLOAD and
              plan.get('workload_group') == GROUP and
              plan.get('upstream') == dict(suite='BEEBS', commit=UPSTREAM_COMMIT,
                  source=PROGRAM, source_sha256=SOURCE_SHA256),
              'Pinned BEEBS strstr context differs')
    c.require(plan.get('strstr_protocol') == PROTOCOL and
              plan.get('memory_partition') == PARTITION and
              plan.get('pool_size') == POOL_SIZE,
              'Fixed strstr qualification protocol required')
    c.require(plan.get('inputs', {}).get('program.c') == SOURCE_SHA256,
              'Original full strstr source must remain unchanged')
    source_bindings = plan.get('source_bindings', {})
    for name in GATE_SOURCES:
        c.require(source_bindings.get(name) == c.sha(c.ROOT / name),
                  'Strstr source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items() if key != 'context_id'}) ==
              plan['context_id'], 'Invalid strstr context identity')
    source_record()


def require_zero_candidates(root):
    root = Path(root)
    c.require(not list((root / 'attempt-ledger').glob('candidate_*')) and
              not list((root / 'measurements').glob('candidate_*')),
              'Qualification requires zero candidate attempts')


def validate_inputs(root):
    root = Path(root)
    require_zero_candidates(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              bw.harness_source(WORKLOAD).encode(),
              'Generic harness plus declared no-op warmup ABI adapter required')
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound strstr input differs: ' + name)
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh strstr qualification root required')
    source_record()
    with registration():
        plan = bw.prepare(reference, output, WORKLOAD)
    plan.pop('context_id')
    plan.update(upstream=dict(suite='BEEBS', commit=UPSTREAM_COMMIT,
                              source=PROGRAM, source_sha256=SOURCE_SHA256),
        source_pin=source_record(), workload_group=GROUP,
        qualification_order=[WORKLOAD],
        qualification_rule='Single pinned original-input BEEBS strstr source, unchanged 12-formula legal/calibrated pool and same-candidate 0.5%/10-replacement opportunity gate; no retries, new inputs, gate changes, or candidate labels.',
        runtime_support='Byte-identical full BEEBS source and original fixed input/wrapper/verifier; existing generic harness plus no-op warm_caches ABI hook only.',
        output_check=PROTOCOL['correctness'], strstr_protocol=PROTOCOL,
        source_family_review='Distinct GNU libc substring-search implementation versus the consumed Cesanta/Embecosm regex engine; still only a provisional same-domain transfer family until the bounded source/formula audit is sealed.',
        qualification_context='Unchanged PicoRV32/PCPI, RV32I/ILP32 -Os, 8 KiB synchronous RAM, 6400-byte program/data cap, 6528-byte stack floor and existing 12 MHz/three-route policy.',
        history_sha256=c.sha(c.ROOT / HISTORY))
    plan['source_bindings'] = dict(plan['source_bindings'])
    plan['inputs'] = {path.name: c.sha(path) for path in (output / 'inputs').iterdir()}
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    passing = [row['name'] for row in public
        if row['latency_features']['estimated_cycle_reduction'] >=
           PROTOCOL['minimum_calibrated_cycle_reduction'] and
           budget.occurrence_count(row) >= PROTOCOL['minimum_timed_replacements']]
    c.require(public, 'Nonempty public candidate set required')
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(passing), qualifying_candidate_ids=passing,
        public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(
            row['latency_features']['estimated_cycle_reduction'] for row in public),
        maximum_timed_replacements=max(budget.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def discovery_public(root):
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = bw.public_projection(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return budget.public_rows(rows)


def opportunity(root):
    root = Path(root)
    c.require(not (root / 'opportunity.json').exists(),
              'Preserve prior strstr opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged public useful-opportunity gate rejected strstr')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged strstr opportunity gate required')
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            result = super().discover()
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == 'baseline',
                  'Candidate dispatch disabled during strstr qualification')
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
        rows, context, before = bw.baseline_public(root)
    context['workload_group'] = before['workload'] = GROUP
    context['context_transfer'] = 'Original fixed-input BEEBS literal substring search under the unchanged guarded RV32I processor.'
    c.require(opportunity_gate(rows) == c.unseal(Path(root) / 'opportunity.json'),
              'Discovery and routed-baseline public projections differ')
    return rows, context, before


def audit(root):
    with registration():
        return bw.audit(root)


def pack(root, snapshot, *, prelabel_commit=None):
    with registration():
        return bw.pack(root, snapshot, prelabel_commit=prelabel_commit)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'opportunity',
        'baseline', 'public', 'freeze', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    args = parser.parse_args(argv)
    began, status = time.monotonic(), 'interrupted'
    try:
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
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == 'freeze':
                    check_opportunity(args.root)
                    with registration():
                        result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
                elif args.command == 'baseline':
                    result = evaluator.measure('baseline')
                elif args.command == 'audit':
                    result = audit(args.root)
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
                candidate=None, status=status, elapsed_seconds=time.monotonic() - began,
                scope='Complete CLI operation through lock close; excludes Python startup and final timer write; overlaps inner scopes.'))


if __name__ == '__main__':
    main()

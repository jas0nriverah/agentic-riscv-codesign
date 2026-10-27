"""Read-only reconstruction of the preserved BEEBS strstr discovery rejection."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import assembly_lowering as lowering
from isaforge import codesign as c
from isaforge import latency_features as latency
from isaforge import strstr_workload as workload

DEFAULT_QUALIFICATION = ROOT / 'results/2026-10-26-strstr-qualification'
DEFAULT_OUTPUT = ROOT / 'results/2026-10-26-strstr-discovery-diagnosis'


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _archive_files(qualification: Path):
    record = c.unseal(qualification / 'archive-manifest.json')
    archive = qualification / record['archive']
    c.require(archive.is_file() and archive.stat().st_size == record['bytes'] and
              c.sha(archive) == record['sha256'], 'Raw archive hash differs')
    expected = {row['path']: row for row in record['files']}
    c.require(len(expected) == len(record['files']), 'Duplicate archive path')
    found = {}
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream.getmembers():
            path = PurePosixPath(member.name)
            c.require(not path.is_absolute() and '..' not in path.parts,
                      'Unsafe archive path')
            if member.isdir():
                continue
            c.require(member.isfile() and member.name in expected and
                      member.name not in found and member.size <= 16 * 1024 * 1024,
                      'Unexpected, duplicate, or oversized archive member')
            handle = stream.extractfile(member)
            c.require(handle is not None, 'Cannot read archive member')
            raw = handle.read()
            row = expected[member.name]
            c.require(len(raw) == row['bytes'] and _sha(raw) == row['sha256'],
                      'Archived member hash differs: ' + member.name)
            found[member.name] = raw
    c.require(set(found) == set(expected), 'Archive file inventory differs')
    return record, found


def analyze(qualification: Path, output: Path):
    qualification, output = qualification.resolve(), output.resolve()
    c.require(qualification == DEFAULT_QUALIFICATION.resolve() and
              output.is_relative_to(ROOT) and not output.exists() and
              output != qualification, 'Fresh output and exact qualification required')
    outcome = c.unseal(qualification / 'qualification.json')
    protocol = c.unseal(qualification / 'protocol.json')
    c.require(outcome['status'] == 'rejected' and
              outcome['records'][0].get('failed_phase') == 'discover' and
              outcome['target_candidate_attempts'] == 0 and
              outcome['protocol_sha256'] == c.sha(qualification / 'protocol.json') and
              protocol.get('candidate_dispatch_enabled') is False,
              'Expected dispatch-disabled discovery rejection')
    for name, digest in protocol['source_bindings'].items():
        c.require(c.sha(ROOT / name) == digest and
                  c.sha(qualification / 'sources' / name) == digest,
                  'Qualification source snapshot differs: ' + name)
    archive_record, files = _archive_files(qualification)
    plan = json.loads(files['plan.json'])
    c.require(plan.get('context_id') == c.digest(
        {key: value for key, value in plan.items() if key != 'context_id'}),
        'Archived prepared plan identity differs')
    c.require(plan.get('workload') == workload.WORKLOAD and
              plan.get('workload_group') == workload.GROUP and
              plan.get('pool_size') == workload.POOL_SIZE and
              plan.get('strstr_protocol') == workload.PROTOCOL,
              'Archived workload or frozen pool protocol differs')
    source_recovery = {}
    backfills = {}
    for name, digest in plan['source_bindings'].items():
        path = PurePosixPath(name)
        c.require(not path.is_absolute() and '..' not in path.parts,
                  'Unsafe source-binding path')
        key = 'sources/' + path.as_posix()
        if key in files:
            raw = files[key]
            recovery = 'archived_source_snapshot'
        elif 'inputs/' + path.name in files and _sha(files['inputs/' + path.name]) == digest:
            raw = files['inputs/' + path.name]
            recovery = 'archived_input_copy'
        else:
            current = ROOT / path.as_posix()
            c.require(current.is_file() and c.sha(current) == digest,
                      'No hash-matching source recovery for: ' + name)
            raw = current.read_bytes()
            recovery = 'posthoc_hash_verified_workspace_backfill'
            backfills[name] = raw
        c.require(_sha(raw) == digest,
                  'Prepared source snapshot differs: ' + name)
        source_recovery[name] = recovery
    for name, digest in plan['inputs'].items():
        key = 'inputs/' + name
        c.require(key in files and _sha(files[key]) == digest,
                  'Prepared input snapshot differs: ' + name)

    folder = 'discovery/attempt-000/'
    assembly = files[folder + 'program.s'].decode()
    marked, sites = lowering.mark_assembly(assembly)
    c.require(marked.encode() == files[folder + 'marked.S'],
              'Marked assembly does not reconstruct')
    site_map = lowering.map_sites(sites,
        files[folder + 'marked/symbols.txt'].decode())
    program = lowering.read_program(
        files[folder + 'marked/disassembly.txt'].decode())
    profile = json.loads(files[folder + 'profile/simulation.json'])
    extracted = lowering.extract(program, profile, site_map, workload.POOL_SIZE)
    guarded = workload.g.guard.filter_executable_candidates(extracted, sites)
    table = latency.latency_table(json.loads(files['inputs/latency-calibration.json']))
    calibrated, uncalibrated = [], []
    for candidate in guarded['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency.instruction_latency(program[int(pc, 16)], table)
        except ValueError:
            uncalibrated.append(candidate['formula'])
        else:
            calibrated.append(candidate)

    runs = Counter({int(pc): count for pc, count in profile['region_counts'].items()})
    starts = set(profile['block_starts'])
    for pc, instruction in program.items():
        if instruction['op'] == 'unknown':
            starts.update((pc, pc + 4))
        if pc in site_map:
            instruction['symbol'] = site_map[pc]['function']
    sensitivity = {str(size): len(lowering.discovery.extractCandidates(
        program, runs, starts, maxSize=size)) for size in range(2, 7)}
    validation = json.loads(files[folder + 'marked/validation.json'])
    original_validation = json.loads(files[folder + 'original/validation.json'])
    c.require(validation == original_validation and
              validation['isa']['custom_static_sites'] == 0 and
              profile['trapped'] is False and profile['words'][1] == 8 and
              profile['stack_violations'] == 0,
              'Original discovery profile/check is invalid')
    c.require(extracted['raw_formula_count'] == 0 and
              extracted['executable_formula_count'] == 0 and
              guarded['executable_formula_count'] == 0 and
              not calibrated and not uncalibrated and
              all(count == 0 for count in sensitivity.values()),
              'Reconstructed extraction does not match the rejection')

    diagnosis = dict(schema='isaforge-strstr-discovery-diagnosis-v1',
        qualification_sha256=c.sha(qualification / 'qualification.json'),
        protocol_sha256=c.sha(qualification / 'protocol.json'),
        raw_archive_sha256=archive_record['sha256'],
        workload_group=workload.GROUP, source_sha256=workload.SOURCE_SHA256,
        qualification_status='rejected_at_discovery',
        frozen_pool_requirement=workload.POOL_SIZE,
        raw_formulas=extracted['raw_formula_count'],
        executable_formulas=extracted['executable_formula_count'],
        relocation_safe_formulas=guarded['executable_formula_count'],
        calibrated_formulas=len(calibrated), uncalibrated_formulas=uncalibrated,
        raw_connected_formulas_by_max_ops=sensitivity,
        max_ops_sensitivity_scope='Raw connected formulas before whole-statement, relocation, calibration, and occurrence filters; diagnostic only. Frozen max remains four.',
        discovery_profile=dict(cycles=profile['host_cycles'],
            instructions=profile['words'][3], benchmark_result_u32=profile['words'][1],
            max_stack_bytes=profile['max_stack_bytes'],
            stack_violations=profile['stack_violations'],
            program_and_bss_end=validation['program_and_bss_end'],
            custom_static_sites=validation['isa']['custom_static_sites']),
        target_candidate_attempts=0, candidate_speedup_area_timing='not_measured',
        opportunity_gate='not_reached', routed_baseline='not_reached',
        finding='The original input/verifier passes and discovery-profile memory checks pass, but no connected legal two-or-more-operation candidate exists. Caps from two through six still yield zero raw formulas; this is workload opportunity scarcity, not calibration loss or a twelve-candidate shortlist shortage.',
        model_fits=0, candidate_outcomes_read=0)
    output.mkdir(parents=True)
    closure_root = output / 'qualification-source-closure-amendment'
    closure_root.mkdir()
    for name, raw in sorted(backfills.items()):
        destination = closure_root / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    amendment = dict(
        schema='isaforge-qualification-source-closure-amendment-v1',
        qualification_sha256=diagnosis['qualification_sha256'],
        original_archive_sha256=archive_record['sha256'],
        note=('The original raw archive omitted some plan-bound source snapshots. '
              'This append-only amendment supplies only exact-SHA256 matches to '
              'the archived plan bindings; the original qualification archive is unchanged.'),
        source_recovery=source_recovery,
        backfilled_files={name: dict(path='sources/' + name,
            sha256=_sha(raw), bytes=len(raw)) for name, raw in sorted(backfills.items())})
    c.seal(closure_root / 'qualification-source-closure-amendment.json', amendment)
    diagnosis['analysis_script_sha256'] = c.sha(Path(__file__))
    diagnosis['source_closure_amendment_sha256'] = c.sha(
        closure_root / 'qualification-source-closure-amendment.json')
    c.seal(output / 'diagnosis.json', diagnosis)
    readme = '''# BEEBS `strstr` discovery rejection

The original pinned BEEBS source, fixed input, wrapper, and target count
verifier passed the baseline-only discovery run. The instrumented discovery
profile used **3,658 cycles / 644 instructions**, returned the expected count
of eight, used at most 64 bytes of stack, and reported no stack violations or
custom static sites. Its program-plus-BSS endpoint was 560 bytes. These are
discovery-profile values, not a separately routed baseline measurement.

The frozen extractor found **zero** connected formulas with operation caps
from two through six. Raw, executable, relocation-safe, and calibrated formula
counts are all zero. The unchanged 12-candidate pool and public opportunity
gates were therefore not reached. Candidate dispatch was disabled throughout;
there are no candidate cycle, speedup, area, timing, or correctness labels.

Reproduce the read-only archived-profile reconstruction from the repository
root with:

```sh
../work/audit-venv/bin/python scripts/analyze_strstr_discovery_rejection.py
```

The sealed [diagnosis](diagnosis.json) binds the qualification and raw archive.
The original archive omitted some plan-bound source snapshots; the append-only
`qualification-source-closure-amendment/` records each recovery method and
includes workspace backfills only when their SHA-256 exactly matches the
archived plan binding. The original qualification files and archive remain
unchanged. The result manifest authenticates the diagnosis, README, and
amendment files.
'''
    (output / 'README.md').write_text(readme)
    c.seal(output / 'manifest.json', {path.relative_to(output).as_posix(): c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file() and
        path.name not in ('manifest.json', 'manifest.json.sha256')})
    return diagnosis


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification-root', type=Path,
                        default=DEFAULT_QUALIFICATION)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(json.dumps(analyze(args.qualification_root, args.output), indent=2))


if __name__ == '__main__':
    main()

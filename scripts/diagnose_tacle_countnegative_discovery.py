"""Authenticate and reconstruct the preserved countnegative discovery rejection offline."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import (assembly_lowering as lowering, codesign as c,
    latency_features, relocation_guard, speedup_corpus)
from isaforge import tacle_countnegative_workload as workload

QUALIFICATION = ROOT / 'results/2026-10-27-countnegative-qualification'
HISTORY = ROOT / 'results/2026-10-26-lift-selection-corpus/corpus.json'
NATIVE = ROOT / 'generated/tacle-countnegative-2026-10-27'
DEFAULT_OUTPUT = ROOT / 'results/2026-10-27-countnegative-discovery-diagnosis'


def _inventory(folder: Path) -> dict[str, str]:
    return {path.relative_to(folder).as_posix(): c.sha(path)
            for path in sorted(folder.rglob('*')) if path.is_file() and
            path.name not in ('manifest.json', 'manifest.json.sha256')}


def _authenticate_qualification() -> tuple[dict, dict, dict]:
    manifest = c.unseal(QUALIFICATION / 'manifest.json')
    c.require(manifest == _inventory(QUALIFICATION),
              'Qualification evidence inventory differs')
    protocol = c.unseal(QUALIFICATION / 'protocol.json')
    record = c.unseal(QUALIFICATION / 'qualification.json')
    archive = c.unseal(QUALIFICATION / 'archive-manifest.json')
    c.require(record['protocol_sha256'] == c.sha(QUALIFICATION / 'protocol.json') and
              record['status'] == 'rejected' and record['target_candidate_attempts'] == 0 and
              len(record['records']) == 1 and
              record['records'][0]['workload'] == workload.WORKLOAD and
              record['records'][0]['status'] == 'rejected' and
              record['records'][0]['failed_phase'] == 'discover',
              'Exact first discovery rejection with zero candidate attempts required')
    phases = record['records'][0]['commands']
    c.require([row['phase'] for row in phases] == ['prepare', 'discover'] and
              [row['record']['status'] for row in phases] == ['success', 'nonzero_exit'],
              'Unexpected qualification phase history')
    c.require(protocol['source_bindings'] == {
        name: c.sha(ROOT / name) for name in protocol['source_bindings']},
        'Qualification source binding differs from the pushed source tree')
    c.require(c.sha(QUALIFICATION / 'reference-plan.json') ==
              protocol['reference_plan_sha256'], 'Reference plan bytes differ')

    raw = QUALIFICATION / archive['archive']
    c.require(c.sha(raw) == archive['sha256'] and raw.stat().st_size == archive['bytes'],
              'Raw native archive hash/size differs')
    entries = {row['path']: row for row in archive['files']}
    c.require(len(entries) == len(archive['files']), 'Duplicate archive manifest paths')
    with tarfile.open(raw, 'r:gz') as stream:
        members = stream.getmembers()
        c.require(all(member.isfile() for member in members) and
                  {member.name for member in members} == set(entries),
                  'Raw archive member inventory differs')
        for member in members:
            content = stream.extractfile(member).read()
            expected = entries[member.name]
            c.require(len(content) == expected['bytes'] and
                      hashlib.sha256(content).hexdigest() == expected['sha256'],
                      'Raw archive member hash/size differs: ' + member.name)
            if member.name == 'plan.json':
                c.require(hashlib.sha256(content).hexdigest() == c.sha(NATIVE / 'plan.json'),
                          'Native root is not the archived qualification root')
    workload.validate_inputs(NATIVE)
    c.require(not list((NATIVE / 'attempt-ledger').glob('candidate_*.json')) and
              not list((NATIVE / 'measurements').glob('candidate_*')),
              'Candidate outcomes appeared in a zero-label qualification')
    return protocol, record, archive


def diagnose(output: Path = DEFAULT_OUTPUT) -> dict:
    output = Path(output).resolve()
    c.require(output.is_relative_to(ROOT) and not output.exists(),
              'Use a fresh repository-local diagnosis directory')
    protocol, qualification, archive = _authenticate_qualification()
    plan = workload.validate_inputs(NATIVE)
    folder = NATIVE / 'discovery/attempt-000'
    original, marked = folder / 'original', folder / 'marked'
    source_assembly = (folder / 'program.s').read_text()
    marked_assembly, sites = lowering.mark_assembly(source_assembly)
    c.require(marked_assembly == (folder / 'marked.S').read_text(),
              'Original marked assembly reconstruction differs')
    c.require(c.sha(original / 'firmware.bin') == c.sha(marked / 'firmware.bin'),
              'Baseline marking changed the compiled firmware bytes')
    program = lowering.read_program((original / 'disassembly.txt').read_text())
    site_map = lowering.map_sites(sites, (marked / 'symbols.txt').read_text())
    profile_path = folder / 'profile/simulation.json'
    profile = c.read(profile_path)
    extraction = lowering.extract(program, profile, site_map, plan['pool_size'])
    guarded = relocation_guard.filter_executable_candidates(extraction, sites)
    calibration = c.read(NATIVE / 'inputs/latency-calibration.json')
    latency = latency_features.latency_table(calibration)

    calibrated, uncalibrated = [], []
    for candidate in guarded['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency_features.instruction_latency(program[int(pc, 16)], latency)
        except ValueError:
            uncalibrated.append(candidate)
        else:
            calibrated.append(candidate)

    history = c.unseal(HISTORY)
    historical_rows = list(history['rows']) + list(history.get('failed_attempts', []))
    historical_families = {speedup_corpus.family(row['formula']) for row in historical_rows
                           if isinstance(row.get('formula'), str)}
    rows = []
    for candidate in calibrated:
        family = speedup_corpus.family(candidate['formula'])
        rows.append(dict(name=candidate['name'], formula=candidate['formula'],
            operation_family=family, overlaps_historical_family=family in historical_families,
            expected_instruction_reduction=candidate['expected_instruction_reduction'],
            timed_replacements=candidate['total_custom_instructions'],
            dynamic_occurrences=len(candidate['occurrences'])))

    validation = c.read(original / 'validation.json')
    failed_command = qualification['records'][0]['commands'][1]['record']
    profile_correct = profile['words'][4] == 1
    c.require(profile_correct and profile['words'][1] == 0,
              'Original target checksum did not pass in the discovery profile')
    c.require(extraction['raw_formula_count'] >= extraction['executable_formula_count'] >=
              guarded['executable_formula_count'] >= len(calibrated),
              'Candidate stage counts are inconsistent')
    metrics = dict(
        status='rejected_at_discovery', failed_phase='discover',
        original_checksum_passed=profile_correct,
        instrumented_profile_cycles=profile['words'][2],
        instrumented_profile_instructions=profile['words'][3],
        program_and_bss_end=validation['program_and_bss_end'],
        program_limit=plan['memory_partition']['program_limit'],
        observed_stack_bytes=profile['max_stack_bytes'],
        stack_limit=plan['memory_partition']['stack_bytes'],
        mapped_source_statements=len(site_map),
        raw_formula_count=extraction['raw_formula_count'],
        executable_formula_count=extraction['executable_formula_count'],
        relocation_safe_executable_formula_count=guarded['executable_formula_count'],
        uncalibrated_relocation_safe_formula_count=len(uncalibrated),
        calibrated_relocation_safe_formula_count=len(calibrated),
        required_pool_size=plan['pool_size'],
        unique_historical_safe_operation_families=sum(
            not row['overlaps_historical_family'] for row in rows),
        calibrated_candidates=rows,
        discovery_error='Too few calibrated executable candidates',
        routed_baseline_measured=False, candidate_attempts=0, candidate_labels=0,
        area_or_timing_results=0,
        observed_command_monotonic_seconds={row['phase']: row['record']['durations']['monotonic_elapsed_seconds']
            for row in qualification['records'][0]['commands']},
        clock_disagreement_phase_count=qualification['clock_disagreement_phase_count'])
    c.require(metrics['calibrated_relocation_safe_formula_count'] < plan['pool_size'],
              'The archived discovery failure no longer matches the fixed-pool gate')

    bindings = {name: c.sha(ROOT / name) for name in (
        'scripts/diagnose_tacle_countnegative_discovery.py',
        'isaforge/tacle_countnegative_workload.py', 'isaforge/guarded_workload.py',
        'isaforge/partitioned_workload.py', 'isaforge/assembly_lowering.py',
        'isaforge/relocation_guard.py', 'isaforge/latency_features.py',
        'isaforge/speedup_corpus.py', 'isaforge/codesign.py')}
    report = dict(schema='isaforge-tacle-countnegative-discovery-diagnosis-v1',
        qualification_protocol_sha256=c.sha(QUALIFICATION / 'protocol.json'),
        qualification_manifest_sha256=c.sha(QUALIFICATION / 'manifest.json'),
        raw_archive_sha256=archive['sha256'], target_context_id=plan['context_id'],
        historical_corpus_sha256=c.sha(HISTORY), source_bindings=bindings,
        metrics=metrics,
        scope='Offline reconstruction of the completed baseline-only discovery rejection. No new target job, candidate measurement, model fit, or outcome label was added.',
        limitations=[
            'Profile counters are from the instrumented discovery simulation, not a routed baseline or measured speedup.',
            'The 12-formula pool and public opportunity gate were never reached; no public pool was frozen.',
            'Operation-family overlap is a public-feature audit of discovered formulas, not independent workload confirmation.',
            'Clock disagreement was flagged for both qualification subprocesses; monotonic durations are retained, with no uninterrupted wall-time claim.',
        ])
    output.mkdir(parents=True)
    c.seal(output / 'report.json', report)
    lines = [
        '# TACLeBench countnegative discovery rejection', '',
        '**Preserved baseline-only rejection.** Preparation succeeded; discovery stopped because the exact relocation-safe calibrated candidate set did not satisfy the frozen twelve-candidate requirement. No smaller pool, fallback, or candidate dispatch was attempted.', '',
        f"Qualification commit: `1b831040`; protocol `{report['qualification_protocol_sha256']}`.",
        f"Target context: `{plan['context_id']}`. Original checksum: **passed**.", '',
        '## Discovery and fit', '',
        f"The instrumented profile recorded **{metrics['instrumented_profile_cycles']:,} cycles / {metrics['instrumented_profile_instructions']:,} instructions**. These are discovery counters, not a routed baseline or speedup. Program/data ended at **{metrics['program_and_bss_end']:,} / {metrics['program_limit']:,} bytes**; observed stack use was **{metrics['observed_stack_bytes']} / {metrics['stack_limit']:,} bytes**.", '',
        f"Offline reconstruction finds **{metrics['raw_formula_count']} raw**, **{metrics['executable_formula_count']} executable**, **{metrics['relocation_safe_executable_formula_count']} relocation-safe**, and **{metrics['calibrated_relocation_safe_formula_count']} calibrated relocation-safe formulas**. The frozen requirement is **{metrics['required_pool_size']}**. Thus no twelve-candidate pool or public opportunity score exists.", '',
        f"Of the {len(rows)} calibrated formulas, {metrics['unique_historical_safe_operation_families']} have operation-tree families absent from the historical feature corpus. This screening is not a model evaluation.", '',
        'Candidate attempts, measured labels, routed baseline, area results, and timing results: **0**.', '',
        '## Reproduction', '',
        '```sh',
        '../work/audit-venv/bin/python scripts/diagnose_tacle_countnegative_discovery.py',
        '```', '',
        'The baseline-only qualification has already been consumed and must not be rerun. Its original source, run receipts, and raw archive remain in `results/2026-10-27-countnegative-qualification/`. This command authenticates that evidence, replays extraction from the archived assembly/profile, and compares only public formula families with the frozen historical corpus; it adds no target jobs, labels, or model fits.', '',
        '## Limits', '',
    ]
    lines.extend('- ' + text for text in report['limitations'])
    (output / 'README.md').write_text('\n'.join(lines) + '\n')
    inventory = _inventory(output)
    c.seal(output / 'manifest.json', inventory)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = diagnose(args.output)
    print(result['metrics'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

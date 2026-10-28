#!/usr/bin/env python3
"""Reproduce the source-level rejection from the sealed Queens discovery run.

This is a read-only post-run diagnosis. It authenticates the qualification
record and native archive, recomputes the extractor's calibrated candidate
count and label-free opportunity estimates, and never launches native tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import assembly_lowering as lowering
from isaforge import codesign as c
from isaforge import latency_features as latency
from isaforge.speedup_corpus import family

QUALIFICATION = Path('results/2026-10-28-llvm-stanford-queens-qualification-r1')
NATIVE = Path('generated/llvm-stanford-queens-qualification-2026-10-28-r1')
HISTORY = Path('results/2026-10-26-lift-selection-corpus/corpus.json')
SOURCES = (
    'scripts/diagnose_llvm_queens_discovery.py',
    'scripts/qualify_llvm_queens.py',
    'isaforge/llvm_queens_workload.py',
    'isaforge/guarded_workload.py',
    'isaforge/partitioned_workload.py',
    'isaforge/assembly_lowering.py',
    'isaforge/latency_features.py',
    'isaforge/features.py',
    'isaforge/speedup_corpus.py',
    'src/candidates.py',
    'src/tracing.py',
    str(HISTORY),
)
DEFAULT_OUTPUT = Path('reports/2026-10-28-llvm-stanford-queens-discovery-diagnosis-r1')
POOL_SIZE = 12
MIN_REDUCTION = .005
MIN_REPLACEMENTS = 10


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text())


def sealed(path: Path):
    return c.unseal(path)


def authenticate_outer(root: Path) -> dict:
    inventory = sealed(root / 'manifest.json')
    require(isinstance(inventory, dict) and inventory, 'Qualification inventory required')
    require((root / 'manifest.json.sha256').read_text().strip() == digest(root / 'manifest.json'),
            'Qualification manifest sidecar mismatch')
    for name, expected in inventory.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file(),
                'Invalid qualification artifact: ' + name)
        require(digest(path) == expected, 'Qualification artifact changed: ' + name)
    return inventory


def authenticate_native(root: Path, outer: Path) -> dict:
    manifest = sealed(outer / 'archive-manifest.json')
    archive = outer / manifest['archive']
    require(digest(archive) == manifest['sha256'] and archive.stat().st_size == manifest['bytes'],
            'Archived raw run checksum mismatch')
    entries = manifest['files']
    require(entries and len({row['path'] for row in entries}) == len(entries),
            'Native archive inventory is empty or duplicated')
    for row in entries:
        relative = PurePosixPath(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts,
                'Unsafe native archive path')
        path = root.joinpath(*relative.parts)
        require(path.is_file() and path.stat().st_size == row['bytes'] and
                digest(path) == row['sha256'], 'Native evidence changed: ' + row['path'])
    return manifest


def calculate(outer: Path = ROOT / QUALIFICATION, native: Path = ROOT / NATIVE) -> dict:
    outer, native = outer.resolve(), native.resolve()
    outer_inventory = authenticate_outer(outer)
    archive_manifest = authenticate_native(native, outer)
    protocol = sealed(outer / 'protocol.json')
    qualification = sealed(outer / 'qualification.json')
    require(protocol['target_candidate_attempts'] == qualification['target_candidate_attempts'] == 0,
            'Expected a zero-candidate-attempt qualification')
    record = qualification['records'][0]
    require(record['failed_phase'] == 'discover' and record['status'] == 'failed',
            'Expected the preserved discovery-stage failure')
    discover_receipt = next(row['record'] for row in record['commands']
                            if row['phase'] == 'discover')
    require(discover_receipt['status'] == 'nonzero_exit' and discover_receipt['returncode'] == 1,
            'Expected the original extractor rejection')
    stderr_path = outer / next(row['observation'] for row in record['commands']
                               if row['phase'] == 'discover') / 'stderr.txt'
    stderr = stderr_path.read_text()
    require('Too few calibrated executable candidates' in stderr,
            'Run failed for a different reason; do not classify this diagnosis as a source rejection')

    plan = sealed(native / 'plan.json')
    for name, expected in plan['inputs'].items():
        require(digest(native / 'inputs' / name) == expected,
                'Prepared workload input differs from its sealed plan: ' + name)
    for name, expected in plan['source_bindings'].items():
        snapshot = native / 'sources' / name
        source = snapshot if snapshot.is_file() else ROOT / name
        require(source.is_file() and digest(source) == expected,
                'Prepared source binding differs from its sealed plan: ' + name)
    attempt = native / 'discovery/attempt-000'
    program_source = (attempt / 'program.s').read_text()
    marked, sites = lowering.mark_assembly(program_source)
    site_map = lowering.map_sites(sites, (attempt / 'marked/symbols.txt').read_text())
    profile = read(attempt / 'profile/simulation.json')
    program = lowering.read_program((attempt / 'marked/disassembly.txt').read_text())
    extraction = lowering.extract(program, profile, site_map, pool_size=30)
    calibration = read(native / 'inputs/latency-calibration.json')
    latency.latency_table(calibration)

    eligible, excluded = [], []
    for row in extraction['executable_candidates']:
        try:
            for occurrence in row['occurrences']:
                for pc in occurrence['pcs']:
                    latency.instruction_latency(program[int(pc, 16)],
                                                latency.latency_table(calibration))
        except ValueError as error:
            excluded.append(dict(formula=row['formula'], reason=str(error)))
        else:
            eligible.append(row)
    eligible.sort(key=lambda row: (-row['expected_instruction_reduction'], row['formula']))

    cycles, instructions = profile['words'][2], profile['words'][3]
    candidates = []
    for index, row in enumerate(eligible):
        estimate = latency.candidate_features(row, program, cycles, instructions, calibration)
        candidates.append(dict(candidate_id=f'candidate_{index:02d}', formula=row['formula'],
            expression_tree_operations=row['features']['tree_op_count'],
            dynamic_replacements=row['region_custom_instructions'],
            expected_instruction_reduction=row['expected_instruction_reduction'],
            estimated_saved_cycles=estimate['estimated_saved_cycles'],
            estimated_cycle_reduction=estimate['estimated_cycle_reduction'],
            estimated_speedup=estimate['estimated_speedup']))

    history = sealed(ROOT / HISTORY)
    old_families = {row.get('candidate_family') or family(row['formula'])
                    for row in history['rows']}
    for row in candidates:
        row['historical_operation_family_overlap'] = family(row['formula']) in old_families

    validation = read(attempt / 'marked/validation.json')
    original_validation = read(attempt / 'original/validation.json')
    require(validation['program_and_bss_end'] == original_validation['program_and_bss_end'] and
            validation['writable_start'] <= validation['program_and_bss_end'] <=
            plan['memory_partition']['program_limit'], 'Unexpected linked-image validation values')
    require(digest(attempt / 'marked/firmware.bin') == digest(attempt / 'original/firmware.bin'),
            'Assembly marker transformation changed original firmware bytes')
    max_candidate = max(candidates, key=lambda row: row['estimated_saved_cycles']) if candidates else None
    threshold_cycles = cycles * MIN_REDUCTION
    passes = [row for row in candidates
              if row['estimated_cycle_reduction'] >= MIN_REDUCTION and
              row['dynamic_replacements'] >= MIN_REPLACEMENTS]
    source_hashes = {name: digest(ROOT / name) for name in SOURCES}
    source_hashes.update({name: expected for name, expected in plan['source_bindings'].items()})
    return dict(schema='isaforge-llvm-queens-discovery-diagnosis-v1',
        classification='source_rejected_at_unchanged_candidate-pool-and-opportunity-gates',
        qualification=dict(path=str(QUALIFICATION), manifest_sha256=digest(outer / 'manifest.json'),
            protocol_sha256=digest(outer / 'protocol.json'), original_status=qualification['status'],
            failed_phase=record['failed_phase'], target_candidate_attempts=qualification['target_candidate_attempts'],
            captured_error='Too few calibrated executable candidates',
            native_archive_sha256=archive_manifest['sha256'],
            archived_native_file_count=len(archive_manifest['files']),
            qualification_output_file_count=len(outer_inventory)),
        workload=dict(name=plan['workload'], workload_group=plan['workload_group'],
            source_commit=plan['upstream']['commit'], fixed_solves=plan['upstream']['fixed_workload']['solves'],
            upstream_and_adapter_self_check_passed=profile['words'][4] == 1,
            firmware_bytes=validation['program_and_bss_end'], program_data_limit=plan['memory_partition']['program_limit'],
            reserved_stack_bytes=plan['memory_partition']['stack_bytes'],
            instrumented_discovery_cycles=cycles, instrumented_discovery_instructions=instructions,
            pcpi_handshakes=profile['pcpi_handshakes'],
            instrumented_profile_is_final_routed_baseline=False),
        extraction=dict(raw_formula_count=extraction['raw_formula_count'],
            relocation_safe_executable_formula_count=extraction['executable_formula_count'],
            calibrated_executable_formula_count=len(eligible),
            required_pool_size=POOL_SIZE, calibrated_formulas_excluded=excluded,
            candidate_rows=candidates),
        opportunity=dict(required_cycle_reduction=MIN_REDUCTION,
            required_timed_replacements=MIN_REPLACEMENTS,
            required_saved_cycles_for_cycle_gate=threshold_cycles,
            maximum_estimated_saved_cycles=max_candidate['estimated_saved_cycles'] if max_candidate else None,
            maximum_estimated_cycle_reduction=max_candidate['estimated_cycle_reduction'] if max_candidate else None,
            joint_gate_passed=bool(passes),
            opportunity_candidate_ids=[row['candidate_id'] for row in passes]),
        research_limitations=[
            'Only the unchanged fixed Queens workload was profiled; no routed baseline completed.',
            'No candidate was lowered/semantically verified, executed as custom RTL, synthesized, or routed.',
            'There are no candidate whole-program speedup, integrated area, timing, or model-training labels.',
            'The three extracted candidates are a discovery diagnosis only; they do not satisfy the frozen 12-candidate pool gate.',
            'Operation-family overlap is descriptive and does not establish an independent workload family.',
            'The preserved outer status remains failed; this derived diagnosis explains the failure without rewriting it.'],
        source_sha256=source_hashes)


def make_readme(report: dict) -> bytes:
    pool = report['extraction']
    opp = report['opportunity']
    work = report['workload']
    rows = report['extraction']['candidate_rows']
    lines = [
        '# LLVM Stanford Queens discovery diagnosis', '',
        'This post-run report authenticates and explains the preserved baseline-only qualification. '
        'It does not edit the failed qualification or launch native tools.', '',
        '## Result', '',
        f"- The original fixed workload passed its self-check: {work['fixed_solves']:,} solves; "
        f"instrumented discovery profile {work['instrumented_discovery_cycles']:,} cycles / "
        f"{work['instrumented_discovery_instructions']:,} instructions.",
        f"- Firmware and data ended at {work['firmware_bytes']:,} bytes under the "
        f"{work['program_data_limit']:,}-byte limit; the declared stack partition was "
        f"{work['reserved_stack_bytes']:,} bytes.",
        f"- Frozen pool gate requires {pool['required_pool_size']} candidates; the unchanged extractor found "
        f"{pool['calibrated_executable_formula_count']} calibrated executable formulas from "
        f"{pool['raw_formula_count']} raw formulas.",
        f"- Best analytic estimate is {opp['maximum_estimated_saved_cycles']:,} cycles "
        f"({100*opp['maximum_estimated_cycle_reduction']:.6f}%); the unchanged 0.5% gate needs "
        f"{opp['required_saved_cycles_for_cycle_gate']:,.0f} cycles plus ten replacements.",
        '- Conclusion: source lead rejected at discovery under existing gates. Do not shrink the workload, pool, or thresholds.',
        '', '## Extracted formulas', '',
        '| Candidate | Formula | Replacements | Estimated saved cycles | Historical family overlap |',
        '|---|---|---:|---:|---|',
    ]
    for row in rows:
        lines.append(f"| {row['candidate_id']} | `{row['formula']}` | {row['dynamic_replacements']} | "
                     f"{row['estimated_saved_cycles']:,} | {'yes' if row['historical_operation_family_overlap'] else 'no'} |")
    lines += ['', '## Limits', '']
    lines += ['- This was not a routed baseline, candidate measurement, or performance-area result.',
              '- No candidate labels were generated; model training and selection did not run.',
              '- The exact qualification remains classified `failed` in its sealed output. This diagnosis attributes the failure to the explicit too-few-candidates extractor gate and independently recomputes the shortfall.',
              '- Keep the run as a negative workload qualification; do not retry with relaxed gates.',
              '', 'Reproduce with `scripts/diagnose_llvm_queens_discovery.py`; verify the report with `--verify`.']
    return ('\n'.join(lines) + '\n').encode()


def render(report: dict) -> dict[str, bytes]:
    body = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    readme = make_readme(report)
    inventory = {'diagnosis.json': hashlib.sha256(body).hexdigest(),
                 'README.md': hashlib.sha256(readme).hexdigest()}
    manifest_bytes = (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode()
    return {'diagnosis.json': body, 'README.md': readme,
            'manifest.json': manifest_bytes,
            'manifest.json.sha256': (hashlib.sha256(manifest_bytes).hexdigest() + '\n').encode()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--output', type=Path)
    group.add_argument('--verify', type=Path)
    args = parser.parse_args()
    report = calculate()
    content = render(report)
    destination = (args.verify or args.output or ROOT / DEFAULT_OUTPUT).resolve()
    require(not destination.is_relative_to((ROOT / 'results').resolve()),
            'Diagnostic must not overwrite sealed result evidence')
    if args.verify:
        require(destination.is_dir() and {p.name for p in destination.iterdir()} == set(content),
                'Diagnostic artifact inventory changed')
        for name, body in content.items():
            require((destination / name).read_bytes() == body, 'Diagnostic reproduction mismatch: ' + name)
        print('Verified Queens qualification/archive and exact diagnosis reproduction.')
        return 0
    require(not destination.exists(), 'Use a fresh output directory')
    destination.mkdir(parents=True)
    for name, body in content.items():
        (destination / name).write_bytes(body)
    print(f'Wrote Queens discovery diagnosis to {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

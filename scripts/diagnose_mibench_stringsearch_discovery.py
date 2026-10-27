"""Reconstruct the frozen MiBench stringsearch discovery rejection offline."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import (assembly_lowering as lowering, codesign as c,
    latency_features, mibench_stringsearch_workload as workload,
    relocation_guard)

DEFAULT_ROOT = ROOT / 'generated/mibench-stringsearch-qualification-2026-10-27'
DEFAULT_OUTPUT = ROOT / 'results/2026-10-27-mibench-stringsearch-qualification/discovery-diagnosis.json'


def diagnose(root: Path, output: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    c.require((root / 'plan.json').is_file(),
              'Extract the preserved MiBench qualification archive first')
    c.require(output.is_relative_to(ROOT), 'Diagnosis output must remain in the repository')
    plan = workload.validate_inputs(root)
    qualification = c.unseal(ROOT / 'results/2026-10-27-mibench-stringsearch-qualification/qualification.json')
    row = qualification['records'][0]
    c.require(qualification['status'] == row['status'] == 'rejected' and
              row['failed_phase'] == 'discover' and
              qualification['target_candidate_attempts'] == 0,
              'Preserved zero-label discovery rejection required')
    workload.require_zero_candidates(root)

    folder = root / 'discovery/attempt-000'
    original = folder / 'original'
    marked = folder / 'marked'
    assembly = (folder / 'program.s').read_text()
    marked_assembly, sites = lowering.mark_assembly(assembly)
    c.require(marked_assembly == (folder / 'marked.S').read_text(),
              'Marked source assembly does not reproduce')
    c.require(c.sha(original / 'firmware.bin') == c.sha(marked / 'firmware.bin'),
              'Marked discovery changed original baseline bytes')
    program = lowering.read_program((original / 'disassembly.txt').read_text())
    site_map = lowering.map_sites(sites, (marked / 'symbols.txt').read_text())
    profile = c.read(folder / 'profile/simulation.json')
    calibration = c.read(root / 'inputs/latency-calibration.json')
    extracted = lowering.extract(program, profile, site_map, plan['pool_size'])

    table = latency_features.latency_table(calibration)
    calibrated, excluded = [], []
    for candidate in extracted['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency_features.instruction_latency(program[int(pc, 16)], table)
        except ValueError:
            excluded.append(candidate['formula'])
        else:
            calibrated.append(candidate)
    filtered = relocation_guard.filter_executable_candidates(
        dict(extracted, executable_candidates=calibrated), list(site_map.values()))
    safe_formulas = {row['formula'] for row in filtered['executable_candidates']}

    validation = c.read(original / 'validation.json')
    failed_command = row['commands'][1]['record']
    metrics = dict(
        profile_cycles=profile['words'][2],
        profile_instructions=profile['words'][3],
        result=profile['words'][1],
        target_correctness=profile['words'][4] == 1,
        program_and_bss_end=validation['program_and_bss_end'],
        program_limit=plan['memory_partition']['program_limit'],
        observed_stack_bytes=profile['max_stack_bytes'],
        stack_limit=plan['memory_partition']['stack_bytes'],
        mapped_source_statements=len(site_map),
        raw_formula_count=extracted['raw_formula_count'],
        executable_formula_count=extracted['executable_formula_count'],
        calibrated_formula_count=len(calibrated),
        uncalibrated_formula_count=len(excluded),
        relocation_safe_calibrated_formula_count=len(safe_formulas),
        required_pool_size=plan['pool_size'],
        discovery_status=failed_command['status'],
        discovery_error='Too few calibrated executable candidates',
        candidate_attempts=0,
        routed_baseline_measured=False,
        candidate_labels=0)
    c.require(metrics['profile_cycles'] == 393191 and
              metrics['profile_instructions'] == 67989 and
              metrics['target_correctness'] is True and
              metrics['program_and_bss_end'] == 5556 and
              metrics['observed_stack_bytes'] == 592 and
              metrics['raw_formula_count'] == 10 and
              metrics['executable_formula_count'] == 10 and
              metrics['calibrated_formula_count'] == 10 and
              metrics['relocation_safe_calibrated_formula_count'] == 2,
              'Reconstructed MiBench rejection differs from the archived diagnosis')
    summaries = [dict(formula=row['formula'],
            instruction_savings=row['expected_instruction_reduction'],
            dynamic_custom_count=row['total_custom_instructions'],
            relocation_safe=row['formula'] in safe_formulas)
        for row in calibrated]
    result = dict(schema='isaforge-mibench-stringsearch-discovery-diagnosis-v1',
        context_id=plan['context_id'], qualification_protocol_sha256=
            qualification['protocol_sha256'], native_discovery_source_sha256=
            c.sha(folder / 'program.s'), original_binary_sha256=c.sha(original / 'firmware.bin'),
        marked_binary_sha256=c.sha(marked / 'firmware.bin'),
        profile_sha256=c.sha(folder / 'profile/simulation.json'), metrics=metrics,
        excluded_uncalibrated_formulas=excluded, formulas=summaries,
        relocation_rejections=filtered['relocation_guard']['rejections'],
        result_scope='Offline reconstruction of one already-completed baseline-only discovery; no target job, candidate attempt, policy fit, or label is added.',
        reproduction_script_sha256=c.sha(__file__))
    c.seal(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(diagnose(args.root, args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

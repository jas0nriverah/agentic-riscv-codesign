"""Read-only diagnosis of the preserved, zero-label nanocobs discovery failure."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from isaforge import assembly_lowering, codesign as c, latency_features
from isaforge import nanocobs_workload as workload
from isaforge import relocation_guard

DEFAULT_NATIVE = ROOT / 'generated/nanocobs-qualification-2026-10-28-r1'
DEFAULT_OUTPUT = ROOT / 'reports/2026-10-28-nanocobs-diagnosis-r1/diagnosis.json'


def classify_candidate_counts(*, raw, executable, relocation_safe, calibrated, required):
    if calibrated >= required:
        return 'pool_size_gate_passed'
    if relocation_safe == 0 and raw > 0:
        return 'source_rejected_no_relocation_safe_candidates'
    if executable == 0:
        return 'source_rejected_no_executable_candidates'
    return 'source_rejected_candidate_pool_too_small'


def diagnose(native, output):
    native, output = Path(native).resolve(), Path(output).resolve()
    c.require(native.is_relative_to(ROOT) and not output.exists(),
              'Repository-local native source and fresh diagnostic output required')
    qualification_root = ROOT / 'results/2026-10-28-nanocobs-qualification-r1'
    qualification = c.unseal(qualification_root / 'qualification.json')
    c.require(qualification.get('status') == 'failed' and
              qualification['records'][0].get('failed_phase') == 'discover' and
              qualification.get('target_candidate_attempts') == 0,
              'Expected preserved zero-label discovery failure')
    # This is a post-run diagnosis, so authenticate against the exact source
    # snapshot used by r1. The test file was extended afterward; the current
    # source tree must not be allowed to rewrite the frozen run's provenance.
    protocol = c.unseal(qualification_root / 'protocol.json')
    plan = c.unseal(native / 'plan.json')
    c.require(c.digest({key: value for key, value in plan.items()
                        if key != 'context_id'}) == plan.get('context_id') and
              plan.get('workload') == workload.WORKLOAD and
              plan.get('pool_size') == workload.POOL_SIZE and
              plan.get('upstream') == workload.source_record(),
              'Archived nanocobs workload plan/source identity differs')
    for name, digest in protocol['source_bindings'].items():
        archived = qualification_root / 'sources' / name
        c.require(archived.is_file() and c.sha(archived) == digest,
                  'Qualification source snapshot differs: ' + name)
        if name in plan['source_bindings']:
            c.require(plan['source_bindings'][name] == digest,
                      'Workload plan source binding differs: ' + name)
        if name != workload.TEST:
            c.require(c.sha(ROOT / name) == digest,
                      'Current diagnostic code differs from r1 source: ' + name)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(native / 'inputs' / name) == digest,
                  'Bound nanocobs target input differs: ' + name)
    workload.require_zero_candidates(native)

    folder = native / 'discovery/attempt-000'
    assembly_path = folder / 'program.s'
    profile_path = folder / 'profile/simulation.json'
    disassembly_path = folder / 'marked/disassembly.txt'
    symbols_path = folder / 'marked/symbols.txt'
    marked, sites = assembly_lowering.mark_assembly(assembly_path.read_text())
    c.require(marked == (folder / 'marked.S').read_text(),
              'Marked assembly does not reconstruct from archived source assembly')
    c.require(c.sha(folder / 'original/firmware.hex') == c.sha(folder / 'marked/firmware.hex'),
              'Production assembly markers changed full linked baseline image')
    site_map = assembly_lowering.map_sites(sites, symbols_path.read_text())
    program = assembly_lowering.read_program(disassembly_path.read_text())
    profile = c.read(profile_path)
    extracted = assembly_lowering.extract(program, profile, site_map, plan['pool_size'])
    safe = relocation_guard.filter_executable_candidates(extracted, sites)
    calibration = latency_features.latency_table(c.read(native / 'inputs/latency-calibration.json'))
    calibrated, uncalibrated = [], []
    for candidate in safe['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency_features.instruction_latency(program[int(pc, 16)], calibration)
        except ValueError:
            uncalibrated.append(candidate['formula'])
        else:
            calibrated.append(candidate)

    counts = dict(raw=extracted['raw_formula_count'],
        executable=extracted['executable_formula_count'],
        relocation_safe=safe['executable_formula_count'],
        calibrated=len(calibrated), required=workload.POOL_SIZE)
    status = classify_candidate_counts(**counts)
    c.require(status.startswith('source_rejected_'),
              'Discovery diagnosis does not reproduce the source-level pool rejection')
    performance = workload.g.w.validate_execution(profile)
    memory = workload.g.q.validate_memory(profile, spec=plan['memory_partition'])
    failure_text = (qualification_root / 'commands/01-discover/stderr.txt').read_text()
    c.require('Too few calibrated executable candidates' in failure_text,
              'Preserved failure does not match the derived candidate shortage')

    bound_artifacts = [native / 'plan.json', native / 'inputs/program.c',
        native / 'inputs/upstream/tests/cobs_ref.c', native / 'inputs/latency-calibration.json',
        qualification_root / 'protocol.json', qualification_root / 'qualification.json',
        assembly_path, folder / 'marked.S', disassembly_path, symbols_path, profile_path,
        qualification_root / 'commands/01-discover/stderr.txt']
    bound_artifacts += [native / 'inputs' / name for name in plan['inputs']]
    bound_artifacts += [folder / 'original/firmware.hex', folder / 'marked/firmware.hex',
                        folder / 'marked/validation.json']
    result = dict(schema='isaforge-nanocobs-discovery-diagnosis-v1',
        status=status, source_level_rejection=True, target_candidate_attempts=0,
        candidate_measurements=0, target_candidate_labels=0,
        reason=f"The fixed 12-candidate pool cannot be formed: {counts['raw']} raw, {counts['executable']} executable, {counts['relocation_safe']} relocation-safe, {counts['calibrated']} calibrated formulas.",
        source_gate=dict(pool_size=workload.POOL_SIZE,
            relocation_guard=relocation_guard.SCHEMA,
            opportunity_gate='not reached; no legal pool existed'),
        counts=counts,
        raw_formulas=[dict(name=row['name'], formula=row['formula'])
                      for row in extracted['executable_candidates']],
        relocation_rejections=safe['relocation_guard']['rejections'],
        uncalibrated_formulas=uncalibrated,
        baseline_simulator_result=performance, memory_check=memory,
        measured_hardware=None,
        interpretation='The qualification wrapper records a failed discover command because the generic extractor raises on a short pool. This label-free diagnosis reclassifies that preserved outcome as a source-level eligibility rejection, not a toolchain or simulator failure. Do not change source, relax the relocation guard, shrink the pool, or lower opportunity gates to rescue it.',
        protocol_sha256=c.sha(qualification_root / 'protocol.json'),
        diagnostic_script_sha256=c.sha(__file__),
        bound_artifacts={path.relative_to(ROOT).as_posix(): c.sha(path)
                         for path in bound_artifacts})
    result['posthoc_projection_not_opportunity_gate'] = [dict(
        name=row['name'], formula=row['formula'],
        timed_replacements=sum(item['blockRuns'] for item in row['occurrences']),
        latency_features=latency_features.candidate_features(row, program,
            performance['cycles'], performance['instructions'],
            c.read(native / 'inputs/latency-calibration.json')))
        for row in calibrated]
    result['program_data_end_bytes'] = c.read(folder / 'marked/validation.json')['program_and_bss_end']
    output.parent.mkdir(parents=True, exist_ok=True)
    c.seal(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, default=DEFAULT_NATIVE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = diagnose(args.native_root, args.output)
    print({key: result[key] for key in
           ('status', 'counts', 'target_candidate_attempts', 'target_candidate_labels')})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

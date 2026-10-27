"""Offline, source-bound coverage preflight for exact Lift tail transfers.

Consumes the saved rejected v1 Lift discovery artifacts. It launches no
compiler, simulator, synthesis, router, or candidate evaluation and records no
candidate performance labels. A future v2 native qualification remains a
separate, one-shot baseline-only experiment.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import codesign as c
from isaforge import cfg_lift_workload_tail as w, cfg_liveness_tail as cfg
from isaforge import latency_features as latency, relocation_guard
from scripts.qualify_cfg_lift_tail import validate_original_rejection, validate_prior_cfg_rejection
from scripts.analyze_speedup_model import authenticated_calibration

SOURCE = 'scripts/preflight_cfg_lift_tail.py'
NATIVE = 'generated/tacle-lift-cfg-2026-10-25'
REJECTION = w.PRIOR_CFG_REJECTION
DEFAULT_OUTPUT = 'results/2026-10-25-lift-cfg-tail-preflight.json'
SOURCES = tuple(dict.fromkeys((SOURCE, 'scripts/analyze_speedup_model.py',
    'scripts/blind_campaign.py', 'isaforge/codesign.py', 'isaforge/assembly_lowering.py',
    'isaforge/cfg_liveness_tail.py', 'isaforge/cfg_lift_workload_tail.py',
    'isaforge/latency_features.py', 'isaforge/relocation_guard.py', *w.GATE_SOURCES)))
ARTIFACT_SUFFIXES = (
    'discovery/attempt-000/program.s',
    'discovery/attempt-000/marked.S',
    'discovery/attempt-000/marked/symbols.txt',
    'discovery/attempt-000/marked/disassembly.txt',
    'discovery/attempt-000/marked/firmware.hex',
    'discovery/attempt-000/original/firmware.hex',
    'discovery/attempt-000/profile/simulation.json',
    'inputs/latency-calibration.json',
)
REJECTION_ARTIFACTS = (
    REJECTION + '/protocol.json', REJECTION + '/qualification.json',
    REJECTION + '/manifest.json')


def _validate_v1_rejection():
    return dict(original_lift=validate_original_rejection(),
        v1_cfg=validate_prior_cfg_rejection())


def _calibrated(candidate, program, table):
    try:
        for occurrence in candidate['occurrences']:
            for pc in occurrence['pcs']:
                latency.instruction_latency(program[int(pc, 16)], table)
    except ValueError:
        return False
    return True


def authenticate_saved_native(native, v1_rejection):
    """Bind consumed files to the frozen v1 rejection's complete raw archive."""
    package = c.ROOT / REJECTION
    archive_record = c.unseal(package / 'archive-manifest.json')
    archive_path = package / archive_record['archive']
    c.require(archive_record['archive'] == 'raw.tar.gz' and
        c.sha(archive_path) == archive_record['sha256'] == v1_rejection['raw_archive_sha256'] and
        c.sha(package / 'archive-manifest.json') == v1_rejection['archive_manifest_sha256'],
        'Saved Lift archive differs from the authenticated v1 rejection')
    members = {row['path']:row for row in archive_record['files']}
    c.require(len(members) == len(archive_record['files']), 'Duplicate archive paths')
    observed = {}
    for suffix in ARTIFACT_SUFFIXES:
        c.require(suffix in members, 'Consumed Lift input absent from rejected native archive: ' + suffix)
        path = (native / suffix).resolve()
        c.require(path.is_relative_to(native) and path.is_file(), 'Missing or escaped saved Lift input: ' + suffix)
        entry = members[suffix]
        c.require(path.stat().st_size == entry['bytes'] and c.sha(path) == entry['sha256'],
                  'Saved Lift input differs from rejected native archive: ' + suffix)
        observed[suffix] = entry['sha256']
    return observed


def derive(native_root=None):
    """Recompute eligible formula counts and stratified names without native work."""
    native = Path(native_root or c.ROOT / NATIVE).resolve()
    c.require(native.is_relative_to(c.ROOT.resolve()), 'Saved native root must remain inside the repository')
    native_label = native.relative_to(c.ROOT.resolve()).as_posix()
    v1 = _validate_v1_rejection()
    archive_inputs = authenticate_saved_native(native, v1['v1_cfg'])
    program, profile, site_map = w.saved_discovery_inputs(native)
    c.require(archive_inputs == authenticate_saved_native(native, v1['v1_cfg']),
              'Saved Lift inputs changed during the offline preflight')
    extraction = cfg.extract(program, profile, site_map, w.POOL_SIZE,
        compiler_abi_returns=True, firmware_trap_exit=True)
    c.require(extraction['certificate']['entry_model']['extraction_supported'],
              'Tail-transfer-aware static extraction remains unsupported')

    filtered = relocation_guard.filter_executable_candidates(
        extraction, list(site_map.values()))
    calibration, _ = authenticated_calibration(c.ROOT / 'results/2026-10-20-latency-calibration')
    c.require(calibration == c.read(native / 'inputs/latency-calibration.json'),
              'Saved discovery calibration differs from authenticated calibration')
    table = latency.latency_table(calibration)
    eligible = [row for row in filtered['executable_candidates'] if _calibrated(row, program, table)]
    excluded = [row['formula'] for row in filtered['executable_candidates'] if not _calibrated(row, program, table)]
    c.require(len(eligible) >= w.POOL_SIZE, 'Too few relocation-safe, calibrated formulas for frozen pool')
    indices = [round(i * (len(eligible) - 1) / (w.POOL_SIZE - 1)) for i in range(w.POOL_SIZE)]
    c.require(len(set(indices)) == w.POOL_SIZE, 'Duplicate frozen stratification indices')
    pool = [eligible[i] for i in indices]

    return dict(schema='isaforge-lift-tail-coverage-preflight-v1',
        interpretation='Consumed engineering coverage replay from the preserved rejected v1 Lift binary; not an untouched confirmatory workload, native qualification, candidate label, or model result.',
        native_activity=dict(compiler=False, simulator=False, synthesis=False, routing=False,
                             candidate_evaluations=0, candidate_labels=0),
        preserved_v1_rejection=v1,
        native_root=native_label,
        consumed_artifacts={native_label+'/'+name:c.sha(native/name) for name in ARTIFACT_SUFFIXES} |
            {name:c.sha(c.ROOT/name) for name in REJECTION_ARTIFACTS} |
            {REJECTION+'/archive-manifest.json':c.sha(c.ROOT/REJECTION/'archive-manifest.json'),
             REJECTION+'/raw.tar.gz':c.sha(c.ROOT/REJECTION/'raw.tar.gz')},
        current_native_discovery_inputs={
            'program_sha256': c.digest([[pc, program[pc]] for pc in sorted(program)]),
            'profile_sha256': c.digest(profile),
            'source_map_sha256': c.digest([[pc, site_map[pc]] for pc in sorted(site_map)]),
            'calibration_sha256': c.sha(native / 'inputs/latency-calibration.json')},
        source_bindings={name:c.sha(c.ROOT/name) for name in SOURCES},
        resolved_direct_tail_transfers=extraction['certificate']['entry_model']['resolved_direct_tail_transfers'],
        counts=dict(raw_formulas=extraction['raw_formula_count'],
            executable_before_relocation=extraction['executable_formula_count'],
            relocation_rejected=filtered['relocation_guard']['rejected_count'],
            executable_after_relocation=filtered['executable_formula_count'],
            calibration_excluded=len(excluded), calibrated_after_relocation=len(eligible),
            frozen_pool_size=w.POOL_SIZE, selected_rank_indices=indices),
        calibration_excluded_formulas=excluded,
        selected_pool=[dict(rank=rank, candidate_name=row['name'], formula=row['formula'],
            expected_instruction_reduction=row['expected_instruction_reduction'])
            for rank, row in enumerate(pool)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, default=ROOT / NATIVE)
    parser.add_argument('--output', type=Path, default=ROOT / DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = derive(args.native_root)
    output = args.output.resolve()
    if output.exists():
        c.require(c.unseal(output) == result,
                  'Existing preflight differs; preserve it and choose a fresh output path')
    else:
        c.seal(output, result)
    counts = result['counts']
    print(dict(status='preflight_complete', native_activity=result['native_activity'],
        resolved_tail_transfers=len(result['resolved_direct_tail_transfers']), counts=counts,
        output=str(output)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

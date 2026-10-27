#!/usr/bin/env python3
"""Reconstruct candidate scarcity from the preserved Fannkuch discovery profile.

Read-only: authenticates the rejected r2 context and source snapshots, then
reuses the frozen extractor on saved artifacts. It never builds, simulates,
measures a candidate, fits a model, or changes the qualification result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import assembly_lowering as lowering
from isaforge import codesign as c
from isaforge import latency_features as latency
from isaforge import speedup_corpus
from isaforge import workload_experiment
from scripts.audit_v12_target_transform import commutative


NATIVE = ROOT / 'generated/fannkuch-qualification-2026-10-26-r2'
QUALIFICATION = ROOT / 'results/2026-10-26-fannkuch-qualification-r2'
HISTORY = ROOT / 'results/2026-10-26-lift-selection-corpus/corpus.json'
OUTPUT = ROOT / 'results/2026-10-26-fannkuch-discovery-diagnosis'
BOUND_SOURCES = (
    'isaforge/assembly_lowering.py',
    'isaforge/partitioned_workload.py',
    'isaforge/latency_features.py',
    'isaforge/speedup_corpus.py',
)
MAX_OPS_DIAGNOSTIC = (2, 3, 4, 5, 6)


def require(condition: bool, message: str) -> None:
    c.require(condition, message)


def alias_key(formula: str) -> str:
    """Existing identity rule: commutative ALU sorting plus global input swap."""
    swapped = formula.replace('in0', '__isaforge_input__')
    swapped = swapped.replace('in1', 'in0').replace('__isaforge_input__', 'in1')
    return min(commutative(formula), commutative(swapped))


def _extract_for_size(program, profile, sites, size):
    original = lowering.discovery.extractCandidates

    def bounded_extractor(p, runs, starts, maxSize=4, limit=None):
        return original(p, runs, starts, maxSize=size, limit=limit)

    with patch.object(lowering.discovery, 'extractCandidates', bounded_extractor):
        return lowering.extract(program, profile, sites, 30)


def _calibration_status(rows, program, table):
    eligible, excluded = [], []
    for candidate in rows:
        unsupported = set()
        for occurrence in candidate['occurrences']:
            for pc in occurrence['pcs']:
                instruction = program[int(pc, 16)]
                try:
                    latency.instruction_latency(instruction, table)
                except ValueError:
                    unsupported.add(instruction['op'])
        if unsupported:
            excluded.append({'formula': candidate['formula'],
                             'unsupported_operations': sorted(unsupported)})
        else:
            eligible.append(candidate)
    return eligible, excluded


def analyze(native: Path = NATIVE, qualification_root: Path = QUALIFICATION,
            history_path: Path = HISTORY) -> dict:
    native = Path(native).resolve()
    qualification_root = Path(qualification_root).resolve()
    history_path = Path(history_path).resolve()

    record = c.unseal(qualification_root / 'qualification.json')
    manifest = c.unseal(qualification_root / 'manifest.json')
    for name, expected in manifest.items():
        path = qualification_root / name
        require(path.is_file() and c.sha(path) == expected,
                'Qualification artifact differs from its manifest: ' + name)
    require(record['status'] == 'rejected' and record['target_candidate_attempts'] == 0,
            'Expected preserved zero-candidate rejected qualification')
    attempt = record['records'][0]
    require(attempt['failed_phase'] == 'discover' and
            attempt['commands'][-1]['phase'] == 'discover' and
            attempt['commands'][-1]['record']['status'] == 'nonzero_exit',
            'Expected discovery-stage rejection')

    plan_path = native / 'plan.json'
    plan = c.unseal(plan_path)
    require(c.sha(plan_path) == attempt['prepared_plan_sha256'],
            'Native plan differs from the rejected qualification receipt')
    require(plan.get('pool_size') == 12, 'Frozen twelve-candidate requirement changed')
    for name in BOUND_SOURCES:
        expected = plan['source_bindings'].get(name)
        require(expected and c.sha(ROOT / name) == expected and
                c.sha(native / 'sources' / name) == expected,
                'Live or archived source differs from the prepared plan: ' + name)

    work = native / 'discovery/attempt-000'
    original_assembly = (work / 'program.s').read_text()
    _, sites = lowering.mark_assembly(original_assembly)
    site_map = lowering.map_sites(sites, (work / 'marked/symbols.txt').read_text())
    program = lowering.read_program((work / 'marked/disassembly.txt').read_text())
    profile = json.loads((work / 'profile/simulation.json').read_text())
    calibration = json.loads((native / 'inputs/latency-calibration.json').read_text())
    table = latency.latency_table(calibration)
    performance = workload_experiment.validate_execution(profile)
    require(performance['upstream_self_check'] is True and
            performance['benchmark_result_u32'] == 1081212944,
            'Saved discovery profile does not pass the pinned N=7 self-check')

    sweep = []
    frozen_candidates = []
    for max_ops in MAX_OPS_DIAGNOSTIC:
        extracted = _extract_for_size(program, profile, site_map, max_ops)
        eligible, excluded = _calibration_status(extracted['executable_candidates'], program, table)
        sweep.append({
            'maximum_operations': max_ops,
            'raw_formula_count': extracted['raw_formula_count'],
            'executable_formula_count': extracted['executable_formula_count'],
            'calibrated_formula_count': len(eligible),
            'excluded_uncalibrated': excluded,
            'pool_requirement': plan['pool_size'],
            'pool_gate_met': len(eligible) >= plan['pool_size'],
        })
        if max_ops == 4:
            frozen_candidates = eligible
    require(frozen_candidates, 'Frozen four-operation extraction unexpectedly empty')

    historical = json.loads(history_path.read_text())
    historical_rows = historical['rows']
    candidates = []
    for candidate in frozen_candidates:
        feature = latency.candidate_features(candidate, program,
            performance['cycles'], performance['instructions'], calibration)
        key = alias_key(candidate['formula'])
        matches = []
        for row in historical_rows:
            formula = row.get('formula')
            if formula and alias_key(formula) == key:
                matches.append({k: row[k] for k in
                    ('benchmark', 'workload_group', 'candidate_id', 'formula') if k in row})
        candidates.append({
            'formula': candidate['formula'],
            'candidate_family': speedup_corpus.family(candidate['formula']),
            'identity_alias_key': key,
            'occurrence_count': len(candidate['occurrences']),
            'timed_replacements': candidate['region_custom_instructions'],
            'instruction_reduction_proxy': candidate['expected_instruction_reduction'],
            'calibrated_projection': {
                'estimated_saved_cycles': feature['estimated_saved_cycles'],
                'estimated_cycle_reduction': feature['estimated_cycle_reduction'],
                'estimated_speedup': feature['estimated_speedup'],
                'is_measured_label': False,
            },
            'prior_formula_family_identity_matches': matches,
        })

    return {
        'schema': 'isaforge-fannkuch-discovery-rejection-diagnosis-v1',
        'classification': 'ineligible_frozen_pool_too_small',
        'qualification_status': record['status'],
        'failed_phase': attempt['failed_phase'],
        'candidate_attempts': record['target_candidate_attempts'],
        'new_target_labels': 0,
        'native_jobs_started_by_analysis': 0,
        'frozen_pool_requirement': plan['pool_size'],
        'saved_discovery_profile': {
            'cycles': performance['cycles'],
            'instructions': performance['instructions'],
            'benchmark_result_u32': performance['benchmark_result_u32'],
            'upstream_self_check': performance['upstream_self_check'],
            'custom_instructions': performance['custom_instructions'],
            'scope': 'Instrumented original-program discovery profile; not the separate routed baseline qualification or hardware-cost measurement.',
            'simulation_json_sha256': c.sha(work / 'profile/simulation.json'),
        },
        'max_operation_sensitivity': sweep,
        'frozen_candidates': candidates,
        'identity_rule': 'Existing V12-style identity: V4-normalized formula, commutative ALU operand sorting, and global in0/in1 permutation; source-family grouping also uses speedup_corpus.family.',
        'historical_rows_read': len(historical_rows),
        'historical_fields_used': ['formula', 'benchmark', 'workload_group', 'candidate_id'],
        'historical_outcome_fields_used': [],
        'source_bindings': {name: plan['source_bindings'][name] for name in BOUND_SOURCES},
        'qualification_json_sha256': c.sha(qualification_root / 'qualification.json'),
        'qualification_archive_manifest_sha256': c.sha(qualification_root / 'archive-manifest.json'),
        'native_plan_sha256': c.sha(plan_path),
        'history_corpus_sha256': c.sha(history_path),
        'analysis_script_sha256': c.sha(Path(__file__)),
        'limitations': [
            'No candidate was lowered into a target instruction or measured for correctness, area, timing, or speedup.',
            'Calibrated projections are public estimates, not measured candidate labels.',
            'The operation-size sweep is post-rejection sensitivity analysis; only maximum size four belongs to the frozen study protocol.',
            'Formula-family equality is the project identity convention, not a claim that the ordered input functions are pointwise equal without swapping operands.',
        ],
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, default=NATIVE)
    parser.add_argument('--qualification-root', type=Path, default=QUALIFICATION)
    parser.add_argument('--history', type=Path, default=HISTORY)
    parser.add_argument('--output', type=Path, default=OUTPUT / 'diagnosis.json')
    args = parser.parse_args(argv)
    result = analyze(args.native_root, args.qualification_root, args.history)
    output = Path(args.output).resolve()
    c.require(output.is_relative_to(ROOT) and not output.exists(),
              'Fresh in-repository diagnosis output required')
    c.seal(output, result)
    print(json.dumps({
        'status': result['classification'],
        'pool_requirement': result['frozen_pool_requirement'],
        'calibrated_candidates': result['max_operation_sensitivity'][2]['calibrated_formula_count'],
        'formula_families': sorted({row['candidate_family'] for row in result['frozen_candidates']}),
        'output': output.relative_to(ROOT).as_posix(),
    }, sort_keys=True))


if __name__ == '__main__':
    main()

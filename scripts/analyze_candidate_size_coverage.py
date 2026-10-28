"""Baseline-only exploratory formula coverage at existing extraction caps 4, 5, and 6."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import signal
import tarfile
import time
from tempfile import TemporaryDirectory
from contextlib import contextmanager
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import assembly_lowering as lowering, codesign as c, guarded_workload as guarded
from isaforge import countnegative_v2_workload as countnegative
from isaforge import mibench_stringsearch_v2_workload as stringsearch
from isaforge import nanocobs_v2_workload as nanocobs
from scripts.reproduce_codesign import restore_archive

STUDIES = {
    'countnegative-v2': (countnegative, ROOT / 'results/2026-10-28-countnegative-v2-qualification-r1',
                         ROOT / 'generated/countnegative-v2-qualification-2026-10-28-r1'),
    'stringsearch-v2': (stringsearch, ROOT / 'results/2026-10-28-mibench-stringsearch-v2-qualification-r1',
                        ROOT / 'generated/mibench-stringsearch-v2-qualification-2026-10-28-r1'),
    'nanocobs-v2': (nanocobs, ROOT / 'results/2026-10-28-nanocobs-v2-qualification-r1',
                    ROOT / 'generated/nanocobs-v2-qualification-2026-10-28-r1'),
}
CAPS = (4, 5, 6)
DEFAULT_OUTPUT = ROOT / 'reports/2026-10-28-candidate-size-coverage-r5/report.json'
SCHEMA = 'isaforge-baseline-only-candidate-size-coverage-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), f'Path outside evidence root: {relative}')
    return path


def verify_sealed_folder(folder: Path):
    folder = Path(folder).resolve()
    entries = c.unseal(folder / 'manifest.json')
    require(isinstance(entries, dict) and entries, f'Empty evidence manifest: {folder}')
    for rel, expected in entries.items():
        path = _inside(folder, rel)
        require(path.is_file() and sha(path) == expected, f'Manifest mismatch: {folder}/{rel}')
    return entries


def verify_native_archive_members(archive_path: Path, archive: dict, native_root: Path):
    """Bind every native artifact read later to its exact baseline archive bytes."""
    archive_path = Path(archive_path).resolve()
    native_root = Path(native_root).resolve()
    expected_files = {item['path']: item for item in archive['files']}
    require(len(expected_files) == len(archive['files']), 'Duplicate archive member paths')
    require(sha(archive_path) == archive['sha256'] and archive_path.stat().st_size == archive['bytes'],
            'Raw baseline archive hash/size differs')
    with tarfile.open(archive_path, 'r:gz') as stream:
        members = stream.getmembers()
        require(all(member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    for member in members) and {member.name for member in members} == set(expected_files),
                'Unsafe or mismatched archive member inventory')
        for member in members:
            content = stream.extractfile(member).read()
            expected = expected_files[member.name]
            digest = hashlib.sha256(content).hexdigest()
            require(len(content) == expected['bytes'] and digest == expected['sha256'],
                    f'Archive member hash/size differs: {member.name}')
            local = _inside(native_root, member.name)
            require(local.is_file() and sha(local) == digest,
                    f'Native baseline file differs from authenticated archive: {member.name}')
            if member.name == 'plan.json':
                require(digest == sha(native_root / 'plan.json'), 'Native plan is not the archived plan')


@contextmanager
def authenticate_baseline(name: str):
    module, evidence_root, _old_native_root = STUDIES[name]
    entries = verify_sealed_folder(evidence_root)
    protocol = c.unseal(evidence_root / 'protocol.json')
    qualification = c.unseal(evidence_root / 'qualification.json')
    archive = c.unseal(evidence_root / 'archive-manifest.json')
    require(qualification.get('status') == 'accepted' and isinstance(qualification.get('accepted'), dict) and
            qualification.get('accepted') and
            qualification.get('target_candidate_attempts') == 0 and
            len(qualification.get('records', [])) == 1 and
            qualification['records'][0].get('status') == 'accepted',
            f'Baseline-only accepted qualification required: {name}')
    require(qualification.get('protocol_sha256') == sha(evidence_root / 'protocol.json'),
            f'Qualification protocol binding differs: {name}')
    require(protocol.get('source_bindings') and protocol.get('historical_corpus_sha256'),
            f'Qualification source bindings missing: {name}')
    for source, expected in protocol['source_bindings'].items():
        source_copy = _inside(evidence_root / 'sources', source)
        require(source_copy.is_file() and sha(source_copy) == expected,
                f'Archived source binding differs: {name}/{source}')
    archive_path = _inside(evidence_root, archive['archive'])
    with TemporaryDirectory(prefix='isaforge-size-coverage-') as temporary:
        native_root = Path(temporary) / 'native'
        restore_archive(evidence_root, archive, native_root)
        try:
            verify_native_archive_members(archive_path, archive, native_root)
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
        plan = module.validate_inputs(native_root)
        require(plan['context_id'] == qualification['records'][0].get('context_id'),
                f'Native baseline context differs: {name}')
        module.require_zero_candidates(native_root)
        with module.registration():
            # This reproduces and authenticates the existing four-operation result.
            discovery = guarded.authenticate_discovery(native_root)
        require(discovery.get('context_id') == plan['context_id'] and
                discovery.get('actual_pool_size') == len(discovery.get('pool', [])),
                f'Existing cap-4 discovery differs: {name}')
        calibration = c.read(native_root / 'inputs/latency-calibration.json')
        profile_path = _inside(native_root, discovery['profile'])
        profile = c.read(profile_path)
        baseline = dict(performance=discovery['baseline_performance'])
        yield (module, evidence_root, native_root, entries, protocol, qualification,
               archive, plan, discovery, profile, calibration, baseline)


@contextmanager
def extraction_size(max_size):
    require(max_size in CAPS, 'Only declared max operation sizes 4, 5, and 6 are supported')
    original = lowering.discovery.extractCandidates

    def scoped(program, runs, starts, maxSize=5, limit=None):
        return original(program, runs, starts, maxSize=max_size, limit=limit)

    lowering.discovery.extractCandidates = scoped
    try:
        yield
    finally:
        lowering.discovery.extractCandidates = original


class AnalysisTimeout(TimeoutError):
    pass


@contextmanager
def source_deadline(seconds=60):
    if not hasattr(signal, 'SIGALRM'):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)
    def expired(_signum, _frame):
        raise AnalysisTimeout(f'Exploratory extraction exceeded {seconds}s/source')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _lowered_inputs(discovery, native_root):
    image = _inside(native_root, discovery['baseline_image'])
    folder = image.parent.parent
    assembly = (folder / 'program.s').read_text()
    marked, sites = lowering.mark_assembly(assembly)
    require(marked == (folder / 'marked.S').read_text(), 'Marked assembly differs from original baseline')
    original_hex = folder / 'original/firmware.hex'
    require(sha(image) == sha(original_hex), 'Marked baseline image differs from original')
    site_map = lowering.map_sites(sites, (image.parent / 'symbols.txt').read_text())
    program = lowering.read_program((image.parent / 'disassembly.txt').read_text())
    return program, site_map


def _candidate_summary(candidate, projected):
    feature = candidate['features']
    public = projected[candidate['formula']]
    return {'formula': candidate['formula'], 'candidate_id': candidate.get('candidate_id'),
        'operation_count': feature['tree_op_count'],
        'total_profile_replacements': candidate['total_custom_instructions'],
        'timed_region_replacements': candidate['region_custom_instructions'],
        'expected_instruction_savings': candidate['expected_instruction_reduction'],
        'projected_cycle_reduction': public['latency_features']['estimated_cycle_reduction']}


def _extractor_view(rows):
    derived_only = {'candidate_id', 'lowering_check', 'assembly', 'assembly_sha256'}
    return [{key: value for key, value in row.items() if key not in derived_only} for row in rows]


def _analyze_study_values(name: str, values):
    module, evidence_root, native_root, entries, protocol, qualification, archive, plan, cap4_discovery, profile, calibration, baseline = values
    program, site_map = _lowered_inputs(cap4_discovery, native_root)
    extractor = getattr(module, 'variable', module)
    output = {'study': name, 'evidence': {'qualification_manifest_sha256': sha(evidence_root / 'manifest.json'),
        'protocol_sha256': sha(evidence_root / 'protocol.json'), 'qualification_sha256': sha(evidence_root / 'qualification.json'),
        'archive_manifest_sha256': sha(evidence_root / 'archive-manifest.json'), 'raw_archive_sha256': archive['sha256'],
        'plan_sha256': sha(native_root / 'plan.json'), 'discovery_sha256': sha(native_root / 'discovery/discovery.json'),
        'profile_sha256': sha(_inside(native_root, cap4_discovery['profile']))},
        'context_id': plan['context_id'], 'source_bindings': protocol['source_bindings'], 'caps': {}}
    cap4_signature = None
    for cap in CAPS:
        with extraction_size(cap):
            derived = extractor.variable_extract_pool(program, profile, site_map, plan['pool_size'], calibration)
        if cap == 4:
            for key, value in derived.items():
                expected = cap4_discovery.get(key)
                if key in ('pool', 'executable_candidates'):
                    require(_extractor_view(value) == _extractor_view(expected or []),
                            f'Cap-4 candidate records differ from authenticated pool: {name}/{key}')
                else:
                    require(value == expected, f'Cap-4 metadata differs from authenticated pool: {name}/{key}')
        for candidate in derived['pool']:
            candidate['candidate_id'] = c.digest([plan['context_id'], candidate['formula']])
            candidate['lowering_check'] = lowering.verify_lowering(candidate, program,
                                                                    cap4_discovery['block_starts'])
        with module.registration():
            projected_rows = module.public_projection(native_root, plan,
                {**cap4_discovery, **derived}, baseline, calibration)
        projected = {r['formula']: r for r in projected_rows}
        require(len(projected) == len(projected_rows) == len(derived['pool']),
                f'Projection roster differs from candidate pool: {name}/cap{cap}')
        formulas = [_candidate_summary(candidate, projected) for candidate in derived['pool']]
        cap_result = {'max_operation_size': cap, 'raw_formula_count': derived['raw_formula_count'],
            'executable_formula_count': derived['executable_formula_count'],
            'calibrated_relocation_safe_formula_count': derived['eligible_formula_count'],
            'selected_pool_count': len(derived['pool']), 'computational_pool_cap': plan['pool_size'],
            'formulas': formulas,
            'projected_opportunity': {'maximum_cycle_reduction': max(
                (row['projected_cycle_reduction'] for row in formulas), default=0.0),
                'candidate_count_with_nonzero_projection': sum(row['projected_cycle_reduction'] > 0 for row in formulas)},
            'benefit_or_occurrence_filters_applied': False}
        if cap == 4:
            expected = cap4_discovery
            cap_result['matches_authenticated_cap4_discovery'] = True
            cap4_signature = [(c['formula'], c['candidate_id']) for c in derived['pool']]
            cap_result['signed_candidate_count'] = expected['actual_pool_size']
        else:
            cap_result['matches_authenticated_cap4_discovery'] = None
        output['caps'][str(cap)] = cap_result
    output['cap4_candidate_roster'] = cap4_signature
    output['scope'] = 'Exploratory baseline-only extraction and public projection. No candidate labels, target outcomes, or model inputs used.'
    return output


def analyze_study(name: str):
    with authenticate_baseline(name) as values:
        return _analyze_study_values(name, values)


def analyze(output_path=DEFAULT_OUTPUT):
    output_path = Path(output_path).resolve()
    require(not output_path.exists(), 'Use a fresh exploratory report path')
    results, errors = {}, {}
    for name in STUDIES:
        started = time.monotonic()
        try:
            with source_deadline(60):
                results[name] = analyze_study(name)
            results[name]['elapsed_host_seconds'] = time.monotonic() - started
        except (AnalysisTimeout, ValueError, OSError) as error:
            errors[name] = {'status': 'not_completed', 'reason': str(error),
                            'elapsed_host_seconds': time.monotonic() - started}
    report = {'schema': SCHEMA, 'scope': 'baseline-only exploratory coverage; not a qualification, label, or selection result',
        'declared_max_operation_sizes': list(CAPS), 'extractor': 'existing src.candidates.extractCandidates, existing operation/block/dataflow logic and existing guards/calibration; scoped in-memory maxSize override only',
        'studies': results, 'not_completed': errors, 'candidate_measurements_or_labels_used': 0,
        'model_fits': 0, 'native_jobs': 0, 'no_benefit_or_occurrence_filter': True,
        'script_sha256': sha(Path(__file__))}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c.seal(output_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = analyze(args.output)
    print(json.dumps({name: {cap: (record.get('calibrated_relocation_safe_formula_count'),
        record.get('projected_opportunity', {}).get('maximum_cycle_reduction'))
        for cap, record in data['caps'].items()} for name, data in report['studies'].items()}, indent=2))
    if report['not_completed']:
        print(json.dumps({'not_completed': report['not_completed']}))


if __name__ == '__main__':
    main()

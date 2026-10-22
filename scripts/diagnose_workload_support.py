"""Replay baseline-only extraction support from the preserved qualification archives.

No compiler, candidate lowering, hardware evaluation, fitting or original
generated root is used. Re-run with a fresh --output to reproduce support.json.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path, PurePosixPath
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import assembly_lowering as al, codesign as c
from isaforge import guarded_workload as g, latency_features as lf
from isaforge import opportunity_workload as w, relocation_guard as guard
from isaforge.speedup_corpus import validate_isa
from scripts.reproduce_codesign import restore_archive

SOURCE = 'scripts/diagnose_workload_support.py'
QUALIFICATION = 'results/2026-10-22-useful-source-qualification'
OUTPUT = 'results/2026-10-22-workload-support'
PROTOCOL_SHA = 'a5a87427c3dd9d9b2e0ae2cfaaf5dae54c1552883466941ebf2163267aa0f388'


def relative(name):
    path = PurePosixPath(name)
    c.require(isinstance(name, str) and not path.is_absolute() and '..' not in path.parts,
              'Relative provenance path required')
    return path.as_posix()


def bindings(values, *, snapshot=None):
    for name, digest in values.items():
        relative(name)
        c.require(c.sha(c.ROOT/name) == digest, 'Bound source changed: '+name)
        if snapshot is not None:
            c.require(c.sha(snapshot/'sources'/name) == digest, 'Source snapshot changed: '+name)


def authenticate(snapshot):
    manifest = c.unseal(snapshot/'manifest.json')
    actual = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*')
              if p.is_file() and p.name not in ('manifest.json', 'manifest.json.sha256')}
    c.require(set(manifest) == actual, 'Qualification membership differs')
    for name, digest in manifest.items():
        relative(name)
        c.require(c.sha(snapshot/name) == digest, 'Qualification evidence changed: '+name)
    protocol, result = (c.unseal(snapshot/name) for name in ('protocol.json', 'qualification.json'))
    c.require(c.sha(snapshot/'protocol.json') == PROTOCOL_SHA == result['protocol_sha256'],
              'Exact completed qualification protocol required')
    c.require(all(protocol[key] == value for key, value in w.PROTOCOL.items() if key != 'schema'),
              'Qualification gates changed')
    bindings(protocol['source_bindings'], snapshot=snapshot)
    c.require(result['target_candidate_attempts'] == protocol['target_candidate_attempts'] == 0 and
              result['accepted'] == {} and result['status'] == 'insufficient_qualified_families',
              'Completed zero-candidate rejected qualification required')
    c.require([row['workload'] for row in result['records']] == protocol['order'], 'Source order differs')
    for row in result['records']:
        name = row['workload']
        c.require(row['family'] == w.FAMILIES[name], 'Source family differs')
        if name in w.STATIC_REJECTIONS:
            c.require(row['status'] == 'static_rejection' and row['commands'] == [] and
                      row['reason'] == w.STATIC_REJECTIONS[name], 'Static rejection differs')
            continue
        c.require(row['status'] == 'rejected' and row['failed_phase'] == 'discover' and
                  [cmd['phase'] for cmd in row['commands']] == ['prepare', 'discover'],
                  'Preserved prepare/discover failure required')
        for cmd in row['commands']:
            folder = snapshot/relative(cmd['observation'])
            record = c.unseal(folder/'record.json')
            c.require(record == cmd['record'] and record['metadata'] == dict(workload=name,
                phase=cmd['phase'], protocol_sha256=PROTOCOL_SHA), 'Observer record differs')
            for stream in ('stdout', 'stderr'):
                c.require(c.sha(folder/(stream+'.txt')) == record[stream+'_sha256'], 'Observer stream changed')
            expected = ('success', 0) if cmd['phase'] == 'prepare' else ('nonzero_exit', 1)
            c.require((record['status'], record['returncode']) == expected, 'Unexpected phase result')
        c.require('Too few calibrated executable candidates' in (folder/'stderr.txt').read_text(),
                  'Different discovery failure')
    return protocol, result


def profile_support(root, archive):
    entries = {row['path'] for row in archive['files']}
    c.require(not any(name.startswith(('attempt-ledger/candidate_', 'measurements/candidate_'))
                      for name in entries), 'Candidate evidence is outside baseline-only scope')
    c.require(not (root/'discovery/discovery.json').exists(), 'Expected preserved failed discovery')
    plan = w.validate_inputs(root)
    bindings(plan['source_bindings'])
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/relative(name)) == digest, 'Bound input changed: '+name)
    for source in (root/'sources').rglob('*'):
        if source.is_file():
            name = source.relative_to(root/'sources').as_posix()
            c.require(plan['source_bindings'].get(name) == c.sha(source), 'Archived source differs: '+name)
    attempt = root/'discovery/attempt-000'
    marked, sites = al.mark_assembly((attempt/'program.s').read_text())
    c.require(marked == (attempt/'marked.S').read_text(), 'Marked assembly derivation differs')
    c.require(c.sha(attempt/'original/firmware.hex') == c.sha(attempt/'marked/firmware.hex'),
              'Marking changed original firmware')
    disassembly = (attempt/'marked/disassembly.txt').read_text()
    c.require(validate_isa(disassembly)['custom_static_sites'] == 0, 'Original image has custom instructions')
    site_map = al.map_sites(sites, (attempt/'marked/symbols.txt').read_text())
    program = al.read_program(disassembly)
    profile = c.read(attempt/'profile/simulation.json')
    performance = g.w.validate_execution(profile)
    memory = g.q.validate_memory(profile, spec=plan['memory_partition'])
    counts = {int(pc): count for pc, count in profile['region_counts'].items()}
    c.require(all(pc in program and type(count) is int and count > 0 for pc, count in counts.items()),
              'Invalid timed instruction profile')
    timed = sum(counts.values())
    c.require(timed+1 == performance['instructions'], 'Timed CSR boundary differs')
    covered = sum(count for pc, count in counts.items() if pc in site_map)
    outside = Counter()
    for pc, count in counts.items():
        if pc not in site_map:
            outside[program[pc].get('symbol') or '<unknown>'] += count
    calibration = c.read(root/'inputs/latency-calibration.json')
    c.require(calibration['context_id'] == plan['calibration_compatibility']['context_id'],
              'Calibration context differs')
    lf.latency_table(calibration)
    raw = g.ORIGINAL_EXTRACT(program, profile, site_map, plan['pool_size'])
    safe = guard.filter_executable_candidates(raw, list(site_map.values()))
    eligible, uncalibrated = [], []
    for candidate in safe['executable_candidates']:
        try:
            features = lf.candidate_features(candidate, program, performance['cycles'],
                                             performance['instructions'], calibration)
        except ValueError as error:
            uncalibrated.append(dict(formula=candidate['formula'], reason=str(error)))
            continue
        eligible.append(dict(formula=candidate['formula'],
            timed_replacements=candidate['region_custom_instructions'], latency_features=features))
    both = [row['formula'] for row in eligible
            if row['timed_replacements'] >= w.PROTOCOL['minimum_timed_replacements']
            and row['latency_features']['estimated_cycle_reduction'] >= w.PROTOCOL['minimum_calibrated_cycle_reduction']]
    paths = ['plan.json', 'inputs/program.c', 'inputs/embench_firmware.c', 'inputs/latency-calibration.json',
             *['discovery/attempt-000/'+p for p in ('program.s', 'marked.S', 'marked/symbols.txt',
                 'marked/disassembly.txt', 'original/firmware.hex', 'marked/firmware.hex', 'profile/simulation.json')]]
    return dict(workload=plan['workload'], context_id=plan['context_id'], status='discovery_rejected',
        upstream=plan['upstream'], inputs_digest=c.digest(plan['inputs']),
        source_bindings=plan['source_bindings'], source_bindings_digest=c.digest(plan['source_bindings']),
        artifact_sha256={path:c.sha(root/path) for path in paths},
        raw_formula_count=raw['raw_formula_count'], mapped_executable_count=raw['executable_formula_count'],
        rejected_occurrences=raw['rejected_occurrences'], relocation_guard=safe['relocation_guard'],
        uncalibrated=uncalibrated, calibrated_eligible_count=len(eligible), eligible=eligible,
        twelve_formula_gate_passed=len(eligible) >= w.POOL_SIZE,
        both_numeric_minima_formulas=both,
        maximum_cycle_reduction=max((r['latency_features']['estimated_cycle_reduction'] for r in eligible), default=None),
        maximum_timed_replacements=max((r['timed_replacements'] for r in eligible), default=0),
        baseline_performance=performance, memory_check=memory,
        timed_source_coverage=dict(profile_instructions=timed, counter_instructions=performance['instructions'],
            counter_boundary_difference=1, mapped_source_instructions=covered,
            outside_mapped_source_instructions=timed-covered, mapped_fraction=covered/timed,
            outside_symbols=dict(sorted(outside.items())),
            scope='Single-word marked program-source statements only; outside sites include pseudo-op expansions and linked runtime/helper code. Outside execution is not proven safely rewritable.'))


def diagnose(snapshot, output):
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    c.require(not output.exists(), 'Fresh diagnostic output required')
    c.require(not output.is_relative_to(snapshot), 'Output must be separate from the qualification snapshot')
    for ancestor in output.parents:
        c.require(not any((ancestor/name).is_file() and (ancestor/(name+'.sha256')).is_file()
                  for name in ('manifest.json', 'archive-manifest.json', 'source-manifest.json',
                               'qualification.json', 'protocol.json')),
                  'Output must not be inside an already sealed result root')
    protocol, qualification = authenticate(snapshot)
    scratch_parent = c.ROOT/'generated'
    scratch_parent.mkdir(exist_ok=True)
    rows, sources = [], {SOURCE:c.sha(c.ROOT/SOURCE), **protocol['source_bindings']}
    with tempfile.TemporaryDirectory(prefix='workload-support-', dir=scratch_parent) as scratch:
        for original in qualification['records']:
            name = original['workload']
            if original['status'] == 'static_rejection':
                rows.append(dict(workload=name, status='static_rejection', reason=original['reason'],
                    upstream_source=w.program(name), source_sha256=w.WORKLOADS[name][1]))
                continue
            folder = snapshot/name
            archive = c.unseal(folder/'archive-manifest.json')
            relative(archive['archive'])
            restored = Path(scratch)/name
            restore_archive(folder, archive, restored)
            row = profile_support(restored, archive)
            for source, digest in row.pop('source_bindings').items():
                c.require(source not in sources or sources[source] == digest, 'Source binding conflicts')
                sources[source] = digest
            c.require(row['workload'] == name and not row['twelve_formula_gate_passed'],
                      'Derived support disagrees with preserved rejection')
            row['archive'] = dict(path=name+'/'+archive['archive'], sha256=archive['sha256'],
                                  inventory_sha256=c.sha(folder/'archive-manifest.json'))
            rows.append(row)
    report = dict(schema='isaforge-archive-workload-support-v1',
        qualification=QUALIFICATION, protocol_sha256=PROTOCOL_SHA,
        qualification_sha256=c.sha(snapshot/'qualification.json'), manifest_sha256=c.sha(snapshot/'manifest.json'),
        source_bindings=dict(sorted(sources.items())),
        target_candidate_attempts=0, original_profiles_replayed=7, static_rejections=1,
        native_jobs_run=0, candidate_lowerings_run=0, models_fitted=0,
        scope='Baseline-only archive replay; calibrated estimates are not candidate measurements. All qualification failures and gates remain unchanged.',
        workloads=rows)
    output.mkdir(parents=True)
    c.seal(output/'support.json', report)
    c.seal(output/'manifest.json', {'support.json':c.sha(output/'support.json'),
                                  'support.json.sha256':c.sha(output/'support.json.sha256')})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, default=ROOT/QUALIFICATION)
    parser.add_argument('--output', type=Path, default=ROOT/OUTPUT)
    args = parser.parse_args(argv)
    report = diagnose(args.qualification, args.output)
    print({row['workload']:row.get('calibrated_eligible_count', row['status']) for row in report['workloads']})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

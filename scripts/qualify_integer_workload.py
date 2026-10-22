"""Predeclare expint then bubblesort with a fixed six-formula acceptance gate.

This new source sequence does not retry either rejected Levenshtein context.
No model fitting or candidate measurement is performed by qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import integer_workload as workload, codesign as c, observed_command
from scripts.reproduce_codesign import pack_archive

SOURCE = 'scripts/qualify_integer_workload.py'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE_PARENT = 'generated/live-gp-integer-six-2026-10-22'
OUTPUT = 'results/2026-10-22-integer-six-qualification'
PHASES = ('prepare', 'discover', 'baseline', 'public', 'freeze')
REJECTIONS = ('results/2026-10-21-blind-qualification',
              'results/2026-10-22-levenshtein-qualification',
              'results/2026-10-22-levenshtein-strlen-qualification')
SOURCES = (SOURCE, workload.SOURCE, workload.ORIGINAL_BLIND_SOURCE,
           'isaforge/observed_command.py', 'scripts/reproduce_codesign.py', workload.LICENSE,
           *(workload.program(name) for name in workload.WORKLOADS))


def zero(native):
    c.require(not list((native / 'attempt-ledger').glob('candidate_*.json')) and
              not list((native / 'measurements').glob('candidate_*')),
              'Qualification requires zero candidate attempts')


def phase_command(phase, native, reference, name):
    c.require(phase in PHASES and name in workload.WORKLOADS, 'Declared source/phase required')
    argv = [sys.executable, '-m', 'isaforge.integer_workload', phase, '--root', str(native)]
    if phase == 'prepare': argv += ['--workload', name, '--reference-root', str(reference)]
    return argv


def qualify(output, native_parent, reference):
    output, native_parent, reference = (Path(path).resolve() for path in (output, native_parent, reference))
    c.require(not output.exists() and not native_parent.exists(), 'Fresh qualification/native parent required')
    c.require(output.is_relative_to(ROOT) and native_parent.is_relative_to(ROOT) and
              not output.is_relative_to(native_parent) and not native_parent.is_relative_to(output),
              'Separate repository-local evidence/native roots required')
    c.require(reference == (ROOT / REFERENCE).resolve() and (reference / 'plan.json').is_file(),
              'Exact preserved reference root required')
    c.require(workload.POOL_SIZE == 6 and list(workload.WORKLOADS) == ['expint', 'bubblesort'] and
              workload.PARTITION == dict(ram_bytes=8192, program_limit=6400, stack_floor=6528,
                                        stack_bytes=1664, minimum_guard_bytes=128),
              'Predeclared fixed-six original-memory protocol required')
    for name, (_, digest) in workload.WORKLOADS.items():
        c.require(c.sha(ROOT / workload.program(name)) == digest, 'Pinned original integer source differs')
    preserved = {}
    for name in REJECTIONS:
        folder = ROOT / name
        entries = c.unseal(folder / 'manifest.json')
        c.require(all((folder / key).resolve().is_relative_to(folder.resolve()) and
                      c.sha(folder / key) == value for key, value in entries.items()),
                  'Earlier qualification rejection evidence changed')
        preserved[name] = c.sha(folder / 'manifest.json')
    protocol = dict(schema='isaforge-integer-six-qualification-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(), order=list(workload.WORKLOADS),
        stop_after_successful_sources=1, phases=list(PHASES), pool_size=6,
        memory_partition=dict(workload.PARTITION), reference_root=REFERENCE,
        reference_plan_sha256=c.sha(reference / 'plan.json'),
        native_parent=native_parent.relative_to(ROOT).as_posix(), target_candidate_attempts=0,
        upstream=dict(suite='BEEBS', commit=workload.UPSTREAM_COMMIT),
        original_inputs=dict(expint=dict(n=50, x=1, expected_return=3883),
                             bubblesort=dict(elements=100, initial='0,-1,...,-99; original 101-element storage',
                                             verifier='All original 100 output elements checked against -99,...,0')),
        selection_rule='First declared source passing original input/verifier, checked baseline and exactly six legal calibrated formulas. No source/partition changes, no retry and no candidate outcomes.',
        pool_justification='New six-candidate source protocol declared before either source discovery, following the earlier DCT-six precedent. Both twelve-candidate Levenshtein contexts and RC4 rejection remain preserved; none is retried.',
        preserved_qualification_manifests=preserved,
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        workers=1, build_workers=2, phase_timeout_seconds=3600,
        clock_contract='Separate paired UTC and monotonic endpoints; no mixed-clock inferred end or uninterrupted wall-time claim.',
        phase_commands={name: {phase: phase_command(phase, native_parent / name, reference, name)
                              for phase in PHASES} for name in workload.WORKLOADS})
    output.mkdir(parents=True)
    c.seal(output / 'protocol.json', protocol)
    shutil.copyfile(reference / 'plan.json', output / 'reference-plan.json')
    for name in SOURCES:
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    c.seal(output / 'source-manifest.json', protocol['source_bindings'])
    records, accepted = [], {}
    result = dict(schema='isaforge-integer-six-qualification-result-v1',
                  protocol_sha256=c.sha(output / 'protocol.json'), records=records,
                  accepted=accepted, successful_sources=0, target_candidate_attempts=0, status='started')

    def seal_progress():
        commands = [cmd for row in records for cmd in row['commands']]
        result.update(successful_sources=len(accepted),
            recorded_subprocess_monotonic_seconds=sum(cmd['record']['durations']['monotonic_elapsed_seconds'] for cmd in commands),
            recorded_subprocess_utc_seconds=sum(cmd['record']['durations']['utc_elapsed_seconds'] for cmd in commands),
            clock_disagreement_phase_count=sum(bool(cmd['record']['durations']['clock_disagreement_detected']) for cmd in commands))
        c.seal(output / 'qualification.json', result)
        c.seal(output / 'manifest.json', {path.relative_to(output).as_posix(): c.sha(path)
            for path in sorted(output.rglob('*')) if path.is_file() and
            path.relative_to(output).as_posix() not in ('manifest.json', 'manifest.json.sha256')})

    seal_progress()
    for name in protocol['order']:
        native = native_parent / name
        folder = output / name; folder.mkdir()
        row = dict(workload=name, root=native.relative_to(ROOT).as_posix(), status='started', commands=[])
        records.append(row)
        try:
            for index, phase in enumerate(PHASES):
                zero(native)
                observed = folder / 'commands' / f'{index:02d}-{phase}'
                try:
                    record = observed_command.run(protocol['phase_commands'][name][phase], observed,
                        cwd=ROOT, metadata=dict(workload=name, phase=phase,
                                               protocol_sha256=c.sha(output / 'protocol.json')),
                        timeout_seconds=protocol['phase_timeout_seconds'])
                except BaseException:
                    if (observed / 'record.json').exists():
                        row['commands'].append(dict(phase=phase, observation=observed.relative_to(output).as_posix(),
                                                    record=c.unseal(observed / 'record.json')))
                    raise
                row['commands'].append(dict(phase=phase, observation=observed.relative_to(output).as_posix(), record=record))
                zero(native)
                print(f'{name} {phase}: {record["status"]}', flush=True)
                if record['status'] != 'success' or record.get('returncode') != 0:
                    row.update(status='rejected', failed_phase=phase)
                    break
                seal_progress()
            else:
                plan = workload.validate_inputs(native)
                frozen = c.unseal(native / 'evaluation-protocol.json')
                c.require(plan['workload'] == name and len(frozen['pool_names']) == 6 and
                          len(set(frozen['pool_names'])) == 6 and frozen['maximum_candidate_attempts'] == 6,
                          'Exactly six frozen legal formulas required')
                row.update(status='accepted', context_id=plan['context_id'])
                accepted[name] = row['root']
        except BaseException as error:
            row.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                       error=repr(error), failed_phase=phase if 'phase' in locals() else None)
            result['status'] = row['status']
            raise
        finally:
            try:
                zero(native)
                if native.exists():
                    c.seal(folder / 'archive-manifest.json', pack_archive(native, folder / 'raw.tar.gz'))
            finally: seal_progress()
        if accepted: break
    result['status'] = 'accepted' if accepted else 'no_source_qualified'
    seal_progress()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    parser.add_argument('--native-parent', type=Path, default=ROOT / NATIVE_PARENT)
    parser.add_argument('--reference-root', type=Path, default=ROOT / REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_parent, args.reference_root)
    print({key: result[key] for key in ('status', 'accepted', 'successful_sources', 'target_candidate_attempts')})
    return 0 if result['accepted'] else 1


if __name__ == '__main__': raise SystemExit(main())

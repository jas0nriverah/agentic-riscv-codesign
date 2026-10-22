"""One-source, zero-candidate Levenshtein qualification with paired clock records.

This is a new protocol. The original source, blind workload adapter, inputs,
extractor, twelve-candidate gate and checked processor partition stay frozen.
Each blocking phase is observed separately; failures are archived without retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import blind_workload as workload, codesign as c, observed_command
from scripts.reproduce_codesign import pack_archive

SOURCE = 'scripts/qualify_levenshtein.py'
PROGRAM = 'benchmarks/beebs/levenshtein/liblevenshtein.c'
PROGRAM_SHA256 = 'fd1ee0e23bab6db0182b32618bc3622a3ce0399714b662076d053d98fb7193f6'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE = 'generated/live-gp-levenshtein-2026-10-22'
OUTPUT = 'results/2026-10-22-levenshtein-qualification'
PHASES = ('prepare', 'discover', 'baseline', 'public', 'freeze')
STRINGS = ('srrjngre', 'asfcjnsdkj', 'string', 'msd', 'strings')
EXPECTED_DISTANCES = ((0, 7, 4, 8, 4), (7, 0, 8, 8, 8), (4, 8, 0, 6, 1),
                      (8, 8, 6, 0, 7), (4, 8, 1, 7, 0))
SOURCES = (SOURCE, workload.SOURCE, PROGRAM, workload.LICENSE,
           'hardware/embench_firmware.c', 'isaforge/observed_command.py',
           'scripts/reproduce_codesign.py')


def reference_distances():
    """Independent rolling-row reference; never calls the native benchmark."""
    result = []
    for left in STRINGS:
        distances = []
        for right in STRINGS:
            row = list(range(len(right) + 1))
            for i, a in enumerate(left, 1):
                following = [i]
                for j, b in enumerate(right, 1):
                    following.append(min(following[-1] + 1, row[j] + 1,
                                         row[j - 1] + (a != b)))
                row = following
            distances.append(row[-1])
        result.append(tuple(distances))
    c.require(tuple(result) == EXPECTED_DISTANCES and sum(map(sum, result)) == 122,
              'Independent original-input edit-distance reference differs')
    return [list(row) for row in result]


def zero_candidate_attempts(native):
    native = Path(native)
    c.require(not list((native / 'attempt-ledger').glob('candidate_*.json')) and
              not list((native / 'measurements').glob('candidate_*')),
              'Qualification must preserve zero candidate attempts')


def phase_command(phase, native, reference):
    c.require(phase in PHASES, 'Only the five declared qualification phases are allowed')
    command = [sys.executable, '-m', 'isaforge.blind_workload', phase,
               '--root', str(native)]
    if phase == 'prepare':
        command += ['--workload', 'levenshtein', '--reference-root', str(reference)]
    return command


def qualify(output, native, reference):
    output, native, reference = (Path(path).resolve() for path in (output, native, reference))
    c.require(not output.exists() and not native.exists(), 'Fresh qualification and native directories required')
    c.require(output.is_relative_to(ROOT) and native.is_relative_to(ROOT) and
              not output.is_relative_to(native) and not native.is_relative_to(output),
              'Separate repository-local evidence and native directories required')
    c.require(reference == (ROOT / REFERENCE).resolve() and (reference / 'plan.json').is_file(),
              'Exact preserved CRC32 reference root required')
    c.require(c.sha(ROOT / PROGRAM) == PROGRAM_SHA256 and workload.POOL_SIZE == 12 and
              workload.PARTITION == dict(ram_bytes=8192, program_limit=6400, stack_floor=6528,
                                        stack_bytes=1664, minimum_guard_bytes=128),
              'Pinned original source, twelve-formula gate and common partition required')
    protocol = dict(schema='isaforge-levenshtein-qualification-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(), order=['levenshtein'],
        phases=list(PHASES), pool_size=12, memory_partition=dict(workload.PARTITION),
        upstream=dict(suite='BEEBS', commit=workload.UPSTREAM_COMMIT, source=PROGRAM,
                      source_sha256=PROGRAM_SHA256),
        original_strings=list(STRINGS), independently_computed_distances=reference_distances(),
        verifier=dict(original_aggregate_sum=122, unchanged=True,
                      limitation='Upstream checks the aggregate sum, not each pair; offsetting errors can cancel. Independent pair references are static checks only.'),
        selection_rule='Accept this sole source only after unchanged baseline/verifier, checked memory and twelve legal calibrated formulas; otherwise preserve failure and stop. No fallback, input change, partition change or candidate attempt.',
        native_root=native.relative_to(ROOT).as_posix(), reference_root=REFERENCE,
        reference_plan_sha256=c.sha(reference / 'plan.json'),
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        observation='Each blocking CLI phase has raw paired UTC/monotonic endpoints and stdout/stderr; clock domains remain distinct. No inferred mixed-clock end instants.',
        phase_timeout_seconds=3600, workers=1, build_workers=2, target_candidate_attempts=0)
    protocol['phase_commands'] = {phase: phase_command(phase, native, reference) for phase in PHASES}
    output.mkdir(parents=True)
    c.seal(output / 'protocol.json', protocol)
    shutil.copyfile(reference / 'plan.json', output / 'reference-plan.json')
    for name in SOURCES:
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    c.seal(output / 'source-manifest.json', protocol['source_bindings'])
    commands = []
    summary = dict(schema='isaforge-levenshtein-qualification-result-v1',
                   protocol_sha256=c.sha(output / 'protocol.json'), status='started',
                   accepted=False, commands=commands, target_candidate_attempts=0)
    c.seal(output / 'qualification.json', summary)
    try:
        for index, phase in enumerate(PHASES):
            zero_candidate_attempts(native)
            folder = output / 'commands' / f'{index:02d}-{phase}'
            try:
                record = observed_command.run(protocol['phase_commands'][phase], folder,
                    cwd=ROOT, metadata=dict(workload='levenshtein', phase=phase,
                                           protocol_sha256=c.sha(output / 'protocol.json')),
                    timeout_seconds=protocol['phase_timeout_seconds'])
            except BaseException:
                if (folder / 'record.json').exists():
                    commands.append(dict(phase=phase, observation=folder.relative_to(output).as_posix(),
                                         record=c.unseal(folder / 'record.json')))
                raise
            commands.append(dict(phase=phase, observation=folder.relative_to(output).as_posix(),
                                 record=record))
            zero_candidate_attempts(native)
            if record.get('status') != 'success' or record.get('returncode') != 0:
                summary.update(status='rejected', failed_phase=phase)
                break
            c.seal(output / 'qualification.json', summary)
        else:
            plan = workload.validate_inputs(native)
            frozen = c.unseal(native / 'evaluation-protocol.json')
            c.require(plan['workload'] == 'levenshtein' and len(frozen['pool_names']) == 12 and
                      len(set(frozen['pool_names'])) == 12 and frozen['maximum_candidate_attempts'] == 12,
                      'Complete frozen twelve-candidate source pool required')
            summary.update(status='accepted', accepted=True, context_id=plan['context_id'],
                           pool_names=frozen['pool_names'])
    except BaseException as error:
        summary.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                       error=repr(error), failed_phase=phase if 'phase' in locals() else None)
        raise
    finally:
        try:
            zero_candidate_attempts(native)
            if native.exists():
                c.seal(output / 'archive-manifest.json', pack_archive(native, output / 'raw.tar.gz'))
        except BaseException as error:
            summary.update(status='failed', accepted=False, archive_or_zero_attempt_error=repr(error))
            raise
        finally:
            summary['recorded_subprocess_monotonic_seconds'] = sum(
                row['record']['durations']['monotonic_elapsed_seconds'] for row in commands)
            summary['recorded_subprocess_utc_seconds'] = sum(
                row['record']['durations']['utc_elapsed_seconds'] for row in commands)
            summary['clock_disagreement_phase_count'] = sum(
                bool(row['record']['durations']['clock_disagreement_detected']) for row in commands)
            c.seal(output / 'qualification.json', summary)
            c.seal(output / 'manifest.json', {path.relative_to(output).as_posix(): c.sha(path)
                for path in sorted(output.rglob('*')) if path.is_file() and
                path.name not in ('manifest.json', 'manifest.json.sha256')})
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT / NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT / REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_root, args.reference_root)
    print(result)
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

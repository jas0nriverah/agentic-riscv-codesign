"""One pinned N=7 Fannkuch-redux baseline qualification; no candidate measures."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, observed_command, fannkuch_workload as w
from scripts.reproduce_codesign import pack_archive

zero = w.require_zero_candidates
SOURCE = 'scripts/qualify_fannkuch.py'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE = 'generated/fannkuch-qualification-2026-10-26-r2'
OUTPUT = 'results/2026-10-26-fannkuch-qualification-r2'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
PHASES = ('prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
SOURCES = tuple(dict.fromkeys((SOURCE, 'scripts/reproduce_codesign.py',
    'isaforge/observed_command.py', *w.GATE_SOURCES)))


def phase_command(phase, native, reference):
    c.require(phase in PHASES, 'Declared Fannkuch qualification phase required')
    argv = [sys.executable, '-m', 'isaforge.fannkuch_workload', phase,
            '--root', str(native)]
    if phase == 'prepare':
        argv += ['--reference-root', str(reference)]
    return argv


def verify_outer_snapshot(output, protocol):
    """Reauthenticate the sealed protocol and its live and archived inputs."""
    output = Path(output)
    c.require(c.unseal(output / 'protocol.json') == protocol,
              'Qualification protocol changed after it was frozen')
    reference = (ROOT / protocol['reference_root'] / 'plan.json').resolve()
    expected_reference = protocol['reference_plan_sha256']
    c.require(c.sha(reference) == expected_reference and
              c.sha(output / 'reference-plan.json') == expected_reference,
              'Preserved reference plan differs from frozen outer protocol')
    c.require(c.sha(ROOT / HISTORY) == protocol['historical_corpus_sha256'],
              'Historical corpus provenance changed during qualification')
    for name, expected in protocol['source_bindings'].items():
        c.require(c.sha(ROOT / name) == expected,
                  'Live qualification source changed: ' + name)
        c.require(c.sha(output / 'sources' / name) == expected,
                  'Archived qualification source changed: ' + name)
    w.verify_source_pins()


def verify_native_plan(native, protocol, row):
    """Join the prepared target context to the already frozen outer sources."""
    plan_path = Path(native) / 'plan.json'
    c.require(plan_path.is_file(), 'Prepared Fannkuch plan is missing')
    plan = c.unseal(plan_path)
    expected_reference = c.read(ROOT / protocol['reference_root'] / 'plan.json')
    c.require(plan.get('reference_context') == expected_reference.get('context_id'),
              'Prepared native context is not derived from the frozen reference plan')
    outer_sources = protocol['source_bindings']
    for name in w.GATE_SOURCES:
        expected = outer_sources.get(name)
        c.require(expected is not None and plan['source_bindings'].get(name) == expected and
                  c.sha(ROOT / name) == expected and
                  c.sha(Path(native) / 'sources' / name) == expected,
                  'Prepared native plan/source archive differs from outer protocol: ' + name)
    c.require(plan['inputs'].get('program.c') == outer_sources[w.PROGRAM] and
              c.sha(Path(native) / 'inputs/program.c') == outer_sources[w.PROGRAM],
              'Prepared Fannkuch program differs from the independently pinned adapter')
    digest = c.sha(plan_path)
    if row.get('prepared_plan_sha256') is None:
        row['prepared_plan_sha256'] = digest
        row['context_id'] = plan['context_id']
    else:
        c.require(row['prepared_plan_sha256'] == digest and
                  row['context_id'] == plan['context_id'],
                  'Prepared native context changed between qualification phases')
    return plan


def candidate_artifacts(native):
    native = Path(native)
    paths = [*native.glob('attempt-ledger/candidate_*.json'),
             *native.glob('measurements/candidate_*')]
    return sorted(path.relative_to(native).as_posix() for path in paths)


def require_zero_and_record(native, row, result):
    found = candidate_artifacts(native)
    if found:
        row['candidate_artifacts_detected'] = found
        result['target_candidate_attempts'] = None
        result['candidate_attempt_count_status'] = 'uncertified: candidate artifacts violate qualification protocol'
        raise ValueError('Fannkuch qualification requires zero candidate attempts and artifacts')


def qualify(output, native, reference):
    output, native, reference = (Path(p).resolve() for p in (output, native, reference))
    c.require(not output.exists() and not native.exists(),
              'Fresh Fannkuch qualification and native roots required')
    c.require(output.is_relative_to(ROOT) and native.is_relative_to(ROOT) and
              not output.is_relative_to(native) and not native.is_relative_to(output) and
              reference == (ROOT / REFERENCE).resolve() and
              (reference / 'plan.json').is_file(),
              'Separate repository-local roots and exact preserved reference required')
    # Preserve historical corpus identity without reading its outcomes or fitting a model.
    c.require((ROOT / HISTORY).is_file(), 'Historical corpus provenance file required')
    w.verify_source_pins()
    protocol = dict(w.PROTOCOL, schema=w.PROTOCOL['schema'] + '-qualification',
        created_at_utc=datetime.now(timezone.utc).isoformat(), phases=list(PHASES),
        reference_root=REFERENCE, reference_plan_sha256=c.sha(reference / 'plan.json'),
        historical_corpus_sha256=c.sha(ROOT / HISTORY),
        native_root=native.relative_to(ROOT).as_posix(), target_candidate_attempts=0,
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        workers=1, build_workers=2, phase_timeout_seconds=3600,
        phase_commands={phase: phase_command(phase, native, reference) for phase in PHASES},
        qualification_rule='One exact pinned N=7 input, twelve legal executable relocation-safe calibrated candidates, and at least one same candidate meeting both public 0.5% cycle-reduction and 10 timed-replacement minima. No candidate measurement or label.',
        rejection_rule='Preserve the first rejection and archive. No retries, alternate input, changed memory/compiler context, or weakened opportunity gate.',
        candidate_dispatch_enabled=False, pool_freeze_is_candidate_authorization=False)
    output.mkdir(parents=True)
    c.seal(output / 'protocol.json', protocol)
    for name in SOURCES:
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    shutil.copyfile(reference / 'plan.json', output / 'reference-plan.json')
    row = dict(workload=w.WORKLOAD, family=w.GROUP,
        root=native.relative_to(ROOT).as_posix(), status='started', commands=[])
    result = dict(schema=w.PROTOCOL['schema'] + '-qualification-result',
        protocol_sha256=c.sha(output / 'protocol.json'), records=[row], accepted={},
        target_candidate_attempts=0, status='started')

    def seal_progress():
        commands = row['commands']
        result.update(
            recorded_subprocess_monotonic_seconds=sum(
                record['record']['durations']['monotonic_elapsed_seconds'] for record in commands),
            recorded_subprocess_utc_seconds=sum(
                record['record']['durations']['utc_elapsed_seconds'] for record in commands),
            clock_disagreement_phase_count=sum(bool(
                record['record']['durations']['clock_disagreement_detected']) for record in commands))
        c.seal(output / 'qualification.json', result)
        c.seal(output / 'manifest.json', {path.relative_to(output).as_posix(): c.sha(path)
            for path in sorted(output.rglob('*')) if path.is_file() and
            path.name not in ('manifest.json', 'manifest.json.sha256')})

    seal_progress()
    phase = None
    try:
        for index, phase in enumerate(PHASES):
            verify_outer_snapshot(output, protocol)
            if phase == 'prepare':
                c.require(not native.exists(), 'Fresh Fannkuch native root required before prepare')
            else:
                verify_native_plan(native, protocol, row)
            require_zero_and_record(native, row, result)
            observation = output / 'commands' / f'{index:02d}-{phase}'
            try:
                record = observed_command.run(protocol['phase_commands'][phase], observation,
                    cwd=ROOT, metadata=dict(workload=w.WORKLOAD, phase=phase,
                        protocol_sha256=c.sha(output / 'protocol.json')),
                    timeout_seconds=protocol['phase_timeout_seconds'])
            except BaseException:
                if (observation / 'record.json').exists():
                    row['commands'].append(dict(phase=phase,
                        observation=observation.relative_to(output).as_posix(),
                        record=c.unseal(observation / 'record.json')))
                raise
            row['commands'].append(dict(phase=phase,
                observation=observation.relative_to(output).as_posix(), record=record))
            verify_outer_snapshot(output, protocol)
            if phase == 'prepare' and record['status'] == 'success' and record['returncode'] == 0:
                verify_native_plan(native, protocol, row)
            elif native.exists() and (native / 'plan.json').is_file():
                verify_native_plan(native, protocol, row)
            require_zero_and_record(native, row, result)
            print(f'{w.WORKLOAD} {phase}: {record["status"]}', flush=True)
            if record['status'] != 'success' or record['returncode'] != 0:
                row.update(status='rejected', failed_phase=phase)
                result['status'] = 'rejected'
                break
            seal_progress()
        else:
            plan = w.validate_inputs(native)
            frozen = c.unseal(native / 'evaluation-protocol.json')
            c.require(len(frozen['pool_names']) == len(set(frozen['pool_names'])) == w.POOL_SIZE and
                      frozen['maximum_candidate_attempts'] == w.POOL_SIZE,
                      'Exact twelve-candidate discovery freeze required')
            gate = w.check_opportunity(native)
            row.update(status='accepted', context_id=plan['context_id'], gate=gate)
            result.update(status='accepted', accepted={w.WORKLOAD: row['root']})
    except BaseException as error:
        row.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
            failed_phase=phase, error=repr(error))
        result['status'] = row['status']
        raise
    finally:
        found = candidate_artifacts(native)
        if found:
            row['candidate_artifacts_detected'] = found
            result['target_candidate_attempts'] = None
            result['candidate_attempt_count_status'] = 'uncertified: candidate artifacts violate qualification protocol'
            if row.get('status') in ('started', 'accepted'):
                row['status'] = result['status'] = 'failed'
                result['accepted'] = {}
        try:
            if native.exists():
                c.seal(output / 'archive-manifest.json',
                       pack_archive(native, output / 'raw.tar.gz'))
        finally:
            seal_progress()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT / NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT / REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_root, args.reference_root)
    print({key: result[key] for key in ('status', 'accepted', 'target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())

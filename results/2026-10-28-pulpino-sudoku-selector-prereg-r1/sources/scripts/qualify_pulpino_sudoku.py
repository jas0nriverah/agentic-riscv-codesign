"""Run one source-bound, baseline-only qualification of the pinned PULPino Sudoku workload."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, observed_command
from isaforge import pulpino_sudoku_workload as w
from scripts.reproduce_codesign import pack_archive

SOURCE = 'scripts/qualify_pulpino_sudoku.py'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE = 'generated/pulpino-sudoku-qualification-2026-10-28-r1'
OUTPUT = 'results/2026-10-28-pulpino-sudoku-qualification-r1'
PHASES = ('prepare', 'discover', 'opportunity', 'baseline', 'public', 'freeze')
SOURCES = tuple(dict.fromkeys((SOURCE, 'scripts/reproduce_codesign.py',
    'scripts/qualify_opportunity_sources.py', 'isaforge/observed_command.py',
    *w.GATE_SOURCES)))


def phase_command(phase, native, reference):
    c.require(phase in PHASES, 'Declared qualification phase required')
    argv = [sys.executable, '-m', 'isaforge.pulpino_sudoku_workload', phase,
            '--root', str(native)]
    if phase == 'prepare':
        argv += ['--reference-root', str(reference)]
    return argv


def classify_phase_failure(phase, native):
    """Only a sealed false opportunity result is a source-level rejection."""
    gate_path = Path(native) / 'opportunity.json'
    if phase == 'opportunity' and gate_path.is_file():
        gate = c.unseal(gate_path)
        if gate.get('passed') is False and gate.get('measured_candidate_labels_used') is False:
            return 'rejected'
    return 'failed'


def qualify(output, native, reference):
    output, native, reference = (Path(path).resolve()
                                 for path in (output, native, reference))
    c.require(not output.exists() and not native.exists(),
              'Fresh qualification and native roots required')
    c.require(output.is_relative_to(ROOT) and native.is_relative_to(ROOT) and
              not output.is_relative_to(native) and not native.is_relative_to(output) and
              reference == (ROOT / REFERENCE).resolve() and
              (reference / 'plan.json').is_file(),
              'Separate repository-local roots and exact preserved reference required')
    upstream = w.source_record()
    history_path = ROOT / w.HISTORY
    history = c.unseal(history_path)
    c.require(len(history.get('rows', [])) == 122 and
              len({row.get('workload_group') for row in history['rows']}) == 14,
              'Expected authenticated 122-label/14-group prelabel corpus')
    protocol = dict(w.PROTOCOL, schema=w.PROTOCOL['schema'] + '-qualification',
        created_at_utc=datetime.now(timezone.utc).isoformat(), phases=list(PHASES),
        reference_root=REFERENCE, reference_plan_sha256=c.sha(reference / 'plan.json'),
        historical_corpus_sha256=c.sha(history_path), upstream=upstream,
        native_root=native.relative_to(ROOT).as_posix(), target_candidate_attempts=0,
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        workers=1, build_workers=2, phase_timeout_seconds=3600,
        phase_commands={phase: phase_command(phase, native, reference)
                        for phase in PHASES},
        rejection_rule='Preserve the first failed phase and raw archive. A nonzero phase is a workload rejection only when its source-bound gate artifact records an explicit failed gate; otherwise classify it as pipeline failure. Do not alter source, tests, compiler, ISA, partition, pool size, or thresholds.',
        pool_freeze_is_candidate_authorization=False)
    output.mkdir(parents=True)
    c.seal(output / 'protocol.json', protocol)
    shutil.copyfile(reference / 'plan.json', output / 'reference-plan.json')
    for name in SOURCES:
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    row = dict(workload=w.WORKLOAD, family=w.GROUP,
        root=native.relative_to(ROOT).as_posix(), status='started', commands=[])
    result = dict(schema=w.PROTOCOL['schema'] + '-qualification-result',
        protocol_sha256=c.sha(output / 'protocol.json'), records=[row],
        accepted={}, target_candidate_attempts=0, status='started')

    def seal_progress():
        commands = row['commands']
        result.update(recorded_subprocess_monotonic_seconds=sum(
            item['record']['durations']['monotonic_elapsed_seconds']
            for item in commands),
            recorded_subprocess_utc_seconds=sum(
            item['record']['durations']['utc_elapsed_seconds']
            for item in commands),
            clock_disagreement_phase_count=sum(bool(
                item['record']['durations']['clock_disagreement_detected'])
                for item in commands))
        c.seal(output / 'qualification.json', result)
        c.seal(output / 'manifest.json', {
            path.relative_to(output).as_posix(): c.sha(path)
            for path in sorted(output.rglob('*')) if path.is_file() and
            path.name not in ('manifest.json', 'manifest.json.sha256')})

    seal_progress()
    phase = None
    try:
        for index, phase in enumerate(PHASES):
            w.require_zero_candidates(native)
            observation = output / 'commands' / f'{index:02d}-{phase}'
            try:
                record = observed_command.run(protocol['phase_commands'][phase],
                    observation, cwd=ROOT,
                    metadata=dict(workload=w.WORKLOAD, phase=phase,
                                  protocol_sha256=c.sha(output / 'protocol.json')),
                    timeout_seconds=protocol['phase_timeout_seconds'])
            except BaseException:
                if (observation / 'record.json').exists():
                    row['commands'].append(dict(phase=phase,
                        observation=observation.relative_to(output).as_posix(),
                        record=c.unseal(observation / 'record.json')))
                raise
            row['commands'].append(dict(phase=phase,
                observation=observation.relative_to(output).as_posix(),
                record=record))
            w.require_zero_candidates(native)
            print(f'{w.WORKLOAD} {phase}: {record["status"]}', flush=True)
            if record['status'] != 'success' or record['returncode'] != 0:
                failure_status = classify_phase_failure(phase, native)
                row.update(status=failure_status, failed_phase=phase)
                result['status'] = failure_status
                break
            seal_progress()
        else:
            plan = w.validate_inputs(native)
            frozen = c.unseal(native / 'evaluation-protocol.json')
            c.require(len(frozen['pool_names']) == len(set(frozen['pool_names'])) ==
                      w.POOL_SIZE and frozen['maximum_candidate_attempts'] ==
                      w.POOL_SIZE, 'Exact twelve-candidate freeze required')
            gate = w.check_opportunity(native)
            row.update(status='accepted', context_id=plan['context_id'], gate=gate)
            result.update(status='accepted', accepted={w.WORKLOAD: row['root']})
    except BaseException as error:
        row.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit))
                   else 'failed', failed_phase=phase, error=repr(error))
        result['status'] = row['status']
        raise
    finally:
        try:
            w.require_zero_candidates(native)
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
    print({key: result[key] for key in
           ('status', 'accepted', 'target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())

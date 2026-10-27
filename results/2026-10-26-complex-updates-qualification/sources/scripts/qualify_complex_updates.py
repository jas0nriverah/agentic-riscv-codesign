"""One fixed, original-input complex_updates qualification; no candidate measurements."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, observed_command, complex_updates_workload as w
from scripts.reproduce_codesign import pack_archive
zero = w.require_zero_candidates

SOURCE = 'scripts/qualify_complex_updates.py'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE = 'generated/tacle-complex-updates-2026-10-26'
OUTPUT = 'results/2026-10-26-complex-updates-qualification'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
PHASES = ('prepare','discover','opportunity','baseline','public','freeze')
SOURCES = tuple(dict.fromkeys((SOURCE, 'scripts/qualify_opportunity_sources.py',
    'scripts/reproduce_codesign.py', 'isaforge/observed_command.py', *w.GATE_SOURCES)))


def phase_command(phase, native, reference):
    c.require(phase in PHASES, 'Declared qualification phase required')
    argv = [sys.executable, '-m', 'isaforge.complex_updates_workload', phase, '--root', str(native)]
    if phase == 'prepare':
        argv += ['--reference-root', str(reference)]
    return argv


def qualify(output, native, reference):
    output, native, reference = (Path(p).resolve() for p in (output,native,reference))
    c.require(not output.exists() and not native.exists(), 'Fresh qualification and native roots required')
    c.require(output.is_relative_to(ROOT) and native.is_relative_to(ROOT) and
              not output.is_relative_to(native) and not native.is_relative_to(output) and
              reference == (ROOT/REFERENCE).resolve() and (reference/'plan.json').is_file(),
              'Separate repository-local roots and exact preserved reference required')
    # Hash existing history bytes for provenance only: never parse candidate outcomes.
    # No models/cohorts are prepared by this baseline-only qualification.
    c.require((ROOT/HISTORY).is_file(), 'Historical provenance file required')
    protocol = dict(w.PROTOCOL, schema=w.PROTOCOL['schema']+'-qualification',
        created_at_utc=datetime.now(timezone.utc).isoformat(), phases=list(PHASES),
        memory_partition=w.PARTITION, reference_root=REFERENCE,
        reference_plan_sha256=c.sha(reference/'plan.json'), historical_corpus_sha256=c.sha(ROOT/HISTORY),
        native_root=native.relative_to(ROOT).as_posix(), target_candidate_attempts=0,
        source_bindings={name:c.sha(ROOT/name) for name in SOURCES},
        workers=1, build_workers=2, phase_timeout_seconds=3600,
        phase_commands={phase:phase_command(phase,native,reference) for phase in PHASES},
        qualification_rule='Single declared original-input complex_updates, twelve legal executable calibrated formulas and unchanged joint0.5%/ten-replacement gate; no retries, smaller inputs, gate changes, memory/context changes or candidate labels.',
        rejection_rule='Preserve first rejection and archive. No retries, fallback, input/checksum/partition changes or weaker gates.',
        candidate_dispatch_enabled=False, pool_freeze_is_candidate_authorization=False)
    output.mkdir(parents=True)
    c.seal(output/'protocol.json', protocol)
    for name in SOURCES:
        destination = output/'sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    shutil.copyfile(reference/'plan.json', output/'reference-plan.json')
    row = dict(workload=w.WORKLOAD, family=w.GROUP, root=native.relative_to(ROOT).as_posix(), status='started', commands=[])
    result = dict(schema=w.PROTOCOL['schema']+'-qualification-result',
        protocol_sha256=c.sha(output/'protocol.json'), records=[row], accepted={},
        target_candidate_attempts=0, status='started')

    def seal_progress():
        commands = row['commands']
        result.update(recorded_subprocess_monotonic_seconds=sum(r['record']['durations']['monotonic_elapsed_seconds'] for r in commands),
            recorded_subprocess_utc_seconds=sum(r['record']['durations']['utc_elapsed_seconds'] for r in commands),
            clock_disagreement_phase_count=sum(bool(r['record']['durations']['clock_disagreement_detected']) for r in commands))
        c.seal(output/'qualification.json', result)
        c.seal(output/'manifest.json', {p.relative_to(output).as_posix():c.sha(p)
            for p in sorted(output.rglob('*')) if p.is_file() and p.name not in ('manifest.json','manifest.json.sha256')})

    seal_progress()
    phase = None
    try:
        for index, phase in enumerate(PHASES):
            zero(native)
            observation = output/'commands'/f'{index:02d}-{phase}'
            try:
                record = observed_command.run(protocol['phase_commands'][phase], observation,
                    cwd=ROOT, metadata=dict(workload=w.WORKLOAD, phase=phase,
                        protocol_sha256=c.sha(output/'protocol.json')),
                    timeout_seconds=protocol['phase_timeout_seconds'])
            except BaseException:
                if (observation/'record.json').exists():
                    row['commands'].append(dict(phase=phase, observation=observation.relative_to(output).as_posix(),
                        record=c.unseal(observation/'record.json')))
                raise
            row['commands'].append(dict(phase=phase, observation=observation.relative_to(output).as_posix(),record=record))
            zero(native)
            print(f'{w.WORKLOAD} {phase}: {record["status"]}', flush=True)
            if record['status'] != 'success' or record['returncode'] != 0:
                row.update(status='rejected', failed_phase=phase)
                result['status'] = 'rejected'
                break
            seal_progress()
        else:
            plan = w.validate_inputs(native)
            frozen = c.unseal(native/'evaluation-protocol.json')
            c.require(len(frozen['pool_names']) == len(set(frozen['pool_names'])) == w.POOL_SIZE and
                      frozen['maximum_candidate_attempts'] == w.POOL_SIZE, 'Exact twelve-candidate freeze required')
            row.update(status='accepted', context_id=plan['context_id'], gate=w.check_opportunity(native))
            result.update(status='accepted', accepted={w.WORKLOAD:row['root']})
    except BaseException as error:
        row.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
            failed_phase=phase, error=repr(error))
        result['status'] = row['status']
        raise
    finally:
        try:
            zero(native)
            if native.exists():
                c.seal(output/'archive-manifest.json', pack_archive(native,output/'raw.tar.gz'))
        finally:
            seal_progress()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT/NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT/REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output,args.native_root,args.reference_root)
    print({key:result[key] for key in ('status','accepted','target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())

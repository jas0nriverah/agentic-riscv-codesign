"""Qualify exactly three fresh source families under a frozen public gate.

No learned fitting or custom-candidate measurement occurs here. Discovery uses
the original program; insufficient opportunities stop before baseline routing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import opportunity_workload as w, codesign as c, observed_command
from scripts.reproduce_codesign import pack_archive

SOURCE = 'scripts/qualify_opportunity_sources.py'
REFERENCE = 'generated/codesign-crc32-2026-10-19-r1'
NATIVE_PARENT = 'generated/useful-opportunity-2026-10-22'
OUTPUT = 'results/2026-10-22-useful-source-qualification'
HISTORY = 'results/2026-10-22-eleven-source-corpus/corpus.json'
PHASES = ('prepare','discover','opportunity','baseline','public','freeze')
SOURCES = tuple(dict.fromkeys((SOURCE,w.SOURCE,w.ORIGINAL_BLIND_SOURCE,*w.GATE_SOURCES,
    'isaforge/observed_command.py','scripts/reproduce_codesign.py',w.LICENSE,
    *(w.program(name) for name in w.WORKLOADS))))


def zero(native):
    c.require(not list((native/'attempt-ledger').glob('candidate_*.json')) and
              not list((native/'measurements').glob('candidate_*')), 'Qualification requires zero candidate attempts')


def phase_command(phase,native,reference,name):
    c.require(phase in PHASES and name in w.WORKLOADS, 'Declared phase/source required')
    argv = [sys.executable,'-m','isaforge.opportunity_workload',phase,'--root',str(native)]
    if phase == 'prepare':
        argv += ['--workload',name,'--reference-root',str(reference)]
    return argv


def qualify(output,native_parent,reference):
    output,native_parent,reference = (Path(path).resolve() for path in (output,native_parent,reference))
    c.require(not output.exists() and not native_parent.exists(), 'Fresh qualification/native parent required')
    c.require(output.is_relative_to(ROOT) and native_parent.is_relative_to(ROOT) and
              not output.is_relative_to(native_parent) and not native_parent.is_relative_to(output),
              'Separate repository-local evidence/native roots required')
    c.require(reference == (ROOT/REFERENCE).resolve() and (reference/'plan.json').is_file(), 'Exact preserved reference required')
    historical = c.unseal(ROOT/HISTORY)
    groups = set(historical['independent_workload_groups'])
    c.require(all('beebs-'+name not in groups for name in w.WORKLOADS), 'Entire candidate source must be absent from history')
    for name,(_,digest) in w.WORKLOADS.items():
        c.require(c.sha(ROOT/w.program(name)) == digest, 'Pinned upstream source differs')
    protocol = dict(w.PROTOCOL, schema='isaforge-useful-source-qualification-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        phases=list(PHASES), memory_partition=w.PARTITION, reference_root=REFERENCE,
        reference_plan_sha256=c.sha(reference/'plan.json'), historical_corpus_sha256=c.sha(ROOT/HISTORY),
        native_parent=native_parent.relative_to(ROOT).as_posix(), target_candidate_attempts=0,
        source_bindings={name:c.sha(ROOT/name) for name in SOURCES},
        static_rejections=w.STATIC_REJECTIONS,
        qualification_rule='Fixed source order; first three distinct accepted families. Skip a later family member only after that family qualifies. Never lower gates or retry rejected contexts.',
        workers=1, build_workers=2, phase_timeout_seconds=3600,
        phase_commands={name:{phase:phase_command(phase,native_parent/name,reference,name)
            for phase in PHASES} for name in w.WORKLOADS})
    output.mkdir(parents=True)
    c.seal(output/'protocol.json',protocol)
    shutil.copyfile(reference/'plan.json',output/'reference-plan.json')
    for name in SOURCES:
        destination=output/'sources'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,destination)
    records,accepted,accepted_families=[],{},[]
    result=dict(schema='isaforge-useful-source-qualification-result-v1',protocol_sha256=c.sha(output/'protocol.json'),
        records=records,accepted=accepted,accepted_families=accepted_families,target_candidate_attempts=0,status='started')

    def seal_progress():
        commands=[command for row in records for command in row['commands']]
        result.update(successful_sources=len(accepted),successful_families=len(accepted_families),
            recorded_subprocess_monotonic_seconds=sum(row['record']['durations']['monotonic_elapsed_seconds'] for row in commands),
            recorded_subprocess_utc_seconds=sum(row['record']['durations']['utc_elapsed_seconds'] for row in commands),
            clock_disagreement_phase_count=sum(bool(row['record']['durations']['clock_disagreement_detected']) for row in commands))
        c.seal(output/'qualification.json',result)
        c.seal(output/'manifest.json',{path.relative_to(output).as_posix():c.sha(path)
            for path in sorted(output.rglob('*')) if path.is_file() and path.name not in ('manifest.json','manifest.json.sha256')})

    seal_progress()
    for name in protocol['order']:
        native=native_parent/name
        row=dict(workload=name,family=w.FAMILIES[name],root=native.relative_to(ROOT).as_posix(),status='started',commands=[])
        records.append(row)
        if name in w.STATIC_REJECTIONS:
            row.update(status='static_rejection',reason=w.STATIC_REJECTIONS[name]);seal_progress();continue
        if w.FAMILIES[name] in accepted_families:
            row.update(status='related_family_skipped',reason='An earlier member of this source family already qualified.');seal_progress();continue
        folder=output/name
        folder.mkdir()
        phase=None
        try:
            for index,phase in enumerate(PHASES):
                zero(native)
                observation=folder/'commands'/f'{index:02d}-{phase}'
                try:
                    record=observed_command.run(protocol['phase_commands'][name][phase],observation,cwd=ROOT,
                        metadata=dict(workload=name,phase=phase,protocol_sha256=c.sha(output/'protocol.json')),
                        timeout_seconds=protocol['phase_timeout_seconds'])
                except BaseException:
                    if (observation/'record.json').exists():
                        row['commands'].append(dict(phase=phase,observation=observation.relative_to(output).as_posix(),
                            record=c.unseal(observation/'record.json')))
                    raise
                row['commands'].append(dict(phase=phase,observation=observation.relative_to(output).as_posix(),record=record))
                zero(native)
                print(f'{name} {phase}: {record["status"]}',flush=True)
                if record['status'] != 'success' or record['returncode'] != 0:
                    row.update(status='rejected',failed_phase=phase)
                    break
                seal_progress()
            else:
                plan=w.validate_inputs(native)
                frozen=c.unseal(native/'evaluation-protocol.json')
                c.require(len(frozen['pool_names']) == len(set(frozen['pool_names'])) == 12 and
                          frozen['maximum_candidate_attempts'] == 12, 'Exact twelve-formula pool required')
                gate=w.check_opportunity(native)
                row.update(status='accepted',context_id=plan['context_id'],gate=gate)
                accepted[name]=row['root']
                accepted_families.append(w.FAMILIES[name])
        except BaseException as error:
            row.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
                failed_phase=phase,error=repr(error))
            result['status']=row['status']
            raise
        finally:
            try:
                zero(native)
                if native.exists():
                    c.seal(folder/'archive-manifest.json',pack_archive(native,folder/'raw.tar.gz'))
            finally:
                seal_progress()
        if len(accepted_families) == 3:
            break
    result['status']='accepted' if len(accepted_families) == 3 else 'insufficient_qualified_families'
    seal_progress()
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/OUTPUT)
    parser.add_argument('--native-parent',type=Path,default=ROOT/NATIVE_PARENT)
    parser.add_argument('--reference-root',type=Path,default=ROOT/REFERENCE)
    args=parser.parse_args(argv)
    result=qualify(args.output,args.native_parent,args.reference_root)
    print({name:result[name] for name in ('status','accepted','successful_families','target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())

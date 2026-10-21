"""Qualify the first three compatible sources in a predeclared BEEBS order.

No candidate is measured. Full native failures, logs and setup costs are kept.
The unchanged inputs and common partition must pass without per-source tuning.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import blind_workload as workload, codesign as c
from scripts.reproduce_codesign import pack_archive


def qualify(output, native_parent, reference):
    output, native_parent, reference = map(lambda p: Path(p).resolve(), (output, native_parent, reference))
    c.require(not output.exists() and not native_parent.exists(), 'Fresh qualification and native parent required')
    c.require(output.is_relative_to(ROOT) and native_parent.is_relative_to(ROOT), 'Repository-local run directories required')
    output.mkdir(parents=True)
    protocol = dict(schema='isaforge-blind-qualification-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        order=list(workload.WORKLOADS), stop_after_successful_sources=3,
        pool_size=workload.POOL_SIZE, memory_partition=workload.PARTITION,
        selection_rule='First three sources passing unchanged baseline, guards, verifier and twelve legal calibrated formulas. No candidate labels or per-source input/partition tuning.',
        source_bindings={name:c.sha(ROOT/name) for name in
            ('scripts/qualify_blind_campaign.py', workload.SOURCE, *[workload.program(name) for name in workload.WORKLOADS])},
        native_parent=native_parent.relative_to(ROOT).as_posix(),
        reference_root=reference.relative_to(ROOT).as_posix(),
        phases=['prepare','discover','baseline','public','freeze'],
        interpretation='Baseline measurements and legal/profile-derived features only; zero candidate attempts throughout qualification.')
    c.seal(output/'protocol.json', protocol)
    records, accepted = [], {}
    for name in protocol['order']:
        if len(accepted) == 3:
            break
        native = native_parent/name
        row = dict(workload=name, root=native.relative_to(ROOT).as_posix(), commands=[])
        for phase in protocol['phases']:
            argv = [sys.executable, '-m', 'isaforge.blind_workload', phase, '--root', str(native)]
            if phase == 'prepare':
                argv += ['--workload', name, '--reference-root', str(reference)]
            stamp = datetime.now(timezone.utc).isoformat()
            started = time.monotonic()
            completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
            elapsed = time.monotonic()-started
            folder = output/name
            folder.mkdir(exist_ok=True)
            (folder/(phase+'.stdout.txt')).write_text(completed.stdout)
            (folder/(phase+'.stderr.txt')).write_text(completed.stderr)
            row['commands'].append(dict(argv=argv, phase=phase, started_at_utc=stamp,
                elapsed_seconds=elapsed, returncode=completed.returncode))
            print(f'{name} {phase}: status={completed.returncode} wall={elapsed:.3f}s', flush=True)
            if completed.returncode != 0:
                row.update(status='rejected', failed_phase=phase)
                break
        else:
            row.update(status='accepted', context_id=c.unseal(native/'plan.json')['context_id'])
            accepted[name] = row['root']
        c.require(not list((native/'attempt-ledger').glob('candidate_*.json')), 'Qualification opened candidate attempts')
        if native.exists():
            c.seal(output/name/'archive-manifest.json', pack_archive(native,output/name/'raw.tar.gz'))
        records.append(row)
        c.seal(output/'qualification.json', dict(protocol_sha256=c.sha(output/'protocol.json'),
            records=records, accepted=accepted, successful_sources=len(accepted), target_candidate_attempts=0,
            complete_subprocess_seconds=sum(cmd['elapsed_seconds'] for item in records for cmd in item['commands'])))
    c.seal(output/'manifest.json',{path.relative_to(output).as_posix():c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()})
    c.require(len(accepted) == 3, 'Fewer than three sources qualified; preserve rejections and declare next qualification before further work')
    return accepted


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/2026-10-21-blind-qualification')
    parser.add_argument('--native-parent',type=Path,default=ROOT/'generated/blind-cohort-2026-10-21')
    parser.add_argument('--reference-root',type=Path,default=ROOT/'generated/codesign-crc32-2026-10-19-r1')
    args=parser.parse_args(argv)
    print(qualify(args.output,args.native_parent,args.reference_root))


if __name__ == '__main__':
    main()

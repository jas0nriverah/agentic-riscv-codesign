"""Build, self-check and trace the actual eight Embench workloads on Spike."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

PROGRAMS = ['aha-mont64', 'crc32', 'edn', 'huffbench', 'matmult-int', 'nettle-aes', 'nettle-sha256', 'wikisort']
ROOT = Path(__file__).resolve().parents[1]


def command(args, log, timeout=600):
    started = time.monotonic()
    with log.open('w') as output:
        result = subprocess.run(args, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    return {'command': args, 'exit_code': result.returncode, 'wall_seconds': round(time.monotonic() - started, 3), 'log': str(log.relative_to(ROOT))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='riscv64-unknown-elf-gcc')
    parser.add_argument('--spike', default='spike')
    parser.add_argument('--spike-source', type=Path, help='Record the simulator source commit when available')
    parser.add_argument('--programs', nargs='+', choices=PROGRAMS, default=PROGRAMS)
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    evidence_dir = ROOT / 'generated/real'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_path = evidence_dir / 'benchmarks.json'
    report = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': 'actual Embench RV32IM execution in Spike',
              'cpu_mhz_scale': 1, 'warmup_heat': 1,
              'compiler_flags': '-march=rv32im -mabi=ilp32 -O2 -std=gnu17 -DCPU_MHZ=1 -DWARMUP_HEAT=1',
              'spike_flags': ['--isa=rv32im_zicntr', '-m16'],
              'measurement_limits': 'Retired instructions only. Spike is not cycle accurate; these are not CPU speedup measurements.',
              'compiler_version': subprocess.check_output([args.cc, '--version'], text=True).splitlines()[0],
              'spike_version': subprocess.run([args.spike, '--help'], capture_output=True, text=True).stderr.splitlines()[0],
              'embench_commit': subprocess.check_output(['git', '-C', 'benchmarks/embench', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'benchmarks': []}
    if args.spike_source:
        report['spike_commit'] = subprocess.check_output(['git', '-C', str(args.spike_source), 'rev-parse', 'HEAD'], text=True).strip()
    for name in args.programs:
        record = {'benchmark': name}
        report['benchmarks'].append(record)
        record['build'] = command(['make', '-B', f'generated/programs/{name}.elf', f'CC={args.cc}'], evidence_dir / f'{name}.build.log')
        if record['build']['exit_code']:
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            sys.exit(f'{name}: build failed')
        elf = ROOT / f'generated/programs/{name}.elf'
        record['elf_sha256'] = hashlib.sha256(elf.read_bytes()).hexdigest()
        record['elf_bytes'] = elf.stat().st_size
        record['self_check'] = command([args.spike, '--isa=rv32im_zicntr', '-m16', str(elf)], evidence_dir / f'{name}.run.log', args.timeout)
        record['self_check_passed'] = record['self_check']['exit_code'] == 0
        if not record['self_check_passed']:
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            sys.exit(f'{name}: self-check failed')
        # Force a fresh trace while preserving the exact self-checked ELF.
        trace = ROOT / f'generated/traces/{name}.jsonl'
        trace.unlink(missing_ok=True)
        trace.with_suffix('.summary.json').unlink(missing_ok=True)
        record['trace'] = command(['make', f'generated/traces/{name}.jsonl', f'CC={args.cc}', f'SPIKE={args.spike}', f'PYTHON={sys.executable}'], evidence_dir / f'{name}.trace.log', args.timeout)
        if record['trace']['exit_code']:
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            sys.exit(f'{name}: trace validation failed')
        if hashlib.sha256(elf.read_bytes()).hexdigest() != record['elf_sha256']:
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            sys.exit(f'{name}: trace ELF differs from the self-checked ELF')
        record['self_check_elf_matches_trace_elf'] = True
        record.update(json.loads(trace.with_suffix('.summary.json').read_text()))
        record['trace_bytes'] = trace.stat().st_size
        digest = hashlib.sha256()
        with trace.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        record['trace_sha256'] = digest.hexdigest()
        record['trace_path'] = str(trace.relative_to(ROOT))
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'{name}: self-check passed, {record["trace_instructions"]:,} validated instructions', flush=True)
    report['all_passed'] = True
    report['total_trace_instructions'] = sum(row['trace_instructions'] for row in report['benchmarks'])
    report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()

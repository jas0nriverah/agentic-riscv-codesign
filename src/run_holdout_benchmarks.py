"""Collect untouched Embench families in an isolated, explicitly frozen holdout.

Full measurement-window commits are retained as gzip JSONL. Candidate extraction
uses exact PC counts and block starts accumulated while writing the trace, so no
uncompressed multi-gigabyte intermediate is needed. No model is loaded or tuned.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from candidates import extractCandidates, readProgram
from tracing import parse_trace
from verify_candidate_fusions import verify_candidates

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRAMS = ['statemate', 'nsichneu', 'minver', 'nbody', 'slre', 'ud']
FLAGS = ['-march=rv32im', '-mabi=ilp32', '-O2', '-std=gnu17', '-DCPU_MHZ=1', '-DWARMUP_HEAT=1']
SPIKE_FLAGS = ['--isa=rv32im_zicntr', '-m16']
FAMILIES = {'statemate': 'state-machine control', 'nsichneu': 'Petri-net/control',
            'minver': 'matrix inversion (RV32IM software floating point)',
            'nbody': 'physics (RV32IM software floating point)',
            'slre': 'regular-expression matching', 'ud': 'integer LU decomposition',
            'cubic': 'floating-point cubic solver', 'picojpeg': 'JPEG image decoder',
            'qrduino': 'QR encoder', 'sglib-combined': 'sorting and data structures',
            'st': 'floating-point statistics'}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def command(args, log, timeout):
    started = time.monotonic()
    with log.open('w') as output:
        result = subprocess.run(args, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    record = dict(command=args, exit_code=result.returncode,
                  wall_seconds=round(time.monotonic() - started, 3), log=str(log.relative_to(ROOT)))
    if result.returncode:
        raise RuntimeError(f'Command failed: {args}; see {log}')
    return record


class CountedTrace:
    def __init__(self, output):
        self.output, self.runs, self.starts, self.previous = output, Counter(), set(), None

    def write(self, line):
        record = json.loads(line)
        pc = int(record['pc'], 16)
        self.runs[pc] += 1
        if self.previous is None or pc != self.previous + 4:
            self.starts.add(pc)
        self.previous = pc
        return self.output.write(line)

    def finish(self):
        if self.previous is not None:
            self.starts.add(self.previous + 4)


def collect_trace(spike, elf, trace, log, timeout):
    args = [spike, *SPIKE_FLAGS, '--log-commits', '--log=/dev/stdout', str(elf)]
    started = time.monotonic()
    partial = trace.with_suffix(trace.suffix + '.partial')
    with log.open('w') as errors:
        process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, start_new_session=True)
        def terminate():
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        timer = threading.Timer(timeout, terminate)
        timer.start()
        try:
            with gzip.open(partial, 'wt', compresslevel=1) as output:
                sink = CountedTrace(output)
                summary = parse_trace(process.stdout, sink)
                sink.finish()
            code = process.wait(timeout=30)
            if code:
                raise RuntimeError(f'Spike trace exit {code}: {log}')
            partial.replace(trace)
        except BaseException:
            terminate()
            process.wait(timeout=30)
            partial.unlink(missing_ok=True)
            raise
        finally:
            timer.cancel()
            process.stdout.close()
    summary.update(command=args, exit_code=code, wall_seconds=round(time.monotonic() - started, 3),
                   log=str(log.relative_to(ROOT)), trace_path=str(trace.relative_to(ROOT)),
                   trace_encoding='gzip JSONL; all commits in the instret measurement window',
                   trace_bytes=trace.stat().st_size, trace_sha256=sha256(trace))
    write_json(trace.with_suffix('.summary.json'), summary)
    return summary, sink.runs, sink.starts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--programs', '--benchmarks', dest='programs', nargs='+', required=True,
                        help='Explicit upstream Embench directory names; frozen before any labels')
    parser.add_argument('--cc', default='riscv-none-elf-gcc')
    parser.add_argument('--objdump', default='riscv-none-elf-objdump')
    parser.add_argument('--spike', default='spike')
    parser.add_argument('--spike-source', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'generated/holdout')
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--max-size', type=int, default=4)
    parser.add_argument('--per-benchmark', type=int, default=48)
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--synthesize', action='store_true')
    args = parser.parse_args()
    if args.max_size < 2 or min(args.timeout, args.per_benchmark, args.workers) < 1:
        parser.error('--max-size must be >=2 and timeout, sampling count, workers must be positive')
    if len(set(args.programs)) != len(args.programs):
        parser.error('program names must be unique')
    source_root = ROOT / 'benchmarks/embench/src'
    sources = {}
    for name in args.programs:
        if '/' in name or name in {'.', '..'}:
            parser.error(f'invalid program name: {name}')
        files = sorted((source_root / name).glob('*.c'))
        if not files:
            parser.error(f'no upstream C sources for {name}')
        sources[name] = files
    output = args.output.resolve()
    # Keep the collection disjoint from the original training artifacts.
    allowed_roots = [ROOT / 'generated/holdout', ROOT / 'generated/final-holdout']
    if not any(output.is_relative_to(folder) for folder in allowed_roots):
        parser.error('--output must be within generated/holdout or generated/final-holdout')
    for folder in ['programs', 'traces', 'candidates', 'logs']:
        (output / folder).mkdir(parents=True, exist_ok=True)
    plan = dict(programs=args.programs, families={name: FAMILIES.get(name, 'upstream Embench workload') for name in args.programs},
                max_size=args.max_size, per_benchmark=args.per_benchmark, seed=args.seed,
                sampling_method='half_top_merit_half_seeded_random_remainder',
                sources={name: {str(p.relative_to(ROOT)): sha256(p) for p in files} for name, files in sources.items()},
                compiler_flags=FLAGS, spike_flags=SPIKE_FLAGS)
    choice_path = output / 'benchmark_choices.json'
    if choice_path.exists():
        old = json.loads(choice_path.read_text())
        if any(old.get(key) != value for key, value in plan.items()):
            parser.error('existing frozen benchmark choices differ; use a fresh subdirectory')
    else:
        write_json(choice_path, dict(plan, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                                     before_candidate_extraction_and_labels=True))
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
                  benchmark_choices_sha256=sha256(choice_path), compiler_flags=FLAGS,
                  spike_flags=SPIKE_FLAGS, cpu_mhz_scale=1, warmup_heat=1,
                  compiler_version=subprocess.check_output([args.cc, '--version'], text=True).splitlines()[0],
                  spike_version=subprocess.run([args.spike, '--help'], capture_output=True, text=True).stderr.splitlines()[0],
                  embench_commit=subprocess.check_output(['git', '-C', str(ROOT / 'benchmarks/embench'), 'rev-parse', 'HEAD'], text=True).strip(),
                  measurement_limits='Retired instructions only; Spike is not cycle accurate.',
                  benchmark_header_sha256={str(p.relative_to(ROOT)): sha256(p) for name in args.programs for p in sorted((source_root / name).glob('*.h'))},
                  support_source_sha256={str(p.relative_to(ROOT)): sha256(p) for p in [
                      ROOT / 'src/spike-setup/startup.S', ROOT / 'src/spike-setup/memory-layout.ld',
                      ROOT / 'benchmarks/embench-hooks.c',
                      *sorted((ROOT / 'benchmarks/embench/support').glob('*.h')),
                      ROOT / 'benchmarks/embench/support/main.c', ROOT / 'benchmarks/embench/support/beebsc.c']},
                  benchmarks=[])
    if args.spike_source:
        report['spike_commit'] = subprocess.check_output(['git', '-C', str(args.spike_source), 'rev-parse', 'HEAD'], text=True).strip()
    setup = ['src/spike-setup/startup.S', 'benchmarks/embench-hooks.c',
             'benchmarks/embench/support/main.c', 'benchmarks/embench/support/beebsc.c']
    for name in args.programs:
        record = dict(benchmark=name, family=plan['families'][name], sources=plan['sources'][name])
        report['benchmarks'].append(record)
        write_json(output / 'benchmarks.json', report)
        elf = output / 'programs' / f'{name}.elf'
        record['build'] = command([args.cc, *FLAGS, '-I', 'benchmarks/embench/support',
                                   '-nostartfiles', '-T', 'src/spike-setup/memory-layout.ld',
                                   *setup, *(str(p) for p in sources[name]), '-lm', '-o', str(elf)],
                                  output / 'logs' / f'{name}.build.log', args.timeout)
        record.update(elf_sha256=sha256(elf), elf_bytes=elf.stat().st_size,
                      elf_path=str(elf.relative_to(ROOT)))
        record['self_check'] = command([args.spike, *SPIKE_FLAGS, str(elf)], output / 'logs' / f'{name}.run.log', args.timeout)
        record['self_check_passed'] = True
        summary, runs, starts = collect_trace(args.spike, elf, output / 'traces' / f'{name}.jsonl.gz',
                                             output / 'logs' / f'{name}.trace.log', args.timeout)
        if sha256(elf) != record['elf_sha256']:
            raise RuntimeError(f'{name}: ELF changed between self-check and trace')
        record.update(summary, self_check_elf_matches_trace_elf=True)
        ranked = extractCandidates(readProgram(elf, args.objdump), runs, starts, args.max_size, None)
        candidate_path = output / 'candidates' / f'{name}.json'
        write_json(candidate_path, ranked)
        record.update(candidate_count=len(ranked), candidate_path=str(candidate_path.relative_to(ROOT)),
                      candidate_sha256=sha256(candidate_path), max_size=args.max_size)
        write_json(output / 'benchmarks.json', report)
        print(f'{name}: self-check passed, {summary["trace_instructions"]:,} validated instructions, {len(ranked)} candidates', flush=True)
    report.update(all_passed=True, total_trace_instructions=sum(r['trace_instructions'] for r in report['benchmarks']))
    write_json(output / 'benchmarks.json', report)
    equivalence = verify_candidates(output / 'candidates', output / 'programs', args.objdump, vectors=16, seed=args.seed)
    write_json(output / 'extraction_equivalence.json', equivalence)
    print('All extracted fusion occurrences passed randomized software equivalence', flush=True)
    if args.synthesize:
        # Resource labels remain unopened until the full candidate inclusion is fixed.
        formula_count = len({row['formula'] for path in (output / 'candidates').glob('*.json')
                             for row in json.loads(path.read_text())})
        if formula_count >= 1000:
            write_json(output / 'synthesis_deferred.json', dict(unique_circuits=formula_count,
                reason='Full pool exceeds the predeclared 999-circuit collection guard; no labels collected.'))
            raise RuntimeError('Full candidate pool too large; collection preserved for explicit review')
        from isaforge.real_experiment import run_experiment
        run_experiment(output / 'candidates', output / 'experiment', args.per_benchmark, args.seed, args.workers)


if __name__ == '__main__':
    main()

"""Explicit v4 simulator validation override; existing frozen RTL stays intact.

Verilator 5.050 translates zero-extended mulhu into signed int64 multiplication.
When a downstream expression tests bit63, C++ signed-overflow optimization can
produce incorrect results. Rebuilding the identical generated source with
-fwrapv defines the required 64-bit wrap. Preserve the original failure and
independently verify its entire boundary-input matrix with Yosys eval.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess

from . import v4_corpus
from .rtl import BOUNDARIES, evaluate_formula, generate_rtl, verify_rtl_batch
from .synthesis import _yosys_quote


def verify_wrapping(formulas, output_dir, **kwargs):
    directory = Path(output_dir).resolve()
    try:
        result = verify_rtl_batch(formulas, directory, **kwargs)
        return {**result, 'v4_validation_override_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'signed_overflow_workaround_applied': False}
    except RuntimeError as error:
        if 'RTL correctness failed: Mismatch formula' not in str(error):
            raise
        initial_error = str(error)
        failure = re.search(r'Mismatch formula (\d+) vector (\d+) got ([0-9a-f]+) expected ([0-9a-f]+)', initial_error)
        if failure is None:
            raise
        index, vector = int(failure[1]), int(failure[2])
        # An explicit incident record is written before any alternate validation.
        incident = {'original_error': initial_error, 'formula_index': index, 'formula': formulas[index],
                    'vector_index': vector, 'got_hex': failure[3], 'expected_hex': failure[4],
                    'resolution': 'identical RTL rebuilt with defined signed wrapping; boundary cross-check in Yosys'}
        v4_corpus._write(directory / 'initial-failure.json', incident)
        shutil.copyfile(directory / 'verification.log', directory / 'initial-failure.log')
    executable = shutil.which(kwargs.get('verilator', 'verilator'))
    timeout = kwargs.get('timeout', 300)
    command = [executable, '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal', '-CFLAGS', '-fwrapv',
               '--top-module', 'verification_top', '--Mdir', str(directory / 'obj_dir_wrapv'),
               str(directory / 'verification.v'), str(directory / 'verification.cpp')]
    build = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    (directory / 'verilator-wrapv-build.log').write_text(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError('defined-wrap Verilator build failed')
    run = subprocess.run([str(directory / 'obj_dir_wrapv/Vverification_top'), str(directory / 'vectors.txt')],
                         capture_output=True, text=True, timeout=timeout)
    (directory / 'verification-wrapv.log').write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'defined-wrap RTL correctness failed: {run.stdout}{run.stderr}')
    # Independent simulator, unchanged candidate RTL, all 100 boundary pairs.
    cross = directory / 'yosys-boundary-cross-check'; cross.mkdir(exist_ok=True)
    rtl = cross / 'candidate.v'; rtl.write_text(generate_rtl(formulas[index]))
    pairs = list(itertools.product(BOUNDARIES, repeat=2))
    commands = [f'read_verilog {_yosys_quote(rtl)}', 'prep -top candidate']
    commands += [f'eval -set in0 {a} -set in1 {b} -show result' for a, b in pairs]
    script = cross / 'eval.ys'; script.write_text('\n'.join(commands) + '\n')
    check = subprocess.run([shutil.which('yosys'), '-s', str(script)], capture_output=True, text=True, timeout=timeout)
    (cross / 'eval.log').write_text(check.stdout + check.stderr)
    observed = re.findall(r"Eval result: \\result = (32'[01]+|[0-9]+)\.", check.stdout)
    expected = [evaluate_formula(formulas[index], a, b) for a, b in pairs]
    values = [int(v.split("'")[1], 2) if "'" in v else int(v) for v in observed]
    if check.returncode or len(observed) != len(expected) or values != expected:
        raise RuntimeError('independent Yosys boundary cross-check failed')
    v4_corpus._write(cross / 'observations.json', [{'in0': a, 'in1': b, 'result': want} for (a, b), want in zip(pairs, expected)])
    vectors = sum(1 for _ in (directory / 'vectors.txt').open())
    result = {'verified': True, 'formula_count': len(formulas), 'vectors_per_formula': vectors,
              'total_comparisons': len(formulas) * vectors, 'random_seed': kwargs.get('seed', 20261013),
              'oracle': 'Python RV32 integer semantics; Verilator with defined signed overflow; Yosys boundary cross-check',
              'tool': subprocess.run([executable, '--version'], check=True, capture_output=True, text=True).stdout.strip(),
              'rtl_sha256': v4_corpus._sha(directory / 'verification.v'),
              'vectors_sha256': v4_corpus._sha(directory / 'vectors.txt'),
              'v4_validation_override_sha256': v4_corpus._sha(__file__),
              'compiler_path': shutil.which('c++'),
              'compiler_version': subprocess.run(['c++', '--version'], check=True, capture_output=True, text=True).stdout.strip(),
              'signed_overflow_workaround_applied': True, 'build_command': command,
              'incident': incident, 'independent_yosys_boundary_comparisons': len(pairs),
              'independent_yosys_log_sha256': v4_corpus._sha(cross / 'eval.log')}
    v4_corpus._write(directory / 'validation-resolution.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('results/2026-10-13-v4/corpus'))
    parser.add_argument('--generated-root', type=Path, default=Path('generated/v4-corpus'))
    parser.add_argument('--collect', choices=('development', 'test'), required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args(argv)
    # Explicit override of the collector's imported verifier in this process.
    # This preserves the original frozen source files and candidate bytes.
    v4_corpus.verify_rtl_batch = verify_wrapping
    v4_corpus.collect(args.root, args.generated_root, args.collect, args.workers, args.release)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

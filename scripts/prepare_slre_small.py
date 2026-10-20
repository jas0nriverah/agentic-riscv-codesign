"""One recorded compiler-only -Oz fallback after SLRE exceeds the guard by 68 B."""
from pathlib import Path
import argparse

from prepare_slre_runtime import ROOT, prepare as runtime_prepare
from isaforge import codesign as c


def prepare(reference, output):
    output = Path(output)
    plan = runtime_prepare(reference, output)
    plan.pop('context_id')
    program = output / 'inputs/program.c'
    # GCC applies this to the benchmark's functions in both C compilation and
    # assembly emission. The generic harness/helpers retain their recorded -Os.
    original = program.read_bytes()
    program.write_bytes(b'#pragma GCC optimize ("Oz")\n' + original)
    plan['inputs']['program.c'] = c.sha(program)
    plan['benchmark_compiler_directive'] = {'pragma': 'GCC optimize ("Oz")',
                                           'upstream_source_sha256': c.sha(ROOT / 'benchmarks/embench/src/slre/libslre.c'),
                                           'reason': 'Memory eligibility only; no candidate outcomes observed.'}
    source = 'scripts/prepare_slre_small.py'
    plan['source_bindings'][source] = c.sha(__file__)
    target = output / 'sources' / source
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(__file__).read_bytes())
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.reference_root, args.root)

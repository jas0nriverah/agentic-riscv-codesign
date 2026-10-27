"""Explicit -Os build context for memory-limited workloads; reuse the evaluator.

The frozen October 19 modules and measurements are unchanged. This serial CLI
temporarily supplies a different compiler flag list, seals that choice before
native work, and checks every recorded compiler invocation. No benchmark source,
processor, linker limit, input, or correctness check is relaxed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path

from . import codesign as c
from . import workload_experiment as w

SOURCE = 'isaforge/compact_workload.py'
FLAGS = tuple('-Os' if flag == '-O2' else flag for flag in w.FLAGS)


@contextmanager
def compiler_flags():
    original = w.FLAGS
    w.FLAGS = list(FLAGS)
    try:
        yield
    finally:
        w.FLAGS = original


def prepare(reference, output, workload, pool_size=6):
    with compiler_flags():
        plan = w.prepare(reference, output, workload, pool_size)
    # Complete the fresh context before any compilation or measurement occurs.
    # w.prepare only copies inputs and seals metadata; no native work is run.
    plan.pop('context_id')
    plan['source_bindings'][SOURCE] = c.sha(__file__)
    plan['build_variant'] = {'optimization': '-Os', 'required_entrypoint': SOURCE,
                             'reason': 'Predeclared memory-fit fallback; no performance labels used to choose compiler settings.'}
    plan['context_id'] = c.digest(plan)
    c.seal(Path(output) / 'plan.json', plan)
    target = Path(output) / 'sources' / SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(__file__).read_bytes())
    return plan


def check(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    c.require(plan.get('build_variant', {}).get('required_entrypoint') == SOURCE,
              'Not a compact-workload context')
    c.require(plan['compiler_flags'] == list(FLAGS) and plan['source_bindings'][SOURCE] == c.sha(__file__),
              'Compact compiler context changed')
    path = root / 'commands.json'
    for receipt in c.unseal(path) if path.exists() else []:
        argv = receipt['argv']
        if argv[0] == plan['tools']['gcc']['path']:
            c.require(argv[1:1+len(FLAGS)] == list(FLAGS), 'Compiler invocation differs from frozen flags')
    return plan


def run(root, command):
    c.require(command in ('discover', 'collect'), 'Unsupported stage')
    check(root)
    with compiler_flags():
        evaluator = w.Evaluator(root)
        try:
            result = getattr(evaluator, command)()
        finally:
            evaluator.runner.lock.close()
            check(root)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'collect', 'check'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--workload', choices=w.WORKLOADS, default='edn')
    parser.add_argument('--pool-size', type=int, default=6)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        prepare(args.reference_root, args.root, args.workload, args.pool_size)
    elif args.command == 'check':
        check(args.root)
    else:
        run(args.root, args.command)


if __name__ == '__main__':
    main()

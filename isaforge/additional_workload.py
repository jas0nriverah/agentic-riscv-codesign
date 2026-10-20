"""Register SLRE's unmodified source/header with the existing serial evaluator.

Additional Embench integer workload after the proposal's remaining workloads
failed memory/library gates. Every input is bound before discovery. The original
workload module and its historical source hashes remain unchanged.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import codesign as c
from . import compact_workload as compact
from . import workload_experiment as w

SOURCE = 'isaforge/additional_workload.py'
WORKLOADS = {'slre': ('slre/libslre.c', 'slre/slre.h')}


def prepare(reference, output, workload='slre', pool_size=6, optimization='-O2'):
    c.require(workload in WORKLOADS and optimization in ('-O2', '-Os'), 'Unsupported workload/build')
    source, header = WORKLOADS[workload]
    c.require(workload not in w.WORKLOADS, 'Duplicate registration')
    w.WORKLOADS[workload] = source
    try:
        prepare_base = compact.prepare if optimization == '-Os' else w.prepare
        plan = prepare_base(reference, output, workload, pool_size)
    finally:
        w.WORKLOADS.pop(workload)
    # Finalize this fresh, unevaluated context, including the required local header.
    plan.pop('context_id')
    inputs = Path(output) / 'inputs'
    header_path = c.ROOT / 'benchmarks/embench/src' / header
    (inputs / header_path.name).write_bytes(header_path.read_bytes())
    plan['inputs'][header_path.name] = c.sha(header_path)
    plan['source_bindings'][str(header_path.relative_to(c.ROOT))] = c.sha(header_path)
    plan['source_bindings'][SOURCE] = c.sha(__file__)
    plan['workload_registration'] = {'source': source, 'header': header, 'optimization': optimization,
                                     'selection_reason': 'Integer regex workload; eligibility decided by fit/correctness, never candidate outcomes.'}
    plan['context_id'] = c.digest(plan)
    c.seal(Path(output) / 'plan.json', plan)
    for relative in (SOURCE, str(header_path.relative_to(c.ROOT))):
        target = Path(output) / 'sources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((c.ROOT / relative).read_bytes())
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--workload', choices=WORKLOADS, default='slre')
    parser.add_argument('--pool-size', type=int, default=6)
    parser.add_argument('--optimization', choices=('O2', 'Os'), default='O2')
    args = parser.parse_args(argv)
    prepare(args.reference_root, args.root, args.workload, args.pool_size, '-'+args.optimization)


if __name__ == '__main__':
    main()

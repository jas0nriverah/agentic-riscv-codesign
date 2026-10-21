"""Disjoint SHA256 candidate pool on the unchanged guarded full-input context.

New candidate evidence on a consumed source, not new-workload generalization.
Six historical literal formulas are excluded before calibrated rank sampling.
Only public historical formula identities determine exclusion.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from . import codesign as c, guarded_workload as g

SOURCE = 'isaforge/training_workload.py'
GUARDED_SOURCE = g.SOURCE
BASE_EXTRACT = g.ORIGINAL_EXTRACT
EXCLUDED_FORMULAS = (
    'xor(add(srli(in0,2),slli(in0,30)),in1)',
    'xor(add(srli(in0,17),slli(in0,15)),in1)',
    'add(in0,slli(in1,21))', 'add(in0,slli(in1,14))',
    'or(slli(in0,24),in1)', 'sub(addi(0,64),in0)',
)
POOL_RULE = ('Exclude the six declared historical SHA256 literal formulas before '
             'guarding, calibration and rank stratification; ' + g.POOL_RULE)


def extract_disjoint(program, profile, sites, size):
    result = BASE_EXTRACT(program, profile, sites, size)
    result['executable_candidates'] = [row for row in result['executable_candidates']
                                      if row['formula'] not in EXCLUDED_FORMULAS]
    result['excluded_historical_formulas'] = list(EXCLUDED_FORMULAS)
    return result


@contextmanager
def registration():
    previous = g.SOURCE, g.POOL_RULE, g.ORIGINAL_EXTRACT
    g.SOURCE, g.POOL_RULE, g.ORIGINAL_EXTRACT = SOURCE, POOL_RULE, extract_disjoint
    try:
        yield
    finally:
        g.SOURCE, g.POOL_RULE, g.ORIGINAL_EXTRACT = previous


def check_plan(plan):
    with registration():
        g.check_plan(plan)
    c.require(plan['workload'] == 'nettle-sha256' and
              plan['memory_partition'] == g.q.partition_spec(7488, 7616) and
              plan.get('excluded_historical_formulas') == list(EXCLUDED_FORMULAS) and
              GUARDED_SOURCE in plan['source_bindings'], 'Different disjoint SHA256 protocol')


def prepare(reference, output):
    with registration():
        plan = g.prepare(reference, output, 'nettle-sha256', 6,
                         program_limit=7488, stack_floor=7616)
    plan.pop('context_id')
    plan['excluded_historical_formulas'] = list(EXCLUDED_FORMULAS)
    plan['selection_evidence_scope'] = 'Prospective disjoint candidate pool on consumed SHA256 source; not source holdout.'
    plan['source_bindings'][GUARDED_SOURCE] = c.sha(c.ROOT/GUARDED_SOURCE)
    target = Path(output)/'sources'/GUARDED_SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(c.ROOT/GUARDED_SOURCE, target)
    plan['context_id'] = c.digest(plan)
    c.seal(Path(output)/'plan.json', plan)
    check_plan(plan)
    return plan


class Evaluator(g.Evaluator):
    def __init__(self, root):
        check_plan(c.unseal(Path(root)/'plan.json'))
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            return super().discover()

    def measure(self, name):
        with registration():
            return super().measure(name)

    def collect(self):
        with registration():
            return super().collect()


def baseline_public(root):
    check_plan(c.unseal(Path(root)/'plan.json'))
    with registration():
        return g.baseline_public(root)


def audit(root):
    check_plan(c.unseal(Path(root)/'plan.json'))
    with registration():
        return g.audit(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'baseline', 'public', 'freeze', 'measure', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    parser.add_argument('--candidate')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, 'Reference required')
        result = prepare(args.reference_root, args.root)
    elif args.command == 'public':
        rows, context, before = baseline_public(args.root)
        for name, value in [('public.json', rows), ('context.json', context), ('before.json', before)]:
            c.seal(args.root/name, value)
        result = dict(context_id=context['context_id'], candidates=len(rows))
    elif args.command == 'audit':
        result = audit(args.root)
    else:
        evaluator = Evaluator(args.root)
        try:
            if args.command == 'freeze':
                with registration():
                    result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
            elif args.command == 'baseline':
                result = evaluator.measure('baseline')
            elif args.command == 'measure':
                c.require(args.candidate is not None, 'Candidate required')
                result = evaluator.measure(args.candidate)
            else:
                result = evaluator.discover()
        finally:
            evaluator.runner.lock.close()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

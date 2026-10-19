#!/usr/bin/env python3
"""One exploratory input-defined route over existing, matched V13 OOF points.

This is post-hoc consumed-development analysis, not a new independent test.
No estimator fitting, synthesis, threshold search or candidate replacement.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from isaforge.features import parse_formula
from isaforge.semantic_features_v7 import _correlation
import audit_v13_comparison as audit

SOURCE = ROOT / 'results/2026-10-15-v13b-coverage-recovery'
SEEDS = (2026101421, 2026101422, 2026101423)
HIGH_PRODUCTS = frozenset(('mulh', 'mulhu', 'mulhsu'))


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())
def need(condition, message):
    if not condition: raise ValueError(message)
def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
def walk(node, path=()):
    yield node, path
    for i, child in enumerate(node.children): yield from walk(child, path + (i,))
def has_input(node):
    return any(n.value in ('in0', 'in1') for n, _ in walk(node))


def route(formula):
    """Accept only syntax; targets, family names, features and errors unavailable."""
    matches = []
    for product, product_path in walk(parse_formula(formula)):
        if product.value not in HIGH_PRODUCTS: continue
        for operand_index, operand in enumerate(product.children):
            for node, local_path in walk(operand):
                rule = _correlation(node)
                if rule is not None and all(has_input(atom) for atom in rule[2]):
                    matches.append({'product': product.value, 'product_path': list(product_path),
                        'operand_index': operand_index, 'pattern_path': list(local_path), 'pattern': rule[1]})
    return {'use_augmented': bool(matches), 'matches': matches}


def inputs():
    fitting = SOURCE / 'fitting'; stage = fitting / 'fit-attempt-0000'
    files = [Path(__file__), ROOT / 'tests/test_evaluate_v14_specialist.py',
        ROOT / 'isaforge/features.py', ROOT / 'isaforge/semantic_features_v7.py',
        ROOT / 'scripts/audit_v13_comparison.py', ROOT / 'scripts/audit_v12_results.py',
        fitting / 'fitting.json', fitting / 'split.json', fitting / 'independent-results-audit.json',
        stage / 'completion.json', stage / 'summary.json']
    files += [stage / 'predictions' / f'{view}-seed-{seed}.json'
              for seed in SEEDS for view in ('control', 'augmented')]
    return files


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    need(not (output / 'routing-plan.json').exists(), 'Single fresh plan required')
    done = read(SOURCE / 'fitting/fit-attempt-0000/completion.json')
    checked = read(SOURCE / 'fitting/independent-results-audit.json')
    need(done['complete'] is True and done['fits_completed'] == 30 and checked['status'] == 'pass'
         and checked['completion_sha256'] == sha(SOURCE / 'fitting/fit-attempt-0000/completion.json'), 'Audited V13 required')
    plan = {'schema': 'isaforge-v14-exploratory-routing-plan-v1', 'variants_scored': 1,
        'gate': 'Any high-product AST operand contains an exact frozen V7 or_sub/sub_and correlation with an input-containing shared atom.',
        'fallback': 'Exact original control OOF point; augmented OOF point only inside the gate.',
        'forbidden_gate_inputs': ['target', 'prediction', 'error', 'cohort', 'family', 'stratum', 'candidate_id'],
        'threshold_search': False, 'new_fits': 0, 'new_native_jobs': 0, 'seeds': list(SEEDS),
        'primary': 'Original1713 nine-stratum macro MAE; coverage48 secondary; caps and tails separate.',
        'scope': 'Post-hoc input-defined development route motivated by observed V13 failures. No fresh-test or promotion claim.',
        'files': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in inputs()]}
    write(output / 'routing-plan.json', plan)
    return plan


def score(output, freeze_commit):
    plan = read(output / 'routing-plan.json')
    need(plan['schema'] == 'isaforge-v14-exploratory-routing-plan-v1' and plan['variants_scored'] == 1,
         'Exact single routing plan required')
    need(not (output / 'routing-results.json').exists(), 'Single scored gate; retain prior results')
    entries = plan['files'] + [{'path': (output / 'routing-plan.json').relative_to(ROOT).as_posix(),
                               'sha256': sha(output / 'routing-plan.json')}]
    for e in entries:
        p = ROOT / e['path']; need(sha(p) == e['sha256'], 'Input/source changed after preparation')
        body = subprocess.check_output(['git', 'show', freeze_commit + ':' + e['path']], cwd=ROOT)
        need(hashlib.sha256(body).hexdigest() == e['sha256'], 'Input/source not in approved Git snapshot')
    data = read(SOURCE / 'fitting/fitting.json'); rows = data['rows']; split = read(SOURCE / 'fitting/split.json')
    gates = [route(row['formula']) for row in rows]
    out = {'schema': 'isaforge-v14-exploratory-routing-results-v1', 'scope': plan['scope'],
           'routing_plan_sha256': sha(output / 'routing-plan.json'), 'freeze_commit': freeze_commit,
           'routed_counts': {cohort: sum(g['use_augmented'] for r, g in zip(rows, gates) if r['cohort'] == cohort)
                             for cohort in ('original1713', 'coverage48')}, 'scores': {}, 'new_fits': 0, 'new_native_jobs': 0}
    decisions = []; scores = {}
    for seed in SEEDS:
        vectors = {}
        for view in ('control', 'augmented'):
            path = SOURCE / 'fitting/fit-attempt-0000/predictions' / f'{view}-seed-{seed}.json'
            vectors[view] = audit.verify_points(read(path), rows, data['original_zero'], split['fold_ids'])
        points = [vectors['augmented' if gate['use_augmented'] else 'control'][i] for i, gate in enumerate(gates)]
        need(all(p == vectors['control'][i] for i, (p, g) in enumerate(zip(points, gates)) if not g['use_augmented']),
             'Ungated control points must be preserved exactly')
        scores[str(seed)] = {v: audit.cohort_scores(rows, pts) for v, pts in {**vectors, 'routed': points}.items()}
        decisions.extend({'seed': seed, 'formula': row['formula'], 'cohort': row['cohort'], 'fold': split['fold_ids'][i],
                          **gates[i], 'predicted_lut4': points[i]} for i, row in enumerate(rows))
    out['scores'] = scores
    differences = [scores[str(s)]['routed']['original1713']['macro_stratum_mae_lut4'] -
                   scores[str(s)]['control']['original1713']['macro_stratum_mae_lut4'] for s in SEEDS]
    out['primary_routed_minus_control'] = {'per_seed': differences, 'mean': statistics.fmean(differences)}
    write(output / 'routing-predictions.json', decisions)
    out['prediction_sha256'] = sha(output / 'routing-predictions.json')
    write(output / 'routing-results.json', out)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'score')); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze-commit')
    args = parser.parse_args(); output = args.output.resolve()
    need(output.is_relative_to(ROOT), 'Repository output required')
    if args.action == 'score': need(args.freeze_commit is not None, 'Exact source freeze required')
    result = prepare(output) if args.action == 'prepare' else score(output, args.freeze_commit)
    print(json.dumps({k: v for k, v in result.items() if k not in ('files', 'scores')}, indent=2))

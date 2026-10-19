"""Evaluate frozen inference and budgeted decisions on new benchmark families."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random

import numpy as np

from .area_model import _metrics, _validated_rows
from .features import parse_formula


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return float(value)


def _key(row):
    if not all(isinstance(row.get(k), str) and row[k] for k in ('benchmark', 'candidate_id')):
        raise ValueError('benchmark and candidate_id are required')
    return row['benchmark'], row['candidate_id']


def operation_count(formula):
    nodes = set()
    def visit(node):
        if node.children:
            nodes.add(node.canonical())
            for child in node.children:
                visit(child)
    visit(parse_formula(formula))
    return len(nodes)


@dataclass(frozen=True)
class Candidate:
    identity: str
    runs: float
    savings: float
    operations: int
    predictions: dict[str, float]


def rank_candidates(candidates, strategy, cap, seed):
    """Pure acquisition function: measured hardware labels are inaccessible."""
    ordered = sorted(candidates, key=lambda c: c.identity)
    if strategy == 'random':
        random.Random(seed).shuffle(ordered)
        return ordered
    if strategy == 'frequency':
        return sorted(ordered, key=lambda c: (-c.runs, c.identity))
    if strategy == 'merit':
        return sorted(ordered, key=lambda c: (-c.savings, c.identity))
    if strategy == 'merit_per_operation':
        return sorted(ordered, key=lambda c: (-c.savings / max(1, c.operations), c.identity))
    if strategy.startswith('model:'):
        name = strategy.removeprefix('model:')
        def priority(c):
            value = c.predictions[name]
            return ((0, -c.savings, value, c.identity) if value <= cap else
                    (1, value - cap, -c.savings, c.identity))
        return sorted(ordered, key=priority)
    raise ValueError(f'unknown strategy {strategy}')


def _bootstrap(values, seed=20261013):
    """Descriptive program-cluster bootstrap; seed repetitions are not samples."""
    if not values:
        return None
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (10000, len(values)))].mean(axis=1)
    return {'mean': float(values.mean()), 'program_count': len(values),
            'bootstrap_95_percentile_interval': [float(x) for x in np.quantile(means, [.025, .975])]}


def evaluate_frozen(training_rows, test_rows, predictions, caps=(32, 64, 128), budgets=(1, 3, 5), random_seeds=range(100), declared_benchmarks=None, calibration_rows=None, policy_predictions=None):
    training = _validated_rows(training_rows)
    calibration = _validated_rows(calibration_rows) if calibration_rows else []
    test = _validated_rows(test_rows)
    if {r['benchmark'] for r in training + calibration} & {r['benchmark'] for r in test}:
        raise ValueError('fresh benchmark families must be absent from training')
    if any(r.get('correctness_verified') is not True for r in test):
        raise ValueError('fresh circuits require verified correctness')
    indexed = {_key(r): r for r in test}
    if len(indexed) != len(test):
        raise ValueError('duplicate candidate identity')
    train_formulas = {r['formula'] for r in training}
    seen_formulas = train_formulas | {r['formula'] for r in calibration}
    estimates = {}
    if not predictions:
        raise ValueError('at least one frozen prediction set is required')
    policy_predictions = policy_predictions or {}
    if set(predictions) & set(policy_predictions):
        raise ValueError('point models and policy scores need distinct names')
    for name, rows in {**predictions, **policy_predictions}.items():
        if not isinstance(name, str) or not name:
            raise ValueError('prediction names must be nonempty strings')
        mapped, by_formula = {}, {}
        for row in rows:
            key = _key(row)
            if key in mapped or key not in indexed:
                raise ValueError('duplicate or unexpected prediction identity')
            if parse_formula(row['formula']).canonical() != indexed[key]['formula']:
                raise ValueError('prediction formula differs from candidate')
            mapped[key] = _number(row.get('predicted_lut4'), 'prediction')
            formula = indexed[key]['formula']
            if formula in by_formula and not math.isclose(by_formula[formula], mapped[key], rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError('formula-only predictions must agree across programs')
            by_formula[formula] = mapped[key]
        if set(mapped) != set(indexed):
            raise ValueError('predictions must cover fresh candidate pool exactly')
        estimates[name] = mapped

    groups = defaultdict(list)
    for row in test:
        groups[row['benchmark']].append(row)
    declared = sorted(set(declared_benchmarks if declared_benchmarks is not None else groups))
    if not set(groups) <= set(declared) or set(declared) & {r['benchmark'] for r in training + calibration}:
        raise ValueError('declared fresh programs must cover test rows and exclude training programs')
    empty = sorted(set(declared) - set(groups))
    accuracy = {}
    for name, mapped in estimates.items():
        if name in policy_predictions:
            continue
        def metrics(rows):
            return _metrics([r['lut4_count'] for r in rows], [mapped[_key(r)] for r in rows]) if rows else None
        novel = [r for r in test if r['formula'] not in seen_formulas]
        unique_novel = list({r['formula']: r for r in novel}.values())
        per_program = {b: {'all': metrics(rows), 'novel': metrics([r for r in rows if r['formula'] not in seen_formulas])}
                       for b, rows in sorted(groups.items())}
        accuracy[name] = {'all_rows': metrics(test), 'novel_rows': metrics(novel),
                          'distinct_novel_formulas': metrics(unique_novel), 'per_program': per_program,
                          'macro_novel_mae': _bootstrap([m['novel']['mae_lut4'] for m in per_program.values() if m['novel']])}

    caps, budgets, random_seeds = list(caps), list(budgets), list(random_seeds)
    if not caps or not budgets or not random_seeds or any(len(set(x)) != len(x) for x in (caps, budgets, random_seeds)):
        raise ValueError('caps, budgets, and random seeds must be nonempty and unique')
    for cap in caps:
        _number(cap, 'cap')
    if any(isinstance(b, bool) or not isinstance(b, int) or b < 1 for b in budgets):
        raise ValueError('budgets must be positive integers')
    if any(isinstance(s, bool) or not isinstance(s, int) for s in random_seeds):
        raise ValueError('seeds must be integers')
    strategies = ['frequency', 'merit', 'merit_per_operation', 'random'] + ['model:' + n for n in estimates]
    details = []
    for benchmark, rows in sorted(groups.items()):
        public = [Candidate(r['candidate_id'], _number(r.get('runs'), 'runs'),
                            _number(r.get('overlap_safe_saved'), 'savings'), operation_count(r['formula']),
                            {n: p[_key(r)] for n, p in estimates.items()}) for r in rows]
        labels = {r['candidate_id']: r['lut4_count'] for r in rows}
        for cap in caps:
            oracle = max((c.savings for c in public if labels[c.identity] <= cap), default=0)
            for budget in budgets:
                for strategy in strategies:
                    for seed in (random_seeds if strategy == 'random' else [0]):
                        ordered = rank_candidates(public, strategy, cap, seed)[:budget]
                        # Acquisition is complete before labels are revealed here.
                        attempted = [{'candidate_id': c.identity, 'actual_lut4': labels[c.identity],
                                      'savings': c.savings} for c in ordered]
                        feasible = [c for c in attempted if c['actual_lut4'] <= cap]
                        best = min(feasible, key=lambda c: (-c['savings'], c['actual_lut4'], c['candidate_id'])) if feasible else None
                        savings = best['savings'] if best else 0
                        details.append({'benchmark': benchmark, 'strategy': strategy, 'cap': cap, 'budget': budget,
                                        'seed': seed, 'attempted': attempted, 'measurements': len(attempted),
                                        'violations': sum(c['actual_lut4'] > cap for c in attempted),
                                        'selected': best, 'oracle_savings': oracle, 'selected_savings': savings,
                                        'absolute_savings_regret': oracle - savings,
                                        'retention': savings / oracle if oracle else None})
    program_trials = defaultdict(list)
    for trial in details:
        program_trials[(trial['strategy'], trial['cap'], trial['budget'], trial['benchmark'])].append(trial)
    program_results = []
    for (strategy, cap, budget, benchmark), trials in sorted(program_trials.items()):
        fractions = [t['retention'] for t in trials if t['retention'] is not None]
        program_results.append({'strategy': strategy, 'cap': cap, 'budget': budget, 'benchmark': benchmark,
                                'retention': float(np.mean(fractions)) if fractions else None,
                                'mean_absolute_savings_regret': float(np.mean([t['absolute_savings_regret'] for t in trials])),
                                'mean_measurements': float(np.mean([t['measurements'] for t in trials])),
                                'mean_violations': float(np.mean([t['violations'] for t in trials])), 'seed_count': len(trials)})
    summaries = []
    for cap in caps:
        for budget in budgets:
            merit = {p['benchmark']: p['retention'] for p in program_results
                     if p['strategy'] == 'merit' and p['cap'] == cap and p['budget'] == budget}
            for strategy in strategies:
                values = [p for p in program_results if p['strategy'] == strategy and p['cap'] == cap and p['budget'] == budget]
                differences = [p['retention'] - merit[p['benchmark']] for p in values if p['retention'] is not None]
                summaries.append({'strategy': strategy, 'cap': cap, 'budget': budget,
                                  'retention': _bootstrap([p['retention'] for p in values if p['retention'] is not None]),
                                  'paired_retention_difference_vs_merit': _bootstrap(differences),
                                  'mean_measurements': float(np.mean([p['mean_measurements'] for p in values])),
                                  'mean_violations': float(np.mean([p['mean_violations'] for p in values])),
                                  'mean_absolute_savings_regret': float(np.mean([p['mean_absolute_savings_regret'] for p in values])),
                                  'excluded_programs_from_retention': empty + [p['benchmark'] for p in values if p['retention'] is None]})
    return {'method': 'frozen prospective new-program inference and offline budgeted selection',
            'training_formula_count': len(train_formulas), 'test_row_count': len(test),
            'test_formula_count': len({r['formula'] for r in test}),
            'calibration_formula_count': len({r['formula'] for r in calibration}),
            'novel_formula_definition': 'canonical formula absent from both model-training and policy-calibration data',
            'novel_formula_count': len({r['formula'] for r in test} - seen_formulas),
            'test_benchmarks': sorted(groups), 'accuracy': accuracy,
            'declared_benchmarks': declared, 'zero_candidate_benchmarks': empty,
            'coverage': [{'benchmark': b, 'measured_candidate_rows': len(groups.get(b, []))} for b in declared],
            'selection': {'summaries': summaries, 'program_results': program_results, 'details': details},
            'limitations': ['Historical training labels are outside target measurement budgets.',
                            'Small convenience sample of programs; program bootstrap intervals are descriptive.',
                            'Point resource predictions and instruction-saving objectives do not measure CPU runtime.',
                            'No claim of outperforming a named published system without a matched implementation.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-rows', type=Path, required=True)
    parser.add_argument('--test-rows', type=Path, required=True)
    parser.add_argument('--predictions', action='append', required=True, help='name=path to frozen prediction JSON')
    parser.add_argument('--policy-predictions', action='append', default=[], help='name=path to acquisition scores, excluded from regression metrics')
    parser.add_argument('--calibration-rows', type=Path, help='Additional seen rows used only for policy calibration; excluded from novel-formula metrics')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--coverage', type=Path, help='Experiment summary containing every declared benchmark, including empty pools')
    args = parser.parse_args(argv)
    paths = {'training': args.training_rows, 'test': args.test_rows}
    predictions = {}
    policies = {}
    for spec in args.predictions:
        name, path = spec.split('=', 1)
        if name in predictions:
            raise ValueError('duplicate model name')
        paths['predictions:' + name] = Path(path)
        predictions[name] = json.loads(Path(path).read_text())
    for spec in args.policy_predictions:
        name, path = spec.split('=', 1)
        if name in predictions or name in policies:
            raise ValueError('duplicate model or policy name')
        paths['policy:' + name] = Path(path)
        policies[name] = json.loads(Path(path).read_text())
    declared = None
    if args.coverage:
        paths['coverage'] = args.coverage
        declared = [row['benchmark'] for row in json.loads(args.coverage.read_text())['benchmarks']]
    calibration_rows = None
    if args.calibration_rows:
        paths['calibration'] = args.calibration_rows
        calibration_rows = json.loads(args.calibration_rows.read_text())
    report = evaluate_frozen(json.loads(args.training_rows.read_text()), json.loads(args.test_rows.read_text()), predictions,
                             declared_benchmarks=declared, calibration_rows=calibration_rows, policy_predictions=policies)
    report['input_sha256'] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('test_row_count', 'test_formula_count', 'novel_formula_count')}, indent=2))


if __name__ == '__main__':
    main()

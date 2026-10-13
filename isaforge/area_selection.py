"""Replay budgeted single-circuit selection using held-out LUT4 predictions.

Acquisition sees only workload frequency, overlap-safe instruction savings and
outer-fold area predictions. Actual LUT4 is revealed only after each candidate
measurement. This offline replay measures isolated resource selection, never CPU
speedup or the area of an integrated collection of custom instructions.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
import random
from typing import Callable

STRATEGIES = ('frequency', 'merit', 'random', 'predicted_area_feasible_merit')
DEFAULT_CAPS = (32, 64, 128)
DEFAULT_BUDGETS = (1, 3, 5)
DEFAULT_SEEDS = (0, 1, 2, 3, 4)
OUTER_METHOD = 'nested leave-one-benchmark-out with identical-formula exclusion'


@dataclass(frozen=True)
class PublicCandidate:
    """Only information available before measuring a candidate's circuit."""
    candidate_id: str
    runs: float
    overlap_safe_saved: float
    predicted_lut4: float


def _nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{label} must be a finite nonnegative number')
    return float(value)


def acquisition_order(candidates: list[PublicCandidate], strategy: str, cap: float, seed: int) -> list[PublicCandidate]:
    """Rank without access to any candidate's measured resource cost."""
    ordered = sorted(candidates, key=lambda item: item.candidate_id)
    if strategy == 'random':
        random.Random(seed).shuffle(ordered)
        return ordered
    if strategy == 'frequency':
        return sorted(ordered, key=lambda item: (-item.runs, item.candidate_id))
    if strategy == 'merit':
        return sorted(ordered, key=lambda item: (-item.overlap_safe_saved, item.candidate_id))
    if strategy == 'predicted_area_feasible_merit':
        return sorted(ordered, key=lambda item: (
            (0, -item.overlap_safe_saved, item.predicted_lut4, item.candidate_id)
            if item.predicted_lut4 <= cap else
            (1, item.predicted_lut4 - cap, -item.overlap_safe_saved, item.candidate_id)))
    raise ValueError(f'unknown selection strategy: {strategy}')


def select_measured_candidate(candidates: list[PublicCandidate], measure: Callable[[str], float],
                              strategy: str, cap: float, budget: int, seed: int) -> dict:
    """Verify each attempted candidate and retain the best measured feasible one."""
    cap = _nonnegative(cap, 'LUT4 cap')
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ValueError('candidate measurement budget must be a positive integer')
    attempted = []
    feasible = []
    for candidate in acquisition_order(candidates, strategy, cap, seed)[:budget]:
        actual = _nonnegative(measure(candidate.candidate_id), 'measured LUT4')
        record = {'candidate_id': candidate.candidate_id,
                  'overlap_safe_saved': candidate.overlap_safe_saved,
                  'predicted_lut4': candidate.predicted_lut4,
                  'actual_lut4': actual, 'actual_area_violation': actual > cap}
        attempted.append(record)
        if actual <= cap:
            feasible.append(record)
    best = min(feasible, key=lambda item: (-item['overlap_safe_saved'], item['actual_lut4'], item['candidate_id'])) if feasible else None
    return {'strategy': strategy, 'lut4_cap': cap, 'measurement_budget': budget, 'seed': seed,
            'candidate_measurements': len(attempted), 'attempted': attempted,
            'attempted_actual_area_violations': sum(item['actual_area_violation'] for item in attempted),
            'first_proposed_actual_area_violation': attempted[0]['actual_area_violation'] if attempted else None,
            'selected_candidate_id': best['candidate_id'] if best else None,
            'selected_actual_lut4': best['actual_lut4'] if best else None,
            'selected_overlap_safe_saved': best['overlap_safe_saved'] if best else 0.0,
            'baseline_overlap_safe_saved': 0.0}


def _outer_predictions(report: dict, expected: set[tuple[str, str]]) -> dict[tuple[str, str], float]:
    if report.get('method') != OUTER_METHOD:
        raise ValueError('selection requires nested outer benchmark holdout predictions, not the final refitted model')
    result = {}
    for fold in report.get('folds', []):
        benchmark = fold.get('held_out_benchmark')
        if fold.get('status') != 'evaluated':
            raise ValueError(f'outer prediction fold for {benchmark} is not evaluated')
        if benchmark in fold.get('train_benchmarks', []):
            raise ValueError('held-out benchmark leaked into training benchmarks')
        for item in fold.get('predictions', []):
            key = (benchmark, item.get('candidate_id'))
            if key in result:
                raise ValueError(f'duplicate outer prediction: {key}')
            result[key] = _nonnegative(item.get('predicted_lut4'), 'held-out predicted LUT4')
    if set(result) != expected:
        raise ValueError(f'outer predictions must cover the entire pool exactly: {len(expected - set(result))} missing, {len(set(result) - expected)} extra')
    if report.get('row_count') != len(expected):
        raise ValueError('outer model report row_count does not match the entire candidate pool')
    return result


def evaluate_area_selection(rows: list[dict], outer_report: dict,
                            caps=DEFAULT_CAPS, budgets=DEFAULT_BUDGETS, seeds=DEFAULT_SEEDS) -> dict:
    """Compare all strategies at fixed budgets against a fully measured oracle."""
    if not rows:
        raise ValueError('at least one measured candidate is required')
    public_by_benchmark = defaultdict(list)
    labels = {}
    public_rows = {}
    for row in rows:
        benchmark, identity = row.get('benchmark'), row.get('candidate_id')
        if not isinstance(benchmark, str) or not benchmark or not isinstance(identity, str) or not identity:
            raise ValueError('each row requires benchmark and candidate_id strings')
        key = (benchmark, identity)
        if key in labels:
            raise ValueError(f'duplicate candidate row: {key}')
        if row.get('measurement_source') != 'rtl_synthesis':
            raise ValueError('selection requires actual rtl_synthesis LUT4 labels')
        if row.get('correctness_verified') is not True:
            raise ValueError('selection requires correctness-verified candidate circuits')
        labels[key] = _nonnegative(row.get('lut4_count'), 'actual LUT4')
        public_rows[key] = (_nonnegative(row.get('runs'), 'runs'),
                            _nonnegative(row.get('overlap_safe_saved'), 'overlap-safe savings'))
    predictions = _outer_predictions(outer_report, set(labels))
    for (benchmark, identity), (runs, saved) in public_rows.items():
        public_by_benchmark[benchmark].append(PublicCandidate(identity, runs, saved, predictions[(benchmark, identity)]))
    caps, budgets, seeds = list(caps), list(budgets), list(seeds)
    if not caps or not budgets or not seeds or len(set(caps)) != len(caps) or len(set(budgets)) != len(budgets) or len(set(seeds)) != len(seeds):
        raise ValueError('caps, budgets and seeds must be nonempty and unique')
    for cap in caps:
        _nonnegative(cap, 'LUT4 cap')
    for budget in budgets:
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise ValueError('candidate measurement budgets must be positive integers')
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError('random seeds must be integers')
    details = []
    for benchmark in sorted(public_by_benchmark):
        candidates = public_by_benchmark[benchmark]
        for cap in caps:
            # Full labels are used here only for the retrospective oracle.
            oracle_feasible = [candidate for candidate in candidates if labels[(benchmark, candidate.candidate_id)] <= cap]
            oracle = min(oracle_feasible, key=lambda item: (-item.overlap_safe_saved, labels[(benchmark, item.candidate_id)], item.candidate_id)) if oracle_feasible else None
            oracle_saved = oracle.overlap_safe_saved if oracle else 0.0
            for budget in budgets:
                for seed in seeds:
                    for strategy in STRATEGIES:
                        result = select_measured_candidate(candidates, lambda identity: labels[(benchmark, identity)], strategy, cap, budget, seed)
                        result.update(benchmark=benchmark, candidate_pool_size=len(candidates),
                                      oracle_candidate_id=oracle.candidate_id if oracle else None,
                                      oracle_overlap_safe_saved=oracle_saved,
                                      oracle_actual_lut4=labels[(benchmark, oracle.candidate_id)] if oracle else None,
                                      retained_oracle_instruction_saving_fraction=result['selected_overlap_safe_saved'] / oracle_saved if oracle_saved else None)
                        details.append(result)
    grouped = defaultdict(list)
    for result in details:
        grouped[(result['strategy'], result['lut4_cap'], result['measurement_budget'])].append(result)
    aggregates = []
    for (strategy, cap, budget), results in sorted(grouped.items()):
        fractions = [item['retained_oracle_instruction_saving_fraction'] for item in results if item['retained_oracle_instruction_saving_fraction'] is not None]
        oracle_sum = sum(item['oracle_overlap_safe_saved'] for item in results)
        measurements = sum(item['candidate_measurements'] for item in results)
        violations = sum(item['attempted_actual_area_violations'] for item in results)
        aggregates.append({'strategy': strategy, 'lut4_cap': cap, 'measurement_budget': budget,
                           'benchmark_seed_cases': len(results), 'positive_oracle_cases': len(fractions),
                           'mean_retained_oracle_instruction_saving_fraction': sum(fractions) / len(fractions) if fractions else None,
                           'pooled_retained_oracle_instruction_saving_fraction': sum(item['selected_overlap_safe_saved'] for item in results) / oracle_sum if oracle_sum else None,
                           'candidate_measurements': measurements,
                           'mean_candidate_measurements': measurements / len(results),
                           'attempted_actual_area_violations': violations,
                           'attempted_actual_area_violation_fraction': violations / measurements if measurements else None,
                           'first_proposed_actual_area_violation_fraction': sum(bool(item['first_proposed_actual_area_violation']) for item in results) / len(results)})
    return {'method': 'offline replay of budgeted single-circuit selection with nested outer-fold area predictions',
            'target': 'overlap-safe instruction savings under an isolated iCE40 SB_LUT4 cap',
            'row_count': len(rows), 'benchmark_count': len(public_by_benchmark),
            'historical_training_formula_counts': {
                fold['held_out_benchmark']: fold.get('train_formula_count')
                for fold in outer_report['folds']},
            'strategies': list(STRATEGIES), 'lut4_caps': caps, 'measurement_budgets': budgets, 'seeds': seeds,
            'baseline_overlap_safe_saved': 0,
            'oracle_zero_savings_fraction_policy': 'undefined fractions are null and excluded from mean retention',
            'aggregates': aggregates, 'details': details,
            'limitations': ['Offline replay over an entirely synthesized finite candidate pool; no live adaptive model updates.',
                            'Measurement budgets count target candidates only; previously measured training circuits from other benchmarks are outside that budget.',
                            'Acquisition excludes measured LUT4; it uses outer held-out predictions and public workload frequency/savings.',
                            'Each case chooses a single candidate circuit, not a collection with an additive area budget.',
                            'LUT4 cap ignores carry resources, physical area, timing, routing, and processor integration overhead.',
                            'Instruction savings assume safe replacement by one instruction; they are not measured CPU speedup.',
                            'Only random ordering varies with seed; deterministic strategies repeat for matched cases.',
                            'Model point predictions have no calibrated area-feasibility uncertainty.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', required=True, type=Path)
    parser.add_argument('--outer-evaluation', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    rows_text = args.rows.read_text()
    evaluation_text = args.outer_evaluation.read_text()
    report = evaluate_area_selection(json.loads(rows_text), json.loads(evaluation_text))
    report['provenance'] = {
        'dataset_path': str(args.rows), 'dataset_sha256': hashlib.sha256(rows_text.encode()).hexdigest(),
        'outer_evaluation_path': str(args.outer_evaluation),
        'outer_evaluation_sha256': hashlib.sha256(evaluation_text.encode()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Evaluated {report['row_count']} candidates across {report['benchmark_count']} benchmarks; wrote {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

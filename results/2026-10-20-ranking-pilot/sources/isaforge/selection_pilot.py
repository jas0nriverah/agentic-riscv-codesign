"""Consumed-data development comparison; never a generalization claim.

Keeps the primary speedup_corpus.evaluate three-workload gate unchanged. Uses
authenticated automatic RV32I pools to test whether grouped ranking or paid
adaptation improves verified selection. No native jobs or parameter search.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import random
import statistics
import time

from . import codesign as c
from . import speedup_corpus as corpus
from .features import FEATURE_COLUMNS
from .model import SpeedupPredictor
from .ranking import PARAMETERS, SpeedupRanker
from .workload_audit import import_automatic

POLICIES = ('frequency', 'merit', 'random', 'regression_zero_shot',
            'ranking_zero_shot', 'regression_adapt', 'ucb_adapt')
PUBLIC_KEYS = ('candidate_id', 'benchmark', 'formula', *FEATURE_COLUMNS)
SOURCES = ('isaforge/selection_pilot.py', 'isaforge/ranking.py', 'isaforge/model.py',
           'isaforge/features.py', 'isaforge/speedup_corpus.py', 'isaforge/codesign.py',
           'isaforge/selection.py', 'isaforge/workload_audit.py')


def public_rows(rows):
    return [{k: copy.deepcopy(row[k]) for k in PUBLIC_KEYS} for row in rows]


def freeze(roots, output):
    output = Path(output)
    c.require(not output.exists(), 'Use a fresh pilot directory')
    collections = [import_automatic(root) for root in roots]
    rows = [row for collection in collections for row in collection['rows']]
    corpus.validate(rows)
    groups = sorted({r['workload_group'] for r in rows})
    c.require(len(groups) >= 2, 'Development transfer needs two workload groups')
    c.require(all(len([r for r in rows if r['workload_group'] == g]) == 6 for g in groups),
              'This bounded pilot requires six candidates per workload')
    for group in groups:
        train, _, _ = corpus.split(rows, group)
        c.require(len(train) >= 2, 'Insufficient unrelated historical training rows')
    protocol = {'scope': 'Consumed-data development pilot; not an untouched test or generalization claim.',
                'hypothesis': 'Fixed within-context pairwise ranking may improve verified selection relative to speedup regression; no tuning.',
                'seeds': [0, 1, 2, 3, 4], 'budgets': [1, 2, 3, 4, 5, 6], 'policies': POLICIES,
                'ranker_parameters': PARAMETERS, 'regressor': 'Unchanged SpeedupPredictor: 20 bootstrap, 80 trees, depth 2, learning rate .05.',
                'split': 'Entire workload held out, with all shared operation-tree families removed from training.',
                'acquisition': 'UCB uses 95th ensemble percentile, then mean, then seeded order; mean and rank policies use seeded order for ties.',
                'features': FEATURE_COLUMNS, 'corpus_sha256': c.digest(rows),
                'public_sha256': c.digest(public_rows(rows)),
                'sources': {name: c.sha(c.ROOT / name) for name in SOURCES},
                'packages': {name: importlib.metadata.version(name) for name in ('numpy', 'xgboost', 'scikit-learn')},
                'measurement_contexts': [collection['source_contexts'][0] for collection in collections],
                'cost_accounting': 'All policies have the same paid historical dataset available. Show target-only and shared-history-plus-target costs; inference is charged separately. Excluded historical rows still cost collection time.',
                'limitations': ['Only consumed workload groups; protocol is frozen before this comparison, after data collection.',
                               'Top-six merit shortlist creates selection bias; oracle covers only that pool.',
                               'No architecture-calibrated merit, constrained EI, cost-aware acquisition or LLM agent in this pilot.',
                               'Empirical ensemble coverage is diagnostic, not a conformal or calibrated guarantee.',
                               'Offline costs reuse recorded durations; no fresh policy wall-clock experiment.',
                               'Single-instruction results; sets require joint evaluation.']}
    output.mkdir(parents=True)
    c.seal(output / 'protocol.json', protocol)
    c.seal(output / 'corpus.json', {'rows': rows, 'readiness': corpus.readiness(rows)})
    c.seal(output / 'public.json', public_rows(rows))
    # Raw command time is disjoint by stage. Measurement wall durations are
    # separate, overlapping views and are never added to command totals.
    setup = []
    for root, collection in zip(roots, collections):
        root = Path(root)
        receipts = c.unseal(root / 'commands.json')
        setup.append({'context_id': collection['source_contexts'][0],
                      'discovery_command_seconds': sum(r['elapsed_seconds'] for r in receipts if r['log'].startswith('discovery/')),
                      'baseline_command_seconds': sum(r['elapsed_seconds'] for r in receipts if r['log'].startswith('measurements/baseline/')),
                      'all_command_seconds': sum(r['elapsed_seconds'] for r in receipts),
                      'all_commands': len(receipts),
                      'candidate_wall_seconds': sum(r['measurement_seconds'] for r in collection['rows'])})
    c.seal(output / 'collection-costs.json', setup)
    return protocol


def zero_shot(training, public, seed):
    began = time.monotonic()
    regression = SpeedupPredictor(seed=seed).fit(training).predict(public)
    regression_seconds = time.monotonic() - began
    began = time.monotonic()
    ranking = SpeedupRanker(seed=seed).fit(training).predict(public)
    return {'regression': regression, 'ranking': ranking,
            'training_ids': [r['candidate_id'] for r in training],
            'regression_seconds': regression_seconds, 'ranking_seconds': time.monotonic() - began}


def search(public, training, provider, area_cap, policy, seed, budget, predictions):
    """Only provider(identity) releases a target outcome, through a charged tool."""
    c.require(policy in POLICIES, 'Unknown policy')
    tools = c.LiveSelectionTools(public, provider, budget, area_cap, seed)
    ordered = copy.deepcopy(public)
    random.Random(seed).shuffle(ordered)
    if policy in ('frequency', 'merit'):
        ordered.sort(key=lambda r: -r['runs' if policy == 'frequency' else 'saved'])
    ranks = {r['candidate_id']: r['rank_score'] for r in predictions['ranking']}
    reg = {r['candidate_id']: r for r in predictions['regression']}
    inference = (predictions['ranking_seconds'] if policy == 'ranking_zero_shot' else
                 predictions['regression_seconds'] if policy.startswith(('regression', 'ucb')) else 0.0)
    curve = []
    while tools.remaining_budget and ordered:
        if policy in ('regression_adapt', 'ucb_adapt') and tools.observations:
            began = time.monotonic()
            values = SpeedupPredictor(seed=seed).fit(training + list(tools.observations.values())).predict(ordered)
            inference += time.monotonic() - began
            reg = {r['candidate_id']: r for r in values}
        if policy in ('regression_zero_shot', 'regression_adapt', 'ucb_adapt'):
            def score(row):
                estimate = reg[row['candidate_id']]
                return (estimate['upper'], estimate['mean']) if policy == 'ucb_adapt' else (estimate['mean'],)
            chosen = max(ordered, key=score)
        elif policy == 'ranking_zero_shot':
            chosen = max(ordered, key=lambda r: ranks[r['candidate_id']])
        else:
            chosen = ordered[0]
        tools.record({'action': 'acquire', 'candidate_id': chosen['candidate_id'], 'policy': policy,
                      'historical_training_ids': [r['candidate_id'] for r in training],
                      'paid_target_ids_before_query': tools.measured_candidate_ids,
                      'predictions': list(reg.values()) if policy in ('regression_adapt', 'ucb_adapt') else []})
        tools.measure(chosen['candidate_id'])
        ordered = [r for r in ordered if r['candidate_id'] != chosen['candidate_id']]
        best = tools.choose_final()
        curve.append({'budget': tools.measurements_used, 'best_speedup': best['speedup'] if best else 1.0,
                      'selected_id': best['candidate_id'] if best else None,
                      'measured_ids': tools.measured_candidate_ids,
                      'target_measurement_seconds': sum(r['measurement_seconds'] for r in tools.observations.values()),
                      'inference_seconds': inference})
    return {'curve': curve, 'events': tools.events}


def pair_accuracy(actual, scores):
    pairs = [(i, j) for i in range(len(actual)) for j in range(i) if actual[i] != actual[j]]
    if not pairs:
        return None
    return sum(0.5 if scores[i] == scores[j] else float((actual[i] > actual[j]) == (scores[i] > scores[j]))
               for i, j in pairs) / len(pairs)


def stable(value):
    """Wall-clock inference measurements vary on replay; scientific results do not."""
    if isinstance(value, list):
        return [stable(v) for v in value]
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in
                ('inference_seconds', 'regression_seconds', 'ranking_seconds', 'total_with_inference_seconds')}
    return value


def run(root, verify=False):
    root = Path(root)
    protocol = c.unseal(root / 'protocol.json')
    for name, expected in protocol['sources'].items():
        c.require(c.sha(c.ROOT / name) == expected, 'Pilot source changed: '+name)
    for name, version in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == version, 'Pilot dependency changed: '+name)
    rows = c.unseal(root / 'corpus.json')['rows']
    corpus.validate(rows)
    c.require(c.digest(rows) == protocol['corpus_sha256'] and c.digest(public_rows(rows)) == protocol['public_sha256'], 'Corpus changed')
    c.require(public_rows(rows) == c.unseal(root / 'public.json'), 'Public features changed')
    c.require(verify or not (root / 'report.json').exists(), 'Preserve existing report; use --verify')
    folds, results = [], []
    for group in sorted({r['workload_group'] for r in rows}):
        training, target, excluded = corpus.split(rows, group)
        public = public_rows(target)
        labels = {r['candidate_id']: r for r in target}
        caps = {r['area_cap'] for r in target}
        c.require(len(caps) == 1, 'Mixed hardware constraints')
        cap = next(iter(caps))
        available = [r for r in rows if r['workload_group'] != group]
        history_seconds = sum(r['measurement_seconds'] for r in available)
        oracle = max([1.0] + [r['speedup'] for r in target if r['area'] <= cap and r['timing_feasible']])
        diagnostics = []
        for seed in protocol['seeds']:
            predictions = zero_shot(training, public, seed)
            path = root / f'predictions-{c.digest(group)[:12]}-{seed}.json'
            if verify:
                c.require(stable(predictions) == stable(c.unseal(path)), 'Prediction replay differs')
            else:
                c.require(not path.exists(), 'Do not overwrite prior predictions')
                c.seal(path, predictions)  # frozen before any policy query/scoring
            actual = [r['speedup'] for r in target]
            reg = predictions['regression']
            diagnostics.append({'seed': seed,
                                'regression_mae': statistics.mean(abs(y-p['mean']) for y,p in zip(actual,reg)),
                                'regression_pair_accuracy': pair_accuracy(actual, [p['mean'] for p in reg]),
                                'ranking_pair_accuracy': pair_accuracy(actual, [p['rank_score'] for p in predictions['ranking']]),
                                'ensemble_interval_coverage': statistics.mean(float(p['lower'] <= y <= p['upper']) for y,p in zip(actual,reg)),
                                'mean_interval_width': statistics.mean(p['upper']-p['lower'] for p in reg)})
            for policy in protocol['policies']:
                outcome = search(public, training, lambda r: copy.deepcopy(labels[r['candidate_id']]), cap,
                                 policy, seed, max(protocol['budgets']), predictions)
                for point in outcome['curve']:
                    point.update(regret=oracle-point['best_speedup'], historical_measurements=len(available),
                                 historical_measurement_seconds=history_seconds,
                                 total_measurements=len(available)+point['budget'],
                                 total_measurement_seconds=history_seconds+point['target_measurement_seconds'],
                                 total_with_inference_seconds=history_seconds+point['target_measurement_seconds']+point['inference_seconds'])
                results.append({'held_out_group': group, 'policy': policy, 'seed': seed, **outcome})
        folds.append({'held_out_group': group, 'training_rows': len(training),
                      'historical_available_rows': len(available), 'excluded_related_ids': excluded,
                      'oracle_speedup': oracle, 'diagnostics': diagnostics})
    summary = []
    for fold in folds:
        for budget in protocol['budgets']:
            for policy in protocol['policies']:
                points = [p for r in results if r['held_out_group'] == fold['held_out_group'] and r['policy'] == policy
                          for p in r['curve'] if p['budget'] == budget]
                summary.append({'held_out_group': fold['held_out_group'], 'budget': budget, 'policy': policy,
                                'mean_best_speedup': statistics.mean(p['best_speedup'] for p in points),
                                'mean_regret': statistics.mean(p['regret'] for p in points),
                                'oracle_hits': sum(p['regret'] == 0 for p in points),
                                'mean_target_measurement_seconds': statistics.mean(p['target_measurement_seconds'] for p in points)})
    report = {'scope': protocol['scope'], 'folds': folds, 'runs': results, 'summary': summary,
              'new_native_jobs': 0, 'workload_generalization_established': False, 'limitations': protocol['limitations']}
    if verify:
        c.require(stable(report) == stable(c.unseal(root / 'report.json')), 'Pilot replay differs')
    else:
        c.seal(root / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'run', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workload-root', type=Path, action='append', default=[])
    parser.add_argument('--acknowledge-consumed-data', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        c.require(args.acknowledge_consumed_data, 'Explicit --acknowledge-consumed-data required for this development pilot')
        freeze(args.workload_root, args.root)
    else:
        report = run(args.root, verify=args.command == 'verify')
        print({'policy_seed_budget_outcomes': sum(len(r['curve']) for r in report['runs']),
               'new_native_jobs': 0, 'workload_generalization_established': False,
               'budget_one': [r for r in report['summary'] if r['budget'] == 1]})


if __name__ == '__main__':
    main()

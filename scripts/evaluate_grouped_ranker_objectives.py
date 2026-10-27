"""Retrospective, whole-workload comparison of XGBoost ranking objectives.

This diagnostic uses only already-consumed labels. It compares the released
pairwise ranker with XGBoost's graded NDCG ranker and fixed frequency, merit,
random, and calibrated-latency orders. Every outer fold withholds a complete
workload and related operation-tree families. Nothing here promotes a model or
constitutes a new untouched confirmation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.metadata
import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as budgeted, codesign as c, speedup_corpus
from isaforge.model import feature_matrix
from isaforge.ranking import PARAMETERS, grouped_labels
from scripts.reproduce_guarded_sha256 import _manifest

SOURCE = 'scripts/evaluate_grouped_ranker_objectives.py'
SOURCES = (SOURCE, 'isaforge/budgeted_selection.py', 'isaforge/model.py',
    'isaforge/ranking.py', 'isaforge/features.py', 'isaforge/speedup_corpus.py',
    'isaforge/codesign.py', 'scripts/reproduce_guarded_sha256.py')
POLICIES = ('frequency', 'merit', 'calibrated_latency', 'random',
    'xgb_rank_pairwise', 'xgb_rank_ndcg')
OBJECTIVES = {'xgb_rank_pairwise': 'rank:pairwise', 'xgb_rank_ndcg': 'rank:ndcg'}
SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
AREA_CAP = 64
CLOCK_MHZ = 12.0


def _cycle_reduction(speedup):
    return 1.0 - 1.0 / float(speedup)


def _fit_ranker(training, public, objective, seed):
    from xgboost import XGBRanker

    ordered, labels, qids, groups = grouped_labels(training)
    c.require(any(group['distinct_labels'] > 1 for group in groups),
        'Training fold needs a measured unequal pair within a benchmark query group')
    params = dict(PARAMETERS)
    params['objective'] = objective
    model = XGBRanker(**params, random_state=seed)
    model.fit(feature_matrix(ordered), labels, qid=qids)
    scores = model.predict(feature_matrix(public))
    c.require(len(scores) == len(public), 'Ranker prediction count differs from held-out pool')
    return {row['candidate_id']: float(score) for row, score in zip(public, scores)}


def _ordered(policy, pool, rank_scores, seed):
    if policy == 'frequency':
        return sorted(pool, key=lambda row: (-row['runs'], row['candidate_id']))
    if policy == 'merit':
        return sorted(pool, key=lambda row: (-row['saved'], row['candidate_id']))
    if policy == 'calibrated_latency':
        return sorted(pool, key=lambda row: (-row['latency_features']['estimated_speedup'], row['candidate_id']))
    if policy == 'random':
        rows = list(pool)
        random.Random(seed).shuffle(rows)
        return rows
    c.require(policy in rank_scores, 'Missing frozen ranker scores')
    return sorted(pool, key=lambda row: (-rank_scores[policy][row['candidate_id']], row['candidate_id']))


def _selection_row(workload, benchmark, policy, seed, budget, ordered, oracle):
    attempted = ordered[:budget]
    feasible = [row for row in attempted if budgeted._feasible(row, AREA_CAP, CLOCK_MHZ)
        and row['speedup'] > 1.0]
    best = min(feasible, key=lambda row: (-row['speedup'], row['area_delta_lut4'], row['candidate_id'])) if feasible else None
    best_speedup = best['speedup'] if best else 1.0
    return dict(workload_group=workload, benchmark=benchmark, policy=policy, seed=seed,
        budget=budget, attempted_candidate_ids=[row['candidate_id'] for row in attempted],
        selected_candidate_id=best['candidate_id'] if best else None,
        best_speedup=best_speedup, verified_cycle_reduction=_cycle_reduction(best_speedup),
        oracle_speedup=oracle, oracle_cycle_reduction=_cycle_reduction(oracle),
        cycle_reduction_regret=max(0.0, _cycle_reduction(oracle)-_cycle_reduction(best_speedup)),
        measurement_seconds=sum(row['measurement_seconds'] for row in attempted),
        known_infeasible_attempts=sum(not budgeted._feasible(row, AREA_CAP, CLOCK_MHZ) for row in attempted),
        oracle_hit=bool(best and best['speedup'] == oracle))


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = fraction * (len(ordered)-1)
    lower = int(position)
    upper = min(lower+1, len(ordered)-1)
    weight = position-lower
    return ordered[lower]*(1-weight)+ordered[upper]*weight


def _paired_bootstrap(group_values, *, seed=20261026, draws=10000):
    """Percentile interval with workloads, rather than rows, as resampling units."""
    groups = sorted(group_values)
    if not groups:
        return dict(mean=None, lower_95=None, upper_95=None, workload_groups=0)
    differences = [group_values[group] for group in groups]
    rng = random.Random(seed)
    boot = [statistics.mean(differences[rng.randrange(len(differences))]
        for _ in differences) for _ in range(draws)]
    return dict(mean=statistics.mean(differences), lower_95=_percentile(boot, .025),
        upper_95=_percentile(boot, .975), workload_groups=len(groups),
        wins=sum(value > 0 for value in differences), ties=sum(value == 0 for value in differences),
        losses=sum(value < 0 for value in differences),
        interpretation='Positive values mean the challenger has lower cycle-reduction regret.')


def _summarize(selections):
    by_group = defaultdict(list)
    for row in selections:
        by_group[(row['workload_group'], row['policy'], row['budget'])].append(row)
    group_summary = []
    for (workload, policy, budget), rows in sorted(by_group.items()):
        group_summary.append(dict(workload_group=workload, policy=policy, budget=budget,
            mean_best_speedup=statistics.mean(row['best_speedup'] for row in rows),
            mean_cycle_reduction=statistics.mean(row['verified_cycle_reduction'] for row in rows),
            mean_regret=statistics.mean(row['cycle_reduction_regret'] for row in rows),
            mean_measurement_seconds=statistics.mean(row['measurement_seconds'] for row in rows),
            mean_infeasible_attempts=statistics.mean(row['known_infeasible_attempts'] for row in rows),
            oracle_hit_rate=statistics.mean(row['oracle_hit'] for row in rows),
            benchmark_contexts=len({row['benchmark'] for row in rows})))

    macro = []
    by_policy_budget = defaultdict(list)
    for row in group_summary:
        by_policy_budget[(row['policy'], row['budget'])].append(row)
    for (policy, budget), rows in sorted(by_policy_budget.items()):
        macro.append(dict(policy=policy, budget=budget, workload_groups=len(rows),
            mean_best_speedup=statistics.mean(row['mean_best_speedup'] for row in rows),
            mean_cycle_reduction=statistics.mean(row['mean_cycle_reduction'] for row in rows),
            mean_regret=statistics.mean(row['mean_regret'] for row in rows),
            mean_measurement_seconds=statistics.mean(row['mean_measurement_seconds'] for row in rows),
            mean_infeasible_attempts=statistics.mean(row['mean_infeasible_attempts'] for row in rows),
            mean_oracle_hit_rate=statistics.mean(row['oracle_hit_rate'] for row in rows)))

    contrasts = []
    indexed = {(row['workload_group'], row['policy'], row['budget']): row for row in group_summary}
    for budget in BUDGETS:
        for baseline in ('frequency', 'merit', 'calibrated_latency'):
            for challenger in ('xgb_rank_pairwise', 'xgb_rank_ndcg'):
                shared = sorted({group for group, p, b in indexed if p == baseline and b == budget} &
                    {group for group, p, b in indexed if p == challenger and b == budget})
                differences = {group: indexed[(group, baseline, budget)]['mean_regret']-
                    indexed[(group, challenger, budget)]['mean_regret'] for group in shared}
                contrasts.append(dict(budget=budget, baseline=baseline, challenger=challenger,
                    **_paired_bootstrap(differences)))
    return dict(group_summary=group_summary, macro_summary=macro, paired_contrasts=contrasts)


def evaluate(corpus_path, output):
    corpus_path, output = Path(corpus_path).resolve(), Path(output).resolve()
    c.require(corpus_path.is_relative_to(ROOT) and output.is_relative_to(ROOT),
        'Repository-local corpus and output required')
    c.require(not output.exists(), 'Use a fresh exploratory output directory')
    _manifest(corpus_path.parent)
    corpus = c.unseal(corpus_path)
    c.require(corpus.get('schema') == 'isaforge-consumed-guarded-corpus-v1' and
        corpus.get('scope') == 'Historical corpus plus all charged consumed Lift transfer attempts.',
        'Authenticated consumed guarded corpus required')
    rows = corpus.get('rows')
    c.require(isinstance(rows, list) and len(rows) == 122 and corpus.get('successful_labels') == 122 and
        corpus.get('total_candidate_attempts') == 126 and corpus.get('new_native_jobs') == 0,
        'Complete 122-label/126-attempt consumed corpus required')
    for row in rows:
        c.require(budgeted.validate_outcome(row), 'Only successful, verified measured rows may be evaluated')
        c.require(row['candidate_family'] == speedup_corpus.family(row['formula']),
            'Candidate-family annotation differs')
    groups = sorted({row['workload_group'] for row in rows})
    c.require(len(groups) >= 3, 'Whole-workload evaluation needs at least three independent groups')

    output.mkdir(parents=True)
    protocol = dict(schema='isaforge-grouped-ranker-objective-diagnostic-v1',
        scope='retrospective consumed-data development; no untouched confirmation',
        corpus_path=corpus_path.relative_to(ROOT).as_posix(), corpus_sha256=c.sha(corpus_path),
        corpus_rows=len(rows), workload_groups=groups, workload_group_count=len(groups),
        source_bindings={name: c.sha(ROOT/name) for name in SOURCES},
        packages={name: importlib.metadata.version(name) for name in ('numpy','xgboost','scikit-learn')},
        models=dict(xgb_rank_pairwise=dict(objective='rank:pairwise',parameters=PARAMETERS),
            xgb_rank_ndcg=dict(objective='rank:ndcg',parameters={**PARAMETERS,'objective':'rank:ndcg'})),
        selection=dict(area_delta_lut4_cap=AREA_CAP,minimum_routed_fmax_mhz=CLOCK_MHZ,
            budgets=list(BUDGETS),seeds=list(SEEDS),baselines=['frequency','merit','calibrated_latency','random']),
        split='Outer whole-workload holdout; all formula-tree families present in target removed from training; ranker query groups are benchmark/build/input contexts.',
        metric='Macro-average workload-level cycle-reduction regret versus the fully measured, area-and-timing-feasible pool oracle.',
        limitations=['Post-hoc model comparison uses consumed data and cannot support a confirmatory claim.',
            'The five model seeds are dependent repetitions; workloads are the independent bootstrap units.',
            'Policy order is static within each candidate pool; measurements are historical costs replayed from the corpus.',
            'Area feasibility is checked only after each simulated measurement; rankers do not predict hardware feasibility.',
            'Operation-tree-family filtering reduces formula overlap but cannot prove semantic independence.'])
    c.seal(output/'protocol.json', protocol)

    selections, rank_snapshots, fold_metadata = [], [], []
    for workload in groups:
        training, test, excluded = speedup_corpus.split(rows, workload)
        c.require(len(training) >= 3, 'Related-family filtering leaves too few training rows: '+workload)
        public = sorted(test, key=lambda row: (row['benchmark'], row['candidate_id']))
        pool_by_benchmark = defaultdict(list)
        for row in public:
            pool_by_benchmark[row['benchmark']].append(row)
        c.require(all(len(pool) >= max(BUDGETS) for pool in pool_by_benchmark.values()),
            'Held-out benchmark pool smaller than maximum query budget: '+workload)
        fold_metadata.append(dict(workload_group=workload, training_rows=len(training),
            training_workload_groups=sorted({row['workload_group'] for row in training}),
            test_rows=len(test), benchmark_contexts=len(pool_by_benchmark),
            excluded_related_candidate_ids=excluded))

        for seed in SEEDS:
            scores_by_policy = {
                policy: _fit_ranker(training, public, objective, seed)
                for policy, objective in OBJECTIVES.items()
            }
            for benchmark, pool in sorted(pool_by_benchmark.items()):
                oracle = max([1.0] + [row['speedup'] for row in pool
                    if budgeted._feasible(row, AREA_CAP, CLOCK_MHZ)])
                for policy in POLICIES:
                    ordered = _ordered(policy, pool, scores_by_policy, seed)
                    for budget in BUDGETS:
                        selections.append(_selection_row(workload, benchmark, policy,
                            seed, budget, ordered, oracle))
                    if policy in OBJECTIVES:
                        rank_snapshots.append(dict(workload_group=workload, benchmark=benchmark,
                            seed=seed, policy=policy, ordered_candidate_ids=[r['candidate_id'] for r in ordered],
                            ordered_scores=[scores_by_policy[policy][r['candidate_id']] for r in ordered]))

    summary = _summarize(selections)
    model_fits = len(groups)*len(SEEDS)*len(OBJECTIVES)
    report = dict(protocol_sha256=c.sha(output/'protocol.json'),folds=fold_metadata,
        selections=selections, **summary,
        candidate_attempts=0, diagnostic_model_fits=model_fits,
        interpretation='All reported model results are cross-validated replays on previously consumed workloads. This is model-selection evidence for the next fresh cohort, not a fresh test.')
    c.seal(output/'rankings.json', rank_snapshots)
    c.seal(output/'report.json', report)
    artifacts = {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()}
    c.seal(output/'manifest.json', artifacts)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(args.corpus, args.output)
    print(json.dumps(dict(workload_groups=len(report['folds']), selections=len(report['selections']),
        diagnostic_model_fits=report['diagnostic_model_fits'], scope='retrospective consumed-data development'), indent=2))


if __name__ == '__main__':
    main()

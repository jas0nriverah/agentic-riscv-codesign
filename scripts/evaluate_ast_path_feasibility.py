#!/usr/bin/env python3
"""One fixed retrospective operator-at-path feasibility challenger.

Uses only the authenticated, consumed 122-row historical corpus. No production
features, trainer, target policy or release is changed. Tiny-regex is not read.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasibility_selection import (AREA_CAPS, MODEL_SETTINGS,
    FeasibilitySelectionPredictor)
from isaforge.features import OPERATIONS, parse_formula
from isaforge.speedup_corpus import family
from scripts import evaluate_feasibility_model_families as screen
from scripts.report_historical_feature_aliasing import (
    CORPUS, CORPUS_MANIFEST_SHA256, CORPUS_SHA256, authenticate, encoded, sha)

OUTPUT = 'reports/2026-10-28-ast-path-feasibility-r1'
PATHS = ((), (0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1))
AST_COLUMNS = tuple('ast_' + ('root' if not path else ''.join(map(str, path)))
                    + '_' + op for path in PATHS for op in OPERATIONS)
MODEL_SEED = 0
AREA_CAP = 64
CLOCK_MHZ = 12.0
BUDGETS = (1, 2, 3)
MODELS = ('existing_feasibility_xgb', 'ast_path_feasibility_xgb')
POLICIES = (*MODELS, 'merit', 'calibrated_latency', 'frequency')
SOURCES = ('scripts/evaluate_ast_path_feasibility.py',
    'scripts/report_historical_feature_aliasing.py',
    'scripts/evaluate_feasibility_model_families.py',
    'isaforge/feasibility_selection.py', 'isaforge/budgeted_selection.py',
    'isaforge/features.py', 'isaforge/model.py', 'isaforge/speedup_corpus.py',
    'isaforge/prospective_selection.py', 'isaforge/codesign.py')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def operator_path_vector(formula):
    """Fixed public syntax vocabulary; no labels or target-derived categories."""
    operators = {}

    def visit(node, path):
        if node.children:
            operators[path] = str(node.value)
            if len(path) < 2:
                for position, child in enumerate(node.children):
                    visit(child, (*path, position))

    visit(parse_formula(formula), ())
    return [int(operators.get(path) == op) for path in PATHS for op in OPERATIONS]


class AstPathFeasibilityPredictor(FeasibilitySelectionPredictor):
    """Same fitted bootstrap recipe/settings, with one fixed feature addition."""
    def _matrix(self, rows, area_cap):
        rows = list(rows)
        base = super()._matrix(rows, area_cap)
        return [values + operator_path_vector(row['formula'])
                for row, values in zip(rows, base)]


def load_corpus():
    source = ROOT / CORPUS
    inventory = authenticate(source, CORPUS_MANIFEST_SHA256)
    require(inventory.get('corpus.json') == CORPUS_SHA256 and
            sha(source / 'corpus.json') == CORPUS_SHA256,
            'Historical corpus binding differs')
    corpus = c.unseal(source / 'corpus.json')
    require(corpus.get('schema') == 'isaforge-consumed-guarded-corpus-v1' and
            corpus.get('successful_labels') == len(corpus.get('rows', [])) == 122 and
            corpus.get('total_candidate_attempts') == 126 and
            len(corpus.get('failed_attempts', [])) == 4 and
            len({row['workload_group'] for row in corpus['rows']}) == 14,
            'Expected 122-label / 126-attempt / 14-workload historical corpus')
    for row in corpus['rows']:
        require(b.validate_outcome(row) and row['candidate_family'] == family(row['formula']),
                'Invalid historical success or expression family')
    for row in corpus['failed_attempts']:
        require(row.get('status') == 'failed' and row.get('measurement_seconds', 0) > 0
                and 'speedup' not in row and 'area_delta_lut4' not in row and
                row['candidate_family'] == family(row['formula']),
                'Failures must retain charged cost without numeric labels')
    return corpus


def folds(corpus):
    rows, failures = corpus['rows'], corpus['failed_attempts']
    result = []
    for group in sorted({row['workload_group'] for row in rows}):
        training, success, failed, excluded = screen._split_with_failures(rows, failures, group)
        require(len(training) >= 3 and len({row['workload_group'] for row in training}) >= 2,
                'Invalid grouped/family training fold: ' + group)
        pool = sorted(success + failed, key=lambda row: (row['benchmark'], row['candidate_id']))
        context_counts = defaultdict(int)
        for row in pool:
            context_counts[row['benchmark']] += 1
        require(all(count >= max(BUDGETS) for count in context_counts.values()),
                'Context pool is smaller than the common maximum budget: ' + group)
        require(not {row['candidate_id'] for row in training} &
                {row['candidate_id'] for row in pool}, 'Training/target ID overlap')
        target_families = {family(row['formula']) for row in pool}
        require(all(row['workload_group'] != group and
                    family(row['formula']) not in target_families for row in training),
                'Target workload or family remained in training')
        result.append((group, training, pool, excluded))
    require(len(result) == 14, 'All fourteen grouped folds are required')
    return result


def probability_metrics(labels, scores):
    from sklearn.metrics import (average_precision_score, brier_score_loss,
                                 log_loss, roc_auc_score)
    require(labels and len(labels) == len(scores), 'Aligned known outcomes required')
    require(all(label in (0, 1) for label in labels) and all(
        math.isfinite(float(score)) and 0 <= score <= 1 for score in scores),
        'Invalid feasibility outcome or score')
    both = len(set(labels)) == 2
    return dict(rows=len(labels), feasible_rows=sum(labels),
        brier=float(brier_score_loss(labels, scores)),
        log_loss=float(log_loss(labels, scores, labels=[0, 1])),
        roc_auc=float(roc_auc_score(labels, scores)) if both else None,
        average_precision=float(average_precision_score(labels, scores)) if both else None,
        ranking_metrics_defined=both)


def score_orders(public, predictions):
    """Only public candidate fields and frozen model scores reach each policy."""
    by_id = {row['candidate_id']: row for row in public}
    require(len(by_id) == len(public) and set(predictions) == set(MODELS),
            'Complete public roster and model set required')
    orders = {}
    for model in MODELS:
        scores = predictions[model]
        require(set(scores) == set(by_id), 'Prediction/public roster differs')
        require(all(math.isfinite(float(value)) and 0 <= value <= 1
                    for value in scores.values()), 'Invalid public model score')
        orders[model] = sorted(by_id, key=lambda identity: (
            -(scores[identity] * max(0.0,
                by_id[identity]['latency_features']['estimated_saved_cycles'] /
                by_id[identity]['latency_features']['baseline_cycles'])),
            -by_id[identity]['latency_features']['estimated_speedup'], identity))
    for policy, key in (('merit', 'saved'), ('frequency', 'runs')):
        orders[policy] = sorted(by_id, key=lambda identity: (-by_id[identity][key], identity))
    orders['calibrated_latency'] = sorted(by_id, key=lambda identity: (
        -by_id[identity]['latency_features']['estimated_speedup'], identity))
    return orders


def simulate(context, public, outcomes, predictions):
    """Freeze all full orders before releasing outcome prefixes for scoring."""
    orders = score_orders(public, predictions)
    by_id = {row['candidate_id']: row for row in outcomes}
    require(set(by_id) == {row['candidate_id'] for row in public},
            'Context outcome/public roster differs')
    successful = {identity: row for identity, row in by_id.items()
                  if row.get('status', 'success') == 'success'}
    failed = {identity: row for identity, row in by_id.items() if row.get('status') == 'failed'}
    require(len(successful) + len(failed) == len(by_id), 'Unknown target status')
    oracle = max([1.0] + [row['speedup'] for row in successful.values()
                           if b._feasible(row, AREA_CAP, CLOCK_MHZ)])
    censored = any(row.get('reference_censored') is True for row in failed.values())
    runs = []
    for policy in POLICIES:
        order = [by_id[identity] for identity in orders[policy]]
        for budget in BUDGETS:
            result = screen._evaluate_group(policy, order, successful, failed,
                oracle, censored, seed=MODEL_SEED, budget=budget)
            runs.append(dict(context=context,
                workload_group=outcomes[0]['workload_group'], **result))
    return orders, runs


def summarize(corpus, protocol, frozen, costs):
    all_rows = {row['candidate_id']: row for row in
                corpus['rows'] + corpus['failed_attempts']}
    success = {row['candidate_id']: row for row in corpus['rows']}
    fold_metrics, runs, fold_results = [], [], []
    expected_folds = folds(corpus)
    require(len(frozen) == len(expected_folds), 'Frozen fold count differs')
    for record, (group, training, pool, excluded) in zip(frozen, expected_folds):
        require(record['workload_group'] == group and record['training_ids'] ==
                sorted(row['candidate_id'] for row in training) and
                record['excluded_related_historical_ids'] == sorted(excluded) and
                record['target_ids'] == [row['candidate_id'] for row in pool],
                'Frozen group/family split differs')
        predictions = record['predictions']
        require(set(predictions) == set(MODELS), 'Frozen model set differs')
        known = [row for row in pool if row['candidate_id'] in success]
        metrics = {}
        for model in MODELS:
            values = predictions[model]
            require(set(values) == set(record['target_ids']), 'Prediction roster differs')
            metrics[model] = probability_metrics(
                [int(b._feasible(row, AREA_CAP, CLOCK_MHZ)) for row in known],
                [values[row['candidate_id']] for row in known])
            fold_metrics.append(dict(workload_group=group, model=model, **metrics[model]))
        contexts = sorted({row['benchmark'] for row in pool})
        for context in contexts:
            context_rows = [row for row in pool if row['benchmark'] == context]
            context_ids = {row['candidate_id'] for row in context_rows}
            public = [screen._public(row) for row in context_rows]
            _, context_runs = simulate(context, public, context_rows,
                {name: {identity: value for identity, value in predictions[name].items()
                        if identity in context_ids} for name in MODELS})
            runs += context_runs
        fold_results.append(dict(workload_group=group, training_rows=len(training),
            training_groups=len({row['workload_group'] for row in training}),
            target_successes=len(known), target_failures=len(pool)-len(known),
            excluded_related_historical_rows=len(excluded), metrics=metrics))
    pooled = {}
    for model in MODELS:
        predictions = {identity: value for record in frozen
                       for identity, value in record['predictions'][model].items()
                       if identity in success}
        require(set(predictions) == set(success), 'Every historical success needs one OOF score')
        ids = sorted(success)
        pooled[model] = probability_metrics(
            [int(b._feasible(success[identity], AREA_CAP, CLOCK_MHZ)) for identity in ids],
            [predictions[identity] for identity in ids])
    grouped = []
    for group in sorted({row['workload_group'] for row in runs}):
        for policy in POLICIES:
            for budget in BUDGETS:
                points = [row for row in runs if row['workload_group'] == group and
                          row['policy'] == policy and row['budget'] == budget]
                require(points, 'Missing grouped selection prefix')
                uncensored = [row for row in points if row['cycle_reduction_regret'] is not None]
                grouped.append(dict(workload_group=group, policy=policy, budget=budget,
                    contexts=len(points), mean_cycle_reduction=statistics.mean(
                        row['verified_cycle_reduction'] for row in points),
                    mean_regret=(statistics.mean(row['cycle_reduction_regret'] for row in uncensored)
                                 if uncensored else None),
                    oracle_complete=bool(uncensored),
                    mean_replayed_measurement_seconds=statistics.mean(
                        row['measurement_seconds'] for row in points),
                    mean_failed_queries=statistics.mean(
                        row['failed_or_unresolved_attempts'] for row in points),
                    mean_infeasible_successful_queries=statistics.mean(
                        row['infeasible_successful_attempts'] for row in points)))
    macro = []
    for policy in POLICIES:
        for budget in BUDGETS:
            points = [row for row in grouped if row['policy'] == policy and row['budget'] == budget]
            complete = [row for row in points if row['mean_regret'] is not None]
            macro.append(dict(policy=policy, budget=budget,
                workload_groups=len(points), oracle_complete_groups=len(complete),
                mean_cycle_reduction=statistics.mean(row['mean_cycle_reduction'] for row in points),
                mean_regret=statistics.mean(row['mean_regret'] for row in complete),
                mean_replayed_measurement_seconds=statistics.mean(
                    row['mean_replayed_measurement_seconds'] for row in points)))
    pairs = []
    indexed = {(row['workload_group'], row['policy'], row['budget']): row for row in grouped}
    for budget in BUDGETS:
        for baseline in ('existing_feasibility_xgb', 'merit', 'calibrated_latency'):
            values = {}
            for group in sorted({row['workload_group'] for row in grouped}):
                before = indexed[(group, baseline, budget)]['mean_regret']
                after = indexed[(group, 'ast_path_feasibility_xgb', budget)]['mean_regret']
                if before is not None and after is not None:
                    values[group] = before - after
            pairs.append(dict(budget=budget, baseline=baseline,
                challenger='ast_path_feasibility_xgb',
                **screen._paired_group_bootstrap(values)))
    require(len(costs) == 14 and all(record['workload_group'] == expected[0]
        and set(record['models']) == set(MODELS)
        and all(math.isfinite(value) and value >= 0
                for timers in record['models'].values() for value in timers.values())
        for record, expected in zip(costs, expected_folds)), 'Invalid fit/prediction costs')
    return dict(schema='isaforge-fixed-ast-path-feasibility-development-v1',
        scope=protocol['scope'], source=protocol['source'],
        fixed_feature_addition=protocol['fixed_feature_addition'],
        successful_rows=122, charged_failures=4, workload_groups=14,
        model_fits=14 * 2 * MODEL_SETTINGS['ensemble_size'],
        pooled_probability_metrics=pooled, fold_probability_metrics=fold_metrics,
        fold_results=fold_results, selection_runs=runs,
        workload_selection_metrics=grouped, macro_selection_metrics=macro,
        paired_workload_regret_contrasts=pairs,
        fit_prediction_costs=costs,
        total_fit_prediction_seconds={model: {
            key: sum(record['models'][model][key] for record in costs)
            for key in ('fit_seconds', 'prediction_seconds')} for model in MODELS},
        limitations=protocol['limitations'])


def markdown(report):
    lines = ['# Fixed AST-path feasibility challenger', '', report['scope'], '',
        'One fixed addition preserves the current numeric features, cap-conditioned '
        '20-member XGBoost bootstrap recipe and seed 0. It adds a predetermined '
        '**7 AST paths × 24 operators = 168 binary columns**: root, left/right '
        'children and four grandchild positions. Leaf values are not added. '
        'No hyperparameters or decision thresholds are tuned.', '',
        'All fourteen folds hold out the entire workload and remove every target '
        'operation-tree family, including families of failed target attempts. '
        'The four historical failures consume selection budgets and recorded time, '
        'but never receive numeric feasibility labels. Candidate rows and repeated '
        'contexts do not increase the number of independent workloads.', '',
        '## Out-of-fold hardware-feasibility scores', '',
        '| Model | Pooled Brier ↓ | Log loss ↓ | ROC AUC ↑ | Average precision ↑ |',
        '|---|---:|---:|---:|---:|']
    for model in MODELS:
        metric = report['pooled_probability_metrics'][model]
        lines.append(f"| {model} | {metric['brier']:.6f} | {metric['log_loss']:.6f} | {metric['roc_auc']:.6f} | {metric['average_precision']:.6f} |")
    lines += ['', 'Scores remain uncalibrated. Brier/log loss are proper-score diagnostics; '
        'AUC/AP are null in single-class workload folds. Pooled metrics are '
        'candidate-weighted and secondary to workload-level selection outcomes.', '',
        '## Matched selection outcomes', '',
        'Each policy orders the same context pool using public features and frozen '
        'OOF predictions before outcome prefixes are scored. Model order is '
        '`feasibility score × nonnegative analytic fractional cycle savings`, '
        'with the existing latency/ID tie breaks. Budgets are 1–3 attempted '
        'evaluations per context. The table averages contexts within workload '
        'before averaging workloads; oracle regret uses twelve complete groups.', '',
        '| Policy | Budget | Verified cycle reduction | Oracle regret | Replayed query time (s) |',
        '|---|---:|---:|---:|---:|']
    for row in report['macro_selection_metrics']:
        lines.append(f"| {row['policy']} | {row['budget']} | {100*row['mean_cycle_reduction']:.4f}% | {100*row['mean_regret']:.4f}% | {row['mean_replayed_measurement_seconds']:.2f} |")
    lines += ['', 'These times sum archived candidate evaluation costs along counterfactual '
        'orders. No hardware evaluation or past time saving occurs in this replay. '
        'UD and G.723 have censored full-pool oracles; their regret remains null.', '',
        '## Challenger versus existing feasibility model', '',
        'Positive regret difference favors the AST-path challenger. Intervals '
        'resample the twelve complete workload groups; they describe consumed '
        'development data and do not establish confirmatory significance.', '',
        '| Budget | Mean regret advantage (percentage points) | 95% workload interval | Wins / ties / losses |',
        '|---|---:|---:|---:|']
    for row in report['paired_workload_regret_contrasts']:
        if row['baseline'] == 'existing_feasibility_xgb':
            lines.append(f"| {row['budget']} | {100*row['mean']:+.4f} | [{100*row['lower_95']:+.4f}, {100*row['upper_95']:+.4f}] | {row['wins']} / {row['ties']} / {row['losses']} |")
    lines += ['', '## Fitting cost and decision', '',
        'Fit and prediction times are measured separately for each fold/model '
        'in `costs.json`; they are not added to archived hardware timers.', '']
    for model in MODELS:
        value = report['total_fit_prediction_seconds'][model]
        lines.append(f"- {model}: {value['fit_seconds']:.4f} s fitting; {value['prediction_seconds']:.4f} s prediction across fourteen folds.")
    lines += ['', '**No model is promoted.** This single fixed feature test is '
        'retrospective consumed-data development. The frozen production model and '
        'all target protocols remain unchanged. Tiny-regex outcomes are not read. '
        'Inspect per-workload selection/regret and negative results before '
        'considering an independently frozen prospective challenger.', '',
        'The current 12-MHz floor does not create difficult timing-boundary '
        'examples; this is primarily an area-feasibility study. Operator paths '
        'represent syntax and do not encode complete integrated hardware sharing '
        'or placement/routing behavior. No selection or calibration generality '
        'is inferred from improving a pooled metric.', '',
        '```sh', '../work/audit-venv/bin/python scripts/evaluate_ast_path_feasibility.py run',
        '../work/audit-venv/bin/python scripts/evaluate_ast_path_feasibility.py verify --root reports/2026-10-28-ast-path-feasibility-r1',
        '```', '', 'The verifier authenticates the historical corpus and frozen '
        'protocol/predictions/costs, then reproduces `report.json` and this '
        'README byte-for-byte. It performs no refit; recorded host timers remain '
        'intact. A fresh `run` refits the fixed recipes, produces fresh timers '
        'and requires a new output directory.', '']
    return '\n'.join(lines).encode()


def seal(root):
    manifest = {path.relative_to(root).as_posix(): sha(path)
                for path in sorted(root.rglob('*')) if path.is_file()
                and path.name not in ('manifest.json', 'manifest.json.sha256')}
    (root / 'manifest.json').write_bytes(encoded(manifest))
    (root / 'manifest.json.sha256').write_text(sha(root / 'manifest.json') + '\n')


def run(output):
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(ROOT) and
            not output.is_relative_to((ROOT / 'results').resolve()),
            'Fresh repository-local report output outside sealed results required')
    corpus = load_corpus()
    split = folds(corpus)
    protocol = dict(schema='isaforge-fixed-ast-path-feasibility-protocol-v1',
        scope='Retrospective consumed-data development only; no independent confirmation or model promotion.',
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        source=dict(corpus=CORPUS + '/corpus.json', corpus_sha256=CORPUS_SHA256,
                    manifest_sha256=CORPUS_MANIFEST_SHA256),
        source_bindings={name: sha(ROOT / name) for name in SOURCES},
        packages={name: importlib.metadata.version(name)
                  for name in ('numpy', 'scipy', 'scikit-learn', 'xgboost')},
        fixed_feature_addition=dict(paths=[list(path) for path in PATHS],
            operators=list(OPERATIONS), columns=list(AST_COLUMNS),
            base_columns=list(b.STRUCTURAL_COLUMNS),
            semantics='One-hot operator at fixed ordered AST path; absent operators/leaf positions are zero; no literal or input-ID features'),
        existing_settings=MODEL_SETTINGS, area_caps=list(AREA_CAPS),
        primary_area_cap_lut4=AREA_CAP, minimum_fmax_mhz=CLOCK_MHZ,
        model_seed=MODEL_SEED, policies=list(POLICIES), budgets=list(BUDGETS),
        split='Whole workload held out; all families in the complete target pool, including failed attempts, excluded from training',
        label='Verified successful hardware outcome: device fit, added LUT4 <= 64, minimum routed Fmax >= 12 MHz',
        model_order='Feasibility score * nonnegative public analytic fractional cycle savings; descending analytic speedup then candidate ID break ties',
        limitations=['Consumed historical data; all fourteen workloads were used for prior development.',
            'No target labels from tiny-regex are loaded; no new native jobs, LLM calls or candidate outcomes.',
            'Bootstrap outputs are uncalibrated scores and estimator disagreement is not confidence.',
            'Candidates/contexts are correlated; the independent unit is the workload group.',
            'Censored full-pool oracles keep null regret; all four failures consume query budget and time.',
            'Timing floor is weakly discriminating; useful feasibility variation is predominantly area.',
            'Exact report verification reuses frozen predictions and recorded costs; it does not rerun model fitting.'])
    output.mkdir(parents=True)
    (output / 'protocol.json').write_bytes(encoded(protocol))
    frozen, costs = [], []
    for group, training, pool, excluded in split:
        public = [screen._public(row) for row in pool]
        require(all(set(row) == set(screen._public(pool[index]))
                    for index, row in enumerate(public)), 'Strict public projection required')
        predictions, timers = {}, {}
        for name, cls in zip(MODELS, (FeasibilitySelectionPredictor, AstPathFeasibilityPredictor)):
            model = cls(seed=MODEL_SEED)
            began = time.monotonic()
            model.fit(training)
            fit_seconds = time.monotonic() - began
            began = time.monotonic()
            scored = model.predict(public, area_cap=AREA_CAP)
            prediction_seconds = time.monotonic() - began
            predictions[name] = {row['candidate_id']: row['feasibility_score_mean'] for row in scored}
            timers[name] = dict(fit_seconds=fit_seconds, prediction_seconds=prediction_seconds)
        frozen.append(dict(workload_group=group,
            training_ids=sorted(row['candidate_id'] for row in training),
            excluded_related_historical_ids=sorted(excluded),
            target_ids=[row['candidate_id'] for row in pool], predictions=predictions))
        costs.append(dict(workload_group=group, models=timers))
        print(group + ': existing and fixed AST challenger fitted', flush=True)
    (output / 'predictions.json').write_bytes(encoded(frozen))
    (output / 'costs.json').write_bytes(encoded(costs))
    report = summarize(corpus, protocol, frozen, costs)
    (output / 'report.json').write_bytes(encoded(report))
    (output / 'README.md').write_bytes(markdown(report))
    seal(output)
    return report


def verify(root):
    root = Path(root).resolve()
    expected_manifest = (root / 'manifest.json.sha256').read_text().strip()
    authenticate(root, expected_manifest)
    require({path.name for path in root.iterdir()} == {'protocol.json', 'predictions.json',
        'costs.json', 'report.json', 'README.md', 'manifest.json', 'manifest.json.sha256'},
        'Unexpected experiment inventory')
    protocol = json.loads((root / 'protocol.json').read_text())
    require(protocol['source_bindings'] == {name: sha(ROOT / name) for name in SOURCES},
            'Diagnostic/training source bindings differ')
    require(protocol['packages'] == {name: importlib.metadata.version(name)
            for name in ('numpy', 'scipy', 'scikit-learn', 'xgboost')},
            'Diagnostic dependency versions differ')
    require(protocol['fixed_feature_addition']['columns'] == list(AST_COLUMNS) and
            protocol['existing_settings'] == MODEL_SETTINGS and protocol['model_seed'] == MODEL_SEED
            and protocol['policies'] == list(POLICIES) and protocol['budgets'] == list(BUDGETS),
            'Fixed challenger protocol differs')
    report = summarize(load_corpus(), protocol,
        json.loads((root / 'predictions.json').read_text()),
        json.loads((root / 'costs.json').read_text()))
    require((root / 'report.json').read_bytes() == encoded(report) and
            (root / 'README.md').read_bytes() == markdown(report),
            'Exact derived report reproduction differs')
    print('Verified historical corpus, source/dependency bindings and exact derived report; no refits.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--root', type=Path, default=ROOT / OUTPUT)
    args = parser.parse_args(argv)
    if args.command == 'verify':
        verify(args.root)
    else:
        report = run(args.root)
        print(json.dumps(report['pooled_probability_metrics'], indent=2))


if __name__ == '__main__':
    main()

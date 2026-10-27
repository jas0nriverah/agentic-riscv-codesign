"""Retrospective, failure-aware screen of small-data feasibility selectors.

The measured cycle-benefit label is exactly reproduced by the independently
calibrated latency estimate for the current 122-row corpus. This screen holds
out whole workloads and related formula families, then tests models on the
remaining difficult decision: which candidate is likely to fit the +64 LUT4 /
12 MHz constraint before paying for hardware evaluation. It uses consumed
labels and is strictly exploratory, not a confirmatory model comparison.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.metadata
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as budgeted, codesign as c
from isaforge import factorized_selection_experiment as factorized
from isaforge import speedup_corpus
from isaforge.model import SpeedupPredictor
from isaforge.ranking import SpeedupRanker
from scripts.reproduce_guarded_sha256 import _manifest

SOURCE = "scripts/evaluate_feasibility_model_families.py"
SOURCES = (
    SOURCE,
    "isaforge/budgeted_selection.py",
    "isaforge/factorized_selection_experiment.py",
    "isaforge/feasibility_selection.py",
    "isaforge/model.py",
    "isaforge/ranking.py",
    "isaforge/features.py",
    "isaforge/speedup_corpus.py",
    "isaforge/codesign.py",
    "isaforge/prospective_selection.py",
    "scripts/reproduce_guarded_sha256.py",
)
AREA_CAP = 64
CLOCK_MHZ = 12.0
MODEL_SEED = 0
POLICY_SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
POLICIES = (
    "frequency",
    "merit",
    "calibrated_latency",
    "latency_cost_heuristic",
    "random",
    "xgb_speedup_regression",
    "xgb_pairwise_ranker",
    "factorized_feasibility_xgb",
    "xgb_feasibility_64",
    "group_bootstrap_xgb_feasibility_64",
    "logistic_feasibility_64",
    "random_forest_feasibility_64",
    "extra_trees_feasibility_64",
)
FEASIBILITY_POLICIES = frozenset(POLICIES[7:])
LEARNED_POLICIES = FEASIBILITY_POLICIES | frozenset({
    "xgb_speedup_regression", "xgb_pairwise_ranker"
})


def _public(row):
    """Strict public projection; never pass target outcome fields to predictors."""
    from isaforge.prospective_selection import PUBLIC_KEYS

    return {key: row[key] for key in PUBLIC_KEYS}


def _split_with_failures(successes, failures, held_out):
    """Hold out a whole group and remove its formula families from training."""
    test_success = [row for row in successes if row["workload_group"] == held_out]
    test_failures = [row for row in failures if row["workload_group"] == held_out]
    c.require(test_success, "Unknown or empty held-out group: " + held_out)
    target_families = {speedup_corpus.family(row["formula"])
                       for row in test_success + test_failures}
    training = [row for row in successes
                if row["workload_group"] != held_out
                and speedup_corpus.family(row["formula"]) not in target_families]
    excluded = [row["candidate_id"] for row in successes
                if row["workload_group"] != held_out
                and speedup_corpus.family(row["formula"]) in target_families]
    test_pool = test_success + test_failures
    c.require(len({row["candidate_id"] for row in test_pool}) == len(test_pool),
              "Duplicate test candidate identity")
    c.require(all(row["workload_group"] == held_out for row in test_pool),
              "Held-out pool crosses workload groups")
    c.require(all(speedup_corpus.family(row["formula"]) not in target_families
                  for row in training), "Related target formula remains in training")
    return training, test_success, test_failures, excluded


def _training_matrix(training):
    """Common public features and train-only area-per-operation proxy."""
    import numpy as np

    public = [_public(row) for row in training]
    base = np.asarray(budgeted.structural_matrix(public), dtype=float)
    area_per_op = statistics.median(
        row["area_delta_lut4"] / row["tree_op_count"] for row in training
    )
    c.require(math.isfinite(area_per_op) and area_per_op > 0,
              "Training area proxy must be positive")
    return public, base, area_per_op


def _feasible(row):
    return budgeted._feasible(row, AREA_CAP, CLOCK_MHZ)


def _classifier_scores(training, test_public, seed=MODEL_SEED):
    """Fit fixed feasibility learners; unknown failed attempts never train."""
    import numpy as np
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    public_train, x_train_base, area_per_op = _training_matrix(training)
    x_test_base = np.asarray(budgeted.structural_matrix(test_public), dtype=float)
    def append_budget_feature(matrix, rows):
        budget = np.asarray([
            AREA_CAP / (area_per_op * row["tree_op_count"]) for row in rows
        ], dtype=float).reshape(-1, 1)
        return np.concatenate([matrix, budget], axis=1)

    x_train = append_budget_feature(x_train_base, public_train)
    x_test = append_budget_feature(x_test_base, test_public)
    labels = np.asarray([int(_feasible(row)) for row in training], dtype=int)
    c.require(len(labels) == len(training) and len(labels) > 0,
              "Successful training labels required")

    if len(set(labels.tolist())) == 1:
        constant = float(labels[0])
        return {name: [constant] * len(test_public) for name in (
            "xgb_feasibility_64", "group_bootstrap_xgb_feasibility_64",
            "logistic_feasibility_64", "random_forest_feasibility_64",
            "extra_trees_feasibility_64")}

    # Cap-specific XGBoost is deliberately fixed to the existing small-tree
    # settings; no target-fold tuning or threshold selection is performed.
    xgb = XGBClassifier(objective="binary:logistic", n_estimators=80,
        max_depth=2, learning_rate=.05, min_child_weight=1, reg_lambda=1.0,
        subsample=1.0, colsample_bytree=1.0, tree_method="hist", n_jobs=1,
        random_state=seed, verbosity=0)
    xgb.fit(x_train, labels)
    scores = {"xgb_feasibility_64": xgb.predict_proba(x_test)[:, 1].tolist()}

    # Group bootstrap resamples independent workload sources, not correlated
    # candidates. This is a targeted alternative to candidate-row bootstrap.
    groups = sorted({row["workload_group"] for row in training})
    if len(groups) >= 2:
        rng = random.Random(seed)
        members = []
        for member in range(20):
            sampled = [groups[rng.randrange(len(groups))] for _ in groups]
            indices = [index for group in sampled for index, row in enumerate(training)
                       if row["workload_group"] == group]
            member_labels = labels[indices]
            if len(set(member_labels.tolist())) == 1:
                members.append(np.full(len(test_public), float(member_labels[0])))
                continue
            model = XGBClassifier(objective="binary:logistic", n_estimators=80,
                max_depth=2, learning_rate=.05, min_child_weight=1, reg_lambda=1.0,
                subsample=1.0, colsample_bytree=1.0, tree_method="hist", n_jobs=1,
                random_state=seed + member + 1, verbosity=0)
            model.fit(x_train[indices], labels[indices])
            members.append(model.predict_proba(x_test)[:, 1])
        scores["group_bootstrap_xgb_feasibility_64"] = np.mean(members, axis=0).tolist()
    else:
        scores["group_bootstrap_xgb_feasibility_64"] = scores["xgb_feasibility_64"]

    logistic = make_pipeline(StandardScaler(), LogisticRegression(
        C=.1, solver="lbfgs", max_iter=5000, random_state=seed))
    logistic.fit(x_train, labels)
    scores["logistic_feasibility_64"] = logistic.predict_proba(x_test)[:, 1].tolist()

    forest = RandomForestClassifier(n_estimators=300, max_features=.8,
        min_samples_leaf=2, random_state=seed, n_jobs=1)
    forest.fit(x_train, labels)
    scores["random_forest_feasibility_64"] = forest.predict_proba(x_test)[:, 1].tolist()

    extra = ExtraTreesClassifier(n_estimators=300, max_features=.8,
        min_samples_leaf=2, random_state=seed, n_jobs=1)
    extra.fit(x_train, labels)
    scores["extra_trees_feasibility_64"] = extra.predict_proba(x_test)[:, 1].tolist()

    for name, values in scores.items():
        c.require(len(values) == len(test_public) and all(
            math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in values),
            "Invalid feasibility scores from " + name)
    return scores


def _prediction_orders(training, test_pool, seed=MODEL_SEED):
    """Create all scores using only training labels and strict target public rows."""
    public = [_public(row) for row in test_pool]
    successes = [row for row in test_pool if row.get("status", "success") == "success"]
    failure_by_id = {row["candidate_id"]: row for row in test_pool if row.get("status") == "failed"}
    c.require(len(successes) + len(failure_by_id) == len(test_pool), "Invalid test statuses")

    orders = {}
    feasibility_predictions = {}
    orders["frequency"] = sorted(test_pool,
        key=lambda row: (-row["runs"], row["candidate_id"]))
    orders["merit"] = sorted(test_pool,
        key=lambda row: (-row["saved"], row["candidate_id"]))
    orders["calibrated_latency"] = sorted(test_pool,
        key=lambda row: (-row["latency_features"]["estimated_speedup"], row["candidate_id"]))
    orders["random"] = list(test_pool)

    area_per_op = statistics.median(
        row["area_delta_lut4"] / row["tree_op_count"] for row in training
    )
    simple_clock = min(row["routed_fmax_min_mhz"] for row in training)
    orders["latency_cost_heuristic"] = sorted(test_pool,
        key=lambda row: (
            -int(area_per_op * row["tree_op_count"] <= AREA_CAP and simple_clock >= CLOCK_MHZ),
            -max(0.0, row["latency_features"]["estimated_speedup"] - 1.0)
              / max(1.0, area_per_op * row["tree_op_count"]),
            -row["latency_features"]["estimated_speedup"], row["candidate_id"]))

    speedup_public = [row for row in public]
    xgb_reg = SpeedupPredictor(seed=seed).fit(training).predict(speedup_public)
    reg_scores = {item["candidate_id"]: item["mean"] for item in xgb_reg}
    orders["xgb_speedup_regression"] = sorted(test_pool,
        key=lambda row: (-reg_scores[row["candidate_id"]], row["candidate_id"]))

    rank_model = SpeedupRanker(seed=seed).fit(training)
    rank_scores = {item["candidate_id"]: item["rank_score"]
                   for item in rank_model.predict(speedup_public)}
    orders["xgb_pairwise_ranker"] = sorted(test_pool,
        key=lambda row: (-rank_scores[row["candidate_id"]], row["candidate_id"]))

    started = time.monotonic()
    classifier_scores = _classifier_scores(training, public, seed=seed)
    fit_and_prediction_seconds = time.monotonic() - started

    # Reproduce the current cap-conditioned factorized model as the status quo.
    started = time.monotonic()
    model = factorized.FeasibilitySelectionPredictor(seed=seed).fit(training)
    factorized_predictions = model.predict(public, area_cap=AREA_CAP)
    factorized_seconds = time.monotonic() - started
    existing = {row["candidate_id"]: row["decision_score"] for row in factorized_predictions}
    feasibility_predictions["factorized_feasibility_xgb"] = {
        row["candidate_id"]: row["feasibility_score_mean"]
        for row in factorized_predictions
    }
    orders["factorized_feasibility_xgb"] = sorted(test_pool,
        key=lambda row: (-existing[row["candidate_id"]],
                         -row["latency_features"]["estimated_speedup"], row["candidate_id"]))

    for name in classifier_scores:
        p = {row["candidate_id"]: float(score)
             for row, score in zip(public, classifier_scores[name])}
        feasibility_predictions[name] = p
        orders[name] = sorted(test_pool,
            key=lambda row: (
                -(p[row["candidate_id"]] * max(0.0,
                    row["latency_features"]["estimated_cycle_reduction"])),
                -row["latency_features"]["estimated_speedup"], row["candidate_id"]))

    # Probability-only baseline: test whether feature learners improve on the
    # source-held-out feasibility prior before interpreting their Brier scores.
    training_prevalence = statistics.mean(int(_feasible(row)) for row in training)
    feasibility_predictions["training_feasibility_prevalence"] = {
        row["candidate_id"]: training_prevalence for row in public
    }

    c.require(set(orders) == set(POLICIES),
              "Incomplete policy order set: missing " + repr(sorted(set(POLICIES)-set(orders)))
              + "; extra " + repr(sorted(set(orders)-set(POLICIES))))
    return orders, feasibility_predictions, dict(
        classifier_fit_and_prediction_seconds=fit_and_prediction_seconds,
        factorized_fit_and_prediction_seconds=factorized_seconds)


def _best_feasible(attempts):
    feasible = [row for row in attempts if row.get("status", "success") == "success"
                and _feasible(row) and row["speedup"] > 1.0]
    return min(feasible, key=lambda row: (-row["speedup"],
        row["area_delta_lut4"], row["candidate_id"])) if feasible else None


def _evaluate_group(policy, order, success_by_id, failure_by_id, oracle, reference_censored,
                    *, seed, budget):
    chosen = order[:budget]
    observed = [success_by_id[row["candidate_id"]] for row in chosen
                if row["candidate_id"] in success_by_id]
    best = _best_feasible(observed)
    speedup = best["speedup"] if best else 1.0
    cycle_reduction = 1.0 - 1.0 / speedup
    oracle_cycle_reduction = 1.0 - 1.0 / oracle
    return dict(
        policy=policy,
        seed=seed,
        budget=budget,
        attempted_candidate_ids=[row["candidate_id"] for row in chosen],
        selected_candidate_id=best["candidate_id"] if best else None,
        best_speedup=speedup,
        verified_cycle_reduction=cycle_reduction,
        best_verified_reference_speedup=oracle,
        best_verified_reference_cycle_reduction=oracle_cycle_reduction,
        cycle_reduction_regret=None if reference_censored else max(
            0.0, oracle_cycle_reduction-cycle_reduction),
        reference_censored=reference_censored,
        reference_kind="lower-bound best-verified reference" if reference_censored
                       else "complete verified candidate-pool oracle",
        measured_success_count=len(observed),
        failed_or_unresolved_attempts=sum(row["candidate_id"] in failure_by_id for row in chosen),
        infeasible_successful_attempts=sum(not _feasible(row) for row in observed),
        measurement_seconds=sum(row["measurement_seconds"] for row in chosen),
    )


def _percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = fraction * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _paired_group_bootstrap(by_group, *, seed=20261026, draws=10000):
    groups = sorted(by_group)
    if not groups:
        return dict(mean=None, lower_95=None, upper_95=None, workload_groups=0)
    differences = [by_group[group] for group in groups]
    rng = random.Random(seed)
    replicates = [statistics.mean(
        differences[rng.randrange(len(differences))] for _ in differences
    ) for _ in range(draws)]
    return dict(mean=statistics.mean(differences), lower_95=_percentile(replicates, .025),
        upper_95=_percentile(replicates, .975), workload_groups=len(groups),
        wins=sum(value > 0 for value in differences),
        ties=sum(value == 0 for value in differences),
        losses=sum(value < 0 for value in differences),
        interpretation="Positive means the challenger has lower regret.")


def _summarize(runs):
    # Seeds are averaged within an independent workload before macro aggregation.
    group_rows = defaultdict(list)
    for row in runs:
        group_rows[(row["workload_group"], row["policy"], row["budget"])].append(row)
    summaries = []
    for (workload, policy, budget), rows in sorted(group_rows.items()):
        uncensored = [row for row in rows if not row["reference_censored"]]
        summaries.append(dict(
            workload_group=workload, policy=policy, budget=budget,
            mean_cycle_reduction=statistics.mean(row["verified_cycle_reduction"] for row in rows),
            mean_best_speedup=statistics.mean(row["best_speedup"] for row in rows),
            mean_regret=(statistics.mean(row["cycle_reduction_regret"] for row in uncensored)
                         if uncensored else None),
            reference_censored=not bool(uncensored),
            mean_measurement_seconds=statistics.mean(row["measurement_seconds"] for row in rows),
            mean_failed_or_unresolved_attempts=statistics.mean(
                row["failed_or_unresolved_attempts"] for row in rows),
            mean_infeasible_successful_attempts=statistics.mean(
                row["infeasible_successful_attempts"] for row in rows),
            best_verified_reference_hits=(statistics.mean(
                row["best_speedup"] == row["best_verified_reference_speedup"] for row in rows)),
            dependent_policy_seeds=len(rows),
        ))

    macro = []
    indexed = {(row["workload_group"], row["policy"], row["budget"]): row
               for row in summaries}
    for policy in POLICIES:
        for budget in BUDGETS:
            pool = [row for row in summaries if row["policy"] == policy
                    and row["budget"] == budget]
            complete = [row for row in pool if row["mean_regret"] is not None]
            macro.append(dict(
                policy=policy, budget=budget,
                workload_groups=len(pool),
                uncensored_oracle_workload_groups=len(complete),
                mean_verified_cycle_reduction=statistics.mean(
                    row["mean_cycle_reduction"] for row in pool),
                mean_cycle_reduction_regret=(statistics.mean(
                    row["mean_regret"] for row in complete) if complete else None),
                mean_measurement_seconds=statistics.mean(
                    row["mean_measurement_seconds"] for row in pool),
                mean_failed_or_unresolved_attempts=statistics.mean(
                    row["mean_failed_or_unresolved_attempts"] for row in pool),
                mean_infeasible_successful_attempts=statistics.mean(
                    row["mean_infeasible_successful_attempts"] for row in pool),
                best_verified_reference_hit_rate=statistics.mean(
                    row["best_verified_reference_hits"] for row in pool),
            ))

    contrasts = []
    for budget in BUDGETS:
        for baseline in ("merit", "calibrated_latency", "latency_cost_heuristic",
                         "factorized_feasibility_xgb"):
            for challenger in LEARNED_POLICIES:
                shared = sorted(
                    group for group in {key[0] for key in indexed}
                    if (group, baseline, budget) in indexed
                    and (group, challenger, budget) in indexed
                    and indexed[(group, baseline, budget)]["mean_regret"] is not None
                    and indexed[(group, challenger, budget)]["mean_regret"] is not None
                )
                differences = {group: indexed[(group, baseline, budget)]["mean_regret"]
                    - indexed[(group, challenger, budget)]["mean_regret"] for group in shared}
                contrasts.append(dict(budget=budget, baseline=baseline,
                    challenger=challenger, **_paired_group_bootstrap(differences)))
    return dict(group_summary=summaries, macro_summary=macro, paired_contrasts=contrasts)


def evaluate(corpus_path, output):
    corpus_path = Path(corpus_path).resolve()
    output = Path(output).resolve()
    c.require(corpus_path.is_relative_to(ROOT) and output.is_relative_to(ROOT),
              "Repository-local corpus and output required")
    c.require(not output.exists(), "Use a fresh exploratory output directory")
    _manifest(corpus_path.parent)
    corpus = c.unseal(corpus_path)
    c.require(corpus.get("schema") == "isaforge-consumed-guarded-corpus-v1"
              and len(corpus.get("rows", [])) == 122
              and corpus.get("successful_labels") == 122
              and corpus.get("total_candidate_attempts") == 126
              and len(corpus.get("failed_attempts", [])) == 4,
              "Authenticated 122-label/126-attempt consumed corpus required")
    successes, failures = corpus["rows"], corpus["failed_attempts"]
    c.require(set(corpus.get("reference_censored_candidates", [])) == {
        row["candidate_id"] for row in failures if row.get("reference_censored") is True
    }, "Censored candidate inventory differs from charged failures")
    for row in successes:
        c.require(budgeted.validate_outcome(row), "Invalid successful training/test row")
        c.require(row["candidate_family"] == speedup_corpus.family(row["formula"]),
                  "Successful row candidate-family annotation differs")
    for row in failures:
        c.require(row.get("status") == "failed" and row.get("candidate_id")
                  and row.get("measurement_seconds", 0) > 0,
                  "Failed attempts must retain identity and charged cost")
        c.require("speedup" not in row and "area_delta_lut4" not in row,
                  "Failed attempts must not become fabricated negative labels")
        c.require(row["candidate_family"] == speedup_corpus.family(row["formula"]),
                  "Failed row candidate-family annotation differs")

    groups = sorted({row["workload_group"] for row in successes})
    folds = []
    for group in groups:
        training, test_success, test_failures, excluded = _split_with_failures(
            successes, failures, group)
        c.require(len(training) >= 3 and len({row["workload_group"] for row in training}) >= 2,
                  "Insufficient grouped training after target-family exclusion: " + group)
        test_pool = sorted(test_success + test_failures,
            key=lambda row: (row["benchmark"], row["candidate_id"]))
        pool_by_benchmark = defaultdict(list)
        for row in test_pool:
            pool_by_benchmark[row["benchmark"]].append(row)
        c.require(all(len(pool) >= max(BUDGETS) for pool in pool_by_benchmark.values()),
                  "Held-out full candidate pool smaller than maximum budget: " + group)
        folds.append((group, training, test_success, test_failures, excluded, pool_by_benchmark))

    output.mkdir(parents=True)
    protocol = dict(
        schema="isaforge-feasibility-model-family-screen-v1",
        scope="retrospective consumed-data model development; no independent confirmation",
        corpus_path=corpus_path.relative_to(ROOT).as_posix(),
        corpus_sha256=c.sha(corpus_path),
        successful_measured_rows=len(successes),
        charged_failed_attempts=len(failures),
        independent_workload_groups=groups,
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        packages={name: importlib.metadata.version(name)
                  for name in ("numpy", "xgboost", "scikit-learn")},
        model_seed=MODEL_SEED,
        policy_seeds=list(POLICY_SEEDS),
        area_cap_lut4=AREA_CAP,
        minimum_routed_fmax_mhz=CLOCK_MHZ,
        budgets=list(BUDGETS),
        policies=list(POLICIES),
        models=dict(
            existing_speedup_predictor="20 row-bootstrap XGBoost regressors; fixed repository settings",
            existing_pairwise_ranker="XGBRanker rank:pairwise; fixed repository settings",
            existing_factorized="Existing 20-member XGBoost cap-conditioned feasibility model",
            xgb_feasibility_64="One fixed depth-2 XGBClassifier trained on +64 feasible labels",
            group_bootstrap_xgb_feasibility_64="20 depth-2 XGB classifiers; sample workload groups with replacement",
            logistic_feasibility_64="StandardScaler + LogisticRegression(C=.1)",
            random_forest_feasibility_64="RandomForestClassifier(300 trees, max_features=.8, min_leaf=2)",
            extra_trees_feasibility_64="ExtraTreesClassifier(300 trees, max_features=.8, min_leaf=2)"),
        decision_rule="feasibility score × max(0, public calibrated estimated cycle reduction); benefit prediction is unchanged",
        split="Outer full-workload holdout; remove all related operation-tree families from training using both successful and failed target candidates.",
        unknown_failures="All four failed attempts are retained as public target-pool queries with their actual charged durations; they never train as infeasible labels. Two infrastructure-censored candidates make their workload oracle unknown.",
        endpoint="Best actually measured, correct, area-feasible and timing-feasible candidate found after 1/2/3 charged queries. Regret is computed only on complete verified candidate pools.",
        model_selection_warning="These previously consumed outcomes have informed earlier model work. Results select no production model and do not support a generalization or superiority claim.",
        limitations=[
            "Twelve groups have complete verified pool references; UD and G.723 include infrastructure-censored candidates and have lower-bound best-verified references only.",
            "Estimator seeds and candidate contexts are not independent workload groups.",
            "The 122 measured speedups equal calibrated analytic latency exactly, so the model comparison targets hardware feasibility, not benefit regression.",
            "Feasibility scores are ranking scores; no calibration or coverage guarantee is claimed.",
            "All policies use static zero-shot order; this is not active target adaptation or live native selection.",
            "All policy comparisons reuse consumed results; fresh frozen candidates are required for confirmation.",
        ],
    )
    c.seal(output / "protocol.json", protocol)

    runs, fold_metadata, fit_times, feasibility_diagnostics, score_snapshots = [], [], [], [], []
    for group, training, test_success, test_failures, excluded, pools in folds:
        target_families = sorted({speedup_corpus.family(row["formula"])
                                  for row in test_success + test_failures})
        fold_metadata.append(dict(workload_group=group, training_rows=len(training),
            training_workload_groups=sorted({row["workload_group"] for row in training}),
            successful_test_rows=len(test_success), failed_test_attempts=len(test_failures),
            censored_candidate_ids=sorted(row["candidate_id"] for row in test_failures
                                          if row.get("reference_censored")),
            excluded_related_candidate_ids=excluded,
            target_formula_families=target_families,
            benchmark_pools={benchmark: len(pool) for benchmark, pool in pools.items()}))
        for benchmark, pool in sorted(pools.items()):
            pool_success = {row["candidate_id"]: row for row in pool
                            if row.get("status", "success") == "success"}
            pool_failures = {row["candidate_id"]: row for row in pool
                             if row.get("status") == "failed"}
            reference = max([1.0] + [row["speedup"] for row in pool_success.values()
                if _feasible(row)])
            reference_censored = any(row.get("reference_censored") is True
                                     for row in pool_failures.values())
            order_started = time.monotonic()
            orders, feasibility_scores, timing = _prediction_orders(training, pool, MODEL_SEED)
            order_seconds = time.monotonic() - order_started
            fit_times.append(dict(workload_group=group, benchmark=benchmark,
                model_seed=MODEL_SEED, order_generation_seconds=order_seconds,
                **timing))
            target_labeled = [row for row in pool if row.get("status", "success") == "success"]
            target_labels = {row["candidate_id"]: int(_feasible(row)) for row in target_labeled}
            for model_name, by_candidate in feasibility_scores.items():
                scores_for_labels = [by_candidate[row["candidate_id"]] for row in target_labeled]
                labels_for_scores = [target_labels[row["candidate_id"]] for row in target_labeled]
                feasibility_diagnostics.append(dict(
                    workload_group=group, benchmark=benchmark, model=model_name,
                    scored_successful_labels=len(target_labeled),
                    unknown_failed_attempts=len(pool_failures),
                    brier_score=statistics.mean((score - label) ** 2
                        for score, label in zip(scores_for_labels, labels_for_scores)),
                    scores_calibrated=False,
                ))
                score_snapshots.append(dict(workload_group=group, benchmark=benchmark,
                    model=model_name,
                    predictions=[dict(candidate_id=row["candidate_id"],
                        feasibility_score=by_candidate[row["candidate_id"]],
                        label=target_labels[row["candidate_id"]]) for row in target_labeled]))
            for seed in POLICY_SEEDS:
                for policy, order in orders.items():
                    if policy == "random":
                        order = list(pool)
                        random.Random(seed).shuffle(order)
                    for budget in BUDGETS:
                        point = _evaluate_group(policy, order, pool_success, pool_failures,
                            reference, reference_censored, seed=seed, budget=budget)
                        runs.append(dict(workload_group=group, benchmark=benchmark, **point))

    report = dict(protocol_sha256=c.sha(output / "protocol.json"),
        folds=fold_metadata, model_timing=fit_times, runs=runs,
        feasibility_diagnostics=feasibility_diagnostics,
        **_summarize(runs),
        interpretation=("Exploratory result on consumed labels. The best model is selected only for follow-up; it is not a production promotion."))
    c.seal(output / "report.json", report)
    c.seal(output / "feasibility-predictions.json", score_snapshots)
    # Human-readable model screen summary, still explicitly marked consumed-data.
    macro = report["macro_summary"]
    lines = ["# Feasibility-model family screen (retrospective)", "",
        "Consumed-data development only; no independent confirmation.", "",
        "| Policy | Budget | Mean verified cycle reduction | Mean regret on complete pools | Complete pools | Mean charged evaluation seconds |",
        "|---|---:|---:|---:|---:|---:|"]
    for row in macro:
        regret = "—" if row["mean_cycle_reduction_regret"] is None else f"{100*row['mean_cycle_reduction_regret']:.4f}%"
        lines.append(f"| {row['policy']} | {row['budget']} | {100*row['mean_verified_cycle_reduction']:.4f}% | {regret} | {row['uncensored_oracle_workload_groups']}/{row['workload_groups']} | {row['mean_measurement_seconds']:.2f} |")
    lines.extend(["", "Failed attempts remain in the target query pools and consume budget and measured time. They are never assigned fabricated feasibility labels. UD and G.723 are excluded from oracle regret because an infrastructure-censored candidate leaves the full pool unresolved.", ""])
    (output / "results.md").write_text("\n".join(lines), encoding="utf-8")
    artifacts = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob("*")) if path.is_file()}
    c.seal(output / "manifest.json", artifacts)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(args.corpus, args.output)
    print(json.dumps(dict(workload_groups=len(report["folds"]),
        rows=len(report["runs"]), policies=len(POLICIES),
        scope="retrospective consumed-data development"), indent=2))


if __name__ == "__main__":
    main()

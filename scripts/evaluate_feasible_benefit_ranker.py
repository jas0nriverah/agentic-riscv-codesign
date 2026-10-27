"""Test a pairwise ranker aligned to measured feasible program improvement.

This is a retrospective, consumed-data development comparison. Training
relevance is measured whole-program cycle reduction for candidates that meet
the fixed area/timing constraint, and zero for measured infeasible designs.
Held-out candidates and failed attempts remain unlabeled until scoring; failed
attempts still consume the same query budget and measured duration.
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

from isaforge import budgeted_selection as budgeted
from isaforge import codesign as c
from isaforge import model as speedup_model
from isaforge import ranking
from isaforge import speedup_corpus
from scripts import evaluate_feasibility_model_families as prior
from scripts.reproduce_guarded_sha256 import _manifest

SOURCE = "scripts/evaluate_feasible_benefit_ranker.py"
SOURCES = (
    SOURCE,
    prior.SOURCE,
    "isaforge/budgeted_selection.py",
    "isaforge/codesign.py",
    "isaforge/features.py",
    "isaforge/model.py",
    "isaforge/ranking.py",
    "isaforge/speedup_corpus.py",
    "scripts/reproduce_guarded_sha256.py",
)
POLICY = "xgb_feasible_benefit_ranker"
AREA_CAP = 64
CLOCK_MHZ = 12.0
MODEL_SEED = 0
POLICY_SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
BASELINES = (
    "merit",
    "latency_cost_heuristic",
    "xgb_pairwise_ranker",
    "factorized_feasibility_xgb",
)


def _measured_feasible_relevance(rows, area_cap=AREA_CAP, clock_mhz=CLOCK_MHZ):
    """Return XGBoost ranker labels: measured feasible cycle-reduction ranks.

    The candidate's measured benefit receives relevance only if its measured
    integrated hardware meets both constraints. All measured infeasible rows
    receive relevance zero. Ties are preserved within each benchmark query.
    """
    speedup_model.validate_training_rows(rows)
    c.require(len({row["candidate_id"] for row in rows}) == len(rows),
              "Duplicate training candidate identity")
    ordered = sorted(rows, key=lambda row: (row["benchmark"], row["candidate_id"]))
    utilities = {}
    for row in ordered:
        c.require(row.get("status", "success") == "success",
                  "Failed attempts cannot train ranking relevance")
        c.require(row["speedup"] > 0 and math.isfinite(float(row["speedup"])),
                  "Measured speedup must be positive and finite")
        feasible = budgeted._feasible(row, area_cap, clock_mhz)
        utilities[row["candidate_id"]] = (
            max(0.0, 1.0 - 1.0 / row["speedup"]) if feasible else 0.0
        )

    labels, qids, groups = [], [], []
    benchmark_names = sorted({row["benchmark"] for row in ordered})
    for qid, benchmark in enumerate(benchmark_names):
        members = [row for row in ordered if row["benchmark"] == benchmark]
        values = sorted({utilities[row["candidate_id"]] for row in members})
        labels.extend(values.index(utilities[row["candidate_id"]]) for row in members)
        qids.extend([qid] * len(members))
        groups.append(dict(benchmark=benchmark, rows=len(members),
                           distinct_relevance_levels=len(values),
                           feasible_training_rows=sum(
                               budgeted._feasible(row, area_cap, clock_mhz)
                               for row in members)))
    return ordered, labels, qids, groups


def _fit_ranker(training, *, seed=MODEL_SEED):
    """Fit only on measured training rows; returns model plus label audit."""
    import numpy as np
    from xgboost import XGBRanker

    ordered, labels, qids, groups = _measured_feasible_relevance(training)
    c.require(any(group["distinct_relevance_levels"] > 1 for group in groups),
              "Training data has no within-workload feasible-benefit pair")
    model = XGBRanker(**ranking.PARAMETERS, random_state=seed)
    model.fit(np.asarray(speedup_model.feature_matrix(ordered), dtype=float),
              np.asarray(labels, dtype=int), qid=np.asarray(qids, dtype=int))
    return model, dict(
        training_ids=[row["candidate_id"] for row in ordered],
        query_groups=groups,
        training_rows=len(ordered),
        positive_relevance_rows=sum(label > 0 for label in labels),
        zero_relevance_rows=sum(label == 0 for label in labels),
    )


def _percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = fraction * (len(values) - 1)
    lower, upper = int(position), min(int(position) + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _paired_bootstrap(differences, seed=20261026, draws=10000):
    groups = sorted(differences)
    values = [differences[group] for group in groups]
    if not values:
        return dict(mean=None, lower_95=None, upper_95=None, workload_groups=0)
    rng = random.Random(seed)
    samples = [statistics.mean(values[rng.randrange(len(values))] for _ in values)
               for _ in range(draws)]
    return dict(mean=statistics.mean(values), lower_95=_percentile(samples, .025),
                upper_95=_percentile(samples, .975), workload_groups=len(groups),
                wins=sum(value > 0 for value in values),
                ties=sum(value == 0 for value in values),
                losses=sum(value < 0 for value in values),
                interpretation="Positive means the challenger has lower regret.")


def _group_summaries(runs):
    grouped = defaultdict(list)
    for row in runs:
        grouped[(row["workload_group"], row["benchmark"], row["budget"])].append(row)
    context_rows = []
    for (workload, benchmark, budget), rows in sorted(grouped.items()):
        uncensored = [row for row in rows if not row["reference_censored"]]
        context_rows.append(dict(workload_group=workload, benchmark=benchmark,
            budget=budget,
            mean_cycle_reduction=statistics.mean(row["verified_cycle_reduction"]
                                                 for row in rows),
            mean_regret=(statistics.mean(row["cycle_reduction_regret"]
                                         for row in uncensored) if uncensored else None),
            mean_evaluation_seconds=statistics.mean(row["measurement_seconds"]
                                                    for row in rows),
            failed_query_count=statistics.mean(row["failed_or_unresolved_attempts"]
                                               for row in rows),
            dependent_policy_seeds=len(rows)))
    workload_rows = []
    for workload in sorted({row["workload_group"] for row in context_rows}):
        for budget in BUDGETS:
            members = [row for row in context_rows if row["workload_group"] == workload
                       and row["budget"] == budget]
            complete = [row["mean_regret"] for row in members
                        if row["mean_regret"] is not None]
            workload_rows.append(dict(workload_group=workload, budget=budget,
                mean_cycle_reduction=statistics.mean(row["mean_cycle_reduction"]
                                                     for row in members),
                mean_regret=statistics.mean(complete) if complete else None,
                reference_censored=not bool(complete),
                mean_evaluation_seconds=statistics.mean(row["mean_evaluation_seconds"]
                                                        for row in members),
                failed_query_count=statistics.mean(row["failed_query_count"]
                                                   for row in members)))
    macro = []
    for budget in BUDGETS:
        members = [row for row in workload_rows if row["budget"] == budget]
        complete = [row["mean_regret"] for row in members if row["mean_regret"] is not None]
        macro.append(dict(policy=POLICY, budget=budget,
            workload_groups=len(members), uncensored_oracle_workload_groups=len(complete),
            mean_verified_cycle_reduction=statistics.mean(row["mean_cycle_reduction"]
                                                          for row in members),
            mean_cycle_reduction_regret=statistics.mean(complete) if complete else None,
            mean_evaluation_seconds=statistics.mean(row["mean_evaluation_seconds"]
                                                    for row in members),
            mean_failed_queries=statistics.mean(row["failed_query_count"]
                                                for row in members)))
    return context_rows, workload_rows, macro


def _paired_contrasts(runs, baseline_runs):
    indexed = {(row["workload_group"], row["benchmark"], row["seed"], row["budget"]): row
               for row in runs}
    baseline_index = {(row["workload_group"], row["benchmark"], row["seed"],
                       row["budget"], row["policy"]): row for row in baseline_runs}
    contrasts = []
    for budget in BUDGETS:
        for baseline in BASELINES:
            by_context = defaultdict(list)
            for (workload, benchmark, seed, run_budget), challenger in indexed.items():
                if run_budget != budget:
                    continue
                old = baseline_index[(workload, benchmark, seed, budget, baseline)]
                if old["cycle_reduction_regret"] is not None and challenger["cycle_reduction_regret"] is not None:
                    by_context[workload].append(old["cycle_reduction_regret"]
                                                - challenger["cycle_reduction_regret"])
            contrasts.append(dict(budget=budget, baseline=baseline,
                challenger=POLICY, **_paired_bootstrap({
                    workload: statistics.mean(values)
                    for workload, values in by_context.items()})))
    return contrasts


def evaluate(corpus_path, baseline_screen, output):
    corpus_path, baseline_screen, output = map(Path, (corpus_path, baseline_screen, output))
    corpus_path, baseline_screen, output = (path.resolve() for path in
                                              (corpus_path, baseline_screen, output))
    c.require(corpus_path.is_relative_to(ROOT) and baseline_screen.is_relative_to(ROOT)
              and output.is_relative_to(ROOT), "Repository-local inputs and output required")
    c.require(not output.exists(), "Use a fresh exploratory output directory")
    _manifest(corpus_path.parent)
    _manifest(baseline_screen)
    corpus = c.unseal(corpus_path)
    baseline_protocol = c.unseal(baseline_screen / "protocol.json")
    baseline_report = c.unseal(baseline_screen / "report.json")
    c.require(corpus.get("schema") == "isaforge-consumed-guarded-corpus-v1"
              and len(corpus.get("rows", [])) == 122
              and len(corpus.get("failed_attempts", [])) == 4,
              "Authenticated 122-label/126-attempt corpus required")
    c.require(baseline_protocol.get("schema") == "isaforge-feasibility-model-family-screen-v1"
              and baseline_protocol["corpus_sha256"] == c.sha(corpus_path)
              and baseline_report["protocol_sha256"] == c.sha(baseline_screen / "protocol.json"),
              "Matching authenticated failure-aware baseline screen required")
    c.require(set(baseline_protocol["policies"]) >= set((*BASELINES, "xgb_pairwise_ranker")),
              "Required exact matched-baseline policies missing")
    successes, failures = corpus["rows"], corpus["failed_attempts"]
    c.require(len(successes) == 122 and len(failures) == 4,
              "Corpus row counts changed")
    for row in failures:
        c.require(row.get("status") == "failed" and "speedup" not in row
                  and "area_delta_lut4" not in row and row.get("measurement_seconds", 0) > 0,
                  "Failed attempts must remain unknown labels and retain charged time")

    baseline_runs = baseline_report["runs"]
    expected_keys = {(row["workload_group"], row["benchmark"], row["seed"],
                      row["budget"], row["policy"])
                     for row in baseline_runs}
    c.require(len(expected_keys) == len(baseline_runs), "Duplicate baseline trajectory key")
    baseline_by_policy = {row["policy"] for row in baseline_runs}
    c.require(set(BASELINES) <= baseline_by_policy, "Matched baseline trajectories incomplete")

    groups = sorted({row["workload_group"] for row in successes})
    output.mkdir(parents=True)
    protocol = dict(
        schema="isaforge-measured-feasible-benefit-ranker-v1",
        scope="retrospective consumed-data model development; no independent confirmation",
        corpus_path=corpus_path.relative_to(ROOT).as_posix(),
        corpus_sha256=c.sha(corpus_path),
        baseline_screen_path=baseline_screen.relative_to(ROOT).as_posix(),
        baseline_manifest_sha256=c.sha(baseline_screen / "manifest.json"),
        baseline_screen_protocol_sha256=c.sha(baseline_screen / "protocol.json"),
        baseline_screen_report_sha256=c.sha(baseline_screen / "report.json"),
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        packages={name: importlib.metadata.version(name)
                  for name in ("numpy", "xgboost", "scikit-learn")},
        independent_workload_groups=groups,
        successful_training_labels=122,
        charged_failures=4,
        model="XGBRanker with existing rank:pairwise parameters; measured feasible cycle-reduction relevance",
        model_settings={**ranking.PARAMETERS, "random_state": MODEL_SEED},
        relevance=("Within each training benchmark, dense ordinal labels of measured whole-program "
                   "cycle reduction when the measured candidate is <=64 LUT4 and >=12 MHz; "
                   "measured infeasible candidates receive zero relevance. Ties are preserved."),
        area_cap_lut4=AREA_CAP,
        minimum_routed_fmax_mhz=CLOCK_MHZ,
        budgets=list(BUDGETS),
        policy_seeds=list(POLICY_SEEDS),
        baselines=list(BASELINES),
        split="Whole workload held out; remove related operation-tree families from training using successful and failed target candidates.",
        failure_handling="All failures remain public pool choices, consume their actual charged duration, and are excluded from training relevance and feasibility labels.",
        selection="Fit once on the remaining successful measured rows, rank all target public candidates before revealing any target outcomes, then score the first 1/2/3 charged queries.",
        model_timing="Fit/inference host time is reported separately from native measurement time.",
        limitations=[
            "This corpus and its prior policy screen already informed development; the result is retrospective and exploratory.",
            "Only 12 workload groups have complete verified pool oracles; two infrastructure-censored groups are reported without regret.",
            "Policy seeds are dependent repetitions, not additional independent workloads.",
            "The ranking output is an ordering score, not a calibrated benefit estimate or uncertainty interval.",
            "The labels optimize single-instruction measured feasibility and benefit; they do not establish multi-instruction set utility.",
        ],
    )
    c.seal(output / "protocol.json", protocol)

    runs, fold_rows, timing_rows = [], [], []
    for group in groups:
        training, test_success, test_failures, excluded = prior._split_with_failures(
            successes, failures, group)
        c.require(len(training) >= 3
                  and len({row["workload_group"] for row in training}) >= 2,
                  "Insufficient source-held-out training rows: " + group)
        start = time.monotonic()
        model, training_audit = _fit_ranker(training, seed=MODEL_SEED)
        fit_seconds = time.monotonic() - start
        target_families = sorted({speedup_corpus.family(row["formula"])
                                  for row in test_success + test_failures})
        pools = defaultdict(list)
        for row in test_success + test_failures:
            pools[row["benchmark"]].append(row)
        fold_rows.append(dict(workload_group=group, training_rows=len(training),
            training_workload_groups=sorted({row["workload_group"] for row in training}),
            successful_test_rows=len(test_success), failed_test_attempts=len(test_failures),
            excluded_related_candidate_ids=excluded, target_formula_families=target_families,
            training_label_audit=training_audit))
        for benchmark, pool in sorted(pools.items()):
            pool = sorted(pool, key=lambda row: row["candidate_id"])
            public = [prior._public(row) for row in pool]
            start = time.monotonic()
            scores = model.predict(speedup_model.feature_matrix(public))
            inference_seconds = time.monotonic() - start
            score_map = {row["candidate_id"]: float(score)
                         for row, score in zip(pool, scores)}
            c.require(all(math.isfinite(score) for score in score_map.values()),
                      "Ranker produced nonfinite target score")
            order = sorted(pool, key=lambda row: (-score_map[row["candidate_id"]],
                                                  row["candidate_id"]))
            success_by_id = {row["candidate_id"]: row for row in pool
                             if row.get("status", "success") == "success"}
            failure_by_id = {row["candidate_id"]: row for row in pool
                             if row.get("status") == "failed"}
            oracle = max([1.0] + [row["speedup"] for row in success_by_id.values()
                                  if prior._feasible(row)])
            censored = any(row.get("reference_censored") is True
                           for row in failure_by_id.values())
            timing_rows.append(dict(workload_group=group, benchmark=benchmark,
                model_fit_seconds=fit_seconds, inference_seconds=inference_seconds,
                fit_training_rows=len(training), target_candidates=len(pool)))
            for seed in POLICY_SEEDS:
                for budget in BUDGETS:
                    point = prior._evaluate_group(POLICY, order, success_by_id,
                        failure_by_id, oracle, censored, seed=seed, budget=budget)
                    runs.append(dict(workload_group=group, benchmark=benchmark, **point))

    context_summaries, workload_summaries, macro = _group_summaries(runs)
    contrasts = _paired_contrasts(runs, baseline_runs)
    report = dict(protocol_sha256=c.sha(output / "protocol.json"), folds=fold_rows,
        model_timing=timing_rows, runs=runs, context_summary=context_summaries,
        workload_summary=workload_summaries, macro_summary=macro,
        paired_contrasts=contrasts,
        interpretation="Decision-aware relevance is a targeted development challenger only; it is not promoted.")
    c.seal(output / "report.json", report)
    lines = ["# Measured feasible-benefit ranker screen", "",
             "Retrospective consumed-data development only; this is not an independent test.",
             "The new ranker trains on measured cycle-reduction relevance only when area and timing are feasible; failures consume budget and time without labels.", "",
             "| Budget | Mean cycle reduction | Mean regret | Complete oracles | Mean native evaluation seconds |", "|---:|---:|---:|---:|---:|"]
    for row in macro:
        regret = "n/a" if row["mean_cycle_reduction_regret"] is None else f"{100*row['mean_cycle_reduction_regret']:.4f}%"
        lines.append(f"| {row['budget']} | {100*row['mean_verified_cycle_reduction']:.4f}% | {regret} | {row['uncensored_oracle_workload_groups']}/{row['workload_groups']} | {row['mean_evaluation_seconds']:.2f} |")
    lines.extend(["", "## Paired comparison against the frozen screen", "",
                  "Positive regret difference means the feasible-benefit ranker has lower regret.",
                  "Intervals resample independent workload groups; policy seeds are averaged within workload and do not increase the sample size.", "",
                  "| Budget | Baseline | Mean regret advantage (pp) | 95% workload-bootstrap interval (pp) | Wins / ties / losses |",
                  "|---:|---|---:|---:|---:|"])
    for row in contrasts:
        mean = "n/a" if row["mean"] is None else f"{100*row['mean']:.4f}"
        interval = "n/a" if row["lower_95"] is None else f"[{100*row['lower_95']:.4f}, {100*row['upper_95']:.4f}]"
        wtl = "n/a" if row["workload_groups"] == 0 else f"{row['wins']} / {row['ties']} / {row['losses']}"
        lines.append(f"| {row['budget']} | {row['baseline']} | {mean} | {interval} | {wtl} |")
    lines.extend(["", "Model fit/inference wall time is recorded in `report.json` separately from measured hardware-evaluation time. UD and G.723 reference comparisons are omitted because an infrastructure-censored candidate leaves their full-pool oracle unknown.", ""])
    (output / "results.md").write_text("\n".join(lines), encoding="utf-8")
    artifacts = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob("*")) if path.is_file()}
    c.seal(output / "manifest.json", artifacts)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--baseline-screen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate(args.corpus, args.baseline_screen, args.output)
    print(json.dumps(dict(workload_groups=len(result["folds"]), runs=len(result["runs"]),
                          policy=POLICY,
                          scope="retrospective consumed-data development"), indent=2))


if __name__ == "__main__":
    main()

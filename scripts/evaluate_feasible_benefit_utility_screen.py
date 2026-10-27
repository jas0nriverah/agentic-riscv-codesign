"""Failure-aware LOCO test of ISAForge's existing cap-conditioned utility XGBoost.

The model already exists and has a prospective SHA256 result. This screen adds
the missing apples-to-apples comparison over the current consumed corpus,
including all failed attempts in each held-out query pool. It is exploratory,
not a fresh generalization claim.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as budgeted
from isaforge import codesign as c
from isaforge import feasible_benefit as utility_model
from isaforge import speedup_corpus
from scripts import evaluate_feasibility_model_families as baseline_screen
from scripts import evaluate_feasible_benefit_ranker as comparison
from scripts.reproduce_guarded_sha256 import _manifest

SOURCE = "scripts/evaluate_feasible_benefit_utility_screen.py"
SOURCES = (
    SOURCE,
    baseline_screen.SOURCE,
    comparison.SOURCE,
    "isaforge/budgeted_selection.py",
    "isaforge/codesign.py",
    "isaforge/features.py",
    "isaforge/feasible_benefit.py",
    "isaforge/model.py",
    "isaforge/prospective_selection.py",
    "isaforge/speedup_corpus.py",
    "scripts/reproduce_guarded_sha256.py",
)
POLICY = "existing_feasible_benefit_xgb"
AREA_CAP = 64
MODEL_SEED = 0
POLICY_SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)


def evaluate(corpus_path, baseline_path, output):
    corpus_path, baseline_path, output = (Path(value).resolve()
        for value in (corpus_path, baseline_path, output))
    c.require(corpus_path.is_relative_to(ROOT) and baseline_path.is_relative_to(ROOT)
              and output.is_relative_to(ROOT), "Repository-local paths required")
    c.require(not output.exists(), "Use a fresh output directory")
    _manifest(corpus_path.parent)
    _manifest(baseline_path)
    corpus = c.unseal(corpus_path)
    frozen = c.unseal(baseline_path / "protocol.json")
    frozen_report = c.unseal(baseline_path / "report.json")
    c.require(corpus.get("schema") == "isaforge-consumed-guarded-corpus-v1"
              and len(corpus.get("rows", [])) == 122
              and corpus.get("successful_labels") == 122
              and corpus.get("total_candidate_attempts") == 126
              and len(corpus.get("failed_attempts", [])) == 4,
              "Authenticated 122-label/126-attempt corpus required")
    c.require(frozen.get("schema") == "isaforge-feasibility-model-family-screen-v1"
              and frozen["corpus_sha256"] == c.sha(corpus_path)
              and frozen_report["protocol_sha256"] == c.sha(baseline_path / "protocol.json"),
              "Matching frozen baseline screen required")
    for name, expected in frozen["source_bindings"].items():
        c.require(c.sha(ROOT / name) == expected,
                  "Frozen baseline-screen source changed: " + name)
    c.require(frozen["area_cap_lut4"] == AREA_CAP
              and frozen["minimum_routed_fmax_mhz"] == utility_model.CLOCK_MHZ
              and frozen["budgets"] == list(BUDGETS)
              and frozen["policy_seeds"] == list(POLICY_SEEDS),
              "Baseline protocol budgets or constraints differ")

    successes, failures = corpus["rows"], corpus["failed_attempts"]
    for row in successes:
        c.require(budgeted.validate_outcome(row)
                  and row["candidate_family"] == speedup_corpus.family(row["formula"]),
                  "Successful measured corpus row failed validation")
    for row in failures:
        c.require(row.get("status") == "failed" and "speedup" not in row
                  and "area_delta_lut4" not in row
                  and row.get("measurement_seconds", 0) > 0
                  and row["candidate_family"] == speedup_corpus.family(row["formula"]),
                  "Failed rows must remain unknown labels with charged cost")

    output.mkdir(parents=True)
    groups = sorted({row["workload_group"] for row in successes})
    protocol = dict(
        schema="isaforge-existing-feasible-benefit-loco-screen-v1",
        scope="retrospective consumed-data model development; no independent confirmation",
        corpus_path=corpus_path.relative_to(ROOT).as_posix(),
        corpus_sha256=c.sha(corpus_path),
        baseline_screen_path=baseline_path.relative_to(ROOT).as_posix(),
        baseline_manifest_sha256=c.sha(baseline_path / "manifest.json"),
        baseline_protocol_sha256=c.sha(baseline_path / "protocol.json"),
        baseline_report_sha256=c.sha(baseline_path / "report.json"),
        source_bindings={name: c.sha(ROOT / name) for name in SOURCES},
        packages={name: importlib.metadata.version(name)
                  for name in ("numpy", "scipy", "xgboost", "scikit-learn")},
        independent_workload_groups=groups,
        successful_measured_labels=len(successes),
        charged_failures=len(failures),
        model="Existing FeasibleBenefitPredictor; 20 candidate-bootstrap XGB regressors with 3 area-cap replicas",
        model_settings=utility_model.MODEL_SETTINGS,
        target=utility_model.decision_utility.__doc__,
        area_cap_lut4=AREA_CAP,
        minimum_routed_fmax_mhz=utility_model.CLOCK_MHZ,
        budgets=list(BUDGETS),
        policy_seeds=list(POLICY_SEEDS),
        split="Whole-workload heldout; remove every related operation-tree family found in all successful and failed target candidates from training.",
        failure_handling="Failures remain target query choices and consume actual measured time. They are never imputed as infeasible or zero-benefit training examples.",
        selection="Rank target public rows by existing FeasibleBenefitPredictor mean_fractional_cycle_savings at +64 LUT4; score first 1/2/3 charged attempts.",
        matched_baselines=list(comparison.BASELINES),
        limitations=[
            "Every corpus workload group and the baseline comparison have already informed development; this is retrospective.",
            "Only 12 workload groups have fully measured pool oracles; two censored groups have no regret estimate.",
            "Policy seeds are dependent repetitions, not additional independent workload groups.",
            "Bootstrap utility spread is not calibrated predictive uncertainty.",
            "All 122 measured speedups exactly match the calibrated latency model; this is a feasibility/decision test, not a new benefit-residual test.",
        ],
    )
    c.seal(output / "protocol.json", protocol)

    runs, folds, timing, predictions = [], [], [], []
    for group in groups:
        training, test_success, test_failures, excluded = baseline_screen._split_with_failures(
            successes, failures, group)
        c.require(len(training) >= 3
                  and len({row["workload_group"] for row in training}) >= 2,
                  "Insufficient grouped training for " + group)
        started = time.monotonic()
        model = utility_model.FeasibleBenefitPredictor(seed=MODEL_SEED).fit(training)
        fit_seconds = time.monotonic() - started
        test_families = sorted({speedup_corpus.family(row["formula"])
                                for row in test_success + test_failures})
        pools = {}
        for row in test_success + test_failures:
            pools.setdefault(row["benchmark"], []).append(row)
        folds.append(dict(workload_group=group, training_rows=len(training),
            training_workload_groups=sorted({row["workload_group"] for row in training}),
            successful_test_rows=len(test_success), failed_test_attempts=len(test_failures),
            excluded_related_candidate_ids=excluded,
            target_formula_families=test_families,
            training_ids=list(model.training_ids),
            training_area_per_operation_lut4=model.area_per_op))
        for benchmark, pool in sorted(pools.items()):
            pool = sorted(pool, key=lambda row: row["candidate_id"])
            public = [baseline_screen._public(row) for row in pool]
            started = time.monotonic()
            estimates = model.predict(public, area_cap=AREA_CAP)
            inference_seconds = time.monotonic() - started
            score_map = {row["candidate_id"]: row["mean_fractional_cycle_savings"]
                         for row in estimates}
            c.require(set(score_map) == {row["candidate_id"] for row in pool}
                      and all(math.isfinite(float(score)) for score in score_map.values()),
                      "Incomplete or nonfinite feasible-benefit predictions")
            predictions.extend(dict(workload_group=group, benchmark=benchmark,
                candidate_id=row["candidate_id"], score=score_map[row["candidate_id"]],
                predicted_utility_std=row["std_saved_cycles_per_occurrence"],
                uncertainty_calibrated=False) for row in estimates)
            order = sorted(pool, key=lambda row: (-score_map[row["candidate_id"]],
                                                  row["candidate_id"]))
            success_by_id = {row["candidate_id"]: row for row in pool
                             if row.get("status", "success") == "success"}
            failure_by_id = {row["candidate_id"]: row for row in pool
                             if row.get("status") == "failed"}
            oracle = max([1.0] + [row["speedup"] for row in success_by_id.values()
                                  if baseline_screen._feasible(row)])
            censored = any(row.get("reference_censored") is True
                           for row in failure_by_id.values())
            timing.append(dict(workload_group=group, benchmark=benchmark,
                fit_seconds=fit_seconds, inference_seconds=inference_seconds,
                training_rows=len(training), target_candidates=len(pool)))
            for seed in POLICY_SEEDS:
                for budget in BUDGETS:
                    point = baseline_screen._evaluate_group(POLICY, order,
                        success_by_id, failure_by_id, oracle, censored,
                        seed=seed, budget=budget)
                    runs.append(dict(workload_group=group, benchmark=benchmark, **point))

    context_summary, workload_summary, macro = comparison._group_summaries(runs)
    for row in macro:
        row["policy"] = POLICY
    contrasts = comparison._paired_contrasts(runs, frozen_report["runs"])
    for row in contrasts:
        row["challenger"] = POLICY
    report = dict(protocol_sha256=c.sha(output / "protocol.json"), folds=folds,
        model_timing=timing, predictions=predictions, runs=runs,
        context_summary=context_summary, workload_summary=workload_summary,
        macro_summary=macro, paired_contrasts=contrasts,
        interpretation="Existing model tested under corrected failure-aware grouped heldout comparison; no production promotion.")
    c.seal(output / "report.json", report)

    lines = ["# Existing feasible-benefit model: failure-aware LOCO screen", "",
             "Retrospective consumed-data development only. The model was not tuned in this screen.",
             "All failed attempts remain charged target choices with their measured duration and unknown labels.", "",
             "| Budget | Mean cycle reduction | Mean regret | Complete oracles | Mean native evaluation seconds |",
             "|---:|---:|---:|---:|---:|"]
    for row in macro:
        regret = "n/a" if row["mean_cycle_reduction_regret"] is None else f"{100*row['mean_cycle_reduction_regret']:.4f}%"
        lines.append(f"| {row['budget']} | {100*row['mean_verified_cycle_reduction']:.4f}% | {regret} | {row['uncensored_oracle_workload_groups']}/{row['workload_groups']} | {row['mean_evaluation_seconds']:.2f} |")
    lines.extend(["", "## Paired comparisons", "",
                  "Positive advantage means the existing feasible-benefit model has lower regret.",
                  "Workload is the bootstrap unit; the five policy seeds are dependent repetitions.", "",
                  "| Budget | Baseline | Mean regret advantage (pp) | 95% workload interval (pp) | Wins / ties / losses |",
                  "|---:|---|---:|---:|---:|"])
    for row in contrasts:
        mean = "n/a" if row["mean"] is None else f"{100*row['mean']:.4f}"
        interval = "n/a" if row["lower_95"] is None else f"[{100*row['lower_95']:.4f}, {100*row['upper_95']:.4f}]"
        counts = "n/a" if not row["workload_groups"] else f"{row['wins']} / {row['ties']} / {row['losses']}"
        lines.append(f"| {row['budget']} | {row['baseline']} | {mean} | {interval} | {counts} |")
    lines.append("")
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

"""Retrospective prequential check of the frozen joint posterior's paid updates.

The existing calibration audit scores only the zero-observation posterior. This
diagnostic uses the same LOCO/family-exclusion folds, predicts each held-out
candidate before reading its numeric outcome in the scoring loop, then conditions
on verified successes only. Candidate order is fixed by full candidate ID, not
selected from target labels or predictions. This is not policy-conditioned or
prospective evidence and does not tune the model.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b, codesign as c
from isaforge import joint_hardware as joint, semantic_selection as semantic
from scripts import audit_joint_posterior_calibration as prior

SOURCE = "scripts/audit_joint_paid_prefix_calibration.py"
DEFAULT_OUTPUT = ROOT / "results/2026-10-27-joint-paid-prefix-calibration-r2"
SOURCES = tuple(dict.fromkeys((
    SOURCE,
    "scripts/audit_joint_posterior_calibration.py",
    "isaforge/joint_hardware.py",
    "isaforge/semantic_selection.py",
    "isaforge/budgeted_selection.py",
    "isaforge/speedup_corpus.py",
    "isaforge/codesign.py",
)))
OUTPUT_FIELDS = prior.OUTPUT_FIELDS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_bindings():
    return {name: c.sha(ROOT / name) for name in SOURCES}


def public_projection(rows):
    return [{key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS} for row in rows]


def prequential_sequence(posterior, attempts, successes, *, workload_group):
    """Score predictions before the next attempt; update only after success."""
    attempts = list(attempts)
    successes = {row["candidate_id"]: row for row in successes}
    require(len({row["candidate_id"] for row in attempts}) == len(attempts),
            "Attempt identities must be unique")
    require(set(successes) <= {row["candidate_id"] for row in attempts},
            "Every successful outcome must have a declared attempt")
    records = []
    for attempt_index, attempt in enumerate(attempts):
        identity = attempt["candidate_id"]
        require(identity in posterior.candidate_ids and identity not in posterior.conditioned_ids,
                "Attempt must be a fresh candidate in the frozen public pool")

        # This query is intentionally before success lookup and posterior update.
        # Its public input is the candidate identity only; measured values enter below.
        prediction = posterior.joint([identity])
        row = dict(candidate_id=identity, workload_group=workload_group,
            attempt_index=attempt_index, charged_attempts_before=attempt_index,
            successful_conditions_before=len(posterior.observed_ids),
            status=attempt.get("status", "success" if identity in successes else "failed"))
        for output, value_of in OUTPUT_FIELDS.items():
            marginal = prediction["outputs"][output]
            mean = float(marginal["mean"][0])
            variance = float(marginal["observation_covariance"][0][0])
            require(math.isfinite(mean) and math.isfinite(variance) and variance > 0,
                    "Finite predictive mean and positive observation variance required")
            row[output] = dict(predicted_mean=mean,
                predictive_std=math.sqrt(variance))

        outcome = successes.get(identity)
        if outcome is not None:
            require(attempt.get("status", "success") == "success",
                    "Successful measurement and attempt status disagree")
            for output, value_of in OUTPUT_FIELDS.items():
                observed = float(value_of(outcome))
                residual = observed - row[output]["predicted_mean"]
                z = residual / row[output]["predictive_std"]
                row[output].update(observed=observed, residual=residual,
                                   standardized_residual=z)
            row["hardware_feasible"] = int(b._feasible(outcome, 64, 12.0))
            # This is the first point where the scoring loop passes the current
            # candidate's measured outputs to the posterior.
            posterior = posterior.condition(outcome, queried_id=identity)
            row["conditioned_after_score"] = True
        else:
            require(attempt.get("status") == "failed",
                    "Unlabeled attempt must remain a charged terminal failure")
            row["failure_class"] = attempt.get("failure_class", "unspecified")
            row["reference_censored"] = bool(attempt.get("reference_censored", False))
            row["conditioned_after_score"] = False
        records.append(row)
    return records, posterior


def summarize(records):
    successful = [row for row in records if row["status"] == "success"]
    result = dict(scored_successes=len(successful), charged_attempts=len(records),
        charged_failures=sum(row["status"] == "failed" for row in records),
        successful_conditions=sum(row["conditioned_after_score"] for row in records),
        by_charged_prefix={})
    prefixes = sorted({row["charged_attempts_before"] for row in successful})
    for prefix in prefixes:
        points = [row for row in successful if row["charged_attempts_before"] == prefix]
        outputs = {}
        for output in OUTPUT_FIELDS:
            metrics = prior.interval_metrics(
                [row[output]["standardized_residual"] for row in points])
            metrics["mean_absolute_error"] = sum(
                abs(row[output]["residual"]) for row in points) / len(points)
            outputs[output] = metrics
        result["by_charged_prefix"][str(prefix)] = dict(n=len(points), outputs=outputs)

    outputs = {}
    for output in OUTPUT_FIELDS:
        outputs[output] = prior.interval_metrics(
            [row[output]["standardized_residual"] for row in successful])
    result["prequential_overall"] = outputs
    return result


def evaluate(corpus, corpus_sha):
    successes = corpus["rows"]
    failures = corpus["failed_attempts"]
    groups = sorted({row["workload_group"] for row in successes})
    folds = []
    fit_calls = 0
    fit_seconds = 0.0
    scoring_seconds = 0.0
    for group in groups:
        training, target, target_failures, families = prior.split_groups(
            successes, failures, group)
        # The public pool includes failed candidates so their attempt is charged
        # in the prefix, while failures contribute no fabricated numeric label.
        target_attempts = sorted(target + target_failures,
                                 key=lambda row: row["candidate_id"])
        public = public_projection(target_attempts)
        fit_started = time.perf_counter()
        fitted = semantic.SemanticHardwareSurrogate().fit(training)
        state = joint.JointHardwarePosterior.from_fitted(fitted, training, public)
        fit_seconds += time.perf_counter() - fit_started
        fit_calls += 1
        success_rows = {row["candidate_id"]: row for row in target}
        scoring_started = time.perf_counter()
        records, final_state = prequential_sequence(
            state, target_attempts, success_rows.values(), workload_group=group)
        scoring_seconds += time.perf_counter() - scoring_started
        require(len(final_state.observed_ids) == len(target),
                "Every verified success must condition exactly once")
        require(not set(final_state.observed_ids) & {row["candidate_id"]
                for row in target_failures}, "Failed attempts must never condition the posterior")
        folds.append(dict(workload_group=group, training_count=len(training),
            target_success_count=len(target), target_failed_attempts=len(target_failures),
            excluded_family_count=len(families), excluded_families=families,
            training_ids=[row["candidate_id"] for row in training],
            attempt_order=[row["candidate_id"] for row in target_attempts],
            summary=summarize(records), scored_candidate_records=records,
            final_posterior_sha256=final_state.snapshot()["posterior_state_sha256"]))
    all_records = [row for fold in folds for row in fold["scored_candidate_records"]]
    pooled = summarize(all_records)
    return dict(schema="isaforge-joint-paid-prefix-calibration-diagnostic-v1",
        status="retrospective_prequential_development_diagnostic_not_confirmatory",
        corpus_sha256=corpus_sha, fold_count=len(folds), fit_calls=fit_calls,
        total_fit_seconds=fit_seconds, total_scoring_seconds=scoring_seconds,
        folds=folds, pooled_summary=pooled,
        interpretation=("Candidate-ID-sorted predictions are scored before each row's recorded "
            "outcome is supplied to the posterior. Successful outcomes update the state; "
            "charged failures do not. This tests sequential conditioning under a fixed, "
            "non-adaptive order, not selection-conditioned calibration or a live acquisition policy."),
        limitations=[
            "All target outcomes are from the consumed 122-success / four-failure development corpus.",
            "Candidate-ID order is deterministic and chosen independently of target labels, but is not a real or simulated active-selection policy.",
            "Repeated within-workload residuals are dependent; confidence intervals are not workload-population intervals.",
            "The fixed Gaussian noise, independent output heads, and feasibility assumptions are unchanged and remain provisional.",
            "No new model recipe, hyperparameter, hardware measurement, or native job was introduced.",
        ])


def run(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and not output.exists(),
            "Use a fresh repository-local output directory")
    corpus, successes, failures, corpus_sha = prior._read_corpus(
        ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json")
    require(len(successes) == 122 and len(failures) == 4,
            "Exact authenticated consumed development corpus required")
    bindings = source_bindings()
    protocol = dict(schema="isaforge-joint-paid-prefix-calibration-protocol-v1",
        status="post_hoc_retrospective_not_preregistered",
        corpus_path="results/2026-10-26-lift-selection-corpus/corpus.json",
        corpus_sha256=corpus_sha,
        corpus_manifest_sha256=c.sha(ROOT / "results/2026-10-26-lift-selection-corpus/manifest.json"),
        source_bindings=bindings,
        folds="leave-one-workload-group-out; exclude every operation-tree family in target successes and failures from fit",
        candidate_order="ascending complete candidate_id within each held-out workload group",
        outcome_order="score public-only prediction, then condition on that candidate's verified numeric outcome; failed attempts stay charged and do not condition",
        interval_basis="future-observation covariance including fixed assumed alpha",
        charged_prefix="number of prior attempts including failures; successful_conditions_before is recorded separately",
        outputs=list(OUTPUT_FIELDS), fit_calls_expected=14, native_jobs=0,
        model_changes=0, claim="retrospective paid-prefix calibration diagnostic only")
    report = evaluate(corpus, corpus_sha)
    require(report["fit_calls"] == protocol["fit_calls_expected"],
            "Fit accounting differs from the frozen LOCO fold count")
    output.mkdir(parents=True)
    c.seal(output / "protocol.json", protocol)
    report["protocol_sha256"] = c.sha(output / "protocol.json")
    c.seal(output / "report.json", report)
    render_coverage_plot(report, output / "paid-prefix-coverage.png")
    lines = [
        "# Joint posterior paid-prefix calibration diagnostic",
        "",
        "**Retrospective development analysis.** The same fixed-joint posterior recipe is scored before each held-out candidate outcome and conditioned only after a verified success. The order is ascending candidate ID, not an active policy. The original zero-query calibration artifact is unchanged.",
        "",
        f"Authenticated input: 122 successful labels and four charged failures (`{corpus_sha}`).",
        f"Folds and model fits: {report['fold_count']} / {report['fit_calls']}. No native jobs or new measurements.",
        "",
        "## Pooled results by charged prefix",
        "",
        "Prefix means the number of earlier attempted candidates; failures count in the prefix but do not update the posterior.",
        "",
        "| Earlier charged attempts | n | Area 50/80/95% coverage | Fmax 50/80/95% coverage | Log time 50/80/95% coverage |",
        "|---:|---:|---|---|---|",
    ]
    for prefix, values in report["pooled_summary"]["by_charged_prefix"].items():
        columns = []
        for output_name in ("area_delta_lut4", "routed_fmax_min_mhz", "log_measurement_seconds"):
            coverage = values["outputs"][output_name]["coverage"]
            columns.append(" / ".join(f"{coverage[level]:.3f}" for level in ("50", "80", "95")))
        lines.append(f"| {prefix} | {values['n']} | {columns[0]} | {columns[1]} | {columns[2]} |")
    lines.extend(["", "![Observed interval coverage after each charged prefix](paid-prefix-coverage.png)",
        "", "## Limits", "", report["interpretation"], ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    (output / "results.md").write_text("\n".join(lines) + "\n")
    inventory = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob("*")) if path.is_file()}
    c.seal(output / "manifest.json", inventory)
    return report


def authenticate(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    inventory = c.unseal(output / "manifest.json")
    expected = {path.relative_to(output).as_posix(): c.sha(path)
                for path in sorted(output.rglob("*"))
                if path.is_file() and path.name not in
                ("manifest.json", "manifest.json.sha256")}
    require(inventory == expected, "Paid-prefix report inventory changed")
    protocol = c.unseal(output / "protocol.json")
    report = c.unseal(output / "report.json")
    require(protocol["source_bindings"] == source_bindings() and
            report["protocol_sha256"] == c.sha(output / "protocol.json") and
            report["fold_count"] == report["fit_calls"] == 14 and
            report["status"] == "retrospective_prequential_development_diagnostic_not_confirmatory",
            "Paid-prefix report provenance or fit accounting differs")
    return report


def render_coverage_plot(report, path):
    """Render a compact figure without implying independent confidence bars."""
    import matplotlib.pyplot as plt

    values = report["pooled_summary"]["by_charged_prefix"]
    prefixes = sorted(int(value) for value in values)
    nominal = ("50", "80", "95")
    colors = {"50": "#2878A8", "80": "#E07A24", "95": "#338A5E"}
    metrics = (("area_delta_lut4", "Added LUT4"),
               ("routed_fmax_min_mhz", "Minimum routed Fmax (MHz)"),
               ("log_measurement_seconds", "Log evaluation time"))
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 7.2), sharex=True,
                             constrained_layout=True)
    for axis, (metric, title) in zip(axes, metrics):
        for level in nominal:
            axis.axhline(float(level) / 100, color=colors[level],
                         linestyle=(0, (2, 2)), alpha=0.35, linewidth=1.1)
            coverage = [values[str(prefix)]["outputs"][metric]["coverage"][level]
                        for prefix in prefixes]
            axis.plot(prefixes, coverage, marker="o", markersize=4,
                      linewidth=1.6, color=colors[level],
                      label=f"{level}% nominal / observed")
        axis.set_title(title, loc="left", fontsize=11, weight="semibold")
        axis.set_ylim(-0.03, 1.04)
        axis.set_yticks((0, 0.25, 0.5, 0.75, 1.0),
                        labels=("0%", "25%", "50%", "75%", "100%"))
        axis.grid(axis="y", color="#DDE4EA", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xticks(prefixes, labels=[
        f"{prefix}\n(n={values[str(prefix)]['n']})" for prefix in prefixes])
    axes[-1].set_xlabel("Earlier charged attempts (failures count; no model update)")
    axes[0].legend(loc="lower left", ncol=3, frameon=False, fontsize=8.5)
    fig.suptitle("Fixed-joint uncertainty after paid-prefix conditioning",
                 fontsize=15, weight="bold", color="#17324D")
    fig.text(0.5, -0.01,
        "Retrospective LOCO development data; candidate-ID order, not policy-selected. "
        "Repeated candidates are dependent; no confidence intervals shown.",
        ha="center", fontsize=8.5, color="#607286")
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "authenticate", "render"), nargs="?", default="run")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.command == "run":
        report = run(args.output)
        print(json.dumps(dict(output=str(args.output), folds=report["fold_count"],
            fits=report["fit_calls"], pooled=report["pooled_summary"]["by_charged_prefix"]), indent=2))
    elif args.command == "render":
        report = authenticate(args.output)
        output = Path(args.output).resolve()
        render_coverage_plot(report, output / "paid-prefix-coverage.png")
        results = output / "results.md"
        content = results.read_text()
        if "paid-prefix-coverage.png" not in content:
            content = content.replace("## Limits\n",
                "![Observed interval coverage after each charged prefix](paid-prefix-coverage.png)\n\n## Limits\n")
            results.write_text(content)
        inventory = {path.relative_to(output).as_posix(): c.sha(path)
                     for path in sorted(output.rglob("*"))
                     if path.is_file() and path.name not in
                     ("manifest.json", "manifest.json.sha256")}
        c.seal(output / "manifest.json", inventory)
        authenticate(output)
        print(json.dumps(dict(rendered=str(output / "paid-prefix-coverage.png"), authenticated=True)))
    else:
        report = authenticate(args.output)
        print(json.dumps(dict(authenticated=True, folds=report["fold_count"],
            fits=report["fit_calls"]), indent=2))


if __name__ == "__main__":
    main()

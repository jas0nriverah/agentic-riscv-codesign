"""Nested, workload-grouped variance calibration for fixed-joint hardware GPs.

Retrospective development diagnostic only. For each outer held-out workload,
estimate one output- and paid-prefix-specific variance multiplier from inner
leave-workload-group-out prequential residuals. Neither the outer workload nor
its operation-tree families enter the base fit or calibration fit. The method
does not change a predictor, choose a policy, or use target results to select a
calibration factor.
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

import numpy as np
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b, codesign as c
from isaforge import joint_hardware as joint, semantic_selection as semantic, speedup_corpus
from scripts import audit_joint_paid_prefix_calibration as paid
from scripts import audit_joint_posterior_calibration as prior

SOURCE = "scripts/audit_nested_joint_uncertainty_scaling.py"
DEFAULT_OUTPUT = ROOT / "results/2026-10-27-nested-joint-uncertainty-scaling-r3"
OUTPUTS = tuple(prior.OUTPUT_FIELDS)
PREFIXES = (0, 1, 2)
AREA_CAP = 64.0
CLOCK_MHZ = 12.0
MIN_CALIBRATION_GROUPS = 5
INTERVALS = prior.INTERVALS
SOURCES = tuple(dict.fromkeys((SOURCE, *paid.SOURCES, *prior.SOURCES, *joint.SOURCES)))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def variance_scales(group_z: dict[str, dict[int, dict[str, list[float]]]], *,
                    minimum_groups: int = MIN_CALIBRATION_GROUPS) -> dict[int, dict[str, float]]:
    """Return group-balanced E[z^2] by charged-attempt prefix and output.

    Each workload group contributes its within-group mean squared standardized
    residual once, so candidate-rich groups cannot dominate. The returned value
    multiplies predictive variance (and therefore divides standardized residuals
    by its square root). This is a fixed formula, not a searched hyperparameter.
    """
    require(type(minimum_groups) is int and minimum_groups > 0,
            "Positive minimum calibration group count required")
    result: dict[int, dict[str, float]] = {}
    for prefix in PREFIXES:
        result[prefix] = {}
        for output in OUTPUTS:
            group_means = []
            for group in sorted(group_z):
                values = group_z[group].get(prefix, {}).get(output, [])
                if values:
                    values = [float(value) for value in values]
                    require(all(math.isfinite(value) for value in values),
                            "Finite inner-fold standardized residuals required")
                    group_means.append(float(np.mean(np.square(values))))
            require(len(group_means) >= minimum_groups,
                    f"Insufficient independent calibration groups at prefix {prefix} for {output}")
            scale = float(np.mean(group_means))
            require(math.isfinite(scale) and scale > 0,
                    "Positive finite variance calibration factor required")
            result[prefix][output] = scale
    return result


def split_outer(successes: list[dict], failures: list[dict], held_out: str):
    training, target, target_failures, families = prior.split_groups(
        successes, failures, held_out)
    outer_training_groups = {row["workload_group"] for row in training}
    outer_failures = [row for row in failures
                      if row["workload_group"] in outer_training_groups
                      and speedup_corpus.family(row["formula"]) not in set(families)]
    return training, target, target_failures, families, outer_failures


def fit_posterior(training: list[dict], attempts: list[dict]):
    require(training and attempts, "Nonempty fitting history and target pool required")
    public = paid.public_projection(attempts)
    fitted = semantic.SemanticHardwareSurrogate().fit(training)
    return joint.JointHardwarePosterior.from_fitted(fitted, training, public), public


def calibration_for_outer(successes: list[dict], failures: list[dict], outer_group: str,
                          outer_training: list[dict], outer_failures: list[dict]):
    group_z: dict[str, dict[int, dict[str, list[float]]]] = {}
    inner_folds = []
    fits = 0
    eligible_groups = sorted({row["workload_group"] for row in outer_training})
    require(outer_group not in eligible_groups, "Outer held-out group leaked into calibration")
    for inner_group in eligible_groups:
        inner_training, inner_target, inner_failures, inner_families = prior.split_groups(
            outer_training, outer_failures, inner_group)
        require(outer_group not in {row["workload_group"] for row in inner_training},
                "Outer workload leaked into nested training")
        outer_families = {speedup_corpus.family(row["formula"]) for row in
                          [*successes, *failures]
                          if row["workload_group"] == outer_group}
        inner_target_families = {speedup_corpus.family(row["formula"])
                                 for row in [*inner_target, *inner_failures]}
        require(not outer_families.intersection(
                    speedup_corpus.family(row["formula"]) for row in inner_training),
                "Outer operation family leaked into nested training")
        require(not inner_target_families.intersection(
                    speedup_corpus.family(row["formula"]) for row in inner_training),
                "Inner held-out operation family leaked into nested training")
        attempts = sorted([*inner_target, *inner_failures],
                          key=lambda row: row["candidate_id"])
        posterior, _ = fit_posterior(inner_training, attempts)
        records, final_state = paid.prequential_sequence(
            posterior, attempts, inner_target, workload_group=inner_group)
        fits += 1
        require(len(final_state.observed_ids) == len(inner_target),
                "Every inner verified success must condition exactly once")
        group_z[inner_group] = {prefix: {output: [] for output in OUTPUTS}
                                for prefix in PREFIXES}
        for record in records:
            if record["status"] != "success":
                continue
            prefix = record["charged_attempts_before"]
            if prefix not in PREFIXES:
                continue
            for output in OUTPUTS:
                group_z[inner_group][prefix][output].append(
                    record[output]["standardized_residual"])
        inner_folds.append(dict(workload_group=inner_group,
            training_count=len(inner_training), target_success_count=len(inner_target),
            target_failure_count=len(inner_failures),
            excluded_families=inner_families,
            training_ids=[row["candidate_id"] for row in inner_training],
            attempt_ids=[row["candidate_id"] for row in attempts],
            posterior_sha256=final_state.snapshot()["posterior_state_sha256"],
            scored_successes=sum(row["status"] == "success" for row in records)))
    return variance_scales(group_z), group_z, inner_folds, fits


def _brier(rows: list[dict], output_name: str) -> float:
    return float(np.mean([(row[output_name] - row["hardware_feasible"]) ** 2
                          for row in rows]))


def paired_group_bootstrap(group_brier: dict[str, dict], *, iterations: int = 20_000,
                           seed: int = 20261027) -> dict:
    """Descriptive paired resampling of whole workload groups, never rows."""
    require(type(iterations) is int and iterations >= 1, "Positive bootstrap count required")
    names = sorted(group_brier)
    require(len(names) >= 2, "At least two workload groups required")
    base = np.asarray([group_brier[name]["base"] for name in names], dtype=float)
    calibrated = np.asarray([group_brier[name]["nested_calibrated"] for name in names], dtype=float)
    counts = np.asarray([group_brier[name]["n"] for name in names], dtype=float)
    delta = calibrated - base
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(names), size=(iterations, len(names)))
    macro = delta[indices].mean(axis=1)
    weighted = (delta[indices] * counts[indices]).sum(axis=1) / counts[indices].sum(axis=1)
    def summary(values, point_estimate):
        return dict(point_estimate=float(point_estimate),
            percentile_95_interval=[float(value) for value in np.quantile(values, [0.025, 0.975])],
            bootstrap_fraction_below_zero=float(np.mean(values < 0)))
    return dict(unit="whole workload group", iterations=iterations, seed=seed,
        sign_convention="nested-calibrated Brier minus base Brier; negative favors calibration",
        macro=summary(macro, float(delta.mean())),
        candidate_weighted=summary(weighted, float((delta*counts).sum()/counts.sum())))


def _coverage(records: list[dict], mode: str):
    values = {output: [] for output in OUTPUTS}
    by_group: dict[str, dict[str, list[float]]] = {}
    for row in records:
        group = row["workload_group"]
        by_group.setdefault(group, {output: [] for output in OUTPUTS})
        for output in OUTPUTS:
            q = (1.0 if mode == "base" else
                 row["calibration_variance_scale_by_output"][output])
            z = row[output]["residual"] / (row[output]["predictive_std"] * math.sqrt(q))
            values[output].append(z)
            by_group[group][output].append(z)
    summary = {}
    for output, standardized in values.items():
        summary[output] = prior.interval_metrics(standardized)
        summary[output]["workload_macro_coverage"] = {
            level: float(np.mean([prior.interval_metrics(group_values[output])["coverage"][level]
                                  for group_values in by_group.values()]))
            for level in INTERVALS}
    return summary


def score_outer_group(successes: list[dict], failures: list[dict], held_out: str,
                      training: list[dict], target: list[dict], target_failures: list[dict],
                      q_by_prefix: dict[int, dict[str, float]]):
    attempts = sorted([*target, *target_failures], key=lambda row: row["candidate_id"])
    posterior, _ = fit_posterior(training, attempts)
    success_by_id = {row["candidate_id"]: row for row in target}
    records = []
    device_alpha, device_beta = posterior.device_fit_alpha, posterior.device_fit_beta
    for attempt_index, attempt in enumerate(attempts):
        identity = attempt["candidate_id"]
        prediction = posterior.joint([identity])
        prefix = min(attempt_index, PREFIXES[-1])
        row = dict(candidate_id=identity, workload_group=held_out,
            attempt_index=attempt_index, charged_attempts_before=attempt_index,
            successful_conditions_before=len(posterior.observed_ids),
            status=attempt.get("status", "success" if identity in success_by_id else "failed"))
        row["calibration_variance_scale_by_output"] = copy.deepcopy(q_by_prefix[prefix])
        for output in OUTPUTS:
            marginal = prediction["outputs"][output]
            mean = float(marginal["mean"][0])
            base_std = math.sqrt(float(marginal["observation_covariance"][0][0]))
            require(math.isfinite(mean) and math.isfinite(base_std) and base_std > 0,
                    "Positive finite outer predictive standard deviation required")
            row[output] = dict(predicted_mean=mean, predictive_std=base_std)
        outcome = success_by_id.get(identity)
        if outcome is None:
            require(row["status"] == "failed", "Unknown target outcome must remain a charged failure")
            row["conditioned_after_score"] = False
            records.append(row)
            continue
        require(row["status"] == "success", "Target success status must match the outcome map")
        for output, value_of in prior.OUTPUT_FIELDS.items():
            observed = float(value_of(outcome))
            estimate = row[output]["predicted_mean"]
            row[output].update(observed=observed, residual=observed-estimate)
        row["hardware_feasible"] = int(b._feasible(outcome, AREA_CAP, CLOCK_MHZ))
        row["device_fit_probability"] = device_alpha / (device_alpha + device_beta)
        for method in ("base", "nested_calibrated"):
            q = ({output: 1.0 for output in OUTPUTS} if method == "base"
                 else q_by_prefix[prefix])
            area = row["area_delta_lut4"]
            fmax = row["routed_fmax_min_mhz"]
            area_std = area["predictive_std"] * math.sqrt(q["area_delta_lut4"])
            fmax_std = fmax["predictive_std"] * math.sqrt(q["routed_fmax_min_mhz"])
            p_area = float(ndtr((AREA_CAP-area["predicted_mean"])/area_std))
            p_timing = float(ndtr((fmax["predicted_mean"]-CLOCK_MHZ)/fmax_std))
            row[method+"_feasibility_probability"] = p_area*p_timing*row["device_fit_probability"]
        posterior = posterior.condition(outcome, queried_id=identity)
        device_alpha = posterior.device_fit_alpha
        device_beta = posterior.device_fit_beta
        row["conditioned_after_score"] = True
        records.append(row)
    return records, posterior


def summarize(successes: list[dict], failures: list[dict], corpus_sha: str):
    groups = sorted({row["workload_group"] for row in successes})
    folds = []
    total_inner_fits = 0
    total_calibration_seconds = 0.0
    total_outer_fit_seconds = 0.0
    for held_out in groups:
        training, target, target_failures, families, outer_failures = split_outer(
            successes, failures, held_out)
        started = time.perf_counter()
        q_by_prefix, group_z, inner_folds, inner_fits = calibration_for_outer(
            successes, failures, held_out, training, outer_failures)
        total_calibration_seconds += time.perf_counter() - started
        total_inner_fits += inner_fits
        attempts = sorted([*target, *target_failures], key=lambda row: row["candidate_id"])
        started = time.perf_counter()
        records, final_state = score_outer_group(successes, failures, held_out,
            training, target, target_failures, q_by_prefix)
        total_outer_fit_seconds += time.perf_counter()-started
        require(len(final_state.observed_ids) == len(target),
                "Every outer verified success must condition exactly once")
        folds.append(dict(workload_group=held_out, training_count=len(training),
            target_success_count=len(target), target_failure_count=len(target_failures),
            excluded_families=families, training_ids=[row["candidate_id"] for row in training],
            calibration_scales={str(prefix): q_by_prefix[prefix] for prefix in PREFIXES},
            calibration_group_counts={str(prefix): {
                output: sum(bool(group_z[group][prefix][output]) for group in group_z)
                for output in OUTPUTS} for prefix in PREFIXES},
            nested_fit_count=inner_fits,
            nested_folds=inner_folds, scored_candidate_records=records,
            final_posterior_sha256=final_state.snapshot()["posterior_state_sha256"]))

    all_success_records = [record for fold in folds for record in fold["scored_candidate_records"]
                           if record["status"] == "success" and
                           record["attempt_index"] < len(PREFIXES)]
    base_coverage = _coverage(all_success_records, "base")
    calibrated_coverage = _coverage(all_success_records, "nested_calibrated")
    # Keep outer-fold calibration maps separate because factors are fold-specific.
    base_probabilities = [row["base_feasibility_probability"] for row in all_success_records]
    calibrated_probabilities = [row["nested_calibrated_feasibility_probability"]
                                for row in all_success_records]
    labels = [row["hardware_feasible"] for row in all_success_records]
    brier = dict(n=len(labels), positives=sum(labels),
        base=float(np.mean((np.asarray(base_probabilities)-np.asarray(labels))**2)),
        nested_calibrated=float(np.mean((np.asarray(calibrated_probabilities)-np.asarray(labels))**2)))
    group_brier = {}
    for fold in folds:
        rows = [row for row in fold["scored_candidate_records"] if row["status"] == "success"]
        group_brier[fold["workload_group"]] = dict(n=len(rows),
            positives=sum(row["hardware_feasible"] for row in rows),
            base=_brier(rows, "base_feasibility_probability"),
            nested_calibrated=_brier(rows, "nested_calibrated_feasibility_probability"))
    brier["workload_macro_base"] = float(np.mean([value["base"] for value in group_brier.values()]))
    brier["workload_macro_nested_calibrated"] = float(np.mean(
        [value["nested_calibrated"] for value in group_brier.values()]))
    brier_bootstrap = paired_group_bootstrap(group_brier)
    prefix_metrics = {}
    for prefix in PREFIXES:
        rows = [row for row in all_success_records if row["attempt_index"] == prefix]
        if not rows:
            continue
        prefix_metrics[str(prefix)] = dict(n=len(rows), outputs={})
        for output in OUTPUTS:
            base_z = [row[output]["residual"]/row[output]["predictive_std"] for row in rows]
            calibrated_z = []
            for fold in folds:
                q = fold["calibration_scales"][str(prefix)][output]
                calibrated_z.extend(row[output]["residual"] /
                    (row[output]["predictive_std"]*math.sqrt(q))
                    for row in fold["scored_candidate_records"]
                    if row["status"] == "success" and row["attempt_index"] == prefix)
            prefix_metrics[str(prefix)]["outputs"][output] = dict(
                base=prior.interval_metrics(base_z),
                nested_calibrated=prior.interval_metrics(calibrated_z))
    return dict(schema="isaforge-nested-joint-uncertainty-scaling-v1",
        status="retrospective_consumed_data_nested_grouped_diagnostic_not_confirmatory",
        corpus_sha256=corpus_sha,
        successful_labels=len(successes), charged_failures=len(failures),
        outer_workload_groups=len(groups), outer_fit_count=len(groups),
        inner_fit_count=total_inner_fits, total_fit_count=len(groups)+total_inner_fits,
        nested_calibration_formula="per-output and prior-charged-attempt-count variance scale = equal-workload mean of inner-LOCO prequential z^2; failures consume a prefix and do not condition",
        minimum_calibration_groups=MIN_CALIBRATION_GROUPS, outputs=list(OUTPUTS),
        prior_charged_attempt_prefixes=list(PREFIXES), fixed_hardware_limits=dict(area_cap_lut4=AREA_CAP,
            minimum_routed_fmax_mhz=CLOCK_MHZ), native_jobs=0, new_measurements=0,
        policy_comparison=False, area_timing_feasibility_brier=brier,
        area_timing_feasibility_brier_group_bootstrap=brier_bootstrap,
        area_timing_feasibility_brier_by_workload=group_brier,
        pooled_interval_metrics=dict(base=base_coverage,nested_calibrated=calibrated_coverage),
        paid_prefix_interval_metrics=prefix_metrics, folds=folds,
        total_nested_calibration_seconds=total_calibration_seconds,
        total_outer_fit_and_scoring_seconds=total_outer_fit_seconds,
        limitations=[
            "All outcomes are from the consumed 122-success/four-failure engineering corpus; this is not confirmatory.",
            "Nested leave-one-workload-group-out and operation-family exclusion prevent the outer target labels and families from entering either base fitting or calibration.",
            "Candidate-ID order is a fixed retrospective sequence, not a live or simulated active-selection policy.",
            "The variance multiplier rescales predictive variances only; it does not correct conditional-mean bias, estimate cross-output covariance, or calibrate correctness/infrastructure failure risk.",
            "Brier and interval summaries use observed successful numeric outcomes only; all failed attempts remain charged and are not imputed.",
            "The engineering workload groups are few and selected; these estimates do not establish exchangeability, population calibration, or future selection gain.",
            "No model, policy, source outcome, or native measurement was changed; a prospective source-family holdout with matched myopic controls is still required before promotion.",
        ])


def source_bindings():
    return {name: c.sha(ROOT / name) for name in SOURCES}


def build(output: Path = DEFAULT_OUTPUT):
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and not output.exists(),
            "Use a fresh repository-local output directory")
    corpus_path = ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json"
    corpus, successes, failures, corpus_sha = prior._read_corpus(corpus_path)
    require(len(successes) == 122 and len(failures) == 4,
            "Exact authenticated consumed development corpus required")
    protocol = dict(schema="isaforge-nested-joint-uncertainty-scaling-protocol-v1",
        status="post_hoc_retrospective_not_preregistered",
        corpus_path=corpus_path.relative_to(ROOT).as_posix(), corpus_sha256=corpus_sha,
        corpus_manifest_sha256=c.sha(corpus_path.parent/"manifest.json"),
        source_bindings=source_bindings(),
        outer_split="leave-one-workload-group-out; exclude every target success/failure operation-tree family",
        calibration_split="within each outer training cohort, leave one eligible workload group out and exclude its success/failure operation-tree families",
        calibration_method="one fixed variance multiplier per output and number of prior charged attempts (0, 1, or 2); equal-weight mean group-level prequential standardized residual square",
        candidate_order="ascending complete candidate_id; predict before each of the first three charged attempts; failures consume budget and only verified successes condition the posterior",
        training_only=True, minimum_independent_calibration_groups=MIN_CALIBRATION_GROUPS,
        outputs=list(OUTPUTS), prior_charged_attempt_prefixes=list(PREFIXES),
        native_jobs=0, new_measurements=0, policy_comparison=False,
        claim="nested calibration diagnostic only; no promotion or superiority claim",
        packages={name: importlib.metadata.version(name)
                  for name in ("numpy", "scipy", "scikit-learn", "matplotlib")})
    report = summarize(successes, failures, corpus_sha)
    report["source_bindings"] = source_bindings()
    output.mkdir(parents=True)
    c.seal(output / "protocol.json", protocol)
    report["protocol_sha256"] = c.sha(output / "protocol.json")
    c.seal(output / "report.json", report)
    _render_plots(report, output)
    _render_markdown(protocol, report, output / "results.md")
    inventory = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob("*")) if path.is_file()
                 and path.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output / "manifest.json", inventory)
    return report


def _render_markdown(protocol: dict, report: dict, path: Path):
    lines = [
        "# Nested joint-posterior uncertainty scaling",
        "",
        "**Retrospective development diagnostic; no policy or model promoted.** The variance multiplier is estimated only from nested, source-family-excluded workload-group folds. The held-out outer workload contributes no labels to either the base fit or calibration factor.",
        "",
        f"Input: {report['successful_labels']} verified outcomes and {report['charged_failures']} charged failures across {report['outer_workload_groups']} workload groups. The nested analysis used {report['total_fit_count']} total fits ({report['inner_fit_count']} inner calibration fits). No native jobs or new measurements.",
        "",
        "## Feasibility score",
        "",
        "| Metric | Base fixed-joint | Nested variance-calibrated |",
        "|---|---:|---:|",
        f"| Candidate-weighted Brier score, n={report['area_timing_feasibility_brier']['n']} | {report['area_timing_feasibility_brier']['base']:.4f} | {report['area_timing_feasibility_brier']['nested_calibrated']:.4f} |",
        f"| Equal-workload macro Brier | {report['area_timing_feasibility_brier']['workload_macro_base']:.4f} | {report['area_timing_feasibility_brier']['workload_macro_nested_calibrated']:.4f} |",
        "",
        f"Paired whole-workload bootstrap (20,000 resamples): macro Brier difference calibrated−base `{report['area_timing_feasibility_brier_group_bootstrap']['macro']['point_estimate']:+.4f}` with descriptive 95% interval `{report['area_timing_feasibility_brier_group_bootstrap']['macro']['percentile_95_interval'][0]:+.4f}` to `{report['area_timing_feasibility_brier_group_bootstrap']['macro']['percentile_95_interval'][1]:+.4f}`; candidate-weighted difference `{report['area_timing_feasibility_brier_group_bootstrap']['candidate_weighted']['point_estimate']:+.4f}` with interval `{report['area_timing_feasibility_brier_group_bootstrap']['candidate_weighted']['percentile_95_interval'][0]:+.4f}` to `{report['area_timing_feasibility_brier_group_bootstrap']['candidate_weighted']['percentile_95_interval'][1]:+.4f}`. These intervals describe resampling of this selected engineering corpus, not a workload population.",
        "",
        "## Interval calibration by charged-attempt prefix",
        "",
        "Entries are 50% / 80% / 95% interval coverage. Prefix 0, 1, or 2 means prior charged attempts, including failures. Each outer workload uses factors estimated from the other groups only. Only the first three attempts per group enter the budget-three diagnostic.",
        "",
        "| Prior charged attempts | Output | Base coverage | Calibrated coverage |",
        "|---:|---|---|---|",
    ]
    for prefix, metrics in report["paid_prefix_interval_metrics"].items():
        for output in OUTPUTS:
            base = metrics["outputs"][output]["base"]["coverage"]
            cal = metrics["outputs"][output]["nested_calibrated"]["coverage"]
            values_base = " / ".join(f"{base[level]:.3f}" for level in ("50", "80", "95"))
            values_cal = " / ".join(f"{cal[level]:.3f}" for level in ("50", "80", "95"))
            lines.append(f"| {prefix} | {output} | {values_base} | {values_cal} |")
    lines.extend(["", "## Learned variance factors", "",
        "Factors multiply predictive variance, not standard deviation. One source/workload group contributes once to each estimate.",
        "", "| Prior charged attempts | Output | Median q | Min q | Max q |",
        "|---:|---|---:|---:|---:|"])
    for prefix in PREFIXES:
        for output in OUTPUTS:
            q = [fold["calibration_scales"][str(prefix)][output] for fold in report["folds"]]
            lines.append(f"| {prefix} | {output} | {float(np.median(q)):.3f} | {min(q):.3f} | {max(q):.3f} |")
    lines.extend(["", "## Limits", ""])
    lines.extend("- " + value for value in report["limitations"])
    lines.extend(["", "## Figures", "",
        "![Per-workload change in area/timing feasibility Brier score](feasibility-brier-by-workload.png)", "",
        "![80% predictive interval coverage at charged-attempt prefixes 0–2](interval-coverage-by-paid-prefix.png)"])
    path.write_text("\n".join(lines) + "\n")


def _render_plots(report: dict, output: Path):
    import matplotlib.pyplot as plt

    group_rows = report["area_timing_feasibility_brier_by_workload"]
    names = sorted(group_rows, key=lambda name:
                   group_rows[name]["nested_calibrated"]-group_rows[name]["base"])
    deltas = [group_rows[name]["nested_calibrated"]-group_rows[name]["base"]
              for name in names]
    colors = ["#16877A" if delta < 0 else "#D66B46" for delta in deltas]
    labels = [name.replace("-", "/", 1) for name in names]
    fig, axis = plt.subplots(figsize=(10.5, 6.6), constrained_layout=True)
    y = np.arange(len(names))
    axis.barh(y, deltas, color=colors, edgecolor="white", linewidth=0.5)
    axis.axvline(0, color="#17324D", linewidth=1.1)
    axis.set_yticks(y, labels=labels, fontsize=9)
    axis.set_xlabel("Δ Brier (nested-calibrated − base; lower is better)")
    axis.set_title("Feasibility probability score change by held-out workload",
                   loc="left", fontsize=14, weight="bold", color="#17324D")
    axis.grid(axis="x", color="#DDE4EA", linewidth=0.7)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)
    axis.invert_yaxis()
    fig.text(0.01, -0.01,
        "Positive bars mean nested variance scaling worsened the Brier score. Whole-workload holdouts; 122 consumed outcomes.",
        fontsize=8.5, color="#607286")
    fig.savefig(output / "feasibility-brier-by-workload.png", dpi=180,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

    coverage_by_prefix = report["paid_prefix_interval_metrics"]
    prefixes = sorted(int(prefix) for prefix in coverage_by_prefix)
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 8.4), sharex=True,
                             constrained_layout=True)
    palette = {"base": "#2878A8", "nested_calibrated": "#D66B46"}
    titles = {"area_delta_lut4": "Added LUT4",
              "routed_fmax_min_mhz": "Minimum routed Fmax (MHz)",
              "log_measurement_seconds": "Log evaluation time"}
    for axis, output_name in zip(axes, OUTPUTS):
        axis.axhline(0.8, color="#17324D", linestyle=(0, (4, 3)),
                     linewidth=1.1, label="80% nominal")
        for method in ("base", "nested_calibrated"):
            metric = [coverage_by_prefix[str(prefix)]["outputs"][output_name][method]
                      ["coverage"]["80"] for prefix in prefixes]
            axis.plot(prefixes, metric, marker="o", markersize=5, linewidth=1.8,
                      color=palette[method], label=("Base" if method == "base"
                      else "Nested variance scaling"))
        axis.set_title(titles[output_name], loc="left", fontsize=11,
                       weight="semibold", color="#17324D")
        axis.set_ylim(-0.03, 1.04)
        axis.set_yticks((0, .25, .5, .75, 1), labels=("0%", "25%", "50%", "75%", "100%"))
        axis.grid(axis="y", color="#DDE4EA", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(loc="lower left", ncol=3, frameon=False, fontsize=8.5)
    axes[-1].set_xticks(prefixes, labels=[
        f"{prefix} prior charge(s)\n(n={sum(row['status'] == 'success' and row['attempt_index'] == prefix for fold in report['folds'] for row in fold['scored_candidate_records'])})"
        for prefix in prefixes])
    axes[-1].set_xlabel("Number of earlier charged attempts (failures consume budget without conditioning)")
    fig.suptitle("80% interval coverage after paid-prefix updates",
                 fontsize=15, weight="bold", color="#17324D")
    fig.text(0.5, -0.005,
        "Nested leave-workload-group-out development diagnostic; candidate-ID order, not active selection.",
        ha="center", fontsize=8.5, color="#607286")
    fig.savefig(output / "interval-coverage-by-paid-prefix.png", dpi=180,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


def authenticate(output: Path = DEFAULT_OUTPUT):
    output = Path(output).resolve()
    inventory = c.unseal(output / "manifest.json")
    expected = {path.relative_to(output).as_posix(): c.sha(path)
                for path in sorted(output.rglob("*")) if path.is_file()
                and path.name not in ("manifest.json", "manifest.json.sha256")}
    require(inventory == expected, "Nested calibration artifact inventory differs")
    protocol = c.unseal(output / "protocol.json")
    report = c.unseal(output / "report.json")
    require(protocol["source_bindings"] == source_bindings() and
            report["protocol_sha256"] == c.sha(output / "protocol.json") and
            report["outer_workload_groups"] == 14 and
            report["charged_failures"] == 4 and report["native_jobs"] == 0,
            "Nested calibration provenance or experiment counts differ")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "authenticate"), nargs="?", default="run")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = build(args.output) if args.command == "run" else authenticate(args.output)
    print(json.dumps(dict(status=report["status"],successful_labels=report["successful_labels"],
        failures=report["charged_failures"],outer_groups=report["outer_workload_groups"],
        fits=report["total_fit_count"],brier=report["area_timing_feasibility_brier"],
        output=str(Path(args.output).resolve())),sort_keys=True))


if __name__ == "__main__":
    main()

"""Exploratory whole-workload calibration audit for the frozen joint GP.

This does not change or select a model. It evaluates the existing fixed-joint
posterior on consumed successful outcomes using whole-workload and operation-
family exclusions, and records uncertainty calibration plus the implied
area/timing feasibility probability. The corpus is development evidence.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.special import ndtr
from scipy.stats import pearsonr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b, codesign as c
from isaforge import joint_hardware as joint, semantic_selection as semantic
from isaforge import speedup_corpus

SOURCE = "scripts/audit_joint_posterior_calibration.py"
SOURCES = (
    SOURCE,
    "isaforge/joint_hardware.py",
    "isaforge/semantic_selection.py",
    "isaforge/budgeted_selection.py",
    "isaforge/speedup_corpus.py",
    "isaforge/codesign.py",
)
DEFAULT_CORPUS = ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json"
DEFAULT_OUTPUT = ROOT / "results/2026-10-26-joint-posterior-calibration"
AREA_CAP = 64
CLOCK_MHZ = 12.0
INTERVALS = {"50": 0.6744897501960817, "80": 1.2815515655446004,
             "95": 1.959963984540054}
OUTPUT_FIELDS = {
    "area_delta_lut4": lambda row: float(row["area_delta_lut4"]),
    "routed_fmax_min_mhz": lambda row: float(row["routed_fmax_min_mhz"]),
    "log_measurement_seconds": lambda row: math.log(float(row["measurement_seconds"])),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bindings():
    return {name: c.sha(ROOT / name) for name in SOURCES}


def interval_metrics(z_values):
    z = np.asarray(z_values, dtype=float)
    require(z.ndim == 1 and len(z) > 0 and np.isfinite(z).all(),
            "Finite nonempty standardized residual vector required")
    return dict(n=len(z), median_absolute_z=float(np.median(np.abs(z))),
        standardized_rmse=float(np.sqrt(np.mean(z*z))),
        coverage={level: float(np.mean(np.abs(z) <= cutoff))
                  for level, cutoff in INTERVALS.items()})


def feasible_probability(area_mean, area_std, fmax_mean, fmax_std, device_fit_probability,
                         *, area_cap=AREA_CAP, clock_mhz=CLOCK_MHZ):
    values = (area_mean, area_std, fmax_mean, fmax_std, device_fit_probability,
              area_cap, clock_mhz)
    require(all(math.isfinite(float(value)) for value in values) and
        area_std >= 0 and fmax_std >= 0 and 0 <= device_fit_probability <= 1,
        "Finite posterior feasibility inputs required")
    p_area = float(ndtr((area_cap-area_mean)/area_std)) if area_std else float(area_mean <= area_cap)
    p_timing = float(ndtr((fmax_mean-clock_mhz)/fmax_std)) if fmax_std else float(fmax_mean >= clock_mhz)
    return p_area*p_timing*device_fit_probability


def split_groups(successes, failures, held_out):
    target = [row for row in successes if row["workload_group"] == held_out]
    target_failures = [row for row in failures if row["workload_group"] == held_out]
    require(target, "Every held-out workload needs scored verified outcomes")
    excluded_families = {speedup_corpus.family(row["formula"])
                         for row in target + target_failures}
    training = [row for row in successes
                if row["workload_group"] != held_out
                and speedup_corpus.family(row["formula"]) not in excluded_families]
    require(training, "Family exclusion left an empty historical fitting cohort")
    target_ids = {row["candidate_id"] for row in target + target_failures}
    require(not target_ids & {row["candidate_id"] for row in training},
            "Target identity leaked into fitting rows")
    require(all(row["workload_group"] != held_out for row in training),
            "Held-out workload leaked into fitting rows")
    require(not ({speedup_corpus.family(row["formula"]) for row in training}
                 & excluded_families), "Target operation family leaked into fitting rows")
    return training, target, target_failures, sorted(excluded_families)


def _read_corpus(path):
    path = Path(path).resolve()
    digest = c.sha(path)
    sidecar = Path(str(path) + ".sha256")
    require(sidecar.is_file() and sidecar.read_text().strip() == digest,
            "Corpus sidecar digest mismatch")
    corpus_manifest_path = path.parent / "manifest.json"
    corpus_manifest = c.unseal(corpus_manifest_path)
    require(corpus_manifest.get(path.name) == digest and
            corpus_manifest.get(path.name + ".sha256") == c.sha(sidecar),
            "Corpus manifest does not bind the data and its digest sidecar")
    corpus = c.read(path)
    require(corpus.get("schema") == "isaforge-consumed-guarded-corpus-v1" and
        len(corpus.get("rows", [])) == 122 and len(corpus.get("failed_attempts", [])) == 4 and
        len(corpus.get("independent_workload_groups", [])) == 14,
        "The exact authenticated 122-label development corpus is required")
    successes = corpus["rows"]
    failures = corpus["failed_attempts"]
    require(len({row["candidate_id"] for row in successes+failures}) == 126,
            "Corpus candidate identities must be unique")
    for row in successes:
        require(b.validate_outcome(row), "Only complete verified success labels can be scored")
        require(row["candidate_family"] == speedup_corpus.family(row["formula"]),
                "Frozen candidate-family label differs from formula")
    for row in failures:
        require(row.get("status") == "failed" and "speedup" not in row and
            "area_delta_lut4" not in row and "routed_fmax_min_mhz" not in row,
            "Failures cannot be converted into model labels")
    require(sorted({row["workload_group"] for row in successes}) ==
            sorted(corpus["independent_workload_groups"]),
            "Corpus workload-group inventory differs")
    return corpus, successes, failures, digest


def _score_fold(group, training, target, target_failures, excluded_families):
    public = [{key: row[key] for key in b.PUBLIC_KEYS} for row in target]
    started = time.perf_counter()
    fitted = semantic.SemanticHardwareSurrogate().fit(training)
    posterior = joint.JointHardwarePosterior.from_fitted(fitted, training, public)
    fit_seconds = time.perf_counter()-started
    started = time.perf_counter()
    prediction = posterior.joint()
    prediction_seconds = time.perf_counter()-started

    standardized = {key: [] for key in OUTPUT_FIELDS}
    residual_vectors = {key: [] for key in OUTPUT_FIELDS}
    z_records = []
    feasibility_labels, feasibility_scores = [], []
    prior_scores = []
    for index, row in enumerate(target):
        record = {"candidate_id": row["candidate_id"], "workload_group": group}
        z_by_output = {}
        for output, value_of in OUTPUT_FIELDS.items():
            marginal = prediction["outputs"][output]
            mean = float(marginal["mean"][index])
            variance = float(marginal["observation_covariance"][index, index])
            require(math.isfinite(mean) and math.isfinite(variance) and variance > 0,
                    "Positive finite future-observation variance required")
            observed = value_of(row)
            residual = observed-mean
            z = residual/math.sqrt(variance)
            standardized[output].append(z)
            residual_vectors[output].append(residual)
            z_by_output[output] = z
            record[output] = dict(predicted_mean=mean, predictive_std=math.sqrt(variance),
                                  observed=observed, standardized_residual=z)

        area = prediction["outputs"]["area_delta_lut4"]
        fmax = prediction["outputs"]["routed_fmax_min_mhz"]
        area_std = math.sqrt(float(area["observation_covariance"][index, index]))
        fmax_std = math.sqrt(float(fmax["observation_covariance"][index, index]))
        probability = feasible_probability(float(area["mean"][index]), area_std,
            float(fmax["mean"][index]), fmax_std, posterior.device_fit_probability)
        label = int(b._feasible(row, AREA_CAP, CLOCK_MHZ))
        feasibility_labels.append(label)
        feasibility_scores.append(probability)
        prior_scores.append(posterior.device_fit_probability)
        record["hardware_feasible"] = label
        record["predicted_hardware_feasibility"] = probability
        record["training_only_device_fit_prior"] = posterior.device_fit_probability
        z_records.append(record)

    group_metrics = {key: interval_metrics(values) for key, values in standardized.items()}
    group_metrics["hardware_feasibility"] = dict(n=len(target), positive_count=sum(feasibility_labels),
        brier=float(np.mean((np.asarray(feasibility_scores)-feasibility_labels)**2)),
        prior_brier=float(np.mean((np.asarray(prior_scores)-feasibility_labels)**2)),
        mean_predicted_probability=float(np.mean(feasibility_scores)),
        observed_rate=float(np.mean(feasibility_labels)))
    return dict(workload_group=group, training_count=len(training), target_success_count=len(target),
        target_unknown_failure_count=len(target_failures), excluded_family_count=len(excluded_families),
        excluded_families=excluded_families, training_ids=[row["candidate_id"] for row in training],
        target_ids=[row["candidate_id"] for row in target], metrics=group_metrics,
        model_fit_seconds=fit_seconds, inference_seconds=prediction_seconds,
        fitted_training_digest=c.digest(training), public_features_digest=c.digest(public),
        scored_candidate_records=z_records)


def evaluate(corpus, successes, failures):
    folds = []
    for group in sorted({row["workload_group"] for row in successes}):
        training, target, target_failures, families = split_groups(successes, failures, group)
        folds.append(_score_fold(group, training, target, target_failures, families))
    all_records = [record for fold in folds for record in fold["scored_candidate_records"]]
    pooled = {}
    for key in OUTPUT_FIELDS:
        pooled[key] = interval_metrics([record[key]["standardized_residual"] for record in all_records])
        pooled[key]["workload_macro_coverage"] = {
            level: float(np.mean([fold["metrics"][key]["coverage"][level] for fold in folds]))
            for level in INTERVALS}
    labels = np.asarray([record["hardware_feasible"] for record in all_records], dtype=float)
    scores = np.asarray([record["predicted_hardware_feasibility"] for record in all_records], dtype=float)
    priors = np.asarray([record["training_only_device_fit_prior"] for record in all_records], dtype=float)
    pooled["hardware_feasibility"] = dict(n=len(labels), positive_count=int(labels.sum()),
        brier=float(np.mean((scores-labels)**2)),
        training_only_device_fit_prior_brier=float(np.mean((priors-labels)**2)),
        mean_predicted_probability=float(scores.mean()), observed_rate=float(labels.mean()),
        workload_macro_brier=float(np.mean([fold["metrics"]["hardware_feasibility"]["brier"]
                                            for fold in folds])))
    residuals = {key: np.asarray([record[key]["observed"]-record[key]["predicted_mean"]
                                  for record in all_records], dtype=float)
                 for key in OUTPUT_FIELDS}
    correlations = {}
    keys = tuple(OUTPUT_FIELDS)
    for left_index, left in enumerate(keys):
        for right in keys[left_index+1:]:
            correlations[left+"__"+right] = float(pearsonr(residuals[left], residuals[right]).statistic)
    return dict(schema="isaforge-joint-posterior-calibration-diagnostic-v1",
        status="retrospective_consumed_data_diagnostic_no_model_change", corpus_rows=len(successes),
        workload_group_count=len(folds), charged_failure_count=len(failures),
        failure_labels_used=0, target_failures_excluded_from_scoring=sum(f["target_unknown_failure_count"] for f in folds),
        target_outcomes_used_during_fit=0, fit_calls=len(folds), prediction_calls=len(folds),
        selection_policy_evaluated=False, native_jobs=0, new_measurements=0,
        model=dict(schema=joint.SCHEMA, update_rule=joint.UPDATE_RULE,
            noise_assumption=joint.NOISE_ASSUMPTION, future_observation_covariance=True,
            predictive_intervals=INTERVALS, feasibility_area_cap_lut4=AREA_CAP,
            feasibility_clock_mhz=CLOCK_MHZ,
            source_bindings=joint.source_bindings(),
            packages={name: importlib.metadata.version(name)
                      for name in ("numpy", "scipy", "scikit-learn")}),
        pooled_metrics=pooled, cross_output_raw_residual_correlations=correlations,
        folds=folds,
        limitations=[
            "All 122 successes and four failures are consumed development evidence; this is not confirmatory.",
            "Whole workload groups and matching operation-tree families are excluded from each fold, but the 14 engineering groups are not an exchangeable population.",
            "The 122 measured successes are scored; all four failures remain charged in the source corpus but have no numerical posterior labels and are excluded from scoring.",
            "Scoring covers the full historical public pools, not selection-conditioned candidate observations; acquisition calibration may differ.",
            "The three Gaussian outputs remain independent by model construction. Residual correlations are descriptive diagnostics, not a test of independence.",
            "Area/timing feasibility probabilities multiply marginal Gaussian probabilities and the fixed common Beta device-fit rate; this approximation is not a release safety guarantee.",
            "No model settings, feature definitions, selection rules, hardware constraints, or source outcomes were changed.",
            "No superiority, calibration guarantee, workload generalization, or active-learning improvement is claimed.",
        ])


def render(report, corpus_sha, source_sha):
    rows = []
    for output, values in report["pooled_metrics"].items():
        if output == "hardware_feasibility":
            rows.append(f"| {output} | {values['n']} | — | — | — | {values['brier']:.4f} | {values['training_only_device_fit_prior_brier']:.4f} |")
        else:
            coverage = values["coverage"]
            rows.append(f"| {output} | {values['n']} | {values['median_absolute_z']:.3f} | {values['standardized_rmse']:.3f} | {coverage['50']:.3f} / {coverage['80']:.3f} / {coverage['95']:.3f} | — | — |")
    corr = report["cross_output_raw_residual_correlations"]
    return "\n".join([
        "# Fixed-joint posterior calibration diagnostic — October 26, 2026", "",
        "**Exploratory retrospective diagnostic only.** The fixed-joint Gaussian update implementation and paid-observation semantics remain unchanged. This checks the existing model’s predictive uncertainty under 14 whole-workload/family-held-out folds on the consumed 122-success corpus. It does not tune or select a model and is not confirmatory.", "",
        f"Input corpus SHA-256: `{corpus_sha}`. Source contract SHA-256: `{source_sha}`. No target outcomes were used during fitting; no native jobs or new measurements were run. Four failed attempts stayed without numerical labels.", "",
        "| Output | Scored labels | Median |z| | Standardized RMSE | 50% / 80% / 95% interval coverage | Feasibility Brier | Training-only prior Brier |",
        "|---|---:|---:|---:|---:|---:|---:|", *rows, "",
        f"The model’s standardized residual correlations were area/Fmax `{corr['area_delta_lut4__routed_fmax_min_mhz']:.3f}`, area/log-time `{corr['area_delta_lut4__log_measurement_seconds']:.3f}`, and Fmax/log-time `{corr['routed_fmax_min_mhz__log_measurement_seconds']:.3f}`. They are descriptive, based on 122 selected engineering-corpus points; they do not establish cross-output independence.", "",
        "The feasibility Brier score uses `P(area ≤ +64 LUT4) × P(min Fmax ≥ 12 MHz) × P(device fit)` from independent Gaussian heads and the training-only Beta rate. The comparator is only the constant device-fit prior, so this is not a comparison against frequency, merit, XGBoost, or an oracle.", "",
        "The clearest calibration concern is log evaluation time: its standardized RMSE exceeds one and its 50% coverage is below nominal. Area and Fmax intervals are closer to nominal in this retrospective sample. These findings justify treating fixed GP uncertainty as provisional; they do not justify changing alpha or claiming improved selection. A future noise-policy change needs a fresh, predeclared held-out measurement cohort and a matched myopic control.", "",
        "Limitations: labels are consumed development data; failures are unscored unknowns; candidate queries are not selection-conditioned; workload groups are not exchangeable; and this audit does not test prospective acquisition or best verified feasible speedup.", "",
    ])


def build(corpus_path=DEFAULT_CORPUS, output=DEFAULT_OUTPUT):
    corpus_path = Path(corpus_path).resolve()
    output = Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(corpus_path.parent),
            "Use a fresh output directory separate from the sealed corpus")
    corpus, successes, failures, corpus_sha = _read_corpus(corpus_path)
    source_hashes = bindings()
    protocol = dict(schema="isaforge-joint-posterior-calibration-protocol-v1",
        status="post_hoc_retrospective_exploratory_not_preregistered",
        corpus_path=corpus_path.relative_to(ROOT).as_posix() if corpus_path.is_relative_to(ROOT) else str(corpus_path),
        corpus_sha256=corpus_sha, corpus_manifest_sha256=c.sha(corpus_path.parent/"manifest.json"),
        corpus_manifest_sidecar=(corpus_path.parent/"manifest.json.sha256").read_text().strip(),
        source_bindings=source_hashes, workload_split="leave-one-workload-group-out",
        formula_exclusion="exclude operation-tree families present in held-out successes and charged failures",
        train_labels="complete successful measured outcomes from other workload groups/families only",
        target_features="frozen public feature projection only",
        outputs=list(OUTPUT_FIELDS), interval_basis="future observation covariance (latent plus assumed alpha)",
        area_cap_lut4=AREA_CAP, clock_mhz=CLOCK_MHZ,
        feasibility_formula="independent Gaussian area and Fmax marginal probabilities times training-only Beta device-fit rate",
        scored_labels=len(successes), charged_failures=len(failures), native_jobs=0,
        model_fits=0, target_outcome_reads_during_fit=0, model_changes=0,
        claim="diagnostic only; no model selection, confirmation, or superiority claim")
    protocol["design_history"] = (
        "A one-off exploratory computation of the same LOCO split and metrics was run before this durable package was written. "
        "This package records the resulting diagnostic; it is explicitly not pre-registered or confirmatory.")
    report = evaluate(corpus, successes, failures)
    report["corpus_sha256"] = corpus_sha
    report["source_bindings"] = source_hashes
    output.mkdir(parents=True)
    c.seal(output/"protocol.json", protocol)
    c.seal(output/"report.json", report)
    markdown = render(report, corpus_sha, c.digest(source_hashes))
    (output/"results.md").write_text(markdown)
    inventory = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.iterdir()) if path.is_file() and
                 path.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output/"manifest.json", inventory)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.corpus, args.output)
    print(json.dumps(dict(status=report["status"], labels=report["corpus_rows"],
        folds=report["workload_group_count"], native_jobs=report["native_jobs"],
        output=str(Path(args.output).resolve())), sort_keys=True))


if __name__ == "__main__":
    main()

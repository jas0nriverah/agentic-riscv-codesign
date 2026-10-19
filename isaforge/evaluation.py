"""Benchmark-held-out evaluation of measured speedup predictors."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .features import FEATURE_COLUMNS
from .model import SpeedupPredictor, UNCERTAINTY_WARNING, validate_training_rows


def _metrics(truth: list[float], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    import numpy as np
    from scipy.stats import spearmanr

    observed = np.asarray(truth, dtype=float)
    predicted = np.asarray([row["mean"] for row in predictions], dtype=float)
    rank_correlation = None
    if len(truth) >= 2 and np.ptp(observed) > 0 and np.ptp(predicted) > 0:
        coefficient = float(spearmanr(observed, predicted).statistic)
        if math.isfinite(coefficient):
            rank_correlation = coefficient
    covered = [row["lower"] <= target <= row["upper"]
               for target, row in zip(truth, predictions)]
    widths = [row["upper"] - row["lower"] for row in predictions]
    return {
        "mae": float(np.mean(np.abs(observed - predicted))),
        "spearman": rank_correlation,
        "interval_coverage": float(np.mean(covered)),
        "mean_interval_width": float(np.mean(widths)),
        "test_size": len(truth),
    }


def leave_one_benchmark_out(
    rows: Sequence[Mapping[str, Any]], seed: int = 0, **predictor_options: Any
) -> dict[str, Any]:
    """Refit for every benchmark, excluding every row of that benchmark.

    Labels and features must use a single measurement source. Spearman is null
    for singleton folds or constant truth/predictions; it is never fabricated.
    """
    rows = list(rows)
    source = validate_training_rows(rows)
    for row in rows:
        if not isinstance(row.get("benchmark"), str) or not row["benchmark"].strip():
            raise ValueError("Every evaluation row needs a nonempty benchmark")
        if "candidate_id" not in row:
            raise ValueError("Every evaluation row needs candidate_id")
    benchmarks = sorted({row["benchmark"] for row in rows})
    if len(benchmarks) < 2:
        raise ValueError("Leave-one-benchmark-out evaluation requires at least two benchmarks")
    folds = []
    pooled_truth = []
    pooled_predictions = []
    warnings = [UNCERTAINTY_WARNING]
    for benchmark in benchmarks:
        train = [row for row in rows if row["benchmark"] != benchmark]
        test = [row for row in rows if row["benchmark"] == benchmark]
        model = SpeedupPredictor(seed=seed, **predictor_options).fit(train)
        predictions = model.predict(test)
        truth = [float(row["speedup"]) for row in test]
        folds.append({
            "held_out_benchmark": benchmark,
            "train_benchmarks": sorted({row["benchmark"] for row in train}),
            "train_size": len(train),
            "metrics": _metrics(truth, predictions),
            "predictions": [{**prediction, "observed_speedup": target}
                            for prediction, target in zip(predictions, truth)],
            "warnings": model.warnings,
        })
        pooled_truth.extend(truth)
        pooled_predictions.extend(predictions)
        warnings.extend(model.warnings)
    return {
        "method": "leave_one_benchmark_out",
        "seed": seed,
        "measurement_source": source,
        "synthetic": source == "synthetic",
        "interval_level": predictor_options.get("interval", 0.90),
        "feature_columns": list(FEATURE_COLUMNS),
        "folds": folds,
        "pooled_metrics": _metrics(pooled_truth, pooled_predictions),
        "warnings": list(dict.fromkeys(warnings)),
    }

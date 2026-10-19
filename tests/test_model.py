"""Regression and evaluation checks against leakage and misleading metrics."""

import json
import math

import pytest

from isaforge.evaluation import leave_one_benchmark_out
from isaforge.features import FEATURE_COLUMNS
from isaforge.model import SpeedupPredictor, feature_matrix


def measured_rows():
    rows = []
    for i in range(12):
        features = {column: float((i + j) % 7) for j, column in enumerate(FEATURE_COLUMNS)}
        rows.append({**features, "candidate_id": f"candidate-{i}",
                     "benchmark": f"kernel-{i // 4}", "formula": "add(in0,in1)",
                     "speedup": 1 + i / 10, "area": i + 1,
                     "measurement_source": "synthetic"})
    return rows


def test_reproducible_finite_predictions():
    rows = measured_rows()
    options = {"seed": 17, "ensemble_size": 5, "n_estimators": 10}
    first = SpeedupPredictor(**options).fit(rows).predict(rows)
    second = SpeedupPredictor(**options).fit(rows).predict(rows)
    assert first == second
    for prediction in first:
        assert all(math.isfinite(prediction[key]) for key in ("mean", "lower", "upper", "std"))
        assert prediction["lower"] <= prediction["upper"]
        assert prediction["std"] >= 0
    json.dumps(first, allow_nan=False)


def test_only_feature_allowlist_is_read():
    rows = measured_rows()
    altered = [{**row, "speedup": 98765, "area": -123,
                "baseline_cycles": 0, "candidate_cycles": 0,
                "measurement_source": "hardware", "benchmark": "changed",
                "secret_outcome": 444} for row in rows]
    assert feature_matrix(rows) == feature_matrix(altered)
    model = SpeedupPredictor(ensemble_size=3, n_estimators=5).fit(rows)
    assert model.predict(rows) == model.predict(altered)
    public = [{key: row[key] for key in (*FEATURE_COLUMNS, "candidate_id")} for row in rows]
    assert model.predict(rows) == model.predict(public)


def test_each_entire_benchmark_is_excluded(monkeypatch):
    rows = measured_rows()
    fits = []
    original_fit = SpeedupPredictor.fit

    def recording_fit(self, training):
        fits.append(list(training))
        return original_fit(self, training)

    monkeypatch.setattr(SpeedupPredictor, "fit", recording_fit)
    report = leave_one_benchmark_out(rows, seed=42, ensemble_size=3, n_estimators=5)
    assert len(report["folds"]) == 3
    for fold, train in zip(report["folds"], fits):
        benchmark = fold["held_out_benchmark"]
        assert all(row["benchmark"] != benchmark for row in train)
        assert len(train) == 8
        assert fold["train_size"] == 8
        assert fold["metrics"]["test_size"] == 4
        assert benchmark not in fold["train_benchmarks"]
        assert {p["candidate_id"] for p in fold["predictions"]} == {
            row["candidate_id"] for row in rows if row["benchmark"] == benchmark}
    assert report["synthetic"] is True
    assert report["pooled_metrics"]["test_size"] == 12
    assert "not calibrated" in " ".join(report["warnings"])
    json.dumps(report, allow_nan=False)


def test_singleton_and_constant_labels_are_honest():
    rows = measured_rows()[:2]
    for i, row in enumerate(rows):
        row["benchmark"] = f"kernel-{i}"
        row["speedup"] = 1.25
    model = SpeedupPredictor().fit(rows[:1])
    assert model.predict(rows)[0] == {"candidate_id": "candidate-0", "mean": 1.25,
                                     "lower": 1.25, "upper": 1.25, "std": 0.0}
    assert any("constant" in warning for warning in model.warnings)
    report = leave_one_benchmark_out(rows)
    assert all(fold["metrics"]["spearman"] is None for fold in report["folds"])
    assert report["pooled_metrics"]["spearman"] is None


def test_mixed_measurement_sources_rejected():
    rows = measured_rows()
    rows[-1]["measurement_source"] = "hardware"
    with pytest.raises(ValueError, match="mix measurement sources"):
        SpeedupPredictor().fit(rows)
    with pytest.raises(ValueError, match="mix measurement sources"):
        leave_one_benchmark_out(rows)


@pytest.mark.parametrize("value", [None, -1, 0, float("inf"), float("nan"), True, "1.0"])
def test_invalid_speedup_rejected(value):
    rows = measured_rows()
    rows[0]["speedup"] = value
    with pytest.raises(ValueError, match="speedup"):
        SpeedupPredictor().fit(rows)


def test_fit_and_prediction_edge_cases():
    model = SpeedupPredictor()
    with pytest.raises(RuntimeError, match="fit"):
        model.predict([])
    with pytest.raises(ValueError, match="At least one"):
        model.fit([])
    rows = measured_rows()
    model.fit(rows[:1])
    assert model.predict([]) == []
    missing = dict(rows[0])
    del missing[FEATURE_COLUMNS[0]]
    with pytest.raises(ValueError, match="missing features"):
        model.predict([missing])
    invalid = {**rows[0], FEATURE_COLUMNS[0]: float("nan")}
    with pytest.raises(ValueError, match="finite"):
        model.predict([invalid])
    with pytest.raises(ValueError, match="at least two benchmarks"):
        leave_one_benchmark_out(rows[:3])
    with pytest.raises(ValueError, match="benchmark"):
        leave_one_benchmark_out([{**row, "benchmark": ""} for row in rows])
    with pytest.raises(ValueError, match="measurement_source"):
        model.fit([{**rows[0], "measurement_source": "unknown"}])


@pytest.mark.parametrize("options", [{"interval": 1}, {"interval": 0},
                                   {"interval": float("nan")}, {"ensemble_size": 0},
                                   {"seed": -1}, {"seed": True}, {"max_depth": 0}])
def test_invalid_model_configuration(options):
    with pytest.raises(ValueError):
        SpeedupPredictor(**options)


def test_large_finite_constant_remains_finite():
    rows = measured_rows()[:1]
    rows[0]["speedup"] = 1e300
    prediction = SpeedupPredictor().fit(rows).predict(rows)[0]
    assert prediction["mean"] == 1e300
    assert prediction["std"] == 0
    assert all(math.isfinite(prediction[key]) for key in ("mean", "lower", "upper", "std"))


def test_unbounded_integer_rejected_without_overflow():
    rows = measured_rows()
    rows[0][FEATURE_COLUMNS[0]] = 10**1000
    with pytest.raises(ValueError, match="finite"):
        SpeedupPredictor().fit(rows)


def test_metric_values_are_observed_not_nominal_coverage():
    from isaforge.evaluation import _metrics

    predictions = [{"mean": 1, "lower": 0.9, "upper": 1.1},
                   {"mean": 2, "lower": 1.9, "upper": 2.1}]
    metrics = _metrics([1.0, 3.0], predictions)
    assert metrics["mae"] == 0.5
    assert metrics["spearman"] == pytest.approx(1.0)
    assert metrics["interval_coverage"] == 0.5
    assert metrics["mean_interval_width"] == pytest.approx(0.2)

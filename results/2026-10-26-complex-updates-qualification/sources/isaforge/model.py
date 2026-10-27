"""Deterministic speedup regression with bootstrap ensemble uncertainty."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

from .dataset import MEASUREMENT_SOURCES
from .features import FEATURE_COLUMNS

UNCERTAINTY_WARNING = (
    "Intervals describe bootstrap ensemble disagreement, not calibrated prediction "
    "coverage. Small or constant datasets can give zero-width intervals even when "
    "predictions are uncertain."
)


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be {'positive and ' if positive else ''}finite")
    return result


def feature_matrix(rows: Sequence[Mapping[str, Any]]) -> list[list[float]]:
    """Read the fixed feature allowlist; measured outcomes never become inputs."""
    matrix = []
    for index, row in enumerate(rows):
        missing = [column for column in FEATURE_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"row {index} missing features: {', '.join(missing)}")
        matrix.append([_number(row[column], column) for column in FEATURE_COLUMNS])
    return matrix


def validate_training_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    """Require positive speedup labels from a single explicit measurement source."""
    if not rows:
        raise ValueError("At least one measured training row is required")
    sources = set()
    for row in rows:
        source = row.get("measurement_source")
        if not isinstance(source, str) or source not in MEASUREMENT_SOURCES:
            raise ValueError(f"Unknown or missing measurement_source: {source!r}")
        sources.add(source)
        if "speedup" not in row:
            raise ValueError("Training rows must include a measured speedup")
        _number(row["speedup"], "speedup", positive=True)
    if len(sources) != 1:
        raise ValueError("Cannot mix measurement sources, including synthetic and real measurements")
    feature_matrix(rows)
    return next(iter(sources))


class SpeedupPredictor:
    """Small XGBoost regressors fit on independently bootstrapped training rows.

    A constant-label training set has an explicit constant fallback, because no
    regression model can infer variation from those labels. Such a fallback has
    zero ensemble disagreement and is not evidence of confidence.
    """

    def __init__(
        self,
        seed: int = 0,
        *,
        ensemble_size: int = 20,
        n_estimators: int = 80,
        interval: float = 0.90,
        max_depth: int = 2,
    ) -> None:
        for name, value in (("seed", seed), ("ensemble_size", ensemble_size),
                            ("n_estimators", n_estimators), ("max_depth", max_depth)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if name != "seed" and value <= 0:
                raise ValueError(f"{name} must be positive")
        if seed < 0:
            raise ValueError("seed must be nonnegative")
        interval = _number(interval, "interval")
        if not 0 < interval < 1:
            raise ValueError("interval must be between 0 and 1")
        self.seed = seed
        self.ensemble_size = ensemble_size
        self.n_estimators = n_estimators
        self.interval = interval
        self.max_depth = max_depth
        self.warnings = [UNCERTAINTY_WARNING]
        self.measurement_source: str | None = None
        self._models: list[Any] | None = None
        self._constant: float | None = None

    def fit(self, rows: Sequence[Mapping[str, Any]]) -> SpeedupPredictor:
        rows = list(rows)
        source = validate_training_rows(rows)
        import numpy as np

        x = np.asarray(feature_matrix(rows), dtype=float)
        y = np.asarray([float(row["speedup"]) for row in rows], dtype=float)
        models = []
        constant = None
        warnings = [UNCERTAINTY_WARNING]
        if len(rows) < 10:
            warnings.append("Fewer than 10 training rows; predictive accuracy and uncertainty are fragile.")
        if self.ensemble_size == 1:
            warnings.append("One ensemble member cannot estimate disagreement; uncertainty is zero.")
        if np.all(y == y[0]):
            constant = float(y[0])
            warnings.append("Training labels are constant; predictions are constant with zero disagreement.")
        else:
            try:
                from xgboost import XGBRegressor
            except ImportError as error:
                raise ImportError("Install the project ML dependencies to use XGBoost regression") from error
            rng = np.random.default_rng(self.seed)
            for _ in range(self.ensemble_size):
                indices = rng.integers(0, len(rows), size=len(rows))
                model_seed = int(rng.integers(0, 2**31 - 1))
                model = XGBRegressor(
                    objective="reg:squarederror",
                    n_estimators=self.n_estimators,
                    max_depth=self.max_depth,
                    learning_rate=0.05,
                    min_child_weight=1,
                    reg_lambda=1.0,
                    subsample=1.0,
                    colsample_bytree=1.0,
                    tree_method="hist",
                    n_jobs=1,
                    random_state=model_seed,
                    verbosity=0,
                )
                model.fit(x[indices], y[indices])
                models.append(model)
        # Publish fitted state only after every ensemble member trained successfully.
        self._models = models
        self._constant = constant
        self.measurement_source = source
        self.warnings = warnings
        return self

    def predict(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if self._models is None:
            raise RuntimeError("Call fit before predict")
        rows = list(rows)
        if not rows:
            return []
        for row in rows:
            if "candidate_id" not in row:
                raise ValueError("Prediction rows must include candidate_id")
        import numpy as np

        x = np.asarray(feature_matrix(rows), dtype=float)
        if self._constant is not None:
            samples = np.full((self.ensemble_size, len(rows)), self._constant)
        else:
            samples = np.stack([model.predict(x) for model in self._models])
        if not np.isfinite(samples).all():
            raise ValueError("Regressor produced non-finite predictions")
        # Normalize before reductions so even a large finite constant does not
        # overflow when the ensemble values are summed or squared.
        scales = np.maximum(np.abs(samples).max(axis=0), 1.0)
        normalized = samples / scales
        means = normalized.mean(axis=0) * scales
        stds = normalized.std(axis=0) * scales
        tail = (1 - self.interval) / 2
        lowers, uppers = np.quantile(normalized, [tail, 1 - tail], axis=0) * scales
        return [
            {"candidate_id": row["candidate_id"], "mean": float(means[i]),
             "lower": float(lowers[i]), "upper": float(uppers[i]), "std": float(stds[i])}
            for i, row in enumerate(rows)
        ]

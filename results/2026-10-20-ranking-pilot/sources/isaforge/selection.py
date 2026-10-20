"""Budgeted, single-instruction selection over a recorded measurement dataset.

Acquisition functions receive public features and measured observations only.
The oracle is a privileged offline reference, never an acquisition input.
"""

from __future__ import annotations

import math
import random
from decimal import Decimal, localcontext
from collections.abc import Iterable, Mapping, Sequence
from numbers import Real
from typing import Any

from .features import FEATURE_COLUMNS
from .dataset import MEASUREMENT_SOURCES, TIMING_COLUMNS

POLICIES = ("frequency", "merit", "random", "active_learning")


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _measurement(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["speedup"] = _number(row.get("speedup"), "speedup", positive=True)
    result["area"] = _number(row.get("area"), "area")
    if result["area"] < 0:
        raise ValueError("area must be nonnegative")
    if (not isinstance(result.get("measurement_source"), str)
            or result["measurement_source"] not in MEASUREMENT_SOURCES):
        raise ValueError("unsupported measurement_source")
    if any(key in row for key in TIMING_COLUMNS):
        timing = {key: _number(row.get(key), key, positive=True) for key in TIMING_COLUMNS}
        with localcontext() as context:
            context.prec = 50
            values = {key: Decimal(str(value)) for key, value in timing.items()}
            expected = float(values["baseline_cycles"] * values["baseline_period_ns"]
                             / (values["candidate_cycles"] * values["candidate_period_ns"]))
        if not math.isfinite(expected) or expected <= 0:
            raise ValueError("timing ratio must yield a finite positive speedup")
        if not math.isclose(expected, result["speedup"], rel_tol=1e-9, abs_tol=0):
            raise ValueError("speedup does not match recorded timing measurements")
    return result


class SelectionTools:
    """Feature-only discovery, predictions, and cached budgeted measurements.

    One budget unit buys one candidate measurement for the target benchmark.
    Repeating an already measured candidate is free. Areas and speedups are
    hidden until measurement; the area cap applies to final selections.
    """

    def __init__(
        self,
        rows: Iterable[Mapping[str, Any]],
        budget: int,
        area_cap: float | None = None,
        seed: int = 0,
        training_rows: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise ValueError("budget must be a nonnegative integer")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if area_cap is not None:
            area_cap = _number(area_cap, "area_cap")
            if area_cap < 0:
                raise ValueError("area_cap must be nonnegative")
        self.budget = budget
        self.area_cap = area_cap
        self.seed = seed
        self.__records: dict[str, dict[str, Any]] = {}
        self.__public: dict[str, dict[str, Any]] = {}
        self.__measured: dict[str, dict[str, Any]] = {}
        for raw in rows:
            row = dict(raw)
            candidate_id = row.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ValueError("candidate_id must be a nonempty string")
            if candidate_id in self.__records:
                raise ValueError(f"duplicate candidate_id: {candidate_id}")
            for key in ("benchmark", "formula"):
                if not isinstance(row.get(key), str) or not row[key]:
                    raise ValueError(f"{key} must be a nonempty string")
            public = {key: row[key] for key in ("candidate_id", "benchmark", "formula")}
            public.update({key: _number(row.get(key), key) for key in FEATURE_COLUMNS})
            if (not isinstance(row.get("measurement_source"), str)
                    or row["measurement_source"] not in MEASUREMENT_SOURCES):
                raise ValueError("unsupported measurement_source")
            self.__records[candidate_id] = row
            self.__public[candidate_id] = public
        if not self.__records:
            raise ValueError("at least one candidate row is required")
        benchmarks = {row["benchmark"] for row in self.__public.values()}
        if len(benchmarks) != 1:
            raise ValueError("selection requires exactly one target benchmark")
        self.benchmark = next(iter(benchmarks))
        sources = {row["measurement_source"] for row in self.__records.values()}
        if len(sources) != 1:
            raise ValueError("selection cannot mix measurement sources")
        self.measurement_source = next(iter(sources))
        self.__training = []
        for raw in training_rows:
            row = _measurement(raw)
            if row.get("benchmark") == self.benchmark:
                raise ValueError("training rows must exclude the target benchmark")
            if not isinstance(row.get("benchmark"), str) or not row["benchmark"]:
                raise ValueError("training benchmark must be a nonempty string")
            if row["measurement_source"] != self.measurement_source:
                raise ValueError("training and target measurement sources must match")
            for key in FEATURE_COLUMNS:
                _number(row.get(key), key)
            self.__training.append(row)

    @property
    def measurements_used(self) -> int:
        return len(self.__measured)

    @property
    def remaining_budget(self) -> int:
        return self.budget - self.measurements_used

    @property
    def measured_candidate_ids(self) -> list[str]:
        return list(self.__measured)

    @property
    def training_size(self) -> int:
        return len(self.__training) + self.measurements_used

    @property
    def historical_training_size(self) -> int:
        return len(self.__training)

    def list_candidates(self) -> list[dict[str, Any]]:
        """Return fresh public feature records without measurement labels."""
        return [dict(row) for row in self.__public.values()]

    def measured_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.__measured.values()]

    def _ids(self, candidate_ids: Sequence[str] | str | None) -> list[str]:
        if candidate_ids is None:
            ids = list(self.__public)
        elif isinstance(candidate_ids, str):
            ids = [candidate_ids]
        else:
            ids = list(candidate_ids)
        unknown = [candidate_id for candidate_id in ids if candidate_id not in self.__public]
        if unknown:
            raise ValueError(f"unknown candidate_id: {unknown[0]}")
        return list(dict.fromkeys(ids))

    def measure(self, candidate_ids: Sequence[str] | str) -> list[dict[str, Any]]:
        """Measure a batch atomically; repeat observations are cached and free."""
        ids = self._ids(candidate_ids)
        fresh = [candidate_id for candidate_id in ids if candidate_id not in self.__measured]
        if len(fresh) > self.remaining_budget:
            raise ValueError("measurement budget exceeded")
        measurements = {candidate_id: _measurement(self.__records[candidate_id]) for candidate_id in fresh}
        self.__measured.update(measurements)
        return [dict(self.__measured[candidate_id]) for candidate_id in ids]

    def predict(self, candidate_ids: Sequence[str] | str | None = None) -> list[dict[str, Any]]:
        """Fit exclusively on separate-benchmark training and observations."""
        ids = self._ids(candidate_ids)
        if not self.training_size:
            raise ValueError("predict requires training data or at least one measurement")
        if not ids:
            return []
        from .model import SpeedupPredictor

        predictor = SpeedupPredictor(seed=self.seed)
        predictor.fit([dict(row) for row in self.__training] + self.measured_rows())
        return predictor.predict([dict(self.__public[candidate_id]) for candidate_id in ids])

    def choose_final(self) -> dict[str, Any] | None:
        """Return the best verified feasible improvement, or no extension.

        None denotes the always available baseline (speedup 1, area 0).
        """
        feasible = [row for row in self.__measured.values() if self.area_cap is None or row["area"] <= self.area_cap]
        if not feasible:
            return None
        best = min(feasible, key=lambda row: (-row["speedup"], row["area"], row["candidate_id"]))
        return dict(best) if best["speedup"] > 1.0 else None


def run_policy(tools: SelectionTools, policy: str, *, bootstrap: int = 3) -> dict[str, Any]:
    """Replay a policy using only the supplied measurement-tool interface."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if isinstance(bootstrap, bool) or not isinstance(bootstrap, int) or bootstrap < 1:
        raise ValueError("bootstrap must be a positive integer")
    candidates = tools.list_candidates()
    rng = random.Random(tools.seed)
    rng.shuffle(candidates)
    # Stable sorting keeps seeded random tie-breaking for tied feature scores.
    if policy == "frequency":
        candidates.sort(key=lambda row: -row["runs"])
    elif policy == "merit":
        candidates.sort(key=lambda row: -row["saved"])
    while tools.remaining_budget and candidates:
        candidates = [row for row in candidates if row["candidate_id"] not in tools.measured_candidate_ids]
        if not candidates:
            break
        if policy == "active_learning" and tools.training_size >= bootstrap:
            predictions = tools.predict([row["candidate_id"] for row in candidates])
            upper = {prediction["candidate_id"]: prediction["upper"] for prediction in predictions}
            chosen = max(candidates, key=lambda row: upper[row["candidate_id"]])
        else:
            chosen = candidates[0]
        tools.measure(chosen["candidate_id"])
    selected = tools.choose_final()
    return {
        "policy": policy,
        "measurements_used": tools.measurements_used,
        "measured_candidate_ids": tools.measured_candidate_ids,
        "selected": selected,
        "best_speedup": selected["speedup"] if selected is not None else 1.0,
    }


def evaluate_policies(
    rows: Iterable[Mapping[str, Any]],
    budget: int,
    area_cap: float | None = None,
    seed: int = 0,
    training_rows: Iterable[Mapping[str, Any]] = (),
    policies: Sequence[str] = POLICIES,
) -> dict[str, Any]:
    """Compare equal-budget replay policies to a privileged feasible oracle.

    Speedup is always a measured single-candidate value. This function does
    not estimate multi-instruction sets or sum candidate speedups.
    """
    rows = [dict(row) for row in rows]
    training_rows = [dict(row) for row in training_rows]
    if len(set(policies)) != len(policies) or any(policy not in POLICIES for policy in policies):
        raise ValueError("policies must contain unique supported policy names")
    oracle_tools = SelectionTools(rows, budget, area_cap, seed, training_rows)
    results = []
    for policy in policies:
        tools = SelectionTools(rows, budget, area_cap, seed, training_rows)
        results.append(run_policy(tools, policy))
    # Only this privileged comparator reads the full recorded outcomes. It
    # runs after policy replay and cannot influence an acquisition decision.
    reference = [_measurement(row) for row in rows]
    reference.sort(key=lambda row: (
        area_cap is not None and row["area"] > area_cap,
        -row["speedup"], row["area"], row["candidate_id"],
    ))
    oracle_tools.measure([row["candidate_id"] for row in reference[:budget]])
    oracle_selected = oracle_tools.choose_final()
    oracle_speedup = oracle_selected["speedup"] if oracle_selected else 1.0
    oracle = {
        "policy": "oracle",
        "privileged": True,
        "reference_label_count": len(rows),
        "measurements_used": oracle_tools.measurements_used,
        "measured_candidate_ids": oracle_tools.measured_candidate_ids,
        "selected": oracle_selected,
        "best_speedup": oracle_speedup,
        "regret": 0.0,
    }
    for result in results:
        result["regret"] = oracle_speedup - result["best_speedup"]
    return {
        "benchmark": oracle_tools.benchmark,
        "measurement_source": oracle_tools.measurement_source,
        "budget": budget,
        "area_cap": area_cap,
        "seed": seed,
        "historical_training_size": len(training_rows),
        "oracle": oracle,
        "results": results,
        "scope": "single_candidate_offline_replay",
        "limitations": [
            "Oracle uses privileged recorded labels and is an offline upper bound.",
            "No multi-instruction set evaluation; overlap and shared clock effects are unknown.",
            "Tool interface is implemented; an LLM-driven selector is not implemented.",
            "Bootstrap ensemble intervals measure model disagreement, not calibrated coverage.",
        ],
    }

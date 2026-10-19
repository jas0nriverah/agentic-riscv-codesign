"""Join discovery candidates to explicitly supplied measurement records."""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

from .features import candidate_id, extract_features


MEASUREMENT_SOURCES = frozenset({"gem5", "synthesis_estimate", "hardware", "synthetic"})
TIMING_COLUMNS = (
    "baseline_cycles", "candidate_cycles", "baseline_period_ns", "candidate_period_ns",
)


def _number(measurement: dict, field: str, *, positive: bool) -> int | float:
    value = measurement.get(field)
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, int) and value.bit_length() > 1023)
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{field} must be finite and {qualifier}")
    return value


def build_dataset(
    benchmark: str,
    candidates: list[dict],
    measurements: list[dict] | None = None,
) -> list[dict]:
    """Produce flat feature rows, optionally joining measured labels by ID.

    Missing labels are preserved for inference. Unknown, duplicate, or mismatched
    measurement identities are errors. Timing values are the effective periods
    of the actual experiment: this function does not silently alter clocks.
    """
    if not isinstance(benchmark, str) or not benchmark.strip():
        raise ValueError("benchmark must be a nonempty string")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    if measurements is not None and not isinstance(measurements, list):
        raise ValueError("measurements must be a list or None")
    rows: list[dict] = []
    by_id: dict[str, dict] = {}
    for candidate in candidates:
        features = extract_features(candidate)
        identity = candidate_id(benchmark, candidate["formula"])
        if identity in by_id:
            raise ValueError(f"duplicate candidate_id {identity}")
        if "candidate_id" in candidate and candidate["candidate_id"] != identity:
            raise ValueError("candidate_id does not match benchmark and formula")
        if "benchmark" in candidate and candidate["benchmark"] != benchmark:
            raise ValueError("candidate benchmark does not match dataset benchmark")
        row = {"candidate_id": identity, "benchmark": benchmark,
               "formula": candidate["formula"], **features}
        rows.append(row)
        by_id[identity] = row
    seen: set[str] = set()
    for measurement in measurements or []:
        if not isinstance(measurement, dict):
            raise ValueError("measurement must be an object")
        identity = measurement.get("candidate_id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("measurement requires a candidate_id")
        if identity in seen:
            raise ValueError(f"duplicate measurement candidate_id {identity}")
        if identity not in by_id:
            raise ValueError(f"measurement candidate_id {identity} has no candidate")
        seen.add(identity)
        if "benchmark" in measurement and measurement["benchmark"] != benchmark:
            raise ValueError("measurement benchmark does not match dataset benchmark")
        if "formula" in measurement and candidate_id(benchmark, measurement["formula"]) != identity:
            raise ValueError("measurement formula does not match candidate_id")
        source = measurement.get("measurement_source")
        if not isinstance(source, str) or source not in MEASUREMENT_SOURCES:
            raise ValueError("measurement_source must be gem5, synthesis_estimate, hardware, or synthetic")
        timings = {field: _number(measurement, field, positive=True) for field in TIMING_COLUMNS}
        area = _number(measurement, "area", positive=False)
        # Decimal intermediate arithmetic keeps finite ratios valid even when
        # individual elapsed products overflow a binary float.
        with localcontext() as context:
            context.prec = 50
            values = {field: Decimal(str(value)) for field, value in timings.items()}
            speedup = float(
                values["baseline_cycles"] * values["baseline_period_ns"]
                / (values["candidate_cycles"] * values["candidate_period_ns"])
            )
        if not math.isfinite(speedup) or speedup <= 0:
            raise ValueError("timing ratio must yield a finite positive speedup")
        if "speedup" in measurement:
            supplied = _number(measurement, "speedup", positive=True)
            if not math.isclose(supplied, speedup, rel_tol=1e-9, abs_tol=0):
                raise ValueError("supplied speedup does not match timing measurements")
        by_id[identity].update(timings, area=area, speedup=speedup, measurement_source=source)
    return rows

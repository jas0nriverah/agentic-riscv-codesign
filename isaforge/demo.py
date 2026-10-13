"""Deliberately synthetic fixtures for exercising the pipeline, never research data."""

from .dataset import build_dataset
from .features import candidate_id


def demo_rows():
    formulas = [
        ("add(add(in0,in1),in0)", 2),
        ("xor(slli(in0,3),in1)", 2),
        ("add(mul(in0,in1),in0)", 2),
        ("and(add(in0,in1),in0)", 2),
        ("xor(srl(add(in0,in1),in1),in0)", 3),
        ("add(slli(add(in0,in1),2),in1)", 3),
        ("xor(mul(add(in0,in1),in0),in1)", 3),
        ("or(and(xor(in0,in1),in0),in1)", 3),
    ]
    rows = []
    for b in range(3):
        benchmark = f"synthetic_{b}"
        candidates, measurements = [], []
        for i, (formula, size) in enumerate(formulas):
            runs = 100 + 37 * i + 23 * b
            saved = (size - 1) * runs
            candidates.append(dict(formula=formula, size=size, runs=runs,
                                   places=1 + i % 3, saved=saved,
                                   savedPercent=100 * saved / 10000))
            # These are arbitrary test costs, not a model of a real processor.
            period = 1.0 + (0.3 if "mul(" in formula else 0.0)
            measurements.append(dict(
                candidate_id=candidate_id(benchmark, formula),
                measurement_source="synthetic", baseline_cycles=10000,
                candidate_cycles=10000 - saved, baseline_period_ns=1.0,
                candidate_period_ns=period, area=10 + 4 * i,
            ))
        rows.extend(build_dataset(benchmark, candidates, measurements))
    return rows

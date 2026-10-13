"""Run a reproducible candidate correctness and resource-synthesis experiment."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time

from .features import candidate_id, extract_features, parse_formula
from .rtl import generate_rtl, verify_rtl_batch
from .synthesis import run_synthesis


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def select_candidates(directory, per_benchmark, seed):
    if per_benchmark < 1:
        raise ValueError("per_benchmark must be positive")
    rows, summary = [], []
    rng = random.Random(seed)
    for path in sorted(Path(directory).glob("*.json")):
        candidates = json.loads(path.read_text())
        if not isinstance(candidates, list):
            continue
        candidates.sort(key=lambda row: (-row["saved"], row["formula"]))
        top_count = min((per_benchmark + 1) // 2, len(candidates))
        top = candidates[:top_count]
        remaining = candidates[top_count:]
        sampled = rng.sample(remaining, min(per_benchmark - top_count, len(remaining)))
        selected = [(row, "top_merit") for row in top] + [(row, "seeded_random_remainder") for row in sampled]
        for candidate, stratum in selected:
            formula = parse_formula(candidate["formula"]).canonical()
            rows.append(dict(candidate_id=candidate_id(path.stem, formula),
                             benchmark=path.stem, formula=formula,
                             **extract_features(candidate), selection_stratum=stratum,
                             trace_total_instructions=candidate["traceTotalInstructions"],
                             overlap_safe_saved=candidate["overlapSafeSaved"],
                             overlap_safe_saved_percent=candidate["overlapSafeSavedPercent"]))
        summary.append(dict(benchmark=path.stem, candidate_count=len(candidates),
                            selected_count=len(selected),
                            trace_total_instructions=candidates[0]["traceTotalInstructions"] if candidates else None,
                            candidates_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if not rows:
        raise ValueError("No candidate arrays found")
    return rows, summary


def run_experiment(candidates_dir, output_dir, per_benchmark=24, seed=20261013, workers=2):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    selected, summary = select_candidates(candidates_dir, per_benchmark, seed)
    formulas = sorted({row["formula"] for row in selected})
    write_json(output / "selection.json", dict(seed=seed, per_benchmark=per_benchmark,
                                              method="half_top_merit_half_seeded_random_remainder",
                                              benchmarks=summary, rows=selected))
    print(f"Selected {len(selected)} benchmark-candidate rows, {len(formulas)} distinct circuits", flush=True)
    verification = verify_rtl_batch(formulas, output / "verification", seed=seed)
    write_json(output / "verification.json", verification)
    print(f"RTL verification: {verification['total_comparisons']} comparisons passed", flush=True)
    tool_version = subprocess.run(["yosys", "-V"], check=True, capture_output=True, text=True).stdout.strip()

    def synthesize(formula):
        key = hashlib.sha256(formula.encode()).hexdigest()[:20]
        folder = output / "circuits" / key
        metrics_path = folder / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            rtl_hash = hashlib.sha256(generate_rtl(formula).encode()).hexdigest()
            if (metrics.get("formula") == formula and metrics.get("tool") == tool_version
                    and metrics.get("rtl_sha256") == rtl_hash and "ice40_lut4_count" in metrics):
                return formula, metrics, True
        metrics = run_synthesis(formula, folder, timeout=300)
        return formula, metrics, False

    measurements, failures = {}, []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(synthesize, formula): formula for formula in formulas}
        for index, future in enumerate(as_completed(futures), 1):
            formula = futures[future]
            try:
                _, metrics, cached = future.result()
                measurements[formula] = metrics
                print(f"[{index}/{len(formulas)}] LUT4={metrics['ice40_lut4_count']} "
                      f"{'cached' if cached else 'synthesized'} {formula}", flush=True)
            except Exception as error:
                failures.append(dict(formula=formula, error=str(error)))
                print(f"[{index}/{len(formulas)}] FAILED {formula}: {error}", flush=True)
            write_json(output / "progress.json", dict(completed=len(measurements),
                                                      total=len(formulas), failures=failures,
                                                      elapsed_seconds=time.monotonic() - started))
    rows = []
    for row in selected:
        if row["formula"] not in measurements:
            continue
        measurement = measurements[row["formula"]]
        rows.append(dict(row, lut4_count=measurement["ice40_lut4_count"],
                         carry_count=measurement["ice40_carry_count"],
                         generic_cell_count=measurement["generic_cell_count"],
                         generic_logic_depth=measurement["generic_logic_depth"],
                         measurement_source="rtl_synthesis", correctness_verified=True,
                         rtl_sha256=measurement["rtl_sha256"], synthesis_tool=measurement["tool"]))
    write_json(output / "dataset.json", rows)
    write_json(output / "summary.json", dict(
        benchmarks=summary, candidate_rows=len(rows), unique_circuits=len(measurements),
        failures=failures, verification=verification,
        synthesis_wall_seconds=time.monotonic() - started,
        target="isolated combinational iCE40 LUT4 resources; no placement or routing",
        limitations=["No measured architectural cycles, clock period, or processor speedup.",
                     "Stratified sample includes top merit and randomly sampled candidates.",
                     "RTL checked against integer oracle using sampled inputs, not a formal proof.",
                     "Overlap-safe savings are instruction counts, not cycles."]
    ))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-dir", default="generated/real/candidates")
    parser.add_argument("--output", default="generated/real/experiment")
    parser.add_argument("--per-benchmark", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20261013)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    run_experiment(args.candidates_dir, args.output, args.per_benchmark, args.seed, args.workers)


if __name__ == "__main__":
    main()

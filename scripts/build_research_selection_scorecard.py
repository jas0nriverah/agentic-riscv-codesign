"""Build a reproducible, workload-level scorecard from the frozen LOCO screen.

This summarizes already-consumed development data. It does not refit, tune, or
promote any model and must not be described as independent confirmation.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "results/2026-10-26-feasibility-model-screen"
OUT = ROOT / "results/2026-10-27-final-selection-scorecard"
BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_SEED = 20261027
PLOT_POLICIES = (
    "random",
    "frequency",
    "latency_cost_heuristic",
    "merit",
    "xgb_speedup_regression",
    "xgb_pairwise_ranker",
    "factorized_feasibility_xgb",
)
MODEL_CHALLENGERS = (
    "xgb_speedup_regression",
    "xgb_pairwise_ranker",
    "factorized_feasibility_xgb",
)
LABELS = {
    "random": "Random",
    "frequency": "Frequency",
    "latency_cost_heuristic": "Timing-aware heuristic",
    "merit": "Merit",
    "xgb_speedup_regression": "XGB speedup regression",
    "xgb_pairwise_ranker": "XGB pairwise ranker",
    "factorized_feasibility_xgb": "Factorized feasibility XGB",
}
COLORS = {
    "random": "#8c8c8c",
    "frequency": "#d28e00",
    "latency_cost_heuristic": "#008c95",
    "merit": "#353535",
    "xgb_speedup_regression": "#4477aa",
    "xgb_pairwise_ranker": "#cc6677",
    "factorized_feasibility_xgb": "#228833",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sidecar(path: Path) -> str:
    actual = sha256(path)
    sidecar = path.with_name(path.name + ".sha256")
    expected = sidecar.read_text().strip().split()[0]
    if actual != expected:
        raise ValueError(f"Hash mismatch: {path}")
    return actual


def mean_interval(values: list[float], rng: random.Random) -> tuple[float, float, float]:
    if not values:
        raise ValueError("Cannot bootstrap an empty workload set")
    mean = statistics.mean(values)
    draws = []
    n = len(values)
    for _ in range(BOOTSTRAP_DRAWS):
        draws.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return mean, lo, hi


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def svg_text(x, y, value, *, size=13, fill="#222", anchor="start", weight="normal", rotate=None):
    rotation = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-size="{size}" fill="{fill}" font-weight="{weight}"{rotation}>'
            f'{html.escape(str(value))}</text>')


def svg_start(width, height, title, description):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif} .grid{stroke:#dedede;stroke-width:1} .axis{stroke:#444;stroke-width:1.2}</style>',
        f'<title>{html.escape(title)}</title>',
        f'<desc>{html.escape(description)}</desc>',
    ]


def polyline_svg(points, color, width=2.5):
    joined = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{joined}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'


def draw_frontier(path: Path, rows_by_key, *, metric: str, ci_low: str, ci_high: str,
                  ylabel: str, title: str, description: str, y_max: float):
    width, height = 1080, 560
    left, right, top, bottom = 88, 790, 66, 405
    x_positions = {1: left + 35, 2: (left + right) / 2, 3: right - 35}
    y = lambda value: bottom - (value / y_max) * (bottom - top)
    parts = svg_start(width, height, title, description)
    parts.append(svg_text(left, 30, title, size=19, weight="bold"))
    parts.append(svg_text((left + right) / 2, 540, "Charged hardware-evaluation budget (candidate attempts)", anchor="middle", size=14))
    parts.append(svg_text(20, (top + bottom) / 2, ylabel, anchor="middle", rotate=-90, size=14))
    max_half_percent_ticks = math.floor(y_max * 200)
    for tick in range(max_half_percent_ticks + 1):
        percent = tick * 0.5
        value = percent / 100
        yy = y(value)
        parts.append(f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}"/>')
        parts.append(svg_text(left - 12, yy + 4, f"{percent:.1f}%", anchor="end", size=11, fill="#555"))
    parts.append(f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>')
    for budget, xx in x_positions.items():
        parts.append(f'<line class="grid" x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}" stroke-dasharray="2 4"/>')
        parts.append(svg_text(xx, bottom + 22, budget, anchor="middle", size=12))
    for policy in PLOT_POLICIES:
        pts = []
        for budget in (1, 2, 3):
            row = rows_by_key[(policy, budget)]
            xx, yy = x_positions[budget], y(float(row[metric]))
            pts.append((xx, yy))
            ylo, yhi = y(float(row[ci_low])), y(float(row[ci_high]))
            parts.append(f'<line x1="{xx:.1f}" y1="{yhi:.1f}" x2="{xx:.1f}" y2="{ylo:.1f}" stroke="{COLORS[policy]}" stroke-width="1.4"/>')
            parts.append(f'<line x1="{xx-4:.1f}" y1="{yhi:.1f}" x2="{xx+4:.1f}" y2="{yhi:.1f}" stroke="{COLORS[policy]}" stroke-width="1.4"/>')
            parts.append(f'<line x1="{xx-4:.1f}" y1="{ylo:.1f}" x2="{xx+4:.1f}" y2="{ylo:.1f}" stroke="{COLORS[policy]}" stroke-width="1.4"/>')
        parts.append(polyline_svg(pts, COLORS[policy], 3 if policy in ("merit", "xgb_pairwise_ranker") else 2))
        for xx, yy in pts:
            parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="4" fill="{COLORS[policy]}" stroke="#fff" stroke-width="1"/>')
    legend_y = 88
    for i, policy in enumerate(PLOT_POLICIES):
        yy = legend_y + i * 27
        parts.append(f'<line x1="825" y1="{yy-4}" x2="858" y2="{yy-4}" stroke="{COLORS[policy]}" stroke-width="3"/>')
        parts.append(svg_text(867, yy, LABELS[policy], size=12))
    parts.append(svg_text(825, 320, "Whiskers: descriptive 95%", size=11, fill="#555"))
    parts.append(svg_text(825, 337, "bootstrap intervals over", size=11, fill="#555"))
    parts.append(svg_text(825, 354, "independent workloads", size=11, fill="#555"))
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def draw_paired_forest(path: Path, contrasts: list[dict]):
    width, height = 1080, 560
    left, right, top, bottom = 325, 925, 74, 474
    xmax, xmin = 1.25, -1.25  # percentage points
    x = lambda value: left + (value - xmin) / (xmax - xmin) * (right - left)
    rows = [(policy, budget) for budget in (1, 2, 3) for policy in MODEL_CHALLENGERS]
    by_key = {(r["challenger"], r["budget"]): r for r in contrasts}
    dy = (bottom - top) / len(rows)
    parts = svg_start(width, height, "Paired regret difference versus merit",
                      "Positive values mean the ML selector has lower oracle regret than merit. Intervals resample 12 complete-oracle workload groups.")
    parts.append(svg_text(70, 31, "Paired regret difference versus merit", size=19, weight="bold"))
    parts.append(svg_text((left + right) / 2, 535, "Merit regret minus ML regret (percentage points)", anchor="middle", size=14))
    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        xx = x(tick)
        parts.append(f'<line class="grid" x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}"/>')
        parts.append(svg_text(xx, bottom + 22, f"{tick:.1f}", anchor="middle", size=11))
    parts.append(f'<line x1="{x(0):.1f}" y1="{top}" x2="{x(0):.1f}" y2="{bottom}" stroke="#222" stroke-width="1.4" stroke-dasharray="5 4"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>')
    for i, (policy, budget) in enumerate(rows):
        yy = top + dy * (i + 0.5)
        row = by_key[(policy, budget)]
        avg = float(row["mean"]) * 100
        lo = float(row["lower_95"]) * 100
        hi = float(row["upper_95"]) * 100
        parts.append(svg_text(left - 15, yy + 4, f"{LABELS[policy]} · B{budget}", anchor="end", size=12))
        parts.append(f'<line x1="{x(lo):.1f}" y1="{yy:.1f}" x2="{x(hi):.1f}" y2="{yy:.1f}" stroke="{COLORS[policy]}" stroke-width="2.3"/>')
        parts.append(f'<line x1="{x(lo):.1f}" y1="{yy-4:.1f}" x2="{x(lo):.1f}" y2="{yy+4:.1f}" stroke="{COLORS[policy]}" stroke-width="1.5"/>')
        parts.append(f'<line x1="{x(hi):.1f}" y1="{yy-4:.1f}" x2="{x(hi):.1f}" y2="{yy+4:.1f}" stroke="{COLORS[policy]}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{x(avg):.1f}" cy="{yy:.1f}" r="4.3" fill="{COLORS[policy]}"/>')
    parts.append(svg_text(left, 505, "← ML lower regret", size=11, fill="#555"))
    parts.append(svg_text(right, 505, "Merit lower regret →", anchor="end", size=11, fill="#555"))
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def draw_heatmap(path: Path, group_rows: list[dict]):
    policies = ("random", "frequency", "latency_cost_heuristic", "merit", *MODEL_CHALLENGERS)
    workloads = sorted({row["workload_group"] for row in group_rows})
    budgets = (1, 2, 3)
    lookup = {(r["workload_group"], r["policy"], r["budget"]): r for r in group_rows}
    width, height = 1290, 600
    left, top = 285, 135
    cell_w, cell_h = 20, 27
    workload_gap = 9
    col_x = {}
    xcur = left
    for workload in workloads:
        for budget in budgets:
            col_x[(workload, budget)] = xcur
            xcur += cell_w
        xcur += workload_gap
    max_abs = 1.4  # percentage points, color saturates at this scale
    parts = svg_start(width, height, "Workload-level regret heatmap",
                      "Cell value is policy regret minus merit regret in percentage points; green favors the row policy, red favors merit, gray means oracle-censored workload.")
    parts.append(svg_text(45, 33, "Per-workload regret difference versus merit", size=19, weight="bold"))
    parts.append(svg_text(left, 78, "Each three-column block is one workload (B1, B2, B3). Gray cells have censored pool oracles.", size=12, fill="#555"))
    for wi, workload in enumerate(workloads):
        x0 = col_x[(workload, 1)]
        short = workload.replace("beebs-", "").replace("embench-", "").replace("tacle-", "")
        parts.append(svg_text(x0 + cell_w * 1.5, top - 32, short, size=10, anchor="middle", rotate=-40))
        for bi, budget in enumerate(budgets):
            parts.append(svg_text(col_x[(workload, budget)] + cell_w / 2, top - 8, f"{budget}", size=9, anchor="middle", fill="#555"))
    for ri, policy in enumerate(policies):
        yy = top + ri * cell_h
        parts.append(svg_text(left - 12, yy + 18, LABELS[policy], size=11, anchor="end"))
        for workload in workloads:
            for budget in budgets:
                row = lookup[(workload, policy, budget)]
                baseline = lookup[(workload, "merit", budget)]
                xx = col_x[(workload, budget)]
                if row["reference_censored"]:
                    fill, tip = "#b7b7b7", f"{workload} B{budget}: oracle censored"
                    text = "×"
                else:
                    delta_pp = (float(row["mean_regret"]) - float(baseline["mean_regret"])) * 100
                    mag = min(1.0, abs(delta_pp) / max_abs)
                    if delta_pp < 0:
                        fill = f"#{int(255-90*mag):02x}{int(255-35*mag):02x}{int(255-90*mag):02x}"
                    elif delta_pp > 0:
                        fill = f"#{int(255-10*mag):02x}{int(255-105*mag):02x}{int(255-100*mag):02x}"
                    else:
                        fill = "#f4f4f4"
                    tip = f"{workload} B{budget}: {delta_pp:+.3f} pp vs merit"
                    text = f"{delta_pp:+.1f}"
                parts.append(f'<rect x="{xx}" y="{yy}" width="{cell_w}" height="{cell_h-2}" fill="{fill}" stroke="#fff" stroke-width="1"><title>{html.escape(tip)}</title></rect>')
                if text == "×":
                    parts.append(svg_text(xx + cell_w / 2, yy + 17, text, size=11, anchor="middle", fill="#444"))
    parts.append(svg_text(left, top + len(policies) * cell_h + 25, "Cell text: percentage-point regret difference; negative/green favors policy, positive/red favors merit.", size=11, fill="#555"))
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def draw_hardware_tradeoff(path: Path, rows_by_key, resource_by_key):
    width, height = 1080, 590
    left, right, top, bottom = 92, 790, 66, 425
    x = lambda value: left + value / 64 * (right - left)
    y = lambda value: bottom - value / 0.025 * (bottom - top)
    markers = {1: "circle", 2: "square", 3: "triangle"}
    parts = svg_start(width, height, "Measured performance and area of selected instructions",
                      "Each point is a policy and budget macro over workload groups. X is the mean added LUT4 of the best verified feasible instruction when one was found; Y is the best verified whole-program cycle reduction over all workloads. Error bars are descriptive workload-bootstrap intervals.")
    parts.append(svg_text(left, 30, "Measured performance-area trade-off under a +64-LUT4 / 12-MHz limit", size=18, weight="bold"))
    parts.append(svg_text((left + right) / 2, 565, "Mean added LUT4 of selected best verified instruction (conditional on a feasible winner)", anchor="middle", size=12))
    parts.append(svg_text(20, (top + bottom) / 2, "Best verified whole-program cycle reduction (%)", anchor="middle", rotate=-90, size=12))
    for tick in (0, 8, 16, 24, 32, 40, 48, 56, 64):
        xx = x(tick)
        parts.append(f'<line class="grid" x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}"/>')
        parts.append(svg_text(xx, bottom + 20, tick, anchor="middle", size=10))
    for tick in (0, .005, .010, .015, .020, .025):
        yy = y(tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}"/>')
        parts.append(svg_text(left - 11, yy + 4, f"{100*tick:.1f}%", anchor="end", size=10))
    parts.append(f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>')
    for policy in PLOT_POLICIES:
        for budget in (1, 2, 3):
            metric = rows_by_key[(policy, budget)]
            resource = resource_by_key[(policy, budget)]
            if resource["mean_area_delta_lut4"] is None:
                continue
            xx = x(float(resource["mean_area_delta_lut4"]))
            yy = y(float(metric["mean_cycle_reduction"]))
            xlo = x(float(resource["area_ci_low_lut4"]))
            xhi = x(float(resource["area_ci_high_lut4"]))
            ylo = y(float(metric["cycle_reduction_ci_low"]))
            yhi = y(float(metric["cycle_reduction_ci_high"]))
            color = COLORS[policy]
            parts.append(f'<line x1="{xlo:.1f}" y1="{yy:.1f}" x2="{xhi:.1f}" y2="{yy:.1f}" stroke="{color}" stroke-width="1.2"/>')
            parts.append(f'<line x1="{xx:.1f}" y1="{yhi:.1f}" x2="{xx:.1f}" y2="{ylo:.1f}" stroke="{color}" stroke-width="1.2"/>')
            tooltip = html.escape(
                f"{LABELS[policy]} B{budget}: coverage {resource['selection_coverage_macro']:.1%}; "
                f"mean selected area {resource['mean_area_delta_lut4']:.1f} LUT4"
            )
            if markers[budget] == "circle":
                parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="4.3" fill="{color}" stroke="#fff" stroke-width="1"><title>{tooltip}</title></circle>')
            elif markers[budget] == "square":
                parts.append(f'<rect x="{xx-4:.1f}" y="{yy-4:.1f}" width="8" height="8" fill="{color}" stroke="#fff" stroke-width="1"><title>{tooltip}</title></rect>')
            else:
                parts.append(f'<path d="M {xx:.1f} {yy-5:.1f} L {xx+5:.1f} {yy+4:.1f} L {xx-5:.1f} {yy+4:.1f} Z" fill="{color}" stroke="#fff" stroke-width="1"><title>{tooltip}</title></path>')
    legend_y = 78
    for i, policy in enumerate(PLOT_POLICIES):
        yy = legend_y + i * 25
        parts.append(f'<circle cx="825" cy="{yy-4}" r="4" fill="{COLORS[policy]}"/>')
        parts.append(svg_text(837, yy, LABELS[policy], size=11))
    marker_y = 295
    for i, budget in enumerate((1, 2, 3)):
        yy = marker_y + i * 24
        if budget == 1:
            parts.append(f'<circle cx="829" cy="{yy-4}" r="4" fill="#555"/>')
        elif budget == 2:
            parts.append(f'<rect x="825" y="{yy-8}" width="8" height="8" fill="#555"/>')
        else:
            parts.append(f'<path d="M 829 {yy-9} L 834 {yy} L 824 {yy} Z" fill="#555"/>')
        parts.append(svg_text(842, yy, f"Budget {budget}", size=11))
    parts.append(svg_text(825, 395, "Area interval uses", size=10, fill="#555"))
    parts.append(svg_text(825, 411, "selected workloads only.", size=10, fill="#555"))
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    report_path = INPUT_DIR / "report.json"
    protocol_path = INPUT_DIR / "protocol.json"
    report_hash = verify_sidecar(report_path)
    protocol_hash = verify_sidecar(protocol_path)
    manifest_hash = verify_sidecar(INPUT_DIR / "manifest.json")
    report = json.loads(report_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    if report.get("protocol_sha256") != protocol_hash:
        raise ValueError("Report does not bind the archived protocol")
    if protocol.get("scope") != "retrospective consumed-data model development; no independent confirmation":
        raise ValueError("Unexpected input experiment scope")
    corpus_path = ROOT / protocol["corpus_path"]
    corpus_hash = sha256(corpus_path)
    if corpus_hash != protocol["corpus_sha256"]:
        raise ValueError("The archived report's source corpus hash does not match its protocol")
    corpus = json.loads(corpus_path.read_text())
    candidate_by_id = {row["candidate_id"]: row for row in corpus["rows"]}
    if len(candidate_by_id) != len(corpus["rows"]):
        raise ValueError("Candidate IDs are not unique in the measured corpus")
    expected_workloads = set(protocol["independent_workload_groups"])
    group_rows = report["group_summary"]
    if len(expected_workloads) != 14 or len(group_rows) != 546:
        raise ValueError("Unexpected workload/policy/budget roster")
    for row in group_rows:
        if row["workload_group"] not in expected_workloads or row["budget"] not in (1, 2, 3):
            raise ValueError("Unexpected workload or budget in scorecard input")
    keys = {(r["workload_group"], r["policy"], r["budget"]) for r in group_rows}
    if len(keys) != len(group_rows):
        raise ValueError("Duplicate workload-policy-budget rows")
    available = {r["policy"] for r in group_rows}
    if not set(PLOT_POLICIES).issubset(available):
        raise ValueError("Plot roster not represented in archived data")

    OUT.mkdir(parents=True, exist_ok=True)
    stale_overhead_path = OUT / "model_scoring_overhead_examples.csv"
    if stale_overhead_path.exists():
        stale_overhead_path.unlink()
    rng = random.Random(BOOTSTRAP_SEED)
    metrics_rows = []
    by_key = {}
    for policy in sorted(available):
        for budget in (1, 2, 3):
            rows = [r for r in group_rows if r["policy"] == policy and r["budget"] == budget]
            if len(rows) != 14:
                raise ValueError(f"Incomplete workload block for {policy}/B{budget}")
            complete = [r for r in rows if not r["reference_censored"]]
            if len(complete) != 12:
                raise ValueError(f"Expected 12 complete oracle groups for {policy}/B{budget}")
            cycle, cycle_lo, cycle_hi = mean_interval([float(r["mean_cycle_reduction"]) for r in rows], rng)
            regret, regret_lo, regret_hi = mean_interval([float(r["mean_regret"]) for r in complete], rng)
            metric = {
                "policy": policy,
                "budget": budget,
                "workload_groups_cycle_reduction": len(rows),
                "mean_cycle_reduction": cycle,
                "cycle_reduction_ci_low": cycle_lo,
                "cycle_reduction_ci_high": cycle_hi,
                "complete_oracle_groups": len(complete),
                "mean_cycle_reduction_regret": regret,
                "regret_ci_low": regret_lo,
                "regret_ci_high": regret_hi,
                "mean_target_evaluation_seconds": statistics.mean(float(r["mean_measurement_seconds"]) for r in rows),
                "mean_best_oracle_hit_rate": statistics.mean(float(r["best_verified_reference_hits"]) for r in rows),
                "mean_infeasible_successful_attempts": statistics.mean(float(r["mean_infeasible_successful_attempts"]) for r in rows),
                "censored_oracle_groups": len(rows) - len(complete),
                "seed_count_within_workload": int(rows[0]["dependent_policy_seeds"]),
            }
            # Assert the independently archived macro aggregation is represented exactly.
            macro = next(m for m in report["macro_summary"] if m["policy"] == policy and m["budget"] == budget)
            if not math.isclose(cycle, float(macro["mean_verified_cycle_reduction"]), abs_tol=1e-12):
                raise ValueError("Recomputed cycle reduction differs from archived macro")
            if not math.isclose(regret, float(macro["mean_cycle_reduction_regret"]), abs_tol=1e-12):
                raise ValueError("Recomputed complete-pool regret differs from archived macro")
            metrics_rows.append(metric)
            by_key[(policy, budget)] = metric

    metric_fields = list(metrics_rows[0])
    write_csv(OUT / "policy_metrics.csv", metric_fields, metrics_rows)
    detail_rows = []
    for row in group_rows:
        detail_rows.append({
            "workload_group": row["workload_group"],
            "policy": row["policy"],
            "budget": row["budget"],
            "mean_cycle_reduction": row["mean_cycle_reduction"],
            "mean_regret": "" if row["reference_censored"] else row["mean_regret"],
            "reference_censored": row["reference_censored"],
            "mean_target_evaluation_seconds": row["mean_measurement_seconds"],
            "mean_infeasible_successful_attempts": row["mean_infeasible_successful_attempts"],
            "best_verified_reference_hits": row["best_verified_reference_hits"],
            "dependent_policy_seeds": row["dependent_policy_seeds"],
        })
    write_csv(OUT / "workload_level_metrics.csv", list(detail_rows[0]), detail_rows)

    run_groups = defaultdict(list)
    for run in report["runs"]:
        run_groups[(run["workload_group"], run["policy"], run["budget"])].append(run)
    selected_resources = defaultdict(list)
    for (workload, policy, budget), runs in run_groups.items():
        for run in runs:
            candidate_id = run["selected_candidate_id"]
            if candidate_id is None:
                continue
            candidate = candidate_by_id.get(candidate_id)
            if candidate is None:
                raise ValueError("Selected candidate is absent from the hash-bound measured corpus")
            if candidate["workload_group"] != workload:
                raise ValueError("Selected candidate crosses workload groups")
            if candidate["correctness_verified"] is not True:
                raise ValueError("A selected candidate is not correctness-verified")
            if (candidate["area_delta_lut4"] > protocol["area_cap_lut4"]
                    or candidate["routed_fmax_min_mhz"] < protocol["minimum_routed_fmax_mhz"]):
                raise ValueError("A selected result violates the frozen hardware constraints")
            if not math.isclose(float(candidate["speedup"]), float(run["best_speedup"]), abs_tol=1e-12):
                raise ValueError("Selected candidate speedup does not match the policy replay")
            selected_resources[(workload, policy, budget)].append(candidate)

    hardware_rows = []
    resource_by_key = {}
    for policy in sorted(available):
        for budget in (1, 2, 3):
            group_areas, group_fmax = [], []
            workload_coverages = []
            selected_count = total_count = 0
            selected_candidates = []
            for workload in sorted(expected_workloads):
                key = (workload, policy, budget)
                runs = run_groups.get(key, [])
                if not runs:
                    raise ValueError(f"Missing policy replay rows for resource summary: {key}")
                total_count += len(runs)
                selected = selected_resources.get(key, [])
                selected_count += len(selected)
                workload_coverages.append(len(selected) / len(runs))
                if selected:
                    group_areas.append(statistics.mean(float(row["area_delta_lut4"]) for row in selected))
                    group_fmax.append(statistics.mean(float(row["routed_fmax_min_mhz"]) for row in selected))
                    selected_candidates.extend(selected)
            if group_areas:
                area, area_lo, area_hi = mean_interval(group_areas, rng)
                mean_fmax = statistics.mean(group_fmax)
                median_area = statistics.median(group_areas)
                min_fmax = min(float(row["routed_fmax_min_mhz"]) for row in selected_candidates)
                max_area = max(float(row["area_delta_lut4"]) for row in selected_candidates)
            else:
                area = area_lo = area_hi = mean_fmax = median_area = min_fmax = max_area = None
            resource = {
                "policy": policy,
                "budget": budget,
                "workload_groups": len(expected_workloads),
                "selected_workload_groups": len(group_areas),
                "selection_coverage_macro": statistics.mean(workload_coverages),
                "selected_policy_seed_context_runs": selected_count,
                "all_policy_seed_context_runs": total_count,
                "mean_area_delta_lut4": area,
                "area_ci_low_lut4": area_lo,
                "area_ci_high_lut4": area_hi,
                "median_workload_mean_area_delta_lut4": median_area,
                "maximum_selected_area_delta_lut4": max_area,
                "mean_selected_min_routed_fmax_mhz": mean_fmax,
                "minimum_selected_min_routed_fmax_mhz": min_fmax,
                "selected_correctness_verified_count": selected_count,
                "area_budget_lut4": protocol["area_cap_lut4"],
                "minimum_routed_fmax_mhz": protocol["minimum_routed_fmax_mhz"],
            }
            hardware_rows.append(resource)
            resource_by_key[(policy, budget)] = resource
    write_csv(OUT / "selected_hardware_metrics.csv", list(hardware_rows[0]), hardware_rows)

    paired = [r for r in report["paired_contrasts"]
              if r["baseline"] == "merit" and r["challenger"] in MODEL_CHALLENGERS]
    if len(paired) != 9:
        raise ValueError("Expected archived paired contrasts for three challengers × three budgets")
    write_csv(OUT / "paired_regret_vs_merit.csv", list(paired[0]), paired)

    draw_frontier(
        OUT / "best_verified_cycle_reduction.svg", by_key,
        metric="mean_cycle_reduction", ci_low="cycle_reduction_ci_low", ci_high="cycle_reduction_ci_high",
        ylabel="Mean best verified whole-program cycle reduction (%)",
        title="Best verified cycle reduction at matched evaluation budgets",
        description="Whole-workload held-out replay on consumed development data. Error bars are 95% workload bootstrap intervals over fourteen independent workload groups; five seeds are averaged within workload.",
        y_max=0.025,
    )
    draw_frontier(
        OUT / "oracle_regret.svg", by_key,
        metric="mean_cycle_reduction_regret", ci_low="regret_ci_low", ci_high="regret_ci_high",
        ylabel="Mean regret to complete measured feasible-pool oracle (%)",
        title="Regret to the measured feasible-pool oracle",
        description="Retrospective LOCO replay. Regret uses only twelve workload groups with complete verified candidate-pool oracles; two infrastructure-censored groups are excluded. Whiskers are descriptive workload bootstrap intervals.",
        y_max=0.018,
    )
    draw_paired_forest(OUT / "paired_regret_vs_merit.svg", paired)
    draw_heatmap(OUT / "workload_regret_differences.svg", group_rows)
    draw_hardware_tradeoff(OUT / "measured_area_performance.svg", by_key, resource_by_key)

    # Keep host-side score generation separate from target measurement cost.
    ranker_timing_path = ROOT / "results/2026-10-26-feasible-benefit-ranker-screen/report.json"
    utility_timing_path = ROOT / "results/2026-10-26-feasible-benefit-utility-screen/report.json"
    ranker_timing = json.loads(ranker_timing_path.read_text())["model_timing"]
    utility_timing = json.loads(utility_timing_path.read_text())["model_timing"]
    combined_order_seconds = statistics.mean(
        float(row["order_generation_seconds"]) for row in report["model_timing"]
    )
    overhead_rows = [
        {"timing_kind": "combined candidate-order generation", "model": "speedup regressor + pairwise ranker + ordering",
         "fit_seconds": "", "inference_seconds": "", "combined_fit_and_score_seconds": combined_order_seconds,
         "training_rows": "fold-dependent", "scored_candidates": "pool-dependent",
         "scope": "mean of 15 contexts in broad LOCO screen; combined timer does not isolate either model"},
        {"timing_kind": "ranker fit/inference", "model": "xgb_feasible_benefit_ranker",
         "fit_seconds": ranker_timing[0]["model_fit_seconds"],
         "inference_seconds": ranker_timing[0]["inference_seconds"], "training_rows": ranker_timing[0]["fit_training_rows"],
         "combined_fit_and_score_seconds": "", "scored_candidates": ranker_timing[0]["target_candidates"],
         "scope": "single held-out context; distinct measured-feasible-benefit relevance target"},
        {"timing_kind": "utility model fit/inference", "model": "existing_feasible_benefit_xgb",
         "fit_seconds": utility_timing[0]["fit_seconds"],
         "inference_seconds": utility_timing[0]["inference_seconds"], "training_rows": utility_timing[0]["training_rows"],
         "combined_fit_and_score_seconds": "", "scored_candidates": utility_timing[0]["target_candidates"],
         "scope": "single held-out context; existing utility model, not the pairwise ranker"},
    ]
    write_csv(OUT / "model_scoring_overhead.csv", list(overhead_rows[0]), overhead_rows)

    pairwise = {(r["budget"]): r for r in paired if r["challenger"] == "xgb_pairwise_ranker"}
    merit = {r["budget"]: r for r in metrics_rows if r["policy"] == "merit"}
    factorized = {r["budget"]: r for r in metrics_rows if r["policy"] == "factorized_feasibility_xgb"}
    shortlist_lines = [
        "| Policy | Budget | Best verified cycle reduction (95% workload CI) | Oracle regret (95% CI; 12 complete pools) | Target evaluation time (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for policy in ("merit", "xgb_pairwise_ranker", "xgb_speedup_regression", "factorized_feasibility_xgb"):
        for budget in (1, 2, 3):
            row = by_key[(policy, budget)]
            shortlist_lines.append(
                f"| {LABELS[policy]} | {budget} | "
                f"{100*row['mean_cycle_reduction']:.3f}% [{100*row['cycle_reduction_ci_low']:.3f}, {100*row['cycle_reduction_ci_high']:.3f}] | "
                f"{100*row['mean_cycle_reduction_regret']:.3f}% [{100*row['regret_ci_low']:.3f}, {100*row['regret_ci_high']:.3f}] | "
                f"{row['mean_target_evaluation_seconds']:.2f} |"
            )
    pairwise_lines = []
    for budget in (1, 2, 3):
        row = pairwise[budget]
        pairwise_lines.append(
            f"- B{budget}: {100*row['mean']:+.3f} percentage points "
            f"(95% CI {100*row['lower_95']:+.3f} to {100*row['upper_95']:+.3f}; "
            f"workload wins/ties/losses {row['wins']}/{row['ties']}/{row['losses']})."
        )
    hardware_lines = [
        "| Budget | Merit: coverage / mean added LUT4 / mean min-routed Fmax | Pairwise XGB: coverage / mean added LUT4 / mean min-routed Fmax |",
        "|---:|---:|---:|",
    ]
    for budget in (1, 2, 3):
        cells = []
        for policy in ("merit", "xgb_pairwise_ranker"):
            resource = resource_by_key[(policy, budget)]
            cells.append(
                f"{100*resource['selection_coverage_macro']:.1f}% / "
                f"{resource['mean_area_delta_lut4']:.1f} LUT4 / "
                f"{resource['mean_selected_min_routed_fmax_mhz']:.1f} MHz"
            )
        hardware_lines.append(f"| {budget} | {cells[0]} | {cells[1]} |")
    minimum_selected_fmax = min(
        float(row["minimum_selected_min_routed_fmax_mhz"])
        for row in hardware_rows if row["minimum_selected_min_routed_fmax_mhz"] is not None
    )
    timing_floor = float(protocol["minimum_routed_fmax_mhz"])
    report_md = f"""# Final selection scorecard — October 27, 2026

This is a reproducible summary of the archived, retrospective, consumed-data
whole-workload-holdout screen at
[`2026-10-26-feasibility-model-screen`](../2026-10-26-feasibility-model-screen/).
It is not an independent test and no selector is promoted by this scorecard.

## Decision

Carry **XGBoost `rank:pairwise`** forward as the single ML challenger for the
next frozen, prospective cohort. Keep the existing merit heuristic as the
operational fallback and strongest comparison. This is a test-priority choice,
not evidence that ML wins. Pairwise ranking is the most balanced candidate
across budgets: its measured regret is {100*pairwise[1]['mean']:.3f} percentage
points lower than merit at one query and {100*pairwise[2]['mean']:.3f} points
lower at two queries, then {abs(100*pairwise[3]['mean']):.3f} points worse at three.
The archived paired intervals cross zero at the first two budgets; at budget
three the point estimate favors merit and its interval touches zero at the
boundary. The matched XGBoost-versus-merit contrasts are:
{chr(10).join(pairwise_lines)}
A feasibility XGBoost policy is stronger at the
one-query point estimate (regret {100*factorized[1]['mean_cycle_reduction_regret']:.3f}%)
but degrades to {100*factorized[3]['mean_cycle_reduction_regret']:.3f}% by three
queries. The mixed ranking is why none is promoted as the universal winner.

## What was evaluated

- 122 successful, measured candidate labels and four charged failures across
  14 held-out workload groups; 12 groups have complete verified candidate-pool
  oracles. The two incomplete oracles are excluded from regret, while observed
  best verified speedup is still summarized across all 14.
- Each fold holds out an entire workload and removes related operation-tree
  families from training. Five selector seeds and repeated contexts are
  averaged within workload; they do not increase the independent sample size.
- These 14 workload-group folds are still a consumed development cohort, not
  the six-independent-source-family confirmatory cohort required by the
  project contract. Candidate selection here is single-instruction; combined
  instruction sets have not been measured in this scorecard.
- All methods receive the same 1, 2, or 3 attempted hardware evaluations.
  The endpoint is the best actually measured, correct result meeting the
  +64-LUT4 and 12-MHz constraints. Failed attempts consume budget and time.
- Selected-design area and minimum routed Fmax are joined to the hash-bound
  measured corpus. These resource means are conditional on finding a verified
  feasible winner; selection coverage is shown separately, so a missing winner
  is not treated as a zero-area result.
- The paired confidence intervals below are the source report's workload
  bootstrap intervals. The frontier intervals are independently recomputed
  with {BOOTSTRAP_DRAWS:,} deterministic workload bootstrap draws. They are
  descriptive intervals over consumed data, not confirmatory inference.

## Research outcome

The regret leader changes with budget: factorized feasibility XGBoost (tied
with logistic feasibility) at one query, pairwise XGBoost at two, and merit at
three. At three queries pairwise
regret is {100*(merit[3]['mean_cycle_reduction_regret']-pairwise[3]['mean']):.3f}%
versus merit's {100*merit[3]['mean_cycle_reduction_regret']:.3f}% (a
{abs(100*pairwise[3]['mean']):.3f}-point disadvantage for pairwise).
The measured pairwise advantage at budgets one and two is too uncertain and
small to support an ML-superiority claim. There is no justification for another
model-family sweep on these same 122 labels.

{chr(10).join(shortlist_lines)}

For the selected feasible winners, mean added area and mean minimum routed
Fmax compare as follows. The minimum selected-design Fmax is
{minimum_selected_fmax:.2f} MHz, {minimum_selected_fmax-timing_floor:.2f} MHz above
the frozen timing floor; timing is not boundary-challenging in this cohort.

{chr(10).join(hardware_lines)}

The speedup labels equal the independent calibrated-latency estimates exactly,
so this corpus does not yet demonstrate that XGBoost learns residual
program-level speedup behavior. The selector comparison mainly tests ranking
and hardware-feasibility decisions. The broad screen's combined order-generation
timer (XGB regression, pairwise ranking and ordering together) averages
{combined_order_seconds:.3f} seconds across 15 contexts; it does not isolate the
pairwise model. A separate measured-benefit ranker example fit in
{ranker_timing[0]['model_fit_seconds']:.3f} seconds and scored twelve candidates
in {ranker_timing[0]['inference_seconds']:.4f} seconds, but it uses a different
training relevance target. These host timings are small relative to target
evaluation time, yet the exact selected ranker's fit/inference duration should
be recorded in the next frozen run.

## Figures and files

- [`best_verified_cycle_reduction.svg`](best_verified_cycle_reduction.svg):
  achieved measured improvement versus query budget.
- [`oracle_regret.svg`](oracle_regret.svg): regret versus complete measured
  feasible-pool oracle; censored pools are excluded.
- [`paired_regret_vs_merit.svg`](paired_regret_vs_merit.svg): matched,
  workload-level ML-versus-merit contrasts and archived intervals.
- [`workload_regret_differences.svg`](workload_regret_differences.svg):
  per-workload heterogeneity; gray cells are oracle-censored.
- [`measured_area_performance.svg`](measured_area_performance.svg): measured
  area/performance trade-off among selected feasible designs.
- [`policy_metrics.csv`](policy_metrics.csv): policy-by-budget aggregate
  metrics and uncertainty intervals.
- [`workload_level_metrics.csv`](workload_level_metrics.csv): one row per
  workload, policy and budget.
- [`selected_hardware_metrics.csv`](selected_hardware_metrics.csv): selected
  area, minimum routed Fmax, and selection coverage under the fixed constraints.
- [`paired_regret_vs_merit.csv`](paired_regret_vs_merit.csv): matched paired
  contrasts from the archived experiment.
- [`model_scoring_overhead.csv`](model_scoring_overhead.csv): fit/inference and
  combined-order timing with each timing scope stated; not pooled with
  target-measurement time.

## Next confirmatory milestone

Freeze the pairwise ranker, merit, frequency, timing-aware merit, and random
policies before any fresh candidate outcomes. Use an untouched eligible
workload/family cohort, identical measurement budgets, and complete-oracle
regret where feasible. Report query count, actual target measurement time,
fit/inference time, correctness, area, timing, best verified performance, and
paired workload-level intervals. If no independent cohort qualifies under the
unchanged gates, say so and retain this as development-only evidence.

## Provenance

- Primary result: `{report_path.relative_to(ROOT)}` (SHA-256 `{report_hash}`).
- Frozen protocol SHA-256: `{protocol_hash}`; source manifest SHA-256:
  `{manifest_hash}`.
- Source data corpus SHA-256: `{protocol['corpus_sha256']}`.
- Regenerate: `python3 scripts/build_research_selection_scorecard.py`.
"""
    (OUT / "README.md").write_text(report_md, encoding="utf-8")

    summary = {
        "schema": "isaforge-research-selection-scorecard-v1",
        "scope": "retrospective consumed-data model selection; not independent confirmation",
        "inputs": {
            "primary_report": str(report_path.relative_to(ROOT)),
            "primary_report_sha256": report_hash,
            "protocol_sha256": protocol_hash,
            "source_manifest_sha256": manifest_hash,
            "corpus_sha256": protocol["corpus_sha256"],
            "builder_script": str(Path(__file__).resolve().relative_to(ROOT)),
            "builder_script_sha256": sha256(Path(__file__).resolve()),
        },
        "workload_groups": len(expected_workloads),
        "successful_measured_labels": protocol["successful_measured_rows"],
        "charged_failures": protocol["charged_failed_attempts"],
        "complete_oracle_groups": 12,
        "censored_oracle_groups": 2,
        "confirmatory_independent_source_families_established": False,
        "combined_instruction_sets_evaluated": False,
        "budget_candidates": [1, 2, 3],
        "selection_decision": {
            "prospective_ml_challenger": "xgb_pairwise_ranker",
            "operational_fallback": "merit",
            "promotion": False,
            "rationale": "Most balanced ML challenger across budgets in consumed-data LOCO; advantage is small/uncertain at budgets one and two, and merit is better at three.",
        },
        "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED,
                      "unit": "workload group; repeated contexts and selector seeds averaged within group"},
        "policy_metrics": metrics_rows,
        "selected_hardware_metrics": hardware_rows,
        "paired_regret_vs_merit": paired,
    }
    (OUT / "scorecard.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name not in {"manifest.json", "manifest.json.sha256"})
    manifest = {
        "schema": "isaforge-research-selection-scorecard-manifest-v1",
        "builder_script": str(Path(__file__).resolve().relative_to(ROOT)),
        "builder_script_sha256": sha256(Path(__file__).resolve()),
        "files": {str(p.relative_to(OUT)): sha256(p) for p in files},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "manifest.json.sha256").write_text(sha256(OUT / "manifest.json") + "  manifest.json\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "files": len(files),
        "models": sorted(available),
        "budgets": [1, 2, 3],
        "workloads": len(expected_workloads),
        "complete_oracles": 12,
        "pairwise_regret_advantage_vs_merit_percentage_points": {
            str(b): round(100 * pairwise[b]["mean"], 6) for b in (1, 2, 3)
        },
        "manifest_sha256": sha256(OUT / "manifest.json"),
    }, indent=2))


if __name__ == "__main__":
    main()

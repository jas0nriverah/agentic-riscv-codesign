#!/usr/bin/env python3
"""Render publication-style plots from the sealed PULPino Sudoku r4 results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "results/2026-10-28-pulpino-sudoku-selection-r4"
DEFAULT_OUTPUT = ROOT / "reports/2026-10-28-pulpino-sudoku-selector-r4"
AREA_CAP = 64
CLOCK_MHZ = 12.0


def save_figure(fig, output: Path, stem: str):
    for suffix in ("png", "svg"):
        path = output / f"{stem}.{suffix}"
        fig.savefig(path, dpi=220 if suffix == "png" else None,
                    bbox_inches="tight", facecolor="white")
        if suffix == "svg":
            # Matplotlib's path serialization leaves trailing spaces in SVG
            # coordinate lines; remove them for clean diffs and linting.
            lines = path.read_text().splitlines()
            path.write_text("\n".join(line.rstrip() for line in lines) + "\n")


def load_json(path: Path):
    return json.loads(path.read_text())


def cycle_reduction(speedup: float) -> float:
    return 100.0 * (1.0 - 1.0 / speedup)


def policy_curves(report: dict, policies: list[str], cap: int = AREA_CAP):
    output = {}
    for policy in policies:
        runs = [run for run in report["runs"]
                if run.get("policy") == policy
                and run.get("area_delta_lut4_cap", run.get("cap")) == cap]
        if not runs:
            continue
        by_budget = {}
        for run in runs:
            for point in run["curve"]:
                by_budget.setdefault(point["budget"], []).append(
                    100.0 * point.get("best_so_far_cycle_reduction",
                                     1.0 - 1.0 / point["best_speedup"]))
        output[policy] = {
            budget: sum(values) / len(values)
            for budget, values in sorted(by_budget.items())
        }
    return output


def plot_candidate_tradeoffs(results: Path, output: Path):
    outcomes = load_json(results / "outcomes.json")
    names = {row["candidate_id"]: row["name"]
             for row in load_json(results / "native-audit.json")["successful"]}
    agent = load_json(results / "agent-report.json")
    attempted = set(agent["attempted_candidate_ids"])
    baseline_cycles = 1_024_889

    feasible = [row for row in outcomes
                if row.get("correctness_verified") is True
                and row.get("device_fits") is True
                and row["area_delta_lut4"] <= AREA_CAP
                and row["routed_fmax_min_mhz"] >= CLOCK_MHZ]
    infeasible = [row for row in outcomes if row not in feasible]

    fig, ax = plt.subplots(figsize=(10.8, 6.2), constrained_layout=True)
    ax.scatter([row["area_delta_lut4"] for row in infeasible],
               [cycle_reduction(baseline_cycles / row["candidate_cycles"])
                for row in infeasible],
               s=86, color="#c9504f", edgecolor="white", linewidth=0.8,
               label="Exceeds +64 LUT4 cap", zorder=3)
    ax.scatter([row["area_delta_lut4"] for row in feasible],
               [cycle_reduction(baseline_cycles / row["candidate_cycles"])
                for row in feasible],
               s=105, color="#16856b", edgecolor="white", linewidth=0.8,
               label="Correct, timing- and area-feasible", zorder=4)
    ax.axvline(AREA_CAP, color="#263445", linestyle="--", linewidth=1.4,
               label="Area cap (+64 LUT4)")

    # A black outline marks the three candidates the live LLM episode measured.
    for row in outcomes:
        if row["candidate_id"] in attempted:
            ax.scatter(row["area_delta_lut4"],
                       cycle_reduction(baseline_cycles / row["candidate_cycles"]),
                       s=180, facecolors="none", edgecolors="#111827",
                       linewidth=1.5, zorder=5)

    labels = {
        "candidate_00": "C00 · live probe",
        "candidate_01": "C01 · live probe",
        "candidate_02": "C02 · measured oracle",
        "candidate_09": "C09 · other feasible",
        "candidate_11": "C11 · live probe",
    }
    offsets = {
        "candidate_00": (7, -2),
        "candidate_01": (7, -8),
        "candidate_02": (8, 1.0),
        "candidate_09": (7, -1.0),
        "candidate_11": (7, -0.2),
    }
    for row in outcomes:
        name = names[row["candidate_id"]]
        if name not in labels:
            continue
        y = cycle_reduction(baseline_cycles / row["candidate_cycles"])
        dx, dy = offsets[name]
        ax.annotate(labels[name], (row["area_delta_lut4"], y),
                    xytext=(dx, dy), textcoords="offset points", fontsize=9,
                    arrowprops=dict(arrowstyle="-", color="#7b8794", lw=0.8))

    ax.set_title("Measured speed–area trade-off on PULPino Sudoku", loc="left",
                 fontsize=16, weight="bold", pad=14)
    ax.text(0, 1.015,
            "12 automatically extracted instructions · fixed puzzle · all 12 correct and above the 12 MHz timing constraint",
            transform=ax.transAxes, fontsize=9.5, color="#526170")
    ax.set_xlabel("Added LUT4 cells", fontsize=11)
    ax.set_ylabel("Whole-program cycle reduction (%)", fontsize=11)
    ax.set_xlim(0, 150)
    ax.set_ylim(-0.12, 5.2)
    ax.grid(axis="both", color="#dce2e8", linewidth=0.8, alpha=0.75)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.text(0.0, -0.19,
            "Black rings show the LLM's three paid probes. Cycle reduction is computed from measured cycles; routed Fmax is a hard feasibility check, not a speedup multiplier.",
            transform=ax.transAxes, fontsize=8.5, color="#526170")
    save_figure(fig, output, "candidate-tradeoff")
    plt.close(fig)


def plot_selection_curves(results: Path, output: Path):
    report = load_json(results / "factorized-policy-report.json")
    agent = load_json(results / "agent-report.json")
    policies = ["merit", "ranking", "factorized_feasibility_xgb",
                "hybrid_gp_zero_shot", "hybrid_gp_adapt", "random"]
    values = policy_curves(report, policies)
    agent_values = {point["budget"]: cycle_reduction(point["best_speedup"])
                    for point in agent["budget_curve"]}
    oracle = cycle_reduction(load_json(results / "study-report.json")["oracle_speedup"])

    styling = {
        "merit": ("Merit heuristic", "#425466", "o", "-"),
        "ranking": ("Pairwise XGBoost ranker", "#2867a5", "s", "-"),
        "factorized_feasibility_xgb": ("Factorized XGBoost", "#8b5cf6", "D", "-"),
        "hybrid_gp_zero_shot": ("Active learning · GP zero-shot", "#d78327", "^", "-"),
        "hybrid_gp_adapt": ("Active learning · GP adaptation", "#b65a38", "v", "-"),
        "random": ("Random (mean of 5 seeds)", "#697784", "x", ":"),
    }
    fig, ax = plt.subplots(figsize=(10.8, 6.3), constrained_layout=True)
    x = [1, 2, 3]
    for policy, curve in values.items():
        label, color, marker, line = styling[policy]
        ys = [curve.get(budget, 0.0) for budget in x]
        ax.plot(x, ys, label=label, color=color, marker=marker,
                linestyle=line, linewidth=2.0, markersize=6)
    ax.plot(x, [agent_values.get(budget, 0.0) for budget in x],
            label="Live LLM selector (one episode)", color="#c43b3b",
            marker="X", linestyle="-", linewidth=2.4, markersize=8,
            zorder=5)
    ax.axhline(oracle, color="#16856b", linestyle="--", linewidth=1.8,
               label=f"Measured feasible-pool oracle ({oracle:.3f}%)")
    ax.set_title("Verified performance found under a measurement budget", loc="left",
                 fontsize=16, weight="bold", pad=14)
    ax.text(0, 1.015,
            "Primary constraint: +64 LUT4, routed Fmax ≥12 MHz · 12-candidate pool · each budget point is best verified feasible candidate so far",
            transform=ax.transAxes, fontsize=9.5, color="#526170")
    ax.set_xlabel("Paid candidate measurements", fontsize=11)
    ax.set_ylabel("Best whole-program cycle reduction (%)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xlim(0.85, 3.15)
    ax.set_ylim(-0.08, oracle * 1.22)
    ax.grid(axis="both", color="#dce2e8", linewidth=0.8, alpha=0.75)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=8.7, ncol=2)
    ax.text(0.0, -0.18,
            "Non-agent curves are five dependent policy/algorithm seeds on the same workload, not independent workload replicates. The live agent is a single Codex chat-relay episode.",
            transform=ax.transAxes, fontsize=8.5, color="#526170")
    save_figure(fig, output, "budgeted-selection")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plot_candidate_tradeoffs(args.results, args.output)
    plot_selection_curves(args.results, args.output)
    print(f"Wrote plots to {args.output}")


if __name__ == "__main__":
    main()

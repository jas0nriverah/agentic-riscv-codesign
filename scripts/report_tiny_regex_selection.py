"""Build concise, reproducible figures and CSVs from the sealed r2 study."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c

RESULTS = ROOT / "results/2026-10-28-tiny-regex-c-selection-r2"
OUTPUT = ROOT / "reports/2026-10-28-tiny-regex-selector-r2-final"
AREA_CAP = 64


def require(condition, message):
    c.require(bool(condition), message)


def _load_results():
    manifest = c.unseal(RESULTS / "manifest.json")
    for relative, expected in manifest.items():
        path = RESULTS / relative
        require(path.is_file() and c.sha(path) == expected,
                "Sealed study input differs: " + relative)
    return {
        "report": c.unseal(RESULTS / "study-report.json"),
        "outcomes": c.unseal(RESULTS / "outcomes.json"),
        "audit": c.unseal(RESULTS / "native-audit.json"),
        "policies": c.unseal(RESULTS / "factorized-policy-report.json"),
        "manifest_sha256": c.sha(RESULTS / "manifest.json"),
    }


def _cycle_reduction(speedup):
    return 1.0 - 1.0 / speedup


def _write_candidate_csv(data):
    report, outcomes, audit = data["report"], data["outcomes"], data["audit"]
    public = audit["public"]
    names = audit["pool_names"]
    require(len(public) == len(names) == len(outcomes) == 12,
            "Expected the complete measured twelve-candidate roster")
    name_by_id = {row["candidate_id"]: name for row, name in zip(public, names)}
    baseline_cycles = report["baseline"]["performance"]["cycles"]
    output = OUTPUT / "measured-candidates.csv"
    fields = ["candidate", "candidate_id", "formula", "baseline_cycles",
              "candidate_cycles", "cycles_saved", "cycle_reduction_percent",
              "speedup", "added_lut4", "total_lut4", "routed_fmax_min_mhz",
              "correctness_verified", "device_fits", "fits_plus64_lut4_budget",
              "measurement_seconds"]
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in outcomes:
            writer.writerow({
                "candidate": name_by_id[row["candidate_id"]],
                "candidate_id": row["candidate_id"],
                "formula": row["formula"],
                "baseline_cycles": row["baseline_cycles"],
                "candidate_cycles": row["candidate_cycles"],
                "cycles_saved": row["baseline_cycles"] - row["candidate_cycles"],
                "cycle_reduction_percent": 100 * _cycle_reduction(row["speedup"]),
                "speedup": row["speedup"],
                "added_lut4": row["area_delta_lut4"],
                "total_lut4": report["baseline"]["resources"]["lut4_count"] + row["area_delta_lut4"],
                "routed_fmax_min_mhz": row["routed_fmax_min_mhz"],
                "correctness_verified": row["correctness_verified"],
                "device_fits": row["device_fits"],
                "fits_plus64_lut4_budget": row["area_delta_lut4"] <= AREA_CAP,
                "measurement_seconds": row["measurement_seconds"],
            })
    return output


def _candidate_frontier(data):
    report, outcomes, audit = data["report"], data["outcomes"], data["audit"]
    baseline = report["baseline"]["performance"]["cycles"]
    names = {row["candidate_id"]: name
             for row, name in zip(audit["public"], audit["pool_names"])}
    selected_id = report["agent"]["selected_id"]
    fastest_raw = max(outcomes, key=lambda row: row["speedup"])

    fig, ax = plt.subplots(figsize=(12.0, 6.2), constrained_layout=True)
    feasible = [row for row in outcomes if row["area_delta_lut4"] <= AREA_CAP]
    over_area = [row for row in outcomes if row["area_delta_lut4"] > AREA_CAP]
    for rows, color, label, marker in (
        (feasible, "#197c66", "Within +64 LUT4 budget", "o"),
        (over_area, "#c35c57", "Over +64 LUT4 budget", "X"),
    ):
        ax.scatter([row["area_delta_lut4"] for row in rows],
                   [100 * _cycle_reduction(row["speedup"]) for row in rows],
                   s=78, c=color, marker=marker, edgecolors="white", linewidths=0.7,
                   label=label, zorder=3)
    selected = next(row for row in outcomes if row["candidate_id"] == selected_id)
    ax.scatter([selected["area_delta_lut4"]],
               [100 * _cycle_reduction(selected["speedup"])],
               s=250, marker="*", facecolors="#f2b84b", edgecolors="#17324d",
               linewidths=1.2, label="LLM agent selection", zorder=5)
    if fastest_raw["candidate_id"] != selected_id:
        ax.scatter([fastest_raw["area_delta_lut4"]],
                   [100 * _cycle_reduction(fastest_raw["speedup"])],
                   s=150, marker="D", facecolors="none", edgecolors="#793d87",
                   linewidths=1.8, label="Fastest raw candidate", zorder=4)
    for row in outcomes:
        name = names[row["candidate_id"]].replace("candidate_", "")
        ax.annotate(name,
                    (row["area_delta_lut4"], 100 * _cycle_reduction(row["speedup"])),
                    xytext=(5, 4), textcoords="offset points", fontsize=8,
                    color="#25364a")
    ax.axvline(AREA_CAP, color="#26384b", linestyle="--", linewidth=1.3,
               label="Area budget")
    ax.set_xlabel("Added LUT4 cells")
    ax.set_ylabel("Measured whole-program cycle reduction (%)")
    ax.set_title("Measured performance–area tradeoff | tiny-regex-c")
    ax.text(0.01, 0.99,
            "12 candidates • all correctness-verified • one candidate measured at a time",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, color="#506176")
    ax.grid(axis="both", color="#d9e0e8", linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8.5)
    fig.savefig(OUTPUT / "measured-performance-area.png", dpi=220, facecolor="white")
    plt.close(fig)


def _budget_rows(data):
    report, policy_report = data["report"], data["policies"]
    runs = [run for run in policy_report["runs"]
            if run.get("cap", run.get("area_delta_lut4_cap")) == AREA_CAP]
    output = []
    policies = sorted({run["policy"] for run in runs})
    for policy in policies:
        selected_runs = [run for run in runs if run["policy"] == policy]
        for budget in (1, 2, 3):
            points = [next(point for point in run["curve"] if point["budget"] == budget)
                      for run in selected_runs]
            values = [100 * _cycle_reduction(point["best_speedup"]) for point in points]
            summary = next(row for row in policy_report["summary"]
                           if row["policy"] == policy and row["cap"] == AREA_CAP
                           and row["budget"] == budget)
            output.append({
                "policy": policy,
                "budget": budget,
                "seed_count": len(points),
                "mean_best_cycle_reduction_percent": float(np.mean(values)),
                "min_seed_cycle_reduction_percent": min(values),
                "max_seed_cycle_reduction_percent": max(values),
                "mean_measurement_seconds": summary["mean_target_measurement_seconds"],
                "mean_best_speedup": summary["mean_best_speedup"],
                "mean_cycle_reduction_regret": summary["mean_cycle_reduction_regret"],
                "mean_known_infeasible_attempts": summary["mean_known_infeasible_attempts"],
                "trajectory_scope": "five dependent policy seeds on one measured workload",
            })
    agent = report["agent"]
    for point in agent["budget_endpoints"]:
        output.append({
            "policy": "codex_chat_agent_hybrid_memory",
            "budget": point["budget"],
            "seed_count": 1,
            "mean_best_cycle_reduction_percent": 100 * point["best_so_far_cycle_reduction"],
            "min_seed_cycle_reduction_percent": 100 * point["best_so_far_cycle_reduction"],
            "max_seed_cycle_reduction_percent": 100 * point["best_so_far_cycle_reduction"],
            "mean_measurement_seconds": agent["target_measurement_seconds"],
            "mean_best_speedup": point["best_verified_feasible_speedup"],
            "mean_cycle_reduction_regret": point["cycle_reduction_regret"],
            "mean_known_infeasible_attempts": None,
            "trajectory_scope": f"one live relay episode; actual attempts used={point['actual_attempts_used']}",
        })
    return output


def _write_budget_csv(rows):
    output = OUTPUT / "budget-selection-summary.csv"
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


def _budget_plot(data, rows):
    report = data["report"]
    fig, ax = plt.subplots(figsize=(10.4, 6.2), constrained_layout=True)
    labels = {
        "frequency": ("Frequency", "#7a8795", "--"),
        "merit": ("Merit", "#343a40", "-"),
        "latency_cost_heuristic": ("Latency / cost", "#c77c22", "--"),
        "random": ("Random (mean)", "#8d99ae", ":"),
        "ranking": ("Pairwise XGBoost", "#197c66", "-"),
        "factorized_feasibility_xgb": ("Factorized XGBoost", "#79549b", "-"),
        "hybrid_gp_adapt": ("Adaptive GP", "#b75d88", "--"),
    }
    grouped = {}
    for row in rows:
        grouped.setdefault(row["policy"], []).append(row)
    for key, (label, color, style) in labels.items():
        series = sorted(grouped[key], key=lambda row: row["budget"])
        x = [row["budget"] for row in series]
        y = [row["mean_best_cycle_reduction_percent"] for row in series]
        ax.plot(x, y, label=label, color=color, linestyle=style, marker="o",
                linewidth=2.0 if key in ("merit", "ranking") else 1.5,
                markersize=5.5, zorder=2)
        if key == "random":
            ax.fill_between(x,
                            [row["min_seed_cycle_reduction_percent"] for row in series],
                            [row["max_seed_cycle_reduction_percent"] for row in series],
                            color=color, alpha=0.14, linewidth=0)
    agent = sorted(grouped["codex_chat_agent_hybrid_memory"],
                   key=lambda row: row["budget"])
    actual_x = [row["budget"] for row in agent
                if row["budget"] <= report["agent"]["charged_attempts"]]
    actual_y = [row["mean_best_cycle_reduction_percent"] for row in agent
                if row["budget"] <= report["agent"]["charged_attempts"]]
    ax.plot(actual_x, actual_y, label="LLM selector (one episode)", color="#1d5f91",
            marker="*", markersize=12, linewidth=2.5, zorder=4)
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Paid candidate evaluations (budget cap)")
    ax.set_ylabel("Best verified cycle reduction (%)")
    ax.set_title("Best feasible performance found under a matched evaluation budget")
    ax.text(0.01, 0.99,
            "+64 LUT4 • 12 MHz floor • oracle from all 12 measured candidates",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, color="#506176")
    ax.grid(axis="both", color="#d9e0e8", linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8.2, ncol=2, loc="lower right")
    fig.savefig(OUTPUT / "best-performance-by-budget.png", dpi=220, facecolor="white")
    plt.close(fig)


def _write_readme(data, candidate_csv, budget_csv):
    report = data["report"]
    baseline = report["baseline"]
    selected = next(row for row in data["outcomes"]
                    if row["candidate_id"] == report["agent"]["selected_id"])
    lines = [
        "# tiny-regex-c selector pilot: readable results",
        "",
        "This is one source/family-disjoint but related-domain transfer pilot. It does not establish that the ML or LLM selector beats strong heuristics or generalizes to unrelated programs.",
        "",
        "## Measured endpoint",
        "",
        f"- Baseline: **{baseline['performance']['cycles']:,} cycles**, {baseline['performance']['instructions']:,} instructions, {baseline['resources']['lut4_count']:,} LUT4, {baseline['resources']['carry_count']} carry cells, {baseline['resources']['memory_blocks']} RAM blocks, {baseline['resources']['flip_flop_count']} flip-flops, {baseline['minimum_routed_fmax_mhz']:.2f} MHz minimum routed Fmax.",
        f"- Agent selection: `{selected['formula']}`; **{selected['candidate_cycles']:,} cycles** ({selected['baseline_cycles']-selected['candidate_cycles']:,} fewer), **{selected['speedup']:.6f}×** ({100*(selected['speedup']-1):.4f}% speedup), +{selected['area_delta_lut4']} LUT4, {selected['routed_fmax_min_mhz']:.2f} MHz minimum routed Fmax, correctness verified.",
        f"- Agent used **{report['agent']['charged_attempts']} of 3** allowed measurements and selected the exact measured oracle winner. Cycle-reduction regret: **{report['agent']['cycle_reduction_regret']:.6f}**.",
        f"- First agent test: `{report['agent']['attempted_ids'][0]}` measured {next(row['area_delta_lut4'] for row in data['outcomes'] if row['candidate_id']==report['agent']['attempted_ids'][0])} additional LUT4 and violated the +64 LUT4 constraint. The second measurement fit at +60 LUT4.",
        f"- Complete pool: {report['target_attempts']} one-shot candidate measurements, {report['candidate_failures']} failures, {report['oracle_feasible_candidate_count']} candidates within the +64 LUT4 / 12 MHz constraints, oracle speedup **{report['oracle_speedup']:.6f}×**.",
        f"- Full-pool data collection cost: {report['actual_dataset_collection']['candidate_wall_seconds']:.1f} seconds of candidate evaluation time ({report['actual_dataset_collection']['candidate_outer_operation_seconds']:.1f} seconds including wrapper checks). This is the cost to establish the oracle, not the 2-measurement agent search budget.",
        "",
        "## Matched-budget comparison",
        "",
        "Merit, calibrated latency, pairwise XGBoost ranking, factorized XGBoost, raw regression, and normalized XGBoost also reached the measured feasible oracle by budget 2 in the frozen offline replays. The LLM selector therefore **matched** these controls on this pool; it did not beat the strongest heuristics. Frequency had not found a feasible improvement by budget 2 and reached 0.0614% mean cycle reduction by budget 3. The adaptive and zero-shot GP controls reached the oracle at budget 3. Random selection remained below the oracle on average. Five control seeds are dependent policy runs on this one candidate pool, not five independent workloads; the LLM result is one episode.",
        "",
        "The counterfactual policy curves release already measured candidate outcomes one at a time and account for each policy's own measurement prefix. Physically collecting the common oracle required all twelve evaluations. See the sealed study package for native jobs, evaluation times, full outcomes, model artifacts, decision requests, rationale links, and SQLite observability.",
        "",
        "![Measured candidate performance versus added LUT4](measured-performance-area.png)",
        "",
        "![Best verified performance versus candidate-evaluation budget](best-performance-by-budget.png)",
        "",
        "## AI engineering evidence and limits",
        "",
        "The model used 106 prior measured rows across 14 workload groups after excluding all 11 exact candidate-tree families in the target pool. Six SLRE rows remain, so this is related-domain text/regex transfer. The ranking model is XGBRanker (`rank:pairwise`); the feasibility model is a 20-member XGBoost ensemble whose output and disagreement are uncalibrated.",
        "",
        "The LLM received the frozen ML predictions, public frequency/merit/latency signals, top-three TF-IDF plus truncated-SVD semantic retrieval fused by reciprocal-rank fusion, and five structured tool decisions. The typed knowledge graph was built and hashed but was not queried in hybrid mode. SQLite observability is a read-only projection; the sealed JSON ledger is authoritative. This was a cooperative current-Codex chat relay, with no API model identifier, token counts, or isolated provider latency. The decision notes are concise public-evidence summaries linked to pre-measure contexts and host-verified outcomes; they are not validated chain-of-thought explanations.",
        "",
        "A first launch was separately preserved as a zero-call, zero-measurement stdin startup failure; it is not counted as a model decision or selection trial. The r5 preregistered interactive run is the one reported above.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "../work/audit-venv/bin/python scripts/report_tiny_regex_selection.py",
        "../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py verify",
        "```",
        "",
        f"Source study manifest SHA-256: `{data['manifest_sha256']}`.",
        f"Generated tables: `{candidate_csv.name}` and `{budget_csv.name}`.",
    ]
    (OUTPUT / "README.md").write_text("\n".join(lines) + "\n")


def generate():
    require(not OUTPUT.exists(), "Preserve prior derived report")
    OUTPUT.mkdir(parents=True)
    data = _load_results()
    candidate_csv = _write_candidate_csv(data)
    budget_rows = _budget_rows(data)
    budget_csv = _write_budget_csv(budget_rows)
    _candidate_frontier(data)
    _budget_plot(data, budget_rows)
    _write_readme(data, candidate_csv, budget_csv)
    files = {path.relative_to(OUTPUT).as_posix(): c.sha(path)
             for path in sorted(OUTPUT.rglob("*")) if path.is_file()}
    c.seal(OUTPUT / "manifest.json", files)
    print(json.dumps({"output": str(OUTPUT), "files": len(files),
                      "source_manifest_sha256": data["manifest_sha256"],
                      "selected_speedup": data["report"]["agent"]["selected_measured_speedup"],
                      "oracle_speedup": data["report"]["oracle_speedup"]}, indent=2))


if __name__ == "__main__":
    generate()

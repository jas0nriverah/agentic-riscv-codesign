"""Render slide-ready figures and a compact report from saved real results."""

import argparse
import html
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def render_report(experiment, model, benchmarks, candidate_summary, output, selection=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = read(Path(experiment) / "dataset.json")
    summary = read(Path(experiment) / "summary.json")
    report = read(Path(model) / "evaluation.json")
    runs = read(benchmarks)
    candidates = read(candidate_summary)
    predictions = [row for fold in report["folds"] if fold["status"] == "evaluated"
                   for row in fold["predictions"]]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white"})
    actual = np.asarray([row["measured_lut4"] for row in predictions])
    predicted = np.asarray([row["predicted_lut4"] for row in predictions])
    fig, ax = plt.subplots(figsize=(7.5, 5.6), layout="constrained")
    ax.scatter(actual + 1, predicted + 1, alpha=.55, s=35, color="#087e8b", edgecolors="none")
    extent = max(max(actual), max(predicted)) + 2
    ax.plot([1, extent], [1, extent], "--", color="#e58443", label="Perfect prediction")
    ax.set(xscale="log", yscale="log", xlabel="Synthesized LUT4 count + 1 (log scale)",
           ylabel="Held-out prediction + 1 (log scale)", title="Unseen-program resource predictions")
    ax.legend(frameon=False)
    fig.savefig(output / "held-out-predictions.png", dpi=190)
    plt.close(fig)

    metrics = report["pooled_metrics"]
    comparisons = dict(report["outer_model_comparison"])
    comparisons["nested_selection"] = metrics
    names = list(comparisons)
    labels = dict(mean="Mean baseline", ridge_log="Ridge", extra_trees_log="Extra Trees",
                  random_forest_log="Random forest", xgboost_log="XGBoost", nested_selection="Nested selection")
    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    values = [comparisons[name]["rmsle"] for name in names]
    bars = ax.barh([labels[name] for name in names], values,
                   color=["#087e8b" if name == "nested_selection" else "#a0b7c5" for name in names])
    ax.bar_label(bars, fmt="%.3f", padding=4)
    ax.set(xlabel="Held-out RMSLE (lower is better)", title="Model comparison on real synthesis labels")
    ax.set_xlim(0, max(values) * 1.18)
    ax.invert_yaxis()
    fig.savefig(output / "model-comparison.png", dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    for benchmark in sorted({row["benchmark"] for row in rows}):
        group = [row for row in rows if row["benchmark"] == benchmark]
        ax.scatter([row["lut4_count"] + 1 for row in group],
                   [row["overlap_safe_saved_percent"] for row in group], s=28, alpha=.6, label=benchmark)
    ax.set(xscale="log", xlabel="Synthesized LUT4 count + 1 (log scale)",
           ylabel="Estimated retired-instruction reduction (%)",
           title="Instruction-saving opportunities versus circuit cost")
    ax.legend(fontsize=8, frameon=False, ncol=2)
    fig.savefig(output / "candidate-tradeoffs.png", dpi=190)
    plt.close(fig)

    def num(value, digits=3):
        return "N/A" if value is None else f"{value:,.{digits}f}"

    fold_rows = "".join(
        f"<tr><td>{html.escape(fold['held_out_benchmark'])}</td><td>{fold['test_size']}</td>"
        f"<td>{html.escape(fold['selected_estimator'])}</td><td>{num(fold['metrics']['mae_lut4'])}</td>"
        f"<td>{num(fold['metrics']['rmsle'])}</td><td>{num(fold['metrics']['spearman'])}</td></tr>"
        for fold in report["folds"] if fold["status"] == "evaluated")
    counts = {row["benchmark"]: row for row in candidates["benchmarks"]}
    workload_rows = "".join(
        f"<tr><td>{html.escape(row['benchmark'])}</td><td>Pass</td><td>{row['trace_instructions']:,}</td>"
        f"<td>{counts[row['benchmark']]['candidateCount']}</td></tr>" for row in runs["benchmarks"])
    base = report["pooled_mean_baseline_metrics"]
    nonzero = metrics["nonzero_lut4_metrics"]
    selection_html = ""
    if selection:
        selected = read(selection)
        fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.3), sharey=True, layout="constrained")
        strategy_labels = dict(frequency="Frequency", merit="Merit", random="Random",
                               predicted_area_feasible_merit="Model-guided")
        colors = dict(frequency="#92a2ac", merit="#e58443", random="#bcc5ca",
                      predicted_area_feasible_merit="#087e8b")
        for ax, cap in zip(axes, selected["lut4_caps"]):
            for strategy in selected["strategies"]:
                points = sorted([item for item in selected["aggregates"]
                                 if item["strategy"] == strategy and item["lut4_cap"] == cap],
                                key=lambda item: item["measurement_budget"])
                ax.plot([item["measurement_budget"] for item in points],
                        [100 * item["mean_retained_oracle_instruction_saving_fraction"] for item in points],
                        marker="o", label=strategy_labels[strategy], color=colors[strategy])
            ax.set(title=f"{cap:g} LUT4 cap", xlabel="New candidate measurements", xticks=selected["measurement_budgets"], ylim=(0,105))
        axes[0].set_ylabel("Oracle instruction savings retained (%)")
        axes[-1].legend(fontsize=8, frameon=False, loc="lower right")
        fig.savefig(output / "selection-budgets.png", dpi=190)
        plt.close(fig)
        selection_html = """<h2>Does the model improve the choice?</h2>
<p>Using only outer-fold predictions, we replayed frequency, merit, random, and predicted-area-filtered merit at budgets of 1, 3, and 5 new candidate measurements, with LUT4 caps of 32, 64, and 128. Final choices must pass measured area verification. The oracle knows the full measured candidate pool.</p>
<img src="selection-budgets.png" alt="Mean oracle instruction-saving retention across three area caps and three measurement budgets">
<p><strong>At caps 64 and 128, one model-guided measurement retained 100% of oracle instruction savings across all eight programs, versus 87.5% mean retention for merit ranking.</strong> The improvement occurs in CRC32: merit first tests a 635-LUT circuit that violates the cap, while the model-guided policy finds an 8-LUT alternative.</p>
<p>This advantage is limited. With three measurements, merit reaches the oracle in all tested caps. At cap 32, prediction mistakes cause an infeasible first EDN attempt and reject WikiSort's zero-LUT optimum. The model-guided policy's mean one-measurement retention is 85.1%, versus 75% for merit.</p>
<p class="muted">Training measurements from other benchmarks are outside the target measurement budget. Only random ordering varies across five seeds; deterministic policies repeat, so there are eight workloads, not forty independent trials. These are instruction-saving estimates under an isolated LUT4 cap, not runtime speedups or a multi-instruction area budget.</p>"""
    body = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>ISAForge — measured midterm results</title><style>
body{{font:17px/1.6 system-ui,sans-serif;max-width:1050px;margin:45px auto;padding:0 28px;color:#172b3c}}
h1{{font-size:38px;line-height:1.15}}h2{{margin-top:36px}}a{{color:#087e8b}}table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{text-align:left;border-bottom:1px solid #d9e2e8;padding:11px}}th{{background:#edf3f6}}img{{max-width:100%}}
.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#edf6f7;padding:18px;flex:1;min-width:170px}}.card strong{{font-size:30px;display:block}}
.note{{background:#fff5e9;border-left:5px solid #e58443;padding:18px}}.muted{{color:#647582}}code{{font-size:13px}}
@media print{{body{{font-size:12px;margin:8px}}h2{{break-after:avoid}}img{{max-height:310px}}tr{{break-inside:avoid}}}}</style>
<p class="muted">ISAForge • Real experiment • October 13, 2026</p>
<h1>A trained model built on actual benchmark and synthesis data</h1>
<p>This session establishes a measured FPGA-resource predictor. It estimates an isolated candidate's iCE40 LUT4 usage from its formula, without running synthesis at inference time.</p>
<div class="cards"><div class="card"><strong>{len(runs['benchmarks'])}/8</strong>Benchmark self-checks passed</div>
<div class="card"><strong>{len(rows)}</strong>Measured candidate examples</div>
<div class="card"><strong>{summary['unique_circuits']}</strong>Distinct synthesized circuits</div></div>
<h2>Held-out model evidence</h2>
<p>Nested evaluation holds out an entire benchmark and excludes identical formulas from training. Inner folds choose among a mean baseline, Ridge, Extra Trees, random forest, and XGBoost. These configurations were fixed before inspecting this evaluation.</p>
<div class="cards"><div class="card"><strong>{num(metrics['mae_lut4'],2)}</strong>Mean absolute error, LUT4</div>
<div class="card"><strong>{num(metrics['spearman'])}</strong>Pooled Spearman rank correlation</div>
<div class="card"><strong>{num(metrics['rmsle'])}</strong>RMSLE, lower is better</div></div>
<p>The mean baseline's MAE is <strong>{num(base['mae_lut4'],2)} LUT4</strong> and RMSLE is <strong>{num(base['rmsle'])}</strong>.
The dataset includes <strong>{metrics['zero_lut4_count']}</strong> zero-LUT rows. On the {nonzero['sample_count']} nonzero-LUT rows, MAE is {num(nonzero['mae_lut4'],2)} and Spearman is {num(nonzero['spearman'])}.</p>
<p>The final saved model is <strong>{html.escape(report['final_estimator'])}</strong>, refit on all distinct training circuits. Its training fit is not presented as held-out performance. Pooled metrics weight candidate rows; the per-program results below expose uneven benchmark sizes.</p>
<img src="model-comparison.png" alt="Held-out comparison of candidate models">
<img src="held-out-predictions.png" alt="Actual versus held-out predicted LUT4 count">
<table><tr><th>Held-out benchmark</th><th>Examples</th><th>Inner-selected model</th><th>MAE (LUT4)</th><th>RMSLE</th><th>Spearman</th></tr>{fold_rows}</table>
<h2>Actual execution and correctness checks</h2>
<p>All traces passed retired-instruction counter validation with zero unknown instructions. Across the eight workloads, the traces contain <strong>{sum(row['trace_instructions'] for row in runs['benchmarks']):,}</strong> instructions.</p>
<table><tr><th>Benchmark</th><th>Self-check</th><th>Trace instructions</th><th>Candidate formulas</th></tr>{workload_rows}</table>
<p>Verilator checked <strong>{summary['verification']['total_comparisons']:,}</strong> candidate RTL outputs against an independent integer-semantics implementation, using boundary and seeded random inputs. All {summary['unique_circuits']} circuits synthesized successfully. These sampled checks are not a formal proof or integrated-processor validation.</p>
<h2>What the candidate pool tells us</h2>
<img src="candidate-tradeoffs.png" alt="Instruction-saving estimates versus measured LUT4 resource costs">
<p>Candidate savings are overlap-aware instruction-count estimates. Some patterns collapse to wires, constants, rotations, or identities. CRC32's highest-merit pattern is in <code>rand_beebs</code>; WikiSort's top pattern is an identity; the conservative two-input extractor finds only one candidate in matrix multiplication. These details constrain what we can claim about kernel acceleration.</p>
{selection_html}
<div class="note"><strong>Do not present these as CPU speedup results.</strong> We have not measured an integrated processor's cycles or routed clock period. LUT4 excludes carry-resource budgeting, decoder/mux/register overhead, placement, routing, and whole-core cost. Zero LUT4 does not mean a free integrated instruction. The model is specific to this compiler/workload/synthesis setup; cross-platform generalization and calibrated uncertainty remain untested.</div>
<h2>Research direction and next week</h2>
<p>Prior work already covers timing-aware selection and automated instruction integration. Our testable contribution is whether measured cost prediction improves selection under a limited evaluation budget. <a href="ISAForge-research-direction.html">Read the primary-source review and one-week plan</a>.</p>
<p>Next: test selection on additional workloads and integrate one or two candidates in one fixed core to obtain architectural cycles and implementation timing. Keep an LLM selector as an additional policy after the non-LLM baselines work.</p>
<p class="muted">Model, schema, dataset, detailed fold predictions, synthesis metrics, and reproduction commands accompany this report. A single fixed benchmark input and compiler configuration were used. Additional independent workloads are needed before making broad accuracy claims.</p></html>"""
    (output / "ISAForge-measured-results.html").write_text(body)
    return output / "ISAForge-measured-results.html"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default="generated/real/experiment")
    parser.add_argument("--model", default="generated/real/model")
    parser.add_argument("--benchmarks", default="generated/real/benchmarks.json")
    parser.add_argument("--candidate-summary", default="generated/real/candidate_summary.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--selection")
    args = parser.parse_args()
    print(render_report(args.experiment, args.model, args.benchmarks, args.candidate_summary, args.output, args.selection))


if __name__ == "__main__":
    main()

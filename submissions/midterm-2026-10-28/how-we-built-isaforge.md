# How we built ISAForge

This is a presentation companion and a map to the recorded scripts and evidence. The October 13 area study and the later processor-speedup corpus are **different datasets with different targets**; do not add their row counts together or call the first one's isolated LUT labels processor speedups.

## 1. Workload traces and the first hardware-cost dataset

The earlier project chat began with existing Spike tracing and dataflow candidate extraction. The team and AI coding assistants extended the code to compile and self-check eight Embench programs, parse their RV32IM execution traces, extract repeated legal expressions, check candidate behavior and synthesize the resulting isolated circuits.

- [`src/run_real_benchmarks.py`](../../src/run_real_benchmarks.py) builds, self-checks and traces the eight programs; [`src/tracing.py`](../../src/tracing.py) validates and decodes Spike commits. Spike supplies retired-instruction traces, not processor-cycle labels.
- [`src/candidates.py`](../../src/candidates.py) constructs and filters dataflow candidates, including input/output and legality checks.
- The October 13 pilot produced **339 candidate examples / 301 distinct synthesized formulas** from eight benchmarks; Verilator checked candidate RTL and Yosys mapped isolated candidate circuits to FPGA resources. The record includes **338,324 input/output comparisons**. The first XGBoost cost model's nested held-out error was **33.08 LUT4 versus 77.32 for a mean baseline** on that study. This is isolated hardware-cost prediction, not measured whole-program speedup. [Original evidence and exact methods](../../results/2026-10-13/README.md).

### The earlier dataset grew beyond the first pilot

The original 301-formula dataset was followed by transfer and final collections. Together the three collections contain **1,098 benchmark/formula rows and 713 distinct formulas**, including overlap across stages. Across 19 self-checking Embench programs, 17 produced candidate-bearing rows. The final set contained **331 formulas absent from training and calibration**. On those 331 isolated-cost labels, the frozen structural linear model had **23.154 LUT4 MAE**, versus **87.595** for the original XGBoost model. These are hardware-cost prediction results, not CPU-speedup or final-selection wins; the later all-713-formula refit has no independent test. The primary one-query +64-LUT selection endpoint tied merit. The first transfer selection was a negative result. [Results, frozen artifacts and limits](../../results/2026-10-13-prospective/README.md); [stage-by-stage methodology](../../docs/methodology-history.md).

## 2. Connect selection to processor measurements

The October 19 CRC32 study connected candidates to a PicoRV32 processor, so the performance label could come from executing the benchmark with the instruction installed. The unmodified CRC32 baseline ran in **32,387,382 simulated cycles**; the best of six tested extensions ran in **30,820,662 cycles** (1.050833× at a common clock). Integrated synthesis increased area from 1,653 to 1,684 LUT4. Correctness controls and routed timing were recorded. The six candidates included a slowdown, which was preserved. [Methods and all results](../../docs/codesign-loop.md).

[`isaforge/codesign.py`](../../isaforge/codesign.py) contains `ProcessorEvaluator`: it builds and verifies implementations, runs the processor evaluation, and calls Yosys and nextpnr for integrated area and routed timing. [`isaforge/workload_experiment.py`](../../isaforge/workload_experiment.py) extends the processor evaluation to supported workloads through prepare, discover, and collect stages. The successor aha-mont64 experiment used automatic extraction and lowering with the same processor setup. [Aha methodology and commands](../../docs/automatic-workloads.md).

Measurements are RTL-simulation cycle counts and FPGA synthesis/place-and-route estimates, not physical-chip stopwatch timings. The benchmark window and toolchain are part of the measurement contract; matching clock assumptions do not make instruction-count savings equivalent to cycles.

## 3. Build the model and evaluate selection

The guarded corpus expanded to **122 successful whole-program candidate measurements** across 14 workload groups, plus four charged failures. Each row joins premeasurement expression/profile features to measured speedup, integrated area, routed timing, and correctness. Data from prior studies and later Ascon measurements are not silently pooled as additional equivalent rows. [Data dictionary and CSVs](dataset/README.md).

- [`isaforge/features.py`](../../isaforge/features.py) validates the 35 candidate features; [`isaforge/ranking.py`](../../isaforge/ranking.py) implements the XGBoost pairwise ranker. Ranking labels are formed from measured speedup order within a workload context.
- [`scripts/evaluate_feasibility_model_families.py`](../../scripts/evaluate_feasibility_model_families.py) runs the retrospective whole-workload-holdout screen and matched-budget comparisons. [`scripts/explain_ranker_contributions.py`](../../scripts/explain_ranker_contributions.py) produces model-contribution analysis. Related candidate families are excluded from training folds.
- [`scripts/reproduce_codesign.py`](../../scripts/reproduce_codesign.py) and [`scripts/reproduce_workload.py`](../../scripts/reproduce_workload.py) verify archived CRC32 and aha results. These are replay/verification tools, not fresh hardware collection.

The final screen compared 13 policies (eight learned and five heuristic/random controls). Its 2,925 policy-budget replay records reused existing labels. The strongest point estimate varied with budget; no consistent ML advantage was established. All 122 historical cycle-speedup labels match independent calibrated latency estimates, so the corpus does not demonstrate a learned residual speedup signal. [Full scorecard](../../results/2026-10-27-final-selection-scorecard/README.md).

### A useful but limited ML result

A predeclared three-source campaign found that two GP selectors reached each measured-pool optimum at three queries, averaging **1.602185% cycle reduction versus merit’s 1.144539%**, under +64 LUT4 and 12 MHz. Its complete native pool was measured, followed by cooperative policy replay; this was not a live adaptive race or a demonstrated total-cost win. On the subsequent bitcount experiment, the latency/cost heuristic reached the feasible pool optimum within three queries while both GP policies returned baseline. This is a concrete example of promising source transfer that did not generalize consistently. [Campaign](../../docs/blind-source-campaign.md); [bitcount outcomes](../../results/2026-10-22-bitcount-report/results.md).

## 4. Add the LLM tool loop

The current LLM selector can inspect candidates, query predictions, request a bounded measurement and return a verified feasible choice. Separately, AI coding assistants helped develop and test scripts, inspect logs and review research; humans remain responsible for the experimental claims. The EDN chat trial was a consumed-data replay and the Ascon pilot measured three candidates, but neither established an agent advantage. In Ascon a status-handling defect prevented live GP updates; the fix was verified afterwards. [Agent pilot](../../docs/codex-chat-selector-pilot.md); [Ascon record](../../results/2026-10-27-ascon-selector-chat-run-v5/README.md).

## Useful replay commands

From the repo root with the pinned environment described in the linked guides:

```sh
python scripts/reproduce_codesign.py replay
python scripts/reproduce_workload.py replay
```

These commands replay and audit archived results; they do not claim to collect new labels. Fresh collection requires the pinned RISC-V toolchain, Verilator, Yosys, nextpnr, a newly prepared reference context, and the documented guards. See [automatic-workload instructions](../../docs/automatic-workloads.md). Reported fit, inference, search, and hardware times have different scopes and should not be added without checking their accounting.

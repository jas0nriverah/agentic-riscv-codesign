# One-hour ISAForge research continuation

## Completed work

Added six actual PicoRV32 candidate measurements across two newly qualified workload contexts. All six pass their fixed-input correctness checks; no new failed attempts. The authenticated development corpus now contains **162 successful labels, four historical failures and 19 workload groups**. The two forward studies used only the earlier 156-label corpus, retaining 141 and 133 rows after their target workload/family exclusions. The expanded 162 corpus is available for future training; these forward models were not trained on their own target results.

| Workload | Candidates | Primary +64-LUT4 result | Agent probes |
|---|---:|---|---:|
| Countnegative | 4 | 12,477→12,470 cycles; +55 LUT4; minimum routed Fmax 67.449 MHz. Agent and merit tie the oracle. | 1/3 |
| MiBench stringsearch | 2 | Baseline retained. Correct candidates add 70/100 LUT4, exceeding the cap. | 2/2 |

The six candidate attempts cost **212.331 seconds** of recorded paid evaluation time, excluding overlapping wrapper durations and separate baseline qualification. The total source-corpus attempt cost is 8,869.444 seconds, including the historical failures. Simulation measures cycles; hardware resources and timing come from synthesis/routing, not fabricated silicon results. Runtime comparisons use the fixed 12 MHz target. Routed Fmax is reported separately; no advantage at each design's maximum clock is claimed.

At Countnegative +32/B2, the fixed factorized feasibility model reaches the feasible oracle while merit's five-seed mean is lower. This is a prespecified sensitivity on one four-candidate source, not a primary-endpoint or general ML win. Stringsearch B2 exhausts its pool; B3 is explicitly capped to two attempts. Both live episodes used the current Codex chat relay with hybrid historical retrieval, structured tool calls, logged decision notes and host-enforced feasibility/budgets. No LLM fine-tuning, new API deployment or multi-model routing is claimed.

[All six measurements, all twelve controls, three area caps and budget curves](../2026-10-28-forward-selection-checkpoint/README.md).

## What the model analysis establishes

- Across all 162 successful labels, measured cycle savings exactly match the public analytic latency estimate. This is evidence about the supported fixed-latency patterns only. Another benefit-regression sweep has no demonstrated residual to correct here; the useful learning problem is hardware feasibility and measurement selection.
- A fixed retrospective sensitivity compared ordinary whole-workload holdout with the existing stricter workload-plus-formula-family holdout on the earlier 156-label corpus. Ordinary pairwise XGBoost ties merit at B3 (1.8079% mean cycle reduction); strict pairwise remains 1.7480%. This does not show superiority or isolate memorization, because training cohorts also change.
- The new exact-formula historical hardware-cache comparator has eight compatible hits out of 160 target attempts in ordinary splits and zero in strict splits. Cached history only ranks candidates; every target observation remains charged. No cached area/timing value is presented as a guaranteed bound.
- Raising the existing extractor's operation cap from 4 to 5/6 adds no legal candidates in these three recently qualified sources. Cap 4 is not the limiting factor for these pools. The archive-only replay preserves source mapping, dataflow, lowering, relocation and calibration checks.

[Transfer results and uncertainty](../2026-10-28-workload-transfer-summary-r1/README.md) · [Baseline-only extraction coverage](../2026-10-28-candidate-size-coverage-r5/README.md).

## Agent-loop reliability

The new serial completion coordinator waits for collection process exit and sealed audit readiness before evaluation, then verifies the result. It never starts a live agent, does not automatically retry failures, and verifies completed studies without rerunning hardware. Both completed studies passed its real verify-only path. Ten fake-subprocess tests exercise ordering/failure/locking behavior; these are not additional live policy trials.

The first stringsearch scoring launch happened before collection finished writing its audit and failed without launching hardware. The same frozen scorer succeeded after collection completed. [The failed launch is preserved](../2026-10-28-stringsearch-scoring-launch-note/README.md), as is the first countnegative preparation failure caused by missing explicit historical contexts. New corpus export authenticates and materializes every source context through release/preregistration provenance.

## Validation and commands

The full repository run passed 4,672 tests and 181 subtests, with one intentional duplicate-ZIP warning. Later focused completion/report/extraction tests are recorded separately in focused-tests.txt. Both forward result archives, native audits, SQLite projections and deterministic policy replays verified. No source experiments or negative outcomes were deleted; unrelated slide edits were left untouched.

```sh
.venv/bin/python scripts/finish_selection_study.py countnegative
.venv/bin/python scripts/finish_selection_study.py stringsearch
.venv/bin/python scripts/export_incremental_selection_corpus.py --verify results/2026-10-28-expanded-selection-corpus-r3
.venv/bin/python scripts/report_forward_selection_checkpoint.py
.venv/bin/python scripts/report_workload_transfer.py --output reports/<fresh-transfer-directory>
.venv/bin/python scripts/analyze_candidate_size_coverage.py --output reports/<fresh-directory>/report.json
```

The first two commands are verification-only for these completed studies. None of these commands starts a new candidate experiment.

## Next useful experiment

Acquire a workload with a larger legal pool and deeper repeated arithmetic sequences, freeze the same strong heuristics and model/agent controls before target outcomes, then compare best verified feasible performance against paid evaluation count and time. Preserve both ordinary-workload transfer and stricter novel-pattern stress tests; do not switch the primary endpoint after seeing which is favorable. Timing-boundary data and jointly measured compatible instruction sets remain missing. Neither tiny pools nor additional in-sample model fitting establish research superiority.

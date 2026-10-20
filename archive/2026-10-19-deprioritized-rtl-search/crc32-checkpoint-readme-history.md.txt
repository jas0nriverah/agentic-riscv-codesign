> Historical draft of the CRC32 checkpoint README, retained because two forward-looking statements below were later corrected. It is not a current roadmap. Raw measurements were not changed.

# CRC32 measured-speedup selection checkpoint

Six legal, retained CRC32 formulas were each lowered to a single custom instruction and evaluated as real firmware on the pinned synchronous-memory PicoRV32 SoC. This connects the existing XGBoost speedup selector to measured program performance. **The best instruction reduces cycles 4.84%; merit beats learned acquisition under the fixed budget.** There is no cross-workload or learned-selection superiority claim.

[Complete methods, all measurements, sources, and next milestone](../../docs/codesign-loop.md).

| Artifact | Contents |
| --- | --- |
| [plan.json](plan.json) | Candidate pool, configuration, source/input/tool hashes, budget and seeds frozen before candidate labels. |
| [observations.json](observations.json) | All six real application-speedup observations with measured SoC cost and feasibility. |
| [independent-audit.json](independent-audit.json) | Recounted raw cycles, resources and routing; all six candidate rows; policy summaries; exact replay status. |
| [selection-report.json](selection-report.json) | All 120 policy/seed/budget outcomes, predictions and paid training identities. |
| [live-selection.json](live-selection.json), [live-events.json](live-events.json) | Actual budget-three acquisition sequence and model predictions before its third measurement. |
| [speedup-corpus.json](speedup-corpus.json) | Six explicitly identified measured samples. One workload; cross-workload evaluation is unavailable. |
| [baseline-probe-report.json](baseline-probe-report.json) | Aha-mont64 passes on the same core; SHA-256 and matmult-int retain link/memory failures. These add no custom-instruction speedup labels. |
| [archive-manifest.json](archive-manifest.json) | SHA-256, size and complete regular-file membership for the three raw archives. |
| [raw.tar.gz](raw.tar.gz) | Firmware, source snapshots, disassembly, native receipts/logs, equivalence and integer checks, mapped netlists, three route reports per design and controls. Excludes rebuildable simulator object directories. |
| [failed-initial-control.tar.gz](failed-initial-control.tar.gz) | Failed byte-identity control check and exact original runner. The corrected experiment uses a full execution-equivalence control. |
| [baseline-probe.tar.gz](baseline-probe.tar.gz) | All three predeclared additional-workload outcomes and native evidence, including failed links. |
| [source-manifest.json](source-manifest.json), `sources/` | Exact evaluator, dependencies and next-stage harness/corpus source snapshots. |
| [environment.json](environment.json) | Python/platform and numerical dependency versions used for collection/replay. |
| [validation.json](validation.json), `validation/` | Full test and historical-model replay logs, raw-checkpoint replay, the earlier two process-cleanup test failures, and a 13-hit cache replay with zero new native commands. |

The measured benchmark includes 170 complete CRC32 repetitions. Startup/checksum/warm-up/reporting are outside its counter interval. All six report the expected full checksum and benchmark result, and each executes 176,128 custom instructions across the complete test program. The fixed registered interface supplies one PCPI wait cycle. Area and timing are measured on the integrated iCE40HX8K SoC; the primary speedup uses a shared feasible 12 MHz clock, with no board-runtime or energy claim.

At budget three across seeds 0–4, merit finds the exact optimum in 5/5 searches; frequency, random, and learned acquisition each do so in 1/5. Mean best speedup is 1.050833× for merit and 1.032260× for the other policies. Learned query order equals random in all tested budgets/seeds. The recorded first prediction has tied upper quantiles despite different means. The next-cohort evaluator resolves these ties using predicted mean; this checkpoint is unchanged and no post-hoc gain is claimed.

The seven complete designs consumed 127 native commands and 281.00 native seconds. The failed initial control attempt cost another 30.41 native seconds. Native concurrency is one; builds use two workers. Per-policy replay charges are separate from physical calls; all methods pay the same target budget. Historical RV32IM discovery proxies are reused and their original collection cost is not reconstructed. No historical speedup training labels or LUT-model predictions enter the selector.

From the repository root, with the recorded Python dependencies:

```sh
python scripts/reproduce_codesign.py replay
```

This verifies archive membership/hashes, restores retained raw files, recounts seven processor measurements and replays all 120 policy outcomes. It invokes no native compiler, simulator, synthesis or routing tool. Re-running it checks the restored tree rather than overwriting it. Fresh native collection commands are in the [guide](../../docs/codesign-loop.md#reproduce-and-preserve).

Current limitations are explicit: one consumed workload/input; six hand-supported source lowerings; inherited RV32IM discovery features; no calibrated uncertainty; no measured cross-workload model; no native RTL-agent optimization experiment. The rule-based RTL controller has formal contract tests but is deferred behind the cross-workload speedup milestone. The archive preserves useful historical cost-model work without promoting it into application-speedup evidence.

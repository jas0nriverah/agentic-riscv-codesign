# Current handoff — October 21, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [the current ML experiment](ml-factorized-selection.md), [primary methods](research-foundation.md) and [teammate compatibility](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. The owner wants continued **ML model and measured-dataset improvement**. Demo, presentation and live LLM work remain paused. The [previous SHA handoff](HANDOFF-history-2026-10-21-feasible-benefit.md) preserves the preceding milestone and every negative outcome.

## Completed increment

One genuinely fresh source, **BEEBS integer JPEG DCT**, now runs through the existing guarded RV32I/PicoRV32 extractor, lowering, verifier, integrated synthesis and three-route evaluator. Exact pinned source, input and all 64 golden coefficient checks remain unchanged. Only an external no-op warmup supplies the absent harness ABI. It is BEEBS, not Embench.

All six candidates from 29 eligible formulas pass, with one serial attempt each. Baseline: **117,522 cycles / 1,653 LUT4**. Best at +64: **116,946 cycles, 1.004925×, +61 LUT4, minimum routed Fmax 70.912 MHz**. The original 8 KiB RAM/12 MHz target, RV32I/ILP32, two-input/one-output PCPI and routing seeds 1/2/3 remain fixed. The explicit checked partition is 3,072-byte program, 128-byte guard, 4,992-byte stack; observed baseline stack use is 304 bytes for the recorded input.

One fixed factorized XGBoost model learns successful-execution conditional hardware feasibility and multiplies it by nonnegative public calibrated cycle savings / baseline cycles. Same structural/cap features and fixed 20-member/80-tree/depth-2 settings; binary logistic objective, candidate bootstraps with three dependent cap replicas and per-member single-class fallbacks. It predicts neither correctness nor calibrated confidence. Existing speedup regressors, ranker, utility model and GPs remain separate unchanged controls.

The complete prelabel package was pushed at **a2004f9540a2355c7b2fec31cacfa8fe8f153bb4** before any candidate attempt. Every learned policy fits exactly 38 historical candidates across six source groups after the same family exclusions; all twelve policies share public information and budgets. Baseline/public state was authenticated before/after fitting and at release. The campaign checks the committed manifest, exact native protocol copy, zero-attempt release and release-before-attempt timestamps. Inner archive provenance asserts receipt/source integrity only; outer proof supplies Git chronology.

## Measured result and limitations

- **Primary +64:** new model reaches the optimum on query one in all five dependent seeds, tying frequency, merit and earlier learned models. Cost heuristic misses through query three. No new-model or broad ML advantage over the strongest comparator.
- **+32 control:** only candidate17 is feasible, 1.000409× at +15 LUT4. New model misses through query three in every seed; frequency finds it in four. Preserve this failure; no post-label reranking or threshold change.
- All twelve policies, three caps, budgets 1/2/3 and five dependent seeds yield **180 trajectories / 540 endpoints**, with exact refits. Full-pool serial collection plus paid cooperative replay is not live adaptive hardware search. Three-query policies spend all three attempts even after finding the optimum.
- Fixed retrospective diagnosis holds whole sources out, both SHA contexts together, and removes all target families. At +64, Brier: XGBoost 0.310182, existing GP 0.319040, simple prior 0.261751. Prior also wins at the other caps. Better selection against the cost heuristic alone does not prove an advantage over frequency/merit. Fresh DCT +64 Brier is 0.213194 vs GP 0.211783. Uncertainty remains unresolved.
- Dataset: **45 successes, three earlier failures, 48 attempts, seven sources, eight contexts**. Six sources are Embench; one is BEEBS. All seven are now consumed data. Both SHA contexts must stay in one source fold. Two historical failures are recorded invalid executions; one UD infrastructure failure remains unknown and censors its full-pool reference.
- All **45** successful measured cycle deltas equal calibrated latency. No speedup residual learner is justified. Successful designs all fit and clear the 12 MHz clock, so timing-boundary/device-fit generalization is untested. Single-instruction speedup and integrated area cannot be summed for sets.
- Historical 42 attempts: 2,497.368142 recorded candidate seconds. New six: 250.772492 ledger / 262.986905 CLI-operation seconds; complete subprocess walls also archived. Baseline ledger 27.569974 s; 133 native commands 266.639223 s across setup/baseline/candidates. Scopes overlap; fitting/prediction and failed qualification costs remain separate. No end-to-end time win.

## Commands and evidence

Use Python 3.12 and pinned `requirements-speedup.txt`:

```sh
make reproduce-jfdctint PYTHON=python
make jfdctint-report PYTHON=python
make export-seven-source-corpus PYTHON=python
make diagnose-factorized-selection PYTHON=python
make test PYTHON=python
make reproduce PYTHON=python
```

Derived directories must be fresh; override Makefile output variables for repeat runs. [Full candidate/policy tables](../results/2026-10-21-jfdctint-report/results.md), [raw evidence](../results/2026-10-21-jfdctint-campaign/README.md), [45-label corpus](../results/2026-10-21-seven-source-corpus/README.md), [qualification failures](../results/2026-10-21-jfdctint-qualification/README.md) and [validation](../results/2026-10-21-factorized-validation/README.md). The classifier, experiment, adapter, freeze/replay and retrospective diagnosis sources are now hash-bound. Preserve them and all older sources/results.

Full suite: **3,117 passed, 179 subtests passed, 102 new tests included**. Exact new native/model/policy replay, dataset export and historical `make reproduce` pass. The earlier intermittent legacy cleanup failure remains preserved; it passed this run without a fix, and no legacy fix is claimed.

## Next smallest useful work

Collect another independent small integer source under an explicit compatible context. Keep the fixed models and every strong heuristic; freeze pools/predictions before labels and assess actual verified performance under identical count/time budgets. Prioritize constraint-diverse measured outcomes and enough independent sources for calibration over another model or parameter sweep. The +32 miss is evidence to preserve, not permission to tune on this test.

Do not repeat known matmult failure: its five 20×20 ILP32 arrays alone occupy 8,000 bytes before code. The initial DCT guard-fixture failure is archived; the accepted partition changes no source arithmetic or monitor. Do not shrink inputs, enlarge RAM or mix teammate RV32IM/external-memory results into this context silently.

Later connect compatible one-to-three-instruction sets using reviewed overlap/slot components, and measure combined execution/area/timing. The bounded LLM comparison remains later work. No RTL-rewriting agent, GNN, new enumerator or unrelated framework.

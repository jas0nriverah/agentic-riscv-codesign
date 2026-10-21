# Current handoff — October 21, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [the current ML experiment](ml-feasible-benefit.md), and [the established-method review](research-foundation.md). Branch: `ai-guided-ml`. The owner wants continued **ML model and dataset improvement**. Demo, presentation and live LLM development are paused. The [previous handoff](HANDOFF-history-2026-10-21-bounded-selector.md) preserves completed agent/demo work and superseded priorities.

## Working model and measured outcome

One fixed budget-conditioned XGBoost model predicts signed feasible decision utility, reusing the existing 31 structural features and 20-member, 80-tree, depth-2 ensemble with one cap-relative historical area feature. Candidate-level bootstrap weights keep cap replicas dependent. Infeasible zero utility is not zero speedup; failed attempts have unknown utility. Original speedup regressors and the pairwise ranker remain unchanged.

Six new automatically extracted SHA256 formulas pass lowering, full-program execution/correctness, processor controls, integrated synthesis and all three routes. Source/input, RV32I/PicoRV32, 8 KiB RAM and checked memory partition are unchanged. Every native attempt was serial and limited to one; none was retried. [All candidate/policy tables](../results/2026-10-21-feasible-benefit-report/results.md).

At +64 LUT4/12 MHz, candidate 23 is the complete declared-pool optimum: **26,135,630 → 25,466,830 cycles, 1.026262×, +43 LUT4**, minimum Fmax 62.992 MHz. New XGBoost reaches it in **two queries/131.808 recorded target seconds**, versus normalized XGBoost's **three/201.231**, for all five dependent seeds. Adaptive GP ties the new model; the cost heuristic wins in **one/63.840**. Fixed three-query runs spend all three attempts. Earlier oracle attainment is not demonstrated automatic stopping. At +32, baseline is known at query0; at +128, candidate 01 is best. All eleven policies and 495 endpoints replay exactly.

The full 157-file baseline/model/prediction preregistration was pushed at **25322573b86b933253f36a8316a18f7b1a058e67** before any new candidate attempt. All old SHA rows are excluded from fitting:27 non-SHA labels available,21 fitted rows across five groups after related-family exclusions. The new freeze checks at least two groups after exclusions. Native zero-attempt state was checked before/after fitting and again before release. Portable JSON ensembles exactly reproduce predictions and refit weights.

The original generated protocol path was ignored by Git; its exact copy was committed under preregistration/baseline. The native-pack original-path Git precheck was rejected without a hardware attempt or archive write; diagnostic retained. The **outer** campaign authenticates the entire committed preregistration, original protocol-copy bytes and release receipt. Internal native provenance asserts receipt/source integrity only. Do not invent a retroactive checkpoint or remove the outer checks.

## Limits and preserved negatives

- All six fresh candidates belong to four already consumed SHA families; none repeats an old SHA structural feature vector exactly. This is new-candidate evidence on consumed source/input, **not unseen-source/family generalization**. All six historical workloads informed development.
- Primary-cap coverage of the new model's 90% bootstrap utility range is only 16.7%, averaged over dependent seeds. It does not repair uncertainty or the first over-budget query. Utility is not speedup, calibrated feasibility or confidence.
- The development EDN +32/query1 regression in one of five seeds and the prior negative ordered-descriptor study remain preserved. Do not retune on these now-consumed outcomes.
- All 39 successful cycle deltas equal calibrated latency. A new speedup residual model remains unjustified. Single-instruction speedup, integrated area and timing cannot be summed for selected sets.
- Dataset: **39 successful labels, three earlier failures,42 attempts, six sources and seven contexts**. Twelve SHA rows span two contexts; future source holdouts must exclude both together. There are46 processor evaluations including seven baseline evaluations, and 138 routes. Older source-adapter CRC32 evidence stays separate.
- New candidate ledger time396.754094s; baseline 39.346900s;133 native commands275.054454s. These overlap. Previous 36 consumed development attempts cost 2100.614048s, cumulative recorded attempt time2497.368142s. Available non-SHA training history costs 1698.152954s including three failures. Fitting/inference, setup/calibration and outer authentication timers remain separate; no end-to-end latency win.
- UD's historical infrastructure failure is still unknown, not infeasible or a zero-speedup label. The new SHA pool oracle is complete; the old UD full-pool oracle is not.

## Reproduce and validate

Use Python 3.12 and pinned `requirements-speedup.txt`:

```sh
make reproduce-feasible-benefit PYTHON=python
make feasible-benefit-report PYTHON=python
make export-model-corpus PYTHON=python
make test PYTHON=python
make reproduce PYTHON=python
```

[Inference command and model semantics](ml-feasible-benefit.md). Derived outputs require fresh paths. Protect frozen results and hash-bound model/runtime sources.

All **54 new tests pass**. Full suite: **3,014 passed,179 subtests passed, one unchanged intermittent legacy process-cleanup failure** in `test_blocked_pipe_or_compressor_drain_has_finite_cleanup[pipe]`. Its reported producer PID was absent in the post-test check; no legacy fix is claimed. [Validation logs](../results/2026-10-21-model-improvement-validation/README.md) preserve the assertion. Exact native audit, all five control prediction packages, all five utility model weights,495 endpoints, dataset export and historical `make reproduce` pass. Prediction CLI reads zero target labels.

## Next smallest useful work

1. Qualify one genuinely fresh small integer source in a declared compatible context. Preserve [sglib/qrduino/minver memory diagnostics](../results/2026-10-21-model-data-qualification/README.md). Do not silently shrink inputs, enlarge RAM or mix teammate RV32IM/external-memory labels into this corpus.
2. Freeze a bounded automatically extracted candidate pool and model predictions before measuring it. Hold out the whole source and related families, retaining all strong heuristics and historical/failed-attempt costs. Collect diverse measured feasibility outcomes before another model change or confidence claim.
3. Assess uncertainty on independent held-out sources. Capture complete outer evaluation wall time alongside current scopes in the next native protocol. No descriptor/model sweep on the now-consumed39 labels.
4. Later, integrate jointly selected sets using the reviewed teammate slot/overlap components inside the checked SoC. Measure combined performance/area/timing. Keep the LLM comparison for later. No RTL-rewriting agent, new enumerator, GNN or unrelated framework.

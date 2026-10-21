# Current handoff — October 21, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [research methods](research-foundation.md), [SHA256 results](guarded-sha256.md), and [the teammate branch review](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. The [previous handoff](HANDOFF-before-guarded-sha256-2026-10-21.md) preserves the five-workload checkpoint and all earlier failure details.

## Verified now

- **33 verified automatic labels across six workloads**, three historical failures, 36 candidate attempts, 39 measured processor designs and 117 routes. Original source-adapter CRC32 evidence remains separate and unchanged.
- SHA256 adds six successful automatically extracted/lowered candidates, seven integrated designs and 21 routes. Original input/full digest verification, RV32I software compatibility and every processor control pass. Baseline: 26,135,630 cycles, 1,653 LUT4, minimum routed Fmax 68.493149 MHz.
- At +64 LUT4 and 12 MHz, candidate 22 is best: 25,588,430 cycles, **1.021384665×**, +50 LUT4, minimum Fmax 65.993530 MHz. The fastest unconstrained candidate is 1.053939769× at +68 LUT4. At +32 the baseline is retained.
- Source guarding rejects three symbolic-address formulas before six candidates are stratified from 56 legal/calibrated formulas. The explicit 7,488-byte program limit, 128-byte guard and 576-byte stack fit the unchanged 8 KiB SoC; observed stack use is 384 bytes.
- Native `guarded_workload` binds source/inputs, rejects legacy entrypoints, rederives cached discovery and uses one-attempt ledgers. Terminal failures stay charged and collection can continue; interruptions cannot become implicit retries. `guarded_evidence` authenticates raw controls, cycles, netlists, routes, receipts and failed/unknown attempts before archive/replay.

## Model result and experiment integrity

All SHA256 predictions, pool, baseline and source bindings were committed/pushed at **ab3789f106eab46df26ebcce56a6909e8d34c45b** before candidate measurements. Historical data: 27 labels/30 attempts from five other workloads; 21 fitting rows after related-family exclusion. Existing models, features, hyperparameters and policies were unchanged. Ten policies × three budgets × three caps × five dependent seeds yield **450 endpoints**, all exactly replayed. One new source workload is the independent unit.

**ML still does not beat the strongest heuristic.** At +64, the cost-aware heuristic finds the optimum in one query (67.471 charged seconds), adaptive GP in two (134.518), and merit/calibrated latency/normalized XGBoost in three (200.552). Frequency also reaches it by two queries. Raw regression and ranking miss it in some seeds. Adaptation helps versus merit at two queries but does not beat the strongest comparator.

All 33 successful cycle deltas equal calibrated latency exactly. Normalized SHA speedup MAE is 0.006941309 versus raw 0.016548112; nominal 90% interval coverage is only 43.3% versus 16.7%. Hardware-feasibility confidence and acquisition remain uncalibrated. Do not add cycle residual models while no measured residual exists. Do not relabel these now-consumed six workloads as new held-out tests.

SHA candidate ledger wall time totals 402.461094 seconds, versus 251.904063 seconds inside the narrower measurement records. Historical candidate attempts cost 1,698.152954 seconds, giving 2,100.614048 recorded attempt seconds across 36 attempts. The SHA baseline ledger costs 35.443627 seconds; all 133 native commands total 277.326737 seconds. Timers overlap. Repeated public discovery checks outside the ledger and other setup/calibration/inference are separate; none of these is a complete collection/lifetime timer. Instrument that outer scope before claiming end-to-end search latency.

The [new JSON/CSV corpus](../results/2026-10-21-six-workload-corpus/README.md) preserves contexts and the three earlier failure classifications. UD candidate 10 remains infrastructure-censored, never a negative performance label; its old full-pool oracle is unresolved. SHA's six-candidate reference is complete. Earlier EDN/UD's 900 endpoints and negative SLRE results remain unchanged.

## Teammate work to reuse

Fetched `hw/dev@d38135c` and `hw/agent-experiments@44a5bd3` contain useful placement diagnostics and ordered three-slot PCPI/joint assembly rewriting. Reuse their small components and microtest cases for the future jointly measured instruction-set adapter. Their reported 70-row/60-core sweep is RV32IM, zero-wait external-memory, core-only synthesis with another clock objective: keep it separate from the 33-label corpus. Committed summaries lack our raw/source/time provenance and do not establish equal-query-budget comparison. C3 uses the entire sweep's measured costs, while oracle selection chooses among three measured sets. Account for that history and information before adapting those baselines.

`main` and `codex/isaforge-ml-foundation` are already ancestors. `latest` is a curated older isolated-area snapshot, not newer pipeline work; do not merge its mass deletion or README replacement. No teammate branch was merged or modified. The full review records pinned commits and exact reusable files.

## Current model-readiness findings

The [readiness analysis](model-selection-readiness.md) independently audits the 33-row corpus and frozen factor rankings without fitting models. Initial duration/timing factor removals do not alter rankings on EDN/UD/SHA. SHA's wrong first query is a hardware-feasibility issue; its benefit-only XGBoost order is actually correct for unconstrained speedup. Keep model, acquisition and input effects separate. Thirteen of 31 structural columns are constant; all successful designs speed up and clear timing, limiting decision diversity. Duration targets mix record/ledger scopes. No confidence calibration or new policy advantage is established.

The next integration milestone is the bounded four-tool LLM selector, alongside one compact structure-aware feasibility development experiment. Keep current numeric models fixed in agent-only comparisons, prove paid-label isolation before LLM calls, and use the same information and budgets as the strongest heuristic/non-agent loop. Start with consumed replay for engineering, then freeze before fresh research validation. SHA query-one heuristic optimality leaves no query-count headroom there. This analysis proposes the pilot; no LLM episode or new model was run.

Reproduce the arithmetic diagnosis with `python scripts/analyze_model_readiness.py --output generated/reproduction/model-readiness` using a fresh output directory. Metrics, source/input hashes, primary methods and a confidence plot are preserved in [the analysis archive](../results/2026-10-21-model-readiness-analysis/README.md). The prior [handoff](HANDOFF-before-model-readiness-2026-10-21.md), [methodology](methodology-before-readiness-2026-10-21.md), and [method review](research-foundation-before-readiness-2026-10-21.md) are historical snapshots; active versions now reflect completed work.

## Next smallest useful work

1. Implement a thin isolated list/predict/measure/finalize selector over the existing guarded APIs. Validate charging, invalid actions, hidden-label access, failures and baseline fallback before LLM trials. Freeze a single model/prompt/tool protocol and five trajectories; run an agent-only comparison with unchanged predictors and equal public information.
2. Run one ordered-structure/immediate descriptor development ablation with current GP/acquisition and whole-workload/family exclusions. Evaluate feasible speedup versus query/time, not area MAE alone. Test uncertainty correction separately; harmonize duration scopes and instrument full outer collection time. Freeze any justified change before fresh tests and retain all historical costs. Do not edit hash-bound sources.
3. For joint sets, adapt the teammate slot/overlap components into the checked RV32I SoC, rather than creating another RTL framework. Include baseline fallback, executable-site conflicts, measured combined area/timing and full-program correctness. Do not sum individual outcomes.
4. Validate prospective agent/ML decisions on genuinely fresh source/input evidence after development. The current replay is cooperative; isolation is required before exposing an LLM. Keep the final optimized implementation/report as the endpoint. No RTL-rewriting agent, GNN, model-version sequence or unsupported novelty/ML win.

A rare crash after sealing a measurement record but before its ledger becomes terminal currently stops strict audit. Preserve such a context for explicit recovery; do not promote its result or silently retry it. This did not occur in SHA256.

## Reproduce and validate

```sh
make test PYTHON=python
make reproduce PYTHON=python
make sha256-report PYTHON=python
python scripts/export_guarded_corpus.py --output generated/reproduction/six-workload-corpus
# Older campaigns remain reproducible:
make reproduce-budget-campaign campaign-report PYTHON=python
make reproduce-prospective PYTHON=python
```

Use Python 3.12 and pinned `requirements-speedup.txt`; export requires a fresh directory. SHA replay authenticates raw evidence, original source hashes, exact prelabel Git bytes, historical prediction refits and all 450 endpoints, with no new native jobs. Reports and consumed corpus exports must remain outside selector access.

[Validation](../results/2026-10-21-guarded-validation/README.md): all **83 new tests pass**. Initial full suite: 2,836 tests and 179 subtests passed. Final full suite after adding the report/export/replay tests: **2,863 pass, 179 subtests pass, one unchanged intermittent legacy process-cleanup test fails**. Its residual-process assertion and prior failures are preserved; no fix to legacy capture code is claimed. `make reproduce`, SHA raw/policy replay, export verification and actual legacy-entrypoint rejection pass.

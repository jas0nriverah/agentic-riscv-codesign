# Current handoff — expanded training data and live native GP selection

Read [README](../README.md), [AGENTS](../AGENTS.md), [experiment guide](ml-live-adaptation.md), [primary methods](research-foundation.md) and [teammate compatibility](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. GPT-6.1 Sol subagents independently checked models, information boundaries, integer-cycle arithmetic and native evidence. The [complete previous handoff](HANDOFF-history-2026-10-21-blind.md) and every historical experiment remain intact. The user canceled service/GCP deployment and asked to continue improving ML; cloud/API/demo/LLM work remains paused.

## Subsequent diagnosis and next bounded change

The [October22 analysis](model-research-analysis-2026-10-22.md) adds primary hardware, constrained-search and reliability methods plus an [archive-backed numerical diagnosis](../results/2026-10-22-model-research-diagnosis/README.md). It fits no models and makes no native measurements. All270 cached first choices reproduce. Duration removal alone improves five dependent Expint+64 first choices, worsens none and ties130; the full variant trajectory is not yet evaluated. Hardware features exactly alias two differently ordered NDES formulas costing70/40LUT4. Constant scaling makes fresh Expint03 nearly identical to the cheaper history vector despite its71-LUT outcome and narrow predicted40-LUT posterior. Existing semantic descriptors separate that pair but retain the DCT counterexample and earlier negative ablation.

Next implement one isolated acquisition ablation using unchanged models, benefit units, cohorts, paid updates and all twelve controls. Replay only as consumed-data development, then freeze untouched useful-opportunity source tests. Do not combine representation, scaling, kernel and acquisition changes or claim that more labels automatically fix transfer. All87 successes pass timing/device capacity, so no such failure boundary has been learned. [Validation](../results/2026-10-22-model-research-validation/README.md) retains the unchanged legacy pipe failure. The completed experiments below remain authoritative measurements.

## Completed engineering and data

**87 verified labels, three preserved failures, 90 attempts, eleven sources and twelve contexts; 99 completed integrated processor designs and 297 routes including baselines.** Six sources are Embench; five are pinned BEEBS. All eleven are now consumed data. This increment contributes one fresh source and one actual live adaptive trajectory, not eleven untouched holdouts or five independent test seeds.

Expint qualifies with six automatically extracted candidates from eight eligible formulas. Its original input n=50/x=1, expected result3883, RV32I/ILP32 `-Os`, PicoRV32/PCPI interface, integrated8KiB RAM and6400/6528 partition are unchanged. Bubblesort is unrun because the declared first-success qualification stops at expint. Both Levenshtein rejections are preserved: missing `strlen`, then too few legal formulas after a separately declared external ABI fix. No source/input was reduced and neither rejected context was retried at a smaller gate.

| Candidate | Cycles | Added LUT4 | Minimum Fmax MHz |
| --- | ---: | ---: | ---: |
| Baseline | 31,843 | 0 | 68.493149 |
| 00 | 31,832 | 17 | 66.476097 |
| 01 | 31,836 | 33 | 67.976341 |
| 03 | 31,837 | 71 | 65.210304 |
| 04 | 31,840 | 35 | 65.733253 |
| 06 | 31,840 | 41 | 64.846642 |
| 07 | 31,840 | 101 | 67.608681 |

All six pass the original verifier, 228-vector instruction checks, exact custom execution/handshake counts, stock/custom processor controls, continuous memory checks, integrated netlist recount and all18 routes. Baseline LUT4=1653; every design retains20 BRAM blocks. All87 cycle deltas exactly match independently calibrated latency. Do not fit a benefit-residual model without new residual evidence. These are native simulated-processor and synthesis/routing outcomes, not physical-board measurements.

## Frozen models and actual live search

Full models/runtime/baseline/qualification were pushed at **`3b6f676cd5b68166f529c5be0020de0ddf540930`** before release or any candidate attempt. Historical81 successes and three failures remain charged; identical source/family exclusions leave67 fitting rows from ten sources for every learned policy. No expint source or related family trains its own model. Existing features/settings remain fixed; no new predictor version was introduced.

The declared GP seed0/+64LUT4/12MHz/three-query run dispatches **03→00→01**, authenticating each partial paid audit before the next model update. Query03 is correct but infeasible at+71. Query00 reaches the pool optimum at query2: **1.000345564×**, or **0.034544484%** fewer cycles, at+17LUT4. The complete trace is sealed before oracle-reference queries04/06/07. All six outcomes now form consumed data.

Merit, calibrated latency and normalized XGBoost find that optimum on query1 in all five dependent replay seeds. Both GP controls need two. Several learned policies tie merit at query3; frequency/random and the cost heuristic remain worse. This source provides no ML superiority or adaptation-specific win. The small input executes each candidate once; its11-cycle public ceiling limits practical value. Do not broaden the pool or revise its input after collection.

Other policies use matched-budget cooperative replay; only one GP trajectory dispatches actual live native queries. No LLM, OS isolation, automatic stopping or joint-set advantage exists. All three fixed-budget queries are spent even when the optimum is reached earlier.

## Expanded-history model result

The fixed development comparison uses four consumed source holdouts and all twelve policies, with4320 endpoints. Original fitting cohorts44/33/29/38 expand to68/55/50/71 after the same family exclusions. Every expanded prediction is sealed before scoring; original model artifacts are reused and their original numerical query decisions checked.

At +64LUT4/three queries, raw XGBoost source-macro cycle reduction improves0.766274→1.602185%; normalized XGBoost1.449636→1.602185%; merit remains1.144539%. However ranking falls1.149319→0.652616%, fixed GP1.602185→1.144539%, and adaptive GP1.602185→0.839441%. DCT+32 remains a failure case. Preserve these regressions; no policy is promoted from this consumed-data study. All81 labels, three failures and84 historical attempts are charged once globally.

## Evidence and commands

[Expint outcomes and all twelve policies](../results/2026-10-22-live-gp-report/results.md), [live raw campaign](../results/2026-10-22-live-gp-campaign/provenance.json), [prelabel cohort](../results/2026-10-22-live-gp-preregistration/cohort.json), [87-label corpus](../results/2026-10-22-eleven-source-corpus/README.md), [development comparison](../results/2026-10-22-expanded-history-verified/report.json) and [prelabel validation](../results/2026-10-22-live-gp-prelabel-validation/README.md) are preserved.

Use Python3.12 and `requirements-speedup.txt`; outputs must be fresh:

```sh
make reproduce-expanded-history PYTHON=python
make reproduce-live-gp PYTHON=python
make live-gp-report PYTHON=python
make export-live-gp-corpus PYTHON=python
make reproduce PYTHON=python
```

The live reproducer must authenticate native evidence, exact Git prelabel/release chronology, all15 grouped model refits, the actual paid decision trace and540 endpoints without new native measurements. The original strict replay's final comparison incorrectly includes nondeterministic host mean inference time; its failure and frozen source are preserved. The explicit post-collection replay adapter requires every other endpoint field exactly and retains both old/new host timings. Never change the frozen runtime, edit a timer or exclude any native duration/prediction/decision from exact checks.

Prelabel `make test` has3352 passes/179 passing subtests and the unchanged intermittent legacy pipe-cleanup failure. The post-collection full run has3360 passes/179 passing subtests and the same failure. All130 focused new tests pass, including completed presenter/export integration and18 replay-adapter checks. Qualified replay passes all540 endpoints and15 grouped refits; only six host mean-inference fields vary, with both raw arrays retained. Report/export commands, expanded replay and historical reproduction pass. [Complete validation](../results/2026-10-22-live-gp-validation/README.md) preserves both full-suite failures; no legacy fix is claimed.

## Costs and next work

Historical84 attempts cost4853.804293 recorded seconds. The new six-candidate ledger records245.028173 seconds; the live prefix118.611717 and separate reference remainder126.416456. The complete parent collection records paired UTC256.191790 and monotonic256.192980334 seconds. Qualification records43.134382 monotonic seconds; earlier failed qualification/setup costs remain separate. These scopes overlap and are not summed into an elapsed-wall-time claim. Both raw clocks/disagreement flags and the earlier MD5 accounting amendment remain unchanged.

Next address demonstrated representation/decision failures and collect independent, constraint-diverse sources with meaningful dynamic opportunities. New expint data contrasts a four-operation17-LUT4 best design with two-operation71/101-LUT4 designs: operation count alone is inadequate. This supports diagnosis, not an isolated area model or a sweep on now-consumed labels. Keep the negative ordered-descriptor study intact. Broader fresh-source transfer, calibrated uncertainty, timing/device-fit boundary evidence and jointly executed one-to-three-instruction sets remain missing. Use the existing pipeline and reviewed compatible teammate slot/overlap code for the later joint stage; never add individual gains or area increments.

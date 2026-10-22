# Expanded training data and live measured adaptation

The next model experiment changes the available data and connects the existing adaptive GP to native evaluation. It introduces no new model settings, features, acquisition rule or area-prediction study. The fixed XGBoost regression/ranking, normalized and feasibility controls remain in the comparison.

## Why this experiment

The completed three-source blind study exposed hardware-feasibility errors. Its static classifier spent all three +64-LUT4 compression queries on infeasible candidates. Some distinct formulas also share identical structural feature vectors, so resampling the same representation cannot resolve those cases. All81 successful cycle deltas still match independently calibrated latency; a new performance-residual model has no demonstrated target to learn.

The existing paid-adaptive GP supplies a measured alternative: on compression, incorporating the first paid69-LUT4 outcome moves the61-LUT4 pool optimum to query two; the fixed GP needs three. Both tie at the primary three-query endpoint. This motivates more historical constraint data and a real measurement feedback loop, rather than another classifier version. The method retains its established constrained/cost-aware acquisition assumptions described in [the primary-method review](research-foundation.md): known calibrated gain times independent GP feasibility estimates and expected inverse evaluation duration. It is not a new enumeration algorithm or a calibrated confidence method.

## Fixed expanded-history development comparison

`scripts/evaluate_expanded_history.py` declares four consumed targets before fitting: compression, NDES, MD5 and DCT. It compares the original archived models with identical models fitted on the expanded ten-source corpus. Whole source workloads, all their contexts and related formula families are excluded from each fitting cohort. Fitting rows rise44→68,33→55,29→50 and38→71; each expanded cohort spans nine historical sources.

All twelve policies, five dependent seeds, caps32/64/128 and budgets1/2/3 remain fixed. The primary macro averages the original three new BEEBS sources; DCT+32 is a separate regression case. Every expanded prediction package is sealed before target scoring. These targets were previously consumed: the inner API's zero-label argument means no target labels enter fitting, not a claim of a new blind study. Original model exports are reused, authenticated and checked against their original query decisions. Replay also requires complete artifact inventories and exact recreated portable model bytes.

```sh
python scripts/evaluate_expanded_history.py prepare \
  --output results/2026-10-22-expanded-history-verified
python scripts/evaluate_expanded_history.py run \
  --root results/2026-10-22-expanded-history-verified
python scripts/evaluate_expanded_history.py replay \
  --root results/2026-10-22-expanded-history-verified \
  --output generated/reproduction/expanded-history
```

Use a fresh output for another run. The first orchestration failure and its original predictions are preserved in a separate snapshot; its tuple/list serialization repair changes no model or numerical decision. No historical native measurement is repeated. All84 earlier attempts, including three failures, cost4853.804293 recorded ledger seconds once globally; fitting and replay costs are separate. The unknown infrastructure failure never becomes a hardware label.

The completed [development result](../results/2026-10-22-expanded-history-verified/report.json) retains4,320 seed endpoints across the old/expanded cohorts. At +64LUT4 and three queries, source-macro cycle reductions are:

| Fixed policy | Original history | Expanded history |
| --- | ---: | ---: |
| Merit / calibrated latency | 1.144539% | 1.144539% |
| Raw XGBoost regression | 0.766274% | 1.602185% |
| Normalized XGBoost | 1.449636% | 1.602185% |
| XGBoost ranking | 1.149319% | 0.652616% |
| Fixed hardware GP | 1.602185% | 1.144539% |
| Paid-adaptive hardware GP | 1.602185% | 0.839441% |
| Factorized feasibility XGBoost | 0.719365% | 0.748475% |

Raw and normalized regression find all three pool optima, while both GP controls and ranking regress. No policy is promoted from this consumed-data comparison. The live GP trial below was chosen for its existing paid-feedback mechanism before these development scores, and remains fixed. The tighter DCT+32 miss also remains unresolved. Additional labels are useful, but more data alone is not a universal improvement.

## Fresh source and live query protocol

The original Levenshtein qualification failed linking `strlen`. A separately declared external ABI helper fixes linking without changing the benchmark source/input/verifier. That context then fails the twelve-candidate extraction gate. Both failures are preserved; neither source context is retried or silently weakened.

The next source protocol declares `expint → bubblesort`, six candidates and stop after the first successful qualification, before either discovery. This follows the earlier DCT-six precedent. It retains original inputs/verifiers, RV32I/ILP32 `-Os`, PicoRV32/PCPI two-input/one-output interface, integrated8KiB RAM,6400-byte program region,128-byte guard,1664-byte stack,12MHz and three routing seeds. Native evaluations are serial with two build workers. Qualification dispatches no candidate measurement.

```sh
python scripts/qualify_integer_workload.py
```

Expint qualifies: eight eligible calibrated formulas, six selected by the existing merit-rank stratification, baseline31,843 cycles and unchanged expected return3883. Observed maximum stack use is128 bytes. Bubblesort is unrun because the declared stopping condition is met. The six-candidate oracle covers this subset, not every formula or instruction set.

`scripts/live_gp_campaign.py` freezes all twelve unchanged selectors from the81-label history, with the same source/family exclusions. Its primary live trajectory is fixed: `hybrid_gp_adapt`, seed0, +64LUT4,12MHz, three charged queries. Complete source/runtime/model/baseline artifacts must be committed and pushed before release and the first candidate attempt.

For each query, the controller seals its chosen identity and paid prefix before dispatch, executes one native evaluation, authenticates the partial raw audit, and gives only paid outcomes to the existing learner. Failures consume queries; interrupted or incomplete dispatch stops without retry. The completed three-query trace is sealed before any remaining candidate is measured. The rest is then collected in declared pool order for a separate oracle. Exact replay checks the live predictions, choices and verified curve; the other policies use matched-budget cooperative replay, not newly measured live runtimes.

The executable stages are `freeze`, `release`, `collect`, `pack` and `replay`; the completed checkpoint will record their exact paths and pushed prelabel commit. Paired raw UTC and monotonic endpoints replace reconstructed mixed-clock end instants for new subprocess observations. Keep each timer scope distinct; clock disagreement is recorded without correction or a tolerance.

## Acceptance and limits

The endpoint remains best verified feasible whole-program performance against charged query count and measured cost, with regret to the measured fixed-pool oracle. Model MAE, interval coverage and LUT errors are secondary. Count historical training and qualification as well as target measurements. Preserve regressions and heuristic wins.

One fresh source and one live seed cannot establish broad transfer, calibrated uncertainty, an agent advantage or a total-cost win. The five comparison seeds are dependent. Timing-boundary and device-fit failures remain missing. Joint one-to-three-instruction selection still needs combined execution and synthesis; individual gains and costs cannot be added. Demo, live LLM, service/cloud deployment and RTL rewriting remain paused under the current model-work direction.

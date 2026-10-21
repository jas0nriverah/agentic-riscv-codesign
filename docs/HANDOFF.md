# Current handoff — October 21, 2026

Read [README](../README.md), [AGENTS](../AGENTS.md), [the method review](research-foundation.md), and [the completed EDN/UD campaign](budget-campaign.md). Branch: `ai-guided-ml`. The [pre-campaign handoff](HANDOFF-before-budget-campaign-2026-10-21.md) preserves the previous SLRE checkpoint.

## Verified now

- Five real Embench workloads supply **27 verified automatic speedup labels**, plus three failed attempts. There are **32 fully measured processor designs and 96 routes**, including five baselines. Original CRC32 source-adapter evidence is separate and unchanged.
- EDN/UD pools and predictions were committed and pushed at `993d5d95ad7edb2539782f49151419f479836969` before either target's candidate labels. Both use the same 18 historical outcomes, with 15 fitting rows each after family exclusion. Ten policies, three budgets, three area caps and five dependent seeds produce 900 endpoints. Two workloads are the independent test units.
- EDN: five successes and one memory-contract failure. Best 386,561,849 → 386,394,809 cycles, **1.000432304×**, +32 LUT4. Merit, calibrated latency and all five learned policies find it on query one.
- UD: four successes, one self-check failure, one infrastructure-censored attempt. Best completed candidate: 37,845,951 → 37,690,761 cycles, **1.004117455×**, +70 LUT4. All four successful candidates cost +65 to +72 LUT4, so every policy retains baseline under the primary +64 limit. At predeclared +128, normalized XGBoost fixes the original regressor's miss but only ties merit. **No ML superiority is established.**
- UD candidate 10 stopped during firmware preparation at a low-free-disk preflight. No simulation/netlist/routes exist. Its 31.322582 seconds and query stay charged; no retry occurred. Correctness, performance and feasibility remain unknown. Frozen `oracle`/`regret` fields mean the best verified reference, with qualified interpretation in the derived report. UD's full-pool oracle remains unknown.
- All nine new successful cycle reductions exactly match calibrated latency, extending the exact match to all 27 labels. Normalized speedup MAE improves 98.43% on EDN and 91.00% on UD, but 90% interval coverage is only 36%/65%; UD coverage worsens. No cycle residual model is warranted yet.
- The fixed hybrid GP predicts integrated area, minimum routed Fmax and log evaluation duration, using analytic latency as its objective. Paid target adaptation is implemented; it shows no selection gain over the strongest heuristic here. Cost/timing uncertainty remains uncalibrated.
- The [expanded corpus](../results/2026-10-21-expanded-corpus/README.md) contains 27 consistent rows and three failed attempts with source/context/cost provenance. All five workloads are now consumed data. The old SQLite/HTML demo deliberately retains its frozen three-workload snapshot.

## Runtime contexts and failures

The unchanged 8 KiB PicoRV32/PCPI target uses RV32I with software arithmetic helpers. CRC32/aha use `-O2`; SLRE/EDN/UD use `-Os`. EDN reserves 1,408 stack bytes and observes a 1,040-byte maximum; UD reserves 896 and observes 592. Both retain a 128-byte declared guard and an 800-million-cycle simulation ceiling. UD's upstream software double helpers remain intact, but candidate extraction targets only marked benchmark assembly. Fixed-input checks do not prove arbitrary-input safety.

Seven failed qualification roots and three exact-flag linker diagnostics are archived. New target candidate attempts cost 904.226627 wall-seconds; all historical automatic candidate attempts cost 793.926327, totaling 1,698.152954 candidate wall-seconds. New baselines cost 127.215140 wall-seconds; other setup, calibration and inference costs are separate. Failed qualification command time is 64.979547 seconds, diagnostic command time 0.768713. Do not add overlapping command/evaluation timers or treat these scopes as total lifetime project cost.

EDN candidate 17 removes symbolic `%hi(a)`/`%lo(a)` references, letting linker garbage collection discard a 400-byte array while a literal old address survives. UD candidate 08 fails the recorded upstream self-check; UD 10's source also has relocation risk but has no measured outcome. The new `relocation_guard.py` checks original marked assembly and rejects symbolic/unsupported operands. It retains 14 EDN and eight UD full executable formulas before calibration filtering. Its source-only diagnosis also flags one successful historical SLRE candidate; preserve that observed success and disclose the risk rather than silently relabeling it.

## Next smallest useful experiment

**Wire the tested relocation guard before the existing pool stratifier in a fresh, source-bound evaluation context.** `filter_executable_candidates` returns the safe full list and removes old shortlist metadata. Keep all frozen modules/pools unchanged; the historical collection CLIs do not automatically apply this new guard. Verify the binding and original-source checks before additional native measurements.

Then freeze a new independent workload/input pool with explicit area/timing constraints and fixed models. Prefer candidate sets where feasible choices differ: calibrated latency currently explains all successful cycle benefits, and every learned tie on EDN/UD remains a tie. Do not tune more models on these targets and present them as held-out wins. A repeated EDN/UD input is within-workload adaptation, not a new source-family holdout. Any separately authorized retry of UD10 belongs to a new charged context and cannot repair the original campaign's chronology.

The bounded LLM selection agent and joint instruction sets remain later integration milestones. Python paid-label replay is cooperative, not an OS sandbox. Isolate target labels before giving an agent tools; supply the same public information and budget as non-agent policies. Lower, execute and synthesize compatible sets together; individual speedups and hardware increments cannot be summed. No RTL-rewriting agent, GNN or isolated LUT-study detour.

## Reproduce and validate

```sh
make test PYTHON=python
make reproduce reproduce-speedup reproduce-selection-research reproduce-model-analysis reproduce-prospective PYTHON=python
make reproduce-budget-campaign campaign-report PYTHON=python
make demo PYTHON=python
```

Use Python 3.12 and pinned `requirements-speedup.txt`. The campaign replay restores raw archives, authenticates all attempts and failures, verifies the prelabel commit, refits frozen predictions exactly and starts zero native jobs. Its CSV/Markdown/figure outputs are analysis artifacts, never selector inputs. The expanded-corpus README gives its portable export command.

The [final validation](../results/2026-10-21-budget-final-validation/README.md) records 2,780 passing tests, 179 passing subtests and one unchanged legacy capture-cleanup EPERM failure. All new guard/report tests and affected research replays pass. Preserve [all pre-report validation](../results/2026-10-20-budget-validation/README.md) as well; never overwrite an earlier failed run or claim the intermittent legacy failures are fixed.

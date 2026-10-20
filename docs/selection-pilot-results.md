# Ranking and automatic CRC32 — October 20, 2026

The [expanded primary-method review](selection-methods-review.md) led to one fixed XGBoost ranking comparison and a correction to the measured-data connection. **Ranking did not improve verified selection over regression, and neither beat merit.** This is consumed-data development evidence, not broad generalization or a prospective ML win.

## Completed engineering

CRC32 now runs through the same automatic RV32I profiling, legal extraction, assembly lowering, execution, integrated synthesis, and three-seed routing path as aha-mont64. Discovery found 37 raw formulas and eight executable formulas; the predeclared six highest-merit candidates were measured. All six passed upstream correctness, custom execution-count checks, sampled full-block equivalence, integer-oracle checks, stock-on-extension controls, and custom-on-baseline trap controls.

The new [CRC32 snapshot](../results/2026-10-20-automatic-crc32/README.md) preserves seven processor designs, 21 routes, 119 native commands, and 272.778 native command-seconds. It also retains 120 replays of the unchanged within-workload selector. The original CRC32 source-adapter experiment and its slowdown remain untouched.

The uniform automatic corpus contains **12 measured candidates from two workloads**. There are 18 total historical candidate outcomes if the older six CRC32 adapter outcomes are included; those are not another workload or six independent new workloads. The primary corpus evaluator still refuses a generalization study with fewer than three workload groups.

## Fixed model comparison

`SpeedupPredictor` remains the original 20-model bootstrap XGBoost ensemble, with 80 depth-two trees per model. The new `SpeedupRanker` uses `rank:pairwise`, 80 depth-two trees, learning rate 0.05, fixed mean pair sampling, and the same 35 public features. It learns within-workload/build/input ordering from actual measured speedups. Rank scores are not speedup predictions or uncertainty intervals. No hyperparameter tuning or new area predictor was performed.

Each target workload is excluded from fitting. One related operation-tree family is also removed, leaving **five fitting rows from the other workload** in each direction. All six historical measurements remain charged. Zero-shot predictions are saved before policy queries/scoring; adaptation can add only explicitly queried target outcomes. These workloads had already been inspected, which is why the protocol requires `--acknowledge-consumed-data`.

The seven policies use seeds 0–4 and target budgets 1–6: 420 policy/seed/budget outcomes from 70 sequential traces. Each prefix represents that policy at the corresponding budget. All candidates are feasible under baseline +128 LUT4 and common 12 MHz, so this experiment does not test difficult feasibility learning.

| Policy | aha-mont64 best speedup, budget 1 | Oracle hits / 5 | Automatic CRC32 best speedup, budget 1 | Oracle hits / 5 |
| --- | ---: | ---: | ---: | ---: |
| Frequency | 1.077394× | 2 | 1.030015× | 1 |
| Merit | **1.094120×** | **5** | **1.050833×** | **5** |
| Random | 1.050966× | 1 | 1.030015× | 1 |
| Zero-shot regression | 1.076165× | 3 | 1.050833× | 5 |
| Zero-shot ranking | 1.076165× | 3 | 1.050833× | 5 |
| Paid mean adaptation | 1.076165× | 3 | 1.050833× | 5 |
| Paid upper-quantile adaptation | 1.076165× | 3 | 1.050833× | 5 |

Values are means over the five seeded orders/fits. The last two policies have no target training observation before their first query. By budget three, all learned policies reach each measured pool's speedup oracle in all five seeds; merit already does so with one query. The ranker has no demonstrated selection advantage. Full trajectories, measured IDs, oracle regret, and costs are in the [pilot snapshot](../results/2026-10-20-ranking-pilot/README.md).

| Zero-shot diagnostic | Held out aha-mont64 | Held out automatic CRC32 |
| --- | ---: | ---: |
| Regression speedup-ratio MAE | 0.020262 | 0.006458 |
| Regression pair-order accuracy | 70.00% | 77.27% |
| Ranking pair-order accuracy | 70.00% | 72.73% |
| Coverage of 5th–95th ensemble quantiles | **26.67%** | 83.33% |
| Mean interval width, speedup ratio | 0.011282 | 0.035631 |

Prediction ties receive half credit; actual outcome ties are excluded from pair accuracy. Coverage is averaged over the same six candidates and five model seeds, not 30 independent test programs. Ensemble quantiles do not have a 90% prediction-coverage guarantee. The low aha coverage is a demonstrated uncertainty problem; a conformal wrapper cannot justify a guarantee with only two dependent workload pools.

In the aha holdout, the historical fitting labels span only 1.016389×–1.050833×. Three of the six target speedups lie outside that range, including the 1.094120× optimum. This is an observed coverage problem for the training data. It motivates broader measured outcomes and workload context before more model tuning; it does not prove a particular replacement model will solve transfer.

Historical candidate collection cost is 253.563 seconds when CRC32 trains the aha selector, or 280.244 seconds in the reverse direction. Every curve includes this shared historical cost, target-query cost, inference time, and total candidate-measurement count/time. The files separately report discovery and baseline command time. Candidate wall durations overlap native command durations and must not be added to them. Failed workload-eligibility probes are additional campaign overhead, preserved separately. Offline policy time curves reuse recorded durations; they are not new timed hardware searches.

The shared-history totals assume the same historical corpus was bought for all policies. **A heuristic deployed from scratch does not need those six historical labels.** In that accounting, merit finds each pool optimum with one target evaluation; learned selection also incurs its historical collection cost. Do not interpret the report's common-history totals as an intrinsic training requirement for merit, frequency, or random.

## Workload expansion: actual blockers

Nine failed workload/build contexts are preserved. None produced a new candidate speedup label:

| Build | Result before candidate measurement |
| --- | --- |
| EDN, `-O2` | Violates the 4 KiB program/data guard. |
| EDN, `-Os` | Code/data/BSS occupy **6,356 bytes**; guard remains 4,096. |
| huffbench, `-O2` | Exceeds the entire 8 KiB RAM by 3,444 bytes. |
| nettle-aes, `-O2` | Exceeds RAM by 7,436 bytes; unresolved `exit`. |
| wikisort, `-O2` | Exceeds RAM by 18,736 bytes; unresolved `memmove` and `sqrt`. |
| SLRE, `-O2` | Program/data guard and missing C-library symbols. |
| SLRE, `-Os` | Missing `_ctype_`, `strlen`, and `strchr`. |
| SLRE, `-Os`, minimal runtime | Library support resolved; **4,164 bytes**, 68 over the guard. |
| SLRE benchmark functions with `-Oz`, harness/runtime `-Os` | Still fails the program/data guard. |

The minimal C-locale runtime passes independent host-libc comparisons over EOF/all 256 character values and string edge cases. That component test is not a successful SLRE processor run. Inputs, compiler variants, command logs, costs, and failed outputs are retained in the [fit-probe archives](../results/2026-10-20-workload-feasibility/README.md), [runtime probe](../results/2026-10-20-slre-runtime-probe/README.md), and [final compiler fallback](../results/2026-10-20-slre-small-probe/README.md). The benchmark algorithm and memory limits were not changed; the final fallback adds a recorded compiler directive only.

## Run and reproduce

Use Python 3.12 with [the pinned dependencies](../requirements-speedup.txt), the initialized Embench submodule, and the repository root:

```sh
# Authenticates seven automatic CRC32 designs, all routes, 420 model-policy
# outcomes, and nine failed build contexts; starts no native evaluations.
python scripts/reproduce_selection_research.py

# Refit/replay the frozen development comparison directly:
python -m isaforge.selection_pilot verify --root results/2026-10-20-ranking-pilot

# Fresh automatic CRC32 collection with the previously prepared reference:
python -m isaforge.workload_experiment prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/automatic-crc32-new --workload crc32 --pool-size 6
python -m isaforge.workload_experiment discover --root generated/automatic-crc32-new
python -m isaforge.workload_experiment collect --root generated/automatic-crc32-new
```

## Next smallest experiment

Unblock one independent workload before adding model variants. SLRE is the closest observed fit; the next bounded engineering experiment should establish stack usage and a checked program/stack partition, or a separately declared memory context, before any change to the 4 KiB reservation. It must reject stack/data collision and preserve the current contexts. Do not silently weaken the guard or trim benchmark inputs to obtain a result.

Then freeze a broader legal pool, existing regression/ranking settings, an architecture-calibrated merit baseline, and constrained acquisition **before its candidate labels**. Compare zero-shot selection and paid adaptation on that new workload, including all historical costs. More than three small groups will still be needed for credible generalization/calibration. The LLM selection agent and jointly measured instruction sets remain subsequent stages. This checkpoint supports neither a novel enumeration claim nor learned-selector superiority.

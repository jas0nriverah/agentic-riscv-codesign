# Fixed selection improvements and workload-support milestone

The two bounded changes from the [preceding diagnosis](model-research-analysis-2026-10-22.md) are implemented and replayed. Six formula-derived features repair one expanded-history selection regression on consumed data. A separate, fixed eight-source qualification attempt finds no valid new test pool. The corpus remains **87 verified labels, three failures, 90 candidate attempts, eleven sources, twelve contexts, 99 completed integrated designs and 297 routes**. No model is promoted and no fresh-source win is claimed.

## Implemented changes

1. [Count-budget acquisition](../isaforge/count_selection.py) removes only inverse predicted measurement duration from the existing adaptive GP score. Analytic speedup improvement, Gaussian area/timing factors, device-fit prior, cached initial predictions, cohorts, ties and paid-success updates remain fixed. Failed attempts are charged; provider exceptions stop without retry. Predictions are sealed before each paid outcome is released. [All outcomes](../results/2026-10-22-count-acquisition-development/README.md) retain the twelve original controls.
2. [Semantic hardware representation](../isaforge/semantic_selection.py) appends exactly six existing formula-only fields to the 31-field GP input: `v3_edge_adder_shift`, `v3_edge_shift_adder`, `v3_adder_sum_bits`, `v3_adder_carry_bits`, `v3_live_demand_bits`, and `v3_output_constant_bits`. Scaling procedure, fixed Matérn kernel, noise, output floors and targets remain unchanged. No historical isolated-area-model weights or labels are loaded. All nine initial models/predictions are sealed before scoring. [All outcomes](../results/2026-10-22-semantic-selection-development/README.md) retain all thirteen preceding controls, making fourteen policies.
3. [Useful-opportunity qualification](../isaforge/opportunity_workload.py) uses the existing guarded extractor, lowering and evaluator with a predeclared twelve-candidate pool. One selected formula must have both at least ten timed replacements and at least 0.5% calibrated whole-program cycle reduction. Original inputs/verifiers, RV32I/ILP32, PCPI, 12 MHz and checked 8 KiB partition remain intact. This public-feature gate precedes expensive synthesis; its estimate is not a measured speedup label.
4. [Archive-only workload diagnosis](../scripts/diagnose_workload_support.py) authenticates the completed qualification, restores its raw archives in temporary roots, and recomputes executable candidate counts and source coverage. It needs no original generated roots, compiler, simulator, lowering or model jobs. It rejects output paths inside sealed evidence before writing.

The GP continues to predict **integrated area, routed timing and log measurement duration**, using independently calibrated latency for benefit. Existing XGBoost regression/ranking models still use measured whole-program performance targets. All 87 successful measured cycle changes match calibrated latency exactly; this change does not establish a need for another speedup-residual learner.

## Measured selection outcome

The primary development comparison averages verified cycle reduction equally across the **three existing compression/DES/MD5 sources**, with expanded historical cohorts, +64 LUT4 and 12 MHz. Five seeds are dependent repetitions, not independent workload tests.

| Policy | Two queries: cycle reduction | Three queries: cycle reduction |
| --- | ---: | ---: |
| Merit | 0.6029% | 1.1445% |
| Raw / normalized XGBoost | 0.6029% | 1.6022% |
| Original adaptive GP | 0.6029% | 0.8394% |
| Count-budget adaptive GP | 0.6029% | 0.8394% |
| Six-feature count-budget GP | **1.3657%** | **1.6022%** |

The semantic policy restores expanded-history AHA selection: it queries **02→07→00**, reaching the already measured optimum at query two. Count-only queries **02→05→11**, retaining baseline through query three. The formula is `xor(slli(xor(in0,in1),8),xor(in0,in1))`: **70,797→69,177 cycles**, 1,620 cycles saved, **1.023418× speedup**, **+61 LUT4**, minimum routed Fmax **64.185 MHz**, with correctness verified. This selects an existing measured design; it is not a new hardware measurement.

Across 135 case/cap/seed trajectories, the semantic change has **five wins, zero losses and 130 ties** versus count-only at each of queries two and three. All five wins belong to that one expanded AHA/+64 setting. Query one is unchanged everywhere. The earlier-history three-source macro stays 1.6022%. Full reports keep old/expanded cohorts separate and include all caps, budgets, policies, DCT and consumed Expint. Expanded history already includes previously collected other-source labels; this is development data, not a new simultaneous blind cohort.

Duration removal alone helps five Expint first choices but changes no query-two or query-three outcome versus the original adaptive GP. Preserve that negative endpoint result. The semantic policy ties existing regressors at query three; it is not uniquely best.

## Remaining model limitations

The six fields distinguish the NDES add/shift orientation alias, but two constant DCT expressions remain identical in this block despite different integrated costs. Both new policies still miss DCT's sole +32-LUT4 feasible candidate through query three. The previous negative 45-descriptor ablation is unchanged.

For Expint03, predicted area changes from **40.002±0.214** to **57.223±21.338 LUT4**, versus **71 measured**. Predicted probability of meeting +64 falls from effectively 1 to 0.6246. The mean remains on the wrong side. Area Brier error worsens in **seven of nine** case/cohort settings at +64. Neither general uncertainty calibration nor general area-prediction improvement is established. All successful historical designs pass the common clock/device limits; a timing/device failure boundary remains untested.

## New-workload qualification: preserved negative result

The [frozen protocol](../results/2026-10-22-useful-source-qualification/protocol.json) tries `cnt`, `bubblesort`, `prime`, `insertsort`, `tarai`, `recursion`, `janne_complex`, then `cover`, seeking three distinct accepted families. Sources match pinned BEEBS commit `049ded9f3aeb5591f553879d3a0376b8614e9422`; sorting variants count as one family. No inputs or verification gates were weakened.

Seven original programs compile and profile but fail discovery with fewer than twelve legal executable formulas. Janne is rejected statically because its verifier checks only a constant return, not a meaningful kernel output. **Zero sources qualify; zero custom-candidate attempts and zero new routed designs occur.** [Raw failures and command receipts](../results/2026-10-22-useful-source-qualification/qualification.json) are preserved.

The [reproducible support diagnostic](../results/2026-10-22-workload-support/support.json) finds eligible formula counts of **0, 0, 1, 1, 0, 0, static rejection, 0**, respectively. Prime's formula executes once and predicts only 3/386,055 saved cycles. Insertsort's formula predicts 45/2,221 saved cycles but executes only nine times. Neither supplies a multiple-candidate test pool; relaxing only pool size would not fix this qualification.

For Prime, only **3,071/75,682 timed instructions (4.06%)** map to marked program source. Most execution is in linked division/multiply helpers. This diagnoses missing extraction coverage; it does not prove helper code is safely rewritable. The new opportunity adapter's candidate-execution branch has not been validated by a new accepted native workload, and no prospective fourteen-policy controller was run.

## Costs and reproducibility

The 90 historical native attempts retain **5,098.832466 recorded seconds**, charged once globally. Replayed target-prefix durations are counterfactual information budgets, not additional collection time. At the primary expanded endpoint, the semantic policy's mean target-ledger prefix is 161.159 seconds versus count-only's 160.136 seconds. There is **no demonstrated time-cost win**.

The semantic experiment performs nine initial surrogate fits and 270 paid-update surrogate fits, each with three scalar GP heads. Recorded model-plus-run host work is 4.481129 seconds; paid-update timers overlap that envelope. Independent startup-inclusive observations record 11.329356 seconds for prepare plus run, and 14.700618 seconds for separate replay. Qualification records another 77.769630 subprocess-monotonic seconds. These scopes must not be added indiscriminately. Raw UTC/monotonic disagreements remain flagged; no uninterrupted elapsed-wall-time or total-cost advantage is claimed. [Validation and receipts](../results/2026-10-22-selection-improvement-validation/README.md) preserve the timings and checks.

From the repository root, using Python 3.12 and `requirements-speedup.txt`:

```sh
make reproduce-count-selection PYTHON=python
make reproduce-semantic-selection PYTHON=python
make diagnose-workload-support PYTHON=python
```

Each output directory must be fresh. Override `COUNT_SELECTION_REPLAY_OUTPUT`, `SEMANTIC_SELECTION_REPLAY_OUTPUT` or `WORKLOAD_SUPPORT_OUTPUT` for another replay. Both selection commands reproduce 135 new trajectories / 405 endpoints, preserve all preceding controls, and exclude only explicitly named host-timer fields from exact comparison. The support command replays archived profiling without native work.

The next milestone is **one useful untouched workload with multiple automatically extracted, executable candidates and measured labels**. Resolve the demonstrated coverage/qualification gap under a declared legal context, preserving these failed sources. Do not lower gates after seeing outcomes, introduce whole-binary rewriting without safety evidence, or sweep feature/kernel variants on consumed labels. Freeze a compatible fresh protocol and controller before collecting its labels. The original research question and later joint-set validation remain unchanged.

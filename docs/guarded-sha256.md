# Guarded sixth workload and prospective selection

The original Embench SHA256 program now runs through automatic extraction, safe lowering, whole-program execution, correctness controls, integrated synthesis, and routing. All six declared candidates pass. This brings automatic evidence to **33 verified labels across six workloads**, with **36 candidate attempts, 39 measured processor designs and 117 routes**. The three older failed attempts and original CRC32 adapter experiment remain unchanged.

The [five-workload analysis](improvement-analysis-2026-10-21.md) found a source-relocation failure, entrypoints that could bypass a new guard, implicit retry behavior, and collection that stopped at the first failure. The new guarded entrypoint fixes these connections. Its fresh source-bound plans reject old runners, check original assembly before stratification, authenticate cached lowering, freeze the public pool before measurements, persist one-attempt ledgers, and continue past recorded terminal failures. Interrupted or unknown outcomes are never turned into speedup labels or free retries.

## Measured outcome

Baseline: **26,135,630 cycles**, **1,653 LUT4**, minimum routed Fmax **68.493149 MHz**. All speedups below use the same feasible **12 MHz** clock, not a candidate-specific maximum clock.

| Candidate | Formula | Cycles | Speedup | Added LUT4 | Min Fmax MHz | Correctness |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 00 | `xor(add(srli(in0,2),slli(in0,30)),in1)` | 24,798,030 | 1.053939769× | 68 | 68.250069 | Pass |
| 11 | `xor(add(srli(in0,17),slli(in0,15)),in1)` | 25,257,830 | 1.034753579× | 68 | 68.096695 | Pass |
| 22 | `add(in0,slli(in1,21))` | 25,588,430 | 1.021384665× | 50 | 65.993530 | Pass |
| 33 | `add(in0,slli(in1,14))` | 25,770,830 | 1.014155539× | 61 | 68.587105 | Pass |
| 44 | `or(slli(in0,24),in1)` | 25,998,830 | 1.005261775× | 47 | 66.626694 | Pass |
| 57 | `sub(addi(0,64),in0)` | 26,134,205 | 1.000054526× | 101 | 67.608681 | Pass |

Each candidate passes the original full digest check, exact PCPI execution counts, independent integer/lowering checks, stock firmware on the extended core, custom firmware rejection on the stock core, integrated netlist recount, and all three routes. These are RTL simulation and FPGA synthesis/routing estimates, not physical-board measurements. Fixed-input correctness does not prove arbitrary-input safety.

Candidate 22 is the measured pool optimum under the primary **+64 LUT4** cap: **2.09% fewer cycles** with 50 extra LUT4. Candidate 00 is faster but exceeds that cap; it wins at the predeclared +128 cap. At +32, the baseline is retained. This complete oracle covers the six frozen candidates, not all 56 eligible formulas.

## Fair comparison and what the model learned

The [prelabel checkpoint](../results/2026-10-21-sha256-preregistration/README.md) and all predictions were committed and pushed at [`ab3789f`](https://github.com/jas0nriverah/agentic-riscv-codesign/commit/ab3789f106eab46df26ebcce56a6909e8d34c45b) before any candidate label. Twenty-seven historical labels from five other workloads were available; 21 remained for fitting after six related-family exclusions. Hyperparameters, features and all ten policies stayed fixed. Ten policies × three budgets × three area caps × five dependent seeds produce **450 endpoints**. SHA256 is one independent held-out workload; seeds are not independent workload trials.

At +64 LUT4, the smallest tested budget reaching the optimum in all five seeds is:

| Policy | Queries | Mean charged candidate seconds at that budget |
| --- | ---: | ---: |
| Latency plus hardware-cost heuristic | **1** | **67.471** |
| Frequency | 2 | 134.518 |
| Hybrid GP with paid adaptation | 2 | 134.518 |
| Merit / calibrated latency | 3 | 200.552 |
| Normalized XGBoost / zero-shot hybrid GP | 3 | 200.552 |

At three queries, raw XGBoost reaches the optimum in 3/5 seeds, pairwise ranking in 2/5, and random in 4/5. **ML does not beat the strongest heuristic.** Adaptation improves over merit at the secondary two-query endpoint, but a simpler cost-aware heuristic still needs fewer measurements. All per-budget, per-cap results are in the [readable report and CSVs](../results/2026-10-21-sha256-campaign/report/results.md).

Raw regression predicts measured whole-program speedup. Normalized XGBoost predicts measured saved cycles per candidate execution and reconstructs program speedup using the untouched baseline profile. Ranking learns from measured benefits. The hybrid policies use analytic latency as the benefit estimate and learned integrated area, timing and evaluation-duration distributions for feasibility/acquisition. They are not isolated LUT predictors, but their hardware uncertainty remains uncalibrated.

All six new cycle deltas exactly match the calibrated analytic baseline, extending that match to **all 33 successful automatic labels**. Normalization reduces SHA256 speedup MAE from 0.016548112 to 0.006941309, but nominal 90% interval coverage is only 43.3% (raw: 16.7%). Better prediction error does not establish better decisions. More cycle-model versions are not justified by this result.

## Architectural compatibility and costs

The compiler remains `-Os`, RV32I plus supported counter reads, ILP32, and existing software helpers. The unchanged PicoRV32/PCPI processor has 8 KiB RAM. Exact-flag linker evidence motivated a declared 7,488-byte program limit, a 128-byte guard and 576 stack bytes. Baseline execution observes 384 stack bytes, leaving 192 bytes of headroom. Both drivers retain the 800-million-cycle ceiling. No benchmark input or digest verification was reduced.

Original marked assembly yields 59 executable formulas before the relocation guard. Three formulas referencing `H0.0`, `K`, or `buffer` are rejected; 56 safe, calibrated formulas remain. The existing merit-rank stratifier chooses six before custom measurements. Deterministic RTL implements those instructions; no RTL-rewriting agent or new enumeration algorithm was added.

The six attempts cost **402.461094 ledger wall-seconds**. Historical candidate attempts cost **1,698.152954 seconds**, including all three failures, for **2,100.614048 seconds** across 36 attempts. The new ledger timer includes validation within its scope; narrower measurement-record timers remain in the CSV. Repeated public discovery checks before ledger creation, baseline qualification, calibration and inference are separate. These figures are not a complete collection or lifetime project timer. Native command times overlap wall timers and must not be added.

The [six-workload corpus](../results/2026-10-21-six-workload-corpus/README.md) keeps compatible features, cycles, speedup, integrated resources, timing, failure classifications and context provenance. All six workloads are now consumed development data. Do not retune on SHA256 and describe it as untouched test evidence.

## Working commands

Python 3.12 and `requirements-speedup.txt` reproduce the archived experiment without native tools:

```sh
make reproduce-sha256 PYTHON=python
make sha256-report PYTHON=python
python scripts/export_guarded_corpus.py --output generated/reproduction/six-workload-corpus
```

The export requires a fresh output directory. Replay authenticates original-source bindings, raw measurements, both Git prelabel proofs, exact historical model refits and all 450 endpoints. The report is an analysis artifact, never a selector input.

Native collection used these commands, with the complete protocol and predictions committed and pushed at the indicated point:

```sh
python -m isaforge.guarded_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/guarded-sha256-2026-10-21 --workload nettle-sha256 \
  --program-limit 7488 --stack-floor 7616
python -m isaforge.guarded_workload freeze \
  --root generated/guarded-sha256-2026-10-21 --scope dataset-expansion
python -m isaforge.guarded_selection freeze \
  --target-root generated/guarded-sha256-2026-10-21 \
  --root results/2026-10-21-sha256-selection --scope prospective
# Preregister every prediction, baseline, source hash and native protocol;
# commit and push before the first candidate attempt.
python -m isaforge.guarded_workload collect --root generated/guarded-sha256-2026-10-21
python -m isaforge.guarded_selection evaluate \
  --root results/2026-10-21-sha256-selection \
  --target-root generated/guarded-sha256-2026-10-21
python -m isaforge.guarded_evidence audit --root generated/guarded-sha256-2026-10-21
```

Use fresh roots for recollection. Do not repeat failed/interrupted attempts in an existing protocol. A rare crash between writing `measurement.json` and finalizing its ledger currently stops strict audit; preserve that context for explicit recovery rather than promoting or retrying the measurement.

## Next useful improvement

The remaining selection problem is hardware feasibility and confidence, not missing cycle benefit labels for these supported patterns. First test operation-order/immediate-sensitive hardware descriptors and uncertainty diagnostics on the now-consumed six-workload data, with whole-workload/family exclusions and the cost-aware heuristic always present. The prior analysis demonstrates a nearly identical feature vector predicting a wrong area boundary with near certainty. Promote a descriptor/acquisition change only if it improves feasible-design decisions in those diagnostics, then freeze it before a fresh workload or explicitly disclosed new-input test. Never claim a development gain as a prospective win.

Also instrument the outer collection wall time and reduce redundant authenticated-discovery work without weakening original-source checks. Preserve both timing scopes and all frozen sources. These are measured engineering bottlenecks, not reasons to create unrelated infrastructure. The bounded LLM selection agent and jointly measured one-to-three-instruction sets remain later milestones; neither is claimed complete here.

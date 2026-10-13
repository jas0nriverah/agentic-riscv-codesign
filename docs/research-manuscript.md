# ISAForge: resource prediction and measured RISC-V instruction fusion

Working research manuscript, 13 October 2026. SoC simulation and paired FPGA routing are complete.

## Abstract

Formula-based resource prediction improves transfer accuracy over the original predictor, but the frozen decision experiments do **not** establish improved measurement efficiency over instruction-saving merit. On the final five programs, the transparent resource baseline outperforms the residual ML model in both MAE and RMSLE; all models and merit tie on the primary selection endpoint. Separately, two CRC32 custom instructions pass processor checks and reduce the complete benchmark's simulated cycles. These results concern different targets: isolated FPGA resources, instruction-saving selection, and processor cycles. They cannot be combined into a claim of general CPU acceleration or superiority over published tools.

## Research direction and related work

The question is whether a reusable, formula-only resource model can prioritize limited hardware measurements while retaining useful instruction savings. The pipeline extracts safe dataflow groups, verifies their semantics, measures hardware resources, predicts costs, and evaluates acquisition decisions under a measurement budget.

[CIDRE](https://arxiv.org/abs/2509.15782v2) analyzes application hotspots and generates custom instructions with nML descriptions for downstream cost/benefit assessment. [ARISE](https://arxiv.org/abs/2508.07725v1) generates extensions from assembly patterns using metrics for code size and instruction-count reduction, with CoreDSL integration. Our frequency and merit policies represent simple heuristic ideas; neither reproduces these systems. Different processors, candidate spaces, constraints, and cost accounting prevent a matched superiority claim.

## Evidence and coverage

All 19 workloads in the pinned Embench checkout were executed across three stages. Compiler flags were RV32IM, ILP32, `-O2`, GNU C17, `CPU_MHZ=1`, and one warmup. GCC 15.2.0, Spike revision `f8a060b7bea8da6f738f193ed1b66b665978d092`, and Embench revision `0466a18e4f6b47e19598d7c6ba72916d54b68f65` were recorded. Counter windows require exact commit-count agreement and zero undecoded instructions.

| Stage | Declared programs | Candidate-bearing programs | Measured rows | Distinct circuits |
| --- | ---: | ---: | ---: | ---: |
| Original development | 8 | 8 | 339 | 301 |
| First transfer / later calibration | 6 | 4 | 198 | 167 |
| Final independent test | 5 | 5 | 561 | 453 |

The original eight were aha-mont64, crc32, edn, huffbench, matmult-int, nettle-aes, nettle-sha256, and wikisort. Stage two declared statemate, nsichneu, minver, nbody, slre, and ud; stage three declared cubic, picojpeg, qrduino, sglib-combined, and st. Numerical workloads use software floating point under RV32IM.

Statemate and nsichneu passed self-checks but yielded no legal candidates. Nsichneu has no eligible dependency edges within its executed blocks. Statemate's only eligible pair, in `memset`, crosses an overwrite of its original input register and is rejected. These are coverage failures, not successful selection trials; stage-two program averages have denominator four, not six. No workload substitution or extractor relaxation occurred.

Candidates contain two to four eligible operations, at most two inputs, one output, preserved input lifetimes, and complete contribution to that output. Savings use disjoint occurrences of one formula, expressed as retired instructions rather than cycles. Full candidate pools were measured in both transfer stages; the initial stage-two 48-per-program sample was expanded before model scoring, with the original sample retained.

## Models and frozen evaluation

The original XGBoost model fits 301 distinct formulas from 339 benchmark-associated rows. V2 adds structural resource features, a nonnegative resource regression, and a fixed XGBoost log-residual correction. Features consult formula structure only; inference receives formula and identity fields. V2 was developed exclusively on original data. Mechanical serialization repairs preserved learned parameters and all 339 original-row predictions.

The earlier frozen protocol designates distinct-novel-formula MAE as primary accuracy; RMSLE, Spearman, nonzero subsets, and per-program results are also retained. A later package declaration used different primary wording; the earlier protocol governs, and both metrics are reported here. Stage two excludes original training formulas, leaving 81 novel circuits. Stage three excludes the union of training and calibration formulas, leaving 331; 271 of these have nonzero LUT cost.

| Stage | Model | Novel MAE, LUT4 | Novel RMSLE |
| --- | --- | ---: | ---: |
| First transfer, 81 circuits | Original v1 | 16.216 | 0.973 |
| | Resource baseline | 12.499 | 0.449 |
| | Residual v2 | 10.152 | 0.546 |
| Final, 331 circuits | Original v1 | 87.595 | 0.755 |
| | Resource baseline | 23.154 | 0.409 |
| | Residual v2 | 33.165 | 0.450 |

V2 improves stage-two MAE while the baseline wins RMSLE. The baseline wins both final metrics. Final nonzero MAEs are 106.809, 28.238, and 40.506 respectively. Final macro program MAE is 36.264 for v2, with descriptive program-bootstrap interval [21.560, 51.230]; this is a different aggregation from distinct-formula MAE.

## Decision results and measurement costs

The frozen primary endpoint is mean per-program oracle-savings retention at 64 LUT4 and one new measurement; caps 32/64/128 and budgets 1/3/5 form the fixed sensitivity grid. Frequency, merit, merit per operation, 100-seed random ordering, and model feasibility-first merit ranking share identical pools. Acquisition cannot access measured labels. Only attempted measurements determine feasibility; the exhaustive oracle is retrospective. Random seeds are averaged within programs, then 10,000 bootstrap resamples use whole programs.

The first transfer result is negative: v1 and v2 retain 0.855 versus merit's 1.000. Both retain only 0.419 on SLRE. Their paired difference versus merit is −0.145, with descriptive interval [−0.435, 0]. A later conservative policy calibrates the maximum novel-formula log overprediction within each of four stage-two programs. Its program-weighted margin was frozen before final labels were accessed; blinded synthesis could run before that freeze. The discounted score orders acquisition and is excluded from regression accuracy.

On the final five programs, merit, all point models, and the conservative policy retain 1.000 with zero feasibility failures. Their primary paired difference is exactly zero; an observed [0,0] bootstrap interval does not establish population equivalence. Frequency and merit per operation retain 0.924; random retains 0.063. Merit already reaches the oracle ceiling, limiting discrimination; model policies show no primary advantage. The full sensitivity grid is retained.

Historical measurements are additional costs: 301 original circuits plus 167 calibration-stage circuits, including 81 novel ones. Final evaluation measured 453 circuits exhaustively, although each simulated policy spends only its declared attempt budget. Summed stage counts are 921 circuit measurements; cross-stage formula overlap leaves 713 distinct formulas overall. Cache-containing expansion wall times are not cold synthesis costs. Final v2 warm inference took approximately 32.5 ms per 561-row batch, excluding loading and JSON IO; this is not an end-to-end synthesis-efficiency result.

## Processor validation

Pinned PicoRV32 revision `ef203c2b0a3fb793280f5114941416c425c5b461` integrates the CRC32 index and shifted-XOR formulas via PCPI. Native recurrence sequences delete actual instructions, without padding. Boundary/random checks, independent host oracles, zero-work controls, identical baseline execution on extended cores, illegal-encoding traps, and handshake counts pass. Long response latencies also show slowdowns, so instruction reduction alone cannot predict cycles.

The complete CRC32 benchmark uses source-level macro lowering, 170 repetitions of 1,024 updates, and matching RV32I compiler flags. Stock versus source-wrapper control and stock execution on extended cores match. The full checksum passes in addition to upstream's truncated check. Both extensions reduce cycles from 27,685,314 to 25,770,434 at one wait cycle, a 1.0743 cycle ratio; combinational response gives 25,422,274 cycles and 1.0890. These are equal-clock cycle ratios, not measured wall-time speedups. The RV32I random generator differs from the original RV32IM tracing target.

A closed SoC also integrates 8 KiB synchronous writable RAM, with 20 BRAM blocks on the common clock and no external memory ports. Matched stock/source-wrapper and stock-on-extended-core controls pass; byte-mask/load and bounds-fault checks pass. Complete CRC32 cycles decrease from 32,387,382 to 29,602,102 (1.0941), with LUT4 growing from 1,633 to 1,704 (+71). This separate memory setting must not be mixed with core-only ratios.

Whole-core mapping grows from 1,488 to 1,625 LUT4 for registered response (+137); combinational response uses 1,570 (+82). Decoder/handshake logic is included; external RAM is excluded. Carry cells, flip-flops, and internal memories are also recorded. Isolated LUT4 labels are neither complete core area nor routed timing.

Matched iCE40HX8K CT256 routes (seeds 1–3) all meet 12 MHz with fixed eight pins and on-chip RAM. Baseline/custom Fmax estimates are 71.803/67.074, 70.897/67.454, and 69.080/72.005 MHz. Paired cycles/Fmax give conditional time ratios 1.0220, 1.0410, and 1.1404 (median 1.0410). Every seed is retained. These tool estimates are not board measurements; reset/status electrical timing remains outside the synchronous estimate.

After evaluation, the transparent resource baseline was selected for deployment and refit on all 1,098 rows / 713 distinct formulas. This artifact has **no independent test**. The prospective scores above belong to separate models frozen on the original 301 formulas; they are not deployment-refit accuracy.

## Limits

Small, correlated convenience samples, constant circuits, approximate structural costs, sampled equivalence tests, one integrated application, and one processor constrain generalization. Formal proof, energy measurements, and broad application integration are absent. Routing estimates do not measure board runtime, energy, temperature, or external I/O electrical behavior. A matched published-system comparison and new independent workloads are required before stronger claims.

Evidence: `results/2026-10-13/`, `generated/holdout/`, `generated/final-holdout/`, and `generated/core/`, and `generated/soc/`; small artifacts are copied to `results/2026-10-13-prospective/`. See [reproduction instructions](reproduce-research.md) and the two frozen protocol documents.

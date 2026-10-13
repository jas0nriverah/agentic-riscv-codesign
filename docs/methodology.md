# Methodology

ISAForge asks whether reusable cost prediction can find useful RISC-V custom instructions with fewer expensive measurements. The implemented study connects execution tracing, safe instruction-fusion extraction, semantic checking, isolated hardware synthesis, budgeted acquisition replay, and a separate processor integration experiment. Its learned models currently predict **isolated iCE40 LUT4 resources**. They do not predict integrated CPU cycles, clock frequency, or speedup. An LLM selection loop and a live gem5 measurement adapter remain unimplemented.

## From executed code to a hardware candidate

Pinned Embench programs are compiled for RV32IM and executed with Spike commit logging. Instruction-counter windows reconcile the dynamic trace with retired instructions before candidate extraction. Recorded tool versions, compiler settings, binary hashes, and trace hashes identify the workload configuration; see [toolchain.md](toolchain.md) and the [original execution record](../results/2026-10-13/benchmarks.json).

The extractor forms two-to-four-operation dataflow groups within executed blocks. Legal candidates have at most two inputs, one output, preserved input lifetimes, and complete contribution to the output. Loads, stores, unsafe register overwrites, and inappropriate control boundaries constrain the search. Canonical RV32 formulas identify shared circuits across programs. A candidate's frequency and estimated saved retired instructions describe its trace occurrences; they do not measure CPU cycles. Disjoint occurrences of one formula support its savings estimate, while combining different formulas requires additional overlap analysis. Details and substitution checks are in [candidates.md](candidates.md) and [extraction-equivalence.json](../results/2026-10-13/extraction-equivalence.json).

Each distinct formula is translated to combinational Verilog with explicit RV32 truncation and signedness. Verilator outputs are compared with an independent integer-semantics oracle on boundary and seeded random inputs before synthesis labels enter the dataset. These checks detect semantic bugs but are sampled testing, not formal equivalence. Yosys separately records generic cells and mapped iCE40 resources; the learned label is the actual `SB_LUT4` count from the isolated candidate, excluding processor integration and routing. Carry, flip-flop, and memory counts retain their own units. See [synthesis.md](synthesis.md).

## Keep quantities and endpoints distinct

| Quantity | Evidence and interpretation |
|---|---|
| Retired instruction savings | Trace-derived estimate for replacing eligible occurrences; no implied cycle saving. |
| Isolated LUT4 label | Actual mapped-cell count from Yosys; one FPGA resource rather than physical silicon area. |
| Predicted LUT4 | Model estimate from formula-derived features, or label-free pre-ABC SOG features for MasterRTL. |
| Acquisition quality | Offline retention of a fully measured pool's oracle instruction savings under a target measurement budget. |
| Integrated cycles | Functional simulation of matched processor/firmware configurations. |
| Routed frequency and elapsed-time ratio | nextpnr timing estimates combined with simulated cycles; no physical-board runtime measurement. |

A model may rank isolated cost well without selecting the best CPU extension. Decoder/handshake costs, memory latency, response latency, occurrence overlap, and clock changes require integrated measurement. The [SoC experiment](soc-integration.md) therefore supplies separate evidence rather than a training label silently inferred from instruction savings.

## Earlier prospective experiment: 301 training formulas

The workload study collected three stages:

| Stage | Declared / candidate-bearing programs | Rows | Distinct formulas |
|---|---:|---:|---:|
| Original development | 8 / 8 | 339 | 301 |
| First transfer, later policy calibration | 6 / 4 | 198 | 167 |
| Final prospective programs | 5 / 5 | 561 | 453 |

The transfer stage has 81 formulas absent from the original training cohort. The final evaluation has 331 absent from both training and calibration, including 271 positive and 60 zero LUT labels. Two declared transfer programs yield no safe candidates; they remain coverage failures, with four candidate-bearing programs in selection averages. Sources are the [transfer evaluation](../results/2026-10-13-prospective/transfer/evaluation.json) and [final evaluation](../results/2026-10-13-prospective/final/evaluation.json).

The original formula XGBoost, nonnegative resource regression, and fixed resource-plus-log-residual XGBoost artifacts train only on the original 301 formulas. Original grouped development validation excludes an entire program and every matching held-out formula, using inner folds for model selection. Prospective predictions use frozen artifacts; a conservative acquisition margin uses the transfer cohort and freezes before final label access. A later all-data deployment refit does not inherit the earlier final set's independent-test status. See [fresh-evaluation-protocol.md](fresh-evaluation-protocol.md) and [final-policy-protocol.md](final-policy-protocol.md).

## Matched six-model experiment: 713 training, 192 test formulas

The later comparison treats all earlier workload labels as development data: 1098 program/formula occurrences, 713 unique formulas, and 17 candidate-bearing programs. Final fits give one weight to each canonical formula. All six comparators receive this same cohort and target: v1 formula XGBoost, v2 resource prior, v2 residual XGBoost, v3 original-feature ablation, v3 structural challenger, and the MasterRTL SOG adaptation.

V3 adds algebraic normalization, live-bit/DAG structure, carry-aware adders, backward barrel-shifter demand, comparator structure, and multiplier resources. A nonnegative structural resource prior permits extrapolation; standardized log features support a bounded, shrunk residual. A fixed six-candidate grid includes the old resource fallback, the feature resource prior, two ridge penalties, and two Huber penalties. Nested program holdouts select by macro-program MAE, excluding identical formulas in outer and inner splits. The final original-feature fit selects the old resource model; the structural fit selects ridge alpha 10. These development scores remain exploratory because earlier labels influenced the research direction. The full grid, selections, predictions, and hashes are in [model records](../results/2026-10-13-v3/models/).

The matched reference adapts [MasterRTL commit 5bccf38](https://github.com/hkust-zhiyao/MasterRTL/tree/5bccf38f8db7bb511a793a709863e7cb1b333ab5): its 14 analytical SOG features and 25-tree, depth-12 raw-target XGBoost recipe. Formula RTL passes through a label-free Yosys pre-ABC flow. Direct one-bit JSON counts replace the authors' Pyverilog graph parser; the target becomes isolated LUT4, sequential features are zero, IO is fixed, and threads/seed are fixed. The recipe is not tuned on this comparison. These departures make it a matched-target adaptation, not a reproduction of the paper's ASIC model or scores; see [the exact protocol](masterrtl-matched-protocol.md).

The probe generator predeclares eight structural strata with 24 formulas each, excludes all 713 canonical training formulas, and freezes candidates before label collection. The resulting 192 circuits pass 412,416 oracle comparisons. Five comparator artifacts freeze at 06:08:10 UTC and MasterRTL at 06:20:14 UTC on 2026-10-13, before the labels are released for scoring. Source, data, artifact, input, and prediction hashes bind the records. Freeze timestamps document consistency and ordering rather than independently proving absence of prior human access. See [probe freeze](../results/2026-10-13-v3/probe/freeze.json), [verification](../results/2026-10-13-v3/probe/verification.json), and [both model freezes](reproduce-matched-comparison.md).

The primary probe endpoint is macro-stratum MAE, numerically equal to pooled MAE because all strata are equally sized. Secondary metrics include RMSLE, positive-label MAPE, correlations, zero-target error, and every stratum. MAPE excludes true zeros and is never converted into an accuracy percentage. Canonical exclusion prevents exact-formula leakage; it does not establish semantic independence, independent real workloads, or a calibrated confidence interval. No refit, feature change, or model substitution follows probe scoring.

## Budgeted decisions and processor validation

The prospective acquisition experiment orders candidates using frequency, merit, seeded random policies, and predicted feasibility plus merit. All policies share pools, caps, and attempted-measurement budgets; only measured candidates can be selected, with the unmodified processor available. Historical training/calibration labels are additional costs outside the target budget. Exhaustively measured pools provide a retrospective oracle, whose full label cost is not counted as ordinary acquisition. The primary decision endpoint is per-program oracle-savings retention at a 64-LUT cap and one new measurement, with the complete sensitivity grid retained. See [selection.md](selection.md).

Two CRC32 formulas are separately implemented through PicoRV32 PCPI and source-level instruction lowering. Response-latency controls, stock firmware on extended cores, a source wrapper without fusion, independent checksums, handshake checks, and memory tests help attribute differences within this experiment. The closed SoC uses the same synchronous on-chip RAM in simulation and synthesis. Matched routes retain every seed, fixed constraints, device/package, pin map, and netlist hashes; their cycle/Fmax ratios remain conditional estimates. No learned CPU-performance model or automated LLM choice is demonstrated.

## Reproducibility and limits

Canonical loaders verify frozen schemas and artifact/source hashes. The five formula models need no synthesis at inference. MasterRTL requires retained graph features or compatible Yosys extraction for uncached formulas; cold and cached timings are reported separately. [Matched replay](reproduce-matched-comparison.md) reproduces all six scores from tracked inputs without regenerating labels, while [hardware reproduction](reproduce-research.md) describes the workload and processor experiments.

Small correlated program samples, synthetic compositions, sparse multiplier coverage, sampled semantic checks, one integrated application/processor, and absent energy or physical-board measurements constrain generalization. Prediction intervals are not calibrated; older program-bootstrap intervals are descriptive, and observed selection ties do not prove population equivalence. The study reports these limitations and unsuccessful comparisons in [results.md](results.md).

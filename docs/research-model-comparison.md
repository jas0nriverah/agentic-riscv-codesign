# Published results and the next cost model

Checked 13 October 2026 against the papers themselves. Different prediction targets and workloads prevent treating this table as a shared leaderboard.

The model-development discussion below records the earlier 713-formula stage.
For the current completed experiment, see [V6 results](v6-results.md): mapping
features improve its fixed synthetic primary by 6.32%, while application
transfer and useful selection gains remain unestablished. The
[14 October literature update](research-update-2026-10-14.md) adds VeriDistill
and concrete follow-up experiments; the [normalization diagnosis](../results/2026-10-14-v6/audit/normalization-research.md)
connects current failures to proved compiler-style transformations.

| Published system | Reported result | Evaluation boundary |
| --- | --- | --- |
| MasterRTL, extended TCAD study, Table III | ASIC total-area MAPE 16%, Pearson R 0.98 | 90 RTL designs; bit-level Simple Operator Graph features and a lightweight area model; ASIC cell area, not iCE40 LUT count |
| HLS GNN, DAC 2022, Table 5, PNA-I | LUT MAPE 21.45%; critical-path MAPE 4.80% | Previously unseen real applications; hierarchical knowledge-infused model infers auxiliary resource information at inference |
| Same paper, PNA-R | LUT MAPE 16.96%; critical-path MAPE 3.97% | Uses HLS intermediate information at inference, so its input cost differs from formula-only prediction |
| CIDRE, Table I | CRC32 estimated execution-time speedup 1.39× for 2-input/1-output; peak 2.47× on AES with 3 inputs/2 outputs | Eight custom instructions per configuration; RV64IM three-stage ASIP and ASIC synthesis; across configurations area overhead stays below 24% |
| ARISE | Average dynamic instruction-count reduction 7.39% | Embench-IoT; up to 16 extensions, compiler/simulator integration; instruction count is not elapsed runtime |

Sources: [MasterRTL extended paper](https://users.cs.duke.edu/~lkw34/papers/fang-presynthesis-tcad2024.pdf), [MasterRTL original representation and method](https://arxiv.org/html/2311.08441v1), [HLS GNN paper](https://arxiv.org/pdf/2201.06848), [CIDRE](https://arxiv.org/html/2509.15782v2), [ARISE](https://arxiv.org/abs/2508.07725).

MAPE means the mean of each example's absolute error divided by its true target, expressed as a percentage. It is undefined at zero. Pearson correlation is not percentage accuracy, and it differs from Spearman rank correlation. A low absolute error need not imply a low percentage error on small circuits.

## Our frozen results in context

On the same 331 final novel formulas, v1/resource/residual MAE is 87.595/23.154/33.165 LUT4. Recomputing percentage error on the 271 positive-LUT formulas gives **57.189% / 39.888% / 32.481% MAPE**. The 60 zero-LUT formulas remain in MAE/RMSLE but are excluded explicitly from percentage error. Thus the structural linear model wins absolute error, while the residual model wins positive-target percentage error. These are different objectives; neither model dominates every metric.

The paper numbers provide useful targets, but they do not establish that our model is better or worse on a matched task. Whole ASIC designs, post-route FPGA programs, and tiny combinational iCE40 instruction formulas differ in scale, tools, available features, and zero-target behavior. Likewise, our two-instruction PicoRV32 CRC result cannot be ranked against CIDRE's eight-instruction RV64 result.

## Changes being tested

1. Represent composition and demanded bits more faithfully. MasterRTL's bit-level representation and HLS GNN's resource-informed neighborhoods motivate features for live carry spans, per-stage barrel-shifter demand, constant comparator patterns, sharing, and multiplication columns. This is an adaptation of those ideas, not a reproduction of either model.
2. Keep an extrapolating physical-resource prior. Compare improved physical counts and small regularized residual models rather than assuming a larger neural network helps with 713 formulas.
3. Use nested program-held-out model selection, excluding identical formulas from each training fold. Primary selection is macro-program MAE, with RMSLE, positive-target MAPE, correlation, zeros, and ablations all retained. The 713-formula corpus has already been inspected, so these scores are development evidence.
4. Freeze model/configuration/source/artifact hashes before opening labels from 192 new synthetic stress formulas. These circuits test transfer across formula compositions; they are not additional real workloads or a published-system benchmark. Do not tune and rescore that probe as if it remained untouched.

Existing observed failures motivate the features: carry spans can be much shorter than 32 bits; a single demanded output bit of a variable shifter can depend on many intermediate muxes; adjacent inverse arithmetic can collapse to wires. Zero LUTs can also mean carry-only logic, so zero LUT cost is not zero hardware cost.

Actual processor timing remains a separate target. CIDRE's clock-aware evaluation is a reason to retain our integrated cycle and routing checks, not to rename area prediction as speedup prediction. A future timing model needs a substantially larger set of integrated processor measurements.

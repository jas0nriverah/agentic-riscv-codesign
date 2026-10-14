# Research update: representation cost and processor-aware selection

This update records additional primary literature reviewed during the V6 experiment. It does not change the frozen V6 hypothesis, inputs, models or scoring rules. The existing [development study](v6-development-direction.md) covers MasterRTL, priority-cut mapping, DeepGate2 and calibration under distribution shift.

## VeriDistill: learn from low-level circuits, predict from source

**The Graph's Apprentice (IJCAI 2025)** trains a predictor on frozen code-model embeddings and regularizes it toward a teacher trained on LUT graphs. At inference, the student needs Verilog source rather than a synthesized graph. The final paper uses about 16,000 retained examples, a 75/10/15 split, and OpenROAD with a 7 nm technology; OpenABCD supplies a separate transfer evaluation. Table 1 reports CodeV VeriDistill area MAE 0.482 and R² 0.872, versus AST-GNN MAE 0.893 and R² 0.661. These are the paper's target scale—its plots show log area—not iCE40 LUT counts. Its MAPE column is therefore not a directly comparable ISAForge percentage. The authors report that the combination of code embeddings and distillation matters; neither component alone provides the same gain. [Final proceedings paper, sections 3–4 and Table 1](https://www.ijcai.org/proceedings/2025/1033.pdf).

**Implication for ISAForge:** prediction quality and preprocessing cost should be separate objectives. Our graph features still require generic synthesis. A later experiment could train a small formula/AST student to reproduce a stronger graph teacher, using teacher outputs from training folds only. Compare it with a label-only student and the full graph model on identical held-out groups; report cold extraction, warm inference, memory and accuracy. Teacher graphs or predictions from held-out labels must not enter fitting. An LLM is a candidate implementation, not a prerequisite or an established improvement for this small dataset. No distillation model has been implemented in this checkpoint.

## CIDRE: instruction savings can lose to the critical path

**Automatic Microarchitecture-Aware Custom Instruction Design for RISC-V Processors (2025)** evaluates eight applications and selects eight instructions per application/configuration. Its selection incorporates synthesis-derived clock periods, with execution-time estimates assuming CPI = 1. Table I reports a maximum 2.47× estimated speedup for AES with three inputs and two outputs. Under two inputs and one output, CRC32 reaches 1.39×, while Susan reaches 0.99×: a small instruction-count benefit is outweighed by the longer clock period. These are architecture/configuration-dependent estimates, not measurements of ISAForge's PicoRV32 implementation. [Primary paper, sections III–IV and Table I](https://arxiv.org/html/2509.15782v1).

**Implication for ISAForge:** the next system experiment should compare complete selected instruction sets at a fixed total measurement budget. Rank by estimated workload time using integrated cycles and timing, while accounting for overlapping instruction opportunities and shared hardware. Compare against merit-only, random and measured-oracle controls. A lower isolated-area MAE is useful evidence but does not establish better instruction selection. Our separate CRC32 case study already measures whole-SoC cycles/resources and paired timing estimates; it does not yet demonstrate a learned selector's advantage.

## Order of work

1. Finish the frozen V6 point-prediction and calibration experiment, retaining every failure and comparator.
2. Diagnose its errors by circuit mechanism and complete structural group; preserve its test as consumed evidence for subsequent development.
3. Test transfer on additional untouched application families. More variants of one synthetic template cannot supply this evidence.
4. Evaluate cost-aware selection and source-only prediction as separate hypotheses, each with a frozen budget, comparator and held-out evaluation.

These papers motivate specific tests. Their reported scores are not targets that can be matched by changing ISAForge's denominator, hardware technology, data split or output scale.

## V7 mechanism study: compiler analysis with proof obligations

LLVM's `KnownBits` representation tracks bits known to be zero or one, distinguishes signed significant width from unsigned width, and provides separate low-product and signed/unsigned high-product analysis. This is a useful reference for the multiplier failures exposed by V6. Sparse support and signed width are different properties: a mask with a small population can still include the sign bit. [LLVM KnownBits reference](https://llvm.org/doxygen/structllvm_1_1KnownBits.html).

The V7 development study adds small, fixed known-bit and modular-affine feature blocks while retaining the original implementation's measured LUT4 target. Every accepted rewrite has a bit-vector proof. LLVM's value-tracking code also uses no-wrap flags and undefined-value assumptions in some transformations; those assumptions cannot be copied into total RV32 arithmetic, where overflow wraps and shift distances are masked. [LLVM value-tracking implementation](https://www.llvm.org/doxygen/ValueTracking_8cpp_source.html).

This is a hypothesis about useful model inputs, not a new compiler-analysis algorithm or an established accuracy gain. Neither proposed correlated-bit identity occurs in the original fitting corpus. The fixed six-view study therefore distinguishes descriptor benefits from stronger normalization and retains an explicit mechanism-coverage limitation. See the [V7 development protocol](v7-development-protocol.md).

## Newer preprints: optimization requires a different endpoint

**AutoPPA (April 2026)** learns rewrite rules from contrasting RTL implementations and applies them through bounded search. Its main flow uses SiliconCompiler and FreePDK 45 nm. Table 3 reports 20.45% average area improvement over original designs across 11 circuits, while average delay improvement is −4.85%: area gains can accompany slower hardware. Its described equivalence filter uses generated simulation testbenches. These are implementation optimization results, not prediction error. [Primary preprint, sections 3.2 and 5, Table 3](https://arxiv.org/html/2604.18445v1).

**Alpha-RTL / TTT-RTL (June 2026)** reports a 0.349 geometric-mean area×delay×power ratio over the 44-design common-success subset of RTLLM v2.0, with 48/49 overall coverage. The paper explicitly identifies different model backbones, mainly single-seed results, and simulation-only correctness as limits. Its Nangate 45 nm benchmark and Sky130 case study are separate from ISAForge's FPGA target. [Primary preprint, Table 1 and limitations](https://arxiv.org/html/2606.05253v1).

**Action for ISAForge:** retain independent functional proofs where our bounded combinational language permits them, and assess any future optimization or instruction-selection policy under equal synthesis budgets. Record every failed candidate and report area and timing separately before combining them. A lowered LUT4 prediction error cannot be presented as either paper's hardware optimization ratio. More LLM sampling without a defined hardware objective and cost-matched baseline would not resolve the current transfer problem.

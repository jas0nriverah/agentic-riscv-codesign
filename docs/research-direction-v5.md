# Literature-informed research direction

This is a research agenda, not a claim that ISAForge reproduces or exceeds a
published system. Updated 2026-10-14. The V5 protocol fixes the next matched
experiment; application transfer and processor benefit are separate studies.

| Primary work | Relevant finding and scope | Consequence for ISAForge |
| --- | --- | --- |
| [MasterRTL, 2023](https://arxiv.org/html/2311.08441v1) | Bit-level simple-operator graphs support cross-design PPA estimation on 90 ASIC designs. Its reported area MAPE is 16%, with correlation 0.98. | Preserve the original bit-level graph, compare equally tuned estimators, and measure preprocessing cost. ASIC area and isolated FPGA LUT4 count are different targets. |
| [Lam, Srikanthan and Clarke, 2014](https://doi.org/10.1145/2560014) · [author preprint](https://purehost.bath.ac.uk/ws/portalfiles/portal/136642138/Rapid_Evaluation_of_Custom_Instruction_Selection_Approaches_with_FPGA_Estimation_Preprint.pdf) | FPGA estimates for 150 custom instructions from 16 applications report average area error 0.40% and delay error 2.85% on Virtex-4/ISE. The evaluated class excludes multiplication, division and nonconstant shifts. | Carry, width and operation structure are useful inductive biases. The small headline error is not a fair target for our broader operation set without a matched restricted experiment. |
| [Constrained Bayesian optimization, 2014](https://arxiv.org/abs/1403.5607) | Models objective and feasibility uncertainty, including constraints that can be evaluated separately. This is a general optimization method, not a hardware accuracy benchmark. | Learn and assess feasibility under a declared measurement budget. Report false accepts, coverage and total measurement cost; prediction MAE alone cannot establish better selection. |
| [ARISE, 2025](https://arxiv.org/html/2508.07725v1) | Automated RISC-V extensions evaluated with Embench report average dynamic instruction reduction of 7.39%, static code reduction of 1.48%, and dynamic code reduction of 3.84%. The study does not establish cycle, area or energy improvements. | Preserve compiler/execution correctness and distinguish retired-instruction savings from hardware speedup. Compare useful end-to-end outcomes under equal resources. |

## What the completed V4 audit changes

V4's same-data MAE difference from the fixed MasterRTL adaptation was small
and its descriptive interval included zero. Most absolute error came from
multipliers. Features from normalized circuits sometimes described very
different implementation costs from the original RTL used for labels. Exact
feature overlap and repeated structural families also weakened the transfer
interpretation of a formula-only holdout.

V5 therefore keeps original and normalized graph channels, adds explicit
unsigned range/output-demand features, compares four strictly nested feature
sets with the same estimator budgets, and holds out complete structural groups
for calibration. All previously inspected examples are development data.
The [protocol](v5-protocol.md) freezes inputs, models and predictions before
new target measurements. The original RTL remains the target in every view.

## Order of evidence

1. **Matched synthetic transfer.** Complete all 256 V5 measurements, report
   both declared scopes and every failure, and retain the original primary
   comparison even if a simpler model wins. There are only 19 novel structural
   clusters; five strata have one cluster each. Conditional bootstrap intervals
   cannot estimate between-family variation in those five strata.
2. **External application transfer.** Compile and check pinned programs from
   independent algorithm families. Report all attempted programs, including
   empty extraction pools, and distinguish familiar formulas from novel ones.
   The first planned families are shortest paths, speech decoding and anagram
   search from [TACLeBench](https://github.com/tacle/tacle-bench), pinned to
   `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`. Licenses are per program.
3. **Budgeted selection.** Freeze merit, random and model-assisted policies
   before revealing candidate costs. Charge feature extraction, failed attempts
   and validation to the total budget. Evaluate feasible instruction benefit,
   not only error on measured circuits. Calibration requires enough independent
   groups in difficult strata; a nominal bound does not establish coverage
   under application shift.
4. **Processor integration.** Lower selected instructions, verify complete
   program outputs, and measure cycles, whole-processor area and timing under
   matched configurations. Isolated LUT savings omit decode, interface,
   registers and routing costs. Existing CRC32 results remain a separate case
   study, not evidence for arbitrary new instructions.

## Model changes that need a later untouched test

The next revision should be driven by V5's retained failure classes and the
external cohort's input structure. Candidate directions include mapper-aware
carry/width features, specialized multiplier structure, physically motivated
cost decomposition, and a calibrated abstention/acquisition policy. These are
hypotheses. Do not select a revision on V5 labels and report its new V5 score as
independent validation. Preserve the old model and start a new lineage.

More model capacity is not automatically the best use of effort: limited
independent families, incomplete application validation and missing integrated
hardware labels can dominate the research conclusion even when training error
is low. The immediate contribution is a reproducible experiment that identifies
which representation improvements transfer and where their cost is justified.

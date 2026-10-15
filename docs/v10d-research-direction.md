# From verified area savings to a useful hardware decision

The [complete V10d result](v10-csd-hardware-results.md) establishes that one exact CSD rewrite can reduce mapped LUT4 cost on the fixed development cohort. It does not establish a new constant-multiplication algorithm or prove that CSD is optimal.

## What prior work motivates

Garcia and Volkova distinguish word-adder count, one-bit-adder cost and adder depth. They optimize these quantities explicitly and evaluate synthesized hardware. Their work also treats truncated arithmetic with a bounded error, a different contract from ISAForge's exact modulo-2^32 semantics. The relevant lesson is to measure resource and timing effects separately; fewer source adders alone cannot decide the best implementation. [Primary paper, sections III-B, IV and VI](https://arxiv.org/html/2210.02742v2).

This motivated the now [completed matched routing study](v10d-timing-results.md). All 32 formula mean periods improve, while carry tradeoffs and one packed-resource regression remain. A separately frozen alternative exact adder-graph comparison is useful only with an explicit resource or timing objective; the current measurements do not establish CSD optimality. Importing approximate truncation would change the functional task and is not part of this study. Published MCM results concern different circuits and flows, so our LUT savings are not a matched superiority result.

## The actual decision we need to support

For each candidate implementation, keep the original formula, exact RTL, synthesis configuration and physical target tied to its measurements. Retain both resources rather than assigning an unsupported exchange rate between LUT4 and carry cells. Measure full registered-harness timing under common boundaries and constraints. Identify a datapath-limited critical path only when packed connectivity supports that attribution; otherwise retain wrapper-limited or unavailable attribution.

The common clock target and PCF have different roles: pin locations alone do not define external arrival or required times. The timing report's clock-level Fmax is the stated endpoint. We do not derive an arithmetic Fmax from an arbitrary sum of net-delay entries. [nextpnr constraints](https://github.com/YosysHQ/nextpnr/blob/main/docs/constraints.md), [report implementation](https://github.com/YosysHQ/nextpnr/blob/main/common/kernel/report.cc).

## What this does and does not change in the model

The latest trained predictor still estimates original-RTL LUT4. Its 299-LUT target for original multiplication by 511 remains correct even though the rewritten implementation measures 62 LUT4. A deployment that selects the rewrite needs implementation-specific labels and validation; rewriting the historical target would invalidate the model comparison.

The next step is to evaluate implementation choice under explicit resource and clock constraints, then integrate selected instructions into the processor and rerun full workloads before claiming a CPU benefit. All 192 harness routes meet the current 12 MHz target, so this cohort establishes no improvement in the count of timing-feasible designs at that threshold. In parallel, preserve the original-area prediction task and address its observed comparator, shift, branch and arithmetic-chain feasibility errors. Those objectives require separate evaluation from the hardware rewrite result.

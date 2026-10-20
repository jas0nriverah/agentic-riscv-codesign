# Prospective SLRE preregistration

Frozen before any of the six target candidates were measured. The target baseline and extraction are complete; target candidate outcomes are pending in this commit. `protocol.json` binds public candidates, predictions, historical labels, source code, package versions, and the new compiler/memory context. `baseline-command-receipts.json` preserves the exact precollection native-command prefix.

- Held-out workload: upstream Embench SLRE with fixed self-checking input; no target candidate performance or hardware labels were read.
- Six formulas sampled at evenly spaced merit ranks from 16 eligible executable formulas, rather than selecting the six largest predicted benefits.
- Existing XGBoost regression and ranking settings are fixed. The only predeclared feature ablation adds eight independently defined execution features to the same regression ensemble. Training uses 12 prior automatic CRC32 and aha-mont64 outcomes with workload/family exclusions.
- Policies: frequency, merit, calibrated latency, seeded random, fixed regression, fixed ranking, and the execution-feature regression ablation. Budgets: 1, 2, 3 target measurements; five model/random seeds. The seeds are not independent workloads.
- Feasibility: integrated area at most baseline +128 LUT4 (1,781 total) and all three routed seeds meet 12 MHz, with verified whole-program correctness. Baseline remains an available incumbent.
- Explicit context shift: SLRE uses GCC -Os and a checked 4,224-byte program limit / 3,840-byte stack reservation in the same 8 KiB hardware. Historical training workloads use -O2 and the original partition. Do not call this a uniform compilation-context study.
- Baseline upstream self-check, continuous stack/write checks, two deliberate memory-violation controls, and observed/unobserved execution equivalence passed. SLRE used 3,072 stack bytes, leaving 768 checked bytes of headroom for these inputs.
- Component tests passed before freezing. The new complete suite and final raw-evidence replay are still pending. An existing legacy process-cleanup test was already failing intermittently in the previous checkpoint; this commit does not claim a green complete suite.

This checkpoint tests prospective transfer, not ML superiority, broad generalization, calibrated uncertainty, or deployed production readiness. The measured oracle will cover only these six candidates. Keep this checkpoint unchanged when outcomes become available.

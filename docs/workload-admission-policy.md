# Workload admission policy — October 28 owner correction

The owner explicitly removed the fixed twelve-candidate and 0.5% projected-benefit admission requirements. These were experimental implementation choices, not requirements of the original proposal. This policy supersedes historical instructions that forbid reconsidering a workload solely because of pool size or projected opportunity.

## Active requirements

- Admit variable-sized pools of legal, executable candidates. One candidate is sufficient for measurement; an empty pool supplies source-screen evidence but no candidate training rows.
- Do not reject a workload for low, zero, or negative projected benefit, or for fewer than ten timed replacements. These are recorded features, not correctness gates. Preserve measured neutral and negative results.
- Record any compute-driven pool cap before labels. A cap is a maximum, never a minimum; retain the complete discovered roster and the sampling rule.
- Compare policies on the same pool and available information within each workload. Use effective measurement budget min(requested budget, pool size), record both, and count failed attempts and elapsed evaluation time.
- If a budget exhausts a pool, do not claim search-efficiency superiority at that budget. Report results by workload and pool size; correlated candidate rows are not independent workloads.
- Keep semantic correctness, executable lowering, relocation safety, ISA/interface compatibility, memory/stack safety, and actual area/timing verification. Predicted feasibility is advisory, not a substitute for measurement.
- Keep entire test workloads and related formula families excluded from fitting; freeze policies before new target outcomes. Reconsidered sources are already source-screened, not untouched source discoveries.

## Historical evidence and revised experiments

Never overwrite historical frozen artifacts or relabel their failures as successes. Existing fixed-pool entrypoints remain reproducibility tools for their named studies, not active admission policy. A revised experiment uses a fresh context/output directory, records its changed admission policy and previous exposure, and may reuse authenticated baseline evidence where the contract supports it. The previous nanocobs run remains a failed fixed-twelve experiment; its ten legal candidates are eligible for a revised study.

No model improvement follows from admission alone. The next evidence is measured per-candidate whole-program cycles, integrated hardware resources, timing, correctness, and evaluation cost. Multiple selected instructions must still be executed and measured together.

# MiBench stringsearch v2 selector transfer pilot

This is one fixed MiBench stringsearch workload with source and exact operator-tree families excluded from model fitting. It does not establish broad workload generalization. The prelabel commit and complete measurement accounting are embedded in `study-report.json`.

The LLM selector ran first as one live current-Codex chat-relay episode, with at most two real candidate measurements (B2 exhausts the pool; requested B3 is capped at two) returned one at a time. Only after it finalized were the remaining candidates measured to form the complete pool. The frequency, merit, latency/cost, random, XGBoost, factorized feasibility, and active-learning policies are replayed under requested B1/B2/B3 budgets with effective min(B,2). Their target observations are counterfactual callback releases from the fully collected dataset; the physical dataset build itself cost all candidate evaluations.

The unit-level metrics are whole-program cycles, speedup, correctness, LUT4 increment, minimum routed Fmax, paid attempts, and actual evaluation time. See `factorized-policy-report.json`, `outcomes.json`, `native-audit.json`, the verified SQLite agent trace, and archived `native.tar.gz` for full evidence.

The Codex relay is cooperative rather than sandboxed; exact model ID, token use and model-only latency are unavailable. One agent episode and one workload are not enough for an agent-quality or generalization claim. Individual-instruction measurements do not demonstrate combined-instruction performance.

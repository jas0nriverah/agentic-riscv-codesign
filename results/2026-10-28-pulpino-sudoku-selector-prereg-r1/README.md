# PULPino Sudoku prospective selection preregistration

This zero-label package freezes the first full pipeline transfer experiment on a new held-out workload. It contains no Sudoku candidate measurements.

## Frozen cohort and models

- Target: one pinned 9×9 Sudoku puzzle run twice; 12 legal, executable, calibrated single-instruction candidates.
- Historical data: 122 successful measured labels and 4 failed attempts across 14 workload groups. Exclude the target workload and all exact target operation-tree families before fitting: 106 rows / 14 groups remain; 16 historical successes are excluded.
- Models: existing pairwise XGBoost speedup ranker, factorized feasibility XGBoost plus public analytic cycle savings, existing regression/ranking/active-learning controls. No new model family or hyperparameter sweep.
- Agent: one current Codex chat relay with frozen seed-zero ML outputs, public frequency/merit/timing signals, hybrid historical retrieval, and four structured tools. No LLM fine-tuning or cross-provider routing claim.

## Budget and evidence

Primary evaluation: 64 added LUT4, at least 12 MHz across all three routes, and a maximum of three charged measurements. The LLM agent runs first and sees only public information and its own paid outcomes. The remaining candidates are measured only after finalization to establish the complete measured oracle; non-agent policy replays release each policy only its own paid prefix. Physical corpus construction can cost twelve candidate evaluations.

The endpoint is best verified feasible whole-program speedup by budget and cycle-reduction regret versus the measured pool oracle. Correctness, timing, area, evaluation count and measured evaluation time are reported separately. No superiority claim is preregistered.

The qualification found baseline **1,024,889 cycles / 198,711 instructions**, a **2,288-byte image**, **3,968-byte observed stack** with **1,792-byte headroom**, no stack/guard violations, **1,653 LUT4**, 295 carry cells, 655 flip-flops, 20 BRAMs, and routed timing above 12 MHz on all three seeds. These are baseline measurements, not candidate speedups.

## Release rule

Candidate dispatch is blocked until the preregistration, source, and evidence hashes are committed and pushed to `ai-guided-ml`. The executor verifies the exact local and remote commit before release. See `preregistration.json`, `agent-protocol.json`, `source-family-audit.json`, `model-fit-costs.json`, and `manifest.json`.

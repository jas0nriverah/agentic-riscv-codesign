# Tiny-regex prospective selector preregistration

This package freezes the next ISAForge selection experiment before any target candidate is measured. It is a related-domain regex/text transfer pilot, not a generalization or superiority result.

## Frozen data and models

- Target: the pinned 76-case `tiny-regex-c` fixed suite; 12 executable candidates across 11 operation-tree families.
- Training: 106 historical measured rows across 14 workload groups after excluding all 11 target families; 16 overlapping historical successes are held out. Six SLRE rows remain, so workload lineage is related-domain.
- Ranker: existing XGBRanker `rank:pairwise` recipe trained on historical measured whole-program speedup orderings. Its score is relative rank, not a speedup estimate.
- Hardware selector: existing 20-member XGBoost feasibility ensemble multiplied by public analytic cycle savings. Scores and member spread are uncalibrated.
- LLM: no fine-tuning. One current Codex chat relay receives bounded predictions and hybrid retrieved historical examples through four structured JSON tools. The exact model ID and token counts are unavailable; cross-provider routing is not used.

## AI engineering and evidence

The host owns the budget, candidate identities, one-attempt dispatch, correctness and feasibility checks, final selection, and the rationale-to-measurement links. Hybrid retrieval uses TF-IDF lexical and TF-IDF/truncated-SVD semantic similarity with reciprocal-rank fusion; a typed knowledge graph is available but is not queried in this hybrid-mode episode. A verified SQLite database will project the sealed requests, decisions, tool calls, memory traces, and host outcomes. The JSON ledger remains authoritative.

## Status and release sequence

Target labels read: **0**. Target labels observed: **0**. Candidate attempts: **0**. Do not dispatch candidates until this complete directory, its source code, and its data bindings are committed and pushed to `ai-guided-ml`. Then run the commands in `docs/tiny-regex-selection-study-contract-2026-10-28.md` in order.

The experiment runs the live agent first with up to three measurements, measures the remaining pool only after it finalizes, then replays all frozen controls at budgets 1, 2, and 3. The physical oracle collection costs up to twelve candidate evaluations. If any outcome is unknown or infrastructure-censored, oracle speedup and regret remain null. Known correctness failures are charged and excluded as infeasible.

See `preregistration.json`, `agent-protocol.json`, `model-fit-costs.json`, `source-family-audit.json`, and `manifest.json` for machine-readable protocol and provenance.

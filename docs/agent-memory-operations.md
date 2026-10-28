# Agent memory, retrieval and local LLMOps

October 28, 2026. Implemented and exercised both offline and with two fresh live GPT-6 Luna subagents. This extends the existing selector; it does not replace the numeric models, hardware guardrails or historical measurements.

| Capability | Concrete implementation | Evidence |
| --- | --- | --- |
| Episode memory | Host stores paid observations, attempted IDs, constraints and incumbent | Both live agents receive updated public snapshots after every action |
| Historical memory | One approved historical measurement per source-linked record/chunk | Corpus and record hashes appear in retrieval traces |
| Semantic search | Local TF-IDF + truncated SVD embeddings and cosine similarity | Semantic-mode offline replay and live hybrid retrieval |
| Hybrid search | TF-IDF cosine ranking + latent-semantic ranking, reciprocal rank fusion k=60 | Four retrieval events in live hybrid episode |
| Function calling | Existing list_candidates, predict, measure, finalize structured actions | 13 live agent decisions, relayed unchanged into the host |
| Loop engineering | Finite calls, charged attempts, outcome feedback, host acceptance and baseline fallback | Three infeasible finalization requests rejected in the no-retrieval episode |
| Observability | Verified SQLite export joins decisions, tools, calls and retrieval events | Separate databases for both live arms, with 9 and 4 model-turn rows |
| LLMOps | Source/prompt/model configurations, sealed run protocols, repeatable tests and versioned reports | Frozen commit 46957811 precedes the live pilot |

## Scope and method

`HistoricalMemory` indexes only the historical measurement records in the host's approved public request. No repository search, arbitrary documents or hidden target labels enter the index. The host's existing history filtering excludes target workload and matching expression families; retrieval adds checks for target groups and exact formulas before fitting. This is a restricted evidence-memory implementation, not a general research-document search engine.

The semantic baseline is **latent semantic analysis**, not pretrained neural language embeddings. Its vocabulary is learned locally; unseen terms cannot produce useful matches. With fewer than two documents no semantic projection is fitted. TF-IDF cosine is the lexical baseline, not BM25. SVD dimensions are min(16, record count minus one, vocabulary size minus one), random state 0. Hybrid uses reciprocal rank fusion with k=60. One historical record is one chunk; no arbitrary prose chunking or cross-encoder reranker is claimed. [scikit-learn method documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html).

A fixed query derived from unattempted candidate formulas retrieves up to three records before each model decision. The full approved history remains available in every arm, so retrieval changes ordering/emphasis rather than information access. Retrieved records are labeled evidence, not instructions or target predictions. The agent cannot choose arbitrary queries yet. Both routing roles receive the same augmented request if routing is enabled. LLM-selected search and pretrained embeddings remain potential later experiments.

SQLite is a derived local inspection store. The exporter verifies sealed manifests, protocol and ledger bindings before reading results. It preserves null token counts when unavailable. Interactive elapsed time includes orchestration and waiting; it must not be labeled inference latency. Remote-provider traces retain observed usage. No cloud deployment, production monitor, automatic rollback or external telemetry is claimed. The primary ledger stays authoritative; exports never modify it.

## Reproduce the software checks

```sh
../work/audit-venv/bin/python -m pytest \
  tests/test_agent_memory.py tests/test_routed_selection.py \
  tests/test_selection_provider.py tests/test_bounded_selector.py \
  tests/test_run_bounded_selector.py tests/test_codex_chat_selector.py -q

# Requires a fresh output path. Runs deterministic controls, no LLM or hardware calls.
../work/audit-venv/bin/python scripts/evaluate_agent_memory.py \
  --output generated/my-agent-memory-check
```

The completed engineering check ran none/lexical/semantic/hybrid modes, each with ten matched archived SHA256 controls and 30 endpoints: 40 trajectories, 120 endpoints, 232 decisions and 174 retrieval events. All controls match. These policies ignore retrieval, so matching proves noninterference only, not retrieval quality or better selection. The new retrieval fits are not new speedup/hardware model versions.

## Inspect actual live-agent evidence

See [the frozen pilot and results](../results/2026-10-28-live-luna-memory/README.md). These contain actual model choices, paid archived measurements, public request snapshots and sealed ledgers. They are not mock responses.

```sh
# Choose a fresh database filename outside the sealed run directory.
../work/audit-venv/bin/python scripts/export_agent_observability.py \
  --run results/2026-10-28-live-luna-memory/hybrid \
  --output generated/live-hybrid-trace.sqlite
```

Useful queries:

```sql
SELECT d.decision, d.status, t.tool, t.status, t.charged_attempt
FROM decisions d LEFT JOIN tools t
ON d.episode=t.episode AND d.tool_sequence=t.sequence
ORDER BY d.episode,d.decision;

SELECT decision, mode, corpus_sha256, returned_ids FROM retrievals;
SELECT model, COUNT(*), SUM(total_tokens), SUM(usage_complete) FROM model_calls GROUP BY model;
SELECT role, trigger_reason, status, COUNT(*) FROM model_calls GROUP BY role, trigger_reason, status;
```

Null total tokens mean unavailable, not free. `elapsed_seconds` on interactive model rows includes host waiting and orchestration. No token-cost comparison is supported by this pilot.

## What the live pilot establishes

Two fresh configured `gpt-6-luna` agents made 13 total live decision turns. Hybrid memory reached the feasible SHA256 pool oracle in two paid replay queries; no retrieval reached it in three. Both finish at 1.0213847x, +50 LUT4 and 65.9935 MHz. The no-retrieval agent made three rejected attempts to finalize a faster but over-cap candidate. Frequency and the latency/cost heuristic already find the optimum on query one, random and adaptive GP on query two for this seed.

Thus the pilot demonstrates real tool use, measured feedback, memory injection and observable guardrail enforcement. One trajectory per arm, one consumed workload, instruction-enforced file boundaries and unavailable token/inference accounting prevent a causal memory-benefit, cost-saving or generalization claim. Shared file access was restricted by instructions, not by sandbox. The configured model alias is known; exact deployment version is not. Model routing recovery remains offline-tested; neither live arm used a second model.

Next evaluate fixed policies across multiple predeclared repetitions/workloads and include retrieval relevance tests. Do not select successful trials or rerun consumed data and call it unseen evidence. Joint instruction sets and novel workload generalization remain unfinished.

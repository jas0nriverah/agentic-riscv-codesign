# Agent memory, retrieval and local LLMOps

October 28, 2026. Implemented and exercised both offline and with two fresh live GPT-6 Luna subagents. This extends the existing selector; it does not replace the numeric models, hardware guardrails or historical measurements. ISAForge trains XGBoost ranking/regression models from measured candidate outcomes; the LLM selector is **not fine-tuned**. It uses a versioned prompt, structured tools, current episode state, and split-approved prior measurements as context.

| Capability | Concrete implementation | Evidence |
| --- | --- | --- |
| Episode memory | Host stores paid observations, attempted IDs, constraints and incumbent | Both live agents receive updated public snapshots after every action |
| Historical memory | One approved historical measurement per source-linked record/chunk | Corpus and record hashes appear in retrieval traces |
| Semantic search | Local TF-IDF + truncated SVD embeddings and cosine similarity | Semantic-mode offline replay and live hybrid retrieval |
| Hybrid search | TF-IDF cosine ranking + latent-semantic ranking, reciprocal rank fusion k=60 | Four retrieval events in live hybrid episode |
| Knowledge graph | Typed local graph: workload, candidate, expression family, operator, measurement; operator-overlap retrieval with source triples | Software prototype and leakage/path tests; no live-agent quality comparison |
| Function calling | Existing list_candidates, predict, measure, finalize structured actions | 13 live agent decisions, relayed unchanged into the host |
| Loop engineering | Finite decision turns, actual provider-call allowance, charged attempts, outcome feedback, one-shot recovery, host-owned incumbent/baseline fallback | Three infeasible finalization requests rejected in the no-retrieval episode; separate budget/fallback accounting is offline-tested |
| Observability | Verified SQLite export joins decisions, tools, calls, retrievals and host fallback events | Live-pilot exports retain calls/retrievals; new controller traces export fallback reasons separately |
| LLMOps | Source/prompt/model configurations, sealed run protocols, repeatable tests and versioned reports | Frozen commit 46957811 precedes the live pilot |

## Scope and method

`HistoricalMemory` indexes only the historical measurement records in the host's approved public request. No repository search, arbitrary documents or hidden target labels enter the index. The host's existing history filtering excludes target workload and matching expression families; memory and graph lookup repeat that exclusion. The new typed evidence graph links the approved candidate record to workload, expression-family, operator, and measurement nodes. It returns source hashes and matched graph triples. The graph score uses operator overlap only and does not use measured outcome values. This is a restricted evidence-memory implementation, not a general research-document search engine or graph database; see the [graph contract](candidate-evidence-graph.md).

The LLM sees the current episode's candidate roster, public predictions, paid measurements, remaining decision/provider/tool/measurement budgets, and optional approved historical rows. This is bounded in-context state, not a long-term chat-memory system. The final model-authored rationale is retained for audit but is not currently fed back as a future training example or memory hit. Do not fine-tune or claim that the LLM learned from one live trajectory; those traces are Evals evidence only.

The semantic baseline is **latent semantic analysis**, not pretrained neural language embeddings. Its vocabulary is learned locally; unseen terms cannot produce useful matches. With fewer than two documents no semantic projection is fitted. TF-IDF cosine is the lexical baseline, not BM25. SVD dimensions are min(16, record count minus one, vocabulary size minus one), random state 0. Hybrid uses reciprocal rank fusion with k=60. One historical record is one chunk; no arbitrary prose chunking or cross-encoder reranker is claimed. [scikit-learn method documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html).

A fixed query derived from unattempted candidate formulas retrieves up to three records before each model decision. The full approved history remains available in every arm, so retrieval changes ordering/emphasis rather than information access. Retrieved records are labeled evidence, not instructions or target predictions. The agent cannot choose arbitrary queries yet. Both routing roles receive the same augmented request if routing is enabled. LLM-selected search and pretrained embeddings remain potential later experiments.

SQLite is a derived local inspection store. The exporter verifies sealed manifests, protocol and ledger bindings before reading results. It preserves null token counts when unavailable. Interactive elapsed time includes orchestration and waiting; it must not be labeled inference latency. Remote-provider traces retain observed usage. No cloud deployment, production monitor, automatic rollback or external telemetry is claimed. The primary ledger stays authoritative; exports never modify it.

## Reproduce the software checks

```sh
../work/audit-venv/bin/python -m pytest \
  tests/test_agent_memory.py tests/test_routed_selection.py \
  tests/test_selection_provider.py tests/test_bounded_selector.py \
  tests/test_run_bounded_selector.py tests/test_codex_chat_selector.py -q

# Trace-bound decision-note and provider-budget tests.
../work/audit-venv/bin/python -m pytest tests/test_decision_rationale.py -q

# Requires a fresh output path. Runs deterministic controls, no LLM or hardware calls.
../work/audit-venv/bin/python scripts/evaluate_agent_memory.py \
  --output generated/my-agent-memory-check
```

The completed engineering check is preserved at [`results/2026-10-28-memory-graph-validation-r1`](../results/2026-10-28-memory-graph-validation-r1/README.md). It ran none/lexical/semantic/hybrid/knowledge_graph modes, each with ten matched archived SHA256 controls and 30 endpoints: 50 trajectories, 150 endpoints, 290 decisions and 232 retrieval events. All controls match; there were zero LLM calls and zero new native jobs. These deterministic policies ignore retrieval, so matching proves noninterference only, not retrieval quality or better selection. The new retrieval mode is not a new speedup/hardware model version.

### Held-out structural support diagnostic

The new [retrieval structural-coverage report](../results/2026-10-28-retrieval-structural-coverage-r1/README.md) queries the existing 122-label / 14-workload corpus with each candidate formula only. Each fold excludes the complete target workload and all matching expression-tree families before indexing. It scores the fraction of target formula operator *types* represented in the top three retrieved formulas; target speedup, area, timing, and correctness labels are not used in scoring. Workload-macro coverage@3 is 0.9301 for the typed knowledge graph, 0.9103 for lexical TF-IDF, 0.9041 for hybrid retrieval, and 0.8765 for TF-IDF/SVD semantic retrieval; no retrieval is 0.0000 by definition. Every retrieval arm returned at least one hit.

This measures **structural support**, not semantic relevance or whether retrieved history helps an LLM choose better hardware. The graph directly ranks by operator overlap, so its higher coverage is not independent evidence of decision value. It adds zero labels, hardware runs, LLM calls, or model fits. Reproduce it with:

```sh
../work/audit-venv/bin/python scripts/evaluate_retrieval_structure.py \
  --output results/my-retrieval-structure-check
```

Choose a fresh output path. The report seals its corpus, source, and split bindings.

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
SELECT reason, error_type, candidate_id, model_calls, provider_calls, tool_calls,
       charged_attempts FROM host_events;
SELECT finalization_source, decision_call, tool_sequence, public_context_sha256,
       summary_author, summary_verified, host_facts_json FROM decision_rationales;
SELECT measurement_id, candidate_id, charged_attempt, status,
       public_observation_sha256, ledger_observation_sha256 FROM rationale_measurements;
```

`agent_summary` in the sealed ledger remains model-authored and unverified. The SQL rationale tables link it to the visible context and host-verified facts; the hashes identify exact logged JSON and are not hashes of native measurement files. A host fallback has no invented model explanation.

Null total tokens mean unavailable, not free. `elapsed_seconds` on interactive model rows includes host waiting and orchestration. No token-cost comparison is supported by this pilot.

## What the live pilot establishes

Two fresh configured `gpt-6-luna` agents made 13 total live decision turns. Hybrid memory reached the feasible SHA256 pool oracle in two paid replay queries; no retrieval reached it in three. Both finish at 1.0213847x, +50 LUT4 and 65.9935 MHz. The no-retrieval agent made three rejected attempts to finalize a faster but over-cap candidate. Frequency and the latency/cost heuristic already find the optimum on query one, random and adaptive GP on query two for this seed.

Thus the pilot demonstrates real tool use, measured feedback, memory injection and observable guardrail enforcement. One trajectory per arm, one consumed workload, instruction-enforced file boundaries and unavailable token/inference accounting prevent a causal memory-benefit, cost-saving or generalization claim. Shared file access was restricted by instructions, not by sandbox. The configured model alias is known; exact deployment version is not. Model routing recovery remains offline-tested; neither live arm used a second model.

Next evaluate fixed policies across multiple predeclared repetitions/workloads and include retrieval relevance tests. Do not select successful trials or rerun consumed data and call it unseen evidence. Joint instruction sets and novel workload generalization remain unfinished.

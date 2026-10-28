# Bounded agent implementation and evaluation

October 28, 2026. The owner resumed bounded engineering after presentation preparation. Existing measurements, trained models and hardware campaigns remain unchanged.

## What makes sense for ISAForge

The scientific question is whether intelligent selection finds better verified feasible designs with fewer costly measurements. Existing numerical models and hardware guards already supply the key tools. Adding retrieval frameworks or more predictors would not resolve the missing matched agent comparison.

| Plan component | Decision and reason |
| --- | --- |
| Structured tools, host guardrails and memory | Reuse the four-tool controller and paid-outcome ledger. Never move acceptance or attempt accounting into an LLM. |
| Dynamic model use | Implement one narrow, testable policy: primary first, one escalation on malformed structured output or the host's explicit incumbent correction. This tests recovery, not calibrated decision difficulty. |
| Observability and versioning | Implement separate per-provider traces and model/prompt/tool identities. Preserve source-bound protocol, explicit model IDs and archived-input hashes. |
| Context management | Retain stateless public JSON and a 200,000-byte request limit; reject oversized input rather than silently discard evidence. Each request now shows remaining decision turns after its response, so the agent can finalize before the host fallback. The router separately caps dispatched provider calls. The memory-augmented policy can hide raw training history and inject only top-K retrieved records, capped at 40,000 serialized bytes; this is byte-bounded retrieval, not token-aware compression or a token estimate. |
| Tokens and cost | Retain observed input/output/total tokens with missing-usage indicators. Per-call output cap remains 512 in the runner. No aggregate input-token or dollar ceiling is claimed; dollar cost stays null without explicit pricing. |
| Uncertainty-based escalation | Defer until a public-state trigger is frozen and validated. Existing uncertainty is not calibrated and LLM self-confidence is not a substitute. |
| Bounded historical retrieval and candidate KG | Implement local lexical, TF-IDF/SVD latent-semantic, hybrid, and typed operator-overlap graph retrieval over approved historical measurements. The small graph is a retrieval prototype, not a predictive model; no retrieval-quality or selection benefit is established. |
| General-document RAG, pretrained embeddings, vector database and reranking | Defer. Current evidence is a small structured table, and importing arbitrary documents adds leakage and provenance risk without an established need. |
| LangGraph / LangChain / MCP | Defer. The existing controller already owns state and tools. No demonstrated need for framework migration. |
| Ragas | Defer. Direct selection and tool-validity metrics are available; retrieval-quality metrics do not measure processor improvement. |
| Deployment | Defer until fixed-model and routed policies have a useful matched comparison. Keep the local research entry point. |

## Implemented behavior

`RoutedSelectionProvider` wraps the existing Responses provider. Both model roles get the same public-state snapshot and tool schema. A successfully parsed action returns directly to the host. One stronger-model call is permitted either after `InvalidActionError`, or on the next decision after the host explicitly rejects a finalization and returns its current incumbent ID. The latter addresses a concrete failure pattern from the earlier live pilot: three repeated finalization rejections. This is a bounded recovery rule, not evidence that routing improves design selection. Network errors, incomplete responses, byte limits, measurement failures, and other provider failures do not trigger escalation. Unknown candidate IDs and repeated measurements still reach the host's existing charging checks; routing does not erase submitted mistakes.

The explicit host-recovery trigger requires a finalization tool result with `status="error"`, `required_candidate_id`, and `allowed_candidate_ids`, as emitted by selector protocol v2. The stronger model receives the complete same public request, including the canonical current incumbent and correction. Only one escalation is allowed per episode across both trigger types, and it uses the same shared model-call allowance. A failed escalation does not cause a retry.

The existing `finalize.summary` field is a model-authored explanation; it is not a verified account of causality. A trace-bound rationale record now binds each accepted explanation to the exact visible context hash, final tool sequence, provider/policy references, host-verified selection facts, constraints, and measurement hashes. Host fallback records deterministic facts with `summary=null`; it never fabricates an LLM rationale. The SQLite exporter preserves these records separately from model prose.

The selector now reports two separate limits: outer decision turns and actual provider calls. Each model-visible request includes remaining decision turns and the available provider-call count, including the current response; a routed policy applies that count to its primary-plus-escalation calls. The runner checks provider exhaustion before opening another decision, so the ledger does not record an empty model turn after a routed budget is used up. Provider calls, decision turns, tool calls, and charged hardware attempts are stored separately. If a provider error or budget exhaustion occurs before agent finalization, the host closes with its best paid, verified, feasible incumbent, or baseline. The ledger marks `status=host_fallback`, `finalization_source=host`, and the reason/error type in a separate `host_events` record. This does not add a model/tool call or hardware attempt, and it never fabricates an agent summary. Correct model finalizations remain `status=finalized`, `finalization_source=agent`. Keyboard/process interruption still propagates after persisting its interrupted status; target-evaluation and host-integrity failures are not converted into successful agent turns.

Each decision records provider role, model identity, request hash, latency, status, usage and whether a provider call was charged. The escalation trigger (`invalid_action` or `host_incumbent_correction`) is retained as `model_calls.trigger_reason` in the SQLite export. Report accounting distinguishes reserved invocations from dispatched calls, decision turns, tool calls, and hardware attempts. Missing usage is explicit; observed token totals are lower bounds when usage is missing. No token count is inferred from characters. Traces are private evaluation data, never added to model input. On normal return, exceptions or catchable interruption the host persists the trace. Abrupt process death during an inner provider call can leave only the host's pending outer event; resume/retry is not implemented. The network timeout is not a strict process wall-time limit.

## Working commands

Use Python 3.12 with the pinned project environment. This command is offline and includes an actual archived SHA256 ten-policy comparison against the preserved control trajectories:

```sh
../work/audit-venv/bin/python -m pytest \
  tests/test_routed_selection.py tests/test_selection_provider.py \
  tests/test_bounded_selector.py tests/test_run_bounded_selector.py \
  tests/test_codex_chat_selector.py -q
```

For the full **122-test** selector, memory, rationale, routing and export suite, use the expanded command in [agent evaluations](agent-evals.md).

For an offline controls report, choose a fresh output directory:

```sh
../work/audit-venv/bin/python scripts/run_bounded_selector.py \
  --provider controls --target sha256 --seed 0 --cap 64 --budget 3 \
  --output generated/routing-controls-20261028
```

After explicitly selecting available model IDs and setting `OPENAI_API_KEY`, the remote replay command is:

```sh
../work/audit-venv/bin/python scripts/run_bounded_selector.py \
  --provider responses --model "$PRIMARY_MODEL" \
  --escalation-model "$ESCALATION_MODEL" --max-model-calls 12 \
  --target sha256 --seed 0 --cap 64 --budget 3 \
  --output generated/routed-selector-first-run
```

The latter is a paid LLM call against consumed archived hardware outcomes, not a fresh hardware experiment. It was not executed for this implementation. Omit `--escalation-model` for a fixed-model control using the same trace accounting. The CLI uses explicit model choices, never saved Codex credentials or an inferred model tier.

## Validation and next experiment

The combined focused selector, routing, memory, rationale, provider and SQLite suite passes **122 tests**, including exact-context hashing, host-fallback provenance, remaining-budget visibility, an exhausted-provider check that opens no empty decision, and a routed policy that refuses escalation when the effective allowance is exhausted. The existing host-correction recovery and incumbent guard remain covered. Earlier offline routing validation produced 10 archived SHA256 control trajectories and 30 endpoints, all matching the preserved controls, with zero LLM calls and zero native jobs. These are software validation results, not LLM-quality results. No live model call, new native job, candidate label, or model fit was performed for this work.

Next freeze three policies: fixed primary, fixed stronger model, and bounded recovery routing. Give each the same target pool, historical data, prediction tools, area/timing limits and hardware allowance; separately report model calls/tokens/time. Include merit, calibrated latency/cost, random and non-agent active learning. Count all failed episodes, report best feasible performance and regret only where the oracle is complete, and account for historical measurement cost. Use consumed pools only for engineering; a subsequent unseen-workload test is required for generalization. Recovery routing may save rejected turns, but may add model cost without changing final performance. Preserve either result.

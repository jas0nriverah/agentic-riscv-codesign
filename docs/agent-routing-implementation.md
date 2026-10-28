# Bounded agent implementation and evaluation

October 28, 2026. The owner resumed bounded engineering after presentation preparation. Existing measurements, trained models and hardware campaigns remain unchanged.

## What makes sense for ISAForge

The scientific question is whether intelligent selection finds better verified feasible designs with fewer costly measurements. Existing numerical models and hardware guards already supply the key tools. Adding retrieval frameworks or more predictors would not resolve the missing matched agent comparison.

| Plan component | Decision and reason |
| --- | --- |
| Structured tools, host guardrails and memory | Reuse the four-tool controller and paid-outcome ledger. Never move acceptance or attempt accounting into an LLM. |
| Dynamic model use | Primary first; retain the existing one-shot escalation on malformed structured output or explicit host correction. A new opt-in review route uses one stronger-model call when the primary proposes measuring a candidate other than the frozen ML utility recommendation. This is a policy-disagreement trigger, not calibrated uncertainty. |
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

The optional utility-override review is enabled with `--review-utility-overrides` on the Responses-provider runners and requires an explicitly configured escalation model. It triggers only after the primary returns a valid `measure` action that differs from the board's top unattempted factorized-score recommendation. Before any measurement is charged, the stronger model receives the same public board plus the primary's structured action and its unverified `decision_summary`; it may keep or replace that action. Each provider sees a freshly decremented remaining-call count, so a reviewer does not see the primary's already-consumed call as available. The board score remains an uncalibrated ordering proxy, so it is a review trigger, never a hard gate. The route is one-shot and shares the provider-call budget. If there is no call allowance or the review call fails, the host returns the already-valid primary action and logs the skipped/fallback reason. Both actions and request hashes are retained for audit. Accepted actions are bound to the exact input that produced them, including the review payload; the memory layer's separate byte-accounted public context remains unchanged. This directly targets the PULPino Sudoku episode where the agent chose C11 despite the displayed C02 utility recommendation; it has only offline protocol tests and no live efficacy result.

The existing `finalize.summary` field is a model-authored explanation; it is not a verified account of causality. A trace-bound rationale record now binds each accepted explanation to the exact visible context hash, final tool sequence, provider/policy references, host-verified selection facts, constraints, and measurement hashes. For routed actions, the exact accepted-action context and its provider-call role/hash are stored separately from the memory layer's pre-review snapshot, preserving byte-accounting checks. Host fallback records deterministic facts with `summary=null`; it never fabricates an LLM rationale. The SQLite exporter preserves these records separately from model prose.

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
../work/audit-venv/bin/python scripts/run_grouped_agent_selector.py \
  --provider responses --model "$PRIMARY_MODEL" \
  --escalation-model "$ESCALATION_MODEL" --max-model-calls 12 \
  --review-utility-overrides \
  --target-group embench-crc32 \
  --benchmark embench-crc32:63c7f40f7e906b046f5a1911d5ed91824bb1aa15673f8fa753a818ccc0d5f511 \
  --memory-mode hybrid --seed 0 --area-cap 64 --budget 3 \
  --output generated/routed-selector-first-run
```

The latter is a paid LLM call against consumed archived hardware outcomes, not a fresh hardware experiment. It was not executed for this implementation. The utility-review trigger requires the grouped board, which appears after predicting the complete pool; the historical SHA256 runner above checks recovery and control accounting. Omit both `--escalation-model` and `--review-utility-overrides` for a fixed-model control using the same trace accounting. The CLI uses explicit model choices, never saved Codex credentials or an inferred model tier.

## Validation and next experiment

October 28 budget/provenance validation passes **173 focused tests** using the command in [agent evals](agent-evals.md). Coverage includes successful review, provider-error and malformed-review fallback through hybrid memory and SQLite, reviewer finalization, and review consuming the final provider allowance before the one charged measurement and host fallback. The exporter rejects inconsistent context hashes or provider-call origins and retains compatibility with ledgers lacking the additive action-context fields. Review summaries distinguish changed actions, changed measurement candidates, skipped calls, and fallback; none means a successful correction by itself.

`make test PYTHON=../work/audit-venv/bin/python` passes **4,523 tests and 181 subtests**, with one existing duplicate-ZIP-name warning. `make reproduce PYTHON=../work/audit-venv/bin/python` reproduces all six frozen scores and the 192-candidate independent audit. These are protocol/reproduction checks, not evidence that a stronger model corrects a bad selection. Earlier offline routing validation produced 10 archived SHA256 control trajectories and 30 endpoints, all matching preserved controls, with zero LLM calls and zero native jobs. This change adds no live provider call, native candidate job, candidate label, model release, or training experiment; tests use local fixtures and the reproduction uses committed predictions.

Next freeze four policies: fixed primary, fixed stronger model, recovery-only routing, and the same recovery router with utility review enabled. The last two isolate the additional review trigger. Give every arm the same public board, target pool, historical data, prediction tools, area/timing limits, measurement-attempt limit, stopping rule, and total provider-call allowance; separately report model calls/tokens/time. Include merit, frequency, calibrated latency/cost, random and non-agent active learning. Count all failed episodes, report best feasible performance and regret only where the oracle is complete, and account for historical measurement cost. Use consumed pools only for engineering; freeze the protocol before labels on a subsequent eligible unseen workload. Review may add model cost without changing final performance. Preserve either result.

# Agentic workflow and evaluation plan

ISAForge evaluates the agent as a bounded measurement-selection workflow. The evaluation separates action reliability from research performance. A valid tool call or a fluent explanation is not evidence that a design is faster.

## Runtime loop

1. **Observe:** the host builds a typed request with the legal candidate roster, fixed predictions, hardware constraints, remaining tool/measurement budgets, decision turns remaining after the current response, paid observations, and any approved historical-memory or knowledge-graph evidence. The router separately enforces its shared cap on dispatched provider calls.
2. **Decide:** the configured primary model makes one structured function call. One stronger-model recovery is allowed after malformed output or an explicit host incumbent correction; both roles share the model-call allowance.
3. **Act:** the host validates the tool name and exact candidate ID. It reserves a measurement attempt before evaluation, including invalid or repeated `measure` requests.
4. **Verify:** the existing compiler/simulator/evaluator checks execution and correctness; synthesis/routing provides hardware cost and timing. The LLM cannot declare these outcomes.
5. **Update:** the host persists the event, result, attempted ID, remaining budget, and current feasible incumbent. The next request uses that public state.
6. **Stop:** a correct agent `finalize` is accepted only for the current host-computed incumbent. If model/tool calls fail or expire first, the host records a separate fallback to the best paid verified feasible result or baseline. An interrupted or charged hardware attempt is never silently retried.

This loop has an input request byte limit of 200,000 bytes and a configured response limit of 512 output tokens in the remote replay runner. The provider does not silently truncate the request. Input-token and dollar budgets are not currently enforced; returned token metadata is logged where available. The interactive Codex pilot does not expose model-only latency or exact token usage.

## Evals

### Deterministic agent and tool-use checks

The existing test suite uses injected transport responses to exercise unexpected outputs and multi-step actions without paying for model calls or hardware runs. The host-side verifier checks:

- only the four allowed functions and exact argument schemas are accepted;
- IDs are drawn from the public candidate roster;
- invalid/repeated measurement requests still consume the declared attempt budget;
- finalization cannot select an unmeasured, infeasible, slower, stale, or non-incumbent candidate;
- malformed output receives at most one stronger-model recovery under a shared call limit;
- failure after recovery closes on the host's verified incumbent/baseline, labeled `finalization_source=host`;
- process interruption, target evaluation failures, and host integrity errors remain distinguishable;
- the final model-authored note is bound to the exact accepted-action context and model/policy trace; routed review inputs are preserved separately from the memory layer's byte-accounted context, and host facts and measurement evidence are stored separately;
- host fallback produces no invented model explanation;
- SQLite export preserves escalation triggers, fallback events, rationale provenance, missing token data, and charged-attempt counts.

Reproduce the focused suite with:

```sh
../work/audit-venv/bin/python -m pytest \
  tests/test_agent_memory.py tests/test_decision_rationale.py tests/test_routed_selection.py \
  tests/test_selection_provider.py tests/test_bounded_selector.py \
  tests/test_run_bounded_selector.py tests/test_codex_chat_selector.py \
  tests/test_current_grouped_predictions.py tests/test_grouped_agent_case.py -q
```

The October 28 budget/provenance refresh passes **173 focused tests** with this command, **4,523 full-suite tests / 181 subtests**, and the frozen six-model reproduction. The full suite retains one existing duplicate-ZIP-name warning. These tests establish controller behavior and accounting invariants. They do not evaluate whether an actual LLM chooses better candidates.

### Decision explanations and traceability

The existing `finalize.summary` is now retained as a **model-authored, unverified note**. The host links it to the exact accepted-action context snapshot/hash visible to that decision, the final tool sequence and provider/policy references. For each decision turn, SQLite's `action_contexts` stores the serialized action input, hash, role, provider-call number, and routing trigger. This preserves a reviewer's input—including the decremented call allowance—without changing `context_windows`, which remains bound to the memory layer's input for byte-accounting. A separate host-generated record contains the accepted candidate's verified measurement facts, the area/timing constraints, charged attempts, and hashes for public and raw ledger observations. SQLite exposes `decision_rationales`, `rationale_measurements`, and `action_contexts` for review. Hashes establish which records were logged, not that the model's prose is true or causally complete. Host fallback explanations are deterministic facts with `summary=null`; the system never fabricates an LLM explanation.

This logging does not add a model call, a tool, or a measurement. It makes the model's stated rationale auditable; it does not establish that the rationale caused the choice. A reviewer can inspect whether the explanation is consistent with visible facts, but the host verifier remains the authority on correctness and final selection.

### Selection-quality evaluation

For every agent/control episode record the best paid verified feasible whole-program speedup after each charged attempt, correctness, area, minimum routed Fmax, number and duration of target evaluations, model calls, returned token counts, escalation and fallback rates, and regret only when the measured-pool oracle is complete. Compare with frequency, merit, latency/cost-aware heuristics, random, non-agent active learning, XGBoost ranking, and the measured oracle using identical public information and hardware budgets. Hold out entire workloads and formula families. Preserve all failed and early-stopped episodes; report incomplete pool references as lower bounds.

When testing the optional utility-override router, report the primary's proposed action, the frozen recommendation and score ratio, the stronger model's response, whether it changed the action, the provider-call/token/time overhead, and final best-so-far measured performance. Pair it against the same primary without review and all non-agent controls on a fresh preregistered pool. Since the factorized score and ensemble spread are uncalibrated, review frequency is not an uncertainty-calibration metric. A changed action is not a successful correction unless the paid, verified outcome improves the feasible performance frontier.

Use the current hardware oracle and host verifier as the decisive measure of system quality. Neither a model judge nor a model explanation can override correctness, speedup, area, or timing outcomes.

### LLM-as-a-judge: narrow and secondary

An optional judge can score the clarity and evidence support of the model's short explanation after the deterministic host outcome has been fixed. Use a blind rubric, source/record references, fixed prompt/model versions, duplicate ratings, and a human-reviewed calibration sample. The judge must not decide tool validity, correctness, feasibility, speedup, oracle regret, or whether the selected instruction is acceptable. If there is no configured judge model, report this component as not run. The current workspace has no live v2 model-comparison run, so no LLM-as-judge scores are claimed.

## Current evidence and limits

The bounded selector, recovery route, host fallback, target-roster checks, and SQLite export are software-tested. The five-mode retrieval replay has ten matched archived SHA256 controls per arm; every control matches, with zero LLM calls and zero native jobs. This is a deterministic noninterference result only. The additional `no_history` and `budget_matched_history` controls each replay ten trajectories / ten endpoints for one SHA256 seed/cap/budget prefix and exactly match the archived controls; they add no live LLM evidence. See the [context-control replay](../results/2026-10-28-memory-context-controls-r1/README.md).

One live Codex relay episode was evaluated on the complete twelve-candidate tiny-regex-c pool. The agent measured two candidates, then selected the correct, feasible pool oracle: **361,839 → 361,328 cycles**, **1.001414× speedup**, **+60 LUT4**, **68.880 MHz** minimum routed Fmax. It had zero regret at budget two, but merit, calibrated latency, pairwise XGBoost and factorized feasibility XGBoost also reached the same oracle at two measurements. This demonstrates the structured observe/decide/tool/verify loop operated on measured feedback; it does not show an LLM advantage. It is one related-domain workload and one relay episode. API/provider token and model-only latency were unavailable; the 72.717 seconds are target measurement time, not inference time. See the [sealed comparison](../results/2026-10-28-tiny-regex-c-selection-r2/README.md).

The bounded router and one-shot recovery are protocol-tested. The opt-in utility-override review is newly protocol-tested but has no live LLM comparison. The knowledge-graph mode has no live decision-quality comparison. The agent is not fine-tuned; it uses a configured pretrained LLM with prompts, structured function calls, verified host tools and optional approved historical context. There is no measured evidence that retrieval, routing, the LLM agent, or ML improves design quality over the strongest heuristic. Keep those as open research questions.

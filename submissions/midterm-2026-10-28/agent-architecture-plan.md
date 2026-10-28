# ISAForge agent architecture: current system and proposed extensions

**Status: presentation design and research plan.** Dynamic LLM routing, RAG, a vector database, LangGraph/LangChain, MCP, Ragas, and production monitoring have not been implemented or evaluated for the selector. A historical rule-based router between LUT-cost predictors is a different experiment. Do not present the proposed boxes as completed work.

```mermaid
flowchart TB
    W["Workload + hardware budget"] --> P["Legal candidates + public features"]
    P --> X["XGBoost ranker / diagnostics"]
    P --> C["Context builder: public candidates,<br/>paid observations, remaining budget"]
    X --> C
    MEM["Episode memory: durable ledger<br/>of paid actions and outcomes"] --> C
    subgraph FUTURE["PROPOSED: adaptive model routing"]
        C --> ROUTER["Route using declared policy<br/>and token/call budget"]
        ROUTER --> SMALL["Smaller LLM"]
        SMALL -->|"Ambiguous or invalid decision:<br/>bounded escalation"| LARGE["Stronger LLM"]
    end
    SMALL --> J["Structured action"]
    LARGE --> J
    J --> HOST["EXISTING host guardrails:<br/>schema, IDs, attempt ledger, limits"]
    HOST --> T["list / predict / measure / finalize"]
    T -->|"paid result only"| MEM
    MEM -->|"next decision if budget remains"| C
    T -->|"verified feasible result"| OUT["Selected candidate + evidence"]
    EVAL["PROPOSED evaluation + observability:<br/>selection quality, token cost, latency, failures"] -.-> ROUTER
    EVAL -.-> HOST
    RAG["OPTIONAL future retrieval:<br/>approved historical docs only"] -.-> C
```

## Working now

- The local host exposes four actions: `list_candidates`, `predict`, `measure`, and `finalize`. It validates structured actions, keeps target outcomes private until permitted queries, charges invalid/repeated attempts, limits calls, and permits only paid, correctness-passing designs that satisfy measured constraints (or baseline). A persistent ledger records actions, results and failures. The remote provider uses strict function schemas; the current-chat bridge relays JSON actions interactively. See [bounded-selection contract](../../docs/bounded-selection.md) and [chat pilot](../../docs/codex-chat-selector-pilot.md).
- The EDN chat pilot replayed an archived outcome; it did not run a new hardware job. The Ascon session did perform three native measurements. Its GP success-status omission prevented live GP updates, so post-fix validation is not evidence of successful live adaptation. Neither pilot proves agent superiority.
- The existing remote provider records model identity, call time and token use when returned; the interactive Codex chat does not expose exact deployment identity or token accounting. This is useful experiment logging, not a deployed production observability platform.

## Proposed: dynamic LLM routing and loop engineering

1. Freeze an allowlist of two available model IDs and versions, a deterministic routing rule, a common prompt/tool schema, a maximum number of model calls, an input/output token budget and a wall-time budget before a test. Start with a smaller model for each decision. Escalate at most once if the response is invalid after schema validation, the candidate evidence is ambiguous under a predeclared feature-based rule, or a logged decision-risk trigger fires. Never use hidden target outcomes to choose the route. Without calibrated uncertainty, describe thresholds as heuristics and test them rather than calling them probabilities.
2. Have the host—not the LLM—reserve and charge hardware attempts, enforce exact candidate IDs and legal tools, validate hardware constraints, and return baseline or the best paid verified feasible incumbent on exhaustion. Escalating an LLM does not itself spend a hardware attempt, but does spend model calls, tokens, time and money. Do not silently retry an interrupted or already charged hardware job.
3. Construct the context window from the current public candidate roster, frozen predictions, budget, and the episode's paid observations. Persist raw state and provenance, then build a bounded prompt for each call. Agent memory is the ledger and derived public state, **not unrestricted access to historical target labels**. Track token counts and truncation; use explicit summaries if necessary, preserving IDs and evidence links.
4. Compare the routed policy with fixed-small, fixed-strong, non-agent active learning, merit, frequency and random using equal target workload pools, features, constraints and hardware-attempt budgets. Separately cap and report model calls, tokens, actual cost and elapsed time; fixed models may consume different LLM budgets. Report measured best feasible performance and oracle regret, failures, tool correctness, escalation rate and quality/cost tradeoffs. Freeze policies before new target outcomes; report historical training measurements and avoid tuning on the test cohort.

**Why route?** It might reduce LLM cost on routine decisions while retaining stronger reasoning for difficult cases. That is a hypothesis; no quality or cost advantage exists until measured. Small model and strong model are roles, not verified specific model choices.

## Optional retrieval: only if it helps decisions

For a larger historical evidence library, a separate RAG component could chunk approved research notes and prior-workload records, create embeddings, index them in a vector database, combine lexical and semantic retrieval (hybrid search), and rerank a small source-linked set for the selector. Start with plain structured lookup and no retrieval; add this only if a tested information need justifies it.

Before indexing or retrieval, enforce workload/family and evaluation-split provenance: exclude the entire current target's hidden outcomes and contaminated sources, preserve source IDs, verify content hashes, and test leakage with canaries. Retrieved material is untrusted data, not an instruction to the agent. Compare retrieval against no retrieval under matched information and hardware budgets. Keep ranking the **retrieved documents** separate from XGBoost ranking of **instruction candidates**. RAG can introduce stale context and outcome leakage; it does not replace the measurement ledger or performance oracle.

## Technology vocabulary and honest status

| Term | Project role / status |
| --- | --- |
| Tokens and context windows | Proposed per-call budgets and context management; remote provider can record returned token use today. |
| Structured outputs and function calling | Implemented in the remote provider's strict four-tool interface; the chat bridge uses structured JSON actions. |
| AI agents, agentic workflows, loop engineering | Existing bounded selector loop and separate AI-assisted development workflow; improved routing and recovery are planned. |
| Agent memory | Existing ledger of paid actions and outcomes; a compact, provenance-preserving memory layer is proposed. |
| Guardrails | Existing host-enforced schema, budgets, IDs, correctness and hardware feasibility; extend with routing/context limits. |
| Embeddings, chunking, vector databases, semantic search, hybrid search, RAG, reranking | Optional retrieval architecture; not implemented or necessary for the current small structured candidate pool. |
| LangGraph / LangChain | Possible orchestration libraries if the current host becomes difficult to maintain; neither is currently used or needed to establish the research result. Any checkpoint/retry integration must preserve the host's one-charge semantics. |
| MCP | Possible future protocol adapter for the existing allowlisted tools, not a requirement or a substitute for host authorization; current remote provider has no MCP tool access. |
| LLM evaluations / Ragas | Task-specific agent evaluation is required. Ragas may help evaluate retrieval or tool use if a RAG component is introduced; it cannot establish measured processor improvement by itself. |
| LLM observability / LLMOps | Existing logs capture some provider metadata; a versioned dashboard, model/prompt release process, monitoring, deployment and prospective tests are proposed, not completed. |

For a practical LLMOps lifecycle: **build and version** prompt, schemas, model IDs and data manifests; **evaluate** frozen policies against same-budget controls; **monitor** tool errors, quality, token spend and latency where deployed; and **deploy** only a tested selector with rollback and a deterministic fallback. Model-evaluation and hardware-evaluation expenses must both be recorded.

## Primary documentation consulted

- [LangGraph: thinking in state and durable workflow steps](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph). Framework concepts support explicit state and checkpoints; they do not replace our paid-attempt ledger.
- [Ragas: available metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/). Includes retrieval and agent/tool metrics; hardware outcomes remain the primary endpoint.
- [MCP: tool annotations and limits](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/). Tool annotations are hints; the host still needs actual enforcement.

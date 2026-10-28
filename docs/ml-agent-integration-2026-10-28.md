# ISAForge ML and selection-agent integration — October 28, 2026

This is the evidence-backed status of the current ML-guided selector and the
bounded LLM selection loop. It distinguishes a working research prototype from
the complete, prospective optimization system in the project proposal.

## Research question and current answer

ISAForge asks whether a model-guided, uncertainty-aware selector can find a
better **verified, feasible whole-program design** with fewer expensive
PicoRV32 evaluations than frequency, merit/calibrated latency, random search,
and non-agent active selection. We do not yet have evidence that ML or an LLM
beats the strongest heuristic across workloads. The live agent results below
are consumed-data replays of the six-candidate Embench CRC32 pool; no new
hardware jobs or labels were produced.

## Implemented path

```mermaid
flowchart LR
  W[Supported RV32 workload + fixed inputs/oracle] --> E[Existing extraction, lowering, legality and correctness gates]
  E --> C[Public candidate roster + static and dynamic features]
  C --> P[Existing grouped XGBoost predictors]
  P --> S[Bounded agent loop]
  M[Approved historical measurements] --> R[Split-scoped local retrieval]
  R --> S
  S -->|list_candidates / predict / measure / finalize| H[Host-owned verifier and attempt ledger]
  H --> V[Measured cycles, correctness, area, routed timing]
  V --> O[Sealed JSON run evidence + SQLite observability]
  O --> T[Future eligible training data; workload/family holdout]
  T --> P
  L[Human review: workload, constraints, release and evaluation authorization] -.-> H
  Q[LLM provider; current evidence uses instruction-bounded Codex chat relay] --> S
  X[Responses API provider and one-step escalation policy] -. supported, not live-compared .-> S
```

The host owns candidate legality, test outcomes, correctness, area/timing
feasibility, charged attempts, and final accepted selection. The language model
receives a public snapshot and can propose the next bounded action; it cannot
declare an unmeasured candidate correct or feasible. The current agent supports
single-instruction selection only. It does not assume speedups or areas add
when combining instructions.

## What the model predicts

The current grouped adapter fits the **existing** XGBoost recipes from the
authenticated 122-label corpus. It is not a new model release and does not
train the LLM.

- `XGBRanker` with `rank:pairwise` produces a relative candidate-ordering
  score. The score is neither an absolute speedup nor a probability.
- The factorized feasibility selector combines an uncalibrated,
  probability-like feasibility score and ensemble disagreement with analytic
  cycle-reduction features. Its disagreement is not a calibrated uncertainty
  interval; its score is not a guaranteed probability.
- The host prediction tool also exposes the existing analytic latency estimate.
  In the measured corpus, every successful cycle-speedup label is explained by
  this calibrated-latency estimate. This is why another standalone speedup
  regressor is not currently justified.
- The fit excludes the full target workload and every expression family in its
  candidate roster. Target outcomes, including failures, remain evaluator-only
  until a candidate is measured or the replay is scored after the policy ends.

Current data before this turn: 122 verified speedup labels, 4 charged failed
attempts, and 14 workload groups. The measured labels are historical and the
active workload-eligibility census has not produced a new independent source
that passes the existing gates.

## Bounded agent, memory and AI engineering

| Component | Working now | Boundary / not yet demonstrated |
| --- | --- | --- |
| Agentic workflow and loop engineering | Persistent, bounded four-tool loop: `list_candidates`, `predict`, `measure`, `finalize`; explicit decision, provider, tool and hardware-attempt accounting; host fallback on model failure or exhaustion. | One live replay used a manual Codex chat relay. That relay was instruction-bounded, not sandboxed, and its exact deployment model ID is unavailable. |
| Function calling / structured output | Typed action protocol and host-side validation; invalid actions and finalization corrections are recorded. | The Codex bridge is not an isolated production tool runtime. No production service is deployed. |
| Model routing | Responses-provider wrapper supports one stronger-model escalation after invalid structured output or explicit host incumbent correction, within the shared provider-call budget. | No Responses API key was present and no routed API comparison ran. The Codex chat replay did not exercise dynamic provider routing. |
| Agent memory, embeddings and semantic/hybrid search | Per-run retrieval over eligible historical measurements: lexical TF-IDF, latent semantic TF-IDF/SVD vector representations, reciprocal-rank hybrid, and typed operator-overlap graph options. Each measurement is a provenance-bound record (the current chunk); hybrid supplies at most three, and raw history is hidden in retrieval mode. | No pretrained dense embeddings, arbitrary-document chunking, persistent vector database, or separate cross-encoder/LLM reranker. The hybrid rank fusion is the reranking step. No causal quality gain is established. |
| Context windows and tokens | Requests are byte-bounded; retrieved memory has a 40,000-byte ceiling. SQLite records serialized context size and history exposure. Only provider-reported token usage is recorded. | A byte count is not a token count. Codex relay token usage is null; do not estimate it from text length. |
| Knowledge graph | Typed operator-overlap graph can retrieve structurally related prior measurements. | It is a retrieval prototype, not a trained performance graph or proof of semantic relevance. |
| Explainability | Final LLM summary is bound to the exact public-context hash, tool trace, policy identity, and separate host-verified facts. | The summary is model-authored and explicitly unverified; it is an explanation artifact, not proof of why the model acted. |
| Evals and guardrails | Deterministic unit tests, sealed retrospective replay, hidden-outcome host boundary, full-pool oracle scoring only after completion, and failure-preserving ledgers. | No LLM-as-a-judge or Ragas evaluation is used. A judge would not replace tool correctness or measured processor outcomes. |
| LLMOps / observability | Source/protocol hashes, JSON event ledgers, and SQLite tables for episodes, decisions, model calls, tools, retrievals, context windows, rationales and verified evidence. | Local research observability only; no deployed monitoring, model release service, or automated production alerting. |
| Agent memory persistence | The retriever rebuilds from the approved split-scoped training rows for each episode; its source hashes and returned record IDs are logged. | It is not a durable conversational memory store. It cannot retrieve target labels or arbitrary files. |
| Human-in-the-loop | Human approval points for workload/constraint/release decisions; the relay operator copied requests and actions for the Codex pilot. | Human review is not yet an interactive runtime approval product. |
| Frameworks and deployment | Existing Python host controller is the orchestration layer. | LangChain, LangGraph, MCP, cloud deployment and general-document RAG are deferred; no demonstrated need or measured benefit. |

The retrieved-only memory change reduced the serialized initial request from
154,008 bytes with 101 raw historical rows to 17,353 bytes with three retrieved
rows and 5,103 bytes of retrieved payload (about 88.7% fewer serialized
bytes). This is context-size evidence only: it does not establish token savings,
lower latency, improved decisions, or a causal retrieval benefit.

## CRC32 selection replay and matched controls

Both runs used the same frozen +64 LUT4 and 12 MHz constraints, seed 0,
three-measurement maximum, target-family/workload-excluded model fit, six public
candidates, and complete measured-pool oracle. They replay previously measured
outcomes; `new_native_jobs=0`.

The best candidate was
`slli(andi(xor(in0,in1),255),2)`: baseline 32,387,382 cycles, candidate
30,820,662 cycles, speedup **1.050833x** (4.8374% cycle reduction), +31 LUT4,
minimum routed Fmax 71.489845 MHz, correctness passed, and archived native
evaluation duration 42.0438 seconds. It is feasible under both constraints.
The complete six-candidate cycle, area, route, and correctness table remains in
the [automatic CRC32 result archive](../results/2026-10-20-automatic-crc32/README.md).

| Selector | Charged measurements to best verified feasible result | Best speedup | Regret to complete six-candidate oracle |
| --- | ---: | ---: | ---: |
| GPT-6.1 Sol chat relay, no retrieval | 2 | 1.050833x | 0 |
| GPT-6.1 Sol chat relay, hybrid retrieved memory | 1 | 1.050833x | 0 |
| Factorized-feasibility XGBoost, retrospective matched control | 1 | 1.050833x | 0 |
| Pairwise XGBoost, retrospective matched control | 2 | 1.050833x | 0 |
| Merit / calibrated latency / latency-cost / random, matched controls | 2 | 1.050833x | 0 |
| Frequency, matched control | 3 | 1.050833x | 0 |

These rows come from the current October 26 feasibility-screen seed-0
trajectories used by the grouped-agent replay. They are not a replacement for
the earlier five-seed CRC32 study: that separate development report records
merit finding the oracle at budget one and documents its own model/policy
protocol. Keep the two results distinct; both show no learned advantage over
merit. See [the original selection-pilot report](selection-pilot-results.md).

These are one seed and one already-consumed workload. The no-retrieval chat
pilot had two invalid candidate-ID actions caused by manual request/response
transcription; those actions were rejected without hardware charge. It then
measured one infeasible candidate (+69 LUT4; timing passed) and the best
feasible candidate. The retrieval run measured only the best feasible
candidate. Pilot relay elapsed time includes human waiting and copying, not
model inference latency; provider calls, exact model identity, and token usage
are unavailable. The two runs differ in information framing and relay history,
so they do **not** isolate retrieval causally. Both tie the best current
non-agent policy at its best budget; hybrid ties factorized XGBoost and does
not beat it.

Artifacts:

- `results/2026-10-28-grouped-agent-crc32-gpt61sol-seed0-pilot2/`
- `results/2026-10-28-grouped-agent-crc32-hybrid-seed0/`
- `results/2026-10-28-grouped-agent-observability-r1/`
- `results/2026-10-28-grouped-agent-crc32-gpt61sol-seed0/` preserves the initial
  no-TTY EOF/host-fallback start (zero paid attempts); it is not a model result.

## Dataset supplement and ablation

The sealed Ascon import authenticates three previously measured outcomes but
keeps them in a separate `training_only` release. The original corpus remains
122 labels; the other nine public candidate IDs remain unmeasured. These three
rows are same-domain crypto transfer and all three formula families already
exist in history, so they add no independent family/workload confirmation.

An outcome-hidden, whole-workload/family-held-out ablation adds those three
rows only to the eligible training fold for the two existing XGBoost recipes.
It adds no model family, label, or native run. Across 13 complete-oracle
contexts: pairwise ranking has one workload loss at B1 (macro regret
0.00841660 to 0.00900788), ties at B2, and one workload win at B3 (0.00070245
to 0.00014510). Factorized-feasibility regret is unchanged at B1/B2/B3
(0.00729212 / 0.00534721 / 0.00527538). **No model was promoted.**
The detailed sealed results are in
`results/2026-10-28-ascon-training-ablation-r2/`.

## Reproduction and current checks

List the authenticated grouped targets:

```sh
../work/audit-venv/bin/python scripts/run_grouped_agent_selector.py --list-targets
```

Run a new Codex-chat replay into a new output directory (the chat provider
requires manual relaying of each JSON request; it is not an API benchmark):

```sh
../work/audit-venv/bin/python scripts/run_grouped_agent_selector.py \
  --provider codex-chat --target-group embench-crc32 \
  --benchmark embench-crc32:63c7f40f7e906b046f5a1911d5ed91824bb1aa15673f8fa753a818ccc0d5f511 \
  --memory-mode hybrid --seed 0 --budget 3 --area-cap 64 \
  --output results/grouped-agent-crc32-reproduction
```

The historical results are immutable; do not reuse their output paths.
The focused relevant suite previously passed **104 tests**. No new live model
API call, model fine-tuning, native job, or speedup label was made in this
integration. The Ascon retrospective does perform local fits of the existing
models and is fully reported above.

## Next research gate

Do not call this a finished optimization system or claim a research win. The
next valid improvement needs an untouched eligible workload and a frozen
prospective protocol before outcomes: same public features/history, model and
agent information, area/timing limits, measurement budget and total cost for
frequency, merit/calibrated latency, random, active learning, XGBoost and the
LLM selector. Repeat the agent comparison across independent workloads and
seeds; record structured-action validity, measurements, wall time, model
latency/tokens/cost when actually available, verified feasible best-so-far,
and oracle regret only for complete pools. Then test selected instruction
combinations together in the processor. Preserve negative results.

# tiny-regex-c selector study contract

## Release amendment r5: preserve and recover a pre-agent relay startup failure

The r3 release was opened from its pushed zero-label commit, but the local
process was started without an interactive input stream. The JSON bridge wrote
one public request and then received end-of-file before any model response.
The host recorded `host_fallback`, zero selector tool calls, zero target
measurements, zero target labels, and zero successful provider calls. Its full
trace is preserved in `results/2026-10-28-tiny-regex-c-selector-launch-failure-r1/`.

This is a harness startup failure, not an LLM decision or candidate-selection
trial. No target outcomes were acquired or exposed, and no candidate identity
was measured. This r5 amendment binds a fresh r2 study path and a corrected
interactive launch. It keeps the same workload, candidate roster, historical
training rows, model recipes, exclusions, budgets, tools, policies and metrics.
The r3 release and failure remain immutable. If the r2 interactive bridge fails
before a model response, stop and report it; do not retry, change the models,
or inspect any target outcomes.

## Question and scope

This study asks whether ISAForge's existing XGBoost ranking and factorized
feasibility selectors, the existing cost-aware active policy, or one bounded
LLM selector can find a verified feasible custom instruction with fewer
candidate evaluations than frequency, merit, calibrated-latency, latency/cost,
and random policies on the pinned 76-case tiny-regex-c workload.

This is a **related-domain regex/text transfer pilot**, not an independent
workload-family confirmation. The 12-candidate pool contains 11 exact
operation-tree families; three are represented in the historical corpus. The
training cohort excludes every target family and contains 106 successful
historical measurements across 14 workload groups. Six SLRE labels remain in
the training history, so the workload lineage remains related. Historical
failures remain charged and excluded from numeric model labels.

The target features and model predictions are frozen before candidate labels.
No target candidate measurements are permitted until the zero-label package
and source bindings are committed and pushed to `ai-guided-ml`.

## Frozen predictors and baselines

Use the existing recipes without tuning or creating a new model version:

- Pairwise XGBoost ranking and factorized feasibility/analytic-benefit
  XGBoost, with the repository's five fixed seeds.
- The existing raw and normalized speedup regressors as challengers.
- The existing hybrid Gaussian-process zero-shot and paid-update policy.
- Frequency, merit, calibrated analytic latency, latency/cost, and seeded
  random controls.
- The current Codex chat model through the four-action JSON bridge, with the
  seed-zero rank/feasibility predictions and hybrid historical memory.

Predicted rankings, probability-like feasibility scores, ensemble spread, and
GP uncertainty are not called calibrated confidence. The model receives only
the 106 family-excluded historical rows, public candidate features, and its
own paid observations. The knowledge graph and semantic/lexical retrieval use
that same approved historical split.

## Measurement sequence and budgets

1. Run one current-Codex chat-relay episode first. The host exposes list,
   predict, measure, and finalize actions. Each measure action is identity-
   checked and charged before dispatch; only that candidate's verified result
   returns to the agent. Limit the episode to three measurements.
2. After the agent finalizes, measure each remaining candidate once to build
   the complete 12-candidate reference pool. This corpus-building experiment
   physically evaluates up to twelve candidates; it must be reported as such.
3. Replay each frozen non-agent policy from an outcome callback that releases
   only the candidate it selected. Report B1, B2, and B3 prefixes under the
   same public information and +64 LUT4 / 12 MHz primary constraint. The
   offline prefixes do not erase the actual full-pool collection cost. Report
   the live agent's best-so-far trajectory at each budget alongside them.
4. Use the exhaustive feasible optimum only after policy decisions are
   complete. The oracle is complete when all twelve attempts are terminal and
   no outcome is unknown or infrastructure-censored. A measured correctness,
   execution, or memory-contract failure is conclusively infeasible and is
   retained as a charged failed attempt; it is not a numeric performance
   label. If any attempt is unresolved/censored, oracle speedup and regret are
   null; best-verified results and regret lower bounds remain descriptive only.

No individual speedups or area increments are added to estimate combined
instruction sets. This study selects single instructions only.

## Required outcomes and costs

For every candidate, preserve correctness, whole-program cycles and
instructions, speedup, added LUT4, three routed timing seeds and minimum
Fmax, device-fit status, charged attempt status, attempt wall time, and raw
native evidence. Report the baseline alongside candidates. The primary curve
is best verified feasible whole-program speedup and cycle reduction versus
budget. Compare agent and non-agent regret in cycle-reduction units
`(1 - 1/speedup)`, with speedup-ratio gaps labeled separately. Report regret
only against a complete measured-pool oracle.

Keep historical training time, qualification, baseline setup, calibration,
individual model fit/prediction, package-build, agent decision/tool/provider
calls, target measurement time, native command time, and full-pool oracle
collection cost in separate timer scopes. Native command, wrapper and overall
agent timers overlap and must not be added.

## Agent and AI-engineering limitations

The selection loop uses structured JSON function calls for `list_candidates`,
`predict`, `measure`, and `finalize`. The deterministic host validates action
schemas, candidate identity, charge limits, correctness, hardware constraints,
and incumbent final selection. The agent records its pre-measure decision
context and a post-measure host verification; its free-text rationale remains
unverified.

Historical memory uses one measured record per chunk. Hybrid retrieval combines
TF-IDF lexical similarity with TF-IDF/truncated-SVD latent-semantic similarity
through reciprocal-rank fusion. The memory package also constructs and hashes a
typed operator/family/workload/measurement graph with a separate graph-query
mode, but this episode does not query that mode. Hybrid retrieval is logged,
source-hashed, and limited to 40,000 bytes. This run has no pretrained neural
embedding service or external vector database.

The SQLite observability database is a verified, read-only projection of sealed
JSON requests, decisions, tool calls, retrieval traces, rationale links, and
host outcomes. The JSON ledger remains authoritative. This is a bounded agent
loop with deterministic evaluation hooks and memory provenance; it does not
implement LangChain, LangGraph, Ragas, or an LLM-as-judge evaluation.

The Codex bridge is human-relayed. The active chat model still has broader
workspace tools available, so this is cooperative context discipline rather
than a security sandbox. There is no configured Responses API key; this run
uses one current Codex model and does not implement cross-provider dynamic
model routing. It cannot claim provider token counts, exact model ID, or
model-only latency. One LLM episode is an engineering demonstration, not a
statistical agent-quality estimate.

## Reproduction commands

Use the pinned environment and keep the release order:

```sh
../work/audit-venv/bin/python scripts/prepare_tiny_regex_selector.py freeze
../work/audit-venv/bin/python scripts/prepare_tiny_regex_selector.py verify
# Commit and push the complete zero-label package and code on ai-guided-ml.
../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py release
../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py agent
../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py collect
../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py evaluate
../work/audit-venv/bin/python scripts/execute_tiny_regex_selector.py verify
```

Do not run `release`, `agent`, or `collect` before the exact release commit is
present both locally and on the remote branch. Preserve every failed or
interrupted measurement. Do not rerun charged candidates within the same
context.

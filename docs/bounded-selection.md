# Working selection interface and shareable demo

ISAForge has a four-tool selection host, an isolated remote-model provider, an
interactive bridge for the active Codex chat model, and an offline showcase of
the current six-workload evidence. Frozen models remain unchanged. One consumed-
data in-chat selector pilot is complete; a repeatable, blinded live-model
comparison and final joint-instruction stage remain missing.

## Try the project

Use Python 3.12 and the pinned replay packages. The demo and deterministic
controls need neither native hardware tools nor an API key:

```sh
python -m pip install -r requirements-speedup.txt
make showcase PYTHON=python
# Open generated/reproduction/selection-showcase/index.html.
make selector-controls PYTHON=python
```

Both targets require a fresh output directory. For later runs, set
`SHOWCASE_OUTPUT=generated/my-new-demo` or
`SELECTOR_OUTPUT=generated/my-new-controls`. The standalone HTML page has
interactive workload, area-cap and measurement-budget controls, candidate
tables, CSV exports, SQLite, SQL examples and provenance. Copy the generated
directory to share it; the page makes no external network requests.

The six-workload corpus contains 33 verified labels and three retained failures,
39 fully measured processor designs and 117 routing results. The 1,350 comparison
endpoints are dependent policy/seed/cap/budget replays, not additional hardware
evaluations or independent generalization tests. UD's unresolved infrastructure
failure means its reference is best verified, not a complete full-pool oracle.

## Host contract

`ReplaySelectionSession` owns the private evaluator and persistent attempt
ledger. `MatchedBaselinePolicy` uses the same serialized interface as the remote
provider and is explicitly a deterministic control, not an LLM.

| Tool | Host behavior |
| --- | --- |
| `list_candidates` | Returns approved public formulas and features. |
| `predict` | Returns frozen XGBoost/ranking predictions, GP acquisition, heuristic estimates and uncalibrated-uncertainty flags. Only paid successes update the GP. |
| `measure` | Persists a charge before validation/lookup. Invalid IDs, repeats and failures consume budget. Repeats never invoke the evaluator again. |
| `finalize` | Accepts baseline or one paid, correct, device-fitting improving candidate satisfying area and routed-clock limits. |

Tool calls and model calls have separate finite limits. Errors/interruption retain
charged or pending evidence; existing ledgers cannot silently restart. Limit/error
fallback is the best paid verified feasible improvement, otherwise baseline.
Final choice and best verified performance found are separate fields.

All trajectories, including zero-query failures and early stops, contribute to
every allocated-budget frontier. Carried-forward incumbents retain actual attempt
counts and costs, without inventing measurements. This prevents survivor bias.

The remote provider sends fresh public JSON to the Responses API with exactly
four strict functions. It attaches no shell, filesystem, MCP, web/retrieval,
private report, oracle or conversation continuation. Public observations remove
raw exceptions and paths. Credentials come only from `OPENAI_API_KEY`, never
saved Codex credentials. Python callbacks remain trusted local code, not an OS
sandbox; isolation applies to the remote model's JSON/function boundary.

The provider follows the official [function-calling interface](https://developers.openai.com/api/docs/guides/function-calling):
strict object schemas and one function action per request. It requests a short
decision summary, not private reasoning. Model, prompt, tools, sources, inputs,
token usage and call time are recorded, with no implicit retries. Current limits
are 12 requests and 512 output tokens per request per episode. HTTP timeout bounds
network operations, not absolute process wall time. Monetary cost is not guessed
from token usage.

## Live command and blocker

No live LLM trial was run: `OPENAI_API_KEY` is not configured. The 21 provider
tests use mocked HTTP envelopes to verify protocol handling, not model quality.
With a key in the process environment, specify an API model actually available to
the account and run the five frozen seed trajectories on one consumed target/cap:

```sh
python scripts/run_bounded_selector.py --provider responses \
  --model "$ISAFORGE_SELECTOR_MODEL" --target sha256 --cap 64 \
  --output generated/bounded-agent-development
```

`ISAFORGE_SELECTOR_MODEL` must contain an explicit available API model ID; no alias
or availability is assumed. The command refuses to create a run or call a model
when the key/model is missing. Never commit a key. These episodes query archived
outcomes rather than fresh synthesis jobs.

### Use the active Codex chat model

When an API key is unavailable, `scripts/run_codex_chat_selector.py` opens an
interactive JSON bridge. The local evaluator presents one allowlisted public
request per turn; the active chat model returns one `list_candidates`, `predict`,
`measure`, or `finalize` action. The host still owns the ledger, charges invalid
measurement requests, validates measured outcomes, and selects only a paid
feasible result. The bridge does not call a model API or make the active chat a
restricted sandbox; the chat session itself can have broader tools and context.

```sh
python scripts/run_codex_chat_selector.py --target edn --cap 64 --seed 0 \
  --budget 3 --output results/my-codex-chat-selector-run
```

The command waits for the operator to relay one JSON action from the active chat
at each prompt. Use a fresh output path. It is a development integration path,
not a hands-off model service. Because invalid IDs consume budget, the bridge
now explicitly instructs the model to copy the complete candidate ID without
shortening it; a focused test protects that reminder.

The October 27 EDN pilot is documented in
[`codex-chat-selector-pilot.md`](codex-chat-selector-pilot.md). The current chat
model queried the six-candidate pool, then selected the best measured candidate:
386,561,849 → 386,394,809 cycles (1.000432×), +32 LUT4, 71.119 MHz minimum
routed Fmax, correctness passed. This matched the measured-pool oracle. One
malformed shortened candidate ID consumed an additional attempt; the pilot
therefore used two charged attempts for one valid measurement. At the same two-
attempt endpoint, frequency, merit, raw XGBoost regression, XGBoost ranking and
the GP control also reach the oracle; the LLM does not beat them. This was a
consumed-data replay, not a new hardware evaluation, blinded test, API call, or
model-quality estimate. Model ID, token usage, and model-only latency are
unavailable. Dynamic model routing remains unimplemented.

## Verified outcome and next work

All ten policies run through the interface on EDN, UD and SHA256: **450
trajectories / 1,350 endpoints exactly reproduce original choices, feasible
speedups and charged durations**. Deterministic control replay establishes no LLM
advantage. Historical costs include failed/excluded attempts: SHA has 27 available
successes plus three failures costing 1,698.152954 recorded seconds, with 21
fitting rows after family exclusions. Setup, calibration, overlapping command
time, actual replay/inference time and archived measurement durations stay separate.

The [one structure-feature ablation](../results/2026-10-21-structure-feasibility-development/README.md)
failed: SHA adaptive GP's +64 optimum moves from query two to query three. The
existing model remains unchanged. Do not launch another sweep to chase this
case. The cost heuristic finds SHA's optimum in one query, leaving no query-count
headroom for an agent there.

Next: run a controlled live-model development comparison using equal charged
attempts, then freeze a justified protocol before fresh source/input evidence.
Native guarded dispatch and jointly verified final instruction sets remain
necessary for the complete optimizer. This milestone adds no labels, formal
calibration, broad generalization or learned/agent superiority claim.

## October 28 bounded routing extension

The remote replay CLI now supports `--escalation-model` and `--max-model-calls`. See [the implementation and evaluation plan](agent-routing-implementation.md). This is schema-recovery routing with offline tests, not uncertainty-based routing or evidence of an LLM advantage.

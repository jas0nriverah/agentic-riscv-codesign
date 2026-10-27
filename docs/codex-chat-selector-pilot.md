# Active Codex chat selector pilot — October 27, 2026

## What was tested

The current Codex chat model acted as the policy in ISAForge's four-tool
selection loop for the six-candidate Embench EDN pool. The host exposed public
candidate features, frozen prediction outputs, 15 historical fitting rows,
constraints of +64 LUT4 and a 12 MHz timing floor, and an allowance of three
measurement attempts. Target outcomes remained inside the host until a paid
measurement request.

The model requested predictions, measured candidate
`00fa9abbfa0f8ae7ccbf7ddd0de60d3e769a7902cbc8f41f272ab57cdeb00fd8`, and
finalized it after the host returned its measured outcome:

| Result | Value |
| --- | ---: |
| Formula | `srai(slli(add(in0,in1),16),16)` |
| Baseline → candidate cycles | 386,561,849 → 386,394,809 |
| Whole-program speedup | 1.0004323× |
| LUT4 area increase | +32 |
| Minimum routed Fmax | 71.1187 MHz |
| Correctness / device fit / area / timing | pass / pass / pass / pass |
| Charged measurement attempts | 2 (one valid, one invalid) |
| Valid paid measurements | 1 |
| Native hardware jobs | 0; archived outcome replay |

The selected result matches the measured-pool oracle, with zero regret on this
consumed pool. At the same **two charged attempts**, archived controls for this
seed and cap reach 1.0004323× for frequency, merit, raw XGBoost regression,
pairwise ranking, and the Gaussian-process adaptive control. The timing-aware
cost heuristic reaches 1.0003566×, while random remains at baseline. The LLM
therefore did not beat the simple heuristics or learned controls in this
episode. The oracle is a retrospective reference only and was not shown to the
chat model.

## Agent loop and boundaries

The chat model consumed the public request and returned one JSON action at a
time: `predict`, `measure`, then `finalize`. The local host charged and executed
the actions, preserved a sealed ledger, withheld unmeasured outcomes, checked
correctness and hardware constraints, and enforced the final-choice rule. The
session made no API request. It used the LLM available in this Codex
conversation; exact model deployment ID, token use, and model-only latency are
not exposed by the chat interface.

The active chat session had wider prior context and workspace tools than the
serialized four-tool exchange. This is not a sandboxed model-quality trial or a
blinded benchmark. The bridge is interactive: an operator relays one JSON
action per prompt. Dynamic model routing and cost-tiered LLM switching were not
implemented or tested. Multi-instruction sets, fresh hardware jobs, uncertainty
calibration, and generalization to unseen workloads were not tested.

One action used a shortened candidate ID. The host rejected and charged it, as
specified by the attempt contract. This is preserved as an agent/tool-use
error; it reduced the pilot's available budget. The following exact-ID
`finalize` chose the verified incumbent. Do not remove this error from counts or
present the run as a clean three-measurement result. After this run, the bridge
prompt was updated to explicitly require complete candidate IDs, and a focused
test was added for that reminder. The sealed pilot itself remains unchanged.

## Reproduction and artifacts

The sealed protocol, action ledger, report, and manifest are in
[`../results/2026-10-27-codex-chat-agent-edn-b64-s0/`](../results/2026-10-27-codex-chat-agent-edn-b64-s0/).
The main report binds the exact actions, selected outcome, matched controls,
and oracle after selection. A supplemental
[`same-charge comparison`](../results/2026-10-27-codex-chat-agent-edn-b64-s0-control-comparison/comparisons.csv)
aligns all archived controls to the chat model's actual two charged attempts.
The main report records two charged attempts, four tool calls,
four model turns, zero native jobs, and the limitations above.

Start a distinct interactive development run using a fresh output directory:

```sh
python scripts/run_codex_chat_selector.py --target edn --cap 64 --seed 0 \
  --budget 3 --output results/my-codex-chat-selector-run
```

This command does not invoke a model API. At each prompt, the active chat model
must return exactly one JSON line with one of the four allowed actions.

## Next experiment

Run multiple frozen seeds and at least one fresh workload with the same candidate
pool, visible information, charged-attempt budget, area/timing constraints, and
evaluation-time accounting for the chat model, frequency, merit, random,
non-agent active learning, and pairwise XGBoost. Keep oracle labels hidden until
the policy pays to measure them. Count invalid calls and operator relay time.
Only then can the project estimate whether the LLM agent adds value beyond the
existing selection methods.

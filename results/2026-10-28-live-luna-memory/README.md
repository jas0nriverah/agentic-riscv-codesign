# Live GPT-6 Luna memory pilot

**Actual LLM decisions, archived hardware measurements.** Two fresh subagents configured as `gpt-6-luna`, medium effort, no inherited parent context. Frozen code/protocol commit: `46957811`. Target: consumed SHA256, seed 0, +64 LUT4, 12 MHz, allowance of three charged measurements and ten decision turns. All results, including rejected actions, are preserved.

| Policy | Queries to oracle | LLM decision turns | Rejected finalizations | Final speedup | Archived measurement seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Live Luna, no retrieval | 3 | 9 | 3 | 1.0213847x | 200.5520 |
| Live Luna, hybrid memory | 2 | 4 | 0 | 1.0213847x | 134.5180 |
| Frequency / latency-cost heuristic | 1 | 0 | 0 | 1.0213847x | See archived control curves |
| Random / adaptive GP (seed 0) | 2 | 0 | 0 | 1.0213847x | See archived control curves |
| Merit / XGBoost ranking | 3 | 0 | 0 | 1.0213847x | See archived control curves |

Both live agents selected `add(in0,slli(in1,21))`, with correctness passed:
26,135,630 baseline cycles to 25,588,430 candidate cycles, 547,200 cycles saved
(2.09369% cycle reduction), +50 LUT4, minimum routed 65.99353 MHz.

Hybrid stopped voluntarily after two measurements. At the shared B3 allowance its
incumbent carries forward; no fictitious third measurement is charged. The
no-retrieval agent's faster first choice exceeded the +64-LUT4 cap. Host rejection
prevented its three erroneous finalization requests from accepting that design.

## Evidence

- `PROTOCOL.md`: frozen conditions and restrictions.
- `none/` and `hybrid/`: sealed protocols, exact public requests, ledgers, reports and manifests.
- `comparison.json`: derived B1/B2/B3 curves plus every archived same-seed control.
- `none.sqlite`, `hybrid.sqlite`: derived, locally inspectable decision/tool/retrieval traces.
- `pilot-performance.png`: curve of best verified feasible cycle reduction versus allowed queries.

The root relayed each raw action unchanged. Agents were instructed to read only
assigned public request files. This was cooperative isolation, not enforced
sandboxing or an independently audited access boundary. The generic chat-bridge
report describes broader tools/context as a limitation; specifically these agents
were forked with no inherited context, while the root retained project context.
No oracle or other arm's choices were sent to a selector. Each host computed its
private report upon completion, and cross-arm scoring occurred after both ended.

One episode per arm is illustrative, not statistical or causal evidence that
memory helps. Historical costs and stored measurement times are not newly incurred
hardware wall time. Exact deployed model version, token usage, dollar cost and
model-only latency are unavailable. Both roles used the same configured model;
no live dynamic-model-routing advantage is claimed. No new native jobs occurred.
Frequency and the latency/cost heuristic remain better on queries to the oracle.

`relayed-actions.json` preserves an orchestrator copy of the exact structured
assistant replies from the collaboration conversation, bound to each public
request hash. It preserves incorrect claims in rejected finalization summaries
as model outputs, not endorsed scientific results.

Rebuild the plot with:

```sh
../work/audit-venv/bin/python scripts/plot_live_luna_pilot.py \
  --output generated/live-luna-figures
```

Final focused validation: 84 tests pass, including export of the preserved live
hybrid episode with four model turns/four retrievals and unavailable token counts
retained as SQL NULL. The slide deck remains eleven slides and 420 scheduled seconds.

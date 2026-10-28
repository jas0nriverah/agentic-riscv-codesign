# Selector v2 incumbent and matched-control replay

This archive evaluates the host-side selector v2 contract against consumed SHA-256 hardware outcomes. It verifies protocol behavior and control reproducibility; it is not a fresh workload, model fit, or live-LLM comparison.

## Changes under evaluation

- The public request names the one host-computed best paid, correct, area- and timing-feasible measured candidate that may be finalized.
- A finalize request for a stale, infeasible, inferior candidate, or baseline while an improvement exists returns the current required candidate ID and keeps the session open.
- The final response carries a host-computed sanitized measurement. The model's own text is retained as `agent_summary`, explicitly separate from `authoritative_selection`.
- The tool allowlist and hardware-attempt accounting are unchanged. Invalid finalize calls do not charge hardware; invalid measurement calls still do.

## Reproduction and result

```sh
../work/audit-venv/bin/python scripts/run_bounded_selector.py \
  --provider controls --target sha256 --seed 0 --cap 64 --budget 3 \
  --output results/2026-10-28-incumbent-v2-control-replay-r2

../work/audit-venv/bin/python -m pytest \
  tests/test_bounded_selector.py tests/test_selection_provider.py \
  tests/test_routed_selection.py tests/test_run_bounded_selector.py \
  tests/test_codex_chat_selector.py -q
```

The sealed report contains **10 policy trajectories / 30 budget endpoints**. Every deterministic control reproduces its archived attempted IDs, best-found speedup, and replayed measurement cost exactly. It made **zero LLM calls and zero native hardware jobs**. The focused test suite passes **79 tests**.

On this consumed SHA-256 pool, the best verified design is `add(in0,slli(in1,21))`: **1.0213847×**, 547,200 cycles saved from 26,135,630, with **+50 LUT4** and **65.9935 MHz** minimum routed Fmax. Frequency and latency/cost reach it in one measurement; merit and XGBoost ranking need three in the archived replay. The raw regression ends at **1.0052618×** after three measurements. These are dependent retrospective controls, not unseen-workload evidence. Selector v2 does not change these performance outcomes.

## Historical failure audit

The four rows in [`failed_attempts.csv`](../../submissions/midterm-2026-10-28/dataset/failed_attempts.csv) remain charged attempts and are not rewritten:

| Workload / candidate | What the preserved evidence shows | Treatment |
| --- | --- | --- |
| Embench `edn`, `addi(lui(4096),1860)` | Simulator exited 10. The archived report records two RAM/stack-contract violations; the first is a write from PC 2688 to address 5956. | Candidate correctness/contract failure; retain as no label. Do not retry the historical candidate. |
| Embench `ud`, `addi(lui(4096),1216)` | Target report completed but its upstream self-check output word is zero; fault and trap flags are clear. | Candidate correctness failure; retain as no label. Do not convert its timing counters into a speedup label. |
| Embench `ud`, `addi(lui(4096),1376)` | Evaluation stopped with `Less than 2 GiB free`, before correctness or performance evidence. | Infrastructure-censored attempt. A new campaign should verify storage headroom before reserving a measurement slot and avoid concurrent build growth. |
| TACLeBench G.723, `add(srai(in0,1),in0)` | nextpnr route seed 3 exceeded its 180-second timeout. Seeds 1 and 2 completed at 73.50 and 66.89 MHz; route 3 has no completed result. | Right-censored hardware evaluation, not a correctness failure. A future protocol may use a predeclared larger timeout; this historical slot stays censored and is not retried. |

Only the first two are recorded candidate correctness/contract failures. The latter two are incomplete infrastructure/measurement outcomes; both consume the historical budget, but neither provides an outcome label. This distinction should appear in any paper or presentation count.

No new area model or speedup fit was justified by this replay. Existing evidence still shows the calibrated latency merit is the strongest selection signal on this pool; measured speedup labels in the current corpus match that latency estimate. Generalization and prospective ML/agent superiority remain unestablished.

## Why additional workload attempts have not yielded labels

The project has more source screening than successfully qualified workload groups. The unchanged frozen pool and opportunity gates stop a workload before candidate measurements when it cannot supply enough distinct legal candidates: countnegative yielded four relocation-safe candidates of twelve required; the pinned stringsearch source yielded two; Fannkuch-redux yielded two; `strstr` yielded none. `complex_updates` exceeded the fixed 6,400-byte program/data partition. These are preserved qualification rejections, not hidden measurements or labels. Lowering gates would make the dataset larger while weakening the prospective comparison. The next blocker is finding an independent source that passes legality, pool-size, opportunity, memory, and toolchain preflight together.

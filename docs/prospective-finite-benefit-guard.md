# Prospective finite-selection benefit guard

`isaforge.guarded_finite_selection.search` is an opt-in adapter around the frozen
finite selector. It adds no model, fit, hardware authorization or campaign
integration. A new preregistration and release must bind this adapter and its
`source_bindings()` before any prospective target outcomes. Existing G.723,
Lift and development campaigns retain their original adapters and exact replay.

The adapter records acquisition proofs before provider calls, charges each
dispatch before invoking the provider, and preserves every returned paid outcome
unchanged. For a verified successful outcome it compares measured saved cycles
(`baseline_cycles - candidate_cycles`) exactly with public calibrated
`estimated_saved_cycles`. Any difference latches the first violation. The next
acquisition callback records that dispatch is blocked and stops before another
provider call. A violation on the last query still produces a stopped receipt.
Unknown failed attempts retain their costs and never acquire invented residual,
performance or feasibility labels.

The separate `assumption_violation_stopped` receipt contains the actual charged
IDs/count, original paid outcomes and hashes, measured durations, measured
feasible incumbent (or baseline fallback), exact residual and append-only event
journal. It sets `reference_complete=false`, `oracle=null`, `regret=null` and
`endpoints=[]`; it does not synthesize unspent-budget rows. Completed runs return
the full original search under `completed_search`, while stopped runs leave it
null. No receipt establishes a complete-pool oracle or comparative model gain.

An optional `on_event` receiver gets independent copies in sequence. It must
persist each entry before returning when durable evidence is required; the
in-memory journal alone is not crash-durable. Receiver, provider and validation
errors propagate and must be preserved by the owning prospective controller.
The adapter is a cooperative Python boundary, not a sandbox or a replacement
for release gates, native attempt ledgers, source/family exclusions or raw audits.

Existing complete-horizon campaign reports reject shortened trajectories. Do not
pass stopped receipts to those reports or relabel the successful paid outcome as
an infrastructure failure. A calibration stop qualifies the trajectory; the
measured label remains the original verified result. No native run or new label
is authorized by adding or testing this module.

Synthetic software validation:

```sh
../work/audit-venv/bin/python -m pytest -q tests/test_guarded_finite_selection.py
```

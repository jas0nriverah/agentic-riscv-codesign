# Ascon selector preregistration v2 — superseded

**Historical zero-label intermediate.** V2 authenticated but did not bind the
script that generated the package. The current, source-closed version is
[`Ascon selector preregistration v3`](ascon-selector-prereg-v3.md). Preserve
this package and its v4 release; neither authorizes dispatch.

This is a new, source-bound prelabel package for the bounded Ascon transfer
experiment. The earlier package remains at
[`results/2026-10-27-ascon-selector-prereg/`](../results/2026-10-27-ascon-selector-prereg/)
as historical evidence. Its input hashes no longer match the committed
`AGENTS.md` and `README.md`, so it cannot authorize dispatch. It was not edited
or reused.

## Frozen scope

The target is pinned Ascon-128 v1.3.0 on the existing PicoRV32 RV32I/Zicsr,
ILP32, `-Os` path. Ascon is an unseen application with related-domain
cryptography motifs; this is a same-domain transfer test, **not** an
independent-family confirmation. The accepted baseline-only qualification
found 45 executable formulas and froze the existing twelve-candidate pool
before target outcomes. The family filter removes all 32 historical rows whose
candidate family overlaps the target pool, leaving 90 successful training
labels across 14 historical groups. All four historical failures remain in
the cost ledger.

The package freezes the existing thirteen selector policies, five seeds, and
one-, two-, and three-attempt budgets at +64 LUT4 and 12 MHz. It creates five
seeded model fits from the 90-row family-safe cohort. This is not a new model
recipe. The outcome remains the best actually measured, correct, feasible
whole-program speedup; the measured-pool oracle is revealed only after the live
agent trace and matched control decisions are sealed.

The current-chat policy is operator-relayed and has conversation context. It
is not an isolated API deployment; model-only latency and token counts are not
available. These limits are part of the frozen interpretation.

## Reproduction and current state

```sh
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py freeze
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py authenticate
../work/audit-venv/bin/python scripts/run_ascon_selector_controller.py freeze-release
```

The zero-label package is at
[`results/2026-10-27-ascon-selector-prereg-v2/`](../results/2026-10-27-ascon-selector-prereg-v2/).
The controller release is at
[`results/2026-10-27-ascon-selector-controller-release-v4/`](../results/2026-10-27-ascon-selector-controller-release-v4/).
Both authenticate with zero target labels and zero candidate attempts. The
release enables dispatch only after every bound source is committed unchanged
on the pushed `ai-guided-ml` branch. The fresh campaign root is
`generated/ascon-native-selector-2026-10-27-v4/`; the earlier v2 controller
root and its one charged unknown reservation remain preserved and must never
be retried.

Passing the release gate permits a bounded transfer experiment, not a claim
that ML beats merit, nor completion of the six-independent-family objective.
Any failed or interrupted attempt remains charged; an unresolved oracle
reference makes regret a lower bound.

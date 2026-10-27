# Ascon selector preregistration v3

This is the current zero-label preregistration for the bounded Ascon transfer
experiment. It preserves v1 and v2 at their original paths. V1 no longer
matches the committed `AGENTS.md` and `README.md`; v2 was an intermediate freeze
that did not hash-bind its own preparation script. Neither old package was
edited or used to authorize dispatch.

## Frozen protocol

The target is pinned Ascon-128 v1.3.0 on the existing PicoRV32 RV32I/Zicsr,
ILP32, `-Os` path. This is a new application in the related cryptography
domain, not an independent-family confirmation. Baseline-only discovery found
45 executable formulas and froze the public twelve-candidate pool before any
target result. The exact family filter excludes 32 related historical rows,
leaving 90 successful training labels across fourteen historical groups. All
four historical failures remain charged in the cost ledger.

The package freezes thirteen existing selector policies, five seeds, and
budgets one through three under a +64-LUT4 cap and 12-MHz floor. Five seeded
model fits use the same fixed recipes; no model family or hyperparameter is
added. The endpoint is the best actually measured, correct, feasible
whole-program speedup. Controls and the measured-pool oracle must not see a
candidate outcome before their corresponding sealed decision prefix.

The current-chat agent is operator-relayed and carries conversation context; it
is not an isolated provider benchmark. Token count and model-only latency are
unavailable. This experiment cannot establish independent workload-family
generalization or superiority over merit.

## Reproduction and release gate

```sh
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py freeze
../work/audit-venv/bin/python scripts/prepare_ascon_selector_prereg.py authenticate
../work/audit-venv/bin/python scripts/run_ascon_selector_controller.py freeze-release
```

The package is at
[`results/2026-10-27-ascon-selector-prereg-v3/`](../results/2026-10-27-ascon-selector-prereg-v3/).
It binds 32 source and data inputs, including the preparation script itself,
and authenticates with zero target labels and candidate attempts. The controller
release is at
[`results/2026-10-27-ascon-selector-controller-release-v5/`](../results/2026-10-27-ascon-selector-controller-release-v5/).
Its dispatch bit is insufficient by itself: every bound source must first be
committed unchanged on the pushed `ai-guided-ml` branch. Only then may a fresh
campaign be prepared at
`generated/ascon-native-selector-2026-10-27-v5/`.

The previous v2 controller root and its charged unknown reservation remain
preserved and must never be retried. The v4 release is also preserved as a
zero-label intermediate; v5 binds the preregistration generator source.

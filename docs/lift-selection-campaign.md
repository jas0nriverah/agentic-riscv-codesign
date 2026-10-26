# Lift candidate-selection campaign

This is consumed Lift CFG-tail engineering development, not an untouched confirmation workload. The accepted baseline-only qualification remains unchanged and records zero candidate labels. This separate campaign tests the release-gated, source-bound comparison; it does not establish research superiority.

The exact pool has twelve formulas. It retains the original 1,001 zero-input iterations/checksum 4005888, compiler, device, partition, clock, and public-opportunity gates. The projected-equivalence verifier and fixed-input correctness limitations remain explicit; qualification must not be rerun.

The comparison retains fourteen prior policies plus three fixed-joint controls. Training uses the complete historical corpus of 110 verified labels, four failures, and 114 attempts, after excluding the full Lift source and every related formula family; the resulting 100 fitting rows span all thirteen prior sources. At +64 LUT4, 12 MHz, and three queries, fixed-joint myopic seed 0 is the only live policy. It must seal each acquisition before dispatch. After its three paid outcomes, the controller seals the complete live trace, then measures the remaining pool once in frozen public order. Other policies are replayed after collection with the same outcomes and charged budgets; they receive no additional native measurements.

The primary outcome is the best verified whole-program cycle reduction at the fixed +64/B3 endpoint. Reports also retain B1/B2 prefixes, separately executed finite B1/B2/B3 horizons, +32/+128 caps, five dependent seeds, measured-pool regret, correctness, candidate cycles/speedup, integrated LUT4, routed timing, and both ledger and paired observed CLI times. Correctness and infrastructure failures are charged without invented labels; a censored candidate makes regret a lower bound. No policy is promoted from one consumed source.

## Frozen workflow

Use the pinned Python 3.12 environment. The active, complete preregistration is `results/2026-10-26-lift-selection-preregistration-v4`. Earlier same-day v1, v2, and v3 zero-label preregistrations are preserved as superseded packages; none is authenticated for candidate release. v1 lacked complete replay/export. v2 included those paths but failed a later integration audit covering terminal-failure exit status, relocated acquisition paths, raw snapshot restoration, frozen-model binding, and root-bound verification. v3 was frozen before the final audit caught a selection-inventory binding mismatch and missing validation-refit cost accounting. No candidate outcomes were read and no candidate jobs were run under any superseded package.

Freeze and authentication read no Lift labels and run no native candidate jobs:

```sh
../work/audit-venv/bin/python scripts/lift_selection_campaign.py freeze \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25 \
  --qualification results/2026-10-25-lift-cfg-tail-qualification \
  --output results/2026-10-26-lift-selection-preregistration-v4
../work/audit-venv/bin/python scripts/lift_selection_campaign.py authenticate \
  --preregistration results/2026-10-26-lift-selection-preregistration-v4
```

Candidate evaluation is enabled only after the complete source/model/protocol package and exact v4 preregistration are committed and pushed to `origin/ai-guided-ml`. Substitute that pushed commit for `<prelabel-commit>`:

```sh
../work/audit-venv/bin/python scripts/lift_selection_campaign.py release \
  --preregistration results/2026-10-26-lift-selection-preregistration-v4 \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25 \
  --commit <prelabel-commit> \
  --output results/2026-10-26-lift-selection-release.json
../work/audit-venv/bin/python scripts/lift_selection_campaign.py collect \
  --preregistration results/2026-10-26-lift-selection-preregistration-v4 \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25 \
  --release results/2026-10-26-lift-selection-release.json \
  --output results/2026-10-26-lift-selection-collection
../work/audit-venv/bin/python scripts/lift_selection_campaign.py pack \
  --preregistration results/2026-10-26-lift-selection-preregistration-v4 \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25 \
  --collection results/2026-10-26-lift-selection-collection \
  --release results/2026-10-26-lift-selection-release.json \
  --output results/2026-10-26-lift-selection-campaign
../work/audit-venv/bin/python scripts/lift_selection_campaign.py replay \
  --campaign results/2026-10-26-lift-selection-campaign \
  --output results/2026-10-26-lift-selection-replay
../work/audit-venv/bin/python scripts/lift_selection_campaign.py report \
  --campaign results/2026-10-26-lift-selection-campaign \
  --output results/2026-10-26-lift-selection-report
../work/audit-venv/bin/python scripts/lift_selection_campaign.py export \
  --campaign results/2026-10-26-lift-selection-campaign \
  --output results/2026-10-26-lift-selection-corpus
```

Collection calls the guarded one-attempt evaluator serially. Each CLI receipt captures the complete operation; its timer stays separate from the native CLI and guarded-candidate timers. A terminal failed outcome is sealed and charged, the command exits nonzero, and collection can continue after reconciling that status with the native ledger. An interrupted reservation is never retried automatically.

The collection package seals its original absolute native and collection paths so archived checks can verify the exact recorded argv while reading copied acquisition bytes. Packing stores the guarded raw archive. Report, export, and replay restore it to a fresh path and validate it with the root-bound CFG callback; they do not depend on the original generated directory. Replay authenticates the top-level campaign inventory and checks every copied frozen model byte-for-byte against the preregistration, then reruns the deterministic model refits. No frozen model may be replaced after outcomes are observed.

The campaign's independent raw archive round-trip was tested on the accepted baseline-only native tree: **zero candidate attempts, zero new native jobs, and exact audit equality**. This validates the archive/root-callback path; it does not validate a candidate collection. The synthetic policy replay covers 345 trajectories, 900 endpoint points, and 180 summaries; those are software checks, not measured results.

The current XGBoost regressors/ranker, calibrated latency baseline, frequency, merit, random, constrained GP, and count/semantic/fixed-joint policies remain unchanged. Do not add another learner based on this consumed workload alone. First measure Lift, preserve residuals and policy losses, and then test whether the observed failures justify a nested whole-workload XGBoost challenger. No isolated LUT study, model promotion, superiority claim, multi-instruction additive assumption, or six-family confirmation follows from this package. Joint selection and processor validation remain future work.

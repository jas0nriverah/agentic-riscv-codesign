# TACLeBench bitcount: useful fresh-source selection experiment

The unchanged guarded pipeline now accepts a new multi-file integer workload.
TACLeBench bitcount executes eight population-count algorithms, ten inputs per
algorithm, with its original seed and aggregate1095 check. The original source
files are pinned and unchanged; an external ILP32 amalgamation/ABI adapter makes
them available to the existing source-marker, extractor and rewriter.
[Source provenance and build-context limitations](../benchmarks/tacle/README.md)
are explicit. This is TACLeBench, not an Embench/BEEBS sample or arbitrary-program support.

## Qualified baseline

The fixed qualification retains twelve formulas and the same-candidate minima
of0.5% calibrated whole-program cycle reduction and ten timed replacements. It
does not retry the eight earlier rejected BEEBS contexts or change their gates.

The full original input passes the native self-check at **51,689 cycles and
10,319 instructions**. Automatic discovery yields forty raw formulas and37
executable formulas before the calibrated guarded shortlist. One selected
formula executes150 times, with a public predicted450-cycle/0.870591% reduction.
This is a calibrated estimate, not a measured optimized-program label. The
baseline passes integrated synthesis, all three route seeds, unobserved versus
observed execution, and deliberate memory-guard controls. The recorded maximum
stack use is336 bytes, leaving1,328 bytes above the declared floor.

[Qualification protocol, raw archive and receipts](../results/2026-10-22-bitcount-qualification/qualification.json)
retain zero custom-candidate attempts. The processor/compiler/interface remain
RV32I_zicsr/ILP32 `-Os`, integrated8KiB RAM,6400/6528 memory partition, one-wait
PCPI and common12MHz objective. Single-word source marking must leave baseline
firmware byte-identical before any rewrite. The compiler's amalgamated build is
a declared context, not an upstream binary-identity claim.

## Fixed comparison

[The complete preregistration](../results/2026-10-22-bitcount-preregistration/cohort.json)
fits every learned policy to the same historical source/family-filtered cohort.
The available history has87 successes, three preserved failures and90 charged
attempts from eleven consumed sources. The entire new source is absent. Exact
and related formula families are excluded before fitting. Historical costs are
charged once and remain distinct from setup, qualification and host inference.

All fourteen policies retain their existing settings: frequency, merit,
calibrated latency, latency/cost heuristic, random, raw-speedup XGBoost, ranking,
normalized XGBoost, both original constrained GPs, feasible-benefit XGBoost,
factorized-feasibility XGBoost, count GP and six-field semantic count GP. No
feature, kernel, model setting, stop rule or budget is tuned on this source.
Each uses caps32/64/128 LUT4, budgets1/2/3,12MHz and five dependent seeds.
The primary endpoint remains best verified feasible whole-program performance
at+64 LUT4 after three paid attempts, with regret to the measured fixed-pool
reference when complete. MAE and area error remain secondary.

The semantic count GP at seed0/+64 performs three actual live native queries.
Before each dispatch, the controller seals its chosen candidate, predictions,
model-state digest, exact historical fitting IDs and successful paid-prefix IDs.
It seals the completed live trace before collecting the remaining nine
candidates in declared order for the separate oracle reference. Every attempt,
including failure, is charged once; interruptions stop collection without retry.
The other policies use bounded cooperative replay of the same measured pool.

Candidate execution requires the complete model/controller package to exist in
the exact pushed Git checkpoint. The native gate rechecks both full-model
authentication and the actual remote head. Release metadata alone cannot permit
measurement. Local callbacks are cooperative isolation, not an OS sandbox.

A [pre-label proof serialization amendment](../results/2026-10-22-bitcount-proof-amendment/cohort.json)
preserves the frozen controller and an actual label-free first-acquisition
witness. Its Python score tuple becomes a list after JSON serialization, so
direct Python equality fails although the canonical JSON digest is identical.
The separate packing/replay adapter normalizes only that two-number proof field
at the comparison boundary. Every score, prediction, model state, decision,
paid outcome and native duration must still match exactly; no numeric tolerance
is added. The complete amendment is pushed before any candidate measurements.

## Commands

Use Python3.12 and `requirements-speedup.txt`. Native commands require the pinned
tool paths recorded by the original processor reference. Do not repeat native
qualification/collection on existing roots.

```sh
# Already completed qualification and model freeze; original roots are preserved.
python scripts/qualify_tacle_bitcount.py
python scripts/tacle_selection_campaign.py freeze \
  --native-root generated/tacle-bitcount-2026-10-22 \
  --qualification results/2026-10-22-bitcount-qualification \
  --output results/2026-10-22-bitcount-preregistration
python scripts/reproduce_tacle_selection.py prepare \
  --preregistration results/2026-10-22-bitcount-preregistration \
  --output results/2026-10-22-bitcount-proof-amendment

# After pushing the entire preregistration, release once with its exact commit.
python scripts/tacle_selection_campaign.py release \
  --preregistration results/2026-10-22-bitcount-preregistration \
  --native-root generated/tacle-bitcount-2026-10-22 \
  --commit PRELABEL_COMMIT --output results/2026-10-22-bitcount-release.json
python scripts/tacle_selection_campaign.py collect \
  --preregistration results/2026-10-22-bitcount-preregistration \
  --native-root generated/tacle-bitcount-2026-10-22 \
  --release results/2026-10-22-bitcount-release.json \
  --output results/2026-10-22-bitcount-collection
python scripts/reproduce_tacle_selection.py pack \
  --preregistration results/2026-10-22-bitcount-preregistration \
  --native-root generated/tacle-bitcount-2026-10-22 \
  --release results/2026-10-22-bitcount-release.json \
  --collection results/2026-10-22-bitcount-collection \
  --output results/2026-10-22-bitcount-campaign

# Hardware-free reproduction/report/export after completed collection.
make reproduce-bitcount PYTHON=python
make bitcount-report PYTHON=python
make export-bitcount-corpus PYTHON=python
```

The reproduction requires exact raw processor evidence, prelabel Git bindings,
fifteen historical model refits, the initial semantic refit, live acquisition
proofs and all210 trajectories/630 endpoint points. Only explicitly named host
timers are excluded from exact equality; their archived and newly observed
endpoint values are both preserved. Native paid durations never use tolerances
or exclusions. Every derived output root must be fresh.

## Limits and next blocker

[Prelabel validation](../results/2026-10-22-bitcount-prelabel-validation/README.md)
records50 focused passes,3,484 full-suite passes and179 passing subtests. The
same earlier legacy pipe-cleanup failure recurs and is preserved; no cleanup
fix or completely green full suite is claimed. Historical model/processor
replays and both fixed count/semantic replays pass.

At this checkpoint only qualification/model preparation is complete: optimized
cycles and hardware outcomes are not yet measured. The twelve-candidate
comparison is one fresh source, not twelve independent tasks or five independent
test repetitions. A tie or loss to merit remains a valid outcome. Uncertainty
is uncalibrated; aggregate correctness is fixed-input evidence, and constrained
sets of one to three instructions still need joint validation. This experiment
tests existing model transfer and connects useful fresh data; it adds no isolated
area-model version, RTL optimization agent, LLM integration or cloud deployment.

Repeated authentication refits are validation work inside outer CLI scopes. The
single initial semantic-fit receipt does not count total model/verification work.
Paired UTC/monotonic clocks, ledgers, native commands and CLI durations remain
separate overlapping scopes; no uninterrupted calendar-wall or total-cost win
is established by a count-budget result.

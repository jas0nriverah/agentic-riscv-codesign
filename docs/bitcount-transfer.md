# TACLeBench bitcount: completed fresh-source selection experiment

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
This was a public calibrated estimate at qualification. Subsequent native execution independently measures the same 450-cycle reduction; its +65 LUT4 cost exceeds the primary +64 cap. The
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
is added. Both complete packages were pushed at `7bbe3f7070e3b31ee4de9fe973c536cccf3aca03` before any candidate measurements. The release gate authenticated the actual remote head before native queries.

## Measured outcomes

All twelve candidates pass correctness, execution/processor controls, memory checks, integrated synthesis/device capacity and all three routes. Baseline resources are 1,653 LUT4, 655 flip-flops, 295 carry cells and 20 BRAM blocks, with minimum Fmax 68.493 MHz. Candidate cycle deltas all equal calibrated estimates. These are simulated processor cycles and routed estimates on the declared fixed input, not board results or general correctness proofs.

| Area cap | Complete-pool best | Cycles | Speedup | Added LUT4 | Minimum MHz |
| --- | --- | ---: | ---: | ---: | ---: |
| +32 | candidate 18 | 51,641 | 1.000929× | 26 | 68.719 |
| **+64 (primary)** | **candidate 31** | **51,599** | **1.001744×** | **39** | **67.783** |
| +128 | candidate 00 | 51,239 | 1.008782× | 65 | 61.824 |

The actual live semantic GP chooses **00→14→11**, with +65/+77/+73 LUT4, and retains baseline after all three paid attempts. The trace is sealed before the nine reference candidates. At +64 / three queries, the cost heuristic reaches the pool optimum in all five dependent seeds. Mean verified cycle reduction is 0.174118% for that heuristic, 0.094024% for random, 0.092863% for frequency and 0.055718% for ranking. Merit, calibrated latency and the other learned policies retain baseline. This source does not support learned superiority; no policy is promoted.

[The full report](../results/2026-10-22-bitcount-report/results.md) contains all twelve measured cycles, correctness, resource counts and minimum timing; its CSV retains every route seed and all fourteen policies/caps/budgets. [The campaign](../results/2026-10-22-bitcount-campaign/provenance.json) preserves raw native evidence, acquisition proofs and the prelabel Git binding. [The expanded corpus](../results/2026-10-22-twelve-source-corpus/README.md) contains **99 verified labels / three failures / 102 attempts / twelve sources / thirteen contexts**. It preserves the earlier 87 labels and failures exactly. This increment adds thirteen integrated designs and 39 routes, bringing completed automatic designs/routes to 112/336 including baselines.

The new candidate ledger records 921.081198 seconds. All native commands total 860.892178 seconds; baseline ledger 28.101971 seconds; the full collection observer records 1064.975519 monotonic seconds. Historical 90 attempts retain 5098.832466 ledger seconds. Scopes overlap and must not be added. Replayed policy cost sums are not independent measured live search lifetimes.

## Working commands

Use Python 3.12 and `requirements-speedup.txt`. Native qualification, freeze, release, three-query collection, nine-query oracle completion and packaging are **finished**. Preserve those original roots; do not repeat native commands on them.

```sh
# Authenticate raw evidence, exact model refits and all policy decisions; no native jobs.
make reproduce-bitcount PYTHON=python
# Produce all-candidate and all-policy Markdown/CSV; no fits, predictions or native jobs.
make bitcount-report PYTHON=python
# Preserve old rows exactly and append twelve native labels.
make export-bitcount-corpus PYTHON=python
```

Each derived output root must be fresh. Override `BITCOUNT_REPLAY_OUTPUT`, `BITCOUNT_REPORT_OUTPUT` or `BITCOUNT_CORPUS_OUTPUT` for another replay. Recorded outputs in `results/` are sealed evidence and must not be overwritten.

The completed reproduction checks exact raw processor evidence, prelabel Git bindings, fifteen historical model refits, the initial semantic refit, live acquisition proofs and **210 trajectories / 630 endpoint points / 126 summaries**. Only explicitly named host timers are excluded from exact equality; archived and newly observed endpoint values are both preserved. Native paid durations never use tolerances or exclusions.

## Limits and next blocker

[Prelabel validation](../results/2026-10-22-bitcount-prelabel-validation/README.md)
records50 focused passes,3,484 full-suite passes and179 passing subtests. The
same earlier legacy pipe-cleanup failure recurs and is preserved; no cleanup
fix or completely green full suite is claimed. Historical model/processor
replays and both fixed count/semantic replays pass.

[Post-collection validation](../results/2026-10-22-bitcount-validation/README.md) passes complete raw/model/live/policy replay, reporting and corpus export. Scientific source hashes remain identical to the prelabel checkpoint. The twelve-candidate comparison is one fresh source, not twelve independent tasks or five independent test repetitions. All outcomes are now consumed development data, including this negative comparison. Uncertainty
is uncalibrated; aggregate correctness is fixed-input evidence, and constrained
sets of one to three instructions still need joint validation. This experiment
tests existing model transfer and connects useful fresh data; it adds no isolated
area-model version, RTL optimization agent, LLM integration or cloud deployment.

Repeated authentication refits are validation work inside outer CLI scopes. The
single initial semantic-fit receipt does not count total model/verification work.
Paired UTC/monotonic clocks, ledgers, native commands and CLI durations remain
separate overlapping scopes; no uninterrupted calendar-wall or total-cost win
is established by a count-budget result.


The next bounded research experiment should address the observed decision failure, not add another isolated area predictor. The chosen GP candidates have broad area uncertainty (standard deviation about 22 LUT4), yet all three queries pursue related risky adders. One fixed finite-pool two-step constrained-lookahead acquisition can test terminal verified benefit using the existing model and joint candidate covariance. Freeze its integration/draw/tie settings before consumed-data development scoring, retain all fourteen controls and host-cost accounting, then test on an untouched source. This is a proposed adaptation of established methods, not implemented lookahead, calibrated confidence or a promised improvement. [Current handoff and next-source qualification limits](HANDOFF.md) define the next task.

The collection observer records UTC 1064.988605 seconds versus monotonic 1064.975519 seconds, outside its paired capture bracket. Both raw observations and the unresolved clock-disagreement flag are retained; no timestamps are corrected and uninterrupted calendar wall time is not established.

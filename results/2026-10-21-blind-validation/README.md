# Blind campaign validation

Prelabel full `make test`:3,223 passes,179 passing subtests,one pending-campaign integration skip,one intentional ZIP fixture warning and the previously documented intermittent legacy process-cleanup failure. The focused rerun passes110tests and skipsone, reproducing the same legacy pipe-cleanup failure. All109new focused tests pass. No legacy source was changed and no cleanup fix is claimed.

All three public baselines, complete model/source/package/cohort bindings and zero-candidate-attempt gates authenticate before measurement. The fixed per-target fitting cohorts contain44/33/29candidates acrossallsevenhistorical sources after related-family exclusions. Candidate results and final replay/export validation will be appended as separate records after the pushed checkpoint.

## Completed campaign

All 36 new candidates pass correctness, custom-execution counts, stock/custom controls, integrated synthesis and108 routes. Independent sealed native audits cover [compression](aha-independent-audit.json), [DES](ndes-independent-audit.json) and [MD5 compression](md5-independent-audit.json). The complete corpus has81 successes, three preserved failures,84 attempts, ten source groups and eleven contexts;92 completed integrated designs and276 routes include baselines. All 81 cycle changes exactly match calibrated latency. No source, input, candidate, model setting or charged attempt was revised after the prelabel freeze.

The original [strict packaging failure](pack.txt) is preserved. Four MD5 candidates fail enclosure when UTC starts are combined with monotonic durations, and one collector-derived serial gap is negative. The cause cannot be distinguished from these records. `reproduce_blind_campaign.py` is a separate post-collection accounting amendment. It preserves raw clocks and the strict error, authenticates the blocking collector and contiguous native receipts, and validates the nested elapsed-duration scopes. Uninterrupted calendar wall time remains unknown. No native attempt was repeated and no tolerance was introduced.

The [qualified pack](qualified-pack.txt) and [complete replay](qualified-replay.txt) pass: three native archives, complete Git prelabel artifact/source proofs, release-before-start chronology,45 model/refit checks and all 1,620 policy endpoints. An [independent check from integer cycles](independent-policy-numerics.json) reproduces all 1,620 points,324 source summaries and108 macro summaries. GP controls reach all three primary optima; the newer classifier loses to merit on two sources and ties one. Every policy remains in the report; no superiority claim is established.

## Tests and commands

- [Prelabel full suite](prelabel-tests.txt):3223 passes,179 subtests,one skip and the existing intermittent legacy pipe-cleanup failure.
- [Prelabel focused rerun](targeted-prelabel-tests.txt):110 passes,one skip and the same legacy failure.
- [Post-collection full suite before accounting amendment](final-tests.txt):3225 passes,179 subtests,one skip and the same legacy failure.
- [Final full suite](amendment-tests.txt):3244 passes,179 subtests,one integration skip and one intentional ZIP-fixture warning. The intermittent legacy case passed in this run; no fix is claimed.
- [Completed focused suite](completed-focused-tests.txt):all 132 tests pass, including real-campaign report/export integration and21 clock-accounting boundary tests. This covers the integration skipped before the campaign manifest existed during full-suite collection.

[Report generation](report.txt), [corpus export](corpus.txt), [figure generation](figures.txt), the actual Make targets for [report](report-command.txt), [corpus](corpus-command.txt) and [figure](figure-command.txt), and [historical `make reproduce`](historical-reproduce.txt) pass. The latter reproduces all six historical metrics without training/synthesis. [The research figure](../2026-10-21-blind-figures/blind-primary-curves.png) was visually inspected; count-budget curves, differing vertical scales and clock qualification are visible. Reporting/export/plotting run zero fits or native jobs. Replay refits only the unchanged frozen models.

Recorded monotonic acquisition costs and shared historical costs are in the report. These scopes overlap and must not become an uninterrupted-wall-time total. The current independent cohort is three new sources with small, filtered single-instruction pools. All successful designs fit and clear12MHz, leaving timing-boundary behavior, calibrated uncertainty and joint instruction sets untested.

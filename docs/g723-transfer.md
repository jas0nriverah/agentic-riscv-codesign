# G.723 transfer: measured processor benefit, no lookahead advantage

The original-input TACLeBench encoder now passes automatic extraction, lowering, processor execution and integrated hardware measurement. The original 256 A-law samples and checksum 24284 are preserved in a declared ILP32 adapter. ISA, PCPI latency, 8-KiB memory partition, HX8K target, 12-MHz acceptance clock and three routing seeds match the guarded contract. These are processor-simulation cycles and synthesized/routed hardware estimates, not physical-board measurements.

The complete seventeen-policy package and identical 86-row source/family-excluded fitting cohorts were pushed at `d8a5c9103cbc8032a62301e5a21a319fdd6f2a26` before candidate evaluation. The three actual lookahead decisions/outcomes are sealed before nine reference queries. No attempt is retried.

**The best verified design reduces 3,783,237 to 3,623,462 cycles (4.223235% cycle reduction / 1.044095× speedup), adds 30 LUT4 and reaches minimum routed Fmax 67.549 MHz.** Frequency, merit, calibrated latency, the cost heuristic and every learned control except lookahead/random reach it at their first query in all five seeds. At +64 LUT4 / three queries, sixteen policies tie; random averages 1.000297% cycle reduction. Lookahead is not promoted.

The actual live seed0 lookahead chooses 09→00→47, finding this design at query two. Across five dependent B3 runs, mean reductions are 1.884175%→3.443548%→4.223235%. Independently planned B1 and B2 lookahead runs both finish at 4.223235% in every seed. Those horizon-aware endpoints are distinct from B3 prefixes. One source and repeated seeds do not establish significance or broad generalization.

**The pool oracle is incomplete.** Candidate57 hits the declared 180-second timeout on route seed3, after two partial routes and passing raw simulation evidence. Its 219.421167-second attempt remains an unknown outcome, with no invented hardware label or retry. Every JSON/CSV endpoint correctly records `reference_complete=False` and `regret_is_lower_bound=True`. The original Markdown table’s plain “Regret %” heading must be read as a lower bound on regret to the unresolved full pool; zero is only zero gap to the best verified reference. Original report bytes are preserved.

## Native outcomes

All verified candidates pass the recorded-input self-check, integer oracle, stock-firmware equivalence, rejection on the unextended processor and all three route seeds at 12 MHz. All eleven successful saved-cycle labels exactly match calibrated latency. Across the complete corpus all 110 successful labels remain explained; a benefit-residual learner is not justified.

| Candidate | Cycles | Speedup | Total / added LUT4 | FF / BRAM | Min Fmax MHz | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline | 3,783,237 | 1.000000 | 1653 / 0 | 655 / 20 | 68.493 | Verified |
| 00 | 3,623,462 | 1.044095 | 1683 / +30 | 696 / 20 | 67.549 | Verified |
| 09 | 3,770,949 | 1.003259 | 1697 / +44 | 700 / 20 | 67.268 | Verified |
| 17 | 3,778,373 | 1.001287 | 1703 / +50 | 696 / 20 | 61.641 | Verified |
| 29 | 3,780,677 | 1.000677 | 1728 / +75 | 712 / 20 | 68.790 | Verified |
| 38 | 3,781,445 | 1.000474 | 1681 / +28 | 681 / 20 | 69.391 | Verified |
| 47 | 3,778,373 | 1.001287 | 1714 / +61 | 712 / 20 | 68.493 | Verified |
| 57 | — | — | — | — | — | Unknown: route3 timeout |
| 67 | 3,782,469 | 1.000203 | 1679 / +26 | 680 / 20 | 65.036 | Verified |
| 74 | 3,782,469 | 1.000203 | 1699 / +46 | 712 / 20 | 70.215 | Verified |
| 85 | 3,782,469 | 1.000203 | 1754 / +101 | 712 / 20 | 71.179 | Verified |
| 91 | 3,782,475 | 1.000201 | 1686 / +33 | 680 / 20 | 63.452 | Verified |
| 103 | 3,783,234 | 1.000001 | 1714 / +61 | 681 / 20 | 67.723 | Verified |

[All formulas, labels and candidate costs](../results/2026-10-25-g723-report/candidates.csv), [all seventeen policy curves](../results/2026-10-25-g723-report/endpoints.csv), [raw campaign/provenance](../results/2026-10-25-g723-campaign/provenance.json) and [expanded corpus](../results/2026-10-25-thirteen-source-corpus/README.md) remain reproducible.

## Commands and validation

Use the pinned Python3.12 environment and fresh output roots:

```sh
python scripts/g723_selection_campaign.py replay --campaign results/2026-10-25-g723-campaign --output generated/g723-replay-new
python scripts/g723_selection_campaign.py report --campaign results/2026-10-25-g723-campaign --output generated/g723-report-new
python scripts/g723_selection_campaign.py export --campaign results/2026-10-25-g723-campaign --output generated/g723-corpus-new
```

Raw/model/live-prefix replay passes 345 trajectories / 900 curve points / 180 summaries with zero native jobs. Initial model refits and actual paid-prefix proofs remain exact. Only explicitly named nondeterministic host timers are excluded, with archived/fresh endpoint arrays retained. [Validation receipts](../results/2026-10-25-g723-validation/README.md) preserve commands and tests.

The corpus is now 110 verified labels, four failures, 114 attempts, thirteen sources and fourteen contexts. Original99+3 rows and exact prior corpus bytes remain unchanged. Including baselines, 124 integrated designs have complete three-seed verification (372 routes), plus two partial routes from candidate57. All sources are now development data.

Candidate ledger cost is 729.893610 seconds; candidate CLI timers total 804.032359 seconds; per-query observers total 813.172007 seconds; the collection observer records 827.713312 monotonic seconds. These scopes overlap. Qualification contributes one separate baseline and 58.626485 subprocess seconds, including baseline work. Historical102 attempts retain 6,019.913664 ledger seconds, yielding 6,749.807273 seconds across114 attempts. Other-policy cost curves are charged replay accounting; only the live policy has an observed native controller lifetime. Paired-clock disagreements remain explicit; uninterrupted calendar wall-time savings are not established.

The next bounded model test is the [historical-likelihood ARD area surrogate](ard-area-experiment.md), with unchanged myopic acquisition and all seventeen controls. It is a consumed-data test, not a new G.723 prospective result. The subsequent [area-model experiment](ard-area-results.md) repairs bitcount but regresses expanded AHA and is not promoted. Original-input Lift qualification rejects the source for fewer than twelve executable formulas, with zero candidate labels. The separate [CFG-liveness coverage experiment](cfg-liveness-experiment.md) addresses a demonstrated conservative output-analysis gap without rerunning that frozen context. The [active research goal](ACTIVE_GOAL.md) remains unachieved.

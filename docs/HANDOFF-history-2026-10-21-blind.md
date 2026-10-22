# Current handoff — completed three-source blind campaign

Read [README](../README.md), [AGENTS](../AGENTS.md), [campaign contract](blind-source-campaign.md), [primary methods](research-foundation.md) and [teammate compatibility](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. GPT-6.1 Sol subagents independently reviewed native evidence, accounting and policy arithmetic. Model/data work remains the priority; demo, live LLM and RTL rewriting are paused. The [previous factorized checkpoint](HANDOFF-history-2026-10-21-factorized.md) and every historical experiment remain intact.

## Completed evidence

**81 verified labels, three preserved failures, 84 attempts, ten source workloads and eleven contexts; 92 completed integrated designs and 276 routes including baselines.** The new independent test is three sources, each with twelve candidates, not ten untouched holdouts. All ten sources are now consumed data.

The complete three-source model/prediction/baseline/qualification package was pushed at **`0b0884e112fbb3635487f7ae93d5d0f1616dbcb2`** before any target candidate attempt. The zero-attempt [release](../results/2026-10-21-blind-release.json) authenticates every source. All twelve existing selectors, five dependent seeds, caps32/64/128 and budgets1/2/3 stayed fixed. Targets never trained one another. Historical 45 successes/seven sources were shared; identical related-family exclusions left44/33/29 fitting rows, respectively. The three old failures remain charged, not fabricated training labels.

| BEEBS source | Baseline cycles | Declared / eligible | +64 oracle cycles | Speedup | Added LUT4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| aha-compress | 70,797 | 12 / 26 | 69,177 | 1.023418× | 61 |
| ndes | 234,519 | 12 / 43 | 232,855 | 1.007146× | 28 |
| nettle-md5 | 6,192 | 12 / 297 | 6,080 | 1.018421× | 55 |

All 36 new candidates pass correctness, counters, stock/custom processor controls, integrated synthesis and all 108 routes. Every successful candidate still clears12MHz and fits the device. The new MD5 source measures its original single64-byte compression block, not complete message hashing. RC4's insufficient-legal-pool qualification rejection remains preserved; Levenshtein was not run. Sources and inputs were not reduced. All three targets share RV32I/ILP32 `-Os`, original8KiB integrated RAM,6400-byte program region,128-byte guard,1664-byte stack and two build workers with serial evaluation.

[All 36 measurements and all twelve selectors](../results/2026-10-21-blind-report/results.md), [raw packed evidence](../results/2026-10-21-blind-campaign/provenance.json), [prelabel cohort](../results/2026-10-21-blind-preregistration/cohort.json), [expanded corpus](../results/2026-10-21-ten-source-corpus/README.md) and [curves](../results/2026-10-21-blind-figures/blind-primary-curves.png) are committed deliverables. Generated native roots are optional local build state; use the raw archives for replay.

## Selection result and interpretation

Primary endpoint: mean verified feasible cycle reduction across the three sources after three attempts at+64LUT4/12MHz. Both preserved GP controls attain all three measured pool optima: **1.602185%** versus **1.144539%** for merit/calibrated latency, **1.449636%** for normalized XGBoost and **0.719365%** for the newer factorized classifier. The classifier loses to merit on two sources and ties on one; do not promote it. Its outputs remain uncalibrated. Adaptive GP reaches compression's oracle on query two; zero-shot GP needs three. Both tie at the primary endpoint. Every three-query trajectory still spends three attempts.

The GP result is promising three-source evidence for existing constrained acquisition, not field superiority or a new method. The shared 48 historical attempts must be counted; a lower total hardware cost after training is not established. Five seeds are dependent repetitions. Oracles cover the declared twelve-candidate subsets, not all formulas or instruction sets. The new+32 compression pool has no feasible improving instruction, so its oracle gain fraction is undefined.

All 81 cycle deltas exactly match calibrated latency. The factorized model learns hardware feasibility combined with known calibrated benefit; speedup regression/ranking remain separate real-label-trained controls. No performance residual learner is justified. Future model changes must address an observed decision failure and be assessed on untouched sources, rather than sweeping against these consumed pools.

## Replay and validation

Use Python3.12 and `requirements-speedup.txt`. All commands below have been run successfully; report/export/plot outputs must be fresh:

```sh
make reproduce-blind-campaign PYTHON=python
make blind-report PYTHON=python
make export-blind-corpus PYTHON=python
make blind-figures PYTHON=python
make reproduce PYTHON=python
```

Override `BLIND_REPLAY_OUTPUT`, `BLIND_REPORT_OUTPUT`, `BLIND_CORPUS_OUTPUT` and `BLIND_FIGURE_OUTPUT` for another run. Replay checks raw hardware evidence, exact Git prelabel artifacts, release-before-start chronology,45 grouped model/refit checks and all 1,620 endpoints, with zero new native jobs. Independent integer-cycle arithmetic also reproduces all 1,620 points,324 source summaries and108 macro summaries. Source hashes of report/export match their sealed provenance. The research figure was visually inspected.

All 132 focused tests pass, including the completed real-campaign integration. The final full suite has3244 passes,179 passing subtests, one integration skip subsequently covered by the focused run, and one intentional ZIP-fixture warning. Earlier prelabel/post-collection full runs retain the unchanged intermittent legacy process-cleanup failure; no legacy fix is claimed. [Validation logs](../results/2026-10-21-blind-validation/README.md) retain every run.

## Clock qualification and next blocker

The frozen `scripts/blind_campaign.py pack` fails mixed-clock enclosure for four MD5 candidates. Do not edit it or its bound sources. `scripts/reproduce_blind_campaign.py` is an explicit post-collection accounting amendment, now bound into final provenance. It retains the original failure and every UTC/monotonic value. Authenticated blocking collection, exact order, one-attempt ledgers, contiguous scoped receipts and nested durations establish separate serial accounting. Reconstructed UTC ends are diagnostic; suspension versus clock adjustment is unresolved. Actual uninterrupted calendar wall time remains unknown.

Recorded new subprocess elapsed is2759.079 monotonic seconds; ledger2105.664; qualification226.105. Historical 48 attempts have2748.141 recorded ledger seconds. These scopes overlap and must not be summed into elapsed wall time. No live adaptive-search or equal-wall-time advantage is established. Future runs need paired clock endpoints declared before collection. Never retry the completed pool or rewrite clock records.

Next: retain every fixed policy and investigate the specific area-feasibility misses before proposing one targeted model change; validate it on another untouched source under the same public information and budgets. Add constraint diversity rather than another isolated LUT study. Timing-boundary outcomes, calibrated uncertainty and jointly executed one-to-three-instruction sets remain missing. Reuse the reviewed teammate slot/overlap components only in a separately checked compatible context; do not sum individual gains/area or import RV32IM/external-RAM labels silently. LLM/demo and unrelated frameworks remain paused.

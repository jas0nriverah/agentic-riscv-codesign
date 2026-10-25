# Current handoff — measured bitcount transfer and feasible-selection failure

Read [README](../README.md), [AGENTS](../AGENTS.md), [bitcount commands and limits](bitcount-transfer.md), [primary methods](research-foundation.md) and [teammate compatibility](teammate-branch-review-2026-10-21.md). Branch: `ai-guided-ml`. GPT-6.1 Sol subagents reviewed the native boundary, controller, report/export and next-source feasibility. The [preceding complete handoff](HANDOFF-history-2026-10-22-pre-bitcount.md) preserves historical priorities and results. The owner canceled service/GCP work; cloud/API/demo/live LLM work remains paused.

**October 25 refinement:** [the new source-bound analysis](../results/2026-10-25-selection-analysis/README.md) reconstructs the frozen GP without new estimator fits or selector trajectories. Its 37-dimensional metric gives related queried adders only 0.006–0.014 posterior area correlation; each target retains at least 99.61% of prior variance. Fixed-current-GP conditional fantasies differ from the actual paid scaler/output-normalization refits. This qualifies the next lookahead recommendation below: first specify/test covariance, noise/units and the update procedure; compare one-step and two-step decisions using identical cycle-reduction utility and update rules. Lookahead is not a demonstrated cure. Keep all fourteen controls, plus a prespecified simple diversity/incumbent fallback control for attribution. All measured corpus counts/results below are unchanged.

## Completed engineering and measured data

**99 verified labels, three preserved failures, 102 charged attempts, twelve sources and thirteen contexts; 112 completed integrated processor designs and 336 routes including baselines.** Six sources are Embench, five BEEBS and one TACLeBench. Every context of a source belongs in the same held-out group. All twelve sources are now consumed development data. Original CRC32, aha-mont64, all negative results, rejected qualifications and earlier clock failures remain intact.

TACLeBench bitcount is the new independent source. Five unchanged pinned C files and an external ILP32 ABI/amalgamation adapter reuse the guarded extractor, assembly lowering and PicoRV32 PCPI evaluator. Original seed, eight population-count algorithms, ten inputs per algorithm and aggregate 1095 verifier are preserved. This declared amalgamated compilation is not an upstream separate-TU binary-identity claim. The original baseline executes **51,689 cycles / 10,319 instructions**. Forty raw / 37 executable formulas precede the twelve-candidate shortlist; the unchanged gate requires twelve formulas and one candidate meeting both 0.5% public estimated cycle reduction and ten timed replacements.

All twelve candidates pass the recorded-input self-check, instruction/control/handshake/memory checks, integrated synthesis/device recount and all three routing seeds. The target remains RV32I_zicsr/ILP32 `-Os`, 8 KiB integrated RAM, 6400/6528 partition, one-wait PCPI, 12 MHz and iCE40HX8K CT256. These are simulated processor and synthesis/routing results, not board measurements or arbitrary-input correctness proofs. All 99 measured cycle deltas agree with calibrated latency; no benefit-residual model is justified by this corpus.

## Frozen models and actual live search

Complete models, runtime, baseline, qualification and narrow proof amendment were pushed at **`7bbe3f7070e3b31ee4de9fe973c536cccf3aca03`** before release or any candidate measurement. All fourteen unchanged policies use the same **67 fitting rows from eleven historical sources** after target-source and exact/related-family exclusions. The available historical 87 successes and three failures remain charged once. No target candidate label was used in fitting.

The actual live semantic count-GP run uses seed 0, +64 LUT4, 12 MHz and three paid queries. Choices **00→14→11** and exact historical/paid-prefix model proofs are sealed before each dispatch. All three are correct but cost **+65/+77/+73 LUT4**, so the policy retains baseline. The completed live trace is sealed before nine separate reference candidates. Every attempt is charged once. Other policies use cooperative matched-budget replay, not independent native reruns or an OS sandbox.

At the primary +64-LUT4 / three-query endpoint:

| Policy | Mean verified cycle reduction | Reference hits / five dependent seeds |
| --- | ---: | ---: |
| Latency/cost heuristic | 0.174118% | 5 |
| Random | 0.094024% | 2 |
| Frequency | 0.092863% | 0 |
| XGBoost ranking | 0.055718% | 0 |
| Merit, calibrated latency, other learned policies | 0% | 0 |

The heuristic finds candidate 31: **51,689→51,599 cycles, 1.001744× speedup, +39 LUT4, minimum routed 67.783 MHz**. It is the exhaustive fixed-pool oracle at the declared primary cap. At +32, the oracle saves 48 cycles at +26 LUT4; at +128 it saves 450 cycles at +65 LUT4. Do not move the primary cap to 65 after seeing the labels. [Every candidate, resource, timing seed and policy budget](../results/2026-10-22-bitcount-report/results.md) is retained.

**This fresh-source result is negative for learned selection.** The preceding semantic-GP development gain on consumed AHA data is not a successful fresh transfer. One source and five dependent seeds do not establish broad generalization, significance or superiority. No model is promoted. Fixed three-query runs spend all three attempts; earlier reference attainment does not demonstrate automatic stopping.

## Reproduction and validation

Use Python 3.12 and `requirements-speedup.txt`; each derived output directory must be fresh:

```sh
make reproduce-bitcount PYTHON=python
make bitcount-report PYTHON=python
make export-bitcount-corpus PYTHON=python
```

All three commands pass without native jobs. Replay authenticates raw execution/hardware evidence, both prelabel Git packages, fifteen historical model refits, the initial semantic refit, the actual paid decision trace and **210 trajectories / 630 endpoint points / 126 summaries**. The frozen controller has a tuple-versus-JSON-list proof comparison issue. A separate amendment was itself pushed before measurements; it normalizes only the canonical-JSON-identical score representation. Numeric values, models, choices, outcomes and paid durations remain exact. Only explicitly named nondeterministic host timers are excluded, and archived/fresh endpoint arrays are both retained. Never edit frozen sources or native timings to pass replay.

[Final validation](../results/2026-10-22-bitcount-validation/README.md) retains logs, receipts and source bindings. All **50 focused tests pass**. The preceding full suite has **3,484 passes, 179 passing subtests and the unchanged legacy pipe-cleanup failure**; no cleanup fix or fully green suite is claimed. Historical six-model replay, both original processor replays and the two fixed count/semantic replays pass. New replay, reporting and corpus export all pass. Ensure ignored `.log` files referenced by manifests are actually tracked before pushing.

Evidence: [preregistration](../results/2026-10-22-bitcount-preregistration/cohort.json), [proof amendment](../results/2026-10-22-bitcount-proof-amendment/cohort.json), [native campaign](../results/2026-10-22-bitcount-campaign/provenance.json), [complete report](../results/2026-10-22-bitcount-report/results.md) and [99-label corpus](../results/2026-10-22-twelve-source-corpus/README.md). Native collection is complete: do not rerun qualification/release/collection or overwrite result roots.

## Accounting and next blocker

The twelve new attempts record **921.081198 ledger seconds**; all 235 native commands record **860.892178 seconds**, including baseline/discovery. The baseline ledger is **28.101971 seconds**. The complete collection CLI observer records **1064.975519 monotonic seconds**. Historical 90 attempts retain **5098.832466 ledger seconds**. These scopes overlap; do not add them or claim uninterrupted calendar-wall or total-cost savings. Repeated authentication refits are validation within CLI scopes; a single initial-fit receipt is not total fitting cost. Other-policy paid-duration sums are replay accounting, not measured live-search lifetimes.

The live GP's area standard deviations are about 22 LUT4, with chosen candidates' modeled area-feasibility probabilities around 0.56–0.59. This is broad, uncalibrated uncertainty; do not call it a narrow-confidence failure. The demonstrated decision problem is using a three-query budget to obtain a verified feasible incumbent while learning from related over-budget candidates.

The next method experiment remains **one fixed finite-pool two-step constrained-lookahead acquisition**, after the covariance/update contract above is verified, adapting the [reviewed 2-OPT-C method](research-notes-acquisition-2026-10-22.md) to known calibrated benefit. Fixed conditioning requires frozen preprocessing; preserving the actual empirical refit instead requires a declared rollout approximation. Do not treat those as the same update. Preserve all fourteen controls and the current model. Joint candidate covariance is required; independent marginal fantasies would not test information transfer. Freeze draw count, deterministic seeds, numerical integration, tie rules and host-cost accounting before development scoring. With three queries, a two-step receding horizon is an approximation, not an optimality guarantee. Treat this corpus as development, preserve losses, and validate on an untouched source before claiming improvement. No implementation or win for lookahead exists yet.

A read-only source scout identifies pinned TACLeBench `bench/sequential/g723_enc/g723_enc.c` as a plausible next independent pool: original 256 A-law samples and checksum 24284, approximately 2.2 KiB declared storage. Code/memory fit, helper compatibility, self-check, legal formulas and the unchanged opportunity gate are **untested**. Original-input `isqrt` is a lower-confidence alternative; do not retry known rejected contexts with weaker gates. The earlier eight-source BEEBS rejection and Prime helper-coverage limitation remain preserved; bitcount resolves the immediate useful-source connection without establishing arbitrary-binary rewriting.

Broader independent-source transfer, calibrated uncertainty, timing/device-fit failure boundaries and jointly executed one-to-three-instruction sets remain missing. Reuse the reviewed teammate slot/overlap components only in an explicit compatible context. Never sum individual gains or area increments. Keep RTL rewriting, model-version sweeps, live LLM, cloud and demo work outside this next experiment.

The collection observer records UTC 1064.988605 seconds versus monotonic 1064.975519 seconds, outside its paired capture bracket. Both raw observations and the unresolved clock-disagreement flag are retained; no timestamps are corrected and uninterrupted calendar wall time is not established.

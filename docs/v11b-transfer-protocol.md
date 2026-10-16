# V11b reserved-source transfer protocol proposal

Independent read-only design review, 2026-10-16. **Named amendment V11b-E1: READY FOR PARENT ADOPTION; not yet adopted or released.** This readiness applies to the endpoint definition, not runtime implementation readiness. The parent must explicitly adopt `V11b-E1` in a hash-bound approval and approve each later stage. This document authorizes no trace, feature extraction, prediction, target label or fit. It complements the [engineering recovery proposal](v11-transfer-recovery-plan.md); it does not replace the original reservation or its unsuccessful outcome.

## Preserved evidence and scientific endpoint

The reservation at commit `b6f1549ae2ef3f20f8a54511a6c3d13d865646e4` fixes TACLeBench `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`, six programs and five declared algorithm families. The original [input plan](../results/2026-10-15-v11-reserved-transfer/input-plan.json) has SHA256 `533fb31680e29cf3173c2bc93821a3a8d27063e96100ffd670a804be9a71d74c`.

| Family | Reserved program | Existing complete-window outcome |
|---|---|---|
| Arbitrary-precision bit strings | `ammunition` | Incomplete capture; no admitted pool |
| Audio beamforming | `audiobeam` | Complete; 169 canonical formulas |
| Numeric template matching | `pm` | Incomplete capture; no admitted pool |
| FM reception | `fmref` | Complete; 148 canonical formulas |
| Integer recurrences | `fac` | Complete; one canonical formula |
| Integer recurrences | `recursion` | Complete 1,181-commit ROI; zero eligible formulas |

The retained four complete outcomes contain 318 program/formula memberships and 196 distinct canonical originals. Those are coverage counts, not labels or model results. This review reauthenticated all seven portable ZIPs and all 229 member hashes against [raw-evidence-manifest.json](../results/2026-10-15-v11-reserved-transfer/raw-evidence-manifest.json), SHA256 `2639044e9019e49740da2746db8b8e19f69e83e137aa5a11310a453f0e5b400d`. It did not rerun their decoder, native selfchecks or candidate extraction, or rehash the two large local failed partials. Their original hash-addressed diagnosis and omission from portable ZIPs remain explicit.

**The original equal-family/equal-all-program area-MAE endpoint is undefined.** Recovery cannot create a formula MAE for the empty `recursion` program. Assigning zero error, silently dropping it, changing its workload or renaming `fac` as the whole original recurrence panel would misstate that endpoint. Both missing captures and the empty outcome remain published. The existing four-family feasibility gate was not met by the first attempt; the original result must not be retroactively relabeled successful.

## Proposed prelabel amendment: coverage plus eligible-program error

Amendment `V11b-E1` proposes two linked outcomes, with the changed error denominator explicitly named:

1. **All-six-program extractability coverage.** Report completion, validated retired-instruction count, canonical candidate count and failure/empty status for every reserved program, plus five-family coverage. Empty is a successful input outcome with unavailable formula error; timeout is incomplete, not empty.
2. **Five-family, equal-eligible-program MAE**, conditional on all six input outcomes being complete and every family having at least one nonempty eligible program. Let `U_p` be every distinct eligible canonical formula in complete program `p`; let `E_f` contain the nonempty programs in reserved family `f`. For fixed predictor `m`:

   `MAE_p(m) = sum_{u in U_p} abs(pred_m(u) - LUT4(u)) / |U_p|`

   `C(m) = (1/5) sum_f [sum_{p in E_f} MAE_p(m) / |E_f|]`

   The paired primary is `Delta = C(V9) - C(V6)`; negative favors V9. Report both scores and the absolute difference, not only a percentage.

Under the known empty recursion outcome, `fac` receives the full one-fifth recurrence-family weight rather than half of it. This is a substantive prelabel amendment motivated by observed input feasibility. It is not the original endpoint and is not prospective evidence about whether the extraction procedure succeeds. If either recovery fails, or any family has no eligible program, amended primary MAE is also unavailable. Any incomplete-panel descriptive result must show the missing denominator and remain secondary.

Within-program formulas receive equal weight; occurrences, instruction frequency and dynamic merit do not weight this primary. Deduplicate canonical originals within each program, retain every cross-program membership, and measure each globally shared canonical original once. Accepted semantic aliases are disclosed diagnostics, not permission to collapse distinct canonical originals or drop familiar functions. Pool-weighted MAE and occurrence-weighted analyses, if declared, are separate secondary endpoints.

## Immutable inputs and fixed predictors

Recover only AMMUNITION then PM, once each, using their original O2 ELF bytes. Authenticate and reuse the four complete original outcomes unchanged; no rerun seeking candidates for recursion, source swap, input edit, shorter ROI or helper exclusion. All six original O2 identities are recoverable from the authenticated ZIP member manifests:

```text
ammunition b48c44ebcea116d8779a09e41c648d73696e6ede520b84ecf21247cdd0c91e43
audiobeam  529cd32dc0dcce4fe4ff3c0e1587c4d9ff490157a6977c8f4769d5d66408910d
pm         a88d8f1096333ac233a40b0b0f671d0eb990360ed46d583cdf339723664529e8
fmref      dd7c04f1010a31325df175b7b552f236da5614f6e2f054e3fc7501d946552c03
fac        23bcfafcb31f814b981ca48e18ab9e5c17ddd0d1fcca04136bcb8c0782c7f83b
recursion  e97a73bf88547bab3431b525d688293fce2b1d789384b0da4132c1a6c271ac43
```

Preserve pinned sources, fixed inputs, compiler/runtime, full computation ROI including software-float and conversion helpers, original parser/counter/static boundaries, `maxSize=4`, `limit=None`, original eligibility barriers, and 16-vector fusion validation with seed `2026101507` and zero opaque skips. Original selfchecks, exact O0/O2 snapshots and meaningful program-specific output oracles remain mandatory; FMREF exit zero alone is insufficient.

The primary predictors are the existing **uncalibrated** mapping217 artifacts:

| Predictor | Artifact | Artifact SHA256 |
|---|---|---|
| V6 baseline | `results/2026-10-14-v6/models/mapping_v6.joblib` | `1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56` |
| V9 coverage model | `results/2026-10-15-v9-coverage-development/fit-attempt-0000/models/mapping-coverage.joblib` | `dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d` |

Both artifacts were byte-hashed for this review, not loaded or used for prediction. Before labels, bind their model metadata, selected columns, inference/runtime source closure, original-generic-zero override, feature tool identity and exact saved predictions for every admitted original. Freeze prediction ordering and require identical candidate membership. No fitting, adaptation, calibration, feature selection or threshold tuning from this panel. V13 fold models and V14 routed development results cannot replace this primary. No additional model controls are proposed.

## Novelty and fair interpretation

Use the authenticated **pre-reservation 2,929-original reference**, reconstructed from its bound historical inputs and accepted historical equivalence records, for the reservation novelty channel. Separately report membership/aliases against each frozen predictor's actual training rows. Keep canonical, accepted-equivalence and weaker skeleton/vector findings distinct; absence of a recorded alias is not a proof of semantic novelty. Do not use the later V13 ledger as the reference: it includes V11's exposed formulas and would compare the panel to itself.

Retain familiar and zero-area formulas in the primary. Show their counts and secondary errors, as well as application-symbol versus shared-helper attribution. These are five declared algorithms, not five independent source collections: FMREF/audiobeam share an ecosystem and numerical helpers can overlap consumed code. Review preprocessing/header/library ancestry and retain related-source findings rather than claiming independent algorithms from token nonmatches. Five deliberately chosen families support a bounded reserved-source comparison, not a population guarantee. Inputs were exposed before this amendment, although target labels remain withheld; describe the test as **reserved source-program transfer with frozen predictors and withheld labels**, not an untouched-input confirmation.

## Concrete release blockers and staged scope

The spooled helper alone is not an end-to-end released collector. Before recovery, a new adapter must bind the original evidence, both provenance/test amendments, all six ELF/snapshot/oracle identities, all source/import dependencies, compressor/Python/tool identity, fixed finite stage budgets and approval. It must own and monitor decoder and extractor children, enforce deadlines and disk/log/whole-attempt caps during every stage, retain primary and cleanup failures independently, and reject remaining owned children. Preserve failed capture/decode/extraction evidence under fresh immutable attempts; no implicit retry or budget extension. Existing synchronous decoder calls do not enforce their own wall deadline. The current 26 GiB initial free-space floor remains unchanged: evidence-preserving archival may free space, but starting below the floor or silently lowering it is not this amendment. Revalidate actual free space at release rather than treating a planned archive as available capacity.

Capture success is insufficient: require raw gzip CRC/EOF, exact full-stream marker/unknown-instruction/modulo32 count checks, unchanged output oracle and ELF hashes, unchanged extraction/fusion, and a complete per-stage status/hash manifest. No partial stream may supply a pool. A read-only package review must authenticate reused and recovered evidence, exact six outcomes, candidate/occurrence membership and provenance before feature or prediction authorization. Native compression provenance does not make the operating system hermetic; report that limit.

After full input recovery, freeze the complete pool and count unique target jobs. **Release a separate complete-pool physical budget before any labels**: target mapping/tool/data/RTL/verification contract, vector seed/count, workers/time/byte caps, one attempt, archived failures, and independent raw-output/netlist recount audit. The input recovery envelope in the engineering proposal is not an area-measurement release. If complete-pool cost is unaffordable, stop before labels and declare the primary unevaluated; no model ranking, candidate cap, frequency cut, easy-case selection or label-dependent replacement. A partial target run also leaves the full-pool primary unavailable; it does not authorize retrying failures until success.

Final paired reporting must retain full program/family denominators, pooled MAE, bias, RMSLE, zeros, p90/p95/p99, maximum underprediction and cap 32/64/128 false accepts/rejects with explicit counts. Keep isolated LUT4 prediction accuracy separate from CPU speed, timing, power or energy claims. This proposal is scientifically defensible if explicitly adopted before predictions/labels and the above implementation gates pass; it is **not yet a GO for native recovery or target collection**.

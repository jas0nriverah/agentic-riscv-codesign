# Research result archives

- [V10 paired hardware attempt](../docs/v10-csd-hardware-results.md): all 32 source proofs pass; 16 actual-RTL proofs pass and 16 time out, blocking all 64 area jobs. Raw evidence and independent audit retained.
- [Synthetic proof and timing preparation](2026-10-15-v10-hardware-preparation/README.md): standalone proof checker and fixed-register wrapper validation; no study result or timing route.

- [V11 reserved transfer input feasibility](2026-10-15-v11-reserved-transfer/README.md): 318 complete-pool rows from three programs, two incomplete traces and one empty pool. The reserved five-family primary remains incomplete; no new model features, predictions, targets or fits.

- [V9 training coverage](2026-10-15-v9-coverage-development/README.md): 48 new measured training circuits, one fixed fit, 25.40% consumed-application MAE reduction; independent raw and inference audits.

- [V9 adaptation development](2026-10-15-v9-adaptation-development/README.md): 1.94% remaining-case MAE reduction after three charged reveals per family; consumed development only.
- [Training support diagnosis](2026-10-15-development-diagnosis/README.md): archived leaf-level analysis with no new fits or labels.

These directories preserve completed experimental stages, including negative
results, model freezes, predictions, and measurement provenance. Read
[current conclusions](../docs/results.md) and [methodology](../docs/methodology.md)
before comparing scores across stages. A historical snapshot describes what
was known at that stage; later development can reuse its labels.

## Stage map

| Archive | Evidence and evaluation status | Entry point |
| --- | --- | --- |
| `2026-10-15-v8-application-transfer/` | Six point predictors frozen before146 original circuit measurements; four primary application families plus related-source secondary; complete errors and budgeted decisions | [V8 results and replay](../docs/v8-application-results.md) |
| `2026-10-14-development-semantics-v7/` | Six fixed feature views, 90 fits and 29,970 OOF predictions; proved transformations, independent metric replay and explicit cross-fold limitations; development only | [V7 results](../docs/v7-development-results.md), [portable evidence](2026-10-14-development-semantics-v7/evidence/REPRODUCE.md) |
| `2026-10-14-v6/` | Eight frozen predictors on 192 test circuits / 96 structural components after separate 192-circuit calibration; all original RTL and failures retained | [V6 evidence](2026-10-14-v6/README.md), [results](../docs/v6-results.md) |
| `2026-10-13/` | Original eight-program pilot: 339 program/formula rows, 301 distinct synthesized circuits; grouped model development and offline selection replay | [Pilot summary](2026-10-13/README.md) |
| `2026-10-13-prospective/` | Six-program transfer collection followed by a five-program final test using models frozen on the original 301 circuits; transfer labels subsequently calibrate the final acquisition policy | [Prospective and hardware summary](2026-10-13-prospective/README.md) |
| `2026-10-13-v3/` | Six matched-target predictors trained on the combined 713-formula development corpus; frozen evaluation on 192 novel synthetic circuits, including the MasterRTL recipe adaptation | [Six-model comparison](2026-10-13-v3/README.md) |
| `2026-10-13-v4/` | Semantics-aware V4 and same-data MasterRTL train on 1,289 circuits; new 256-circuit frozen holdout includes three unchanged historical comparators | [V4 results and replay](../docs/v4-results.md) |
| `2026-10-14-v5-external/` | Six frozen models on 80 application-derived rows / 79 measured original circuits; input overlap and all failures retained | [External results](../docs/external-v5-results.md) |
| `2026-10-14-v5/` | Four equally tuned feature views fit 1,665 circuits, reserve 392 for calibration, and compare six frozen predictors on 256 new circuits | [V5 results](../docs/v5-results.md) |

The [post-V5 development diagnostics](2026-10-14-development-diagnostics/README.md) retain 75 fitting-only seed runs and an exact-output inference optimization. These are development/runtime results, not a replacement independent test.

The three workload collections together cover all 19 pinned Embench programs,
with 1,098 program/formula occurrences and 713 unique circuits. Two transfer
programs have no legal candidates, so candidate-bearing program counts total
17. The 192-formula probe is a separate synthetic circuit source with eight
equal strata; it adds no executed workload.

## Find the evidence

| Question | Files |
| --- | --- |
| What was executed and measured in the pilot? | [Benchmark provenance](2026-10-13/benchmarks.json), [candidate summaries](2026-10-13/candidate-summary.json), [RTL verification](2026-10-13/verification.json), [mapped resource measurements](2026-10-13/synthesis-metrics.json) |
| What were the prospective prediction and selection outcomes? | [Transfer evaluation](2026-10-13-prospective/transfer/evaluation.json), [final evaluation](2026-10-13-prospective/final/evaluation.json), [frozen original-cohort models](2026-10-13-prospective/models/) |
| Were zero-candidate programs retained? | [Transfer coverage](2026-10-13-prospective/transfer/benchmarks.json), [zero-candidate diagnostics](2026-10-13-prospective/transfer/zero_candidate_diagnostics.json) |
| What changed in the integrated processor? | [Core cycle measurements](2026-10-13-prospective/core/crc32-measurements.json), [SoC measurements](2026-10-13-prospective/soc/measurements.json), [matched SoC routing](2026-10-13-prospective/soc/routing-summary.json) |
| Which six-model inputs and artifacts were frozen? | [Five-model preregistration](2026-10-13-v3/models/preregistration.json), [MasterRTL preregistration](2026-10-13-v3/masterrtl/preregistration.json), [probe freeze](2026-10-13-v3/probe/freeze.json), [predictions and timing sidecars](2026-10-13-v3/probe-inference/) |
| What supports the final matched comparison? | [Probe scores](2026-10-13-v3/probe-evaluation.json), [verified labels](2026-10-13-v3/probe/dataset.json), [collector audit](2026-10-13-v3/probe/collector_checks.json), [independent numerical audit](2026-10-13-v3/independent-audit.txt), [full error and bootstrap data](2026-10-13-v3/independent-audit.json) |

The v3 development folder contains both a readable evaluation summary and a
compressed full evaluation with detailed inner-fold records. They are distinct
representations, not interchangeable duplicate files. Artifact schemas and
preregistrations retain their original hashes and provenance paths.

## Interpret stage labels

The transfer and final workload sets were held out from the earlier models
trained on 301 formulas. All their labels become development data in the later
713-formula matched comparison. The earlier deployment refit is recorded as
untested at its historical stage; the later probe evaluates the full-cohort
resource model alongside the other five matched predictors.

LUT4 labels describe isolated combinational circuits. Instruction-saving
selection scores do not measure CPU cycles. Integrated CRC32 cycles come from
RTL simulation, and routed runtime ratios depend on timing-model assumptions;
they are not physical-board measurements. The MasterRTL comparison retrains a
published recipe on the shared LUT4 target and synthetic probe, rather than
replicating the paper's ASIC benchmark.

## Replay or recollect

Use the [matched reproduction guide](../docs/reproduce-matched-comparison.md) to
replay tracked scores, the independent bootstrap audit, and figures. Use the
[workload and processor reproduction guide](../docs/reproduce-research.md) for
earlier frozen-model inference or fresh measurement collection.

Bulky traces, toolchains, circuit logs/netlists, and the MasterRTL SOG cache are
outside tracked Git files. The evidence archive supplies selected retained
hardware artifacts and the complete SOG cache; the guides explain where to put
them and which external tools are needed. Preserve frozen files when replaying:
write new outputs under `generated/` or `work/`.

[Fixed-router development study](2026-10-14-development-router/README.md): two predeclared input-only gates on existing fitting-only OOF predictions; all controls and seeds retained.

[Mapping-feature development study](2026-10-14-development-mapping/README.md): fixed 23-descriptor ablation, 30 matched fits, all three seeds and nine strata. Development only; fresh V6 validation is a separate lineage.

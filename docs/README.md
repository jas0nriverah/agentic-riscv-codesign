# Documentation

[Project scope contract](../README.md) · [Agent instructions](../AGENTS.md) · [Current handoff](HANDOFF.md)

- [October 20 methods review](selection-methods-review.md): six additional primary methods and their precise adaptation limits.
- [Full speedup-model diagnosis](model-analysis.md): measured failure mechanisms, independent latency calibration, stronger baseline, new public features, and a prospective improvement plan.
- [Fixed ranking and automatic CRC32 results](selection-pilot-results.md): 420 development outcomes, poor uncertainty coverage, nine preserved fit failures, and the next data blocker.
- [Automatic workload milestone](automatic-workloads.md): actual aha-mont64 extraction, lowering, program execution, hardware results, and reproduction.
- [Established methods and research decisions](research-foundation.md): primary publications, algorithm assumptions, feasible baselines, and remaining gaps.
- [Current methodology](methodology.md): measured endpoints, whole-workload splits, fair budgets, and joint-set validation.
- [Preserved CRC32 selection study](codesign-loop.md): six candidates and the negative learned-versus-merit result.
- [Repository alignment review](scope-review.md): completed cleanup, remaining engineering gaps, and next experiment.

## Historical evidence and earlier roadmaps

All versioned cost-model studies, old directions, diagrams, and literature notes below are historical evidence. Their statements about the next model or current priority are superseded by the scope contract. Preserve their measurements and negative results; do not resume their roadmaps automatically.

[V15 scoped model and diagram](v15-scoped-results.md) — 32-circuit prospective stress, improvement and underprediction regression.


[Historical: completed 327-circuit comparison](v11e-transfer-results.md) — full measurements, negative transfer result, research figures and replay.


[Historical project handoff](HANDOFF-history-2026-10-19.md) — verified checkpoint, unfinished work and retained data.

- [V11c complete input collection](../results/2026-10-16-v11c-dtc-recovery/README.md): all six outcomes, 521 memberships and 327 originals; independent raw replay pending, no new model score.

- [Team progress brief — October 16](team-progress-2026-10-16.md): current model, measured gains, tradeoffs and next evaluation.
- [V11c environment correction](v11c-environment-amendment.md): pinned device-tree compiler, verified startup and frozen original transfer inputs.

- [V11b recovery outcome](../results/2026-10-16-v11b-transfer-recovery/STATUS.md): both captures failed at Spike startup; no new ML evidence, with the failure independently audited.

- [ML model overview](ml-model.md): an editable diagram of the 217-feature, 300-tree predictor and its measured improvement process.
- [V14 exploratory structural route](v14-specialist-results.md): retains all original control predictions while improving new coverage; no fresh-transfer or deployment claim.
- [V13 regression diagnosis](v13-regression-diagnosis.md): where global augmentation changed predictions and why the structural route was investigated.
- [Specialization research](research-specialization-2026-10-16.md): five primary sources, the fixed gate hypothesis and its evaluation limits.
- [V11 transfer recovery design](v11-transfer-recovery-plan.md): original bounded compressed tracing design and explicit endpoint limitations; see the later V11b/V11c records for execution status.
- [V13 targeted coverage results](v13-coverage-results.md): 48 new measurements and 30 matched fits; new coverage improves but original-cohort primary error worsens 5.16%, so V9 is retained.
- [V12 target-scale results](v12-target-transform-results.md): 30 matched fits; log targets lower MAPE but worsen MAE and over-budget acceptance, so raw-target fitting is retained.

- [Hardware tradeoff ledger](hardware-tradeoffs.md): resource costs, feasibility mistakes, processor timing evidence and unmeasured quantities.
- [Completed CSD timing study](v10d-timing-results.md): common registered wrapper, 192 routes and explicit timing-attribution limits.
- [Reserved transfer input feasibility](../results/2026-10-15-v11-reserved-transfer/README.md): all six first attempts, two incomplete traces and an empty pool; no new model evaluation.

- [V9 training coverage](v9-coverage-results.md): one fixed 48-circuit augmentation, 25.40% consumed-application MAE reduction, all tradeoffs and independent replay.

- [V9 adaptation development](v9-adaptation-results.md): fixed paid-label correction, independent arithmetic audit and publication figure.
- [Training coverage diagnosis](v9-training-coverage-direction.md): tree-level evidence and fixed augmentation direction.

Start with [methodology](methodology.md) for the experimental design and
[results](results.md) for the conclusions and limitations. The
[result archive index](../results/README.md) identifies the evidence belonging
to each stage; the [repository overview](../README.md) provides installation
and entry points.

The project measures three different things: isolated FPGA resource counts,
instruction-saving acquisition decisions, and integrated processor cycles and
routing estimates. Keep their evidence and conclusions separate. The generic
demo uses synthetic performance labels; the later formula probe uses actual
RTL synthesis of synthetic expressions.

## Follow the research workflow

| Task | Read |
| --- | --- |
| Choose measured implementations under explicit resource and clock caps | [Selection policy and CLI](v10d-selection-policy.md), [all decisions](../results/2026-10-15-v10d-selection/README.md) |
| Compare all 192 routed arms and resource/timing tradeoffs | [V10d timing results](v10d-timing-results.md), [timing protocol](v10d-timing-protocol.md) |
| Inspect all 32 verified original/CSD hardware pairs and carry tradeoffs | [V10 hardware results](v10-csd-hardware-results.md), [V10d protocol](v10d-csd-hardware-protocol.md) |
| Execute pinned Embench programs and reconcile Spike traces | [Toolchain and workload collection](toolchain.md) |
| Extract legal two-input, one-output instruction groups and verify substitutions | [Candidate contract](candidates.md) |
| Generate RV32 RTL, check its outputs, and measure isolated LUT4 resources | [RTL verification and synthesis](synthesis.md) |
| Understand formula predictors and grouped model evaluation | [Methodology](methodology.md), [v1 model](area-model.md), [v2 resource and residual models](area-model-v2.md) |
| Replay complete application-pool transfer and selection outcomes | [V8 application results](v8-application-results.md), [frozen protocol](v8-application-pilot-protocol.md) |
| Inspect the earlier fitting-only semantic ablation and its limitations | [V7 development results](v7-development-results.md), [pre-score protocol](v7-development-protocol.md) |
| Evaluate a fixed measurement budget over a measured candidate pool | [Area selection](area-selection.md) |
| Reproduce the six-model comparison and independent error audit | [Matched comparison reproduction](reproduce-matched-comparison.md) |
| Reproduce historical V4, inspect its remaining failures, or run frozen inference | [V4 results and replay](v4-results.md), [frozen protocol](v4-protocol.md) |
| Replay the latest mapping-feature experiment and inspect its failures | [V6 results](v6-results.md), [reproduction and inference](v6-reproduction.md), [frozen protocol](v6-protocol.md), [optional descriptor cache](v6-cached-inference.md) |
| Audit external program transfer and restore raw synthesis evidence | [External results](external-v5-results.md), [evaluation protocol](external-v5-evaluation.md), [collection protocol](external-v5-protocol.md) |
| Replay V5, inspect matched feature ablations and calibration failures | [V5 results](v5-results.md), [reproduction](v5-reproduction.md), [protocol](v5-protocol.md), [research direction](research-direction-v5.md) |
| Integrate custom instructions and distinguish cycles from clock estimates | [Processor experiment](../hardware/README.md), [closed-memory SoC](soc-integration.md) |
| Connect newer research to concrete next experiments | [Transfer and labeling budgets](research-update-2026-10-15.md), [representation cost and processor-aware selection](research-update-2026-10-14.md), [mapping-feature development](v6-development-direction.md) |

The [general data contract](data-contract.md), [performance-model interface](model.md),
and [general selection interface](selection.md) also support future measured
cycle/clock experiments. Their synthetic demo is distinct from the measured
LUT4 research pipeline.

## Reproduce a result

- [Measured workload and processor reproduction](reproduce-research.md):
  original/prospective model replay, recollection, and core/SoC experiments.
- [Matched comparison reproduction](reproduce-matched-comparison.md): all six
  frozen predictors, strict score replay, bootstrap audit, and figure generation.
- [Core routing](core-routing.md) and [SoC routing](soc-routing.md): matched FPGA
  settings, clock assumptions, seeds, and conditional runtime estimates.

For a quick audit using tracked inputs, run
`python -m isaforge.probe_audit --output-prefix generated/audit-replay/independent-audit`
from an installed checkout. Saved-score replay and this audit require no hardware
recollection. New MasterRTL formulas require compatible Yosys preprocessing;
warm inference requires its complete evidence cache. The matched reproduction
guide describes those dependencies explicitly.

## Frozen protocols

These documents retain the decisions made before their associated tests.
Later experiments do not replace the earlier protocols or historical outcomes.

| Stage | Protocol and collection notes |
| --- | --- |
| First prospective workload test | [Fresh evaluation protocol](fresh-evaluation-protocol.md), [holdout collection](holdout-collection.md) |
| Final workload/policy test | [Final policy protocol](final-policy-protocol.md) |
| Synthetic circuit stress test | [Probe acquisition and verification protocol](probe-protocol.md) |
| Matched published-recipe adaptation | [MasterRTL adaptation protocol](masterrtl-matched-protocol.md) |

## Historical context

- [Prospective research manuscript](research-manuscript.md) describes the
  workload/policy and processor stages before the later six-model probe.
- [Related-work comparison and design rationale](research-model-comparison.md)
  explains the literature that motivated the structural revision. Use the
  [current results](results.md) to assess that revision's measured outcome.

Historical reports and refits have stage-specific meanings. A dataset that was
held out in an earlier experiment can be development data for a later model;
the result archive index makes those transitions explicit.

Development hypotheses and literature: [V6 conditional routing and mapping descriptors](v6-development-direction.md). These fitting-only diagnostics do not replace frozen test results.

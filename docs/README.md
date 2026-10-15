# Documentation

- [Hardware tradeoff ledger](hardware-tradeoffs.md): resource costs, feasibility mistakes, processor timing evidence and unmeasured quantities.

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
| Execute pinned Embench programs and reconcile Spike traces | [Toolchain and workload collection](toolchain.md) |
| Extract legal two-input, one-output instruction groups and verify substitutions | [Candidate contract](candidates.md) |
| Generate RV32 RTL, check its outputs, and measure isolated LUT4 resources | [RTL verification and synthesis](synthesis.md) |
| Understand formula predictors and grouped model evaluation | [Methodology](methodology.md), [v1 model](area-model.md), [v2 resource and residual models](area-model-v2.md) |
| Replay complete application-pool transfer and selection outcomes | [V8 application results](v8-application-results.md), [frozen protocol](v8-application-pilot-protocol.md) |
| Inspect the latest fitting-only semantic ablation and its limitations | [V7 development results](v7-development-results.md), [pre-score protocol](v7-development-protocol.md) |
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

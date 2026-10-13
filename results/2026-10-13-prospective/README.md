# Prospective inference and processor results

All 19 pinned Embench programs passed their self-checks and trace reconciliation.
Three collections contain 1,098 benchmark/formula rows and 713 distinct circuits.
The original eight-program pilot is under `../2026-10-13/`.

## What changed after the original pilot

- `models/`: frozen structural linear and residual-XGBoost models fitted only on
  the original 301 circuits, with source/artifact hashes and packaging-migration audit.
- `transfer/`: six prospective programs,198 rows/167 circuits. Two control-heavy
  programs produced no safe candidates.81 distinct formulas were new to training.
- `policy/`: program-level empirical rejection margin calibrated on the first
  prospective group and frozen before final labels were inspected.
- `final/`: five final programs,561 rows/453 circuits;331 formulas were absent
  from both training and calibration. Full candidate pools were measured.
- `core/`: actual PicoRV32 PCPI integration, recurrence latency sweep, complete
  CRC32 port, and whole-core synthesis; external zero-wait memory.
- `soc/`: subsequent closed system with initialized 8 KiB synchronous on-chip
  memory, actual CRC execution, whole-SoC synthesis, and matched FPGA routing.
- `deployment/`: structural model refitted on all 713 formulas after evaluation.
  This deployment artifact has **no independent test of the refit**. Its
  inference smoke output is not a held-out score.

All inference JSON includes candidate identities and actual frozen-model
predictions. Timing files record model load and 20 warm batches. Inputs to
inference are formula and identity only. Raw RTL, netlists, logs, verification
vectors, firmware, pin constraints and routed configurations are in the
separate evidence archive; traces/toolchains are not committed.

## Results that matter

| Final 331 novel formulas | MAE, LUT4 | RMSLE | Spearman |
| --- | ---: | ---: | ---: |
| Original XGBoost |87.595|0.755|0.926|
| Structural linear model |23.154|0.409|0.934|
| Structural plus XGBoost residual |33.165|0.450|0.931|

The simpler structural model is strongest on this final set. On the first
transfer set, residual XGBoost had lower MAE but the structural model had lower
RMSLE. Both results and all per-program metrics remain visible.

At the primary 64-LUT/one-measurement endpoint, all models and merit retain 100%
of final-pool oracle instruction savings. Frequency retains 92.4%; random 6.3%.
This is **not superiority over merit**. The first prospective test was a loss
for point-model selection:85.5% versus merit 100%. Historical training/calibration
measurements are outside these target budgets, and the oracle is retrospective.

Closed-memory CRC cycles fall from 32,387,382 to 29,602,102 (8.60% fewer;1.0941×
cycle ratio). Whole-SoC LUT4 changes from 1,633 to 1,704; both use 20 BRAMs. All six
matched nextpnr runs fit HX8K/CT256 and pass 12 MHz. Per-seed cycle/Fmax estimates
show 1.022×,1.041×,1.140× runtime ratios. These are post-route timing-model
estimates, not measurements on a physical board. Reset/status external timing
and board operation remain assumptions.

## Reproduce inference without rerunning hardware

Install the source package using the dependency versions recorded in model
schemas for reliable loading. From the repository root:

```sh
python -m isaforge.frozen_inference \
  --model results/2026-10-13-prospective/models/resource-ridge.joblib --kind v2 \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/replay/resource.json
python -m isaforge.area_model_v2 predict \
  --model results/2026-10-13-prospective/deployment/resource-deployment.joblib \
  --candidates results/2026-10-13-prospective/final/dataset.json \
  --output generated/deployment-smoke.json
```

The first command reproduces frozen test inference; the second exercises the
all-data deployment model and must not be scored as a new holdout. See the
[manuscript](../../docs/research-manuscript.md),
[reproduction guide](../../docs/reproduce-research.md),
[prospective protocol](../../docs/fresh-evaluation-protocol.md), and
[final policy protocol](../../docs/final-policy-protocol.md).

## Limits

LUT4 is one FPGA resource, not physical area or energy. Predictor outputs do not
estimate integrated CPU speedup. One-candidate savings do not solve multi-pattern
overlap or combined hardware costs. No LLM selection comparison or matched
reproduction of CIDRE/ARISE is completed. Program samples are small/correlated;
bootstrap intervals are descriptive. The dataset/pipeline and negative results
are research evidence, not a claim of outperforming published systems.

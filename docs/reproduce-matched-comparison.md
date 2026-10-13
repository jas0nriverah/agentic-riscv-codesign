# Reproduce the six-model matched comparison

The frozen MasterRTL SOG adaptation achieved the lowest primary error on this probe: **35.0687 LUT4 MAE**, compared with 41.5933 for the v2 residual model and 56.4018 for the structural v3 challenger. This establishes the result for the declared synthetic probe and isolated iCE40 LUT target. It does not establish superiority on real workloads, processor performance, or MasterRTL's published ASIC-area task.

All six artifacts were fitted on the same **713 unique formulas**, drawn from **1098 formula/program occurrences across 17 programs**. Those 17 programs are development data: their labels were already inspected. V3 uses nested program holdouts for candidate selection, excluding every matching validation/test formula from the remaining training programs. The MasterRTL adaptation uses its fixed public estimator recipe and the same outer holdouts without model selection. Final fits give each unique formula one training weight.

The fresh probe contains **192 canonically novel formulas**, with **24 formulas in each of eight declared strata**. Its labels include **181 positive LUT counts and 11 zeros**. Every candidate has oracle verification and an actual Yosys iCE40 synthesis label. Canonical novelty excludes identical formulas; it does not imply semantic independence or independent real applications.

## Frozen probe result

The primary endpoint is macro-stratum MAE. Because every stratum has exactly 24 samples, it equals pooled MAE up to floating-point rounding. RMSLE uses `log1p` and includes zero targets. Positive MAPE includes only the 181 positive labels; the 11 zero labels have a separate MAE column.

| Frozen model / score key | Primary MAE, LUT4 | RMSLE | Positive MAPE, % | Pearson | Zero-target MAE, LUT4 |
|---|---:|---:|---:|---:|---:|
| MasterRTL SOG adaptation / `masterrtl_sog` | 35.0687 | 0.4943 | 36.5042 | 0.9196 | 3.3961 |
| V2 residual XGBoost / `v2_residual_xgb` | 41.5933 | 0.8076 | 320.1410 | 0.9236 | 6.5943 |
| V3 structural challenger / `v3_structural` | 56.4018 | 0.8388 | 478.1287 | 0.9117 | 14.9803 |
| V2 resource prior / `resource_v2` | 60.7228 | 0.9297 | 514.2029 | 0.9434 | 14.4997 |
| V3 original-feature ablation / `v3_original` | 60.7228 | 0.9297 | 514.2029 | 0.9434 | 14.4997 |
| V1 formula XGBoost / `v1_xgboost_log` | 80.8586 | 1.2388 | 165.8149 | 0.7650 | 105.4079 |

The original-feature ablation selected the unchanged v2 resource model, so its point predictions equal `resource_v2`. Both rows remain in the comparison. Pearson correlation measures association and can remain high when absolute or relative errors are large.

The large MAPE values are retained. MAPE divides each error by its own positive target, so errors on one- or few-LUT implementations can dominate the average. Multiplication is especially difficult: positive-label MAPE in that stratum is 2369.2697% for v2 residual, 3860.7234% for structural v3, and 143.3344% for the MasterRTL adaptation. The full-stratum multiplication MAEs are 246.2298, 376.8695, and 203.5133 LUT4 respectively. These failures are part of the test, not excluded outliers. MAPE is not an accuracy percentage, and `100 − MAPE` is not reported.

The machine-readable result, all per-stratum scores, and provenance are in [probe-evaluation.json](../results/2026-10-13-v3/probe-evaluation.json). All six prediction files and timing sidecars are in [probe-inference](../results/2026-10-13-v3/probe-inference/).

## Freeze and adaptation record

The candidate protocol froze at **2026-10-13 05:58:35 UTC**. The five original/v3 artifacts froze at **06:08:10 UTC**, and the MasterRTL artifact froze at **06:20:14 UTC**. The first matched scoring record is **06:25:30 UTC**. The model sources, weights, predictions, and protocols were committed before label release in `f62a167`. No model, grid, or feature changes follow probe scoring. Timestamps and hashes document consistency and ordering; they cannot independently prove that nobody previously accessed labels.

The normalized shared training-data SHA256 is:

```
e0f55ec99ecc65772c4c55368a860d38aabe219853cdef87b17670d3b41f6d5f
```

Both [model preregistration](../results/2026-10-13-v3/models/preregistration.json) and [MasterRTL preregistration](../results/2026-10-13-v3/masterrtl/preregistration.json) record that same training cohort. They include artifact and runtime-source hashes. The [probe freeze](../results/2026-10-13-v3/probe/freeze.json) records candidates, seed, strata, and canonical exclusions; its completion record binds the complete measured dataset to that freeze.

The reference is [MasterRTL commit 5bccf38](https://github.com/hkust-zhiyao/MasterRTL/tree/5bccf38f8db7bb511a793a709863e7cb1b333ab5). Its 14 analytical SOG features and raw-target XGBoost recipe—25 estimators, depth 12—are retrained on the shared LUT target. Direct one-bit Yosys JSON counting replaces the authors' Pyverilog graph parser. Combinational candidates have zero DFF/register-fanout/sequential-area features and 96 declared IO bits. Native generated Verilog replaces Verific; worker threads change from 20 to 1, with a fixed seed. Unspecified estimator defaults belong to the recorded installed library version. This is a matched-target recipe adaptation, not a reproduction of the paper's ASIC-area model, dataset, or score. Exact changes and reference file hashes are documented in [masterrtl-matched-protocol.md](masterrtl-matched-protocol.md).

## Runtime requirements and cache

Run commands from the repository root. The artifact schemas record these package versions: NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, XGBoost 3.4.1, and joblib 1.6.0. Use Python 3.11 or newer. A fresh environment can be prepared with:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . numpy==2.5.4 scipy==1.18.1 scikit-learn==1.9.1 xgboost==3.4.1 joblib==1.6.0
```

Scoring the saved prediction files requires neither Yosys nor the SOG cache. Inference for the five formula models also needs neither. MasterRTL cached inference requires the complete retained SOG cache, distributed in the evidence archive at:

```
source/results/2026-10-13-v3/masterrtl/sog-cache/
```

Inside the archive's `source/` repository, this cache is alongside `masterrtl-sog.joblib`. For a separate Git checkout, copy that directory to `results/2026-10-13-v3/masterrtl/sog-cache/` before running all six inference commands. Its approximately 327 MB of RTL, scripts, logs, Verilog, and JSON graphs is intentionally outside tracked Git files. The loader resolves the cache relative to the artifact, verifies retained-file hashes, and rederives features from each JSON graph; it does not reuse the original absolute machine path.

A complete cache permits replay without executing Yosys. An uncached formula requires the frozen tool version and binary hash, because a different Yosys build can change the features. The frozen tool is Yosys 0.69+post, Git SHA `143eb14f9cc55d6f8927e68523b0c9d2166ed02c`; its executable SHA256 is:

```
1222a95c90c84f66238b0a5ecb8b228bf787318cf1c412b41363e26ace5544cf
```

The pre-ABC feature flow uses `proc; flatten; opt; fsm; opt; memory; opt; techmap; opt`. It does not run ABC or iCE40 mapping to produce inference features. The test labels use separate actual iCE40 mapping.

## Replay the saved strict score

The following command uses only tracked result inputs and saved predictions. It checks both completed model freezes, equal training cohorts, current frozen runtime sources, artifact hashes, prediction timing-sidecar hashes, complete candidate identity coverage, verified synthesis labels, and canonical novelty. All and only the six frozen comparators must be supplied.

```sh
.venv/bin/python -m isaforge.probe_evaluation \
  --training results/2026-10-13/dataset.json \
  --training results/2026-10-13-prospective/transfer/dataset.json \
  --training results/2026-10-13-prospective/final/dataset.json \
  --probe results/2026-10-13-v3/probe \
  --model-freeze results/2026-10-13-v3/models/preregistration.json \
  --model-freeze results/2026-10-13-v3/masterrtl/preregistration.json \
  --predictions resource_v2=results/2026-10-13-v3/probe-inference/resource_v2.json \
  --predictions v1_xgboost_log=results/2026-10-13-v3/probe-inference/v1_xgboost_log.json \
  --predictions v2_residual_xgb=results/2026-10-13-v3/probe-inference/v2_residual_xgb.json \
  --predictions v3_original=results/2026-10-13-v3/probe-inference/v3_original.json \
  --predictions v3_structural=results/2026-10-13-v3/probe-inference/v3_structural.json \
  --predictions masterrtl_sog=results/2026-10-13-v3/probe-inference/masterrtl_sog.json \
  --output work/replay/saved-probe-evaluation.json
```

The numerical scores should match the archived report; the new scoring timestamp and provenance paths will differ.

## Run all six frozen predictors, then score

After placing the evidence cache as described above, this script runs each canonical loader against the same label-free candidate file. The runner removes measurements and passes only benchmark, candidate ID, and formula. It records a first batch plus 20 deterministic warm batches and writes timing sidecars required by the scorer. It does not retrain anything.

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess
import sys

root = Path('results/2026-10-13-v3')
models = [
    ('resource_v2', 'v2', 'models/resource-v2-full.joblib'),
    ('v1_xgboost_log', 'v1', 'models/v1-full/area-model.joblib'),
    ('v2_residual_xgb', 'v2', 'models/area-model-v2-full.joblib'),
    ('v3_original', 'v3', 'models/area-model-v3-original.joblib'),
    ('v3_structural', 'v3', 'models/area-model-v3.joblib'),
    ('masterrtl_sog', 'masterrtl', 'masterrtl/masterrtl-sog.joblib'),
]
for name, kind, artifact in models:
    subprocess.run([
        sys.executable, '-m', 'isaforge.frozen_inference',
        '--kind', kind, '--model', str(root / artifact),
        '--candidates', str(root / 'probe/candidates.json'),
        '--output', f'work/replay/predictions/{name}.json',
    ], check=True)
PY

.venv/bin/python -m isaforge.probe_evaluation \
  --training results/2026-10-13/dataset.json \
  --training results/2026-10-13-prospective/transfer/dataset.json \
  --training results/2026-10-13-prospective/final/dataset.json \
  --probe results/2026-10-13-v3/probe \
  --model-freeze results/2026-10-13-v3/models/preregistration.json \
  --model-freeze results/2026-10-13-v3/masterrtl/preregistration.json \
  --predictions resource_v2=work/replay/predictions/resource_v2.json \
  --predictions v1_xgboost_log=work/replay/predictions/v1_xgboost_log.json \
  --predictions v2_residual_xgb=work/replay/predictions/v2_residual_xgb.json \
  --predictions v3_original=work/replay/predictions/v3_original.json \
  --predictions v3_structural=work/replay/predictions/v3_structural.json \
  --predictions masterrtl_sog=work/replay/predictions/masterrtl_sog.json \
  --output work/replay/frozen-inference-probe-evaluation.json
```

## Recorded latency

These local CPU measurements cover the same 192 candidates. Warm medians are from the archived 20-repeat inference sidecars. They exclude process startup, model loading, and input/output JSON serialization. The MasterRTL row includes cache IO, integrity checks, and primitive-graph traversal as well as ML prediction.

| Model | Median warm batch, milliseconds |
|---|---:|
| `resource_v2` | 5.044 |
| `v1_xgboost_log` | 2.854 |
| `v2_residual_xgb` | 15.566 |
| `v3_original` | 10.261 |
| `v3_structural` | 47.125 |
| `masterrtl_sog` | 204.801 |

A separate same-artifact, same-192-input MasterRTL run started with an absent cache: **7.4315 seconds cold feature-plus-ML**, then **0.2128 seconds warm**, with identical predictions. Model load was 0.0273 seconds. That cold inference used one extraction worker. Initial preparation of all 905 training/probe-input graphs took 18.3901 seconds with two workers; it is a different batch and is not substituted for 192-input latency. See [cold-probe-timing.json](../results/2026-10-13-v3/masterrtl/cold-probe-timing.json). These measurements describe this machine and cache state, not universal throughput or hardware acceleration.

## Reproduce the independent audit and research figures

The audit recomputes the frozen scores and paired formula bootstrap from tracked inputs. It does not refit or select a model. Its replay differs from the archived JSON only in the creation timestamp.

```sh
.venv/bin/python -m isaforge.probe_audit \
  --output-prefix generated/audit-replay/independent-audit
```

Figure replay reads the tracked evaluation reports, predictions, timing records and independent audit. It requires neither synthesis nor model inference. Install the plotting dependency, then run the exact recorded invocation below; change only the output directory for another checkout.

```sh
.venv/bin/python -m pip install -e '.[reports]'
.venv/bin/python -m isaforge.challenger_plots \
  --development results/2026-10-13-v3/models/development-evaluation.json \
  --reference-development results/2026-10-13-v3/masterrtl/development-evaluation.json \
  --probe results/2026-10-13-v3/probe-evaluation.json \
  --probe-dataset results/2026-10-13-v3/probe/dataset.json \
  --prediction resource_v2=results/2026-10-13-v3/probe-inference/resource_v2.json \
  --prediction v1_xgboost_log=results/2026-10-13-v3/probe-inference/v1_xgboost_log.json \
  --prediction v2_residual_xgb=results/2026-10-13-v3/probe-inference/v2_residual_xgb.json \
  --prediction v3_original=results/2026-10-13-v3/probe-inference/v3_original.json \
  --prediction v3_structural=results/2026-10-13-v3/probe-inference/v3_structural.json \
  --prediction masterrtl_sog=results/2026-10-13-v3/probe-inference/masterrtl_sog.json \
  --timing resource_v2=results/2026-10-13-v3/probe-inference/resource_v2.timing.json \
  --timing v1_xgboost_log=results/2026-10-13-v3/probe-inference/v1_xgboost_log.timing.json \
  --timing v2_residual_xgb=results/2026-10-13-v3/probe-inference/v2_residual_xgb.timing.json \
  --timing v3_original=results/2026-10-13-v3/probe-inference/v3_original.timing.json \
  --timing v3_structural=results/2026-10-13-v3/probe-inference/v3_structural.timing.json \
  --timing masterrtl_sog=results/2026-10-13-v3/probe-inference/masterrtl_sog.timing.json \
  --masterrtl-cold-timing results/2026-10-13-v3/masterrtl/cold-probe-timing.json \
  --independent-audit results/2026-10-13-v3/independent-audit.json \
  --output generated/research-figures
```

The nine figures are exported as editable SVG, vector PDF and 300 dpi PNG. `figure-data.json` retains complete plotted observations, intervals, runtime versions and SHA-256 provenance; `README.txt` gives figure captions, and `invocation.json` records the exact command. The renderer checks matched development data/splits and hashes of the probe labels, predictions and independent audit.

Development error bars resample the 17 programs as descriptive program-mix sensitivity intervals. Probe paired-difference intervals instead resample candidate pairs within each of the eight fixed strata; neither programs nor strata are resampled for that audit. Both interpretations are stated in the captions. Figure 8 shows every stratum in linear and log(1 + MAE) views, while Figure 9 retains the residual-XGBoost comparison interval crossing zero. No plotted model is refitted after seeing probe labels.

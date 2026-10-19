# Pretrained models

| Directory | Training circuits | Description |
| --- | ---: | --- |
| `base/` | 1,665 | Default 300-tree, 217-feature ExtraTrees area predictor |
| `coverage/` | 1,713 | Same estimator and features, with 48 added arithmetic circuits |

Each contains a byte-identical `model.joblib` and adjacent `model.json` from the completed research artifacts. The metadata records dependencies, feature columns, source hashes and training provenance. Only trusted repository artifacts are loaded. `scripts/predict.py` verifies the exact artifact and metadata hashes before loading.

`scoped` is an experimental input-only policy over these two forests, not a third fitted model. Both produce uncalibrated isolated LUT4 estimates. [Architecture](../docs/model.md) · [Inference](../docs/reproduce.md) · [Registry](registry.json).

# Consumed measured corpus — six workloads

This export contains **33 verified automatic candidate labels across six source workloads**, with **three earlier failed attempts** preserved separately: 36 charged candidate attempts, 39 fully measured processor designs including six baselines, and 117 routing results. SHA256 adds six correct, fully measured candidates to the unchanged five-workload corpus. The original source-adapter CRC32 experiment is separate from these counts.

- `corpus.json` contains consistent public features, measured whole-program cycles/speedup, integrated hardware costs, contexts, attempt costs and failures.
- `verified-labels.csv` contains the same 33 successful rows; nested feature maps are JSON cells.
- `failed-attempts.csv` and the JSON failure records retain EDN's recorded memory-contract failure, UD's self-check failure and UD's infrastructure-censored attempt. The latter still has unknown correctness, performance and feasibility. No retry or fabricated label repairs the earlier campaign.
- `provenance.json` binds the exporter, authenticated historical corpus, frozen SHA256 selection/report and native evaluation protocol. `manifest.json` authenticates all files in this export.

The successful-label counts are six each for aha-mont64, CRC32, SLRE and nettle-sha256, five for EDN and four for UD. All six source workloads are now consumed data for later experiments. Compiler and memory partitions differ explicitly; neither random candidate splits nor revisions on these rows establish new source-family generalization.

The exporter authenticated the old native history, exactly refit the frozen predictions, and verified the complete SHA256 selection report before writing this new directory. The [older corpus](../2026-10-21-expanded-corpus/README.md) and all earlier evidence remain unchanged. Selection conclusions belong to the [SHA256 selection report](../2026-10-21-sha256-selection/report.json); adding rows is not evidence of an ML advantage.

Historical recorded candidate-attempt cost is **1,698.152954 seconds**. New SHA256 attempts cost **402.461094 seconds** on the persistent attempt ledger, yielding **2,100.614048 recorded seconds** across all 36 attempts. The old successful durations use the narrower measurement-record timer; new ledger durations include validation overhead. New successful measurement records sum to **251.904063 seconds**, retained separately through `measurement_record_seconds`. These two SHA256 timer scopes overlap and must not be added. Baseline/setup, native commands, calibration and inference are separate; these figures are not complete lifetime project cost.

After restoring the preserved native campaign, reproduce into a fresh output directory:

```sh
python scripts/reproduce_guarded_sha256.py replay
python scripts/export_guarded_corpus.py \
  --selection-root results/2026-10-21-sha256-selection \
  --target-root generated/reproduction/guarded-sha256 \
  --output generated/reproduction/six-workload-corpus
```

These commands replay preserved evidence and start zero native hardware jobs. The original export used `generated/guarded-sha256-2026-10-21` as its authenticated native root.

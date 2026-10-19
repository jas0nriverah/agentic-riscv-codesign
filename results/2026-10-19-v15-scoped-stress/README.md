# V15 prospective covered-domain stress

**32 originals, 96 frozen points, 68,736 passing RTL comparisons, 32 completed mappings, zero fits.** The complete bounded pipeline took **43.49 seconds**. Equal-four-template MAE falls **15.5211 → 12.0093 LUT4 (22.63%)**, while maximum underprediction rises **2.8267 → 32.0067 LUT4**. V15 remains experimental.

All 32 circuits select V9 by construction. This tests related synthetic arithmetic coverage, not new application transfer or superiority of the router over V9. [Full results and model diagram](../../docs/v15-scoped-results.md) · [Frozen protocol](../../docs/v15-scoped-protocol.md).

## Evidence

- [Plan](plan.json), [original candidates](candidates.json), [novelty check](novelty.json) and source were committed at `9860124c8f405b2cbd9443646a340946f27f9175` before this attempt. The [rejected input draft](../../archive/2026-10-19-v15-preflight/README.md) documents the single pre-freeze template amendment.
- [Point freeze](point-freeze.json) binds all 96 predictions and the complete full336 features before target mapping.
- [Completion](attempt/completion.json), [verification](attempt/verification.json), [labels](attempt/labels.json), [resource records](attempt/measurements.json), [predictions](attempt/predictions.json) and [metrics](attempt/metrics.json) retain the full panel.
- [Independent review](independent-review.json) recounts netlists and independently recomputes results from saved evidence.
- [Raw manifest](attempt/raw-evidence.json) binds all raw worker, graph, RTL, vector, netlist and compiler files. The committed [raw archive](raw-evidence.zip) preserves the expanded `raw/` tree, which also remains locally available. [Archive receipt](raw-archive.json).
- [Research figure](../../docs/figures/v15-scoped/v15-stress.pdf), [SVG](../../docs/figures/v15-scoped/v15-stress.svg), [exact plot inputs](../../docs/figures/v15-scoped/figure-data.json).

## Cached inference replay

From the repository root with the project environment installed, choose a fresh output path:

```sh
.venv/bin/python scripts/model_v15_scoped.py \
  --rows results/2026-10-19-v15-scoped-stress/candidates.json \
  --features results/2026-10-19-v15-scoped-stress/attempt/features.json \
  --output /tmp/isaforge-v15-replay.json
```

This loads the two hash-fixed forest artifacts and computes the three point sets from cached features, without training or native synthesis. Compare its `models` and `routes` fields to `attempt/predictions.json`. It does not provide calibrated upper bounds.

Regenerate the figure from the completed saved metrics without native jobs:

```sh
.venv/bin/python scripts/plot_v15_scoped.py \
  --root results/2026-10-19-v15-scoped-stress \
  --output /tmp/isaforge-v15-figure-replay
```

The standalone audit runs without producer/scorer imports or native jobs:

```sh
.venv/bin/python scripts/audit_v15_scoped.py \
  --root results/2026-10-19-v15-scoped-stress \
  --output /tmp/isaforge-v15-independent-replay.json
```

For raw evidence review on a new checkout, extract `raw-evidence.zip` into this result directory, restoring the original `raw/` paths. The manifest retains each file's SHA256. Installed native tool paths in historical receipts describe the original machine; cached inference and plotting do not require those tools. A new physical replication would be a separate attempt with explicit tool validation, not an overwrite of this frozen run.

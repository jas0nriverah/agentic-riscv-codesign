# V11e frozen comparison evidence

Completed October 19, 2026: all327 original targets /521 program memberships, frozen V6/V9, no retraining. Primary equal-five-family MAE **0.506605 → 0.525239 LUT4 (+3.68%, worse)**. [Readable results, verification fallback and limitations](../../docs/v11e-transfer-results.md).

## Evidence order

1. Source/inference freeze: commit `7234bc68e484ec3ade9dcf4e7dc7aabc09a9a5bb`.
2. All654 predictions: [point-freeze.json](point-freeze.json), committed `d9deb60` before label release.
3. Measurement source and one-hour cap sealed at `b35f2eff7b72806d183c806c5fcb693c71302074`; [measurement-approval.json](measurement-approval.json) records actual parent review under the user's authorization.
4. [Label release](label-release.json), [completion](measurements/attempt-0000/completion.json), [raw archive](measurements/attempt-0000/raw-evidence.zip), logs and index retain every original measurement and the declared signed-overflow verification fallback.
5. [Independent target audit](independent-target-audit/audit.json), [admitted scoring inputs](independent-target-audit/scoring-inputs.json), [scores](scores.json), [independent arithmetic review](independent-metric-review.json).
6. [Research figures and hashes](../../docs/figures/v11e-transfer/manifest.json).

The small target and recovered-feature ZIPs are committed. Expanded caches and some original trace dependencies remain local and hash-bound; the full admission audit is not a claim of hermetic checkout-only reproduction. Do not rerun target measurement to regenerate plots.

## Saved-payload score replay

From the repository root, the following uses already admitted evidence and performs no fits, feature extraction or synthesis:

```sh
.venv/bin/python - <<'PYCODE'
import json
from pathlib import Path
from scripts.score_v11_transfer import score
root = Path('results/2026-10-19-v11e-frozen-comparison')
p = json.loads((root/'independent-target-audit/scoring-inputs.json').read_text())
actual = score(**{k:p[k] for k in ('outcomes','membership','labels','predictions')})
assert actual == json.loads((root/'scores.json').read_text())
print(actual['primary'])
PYCODE
```

Figure replay (use a new output directory):

```sh
.venv/bin/python scripts/plot_v11_transfer.py \
  --payload results/2026-10-19-v11e-frozen-comparison/independent-target-audit/scoring-inputs.json \
  --reviewed-payload-sha256 7b87dc039fa38c05d666abc4e9d54c570a8b9f81b30b9dd5f3b94dfd8af9b77e \
  --overlap results/2026-10-16-v11-model-inputs/overlap.json \
  --reviewed-overlap-sha256 bfbc045ce03f258d5e78f7ebb5f52b6f3c9e18d1ebbd5873708b799105d6fccd \
  --output /tmp/isaforge-v11e-figure-replay
```

The pure scorer validates supplied metric structure, not provenance. The stored independent audit establishes admission; rerunning that audit additionally requires its hash-bound local source/trace dependencies.

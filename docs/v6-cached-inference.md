# Optional exact-output V6 mapping-block cache

`isaforge.cached_mapping_inference_v6` is a separate inference wrapper for the
frozen V6 point and calibrated artifacts. It reuses the 23 mapping descriptors
of each original generic graph. The existing V5 313-feature extractor and frozen
V6 `predict_features` remain unchanged; the resulting vector still has 336
columns and the fitted mapping estimator still selects the same 217 columns.
There is no fitting, recalibration, feature change, or target-label access.

```sh
python -m isaforge.cached_mapping_inference_v6 \
  --model results/2026-10-14-v6/calibrated-models/mapping_v6.joblib \
  --candidates inputs.json \
  --cache-root generated/v5-features \
  --mapping-cache-root generated/v6-mapping-blocks \
  --output predictions.json
```

`router_v6.joblib` uses the same interface. The output file must not exist.
Outcome fields supplied with a candidate are ignored. A missing generic cache
may still require the frozen extractor's native generic-graph/SOG acquisition;
this wrapper does not cache native target mapping or target measurements.

Each mapping-block entry is addressed by the exact formula, original generic
manifest and graph digests, frozen runtime and wrapper source digests, generic
tool identity, cache schema, and ordered mapping columns. On every hit the
original manifest/graph bytes are checked again and the entry's exact structure,
context, digest, length, finite values and nonnegative values are validated.
Entries are written atomically; corrupted entries fail closed. The payload
digest detects corruption, not an adversary able to rewrite the payload and its
digests. A source/tool change creates a different cache identity.

The public `FeatureExtractor` additionally checks runtime and wrapper bytes
before and after extraction. The lower-level `MappingBlockCache` captures source
identity at construction and should be used through this guarded extractor.
Mapping cache counts are diagnostics outside the prediction JSON. The cache
adds storage and JSON/hash checks; the original graph is still read for its hash.

Development evidence is retained in `work/v6-cache-profile` and
`work/v6-cached-inference` outside the repository. A mechanism profile on the
fixed 384 input rows attributed 60.75% of profiled warm extraction time to the
unchanged mapping analysis, exceeding the predeclared 15% implementation
threshold. Profiling overhead and concurrent activity make that attribution
unsuitable as a latency speedup estimate.

The exactness replay compares all 384-by-336 feature values with the sealed
inputs. It compares both point and calibrated mapping/router artifacts against
all frozen prediction fields, for ordinary and poisoned outcome metadata. The
first pass creates 384 blocks; every repeated pass is a hit with the descriptor
function disabled. Native subprocess creation is forbidden during this replay.
All source/model/schema digests remain unchanged. No target labels are read.
Unit tests separately exercise payload/schema/source/column corruption,
graph/manifest/tool mismatch, and invalid shape/negative values even with an
internally consistent digest.

The timing protocol uses two independent byte-identical warm generic caches,
one initially absent mapping cache, one untimed pass per side, and three matched
pairs in alternating order. Both sides retain their extractors and invoke the
same frozen `predict_features`; the timed work includes complete feature
extraction and mapping-model prediction, excluding model loading and native
cache acquisition. It runs only after the parent confirms target synthesis is
idle. Every timed output must remain exact and all generic files must remain
unchanged. Results describe one host and this fixed input corpus; they are not a
population latency guarantee or an accuracy improvement.

The completed fixed comparison retained in
`results/2026-10-14-v6-runtime-cache/timings.json` measured baseline times of
19.711/20.161/19.824 seconds versus cached times of 8.681/7.828/8.828 seconds per
384-row batch. The median fell from 19.824 to 8.681 seconds (2.284×; 56.21% less
time). First mapping-cache construction took 19.569 seconds, outside the timed
hit comparisons. All timed vectors/predictions were exact; no native process
was created and generic caches were unchanged. Timing used the mapping predictor;
both point and calibrated mapping/router outputs were independently replayed.
An earlier attempt interrupted during untimed warm-up because of competing audit
work is retained separately and contributes no timing observations.

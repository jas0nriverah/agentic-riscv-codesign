# Exact-output V6 mapping cache evidence

The separate optional wrapper caches only the frozen 23 mapping descriptors.
Frozen V5/V6 sources, 336-feature schema, fitted weights, point predictions and
calibrated bounds remain unchanged. No fitting, recalibration or target-label
reads were performed. Usage and limits: `../../docs/v6-cached-inference.md`.

- `evidence.json`: SHA-bound source files and 22 completed evidence files.
- `replay.json` / `replay.py`: exact all384×336 vectors; both point/calibrated
  mapping/router artifacts, ordinary/poisoned metadata; all prediction fields
  equal, 384 cache hits with descriptor recomputation disabled, no native calls.
- `cli.json`, `cli.py`, `cli-*.json`: actual calibrated CLI all384-row replay.
- `mechanism-profile/`: profile attributing 60.75% of profiled warm time to the
  mapping-analysis mechanism; this attribution is not a speedup measurement.
- `timing-plan.json`, `benchmark.py`, `benchmark.log`, `timings.json`: three
  alternating matched pairs after untimed warm-up, independent byte-identical
  warm generic caches, workers1 and identical retained extractors/predictor.
  Median384-row batch: **19.8241→8.6806 s (2.2837×,56.21% less)**. Initial block
  construction took19.5695s. Loading/cold native acquisition excluded. Every timed
  vector/prediction remained exact and generic caches unchanged. One host/fixed
  corpus; no population latency or accuracy claim.
- `parent-cpu-idle.json`: successful-run full CPU-idle confirmation.
- `aborted-contended-attempt-0000/`: earlier attempt interrupted during untimed
  baseline warm-up after peer CPU contention was reported. No measured pair from
  that attempt contributes to the result; plan/source/traceback/status retained.
- `findings.md`: complete interpretation, scope and limitations.

This README was added after the evidence manifest; it is explanatory navigation
and does not alter any SHA-bound evidence or cache source.

# Reproduce V6 and run its frozen models

V6 tests 23 mapping-related descriptors added to the 194-column dual-graph
predictor. The primary estimator is a 300-tree ExtraTrees regressor with the
same 1,665 fitting circuits, parameters and random seed as the frozen V5
dual-graph control. A secondary fixed router uses V5's semantic expert when
the original formula contains a multiplication operation.

The [protocol](v6-protocol.md) fixes the experiment before measurement. The
historical [development study](v6-development-direction.md) explains the
feature hypothesis and its limits.

## Replay a completed snapshot

Use a full Git clone on `codex/isaforge-ml-foundation`, create and activate a
**Python 3.13** environment, then install the project:

```sh
python -m pip install -e '.[dev,reports]' -r requirements-research.txt
make reproduce-v6
```

The recipe restores the hash-checked calibration and test raw-evidence
archives, checks the committed stage freezes and original-RTL evidence,
recomputes every score and the fixed paired bootstrap, then exports PNG,
editable SVG and vector PDF figures under `generated/reproduction/v6/`.
Score replay does not execute Yosys, train an estimator or load model pickles.
Full Git history is required to validate the exact premeasurement commits.
The pinned numerical versions are required even for V6 score replay: its
frozen provenance check compares the installed environment with the fitting
manifest. Generic package installation ranges alone do not satisfy that check.
Python 3.11 remains covered by general compatibility tests, but cannot install
all of these exact recorded numerical versions. CI runs the frozen V6 replay
in its pinned Python 3.13 job.
A partial or failed snapshot is rejected; it is not silently scored on a
smaller successful subset.

## Run actual inference

For a completed calibrated snapshot:

```sh
python -m isaforge.area_model_v6 \
  --model results/2026-10-14-v6/calibrated-models/mapping_v6.joblib \
  --candidates results/2026-10-14-v6/corpus/test/candidates.json \
  --cache-root generated/v6-inference-cache \
  --output generated/v6-inference/mapping-test.json
```

Substitute `router_v6.joblib` and a new output path to run the secondary router.
The CLI refuses to overwrite existing outputs. Formula inputs determine
features; supplied target counts, correctness flags and stratum labels cannot
change predictions. Benchmark and candidate identifiers are preserved for
alignment.

Actual artifact loading requires the numerical-library versions recorded in
the model's adjacent JSON schema. New feature extraction also requires the
exact frozen Yosys binary/version. A valid content-addressed cache can replay
its graphs, with source/tool/graph hashes checked. Large graph caches are
local generated data and are not included in Git; the raw target-measurement
archives serve a different purpose and do not replace the feature cache.

The `models/` directory holds point artifacts saved before calibration; these
explicitly return null upper bounds. The separate `calibrated-models/`
artifacts add a fixed margin from 96 complete calibration components without
changing fitted trees or point predictions. Bounds concern this synthetic
grammar under the stated assumptions, not arbitrary applications. Tree spread
and feature-range flags are descriptive diagnostics.

## Evidence sequence

1. `corpus/input-seal.json` binds both 192-case cohorts, their 336-column
   lineage features, components, exclusions and acquisition attempts.
2. `point-freeze.json` binds all eight predictors and every calibration/test
   point prediction before calibration labels.
3. `corpus/calibration/label-approval.json` identifies the reviewed Git commit;
   the collector records its release, verification and original-RTL synthesis.
4. `calibration-freeze.json` binds the calibration evidence, new calibrated
   artifacts and all test bounds, with no new estimator fit.
5. The separate test approval names that later commit before any test
   measurement. `evaluation.json` then retains all eight models and all cases.

`audit/` retains independent input, artifact, numerical and raw-evidence
checks. The sibling `2026-10-14-v6-attempt-0000/` preserves the failed first
serialization check, sources and fit. Its corrected retry must be counted in
total computational work. The input and weight identity audits establish that
this prelabel repair did not choose a different model or evaluation corpus.

Do not edit source files bound by a completed freeze. A later improvement
needs a new version and experiment directory; prior tests become consumed
development evidence, not fresh tests for the revision.

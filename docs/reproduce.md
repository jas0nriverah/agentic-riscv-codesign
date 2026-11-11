# Reproduce and run inference

Use a source checkout of `latest` with Python 3.13 and the exact numerical versions in `requirements-research.txt`. The saved model loader validates artifact, metadata and runtime-source hashes. Model files and command scripts live in this checkout; they are not bundled into an independently installable model wheel.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,reports]' -r requirements-research.txt
make reproduce
make predict
```

`make reproduce` validates the curated artifact hashes, recomputes MAE, positive-target MAPE, zero-target error, grouped primary endpoints and cap decisions, and checks exact agreement with `results/summary.json`. Its output is `generated/reproduction/summary.json`. This is saved-evidence replay, not new training or measurement.

`make predict` loads the base forest and performs actual inference on the 32-case cached arithmetic panel. Its output is `generated/predictions.json`. For other models or panels, use a fresh output path:

```sh
python scripts/predict.py --model scoped \
  --candidates results/application-transfer/candidates.json \
  --features results/application-transfer/features.json \
  --output generated/scoped-transfer.json
```

Choose `base`, `coverage` or `scoped`. The output includes complete points and their selected-model routes. Saved model metadata and zero overrides remain unchanged. Upper bounds are null: these are uncalibrated area estimates.

Cached inference needs no Yosys, Verilator or RISC-V toolchain. For a genuinely new formula, omit `--features` and supply a candidate JSON list containing `formula` strings. That invokes the frozen graph extractor and requires its exact recorded Yosys binary/version; an arbitrary system Yosys is not interchangeable. Use `--cache-root generated/new-features` for new extraction. The [original toolchain instructions](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/toolchain.md) preserve the hardware environment.

## Checks and figures

```sh
make test
make figures
```

The retained tests cover prediction, features, graph semantics, area modeling and core package behavior. Native unit checks run when tools are installed. The archive retains historical experiment-specific acquisition and audit tests. The clean branch CI checks its own retained scope and includes pinned-model inference.

Both diagrams have SVG, PDF and PNG exports under `docs/figures/research/`. The rendering script retains the exact plotted values and immutable source references. It renders four separate matched comparisons rather than combining different cohorts into a misleading learning curve.

## Historical evidence

This branch is a curated snapshot of commit `b64716a2b94b332fdbced677869620bb949c073d`. [The original research tree](https://github.com/jas0nriverah/agentic-riscv-codesign/tree/b64716a2b94b332fdbced677869620bb949c073d) contains full collection scripts, raw archives, source freezes and negative results. Reproducing those historical native pipelines should use that checkout. The clean branch keeps the inputs needed for model inference and score replay, plus hash-bound provenance to the complete evidence.

## Feature comparison

Replay the retained feature experiment without training:

```sh
make feature-check
```

To repeat the bounded 15-fit experiment in a fresh directory (requires the archive commit in Git history):

```sh
python scripts/compare_features.py prepare --output generated/feature-comparison-repeat
python scripts/compare_features.py run --output generated/feature-comparison-repeat
```

The runner freezes inputs and folds before fitting, limits native libraries to one thread, and enforces a 600-second wall limit. Do not overwrite the retained experiment. `make figures` also regenerates its comparison plot. [Protocol and interpretation](../results/feature-comparison/README.md).

`make feature-check` also replays the selection-stability and fresh-validation follow-ups. The stability replay uses the standard library; fresh-validation replay uses the pinned project environment but launches no fitting or native jobs. Full model weights, ordered feature schemas, prediction freezes and compressed native evidence are retained. See [stability](../results/selection-stability/README.md) and [fresh validation](../results/selection-validation/README.md) for their separate compute budgets and interpretation.

## Validated coverage candidate

The [budget-preserving candidate](../results/budget-preserving-coverage/README.md#run-actual-cached-inference) has an explicit cached-feature prediction command. It reuses the base forest and the new 1,729-row forest; no native tools or fitting are needed for cached inference. `make coverage-check` independently verifies both coverage experiments, including saved predictions, raw mapped netlists, oracle vectors, budget decisions and chronology. This audit uses the pinned numerical environment and launches no fits or native jobs.

## Signed-arithmetic revision

The [current experimental revision](../results/guarded-revision/README.md#run-and-replay) provides a separate cached-inference command. Reproduce its new measurement/model audit with `.venv/bin/python scripts/audit_guarded_revision.py`; this compares frozen receipts without modifying them and launches no new fits or native jobs. Regenerate its figure with `.venv/bin/python scripts/render_guarded_revision.py`. Earlier commands and frozen artifacts remain unchanged.

## Signed-shift refinement

Use [the latest cached inference command](../results/signed-refinement/README.md#run-and-replay) to evaluate the explicit refinement. `python scripts/refine_signed_coverage.py replay` checks all saved points and metrics without writes. `python scripts/audit_signed_refinement.py` independently checks raw evidence and frozen receipts without new fits or native jobs. Regenerate its figure with `python scripts/render_signed_refinement.py` in the pinned environment. Earlier snapshots and commands remain preserved.

## Budget-release diagnostic

The [budget-release report](../results/budget-release/README.md) provides cached inference and replay commands for the new 1,825-row forest and structural policy. It improves fresh area estimates and false acceptances but fails the separate false-rejection gate; it is not promoted. `scripts/release_budget_coverage.py replay` and `scripts/audit_budget_release.py` check frozen evidence without fitting or native measurement. `scripts/render_budget_release.py` regenerates the fresh comparison figure.

## Median boundary diagnostic

See the [boundary-repair report](../results/boundary-repair/README.md) for cached inference and read-only replay with `scripts/repair_boundary_coverage.py` and `scripts/audit_boundary_repair.py`. These reuse existing weights without fitting. `scripts/render_boundary_repair.py` renders the matched fresh comparison; its failed activity gate remains explicit.

## Conditional boundary challenge

The [challenge report](../results/boundary-challenge/README.md) documents input-only selection, all-pool provenance, cached inference and read-only replay with `scripts/challenge_boundary_coverage.py` and `scripts/audit_boundary_challenge.py`. `scripts/render_boundary_challenge.py` reproduces the conditional comparison figure. The experiment has zero fits and retains its failed accuracy and false-acceptance gates.

## Structural boundary refinement

The [refinement report](../results/boundary-refinement/README.md) provides cached inference and read-only replay using `scripts/refine_boundary_coverage.py` and `scripts/audit_boundary_refinement.py`. All128 pool features/points and48 unique measured labels are retained. `scripts/render_boundary_refinement.py` reproduces separate general and conditional panels, including the failed general false-rejection gate. No fitting is required.

## Matched coverage and local-feature experiment

The [coverage experiment](../results/boundary-coverage/README.md) compares two saved forests trained on identical 1,857-row data: 217 existing features versus 233 features with 16 local structural descriptors. The development-selected policy uses the 217-feature forest. Replay and cached inference require no retraining or FPGA tools:

```sh
python scripts/learn_boundary_coverage.py replay
python scripts/audit_boundary_coverage.py
python scripts/learn_boundary_coverage.py predict-cached \
  --candidates results/boundary-coverage-validation/candidates.json \
  --features results/boundary-coverage-validation/features.json \
  --prediction-output generated/boundary-coverage-predictions.json
python scripts/render_boundary_coverage.py
```

The saved protocol binds both fitted models, their ordered training data, all pool predictions and the pre-label selection. Raw forest errors and final policy errors are separate. Preserve the existing evidence directories; repeating training or measurement requires a new experiment protocol and output directory.

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

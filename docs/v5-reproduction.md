# V5 development and reproduction

V5 is a new experiment with separately named sources, artifacts and inputs.
The [protocol](v5-protocol.md) defines what freezes before measurement and which
results can support a claim. Existing V4 sources and evidence stay frozen.
This guide describes the implementation and commands; it does not declare a
completed V5 holdout result or authorize release of sealed labels.

Run commands from the repository root. The recorded development environment
uses CPython 3.14.7 on Apple Silicon macOS. Numerical and test package versions
are pinned in [requirements-v5.lock](../requirements-v5.lock):

```sh
python3.14 -m venv .venv-v5
.venv-v5/bin/python -m pip install -r requirements-v5.lock
.venv-v5/bin/python -m pip install -e . --no-deps
.venv-v5/bin/python -m pytest -q tests/test_structural_features_v5.py tests/test_graph_features_v5.py tests/test_area_model_v5.py tests/test_v5_corpus.py tests/test_evaluate_v5.py
```

The lock records package versions rather than distribution hashes. It does not
bundle wheels, Python, OpenMP, native tools or isolated packaging dependencies.
Installing these pins on another platform must be checked locally. V5 artifact
loading compares the numerical-library versions with its saved schema and
rejects mismatches before unpickling. Only load trusted local joblib artifacts.

## Feature extraction and portable cache replay

V5 keeps original RTL and normalized RTL as separate channels. Generic Yosys
processing first retains a word-level arithmetic graph, then runs
`synth -top candidate -noabc`. No ABC, target-device mapping or measured
resource labels enter these graph features. Word-level add/sub widths describe
possible carry work; they are not dedicated carry-cell measurements. Existing
original-formula SOG features are an additional control.

The combined runtime stores caches under a user-selected root, with `generic/`
and `sog/` subdirectories. Generic scripts and graph references use paths
relative to each cache entry. The V5 wrapper supplies the same stable SOG
context at training and replay. Cache integrity checks include retained files,
source/tool/pass identities, feature rederivation and formula RTL.

A complete compatible cache permits inference without an installed Yosys.
Relocated-cache tests exercise both graph channels and the SOG channel with
tool lookup disabled. A previously unseen formula requires the recorded
Yosys version and executable SHA-256; the native Apple build used here cannot
be replaced by an arbitrary Linux or Homebrew binary. A version-matched Python
environment alone does not supply that tool. Use a new declared lineage and
revalidate features when changing the native toolchain.

Once a trusted V5 model bundle has actually been frozen, replay its inference
with an explicit cache root:

```sh
.venv-v5/bin/python -m isaforge.area_model_v5 \
  --model results/2026-10-14-v5/models/dual_semantics.joblib \
  --candidates results/2026-10-14-v5/corpus/test/candidates.json \
  --cache-root generated/v5-features \
  --output generated/v5-replay/dual-semantics.json
```

Outputs include point LUT4 predictions, a one-sided upper bound, tree
disagreement where available, and counts of features outside their fitting
ranges. `upper_lut4: null` represents an unbounded interval when calibration
has too few groups. Tree disagreement and feature-range warnings are
diagnostics; neither proves coverage or automatically makes a circuit safe.
The upper bound assumes exchangeable complete groups, an assumption not
established for novel compositions or new applications.

A later, separately versioned [original-only inference wrapper](../results/2026-10-14-development-diagnostics/README.md)
skips channels unused by the `original_graph` artifact while preserving every
prediction and diagnostic field exactly. It does not change the frozen V5
implementation or the external comparison. The linked benchmark reports actual
cold/warm costs and their limitations.

## Prepare and freeze a new experiment

The preparation workflow generates input-only cohorts, collects development
measurements, extracts all original/normalized features, seals component
separation, reserves entire calibration components and selects configurations
using fitting-only grouped folds. Input sealing must precede fitting. If it
fails, the protocol permits a separately recorded deterministic input repair
before fitting and target-label access; failed inputs and exclusions remain
evidence. Input repair after final model freeze is rejected.

Development measurement invokes actual Verilator verification and original
RTL iCE40 synthesis. Both are required native tools. All formulas must finish;
failed measurements do not authorize scoring a convenient subset. Full generic
extraction has a 120-second per-channel timeout and retains explicit failures.
See [toolchain](toolchain.md) and [V4 correctness and tools](v4-results.md) for
the retained native-tool and signed-overflow incident context.

The trainer expects a complete protocol-consistent experiment root with its
own `corpus/development/dataset.json` and `corpus/test/candidates.json`:

```sh
.venv-v5/bin/python scripts/train_v5.py \
  --root results/2026-10-14-v5 --features-only
```

This extracts features, writes feature records and attempts the input seal. It
fits no estimators and reads no V5 test labels. It may require Yosys on cache
misses. The trainer consumes already inspected historical and V4 labels as
development data; those results retain historical status for their old models
but are not independent tests of V5.

After final sealing and native development measurement, the same command
without `--features-only` selects and fits the preregistered models, calibrates
on reserved components, produces all comparator predictions and writes the
freeze bundle. It refuses to retrain a root containing `freeze.json`.
Do not edit runtime sources, the protocol or the declared pool during fitting.
Use a new lineage for any subsequent revision.

Before test-label collection, validate the entire frozen bundle without
loading estimators, running hardware tools or reading sealed labels:

```sh
.venv-v5/bin/python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from evaluate_v5 import validate_freeze
validate_freeze(Path('results/2026-10-14-v5'))
print('V5 freeze validated; test labels remain sealed')
PY
```

The validator checks all required inputs, sources, artifacts and predictions,
model/schema coherence, fitting/calibration separation, chronology and upper
bounds. Frozen `test-clusters.json` uses the same skeleton-plus-equivalence
component rule as calibration, restricted to test inputs. Input-independence
sealing uses its separately declared rule because known-family tests permit
familiar skeletons. These purposes should remain distinct.

## Replay scores after an authorized release

Only after model/prediction freeze and authorized test measurement may the
independent scorer consume `label-release.json` and the completed test dataset:

```sh
.venv-v5/bin/python scripts/evaluate_v5.py \
  --root results/2026-10-14-v5 \
  --output generated/v5-replay/evaluation.json
```

This validates the freeze, release, collector and complete measurement records,
then reports both scopes and every candidate for all six predictors. The
primary comparison is dual-semantics versus equally tuned original SOG on
unseen compositions. Cluster bootstrap draws preserve components globally
across strata, with rejected empty-stratum draws recorded. Upper-bound coverage
is descriptive by candidate, component and stratum. A lower synthetic area
error does not establish useful acquisition, CPU speedup, energy savings or
end-to-end measurement savings.

Keep replay outputs in `generated/`. The scorer does not fit models, extract
features or generate labels. A completed replay requires actual released
evidence; artificial fixtures in evaluator tests only check the protocol code.

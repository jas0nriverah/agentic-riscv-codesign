# Model

ISAForge predicts the number of iCE40 four-input lookup tables required by an original RV32 instruction candidate. A candidate is a bounded computation with up to two inputs and one output. Training targets come from verified RTL and actual Yosys synthesis.

![Model architecture](figures/research/model.svg)

## Representation and estimator

The extractor computes 336 descriptors; the forest uses a fixed 217-feature view:

| Feature block | Count |
| --- | ---: |
| Simple operator graph | 14 |
| Original generic graph | 60 |
| Normalized generic graph | 60 |
| Absolute differences between the two graph views | 60 |
| Mapping-related graph descriptors | 23 |
| **Model inputs** | **217** |

The model is an ExtraTrees regressor with 300 trees, one-sample minimum leaves, all features considered at splits, randomized split thresholds, and no bootstrap sampling. Every tree sees the training dataset. Its prediction is the equally weighted mean of tree outputs, clipped to nonnegative values, with the frozen original-generic-zero rule preserved. Tree disagreement is recorded but is not a calibrated uncertainty bound.

Both graph views describe the same original implementation. Labels always measure original RTL, never a cheaper rewritten implementation substituted after observing the result. Cached features avoid preprocessing; a new formula still requires compatible pre-mapping graph extraction.

## Available predictors

| Name | Training circuits | Role |
| --- | ---: | --- |
| `base` | 1,665 | Default; strongest primary result on the completed application-transfer panel |
| `coverage` | 1,713 | Same representation and estimator, with 48 targeted arithmetic examples |
| `scoped` | Uses the two saved forests | Experimental input-only selection of one forest |

The scoped policy selects coverage when the original formula contains a low multiplication with a syntactic positive constant from 1 through 2047, or a signed-shift difference `sub(srai(A,k),srai(B,31))`, with input-containing A/B and k from 0 through 31. Otherwise it selects base. It does not inspect labels, predicted error or benchmark identity. The CLI computes only the required model subsets and returns the selected original points.

On the 32-case arithmetic test every case selects coverage, so the scoped policy equals coverage by construction. On the consumed 327-case application panel every case selects base. These checks do not establish routing generalization to a new mixed application distribution.

The weights and adjacent metadata in [models/](../models/) are byte-identical to their archived artifacts. Their original internal module names remain unchanged to preserve serialization and source validation. [Inference and reproduction](reproduce.md).

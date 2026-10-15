# V13 targeted coverage: sealed inputs

**Status: input preparation complete; no new hardware measurements or model fits.** The next experiment tests whether measured training coverage helps the unchanged raw-target mapping model after the V12 log-target candidate failed its primary comparison.

| Proposed originals | Count |
| --- | ---: |
| Correlated high-half products | 16 |
| Affine and masked arithmetic chains | 16 |
| Comparator and shift compositions | 16 |

[Protocol and matched comparison](../../docs/v13-coverage-protocol.md) · [Exact candidates](candidates.json) · [Preparation manifest](preparation.json) · [Recipe](recipe.json) · [Complete overlap analysis](duplicate-analysis.json) · [Coverage diagnostics](coverage-diagnostics.json)

All 48 use encodable RV32 immediates and at most four distinct operations. They syntactically use two input symbols; eight intentional cancellation cases are semantically unary. A fixed pure-oracle witness set distinguishes all 1,128 internal pairs. This is not RTL equivalence verification.

The input ledger retains 3,008 previously exposed originals, including the V11 input-only cohort. No proposed original matches a recorded canonical original or declared accepted alias, and no internal declared aliases were found. This finite identity audit does not prove exhaustive novelty. All proposals are motivated by consumed development errors and remain development data.

The future measured-label budget is 48 original circuits. The collector, tool identities, verification and artifact contract must be separately fixed before native collection. The subsequent raw-control/augmentation comparison must use one common closed grouping over the old and new inputs, excluding all linked validation rows from both training sets. Its primary denominator is the original 1,713 rows; the new 48 are secondary challenges. No candidate replacement, final deployment refit, or fresh-transfer claim is included in this preparation.

Recheck the sealed inputs:

```sh
.venv/bin/python scripts/prepare_v13_coverage.py \
  --root results/2026-10-15-v13-coverage-development --validate
```

Fourteen focused tests pass, covering exact grids and immediates, source/identity lineage, label-poison invariance, fixed output validation, and constructive pairwise differences.

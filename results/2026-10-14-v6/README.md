# V6 frozen experiment evidence

The primary mapping-feature model reaches **32.160946 LUT4 MAE** against
the unchanged dual-graph control's **34.332170** on 192 fresh test circuits.
The fixed paired difference is −2.171224, with descriptive component interval
[−3.472539, −0.937534]. All eight models, eight strata, 96 test components,
zeros and outliers remain. [Interpretation and limits](../../docs/v6-results.md)
and [reproduction](../../docs/v6-reproduction.md) explain the experiment.

## Frozen stages

| Evidence | Purpose |
| --- | --- |
| [Input seal](corpus/input-seal.json) | Both 192-row scopes, component identities, consumed-input exclusions and complete feature vectors |
| [Point freeze](point-freeze.json) | All point artifacts and predictions before calibration labels; committed at `60128277` |
| [Calibration release](corpus/calibration/label-release.json) | Release following review of the exact point commit |
| [Calibration freeze](calibration-freeze.json) | Fixed rank-88 margins, unchanged trees and test upper bounds; committed at `abf321cc` |
| [Test release](corpus/test/label-release.json) | Separate release following review of the calibrated commit |
| [Evaluation](evaluation.json) | Complete metrics, paired bootstrap, all errors, bounds and cap decisions |

Both point and calibrated models are retained under `models/` and
`calibrated-models/`. Predictions precede their associated measurement
releases. Runtime sources bound by these freezes must not be edited.

## Original-circuit measurements

Each scope contains 192 verified and synthesized circuits, with 412,416
boundary/random oracle comparisons and zero failures. Independent recounts
find 53,246 LUT4 / 6,778 carry cells in calibration and 41,902 / 5,965 in test.
Each raw ZIP contains 1,358 retained files, including original RTL, commands,
logs, netlists and oracle artifacts.

- Calibration: [completion](corpus/calibration/completion.json),
  [archive manifest](corpus/calibration/raw-evidence.json),
  [raw ZIP](corpus/calibration/raw-evidence.zip).
- Test: [completion](corpus/test/completion.json),
  [archive manifest](corpus/test/raw-evidence.json),
  [raw ZIP](corpus/test/raw-evidence.zip).

Run `make reproduce-v6` from the repository root. It restores and validates
both archives, checks Git freeze history, recomputes all scores and the
10,000-draw primary interval, and renders the figures without retraining or
running hardware tools.

## Independent audits

| Check | Evidence |
| --- | --- |
| Input acquisition, identity exclusions and grouping | [Input audit](audit/v6-input-independent-audit.json) |
| All eight point models, 3,072 predictions, metadata resistance | [Artifact replay](audit/point-replay.json) |
| Real cold/warm/poisoned CLI inference | [CLI replay](audit/cli-replay.json) |
| Calibration raw/oracle evidence, independent implementation | [Raw audit](audit/calibration-raw-oracle.json), [second audit](audit/v6-calibration-raw-audit.json) |
| Fixed margins, unchanged trees and test bounds | [Calibration replay](audit/calibration-replay.json), [second frozen audit](audit/v6-calibration-frozen-audit.json) |
| Test raw/oracle evidence, independent implementation | [Raw audit](audit/test-raw-oracle.json) |
| All test metrics, caps, coverage and primary bootstrap | [Independent test audit](audit/v6-test-independent-audit.json), [readable report](audit/v6-test-independent-audit.txt) |
| Consumed post-test mechanism/tail analysis | [Diagnostics](audit/v6-posttest-diagnostics.json), [readable report](audit/v6-posttest-diagnostics.txt) |

Executed audit source files are retained alongside results. The first
training attempt failed a padding-sensitive serialization fingerprint check
before labels; all evidence lives in the sibling
[failed-attempt archive](../2026-10-14-v6-attempt-0000/README.md).
The [input identity](audit/prelabel-amendment-input-identity.json) and
[fit identity](audit/fit-identity-after-fingerprint-fix.json) checks establish
unchanged candidates, feature values and canonical tree weights on retry.
This history includes two fits in total, not one.

The separate descriptor-cache optimization does not modify any frozen model,
feature value or result. See [runtime documentation](../../docs/v6-cached-inference.md).
Current test labels are consumed evidence for subsequent research; a new model
needs a new frozen evaluation to establish an independent improvement.

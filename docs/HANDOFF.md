# Project handoff — October 16, 2026

**Paused at the user's request.** Research agents and local jobs are stopped. Resume only when requested.

## Show the team

- [Project overview, methodology and architecture](../README.md)
- [ML model diagram and explanation](ml-model.md)
- [Verified results and hardware tradeoffs](team-progress-2026-10-16.md)
- [Research figures](v13-coverage-results.md)

V9 remains the retained development model: 217 circuit features, 300 ExtraTrees and 1,713 training circuits. Development improvements and regressions are reported separately; no new independent transfer score or state-of-the-art claim is established.

## Verified checkpoint

The reserved transfer panel has all six outcomes, 327 unique circuits and 521 program/circuit memberships. Independent input replay passed. All 327 feature extractions and the 806-channel raw feature replay passed. The complete 336-feature matrix is committed.

The last full local suite passed **2,190 tests and 179 subtests**. CI at `4331d0f` passed Python 3.11, Python 3.13 and hardware checks. This cleanup changes documentation and archives unexecuted drafts; it does not change the validated pipeline.

## Unfinished work

The feature archive exceeded its 300-second deadline due to repeated whole-directory scans. The original completion remains false and its partial ZIP/log/terminal receipt are preserved. **New V6/V9 inference, fresh target measurements and transfer accuracy scoring have not run.**

Five unfinished recovery/inference source and test files are preserved in the [draft archive](../archive/2026-10-16-unreleased-v11-recovery/README.md), outside active scripts/tests. The draft inference adapter is untested. The unexecuted target collector has the same repeated-scan packaging pattern and needs correction before release.

When resuming: finish efficient packaging and its audit, freeze paired V6/V9 predictions, then measure all 327 original circuits and audit the labels before scoring and generating actual comparison figures. Keep the existing protocol, cohort and frozen model artifacts unchanged.

## Data retained locally

Large raw traces, expanded feature caches and some historical cross-validation forests remain local and hash-bound; they are intentionally not all duplicated in Git. **Do not delete `generated/` or the V11d feature cache/workers if continuing this experiment.** Committed manifests document the reproduction boundary. No local research data were deleted during cleanup.

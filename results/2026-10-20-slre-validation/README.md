# SLRE and portfolio-demo validation — October 20, 2026

The complete suite passes: **2,639 tests, 179 subtests**, one intentional duplicate-ZIP-member warning, 143.88 seconds. All 88 new component tests also passed together. The previous unchanged legacy process-cleanup failure did not recur in this run; no causal fix is claimed and its [earlier failure logs](../2026-10-20-model-analysis-validation/README.md) remain preserved.

| Check | Result | Evidence |
| --- | --- | --- |
| Complete suite, `make test` | 2,639 tests / 179 subtests passed | [Log](full-suite.log) |
| Historical model and processor replays | Six-model metrics/bootstrap, original CRC32, automatic aha/CRC, 420 development endpoints, nine failed contexts, 222 calibration cases and 60 latency endpoints match | [Replay log](replays.log) |
| Prospective SLRE | Seven raw processor measurements, 21 routes, unchanged preregistration and receipt prefix, 90 exactly refitted predictions, 105 policy endpoints match | [Replay log](replays.log) |
| Offline demo | Three verified workload contexts, authenticated SQLite imports and HTML generated | [Demo log](demo.log) |
| Actual SQL examples | Feasible best-design window query, disjoint cost summaries and preserved failure join execute | [SQL output](sql-queries.log) |
| Visual inspection | Actual browser render checked; complete cycle values and correctness columns visible; chart/table agree | [Validation record](validation.json) |

The renderer's first layout split long cycle values in narrow cards. A separate presentation-only CSS wrapper now uses full-width measurement tables. It changes no measured text, prediction, policy result, or frozen renderer source. Its actual CLI and final `make demo` were exercised after that adjustment; no new unit test was added for CSS presentation.

All replay commands run without new hardware jobs. New native evidence is accounted for separately in [the experiment cost record](../2026-10-20-slre-transfer/measurement-costs.json): 149 commands including the failed partition attempt, 288.697 command-seconds. Policy replays are not new hardware evaluations.

Use Python 3.12 with [pinned dependencies](../../requirements-speedup.txt):

```sh
make test PYTHON=python
make reproduce reproduce-speedup reproduce-selection-research reproduce-model-analysis reproduce-prospective PYTHON=python
make demo PYTHON=python
sqlite3 -header -column generated/reproduction/prospective-slre/experiments.sqlite < docs/experiment-queries.sql
```

[The manifest](manifest.json) covers logs and validation metadata. This explanatory README is outside that manifest. The record names the three GPT-6.1-Sol review scopes and source hashes. Read [the result](../../docs/prospective-slre.md) before interpreting the ML metrics: lower MAE did not improve selection, and uncertainty coverage was zero on the prospective workload.

Final checks resolve all 295 relative links examined in changed/new documentation and confirm that all 88 manifest-bound files match staged Git contents. Whitespace checks exclude raw logs and the unchanged, hash-bound `embench_strings.c` snapshot's pre-existing blank EOF line; neither scientific evidence nor padded SQL output is rewritten for formatting.

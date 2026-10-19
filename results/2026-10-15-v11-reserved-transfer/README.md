# V11 reserved transfer — input feasibility only

The six-program reservation was committed at `b6f1549ae2ef3f20f8a54511a6c3d13d865646e4` before any new trace. See `docs/v9-reserved-transfer-direction.md` for the exact TACLeBench pin, source-program list, five proposed family weights and consumed-lineage limits.

`collect_v11_reserved.py` collects the complete original computation window and all called helpers, using the unchanged V8 GCC/Spike/runtime/decoder/candidate/fusion contract. It runs no ML feature extraction, model prediction, fitting, Yosys target mapping or area-label collection. All original fixed inputs and source directories are captured before execution; snapshots and correctness probes run after the measurement markers. No failed program is replaced or shortened.

The first raw attempt is retained under `generated/v11-reserved-inputs/attempt-0000`; the console log is `../v11-reserved-input-first.log`. Its immutable `input-plan.json` binds 41 upstream source/input/notice files and 14 runtime/source files. `input-provenance-amendment.json` separately binds the committed unchanged CountedTrace helper and two imported package modules omitted from the inherited V8 base dependency list. The original plan and running collector remain unchanged. The amendment is explicit and does not claim that the initial flat dependency list was complete.

Correctness evidence has different strengths:

- Factorial and Fibonacci: independent exact Python integer outputs for the original fixed workload.
- AMMUNITION: original package self-check plus independent unsigned multiplication and bit-string probes outside the measured window; this is not a complete independent implementation of the package.
- Pattern matching: original expected match12, all60 score finite/nonnegative/argmin invariants, and full-score-array digest. No independent complete HPEC matcher is claimed.
- Audio: independent binary32 geometry, delay, interpolation and Hamming-weight simulation for the first16 output samples; all371 actual samples must be finite, and the full384-slot output buffer digest must match O0/O2. Host transcendental approximations use fixed relative1e-4/absolute1e-7 bounds; upstream output words still must match O0/O2 and trace exactly.
- FM: independent binary32 pipeline simulation including the upstream byte-count compaction behavior, exact buffer progress and14 numeric coefficient/output snapshots. Host transcendental approximations use fixed relative1e-4/absolute1e-6 bounds. All four full buffer digests and snapshot words must match O0/O2 and trace exactly. An always-zero return value alone cannot pass.

The collector's 14 synthetic tests passed before the first native attempt. One earlier synthetic fixture omitted its fake compiler path and was corrected before native execution; its cause is retained in `implementation-review/initial-synthetic-fixture-failure.json`. These tests cover exact oracles, bad/null/nonfinite outputs, reserved family assignment, source-initializer shapes, actual byte-compaction behavior, failure retention, immutable output directories, complete empty pools, inclusion of helper PCs, and unrestricted `maxSize=4, limit=None` extraction.

All six first attempts finished without a retry or cohort change:

| Program | Outcome | Complete ROI instructions | Eligible formulas |
|---|---|---:|---:|
| ammunition | Incomplete trace at fixed300s; correctness/O0/O2 passed | Not complete | Undefined |
| audiobeam | Complete, fusion passed | 2,562,210 | 169 |
| pm | Incomplete trace at fixed300s; correctness/O0/O2 passed | Not complete | Undefined |
| fmref | Complete, fusion passed | 4,943,002 | 148 |
| fac | Complete, fusion passed | 91 | 1 |
| recursion | Complete, empty pool | 1,181 | 0 |

The successful pools contain318 program/formula rows and196 unique canonical originals. Of318 rows,213 match a canonical original in the minimum2,929-input consumed ledger;105 do not. This is a canonical-only diagnostic, not a complete semantic identity/novelty assessment. All helper rows remain. Across complete pools, fusion checked12,176 individual and11,856 joint comparisons with zero opaque skips. Audio's independent first16 maximum absolute difference was9.313225746154785e-10.

The proposed **five-family primary is incomplete**, and the at-least-four-family feasibility gate is not met. Only three families have any nonempty pool; the recurrence family itself has an empty Fibonacci program, so even a three-family complete-program macro is not available. No primary admission, feature/model/prediction freeze or target-measurement release has occurred. Empty and incomplete programs remain coverage outcomes; they do not receive zero MAE or silently disappear from a denominator. No fresh generalization claim exists.

`input-summary.json`, `completed-rows.json` and unchanged plan/report/inventory copies expose the input results. `raw-evidence-manifest.json` binds seven portable ZIP archives: all successful raw traces and every program's source/build/oracle/selfcheck/fusion/log evidence. Two incomplete local gzip traces remain at their original generated paths (613,846,707 and511,351,171 bytes); their hashes/sizes and explicit omission from portable ZIPs are retained. No partial trace supplies an admitted candidate pool.

`input-review/partial-volume-diagnosis.json` reads the existing partials only. They contain58,204,402 and51,806,185 measured commits (5.93GB and5.30GB JSONL), respectively; valid gzip CRC/EOF does not mean a complete measured window. Their first500,000 commits concentrate on integer conversion/division helpers or software floating point. The surfaced error is a cleanup `PermissionError`, which may mask the original termination context; no owned Spike process remains. Source execution passed untraced, while trace parsing/JSON formatting/JSON reparsing/compression sits synchronously between Spike and storage. Native compressed raw-commit capture followed by offline unchanged marker/decoder validation is a possible separately reviewed input-only improvement. It has not been run or authorized here as a retry.

After collection completed, three synthetic fixtures were made portable to clean clones by using system temporary directories instead of assuming `generated/` exists. The original pre-run test bytes remain in the frozen source archive; `implementation-review/test-portability-amendment.json` binds old/new test hashes. Production collector, oracles, source inputs, tools and candidate results are unchanged; the portable14-test suite passed. `input-review/input-package-review.json` verifies package hashes and explicitly accounts for this test-only amendment. The provenance amendment and test amendment must both be acknowledged by any future input seal; the original14-binding plan is not silently reinterpreted.

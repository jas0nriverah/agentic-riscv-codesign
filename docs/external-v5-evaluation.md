# External V5 transfer freeze and evaluation

The fixed input cohort is the completed external `cohort-02`: all 80
program/formula rows, 79 unique original formulas, with Dijkstra/ADPCM/anagram
counts 5/47/28. No row is filtered using a prediction or mapped target. Dijkstra
is explicitly a one-path partial-workload trace on the original graph; its full
20-path checksum and replay-vector correctness control lie outside that window.
The other two programs retain their pinned original core invocation. Source
checks and scope limits are in `docs/external-v5-protocol.md` and the archived
original collection-source snapshots. Cohort01's infrastructure failure remains
retained. Later collector hardening does not rewrite the cohort02 evidence.

Use exactly the six already frozen artifacts from `results/2026-10-14-v5`:
`sog_tuned`, `original_graph`, `dual_graph`, `dual_semantics`, `masterrtl_fixed`,
and `v4_frozen`. No fitting, configuration selection, calibration update, model
substitution or comparator selection is performed. The full V5 model is
`dual_semantics`; its primary comparator remains equally tuned `sog_tuned`.
All models receive the same 80 declared identities/formulas. Repeated formulas
retain both program weights; their exact original circuit is measured once.

The primary endpoint is MAE averaged equally over the three fixed families:
graph shortest paths, speech codec, and multiset word search. Report full V5
minus tuned SOG; a negative difference favors V5. Also report each family,
all-row pooled metrics, positive-label percentage errors, true-zero errors,
tail errors, signed bias and cap confusion using the existing audited metric
helper. A unique-formula pooled score is secondary and must not replace the
80-row, equal-family primary endpoint. No population or processor-performance
claim follows from three curated workload families.

For each of the four V5 views, report the existing frozen upper bounds without
recalibration: finite-bound count/fraction, observed candidate coverage, mean
and minimum slack, and rows/dimensions outside the selected training feature
ranges, for all 80 rows and each family. Whole-family coverage across these
three curated families is a descriptive secondary count. Application families
are not the calibration groups; no 90% guarantee applies under this shift.

Before any external target label exists, freeze an overlap inventory against
ALL 2,313 consumed formulas: V5 development 2,057 plus consumed V5 test 256.
Report exact canonical, current V5-normalized, exact full-feature-vector,
original ordered operator-skeleton, and normalized ordered skeleton matches,
separately for development and consumed test. Current normalizer and feature
sources/schema are frozen with this inventory.

`strict_novel` means no match under ANY of those five keys in either reference
cohort. The supplementary `formula_novel` subset excludes exact, normalized and
full-vector matches while explicitly allowing familiar skeletons. Both subsets
are fixed before labels; neither may replace the all-row primary endpoint.
If any fixed family has zero rows in a subset, its three-family macro MAE is
unavailable/incomplete. Do not silently average only represented families and
claim three-family transfer. Empty subsets remain explicit.

The freezer verifies that the collection passed all three self-checks,
O0/O2 controls, trace counters and complete randomized fusion coverage, with no
skipped opaque occurrences. A completion marker alone is insufficient. It
copies small input/source/ELF evidence, retains original archived controller
bytes, computes label-free features, predicts all six artifacts, and freezes
all input/program/protocol/runtime/feature/model/prediction hashes. Original
C source inputs and exact binaries are retained; large raw traces and generic
feature caches remain under `generated/` with their provenance hashes.

Run the label-free preparation:

```sh
.venv/bin/python scripts/evaluate_external_v5.py freeze
```

The external freeze must then be independently reviewed and committed. This
preparation does not authorize label release. The measurement command requires
a separate, explicit parent-created approval record with schema
`isaforge-external-review-v1`, `approved_for_label_release: true`, the exact
`freeze_sha256`, full 40-character `freeze_commit`, and UTC `reviewed_at_utc`.
The collector never creates this approval. It verifies every frozen source,
input, model and prediction against the named Git commit as well as current
bytes before creating a release record or invoking RTL verification/mapping.
An uncommitted freeze, changed evidence, missing review or wrong commit blocks
measurement. Parent review/commit must precede this later command:

```sh
.venv/bin/python scripts/measure_external_v5.py \
  --review results/2026-10-14-v5-external/label-approval.json
```

After release, verify every one of the 79 ORIGINAL formulas with the existing
RV32 RTL/oracle checker (100 boundary plus 2,048 seeded random vectors per
formula). Use the audited explicit signed-overflow simulator wrapper only with
its retained evidence. Technology-map ORIGINAL emitted RTL with the frozen
Yosys identity and default `synth_ice40`, no DSP or place/route. The existing
mapped-netlist helper retains RTL, script, log, netlist and their hashes.
Equivalent normalized syntax must never replace an original circuit target.
No synthesis result from a consumed cohort is silently substituted.

Expand the 79 unique original measurements back to all 80 declared rows. Retain
all verification/synthesis failures, make incomplete scoring fail closed, and
preserve partial measurements for diagnosis. Completed measurements are
immutable. Each failed retry retains its own numbered attempt directory,
including verification and partial labels. Verification/mapping helpers run in
owned subprocess groups; timeout or cancellation kills their descendants.
Cache validation requires the frozen binary SHA, original emitted RTL bytes,
and script/log/netlist hashes; unbound legacy caches are rejected. The scorer requires a valid post-freeze release, complete verification
and all 79/80 expected measurement identities before producing results:

```sh
.venv/bin/python scripts/evaluate_external_v5.py score \
  --output generated/external-v5/evaluation.json
```

These results concern isolated original-RTL LUT4 prediction on application-derived
circuits. They do not measure instruction acquisition efficiency, modified-core
correctness, integrated cycles, FPGA-board timing, or complete-application speedup.

Scorer replay requires the reviewed Git commit/history and the retained generated
original circuit/verification archive. A source ZIP alone cannot satisfy the
commit/blob or physical synthesis-evidence gates. CI must fetch the reviewed
commit (full history is the simplest option) and restore the archive at the
recorded repository-relative path. Raw-artifact lookup is relative to the bundle;
absolute command paths remain historical execution evidence only. The mapping
archive must lie under `generated/external-v5/target-measurements/`.

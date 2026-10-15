# V10: paired CSD hardware study — pending

**No hardware result is available yet.** This page is a presentation skeleton,
not evidence of a rewrite gain. Actual figures require a completed, audited
32-pair experiment: all 32 universal actual-RTL pair proofs and all 64 fresh
original/CSD synthesis arms must succeed. A failed or unresolved pair leaves
the complete primary comparison pending; no cases may be filtered or replaced.

The [fixed protocol](v10-csd-hardware-protocol.md) compares one predetermined
canonical signed-digit implementation against the original emitted RTL for
eight constants in four arithmetic contexts. Both arms use wrapping unsigned
32-bit arithmetic and identical default iCE40 synthesis settings. Earlier V9
labels motivated this consumed development study; they do not substitute for
fresh original-arm controls. No predictor is fitted.

## Complete paired outcome — pending

The primary endpoint is **CSD LUT4 minus original LUT4 over all 32 pairs**.
The completed report will include every original and CSD count, the complete
eight-constant by four-context delta matrix, mean, median, extrema, wins, ties
and losses. Context and constant summaries are descriptive. SB_CARRY counts
and changes will be reported separately from LUT4. Any disagreement between
fresh original measurements and the earlier V9 labels will accompany the result.

The [unfrozen plotting helper](../scripts/plot_v10_csd_hardware.py) is ready to
render publication PNG, SVG and PDF after outcomes and the full auditor report
exist. It requires the completed preparation/release, authenticates their file
hashes and complete arm/proof denominators, and matches all paired values to
the auditor report. It saves full original and CSD formulas, both resource
counts and the exact input hashes alongside the figures. No actual figure is
published on this pending page; synthetic layout files remain under `generated/`
and carry a visible **SYNTHETIC — NO EXPERIMENTAL RESULTS** label.

## Verification and interpretation

Universal high-level source QF_BV32 equivalence and universal equality of the
actual two emitted RTL modules are separate obligations. Source equivalence
alone does not validate the emitter. Mapped-netlist verification is sampled:
each of the 64 arms receives 100 boundary and 2,048 seeded input pairs, checked
at actual RTL and independently interpreted mapped netlist against the original
unsigned oracle. These samples do not constitute universal mapped equivalence.

LUT4 is an isolated-datapath FPGA resource proxy. These 32 fixed, consumed cases
do not support a population confidence interval, unseen-source generalization,
ASIC area, device timing, power, CPU integration or processor speedup claims.
All losses and ties must remain visible beside any gains. Native failures,
timeouts, raw sources, proof queries/logs, vectors and mapped netlists are
retained; later presentation must not select a favorable attempt.

## Evidence — pending completion

The final page will link the completed preparation, release, all proof verdicts,
all 64 arm records, raw archive, independent auditor report, full table and
figure data/hash manifest. Until those obligations are complete, numeric
outcomes and optimization claims remain pending.

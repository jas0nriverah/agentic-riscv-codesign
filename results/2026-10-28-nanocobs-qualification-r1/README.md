# Nanocobs baseline-only qualification: discovery failure

Source release `c121a0ec` was pushed before this run. Command: `.venv/bin/python scripts/qualify_nanocobs.py`. The sealed result records `failed` at discovery: **Too few calibrated executable candidates** for the fixed twelve-slot pool. Raw evidence is preserved in `raw.tar.gz`; no gate was changed and no rerun was attempted.

The original marked baseline completed its 8,215-case self-check: **96,372,374 cycles / 18,831,889 instructions**, 3,408 program/data bytes of 6,400, and 432 stack bytes of 1,664. Original and marked images passed the inherited identity check. These are discovery-profile measurements of the entire original probe, including reference/checker overhead, not standalone codec throughput or an optimized design.

The independent host oracle separately passed all 8,215 fixed inputs, and 15 focused workload/oracle tests passed. Qualification stopped before opportunity scoring, synthesis and routing. **Zero candidate attempts, speedup labels, area/timing outcomes, or model updates.**

Keep the formal failed status and first failure. The offline diagnosis is separate from this sealed archive. The next dataset step requires a workload with enough legal executable opportunities under the unchanged protocol.

[Offline diagnosis](../../reports/2026-10-28-nanocobs-diagnosis-r1/diagnosis.json) reconstructs 12 raw formulas, ten executable/relocation-safe/calibrated formulas versus twelve required. Even the maximum posthoc projected cycle reduction is only 0.2517%, below the 0.5% opportunity gate. That projection is not a measured custom-instruction speedup; the official opportunity phase was never reached.

# TACLeBench countnegative discovery rejection

**Preserved baseline-only rejection.** Preparation succeeded; discovery stopped because the exact relocation-safe calibrated candidate set did not satisfy the frozen twelve-candidate requirement. No smaller pool, fallback, or candidate dispatch was attempted.

Qualification commit: `1b831040`; protocol `d1ede28199a24bd842843471f45e44139845b111e0986a0d7afc08826be4f6b5`.
Target context: `44d4a7a49c5f756254544a61eea2bdc71d67deec212b72311be06d3e50026bd5`. Original checksum: **passed**.

## Discovery and fit

The instrumented profile recorded **12,477 cycles / 2,510 instructions**. These are discovery counters, not a routed baseline or speedup. Program/data ended at **2,472 / 6,400 bytes**; observed stack use was **64 / 1,664 bytes**.

Offline reconstruction finds **5 raw**, **5 executable**, **4 relocation-safe**, and **4 calibrated relocation-safe formulas**. The frozen requirement is **12**. Thus no twelve-candidate pool or public opportunity score exists.

Of the 4 calibrated formulas, 2 have operation-tree families absent from the historical feature corpus. This screening is not a model evaluation.

Candidate attempts, measured labels, routed baseline, area results, and timing results: **0**.

## Reproduction

```sh
../work/audit-venv/bin/python scripts/diagnose_tacle_countnegative_discovery.py
```

The baseline-only qualification has already been consumed and must not be rerun. Its original source, run receipts, and raw archive remain in `results/2026-10-27-countnegative-qualification/`. This command authenticates that evidence, replays extraction from the archived assembly/profile, and compares only public formula families with the frozen historical corpus; it adds no target jobs, labels, or model fits.

## Limits

- Profile counters are from the instrumented discovery simulation, not a routed baseline or measured speedup.
- The 12-formula pool and public opportunity gate were never reached; no public pool was frozen.
- Operation-family overlap is a public-feature audit of discovered formulas, not independent workload confirmation.
- Clock disagreement was flagged for both qualification subprocesses; monotonic durations are retained, with no uninterrupted wall-time claim.

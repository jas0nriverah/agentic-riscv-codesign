# Automatic RV32I CRC32 measurement checkpoint

Independent build context `63c7f40f7e906b046f5a1911d5ed91824bb1aa15673f8fa753a818ccc0d5f511`. Automatic profile/extraction/lowering uses actual RV32I PicoRV32 execution, the same path as aha-mont64. This does not replace the October 19 hand-adapter experiment or erase its slowdown.

Discovery: 37 raw formulas, **eight executable**, six frozen by merit before candidate measurements. All measurements use 12 MHz, baseline +128 LUT4, three routing seeds, and the original 8 KiB RAM / 4 KiB stack reservation.

| Candidate | Whole-program cycles | Speedup | LUT4 (added) | FF | Carry | Fmax MHz, seeds 1 / 2 / 3 | Correct |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Baseline | 32,387,382 | 1.000000× | 1653 (0) | 655 | 295 | 77.16 / 68.49 / 70.39 | Pass |
| 00: address + masked offset | 30,820,662 | 1.050833× | 1722 (+69) | 712 | 326 | 60.71 / 68.60 / 68.17 | Pass |
| 01: index offset | 30,820,662 | 1.050833× | 1684 (+31) | 688 | 297 | 76.59 / 72.04 / 71.49 | Pass |
| 02: address + offset | 31,516,982 | 1.027617× | 1723 (+70) | 712 | 326 | 61.85 / 71.05 / 64.92 | Pass |
| 03: index byte | 31,865,142 | 1.016389× | 1689 (+36) | 688 | 297 | 65.66 / 67.69 / 68.13 | Pass |
| 04: masked offset | 31,516,982 | 1.027617× | 1687 (+34) | 688 | 297 | 72.75 / 72.60 / 74.18 | Pass |
| 05: shift xor | 31,516,982 | 1.027617× | 1718 (+65) | 712 | 297 | 71.34 / 68.39 / 71.76 | Pass |

All use 20 RAM4K blocks and pass common-clock routing constraints. Fmax values are internal routed estimates, not board measurements. `audit.json` gives exact formulas, counters, resources, timing, and conditional clock-adjusted ratios. The best speedup ties; candidate 01 has lower measured area. Some results differ from same-formula hand adapters because actual lowered software differs. A formula alone is not a program-speedup identity.

Cost: 119 native commands, 272.778 command-seconds, no failed commands. Candidate measurement wall time totals 253.563 seconds; baseline and discovery costs are separate. Do not add overlapping wall and command timings.

`raw.tar.gz` and `archive-manifest.json` preserve raw evidence and checksums. The source snapshot and environment record support replay. `selection-report.json` retains the unchanged within-workload policy replay: 120 outcomes, no historical labels. **Template correction:** its inherited aha-specific limitation says “other 15 executable formulas”; for this CRC32 context there are **two** unmeasured executable formulas. The audited counts above and in `audit.json` are authoritative. That frozen template wording does not affect numerical outcomes.

```sh
python scripts/reproduce_workload.py replay \
  --snapshot results/2026-10-20-automatic-crc32 \
  --output generated/reproduction/automatic-crc32-2026-10-20
```

[Cross-workload development comparison](../../docs/selection-pilot-results.md)

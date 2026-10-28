# Nanocobs v2 variable-pool qualification — accepted

Source release `661fe4a4` was pushed before the run. The owner removed fixed candidate-count and projected-benefit/replacement admission requirements. This revised experiment preserves the earlier r1 rejection; the source was already screened and is not a new untouched-source discovery.

Commands:

```sh
.venv/bin/python scripts/qualify_nanocobs_v2.py
.venv/bin/python -m isaforge.nanocobs_v2_workload audit --root generated/nanocobs-v2-qualification-2026-10-28-r1
```

All six phases passed: preparation, discovery, admission, baseline, public evidence and pool freeze. Independent baseline audit also passed. The immutable plan records compute cap30, while discovery authenticates ten actual candidates. No minimum benefit or replacement count was applied; all ten supported legal candidates were retained.

| Measured baseline outcome | Value |
|---|---:|
| Whole fixed-probe cycles | 96,372,374 |
| Instructions | 18,831,889 |
| LUT4 / carry / RAM blocks / flip-flops | 1,653 / 295 / 20 / 655 |
| Routed Fmax, seeds 1/2/3 | 77.160 / 68.493 / 70.388 MHz |
| Timing floor | 12 MHz; all pass |
| Program/data bytes | 3,408 / 6,400 |
| Observed stack bytes | 432 / 1,664 |
| Original fixed-input self-check | Pass |
| Candidate measurements / new speedup labels | 0 / 0 |

The measured program includes the original production codec, scalar reference, input generation and checker; this is not standalone codec throughput. The separate host oracle passed all 8,215 short payloads. Neither establishes arbitrary-input correctness. Candidate semantic checks and final optimized-program execution remain required at measurement time.

The existing extractor remains restricted to profiled source-mapped expressions of at most four operations with supported calibration and relocation-safe lowering. This is not arbitrary RISC-V candidate support. There were no uncalibrated exclusions for this pool. The prospective selector release still needs family exclusions against historical and recent workload pools, frozen model/policy predictions, and equal requested/effective measurement budgets. No retraining or model improvement is claimed.

Sixteen v2 focused tests passed before this run; frozen model and processor-evidence replays passed. Raw source-bound qualification logs, protocol, source snapshots and archive are preserved alongside this README.

Full regression validation: `make test PYTHON=.venv/bin/python` passed **4,554 tests and 181 subtests**, with one expected duplicate-ZIP-member fixture warning, in 243.67 seconds. `make reproduce reproduce-speedup PYTHON=.venv/bin/python` also passed.

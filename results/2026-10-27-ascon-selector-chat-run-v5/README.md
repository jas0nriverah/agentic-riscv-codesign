# Ascon current-chat selector run (v5 release)

This is a three-query, operator-relayed current-Codex chat run on the frozen Ascon v1.3.0 target pool. It is same-domain crypto-transfer development evidence, not independent-workload confirmation. The controller release and preregistration were source-closed and pushed before dispatch.

## Results

| Handle | Formula | Cycles | Speedup | Added LUT4 | Minimum routed Fmax | Correct | Feasible at +64 LUT4 / 12 MHz |
|---|---|---:|---:|---:|---:|---|---|
| C01 | `and(xori(in0,-1),in1)` | 242,448,246 | 1.019698x | +73 | 62.992 MHz | yes | no (area) |
| C06 | `add(slli(in0,31),in1)` | 243,085,014 | 1.017027x | +41 | 67.069 MHz | yes | yes |
| C02 | `add(slli(in0,31),srli(in1,1))` | 241,493,094 | 1.023731x | +42 | 64.620 MHz | yes | yes |

C02 is the best verified feasible candidate among the three measured attempts. Nine candidates remain unmeasured, so the measured-pool oracle is incomplete and no regret-versus-oracle or heuristic superiority claim is supported. The speedup labels equal the independent calibrated-latency estimates for these three rows.

## Limitation discovered

The guarded outcome audit omits `status` for successful rows. The controller's adaptive-GP code filtered successes only with `row.get("status") == "success"`, so the paid-prefix refit saw no successes and recorded zero fit time. This invalidates adaptive-GP updates in this run. The LLM could see the paid outcomes, but this run is not valid evidence that the adaptive-GP update works. A regression fix and new source-bound release are required before another adaptive-policy measurement.

## Reproduction and integrity

The full generated campaign, including source inputs, controller journal, durable attempt slots, Verilator/synthesis/route outputs and labels, is preserved in `raw-evidence.zip`. Verify its archive hash and every member against `raw-manifest.json`. The exact source release commit is recorded in `report.json`; controller release and preregistration remain at `results/2026-10-27-ascon-selector-controller-release-v5` and `results/2026-10-27-ascon-selector-prereg-v3`.

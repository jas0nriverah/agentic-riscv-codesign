# LLVM Stanford Queens discovery diagnosis

This post-run report authenticates and explains the preserved baseline-only qualification. It does not edit the failed qualification or launch native tools.

## Result

- The original fixed workload passed its self-check: 5,000 solves; instrumented discovery profile 465,269,849 cycles / 85,567,250 instructions.
- Firmware and data ended at 1,160 bytes under the 6,400-byte limit; the declared stack partition was 1,664 bytes.
- Frozen pool gate requires 12 candidates; the unchanged extractor found 3 calibrated executable formulas from 3 raw formulas.
- Best analytic estimate is 600 cycles (0.000129%); the unchanged 0.5% gate needs 2,326,349 cycles plus ten replacements.
- Conclusion: source lead rejected at discovery under existing gates. Do not shrink the workload, pool, or thresholds.

## Extracted formulas

| Candidate | Formula | Replacements | Estimated saved cycles | Historical family overlap |
|---|---|---:|---:|---|
| candidate_00 | `addi(lui(0),1124)` | 200 | 600 | yes |
| candidate_01 | `sltiu(addi(in0,-101),1)` | 1 | 3 | no |
| candidate_02 | `sub(0,xori(in0,1))` | 1 | 3 | no |

## Limits

- This was not a routed baseline, candidate measurement, or performance-area result.
- No candidate labels were generated; model training and selection did not run.
- The exact qualification remains classified `failed` in its sealed output. This diagnosis attributes the failure to the explicit too-few-candidates extractor gate and independently recomputes the shortfall.
- Keep the run as a negative workload qualification; do not retry with relaxed gates.

Reproduce with `scripts/diagnose_llvm_queens_discovery.py`; verify the report with `--verify`.

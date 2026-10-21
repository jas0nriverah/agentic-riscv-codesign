# BEEBS jfdctint qualification — October 21, 2026

The original BEEBS integer JPEG DCT passes the complete upstream 64-coefficient verifier on the existing RV32I PicoRV32 processor. This is **BEEBS**, not Embench. The pinned source is unchanged: `mageec/beebs@049ded9f3aeb5591f553879d3a0376b8614e9422`, `src/jfdctint/libjfdctint.c`, 13,463 bytes, SHA256 `2fb8b63b4e0da2012da6d63617e99b4f7ef263899ad01f0426d1277466a79c5e`. The vendored GPL COPYING file and source notices are preserved in `benchmarks/beebs/`.

A declared no-op `warm_caches` function, appended only to the copied generic harness, supplies the missing Embench-compatible ABI entrypoint. It changes no benchmark arithmetic, seed, input, transform or verification. The original initializer uses seed 1, the benchmark executes one complete transform, and the original verifier compares all 64 coefficients.

## Accepted baseline and frozen pool

The accepted context is `9a2098d3c3dbeefdada16733113567bfd5c04ad2073bd423e2ded9db663c717f`, under `generated/beebs-jfdctint-2026-10-21-r2`. Group and public benchmark identities are `beebs-jfdctint`. The compiler is pinned RV32I ILP32 `-Os`, with existing software multiplication and unchanged processor/memory RTL.

| Check | Recorded result |
| --- | --- |
| Static program and BSS end | 2,380 bytes |
| Checked partition | Program limit 3,072; stack floor 3,200; 128-byte guard; 4,992-byte stack reservation |
| Full baseline execution | 117,522 cycles; 23,428 instructions; upstream self-check passes |
| Observed stack | 304 bytes; 4,688 bytes headroom |
| Integrated baseline | 1,653 LUT4; all three routing seeds fit and pass 12 MHz |
| Minimum routed Fmax | 68.49314880371094 MHz |
| Candidate discovery | Six candidates from 29 guarded, calibrated, executable formulas |
| Pool names | `candidate_00`, `candidate_06`, `candidate_11`, `candidate_17`, `candidate_22`, `candidate_28` |
| Candidate attempts at this checkpoint | **Zero** |

The baseline protocol SHA256 is `6f8d9a21a65ba8de35f88588151fdae8930841aa4f2029efb566c3b2d2ce8630`. `r2-baseline/` preserves the sealed prelabel plan, public features, context, receipt/hash bindings, native evaluation protocol, strict audit and outer timing records. Complete r2 raw evidence will be archived once by the candidate campaign; this qualification package does not duplicate that baseline archive. Candidate measurements require the separately committed model/prediction preregistration.

## Preserved qualification failures and costs

The first `4096/4224` partition failed its deliberately invalid stack-pointer fixture before any benchmark or candidate execution. `li sp,4220` expands to an intermediate `lui sp,4096`, which the continuous stack monitor correctly detects below the 4,224 floor before the intended final 4,220 address. The existing fixture requires its declared first address, so it rejects that observation. The failed root is preserved as `failed-guard-fixture/raw.tar.gz`, including its original wrapper source snapshot, inputs, compile/disassembly/symbol records, raw simulation, command receipts and failure record. Its `obj_dir` build trees and lock file are excluded. No monitor or RTL workaround was introduced, and the failed context was not retried. The accepted fresh r2 partition has a valid intermediate SP before its deliberate underflow.

The source-only matmult inspection is separately recorded in `matmult-static-analysis.json`. Its **five** live 20×20 RV32 ILP32 `long` matrices need 8,000 bytes before code, constants or `Seed`, exceeding the 7,552-byte maximum program region with a minimum 512-byte stack and 128-byte guard. The earlier linker failure remains documented in `docs/codesign-loop.md`. This inspection launched no new compiler/native jobs and produced no labels.

| Cost scope | Seconds |
| --- | ---: |
| Independent static jfdctint compile/link | 0.494943041 |
| Failed first guard-fixture CLI operation | 3.938867208 |
| Accepted r2 prepare/discover/baseline/public/freeze CLI operations | 44.792233583 |
| r2 baseline ledger | 27.569973708 |
| r2 baseline measurement record | 27.113970333 |
| r2 native commands, 31 total | 36.718795128 |

The first three rows describe separate operations. The last three **overlap** the r2 CLI time and each other; do not add them. Individual CLI records cover evaluator creation, repeated discovery authentication, guarded work, lock close and JSON formatting, excluding the final timing-record write. This is not a lifetime or gap-inclusive project timer. Archive/hash work and later model fitting are separate. No candidate cost or successful candidate label is invented from these diagnostics.

## Recorded commands

These are the actual qualification command forms; the failed initial context is preserved and must not be overwritten or silently rerun. Every command used the pinned Python below. The exact static compiler argv is preserved in `static-link/raw.tar.gz` → `diagnostic.json` with its map, ELF, symbols and log.

```sh
PYTHON=/Users/jasonrivera/Documents/Codex/2026-10-19/clo/work/audit-venv/bin/python
"$PYTHON" -m isaforge.beebs_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/beebs-jfdctint-2026-10-21
"$PYTHON" -m isaforge.beebs_workload discover \
  --root generated/beebs-jfdctint-2026-10-21  # Preserved failed guard fixture.
# After declaring the fresh 3072/3200 partition in the new bound wrapper:
"$PYTHON" -m isaforge.beebs_workload prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/beebs-jfdctint-2026-10-21-r2
"$PYTHON" -m isaforge.beebs_workload discover --root generated/beebs-jfdctint-2026-10-21-r2
"$PYTHON" -m isaforge.beebs_workload baseline --root generated/beebs-jfdctint-2026-10-21-r2
"$PYTHON" -m isaforge.beebs_workload public --root generated/beebs-jfdctint-2026-10-21-r2
"$PYTHON" -m isaforge.beebs_workload freeze --root generated/beebs-jfdctint-2026-10-21-r2
"$PYTHON" -m pytest tests/test_beebs_workload.py -q
```

Five wrapper/source/group/audit tests pass. Both archives use the existing `scripts.reproduce_codesign.pack_archive`; archive manifests bind every retained file. `qualification-summary.json` records exact facts and scopes; `source-manifest.json` binds current source and packaging code; `manifest.json` binds the complete package. No candidate measurements or model tuning were performed by this qualification report.

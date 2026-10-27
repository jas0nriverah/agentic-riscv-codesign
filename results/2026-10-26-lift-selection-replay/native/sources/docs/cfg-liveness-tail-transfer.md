# CFG coverage v2: exact direct tail transfers

## Why this is a separate context

The first CFG-aware Lift qualification remains rejected and immutable at [its recorded result](../results/2026-10-25-lift-cfg-qualification/qualification.json). Preparation succeeded, but discovery failed closed before candidate dispatch because four instructions were unresolved indirect controls at PCs 944, 1972, 2216 and 2336. The saved disassembly shows each is an adjacent `auipc t1, imm` / `jalr x0, t1, offset` pair with a statically resolved in-program target. This is a compiler-emitted non-linking tail transfer. The v1 analyzer deliberately recognized only `x1`-linking calls and canonical ABI returns.

This v2 contract extends static control-flow closure for that exact machine pattern. It does not retry or relabel either earlier Lift rejection, and it does not change the liveness proof, workload, input, compiler flags, hardware, pool size, stratification or opportunity gate. Its own result is versioned and source-bound. Lift remains consumed engineering evidence, not untouched model confirmation.

## Tail-transfer proof rule

Recognize a transfer only when the complete decoded program contains adjacent raw RV32 words:

- `AUIPC rd, upper`, where `rd` is nonzero;
- `JALR x0, rd, offset` using that same register.

Recompute the target as `((auipc_pc + upper + offset) mod 2^32) & ~1`. Require a four-byte-aligned target present in the decoded static program. Collect all branch targets, direct-call targets, call continuations and proposed call/tail targets before accepting any pair. Refuse extraction if any static entry can land on the JALR second word. Calls and tail transfers remain all-register-live barriers; neither may be fused or crossed. The tail edge has only its resolved target, since `rd=x0` does not create a return continuation.

This rule does not propagate register values, infer a target from profiling, resolve arbitrary JALR instructions, accept register-indirect calls, or change the explicit ordinary-C ABI return assumption. Every other indirect or unknown transfer remains a global extraction rejection. The analysis binds exact raw instructions, whole-program bytes, source-PC mapping and its new schema; verifier calls independently rederive the proof from saved inputs.

## Validation and native boundary

Pure checks cover signed/wrapped RV32 target arithmetic, `JALR` bit-zero clearing, alignment, target presence, exact raw words and register matches, and direct entry into the second word. Calls and tail transfers both remain barriers. A replay against the already saved original marked Lift binary may count coverage, but it is not a native candidate result.

Only after the v2 source and contract are pushed may the distinct baseline-only qualification run:

```sh
../work/audit-venv/bin/python scripts/qualify_cfg_lift_tail.py \
  --output results/2026-10-25-lift-cfg-tail-qualification \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25
```

It preserves the original 1,001 zero-input iterations and checksum 4005888, RV32I_zicsr/ILP32 `-Os`, 8 KiB RAM, 6400/6528 partition, one-wait PCPI, twelve-formula pool and joint >=0.5% / ten-execution gate. Candidate dispatch remains disabled. Acceptance can establish a qualified pool and unextended baseline only; it adds no candidate speedup or hardware labels. Preserve any rejection. Any later candidate collection first needs a separately pushed complete model/controller release, then matched controls and verified program-level and integrated-hardware outcomes.

## Current status

The v1 failure remains final. Its qualification stopped in discovery with zero candidate attempts because of four direct tail transfers. A separate v2 source-bound preflight now authenticates each consumed disassembly/profile/calibration file against that rejection's raw archive before replaying extraction.

Offline preflight command:

```sh
../work/audit-venv/bin/python scripts/preflight_cfg_lift_tail.py \
  --output results/2026-10-25-lift-cfg-tail-preflight.json
```

From the archived Lift image, v2 resolves the four direct tail transfers and reproduces 17 executable formulas. The unchanged relocation guard removes four, calibration excludes none, and the original even-rank stratifier selects twelve formulas from the remaining thirteen at indices `[0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]`. The source-bound record is [here](../results/2026-10-25-lift-cfg-tail-preflight.json). This is consumed engineering coverage replay, not untouched confirmation, native qualification, candidate measurement, speedup evidence, area/timing evidence, or model improvement. The run launches no compiler, simulator, synthesis, or routing job.

The focused v1/v2 CFG regression passes **199 tests**, including explicit checks that changed or missing saved inputs fail against the v1 archive. The v2 source and contract must be pushed before this distinct, baseline-only qualification is attempted:

```sh
../work/audit-venv/bin/python scripts/qualify_cfg_lift_tail.py \
  --output results/2026-10-25-lift-cfg-tail-qualification \
  --native-root generated/tacle-lift-cfg-tail-2026-10-25
```

Candidate dispatch remains disabled. Qualification acceptance can establish only that the unchanged Lift workload produces the predeclared candidate pool and baseline; it adds no candidate speedup or hardware labels. Preserve its first rejection if it fails. No v2 native qualification, candidate measurement, area/timing result, or model improvement has yet been established.

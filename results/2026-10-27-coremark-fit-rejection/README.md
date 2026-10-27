# CoreMark v1.01 baseline-fit rejection

This preserves a baseline-only screen under ISAForge’s existing PicoRV32/RV32I memory contract. It produced no candidate measurements.

The source is the official EEMBC CoreMark v1.01 tag at commit `cfa9ab377835911f23d9b0831c7be302ed1f58de`. The workload configuration uses the standard 2 KB validation data size, validation seeds `0x3415, 0x3415, 0x66`, stack data allocation, and a fixed 10-iteration simulator run. Fixed iterations would be shared by every design; this is not an official CoreMark performance score.

The target build compiled the upstream translation units separately with the pinned RV32I/Zicsr ILP32 GCC 15.2 toolchain and `-O2`, using the unmodified v1.01 port header and the existing PicoRV32 SoC. The linker rejected the firmware: `.text` does not fit, and the 8 KiB RAM region overflows by **6,360 bytes**. The existing linker reserves 4 KiB for stack. The complete linker map and per-file logs are in `native/`; the exact command structure, flags, tool hashes, and source hashes are in `protocol.json`.

No target simulation, baseline cycle count, candidate extraction, candidate pool, target correctness result, synthesis, routing, or speedup label exists. Candidate dispatch remained disabled. Do not shrink the workload, change `-O2`, enlarge RAM, or relax the stack guard to clear this gate.

A separate host-only smoke check with the three CRC oracles passed at 10 iterations (`list=e3c1`, `matrix=0747`, `state=8d84`). It used a host pointer-width port adaptation and treats only the benchmark’s 10-second reporting threshold as non-fatal. That check does not establish target compatibility, target correctness, fit, or performance.

This screen also does not establish algorithmic independence from prior candidate families; no target formulas were extracted. CoreMark is not counted as an eligible workload family. The failure adds no model evidence.

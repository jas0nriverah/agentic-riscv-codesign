# Pinned TACLeBench bitcount

The eight upstream files in `bitcount/` are byte-identical to
[TACLeBench commit c6a0d73](https://github.com/tacle/tacle-bench/tree/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08/bench/kernel/bitcount).
[SOURCES.json](SOURCES.json) records the exact primary archive hash, file SHA256s
and independently checked upstream Git blob IDs. Original notices and the
upstream `LICENSE` remain intact; they permit use, modification and redistribution.

`isaforge_adapter.c` is an external ABI/build adapter. It includes all five
original C files and the original header in one translation unit, renames the
original `main` and the two conflicting private lookup arrays, and supplies the
existing processor harness interface. The arrays retain separate storage. The
declared compilation context is ILP32 RV32I_zicsr `-Os` with amalgamation; it is
not a claim of binary identity with an upstream separate-object build. Marking
must still produce a byte-identical baseline firmware image before lowering.

The original random seed1, eight algorithms, ten iterations per algorithm,
initialization and aggregate1095 return check are unchanged. Initialization is
outside the measured interval; all eight algorithms and their input generation
are inside it. The upstream aggregate check is a fixed-input correctness test,
not a universal proof or a separate check of every intermediate result. The
existing sampled low-level rewrite checks and processor controls are also required.

The new `isaforge.tacle_workload` entrypoint reuses the frozen guarded extractor,
relocation rejection, assembly lowering, memory monitor and integrated8KiB
PicoRV32/PCPI evaluator. The twelve-formula pool and same-candidate minimum0.5%
calibrated cycle-reduction/ten-execution gate are fixed before profiling. No
earlier rejected context is retried or weakened. This source is not Embench or
BEEBS. Candidate measurements require a complete committed, pushed model package
and the original one-attempt ledger.

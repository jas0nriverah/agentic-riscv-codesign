# Nanocobs: concrete new workload lead

October 28, 2026. Source, host-correctness and RV32 link preflight succeeded.
This is not yet an accepted candidate pool or a set of training labels.

## Source and fixed input

Pinned [nanocobs](https://github.com/charlesnicholson/nanocobs) commit
`8d47d35ebe81c7caecc2b8954b1355d223ecabcb` implements Consistent Overhead Byte
Stuffing for communication framing. The original freestanding
[`tests/qemu/probe.c`](https://github.com/charlesnicholson/nanocobs/blob/8d47d35ebe81c7caecc2b8954b1355d223ecabcb/tests/qemu/probe.c)
enumerates every binary payload of lengths 0–12 (8,191 cases) and 24 additional
zero/data runs. All 8,215 original cases are preserved. Source and tests are
Unlicense OR 0BSD; the excluded doctest dependency is unnecessary here.

`inputs/upstream/` holds exact upstream files. `source-pin.json` hashes every
source, adapter, runtime and linker input. The ABI adapter includes the original
probe unchanged, suppresses printing, resets its counters, and requires both
zero failures and 8,215 successes. Production and scalar reference remain
separate translation units. Both are included in the preliminary timed scope.

## Executed evidence

| Check | Observed outcome |
| --- | --- |
| Host build with `COBS_SWAR_WORD_BITS=32` | Passed |
| Original complete host probe | **8,215 / 8,215 passed**, exit 0 |
| Upstream `COBS_PROBE_FAULT` control | **8,214 / 8,215**, expected exit 1 |
| RV32I/Zicsr, ILP32, `-Os` freestanding link | Passed with existing ISAForge startup, harness and byte-memory routines |
| `_program_end` | **3,408 bytes / 6,400-byte limit** |
| Unresolved target symbols | None |
| Independent reproduction from captured source inputs | Passed; same counts and linked size |
| Target simulation, measured stack, candidate pool, speedup/PPA labels | **Not performed / unknown / zero labels** |

The host still has 64-bit `size_t`; the explicit macro tests the 32-bit SWAR
path there. Host success must not be presented as RV32 execution. GCC's static
stack records give a 192-byte probe frame and smaller callee frames, but these
are not a measured call-chain high-water mark.

On this RV32 build, `cobs_word_load` calls the existing byte-copy `memcpy` and
then reads an aligned local word. Thus the examined load does not require
hardware unaligned-word support. That software-copy overhead is retained and
may limit the opportunity for speedup. The linker reports the expected RWX
load-segment warning for this bare-metal combined RAM image.

## Why pursue it

The program has bounded storage, no heap, no file input and no function-pointer
dispatch. Its runtime SWAR expression `(w - 0x01010101) & ~w & 0x80808080`,
buffer-index arithmetic and protocol-state calculations are plausible fusion
opportunities. Their actual compiler-emitted candidate count, relocation
safety, liveness and overlap with historical families remain unknown.

The differential reference is the **same implementation compiled with SWAR
disabled**, so common-mode codec bugs may survive. Round-trip and buffer checks
add useful evidence but do not prove general codec correctness. The fixed probe
does not cover arbitrary byte payloads, malformed frames or 254-byte boundaries.
Production candidate rewriting must exclude the reference, probe and verifier.
This is a protocol-framing source lead; independent formula-family status is
not established.

## Reproduce

Supply the path to the pinned xPack RISC-V GCC 15.2.0 toolchain. The recorded GCC
SHA-256 is in `report.json`; alternate toolchains are a different preflight.

```sh
python3 results/2026-10-28-nanocobs-source-preflight-r1/reproduce.py \
  --riscv-gcc /absolute/path/to/riscv-none-elf-gcc \
  --output generated/nanocobs-preflight-fresh
```

The script authenticates inputs, reruns the two host controls, links the RV32
firmware, checks unresolved symbols and the partition, and writes fresh command
logs and a report. It never launches a processor simulation, hardware job or
candidate evaluation. `original-run/` preserves initial commands/disassembly;
`reproduction/` records the repeat from this portable input package.

## Next engineering step

Freeze the full unchanged input suite, precise production-only rewrite scope,
oracle limitations and multi-translation-unit build in a baseline qualification
adapter. Then check target correctness, actual stack use, CFG support, twelve
legal calibrated candidates, and the existing joint 0.5%/ten-execution
opportunity gate. Only after qualification should a separate policy/model release
authorize candidate labels. No training data or model performance is claimed here.

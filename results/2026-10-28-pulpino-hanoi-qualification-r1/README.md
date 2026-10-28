# PULPino Hanoi qualification — source-pool rejection

## Result

The pinned PULPino twelve-plate Tower of Hanoi program is **not eligible for a
candidate campaign under the existing gates**. The source compiled and its
baseline self-check passed, but automatic discovery found only three formulas;
the relocation guard correctly rejected all three because they remove
`%hi/%lo` relocations for global arrays `A`, `B`, and `C`. That leaves zero
legal candidates for the frozen pool of twelve. Candidate dispatch stayed
disabled, so this run produced **zero candidate measurements and zero speedup,
area, or routing labels**.

The source-level diagnosis is recorded in
[`discovery-diagnosis.json`](discovery-diagnosis.json). The original qualification
wrapper records the `discover` command as failed because the generic extractor
raises when fewer than twelve calibrated candidates are present. The
post-run diagnosis separately adjudicates that preserved result as an
eligibility rejection, not a compiler, simulator, or hardware failure.

## Fixed experiment

- Upstream: PULPino commit `6631c49ba38a9258da44d6b120d902f7b81f9233`.
- Input: original twelve plates and recursive `ToH` / `computeGold` algorithm.
- Compiler and processor: existing RV32I/Zicsr, ILP32, `-Os`, PicoRV32/PCPI
  pipeline; same 8 KiB RAM partition, 12 MHz target, and routing seeds reserved
  by the project protocol.
- Candidate rules: twelve candidates, relocation-free lowering, and the
  unchanged joint opportunity threshold of at least 0.5% calibrated cycle
  reduction and ten timed replacements for the same candidate.
- Source lineage: separate PULPino program group, but related recursive
  embedded-test-suite evidence. It is not an independent application-family
  confirmation.

The adapter keeps the upstream algorithm bodies text-identical and checks the
upstream destination condition `B[i] == i` for all twelve entries. The target
baseline self-check passed at **416,259 cycles / 71,780 instructions**. The
continuous stack monitor observed **432 bytes used**, leaving **1,232 bytes of
headroom** under the shared 1,664-byte stack reservation. These are baseline
simulation results, not candidate speedups or routed hardware results.

## Discovery evidence

| Stage | Count | Outcome |
| --- | ---: | --- |
| Raw formulas | 3 | All are global-array address expressions |
| Executable formulas | 3 | Passed the existing formula/lowering checks |
| Relocation-safe formulas | 0 | Every formula removes symbolic `%hi/%lo` operands |
| Calibrated legal formulas | 0 | No legal formula remains to calibrate |
| Required pool | 12 | Unchanged |
| Candidate attempts / labels | 0 / 0 | Dispatch was disabled |

The formulas were `addi(lui(0),508)`, `addi(lui(0),520)`, and
`addi(lui(0),532)`. They correspond to address construction for `C`, `B`, and
`A`; none represents a useful arithmetic fusion. The fixed pool and
relocation guard were not changed. The opportunity gate, routed baseline
measurement, synthesis, and routing phases were not reached.

## Commands and evidence

The one-time qualification command was:

```sh
.venv/bin/python scripts/qualify_pulpino_hanoi.py
```

It completed source preparation, compiled/ran the checked baseline, and
stopped at automatic discovery. To reproduce the read-only diagnosis from a
fresh checkout, unpack the archived target root to a new directory and direct
the output to a fresh filename:

```sh
mkdir -p generated/pulpino-hanoi-r1-replay
tar -xzf results/2026-10-28-pulpino-hanoi-qualification-r1/raw.tar.gz \
  -C generated/pulpino-hanoi-r1-replay
.venv/bin/python scripts/diagnose_pulpino_hanoi_discovery.py \
  --native-root generated/pulpino-hanoi-r1-replay \
  --output /tmp/pulpino-hanoi-diagnosis-reproduction.json
```

It reproduced the 3 / 3 / 0 / 0 formula counts using the preserved assembly,
symbols, disassembly, latency table, and profile. Its output binds those files
by SHA-256. The original command receipts and full generated archive are in
[`raw.tar.gz`](raw.tar.gz); the frozen zero-candidate protocol is in
[`protocol.json`](protocol.json), and the original qualification status is in
[`qualification.json`](qualification.json). The post-run human-readable
interpretation and diagnosis are listed in
[`postrun-addendum-manifest.json`](postrun-addendum-manifest.json), separate
from the original qualification manifest.

The adapter/contract suite passes **10 tests**. The full repository suite now
passes **4,504 tests and 181 subtests**, with one existing duplicate-ZIP-name
warning.

## Next blocker

Hanoi cannot contribute measured labels unless a different, independently
justified candidate interface can safely handle relocation-bearing address
construction. That would change the candidate interface and needs its own
research review. Do not move the arrays, strip relocation metadata, weaken the
guard, reduce the pool, or reduce the opportunity threshold to rescue this
input. Continue with a different untouched workload that naturally yields at
least twelve legal candidates under the existing contract.

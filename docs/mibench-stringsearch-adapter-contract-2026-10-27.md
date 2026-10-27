# MiBench stringsearch adapter contract

This is a new baseline-only qualification path for the MiBench small
Pratt-Boyer-Moore workload. Its purpose is to test whether the existing guarded
PicoRV32 extraction pipeline can support another independent source family;
it is not yet a measured candidate pool or an ML result.

The source is pinned to Embecosm MiBench commit
`092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57`. The vendored
`pbmsrch_small.c` is byte-identical to upstream, including its fixed 57
pattern/text pairs. The directory license file says to assume GPL, while the
source attributes public-domain status to its author. Both notices are
preserved; the project treats it conservatively as GPL without asserting a
version. See the [source pin](../benchmarks/mibench/stringsearch/MIBENCH_SOURCE_PIN.json).

The adapter only renames upstream `main`, replaces the two `printf` forms and
`putchar` with a no-I/O result-capture shim, adds the existing benchmark ABI,
and supplies freestanding `strlen`/`strncmp`. Its verifier checks all 57 actual
hit/miss results and offsets against a pinned independent Python `str.find`
oracle after the measured cycle interval. The capture shim executes within
`benchmark()` and contributes a small, explicit bookkeeping cost to reported
cycles. The host test confirms all 57 cases; this does not prove correctness on
unseen strings.

The target contract is unchanged: RV32I with Zicsr, ILP32, GCC `-Os`, the
existing PicoRV32/PCPI implementation, the 8 KiB RAM with a 6,400-byte
program/data ceiling and 1,664-byte stack, original three-route timing policy,
12 MHz minimum, 12 candidates, and the joint public 0.5% cycle-reduction / 10
timed-replacement opportunity threshold. Candidate dispatch is disabled during
qualification. A failed source, memory, correctness, extraction, pool, or
opportunity gate is preserved as a rejection; no threshold or input may be
changed to rescue it.

Run the host contract test with:

```sh
../work/audit-venv/bin/python -m pytest tests/test_mibench_stringsearch_workload.py -q
```

The target baseline-only qualification command is:

```sh
../work/audit-venv/bin/python scripts/qualify_mibench_stringsearch.py
```

An accepted baseline qualification is still not candidate performance
evidence. Exact emitted formula families must be audited against historical
training pools. Any paid evaluation requires a fresh source-bound release,
frozen policies and equal-budget controls before its first label.

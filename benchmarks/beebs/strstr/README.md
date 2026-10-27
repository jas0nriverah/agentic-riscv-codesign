# Pinned BEEBS `strstr`

This directory holds the byte-identical `src/strstr/libstrstr.c` from BEEBS
commit `049ded9f3aeb5591f553879d3a0376b8614e9422`. The source SHA-256, Git blob
ID, and retained suite license are in
[`STRSTR_SOURCE_PIN.json`](STRSTR_SOURCE_PIN.json). The implementation is
credited upstream to Stephen R. van den Berg and GNU libc; the benchmark wrapper
and verifier are also upstream source and have not been edited.

The fixed wrapper repeatedly calls `strstr(f + 1, "abba")` over the original
68-byte string. It deliberately skips the match at offset zero, finds matches
at offsets 4, 17, 31, 36, 45, 50, and 64, then makes one final failed call. The
upstream verifier checks that the total call count is eight. It does not check
the individual offsets; the separate host preflight compares them with a simple
reference scan without changing the timed target wrapper.

This is a distinct literal-substring-search implementation compared with the
consumed Embench SLRE regular-expression engine, but both belong to text
processing. Treat it as a provisional same-domain transfer source, not yet as
an independent confirmatory family. Candidate-operation overlap, target fit,
and opportunity remain to be established under the unchanged gates.

The existing harness supplies only a no-op `warm_caches` ABI hook. The
qualification preserves RV32I/ILP32 `-Os`, the original input and algorithm,
the 8 KiB RAM, 6,400-byte program/data cap, 6,528-byte stack floor, 12 MHz
constraint, twelve-candidate pool, and joint public opportunity gate.

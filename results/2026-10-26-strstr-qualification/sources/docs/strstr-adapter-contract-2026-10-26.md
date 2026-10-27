# BEEBS `strstr` source and adapter contract

**Status: source pinned and host behavior checked; target qualification has not
run.** This is a preparatory workload integration, not a measured result or a
claim of broad workload-family independence.

## Source identity and family scope

The source is byte-identical to BEEBS commit
`049ded9f3aeb5591f553879d3a0376b8614e9422`, path
`src/strstr/libstrstr.c`. Its SHA-256, Git blob ID and license digest are bound
in [`STRSTR_SOURCE_PIN.json`](../benchmarks/beebs/strstr/STRSTR_SOURCE_PIN.json).
The upstream copyright and GPL-3.0-or-later terms are retained with the suite's
`COPYING` file.

The implementation credits Stephen R. van den Berg/GNU libc and performs
literal substring matching. The consumed Embench SLRE source credits Sergey
Lyubka/Cesanta and implements a regex engine with classes, alternation,
captures and quantifiers. The algorithms and source lineages differ. They are
both text-processing workloads, so `strstr` is only a provisional same-domain
transfer source until the project freezes its source-family taxonomy and the
candidate/formula-family overlap audit. A separate benchmark name or author
does not establish independent evidence.

## Exact fixed-input behavior

The full upstream source, input, timed wrapper and verifier remain unchanged.
The wrapper starts with `f = text`, searches from `f + 1`, increments its call
counter for each result including the terminal miss, and expects eight calls.
This skips the offset-zero match. A separate host test independently scans the
fixed string and checks returned offsets `4, 17, 31, 36, 45, 50, 64`, followed by
the null result. This supplements the host preflight only; the target's original
scalar verifier remains unchanged and checks only the count, not match
locations. No claim is made about arbitrary strings or needles.

The implementation decrements `haystack` at entry, marked upstream as a
possible ANSI violation. In every fixed wrapper call, the input pointer is
`f + 1` within the same string object, so this returns to a position inside
that object. This scoped reasoning does not prove general API safety.

## Permitted integration

The only harness addition is the existing generic no-op `warm_caches` hook.
Do not rewrite the matcher, change the search strings, add repetitions, alter
the verifier, or change compiler flags. The baseline-only evaluator exposes
`prepare`, `discover`, `opportunity`, `baseline`, `public`, `freeze`, and
`audit`; it rejects candidate measurements. Discovery and baseline work must
leave zero candidate attempts.

The unchanged qualification gates require twelve legal, executable, calibrated
formulas and at least one same formula with both at least 0.5% public projected
cycle reduction and at least ten timed replacements. The pool is fixed before
any labels. Failure at any stage is preserved; no input, memory partition, pool
size or numerical gate may be relaxed.

## Host evidence

`tests/test_strstr_workload.py` compiles the byte-identical upstream C file with
`-fno-builtin`, checks the original eight-call verifier, and independently
validates the seven fixed match offsets. This prevents the host compiler from
substituting its own `strstr` for the implementation. Host success does not
establish PicoRV32 fit, legal candidate count, opportunity, integrated speedup,
area, timing, or selection transfer.

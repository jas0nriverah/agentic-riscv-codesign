# MiBench source scout — October 27, 2026

The initial screen was a read-only source and contract review of the official
[Embecosm MiBench repository](https://github.com/embecosm/mibench/tree/092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57)
at commit `092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57` and the original
[University of Michigan MiBench page](https://vhosts.eecs.umich.edu/mibench/).
The initial screen compiled no programs and exposed no target pools. The later
office `stringsearch` host preflight and baseline-only target qualification are
recorded below. Its target run was rejected before a legal candidate pool or
candidate measurement existed.

- **Automotive `qsort`:** `qsort_small.c` allocates `MAXARRAY=60000` records of
  128 bytes in its automatic array, requiring about 7.32 MiB of stack before
  sorting. The provided small input is 53,437 bytes. It cannot use the current
  target partition without changing the workload or memory gate.
- **Automotive `basicmath`:** its bundled `usqrt` implementation is related to
  already-consumed integer-square-root work, and the benchmark also depends on
  double-precision math and extensive formatted output. It is not a clean
  independent integer-family test under this contract.
- **Automotive `susan`:** the bundled notice restricts use to research, forbids
  sale, and requires retaining Crown Copyright and patent notices. Exclude it
  from the distributable candidate set.
- **Network `patricia`:** the provided small input is 251,969 bytes. The test
  program has no expected-output comparison or meaningful success status
  (the script only captures output; the program exits with status 1). Its
  mutation/search path therefore lacks an upstream correctness oracle and
  exceeds the fixed data budget without a change to input scope.
- **Automotive `bitcount`:** its `bitcnt_1.c` through `bitcnt_4.c` implement the
  same Snippets.org population-count algorithms already adapted into the
  measured TACLeBench `bitcount` workload. The TACLeBench source headers state
  that those algorithms have no major functional changes; the file diffs show
  the same loop, SWAR, nibble-table, and byte-table implementations with
  benchmark-specific names, table initialization, and annotations. The
  MiBench harness calls seven methods over seeded values; TACLeBench calls
  those same methods in its checked benchmark. This is useful as a harness or
  adapter compatibility test, but it is not an independent workload for a
  confirmatory selection result. This was a pinned-source comparison only; no
  build, trace, extraction, or target run was performed.

This screen rejects these five paths only; it is not a survey of every MiBench
program. Do not count it as target compatibility, candidate extraction,
measured performance, or a workload rejection after execution.

## October 27 host preflight — office `stringsearch`

The pinned small Pratt-Boyer-Moore program at the same MiBench commit is a
candidate for the next workload qualification. Its source has 57 fixed
pattern/text pairs. The upstream four-file host build was run at `-O3`; an
independent Python `str.find` oracle matched all output hit/miss states and
suffix offsets (29 hits, 28 misses). The offset list hash is
`dde521d64680496b747ec7a8dbbd61fa37c0b77c8c19175e6edeca9b2a5c299d`. The
committed source pin and ABI adapter pass host tests, including exact offset
verification after the workload call.

The directory notice says to assume GPL while the source says its author put it
in the public domain. Both notices are preserved; the project treats the
source conservatively as GPL without claiming a version. The unchanged
12-candidate, 0.5%/10-occurrence and memory gates were retained when the
source-bound adapter and protocol were committed and pushed.

## October 27 target qualification — rejected at discovery

The target completed its fixed-input correctness check (result 57) and
discovery profile (**393,191 cycles / 67,989 instructions**). Program and BSS
ended at byte **5,556 / 6,400**, and observed stack use was **592 / 1,664
bytes**. These profile figures are not a routed baseline.

Automatic extraction found **10 raw, executable, calibrated formulas**, short
of the unchanged 12-candidate requirement. Only **two** passed the relocation
guard; the other eight include symbolic `%hi`/`%lo` address relocations. The
run stopped at discovery with `Too few calibrated executable candidates`,
before opportunity scoring or routed baseline measurement. Candidate dispatch
remained disabled: **zero candidate attempts, zero speedup labels, zero area
or Fmax results, and no model or policy comparison**. Preserve the raw run and
offline reconstruction in the [qualification record](../results/2026-10-27-mibench-stringsearch-qualification/README.md).

This is an engineering rejection that documents the report's automatic
candidate-discovery objective, not a completed performance-selection
experiment. `strstr` shares the broad text domain, though its GNU libc
implementation is structurally different. Since no pool was frozen and exact
candidate families were not audited against historical pools, stringsearch
cannot count as independent confirmatory evidence. Do not rerun this context,
relax its gates, or describe its instrumented profile as a measured speedup.

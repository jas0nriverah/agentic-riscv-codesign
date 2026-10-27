# MiBench source scout — October 27, 2026

This was a read-only source and contract screen of the official
[Embecosm MiBench repository](https://github.com/embecosm/mibench/tree/092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57)
at commit `092483c3f8c1e7efe7bbb54e010cc7ee31ccdc57` and the original
[University of Michigan MiBench page](https://vhosts.eecs.umich.edu/mibench/).
No benchmark was compiled or run, no target candidate pool was exposed, and no
measurement or label was produced. The four screened workloads are not
qualified for the current 8 KiB PicoRV32 RAM / 4 KiB stack / 6,400-byte
program-and-data contract.

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

This screen rejects these four paths only; it is not a survey of every MiBench
program. Do not count it as target compatibility, candidate extraction,
measured performance, or a workload rejection after execution. Continue the
search for a freely distributable, well-checked, memory-fitting integer
application with enough automatically discovered legal candidates.

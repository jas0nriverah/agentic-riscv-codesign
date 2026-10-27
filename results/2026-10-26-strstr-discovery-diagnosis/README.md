# BEEBS `strstr` discovery rejection

The original pinned BEEBS source, fixed input, wrapper, and target count
verifier passed the baseline-only discovery run. The instrumented discovery
profile used **3,658 cycles / 644 instructions**, returned the expected count
of eight, used at most 64 bytes of stack, and reported no stack violations or
custom static sites. Its program-plus-BSS endpoint was 560 bytes. These are
discovery-profile values, not a separately routed baseline measurement.

The frozen extractor found **zero** connected formulas with operation caps
from two through six. Raw, executable, relocation-safe, and calibrated formula
counts are all zero. The unchanged 12-candidate pool and public opportunity
gates were therefore not reached. Candidate dispatch was disabled throughout;
there are no candidate cycle, speedup, area, timing, or correctness labels.

Reproduce the read-only archived-profile reconstruction from the repository
root with:

```sh
../work/audit-venv/bin/python scripts/analyze_strstr_discovery_rejection.py
```

The sealed [diagnosis](diagnosis.json) binds the qualification and raw archive.
The original archive omitted some plan-bound source snapshots; the append-only
`qualification-source-closure-amendment/` records each recovery method and
includes workspace backfills only when their SHA-256 exactly matches the
archived plan binding. The original qualification files and archive remain
unchanged. The result manifest authenticates the diagnosis, README, and
amendment files.

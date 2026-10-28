# PULPino Sudoku adapter contract — 2026-10-28

**Status:** Upstream source and fixed input are pinned; deterministic adapter and
host correctness check pass. The cross-compiled image links and fits the explicit
program partition. Full target discovery, continuous stack observation, and a
routed baseline are still pending. Candidate dispatch remains disabled.

## Source and workload

The source is PULPino's sequential-test Sudoku solver at commit
[`6631c49`](https://github.com/pulp-platform/pulpino/commit/6631c49ba38a9258da44d6b120d902f7b81f9233).
The exact Solderpad license, C source, and header are retained under
[`benchmarks/pulpino-sudoku/`](../benchmarks/pulpino-sudoku/); their byte, SHA-256,
and Git blob identities are in [`SOURCE_PIN.json`](../benchmarks/pulpino-sudoku/SOURCE_PIN.json).

The fixed 9×9 puzzle and recursive `safe`, `solve`, and `sudokusolver` code are
preserved. The adapter replaces only PULPino's suite registration, callback-based
timer API, and formatted output with the existing ISAForge firmware ABI. It
constructs the same puzzle, resets the solution buffer, and calls the solver
twice inside `benchmark()`. `verify_benchmark()` requires the completion flag and
all 81 cells to match the pinned upstream oracle. This is one fixed puzzle, not a
general Sudoku solver correctness claim.

The deterministic source transform is
[`build_pulpino_sudoku_adapter.py`](../scripts/build_pulpino_sudoku_adapter.py).
It copies the upstream solver tail byte-for-byte and extracts the fixed puzzle
initialization from the pinned `check()` routine. `--check` authenticates the
result without writing.

## Target compatibility and measurement

The target uses the existing PicoRV32 core, PCPI interface, RV32I/Zicsr, ILP32,
`-Os`, synchronous 8 KiB RAM, three route seeds, and 12 MHz timing target. A
source-only cross-link preflight produced `_program_end = 2288` bytes. The
source has at most 82 solver activations; GCC reports 48 bytes for the recursive
solver frame. The qualification reserves program limit 2304, stack floor 2432,
5760 stack bytes, and a 128-byte minimum guard. These static figures only size
the preflight. Runtime stack fit must still be measured on the unchanged fixed
input with the continuous stack monitor before interpreting any target profile.

The measured region includes puzzle initialization, both 81-cell resets, and both
solver calls. It excludes harness setup/warmup and the post-run oracle scan. Every
candidate dispatch is disabled until baseline discovery, correctness, observed
stack safety, the 12-candidate executable-pool requirement, and the unchanged
joint opportunity gate pass. The gate remains at least 0.5% estimated cycle
reduction and ten timed replacements for the same candidate. No threshold or
pool-size reduction is allowed to rescue a failure.

## Commands and evidence

```sh
python3 scripts/build_pulpino_sudoku_adapter.py --check
python3 -m pytest -q tests/test_pulpino_sudoku_workload.py
python3 scripts/qualify_pulpino_sudoku.py
```

The qualification is source-bound, baseline-only, and preserves each phase and
raw archive. A discovery or integration failure is not automatically a workload
rejection. No independent-family claim follows from a distinct benchmark name;
operation-tree overlap against the historical corpus is reported before any
learning or selection claim.

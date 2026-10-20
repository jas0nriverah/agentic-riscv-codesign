# Research-contract and automatic-workload validation

October 19, 2026, Python 3.12.14 with recorded project dependencies.

- `make test`: **2,506 tests and 179 subtests passed**, 166.09 s. The one warning is the intentional duplicate-ZIP-member rejection fixture. The retired RTL-search module's 32 tests are preserved outside the active suite; 11 automatic-lowering tests were added.
- `make reproduce`: all six historical model scores match on 192 candidates, with the existing 10,000-replicate bootstrap audit and figure regeneration.
- `make reproduce-speedup`: both raw processor checkpoints authenticate and replay: **14 baseline/candidate designs, 42 routing outcomes, 240 policy/seed/budget outcomes**, with no new native measurements. Aha candidates are re-extracted and re-lowered during replay.

[Machine-readable receipt](validation.json), [full tests](tests.log), [historical replay](historical-replay.log), [processor replays](processor-replay.log). Documentation/source checks are recorded in `documentation-check.json` after the final text review.

Native aha collection separately completed 119 commands and its recorded correctness/processor/hardware checks; see [the preserved experiment](../2026-10-19-automatic-aha-mont64/README.md). No physical-board test, independent universal program proof, held-out-workload result, or LLM selection experiment is implied.

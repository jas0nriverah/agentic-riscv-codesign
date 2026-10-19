# V11b outcome: startup failure preserved

The bounded attempt ran both approved Spike capture commands. Both exited with code 1 before executing the workload because the controlled PATH omitted `dtc`, Spike's device-tree compiler helper. Each retained gzip is 20 bytes and decompresses to an empty stream. Cleanup completed without remaining owned processes.

No decode, candidate extraction, feature computation, prediction, fitting or target measurement ran. The four original completed outcomes remain unchanged (318 program/formula memberships); the two missing programs remain incomplete. Neither the original endpoint nor amended V11b-E1 has an evaluable full-panel error result.

The [independent failure audit](run/input-review/independent-failure-audit.json) authenticates all six outcomes, the exact reused evidence, both empty partials, the logs and the archived metadata. Its status is **pass for preserved failure only**, not successful recovery. [Completion receipt](completion.json) · [stage outcomes](run/attempt-0000/programs.json).

The environment correction is a separate V11c attempt: explicitly pin `dtc` and its dependency inventory, include its directory in the controlled PATH, and verify Spike startup using an already completed input before releasing any new cohort capture. Original programs, binaries, ROI, extraction rules, resource budgets and frozen models remain the same. This infrastructure correction supplies no ML improvement claim.

Implementation validation before this attempt: 1,910 tests and 159 subtests passed; [full log](input-review/full-suite.log). The failed native result is retained alongside those tests because synthetic coverage did not detect the missing runtime helper.

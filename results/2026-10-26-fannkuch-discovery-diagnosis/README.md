# Fannkuch discovery-rejection diagnosis

This is a post-rejection, read-only reconstruction of the preserved Fannkuch
r2 candidate-discovery phase. It does not amend or replace the original
[qualification archive](../2026-10-26-fannkuch-qualification-r2/), change its
12-candidate requirement, run a model, or launch a native command.

The corrected qualification stopped at discovery because it required 12
calibrated executable formulas. Replaying the frozen source-bound extractor on
the saved disassembly and trace yields **2 raw / 2 executable / 2 calibrated**
formulas, with no calibration exclusions. An offline sensitivity check at
maximum operation counts 2, 3, 4, 5, and 6 yields the same two formulas. Only
the four-operation configuration is part of the frozen study contract.

Discovery compiled and executed the original N=7 program under the PicoRV32
simulation harness. The saved profile reports **5,193,765 cycles and 974,182
instructions**, returns packed value `1081212944`, and passes the upstream
checksum/max-flips self-check. The target image reports 179 RV32I/Zicsr
instructions, zero custom instruction sites, program/BSS end at 716 bytes, and
maximum observed stack use of 160 bytes with no stack violations. These are
discovery/setup observations. The separate routed baseline/resource phase was
not reached, and no candidate was executed or measured.

| Extracted formula | Timed replacements | Calibrated projected cycle reduction | Existing family evidence |
| --- | ---: | ---: | --- |
| `add(slli(in0,2),in1)` | 18,508 | 1.781752% | Exact historical formula in UD and TACLeBench bitcount; same identity family also appears in CRC32, EDN, and NDES. |
| `add(in0,slli(in1,2))` | 3,620 | 0.348495% | Exact historical formula in CRC32, EDN, and NDES; same identity family also appears in UD and TACLeBench bitcount. |

The project’s established identity convention maps both to
`add(input,slli(input,constant))`: global input renaming plus commutative add
sorting produces the same key. The ordered input functions differ unless the
inputs are swapped, so this is an explicit family/identity relation rather
than an assertion that their ordered outputs are pointwise identical. Neither
formula supplies a fresh candidate family. The first projection exceeds the
0.5% / 10-replacement numeric opportunity thresholds; the second misses the
0.5% projection threshold. Those are calibrated public projections, not
candidate speedup labels, and passing one numeric threshold cannot clear the
12-formula pool gate.

Reproduce the analysis with:

```sh
../work/audit-venv/bin/python scripts/analyze_fannkuch_discovery_rejection.py
```

The sealed output path is already occupied by the first run. To reproduce into
a new artifact, add `--output` with a fresh path under `results/`.

The command authenticates the rejected qualification and source snapshots,
reconstructs candidate counts from saved artifacts, checks the original
self-test result, and seals a machine-readable [diagnosis](diagnosis.json). It
reads only formula and candidate-identity metadata from the historical corpus;
it does not inspect historical outcome values. The diagnosis records hashes of
the qualification receipt, archived plan, profile, history corpus, and bound
extractor sources. The original rejected run remains immutable.

**Decision:** preserve Fannkuch as rejected and move to another workload. Do
not rerun this pool, duplicate aliases, change the compiler, or relax the
12-candidate and opportunity gates to force a selection experiment.

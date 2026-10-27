# MiBench stringsearch qualification — rejected at discovery

The pinned office `stringsearch` workload passed host preflight, then failed
the unchanged target discovery gate. Preserve this as a negative result; do
not retry the context, reduce its 12-candidate requirement, or weaken the
opportunity, relocation, memory, correctness, or timing checks.

## Target result

The baseline-only command was run after the source-bound workload adapter and
qualification protocol had been committed and pushed:

```sh
../work/audit-venv/bin/python scripts/qualify_mibench_stringsearch.py
```

The program itself completed correctly: the target profile reported result
57, **393,191 cycles**, **67,989 instructions**, and no target correctness
failure. The linked program and BSS ended at byte **5,556 of the 6,400-byte
limit**; measured stack use was **592 of 1,664 reserved bytes**. These are
instrumented discovery-profile values, not routed-baseline measurements.

Automatic extraction found **10 raw, executable, calibrated formulas**, below
the frozen pool requirement of 12. The relocation guard retained only two:

| Formula | Projected instruction savings | Dynamic occurrences | Relocation-safe |
| --- | ---: | ---: | --- |
| `add(in0,slli(in1,2))` | 581 | 581 | yes |
| `add(addi(lui(4096),1004),in0)` | 114 | 57 | no |
| `add(addi(lui(4096),1232),in0)` | 114 | 57 | no |
| `add(addi(in0,1004),in1)` | 57 | 57 | no |
| `add(addi(in0,1232),in1)` | 57 | 57 | no |
| `addi(lui(4096),-40)` | 57 | 57 | no |
| `addi(lui(4096),1004)` | 57 | 57 | no |
| `addi(lui(4096),1232)` | 57 | 57 | no |
| `sub(addi(0,1),in0)` | 57 | 57 | yes |
| `addi(lui(4096),-508)` | 1 | 1 | no |

The eight rejected formulas contain symbolic `%hi`/`%lo` relocations; replacing
those address-producing instructions with a fused literal formula can change
program semantics. Discovery stopped with `Too few calibrated executable
candidates`. The baseline opportunity gate and routed baseline were not run.
There were **zero candidate attempts, zero candidate labels, zero resource or
Fmax measurements, and no policy comparison or model update**. The
discovery subprocess took 10.374530 monotonic seconds; the recorded clock
observer flags endpoint disagreement, so this is process timing rather than an
uninterrupted wall-clock claim.

The source's result is useful for the report's automatic candidate-discovery
goal, but it does not complete the report's central selection comparison. It
also cannot count as independent workload confirmation: it is a single
text-search workload, and its exact candidate families were never frozen into
a qualifying pool for historical-family comparison.

## Reproduction and evidence

`qualification.json`, its command receipts, `raw.tar.gz`, and the archive
manifest preserve the baseline-only target run. `discovery-diagnosis.json`
is a post-hoc offline reconstruction; its result is not a new native run.

```sh
mkdir -p generated/mibench-stringsearch-raw
tar -xzf results/2026-10-27-mibench-stringsearch-qualification/raw.tar.gz \
  -C generated/mibench-stringsearch-raw
../work/audit-venv/bin/python scripts/diagnose_mibench_stringsearch_discovery.py \
  --root generated/mibench-stringsearch-raw \
  --output results/2026-10-27-mibench-stringsearch-qualification/replay-check.json
```

The focused host adapter suite passed as part of the 83-test focused
qualification check. The separately recorded host oracle checked all **57 of
57** pattern/text cases (29 hits, 28 misses, including suffix offsets). See the
[source scout](../../docs/mibench-scout-2026-10-27.md),
[adapter contract](../../docs/mibench-stringsearch-adapter-contract-2026-10-27.md),
and machine-readable [discovery diagnosis](discovery-diagnosis.json).

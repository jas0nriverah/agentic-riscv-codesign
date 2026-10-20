# Preserved workload eligibility failures

Seven build contexts: EDN `-O2`/`-Os`, huffbench, AES, wikisort, and SLRE `-O2`/`-Os`. All stop before candidate labels. `manifest.json` records compiler flags, contexts, native costs, failure counts, and per-file archive hashes. Archives include inputs, source snapshots and raw compile logs. EDN `-Os` also includes a charged linker-map diagnostic: program/data/BSS end at 6,356 bytes, beyond the 4,096-byte guard.

Eight recorded native compiler invocations cost 2.730 seconds in total. The additional two SLRE runtime/compiler attempts live in [the runtime probe](../2026-10-20-slre-runtime-probe/README.md) and [final size fallback](../2026-10-20-slre-small-probe/README.md). No failed candidate measurement was converted to a performance label.

```sh
python scripts/reproduce_selection_research.py
```

[Detailed blockers and next experiment](../../docs/selection-pilot-results.md)

# SLRE final compiler-size fallback — failed

A fresh context adds the recorded `#pragma GCC optimize ("Oz")` directive to the benchmark translation unit; the generic harness/runtime retain `-Os`. The upstream benchmark algorithm is unchanged. GCC accepts the directive, but the linker still rejects the 4 KiB program/data limit. No memory guard was weakened and no candidate outcome was obtained.

The archive contains the source directive, upstream-source SHA-256, plan, complete inputs and failed compile log. An earlier preparation-only scratch directory had no native commands and was replaced by this run before compilation to correct metadata hashing; it produced no research observations.

```sh
python scripts/prepare_slre_small.py \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/slre-small-new
python -m isaforge.compact_workload discover --root generated/slre-small-new
```

Discovery is expected to fail under this preserved protocol. Authenticate without native jobs: `python scripts/reproduce_selection_research.py`.

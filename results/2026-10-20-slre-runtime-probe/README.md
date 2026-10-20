# SLRE minimal-runtime fit probe — failed

The recorded `-Os` build resolves `_ctype_`, `strlen`, and `strchr` using the tested freestanding C-locale runtime. Program/data end at **4,164 bytes**, 68 beyond the unchanged 4 KiB guard. Baseline compilation fails; no processor execution or candidate speedup labels are claimed.

Two native compiler commands, including a linker-map diagnostic, consumed 1.134409 seconds. The archive preserves input/source hashes, actual commands, logs, and the link map. The native C-library component test passes separately; it is not a successful workload measurement.

Preparation command (expected discovery failure under this protocol):

```sh
python scripts/prepare_slre_runtime.py \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/slre-runtime-new
python -m isaforge.compact_workload discover --root generated/slre-runtime-new
```

Authenticate without native jobs: `python scripts/reproduce_selection_research.py`.

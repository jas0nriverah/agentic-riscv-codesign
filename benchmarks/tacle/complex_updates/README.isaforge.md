# Pinned TACLeBench complex_updates

Original `complex_updates.c` and `ChangeLog.txt` are byte-identical to commit
`c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`, `bench/kernel/complex_updates`.
The source's original DSP-Stone notice and permission remain intact.
`../COMPLEX_UPDATES_SOURCES.json` records SHA256s, byte counts and Git blob IDs.

`isaforge_adapter.c` is the separate external ABI wrapper. It keeps original
N=16, four arrays, float operations and the exact 144.0f checksum. The original
checksum covers the first16 of32 D elements only. Compiler/helper/memory fit,
legal executable calibrated pool and opportunity qualification remain untested.
Only zero-candidate baseline qualification is implemented; dispatch is disabled.
See `docs/complex-updates-qualification.md` at the repository root.

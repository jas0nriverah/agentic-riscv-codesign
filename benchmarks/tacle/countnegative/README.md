# Pinned TACLeBench countnegative

The upstream `countnegative.c` and `ChangeLog.txt` are byte-identical to TACLeBench commit `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`. [`COUNTNEGATIVE_SOURCES.json`](../COUNTNEGATIVE_SOURCES.json) records the source archive hash, file hashes, and Git blob IDs. The source header permits use, modification, and redistribution. The external ABI adapter does not modify the upstream file.

The workload initializes its original deterministic 20×20 integer matrix, scans it, and checks the upstream checksum `0x1778de`. Initialization runs outside the timed benchmark call; the original scan and return check run inside it. The adapter's verifier rechecks the upstream return value.

This is a source pin and host/target compatibility candidate only. Workload independence, 8 KiB firmware fit, the 12-formula pool, the 0.5% / ten-replacement opportunity gate, and routed baseline acceptance remain unproven until the frozen baseline-only qualification completes. No candidate measurements are authorized by this source package.

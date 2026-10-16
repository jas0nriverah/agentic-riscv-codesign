# V13b: explicit prelabel compiler-environment recovery

The original V13 attempt is retained as a failed measurement stage. Verilator's generated C++ compilation failed because the controlled compiler environment could not locate the standard header `cstdint`. Its authoritative completion records zero physical labels, zero RTL comparisons and zero estimator fits. Original sources, approval, archive and completion remain unchanged.

V13b is a separately named engineering amendment. It copies all six prepared input artifacts byte for byte: the same 48 candidates, verification seed 2026101529, original RTL and physical synthesis target. No candidate substitutions or outcome-conditioned filtering are permitted. The original attempt is not silently retried.

A noncohort C++ probe reproduced the missing-header failure. Adding explicit SDKROOT made that probe compile and execute successfully. A separate probe through the actual V13b owned worker also compiled and executed successfully. The recovery pins the resolved SDK path, SDK settings and libc++ header inventory, and propagates SDKROOT to child processes. This is a partially pinned local toolchain, not a hermetic operating-system image.

Recovery measurement requires a new tool/plan seal and recorded parent release, then one bounded attempt. Successful measurements must pass independent RTL-vector and mapped-netlist audits before feature extraction or fitting. The planned model experiment compares the existing training cohort with an augmented cohort on shared grouped folds; old-cohort performance is primary and the 48 added examples are secondary. Hardware timing, processor performance and power claims cannot be inferred from an area-prediction improvement.

The original failed evidence is in [V13](../results/2026-10-15-v13-coverage-development/README.md). The new [recovery record](../results/2026-10-15-v13b-coverage-recovery/README.md) tracks execution status.

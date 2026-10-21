# Pinned BEEBS jfdctint

Source: https://github.com/mageec/beebs/tree/049ded9f3aeb5591f553879d3a0376b8614e9422/src/jfdctint

The upstream benchmark and complete 64-coefficient verifier are unmodified. This is BEEBS, not Embench. GPL version 3 or later; copyright notices remain in the source and the upstream COPYING file is retained.

- libjfdctint.c SHA256: 2fb8b63b4e0da2012da6d63617e99b4f7ef263899ad01f0426d1277466a79c5e
- COPYING SHA256: 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903

The declared no-op warm_caches ABI adapter lives in isaforge/beebs_workload.py, outside the benchmark. Compiler: RV32I ILP32 -Os; original fixed seed 1 and full integer transform.

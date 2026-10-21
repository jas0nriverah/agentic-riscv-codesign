# Pinned BEEBS jfdctint

Source: https://github.com/mageec/beebs/tree/049ded9f3aeb5591f553879d3a0376b8614e9422/src/jfdctint

The upstream benchmark and complete 64-coefficient verifier are unmodified. This is BEEBS, not Embench. GPL version 3 or later; copyright notices remain in the source and the upstream COPYING file is retained.

- libjfdctint.c SHA256: 2fb8b63b4e0da2012da6d63617e99b4f7ef263899ad01f0426d1277466a79c5e
- COPYING SHA256: 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903

The declared no-op warm_caches ABI adapter lives in isaforge/beebs_workload.py, outside the benchmark. Compiler: RV32I ILP32 -Os; original fixed seed 1 and full integer transform.

## Blind source campaign

The next campaign uses the same pinned commit, license, RV32I/ILP32 compiler and original full benchmark inputs. Sources below are byte-identical upstream files, with their copyright notices retained. The new adapter is `isaforge/blind_workload.py`; the [experiment contract](../../docs/blind-source-campaign.md) records the common memory partition and qualification order.

| Source | SHA256 | Original verifier and qualification |
| --- | --- | --- |
| `aha-compress/compress_test.c` | `1e9e7929e0466968e1bc069f406597aa7bb1c7e1eeaeb7f4bc593be4510d4af8` | Four compression implementations across 18 original data/mask/golden triples; qualifies for twelve candidates. |
| `ndes/libndes.c` | `78d92b71cc0edd3a26ef1a49e2904ac7d6b6dc5ab33d172ab17cb68fdb92d071` | Both original DES output halves; qualifies for twelve candidates. |
| `nettle-arcfour/arcfour.c` | `1efb711913921a574cb6092a4e2f996f8514cd1d2fade3c19c9aef6d5787cff7` | Original 16-byte roundtrip plus external independent ciphertext check; rejected for too few legal formulas in the declared twelve-candidate pool. |
| `nettle-md5/md5.c` | `7b8b50fc6ffe75a6e6fa9067a79f502d8cf4a3e5701bfc0ed94de1347b830b2f` | All four original compression output words; qualifies for twelve candidates. This is the upstream one-block compression benchmark, not a complete padded-message hashing application. |
| `levenshtein/liblevenshtein.c` | `fd1ee0e23bab6db0182b32618bc3622a3ce0399714b662076d053d98fb7193f6` | Original five strings / 25 ordered distances and scalar check; vendored fallback, not executed because three earlier sources qualified. |

Every source is under `https://github.com/mageec/beebs/tree/049ded9f3aeb5591f553879d3a0376b8614e9422/src/`. Qualification measures no custom candidate. Full histories and source-family exclusions remain necessary: separate benchmark names do not prove instruction-pattern independence.

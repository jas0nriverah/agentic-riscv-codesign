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

## Original-verifier opportunity qualification, October 22, 2026

The fixed proposed order is **cnt → bubblesort → prime → insertsort → tarai → recursion → janne_complex → cover**. These are unchanged, single-file sources from the same pinned BEEBS commit above. Bubblesort was already vendored and remains byte-identical; the other seven files are newly vendored. Each file was compared byte-for-byte with the primary commit archive and its Git blob SHA1 was independently recomputed against the pinned upstream tree. The GPL-3.0-or-later notices and existing upstream `COPYING` are retained. Every file includes only the existing `support.h` benchmark interface; no new helper, input, arithmetic or verifier modification is introduced by this vendoring step.

| File | SHA256 | Original input and verifier |
| --- | --- | --- |
| `cnt/cnt.c` | `0c6b201ccb8f25a7ee7741206422c237580e053d9e7cc71a989753413887fe04` | Original 10×10 integer matrix, initialized with seed 0 and `(seed*133+81)%8095`; timed sum/count routine returns 396675. The verifier checks that scalar sum; it does not separately check all four exported counts/totals. Initialization is outside the timed region. |
| `bubblesort/libbubblesort.c` | `d4a9c32096ebe287ac83d50c69d4ec7cab1c253c6a7e383415b7db521e1b6f9a` | Original 101-int storage and 100 initialized elements `0,-1,…,-99`; the original verifier checks all 100 sorted elements against `-99,…,0`. |
| `prime/libprime.c` | `2515479b9d94630e01aa294a5e1870a0fcb68020b34da93f1240616babf49735` | Original 21649/513239 operands, swapped before both primality tests. The verifier checks the exported volatile failure flag equals 0. RV32I arithmetic uses the existing libgcc support where required. |
| `insertsort/libinsertsort.c` | `d25e603246fd509ae4dc972770e98fed8d20d386979870596af8cfc9b1ae0d0e` | Original 11 unsigned integers `{0,11,10,9,8,7,6,5,4,3,2}`; verifier checks the complete result `{0,2,3,4,5,6,7,8,9,10,11}`. |
| `tarai/libtarai.c` | `ff5dcf69f4adca26a61c14f1f725c2523d9c12deb45b77627126b169dab8d7fc` | Original Takeuchi inputs 9/6/3; verifier checks scalar result 9. Recursion/stack fit remains to be qualified. |
| `recursion/librecursion.c` | `bc0572c7bab5ec43c1afb645f836d8fd4f86ffb83763800f10f2cd8ea8d9d98a` | Original recursive Fibonacci input 10; verifier checks scalar result 89. Unused mutual-recursion functions are preserved. |
| `janne_complex/libjanne_complex.c` | `dfb9adb3959064de1541f4a469ea0389558c85d1a350cc371207646554c1483c` | Original nested-loop inputs 1/1; verifier checks return 1. The computation returns a constant and exports no intermediate state, so this original verifier is weak; optimization may remove the loop work. |
| `cover/libcover.c` | `80ac586a7aec55ae9ce1ad3266b94f530ce06c09108531544f2183da21e2f1d9` | Original switch loops 10/50/120; verifier checks aggregate return 180. Constant folding and an insufficient executable pool are substantial qualification risks. |

The source inventory itself does not establish qualification. The fixed protocol retains the original 8 KiB/6400/6528 partition and requires 12 legal calibrated executable formulas, with the same candidate providing both at least 0.5% public analytic whole-program cycle reduction and 10 timed replacements. The declared stop is exactly three independent source families; bubblesort/insertsort share the sorting family, so a later sorting variant is skipped only after one is accepted, with that reason preserved. No rejected source is retried at weaker gates. Candidate measurements remain forbidden before a compatible protocol/model/prediction freeze.

**Completed qualification:** zero sources qualify. Seven original programs compile/profile but fail discovery with fewer than twelve legal executable formulas; Janne is statically rejected for its weak constant-return verifier. There are no new custom-candidate measurements or routed designs. [Raw failures](../../results/2026-10-22-useful-source-qualification/qualification.json), [archive-only support diagnosis](../../results/2026-10-22-workload-support/support.json) and [working commands/limitations](../../docs/selection-improvements-2026-10-22.md) are preserved. Prime/insertsort each have one eligible formula; the other profiled sources have zero. Linked-helper coverage is a demonstrated limitation, not permission for unsafe rewriting or weaker gates.

Primary archive: `https://codeload.github.com/mageec/beebs/tar.gz/049ded9f3aeb5591f553879d3a0376b8614e9422`, SHA256 `0f608bdf00c30b6aaf7c5b81d887fa244281b581f0a69d326c9a5a5288286f31`. Source URLs use the pinned `src/<file>` paths above. No compiler, simulator or synthesis job was run to prepare these files.

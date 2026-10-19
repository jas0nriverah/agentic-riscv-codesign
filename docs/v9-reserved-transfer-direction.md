# Reserved application transfer after V9 coverage development

Planning only, 2026-10-15. Reserve the six programs below now, before compiling them, extracting their candidates, viewing predictions or obtaining area labels. This inspection read source, manifests and input lineage only; it ran no workload, native feature extraction, target mapping, fitting or label evaluation. V8 and both V9 development studies are consumed evidence. A fresh transfer result must use new application inputs and frozen existing models.

## Fixed source reservation

Use TACLeBench commit `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`, the same pin as V5 external and V8, from `https://github.com/tacle/tacle-bench`. The local reference checkout matches that commit and is clean. Its 57 programs include these six reserved programs, grouped conservatively into **five proposed algorithm families**, not six independent families or five new broad domains:

| Primary family | Exact upstream program directory | Compile every listed C translation unit | Source ancestry and limits |
|---|---|---|---|
| Arbitrary-precision arithmetic and bit strings | `bench/sequential/ammunition` | `ammunition.c`, `ammunition_libc.c`, `arithm.c`, `bits.c` | Vladimir Makarov / DINO AMMUNITION packages; distinct implementation from consumed fixed-width Montgomery/GCD and bitcount. Retain GPL/LGPL notices. This is a package test, not a complete compiler. |
| Audio beamforming | `bench/sequential/audiobeam` | `audiobeam.c`, `audiobeaminput.c`, `audiobeamlibm.c`, `audiobeamlibmalloc.c` | Eugene Weinstein / MIT StreamIt/Oxygen; delay-and-sum microphone processing. DSP and software floating point are familiar domains. Retain the actual MIT and Sun library notices, including incomplete placeholder attribution in the supplied license file. |
| Numeric template matching | `bench/kernel/pm` | `pm.c`, `pm_input.c`, `pm_libm.c`, `pm_stdlib.c` | Hector Chan / MIT Lincoln Laboratory HPEC Pattern Match; numeric profile matching, not consumed SLRE regular expressions or anagram multiset search. BSD notices retained. |
| FM reception | `bench/sequential/fmref` | `fmref.c`, `wcclibm.c` | David Maze's FM radio reference; demodulation/equalization pipeline. Shares the MIT/StreamIt ecosystem with audiobeam and FIR operations with consumed EDN; these are distinct declared algorithms, not wholly unrelated source collections. Shared library/formula overlap must be reported. |
| Elementary integer recurrences, **one family** | `bench/kernel/fac` and `bench/kernel/recursion` | `fac.c`; `recursion.c`, built as separate programs | MRTC factorial sum and recursive Fibonacci. Neither appears in the consumed program inventory. Two small kernels, not two independent application families; one family weight shared equally between them. |

Every program's original fixed input and complete directory contents, including headers, input arrays, change logs and notices, must be pinned in a future preparation manifest. No new input values, constants, loop bounds or optimized replacements are proposed. Main-source SHA256s, in table order (`fac`, then `recursion` last):

```text
ammunition  91275ca49deabae23b979ee2e8b72d6d8089d66df68992485f33b1abc26ff1ba
audiobeam   932d0a606e9acbb23dd29295825b276a39e35989fa9cce5f1cb6e6ae9767f4ad
pm          956e60a5a93e2e057df3c0a0c56e648bd10c1c08942411e7af05264ac84f5f70
fmref       5a64ade837ad3e059a851f47385e5db4b514f4e21432f464f5f721d71b55356d
fac         bec4ca75a8653b5893cf0c47d0abdd82181f7d54e80750f7d904edacec7f4d40
recursion   de88f42686816d10ded0ccc9f06c549d563284927732107d17ec12e2cc0ba1df
```

These are untouched **candidate/target application inputs in the audited repository lineage**, now reserved and source-inspected. Absence from that inventory does not prove independent authorship, no shared code, or unseen formulas. Before primary admission, check headers/macros and computation ancestry against all prior sources; retain any related-source finding explicitly. Do not replace a difficult or empty program with another after looking at candidate richness or model outputs.

## Consumed boundary and current coverage

All 19 Embench directories count as consumed, including failures/empty pools: `aha-mont64`, `crc32`, `cubic`, `edn`, `huffbench`, `matmult-int`, `minver`, `nbody`, `nettle-aes`, `nettle-sha256`, `nsichneu`, `picojpeg`, `qrduino`, `sglib-combined`, `slre`, `st`, `statemate`, `ud`, `wikisort`. The submodule pin is `0466a18e4f6b47e19598d7c6ba72916d54b68f65`. V5 external additionally consumed TACLe `dijkstra`, `adpcm_dec`, `anagram`; V8 inspected `bitcount`, `fft`, `ndes`, `h264_dec`, related `isqrt`, and failed `mpeg2`. None can supply a fresh primary family.

The V9 coverage ledger has 2,881 canonical originals (2,764 pre-V8 plus 146 V8, with 29 shared); its 48 new coverage circuits were disjoint from that union. Thus the current minimum original-formula reference is **2,929**, augmented by any subsequently inspected inputs before a future seal. Include accepted V5 and V7 bit/affine/combined identities, conservative skeleton/vector diagnostics, and every retained prior acquisition attempt; do not just subtract the 1,713 fitting rows. The 48 constants/shifts are consumed synthetic development, not new application families. V9 residual adaptation reused V8 and supplied no new source family.

Concrete exclusions matter: `petrinet` shares Friedhelm Stappert/C-LAB Petri-net ancestry, marking arrays and transition structure with consumed `nsichneu`; `statemate`, cubic/minver/st/LU, AES, Huffman/JPEG and sorting siblings are related or consumed. `binarysearch` overlaps the SGLIB retained binary-search API; execution differs, but it is not a conservative new-family primary. Keep MD5/SHA variants outside this primary as related hash controls. In this checkout the consumed directory is `nettle-sha256`, not `nettle-md5`; a different name alone cannot establish an untouched hash family. FIR/IIR/DCT derivatives are similarly unsafe substitutes because EDN already contains FIR, IIR and JPEG DCT. SUSAN/EPIC were previously considered at source-notice level and carry use restrictions; neither is a silent replacement.

A read-only mechanical screen reused the retained V8 genealogy tokenizer against 43 C files from all 19 Embench directories and all nine previously inspected TACLe programs. It found no exact alpha-renamed body match of at least 40 tokens for the six reserved programs (49/27/10/9/1/0 examined bodies respectively). This heuristic omits preprocessing and short functions—Fibonacci had no qualifying body—and cannot establish independence. Shared math-library ancestry remains a manual-review gate.

## Input and candidate contract

Reuse the V8 RV32IM/ILP32 GCC 15.2 toolchain, Spike `rv32im_zicntr` with 16 MiB, startup/runtime/markers, O2 computation plus separate O0 output control, and unchanged decoder/extractor. The V8 tool manifest binds compiler `d21f58713e7f2f9a9ef9de8762b2c2d1995cd4cdeda724d5fe4834f3af4737b2`, objdump `87a57cf5bdabdf2ca91ebca54fe568bd6c3524f2558782520547b1b8f29b925b` and Spike `e4bbfc59a6fdf3244f3c2234e6b03e74ccbd114ab704e2d47bfc4bcf08ec853e`; verify executable and dependent input bytes before authorized input preparation. Build/self-check/trace limits remain 60/60/300 seconds per program, with immutable failures and process-group cleanup.

ROI is the complete original `PROGRAM_main` computation and **all dynamically called helpers**, with original init before markers and status/output capture after. Retain soft-float/runtime helpers with attribution, as V8's all-ROI contract does. No smaller kernel-only rescue or shortened trace. Preserve source-declared status semantics in an explicit adapter. `fmref_return()` unconditionally returns zero: it requires captured output buffers and an independently specified check; exit zero alone is not correctness evidence. Other programs also need meaningful snapshots, original self-checks and O0/O2 comparison; those checks are not universal proofs.

Enumerate **every eligible canonical formula in each complete ROI**, `maxSize=4`, 2–4 contributing instructions, at most two 32-bit inputs and one output, unchanged memory/control/liveness barriers, no top-K, model ranking, manual constants or frequency cutoff. Retain all occurrences, helper attribution and overlap-safe dynamic merit. Fusion validation uses the existing 16-vector/seed2026101507 contract with zero opaque skips. Familiar and zero-area formulas remain; sharing a canonical original allows one physical measurement but preserves every program membership. Publish failed, timeout, null and zero-candidate programs as coverage outcomes. Empty-program MAE is undefined, never zero; any missing/empty proposed primary family means the full five-family endpoint is incomplete, with any observed-subset result clearly secondary.

Freeze complete program pools, genealogy/novelty, tool/runtime/source hashes, model artifacts and both predictions before new target labels. There is no per-program candidate cap. If total cost exceeds an agreed prelabel physical budget, retain the full reservation and stop for a revised prospective plan; do not silently sample it and call the result whole-pool transfer.

## Frozen comparison and release gates

Primary: frozen V9 coverage-augmented mapping217 minus frozen V6 mapping217, paired equal-family MAE; average formulas within program, programs within family, then the five family means equally. Negative favors augmentation. The V9 model is `results/2026-10-15-v9-coverage-development/fit-attempt-0000/models/mapping-coverage.joblib`, SHA256 `dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d`. Bind the exact existing V6 artifact/schema separately. Neither model may refit, adapt, select features or calibrate from this reservation. Existing original336/SOG/MasterRTL artifacts may be frozen optional controls before release; they do not alter the primary.

Report family/program counts and paired errors, pooled MAE, bias, RMSLE, zeros, p90/p95/p99, worst underprediction, and cap32/64/128 false accepts/rejects with denominators. Familiar/novel and algorithm/helper strata are secondary; never drop familiar rows to create apparent transfer. Five small, deliberately selected families support a bounded panel claim, not population-level guarantees or family conformal calibration.

Current blockers: no new build/trace/candidate feasibility is established; whole-ROI completion and pool size are unknown; software floating point may dominate audiobeam/pm/fmref or leave little eligible work; lineage/license snapshots and independent output checks are unfinished; no input/prediction seal or measurement release exists. At least four complete, defensibly distinct algorithm families must survive input-only review to call it a multi-family fresh transfer panel. Keep all six attempted programs visible even if that gate fails. No source swap follows predictions or area outcomes.

Only a subsequently authorized, sealed original-RTL collection under the same frozen Yosys target can supply fresh labels. A successful result would test generalization after consumed-development augmentation. Equal-budget random versus coverage-selected augmentation needs a separately declared development design and new fits; these reserved transfer labels cannot select that control, repair the model and remain fresh confirmation.

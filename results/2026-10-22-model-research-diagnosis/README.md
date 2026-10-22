# Current model and data diagnosis

Consumed-data arithmetic and existing cached predictions only: zero fits, new model predictions, native jobs or variant trajectories. The independent units are11 source workloads, with12 contexts; dependent seeds and candidate pairs are not new sources.

Discovery inputs are authenticated from committed raw archives and matched to each frozen context’s expected hash. If original generated files exist, their bytes must agree exactly; absent generated roots require no native rebuild or metadata substitution. The original discovery JSON bytes are preserved under inputs/discovery/.

87 verified labels, three failures (two known validation failures, one unknown infrastructure outcome),90 charged attempts. All87 cycle deltas match calibrated latency. Area feasibility counts at+32/+64/+128 are12/44/87; all87 measured designs fit the device and clear12MHz. Routed minima range59.133110–73.410660MHz. The classifier therefore has no observed timing/device negative examples; cap replicas do not turn87 physical measurements into261 independent labels.

## Pool coverage

| Source/context | Selected | Eligible calibrated | Coverage |
| --- | --- | --- | --- |
| embench-aha-mont64:1bd107eac10ff77bff15d8903da582a8f03b4db1a1294df085c3fc02642df997 | 6 |  |  |
| embench-crc32:63c7f40f7e906b046f5a1911d5ed91824bb1aa15673f8fa753a818ccc0d5f511 | 6 |  |  |
| embench-slre:a19fb0306623215e50eed26a0ea8ff85b9238ebccb6e453724f5570ef1decb24 | 6 | 16 | 37.500% |
| embench-edn:3f53183b901bbd833b93bb6b1d88c74eef9fc851e99847a4c58e9ac1d1b54567 | 6 | 16 | 37.500% |
| embench-ud:dff930b3f62af548560facf4403cb3bbd411bda014b383a8383a127dd21b4d29 | 6 | 11 | 54.545% |
| embench-nettle-sha256:297fc315d85f9c805cc0e0be585bdb426d126723763d57f1ac1925049962dce3 | 6 | 56 | 10.714% |
| embench-nettle-sha256:c2fd4e9288ddc21105edee92508d71353a62d98723b609bfaa6434205a2e22b6 | 6 | 50 | 12.000% |
| beebs-jfdctint:9a2098d3c3dbeefdada16733113567bfd5c04ad2073bd423e2ded9db663c717f | 6 | 29 | 20.690% |
| beebs-aha-compress:56fc6fb2ebba72e8396e83826d3d72969e531f7a3084d28d8ff2f674f4522460 | 12 | 26 | 46.154% |
| beebs-ndes:a20aa9f25bb8aa7471aacd09b8cd5d200a97b72d5a9536b04bfdd8ae8f2decf6 | 12 | 43 | 27.907% |
| beebs-nettle-md5:5c051a1eb29ba10fc813470abccc26e425e13e9e63c8321f5b747342085a6c07 | 12 | 297 | 4.040% |
| beebs-expint:ba30de03eae52b15c37a9c0709baeb1712baa640dd1a1b8ef8f16dd621803eaa | 6 | 8 | 75.000% |

Early AHA/CRC use top instruction-saving pools; subsequent pools span evenly spaced instruction-saving ranks rather than a simple top-K cutoff. Those are public merit-stratified convenience subsets, not random formulas. Outside-pool hardware labels are absent; no full-source hardware optimum or unbiased population error is identifiable. SHA contexts exclude earlier literal formulas and remain one source. Headroom is retained separately for every context/cap in headroom.csv.

## Ranking and representation

The12 context groups provide319 unordered candidate pairs:294 unequal-performance pairs and25 ties. At+64,78 unequal pairs favor a faster but infeasible candidate over a slower feasible candidate; at+32 there are38. The pure speedup ranker is trained to favor these faster candidates. Its raw scores are not constraint-aware or magnitude-calibrated. Pair counts share rows and do not provide294 independent observations;198 of319 pairs come from the three twelve-candidate sources.

The31 hardware features yield79 unique vectors among87 rows, five duplicate groups covering13 rows. Only one same-context duplicate group contains different formulas: NDES add(in0,slli(in1,2)) costs70LUT4 and saves3280cycles; slli(add(in0,in1),2) costs40 and saves720. At+64 their feasibility labels differ but the GP/classifier representation is identical. Full35 profile/structural features are unique across87 rows; this specific exact alias does not apply to the raw/ranking input.

Existing formula-only v3 bit-cone descriptors separate the NDES pair and expose Expint’s cheap Boolean-conditioned constant expression. They collapse both DCT constant formulas to the same zero-LUT proxy despite measured integrated additions33 and15. The original31 DCT features differ in max_abs_constant16384vs4096; the cached classifier nevertheless gives both formulas identical member outputs at every cap/seed in both cohorts. This is a fitted-score equivalence, not an exact original-feature collision. This is representation diagnosis, not successful prediction. The earlier45-descriptor ablation remains negative: adaptive SHA optimum moves query2→3, so no descriptor bundle is promoted.

## First-query acquisition and data transfer

Cached acquisition arithmetic exactly reproduces both GP policies’ first choice for all270 policy/cohort/source/cap/seed entries. Removing inverse-time only changes20 of135 distinct initial cases: all five old-AHA seeds at each cap, and all five fresh-Expint seeds at+64. The other initial choices stay the same. Old AHA flips are extremely close scores for two equal-benefit formulas, both infeasible at+32/+64; exact choices are recorded without treating tiny floating differences as robust evidence. Measured first-query outcomes improve in5 cases, worsen in0 and tie in130; these dependent cases are descriptive, not an independent-source statistical test.

Fresh Expint at+64 is a substantive flip: the frozen cost score chooses add(in0,slli(in1,3)) (+71LUT4, infeasible), while the same gain×predicted-feasibility without inverse-time chooses the actual11-cycle optimum (+17LUT4). This is a first-query retrospective counterfactual only; it is not a replayed policy, a whole-trajectory improvement or a wall-time result. Full decompositions retain mean/std area, timing and logtime, positive analytic speedup gain, Gaussian probability factors, fit rate, inverse time and scores.

Expint’s initial area prediction for that infeasible query is40.002±0.214LUT4. Its nearest standardized history row is NDES slli(add(in0,in1),2), actual40LUT4, at distance2.699e-9. The only differing numeric feature is constant magnitude3vs2, divided by historical standard deviation370,562,752.59. Whole-family exclusion correctly removes add(input,shift(input,constant)) examples but retains the differently ordered graph. Missing operator order and raw-constant scaling make them effectively identical to this GP. Family exclusion should remain; the representation, not leakage protection, needs scrutiny.

Expanded-history GP regression is concentrated on AHA: its old44-row vs expanded68-row post-family cohorts are each disjoint from the target source and excluded related families, yet expanding history loses its+64 oracle in the adaptive three-query runs. Cached factor crossings and input scale summaries expose changes without identifying a unique training-row/scaler cause. More data changes input standardization, posterior area/timing/time estimates and paid-update geometry together. Do not infer that source balancing or a kernel change will fix it without a single declared development test and later untouched-source validation.

## Bounded next research questions

1. Does matching acquisition to the primary charged-count objective prevent avoidable first-query losses? A fixed no-inverse-time ablation using unchanged models is justified by Expint’s observed cost flip; compare query-count and qualified-time endpoints separately, preserve every control, and validate on untouched useful-headroom sources. No new fit was made here.

2. Can a small existing formula-only bit-demand/order representation distinguish the demonstrated hardware aliases without worsening transfers? Reuse the frozen descriptors before engineering graphs/embeddings, preserve the DCT counterexample and earlier negative ordered ablation, and avoid selecting feature variants on these consumed labels.

3. Can new measurements add useful constraint and source diversity? Current+128 labels are all feasible, timing is far from12MHz, and several sources offer negligible headroom. Predeclare independent-source pools spanning boundary area/semantic cases and materially useful benefit. Do not post-curate outcomes or claim missing timing/device classes have been learned.

All results remain consumed-data diagnostics. No policy/model promotion, calibrated confidence, independent-seed significance or total historical-cost advantage is established.

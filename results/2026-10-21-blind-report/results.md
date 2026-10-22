# Blind independent-source campaign

3 independent source workloads; 36 declared candidate attempts. Primary endpoint: three charged attempts, at most64 added LUT4, minimum routed Fmax12MHz. Original inputs and recorded-input verifiers are retained. All hardware costs cover the integrated processor/PCPI/RAM; Fmax is the minimum of three routing seeds. No frequency increase is credited.

## Whole-source primary comparison

| Policy | Cycle reduction | Cycle-reduction regret | Oracle gain fraction | Sources with positive reference | Mean ledger monotonic s |
| --- | --- | --- | --- | --- | --- |
| Frequency | 0.010103633 | 0.005918219 | 0.610897436 | 3 | 160.184790928 |
| Merit | 0.011445386 | 0.004576465 | 0.800000000 | 3 | 160.905920172 |
| Calibrated latency | 0.011445386 | 0.004576465 | 0.800000000 | 3 | 160.905920172 |
| Latency + cost heuristic | 0.007052656 | 0.008969195 | 0.477564103 | 3 | 159.551268972 |
| Random | 0.005954051 | 0.010067800 | 0.383849715 | 3 | 187.230458378 |
| Original XGBoost | 0.007662736 | 0.008359115 | 0.555306268 | 3 | 163.148377219 |
| Pairwise XGBoost | 0.011493190 | 0.004528661 | 0.634706960 | 3 | 162.355679792 |
| Normalized XGBoost | 0.014496363 | 0.001525488 | 0.933333333 | 3 | 161.074358761 |
| Hybrid GP: zero shot | 0.016021852 | 0.000000000 | 1.000000000 | 3 | 161.158578056 |
| Hybrid GP: paid adaptation | 0.016021852 | 0.000000000 | 1.000000000 | 3 | 161.158578056 |
| Feasible-benefit XGBoost | 0.006029285 | 0.009992566 | 0.333333333 | 3 | 161.369352681 |
| Factorized feasibility XGBoost | 0.007193654 | 0.008828197 | 0.497435897 | 3 | 160.980288484 |

Cycle reduction is1−1/speedup, computed within every seed before averaging. Oracle gain fraction divides achieved cycle reduction by the best verified feasible cycle reduction. A baseline-only reference has zero gain and an undefined fraction, excluded from the fraction macro with its denominator disclosed. It never earns a90% gain success or an improving-design discovery. Regret is the difference in these cycle reductions. For censored pools this is regret to the best verified reference, a lower bound on regret to the unresolved optimum.

Each source receives equal macro weight after its five dependent seed repetitions are averaged. Seeds are bootstrap/tie repetitions, not independent workloads. Every policy uses the same frozen historical cohort and pays for each query before observing its outcome. All twelve policies, caps32/64/128 and budgets1/2/3 are in endpoints.csv and source-macro.csv. These are cooperative paid replays, not measured live adaptive-search lifetimes.

| Factorized model versus | Source wins | Ties | Losses |
| --- | --- | --- | --- |
| Frequency | 1 | 1 | 1 |
| Merit | 0 | 1 | 2 |
| Calibrated latency | 0 | 1 | 2 |
| Latency + cost heuristic | 1 | 2 | 0 |

These counts compare mean verified cycle reduction at the fixed primary endpoint in each source. They are descriptive comparisons of the frozen policies; no statistical significance or general model superiority is established. Source-specific gains and differences are in primary-comparisons.csv.

## Actual processor evidence

| Source | Baseline cycles | LUT4 | Minimum Fmax MHz |
| --- | --- | --- | --- |
| beebs-aha-compress | 70797 | 1653 | 68.493148804 |
| beebs-ndes | 234519 | 1653 | 68.493148804 |
| beebs-nettle-md5 | 6192 | 1653 | 68.493148804 |

| Source | Candidate | Cycles | Speedup | LUT4 / added | Minimum Fmax MHz | Correctness | Charged monotonic s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| beebs-aha-compress | candidate_00 | 68277 | 1.036908476 | 1722 / 69 | 65.291198730 | Verified for recorded input | 39.504767167 |
| beebs-aha-compress | candidate_02 | 68277 | 1.036908476 | 1725 / 72 | 66.299804688 | Verified for recorded input | 43.785656875 |
| beebs-aha-compress | candidate_05 | 69177 | 1.023418188 | 1729 / 76 | 66.339393616 | Verified for recorded input | 39.011896334 |
| beebs-aha-compress | candidate_07 | 69177 | 1.023418188 | 1714 / 61 | 64.184852600 | Verified for recorded input | 40.275185750 |
| beebs-aha-compress | candidate_09 | 70077 | 1.010274412 | 1722 / 69 | 69.089401245 | Verified for recorded input | 41.357208042 |
| beebs-aha-compress | candidate_11 | 69897 | 1.012876089 | 1730 / 77 | 62.449256897 | Verified for recorded input | 39.413748334 |
| beebs-aha-compress | candidate_14 | 70527 | 1.003828321 | 1749 / 96 | 66.648895264 | Verified for recorded input | 42.483475125 |
| beebs-aha-compress | candidate_16 | 70563 | 1.003316186 | 1721 / 68 | 67.654418945 | Verified for recorded input | 38.892833041 |
| beebs-aha-compress | candidate_18 | 70635 | 1.002293481 | 1720 / 67 | 64.557777405 | Verified for recorded input | 43.448753333 |
| beebs-aha-compress | candidate_20 | 70725 | 1.001018028 | 1727 / 74 | 68.124534607 | Verified for recorded input | 44.967138292 |
| beebs-aha-compress | candidate_23 | 70707 | 1.001272858 | 1720 / 67 | 64.354209900 | Verified for recorded input | 44.627513208 |
| beebs-aha-compress | candidate_25 | 70707 | 1.001272858 | 1716 / 63 | 64.603652954 | Verified for recorded input | 40.066809083 |
| beebs-ndes | candidate_00 | 229399 | 1.022319191 | 1725 / 72 | 73.410659790 | Verified for recorded input | 41.085578875 |
| beebs-ndes | candidate_05 | 231239 | 1.014184459 | 1723 / 70 | 61.854396820 | Verified for recorded input | 50.917899333 |
| beebs-ndes | candidate_09 | 232855 | 1.007146078 | 1681 / 28 | 67.934783936 | Verified for recorded input | 40.668054000 |
| beebs-ndes | candidate_12 | 233495 | 1.004385533 | 1727 / 74 | 61.470371246 | Verified for recorded input | 41.611556167 |
| beebs-ndes | candidate_16 | 233495 | 1.004385533 | 1693 / 40 | 68.264045715 | Verified for recorded input | 40.840389333 |
| beebs-ndes | candidate_20 | 233799 | 1.003079568 | 1693 / 40 | 66.983726501 | Verified for recorded input | 40.386835041 |
| beebs-ndes | candidate_24 | 233879 | 1.002736458 | 1679 / 26 | 69.735008240 | Verified for recorded input | 40.042927584 |
| beebs-ndes | candidate_28 | 234135 | 1.001640079 | 1692 / 39 | 66.480522156 | Verified for recorded input | 43.065202375 |
| beebs-ndes | candidate_32 | 234127 | 1.001674305 | 1694 / 41 | 67.608680725 | Verified for recorded input | 49.095562375 |
| beebs-ndes | candidate_36 | 234291 | 1.000973149 | 1698 / 45 | 64.250831604 | Verified for recorded input | 51.186770583 |
| beebs-ndes | candidate_43 | 234455 | 1.000272973 | 1733 / 80 | 64.234329224 | Verified for recorded input | 45.992210666 |
| beebs-ndes | candidate_54 | 234471 | 1.000204716 | 1709 / 56 | 68.301345825 | Verified for recorded input | 44.084521334 |
| beebs-nettle-md5 | candidate_00 | 6080 | 1.018421053 | 1708 / 55 | 68.493148804 | Verified for recorded input | 71.738368875 |
| beebs-nettle-md5 | candidate_27 | 6104 | 1.014416776 | 1693 / 40 | 65.214553833 | Verified for recorded input | 79.226941500 |
| beebs-nettle-md5 | candidate_54 | 6168 | 1.003891051 | 1715 / 62 | 65.876152039 | Verified for recorded input | 76.273281792 |
| beebs-nettle-md5 | candidate_81 | 6181 | 1.001779647 | 1743 / 90 | 63.897766113 | Verified for recorded input | 78.634455458 |
| beebs-nettle-md5 | candidate_108 | 6181 | 1.001779647 | 1752 / 99 | 69.623336792 | Verified for recorded input | 78.752522125 |
| beebs-nettle-md5 | candidate_135 | 6185 | 1.001131770 | 1724 / 71 | 69.512023926 | Verified for recorded input | 71.843900250 |
| beebs-nettle-md5 | candidate_161 | 6185 | 1.001131770 | 1719 / 66 | 64.532783508 | Verified for recorded input | 79.727678375 |
| beebs-nettle-md5 | candidate_188 | 6189 | 1.000484731 | 1748 / 95 | 68.799453735 | Verified for recorded input | 94.105741541 |
| beebs-nettle-md5 | candidate_215 | 6189 | 1.000484731 | 1754 / 101 | 69.905624390 | Verified for recorded input | 118.238860875 |
| beebs-nettle-md5 | candidate_242 | 6189 | 1.000484731 | 1676 / 23 | 69.468566895 | Verified for recorded input | 104.024682917 |
| beebs-nettle-md5 | candidate_269 | 6189 | 1.000484731 | 1680 / 27 | 59.133110046 | Verified for recorded input | 102.093134417 |
| beebs-nettle-md5 | candidate_298 | 6189 | 1.000484731 | 1669 / 16 | 67.879447937 | Verified for recorded input | 124.191598542 |

Complete candidate resources, analytic-cycle residuals, failures and enclosing operation times are in candidates.csv. Unknown correctness/performance/hardware outcomes remain blank and charged; infrastructure failures do not become negative labels. References cover the declared recorded-input pools, not all legal formulas or arbitrary inputs.

## Costs and reliability

Clock-accounting status: **post-collection accounting amendment**. The unchanged frozen strict checker failed for beebs-nettle-md5. Every original strict-check outcome and mixed-clock diagnostic is preserved in clock-accounting.json. Adding a monotonic duration to a UTC start cannot establish UTC end-time enclosure in this collection. The records do not distinguish suspend from clock adjustment. Uninterrupted calendar wall time remains unknown. Source-bound blocking collector calls, unique charged attempts and contiguous native receipt spans provide the separate serial-order evidence. This accounting amendment changes no model, candidate, policy, label or native measurement.

New collection: 36 charged attempts / 2105.664ledger monotonic seconds, including failures. Candidate operation monotonic elapsed: 2756.322s. Complete candidate subprocess monotonic elapsed, including startup: 2759.079s across 36 successful and 0 failed commands. Baseline ledger monotonic elapsed: 90.610s. Native commands (recorded monotonic elapsed): 705 / 1609.587s. These scopes overlap and must not be added. Historical cost:45 successful labels plus3 failed attempts =48 attempts / 2748.141s. History plus new candidate attempts: 84 / 4853.804s. Qualification/setup subprocess monotonic elapsed: 226.105s, including rejected sources. This overlaps accepted-source baseline/CLI/native timers and is not added to them. Shared historical training costs, setup/calibration and per-seed fitting/prediction timers are retained in costs.json. The shared history is counted once. Recorded durations do not establish uninterrupted wall time. Legacy JSON/CSV fields containing wall retain their original names and now carry this explicit qualification. Policy sums of recorded monotonic durations are not an observed end-to-end acquisition runtime, and no adaptive-time advantage is established.

Feasibility Brier error uses successfully verified candidates only; unknown hardware outcomes are excluded and charged. Bootstrap score spread is uncalibrated estimator disagreement. Broad model superiority, calibrated confidence and joint-set performance are not established. Preserve heuristic wins, ties and regressions. Target labels are now consumed data.

This presenter performs zero model fits and zero native measurements. Qualified clock accounting, raw-evidence and exact policy verification belong to reproduce_blind_campaign replay.

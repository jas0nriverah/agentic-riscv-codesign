# Frozen six-model matched LUT4 comparison

The **MasterRTL SOG adaptation has the lowest primary error on the 192-formula probe: 35.0687 LUT4 MAE**. V2 residual achieves 41.5933 and structural v3 achieves 56.4018. The structural challenger therefore does not beat the matched reference adaptation on this test.

All six models train on the same **713 unique formulas**, from 1098 occurrences across 17 programs. Those programs are development data; nested v3 selection and fixed MasterRTL program holdouts exclude identical held-out formulas. The final independently collected probe has eight predeclared strata of 24 formulas each, all canonically absent from training, with 181 positive labels and 11 zero labels. The primary macro-stratum MAE equals pooled MAE because the strata are equally sized.

| Frozen model | MAE, LUT4 | RMSLE | Positive MAPE, % | Pearson | Zero-target MAE, LUT4 |
|---|---:|---:|---:|---:|---:|
| `masterrtl_sog` | 35.0687 | 0.4943 | 36.5042 | 0.9196 | 3.3961 |
| `v2_residual_xgb` | 41.5933 | 0.8076 | 320.1410 | 0.9236 | 6.5943 |
| `v3_structural` | 56.4018 | 0.8388 | 478.1287 | 0.9117 | 14.9803 |
| `resource_v2` | 60.7228 | 0.9297 | 514.2029 | 0.9434 | 14.4997 |
| `v3_original` | 60.7228 | 0.9297 | 514.2029 | 0.9434 | 14.4997 |
| `v1_xgboost_log` | 80.8586 | 1.2388 | 165.8149 | 0.7650 | 105.4079 |

MAPE excludes the 11 zero labels and divides each remaining error by its own true positive count. Large errors on very small implementations, especially multiplication, explain the hundreds-of-percent values. They remain reported. MAPE is not converted into an accuracy percentage. The original-feature v3 ablation selected the v2 resource prior, producing the same predictions as `resource_v2`.

An [independent recomputation](independent-audit.txt) agrees with every pooled and stratum score. Paired, within-stratum bootstrap differences (comparator minus MasterRTL; 10,000 draws) are 21.33 LUT4 versus v3, with a descriptive 95% interval [2.88, 40.58], and 6.52 LUT4 versus residual v2, interval [−4.89, 18.04]. The latter includes zero. These intervals describe sampled formula variability conditional on the eight curated strata, not new real-workload performance. MasterRTL has lower MAE in seven strata and loses on variable shifts.

The probe candidate freeze is 05:58:35 UTC on 2026-10-13. Five models froze at 06:08:10 UTC; MasterRTL froze at 06:20:14 UTC. The first matched score is recorded at 06:25:30 UTC. Commit `f62a167` records models, sources, protocols, and predictions before label release. No post-probe tuning occurred. Source/data/artifact hashes and exact timestamps are preserved in both preregistrations and the score provenance.

The reference follows [MasterRTL commit 5bccf38](https://github.com/hkust-zhiyao/MasterRTL/tree/5bccf38f8db7bb511a793a709863e7cb1b333ab5): 14 analytical pre-ABC SOG features and 25-tree/depth-12 raw-target XGBoost. It retrains on isolated iCE40 LUT labels, replaces Pyverilog graph parsing with direct one-bit Yosys JSON counts, uses combinational/fixed-port inputs, and fixes threads/seed. This comparison is a matched-target recipe adaptation. It does not reproduce the paper's ASIC-area task or establish real-workload/processor superiority.

Warm median times for all 192 candidates are 5.044 ms (`resource_v2`), 2.854 ms (`v1_xgboost_log`), 15.566 ms (`v2_residual_xgb`), 10.261 ms (`v3_original`), 47.125 ms (`v3_structural`), and 204.801 ms (`masterrtl_sog`). MasterRTL cache IO, integrity checks, and graph traversal are included. A separate fresh-cache MasterRTL run takes 7.4315 seconds cold and 0.2128 seconds warm with identical predictions; cached latency cannot represent cold preprocessing cost. Timing excludes process startup and input/output JSON serialization; model loading is separately recorded.

The evidence archive includes the complete approximately 327 MB SOG cache at `source/results/2026-10-13-v3/masterrtl/sog-cache/`, beside its artifact. This cache is outside Git. Cached replay resolves that relative path and does not execute Yosys. New uncached formulas require the exact frozen Yosys version/binary recorded in the schema. Scoring the saved predictions requires neither the cache nor Yosys.

Contents:

- [probe-evaluation.json](probe-evaluation.json): all six scores, every stratum, and scoring provenance.
- [probe/](probe/): frozen candidates, canonical exclusions, verified measured labels, and completion/freeze integrity records.
- [models/](models/): five full-cohort frozen artifacts, configuration, preregistration, and development evaluation.
- [masterrtl/](masterrtl/): matched reference artifact, feature manifest, source/reference hashes, preregistration, development evaluation, and cold/warm timing.
- [probe-inference/](probe-inference/): six prediction files and artifact/input-bound timing sidecars.
- [Reproduction commands](../../docs/reproduce-matched-comparison.md): pinned runtime setup, strict saved-score replay, all-six frozen inference, and cache requirements.
- [MasterRTL adaptation protocol](../../docs/masterrtl-matched-protocol.md): reference recipe and explicit departures.

All 17-program evaluation results remain development evidence. The 192-formula probe supports this synthetic LUT4 comparison; it does not measure ASIC physical area, timing, CPU speedup, or independent real application performance.

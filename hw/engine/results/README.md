PRELIMINARY: baseline multiplier choice pending team confirmation; numbers may change.

Committed results of the PROVISIONAL measurement engine. Every row was produced by `make hw-measure` / `make hw-sweep*` under the protocol in the root README (frozen PCF, seeds 1–10, every check passing).

| File | What it is |
|---|---|
| `sweep-top3.csv` | each program's top 3 candidates by finder `saved`, each measured alone (21 cores, 22 rows) |
| `sweep-top10-placeable.csv` | each program's top 10 candidates the rewriter can fuse, each measured alone (60 cores, 70 rows) |
| `rankcheck-top10.csv` | Spearman rank agreement between finder `saved` and measured cycles saved, per program |
| `placeability.csv` | rewriter-only pre-check of all 348 candidates: placeable sites and placeable saved vs finder saved |
| `frequency-top3.*` | the frequency-ranking baseline: request, full result, measurement rows |
| `sweep-top10-placeable.csv`, `rankcheck-top10.csv` | the top-10 placeable sweep and its rank check |
| `frequency-placeable-top3.*` | the placement-aware frequency pick (request, selection log) |
| `oracle-lut<budget>.estimates.json`, `oracle-lut<budget>-set<n>.request.json` | the oracle's estimated sets per LUT budget and the requests built |
| `experiments.csv`, `experiments.json` | the comparison of all selection experiments: per-program speedups under both rules, geomeans, LUTs, Fmax, builds needed |
| `builds/<id>.json` | the full result of every measured core, including every fused and skipped site |

## Columns

Speedups follow the root README's protocol: `speedup` uses T_fused = max(T_base, T_measured) with T_base = 1000 / 61.48 MHz; `speedup_cycles_only` is `base_cycles / fused_cycles`. Deltas are fused − baseline for the row's program unless named otherwise.

**`sweep-top3.csv`, `sweep-top10-placeable.csv`** (one row per program × candidate, measured alone)

| column | meaning |
|---|---|
| `program`, `rank`, `formula`, `size`, `runs`, `saved`, `has_mul` | the candidate as the finder reported it (`rank` is its position in `generated/candidates/<program>.json`), its canonical formula, and whether it contains a multiply |
| `status`, `problems` | `ok` when every check passed; `problems` is the check list otherwise |
| `fused_sites`, `predicted_saved` | sites the rewriter fused in this program and Σ (size − 1) × runs over them |
| `instret_delta`, `cycle_delta` | instructions and cycles saved in the program's measured window (positive = saved) |
| `cycles_per_instr_saved` | `cycle_delta / instret_delta` |
| `gap`, `gap_reasons` | finder `saved` − `instret_delta`, and why (per group of sites) |
| `luts`, `lut_delta` | SB_LUT4 of the core and its delta against 2,439 |
| `fmax_median`, `fmax_min`, `fmax_max` | routed Fmax over seeds 1–10, MHz |
| `on_critical_path_seeds` | seeds (of 10) in which the unit's logic is on the critical arc |
| `speedup`, `speedup_cycles_only` | the two scores |
| `verified`, `stock_unchanged`, `micro_ok` | `verify_benchmark` passed; all 8 stock programs unchanged on this core; microtests passed |
| `other_programs` | cycles and instructions this formula also saved in the other programs |
| `cycles_per_custom` | cycles one execution of the fused instruction takes (microtest) |
| `build` | the core's directory under `generated/hw/engine/`; its full result is `builds/<id>.json` |

**`placeability.csv`** (one row per program × candidate, rewriter only)

| column | meaning |
|---|---|
| `program`, `rank`, `formula`, `size`, `has_mul` | as above |
| `finder_saved`, `finder_sites` | the finder's `saved` and `places` |
| `placeable_sites`, `placeable_sites_executed` | sites the rewriter would fuse with this formula alone, and how many of them run in the trace |
| `placeable_saved` | Σ (size − 1) × runs over the placeable sites: the instruction saving a build would measure |
| `gap`, `gap_reasons` | `finder_saved − placeable_saved` and why |

**`rankcheck-top10.csv`**: per program, Spearman ρ between finder `saved` and measured `cycle_delta` / `instret_delta` over its sweep rows, whether the finder's top candidate is the best by cycles, and the geometric means of the two scores over those rows.

**`experiments.csv`**: one row per selection experiment: `formulas`, `luts_delta` (and `est_luts_delta`), `fmax_*`, `unit_on_arc_seeds`, `geomean_max_rule`, `geomean_cycles_only` (and the estimates), `geomean_max_rule_at_fmax_min/max` (the noise interval), `hardware_builds_needed`, and per program `<program>_max_rule`, `<program>_cycles_only`, `<program>_cycles_saved`.

**`../../results/baseline.csv`**: `benchmark, cycles, instret, spike_instret, match, luts, fmax_mhz, fmax_min_mhz, fmax_max_mhz`; core-level columns repeat on every row. **`../../results/fastmul-probe.csv`**: per program `baseline_cycles`, `fastmul_cycles`, `cycle_delta`, `instret`, `verified_and_instret_match`, the two speedups, and the core-level `luts`, `baseline_luts`, `fmax_*`, `baseline_fmax_mhz`, `mul_on_critical_arc_seeds`.

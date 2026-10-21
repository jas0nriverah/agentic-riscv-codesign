# Blind source-transfer campaign

This increment tests the existing twelve selectors on **three independent new sources with twelve candidates each**, doubling the earlier per-source pool size. It introduces no new model settings. The previous 45 verified labels, three failures, seven source workloads and eight contexts remain immutable history. The complete cohort is frozen and pushed before any candidate attempt in any target.

## Before candidate labels

The pinned BEEBS source order is `aha-compress`, `ndes`, `nettle-arcfour`, then `nettle-md5` and `levenshtein` as qualification fallbacks. The first three passing sources are accepted. Qualification uses only unchanged source/input, baseline execution, recorded-input verifier, continuous memory checks and at least twelve legal calibrated formulas. Every rejection, command and setup cost is preserved. Candidate hardware outcomes cannot influence eligibility, order or pool selection.

All sources use the same RV32I/ILP32 `-Os` compiler context, original PicoRV32/PCPI interface and 8 KiB synchronous integrated RAM. The common partition reserves 6,400 bytes for program/data/BSS, at least 128 bytes of guard and 1,664 stack bytes. Original benchmark sources and inputs are byte-identical to BEEBS commit `049ded9f3aeb5591f553879d3a0376b8614e9422`; an external no-op warmup supplies the harness ABI. RC4 additionally checks all sixteen ciphertext bytes against an independently computed golden result outside the counter window, retaining its original roundtrip verifier. The independent reference passes the first [RFC 6229 test vector](https://www.rfc-editor.org/rfc/rfc6229.html#section-2).

The existing relocation guard, calibrated merit-rank stratification, reassembly, stock/custom controls, execution-count checks, integrated synthesis and three route seeds are reused. New scoped registration increases the pool to twelve and the per-context native ceiling to 480 commands / 3,600 seconds; native evaluations remain serial with two build workers. Old six-candidate entry points, source hashes and experiments are unchanged.

Every target uses only the same 45 historical successes for fitting, with its related formula families excluded identically across learned methods. All contexts of each historical source remain grouped. The three new sources never train one another during this campaign. Historical failures remain charged and never become invented negative hardware labels. Baseline/public authentication before and after fitting spans the entire cohort. Candidate dispatch requires the pushed zero-attempt release receipt.

## Comparisons and acceptance

Retain all twelve policies: frequency, instruction-saving merit, calibrated latency merit, historical-cost heuristic, random, existing speedup regressors/ranking, constrained hardware GP acquisition, paid adaptive GP, utility XGBoost and factorized feasibility XGBoost. Exact names and settings live in the frozen selection protocols. Five seeds are dependent repetitions, not additional workloads.

Caps are +32, **+64 primary**, and +128 LUT4; the common required clock is 12 MHz with routing seeds 1/2/3. Each policy receives one, two and **three primary** paid attempts from the same declared pool, including failures. Only measured correct designs satisfying integrated area and minimum routed timing can improve upon baseline. Oracle references cover the twelve-candidate subset, not every legal formula; unknown infrastructure outcomes censor those references.

The primary outcome is source-macro verified feasible cycle reduction after three attempts at +64 LUT4. Also report all caps/budgets, raw cycles/speedup, hardware resources, timing, correctness and actual measurement seconds. Oracle gain fraction is achieved cycle reduction divided by oracle cycle reduction, with baseline-only references undefined and disclosed. It never divides raw speedups or awards baseline a 90% gain success.

All target measurements, failures, model fitting/inference and historical training costs are recorded. Shared history is charged once to cohort totals. Baseline/setup, qualification subprocess time, CLI operations, ledger wall and native-command timers retain separate overlapping scopes. Count-budget comparisons and elapsed-time frontiers do not establish a live equal-wall-time stopping policy. Full-pool serial collection followed by paid cooperative replay is not live adaptive native search.

Scores remain uncalibrated. This campaign tests source transfer and selection value of existing methods; it does not claim novelty, uncertainty coverage, ML superiority or reproduction of CIDRE. Timing-aware joint lookahead and jointly validated one-to-three-instruction sets remain later work. No individual speedups or area increments may be summed for sets.

## Commands

Use Python 3.12 with `requirements-speedup.txt`. Qualification requires the pinned local native tools/reference context and starts zero candidate attempts:

```sh
python scripts/qualify_blind_campaign.py
```

The `scripts/blind_campaign.py freeze` command takes every accepted source as a repeated `--target workload=generated/root` argument. `release` requires the complete preregistration commit to exist on `origin/ai-guided-ml`. Candidate collection then calls `python -m isaforge.blind_workload measure --root ROOT --candidate NAME` once per declared name; never retry a charged failure.

After the campaign is packed, hardware-free reproduction and export are:

```sh
make reproduce-blind-campaign PYTHON=python
make blind-report PYTHON=python
make export-blind-corpus PYTHON=python
```

Derived directories must be fresh; override `BLIND_REPLAY_OUTPUT`, `BLIND_REPORT_OUTPUT` and `BLIND_CORPUS_OUTPUT` for another run. Exact refits, complete Git artifact proof, release-before-attempt chronology and paid policy replay are checked separately from report/export. Results, tests and remaining limitations will be recorded after the frozen campaign completes.

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

All target measurements, failures, model fitting/inference and historical training costs are recorded. Shared history is charged once to cohort totals. Baseline/setup, qualification subprocess time, CLI operations, ledger and native-command timers retain separate overlapping scopes. The completed run's clock qualification below applies: recorded monotonic elapsed seconds cannot establish uninterrupted calendar wall time. Full-pool serial collection followed by paid cooperative replay is not live adaptive native search.

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

Derived directories must be fresh; override `BLIND_REPLAY_OUTPUT`, `BLIND_REPORT_OUTPUT` and `BLIND_CORPUS_OUTPUT` for another run. Exact refits, complete Git artifact proof, release-before-attempt chronology and paid policy replay are checked separately from report/export. `make blind-figures` produces count-budget research plots from the derived report, with PNG/PDF/SVG and numeric metadata.

## Completed native measurements

The complete cohort was pushed at **`0b0884e112fbb3635487f7ae93d5d0f1616dbcb2`** before the zero-attempt release at `2026-10-21T21:36:24.550409+00:00`. All 36 candidates passed integer-oracle checks, the original benchmark verifier, actual custom-execution counters, stock/custom processor controls, integrated synthesis and all 108 candidate routes. The three baselines add nine routes. The existing45 labels and three failed attempts remain unchanged, giving **81 verified labels,84 candidate attempts, ten source groups and eleven contexts**.

| Source | Baseline cycles | Declared / eligible formulas | +64-LUT4 oracle cycles | Speedup | Added LUT4 | Minimum Fmax MHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| aha-compress | 70,797 | 12 / 26 | 69,177 (`candidate_07`) | 1.023418188× | 61 | 64.184853 |
| ndes | 234,519 | 12 / 43 | 232,855 (`candidate_09`) | 1.007146078× | 28 | 67.934784 |
| nettle-md5 | 6,192 | 12 / 297 | 6,080 (`candidate_00`) | 1.018421053× | 55 | 68.493149 |

Every baseline has1,653 LUT4. At+32, compression's restricted pool has no feasible improving instruction; its oracle gain fraction is undefined. DES's+32 optimum is the same as its+64 optimum. MD5's+32 optimum is6,189 cycles at+16 LUT4 (1.000484731×). At+128, compression reaches68,277 cycles/+69 LUT4 (1.036908476×), DES229,399/+72 (1.022319191×), and MD5 retains its+64 optimum. These are measured references, not free inputs to selectors. No candidate had a timing-boundary or device-fit failure.

All 36 cycle deltas match the public calibrated-latency predictions exactly, as did the earlier 45. The factorized selector predicts hardware feasibility and combines that score with this calibrated benefit; it is not a new learned speedup regressor. Existing regressors and the ranking model remain separate, measured-label-trained controls. Additional target rows improve evaluation evidence without proving that a more complex performance model is needed.

The MD5 workload is the original single64-byte compression-block benchmark, not complete padded-message hashing. Source/input verifiers cover the recorded runs. All new pools are merit-rank-stratified subsets after executable/legal filtering. These limitations restrict oracle and generalization claims. Targets are now consumed data; do not tune against them and report a new prospective improvement.

## Fixed-policy result

At the preregistered three-query/+64-LUT4 endpoint, mean cycle reduction over the three new sources is:

| Frozen method | Mean cycle reduction | Mean oracle gain fraction |
| --- | ---: | ---: |
| Merit / calibrated latency | 1.144539% | 0.800000 |
| Normalized XGBoost | 1.449636% | 0.933333 |
| Constrained GP, zero shot | 1.602185% | 1.000000 |
| Constrained GP, paid adaptation | 1.602185% | 1.000000 |
| Factorized feasibility XGBoost | 0.719365% | 0.497436 |

This is a summary of fixed, prelabel methods, not a posthoc best-model selection. [All twelve methods, caps and budgets](../results/2026-10-21-blind-report/results.md) remain visible. Both GP controls reach all three measured optima by query three in every dependent seed. Merit/calibrated latency reach two; compression's query-three choice saves648 cycles versus the oracle's1,620. Normalized XGBoost reaches that oracle in four of five seeds. The factorized classifier finds no feasible compression design through three queries and reaches only0.349311% DES cycle reduction, versus0.709537% for merit; MD5 ties. Its two losses/one tie against merit reject its promotion from this experiment.

The GP policies combine public calibrated benefit with learned integrated area, routed minimum Fmax and measurement-duration surrogates. Their positive result supports learned constraint-aware acquisition in these pools; it does not establish a need for learned speedup when calibrated benefit is exact. Normalized XGBoost separately learns from actual historical program-performance labels. Neither GP probabilities nor classifier spread are calibrated confidence.

Adaptive GP reaches compression's optimum on query two while zero-shot GP reaches it on query three. They tie on the primary endpoint, and all methods still spend three attempts in a three-query run. These are count-budget cooperative replays from a fully measured pool, not automatic early stopping or live hardware acquisition. Historical fitting access costs48 attempts and is shared once; it must not be omitted when considering total or amortized efficiency. Three new source groups cannot establish statistical superiority, reliability under arbitrary shifts or a novel acquisition method. Existing constrained GP is a promising control for the next fixed experiment, not evidence that ISAForge beats the field.

The next model change must address a demonstrated decision failure, such as the classifier's compression/DES misses, and be tested on another untouched source. First retain these fixed controls and qualify future duration measurements with paired clock endpoints. More hyperparameter/model sweeps or a speedup residual learner are not justified by zero measured latency residuals. Joint instruction sets and timing-boundary generalization remain untested.

## Post-collection clock qualification

The unchanged frozen packer rejected mixed-clock end enclosure on MD5 candidates215,242,269 and298. It adds calendar UTC starts to monotonic durations; inferred CLI ends fall short of inferred ledger ends by328.946,2,005.594,16.928 and2,970.152 seconds. The logs do not distinguish suspension from wall-clock adjustment. No measurement or timestamp was corrected or retried.

`scripts/reproduce_blind_campaign.py` is an explicit **post-collection accounting amendment**, outside the prelabel freeze. It preserves that strict failure and every raw clock. It separately authenticates the frozen collector's blocking serial subprocess calls, exact candidate order, one-attempt ledgers, contiguous scoped native receipts, terminal statuses and `subprocess ≥ CLI ≥ ledger` monotonic duration totals. Recorded UTC starts remain ordered after release; reconstructed UTC ends are diagnostics rather than enclosure proof. The adapter, collector manifest and clock audits are bound into final provenance. Frozen models, hardware measurements, candidates, policies and count-budget endpoints are unchanged.

Collection recorded2,759.079 subprocess monotonic seconds,2,105.664 ledger seconds and226.105 qualification/setup subprocess seconds. These scopes overlap. The shared 48 historical attempts cost2,748.141 recorded ledger seconds and are counted once. Historical and current timer coverage differs; these numbers are not an end-to-end or uninterrupted wall-time total. No equal-wall-time or live adaptive-search advantage is claimed. The original failure is retained in [validation](../results/2026-10-21-blind-validation/README.md).

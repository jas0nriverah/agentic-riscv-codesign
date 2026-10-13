# Measured ISAForge pilot — October 13, 2026

These results come from actual Embench execution, Verilator checks, and Yosys
synthesis. They are **not measured processor speedups**.

| Evidence | Result |
| --- | --- |
| RV32IM benchmark self-checks | 8 / 8 passed |
| Counter-validated retired instructions | 26,203,169 |
| Extracted candidate examples | 339 across 8 benchmarks |
| Distinct synthesized formulas | 301, no synthesis failures |
| Candidate RTL input/output comparisons | 338,324 passed |
| Software block replacement comparisons | 24,624 individual + 8,880 joint passed |
| Nested held-out MAE | 33.08 LUT4, versus mean baseline 77.32 |
| Nested held-out Spearman | 0.801 overall; 0.611 on nonzero-LUT rows |
| Final model | XGBoost, chosen through grouped validation and refit on all distinct formulas |

The fitted target is the count of `SB_LUT4` resources in an **isolated
combinational iCE40-mapped circuit**. Other resource types are recorded but are
not included in the prediction target. No device place-and-route, core decoder,
pipeline, architectural cycles, or final clock period is measured here.

## Read the evidence

- [benchmarks.json](benchmarks.json): actual commands, self-check exit codes,
  retired-instruction counters, toolchain/source versions, and trace/binary hashes.
- [candidate-summary.json](candidate-summary.json) and [candidates](candidates/):
  all formulas, static occurrences, function symbols, and instruction-saving estimates.
- [extraction-equivalence.json](extraction-equivalence.json): original-block versus
  substituted-formula comparisons, including architectural registers and memory.
- [verification.json](verification.json): actual Verilator comparisons of every
  synthesized formula with seeded boundary/random vectors.
- [synthesis-metrics.json](synthesis-metrics.json): actual per-circuit mapped
  counts, tool versions, and source hashes.
- [dataset.json](dataset.json): trainable rows; identical circuits retain their
  benchmark associations, but fitting deduplicates formulas.
- [evaluation.json](evaluation.json): all outer predictions, inner model choices,
  per-benchmark scores, baseline scores, and nonzero-LUT subsets.
- [area-selection.json](area-selection.json): full budgeted selection replay.
- [research-direction.html](research-direction.html): primary-source positioning
  and the one-week midterm plan.

`experiment-summary.json` describes the final expansion run. Its synthesis wall
time includes cache reuse of the initial 142-circuit run; it is not the cold
runtime for synthesizing all 301 circuits. Raw synthesis logs, RTL, netlists, and
verification vectors remain under `generated/real/experiment` and accompany the
separate evidence archive. Multi-gigabyte traces are regenerated rather than
committed to Git.

## Train and use the model

From the repository root after installing `pip install -e '.[dev,reports]'`:

```sh
python -m isaforge.area_model train \
  --rows results/2026-10-13/dataset.json \
  --output-dir generated/real/model --seed 20261013
python -m isaforge.area_model predict \
  --model generated/real/model/area-model.joblib \
  --candidates results/2026-10-13/candidates/crc32.json \
  --output generated/real/model/crc32-predictions.json
python -m isaforge.area_selection \
  --rows results/2026-10-13/dataset.json \
  --outer-evaluation generated/real/model/evaluation.json \
  --output generated/real/area-selection.json
```

Inference requires only formula text. The saved schema records dependency
versions, source-data hashes, and model configuration. Use the recorded versions
to reproduce the saved artifact. See [model methodology](../../docs/area-model.md).

## What the pilot supports

The nested evaluation excludes each entire benchmark and every matching formula
from training. Model configuration selection uses only inner folds. The final
refitted model is distinct from the held-out predictions used for evaluation.
The fixed comparison includes mean, Ridge, Extra Trees, random forest, and XGBoost.
The corpus includes 92 zero-LUT examples, and nonzero-LUT metrics are reported
separately. Expensive multiplier circuits, especially EDN examples, remain a
substantial source of error. There is one compiler configuration and one input
workload per benchmark; broader generalization has not been established.

With one new target measurement and caps of 64 or 128 LUT4, the model-guided policy
retains 100% of the measured pool oracle's instruction savings across the eight
benchmarks, versus 87.5% mean retention for merit ranking. **Historical training
measurements from other benchmarks are outside this target budget.** With three
measurements, simple merit reaches the oracle for every tested cap. At cap 32,
prediction errors hurt EDN and WikiSort. Thus this is a limited-budget benefit,
not universal superiority or measured runtime acceleration.

Candidate interpretation matters: CRC32's top pattern is in `rand_beebs`,
WikiSort's top pattern is an identity, and the conservative extractor finds only
one matrix-multiplication candidate. No instruction-saving percentages should be
presented as measured CPU speedup.

## Recollect rather than replay

Follow [toolchain setup](../../docs/toolchain.md), then extract all eight candidate
files with `src/candidates.py --max-size 4 --objdump <toolchain-objdump>` into
`generated/real/candidates`. Verify substitutions with
`src/verify_candidate_fusions.py` and run:

```sh
python -m isaforge.real_experiment --per-benchmark 10000 --workers 2 \
  --output generated/real/experiment
```

The high per-benchmark limit includes every candidate in this finite pool; larger
future pools may require an explicit sampling plan. Every distinct formula passes
RTL verification before synthesis labels are admitted. A real chained-shift
verification failure was found and corrected before these labels were collected;
the regression remains in the test suite.

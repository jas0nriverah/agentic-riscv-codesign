# Prospective synthetic formula stress test

The probe is a separate, deterministic circuit source designed after the prior
benchmark-based experiments. It tests structural extrapolation on **synthetic
formulas**, and must not be described as independent real workloads or as a
comparison against a published system. Exact canonical novelty does not imply
semantic novelty: commutative operands, related constants, and related graph
families can still overlap with earlier corpora.

The frozen plan uses seed `2026101303` and 192 formulas, with 24 in each stratum:
arithmetic chains, shared diamonds, parallel branches, mask logic, constant
shifts, variable shifts, signed/unsigned comparators, and constant/variable
multiplication (including high product instructions). Each formula has two to
four distinct operation nodes and at most two input leaves. Shared nodes count
once. Sampling uses only seeded graph patterns and constants; it cannot access
model predictions or hardware labels. Dynamic instruction frequency and savings
are unavailable because no workload is executed, so no budgeted workload
selection claims can be made on this probe.

Before candidate creation, collect canonical formulas from the training,
calibration, and final benchmark datasets. Their combined union must contain
exactly 713 formulas. Reject every exact canonical duplicate of this union or
another probe candidate. Before invoking measurement tools, save the complete
candidate list, excluded formula list, seed, strata, generator source hash,
measurement source hashes, input dataset hashes, and freeze timestamp. Resuming
requires the candidate list and source/input hashes to match this freeze.

Every candidate is actual generated RV32 RTL. Compile all candidates together
with Verilator and compare outputs with the independent Python integer oracle
on the existing Cartesian boundary vectors plus 2,048 seeded random input pairs.
Then synthesize every candidate with the existing Yosys generic and default
`synth_ice40` flows. Retain RTL, vectors, harness, complete tool logs, scripts,
netlists, hashes, and per-circuit measurements. Default iCE40 LUT4 and carry
counts are resource proxies; they do not represent physical area, timing, CPU
cycles, or speedup. Oracle sampling is not formal equivalence.

Collection may proceed while v3 training is in progress. The collector reports
only completeness until the v3 model is frozen; neither label values nor probe
accuracy can be disclosed to the modeling agent before that freeze. Probe
labels must never enter v3 training, calibration, model selection, or feature
selection. After model freeze, score every candidate and report accuracy once,
including each stratum and the full pool. A post-result change to the model or
probe requires a separately named experiment.

```sh
.venv/bin/python -m isaforge.probe_corpus \
  --exclude generated/real/experiment/dataset.json \
  --exclude generated/holdout/experiment/dataset.json \
  --exclude generated/final-holdout/experiment/dataset.json \
  --output generated/probe-v3 --count 192 --seed 2026101303 \
  --expected-excluded-count 713 --workers 2 --random-vectors 2048
```

Use `--freeze-only` to inspect the candidate plan before collection. Reusing the
same command resumes verified, hash-matched circuit measurements. The collector
returns an error if any circuit fails, and its completion report preserves the
declared pool size instead of silently treating a smaller pool as complete.

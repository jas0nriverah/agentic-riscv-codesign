# Pairwise-ranker explainability diagnostic — October 27, 2026

This interpretation-only result uses the existing XGBoost pairwise ranker and the frozen 122-label corpus. It adds no hardware measurements, does not tune the model, and does not promote it. All figures are retrospective on consumed development data.

## What the model learned to use

The global chart summarizes native XGBoost additive tree contributions from 14 whole-workload-held-out fits. Each fold also excludes related operation-tree families. Absolute feature contributions are normalized within each candidate; candidates are averaged within each workload, then the 14 workloads receive equal weight. Whiskers are descriptive 95% bootstrap intervals over workload groups.

Trace-derived opportunity features (`saved_percent`, `places`, `saved`, and `runs`) dominate the rank score. These are candidate-enumeration/profile proxies: `saved` is the theoretical number of trace instructions displaced if that pattern is fused at all counted executions. Overlap, implementation cost, compiler effects, and whole-program runtime are not captured by that number. Feature attribution is explanatory for this fitted model, not causal.

## Local held-out example

The bitcount candidate `add(in0,andi(in1,15))` ranked **1 of 12** by raw rank score (0.473). Its highest positive contributions are `saved_percent` and `places`. The actual measurement yielded 1.0088× speedup, verified correctness, 65 additional LUT4, and 61.82 MHz minimum routed Fmax. With a +64-LUT4 cap, it exceeds the limit by one LUT4. The ranker has no hardware-cost input, so this is a useful example of why a strong opportunity score must be combined with measured or separately predicted feasibility.

The signed contributions sum with the base value to the raw rank score. Positive values push the score higher; negative values push it lower. That raw score is only an ordering value, not predicted speedup or a probability.

## Files and reproduction

- `global_feature_contributions.svg` and `.csv`: global feature attribution and workload-bootstrap intervals.
- `local_candidate_explanation.svg` and `.csv`: signed contribution waterfall for the held-out bitcount example.
- `explanation.json`: method, data/source provenance, package versions, fold checks, measured local outcome, and limits.
- `manifest.json`: hashes for every artifact in this directory except the manifest itself.

Reproduce from the repository root with the pinned audit environment:

```bash
../work/audit-venv/bin/python scripts/explain_ranker_contributions.py
```

The script refuses to overwrite this result directory and verifies the source corpus hash and its adjacent integrity seal before fitting.

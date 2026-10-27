# Joint posterior paid-prefix calibration diagnostic

**Retrospective development analysis.** The same fixed-joint posterior recipe is scored before each held-out candidate outcome and conditioned only after a verified success. The order is ascending candidate ID, not an active policy. The original zero-query calibration artifact is unchanged.

Authenticated input: 122 successful labels and four charged failures (`901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef`).
Folds and model fits: 14 / 14. No native jobs or new measurements.

## Pooled results by charged prefix

Prefix means the number of earlier attempted candidates; failures count in the prefix but do not update the posterior.

| Earlier charged attempts | n | Area 50/80/95% coverage | Fmax 50/80/95% coverage | Log time 50/80/95% coverage |
|---:|---:|---|---|---|
| 0 | 14 | 0.429 / 0.714 / 0.929 | 0.500 / 0.714 / 0.929 | 0.571 / 0.786 / 0.857 |
| 1 | 13 | 0.692 / 0.769 / 0.923 | 0.308 / 0.615 / 0.846 | 0.462 / 0.923 / 0.923 |
| 2 | 14 | 0.500 / 0.714 / 0.857 | 0.571 / 0.714 / 0.929 | 0.500 / 0.714 / 0.857 |
| 3 | 13 | 0.538 / 0.769 / 0.923 | 0.385 / 0.769 / 1.000 | 0.615 / 0.923 / 1.000 |
| 4 | 13 | 0.615 / 0.692 / 0.846 | 0.462 / 0.615 / 0.769 | 0.462 / 0.769 / 0.769 |
| 5 | 14 | 0.571 / 0.857 / 0.929 | 0.571 / 0.786 / 0.857 | 0.429 / 0.786 / 0.857 |
| 6 | 6 | 0.500 / 0.833 / 1.000 | 0.167 / 0.500 / 0.500 | 0.333 / 0.667 / 0.667 |
| 7 | 7 | 0.429 / 0.571 / 0.571 | 0.143 / 0.429 / 0.571 | 0.286 / 0.571 / 0.714 |
| 8 | 7 | 0.714 / 0.714 / 1.000 | 0.571 / 0.714 / 0.714 | 0.286 / 0.571 / 0.714 |
| 9 | 7 | 0.429 / 0.714 / 1.000 | 0.429 / 0.571 / 0.714 | 0.143 / 1.000 / 1.000 |
| 10 | 7 | 0.429 / 0.857 / 1.000 | 0.429 / 0.714 / 0.857 | 0.429 / 0.714 / 0.857 |
| 11 | 7 | 0.714 / 0.857 / 1.000 | 0.571 / 0.714 / 0.857 | 0.286 / 0.571 / 0.857 |

## Limits

Candidate-ID-sorted predictions are scored before each row's recorded outcome is supplied to the posterior. Successful outcomes update the state; charged failures do not. This tests sequential conditioning under a fixed, non-adaptive order, not selection-conditioned calibration or a live acquisition policy.

- All target outcomes are from the consumed 122-success / four-failure development corpus.
- Candidate-ID order is deterministic and chosen independently of target labels, but is not a real or simulated active-selection policy.
- Repeated within-workload residuals are dependent; confidence intervals are not workload-population intervals.
- The fixed Gaussian noise, independent output heads, and feasibility assumptions are unchanged and remain provisional.
- No new model recipe, hyperparameter, hardware measurement, or native job was introduced.

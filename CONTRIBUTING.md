# Development

```sh
./start.sh --test
```

| Change | Required checks |
| --- | --- |
| Runtime, startup or inference | Full tests, saved-score replay and actual cached inference |
| Model or training data | Declared comparison, frozen predictions, independent validation |
| Documentation or figures | Local links, accurate numbers and visual inspection |
| Hardware | Relevant simulation, synthesis and toolchain checks in `hw/README.md` |

| Preserve | Why |
| --- | --- |
| Frozen weights, runtime source, observations and receipts | Hash-checked reproducibility |
| Failed cases, zero-area circuits and incomplete cohorts | Honest evaluation |
| Separate MAE, tail errors and budget mistakes | Better averages do not imply safe hardware decisions |
| A new output path for each run | Avoid silently replacing evidence |

Keep transient outputs in `generated/`. Add new research implementations outside the frozen `isaforge/` runtime unless you also produce and validate compatible model artifacts. Historical implementation names are evidence identities, not front-page content.

`main` is the entry point for users. Research records remain under `results/`; the hardware track remains under `hw/`. Merge changes only after their relevant checks pass.

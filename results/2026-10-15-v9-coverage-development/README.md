# V9 fixed training-coverage development

One fixed fit adds 48 measured training circuits to the original 1,665, with unchanged 217 mapping features, 300-tree ExtraTrees settings and seed. Equal-family MAE on consumed V8 applications falls 3.409191 → 2.543396 LUT4 (25.40%). All four families improve. The six diagnosed constant-product cases improve 49.72% in aggregate, with two individual regressions.

This is consumed development evidence. The full 192-case V6 regression set improves 9.66% in MAE, but P99 error, maximum underprediction and cap128 false rejections worsen. Application cap64 false rejections remain three. No independent transfer, learned-selection or CPU improvement is established.

See [complete results and publication figures](../../docs/v9-coverage-results.md).

## Evidence

- `preparation.json`: 85 frozen input/source bindings; input freeze commit `7515b8c8e640bf85cdcd11a6ec3fd2f29606a764`.
- `input-review/`: independent preparation review, Git identity review and parent validation.
- `measurement-approval.json`, `measurements/`: the authorized first collection, 48 complete labels, all 103,104 RTL output checks, logs and authenticated raw ZIP.
- `independent-audit/`: independent unsigned oracle, original-RTL identity and mapped LUT4/carry recount; all 343 archive members validated.
- `fit-approval.json`, `fit-claim.json`: separately released, root-scoped single fit after raw audit.
- `fit-attempt-0000/`: native feature evidence, the 1,713-row model, point freeze, first fit log and complete evaluation.
- `fit-review/`: independent arithmetic replay across all four cohorts and real CLI inference for 48 native cases. The initial type-only audit failure and precisely scoped correction remain preserved.

The preparation proposal describes the experiment before outcomes and remains immutable. The results note records its completed outcome. All model outputs are predictions of original-RTL iCE40 LUT4 count.

## Reproduce and infer

From an installed checkout with `requirements-research.txt`, run `make reproduce-v9-coverage` to authenticate evidence, run saved-feature inference, and replay metrics and figures into a fresh output directory. It does not retrain or invoke native hardware tools.

For actual formula inference, compatible Yosys preprocessing is required for a new formula; a verified native cache can be reused:

```sh
python -m isaforge.area_model_v6 \
  --model results/2026-10-15-v9-coverage-development/fit-attempt-0000/models/mapping-coverage.joblib \
  --candidates results/2026-10-15-v9-coverage-development/candidates.json \
  --cache-root generated/v9-coverage-features/fit-attempt-0000 \
  --output generated/v9-coverage-inference.json
```

Use a fresh output path and preserve frozen artifacts. The saved-feature reproduction is the portable path; native extraction has separate toolchain requirements. Training MAE is an in-sample diagnostic, not an estimate of transfer performance.

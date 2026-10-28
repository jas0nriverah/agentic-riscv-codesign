# Historical feature-aliasing diagnostic

This report authenticates the consumed **122-success / 14-workload** historical corpus. Four charged failures are excluded from this numeric hardware-label diagnostic. It fits no model, tunes no threshold and reads no tiny-regex target outcomes.

The diagnostic asks whether different measured +64-LUT4 / 12-MHz feasibility outcomes share exactly the same input representation. All representation keys are computed from public features and syntax before their labels are scored.

| Representation | Unique vectors | Mixed-label groups | Rows in mixed groups | Opposite-label pairs |
|---|---:|---:|---:|---:|
| Current ranker numeric features (including profile counts) | 122 | 0 | 0 | 0 |
| Current hardware-feasibility structural features | 108 | 2 | 8 | 6 |
| Proposed structural features + ordered AST paths | 114 | 0 | 0 | 0 |

## Demonstrated limitation

These historical rows share one structural numeric vector:

- `add(in0,slli(in1,2))` — beebs-ndes, +70 LUT4, infeasible.
- `add(in0,slli(in1,2))` — embench-crc32, +70 LUT4, infeasible.
- `add(in0,slli(in1,2))` — embench-edn, +70 LUT4, infeasible.
- `slli(add(in0,in1),2)` — beebs-ndes, +40 LUT4, feasible.
- `add(slli(in0,2),in1)` — tacle-bitcount, +70 LUT4, infeasible.
- `add(slli(in0,2),in1)` — embench-ud, +70 LUT4, infeasible.

These historical rows share one structural numeric vector:

- `xor(in0,srli(in1,8))` — embench-crc32, +65 LUT4, infeasible.
- `xor(srli(in0,8),in1)` — beebs-aha-compress, +63 LUT4, feasible.

The feature vector records operation counts, depth and aggregate constants, but omits parent/child ordering and operand placement. At a fixed area cap, the existing cap-relative proxy also cannot distinguish identical vectors. The proposed descriptor preserves full ordered AST paths, input roles and exact constants using public syntax alone. It is a representation diagnostic, not a trained embedding or a recommendation to memorize full formulas.

## Decision and limits

This supports testing compact operator-order and operand-position features. It does **not** justify promoting a new selector or changing the frozen model. Separating syntax does not establish prediction or selection improvements. Any feature challenger needs a separately frozen, grouped workload/family evaluation; results on this already-consumed corpus remain development evidence.

The collision-based in-sample classification-error lower bound applies only to deterministic classification of these exact feature vectors. It is not an irreducible generalization error estimate. The ranker includes dynamic profile counts; absence of full-vector collisions there does not make those profile counts a hardware-cost representation or demonstrate a selection win.

```sh
../work/audit-venv/bin/python scripts/report_historical_feature_aliasing.py
../work/audit-venv/bin/python scripts/report_historical_feature_aliasing.py --verify reports/2026-10-28-historical-feature-aliasing-r1
```

Every input and output is hash-bound in `diagnostic.json` and `manifest.json`. No native jobs, LLM calls, training fits or candidate measurements are performed.

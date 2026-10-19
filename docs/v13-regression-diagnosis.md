# V13 collateral regressions and the bounded specialist hypothesis

V13's global augmentation changes predictions on **1,370 of the original 1,713 formulas** in at least one seed (1,269 in all three). Across formula-level AE means over the three seeds, **673 worsen, 691 improve and 349 tie**. The sums of positive and negative AE changes are **+1,218.726 and −712.604 LUT4**, leaving **+506.121 LUT4** total error, or pooled MAE +0.295459. The primary equal-nine-stratum macro MAE change remains **+0.284232 LUT4**. These are consumed-development diagnostics of the published negative [V13 result](v13-coverage-results.md), not a new selection result.

The [complete diagnosis](../results/2026-10-16-v14-specialist-development/diagnosis.json) preserves every original row's three paired predictions, exact targets/folds, top 10 hurt/help lists, all 115 original high-product formulas, operand support and training-context counts. AE means are `mean_seed(abs(prediction−target))`, not the absolute error of an averaged prediction.

| Original stratum | Rows | Predictions changed, any seed | Mean AE, control→augmented | AE change |
|---|---:|---:|---:|---:|
|Arithmetic chain|131|131|6.1392→6.7030|+0.5638|
|Comparators|139|127|0.5872→0.6121|+0.0249|
|Constant shifts|142|115|1.8408→1.8968|+0.0559|
|Mask logic|166|87|0.5605→0.5541|−0.0064|
|Multiplication|186|147|28.0132→30.3800|+2.3668|
|Parallel branches|142|120|1.5163→1.5445|+0.0281|
|Shared diamond|116|116|3.6792→3.5928|−0.0864|
|Variable shifts|117|113|3.5648→3.1034|−0.4613|
|Workload|574|414|3.6345→3.7072|+0.0727|

## Where the costly regressions are

The 115 original formulas containing a high-half product contribute **+418.526 LUT4 net AE (82.69% of the total increase)**; their MAE rises 37.3884→41.0277. Among the other 1,598 originals, 1,284 predictions change and net AE increases 87.596 LUT4. Global refitting therefore perturbs both related operators and unrelated structures.

The five largest mean-AE regressions are all unsigned `mulhu` contexts in fold 3. Negative literals here denote unsigned 32-bit values near `2^32`, not small signed multiplier operands:

| Formula | Target | Mean AE, control→augmented |
|---|---:|---:|
|`xori(mulhu(addi(in0,-257),-1),2)`|1318|163.028→281.498|
|`addi(mulhu(xori(in1,65535),-1),0)`|1271|172.508→279.187|
|`srli(mulhu(addi(in1,17),-7),7)`|1347|209.161→309.739|
|`andi(mulhu(addi(in0,-1023),-257),65535)`|1236|157.056→251.121|
|`addi(mulhu(xori(in0,63),-17),3)`|1293|139.615→225.666|

Each was already underpredicted; augmentation moves its point downward further. The largest improvement is `xori(mulhu(addi(in0,-257),andi(in1,1431655765)),1)`, reducing mean AE by 87.698 LUT4. A blanket “high products improve” account would hide both directions.

There are **38 `mulh`, 39 `mulhu` and 38 `mulhsu` original formulas**. None contains the frozen V7 correlation pattern inside a high-product operand. Only one high-product node shares an input symbol between its operands: `add(in0,mulhu(in1,in1))`; its mean AE improves 20.559 LUT4. Repeated-input multiplication alone therefore differs from `(x|K)−x` or `x−(x&K)` correlation. Of 230 original multiplier operands, 134 receive interpreted width 32 under the existing independent known-bit analysis; the full support/width histogram is retained without choosing a width threshold.

## Fold context does not identify a cause

| Fold | Original validation rows | New training rows: high/affine/composition | Original pooled MAE change |
|---|---:|---:|---:|
|0|368|16/12/16|−0.0329|
|1|374|16/8/16|−0.2360|
|2|345|16/16/12|−0.0225|
|3|305|8/12/4|+1.4400|
|4|321|8/16/16|+0.5454|

The high-product contexts are withheld as complete eight-row groups: fold 3 assesses `sub_and_complement`, fold 4 assesses `or_sub`. Folds differ in both training additions and original assessment formulas. Their error shifts cannot establish which new family, point or tree split caused the losses. No model was loaded and no leaf-influence or ablation claim is made.

## One input-defined route, with an explicit limit

The existing [V6 mapping selector](../isaforge/area_model_v6.py) uses194 SOG/generic-graph columns plus23 original mapping descriptors; its217 columns do not include the V7 bit-correlation block. The pattern can therefore define an input scope without proposing another feature block or another fit. This observation does not establish that adding semantic features would improve the predictor.

The single prospective predicate is now fixed separately: a `mulh`/`mulhu`/`mulhsu` operand subtree contains frozen V7's exact `or_sub` or `sub_and` pattern with an **input-containing shared atom**. It uses no target, point, error, cohort, mask threshold or formula whitelist. The diagnosis finds **0/1,713 old rows and 16/48 new rows** inside that predicate. Returning the exact V13 control OOF point outside it preserves the old cohort by construction; this does not prove transfer quality. An input-containing atom can still cancel to a semantic constant. New training support consists of 16 root-`mulhsu` circuits, so other product kinds, nesting and masks remain unconfirmed.

After the source/plan freeze, the parent scored that one route once. The [independent routing replay](../results/2026-10-16-v14-specialist-development/independent-routing-audit.json) verified all 5,283 selected points: **5,235 exact control fallbacks and 48 exact augmented selections**, with original primary differences exactly 0 for all three seeds. All saved scores, caps and tails replayed. New-cohort pooled MAE is 27.4819 versus 480.7060 control, but maximum underprediction remains 173.8583 versus 53.5078 control. This is post-hoc consumed-development evidence, not promotion or independent confirmation. No alternate gates were scored. A temporary review-driver loop error was retained separately and corrected without changing experiment inputs or code.

The actionable next step is to assess this one frozen structural boundary on genuinely reserved source groups, retaining original labels, complete pools, budget errors and underprediction tails. The routing comparison preserves the matched V13 control; it does not create a deployed full-data model or validate a new calibration bound.

## Reproduce and source identities

[diagnose_v13_regressions.py](../scripts/diagnose_v13_regressions.py) reads the existing six OOF pointsets and thirty start receipts, checks unchanged source bytes, and writes a fresh JSON output. It calls only the frozen parser and pure V7 syntax/known-bit helpers; no solver normalization, graph extraction, fits, model loading, native measurements or new labels occur. Its source SHA256 is `02e6832b1072659fcd3d170a38334bfbfce6c4823a8b79a59f7c97188b8875a4`; frozen V7 source SHA256 is `eddc21bd80fd97dea7e02cbfe14bb5b50649f779ed53ec6068674adc1dc0f9e3`. All input/source SHA256 values, including the frozen V13 runner and each pointset, are in `diagnosis.json`.

```sh
python scripts/diagnose_v13_regressions.py --output /tmp/v13-diagnosis-new.json
```


The corrected routing replay is retained as [audit_v14_routing.py](../scripts/audit_v14_routing.py), source SHA256 `4b4932b955ba6f18ad76bac0ab8b9ed2fa3e21b3bcf3041cc26f5a670f1065bc`. Its [fresh v2 receipt](../results/2026-10-16-v14-specialist-development/independent-routing-audit-replay.json) records that source identity and reproduces the original routing audit; the original receipt and initial driver-error record remain unchanged. It independently selects points with the diagnostic AST traversal while disclosing shared V7 syntax and the standard-library metric engine.

```sh
python scripts/audit_v14_routing.py --output /tmp/v14-routing-replay-new.json
```

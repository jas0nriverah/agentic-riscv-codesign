# V15: bounded coverage routing and prospective stress

After the complete V11 comparison showed a global V9 regression, freeze one no-fit router. The input is the original formula AST; no error, target, prediction, candidate ID or application name determines the route. Use frozen V9 if the AST contains a low `mul` with a positive syntactic constant from 1 through 2047 (literal or exact `addi(0,K)`), or `sub(srai(A,k),srai(B,31))` where k is 0 through31 and both A and B contain an input. A and B may differ. Use frozen V6 otherwise. Preserve the chosen point and its uncalibrated metadata exactly.

This tests whether V9's added arithmetic coverage can be used without changing the rest of V6. It does not fit new parameters or claim that these two syntactic classes exhaust the model's training support.

## Final prospective panel

The [prepared plan](../results/2026-10-19-v15-scoped-stress/plan.json) fixes four templates with eight original circuits each:

- Constant multiplication after input XOR: `mul(xor(in0,in1),addi(0,K))`.
- Constant multiplication before input XOR: `xor(mul(in0,addi(0,K)),in1)`.
- Signed shift after input XOR: `sub(srai(xor(in0,in1),k),srai(in1,31))`.
- Signed shift after input AND: `sub(srai(and(in0,in1),k),srai(in1,31))`.

K is 31,47,79,95,111,127,143,159. k is 2,4,6,8,10,12,14,16. The first proposed fourth template used subtraction and overlapped four consumed originals. Its complete draft and failed input-only preflight are preserved in [V15-I1](../archive/2026-10-19-v15-preflight/README.md). Before freezing this panel or generating its predictions/labels, the entire fourth template changed to AND; the other24 inputs remain exact. No post-freeze replacement is allowed.

The input-only novelty check covers fitting1761, V11, the2929 pre-reservation rows, V8 and prior consumed-input ledgers. It compares canonical formulas and recorded aliases. It is not an exhaustive semantic-equivalence proof; the templates deliberately remain related to V9's added arithmetic training.

Freeze all96 V6/V9/V15 predictions before any of the32 fresh target labels. Verify each original on2148 sampled/boundary vectors, then measure its original RTL with pinned Yosys iCE40 synthesis. Keep all results or mark the whole primary unavailable.

## Endpoints and limits

Primary: equal-four-template MAE, with all eight originals per template. Also retain each template, cap32/64/128 false accepts/rejects, bias, RMSLE, error quantiles and maximum underprediction. All32 route to V9 by construction. Their prospective comparison tests covered-domain V9 behavior, not router generalization or new application-family transfer. Any V15 comparison on the now-consumed V11 panel is retrospective and cannot establish a fresh improvement.

One local attempt only: **900seconds total**, at most **two workers**, **360seconds per worker**, **32 target measurements**, **zero new fits**, no parameter sweep, no post-freeze replacements or candidate retries. Keep raw features, netlists, verification files, worker logs and failures. Review average error alongside hardware-budget mistakes and tails; an improved average alone does not justify deployment. The recurring automation stays paused.

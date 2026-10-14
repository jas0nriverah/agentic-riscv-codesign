# Independent semantic correctness audit

Status: **PASS**, before model fitting. No target-label files, calibration/test inputs, model fitting or hardware tools were used. V4/V5/V6 frozen files were not edited.

The tested V7 runtime source SHA256 is `eddc21bd80fd97dea7e02cbfe14bb5b50649f779ed53ec6068674adc1dc0f9e3`. `fitting-inputs/fitting-input-audit.json` binds exact source, original V5 input-feature/split hashes, all 1,665 fitting indices, formula order and retained per-input certificates.

- `prove_rules.py`, `generic-proofs.json`, and `smt2/`: 110 generic QF_BV32 inequality queries and archived-query replays returned UNSAT. They cover both generic-mask bit identities, additive/coefficient reconstruction laws, every fixed left shift 0..31, and RV32 shift-word masking. The solver is isolated pinned z3-solver4.15.4.0; version, native/Python hashes, options and 500ms limits are retained.
- `tests/test_semantic_features_v7_independent.py`: 56 tests passed. The independent tokenizer/parser, recursive integer interpreter and separate complete RV32 SMT translator do not import production evaluation. Tests cover masks, signs, modular overflow, shift masking and chained shifts, negative patterns, nonlinear/high-product barriers, deterministic/idempotent forms, exact feature nesting, metadata exclusion, proof-chain tampering, atomic failure/structural-budget rollback and SAT-fatal behavior.
- `audit_fitting.py`, `fitting-inputs/`: all 1,665 fitting formulas in three modes were independently audited. Affine and combined each changed 933 formulas with 1,037 accepted local steps. Each local inequality was independently UNSAT, and its exact ordered tree path/context was replayed from original to final. All fitting records were accepted with zero unknown, unavailable, budget or SAT outcomes. Every query and certificate remains available.
- The separate recursive interpreter checked 1,603,395 original/final evaluations (321 boundary/random pairs per formula/mode). Another 362,088 multiplier operand checks validated known-bit/range/support and interpreted signed-width claims. Re-execution of all 4,995 formula/mode rows with poisoned target/stratum/component/residual/prediction fields produced exact features and normal forms.

The bit-only mode changed **zero** fitting formulas: neither new identity occurs in this fitting corpus. This study therefore cannot demonstrate learning those identities. Other known-bit descriptor columns can vary; a later OOF improvement must not be attributed to these absent rewrite mechanisms. Do not add examples or labels after observing this limitation within the declared study.

Boundary/random agreement supplements the universal local proofs; it does not replace them. Compositional certificates establish semantic equivalence of the rewritten functions, never original implementation area, mapping optimality or prediction improvement. The original graph and LUT targets remain authoritative. Correctness gates permit the declared fitting-only study; any accuracy or application-transfer claim still needs its own untouched evaluation.

Reproduction (from the repository root): install the optional pinned `proofs` dependency, or put a pinned installation in an isolated directory. Then run the unit tests and the audit scripts. `prove_rules.py` and `audit_fitting.py` require explicit `--deps` paths; they contain no absolute developer path.

```text
python -m pytest -q tests/test_semantic_features_v7_independent.py
python results/2026-10-14-development-semantics-v7/audit/prove_rules.py --deps PATH_TO_PINNED_DEPS --output results/2026-10-14-development-semantics-v7/audit/smt2
python results/2026-10-14-development-semantics-v7/audit/audit_fitting.py --root REPOSITORY_ROOT --deps PATH_TO_PINNED_DEPS --output results/2026-10-14-development-semantics-v7/audit/fitting-inputs
```

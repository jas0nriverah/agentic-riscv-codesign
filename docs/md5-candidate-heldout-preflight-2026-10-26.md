# MD5 candidate-heldout public preflight — October 26, 2026

**Eligibility is pending, candidate dispatch is disabled, and the new-pool label count is zero.** The [preflight package](../results/2026-10-26-md5-candidate-heldout-prereg/README.md) binds the [ordered 12-formula roster](../results/2026-10-26-md5-candidate-heldout-prereg/roster.json), [public evidence and selection rule](../results/2026-10-26-md5-candidate-heldout-prereg/preregistration.json), and [33-row surviving inventory](../results/2026-10-26-md5-candidate-heldout-prereg/remaining-public-inventory.json). The independent [training-cohort audit](../results/2026-10-26-md5-candidate-heldout-prereg/independent-cohort-audit.json) confirms the family exclusion. A fresh exact-28-row [zero-label model preparation](../results/2026-10-26-md5-candidate-heldout-prereg/model-preparation-v1/model-preparation.json) has since completed 31 existing-recipe fits and 115 initial proofs, with zero target-outcome reads, new-pool labels, or native jobs. Its status is `zero_label_models_complete_not_released`; it is not an eligibility release or measurement authorization.

The saved discovery records 299 raw formulas, 297 relocation-safe executable
formulas, and 297 calibrated formulas. Twelve historical attempt filenames
match the prior pool. Excluding all seven attempted operation-tree families
leaves 33 formulas in three families. Sort by descending public instruction
savings, then formula and name; select Python `round(i*32/11)` at indices
`[0,3,6,9,12,15,17,20,23,26,29,32]`. Commutative and global input-swap
canonicalization finds 33 distinct keys. This syntax check does not prove
arbitrary bit-vector semantic equivalence.

The preserved pool-level opportunity gate passes through candidate_03 alone:
`or(xori(in0,-1),in1)` executes 16 times in the original baseline. Archived
xori/or/PCPI latencies of 4/4/5 yield public savings of
`16 × (4 + 4 − 5) = 48` cycles, or `48/6192 = 0.7751937984%`. The other 32
survivors have three or four replacements. The existing rule requires twelve
eligible formulas and at least one same formula meeting both the 0.5% and ten
replacement thresholds. It does not require all twelve formulas to qualify.
These are public projections, not candidate performance measurements.

All historical MD5 rows remain excluded from fitting. The independent cohort
audit removes one additional AHA-mont64 row that shares a formula family with
this roster, leaving 28 rows across seven non-MD5 workload groups. The audit
confirms the fixed recipes can be rebuilt from those historical labels. The old
29-row fitted models, preprocessors, predictions, and pool covariance were
discarded. The exact 28-row recipes were rebuilt in
[`model-preparation-v1`](../results/2026-10-26-md5-candidate-heldout-prereg/model-preparation-v1/model-preparation.json),
which records 31 fit calls and 115 zero-paid initial proofs across the frozen
17-policy comparison. This used historical labels and public target features
only; target outcomes read, new-pool labels, and native jobs are all zero. The
saved models are not released for selection or measurement.

Current zero-label validation: the model-preparation manifest authenticates
all 353 listed artifacts. The focused controller/model-preparation suite passes
166 tests:

```sh
../work/audit-venv/bin/python -m pytest \
  tests/test_md5_offline_controller.py \
  tests/test_md5_protocol_bridge.py \
  tests/test_prepare_md5_heldout_controller.py \
  tests/test_freeze_md5_historical28_models.py \
  tests/test_certify_md5_heldout_roster.py -q
# 166 passed in 2.63s
```

These checks validate package integrity and the disabled/synthetic controller
contracts; they do not establish hardware correctness or authorize candidate
measurement.

The outcome-free cohort binding confirms retained counts of jfdctint 4,
AHA-mont64 3, CRC32 5, EDN 4, SHA256 6, SLRE 4, and UD 2. It excludes candidate
`24881c0f2a3aa96a7b5c2747c870c120bed84db7195d6c80971114f48a3ba7c6`, formula
`add(srli(in0,31),slli(in1,1))`, because its formula family overlaps the new
roster. All eight source hashes in the independent audit still match. The
cohort audit SHA256 is
`c0c58c9f6e89bb12cc954cf54ffe84eb22b23b911f8dbc1ecb8842e6debc2f8b`; its
retained-ID digest is `de2030c83e35df10a476e7cfad3e789dd00cafb3351200eefafbea1d49b56861`.
This verification read only cohort membership metadata, not target values.

The extended [cross-context identity audit](md5-cross-context-identity-audit-2026-10-26.md)
found no literal/canonical alias among 132 public candidates across 16
contexts, including all inventoried automatic pools; all 132 historical
attempt-directory identities map to those pools. This closes the bounded
identity-membership gate, not all historical or semantic-equivalence claims.
The
offline [certificate artifact](../results/2026-10-26-md5-candidate-heldout-prereg/offline-certificates-v1/certificates.json)
binds all twelve entries to archived-context candidate IDs, 59 saved
occurrences, source-PC mappings, relocation checks, 64 sampled block checks
per candidate, and emitted assembly hashes. Its 768 bounded checks are useful
lowering evidence, not universal equivalence, assembler acceptance, or full
program execution/correctness. The old twelve-candidate seal still does not
authorize these entries. A new complete zero-label model and controller
release is required before measurement, followed by root review.

Provenance caveat: an earlier broad documentation search exposed summary
metrics for the old, consumed MD5 pool. Those metrics were treated as tainted
and were not used to select this roster or calculate its opportunity gate. No
candidate-ledger contents or new-pool outcomes were opened.

This is consumed-workload candidate-heldout development. It is not an
untouched-workload test, a calibrated-confidence result, an ML win, or
collection authorization. See the [current handoff](HANDOFF.md) for remaining
gates and ownership.

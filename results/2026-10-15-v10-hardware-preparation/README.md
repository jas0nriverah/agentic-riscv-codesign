# Hardware proof and timing preparation — synthetic checks only

These artifacts validate tools under development, not the 32-pair CSD hardware result. The first actual-RTL SAT attempt separately retained 16 passes and 16 timeouts; no study synthesis arm ran.

The algebra checker derives exact modular affine forms from unsigned equal-width Yosys word-level JSON, retaining bit/mask function identity. It rejects unsupported semantics and does not treat different normal forms as counterexamples. Its 18 synthetic tests and 39 subtests include over 16,000 reduced-width comparisons. The parent additionally ran 12 native frontend jobs on coefficient 13 toy circuits at widths 5/32: four expected equalities passed, four wrong-coefficient controls did not prove, and 2,146 direct-oracle checks passed. These fixtures differ from the study constants; no actual study JSON was collected. RTL/frontend/JSON provenance must be sealed separately before this checker can authorize study measurements.

The timing wrapper and sequential checker have 40 passing tests. Three native toy synthesis jobs ran: the first XOR mapping exposed an unsupported scope-metadata check; its raw output was retained and subsequently replayed without re-synthesis. Final XOR and constant-zero mappings each retain 132 explicit boundary FFs and pass 2,148 complete 99-edge serial transactions. All toy attempts and tool/source hashes remain in the archives. No nextpnr route or actual study candidate was run.

The immutable `evidence-manifest.json` binds every archive member and the tested sources. These checks do not release a new actual-RTL proof attempt, fresh area measurements or the 192 planned routes. The [timing plan](../../docs/v10-timing-direction.md) keeps those stages gated on complete prior results.

A second reviewer independently checked the accepted word-level semantics, rehashed 48 native frontend files, replayed eight proof records and checked 6,438 concrete wire evaluations. All four wrong-coefficient controls have the witness `(in0,in1)=(1,0)`: 12 versus 13. The [review](independent-algebra-review.json) accepts the checker only within its strict unsigned JSON scope and requires authenticated frontend lineage before study use.

The full local suite after these changes passes **1,262 tests and 111 subtests**; see `full-suite.log`. This includes earlier frozen-model regression coverage and does not turn the incomplete hardware study into a successful result.

# Teammate branch review — October 21, 2026

Three GPT-6.1 Sol subagents reviewed the fetched branches without merging, switching the working checkout, running native hardware jobs, or changing frozen experiments. **The hardware branches contain useful work, especially placement diagnostics and joint instruction sets.** Their results require a separate architectural context and stronger measurement accounting before reuse in our selection experiment.

## Branch inventory

| Branch and inspected commit | Relationship / useful content | Decision |
| --- | --- | --- |
| `hw/agent-experiments` — `44a5bd3a48461a58b29b6c98599717e87cb2311e` | Extends `hw/dev` with placement diagnostics, a reported 70-row / 60-core sweep, budget-constrained frequency and small-set enumeration. | Reuse selected ideas/components; do not merge the complete branch or treat its comparisons as prospective ML evidence. |
| `hw/dev` — `d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0` | Separate PicoRV32 hardware track, automatic assembly rewriting, three PCPI slots, joint execution and ten routing seeds. | Best starting point for the later joint-set adapter; preserve our guarded evaluator and evidence contract. |
| `latest` — `7e10fbc4fae9fd2f716827e6421a2906db8dce11` | One curated snapshot commit beyond the foundation: old area models, inference packaging and diagrams. Model weights are byte-identical copies; provenance records no new fits or hardware labels. | No current engineering improvement to merge. Its mass deletion/repackaging would remove current evidence and replace the scope narrative with isolated area prediction. |
| `main` — `23a3d090172ccc0f4551346b959c11661b5ca774` | Already an ancestor; original tracing and candidate finder are included here. | No missing commits to integrate. |
| `codex/isaforge-ml-foundation` — `b64716a2b94b332fdbced677869620bb949c073d` | Already an ancestor; earlier ML, area experiments and audits are included here. | Preserve as history; no missing commits. |

`hw/agent-experiments` is a hardware-selection development branch. Its name does not mean it implements an LLM selection agent or learned acquisition.

## What is worth reusing

1. **Cheap placement diagnostics.** Commit `ff80eee` adds [placeability.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/44a5bd3a48461a58b29b6c98599717e87cb2311e/hw/engine/placeability.py#L64): it reconciles finder sites with executable rewrites and reports rejection/gap reasons. The branch documents a raw-frequency-selected multiplier that executed no sites yet added roughly 650 LUTs. Use its rejection cases and diagnostic fields alongside our existing guarded discovery; do not replace the working extractor or create a second unrelated rewriter.
2. **Relocation-aware assembly scanning.** [asmscan.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0/hw/engine/asmscan.py#L79) and [rewrite.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0/hw/engine/rewrite.py#L59) independently avoid treating symbolic addresses as ordinary constants. This corroborates our demonstrated EDN bug and the new SHA256 guard. Our source guard already provides the needed protection; borrow additional regression cases if they expose a missing case.
3. **Joint one-to-three-instruction implementation.** Commit `07d32f3` provides ordered slots and deterministic decoding in [units.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0/hw/engine/units.py#L66), with overlap-aware rewriting in [rewrite.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0/hw/engine/rewrite.py#L146). This is directly relevant to our missing final-set stage. Port the minimal slot/overlap logic behind our compatible RV32I interface, then execute and synthesize each chosen set jointly.
4. **Small compatible-set enumeration and routing diagnostics.** Commit `450700f` adds [selection.py](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/44a5bd3a48461a58b29b6c98599717e87cb2311e/hw/engine/selection.py#L150), and the hardware track records ten routing seeds and critical-cone diagnostics. These are useful implementation references. The reported 107-LUT set versus 175 LUTs estimated by adding individual increments illustrates why we require joint hardware measurements. Treat routing ranges as descriptive sensitivity, not calibrated confidence.

## Compatibility and evidence limits

| Dimension | Current guarded ISAForge context | Teammate hardware context |
| --- | --- | --- |
| ISA / arithmetic | RV32I plus supported counter reads; software helpers | RV32IM with sequential hardware multiply/divide; fast-multiply probe is a separate configuration |
| Memory | Checked 8 KiB synchronous integrated RAM | Simulated 16 MiB external zero-wait RAM |
| Synthesized boundary | Integrated processor/PCPI/RAM SoC | Processor/PCPI core with external memory interface; the simulated 16 MiB is not synthesized RAM |
| Compiler | Recorded `-O2` or `-Os`, depending on workload context | Original main RV32IM `-O2` build |
| Instruction encoding | Existing guarded custom-0 contract | Up to three slots using a different funct7/slot convention |
| Timing objective | Common feasible 12 MHz; three route seeds | Ten seeds; speedup charges median-Fmax slowdowns and never credits a faster routed clock |
| Primary selection budget | One to three paid target attempts, including failures | LUT-area budget using a previously measured candidate sweep |
| Provenance | Source/input/context-bound plans, raw archives, one-attempt ledgers, Git prelabel predictions | Committed result summaries and checks; formula-only build cache identity and no equivalent paid-attempt ledger |

The committed sweep reports actual Verilator whole-program outcomes and processor synthesis/routing, rather than only instruction-count estimates. The review found passing summary checks in all 21 `hw/dev` single-build JSONs and a passing three-instruction result. **We did not independently rerun or raw-authenticate those hardware results.** Raw simulator binaries, netlists and route logs needed for our audit are not preserved in those committed summaries. Do not add their 70 rows to our 33 verified-label count or silently combine their targets.

The cache key in [units.py:66–88](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/d38135cee1b4e248d8ec91bbfb32c4bcd3ac91b0/hw/engine/units.py#L66) hashes only ordered formula strings. An isolated pure-Python check reproduced the same build ID for the same formula with different `size` metadata. Source, compiler, core and measurement-contract changes also need identity binding before importing this cache into our system. The changed metadata collision is evidence of a missing binding; it does not by itself prove an existing measurement is wrong.

## Why its selection tables are not our equal-budget result

The C3 frequency selector reads measured individual LUT costs from the full sweep ([selection.py:99–102](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/44a5bd3a48461a58b29b6c98599717e87cb2311e/hw/engine/selection.py#L99)). The oracle also reads measured savings across all eight programs ([selection.py:141–147](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/44a5bd3a48461a58b29b6c98599717e87cb2311e/hw/engine/selection.py#L141)). Thus both depend on the 60-core measurement history. The comparison then selects the best of three measured oracle sets per cap against one measured frequency set ([compare.py:123–136](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/44a5bd3a48461a58b29b6c98599717e87cb2311e/hw/engine/compare.py#L123)). Those are useful development experiments, with unequal additional evaluation counts and different information from our prospective policies.

The enumeration uses additive individual area/savings estimates, conflicts derived from all finder-counted sites, and no empty baseline set. It is a shortlist generator, not an exhaustive measured joint-set oracle. A final policy adapter needs executable-site conflicts, baseline fallback, actual combined performance, measured area/timing acceptance, and a charged query interface. The complete 60-core history, additional set evaluations and failures must be counted. Measured target outcomes cannot become free cost features for a frequency comparator.

No ML, LLM-agent, random-query comparison, or faithful named-paper reproduction is demonstrated by these branch changes. Keep their useful engineering evidence and limitations together.

## Integration order

1. Preserve both tracks and this reviewed commit inventory. Keep the completed SHA256 experiment, its prelabel chronology, and all historical failures unchanged.
2. Carry placement rejection cases into our source/lowering diagnostics where they reveal missing coverage. Our current guard already rejects the three SHA256 relocation formulas, so avoid duplicating that solved path.
3. For the planned joint-set milestone, adapt the small slot/overlap components from the hardware engine, with explicit encoding and handshake tests on our processor. Bind all inputs to new contexts and jointly execute/synthesize selected sets. This saves rebuilding the entire framework.
4. Treat the hardware branch's data as a separate consumed dataset until raw provenance, context fields and measurement durations meet an explicit import contract. Group all occurrences of a workload/formula family across architectures when designing holdouts. Inspecting these results is not permission to call them newly unseen data later.
5. Continue to evaluate learned feasibility and acquisition against the strongest cost-aware heuristic. No wholesale branch merge, model replacement, or new RTL-generation framework is needed for this reuse.

Read-only commands used include `git fetch origin --prune`, `git for-each-ref`, `git merge-base --is-ancestor`, `git log`, `git diff`, and `git show` at the pinned commits above. No teammate branch was modified.

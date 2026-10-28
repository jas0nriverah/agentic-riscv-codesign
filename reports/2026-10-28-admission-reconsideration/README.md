# Admission-policy reconsideration inventory

This report reclassifies saved workload rejections under the owner’s active [variable-pool admission policy](../../docs/workload-admission-policy.md). The policy removes the fixed twelve-candidate, 0.5% projected-benefit, and ten-replacement minima. One legal candidate is sufficient for an admission pool; low or negative measured results remain valid outcomes. It does not waive correctness, defined behavior, relocation safety, ISA/lowering compatibility, memory/stack fit, source-family holdouts, or hardware verification.

The [machine-readable inventory](inventory.json) records each named rejection, known safe-candidate counts, substantive blockers, and its evidence paths. `null` means the saved report did not establish the value. This is a read-only synthesis of existing evidence: no source was downloaded or re-run, no build or target job was launched, and no label was created.

## Reconsiderable candidates

| Source | Preserved result | Current interpretation |
| --- | --- | --- |
| TACLeBench **countnegative** | Target checksum passed; image 2472/6400 bytes; stack 64/1664; four calibrated relocation-safe formulas. Old rejection was the fixed-12 minimum. | **Best next candidate.** Fresh context can use the four known candidates; exact source/formula family separation still needs review. |
| LLVM **Stanford Queens** | Target self-check passed; 3 legal formulas; 1160-byte image/data. Old pool and tiny projected benefit failed old numeric gates. | Pool/opportunity-only rejections are gone; fresh evaluation is possible. Puzzle-family relation to Hanoi/Sudoku needs grouping review. |
| MiBench **stringsearch** | 57 fixed cases passed; image 5556/6400; stack 592/1664; 2 safe formulas out of 10 calibrated. Eight candidate expressions used symbolic relocations and were correctly filtered. | Pool size alone no longer blocks its two candidates. It remains closely related to other text-search workloads and has prior exposure. |
| **nanocobs** v1 | Target self-check and memory fit passed; ten safe formulas; old best projection was 0.2517%. | Already reconsidered under v2, which passed the variable-pool baseline qualification. No candidate labels exist. |
| BEEBS **prime** | Fixed self-check passed; one legal formula. Only 4.06% of timed instructions map to marked source; most execution is in linked arithmetic helpers. | Formally admissible by pool size, but weak rewrite coverage makes it a poor next use of evaluation budget. |
| BEEBS **insertsort** | Fixed output check passed; one legal formula and nine occurrences. | Pool gate removed; sorting family is already represented by BEEBS bubblesort and other prior sorting work. |
| BEEBS **Levenshtein** (strlen-adapted context) | First context failed link on missing `strlen`; second preserved context failed the old twelve-candidate gate. The saved summary does not give its exact safe count. | Only the second ABI context is reconsiderable. Its text-distance family is related, and source/input exposure must be carried forward. |
| BEEBS **Nettle ArcFour** | Roundtrip plus independent RFC 6229 first-vector check; old summary says fewer than twelve legal formulas, count not recorded. | Pool gate removed, but this is explicitly a crypto-domain transfer source, not independent-family evidence. |
| Fannkuch-redux | Original N=7 check passed; two safe formulas, both in historical add/shift identity families; image 716 bytes, stack 160 bytes. | Size gate removed, but its candidate formulas are already represented. Do not describe as an independent formula-family test. |

These are **not** new source discoveries. Reconsideration requires a fresh context with the prior result and source exposure disclosed. Use a variable-sized roster and the effective budget `min(requested budget, roster size)`; retain failures, neutral outcomes, and negative outcomes.

## Rejections with substantive blockers

- **No legal candidate under the unchanged relocation guard:** BEEBS `cnt` (its sole expression removes symbolic array relocations), BEEBS bubblesort (sole candidate relocation), PULPino Hanoi (all three candidates remove `%hi/%lo` references to arrays), and BEEBS `strstr` (zero formulas at caps 2–6). The revised policy cannot turn a zero-safe-candidate source into a candidate row.
- **Correctness or defined-behavior concern:** BEEBS `stringsearch1` forms out-of-bounds pointers on its fixed input and its verifier checks only the product of counts; BEEBS `janne_complex` verifies a constant return rather than the computation; MiBench Patricia has no useful expected-output check and its input alone exceeds the data limit; Richards’ small mode fails its reference counters.
- **Memory/runtime/stack:** CoreMark’s standard target link exceeds the 6400-byte program/data allowance by 6360 bytes; TACLeBench `complex_updates` fails the same program/data limit; MiBench qsort needs about 7.32 MiB of automatic storage; GSM input is 21312 bytes and requires file I/O; MiBench FFT and standard MachSuite Viterbi exceed RAM; jsmn’s full test uses a 2048-byte automatic token array plus dynamic allocation; heatshrink’s unchanged suite reaches a 32768-byte VLA and heap buffers.
- **ISA/control/helper coverage:** Richards’ default has `malloc` and function-pointer dispatch; `complex_updates` is a floating-point kernel while the current candidate extractor is integer-only and software-float helper provenance was not retained; prime’s timed path is dominated by linked arithmetic helpers. These are not pool-size rejections.
- **License/family constraints:** MiBench Susan’s notice restricts distribution; MiBench basicmath overlaps consumed integer-square-root work and depends on double math/formatting; MiBench bitcount duplicates the measured TACLeBench population-count algorithms; CHStone `mips` is a bubble-sort program with unclear redistribution rights; heatshrink, FFT, and other suite leads have family overlap noted in the census.

## Superseded or aggregate records

The first TACLeBench Lift rejection was a CFG-analysis limitation for statically resolved non-linking tail transfers. A later, separately versioned analysis accepted the same source with ten candidates; Lift is now consumed evidence, not a fresh lead. Nanocobs likewise has a new v2 variable-pool qualification; the v1 fixed-pool failure remains immutable.

The BEEBS 85-program survey and the MiBench remaining-workload survey are retained as aggregate screens. Their old combined verdicts cannot be read as current blanket rejection under the revised numeric policy. Where saved evidence identifies only a pool/opportunity blocker, reconsider that specific source; where it identifies memory, correctness, relocation, license, or family blockers, those still apply. The inventory avoids inventing per-program counts where source records did not preserve them.

## Next workload to reconsider (independence unproven)

Recommend **TACLeBench countnegative** for the next fresh-policy experiment. It is a 20×20 integer matrix scan with a passed original target checksum, a small recorded image and stack footprint, and four already-derived legal formulas. Its only qualification failure was the removed minimum pool size. That makes it a more useful and safer starting point than the one-candidate prime/insert-sort cases, zero-candidate strstr, or the relocation-heavy MiBench search pool. Two of its four formula families were absent from the historical corpus, but neither that fact nor its new workload-group name proves independence; audit exact families and group lineage before fitting or releasing results.

This inventory performs no new native execution. The next concrete experiment should disclose the previous countnegative screen, bind a fresh variable-pool protocol, and reuse authenticated fixed-input evidence only where the adapter contract permits it.

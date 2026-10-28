**Superseded exploratory diagnostic:** use [archive-only r5](../2026-10-28-candidate-size-coverage-r5/README.md). Earlier runs and failures remain preserved; these are not additional measurements or model versions.

# Baseline-only extraction size coverage

This exploratory replay authenticates only the three baseline-only v2 qualification archives and their zero-candidate-attempt native roots. It does not read candidate selection/outcome archives, fit a model, or run native tools. For each source it replays the signed four-operation discovery, then changes only the in-memory `maxSize` argument passed to the existing extractor to test caps 5 and 6. Existing executable-statement mapping, CFG/dataflow, relocation filtering, latency calibration, lowering verification, memory checks, and public-feature projection remain in force. No benefit or occurrence filter is applied.

## Counts and projected opportunity

| Baseline source | Max operations | Raw formulas | Executable | Relocation-safe and calibrated | Selected pool | Max projected cycle reduction |
|---|---:|---:|---:|---:|---:|---:|
| Countnegative v2 | 4 / 5 / 6 | 5 / 5 / 5 | 4 / 4 / 4 | 4 / 4 / 4 | 4 / 4 / 4 | 0.0561% |
| MiBench stringsearch v2 | 4 / 5 / 6 | 10 / 10 / 10 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 | 0.7388% |
| Nanocobs v2 | 4 / 5 / 6 | 12 / 12 / 12 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 | 0.2517% |

For all three, the cap-4 replay exactly matches the authenticated discovery count and candidate records after excluding only assembly/lowering artifacts already independently checked by the source authenticator. Every native file consumed by the analysis is also checked against its byte hash in the sealed raw archive, so locally resealing a changed profile or discovery file does not substitute for the archived bytes. Caps 5 and 6 yield the same raw, executable, calibrated, relocation-safe formula sets; the largest selected legal formula has three operations.

The report separates total-profile replacements from timed-region replacements. Public cycle-reduction projections use the latter, so out-of-region dynamic occurrences are not counted toward projected benefit. Countnegative's first formula has 2 total-profile occurrences but 1 timed-region occurrence. Stringsearch's leading formula is `add(in0,slli(in1,2))` (581 total and timed-region replacements); its second is `sub(addi(0,1),in0)` (57/57). Nanocobs' leading formula is `addi(lui(16842752),257)` (80,862/80,862); countnegative's is `sub(0,sltu(0,add(in0,in1)))` (2 total, 1 timed).

## Assessment

Increasing the extractor cap from four to five or six does not expand any of these three pools. That does not establish that larger formulas cannot be supported elsewhere; it shows no such opportunity in these already-qualified baseline workloads. A future study looking for broader pools should source a workload with deeper repeated operation sequences, then preserve this exact guarded extraction and calibration pipeline. The figures above are analytic baseline projections, not measured speedups or qualification results.

The machine-readable counts, separate replacement scopes, and source/archive bindings are in [report.json](report.json). Reproduce the offline analysis with:

```sh
.venv/bin/python scripts/analyze_candidate_size_coverage.py --output reports/2026-10-28-candidate-size-coverage-next/report.json
```

The completed r4 report is in `reports/2026-10-28-candidate-size-coverage-r4/`; existing reports are never overwritten.

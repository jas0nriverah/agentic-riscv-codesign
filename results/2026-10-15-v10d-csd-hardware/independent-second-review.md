# V10d second portable review

PASS: all 32 fixed pairs completed, with 64 successful word frontends, 32 universal actual-RTL proofs replayed through the shared reviewed algebra checker, and 64 fresh mapped synthesis arms. The separate portable replay authenticated 343 preparation bindings and 1,137 archived members, checked 137,472 concrete word evaluations and 274,944 raw-source/mapped evaluations, and found no failures. Its complete JSON exactly matches the independently invoked publication audit in `../../docs/figures/v10d-csd-hardware/independent-audit.json`.

The pair file is byte-for-byte identical to frozen V10c (SHA-256 `1b9cc7f0b4100d66cb90d91e6262806ab1cdb1006982d8d7e4406bcd9839885e`). All eight constants appear in all four contexts. All 32 original RTL identities and tool identities match V9, and every fresh original LUT4 and carry count agrees with V9 (zero disagreements). Old V10c evidence remains incomplete at 16 SAT proofs, 16 timeouts and zero area arms; none of those outcomes filtered the new cohort. The last new proof completed at `2026-10-15T21:19:09.559671+00:00`; the global area gate was recorded afterward at `2026-10-15T21:19:09.681621+00:00`, and the replay checked every arm-start sidecar against it.

Across the fixed 32 pairs, original/CSD LUT4 totals are **7,817 / 4,983** (−2,834; 36.2543% aggregate reduction). Thirty-one pairs decrease and one ties; none increases. Mean paired change is −88.5625 LUT4, median −39.5, range −272 to 0. Carry totals are **1,453 / 1,358** (−95); 13 decrease, seven tie, and 12 increase, with paired changes ranging from −29 to +3. The raw primitive totals contain only SB_LUT4 and SB_CARRY. These are sums over separate circuits, not the area of a combined implementation.

The sole LUT4 tie is `44*x + y`: 141→141 LUT4, while carry changes 56→28. The largest LUT4 decreases (−272) occur for coefficient 511 in add-after, sub-before and masked-sub-before contexts. Coefficients 511 and 2044 also have +3 carry changes in direct/sub-before/masked contexts. Thus LUT improvement does not imply every resource improves.

All results use unsigned wrapping 32-bit arithmetic. Universal equality is replayed with the shared formal checker; independent concrete evaluation, source-observation parsing, netlist simulation and resource recount complement that checker. This review supplies no universal mapped-netlist proof, population confidence interval, timing, CPU, or power claim. No native jobs, model fits, targets or frozen-source edits were made during this review.

## All 32 paired resource counts

Each cell is original→CSD LUT4; parentheses give original→CSD carry. Full formulas, identities and prior-V9 comparisons are retained in `independent-second-review.json`.

| Constant | Direct product | Add after product | Sub before product | Masked sub before product |
|---:|---:|---:|---:|---:|
| 11 | 119→92 (29→30) | 176→148 (30→29) | 182→155 (60→61) | 181→154 (60→61) |
| 44 | 111→86 (27→28) | 141→141 (56→28) | 170→145 (56→57) | 169→144 (56→57) |
| 85 | 206→137 (28→27) | 228→200 (29→28) | 247→200 (59→58) | 246→199 (59→58) |
| 340 | 190→127 (26→25) | 220→186 (55→26) | 229→186 (55→54) | 228→185 (55→54) |
| 341 | 219→180 (26→26) | 284→240 (30→28) | 281→243 (57→57) | 281→242 (57→57) |
| 511 | 299→62 (27→30) | 366→94 (30→30) | 389→117 (58→61) | 389→117 (58→61) |
| 1364 | 206→166 (24→24) | 232→222 (53→26) | 260→225 (53→53) | 260→224 (53→53) |
| 2044 | 278→58 (25→28) | 306→90 (54→29) | 362→109 (54→57) | 362→109 (54→57) |

The audit JSON binds preparation SHA-256 `7c3b89e1405f8c999ac7cc95ceeb7f71971e5cd7a94225a9b1b600651c057560`, completion `83676a2f949bad0276160e7d8a82aa2ded2beaf2352c9fe9d47706de7dbf3f3c`, and raw archive `f0e2c4da7098d4be66ed1ddeab39ec375cf433adcaaf759f5b8e324e1564db97`. The frozen auditor and audit-test source hashes remain `78d219f0c3acc0fcfad4e5cd675982979712b068576684aca24d4a385a439bec` and `1e606172d4effe578db94027e0d7cd060dfabc68d0b851f3636b9a183ca30dcb`.

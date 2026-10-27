# MD5 cross-context candidate identity audit — October 26, 2026

The hashed [machine-readable audit amendment v2](../results/2026-10-26-md5-candidate-heldout-prereg/cross-context-identity-audit-v2.json)
is authoritative for the complete context list, all 21 input hashes and the
attempt-membership reconciliation. The original preregistration artifact
manifest is preserved; a separate versioned manifest records its README hash
discrepancy.

**Result:** no literal or declared canonical-alias match was found in 132
candidate identities from 21 public pool/plan artifacts. This includes the
currently inventoried automatic pool set (126 identities across 15 contexts)
and one additional legacy integrated CRC source-adapter pool (six identities
in one context). A bounded attempt-membership reconciliation then confirmed
that all 132 historical `attempt-*` directory identities map to these 16
audited pools; 96 candidate-ledger JSON filenames map in the ten contexts
that have ledgers. All 15 automatic discovery files match their authenticated
pool formulas, all 16 context digests validate, and 15 native plans have
valid SHA sidecars. The older CRC plan has no standalone sidecar, but its
self-digest matches the public prelabel context. No outcome-bearing file
contents were opened. This closes the candidate-identity membership gate for
these 16 declared integrated contexts; it does not establish terminal status
or success. Candidate dispatch remains disabled; new-pool labels remain zero.

The inspected roster SHA256 is
`c4ac398adbd28f3ef975d60a73b0863b20974a794259ed3141050bbc7e60cdd9`.
The checked pools and their SHA256 digests are:

| SHA256 | Public prelabel pool paths (relative to repository root) |
|---|---|
| `82f4f390b67dec29d89b506cd8eb7b5e168f37fc82fa0d2006443c970e339018` | `results/2026-10-20-budget-preregistration/selection/embench-edn/public.json` |
| `a06593911abcb603b5542ceb2c6ff2d9b0889f61b96f088d2dd4cbad9f68a8eb` | `results/2026-10-20-budget-preregistration/selection/embench-ud/public.json` |
| `0ae2a40b71d8943bfb1a8ac86191b7264ea14268a7e9b202c5ca2e6c04bd3f53` | `results/2026-10-20-slre-preregistration/public.json` |
| `2501d74d163d3cbca784624d26da024d7c0f61a3f6fd3024b115e895e0f84886` | `results/2026-10-21-blind-preregistration/targets/beebs-aha-compress/public.json` |
| `9d958b0ae3a97bd21ecfa29e33376ac20d34925e7e92ce11d4f77e2bbc107bb1` | `results/2026-10-21-blind-preregistration/targets/beebs-ndes/public.json` |
| `30e97ee872225aedd1210597bfaef48ac24ecd4d012747f5bc9d8e907f31c53d` | `results/2026-10-21-blind-preregistration/targets/beebs-nettle-md5/public.json` |
| `9a9885edd688787109e7e42a1819e2720e9a8475feb208f895dd5c022108d5fc` | `results/2026-10-21-disjoint-sha256-selection/model/public.json`; `results/2026-10-21-feasible-benefit-preregistration/baseline/public.json`; `results/2026-10-21-feasible-benefit-preregistration/inputs/public.json` |
| `69298295f362ecdafe9f8e75a2b14ed0d9d5fd545ebb6d58e1b98470c1fca7b2` | `results/2026-10-21-jfdctint-preregistration/baseline/public.json`; `results/2026-10-21-jfdctint-preregistration/inputs/public.json` |
| `fe2ccfae4013d5f16c4bddb21c8f52ca9691d6d8d9bef546edb2e996ff7dd51d` | `results/2026-10-21-sha256-preregistration/selection/model/public.json` |
| `4022730317c50f48c9d792df21d3dc4280be68dc942e96b9c9515947a103c0d6` | `results/2026-10-22-bitcount-preregistration/targets/tacle-bitcount/public.json` |
| `1d2cfd2eed55b2453966b252389f111d7c8f7303f4f6b9c9c7ee5170e48f8469` | `results/2026-10-22-live-gp-preregistration/targets/beebs-expint/public.json` |
| `a4b2403e994d94859db269b67f7035fa968f5b028ef2a322386cd2e76c41c0ef` | `results/2026-10-25-g723-preregistration/targets/tacle-g723-enc/public.json` |
| `6e645878bae6ce75407b4869651c88b776b1c657b35d1559b9d583f574fd059e` | `results/2026-10-26-lift-selection-preregistration/targets/tacle-lift/public.json`; matching `targets/tacle-lift/public.json` in preregistration v2, v3 and v4 |
| `b1ee919d4be1b08c8cc1591e58521d4e2bd49bb162ecba784c2b096d5d1f5f21` | `results/2026-10-20-ranking-pilot/public.json` |
| `796167e07bdc413f348c829ca93e60eda87162ca02143d3f57269ff2059197b9` | `results/2026-10-19-codesign/plan.json` |

The original 19 files deduplicated to **114 candidate identities in 13 contexts**:
EDN, UD, SLRE, two SHA256 contexts, DCT, AHA-compress, NDES, historical MD5,
Expint, bitcount, G.723 and Lift. Each roster formula was parsed with the
repository formula grammar. The audit preserved operation nodes, literal
constants and input-sharing structure, recursively sorted children of
`add`, `and`, `or`, `xor`, and `mul`, and repeated the comparison after a
global `in0`/`in1` swap. It compared the lexicographically smaller
serialization. It did not assume associativity, distributivity, or arbitrary
bit-vector equivalence.

The safe supplemental pilot file `results/2026-10-20-ranking-pilot/public.json`
(SHA256 above) adds 12 identities—six each in automatic AHA-mont64
(`1bd107eac10ff77bff15d8903da582a8f03b4db1a1294df085c3fc02642df997`) and
automatic CRC32 (`63c7f40f7e906b046f5a1911d5ed91824bb1aa15673f8fa753a818ccc0d5f511`).
Its producer `selection_pilot.py` projects only the declared public keys
(`candidate_id`, benchmark, formula and discovery features); it contains 12
rows and no labels. The IDs bind to the original MD5 prelabel protocol's
45-element historical-training/excluded-related identity universe. No roster
formula had a literal or declared canonical-alias match in these rows.

The older `results/2026-10-19-codesign/plan.json` (SHA256 above) adds six
public candidate formulas for legacy integrated CRC source-adapter context
`cf16df2e04d6c845c4d990e9355bfe2060a79d71e5a92cc22afc4dedb5373fb2`. The plan
marks them frozen before new labels and derives IDs from `[context, name,
formula]`. No roster formula had a literal or declared canonical-alias match.
This older source-adapter pool is outside the 126-identity automatic campaign
set, so it is reported separately.

**Scope limit:** within the 16 declared integrated contexts, none of the 132
audited candidate identities is a literal or declared canonical alias of a
roster formula, and the attempt-directory identities map to those pools.
Outcome-bearing ledger contents and archives were not read, so terminal
status, correctness and success remain unknown. This does not rule out
arbitrary semantic aliases, cover isolated-area datasets, or certify
unenumerated architectural contexts. Describe this as a bounded 16-context
identity/membership pass, not as a universal equivalence or performance claim.

No candidates were substituted. This audit closes one identity gate but does
not authorize a fit or measurement. The next safe work is to complete the
zero-label model/controller release while retaining the old pool seal as
non-authorizing. Do not expose outcomes to selection or weaken the check.
The [candidate-heldout preflight](md5-candidate-heldout-preflight-2026-10-26.md)
and [offline lowering certificates](../results/2026-10-26-md5-candidate-heldout-prereg/offline-certificates-v1/certificates.json)
remain separate evidence. These results do not authorize model fitting or
measurement.

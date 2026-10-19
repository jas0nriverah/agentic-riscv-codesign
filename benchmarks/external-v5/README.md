# External V5 input fixture

The fixed TACLeBench programs are `dijkstra`, `adpcm_dec`, and `anagram`.
`fetch.json` pins every needed upstream file and commit. Source files are fetched
unchanged into the generated evidence directory. Retain the per-program notices
under `licenses/`; the corpus has no uniform license supplied by this fixture.
The anagram notice requires alterations to be identified: ISAForge adds separate
marker, snapshot and diagnostic wrappers; it does not change upstream files.

`runtime.c` emits output values through Spike HTIF after the measured window.
`wrapper.c` keeps initialization and all checks/output outside that window.
See [the protocol](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/external-v5-protocol.md) for input scopes, correctness
limits, filtering, freezing and the separation from hardware target labeling.

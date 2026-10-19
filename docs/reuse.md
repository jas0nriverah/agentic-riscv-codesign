# Reuse and attribution

ISAForge is a research artifact. A repository-wide license for ISAForge's original code has not yet been selected or added; this documentation cleanup does not assign one. Third-party code and tools retain their own upstream license and attribution notices.

| Component | Recorded source | Use in this project |
| --- | --- | --- |
| Embench | [Pinned source](https://github.com/embench/embench-iot/tree/0466a18e4f6b47e19598d7c6ba72916d54b68f65) | Workload submodule and benchmark code; retain upstream notices |
| PicoRV32 | [Pinned source](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461) | Unmodified processor source retrieved for hardware experiments |
| MasterRTL | [Pinned source](https://github.com/hkust-zhiyao/MasterRTL/tree/5bccf38f8db7bb511a793a709863e7cb1b333ab5) | Published SOG feature recipe and fixed estimator configuration, adapted to LUT4 labels |
| GCC, Spike, Yosys, Verilator, nextpnr | [Toolchain and recorded versions](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/reproduce-research.md#inputs-tools-and-provenance) | External compilation, tracing, verification, synthesis, and routing tools |

The [MasterRTL protocol](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/masterrtl-matched-protocol.md) records the exact reference files, feature weights, and departures from the original implementation. The [related-work comparison](https://github.com/jas0nriverah/agentic-riscv-codesign/blob/b64716a2b94b332fdbced677869620bb949c073d/docs/research-model-comparison.md) links the primary papers. Include those primary references when discussing the corresponding research methods.

When referencing ISAForge results, identify the repository commit and exact experiment snapshot, rather than citing a headline metric without its data split or target. `CITATION.cff` provides repository-level attribution; there is no associated publication DOI or archived release identifier recorded here.

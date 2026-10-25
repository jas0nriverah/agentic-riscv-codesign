# Full-text methods update: Sun journal and Hussein preprint

This update resolves one access gap in the [original method review](research-foundation.md). It does not establish a new ISAForge result or erase the earlier retrieval failures. Primary PDFs were read; archived links preserve institutional/publisher-hosted documents. No copyrighted PDFs are redistributed.

## Sun et al., exact TCAD 2004 article

Fei Sun, Srivaths Ravi, Anand Raghunathan and Niraj K. Jha, *Custom-Instruction Synthesis for Extensible-Processor Platforms*, IEEE TCAD 23(2), February 2004, pp. 216–228, [DOI 10.1109/TCAD.2003.822133](https://doi.org/10.1109/TCAD.2003.822133). The [archived institutional PDF](https://web.archive.org/web/20050316041352id_/http://www.ee.oulu.fi:80/~cavallar/arch_course/papers/03_jha.pdf) is the published thirteen-page journal article: title, volume, issue, page headers and DOI match. This closes the exact-journal-method gap; the separately reviewed 2002 conference paper remains a distinct publication.

Sections IV-A/B.1–3, pp. 219–223, grow basic, dependent and independent templates from profiled control blocks. Dependency-cycle-producing contractions are rejected. Insertion must preserve dependencies; independent statements may be reordered. Candidate priority uses profiled execution share divided by estimated custom latency plus excess-operand transfer overhead. Dynamic thresholds 0.10–0.15 prune candidates, and similar priorities are binned for detailed evaluation.

Sections IV-A/B.2/B.4, pp. 220–225, synthesize shortlisted instructions and execute modified programs in a cycle-accurate ISS. Clock-period/multicycle alternatives affect the objective: normalized execution **time**, including clock changes. Branch-and-bound proposes combinations using additive area/cycle-saving approximations and the maximum clock period; the best k combinations receive joint synthesis to check those approximations. ISAForge must likewise measure selected combinations, never treat additive estimates as final evidence.

Section V uses Xtensa/TIE, an NEC 0.18 μm ASIC library, six benchmarks including PopCount, and a 10% additional-area constraint. Complete runs take under one to over six hours. No learned split, matched attempt-budget comparison, exact experimental k, or public implementation/data artifact was identified.

**Feasible baseline:** name our adaptation explicitly: profiled latency shortlist followed by charged integrated measurement under the same pool, area/timing constraints and attempt budget. This is stronger research grounding for timing-aware merit and eventual joint-set selection. The current single-instruction system does not reproduce Sun's full joint synthesis flow, adjustable-clock exploration, Xtensa state or commercial toolchain.

## Hussein et al.: recovered 2025 v1 is not the 2026 journal article

The exact [TACO 2026 article, DOI 10.1145/3828552](https://doi.org/10.1145/3828552), still requires publisher access verification; no accessible exact journal manuscript was established. Its methods/results remain unverified.

The recovered [archived official preprint](https://web.archive.org/web/20250707084536id_/https://d197for5662m48.cloudfront.net/documents/publicationstatus/258099/preprint_pdf/cec4958d1c0ff92e6deb2687e73ac7c7.pdf) is explicitly *Scalable Custom Instruction Identification using Graph Neural Networks and Reinforcement Learning*, TechRxiv v1, May 12, 2025, [DOI 10.36227/techrxiv.174702136.65195692/v1](https://doi.org/10.36227/techrxiv.174702136.65195692/v1): cover plus twelve manuscript pages, marked unreviewed. Do not attribute its results to the later journal version.

Preprint §§III–IV, manuscript pp. 3–6, use PPO with GIN graph embeddings to grow a subgraph through node/stop actions. Convexity, forbidden operations, I/O and area restrict actions. Merit subtracts hardware critical-path latency from software latency; area sums operator costs. Equation 2 uses software latency of the current subgraph minus hardware latency after expansion. It must not be silently replaced by an incremental-merit reward.

Section V, pp. 7–10, uses normalized operator synthesis costs for 0.13 μm CMOS, I/O limits from 2/1 through 12/6, area fractions 20–100% and an approximately 4,000-second cutoff. Training graphs reach 100 nodes; synthetic tests reach 2,000 nodes with 300 runs per size. Real graphs include SHA, MD5, AES, MPEG2 and two Hadamard kernels. Full RISC-V synthesis integration is future work in this version. PPO episode count, initial learning rate, curriculum thresholds, precise split/seeds and released checkpoints are unspecified; SARSA receives 10,000 episodes. No code/data/checkpoint artifact was identified.

This graph-identification task differs from our budgeted selection of executable candidates using integrated processor measurements. A direct comparison would require matched graph datasets, learned policies, legality/lowering and cost models. A new GNN/RL enumerator remains outside ISAForge's scope. The useful research endpoint remains verified feasible whole-program performance per charged evaluation/time, with historical training costs and true unseen-source evidence. Neither publication makes our current model superior to the field.

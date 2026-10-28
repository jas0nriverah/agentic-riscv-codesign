# ECE 4803 midterm submission materials

Prepared October 27, 2026, for the October 28 progress presentation.

**Version note:** the owner confirmed that the separately supplied 15-page
`AgenticRiscPredictor.pdf` is the current report. The DOCX listed below is a
different draft and must not silently replace it. The current PDF still has
blank AI-methodology and AI-results subsections, unresolved major/email
placeholders, and older setup/results that need explicit historical labeling.
Use the [report-to-evidence crosswalk](../../docs/midterm-report-alignment.md)
to fill those gaps from verified results before submitting.

## Deliverables

- [AI track inserts and presentation notes](ai-track-insert.md) — copy-ready text for the current PDF's empty Sections 2.3/3.3, an evidence-based stopping-point analysis, seven-minute allocation, and Q&A. The supplied PDF remains unchanged; the full deck has now been revised using these evidence qualifications.

- `isaforge-midterm-progress-report.docx` — methodology, AI use, measured results, model evaluation, explainability, chat-agent pilot, timeline, and contribution matrix.
- `isaforge-midterm-progress-slides-final.pptx` — Current, validated 11-slide presentation: research foundations, timeline/contributions, methodology, dataset, XGBoost ranking, explainability/uncertainty, LLM agent, baselines, results, and next steps. Native editable charts and diagrams; speaker scripts total 420 seconds (966 words); deck SHA-256 `858a060ef5ec91dcb12569c734c4ab83eddabbdfab2fd135b37a6eecc3db5839`. The October 28 refresh documents the selector-v2 host incumbent guard, one-shot recovery routing, the four charged failures, and the workload qualification bottleneck. Recovery routing is software-tested only; no live v2 LLM run has occurred.
- `isaforge-xgboost-model-architecture-slide.pptx` — copy-ready standalone replacement slide with a tree-ensemble schematic and the current model details. This is a historical standalone asset; the revised full deck is the presentation deliverable.
- `isaforge-xgboost-model-architecture-slide-preview.png` — 16:9 preview of the standalone slide. Slide text and speaker notes are editable in PowerPoint; the tree illustration is an image.
- `model-architecture-slide.png` — historical architecture preview; not a preview of the revised full deck.
- `dataset/` — CSV data, figure exports, and data dictionary.
- `isaforge-midterm-dataset.zip` — same dataset folder in one portable archive.

Before Canvas upload, confirm the member names, Git author aliases, actual contribution mapping, and contribution shares on the matrix page. Recent Git history provides evidence for two author aliases but cannot confirm identity or capture work outside Git. The proposal role for the third member is shown as planned and still needs confirmation.

## Results and limitations to present accurately

- 122 verified candidate speedup labels and four charged failures across 14 workload groups. Twelve candidate pools have complete oracles; two are censored.
- CRC32 and aha-mont64 six-candidate experiments remain preserved. The best aha-mont64 result is 1.094120×, +42 LUT4, 64.88 MHz minimum routed Fmax, correctness passed.
- Pairwise XGBoost has lower mean regret than merit at budgets 1 and 2, but paired intervals cross zero; merit wins at budget 3. No ML superiority is established.
- The current Codex chat model completed one bounded EDN selector replay and matched the measured-pool oracle after one valid measurement; a malformed ID charged a second attempt. Frequency, merit, XGBoost, and GP controls also match the oracle at the same two-attempt endpoint. This is not a new native measurement or an LLM win.
- A narrow dynamic route can use one stronger-model call after malformed structured output or an explicit host incumbent correction, under a shared call budget. This recovery path has offline tests but no live v2 comparison. Cost-tiered or uncertainty-triggered routing is not implemented. One-to-three-instruction joint selection and validation remains future work.

The slide and dataset artifacts are included in this bundle; the report still
needs the AI-section and placeholder corrections above, and the contribution
matrix needs team confirmation. No Canvas upload was performed.

## Revised 11-slide deck

- `speaker-notes-7-minutes.md` mirrors the embedded scripts, per-slide timings and source/Q&A notes. Rehearse once for handoffs; source notes are not part of the seven-minute script.
- `source/build-slides.mjs` preserves the Artifact Tool authoring source. It requires the bundled `@oai/artifact-tool` runtime and presentation skill paths recorded in the source; set `RUNTIME_NODE_MODULES` to the bundled module directory. The script writes a fresh private build directory and does not automatically overwrite the submitted deck.
- All 11 slides were rendered and visually inspected; native chart/workbook, table, package, layout, and first-party import validation passed. Native PowerPoint opening was not tested.
- Contribution mapping on slide 3 remains provisional and must be team-confirmed.

- [Codex activity and baseline evidence](codex-history-and-baseline.md) documents the scoped log inventory, model screen and initial CRC32 reference; activity durations are not model-training time.

- [How we built ISAForge](how-we-built-isaforge.md) traces early benchmark collection and isolated LUT experiments through processor measurement, dataset creation, model evaluation, and the agent tools, with links to the actual scripts and safe replay commands.

- [Agent architecture and LLMOps plan](agent-architecture-plan.md) distinguishes the working bounded selector and narrow recovery route from proposed cost/uncertainty-based routing, retrieval and production monitoring.

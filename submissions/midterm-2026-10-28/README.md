# ECE 4803 midterm submission materials

Prepared October 27, 2026, for the October 28 progress presentation.

**Version note:** the `AgenticRiscPredictor.pdf` supplied separately on October
27 is a different 15-page report version from the DOCX listed below. That PDF
has blank AI-methodology/results subsections and unresolved major/email
placeholders. Reconcile the intended submission file before upload; see the
[report-to-evidence crosswalk](../../docs/midterm-report-alignment.md). Do not
assume this bundle replaces or corrects the separately supplied PDF.

## Deliverables

- `isaforge-midterm-progress-report.docx` — methodology, AI use, measured results, model evaluation, explainability, chat-agent pilot, timeline, and contribution matrix.
- `isaforge-midterm-progress-slides-final.pptx` — 11-slide, approximately 7-minute editable presentation with a new XGBoost model-architecture diagram, native charts, and tables.
- `isaforge-xgboost-model-architecture-slide.pptx` — copy-ready standalone replacement slide with a tree-ensemble schematic and the current model details. The original full deck remains unchanged.
- `isaforge-xgboost-model-architecture-slide-preview.png` — 16:9 preview of the standalone slide. Slide text and speaker notes are editable in PowerPoint; the tree illustration is an image.
- `model-architecture-slide.png` — preview of the architecture slide already inside the original 11-slide deck.
- `dataset/` — CSV data, figure exports, and data dictionary.
- `isaforge-midterm-dataset.zip` — same dataset folder in one portable archive.

Before Canvas upload, confirm the member names, Git author aliases, actual contribution mapping, and contribution shares on the matrix page. Recent Git history provides evidence for two author aliases but cannot confirm identity or capture work outside Git. The proposal role for the third member is shown as planned and still needs confirmation.

## Results and limitations to present accurately

- 122 verified candidate speedup labels and four charged failures across 14 workload groups. Twelve candidate pools have complete oracles; two are censored.
- CRC32 and aha-mont64 six-candidate experiments remain preserved. The best aha-mont64 result is 1.094120×, +42 LUT4, 64.88 MHz minimum routed Fmax, correctness passed.
- Pairwise XGBoost has lower mean regret than merit at budgets 1 and 2, but paired intervals cross zero; merit wins at budget 3. No ML superiority is established.
- The current Codex chat model completed one bounded EDN selector replay and matched the measured-pool oracle after one valid measurement; a malformed ID charged a second attempt. Frequency, merit, XGBoost, and GP controls also match the oracle at the same two-attempt endpoint. This is not a new native measurement or an LLM win.
- Dynamic LLM routing and cost-tiered model selection are not implemented. One-to-three-instruction joint selection and validation remains future work.

The report and slides are submission-ready aside from the contribution confirmation above. No Canvas upload was performed.

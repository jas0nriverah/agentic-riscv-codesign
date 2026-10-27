# Midterm report and project alignment

Reviewed October 27, 2026 against the 15-page `AgenticRiscPredictor.pdf` supplied in the conversation, the current scope contract, and the committed experiment records.

## Conclusion

The report's central research objective matches ISAForge: discover legal custom-instruction candidates from real workloads, measure whole-program performance and hardware effects, and test whether learned or agent-guided selection can find better feasible designs with fewer evaluations than simple policies. The codebase is on that path. The research result is not complete: neither ML nor the LLM has demonstrated an advantage over merit, and the final compatible instruction set has not been selected and validated jointly.

The original proposal and the [project README](../README.md) define implementation scope. The course report describes a milestone and is useful for presentation, but its early implementation details do not override the repository's verified contracts or later evidence.

## What is working

- The supported pipeline extracts, lowers, executes, checks, and measures real RV32 custom-instruction candidates on the existing PicoRV32 path. The working measured corpus has **122 verified speedup labels, four charged failures, 14 workload groups, and 15 contexts**. Every speedup label in that corpus still matches the calibrated latency estimate; the speedup regressor has no residual signal demonstrated so far.
- Integrated outcomes record whole-program cycles, correctness, LUT4 resources, and routed timing. The standard target uses a 12 MHz timing floor and three route seeds. These are FPGA implementation-flow results, not measurements on fabricated silicon.
- Frequency, merit, random, XGBoost, and non-agent active-learning controls have been evaluated on shared historical pools. The October 27 scorecard keeps pairwise XGBoost as a prospective challenger and merit as the fallback. Pairwise XGBoost's mean-regret point estimates beat merit at budgets one and two, but their paired intervals cross zero; merit leads at budget three. This does not establish ML superiority.
- A four-tool LLM selector interface is implemented. The consumed EDN replay ties frequency, merit, XGBoost, and GP at the same measured-pool oracle; it is not a new hardware evaluation or an LLM win.
- A separate October 27 live Ascon session made three real candidate measurements. C01 achieved 1.019698× at +73 LUT4 / 62.992 MHz and exceeded the +64-LUT4 area budget. C06 achieved 1.017027× at +41 LUT4 / 67.069 MHz. C02 achieved 1.023731× at +42 LUT4 / 64.620 MHz. All three passed correctness. Nine pool candidates remain unmeasured, so there is no complete-pool oracle or matched-policy comparison. Ascon is a same-domain crypto transfer, not an independent workload confirmation. Its successful paid observations exposed a controller status bug; the source fix and post-hoc replay are preserved, but the replay is not prospective evidence that adaptive refitting worked during that run.

The 122-label historical model corpus and the three Ascon target measurements have separate roles. Do not merge the Ascon outcomes into historical training or use its revealed candidate pool for confirmatory comparisons without a new, explicit protocol.

## What remains open

- The report's intended fair comparison still needs an eligible, untouched workload pool with one frozen candidate set and equal information and measurement-count/time budgets for frequency, merit, random, learned policies, non-agent active learning, and the LLM agent.
- Independent workload coverage remains the blocker. Ascon is related to existing crypto pools. Rejections such as CoreMark, Fannkuch, `strstr`, and `complex_updates` must remain preserved; do not relax the support or opportunity gates to manufacture a positive result.
- The final selection of one to three compatible instructions, their program rewrites, and their combined area, timing, correctness, and whole-program performance are not yet validated. Individual speedups, area deltas, or cycle savings must not be added to predict the combined result.
- Dynamic routing across LLMs or cost tiers is not implemented. It is optional future engineering and does not replace the fair selection experiment.
- Team contribution claims cannot be established from code alone. Confirm member names, author aliases, work outside Git, and contribution shares with the team before submitting a matrix.

## Corrections to keep the report accurate

The supplied PDF has placeholders for two members' majors/emails and an empty Section 3.3, “Analyzing the AI-Guided Selection.” Its Section 2.3 is also blank, despite later text saying learned selection methods were tested. These are presentation defects; fill the methodology/results sections from the measured evidence and replace placeholders before using that PDF as the final submission.

The PDF describes an earlier eight-Embench, separate-track setup and reports a 2,439-LUT / 61.5-MHz baseline. Later guarded experiments use different compiler, firmware, memory, and hardware configurations. Keep those rows labeled as historical context; do not pool or compare them as though they share one processor configuration. Likewise, “each new measurement becomes training data” is too broad: frozen XGBoost policies do not refit after every paid query, and the Ascon adaptive-GP run did not successfully incorporate paid observations until after the defect was fixed and replayed.

The PDF's statement that individual cycle savings add exactly is not a final-set validation rule. The current project contract requires selected instructions to be implemented and measured together because overlap, shared logic, timing, and processor interactions can change the result.

The PDF supplied in chat is materially different from the repository's `submissions/midterm-2026-10-28/isaforge-midterm-progress-report.docx`. The repository version contains a completed model-results section and explicit claim limitations, but it predates the Ascon paid run described above. Treat them as separate versions and reconcile the intended submission file before presenting.

## Next work in scope

1. Qualify an untouched workload under the existing architecture, source, memory, candidate-opportunity, and correctness gates. Keep every rejection and its raw evidence.
2. Before target outcomes are visible, freeze the candidate pool, related-family exclusions, training data, model, policy implementations, prompts/tools, seeds, budgets, and evaluation environment.
3. Run all selection methods against the same information and pool. Report the best verified feasible whole-program performance versus evaluation count and actual elapsed evaluation time, with oracle regret only when the pool oracle is complete.
4. After selection works on a fresh workload, implement the chosen one-to-three-instruction set together and validate the complete modified workload and integrated processor.

Until those experiments exist, present the results as a working research prototype with valuable positive and negative measurements, not as a completed optimization agent or an ML win.

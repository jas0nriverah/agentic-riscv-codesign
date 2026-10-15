# Research direction: transfer and measurement budgets

This note extends the [October 14 review](research-update-2026-10-14.md). It does not change the frozen V8 application protocol, models, features, endpoints or measurement budget.

## A useful 2026 comparison: MARU

The authors' extended MARU paper predicts **ASIC-equivalent area from FPGA resource reports**, including LUT, FF, DSP and BRAM counts. These inputs are later-stage information than our pre-mapping features, and the target is not iCE40 LUT4 count. Its headline error is therefore not a directly comparable ISAForge score. [Author-hosted paper](https://lca.ece.utexas.edu/pubs/kholay_arc26.pdf).

The distinction between direct transfer and adaptation is consequential. Table 6 reports mean MAPE **45.54% without adaptation versus 2.73% after using 20% of each target benchmark**. Table 8 reports **20.15% versus 1.71%** in leave-one-benchmark-out experiments, with adaptation using **50% of the held-out benchmark**. Table 9 instead studies cross-FPGA transfer and reports **4.96% versus 4.01%**, using 20% target-platform data. These are separate tasks and labeling budgets. [Sections 4.2–4.5](https://lca.ece.utexas.edu/pubs/kholay_arc26.pdf).

Our inference from these results: data coverage and explicitly budgeted adaptation deserve priority alongside representation changes. Low error after receiving target labels is a different achievement from predicting an untouched application.

## Consequences for ISAForge

1. Finish V8 as declared: both new fits use the original 1,665 training circuits; all application predictions precede fresh target measurement. Keep that untouched-transfer result even if it is negative.
2. Diagnose whether failures are concentrated in arithmetic operators, target-size ranges, missing training support, normalization fallbacks or threshold decisions. Treat these as consumed-test diagnostics, not a second independent success claim.
3. If adaptation is warranted, declare a separate development experiment with fixed measurement budgets. Charge every revealed target to that budget, compare against merit, random sampling and a frozen-model policy, and evaluate only unqueried cases. Formulas and related-source variants must stay grouped.
4. Select a future method using consumed data, freeze it, then evaluate it on newly reserved source families. Reusing V8 for tuning makes it development evidence thereafter.
5. Report the practical objective: quality of the chosen verified instruction per measurement cost, with processor integration as a separate endpoint. A lower area-prediction error does not establish lower CPU latency.

The next research claim should be tied to a matched target, dataset boundary and information budget. This avoids chasing a published percentage obtained with a different amount of synthesis information.


## Further evidence for targeted data coverage

The expanded **MasterRTL journal paper (2025)** evaluates generated training RTL as well as its original prediction framework. Its augmentation study adds 45 designs (30 graph-generated and 15 LLM-generated) and examines TNS transfer and path-level slack, not our small-circuit LUT4 task. The authors report stronger gains from graph generation than LLM generation and improved results from combining sources, particularly with fewer real training designs. They emphasize synthesizability, diversity and resemblance to real design structure. This supports testing representative training compositions; it does not establish that arbitrary synthetic circuits improve area prediction. [Author-hosted paper, Sections II-F and III-F, Figure 14](https://zhiyaoxie.com/files/TCAD25_MasterRTL.pdf).

A **2025 TinyML resource estimator** builds constant-specific multiplication resource tables and models dense-layer composition. On PYNQ-Z2, it reports 0.82% average LUT RRMSE for randomized dense-layer experiments with generic multiplication implemented in LUTs, but 27% for the smallest evaluated full MLP; omitted activation costs become proportionally important there. RRMSE is not MAPE, and this is a specialized hls4ml/Xilinx task. Our inference is that primitive coverage and composition costs deserve explicit tests, especially for small circuits where one missing operation matters. [Paper, Sections 3–4](https://mdpi-res.com/d_attachment/electronics/electronics-14-00247/article_deploy/electronics-14-00247.pdf?version=1736402512).

Accordingly, V9 separates two questions: a fixed paid-label residual correction, and a 48-circuit coverage augmentation with the existing mapping217 features and ET300 learner. Both use consumed applications for development; a later untouched source-family evaluation is required.

# Python research package

The public command-line entry point is `isaforge`; measured-study modules also expose `python -m isaforge.<module>` commands. See the [repository quick start](../README.md#reproduce-the-comparison) and [documentation index](../docs/README.md).

| Responsibility | Modules |
| --- | --- |
| Formula semantics and measured circuits | `features`, `rtl`, `synthesis`, `real_experiment`, `probe_corpus` |
| Frozen hardware-cost predictors | `area_model`, `area_model_v2`, `area_model_v3`, `structural_features_v3`, `masterrtl_baseline` |
| Inference, validation, and audit | `frozen_inference`, `evaluation`, `fresh_evaluation`, `probe_evaluation`, `probe_audit` |
| Candidate selection | `area_selection`, `selection`, `conservative_policy` |
| Processor and FPGA experiments | `core_experiment`, `core_routing`, `soc_experiment` |
| Research reports and figures | `challenger_plots`, `challenger_report`, `research_report`, `midterm_report` |
| General interface and exploratory demo | `cli`, `dataset`, `model`, `demo`, `deployment` |

The generic demo's synthetic performance labels are distinct from the measured LUT4 pipeline. Versioned model modules remain separate because serialized artifacts hash their exact runtime sources. The [`results/`](../results/README.md) directory binds those versions to training cohorts and evaluation stages. Do not refactor frozen modules in place while retaining their original artifact/evaluation claims; see [contribution conventions](../CONTRIBUTING.md).

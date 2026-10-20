# Python research package

The public command-line entry point is `isaforge`; measured-study modules also expose `python -m isaforge.<module>` commands. See the [repository quick start](../README.md#run-and-reproduce) and [documentation index](../docs/README.md).

| Responsibility | Modules |
| --- | --- |
| Current automatic workload pipeline | `assembly_lowering`, `workload_experiment`, `workload_audit`, `workload_selection` |
| Preserved measured speedup selection | `codesign`, `codesign_audit`, `speedup_corpus`, `model`, `selection` |
| Formula semantics and measured circuits | `features`, `rtl`, `synthesis`, `real_experiment`, `probe_corpus` |
| Frozen hardware-cost predictors | `area_model`, `area_model_v2`, `area_model_v3`, `structural_features_v3`, `masterrtl_baseline` |
| Inference, validation, and audit | `frozen_inference`, `evaluation`, `fresh_evaluation`, `probe_evaluation`, `probe_audit` |
| Candidate selection | `area_selection`, `selection`, `conservative_policy` |
| Processor and FPGA experiments | `core_experiment`, `core_routing`, `soc_experiment` |
| Research reports and figures | `challenger_plots`, `challenger_report`, `research_report`, `midterm_report` |
| General interface and exploratory demo | `cli`, `dataset`, `model`, `demo`, `deployment` |

The active project contract is [README.md](../README.md). Versioned area models and rewrite experiments support historical reproduction, not new project priorities. The retired RTL-search controller is a text snapshot under `archive/`.

The generic demo's synthetic labels are distinct from both measured application speedup and the historical LUT4 pipeline. Versioned model modules remain separate because serialized artifacts hash their exact runtime sources. The [`results/`](../results/README.md) directory binds those versions to training cohorts and evaluation stages. Do not refactor frozen modules in place while retaining their original artifact/evaluation claims; see [contribution conventions](../CONTRIBUTING.md).

# Workload collection and tracing

These are the hardware-facing collection programs. They are separate from the installable [`isaforge/`](../isaforge/) learning and evaluation package.

| File | Role |
| --- | --- |
| `tracing.py` | Parse Spike commit logs into instruction records |
| `candidates.py` | Extract bounded computation graphs and occurrence information |
| `verify_candidate_fusions.py` | Verify candidate fusion semantics and evidence |
| `run_real_benchmarks.py` | Collect the original eight-workload pilot |
| `run_holdout_benchmarks.py` | Collect declared prospective workload groups with pinned inputs |
| `spike-setup/` | Bare-metal startup and memory layout used for tracing |

The root Makefile retains the original eight-program build/trace targets. Full 19-program collection is documented in the [research reproduction guide](../docs/reproduce-research.md). Script paths are preserved because existing commands and evidence manifests refer to them.

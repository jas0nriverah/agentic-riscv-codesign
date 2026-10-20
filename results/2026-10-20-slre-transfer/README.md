# Prospective SLRE transfer checkpoint

The third real workload is complete: six automatically extracted/lowered candidates, seven verified processor designs, 21 routes, 90 frozen prediction rows, and 105 policy/budget/seed replay endpoints. The [full results guide](../../docs/prospective-slre.md) contains every candidate's cycles, resources, timing, correctness, selection outcome, costs, limitations, and collection commands.

The best instruction reduces 16,333,432 to 16,221,562 cycles (1.006896×) with +77 integrated LUT4. Frequency, merit, and independently calibrated latency find it in one evaluation. All learned policies rank it fifth and miss it through budget three. The execution-feature ablation reduces MAE 21.14% but does not improve selection; both ensembles have zero interval coverage on this workload in every seed. The latency baseline predicts all six new cycle deltas exactly.

## Evidence

| Artifact | Contents |
| --- | --- |
| [Prelabel checkpoint](../2026-10-20-slre-preregistration/README.md) | Pushed commit `1c812e1c6c09070ae45931241c37163d53ee05ee` before target candidate measurement; unchanged predictions, baseline, and receipt prefix |
| [Protocol](protocol.json), [public candidates](public.json), [predictions](predictions.json) | Source/package identities, two-workload training support, fixed settings, context shift, constraints and budgets |
| [Raw archive](raw.tar.gz) | Complete successful SLRE evidence excluding simulator build directories |
| [Failed partition archive](failed-partition.tar.gz) | First failed image-packing attempt, original source snapshot, receipts and failure; no performance labels |
| [Archive manifest](archive-manifest.json) | Every archive/member hash, size, and path |
| [Processor audit](audit.json) | Re-extraction/lowering, raw execution/resource/route checks, memory checks and negative controls |
| [Selection report](report.json) | 35 policy/seed runs, three budgets each, oracle, regret, uncertainty and historical/inference costs |
| [Prediction refit](prediction-replay.json) | Exact replay of all 90 predictions, using only historical labels; only fit/inference timers excluded from equality |
| [Chronology](preregistration-check.json) | Frozen manifest identity and exact 31-receipt prefix of 133 final commands |
| [Costs](measurement-costs.json) | 149 native commands including the failed attempt, 288.697 command-seconds; overlapping evaluation-wall timers kept separate |
| [Sources](source-manifest.json), [environment](environment.json), [manifest](manifest.json) | Immutable source copies and authenticated checkpoint files |

## Replay

```sh
# Python 3.12 and requirements-speedup.txt
make reproduce-prospective PYTHON=python
make demo PYTHON=python
sqlite3 -header -column generated/reproduction/prospective-slre/experiments.sqlite < docs/experiment-queries.sql
```

Replay restores this archive and the two historical automatic archives, authenticates raw evidence, refits the unchanged historical models exactly, and reproduces all decisions. No hardware tools or new native measurements are invoked. `make demo` adds a typed SQLite analysis projection and offline HTML. A presentation-only stylesheet wrapper keeps cycle counts and correctness columns readable; the frozen renderer and scientific content are unchanged.

This is one prospective workload with an explicit `-Os`/memory-partition shift, not broad generalization. Five seeds share the same labels. The oracle covers six rank-stratified candidates from 16 eligible formulas, all positive and feasible. Simulation/routing are not physical-board measurements. Partition observation is limited to the recorded inputs. No active-learning/LLM agent or joint instruction-set result is claimed here.

This explanatory README was added after sealing the scientific checkpoint and is outside `manifest.json`. Preserve every manifest-bound file and hash-bound source. [Validation](../2026-10-20-slre-validation/README.md) preserves the complete suite and reproduction logs.

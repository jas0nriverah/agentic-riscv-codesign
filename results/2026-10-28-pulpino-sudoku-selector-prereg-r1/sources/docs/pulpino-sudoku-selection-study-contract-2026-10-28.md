# PULPino Sudoku selection study contract — 2026-10-28

## Research question

Can a model-guided, tool-using selector find a correctness-verified, area- and
timing-feasible custom instruction that improves whole-program performance
with fewer measured candidates than frequency, merit, random, and non-agent
active-learning policies? This is a prospective transfer pilot. It cannot by
itself establish broad generalization, agent superiority, or improvement over
published research.

## Frozen workload and baseline

The target is one fixed 9×9 Sudoku input from pinned PULPino source. The adapter
executes it twice per timed benchmark and checks all 81 cells against the
upstream oracle. This is a fixed-input correctness claim, not arbitrary-input
verification. The target is RV32I/Zicsr on the existing PicoRV32/PCPI toolchain.

The qualification uses the existing 8 KiB RAM with a predeclared 2,304-byte
program region and 5,760-byte stack region. The measured run reached a 3,968-byte
stack high-water mark (1,792 bytes headroom), with zero stack or guard violations.
The baseline completed correctly in 1,024,889 cycles and 198,711 instructions.
Its synthesized design used 1,653 LUT4, 295 carry cells, 655 flip-flops, and 20
BRAMs. Three routes reported minimum Fmax values of 77.16, 68.49, and 70.39 MHz
against a 12 MHz constraint. These are baseline measurements, not candidate
speedups. This stack partition differs from the earlier tiny-regex experiment;
the result is specific to this declared memory partition and fixed input.

The frozen pool contains 12 automatically discovered and executable individual
instruction candidates. It is the existing extractor's shortlist, not an
exhaustive set of all legal instructions. Before candidate measurements, the
qualification reported a best public analytic estimate of about 4.54% cycle
savings. That estimate is an opportunity-screen feature, **not measured speedup**.

## Data and frozen models

The historical dataset contains 122 successful measured candidate labels and
four failed attempts across 14 workload groups. Before fitting, the protocol
excludes the target source and every exact ordered operator-tree family found
in the target pool. This removes 16 historical successful rows and leaves 106
rows from 14 workload groups. The Sudoku candidate labels are not used for
fitting, ranking, memory retrieval, or prompt context before the agent's own
paid measurements.

The frozen controls reuse the existing models and heuristics:

- Pairwise XGBoost (`rank:pairwise`) predicts a relative candidate ordering from
  historical whole-program measured speedup orderings. Its score is not a
  calibrated speedup magnitude.
- A 20-member XGBoost feasibility ensemble estimates hardware feasibility.
  Its probabilities are uncalibrated. The factorized utility multiplies that
  estimate by public analytic cycle savings; it is not a direct learned
  whole-program speedup model.
- Frequency, merit, latency/cost-aware, random, and the frozen active-learning
  and regression controls provide non-agent comparisons. Their model and
  hyperparameters are fixed before target candidate labels exist.
- Five fixed model seeds quantify algorithm-run variation on this one pool.
  They are not five independent workload replicates.

No new model is promoted in this study. Earlier diagnosis showed that AST-path
features reduce historical held-out feasibility error but worsen selection at
measurement budgets one and two; merit remains stronger at budget three. Keep
that challenger result as a negative model-selection finding.

## Agent, tools, memory, and AI operations

One current Codex chat model interacts through a local structured-JSON relay.
The host exposes four bounded tools: `list_candidates`, `predict`, `measure`,
and `finalize`. It validates schemas, candidate identities, correctness,
resource limits, and the one-to-three measurement budget. The selector sees
public candidate features and frozen predictions, then receives only outcomes
from measurements it requested. It may stop and choose baseline at any point.
The human relays structured actions; the host enforces the safety and budget
rules. This is a human-in-the-loop relay, not an unattended isolated API agent.

The one frozen agent episode uses bounded hybrid retrieval over the same 106
training rows: TF-IDF lexical similarity plus truncated-SVD latent similarity,
combined by reciprocal-rank fusion. Retrieval has a three-record and 40,000-byte
limit. Target outcomes are never written to historical memory. Typed knowledge
graph support exists in the codebase but is **not queried** in this episode.
The configured Responses API route can support provider escalation, but this
episode uses one current Codex relay; dynamic cross-provider routing is not
evaluated here. There is no LLM fine-tuning, LangGraph/LangChain orchestration,
RAG evaluation suite, or LLM-as-a-judge claim in this experiment.

The host seals structured requests, action traces, model/tool call counts,
retrieval IDs and source hashes, pre-measure context hashes, attempt outcomes,
and the agent's decision rationale. A SQLite observability database is a
read-only, reproducible projection; sealed JSON is authoritative. Exact chat
model ID, token usage, and model-only latency are unavailable through the
current relay. The rationale is recorded for audit; it is not treated as proof
that the LLM's explanation caused its decision.

## Evaluation protocol

Primary constraint: at most 64 additional LUT4, routed Fmax at least 12 MHz on
all three route seeds, and at most three paid candidate measurements. Budgets
one, two, and three are reported. The agent runs first on zero target labels.
Only after it finalizes are remaining candidates measured once to create a
complete pool and measured oracle. Then fixed non-agent policies are replayed
with one-at-a-time outcome release and only their own paid prefixes.

This means the full physical dataset build costs up to 12 candidate evaluations.
The replay curves estimate what each policy would select from that pool at a
smaller budget; they do **not** mean those policy outcomes were physically
measured at that lower cost. Report both total data-collection cost and each
policy's charged prefix cost. If any result is infrastructure-censored, oracle
regret is unavailable. A failed or incorrect candidate is not a speedup.

Report whole-program cycles, speedup, cycle reduction, correctness, LUT4 delta,
all-route Fmax, device fit, paid attempts, measured evaluation time, model fit
and inference time, agent tool/provider calls, decision latency, and regret to
the complete measured feasible-pool oracle. A feasible selected candidate must
beat baseline and satisfy the full correctness, area, and timing gate. Report
combined instruction sets only after measuring their integrated combinations;
never add single-instruction speedups as if they were additive.

## Frozen workflow

```sh
python3 scripts/build_pulpino_sudoku_adapter.py --check
python3 -m pytest -q tests/test_pulpino_sudoku_workload.py
python3 scripts/qualify_pulpino_sudoku.py
python3 scripts/prepare_pulpino_sudoku_selector.py freeze
python3 scripts/prepare_pulpino_sudoku_selector.py verify
python3 scripts/execute_pulpino_sudoku_selector.py release
python3 scripts/execute_pulpino_sudoku_selector.py agent
python3 scripts/execute_pulpino_sudoku_selector.py collect
python3 scripts/execute_pulpino_sudoku_selector.py evaluate
python3 scripts/execute_pulpino_sudoku_selector.py verify
```

`release` must verify that the frozen prelabel commit is the exact local and
pushed `ai-guided-ml` head, and must confirm zero target attempts before the
agent starts. Preserve qualification, source hashes, raw evidence archive,
selection transcript, model package/version hashes, protocol, costs, and
failures. A source or protocol change after preregistration requires a new
study root; never overwrite the sealed run.

## Interpretation limits

This test contains one fixed workload, one agent episode, one 12-candidate
shortlist, and a historical corpus with 14 workload groups. It tests one
prospective transfer and a carefully controlled selector loop, not arbitrary
RISC-V support or broad statistical superiority. The LLM is a decision policy
around ML scores and real measurement tools; it is not the speedup predictor.
Do not claim the ML model or agent beats heuristics or published methods unless
the prospective measured results support that exact claim.

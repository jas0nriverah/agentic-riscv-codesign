# One six-field semantic GP development hypothesis

All nine initial models/predictions were sealed before any target scoring. The sole representation change appends the fixed six fields to the duration-free adaptive GP. All13 earlier controls remain unchanged. Nine cached cohort/source cases, five dependent seeds, caps32/64/128, budgets1/2/3. Expanded history already contains consumed other-source labels; no newly scored outcomes cross cases.

| Case | Comparator | Semantic gain% | Control gain% | Difference pp | Result |
| --- | --- | --- | --- | --- | --- |
| old__beebs-aha-compress | hybrid_gp_adapt_count | 2.288232552 | 2.288232552 | 0.000000000 | tie |
| old__beebs-aha-compress | hybrid_gp_adapt | 2.288232552 | 2.288232552 | 0.000000000 | tie |
| old__beebs-aha-compress | hybrid_gp_zero_shot | 2.288232552 | 2.288232552 | 0.000000000 | tie |
| old__beebs-aha-compress | merit | 2.288232552 | 0.915293021 | 1.372939531 | win |
| old__beebs-ndes | hybrid_gp_adapt_count | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-ndes | hybrid_gp_adapt | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-ndes | hybrid_gp_zero_shot | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-ndes | merit | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-nettle-md5 | hybrid_gp_adapt_count | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-nettle-md5 | hybrid_gp_adapt | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-nettle-md5 | hybrid_gp_zero_shot | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-nettle-md5 | merit | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-jfdctint | hybrid_gp_adapt_count | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| old__beebs-jfdctint | hybrid_gp_adapt | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| old__beebs-jfdctint | hybrid_gp_zero_shot | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| old__beebs-jfdctint | merit | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-aha-compress | hybrid_gp_adapt_count | 2.288232552 | 0.000000000 | 2.288232552 | win |
| expanded__beebs-aha-compress | hybrid_gp_adapt | 2.288232552 | 0.000000000 | 2.288232552 | win |
| expanded__beebs-aha-compress | hybrid_gp_zero_shot | 2.288232552 | 0.915293021 | 1.372939531 | win |
| expanded__beebs-aha-compress | merit | 2.288232552 | 0.915293021 | 1.372939531 | win |
| expanded__beebs-ndes | hybrid_gp_adapt_count | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-ndes | hybrid_gp_adapt | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-ndes | hybrid_gp_zero_shot | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-ndes | merit | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | hybrid_gp_adapt_count | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | hybrid_gp_adapt | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | hybrid_gp_zero_shot | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | merit | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-jfdctint | hybrid_gp_adapt_count | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-jfdctint | hybrid_gp_adapt | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-jfdctint | hybrid_gp_zero_shot | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-jfdctint | merit | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| fresh__beebs-expint | hybrid_gp_adapt_count | 0.034544484 | 0.034544484 | 0.000000000 | tie |
| fresh__beebs-expint | hybrid_gp_adapt | 0.034544484 | 0.034544484 | 0.000000000 | tie |
| fresh__beebs-expint | hybrid_gp_zero_shot | 0.034544484 | 0.034544484 | 0.000000000 | tie |
| fresh__beebs-expint | merit | 0.034544484 | 0.034544484 | 0.000000000 | tie |

Query-three comparisons over27 cohort/source/cap means: {'hybrid_gp_adapt_count': {'tie': 26, 'win': 1}, 'hybrid_gp_adapt': {'tie': 26, 'win': 1}, 'hybrid_gp_zero_shot': {'tie': 26, 'win': 1}, 'merit': {'tie': 23, 'win': 2, 'loss': 2}}. Early mean comparisons versus count-only: {'1': {'tie': 27}, '2': {'tie': 26, 'win': 1}}. All caps, budgets, source macros and regressions are retained in CSV/JSON. Old/expanded AHA/NDES/MD5 macros remain separate; DCT and Expint remain separate.

NDES operation orientation is now distinguishable, but this does not guarantee correct synthesis costs or calibrated GP probabilities. Both constant DCT expressions still have the identical six-field block despite different integrated costs; their original constant feature remains. The earlier45-descriptor negative result remains bound and unmodified. Area Brier/error/false-feasible diagnostics are secondary, not confidence guarantees.

All90 prior native attempts, including3 failures, remain charged once globally in costs. No new native measurements occur. Nine initial surrogate fits (27 scalar GPs) and paid-success update fits are new host work. Their raw monotonic timers are retained separately; counterfactual policy native costs overlap, and historical clock qualifications remain. No automatic stopping, uninterrupted wall-time or total-cost advantage is established.

This is one fixed consumed-data representation experiment, not a feature sweep or an untouched-source result. No learner is promoted. Replay with `python scripts/evaluate_semantic_selection.py replay --root results/2026-10-22-semantic-selection-development --output generated/reproduction/semantic-selection` using a fresh output. Only explicitly named host timing fields may differ.

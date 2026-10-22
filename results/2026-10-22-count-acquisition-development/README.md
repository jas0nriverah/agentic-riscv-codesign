# One duration-removal adaptive-GP development ablation

Nine archived cohort/source cases, five dependent seeds, caps32/64/128 and budgets1/2/3. One new adaptive policy removes solely inverse duration. All12 controls, initial predictions, fitting cohorts, Gaussian feasibility, public speedup-improvement units and successful-paid update rules remain unchanged. All inputs/predictions were sealed before scoring; each dynamic acquisition prediction was sealed before its outcome provider released a label.

| Case | Comparator | Count gain% | Control gain% | Difference pp | Result |
| --- | --- | --- | --- | --- | --- |
| old__beebs-aha-compress | hybrid_gp_adapt | 2.288232552 | 2.288232552 | 0.000000000 | tie |
| old__beebs-aha-compress | hybrid_gp_zero_shot | 2.288232552 | 2.288232552 | 0.000000000 | tie |
| old__beebs-aha-compress | merit | 2.288232552 | 0.915293021 | 1.372939531 | win |
| old__beebs-ndes | hybrid_gp_adapt | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-ndes | hybrid_gp_zero_shot | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-ndes | merit | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| old__beebs-nettle-md5 | hybrid_gp_adapt | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-nettle-md5 | hybrid_gp_zero_shot | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-nettle-md5 | merit | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| old__beebs-jfdctint | hybrid_gp_adapt | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| old__beebs-jfdctint | hybrid_gp_zero_shot | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| old__beebs-jfdctint | merit | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-aha-compress | hybrid_gp_adapt | 0.000000000 | 0.000000000 | 0.000000000 | tie |
| expanded__beebs-aha-compress | hybrid_gp_zero_shot | 0.000000000 | 0.915293021 | -0.915293021 | loss |
| expanded__beebs-aha-compress | merit | 0.000000000 | 0.915293021 | -0.915293021 | loss |
| expanded__beebs-ndes | hybrid_gp_adapt | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-ndes | hybrid_gp_zero_shot | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-ndes | merit | 0.709537394 | 0.709537394 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | hybrid_gp_adapt | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | hybrid_gp_zero_shot | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-nettle-md5 | merit | 1.808785530 | 1.808785530 | 0.000000000 | tie |
| expanded__beebs-jfdctint | hybrid_gp_adapt | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-jfdctint | hybrid_gp_zero_shot | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| expanded__beebs-jfdctint | merit | 0.490120999 | 0.490120999 | 0.000000000 | tie |
| fresh__beebs-expint | hybrid_gp_adapt | 0.034544484 | 0.034544484 | 0.000000000 | tie |
| fresh__beebs-expint | hybrid_gp_zero_shot | 0.034544484 | 0.034544484 | 0.000000000 | tie |
| fresh__beebs-expint | merit | 0.034544484 | 0.034544484 | 0.000000000 | tie |

First-query paired outcomes over135 dependent case/cap/seed entries: {'tie': 130, 'win': 5}. Query-three mean comparisons over27 cohort/source/cap endpoints: {'hybrid_gp_adapt': {'tie': 27}, 'hybrid_gp_zero_shot': {'tie': 26, 'loss': 1}, 'merit': {'tie': 23, 'win': 1, 'loss': 3}}. Allcaps/budgets and every regression remain in CSV/JSON; source macros treat old/expanded AHA/NDES/MD5 separately. DCT and consumed Expint remain separate regression cases. These counts are descriptive, not independent-source significance.

Semantic representation is still unresolved: removing a duration factor cannot distinguish the demonstrated NDES hardware-feature alias, repair constant semantics or add missing timing/device failure classes. The consumed first-query diagnosis justified this single ablation; full-trajectory regressions must be retained and no policy is promoted. Expint’s entire pool has only11 saved cycles /31843baseline cycles of headroom.

All90 earlier native attempts, including3 failures, remain uniquely charged once at5098.832466 recorded seconds. Only paid GP update fits and host replay are newly executed. Ledger/native/CLI/observer/qualification scopes overlap; historical clock qualifications are preserved. No uninterrupted elapsed-wall-time, broad generalization, calibrated confidence or total-cost advantage is established.

Replay with `python scripts/evaluate_count_acquisition.py replay --root results/2026-10-22-count-acquisition-development --output generated/reproduction/count-acquisition`. Use a fresh output. Exact acquisition predictions, paid choices, numerical curves, all controls and all non-host-timing results must reproduce.

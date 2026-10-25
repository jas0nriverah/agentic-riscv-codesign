# Next bounded surrogate experiment: historical-data ARD area GP

This procedure is declared before fitting it to real cohorts or scoring it. It does not change the frozen seventeen-policy G.723 campaign. That target is excluded from this development experiment, including its outcomes and future exported corpus.

The fixed-joint experiment finds no lookahead advantage at any of thirty query-three case/cap means. Bitcount still returns baseline after three over-budget designs; the heuristic fallback repairs it but regresses DES. The preceding covariance diagnosis shows almost independent predictions for related candidates. These are selection failures that justify testing the surrogate itself.

[Zhang, Zhang and Frazier, NeurIPS 2021, §5.1](https://papers.nips.cc/paper_files/paper/2021/file/685217557383cd194b4f10ae4b39eebf-Paper.pdf) fits ARD squared-exponential GP hyperparameters by marginal likelihood. We adapt that established fitting procedure to the area constraint. The paper's continuous, noise-free problems, initialization, recommendation endpoint and GPy implementation differ from ours. This is not a faithful full-paper reproduction, a new kernel or a novelty claim.

## Fixed procedure

- Keep all 37 semantic features, cached fitting rows, source/family exclusions, calibrated benefit, timing/duration models, device model, paid Gaussian update and acquisition unchanged. Change only the area-surrogate procedure; this combines a kernel and fitting change and cannot isolate either individually.
- Use `ConstantKernel * RBF` with one ARD length scale per feature. In normalized units, variance bounds are [0.01, 100] and length-scale bounds [0.1, 100]. Preserve initial historical input/output normalization and assumed observation variance `alpha=1e-4`; this is not calibrated measurement noise.
- Fit three deterministic starts: variance 1, with all length scales respectively 1, sqrt(37) and 10. Use analytic-gradient L-BFGS-B with maxiter 200, maxfun 1000, ftol 1e-9 and gtol 1e-5. Select the finite smallest negative historical log marginal likelihood; earlier start wins ties. Retain every status, exception, warning, boundary hit and evaluation count. A finite iterate may be used after a limit with explicit nonconvergence; fail if none is finite. No target-performance tuning or adaptive restarts.
- Freeze the selected parameters during paid queries. Real and hypothetical observations use the same existing immutable joint conditioner. A new initializer schema must identify the changed area model and bind its source, numerical state and private coupling to the frozen adapter. It must not impersonate the original semantic fit.
- Count the original semantic fit's three scalar GPs, including its unused area GP, and all three ARD fit attempts. Separate initial preparation, authentication rebuilds, optimization, acquisition and conditioning costs; preserve raw nondeterministic host timers separately from deterministic model proofs.

## Comparison and decision

Use exactly the ten cached development cases and seventeen completed controls. Seal all initial models and fixed normal tables before parsing outcomes. The only new selector is the existing myopic acquisition using the new area model. Execute planned budgets 1/2/3 independently at +32/+64/+128 LUT4, 12 MHz, seeds 0–4: 450 trajectories / 900 curve points. Preserve B3 prefixes separately from horizon-aware terminal endpoints.

Primary outcome remains verified feasible cycle reduction and measured-pool regret at +64 / B3. Compare every case against the cost heuristic, original fixed-joint myopic model and strongest existing control. Keep old/expanded AHA/NDES/MD5 macros separate and the other source cases explicit. Ten cases are six consumed sources; seeds, contexts and horizons are dependent. Prediction error is secondary. No development result establishes calibration, promotion or field superiority.

The original 102 historical attempts remain charged once for these frozen cohorts. G.723 measurements belong to a separate experiment and broader project accounting; they must not become free training labels or be silently added to these fitting cohorts. A favorable result must survive a complete untouched-source-family freeze and prospective evaluation before any superiority claim.

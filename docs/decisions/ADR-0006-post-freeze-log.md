# ADR-0006: Changes and observations after the plan was frozen

Plan v1 (hash `b631fa5a…`) was frozen 15 Nov 2026 at 03:34 UTC. The observations below were made under v1; its results are kept in `outputs/results_v1_frozen/`. Plan v2 (ADR-0007) changed one estimator setting after the planted-effect test failed. The lock file records both hashes.

## Changes to code (no change to the plan)

| When | Change | Why it is not a specification search |
|---|---|---|
| First estimation run | `station_estimates` aggregated every cohort's cells into each station's estimate, so several stations reported the pooled number | A plain bug: the plan defines a station effect as that station's cohort cells only. Fixed, then re-run. The primary estimate is unaffected |

## Results seen and not acted on

- **The primary estimate rests on its base year.** With a universal base year (g − 1), every Central Link cell sits 5–14% below the 2002 base. The year-to-year gap between treated and control residuals moves by about ±5% with roughly 100 treated sales a year. One noisy base year therefore shifts the whole event study. A varying or averaged base period would be less fragile, but the plan fixed the universal base, so the primary result stands as estimated. The pre-trend bound and the specification curve are the plan's own record of this fragility.
- **The cohort date changes the sign.** Funding-dated −5.3%, announcement-dated +1.0%, opening-dated +7.2%. Central Link's surface construction on Martin Luther King Jr Way ran 2004–2009, between funding and opening. A construction dip followed by recovery is consistent with this pattern, but the design does not test it.
- **Only four of nine cohorts contribute.** The pre-registered minimum of 20 sales per cell excludes University Link (2009), Angle Lake (2011), Lynnwood Link (2018), Federal Way (2020) and Downtown Redmond (2021) from every cell. Station-level effects exist for three stations only, so the elasticity rests on k = 3.
- **The West Seattle control alternate is a no-op.** Planned-area sales lie in assessor areas 16, 18 and 48, none of which contains treated sales. The submarket rule already kept them out of every comparison.

## Owner

Project analyst. Any change to `pap.yaml` from here requires `config.refreeze(reason)` and a new entry in this file.

## Reproducibility check (15 Nov 2026, `make all` from raw data)

- **Exact:** the primary estimate, its bounds, the spillover estimate, the elasticity and every specification-curve entry rebuilt identically. Revenue results matched to floating-point tolerance.
- **Close, not exact:** the simulation-based tests matched in every pass/fail verdict but not in their statistics. Planted-effect coverage was 77% in one run and 80% in the other. The placebo band moved by about 2 points.
- **Likely cause:** multithreaded linear algebra sums in a nondeterministic order, and propensity logits that are nearly separated (a submarket holding only placebo-treated or only control sales) amplify the difference.
- **Run time also varies:** the placebo test took 8.5 minutes in one run and 3.5 hours in the other on a machine with 7 GB of RAM.
- **Next action:** restrict each cell to submarkets containing both groups (common support), then rerun with single-threaded BLAS (`OPENBLAS_NUM_THREADS=1`) to confirm bit-for-bit reproducibility. This changes the estimator, so it requires plan v3.

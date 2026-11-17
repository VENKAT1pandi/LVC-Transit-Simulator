# Pre-analysis plan: Link capitalization and West Seattle value capture

Version 1 · written and frozen 15 November 2026, before any treatment contrast was estimated · Owner: project analyst

The machine-readable plan is [`config/pap.yaml`](../config/pap.yaml). `transitcap freeze` records its SHA-256 in `config/pap.lock`. Every estimation command checks that hash and refuses to run if the file has changed. Deviations after freezing are recorded in `docs/decisions/` and re-frozen with a stated reason.

## 1. The decision this serves

Sound Transit's West Seattle Link Extension (Delridge and Alaska Junction stations, planned for 2035) has a funding gap. This plan asks whether a value-capture instrument available in Washington law could close a material part of it.

The question splits in two:

1. On the Link stations that have opened, how much did home values rise per unit of access gain?
2. Carried to West Seattle, how likely is the resulting net revenue to reach 5% of the funding gap?

The audience is the agency's finance team. A credible null result counts as success.

## 2. Data

| Source | Content | Use |
|---|---|---|
| King County Assessor bulk extracts (downloaded 15 Nov 2026) | Sales 1900–2026, parcels, residential buildings, value history with land and improvement split | Outcome, covariates, assessment bridge, land split |
| King County parcel map service | Parcel polygons within 3.5 km of every King County station | Location, area, rings |
| Sound Transit GTFS `SC-Fall-2026.6` | Weekday Link timetable | Rail travel times and headways |
| OpenStreetMap, Geofabrik Washington extract (15 Nov 2026) | Street and path network | Network walk times |
| LODES 8 workplace area characteristics, 2019 | Jobs by census block | Accessibility |
| Census 2020 blocks; ACS 2018–2022 block groups | Block points; household income and tenure | Job locations; incidence |
| `data/reference/station_milestones.csv` | Announcement, funding, construction and opening dates with precision and source | Cohorts |

Raw files are kept unmodified in `data/raw` with checksums in `outputs/manifest.json`.

## 3. Sample

An observation is one sale. It is kept if all of the following hold:

- the sale is arm's-length: principal use residential (code 6), property class "residential improved" (8), a warranty-type deed (instrument 2, 3, 4 or 5), sale reason "none" (1), no sale warning, a single parcel, and a price of at least $50,000;
- the parcel's present use is single family or townhouse (codes 2, 6, 29);
- the parcel has exactly one residential building;
- the building existed at the sale date and was not renovated after it;
- the sale year is between 1995 and 2026.

Before 1995 the extract holds fewer than 15,000 qualifying sales a year county-wide.

## 4. Treatment

**Rings.** The plan computes walk time on the street network at 80 metres per minute.

| Ring | Rule | Role |
|---|---|---|
| Treated | 0–10 minutes to the station that assigns the cohort | Primary effect |
| Spillover | 10–20 minutes | Estimated on its own and never used as a control |
| Control | 20–40 minutes to the nearest station, and no open station within 20 minutes | Never-treated |
| Planned area | Within 20 minutes of a planned West Seattle station only | Never-treated control |
| Outside | More than 40 minutes | Dropped |

**Cohort.** The earliest station within 20 minutes, ranked by the chosen milestone, sets the parcel's cohort and ring. The primary milestone is the funding commitment; announcement and opening are the alternates. Each milestone is recorded with its precision. Funding dates marked PROXY are lower quality, and the cohort-date alternates show how much this matters.

**Exclusions.** Westlake, Symphony, Pioneer Square and International District have had bus-tunnel service since 1990 and few single-family sales. Their rings are excluded from both treated and control groups.

**Dose.** The dose is the change in log jobs reachable within 45 minutes by walking plus Link, with the parcel's station open versus not yet open, holding 2019 jobs fixed. Buses are not modelled (ADR-0002).

## 5. Estimator

**Group-time effects.** ATT(g, t) uses the doubly robust estimator for repeated cross-sections (ADR-0003). The base year is g − 1, a universal base. Controls are never-treated and not-yet-treated sales in assessor residential areas where the cohort has treated sales. A cell needs at least 20 sales in each of its four groups. The covariates are log living area, age, age squared, grade, bedrooms, bathrooms, log lot area, condition, view and waterfront.

**Aggregation.**

- The event study spans e = −8 to +10, weighting cohorts by treated sales.
- The headline is the average of e = 0..10, each event time weighted equally.

**Inference.**

- Clusters are station catchments, defined by the nearest station.
- The wild cluster bootstrap uses Rademacher weights, 999 draws, seed 20261115.
- Intervals are 95% percentile intervals. Conley standard errors are not computed; see §9.

**Elasticity.**

- Each station's post-period effect is regressed on its mean dose: weighted least squares through the origin, weighted by treated sales.
- Stations with a dose below 0.05 log points are dropped, because they carry no dose signal.
- Heterogeneity between stations is estimated with the DerSimonian–Laird method and supplies the transfer error.

**Spillover.** The spillover ring is estimated with the same estimator against the same controls.

**Specification curve.** The pre-registered alternates are: cohort dated by announcement; cohort dated by opening; never-treated controls only; controls excluding the West Seattle planned areas; and no covariates.

## 6. Power, before estimation

The minimum detectable effect uses 80% power and a two-sided 5% test. It is built from:

- sale counts by ring and year;
- the residual variance of a hedonic model with area-by-year effects, fit only on sales that are not post-treatment;
- a design effect from the cluster-year intraclass correlation.

The break-even effect is the elasticity at which the better instrument reaches a 5% funding ratio at central parameter values, converted to a price effect on the completed corridor using the corridor's mean dose. If the minimum detectable effect exceeds the break-even effect, G1 fails and the work stops.

## 7. Falsification

Each test has its own pass rule.

| Test | Pass rule |
|---|---|
| Planted effect | 100 simulated price sets on the real design with a 0.05 log-point effect; the 95% interval covers it in at least 90% of runs |
| Pre-trend bounds | The sign of the effect holds at M̄ = 1 (violations as large as the largest pre-period step) |
| Placebo stations | 100 relocations of every included station to random never-treated parcels with a 700 m ring; the real estimate lies outside the central 95% |
| Placebo date | Milestones shifted 5 years early, using only sales before the true date and four post years; the interval covers zero |
| Rezoning split | Blocked: no parcel-level zoning history exists in the open data |
| Composition | Effect on log living area, age and grade, with no covariates, under 0.10 standard deviations |
| Leave one station out | Every leave-one-out estimate inside the full-sample interval |

## 8. From estimate to revenue

| Element | Rule |
|---|---|
| Land split | The whole gain goes to land. Land share is reported from the assessor split and from vacant single-family lot sales by area and 5-year window |
| Assessment bridge | Median ratio of assessed value to price; a sale in year t is compared with tax year t + 1. Washington revalues annually with no assessed-value cap, so the gain reaches the roll after a one-year lag |
| Base | Single-family parcels within a 10-minute walk of the planned stations. 2026 assessed value is divided by the assessment ratio to give market value |
| Timing | Capitalization ramps linearly from funding commitment to full value at +10 years and grows with background assessed-value growth (median for control parcels, 2000–2026) |
| LID | One assessment at +10 years: 30–60% of special benefit, response −5% to −30%, collection 95–99%, administration 2–5%, 20 annual installments at the borrowing rate |
| TIA | Two areas, each filled nearest-first up to $200M base assessed value. Levy rate $6–9 per $1,000, collection 97–99.5%, administration 1–3%, response −2% to −20%, 25-year sunset, adoption lag 0–3 years. Gross and net reported |
| Overlap | In the package, gain assessed by the LID is not counted again under the TIA |
| Funding ratio | Present value of net revenue at the borrowing rate (3.5–5%) ÷ funding gap ($0.8–3.8 billion) |
| Bankability | 10th-percentile annual net revenue ÷ annual debt service on the gap (30-year annuity), years 1–10 |
| Monte Carlo | 10,000 draws. Elasticity from the bootstrap plus normal transfer error with the between-station SD; policy parameters uniform on the ranges above; seed 20261116 |
| Bands | Below 5%, 5–15%, 15–30%, above 30% |

## 9. Gates

The gates and their thresholds are in ADR-0004 and `config/pap.yaml`. G4 passes if the probability of a funding ratio of at least 5% is 50% or more. G5 passes if the median block-group annual LID charge is no more than 5% of median household income.

## 10. What this plan does not do

- Conley standard errors, SLX and spatial Durbin checks
- Repeat-sales, synthetic difference-in-differences, geographic discontinuity and causal-forest checks
- The commercial track, rental listings and a causal rent effect
- Displacement measures

These are phase 2. Their absence widens what the results cannot rule out, and the decision memo says so.

## 11. Known threats

| Threat | Where it shows |
|---|---|
| Bus service ignored, so the dose is overstated | ADR-0002; elasticity interpretation |
| Current building characteristics | Composition check |
| West Seattle announced in 2016 (ST3), so its areas may already price the line | Planned areas enter as controls and may bias the effect down. The specification-curve alternate that drops them from the controls is the check |
| Mixed-quality funding dates | Specification curve |

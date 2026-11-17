# TransitCap v3: Prototype Specification

Nov 15, 2026 · @Venkatesh

## Verdict

The draft has the right ambition and the wrong shape. It lists everything a senior study could contain (8 identification methods, 32 tables, 6 deliverables) with no order, no priority and no stopping point. That is a research agenda. A prototype needs one corridor, one primary specification and a point at which it says stop.

**Keep:** capitalization rather than uplift, the land and improvement split, collectable revenue as the only number finance cares about, the materiality test, and a decision protocol as the end product.

**Change:** v3 corrects three technical errors, adds the missing links between the estimate and the money, reorders the decision rules by cost, and cuts the build to one corridor, 10 tables and 12 weeks.

## The nine upgrades

Rows 5, 6 and 9 are errors in the draft. The rest are gaps.

| # | In the draft | Why it fails | v3 fix |
| --- | --- | --- | --- |
| 1 | Eight methods, all co-equal | No estimate is the answer; results can be picked after the fact | One frozen primary specification; every other method gets one named job |
| 2 | Studies a completed line to justify a levy on it | The gain on a completed line went to whoever owned at announcement. Later buyers already paid for access in their price | Use the completed line to calibrate, then transfer to a planned line. On the existing line, test only flow instruments |
| 3 | Treatment is nearness to a station | A station that adds little access adds little value; distance alone cannot be carried to another corridor | Treatment dose is the gain in job accessibility by transit, computed from before and after timetables |
| 4 | Event time counts from opening day | Prices move at announcement and funding. A baseline after announcement understates the effect | Four dated milestones per station: announcement, funding commitment, construction start, opening |
| 5 | The staggered DiD equation shown is two-way fixed effects | It is the biased estimator the draft warns against | Group-time average effects with not-yet-treated controls |
| 6 | Spatial Durbin model with total effect scaled by 1/(1 − ρ) | ρ is identified by the assumed weights matrix, not by the data; with a WX term the total is (β + θ)/(1 − ρ); the multiplier inflates any revenue base it touches | Ring design with a separately estimated spillover ring. SLX as a check. Spatial Durbin as appendix sensitivity only |
| 7 | Revenue is base × rate × collection × eligibility × timing | Static. No link from market price to taxable value, no behavioural response, no overlap between instruments, no gross versus net | Revenue model with an assessment bridge, response elasticities, overlap deduction and a net-new rule |
| 8 | No check that the corridor can answer the question | A thin sales sample gives a wide interval that reads as no effect | Compute the minimum detectable effect and compare it with the break-even effect before estimating |
| 9 | Decisions hinge on statistical significance and a pass or fail pre-trend test | Insignificant is not zero; pre-tests have low power and distort what survives them | Decide on the probability of materiality; replace pass or fail with sensitivity bounds; order gates by cost |

## Question and estimands

The draft asks about a completed line, but the decision it serves is about the next one. v3 states both halves.

> On a rail corridor that has opened, how much land value did the accessibility gain create, where and when? Carried to a planned corridor, what net revenue could a legally available instrument collect, and how likely is that revenue to be material to the funding plan?

The work runs as a chain of four steps:

1. **Estimate.** On the completed corridor, measure capitalization per unit of accessibility gain.
2. **Transfer.** Apply that elasticity to the planned corridor's accessibility gain and land base, with a transfer-error term.
3. **Design.** Convert the value gain into an instrument-specific base and net collectable revenue.
4. **Decide.** Report the probability that the present value of net revenue clears the materiality threshold.

With no planned corridor in scope, the chain stops after step 1 and step 3 covers only flow instruments on the existing line.

| Estimand | Definition | Used for |
| --- | --- | --- |
| Group-time effect, ATT(g, t) | Average effect on log price at time t for parcels first treated at milestone g | Event study, anticipation, construction disruption |
| Capitalization elasticity, ε | Percent change in land value per percent gain in job accessibility | The transfer step |
| Spillover effect | Effect on parcels outside the treated ring but exposed to it | Where the levy zone ends; whether controls are clean |
| Land-value effect | Effect on the land component alone | Base for land-based instruments |
| Net-new share | Share of corridor gain not offset by losses elsewhere in the metro | Any citywide fiscal claim |

The net-new share is bounded, not point-identified. A reduced-form design cannot separate value created from value moved, so v3 reports a range and says so.

## Identification design

One specification is primary and is frozen before any outcome data is opened. Everything else is a named check on it.

### Primary specification

| Element | Choice |
| --- | --- |
| Outcome | Log price of arm's-length residential sales, repeated cross-section |
| Treated ring | Parcels within a 10-minute network walk of a new station |
| Spillover ring | 10 to 20 minutes; excluded from controls and estimated on its own |
| Controls | Never-treated and not-yet-treated parcels at 20 to 40 minutes in the same submarket; planned-but-unbuilt station areas where they exist |
| Cohort date | Funding commitment (primary); announcement and opening as alternates |
| Dose | Change in log job accessibility within 45 minutes by transit |
| Estimator | Callaway and Sant'Anna group-time effects, doubly robust, aggregated to event years −8 to +10 |
| Inference | Clustered by station catchment; wild cluster bootstrap below 30 stations; Conley standard errors as a check |

The ring widths are starting values. The pre-analysis plan fixes them from the walk-time distribution before estimation, not after.

```latex
ATT(g,t) = \mathbb{E}\left[\,Y_t(g) - Y_t(\infty) \mid G = g\,\right]
\qquad
\varepsilon = \frac{\partial\, \mathbb{E}[\ln V]}{\partial\, \Delta \ln A}
```

### Spillovers

Spillovers are a control-contamination problem before they are a modelling choice. If value spreads into the control ring, the estimate shrinks toward zero. If the station pulls demand out of the control ring, the estimate is inflated. The ring design handles both by keeping exposed parcels out of the control group and estimating their effect separately.

An SLX model with alternative weights matrices is the parametric check. Spatial Durbin results go in an appendix as average direct and indirect impacts, and no multiplier is ever applied to a revenue base.

### Power before estimation

Work out the break-even effect first: the capitalization needed for the best available instrument to reach the materiality threshold. Then compute the minimum detectable effect from sale counts by ring and year. If the detectable effect is larger than the break-even effect, the corridor cannot answer the question and the work stops or moves.

### Falsification suite

| Test | What it catches | Pass criterion |
| --- | --- | --- |
| Planted-effect simulation | Pipeline bugs, estimator bias | A known injected effect is recovered inside its interval in at least 90% of runs |
| Pre-trend sensitivity bounds | Parallel-trend violations | Sign of the effect survives violations as large as the worst pre-period deviation |
| Placebo stations | Stations sited where prices were already moving | Real estimate lies outside the central 95% of placebo estimates |
| Placebo date | Divergence that predates the project | No effect when the milestone is shifted 5 years early |
| Rezoning split | Upzoning bundled with the station | Effect reported separately for parcels with and without a zoning change within 3 years |
| Composition check | A change in which homes sell | Characteristics of sold homes do not shift at treatment |
| Leave one station out | One station driving the result | Estimate stays inside the full-sample interval |

### Secondary designs, one job each

- **Repeat sales:** checks that unobserved quality is not driving the result. Renovated parcels are dropped using permits.
- **Synthetic difference-in-differences:** station-level estimate where clean controls are scarce.
- **Geographic discontinuity:** used only at a legal boundary of an existing instrument or service area.
- **Causal forest:** exploratory heterogeneity by property type, income and zoning capacity. Never the headline.
- **Commercial property:** a separate track on assessed values and rents, labelled descriptive unless sales are sufficient.

## From capitalization to collectable revenue

Four links connect a causal price effect to money an agency can spend. The draft has the first and the last; the middle two are missing.

### 1. Land split

A station does not change what a building costs to replace, so the whole value gain belongs to land. The percent gain in land value is therefore the percent gain in property value divided by the land share. A 6% property effect on a parcel that is 40% land is a 15% land effect.

Sources for the land share, in order of preference:

1. Vacant-land and teardown sales near stations, where price is land value.
2. Property value minus depreciated replacement cost.
3. The assessor's split, flagged as formula-driven.

The levy base is reported under at least two of these.

### 2. Assessment bridge

The causal estimate is in market prices. Tax instruments bill on assessed value. The bridge models the assessment ratio, the reassessment cycle and any annual cap on increases. Where assessments reset only on resale, the gain reaches the roll at the turnover rate, and that sets the revenue timing.

### 3. Revenue model

```latex
R^{k}_{i,t} \;=\; B^{k}_{i,t}\!\left(\hat{\tau},\, a,\, \eta^{k}\right)\cdot r^{k}\cdot e^{k}_{i}\cdot c^{k}_{t}\cdot\left(1-\alpha^{k}\right)\;-\;O^{k}_{i,t}
```

The base B depends on the causal effect, the assessment bridge a and a behavioural response η. Rate r, eligibility e and collection c are as in the draft, with c net of appeals and delinquency. α is the administrative cost share. O is the overlap deduction.

Three rules govern it:

- **Net-new rule.** A tax-increment district collects all growth above its baseline, including growth that would have happened without the line. Only the causal share is project revenue. The rest is a transfer from the general fund or overlapping taxing bodies. Report gross and net.
- **Response rule.** Charges on development delay or move development. Charges on land lower land prices. Use an elasticity range, never zero.
- **Overlap rule.** No parcel-year gain is counted under two instruments.

### 4. Materiality test

The draft divides annual revenue by annual debt service. Revenue arrives years after debt service starts, so that ratio flatters the instrument. v3 uses two tests:

| Test | Ratio | Answers |
| --- | --- | --- |
| Funding | Present value of net revenue ÷ present value of the funding gap, at the agency's borrowing rate | Does it change the funding plan? |
| Bankability | 10th-percentile annual net revenue ÷ annual debt service, each year for the first 10 | Could debt be raised against it without a backstop? |

The draft's bands (below 5%, 5 to 15%, 15 to 30%, above 30%) apply to the funding ratio and are fixed in the pre-analysis plan. The output is the probability of landing in each band.

### Uncertainty

One Monte Carlo run draws jointly from the estimator's bootstrap distribution, the transfer error, the policy parameters and the implementation lag. A tornado chart names the input that drives the variance. Model uncertainty is shown as a specification curve across the pre-registered alternates, not averaged away.

## Equity and incidence

Who pays depends on the instrument and on when the owner bought, not on who lives near the station.

| Instrument | Who bears it | Main equity risk | Safeguard |
| --- | --- | --- | --- |
| One-time betterment levy | Owners at the levy date | Charges buyers who already paid for access; cash-poor owner-occupiers | Levy only gains after a published valuation date; defer payment to sale |
| Tax increment district | Other taxing bodies, for the non-causal share | Schools and services lose ordinary growth | Cap the increment at the causal share; fixed sunset |
| Development-rights sale or density charge | Developers and, through land prices, landowners | Slows housing supply at stations | Exempt income-restricted units; calibrate to residual land value |
| Annual land-value surcharge | Landowners | Fixed-income owners; short-run pass-through to rents | Income-tested deferral |
| Joint development on public land | No compulsory payer | Public land sold below value | Competitive disposal with a published reserve |

### What can honestly be measured

The draft promises a causal displacement framework. Public tract-level data cannot deliver that, because involuntary moves are rarely observed. v3 commits to three things:

1. **A causal rent effect.** The same design as prices, run on rental listings. This is estimable.
2. **Descriptive monitoring with triggers.** Rent burden, eviction filings where public, expiring affordability restrictions and tenure change. Labelled descriptive.
3. **Individual displacement.** Only if a linked migration or administrative panel is available. Otherwise stated as not measured.

A block-level incidence table (who pays, how much, as a share of income) is published before any instrument is adopted.

## Decision protocol

The draft's rules are a flat list that runs the expensive econometrics before the cheap legal check. v3 orders six gates by cost, so a dead end is found as early as possible.

&#91;embedded content: decision protocol · 6 gates, 5 exits\]

A failed G5 loops back to G4 with the redesigned instrument. Three rules sit behind the gates:

- **Precise zero versus no answer.** At G2, a tight interval around zero rejects LVC. A wide interval sends the work back to G1.
- **Collect more data** is chosen only when resolving the largest driver in the tornado chart could move the result across a materiality band.
- **Above 30%** on the funding ratio triggers independent valuation, legal and governance due diligence before any commitment.

## Prototype scope and build plan

One corridor, one analyst, open data, 12 weeks. A credible null result counts as success.

### Test bed

A corridor qualifies if it has:

- Open parcel-level sales from 8 years before announcement to 5 years after opening
- At least 6 stations with staggered opening dates
- Archived timetables (GTFS) from before and after opening
- A land and improvement split in the assessment roll
- At least one value-capture instrument already in law
- A planned extension to transfer the estimate to

The candidates below are from memory and were not checked against live sources. Gate G1 verifies data access and dates.

| Candidate | Strength | Weakness |
| --- | --- | --- |
| Seattle, Link light rail | Several opening cohorts since 2009; open county assessor sales; extensions still being built | Strong regional price growth makes controls harder |
| New York, Second Avenue Subway | Open city sales and parcel data; a published value-capture study to replicate against | One opening cohort; co-ops and condos complicate the land split |
| London, Elizabeth line | Open national price-paid data; existing levies to back-test | No parcel land split; a very long anticipation period |
| Chicago, Cook County | Assessor data matches the draft's PIN schema; tax-increment districts in wide use | Few new stations, so a weak staggered design |
| An Indian metro corridor | Value-capture instruments exist in national and state policy | Registered prices tend to track guidance values, so the outcome variable needs listings or another market source |

Default: Seattle, for the staggered cohorts and the live extension pipeline.

### Minimum viable data

Ten tables, down from 32. The rest wait for phase 2.

| Table | Grain | Why it is in the minimum |
| --- | --- | --- |
| dim\_parcel | Parcel | Geometry, land area, use, submarket |
| fact\_sales | Transaction | Outcome; arm's-length and quality flags merged in |
| fact\_assessed\_value | Parcel-year | Land split and the assessment bridge |
| dim\_station | Station | Location and the four milestone dates |
| gtfs\_history | Feed version | Before and after timetables |
| parcel\_access | Parcel-year | Job accessibility, the treatment dose |
| treatment\_assignment | Parcel-cohort | Ring, cohort, control or excluded |
| dim\_zoning | Parcel-period | Zoning and its change dates, for the rezoning split |
| dim\_lvc\_instrument | Instrument | Legal base, rate, exemptions, collection path |
| fact\_project\_finance | Project-year | Capital cost, funding gap, debt service |

Phase 2 adds rental listings, permits, ownership, census indicators and collection history.

Stack: DuckDB with GeoParquet or PostGIS for storage; R5 for accessibility; the R packages `did`, `HonestDiD`, `fixest` and `synthdid` for estimation; Python for the Monte Carlo; MapLibre for the atlas.

### Build plan

| Weeks | Work | Output | Gate |
| --- | --- | --- | --- |
| 1 | Legal screen; corridor choice; break-even effect | Legal memo, 2 pages; break-even percentage | G0 |
| 2 to 3 | Ingest the ten tables; clean sales; power calculation | Data audit; detectable effect against break-even | G1 |
| 4 | Freeze the pre-analysis plan; run the planted-effect simulation | Plan of 8 to 10 pages, registered |  |
| 5 to 7 | Primary estimate; spillover ring; falsification suite | Event study, dose-response curve, results memo | G2, G3 |
| 8 to 9 | Land split; assessment bridge; revenue model for two instruments | Gross and net revenue distributions |  |
| 10 | Monte Carlo; materiality tests; incidence table | Probability of each materiality band | G4 |
| 11 | Transfer to the planned extension; capitalization atlas | Interactive map with intervals | G5 |
| 12 | Decision memo; replication package | Memo of 2 pages; code and data hash |  |

### The prototype succeeds if

- The pipeline recovers a planted effect
- The primary estimate and its bounds rebuild from one command
- Two instruments have gross and net revenue distributions
- Every line of the decision memo traces to a gate, and the memo says what would change its conclusion

## Choices that are yours

Five decisions shape the build. Each has a default I assumed so the spec is complete; change any of them and the affected sections follow.

| Choice | Default assumed | What it changes |
| --- | --- | --- |
| Corridor and jurisdiction | Seattle | Data tables, legal screen, which instruments are testable |
| Audience for the decision memo | A transit agency's finance team | The materiality denominator and the instruments in scope |
| A planned line to transfer to | Yes, an extension on the same network | Without one, the chain stops at step 1 and only flow instruments are tested |
| Resourcing | One analyst, full time, open data only | The 12-week plan; a funded team could add the commercial track and phase 2 data |
| Materiality bands and discount rate | The draft's bands; the agency's borrowing rate | Every result at G4; must be fixed before estimation |

## References

Cited from memory. Check each against the published version before it goes into a pre-analysis plan.

**Staggered difference-in-differences and pre-trends**

- Callaway and Sant'Anna (2021). Difference-in-differences with multiple time periods. *Journal of Econometrics*.
- Goodman-Bacon (2021). Difference-in-differences with variation in treatment timing. *Journal of Econometrics*.
- Sant'Anna and Zhao (2020). Doubly robust difference-in-differences estimators. *Journal of Econometrics*.
- Roth (2022). Pretest with caution: event-study estimates after testing for parallel trends. *AER: Insights*.
- Rambachan and Roth (2023). A more credible approach to parallel trends. *Review of Economic Studies*.
- Arkhangelsky, Athey, Hirshberg, Imbens and Wager (2021). Synthetic difference-in-differences. *American Economic Review*.

**Spatial spillovers and inference**

- Butts (2021). Difference-in-differences estimation with spatial spillovers. Working paper.
- Gibbons and Overman (2012). Mostly pointless spatial econometrics? *Journal of Regional Science*.
- Halleck Vega and Elhorst (2015). The SLX model. *Journal of Regional Science*.
- LeSage and Pace (2009). *Introduction to Spatial Econometrics*. CRC Press.
- Conley (1999). GMM estimation with cross sectional dependence. *Journal of Econometrics*.
- Cameron, Gelbach and Miller (2008). Bootstrap-based improvements for inference with clustered errors. *Review of Economics and Statistics*.
- Keele and Titiunik (2015). Geographic boundaries as regression discontinuities. *Political Analysis*.
- Wager and Athey (2018). Estimation and inference of heterogeneous treatment effects using random forests. *Journal of the American Statistical Association*.

**Transit capitalization, land value and value capture**

- McMillen and McDonald (2004). Reaction of house prices to a new rapid transit line: Chicago's Midway Line, 1983 to 1999. *Real Estate Economics*.
- Dye and McMillen (2007). Teardowns and land values in the Chicago metropolitan area. *Journal of Urban Economics*.
- Gupta, Van Nieuwerburgh and Kontokosta (2022). Take the Q train: value capture of public infrastructure projects. *Journal of Urban Economics*.
- Suzuki, Murakami, Hong and Tamayose (2015). *Financing Transit-Oriented Development with Land Values*. World Bank.

# ADR-0007: Add submarket indicators after the planted-effect test failed (plan v2)

Status: accepted, 15 Nov 2026. Deviation from the frozen plan v1 (`b631fa5a…`). Owner: project analyst.

## What happened

The planted-effect simulation (spec: "catches pipeline bugs, estimator bias") ran after plan v1 was frozen. It failed. On simulated prices with the real design and a planted 0.05 log-point effect, the v1 estimator averaged 0.033, and its 95% interval covered the truth in 75 of 100 runs.

## Diagnosis

Controls are restricted to the treated cohort's assessor areas, but v1's outcome and propensity models had no area terms. When areas trend differently, the pooled controls' area mix does not match the treated mix, and the estimate is biased.

A 20-run diagnostic on simulated outcomes only:

| Model | Mean estimate | Bias | Coverage |
|---|---|---|---|
| v1 | 0.036 | −0.014 | 80% |
| v1 + assessor-area indicators | 0.053 | +0.003 | 70% |

## Decision

Plan v2 adds assessor-area indicators to both nuisance models (`estimator.submarket_indicators: true`). The plan was re-frozen with this reason recorded in `config/pap.lock`. Everything downstream was re-run.

## What this does not fix

The full 100-run test under v2 averaged 0.052 against the planted 0.050, so the bias is fixed. Coverage was 77% (80% in the full rebuild; see ADR-0006), still below 90%. The likely causes are:

- few effectively treated clusters (Central Link's seven stations carry most of the weight);
- the influence function treating nuisance models as known (ADR-0003).

The intervals in v2 are therefore too narrow, and the memo says so. G3 still fails on this test.

## Why this is not a specification search

The fix was chosen from the simulation, where the truth is known, not from the real estimate. The real v1 results are kept unchanged in `outputs/results_v1_frozen/` for comparison.

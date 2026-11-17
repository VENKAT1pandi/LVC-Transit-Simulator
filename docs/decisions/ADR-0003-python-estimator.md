# ADR-0003: Estimators implemented in Python, not the R packages named in the spec

Status: accepted, 15 Nov 2026 (user chose "Python only"). Owner: project analyst.

## Decision

`estimate/csdid.py` implements Callaway–Sant'Anna group-time effects with the Sant'Anna–Zhao doubly robust estimator for repeated cross-sections (the "traditional" form, eq. 3.3). It uses not-yet-treated controls, a universal base period, and a wild cluster (Rademacher multiplier) bootstrap on influence functions. Pre-trend sensitivity is a simplified relative-magnitude bound (`estimate/falsify.py`).

## Known differences from `did` and `HonestDiD`

1. The influence function treats the propensity score and outcome regressions as known. `did` adds their estimation effect. Standard errors may be slightly too small. The planted-effect simulation measures whether coverage still reaches 90%.
2. `did`'s default repeated-cross-section estimator is the locally efficient variant. This build uses the traditional doubly robust variant, which is consistent under the same conditions but less efficient.
3. The pre-trend bound is a conservative box (bias grows by at most M̄ times the largest pre-period step per year). It is not HonestDiD's optimal fixed-length interval, so it is wider than HonestDiD would report.
4. Synthetic difference-in-differences, causal forests and the geographic discontinuity design are not implemented (spec: secondary designs). Repeat sales is also deferred.

## Check

Unit tests in `tests/test_csdid.py` recover a planted effect on synthetic staggered data with selection on observables. Cross-checking against `did` in R on the same data would retire difference 1 and is a phase-2 task.

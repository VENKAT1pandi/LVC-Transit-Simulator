"""Falsification suite (spec: Falsification suite). Each test returns a dict with a `passed` flag
(True, False, or None when the test could not be run) and the evidence behind it."""

import numpy as np
import pandas as pd
from scipy import stats

from transitcap.estimate import csdid
from transitcap.estimate.csdid import NEVER, Sample
from transitcap.estimate.power import residuals
from transitcap.estimate.prepare import subset


def planted_effect(s: Sample, d: pd.DataFrame, covariates: list[str], effect: float, runs: int,
                   min_coverage: float, event_max: int, seed: int) -> dict:
    """Replace outcomes with simulated prices on the real design and plant a known effect."""
    rng = np.random.default_rng(seed)
    r = residuals(d.assign(cohort=np.where(d.ring == "treated", d.cohort, NEVER)), covariates)
    sigma2 = float(r.resid.var())
    cy = r.groupby(["cluster_station", "sale_year"]).resid
    sd_cy = float(np.sqrt(max(cy.mean().var() - sigma2 / cy.size().mean(), 0)))
    sd_e = float(np.sqrt(max(sigma2 - sd_cy ** 2, 1e-6)))
    beta, *_ = np.linalg.lstsq(s.X, s.y, rcond=None)
    base = s.X @ beta
    area_year = pd.Series(s.y - base).groupby([s.block, s.year]).transform("mean").to_numpy()
    post = (s.g < NEVER) & (s.year >= s.g)
    cy_code = s.cluster * 10_000 + s.year
    _, cy_inv = np.unique(cy_code, return_inverse=True)
    covered, estimates = [], []
    for k in range(runs):
        shock = rng.normal(0, sd_cy, cy_inv.max() + 1)[cy_inv]
        y = base + area_year + shock + rng.normal(0, sd_e, len(s.y)) + effect * post
        sim = Sample(y=y, year=s.year, g=s.g, cluster=s.cluster, X=s.X, block=s.block)
        xi = csdid.multipliers(s.n_clusters, 199, seed + k)
        a = csdid.overall_post(csdid.att_gt(sim, event_max=event_max), xi)
        estimates.append(a.estimate)
        covered.append(a.lo <= effect <= a.hi)
    cov = float(np.mean(covered))
    return {"test": "planted_effect", "planted": effect, "runs": runs, "coverage": cov,
            "mean_estimate": float(np.mean(estimates)), "bias": float(np.mean(estimates) - effect),
            "passed": cov >= min_coverage}


def pretrend_bounds(es: pd.DataFrame, post: csdid.Aggregate, mbar: float, event_max: int,
                    alpha: float = 0.05) -> dict:
    """Relative-magnitude bounds in the spirit of Rambachan and Roth (2023), simplified.

    D = largest absolute change between consecutive pre-period coefficients (e = -1 is 0).
    A post-period violation may grow by at most mbar * D per year, so at horizon e the bias is
    at most (e + 1) * mbar * D; for the average over e = 0..H the bound is mbar * D * (H + 2) / 2.
    This is a conservative box, not the optimal fixed-length interval of HonestDiD.
    """
    pre = es[(es.e < 0)].dropna(subset=["att"]).sort_values("e")
    D = float(np.max(np.abs(np.diff(pre.att.to_numpy())))) if len(pre) > 1 else np.nan
    H = int(es[(es.e >= 0) & es.att.notna()].e.max()) if (es.e >= 0).any() else event_max
    z = float(stats.norm.ppf(1 - alpha / 2))

    def bounds(m):
        bias = m * D * (H + 2) / 2
        return post.estimate - bias - z * post.se, post.estimate + bias + z * post.se

    lo, hi = bounds(mbar)
    # breakdown: largest mbar at which the robust interval still excludes zero
    if D > 0 and post.estimate != 0:
        mb = max(0.0, (abs(post.estimate) - z * post.se) / (D * (H + 2) / 2))
    else:
        mb = np.nan
    same_sign = (lo > 0) if post.estimate > 0 else (hi < 0)
    return {"test": "pretrend_bounds", "max_pre_step": D, "mbar": mbar, "robust_lo": float(lo),
            "robust_hi": float(hi), "breakdown_mbar": float(mb), "passed": bool(same_sign)}


def placebo_stations(s: Sample, d: pd.DataFrame, xy: np.ndarray, real: csdid.Aggregate,
                     replicates: int, ring_m: float, central_share: float, event_max: int,
                     seed: int) -> dict:
    """Relocate every included station to a random never-treated parcel and re-estimate."""
    rng = np.random.default_rng(seed)
    ctrl = (s.g == NEVER)
    cs = subset(s, ctrl)
    cxy = xy[ctrl]
    stations = d[d.ring == "treated"].groupby("station_id").cohort.first()
    est = []
    for k in range(replicates):
        centres = cxy[rng.choice(len(cxy), size=len(stations), replace=False)]
        g = np.full(len(cxy), NEVER)
        near_any = np.zeros(len(cxy), bool)
        for c, coh in zip(centres, stations.to_numpy()):
            dist = np.hypot(*(cxy - c).T)
            g[(dist <= ring_m) & (g == NEVER)] = coh
            near_any |= dist <= 2 * ring_m
        keep = (g < NEVER) | ~near_any  # drop placebo spillover band from controls
        p = Sample(y=cs.y[keep], year=cs.year[keep], g=g[keep], cluster=cs.cluster[keep],
                   X=cs.X[keep], block=cs.block[keep])
        p.n_clusters = s.n_clusters
        xi = csdid.multipliers(s.n_clusters, 2, seed + k)
        est.append(csdid.overall_post(csdid.att_gt(p, event_max=event_max), xi).estimate)
    est = np.array([e for e in est if np.isfinite(e)])
    lo, hi = np.quantile(est, [(1 - central_share) / 2, 1 - (1 - central_share) / 2])
    return {"test": "placebo_stations", "replicates": int(len(est)), "placebo_lo": float(lo),
            "placebo_hi": float(hi), "real": real.estimate,
            "passed": bool(real.estimate < lo or real.estimate > hi)}


def placebo_date(s: Sample, shift: int, horizon: int, seed: int) -> dict:
    """Pretend each cohort was treated `shift` years early; use only sales before the true date."""
    true_g = s.g
    keep = (true_g == NEVER) | (s.year < true_g)
    p = subset(s, keep)
    p.g = np.where(p.g < NEVER, p.g - shift, NEVER)
    xi = csdid.multipliers(s.n_clusters, 999, seed)
    a = csdid.overall_post(csdid.att_gt(p, event_max=horizon), xi, event_max=horizon)
    return {"test": "placebo_date", "shift_years": shift, "estimate": a.estimate, "lo": a.lo,
            "hi": a.hi, "passed": bool(a.lo <= 0 <= a.hi)}


def composition(s: Sample, d: pd.DataFrame, outcomes: list[str], max_abs_std: float,
                event_max: int, seed: int) -> dict:
    xi = csdid.multipliers(s.n_clusters, 999, seed)
    rows = []
    for col in outcomes:
        y = d[col].to_numpy(dtype=float)
        c = Sample(y=y, year=s.year, g=s.g, cluster=s.cluster, X=s.X[:, :1], block=s.block)
        c.n_clusters = s.n_clusters
        a = csdid.overall_post(csdid.att_gt(c, event_max=event_max), xi)
        std = a.estimate / np.std(y)
        rows.append({"characteristic": col, "effect": a.estimate, "lo": a.lo, "hi": a.hi,
                     "std_effect": float(std), "ok": bool(abs(std) <= max_abs_std)})
    return {"test": "composition", "rows": rows, "passed": all(r["ok"] for r in rows)}


def leave_one_station_out(s: Sample, d: pd.DataFrame, full: csdid.Aggregate, event_max: int,
                          xi: np.ndarray) -> dict:
    rows = []
    for sid in sorted(d.loc[d.ring == "treated", "station_id"].dropna().unique()):
        drop = (d.station_id == sid).to_numpy() & (s.g < NEVER)
        a = csdid.overall_post(csdid.att_gt(subset(s, ~drop), event_max=event_max), xi)
        rows.append({"station_id": sid, "estimate": a.estimate,
                     "inside_full_ci": bool(full.lo <= a.estimate <= full.hi)})
    return {"test": "leave_one_station_out", "rows": rows,
            "passed": all(r["inside_full_ci"] for r in rows)}


def rezoning_split(zoning: pd.DataFrame) -> dict:
    if zoning.change_date.notna().any():
        raise NotImplementedError("zoning history is now present: implement the split estimate")
    return {"test": "rezoning_split", "passed": None, "status": "blocked",
            "reason": "dim_zoning holds only the current zoning snapshot; no open, parcel-level "
                      "history of zoning changes was found for King County jurisdictions"}

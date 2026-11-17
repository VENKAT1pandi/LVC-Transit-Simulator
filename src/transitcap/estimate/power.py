"""Minimum detectable effect from sale counts, computed before any treatment contrast is estimated.

Residual variance and the cluster-year intraclass correlation come from a hedonic model with
area-by-year effects fit only on sales that are not post-treatment (treated parcels before their
cohort year and never-treated parcels), so no treatment effect enters the calculation.
"""

import numpy as np
import pandas as pd
from scipy import stats

from transitcap.estimate.csdid import NEVER


def residuals(d: pd.DataFrame, covariates: list[str]) -> pd.Series:
    pre = d[(d.cohort == NEVER) | (d.sale_year < d.cohort)].copy()
    fe = pre.assessor_area.astype(str) + "_" + pre.sale_year.astype(str)
    X = pre[covariates].to_numpy(dtype=float)
    # absorb area-year effects by within-transformation, then OLS on covariates
    Xd = X - pd.DataFrame(X).groupby(fe.to_numpy()).transform("mean").to_numpy()
    yd = pre.log_price - pre.groupby(fe).log_price.transform("mean")
    beta, *_ = np.linalg.lstsq(Xd, yd.to_numpy(), rcond=None)
    pre["resid"] = yd.to_numpy() - Xd @ beta
    return pre.set_index(pre.index)[["resid", "cluster_station", "sale_year"]]


def mde(d: pd.DataFrame, covariates: list[str], event_min: int, event_max: int,
        alpha: float, power: float, last_year: int) -> dict:
    r = residuals(d, covariates)
    sigma2 = float(r.resid.var())
    cy = r.groupby(["cluster_station", "sale_year"]).resid
    m_bar = float(cy.size().mean())
    # one-way ANOVA estimator of the intraclass correlation
    between = float(cy.mean().var())
    icc = max(0.0, (between - sigma2 / m_bar) / sigma2)
    deff = 1 + (m_bar - 1) * icc

    treated = d[d.ring == "treated"]
    ctrl = d[d.ring.isin(["control", "planned_area"])]
    n_ctrl = ctrl.groupby("sale_year").size()
    var_terms, n_e = 0.0, 0
    per_e = {}
    for g, tg in treated.groupby("cohort"):
        n_t = tg.groupby("sale_year").size()
        for e in range(0, event_max + 1):
            t = g + e
            if t > last_year:
                continue
            nt, nb = n_t.get(t, 0), n_t.get(g - 1, 0)
            if nt == 0 or nb == 0:
                continue
            v = 1 / nt + 1 / nb + 1 / n_ctrl.get(t, np.inf) + 1 / n_ctrl.get(g - 1, np.inf)
            per_e.setdefault(e, []).append((nt, v))
    for e, items in per_e.items():
        tot = sum(n for n, _ in items)
        var_terms += sum((n / tot) ** 2 * v for n, v in items)
        n_e += 1
    se = float(np.sqrt(sigma2 * deff * var_terms) / n_e) if n_e else np.inf
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return {"sigma_resid": float(np.sqrt(sigma2)), "icc_cluster_year": icc,
            "mean_sales_per_cluster_year": m_bar, "design_effect": deff,
            "se_overall_post": se, "mde_log_points": float(z * se), "event_times_used": n_e,
            "n_treated_sales": int(len(treated)), "n_control_sales": int(len(ctrl))}

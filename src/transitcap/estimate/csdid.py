"""Callaway and Sant'Anna (2021) group-time average treatment effects for repeated cross-sections.

Each ATT(g, t) compares sales in cohort g with sales in never-treated or not-yet-treated areas,
between year t and the universal base year g - 1, using the doubly robust estimator of
Sant'Anna and Zhao (2020, eq. 3.3, "traditional" DR for repeated cross-sections):

    tau = E[(w11 - w10)(Y - mu0(T, X))] - E[(w01 - w00)(Y - mu0(T, X))]

with w1t = D 1{T=t} / E[D 1{T=t}], w0t = r 1{T=t} / E[r 1{T=t}], r = p(X)(1-D)/(1-p(X)),
p(X) a pooled logit propensity score, and mu0(t, X) an OLS outcome model fit on controls in t.

Inference uses each estimate's influence function, summed by cluster, with a Rademacher
multiplier (wild cluster) bootstrap shared across all cells so aggregations have a joint
distribution. Nuisance-estimation error is not propagated into the influence function; the
planted-effect simulation (estimate.falsify) checks whether coverage is still adequate.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

NEVER = 10_000  # cohort code for never-treated units


@dataclass
class Sample:
    y: np.ndarray          # outcome (log price)
    year: np.ndarray       # sale year
    g: np.ndarray          # cohort year, NEVER for never-treated
    cluster: np.ndarray    # integer cluster code 0..C-1
    X: np.ndarray          # covariates incl. intercept
    block: np.ndarray      # comparison block (submarket); controls must share it with treated
    n_clusters: int = field(init=False)

    def __post_init__(self):
        self.n_clusters = int(self.cluster.max()) + 1


@dataclass
class CellResult:
    g: int
    t: int
    att: float
    n_treated: int
    n_control: int
    psi_c: np.ndarray      # cluster-summed influence function / n, length C


def _logit(X: np.ndarray, d: np.ndarray, iters: int = 25) -> np.ndarray:
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (d - p))
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))


def _ols_predict(X: np.ndarray, y: np.ndarray, Xp: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return Xp @ beta


def dr_rc(y, D, T, X, cluster, n_clusters, trim: float = 0.995) -> tuple[float, np.ndarray]:
    """Doubly robust DiD for repeated cross-sections. Returns (att, cluster-summed psi / n)."""
    n = len(y)
    # drop columns constant at zero in this cell (submarket dummies absent from the cell); they
    # carry no information and dominate run time
    X = X[:, np.any(X != 0, axis=0)]
    p = np.minimum(_logit(X, D.astype(float)), trim)
    c0, c1 = (D == 0) & (T == 0), (D == 0) & (T == 1)
    mu = np.where(T == 1, _ols_predict(X[c1], y[c1], X), _ols_predict(X[c0], y[c0], X))
    e = y - mu
    r = p * (1 - D) / (1 - p)
    att, psi = 0.0, np.zeros(n)
    for a, sign in ((D * T, 1), (D * (1 - T), -1), (r * T, -1), (r * (1 - T), 1)):
        s = a.sum()
        theta = (a * e).sum() / s
        att += sign * theta
        psi += sign * n * a * (e - theta) / s
    psi_c = np.bincount(cluster, weights=psi, minlength=n_clusters) / n
    return float(att), psi_c


def att_gt(s: Sample, event_min: int = -8, event_max: int = 10, min_cell: int = 20,
           control: str = "notyet") -> list[CellResult]:
    out = []
    cohorts = sorted(set(s.g[s.g < NEVER].tolist()))
    years = sorted(set(s.year.tolist()))
    for g in cohorts:
        base = g - 1
        treated_blocks = np.unique(s.block[s.g == g])
        in_block = np.isin(s.block, treated_blocks)
        for t in years:
            e = t - g
            if e < event_min or e > event_max or t == base:
                continue
            last = max(t, base)
            is_ctrl = ((s.g == NEVER) | (s.g > last)) if control == "notyet" else (s.g == NEVER)
            keep = np.isin(s.year, (t, base)) & ((s.g == g) | (is_ctrl & in_block))
            D = (s.g[keep] == g).astype(int)
            T = (s.year[keep] == t).astype(int)
            cells = [(D == d) & (T == tt) for d in (0, 1) for tt in (0, 1)]
            if min(c.sum() for c in cells) < min_cell:
                continue
            att, psi_c = dr_rc(s.y[keep], D, T, s.X[keep], s.cluster[keep], s.n_clusters)
            out.append(CellResult(g, t, att, int(D.sum()), int((1 - D).sum()), psi_c))
    return out


@dataclass
class Aggregate:
    label: str
    estimate: float
    se: float
    lo: float
    hi: float
    draws: np.ndarray      # bootstrap draws of the estimate (B,)


def multipliers(n_clusters: int, B: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 1.0], size=(B, n_clusters))


def aggregate(cells: list[CellResult], weights: dict[tuple[int, int], float], xi: np.ndarray,
              label: str, alpha: float = 0.05) -> Aggregate:
    """Weighted combination of cells; weights need not be normalised."""
    sel = [(c, weights[(c.g, c.t)]) for c in cells if weights.get((c.g, c.t), 0) > 0]
    if not sel:
        return Aggregate(label, np.nan, np.nan, np.nan, np.nan, np.full(len(xi), np.nan))
    wsum = sum(w for _, w in sel)
    est = sum(w * c.att for c, w in sel) / wsum
    psi = sum(w * c.psi_c for c, w in sel) / wsum
    draws = est + xi @ psi
    se = float(np.sqrt((psi ** 2).sum()))
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return Aggregate(label, float(est), se, float(lo), float(hi), draws)


def event_study(cells: list[CellResult], xi: np.ndarray, event_min=-8, event_max=10) -> pd.DataFrame:
    rows = []
    for e in range(event_min, event_max + 1):
        if e == -1:
            rows.append(dict(e=e, att=0.0, se=0.0, lo=0.0, hi=0.0, n_treated=0))
            continue
        w = {(c.g, c.t): c.n_treated for c in cells if c.t - c.g == e}
        a = aggregate(cells, w, xi, f"e={e}")
        rows.append(dict(e=e, att=a.estimate, se=a.se, lo=a.lo, hi=a.hi,
                         n_treated=int(sum(w.values()))))
    return pd.DataFrame(rows)


def overall_post(cells: list[CellResult], xi: np.ndarray, event_max: int = 10,
                 label: str = "post") -> Aggregate:
    """Average of event-time effects e = 0..event_max (each event time weighted equally,
    as in did::aggte(type = 'dynamic')), cohorts within an event time weighted by treated n."""
    per_e = {}
    for c in cells:
        e = c.t - c.g
        if 0 <= e <= event_max:
            per_e.setdefault(e, []).append(c)
    w = {}
    for e, cs in per_e.items():
        tot = sum(c.n_treated for c in cs)
        for c in cs:
            w[(c.g, c.t)] = c.n_treated / tot / len(per_e)
    return aggregate(cells, w, xi, label)

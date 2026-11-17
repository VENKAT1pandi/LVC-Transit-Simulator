"""Revenue model and Monte Carlo (spec: From capitalization to collectable revenue).

R^k_{i,t} = B^k_{i,t}(tau, a, eta^k) * r^k * e^k_i * c^k_t * (1 - alpha^k) - O^k_{i,t}

Timeline: year k = 0 is the funding commitment of the planned line. Capitalization ramps linearly
to its full value over `realization_years` (PAP). All money is nominal; the gain grows with
background value growth g. Present values are taken at k = 0 at the borrowing rate.

Instruments
- LID: one special assessment at k = realization_years on the causal gain of single-family
  parcels in the 10-minute ring, times capture share, paid in equal installments with interest
  at the borrowing rate (so its present value at assessment equals the assessed amount).
- TIA: levy on increment assessed value in up to two areas, each capped at $200M base AV
  (RCW 39.114.020), parcels added nearest-first. Gross = all increment; net = causal share only
  (net-new rule). Adoption lag puts gain accrued before adoption into the base.
- Package: LID + TIA with the overlap rule; gain already assessed by the LID is not counted again.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Base:
    market_value: np.ndarray   # parcel market value now (assessed / assessment ratio)
    assessed: np.ndarray       # assessed total value now
    dose: np.ndarray           # planned change in log job access
    station: np.ndarray        # nearest planned station
    walk_min: np.ndarray
    single_family: np.ndarray  # parcel type the elasticity was estimated on
    in_lid_zone: np.ndarray    # 10-minute ring
    assessment_ratio: float
    growth: float              # background annual growth of assessed value


def _uniform(rng, lo_hi, n):
    lo, hi = lo_hi
    return rng.uniform(lo, hi, n)


def draw_params(pap: dict, n: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    rv, fin = pap["revenue"], pap["finance"]
    p = {
        "lid_capture": _uniform(rng, rv["lid"]["capture_share"], n),
        "lid_collection": _uniform(rng, rv["lid"]["collection"], n),
        "lid_admin": _uniform(rng, rv["lid"]["admin_cost_share"], n),
        "lid_eta": _uniform(rng, rv["lid"]["response_elasticity"], n),
        "tia_rate": _uniform(rng, rv["tia"]["levy_rate_per_1000"], n) / 1000,
        "tia_collection": _uniform(rng, rv["tia"]["collection"], n),
        "tia_admin": _uniform(rng, rv["tia"]["admin_cost_share"], n),
        "tia_eta": _uniform(rng, rv["tia"]["response_elasticity"], n),
        "gap": _uniform(rng, fin["funding_gap_usd"], n),
        "rate": _uniform(rng, fin["borrowing_rate"], n),
        "lag": rng.integers(fin["implementation_lag_years"][0], fin["implementation_lag_years"][1] + 1, n),
    }
    return p


def tia_areas(base: Base, cap_usd: float, max_areas: int) -> np.ndarray:
    """Boolean mask of parcels inside the TIA areas: nearest-first per station until the cap."""
    mask = np.zeros(len(base.assessed), bool)
    for s in sorted(set(base.station.tolist()))[:max_areas]:
        idx = np.flatnonzero((base.station == s) & base.in_lid_zone)
        idx = idx[np.argsort(base.walk_min[idx])]
        within = np.cumsum(base.assessed[idx]) <= cap_usd
        mask[idx[within]] = True
    return mask


def simulate(base: Base, eps: np.ndarray, p: dict[str, np.ndarray], pap: dict) -> dict:
    rv, fin = pap["revenue"], pap["finance"]
    H, R = rv["horizon_years"], rv["realization_years"]
    n = len(eps)
    k = np.arange(H)
    ramp = np.minimum(k / R, 1.0)                                      # [H]
    grow = (1 + base.growth) ** k                                      # [H]
    disc = (1 + p["rate"][:, None]) ** -k[None, :]                     # [n, H]

    # causal market-value gain at full realization, per draw, by parcel group
    gain_full = base.market_value[None, :] * np.expm1(eps[:, None] * base.dose[None, :])
    sf = base.single_family
    lid_zone = base.in_lid_zone & sf
    tia = tia_areas(base, pap["gates"]["tia_max_area_av_usd"], pap["gates"]["tia_max_areas"])

    # ---- LID
    benefit = gain_full[:, lid_zone].sum(axis=1) * grow[R]             # at assessment year R
    assessed_lid = np.maximum(benefit, 0) * p["lid_capture"] * (1 + p["lid_eta"])
    npay = rv["lid"]["payment_years"]
    r = p["rate"]
    installment = assessed_lid * r / (1 - (1 + r) ** -npay)
    lid_net = np.zeros((n, H))
    pay_years = (k > R) & (k <= R + npay)
    lid_net[:, pay_years] = (installment * p["lid_collection"] * (1 - p["lid_admin"]))[:, None]

    # ---- TIA (standalone): increment measured against the base at adoption year `lag`
    lag = p["lag"]
    sunset = rv["tia"]["sunset_years"]
    av_now = base.assessed[tia].sum()
    kk = np.maximum(k[None, :] - 1, 0)                       # one-year assessment lag
    lag_c = lag[:, None]
    active = (k[None, :] > lag_c) & (k[None, :] <= lag_c + sunset)
    path = ramp[kk] * grow[kk] - ramp[lag_c] * grow[lag_c]  # causal gain accrued since adoption
    factor = (p["tia_rate"] * p["tia_collection"] * (1 - p["tia_admin"]) * (1 + p["tia_eta"]))[:, None]

    def tia_causal(mask):
        av_gain = base.assessment_ratio * gain_full[:, mask].sum(axis=1)  # [n] at full ramp
        return np.where(active, av_gain[:, None] * path * factor, 0.0)

    background_inc = av_now * (grow[kk] - grow[lag_c])
    tia_net = tia_causal(tia & sf)
    tia_gross = tia_net + np.where(active, background_inc * factor, 0.0)

    # ---- Package with overlap rule: a gain already assessed by the LID is not counted again,
    # so only TIA parcels outside the LID zone add causal revenue
    package_net = lid_net + tia_causal(tia & sf & ~lid_zone)

    pv = lambda flows: (flows * disc).sum(axis=1)  # noqa: E731
    gap = p["gap"]
    ds = gap * r / (1 - (1 + r) ** -fin["debt_term_years"])
    out = {
        "lid_pv_net": pv(lid_net), "tia_pv_gross": pv(tia_gross), "tia_pv_net": pv(tia_net),
        "package_pv_net": pv(package_net),
        "lid_annual_net": lid_net, "tia_annual_net": tia_net, "package_annual_net": package_net,
        "debt_service": ds, "gap": gap,
        "tia_area_base_av": float(av_now), "tia_area_parcels": int(tia.sum()),
        "lid_zone_parcels": int(lid_zone.sum()),
    }
    for name in ("lid", "tia", "package"):
        out[f"{name}_funding_ratio"] = out[f"{name}_pv_net"] / gap
    return out


def band_probabilities(ratio: np.ndarray, bands: list[float]) -> dict[str, float]:
    edges = [-np.inf, *bands, np.inf]
    labels = [f"below {bands[0]:.0%}"] + [f"{a:.0%} to {b:.0%}" for a, b in zip(bands[:-1], bands[1:])] \
        + [f"above {bands[-1]:.0%}"]
    return {lab: float(np.mean((ratio >= lo) & (ratio < hi))) for lab, lo, hi in zip(labels, edges[:-1], edges[1:])}


def bankability(annual: np.ndarray, ds: np.ndarray, q: float, years: int) -> list[float]:
    """q-quantile of annual net revenue / annual debt service for years 1..years."""
    return [float(np.quantile(annual[:, y] / ds, q)) for y in range(1, years + 1)]


def tornado(base: Base, eps: np.ndarray, p: dict[str, np.ndarray], pap: dict, key: str) -> list[dict]:
    """One-at-a-time swing of each input between its 10th and 90th percentile, others at median."""
    med = {k: np.array([np.median(v)]) for k, v in p.items()}
    med["lag"] = np.array([int(np.median(p["lag"]))])
    inputs = {"elasticity (incl. transfer error)": None, **{k: k for k in p}}
    rows = []
    for label, name in inputs.items():
        vals = []
        for q in (0.1, 0.9):
            pp = {k: v.copy() for k, v in med.items()}
            e = np.array([np.median(eps)])
            if name is None:
                e = np.array([np.quantile(eps, q)])
            else:
                pp[name] = np.array([np.quantile(p[name], q)]).astype(p[name].dtype)
            vals.append(float(simulate(base, e, pp, pap)[f"{key}_funding_ratio"][0]))
        rows.append({"input": label, "low": vals[0], "high": vals[1], "swing": abs(vals[1] - vals[0])})
    return sorted(rows, key=lambda r: -r["swing"])

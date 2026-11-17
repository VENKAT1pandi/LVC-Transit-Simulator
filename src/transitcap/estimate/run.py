"""Estimation steps. `power_and_breakeven` runs before the plan is frozen; everything else after."""

import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd

from transitcap.estimate import csdid, falsify, power, prepare
from transitcap.estimate.csdid import NEVER
from transitcap.paths import OUTPUTS, PROCESSED

RES = OUTPUTS / "results"
RES.mkdir(parents=True, exist_ok=True)


def _dump(obj, name):
    (RES / name).write_text(json.dumps(obj, indent=2, default=float))


def primary_frame(pap: dict, milestone: str = "funding") -> pd.DataFrame:
    return prepare.with_assignment(prepare.sales_frame(pap), milestone)


def run_power(pap: dict) -> dict:
    d = primary_frame(pap)
    e = pap["estimator"]
    res = power.mde(d, e["covariates"], e["event_min"], e["event_max"], pap["power"]["alpha"],
                    pap["power"]["power"], pap["outcome"]["last_year"])
    ring_counts = d.groupby(["ring", "sale_year"]).size().unstack(0).fillna(0).astype(int)
    ring_counts.to_csv(RES / "sales_by_ring_year.csv")
    res["treated_dose_mean"] = float(d.loc[d.ring == "treated", "dose_dlnA"].mean())
    _dump(res, "power.json")
    return res


def station_estimates(s, d, xi, event_max) -> tuple[pd.DataFrame, dict]:
    rows, draws = [], {}
    for sid, grp in d[d.ring == "treated"].groupby("station_id"):
        g = int(grp.cohort.iloc[0])
        # other cohorts stay in the sample as not-yet-treated controls, but only this station's
        # cohort cells are aggregated (an earlier version averaged every cohort's cells)
        mask = (s.g == NEVER) | (s.g != g) | (d.station_id == sid).to_numpy()
        cells = [c for c in csdid.att_gt(prepare.subset(s, mask), event_max=event_max) if c.g == g]
        a = csdid.overall_post(cells, xi, event_max=event_max, label=sid)
        if not np.isfinite(a.estimate):
            continue
        rows.append({"station_id": sid, "cohort": g, "att": a.estimate, "se": a.se, "lo": a.lo,
                     "hi": a.hi, "n_treated_sales": int(len(grp)),
                     "dose": float(grp.dose_dlnA.mean())})
        draws[sid] = a.draws
    return pd.DataFrame(rows), draws


def elasticity(st: pd.DataFrame, draws: dict) -> dict:
    """WLS through the origin of station ATT on station dose; DerSimonian-Laird heterogeneity."""
    st = st[st.dose > 0.05].copy()  # stations with no measurable access gain carry no dose signal
    w, x, y = st.n_treated_sales.to_numpy(float), st.dose.to_numpy(), st.att.to_numpy()
    eps = float((w * x * y).sum() / (w * x * x).sum())
    D = np.column_stack([draws[s] for s in st.station_id])
    eps_draws = (D * (w * x)).sum(1) / (w * x * x).sum()
    ei, vi = y / x, (st.se.to_numpy() / x) ** 2
    wi = 1 / vi
    fixed = (wi * ei).sum() / wi.sum()
    Q = float((wi * (ei - fixed) ** 2).sum())
    tau2 = max(0.0, (Q - (len(ei) - 1)) / (wi.sum() - (wi ** 2).sum() / wi.sum()))
    lo, hi = np.quantile(eps_draws, [0.025, 0.975])
    return {"elasticity": eps, "lo": float(lo), "hi": float(hi), "se": float(np.std(eps_draws)),
            "tau_between_station": float(np.sqrt(tau2)), "Q": Q, "k_stations": int(len(ei)),
            "draws": eps_draws.tolist()}


def dose_response(s, d, xi, event_max, bins: int = 3) -> list[dict]:
    t = d.ring == "treated"
    station_dose = d[t].groupby("station_id").dose_dlnA.mean()
    q = pd.qcut(station_dose, bins, labels=False, duplicates="drop")
    out = []
    for b in sorted(q.unique()):
        ids = q.index[q == b]
        mask = (s.g == NEVER) | d.station_id.isin(ids).to_numpy() | ~t.to_numpy()
        a = csdid.overall_post(csdid.att_gt(prepare.subset(s, mask), event_max=event_max), xi)
        out.append({"bin": int(b), "dose_mean": float(station_dose[ids].mean()),
                    "dose_min": float(station_dose[ids].min()), "dose_max": float(station_dose[ids].max()),
                    "att": a.estimate, "lo": a.lo, "hi": a.hi, "stations": list(ids)})
    return out


def run_estimation(pap: dict) -> dict:
    e, inf = pap["estimator"], pap["inference"]
    emax = e["event_max"]
    frame = primary_frame(pap)
    s, d = prepare.to_sample(frame, pap)
    xi = csdid.multipliers(s.n_clusters, inf["draws"], inf["seed"])
    cells = csdid.att_gt(s, e["event_min"], emax, e["min_cell"], e["control_group"])
    es = csdid.event_study(cells, xi, e["event_min"], emax)
    post = csdid.overall_post(cells, xi, emax)
    es.to_csv(RES / "event_study_primary.csv", index=False)
    pd.DataFrame([{"g": c.g, "t": c.t, "att": c.att, "n_treated": c.n_treated,
                   "n_control": c.n_control} for c in cells]).to_csv(RES / "att_gt_primary.csv", index=False)

    # spillover ring on its own, against the same controls
    ss, _ = prepare.to_sample(frame, pap, treated_ring="spillover")
    xs = csdid.multipliers(ss.n_clusters, inf["draws"], inf["seed"] + 1)
    sp_cells = csdid.att_gt(ss, e["event_min"], emax, e["min_cell"])
    sp = csdid.overall_post(sp_cells, xs, emax)
    es_sp = csdid.event_study(sp_cells, xs, e["event_min"], emax)
    es_sp.to_csv(RES / "event_study_spillover.csv", index=False)

    st, st_draws = station_estimates(s, d, xi, emax)
    st.to_csv(RES / "station_estimates.csv", index=False)
    el = elasticity(st, st_draws)
    dr = dose_response(s, d, xi, emax)

    # specification curve over pre-registered alternates
    spec = [{"spec": "primary (funding, not-yet, covariates)", "estimate": post.estimate,
             "lo": post.lo, "hi": post.hi, "elasticity": el["elasticity"]}]
    for m in pap["treatment"]["cohort_alternates"]:
        sa, da = prepare.to_sample(primary_frame(pap, m), pap)
        xa = csdid.multipliers(sa.n_clusters, 499, inf["seed"] + 7)
        ca = csdid.att_gt(sa, e["event_min"], emax, e["min_cell"])
        a = csdid.overall_post(ca, xa, emax)
        sta, dra = station_estimates(sa, da, xa, emax)
        spec.append({"spec": f"cohort date = {m}", "estimate": a.estimate, "lo": a.lo, "hi": a.hi,
                     "elasticity": elasticity(sta, dra)["elasticity"]})
    a = csdid.overall_post(csdid.att_gt(s, e["event_min"], emax, e["min_cell"], "never"), xi, emax)
    spec.append({"spec": "never-treated controls only", "estimate": a.estimate, "lo": a.lo, "hi": a.hi,
                 "elasticity": None})
    no_plan = (d.ring != "planned_area").to_numpy()
    a = csdid.overall_post(csdid.att_gt(prepare.subset(s, no_plan), e["event_min"], emax, e["min_cell"]),
                           xi, emax)
    spec.append({"spec": "controls exclude West Seattle planned areas", "estimate": a.estimate,
                 "lo": a.lo, "hi": a.hi, "elasticity": None})
    sn = csdid.Sample(y=s.y, year=s.year, g=s.g, cluster=s.cluster, X=s.X[:, :1], block=s.block)
    a = csdid.overall_post(csdid.att_gt(sn, e["event_min"], emax, e["min_cell"]), xi, emax)
    spec.append({"spec": "no covariates", "estimate": a.estimate, "lo": a.lo, "hi": a.hi,
                 "elasticity": None})

    res = {"primary": {k: getattr(post, k) for k in ("estimate", "se", "lo", "hi")},
           "spillover": {k: getattr(sp, k) for k in ("estimate", "se", "lo", "hi")},
           "n_sales": int(len(s.y)), "n_treated_sales": int((s.g < NEVER).sum()),
           "n_clusters": int(s.n_clusters), "n_cells": len(cells),
           "cohorts": sorted({int(c.g) for c in cells}),
           "elasticity": {k: v for k, v in el.items() if k != "draws"},
           "dose_response": dr, "spec_curve": spec}
    _dump(res, "estimates.json")
    np.save(RES / "elasticity_draws.npy", np.array(el["draws"]))
    np.save(RES / "primary_post_draws.npy", post.draws)
    return res


def run_falsification(pap: dict) -> dict:
    e, inf, f = pap["estimator"], pap["inference"], pap["falsification"]
    emax = e["event_max"]
    d = primary_frame(pap)
    s, d = prepare.to_sample(d, pap)
    xi = csdid.multipliers(s.n_clusters, inf["draws"], inf["seed"])
    cells = csdid.att_gt(s, e["event_min"], emax, e["min_cell"])
    post = csdid.overall_post(cells, xi, emax)
    es = csdid.event_study(cells, xi, e["event_min"], emax)
    parcel = gpd.read_parquet(PROCESSED / "dim_parcel.parquet", columns=["pin", "geometry"])
    coords = pd.DataFrame({"pin": parcel.pin, "x": parcel.geometry.x, "y": parcel.geometry.y})
    xy = d[["pin"]].merge(coords, on="pin", how="left")[["x", "y"]].to_numpy()
    zoning = pd.read_parquet(PROCESSED / "dim_zoning.parquet")
    pe, ps = f["planted_effect"], f["placebo_stations"]
    steps = [
        lambda: falsify.planted_effect(s, d, e["covariates"], pe["effect"], pe["runs"],
                                       pe["min_coverage"], emax, inf["seed"] + 100),
        lambda: falsify.pretrend_bounds(es, post, f["pretrend_bounds"]["mbar"], emax, inf["alpha"]),
        lambda: falsify.placebo_stations(s, d, xy, post, ps["replicates"], ps["ring_m"],
                                         ps["central_share"], emax, inf["seed"] + 200),
        lambda: falsify.placebo_date(s, f["placebo_date"]["shift_years"], f["placebo_date"]["horizon"],
                                     inf["seed"] + 300),
        lambda: falsify.rezoning_split(zoning),
        lambda: falsify.composition(s, d, f["composition"]["outcomes"],
                                    f["composition"]["max_abs_std_effect"], emax, inf["seed"] + 400),
        lambda: falsify.leave_one_station_out(s, d, post, emax, xi),
    ]
    tests = []
    for k, step in enumerate(steps, 1):
        t0 = time.time()
        tests.append(step())
        print(f"  test {k}/{len(steps)} {tests[-1]['test']}: passed={tests[-1]['passed']} "
              f"({time.time() - t0:.0f}s)", flush=True)
    _dump(tests, "falsification.json")
    return {"tests": tests}

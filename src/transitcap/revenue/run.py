"""Revenue steps: planned-corridor base, break-even effect, Monte Carlo, tornado, incidence."""

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from transitcap.build.access import block_points
from transitcap.build.walk import to_utm
from transitcap.estimate.prepare import sales_frame
from transitcap.paths import OUTPUTS, PROCESSED, RAW
from transitcap.revenue import bridge, model

RES = OUTPUTS / "results"


def _dump(obj, name):
    (RES / name).write_text(json.dumps(obj, indent=2, default=float))


def planned_base(pap: dict) -> tuple[model.Base, pd.DataFrame, dict]:
    ta = pd.read_parquet(PROCESSED / "treatment_assignment.parquet")
    ta = ta[ta.milestone == "funding"]
    st = pd.read_parquet(PROCESSED / "dim_station.parquet", columns=["station_id", "status"])
    ws = st.loc[st.status == "planned", "station_id"].tolist()
    zone = ta[ta.cluster_station.isin(ws) & (ta.nearest_walk_min <= pap["rings"]["treated_max"])]
    av = bridge.load_av()
    year = bridge.current_tax_year(av)
    cur = av[av.tax_year == year].assign(total=lambda v: v.land_val + v.imps_val)
    parcel = gpd.read_parquet(PROCESSED / "dim_parcel.parquet",
                              columns=["pin", "present_use", "assessor_area", "sqft_lot", "geometry"])
    z = parcel.merge(zone, on="pin").merge(cur[["pin", "total", "land_val"]], on="pin")
    z = z[z.total > 0].reset_index(drop=True)

    sales = sales_frame(pap)
    ratio = bridge.assessment_ratio(sales, av)
    ratio = ratio[ratio["size"] >= 200]
    a = float(ratio.loc[ratio.sale_year == ratio.sale_year.max(), "median"].iloc[0])
    controls = ta.loc[ta.ring == "control", "pin"]
    growth = bridge.background_growth(av, controls, 2000, year)
    base = model.Base(market_value=z.total.to_numpy(float) / a, assessed=z.total.to_numpy(float),
                      dose=z.dose_dlnA_planned.to_numpy(float), station=z.cluster_station.to_numpy(),
                      walk_min=z.nearest_walk_min.to_numpy(float),
                      single_family=z.present_use.isin(pap["outcome"]["present_use"]).to_numpy(),
                      in_lid_zone=np.ones(len(z), bool), assessment_ratio=a, growth=growth)
    meta = {"tax_year": year, "assessment_ratio": a, "background_growth": growth,
            "zone_parcels": int(len(z)), "zone_single_family": int(base.single_family.sum()),
            "zone_assessed_value": float(z.total.sum()),
            "zone_sf_assessed_value": float(z.total[base.single_family].sum()),
            "dose_mean_sf": float(base.dose[base.single_family].mean()),
            "assessment_ratio_by_year": ratio.to_dict("records")}
    return base, z, meta


def median_params(pap: dict) -> dict:
    p = model.draw_params(pap, 20001, seed=1)
    m = {k: np.array([np.median(v)]) for k, v in p.items()}
    m["lag"] = np.array([int(np.median(p["lag"]))])
    return m


def breakeven(pap: dict, base: model.Base) -> dict:
    """Smallest elasticity at which an instrument reaches the materiality threshold at central
    parameter values, and the matching effect on the completed corridor."""
    thr = pap["materiality"]["threshold"]
    m = median_params(pap)
    out = {}
    for inst in ("lid", "tia"):
        f = lambda e: model.simulate(base, np.array([e]), m, pap)[f"{inst}_funding_ratio"][0] - thr  # noqa: E731
        lo, hi = 0.0, 1.0
        if f(hi) < 0:
            out[inst] = None  # not reachable at any plausible elasticity
            continue
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
        out[inst] = hi
    reachable = {k: v for k, v in out.items() if v is not None}
    best = min(reachable, key=reachable.get) if reachable else None
    power = json.loads((RES / "power.json").read_text())
    res = {"threshold": thr, "elasticity_needed": out, "best_instrument": best,
           "best_elasticity_needed": reachable.get(best) if best else None,
           "completed_corridor_dose_mean": power["treated_dose_mean"]}
    res["breakeven_att_completed_corridor"] = (res["best_elasticity_needed"] * power["treated_dose_mean"]
                                               if best else None)
    res["mde_log_points"] = power["mde_log_points"]
    res["corridor_can_answer"] = bool(best) and power["mde_log_points"] <= res["breakeven_att_completed_corridor"]
    _dump(res, "breakeven.json")
    return res


def land_split(pap: dict, z: pd.DataFrame) -> dict:
    av = bridge.load_av()
    assessor = bridge.assessor_land_share(av, z.pin, bridge.current_tax_year(av))
    s = pd.read_parquet(PROCESSED / "fact_sales.parquet")
    parcel = pd.read_parquet(PROCESSED / "dim_parcel.parquet",
                             columns=["pin", "assessor_area", "present_use", "sqft_lot"])
    improved = sales_frame(pap)
    improved = improved[improved.assessor_area.isin(z.assessor_area.unique())]
    vac = bridge.vacant_land_share(s, improved, parcel, pap)
    recent = vac[vac.sale_year >= vac.sale_year.max() - 4]
    sf = z.present_use.isin(pap["outcome"]["present_use"])
    return {"assessor_median_land_share_sf": float(assessor.reindex(z.pin[sf]).median()),
            "vacant_sales_median_land_share_sf": float(recent.land_share_vacant.median()) if len(recent) else None,
            "vacant_sales_n_improved_matched": int(len(recent)),
            "vacant_sales_n_area_periods": int(vac[["assessor_area", "sale_year"]].drop_duplicates().shape[0]),
            "note": "assessor split is formula-driven; vacant-sales share uses area-by-5-year medians"}


def incidence(pap: dict, base: model.Base, z: gpd.GeoDataFrame, eps_med: float, p_med: dict) -> pd.DataFrame:
    """Block-group incidence of the LID at central values: charge as a share of median income."""
    blocks = block_points()
    blocks = blocks[blocks.block.str.startswith("53033")]
    bxy = to_utm(blocks.lon.to_numpy(), blocks.lat.to_numpy())
    _, k = cKDTree(bxy).query(np.column_stack([z.geometry.x, z.geometry.y]))
    z = z.assign(bg=blocks.block.str[:12].to_numpy()[k])
    gain = base.market_value * np.expm1(eps_med * base.dose)
    rv = pap["revenue"]["lid"]
    r = float(p_med["rate"][0])
    charge = np.where(base.single_family, np.maximum(gain, 0) * p_med["lid_capture"][0]
                      * (1 + p_med["lid_eta"][0]), 0)
    annual = charge * r / (1 - (1 + r) ** -rv["payment_years"])
    z = z.assign(charge=charge, annual=annual)
    inc = pd.read_csv(RAW / "census" / "acs5y2022_b19013.dat", sep="|", dtype=str)
    inc = inc[inc.GEO_ID.str.startswith("1500000US53033")]
    inc = pd.DataFrame({"bg": inc.GEO_ID.str[-12:],
                        "median_hh_income": pd.to_numeric(inc.B19013_E001, errors="coerce")})
    ten = pd.read_csv(RAW / "census" / "acs5y2022_b25003.dat", sep="|", dtype=str)
    ten = ten[ten.GEO_ID.str.startswith("1500000US53033")]
    ten = pd.DataFrame({"bg": ten.GEO_ID.str[-12:],
                        "owner_share": pd.to_numeric(ten.B25003_E002, errors="coerce")
                        / pd.to_numeric(ten.B25003_E001, errors="coerce")})
    g = (z[base.single_family].groupby("bg")
         .agg(parcels=("pin", "size"), mean_charge=("charge", "mean"), mean_annual=("annual", "mean"))
         .reset_index().merge(inc, on="bg", how="left").merge(ten, on="bg", how="left"))
    g["annual_share_of_median_income"] = g.mean_annual / g.median_hh_income
    g.to_csv(RES / "incidence_block_group.csv", index=False)
    return g


def run_revenue(pap: dict) -> dict:
    base, z, meta = planned_base(pap)
    m = pap["materiality"]
    est = json.loads((RES / "estimates.json").read_text())
    rng = np.random.default_rng(m["seed"])
    eps_boot = np.load(RES / "elasticity_draws.npy")
    tau = est["elasticity"]["tau_between_station"]
    n = m["monte_carlo_draws"]
    eps = rng.choice(eps_boot, n) + rng.normal(0, tau, n)
    p = model.draw_params(pap, n, m["seed"] + 1)
    out = model.simulate(base, eps, p, pap)
    summary = {"base": meta, "elasticity_draws": {"median": float(np.median(eps)),
                                                  "p10": float(np.quantile(eps, .1)),
                                                  "p90": float(np.quantile(eps, .9)),
                                                  "share_negative": float(np.mean(eps < 0))},
               "tia_area_base_av": out["tia_area_base_av"], "tia_area_parcels": out["tia_area_parcels"],
               "lid_zone_parcels": out["lid_zone_parcels"], "instruments": {}}
    for inst in ("lid", "tia", "package"):
        ratio = out[f"{inst}_funding_ratio"]
        summary["instruments"][inst] = {
            "pv_net_median": float(np.median(out[f"{inst}_pv_net"])),
            "pv_net_p10": float(np.quantile(out[f"{inst}_pv_net"], .1)),
            "pv_net_p90": float(np.quantile(out[f"{inst}_pv_net"], .9)),
            "funding_ratio_median": float(np.median(ratio)),
            "funding_ratio_p10": float(np.quantile(ratio, .1)),
            "funding_ratio_p90": float(np.quantile(ratio, .9)),
            "p_material": float(np.mean(ratio >= m["threshold"])),
            "bands": model.band_probabilities(ratio, m["bands"]),
            "bankability_q10_by_year": model.bankability(out[f"{inst}_annual_net"], out["debt_service"],
                                                          m["bankability_quantile"], m["bankability_years"]),
        }
    summary["instruments"]["tia"]["pv_gross_median"] = float(np.median(out["tia_pv_gross"]))
    summary["instruments"]["tia"]["net_share_of_gross_median"] = float(
        np.median(out["tia_pv_net"] / out["tia_pv_gross"]))
    proj = []
    for s in sorted(set(base.station.tolist())):
        m_ = (base.station == s) & base.single_family
        g = {q: float((base.market_value[m_] * np.expm1(np.quantile(eps, q) * base.dose[m_])).sum())
             for q in (0.1, 0.5, 0.9)}
        proj.append({"station_id": s, "parcels": int(m_.sum()), "dose_mean": float(base.dose[m_].mean()),
                     "gain_p10": g[0.1], "gain_p50": g[0.5], "gain_p90": g[0.9]})
    summary["station_projection"] = proj
    best = max(("lid", "tia"), key=lambda k: summary["instruments"][k]["p_material"])
    summary["best_instrument"] = best
    summary["tornado"] = model.tornado(base, eps, p, pap, best)
    summary["land_split"] = land_split(pap, z)
    med = median_params(pap)
    inc = incidence(pap, base, z, float(np.median(eps)), med)
    summary["incidence"] = {"block_groups": int(len(inc)),
                            "median_annual_share": float(inc.annual_share_of_median_income.median()),
                            "max_annual_share": float(inc.annual_share_of_median_income.max()),
                            "median_charge_usd": float(inc.mean_charge.median())}
    _dump(summary, "revenue.json")
    return summary

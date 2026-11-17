"""Build the ten minimum tables (spec: Minimum viable data) into data/processed as (Geo)Parquet.

dim_parcel, fact_sales, fact_assessed_value, dim_station, gtfs_history, parcel_access,
treatment_assignment, dim_zoning, dim_lvc_instrument, fact_project_finance.

Raw files are read, never modified. Every table is validated against build.schemas before write.
"""

import json

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd

from transitcap.build import access, rail, schemas
from transitcap.build.walk import WalkGraph, station_frame
from transitcap.config import load_pap
from transitcap.ingest import parcels
from transitcap.paths import CRS_METRIC, INTERIM, PROCESSED, REFERENCE

KC = INTERIM / "kc_assessor"
NEVER = 10_000


def _write(df: pd.DataFrame, name: str) -> None:
    schemas.validate(df, name)
    if isinstance(df, gpd.GeoDataFrame):
        df.to_parquet(PROCESSED / f"{name}.parquet")
    else:
        df.to_parquet(PROCESSED / f"{name}.parquet", index=False)


def build_dim_parcel(con: duckdb.DuckDBPyConnection) -> gpd.GeoDataFrame:
    pts = parcels.load_centroids()
    con.register("pins", pd.DataFrame({"pin": pts.pin}))
    attrs = con.sql(f"""
        select lpad(trim(Major),6,'0')||lpad(trim(Minor),4,'0') as pin,
               trim(Area) as assessor_area, trim(PresentUse) as present_use,
               try_cast(SqFtLot as bigint) as sqft_lot, trim(CurrentZoning) as zoning,
               trim(LevyCode) as levy_code, trim(DistrictName) as district,
               (try_cast(MtRainier as int) + try_cast(Olympics as int) + try_cast(Cascades as int)
                + try_cast(Territorial as int) + try_cast(SeattleSkyline as int)
                + try_cast(PugetSound as int) + try_cast(LakeWashington as int)
                + try_cast(LakeSammamish as int) + try_cast(SmallLakeRiverCreek as int)
                + try_cast(OtherView as int)) > 0 as has_view,
               coalesce(try_cast(WfntLocation as int), 0) > 0 as waterfront
        from read_csv('{KC / "EXTR_Parcel.csv"}', all_varchar=true)
        where lpad(trim(Major),6,'0')||lpad(trim(Minor),4,'0') in (select pin from pins)
    """).df()
    gdf = pts.merge(attrs, on="pin", how="left")
    gdf.attrs = pts.attrs
    return gdf


def build_fact_sales(con: duckdb.DuckDBPyConnection, pap: dict) -> pd.DataFrame:
    o = pap["outcome"]
    inst = ",".join(f"'{x}'" for x in o["sale_instruments"])
    return con.sql(f"""
        with s as (
          select trim(ExciseTaxNbr) as excise_nbr,
                 lpad(trim(Major),6,'0')||lpad(trim(Minor),4,'0') as pin,
                 try_strptime(DocumentDate, '%m/%d/%Y')::date as sale_date,
                 try_cast(SalePrice as bigint) as price,
                 trim(PrincipalUse) as principal_use, trim(PropertyClass) as property_class,
                 trim(PropertyType) as property_type, trim(SaleInstrument) as sale_instrument,
                 trim(SaleReason) as sale_reason, trim(SaleWarning) as sale_warning
          from read_csv('{KC / "EXTR_RPSale.csv"}', all_varchar=true)
        ), s2 as (
          select *, count(distinct pin) over (partition by excise_nbr) as n_parcels_in_sale
          from s
        )
        select s2.*, year(sale_date) as sale_year,
               (principal_use = '{o["principal_use"]}' and property_class = '{o["property_class"]}'
                and sale_instrument in ({inst}) and sale_reason = '{o["sale_reason"]}'
                and coalesce(sale_warning, '') = '' and price >= {o["min_price_usd"]}
                and n_parcels_in_sale = 1) as arms_length
        from s2
        where pin in (select pin from pins) and sale_date is not null
          and year(sale_date) between {o["first_year"]} and {o["last_year"]}
    """).df()


def build_buildings(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Single-building parcels only; characteristics are the current snapshot."""
    return con.sql(f"""
        with b as (
          select lpad(trim(Major),6,'0')||lpad(trim(Minor),4,'0') as pin,
                 try_cast(SqFtTotLiving as double) as sqft_living,
                 try_cast(YrBuilt as int) as yr_built, try_cast(YrRenovated as int) as yr_renovated,
                 try_cast(BldgGrade as int) as grade, try_cast(Bedrooms as int) as bedrooms,
                 try_cast(BathFullCount as double) + 0.75 * try_cast(Bath3qtrCount as double)
                   + 0.5 * try_cast(BathHalfCount as double) as bathrooms,
                 try_cast(Condition as int) as condition
          from read_csv('{KC / "EXTR_ResBldg.csv"}', all_varchar=true)
        )
        select * from b where pin in (select pin from pins)
          and pin in (select pin from b group by pin having count(*) = 1)
    """).df()


def build_fact_assessed_value(con: duckdb.DuckDBPyConnection, first_year: int) -> pd.DataFrame:
    """One row per parcel-year: the most recent value record for that tax year."""
    return con.sql(f"""
        with v as (
          select lpad(trim(Major),6,'0')||lpad(trim(Minor),4,'0') as pin,
                 try_cast(TaxYr as int) as tax_year,
                 try_cast(LandVal as bigint) as land_val, try_cast(ImpsVal as bigint) as imps_val,
                 try_cast(ChangeDate as timestamp) as change_date
          from read_csv('{KC / "EXTR_ValueHistory_V.csv"}', all_varchar=true)
        )
        select pin, tax_year, arg_max(land_val, change_date) as land_val,
               arg_max(imps_val, change_date) as imps_val
        from v where pin in (select pin from pins) and tax_year >= {first_year}
        group by pin, tax_year
    """).df()


def load_stations() -> pd.DataFrame:
    st = pd.read_csv(REFERENCE / "station_milestones.csv")
    for m in ("announce", "funding", "construction", "open"):
        st[f"{m}_date"] = pd.to_datetime(st[f"{m}_date"])
        st[f"{m}_year"] = st[f"{m}_date"].dt.year
    return st


def build_dim_station() -> pd.DataFrame:
    st = load_stations()
    g = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lon, st.lat), crs="EPSG:4326")
    return g


def assign_treatment(walk: np.ndarray, st: pd.DataFrame, pap: dict, milestone: str) -> pd.DataFrame:
    """Ring, cohort and cluster for each parcel, for one cohort milestone."""
    r = pap["rings"]
    excluded = set(pap["treatment"]["excluded_stations"])
    is_open = (st.status == "open").to_numpy()
    year = st[f"{milestone}_year"].to_numpy(dtype=float)
    w = np.where(np.isnan(walk), np.inf, walk)
    near = (w <= r["spillover_max"]) & is_open[None, :]
    # earliest station (by milestone) within the spillover ring decides cohort and ring
    key = np.where(near, year[None, :], np.inf)
    first = np.argmin(key, axis=1)
    has = np.isfinite(key[np.arange(len(w)), first])
    d_first = w[np.arange(len(w)), first]
    nearest_any = np.argmin(w, axis=1)
    d_any = w[np.arange(len(w)), nearest_any]
    ring = np.full(len(w), "outside", dtype=object)
    ring[(d_any >= r["control_min"]) & (d_any <= r["control_max"])] = "control"
    planned = (~is_open)[nearest_any] & (d_any < r["control_min"])
    ring[planned & ~has] = "planned_area"
    ring[has & (d_first <= r["treated_max"])] = "treated"
    ring[has & (d_first > r["treated_max"])] = "spillover"
    station = np.where(has, st.station_id.to_numpy()[first], None)
    exc = has & np.isin(station.astype(str), list(excluded))
    ring[exc] = "excluded_station"
    cohort = np.where(has, year[first], NEVER).astype(int)
    cohort[~has] = NEVER
    return pd.DataFrame({"ring": ring, "station_id": station, "walk_min": np.where(has, d_first, d_any),
                         "cohort": cohort, "cluster_station": st.station_id.to_numpy()[nearest_any],
                         "nearest_walk_min": d_any})


def network_dates(st: pd.DataFrame, first_year: int, last_year: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(f"{y}-07-01") for y in range(first_year, last_year + 1)]


def build_access(dim_parcel: gpd.GeoDataFrame, walk: np.ndarray, st: pd.DataFrame, pap: dict,
                 sample: np.ndarray):
    """parcel_access (origin-cell grain, mapped to parcels) and per-parcel dose."""
    tt = rail.load_timetable()
    sxy = station_frame(st)
    xy_by_id = dict(zip(st.station_id, sxy))
    speed = rail.observed_speed(tt, xy_by_id)
    ws = st.loc[st.status == "planned", "station_id"].tolist()
    order = sorted(ws, key=lambda s: -xy_by_id[s][0])  # east to west: Delridge then Junction
    tt_plan = rail.add_planned_line(tt, "WS", [pap["transfer"]["planned_connection"], *order],
                                    xy_by_id, speed, pap["transfer"]["planned_headway_min"])
    open_date = dict(zip(st.station_id, st.open_date))
    ids = st.station_id.tolist()

    pts = np.column_stack([dim_parcel.geometry.x, dim_parcel.geometry.y])[sample]
    cell = np.floor(pts / 100.0).astype(np.int64)
    ckey = cell[:, 0] * 1_000_000 + cell[:, 1]
    uniq, inv = np.unique(ckey, return_inverse=True)
    oxy = (np.column_stack([uniq // 1_000_000, uniq % 1_000_000]) + 0.5) * 100.0
    ow = np.full((len(uniq), walk.shape[1]), np.nan, dtype=np.float32)
    ws_ = walk[sample]
    for k in range(walk.shape[1]):  # per-cell median walk time to each station
        s = pd.Series(ws_[:, k]).groupby(inv).median()
        ow[s.index.to_numpy(), k] = s.to_numpy()

    jobs = access.job_cells(pap["dose"]["jobs_year"])
    acc = access.Accessibility(jobs, sxy)
    direct = acc.direct_jobs(oxy)
    cache: dict[tuple, np.ndarray] = {}

    def jobs_on(date: pd.Timestamp, timetable=tt, extra_open: dict | None = None) -> np.ndarray:
        od = {**open_date, **(extra_open or {})}
        state = tuple(sorted(s for s in ids if od.get(s, pd.Timestamp.max) <= date)) + \
            (("WS",) if extra_open else ())
        if state not in cache:
            cache[state] = acc.total_jobs(oxy, ow, rail.travel_matrix(timetable, od, date, ids), direct)
        return cache[state]

    o = pap["outcome"]
    yearly = {d.year: jobs_on(d) for d in network_dates(st, o["first_year"], o["last_year"])}
    now = pd.Timestamp("2026-11-01")
    plan_open = {s: now for s in ws}
    with_ws = jobs_on(now, tt_plan, plan_open)
    return inv, yearly, with_ws, jobs_on, cache


def build_all() -> None:
    pap = load_pap()
    con = duckdb.connect(str(INTERIM / "transitcap.duckdb"))
    dim_parcel = build_dim_parcel(con)
    con.register("pins", pd.DataFrame({"pin": dim_parcel.pin}))
    _write(dim_parcel, "dim_parcel")

    st = load_stations()
    _write(build_dim_station(), "dim_station")

    sales = build_fact_sales(con, pap)
    bld = build_buildings(con)
    sales = sales.merge(bld, on="pin", how="left")
    _write(sales, "fact_sales")
    _write(build_fact_assessed_value(con, pap["outcome"]["first_year"]), "fact_assessed_value")

    graph = WalkGraph()
    pxy = np.column_stack([dim_parcel.geometry.x, dim_parcel.geometry.y])
    walk = graph.minutes_to_stations(station_frame(st), pxy)
    np.save(INTERIM / "walk_minutes.npy", walk)

    ta = []
    for m in ["funding", *pap["treatment"]["cohort_alternates"]]:
        a = assign_treatment(walk, st, pap, m)
        a.insert(0, "pin", dim_parcel.pin.to_numpy())
        a.insert(1, "milestone", m)
        ta.append(a)
    ta = pd.concat(ta, ignore_index=True)

    # accessibility for parcels in any analysis ring or planned area
    prim = ta[ta.milestone == "funding"].reset_index(drop=True)
    sample = prim.ring.isin(["treated", "spillover", "control", "planned_area"]).to_numpy()
    inv, yearly, with_ws, jobs_on, cache = build_access(dim_parcel, walk, st, pap, sample)
    pins = dim_parcel.pin.to_numpy()[sample]
    pa = pd.concat([pd.DataFrame({"pin": pins, "year": y, "jobs_45min": v[inv]})
                    for y, v in yearly.items()], ignore_index=True)
    pa_ws = pd.DataFrame({"pin": pins, "year": 2035, "jobs_45min": with_ws[inv]})
    pa_ws["scenario"] = "with_west_seattle"
    pa["scenario"] = "observed_network"
    _write(pd.concat([pa, pa_ws], ignore_index=True), "parcel_access")

    # dose: change in log access at the opening of the parcel's assigning station
    od = dict(zip(st.station_id, st.open_date))
    dose = np.zeros(len(prim))
    sub = prim[sample].reset_index(drop=True)
    for sid, idx in sub.groupby("station_id").groups.items():
        d0 = od[sid] - pd.Timedelta(days=1)
        before, after = jobs_on(d0)[inv[idx]], jobs_on(od[sid])[inv[idx]]
        dose[np.flatnonzero(sample)[idx]] = np.log(after) - np.log(before)
    planned_dose = np.log(with_ws) - np.log(jobs_on(pd.Timestamp("2026-11-01")))
    dose_planned = np.zeros(len(prim))
    dose_planned[np.flatnonzero(sample)] = planned_dose[inv]
    ta["dose_dlnA"] = np.tile(dose, len(ta) // len(prim))
    ta["dose_dlnA_planned"] = np.tile(dose_planned, len(ta) // len(prim))
    _write(ta, "treatment_assignment")

    gh = pd.DataFrame([{"feed_version": "SC-Fall-2026.6", "agency": "Sound Transit",
                        "start": "2026-11-01", "end": "2027-03-26",
                        "method": "observed", "n_network_states": len(cache),
                        "note": "historical networks reconstructed by masking unopened stations"}])
    _write(gh, "gtfs_history")

    z = dim_parcel[["pin", "zoning"]].copy()
    z["period_start"], z["change_date"] = pd.NaT, pd.NaT
    z["source"] = "EXTR_Parcel CurrentZoning snapshot; no change history available"
    _write(pd.DataFrame(z), "dim_zoning")
    _write(pd.read_csv(REFERENCE / "lvc_instruments.csv"), "dim_lvc_instrument")
    _write(pd.read_csv(REFERENCE / "project_finance.csv"), "fact_project_finance")

    (PROCESSED / "build_log.json").write_text(json.dumps({
        "n_parcels": int(len(dim_parcel)), "n_repaired_geometries": dim_parcel.attrs.get("n_repaired"),
        "n_sales": int(len(sales)), "n_arms_length": int(sales.arms_length.sum()),
        "n_walk_unsnapped": int(np.isnan(walk).all(axis=1).sum()),
        "jobs_unmatched_blocks": None, "n_network_states": len(cache),
        "crs_metric": CRS_METRIC,
    }, indent=2))


if __name__ == "__main__":
    build_all()

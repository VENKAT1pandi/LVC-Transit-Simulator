"""Data for the dashboard's geospatial layers: the West Seattle parcel twin, a corridor grid with
yearly job access, household-burden block groups, and the constant that ties the page's what-if
panel to the revenue model.

The what-if panel recomputes LID revenue in the browser. At fixed non-elasticity parameters the
model's LID present value is linear in capture share and in the positive part of the aggregate
causal gain, so pv = K * capture * max(B(eps), 0) with B(eps) = sum over single-family zone
parcels of market_value * (exp(eps * dose) - 1). K is taken from `model.simulate` at the plan's
median parameters and checked against it at two elasticities.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import box

from transitcap.build.access import block_points
from transitcap.build.walk import to_utm
from transitcap.paths import CRS_GEO, CRS_METRIC, OUTPUTS, PROCESSED, RAW
from transitcap.revenue import model
from transitcap.revenue.run import median_params, planned_base

CELL_M = 300
RINGS = ("treated", "spillover", "control", "planned_area")


def _round_coords(geojson: dict, nd: int = 5) -> dict:
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], float) else [r(x) for x in c]
    for f in geojson["features"]:
        f["geometry"]["coordinates"] = r(f["geometry"]["coordinates"])
    return geojson


def _parcel_polygons(pins: set, xy: np.ndarray) -> gpd.GeoDataFrame:
    """Polygons for the given PINs from the cached county pages, reading only tiles in range."""
    x0, y0 = xy.min(axis=0) - 2000
    x1, y1 = xy.max(axis=0)
    feats = []
    for path in sorted(Path(RAW / "kc_parcels").glob("tile_*.json")):
        _, tx, ty, _ = path.stem.split("_")
        if not (x0 <= int(tx) <= x1 and y0 <= int(ty) <= y1):
            continue
        for f in json.loads(path.read_text()).get("features", []):
            if str(f["properties"].get("PIN")) in pins and f.get("geometry"):
                feats.append(f)
    g = gpd.GeoDataFrame.from_features(feats, crs=CRS_METRIC).rename(columns={"PIN": "pin"})
    g["pin"] = g.pin.astype(str)
    g = g.drop_duplicates("pin")[["pin", "geometry"]]
    g["geometry"] = g.geometry.buffer(0).simplify(0.5)
    return g


def lid_constant(pap: dict, base: model.Base) -> dict:
    m = median_params(pap)
    one = dict(m, lid_capture=np.array([1.0]))
    sf = base.single_family & base.in_lid_zone
    ks = []
    for e in (0.03, 0.08):
        B = float((base.market_value[sf] * np.expm1(e * base.dose[sf])).sum())
        ks.append(model.simulate(base, np.array([e]), one, pap)["lid_pv_net"][0] / B)
    if not np.isclose(ks[0], ks[1], rtol=1e-9):
        raise AssertionError("LID PV is not linear in the aggregate gain; the what-if panel would be wrong")
    rv = pap["revenue"]["lid"]
    return {"K": ks[0], "capture_median": float(m["lid_capture"][0]), "eta": float(m["lid_eta"][0]),
            "rate": float(m["rate"][0]), "payment_years": rv["payment_years"],
            "capture_range": rv["capture_share"], "gap_median": float(m["gap"][0]),
            "gap_range": pap["finance"]["funding_gap_usd"], "threshold": pap["materiality"]["threshold"]}


def west_seattle(pap: dict) -> tuple[dict, dict, dict]:
    """Parcel twin, burden block groups and the LID constant for the planned stations."""
    base, z, meta = planned_base(pap)
    tia = model.tia_areas(base, pap["gates"]["tia_max_area_av_usd"], pap["gates"]["tia_max_areas"])
    xy = np.column_stack([z.geometry.x, z.geometry.y])
    blocks = block_points()
    blocks = blocks[blocks.block.str.startswith("53033")]
    _, k = cKDTree(to_utm(blocks.lon.to_numpy(), blocks.lat.to_numpy())).query(xy)
    bg = blocks.block.str[:12].to_numpy()[k]
    attrs = pd.DataFrame({"pin": z.pin.astype(str), "mv": base.market_value.round(0), "av": z.total,
                          "dose": base.dose.round(4), "sf": base.single_family.astype(int),
                          "tia": tia.astype(int), "st": base.station, "walk": base.walk_min.round(1),
                          "bg": bg})
    poly = _parcel_polygons(set(attrs.pin), xy).merge(attrs, on="pin")
    missing = len(attrs) - len(poly)
    poly = poly.to_crs(CRS_GEO)
    parcels = _round_coords(json.loads(poly.to_json(drop_id=True)), 6)

    inc = pd.read_csv(OUTPUTS / "results" / "incidence_block_group.csv",
                      dtype={"bg": str})
    tb = gpd.read_file(f"zip://{RAW / 'census' / 'tl_2020_53_tabblock20.zip'}", engine="pyogrio",
                       columns=["GEOID20"], where="GEOID20 LIKE '53033%'")
    tb["bg"] = tb.GEOID20.str[:12]
    bgs = tb[tb.bg.isin(inc.bg)].dissolve("bg").reset_index()[["bg", "geometry"]]
    bgs = bgs.merge(inc[["bg", "median_hh_income", "owner_share"]], on="bg").to_crs(CRS_GEO)
    bgs["geometry"] = bgs.geometry.simplify(0.00005)
    burden = _round_coords(json.loads(bgs.to_json(drop_id=True)))
    lid = lid_constant(pap, base) | {"parcels_without_polygon": int(missing),
                                     "tax_year": meta["tax_year"]}
    return parcels, burden, lid


def service_years() -> pd.DataFrame:
    """First year a station counts as open on the access layer, which samples the network on
    1 July (`build.tables.network_dates`), and its funding year (the study's treatment date)."""
    st = pd.read_parquet(PROCESSED / "dim_station.parquet", columns=["station_id", "funding_date", "open_date"])
    d = st.open_date
    st["service_year"] = d.dt.year + (d > pd.to_datetime(d.dt.year.astype(str) + "-07-01")).astype(int)
    st["funding_year"] = st.funding_date.dt.year.fillna(9999).astype(int)
    return st[["station_id", "service_year", "funding_year"]]


def corridor_grid(pap: dict) -> tuple[dict, list[int]]:
    """300 m cells over every ringed parcel: majority ring, the opening year of the cell's
    nearest station (so the page can show a ring only once its station is open) and mean jobs
    reachable by year."""
    ta = pd.read_parquet(PROCESSED / "treatment_assignment.parquet",
                         columns=["pin", "milestone", "ring", "cluster_station"])
    ta = ta[(ta.milestone == "funding") & ta.ring.isin(RINGS)]
    p = gpd.read_parquet(PROCESSED / "dim_parcel.parquet", columns=["pin", "geometry"]).merge(ta, on="pin")
    cx = (p.geometry.x // CELL_M).astype(int)
    cy = (p.geometry.y // CELL_M).astype(int)
    st = service_years().set_index("station_id")
    p = pd.DataFrame({"pin": p.pin, "ring": p.ring, "cell": cx.astype(str) + "_" + cy.astype(str),
                      "open": p.cluster_station.map(st.service_year),
                      "fund": p.cluster_station.map(st.funding_year)})
    open_year = p.groupby("cell").open.median()
    fund_year = p.groupby("cell").fund.median()
    ring = (p.groupby(["cell", "ring"]).size().rename("n").reset_index()
            .sort_values("n", ascending=False).drop_duplicates("cell").set_index("cell").ring)
    n = p.groupby("cell").size()
    acc = pd.read_parquet(PROCESSED / "parcel_access.parquet", filters=[("scenario", "=", "observed_network")],
                          columns=["pin", "year", "jobs_45min"]).merge(p[["pin", "cell"]], on="pin")
    jobs = acc.groupby(["cell", "year"]).jobs_45min.mean().unstack("year")
    years = [int(y) for y in jobs.columns]
    cells = n.index.to_series().str.split("_", expand=True).astype(int)
    geoms = [box(i * CELL_M, j * CELL_M, (i + 1) * CELL_M, (j + 1) * CELL_M) for i, j in cells.to_numpy()]
    g = gpd.GeoDataFrame({"ring": ring.reindex(n.index).to_numpy(), "n": n.to_numpy(),
                          "open": open_year.reindex(n.index).fillna(9999).astype(int).to_numpy(),
                          "fund": fund_year.reindex(n.index).fillna(9999).astype(int).to_numpy()},
                         index=n.index, geometry=geoms, crs=CRS_METRIC)
    j = jobs.reindex(n.index).fillna(0).round(-1).astype(int)
    g["jobs"] = [json.dumps(v) for v in j.to_numpy().tolist()]
    g = g[g.n >= 3].to_crs(CRS_GEO)
    out = json.loads(g.to_json(drop_id=True))
    for f in out["features"]:
        f["properties"]["jobs"] = json.loads(f["properties"]["jobs"])
    jy = jobs.reindex(n.index).fillna(0).mean()
    changed = [y for a, y in zip(years, years[1:]) if abs(jy[y] - jy[a]) > 1]
    if not set(changed) <= set(service_years().service_year):
        raise AssertionError("access changes in a year with no station opening; service_years is wrong")
    return _round_coords(out), years

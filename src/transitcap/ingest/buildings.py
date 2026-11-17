"""Building footprints for the dashboard's 3D view.

- Microsoft Global ML Building Footprints: machine-mapped outlines with an estimated height
  (-1 when unknown). The zoom-9 quadkey files covering the corridor are cached unmodified in
  data/raw/ms_buildings/.
- OpenStreetMap buildings from the Geofabrik extract, with `height` or `building:levels` when mapped.

Output: data/interim/buildings.parquet (EPSG:4326) with one row per building or building part:
height and base height in metres, whether the height was measured, taken from the storey count,
estimated or defaulted, and the source.
"""

import gzip
import json
import math

import geopandas as gpd
import osmium
import pandas as pd
import requests
from shapely import STRtree, wkb
from shapely.geometry import shape

from transitcap.ingest.osm import PBF, corridor_bbox
from transitcap.paths import CRS_GEO, INTERIM, RAW

MS_INDEX = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
MS_DIR = RAW / "ms_buildings"
LEVEL_M = 3.2       # metres per storey when only the storey count is mapped
DEFAULT_M = 6.0     # a two-storey house when nothing is known


def _quadkeys(bbox: tuple[float, float, float, float], z: int = 9) -> set[str]:
    def tile(lon, lat):
        n = 2 ** z
        return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    w, s, e, n_ = bbox
    (x0, y1), (x1, y0) = tile(w, s), tile(e, n_)
    return {"".join(str(((x >> (z - i)) & 1) + (((y >> (z - i)) & 1) << 1)) for i in range(1, z + 1))
            for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def fetch_microsoft() -> list:
    MS_DIR.mkdir(parents=True, exist_ok=True)
    idx = MS_DIR / "dataset-links.csv"
    if not idx.exists():
        idx.write_bytes(requests.get(MS_INDEX, timeout=120).content)
    links = pd.read_csv(idx, dtype=str)
    want = links[(links.Location == "UnitedStates") & links.QuadKey.isin(_quadkeys(corridor_bbox()))]
    paths = []
    for r in want.itertuples():
        path = MS_DIR / f"{r.QuadKey}.csv.gz"
        if not path.exists():
            with requests.get(r.Url, timeout=600, stream=True) as resp:
                resp.raise_for_status()
                path.write_bytes(resp.content)
        paths.append(path)
    return paths


def microsoft(paths) -> gpd.GeoDataFrame:
    w, s, e, n = corridor_bbox()
    geoms, heights = [], []
    for path in paths:
        with gzip.open(path, "rt") as f:
            for line in f:
                feat = json.loads(line)
                g = shape(feat["geometry"])
                x, y = g.representative_point().coords[0]
                if w <= x <= e and s <= y <= n:
                    geoms.append(g)
                    heights.append(float(feat["properties"].get("height", -1)))
    return gpd.GeoDataFrame({"ms_height": heights}, geometry=geoms, crs=CRS_GEO)


def _metres(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v.lower().replace("m", "").replace("'", "").strip().split(";")[0])
    except ValueError:
        return None


def osm() -> gpd.GeoDataFrame:
    """Building outlines and building parts (towers are often mapped as parts with their own
    height and base height)."""
    w, s, e, n = corridor_bbox()
    factory = osmium.geom.WKBFactory()
    rows = []
    keys = osmium.filter.KeyFilter("building", "building:part")
    for obj in osmium.FileProcessor(str(PBF)).with_areas(keys).with_filter(keys):
        if not obj.is_area():
            continue
        try:
            first = next(iter(next(iter(obj.outer_rings()))))
            if not (w <= first.lon <= e and s <= first.lat <= n):
                continue
            g = wkb.loads(factory.create_multipolygon(obj), hex=True)
        except (RuntimeError, StopIteration, osmium.InvalidLocationError):
            continue
        t = obj.tags
        levels, min_level = _metres(t.get("building:levels")), _metres(t.get("building:min_level"))
        base = _metres(t.get("min_height"))
        rows.append({"part": "building:part" in t and t.get("building:part") != "no" and "building" not in t,
                     "osm_height": _metres(t.get("height")),
                     "osm_levels_m": levels * LEVEL_M if levels else None,
                     "base_m": base if base is not None else (min_level * LEVEL_M if min_level else 0.0),
                     "geometry": g})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_GEO)


def extract() -> gpd.GeoDataFrame:
    """OSM buildings where mapped; Microsoft outlines fill the gaps.

    Following OSM's Simple 3D Buildings rule, an outline that contains building parts is replaced
    by its parts. Height preference: OSM height tag, then OSM storeys x 3.2 m, then Microsoft's
    estimate (machine-learned; it runs low on towers), then a 6 m default."""
    o = osm()
    parts, outlines = o[o.part].reset_index(drop=True), o[~o.part].reset_index(drop=True)
    p_in, o_has = STRtree(outlines.geometry.values).query(
        parts.geometry.representative_point().values, predicate="within")
    o = pd.concat([outlines.drop(outlines.index[sorted(set(o_has))]), parts], ignore_index=True)
    m = microsoft(fetch_microsoft())
    pts = m.geometry.representative_point()
    ms_i, osm_i = STRtree(o.geometry.values).query(pts.values, predicate="within")
    m_new = m.drop(m.index[sorted(set(ms_i))])  # Microsoft outline already mapped in OSM
    # OSM buildings take the Microsoft height of any Microsoft building whose centre they contain
    ms_h = pd.Series(m.ms_height.to_numpy()[ms_i], index=osm_i)
    ms_h = ms_h[ms_h > 0].groupby(level=0).max()
    o["ms_height"] = ms_h.reindex(range(len(o))).to_numpy()

    def pick(measured, levels, ms):
        h = measured.copy()
        kind = pd.Series(["measured"] * len(h), index=h.index).where(h.notna())
        for src, label in ((levels, "storeys"), (ms.where(ms > 0), "estimated")):
            fill = h.isna() & src.notna()
            h[fill], kind[fill] = src[fill], label
        kind[h.isna()] = "default"
        return h.fillna(DEFAULT_M), kind

    nan = pd.Series(float("nan"), index=m_new.index)
    oh, ok = pick(o.osm_height, o.osm_levels_m, o.ms_height)
    mh, mk = pick(nan, nan, m_new.ms_height)
    out = pd.concat([
        gpd.GeoDataFrame({"height_m": oh.round(1), "base_m": o.base_m.fillna(0).round(1).to_numpy(),
                          "height_kind": ok, "source": "openstreetmap"}, geometry=o.geometry.values, crs=CRS_GEO),
        gpd.GeoDataFrame({"height_m": mh.round(1), "base_m": 0.0, "height_kind": mk, "source": "microsoft"},
                         geometry=m_new.geometry.values, crs=CRS_GEO)], ignore_index=True)
    out = out[out.height_m.between(2, 330) & (out.base_m < out.height_m)]  # tallest Seattle tower: 284 m
    INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_parquet(INTERIM / "buildings.parquet")
    return out


if __name__ == "__main__":  # pragma: no cover
    b = extract()
    print(b.groupby(["source", "height_kind"]).size())

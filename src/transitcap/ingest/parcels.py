"""Fetch King County parcel polygons near Link stations from the county's public ArcGIS service.

Only parcels inside a square tile grid covering a buffer around each station are requested,
because the full county layer (about 640,000 polygons) is not needed. Each response page is
cached unmodified under data/raw/kc_parcels so the fetch is idempotent and auditable.
"""

import json
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

from transitcap.paths import CRS_GEO, CRS_METRIC, RAW, REFERENCE

SERVICE = "https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_Parcels/MapServer/0/query"
PAGE = 1000
TILE_M = 2000


def tiles_around_stations(radius_m: float) -> list[tuple[float, float, float, float]]:
    st = pd.read_csv(REFERENCE / "station_milestones.csv")
    st = st[st.county == "King"]
    pts = gpd.GeoSeries(gpd.points_from_xy(st.lon, st.lat), crs=CRS_GEO).to_crs(CRS_METRIC)
    area = pts.buffer(radius_m).unary_union
    minx, miny, maxx, maxy = area.bounds
    tiles = []
    x = minx - minx % TILE_M
    while x < maxx:
        y = miny - miny % TILE_M
        while y < maxy:
            box = gpd.GeoSeries.from_xy([x, x + TILE_M], [y, y + TILE_M], crs=CRS_METRIC)
            if area.intersects(box.unary_union.envelope):
                tiles.append((x, y, x + TILE_M, y + TILE_M))
            y += TILE_M
        x += TILE_M
    return tiles


def _get(params: dict) -> dict:
    for attempt in range(5):
        try:
            r = requests.get(SERVICE, params=params, timeout=120,
                             headers={"User-Agent": "transitcap-prototype/0.1"})
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception:  # network errors are retried, then re-raised
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch(radius_m: float = 3500) -> None:
    out = RAW / "kc_parcels"
    out.mkdir(parents=True, exist_ok=True)
    for (x0, y0, x1, y1) in tiles_around_stations(radius_m):
        offset = 0
        while True:
            path = out / f"tile_{int(x0)}_{int(y0)}_{offset}.json"
            if path.exists():
                data = json.loads(path.read_text())
            else:
                data = _get({
                    "where": "1=1", "geometry": f"{x0},{y0},{x1},{y1}",
                    "geometryType": "esriGeometryEnvelope", "inSR": 32610,
                    "spatialRel": "esriSpatialRelIntersects", "outFields": "PIN,MAJOR,MINOR",
                    "returnGeometry": "true", "outSR": 32610, "geometryPrecision": 1,
                    "orderByFields": "OBJECTID", "resultOffset": offset,
                    "resultRecordCount": PAGE, "f": "geojson",
                })
                path.write_text(json.dumps(data))
            n = len(data.get("features", []))
            if n < PAGE:
                break
            offset += PAGE


def load_centroids() -> gpd.GeoDataFrame:
    """One row per PIN: centroid and polygon area in metres. Tile overlaps are deduplicated."""
    rows = []
    for path in sorted((RAW / "kc_parcels").glob("tile_*.json")):
        for f in json.loads(path.read_text()).get("features", []):
            if f.get("geometry") is None:
                continue
            rows.append((f["properties"]["PIN"], shape(f["geometry"])))
    gdf = gpd.GeoDataFrame(rows, columns=["pin", "geometry"], crs=CRS_METRIC)
    gdf = gdf[gdf.pin.notna()]
    invalid = ~gdf.geometry.is_valid
    gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)
    gdf = gdf.drop_duplicates("pin")  # a parcel spanning two tiles arrives twice
    gdf["parcel_area_m2"] = gdf.geometry.area
    gdf["geometry"] = gdf.geometry.representative_point()  # always inside the polygon
    gdf.attrs["n_repaired"] = int(invalid.sum())
    return gdf


if __name__ == "__main__":
    fetch()

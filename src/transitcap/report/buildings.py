"""Vector tiles of building footprints for the dashboard's 3D view.

Buildings are kept within a 40-minute walk's straight-line reach (3.3 km) of any King County
station, in the map's 300 m cells, or inside a West Seattle zone parcel. Tiles are Mapbox Vector
Tiles (spec v2) in outputs/atlas/buildings/{z}/{x}/{y}.pbf for zooms 12-14, one layer "b" with
height `h` and base height `b` in metres and `ws` = 1 inside the West Seattle zone, where the parcel layer takes over.
The map overzooms past 14. Below zoom 12 a 100 m tower is under 4 pixels tall, so the region view
keeps the 300 m cells instead.

The encoder is written here with vectorised shapely/numpy because the reference library takes
about 3 ms per building (95 minutes for this corridor); `tests/test_buildings.py` checks the two
decode to the same footprints.
"""

import shutil

import geopandas as gpd
import numpy as np
import shapely
from mapbox_vector_tile.Mapbox import vector_tile_pb2
from shapely import STRtree

from transitcap.paths import CRS_GEO, CRS_METRIC, INTERIM, OUTPUTS

ORIGIN = 20037508.342789244
ZOOMS = {12: (2.0, 60.0), 13: (1.0, 0.0), 14: (0.0, 0.0)}  # zoom: (simplify m, min footprint m2)
EXTENT, BUFFER = 4096, 64
REACH_M = 3300


def _zz(v: np.ndarray) -> np.ndarray:
    return (v << 1) ^ (v >> 31)


def encode(geoms, props: dict[str, np.ndarray], bounds) -> bytes:
    """Encode polygons (already clipped to the buffered tile) with integer properties."""
    x0, y0, x1, y1 = bounds
    tile = vector_tile_pb2.tile()
    layer = tile.layers.add()
    layer.name, layer.version, layer.extent = "b", 2, EXTENT
    keys = list(props)
    layer.keys.extend(keys)
    vals = sorted({int(v) for a in props.values() for v in a})
    vidx = {v: i for i, v in enumerate(vals)}
    for v in vals:
        layer.values.add().int_value = v

    parts, feat_of_part = shapely.get_parts(geoms, return_index=True)
    poly = shapely.get_type_id(parts) == 3
    parts, feat_of_part = parts[poly], feat_of_part[poly]
    rings, part_of_ring = shapely.get_rings(parts, return_index=True)
    exterior = np.r_[True, part_of_ring[1:] != part_of_ring[:-1]]
    xy, ring_of_pt = shapely.get_coordinates(rings, return_index=True)
    q = np.empty(xy.shape, dtype=np.int64)
    q[:, 0] = np.round((xy[:, 0] - x0) / (x1 - x0) * EXTENT)
    q[:, 1] = np.round((y1 - xy[:, 1]) / (y1 - y0) * EXTENT)
    starts = np.r_[0, np.flatnonzero(np.diff(ring_of_pt)) + 1]

    cmds: dict[int, list[int]] = {}
    pen: dict[int, np.ndarray] = {}  # MVT deltas run across all rings of a feature
    for r, (s, e) in enumerate(zip(starts, np.r_[starts[1:], len(q)])):
        pts = q[s:e - 1]  # drop the repeated closing point
        pts = pts[np.r_[True, np.any(pts[1:] != pts[:-1], axis=1)]]
        if len(pts) < 3:
            continue
        area = np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
        if area == 0:
            continue
        if (area > 0) != bool(exterior[r]):  # exterior rings positive in y-down tile space
            pts = pts[::-1]
        f = int(feat_of_part[part_of_ring[r]])
        zz = _zz(np.diff(np.vstack([pen.get(f, np.zeros(2, np.int64)), pts]), axis=0)).ravel().tolist()
        cmds.setdefault(f, []).extend([9, zz[0], zz[1], 2 | ((len(pts) - 1) << 3), *zz[2:], 15])
        pen[f] = pts[-1]
    for f, c in cmds.items():
        feat = layer.features.add()
        feat.type = 3
        feat.tags.extend([t for i, k in enumerate(keys) for t in (i, vidx[int(props[k][f])])])
        feat.geometry.extend(c)
    return tile.SerializeToString()


def write(grid: dict, parcels: dict, stations: dict) -> list[float]:
    """Write the tiles; return [west, south, east, north] for the map source."""
    b = gpd.read_parquet(INTERIM / "buildings.parquet")
    pts = b.geometry.representative_point()
    shape = lambda fc: [shapely.geometry.shape(f["geometry"]) for f in fc["features"]]  # noqa: E731
    reach = gpd.GeoSeries(shape(stations), crs=CRS_GEO).to_crs(CRS_METRIC).buffer(REACH_M).to_crs(CRS_GEO)
    ws = shapely.union_all(shape(parcels))
    area = shapely.union_all(shape(grid) + list(reach.values) + [ws])
    b = b[shapely.contains_xy(area, pts.x.values, pts.y.values)].reset_index(drop=True)
    rp = b.geometry.representative_point()
    b["ws"] = shapely.contains_xy(ws, rp.x.values, rp.y.values).astype(int)
    b["h"] = b.height_m.round().astype(int)
    b["b"] = b.base_m.round().astype(int)
    m = b.to_crs(3857)
    out = OUTPUTS / "atlas" / "buildings"
    shutil.rmtree(out, ignore_errors=True)
    minx, miny, maxx, maxy = m.total_bounds
    for z, (tol, min_area) in ZOOMS.items():
        g = m[m.geometry.area >= min_area]
        geoms = g.geometry.simplify(tol).values if tol else g.geometry.values
        tree, h, base, wsf = STRtree(geoms), g.h.to_numpy(), g.b.to_numpy(), g.ws.to_numpy()
        size = 2 * ORIGIN / 2 ** z
        pad = size * BUFFER / EXTENT
        for x in range(int((minx + ORIGIN) // size), int((maxx + ORIGIN) // size) + 1):
            for y in range(int((ORIGIN - maxy) // size), int((ORIGIN - miny) // size) + 1):
                x0, y1 = -ORIGIN + x * size, ORIGIN - y * size
                x1, y0 = x0 + size, y1 - size
                idx = tree.query(shapely.box(x0 - pad, y0 - pad, x1 + pad, y1 + pad))
                if not len(idx):
                    continue
                clipped = shapely.clip_by_rect(geoms[idx], x0 - pad, y0 - pad, x1 + pad, y1 + pad)
                path = out / str(z) / str(x) / f"{y}.pbf"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encode(clipped, {"h": h[idx], "b": base[idx], "ws": wsf[idx]}, (x0, y0, x1, y1)))
    w, s, e, n = b.to_crs(CRS_GEO).total_bounds
    return [float(np.round(v, 5)) for v in (w, s, e, n)]

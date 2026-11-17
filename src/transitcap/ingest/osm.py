"""Extract the pedestrian street network around the stations from the Geofabrik Washington extract.

Output: data/interim/walk_edges.parquet with one row per street segment (lon/lat of both ends).
Ways tagged as motorways, construction, or foot=no / access=private are excluded.
"""

import numpy as np
import osmium
import pandas as pd

from transitcap.paths import INTERIM, RAW, REFERENCE

PBF = RAW / "osm" / "washington-latest.osm.pbf"
NOT_WALKABLE = {"motorway", "motorway_link", "trunk_link", "construction", "proposed",
                "raceway", "bus_guideway", "abandoned", "platform"}
MARGIN_DEG = 0.05  # about 4 km of latitude beyond the outermost station


def corridor_bbox() -> tuple[float, float, float, float]:
    st = pd.read_csv(REFERENCE / "station_milestones.csv")
    st = st[st.county == "King"]
    return (st.lon.min() - MARGIN_DEG, st.lat.min() - MARGIN_DEG,
            st.lon.max() + MARGIN_DEG, st.lat.max() + MARGIN_DEG)


def extract() -> pd.DataFrame:
    w, s, e, n = corridor_bbox()
    rows = []
    fp = (osmium.FileProcessor(str(PBF))
          .with_locations()
          .with_filter(osmium.filter.KeyFilter("highway")))
    for obj in fp:
        if not obj.is_way():
            continue
        tags = obj.tags
        if tags.get("highway") in NOT_WALKABLE or tags.get("foot") == "no" \
                or tags.get("access") in ("private", "no"):
            continue
        try:
            pts = [(nd.ref, nd.lon, nd.lat) for nd in obj.nodes]
        except osmium.InvalidLocationError:
            continue
        if not any(w <= lon <= e and s <= lat <= n for _, lon, lat in pts):
            continue
        for (a, ax, ay), (b, bx, by) in zip(pts[:-1], pts[1:]):
            if a != b:
                rows.append((a, ax, ay, b, bx, by))
    df = pd.DataFrame(rows, columns=["a", "ax", "ay", "b", "bx", "by"])
    df[["ax", "ay", "bx", "by"]] = df[["ax", "ay", "bx", "by"]].astype(np.float64)
    df.to_parquet(INTERIM / "walk_edges.parquet")
    return df


if __name__ == "__main__":
    print(len(extract()), "walkable segments")

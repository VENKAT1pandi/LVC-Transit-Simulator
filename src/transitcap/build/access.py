"""Job accessibility by walk + Link light rail within a 45-minute budget (the treatment dose).

A(o, D) = jobs reachable from origin o on network date D, where a job cell j is reached if
    walk_direct(o, j) <= 45  or  min_s,s' [walk(o, s) + rail(s, s'; D) + walk(s', j)] <= 45.

- walk(o, s): OSM network walk (build.walk), at most 41 minutes.
- rail: build.rail.travel_matrix, including half-headway wait and transfers.
- walk(s', j) and walk_direct: straight line x 1.3 detour at 80 m/min; egress capped at 20 minutes.
- Jobs: LODES 8 workplace area characteristics, all jobs (C000), at 2020 census-block internal
  points, aggregated to a 200 m grid. Jobs are held at one year so the dose reflects the network
  change only, not job relocation that the station may itself cause (ADR-0002).
"""

import gzip
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from transitcap.build.walk import WALK_M_PER_MIN, to_utm
from transitcap.paths import INTERIM, RAW

BUDGET_MIN = 45.0
DETOUR = 1.3
EGRESS_MAX_MIN = 20.0
CELL_M = 200.0


def block_points() -> pd.DataFrame:
    cache = INTERIM / "blocks_53.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    path = RAW / "census" / "tl_2020_53_tabblock20.zip"
    with zipfile.ZipFile(path):
        pass  # fail early on a corrupt archive
    g = gpd.read_file(f"zip://{path}", engine="pyogrio", ignore_geometry=True,
                      columns=["GEOID20", "INTPTLAT20", "INTPTLON20"])
    df = pd.DataFrame({"block": g.GEOID20, "lat": g.INTPTLAT20.astype(float),
                       "lon": g.INTPTLON20.astype(float)})
    df.to_parquet(cache)
    return df


def job_cells(year: int) -> pd.DataFrame:
    with gzip.open(RAW / "lodes" / f"wa_wac_S000_JT00_{year}.csv.gz", "rt") as f:
        wac = pd.read_csv(f, usecols=["w_geocode", "C000"], dtype={"w_geocode": str})
    b = block_points().merge(wac, left_on="block", right_on="w_geocode", how="inner")
    xy = to_utm(b.lon.to_numpy(), b.lat.to_numpy())
    b["cx"] = (np.floor(xy[:, 0] / CELL_M) + 0.5) * CELL_M
    b["cy"] = (np.floor(xy[:, 1] / CELL_M) + 0.5) * CELL_M
    cells = b.groupby(["cx", "cy"], as_index=False).C000.sum().rename(columns={"C000": "jobs"})
    cells.attrs["unmatched_blocks"] = int(len(wac) - len(b))
    return cells


class Accessibility:
    def __init__(self, jobs: pd.DataFrame, station_xy: np.ndarray):
        self.cxy = jobs[["cx", "cy"]].to_numpy()
        self.jobs = jobs.jobs.to_numpy(dtype=float)
        self.tree = cKDTree(self.cxy)
        reach_m = EGRESS_MAX_MIN * WALK_M_PER_MIN / DETOUR
        triples = []
        for s, xy in enumerate(station_xy):
            idx = self.tree.query_ball_point(xy, reach_m)
            d = np.hypot(*(self.cxy[idx] - xy).T)
            triples += [(s, j, dj * DETOUR / WALK_M_PER_MIN) for j, dj in zip(idx, d)]
        t = np.array(triples)
        self.eg_station = t[:, 0].astype(int)
        self.eg_cell = t[:, 1].astype(int)
        self.eg_min = t[:, 2]
        self.direct_m = BUDGET_MIN * WALK_M_PER_MIN / DETOUR

    def direct_jobs(self, origin_xy: np.ndarray) -> np.ndarray:
        idx = self.tree.query_ball_point(origin_xy, self.direct_m)
        return np.array([self.jobs[i].sum() for i in idx])

    def total_jobs(self, origin_xy: np.ndarray, walk_min: np.ndarray, rail: np.ndarray,
                   direct: np.ndarray, chunk: int = 2000) -> np.ndarray:
        """walk_min: [O, S] network walk minutes (NaN = unreachable); rail: [S, S] minutes."""
        w = np.where(np.isnan(walk_min), np.inf, walk_min)
        out = direct.astype(float).copy()
        cells = np.unique(self.eg_cell)
        pos = np.searchsorted(cells, self.eg_cell)
        order = np.argsort(pos, kind="stable")
        starts = np.r_[0, np.flatnonzero(np.diff(pos[order])) + 1]
        cell_xy, cell_jobs = self.cxy[cells], self.jobs[cells]
        for k in range(0, len(origin_xy), chunk):
            wk = w[k:k + chunk]
            # arrival time at each alighting station: min over boarding stations
            arrive = np.min(wk[:, :, None] + rail[None, :, :], axis=1)        # [o, S]
            t = arrive[:, self.eg_station[order]] + self.eg_min[order][None]  # [o, triples]
            best = np.minimum.reduceat(t, starts, axis=1)                    # [o, cells]
            far = np.hypot(origin_xy[k:k + chunk, None, 0] - cell_xy[None, :, 0],
                           origin_xy[k:k + chunk, None, 1] - cell_xy[None, :, 1]) > self.direct_m
            out[k:k + chunk] += ((best <= BUDGET_MIN) & far) @ cell_jobs
        return out

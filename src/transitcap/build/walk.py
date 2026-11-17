"""Network walk times from every point of interest to every station, on the OSM pedestrian graph.

Walk speed is 80 m/min (4.8 km/h). Distances are computed in UTM 10N metres.
A point more than SNAP_MAX_M from the nearest graph node has no network time (NaN), which
makes it fall out of the rings rather than silently receiving a straight-line estimate.
"""

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from transitcap.paths import INTERIM

WALK_M_PER_MIN = 80.0
SNAP_MAX_M = 150.0
_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32610", always_xy=True)


class WalkGraph:
    def __init__(self) -> None:
        e = pd.read_parquet(INTERIM / "walk_edges.parquet")
        ends = pd.concat([e[["a", "ax", "ay"]].set_axis(["id", "lon", "lat"], axis=1),
                          e[["b", "bx", "by"]].set_axis(["id", "lon", "lat"], axis=1)])
        nodes = ends.drop_duplicates("id").reset_index(drop=True)
        self.xy = to_utm(nodes.lon.to_numpy(), nodes.lat.to_numpy())
        index = pd.Series(np.arange(len(nodes)), index=nodes.id)
        i, j = index[e.a].to_numpy(), index[e.b].to_numpy()
        length = np.hypot(*(self.xy[i] - self.xy[j]).T)
        n = len(nodes)
        # duplicate segments are summed by tocsr(); take the minimum instead via sorted dedup
        key = np.minimum(i, j) * n + np.maximum(i, j)
        _, first = np.unique(key, return_index=True)
        i, j, length = i[first], j[first], length[first]
        self.graph = coo_matrix((np.r_[length, length], (np.r_[i, j], np.r_[j, i])),
                                shape=(n, n)).tocsr()
        # snap only to the largest connected component, so a point never lands on an isolated
        # fragment (a station platform or private path) and silently gets no walk times
        _, label = connected_components(self.graph, directed=False)
        main = np.flatnonzero(label == np.bincount(label).argmax())
        self.main_share = len(main) / n
        self._main = main
        self.tree = cKDTree(self.xy[main])

    def snap(self, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dist, k = self.tree.query(xy)
        return self._main[k], dist

    def minutes_to_stations(self, station_xy: np.ndarray, point_xy: np.ndarray,
                            limit_m: float = 3300.0) -> np.ndarray:
        """Matrix [n_points, n_stations] of walk minutes; NaN beyond limit_m or unsnappable."""
        s_node, s_snap = self.snap(station_xy)
        p_node, p_snap = self.snap(point_xy)
        metres = np.empty((len(point_xy), len(station_xy)))
        for k in range(0, len(s_node), 4):  # chunked: a dense [S, N] matrix would not fit in memory
            dist = dijkstra(self.graph, directed=False, indices=s_node[k:k + 4], limit=limit_m)
            metres[:, k:k + 4] = dist[:, p_node].T
        metres += p_snap[:, None] + s_snap[None, :]
        metres[~np.isfinite(metres) | (metres > limit_m)] = np.nan
        metres[p_snap > SNAP_MAX_M, :] = np.nan
        return (metres / WALK_M_PER_MIN).astype(np.float32)


def to_utm(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    x, y = _to_utm.transform(np.asarray(lon), np.asarray(lat))
    return np.column_stack([x, y])


def station_frame(stations: pd.DataFrame) -> np.ndarray:
    return to_utm(stations.lon.to_numpy(), stations.lat.to_numpy())

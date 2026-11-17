"""Link light rail network as it stood on any date, built from the current Sound Transit GTFS.

Archived GTFS from 2009-2024 is not openly available, so historical networks are reconstructed by
removing segments whose stations had not yet opened (decision record ADR-0002). Running times and
headways come from the current weekday timetable. Bus service is not modelled.

A station whose opening postdates both neighbours on the current pattern is an infill station
(Pinehurst): before it opens, trains run through it, so its neighbours stay connected.
"""

import io
import zipfile
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from transitcap.paths import RAW

LINK_ROUTES = {"100479": "1", "2LINE": "2"}
TRANSFER_WALK_MIN = 2.0


def _read(z: zipfile.ZipFile, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(z.read(name)), dtype=str, **kw)


def _secs(s: pd.Series) -> pd.Series:
    hms = s.str.split(":", expand=True).astype(int)
    return hms[0] * 3600 + hms[1] * 60 + hms[2]


@dataclass
class Timetable:
    patterns: dict[str, list[str]]           # line -> ordered station ids (one direction)
    run_min: dict[tuple[str, str], float]   # undirected consecutive pair -> minutes
    headway_min: dict[str, float]           # line -> weekday midday headway


def load_timetable(path=RAW / "gtfs" / "st_40_gtfs.zip") -> Timetable:
    with zipfile.ZipFile(path) as z:
        stops = _read(z, "stops.txt")[["stop_id", "parent_station"]]
        trips = _read(z, "trips.txt")
        cal = _read(z, "calendar.txt")
        st = _read(z, "stop_times.txt", usecols=["trip_id", "stop_id", "arrival_time",
                                                  "departure_time", "stop_sequence"])
    weekday = cal.loc[cal.wednesday == "1", "service_id"]
    trips = trips[trips.route_id.isin(LINK_ROUTES) & trips.service_id.isin(weekday)]
    x = (st.merge(trips[["trip_id", "route_id", "direction_id"]], on="trip_id")
           .merge(stops, on="stop_id"))
    x["seq"] = x.stop_sequence.astype(int)
    x["arr"], x["dep"] = _secs(x.arrival_time), _secs(x.departure_time)
    x = x.sort_values(["trip_id", "seq"])

    patterns, headway = {}, {}
    for rid, line in LINK_ROUTES.items():
        xr = x[(x.route_id == rid) & (x.direction_id == "0")]
        seqs = xr.groupby("trip_id").parent_station.agg(tuple)
        patterns[line] = list(seqs.value_counts().index[0])  # most common full pattern
        mid = patterns[line][len(patterns[line]) // 2]
        dep = np.sort(xr.loc[(xr.parent_station == mid) & xr.dep.between(10 * 3600, 15 * 3600), "dep"])
        headway[line] = float(np.median(np.diff(dep)) / 60)

    nxt = x.groupby("trip_id").shift(-1)
    pair = pd.DataFrame({"a": x.parent_station, "b": nxt.parent_station,
                         "t": (nxt.arr - x.dep) / 60}).dropna()
    pair["key"] = [tuple(sorted(k)) for k in zip(pair.a, pair.b)]
    run = pair.groupby("key").t.median().to_dict()
    return Timetable(patterns, run, headway)


def add_planned_line(tt: Timetable, line: str, stations: list[str], xy: dict[str, np.ndarray],
                     speed_m_per_min: float, headway_min: float) -> Timetable:
    """Add a hypothetical line; run time = 1.2 x straight-line distance at the given speed."""
    run = dict(tt.run_min)
    for a, b in zip(stations[:-1], stations[1:]):
        run[tuple(sorted((a, b)))] = 1.2 * float(np.hypot(*(xy[a] - xy[b]))) / speed_m_per_min
    return Timetable({**tt.patterns, line: stations}, run, {**tt.headway_min, line: headway_min})


def observed_speed(tt: Timetable, xy: dict[str, np.ndarray]) -> float:
    """Median station-to-station speed on the current network, metres per minute."""
    v = [float(np.hypot(*(xy[a] - xy[b]))) / t for (a, b), t in tt.run_min.items()
         if a in xy and b in xy and t > 0]
    return float(np.median(v))


def travel_matrix(tt: Timetable, open_date: dict[str, pd.Timestamp], on: pd.Timestamp,
                  stations: list[str]) -> np.ndarray:
    """Station-to-station minutes on date `on`, including the initial wait (half headway) and
    transfer penalties. Inf where no path. The diagonal is inf: staying at one station is walking,
    which the accessibility calculation counts separately."""
    is_open = {s: open_date.get(s, pd.Timestamp.max) <= on for s in stations}
    nodes: dict[tuple, int] = {}

    def nid(key):
        return nodes.setdefault(key, len(nodes))

    rows, cols, w = [], [], []

    def edge(a, b, c):
        rows.append(nid(a)), cols.append(nid(b)), w.append(c)

    for line, pat in tt.patterns.items():
        full_open = {s: open_date.get(s, pd.Timestamp.max) for s in pat}
        # a segment between consecutive *open* stations exists if every skipped station is infill
        kept = [s for s in pat if is_open.get(s, False)]
        for a, b in zip(kept[:-1], kept[1:]):
            i, j = pat.index(a), pat.index(b)
            infill_only = all(full_open[pat[k]] > max(full_open[pat[k - 1]], full_open[pat[k + 1]])
                              for k in range(i + 1, j))
            if not infill_only:
                continue
            t = sum(tt.run_min[tuple(sorted((pat[k], pat[k + 1])))] for k in range(i, j))
            edge((a, line), (b, line), t), edge((b, line), (a, line), t)
        for s in kept:
            edge(("src", s), (s, line), tt.headway_min[line] / 2)
            edge((s, line), ("dst", s), 0.0)
            for other, pat2 in tt.patterns.items():
                if other != line and s in pat2:
                    edge((s, line), (s, other), TRANSFER_WALK_MIN + tt.headway_min[other] / 2)
    n = len(nodes)
    g = coo_matrix((w, (rows, cols)), shape=(n, n)).tocsr()
    out = np.full((len(stations), len(stations)), np.inf)
    src = [nodes.get(("src", s)) for s in stations]
    dst = [nodes.get(("dst", s)) for s in stations]
    have = [i for i, k in enumerate(src) if k is not None]
    if have:
        d = dijkstra(g, indices=[src[i] for i in have])
        for r, i in enumerate(have):
            for j, k in enumerate(dst):
                if k is not None:
                    out[i, j] = d[r, k]
    np.fill_diagonal(out, np.inf)
    return out

"""The fast building-tile encoder must decode to the same footprints as the reference library."""

import mapbox_vector_tile
import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape

from transitcap.report.buildings import encode

BOUNDS = (0.0, 0.0, 1000.0, 1000.0)


def _decoded(blob: bytes) -> list[tuple[dict, object]]:
    layer = mapbox_vector_tile.decode(blob)["b"]
    return [(f["properties"], shape(f["geometry"])) for f in layer["features"]]


def test_matches_reference_encoder():
    courtyard = Polygon([(100, 100), (400, 100), (400, 400), (100, 400)],
                        [[(200, 200), (300, 200), (300, 300), (200, 300)]])
    two_part = MultiPolygon([Polygon([(500, 500), (600, 500), (600, 600)]),
                             Polygon([(700, 700), (800, 700), (800, 800), (700, 800)])])
    clockwise = Polygon([(900, 100), (900, 200), (980, 200), (980, 100)])
    over_edge = shapely.clip_by_rect(Polygon([(950, 950), (1050, 950), (1050, 1050), (950, 1050)]),
                                     -16, -16, 1016, 1016)
    geoms = np.array([courtyard, two_part, clockwise, over_edge], dtype=object)
    h = np.array([12, 30, 6, 9])
    ws = np.array([0, 1, 0, 0])
    ours = _decoded(encode(geoms, {"h": h, "ws": ws}, BOUNDS))
    ref = _decoded(mapbox_vector_tile.encode(
        [{"name": "b", "features": [{"geometry": g, "properties": {"h": int(a), "ws": int(b)}}
                                    for g, a, b in zip(geoms, h, ws)]}],
        default_options={"quantize_bounds": BOUNDS, "extents": 4096}))
    assert len(ours) == len(ref) == 4
    for (p1, g1), (p2, g2) in zip(ours, ref):
        assert p1 == p2
        assert g1.is_valid and g1.geom_type == g2.geom_type
        assert abs(g1.area - g2.area) < 1e-6 * max(g2.area, 1)
        assert g1.symmetric_difference(g2).area < 1e-6 * g2.area

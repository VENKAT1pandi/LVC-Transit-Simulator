import numpy as np
import pytest
import yaml

from transitcap.paths import CONFIG
from transitcap.revenue import model
from transitcap.revenue.bridge import land_effect

PAP = yaml.safe_load((CONFIG / "pap.yaml").read_text())


def _base(n=200, seed=0):
    rng = np.random.default_rng(seed)
    av = rng.uniform(4e5, 1.2e6, n)
    return model.Base(market_value=av / 0.9, assessed=av, dose=rng.uniform(0.5, 2.0, n),
                      station=np.where(np.arange(n) % 2 == 0, "WS1", "WS2"),
                      walk_min=rng.uniform(0, 10, n), single_family=rng.random(n) < 0.8,
                      in_lid_zone=np.ones(n, bool), assessment_ratio=0.9, growth=0.04)


def test_land_split_example_from_spec():
    assert land_effect(0.06, 0.40) == pytest.approx(0.15)


def test_zero_elasticity_gives_zero_net_revenue_but_positive_tia_gross():
    b = _base()
    p = model.draw_params(PAP, 50, seed=1)
    out = model.simulate(b, np.zeros(50), p, PAP)
    assert np.allclose(out["lid_pv_net"], 0) and np.allclose(out["tia_pv_net"], 0)
    assert (out["tia_pv_gross"] > 0).all()  # background growth is a transfer, not project revenue


def test_net_never_exceeds_gross_and_package_respects_overlap():
    b = _base()
    p = model.draw_params(PAP, 200, seed=2)
    out = model.simulate(b, np.full(200, 0.03), p, PAP)
    assert (out["tia_pv_net"] <= out["tia_pv_gross"] + 1e-6).all()
    assert (out["package_pv_net"] <= out["lid_pv_net"] + out["tia_pv_net"] + 1e-6).all()


def test_tia_area_respects_statutory_cap():
    b = _base(n=2000)
    mask = model.tia_areas(b, cap_usd=2e8, max_areas=2)
    for s in ("WS1", "WS2"):
        assert b.assessed[mask & (b.station == s)].sum() <= 2e8


def test_band_probabilities_sum_to_one():
    pr = model.band_probabilities(np.linspace(-0.1, 0.5, 1000), [0.05, 0.15, 0.30])
    assert sum(pr.values()) == pytest.approx(1.0)

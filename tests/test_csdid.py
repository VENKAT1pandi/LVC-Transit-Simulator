import numpy as np

from transitcap.estimate import csdid


def _synthetic(effect: float, seed: int, n_clusters: int = 40, n_per_year: int = 60):
    """Staggered adoption with selection on X and a common trend; true ATT = effect."""
    rng = np.random.default_rng(seed)
    years = np.arange(2000, 2016)
    cohort_of_cluster = rng.choice([2006, 2009, 2012, csdid.NEVER], size=n_clusters)
    rows = []
    for c in range(n_clusters):
        for t in years:
            x = rng.normal(0.3 if cohort_of_cluster[c] < csdid.NEVER else 0.0, 1, n_per_year)
            g = cohort_of_cluster[c]
            y = 12 + 0.5 * x + 0.03 * (t - 2000) + 0.1 * x * (t - 2000) / 10 \
                + rng.normal(0, 0.05) + rng.normal(0, 0.3, n_per_year)
            y = y + effect * (t >= g)
            rows += [(yy, t, g, c, xx) for yy, xx in zip(y, x)]
    a = np.array(rows, dtype=float)
    X = np.column_stack([np.ones(len(a)), a[:, 4]])
    return csdid.Sample(y=a[:, 0], year=a[:, 1].astype(int), g=a[:, 2].astype(int),
                        cluster=a[:, 3].astype(int), X=X, block=np.zeros(len(a), dtype=int))


def test_recovers_planted_effect_and_zero_pretrends():
    s = _synthetic(effect=0.08, seed=1)
    cells = csdid.att_gt(s)
    xi = csdid.multipliers(s.n_clusters, 499, seed=2)
    post = csdid.overall_post(cells, xi)
    assert abs(post.estimate - 0.08) < 0.03
    assert post.lo < 0.08 < post.hi
    es = csdid.event_study(cells, xi)
    pre = es[(es.e < -1) & es.att.notna()]
    assert (pre.att.abs() < 0.05).all()


def test_null_effect_interval_covers_zero():
    s = _synthetic(effect=0.0, seed=3)
    post = csdid.overall_post(csdid.att_gt(s), csdid.multipliers(s.n_clusters, 499, seed=4))
    assert post.lo < 0 < post.hi


def test_doubly_robust_corrects_selection_bias_in_levels():
    # treated units have higher x, hence higher levels; a naive mean comparison is biased
    s = _synthetic(effect=0.0, seed=5)
    treated_post = (s.g < csdid.NEVER) & (s.year >= s.g)
    naive = s.y[treated_post].mean() - s.y[~treated_post & (s.g == csdid.NEVER)].mean()
    post = csdid.overall_post(csdid.att_gt(s), csdid.multipliers(s.n_clusters, 99, seed=6))
    assert abs(post.estimate) < abs(naive)

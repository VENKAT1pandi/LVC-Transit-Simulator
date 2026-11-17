"""Assemble estimation samples from the processed tables."""

import numpy as np
import pandas as pd

from transitcap.estimate.csdid import NEVER, Sample
from transitcap.paths import PROCESSED


def sales_frame(pap: dict) -> pd.DataFrame:
    """Arm's-length single-family sales with hedonic covariates, one row per sale."""
    s = pd.read_parquet(PROCESSED / "fact_sales.parquet")
    p = pd.read_parquet(PROCESSED / "dim_parcel.parquet",
                        columns=["pin", "assessor_area", "present_use", "sqft_lot", "has_view",
                                 "waterfront"])
    s = s[s.arms_length].merge(p, on="pin", how="inner")
    s = s[s.present_use.isin(pap["outcome"]["present_use"])]
    s = s.dropna(subset=["sqft_living", "yr_built", "grade", "sqft_lot"])
    s = s[(s.sqft_living > 0) & (s.sqft_lot > 0)]
    s["age"] = s.sale_year - s.yr_built
    # current characteristics describe the sold home only if it was built and not renovated since
    s = s[(s.age >= 0) & ~(s.yr_renovated.fillna(0) > s.sale_year)]
    s["log_price"] = np.log(s.price)
    s["log_sqft_living"] = np.log(s.sqft_living)
    s["log_sqft_lot"] = np.log(s.sqft_lot)
    s["age_sq"] = s.age ** 2 / 100
    s["has_view"] = s.has_view.fillna(False).astype(float)
    s["waterfront"] = s.waterfront.fillna(False).astype(float)
    for c in ("bedrooms", "bathrooms", "condition"):
        s[c] = s[c].fillna(s[c].median())
    return s.reset_index(drop=True)


def with_assignment(sales: pd.DataFrame, milestone: str) -> pd.DataFrame:
    ta = pd.read_parquet(PROCESSED / "treatment_assignment.parquet")
    ta = ta[ta.milestone == milestone].drop(columns="milestone")
    return sales.merge(ta, on="pin", how="inner")


def to_sample(df: pd.DataFrame, pap: dict, treated_ring: str = "treated",
              outcome: str = "log_price", covariates: list[str] | None = None) -> tuple[Sample, pd.DataFrame]:
    """Treated ring vs never-treated controls (control ring and planned-station areas).

    Parcels in other rings are dropped, so the spillover ring never contaminates controls.
    """
    keep = df.ring.isin([treated_ring, "control", "planned_area"])
    d = df[keep].copy()
    d.loc[d.ring != treated_ring, "cohort"] = NEVER
    cov = pap["estimator"]["covariates"] if covariates is None else covariates
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(dtype=float) for c in cov])
    clusters = pd.Categorical(d.cluster_station)
    blocks = pd.Categorical(d.assessor_area)
    if covariates is None and pap["estimator"].get("submarket_indicators"):
        # submarket-specific levels in both nuisance models (ADR-0007)
        X = np.column_stack([X, pd.get_dummies(blocks).to_numpy(float)[:, 1:]])
    s = Sample(y=d[outcome].to_numpy(dtype=float), year=d.sale_year.to_numpy(dtype=int),
               g=d.cohort.to_numpy(dtype=int), cluster=clusters.codes.astype(int), X=X,
               block=blocks.codes.astype(int))
    return s, d.reset_index(drop=True)


def subset(s: Sample, mask: np.ndarray) -> Sample:
    """Rows of a sample; cluster codes are kept so bootstrap multipliers stay aligned."""
    out = Sample(y=s.y[mask], year=s.year[mask], g=s.g[mask], cluster=s.cluster[mask],
                 X=s.X[mask], block=s.block[mask])
    out.n_clusters = s.n_clusters
    return out

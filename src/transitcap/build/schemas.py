"""Column contracts for the ten minimum tables. A table that breaks its contract is not written."""

import pandas as pd

CONTRACTS: dict[str, dict] = {
    "dim_parcel": {"key": ["pin"], "required": ["pin", "geometry", "parcel_area_m2"],
                   "nonneg": ["parcel_area_m2"]},
    "fact_sales": {"key": None, "required": ["excise_nbr", "pin", "sale_date", "price", "arms_length"],
                   "nonneg": []},
    "fact_assessed_value": {"key": ["pin", "tax_year"], "required": ["pin", "tax_year", "land_val"],
                            "nonneg": []},
    "dim_station": {"key": ["station_id"], "required": ["station_id", "open_date", "status"],
                    "nonneg": []},
    "gtfs_history": {"key": ["feed_version"], "required": ["feed_version", "method"], "nonneg": []},
    "parcel_access": {"key": ["pin", "year", "scenario"], "required": ["jobs_45min"],
                      "nonneg": ["jobs_45min"]},
    "treatment_assignment": {"key": ["pin", "milestone"], "required": ["ring", "cohort"],
                             "nonneg": []},
    "dim_zoning": {"key": ["pin"], "required": ["pin", "source"], "nonneg": []},
    "dim_lvc_instrument": {"key": ["instrument_id"], "required": ["legal_base"], "nonneg": []},
    "fact_project_finance": {"key": ["project_id", "item"], "required": ["low_usd", "high_usd"],
                             "nonneg": ["low_usd", "high_usd"]},
}


class ContractError(ValueError):
    pass


def validate(df: pd.DataFrame, name: str) -> None:
    c = CONTRACTS[name]
    missing = [k for k in c["required"] + (c["key"] or []) if k not in df.columns]
    if missing:
        raise ContractError(f"{name}: missing columns {missing}")
    if c["key"] and df.duplicated(c["key"]).any():
        n = int(df.duplicated(c["key"]).sum())
        raise ContractError(f"{name}: {n} duplicate keys on {c['key']}")
    for col in c["nonneg"]:
        if (df[col] < 0).any():
            raise ContractError(f"{name}: negative values in {col}")
    if name == "fact_sales" and (df.loc[df.arms_length, "price"] <= 0).any():
        raise ContractError("fact_sales: arm's-length sale with non-positive price")

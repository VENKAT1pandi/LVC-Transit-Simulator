"""Land split and assessment bridge: from a market-price effect to taxable and levyable bases."""

import numpy as np
import pandas as pd

from transitcap.paths import PROCESSED


def land_effect(property_effect: float, land_share: float) -> float:
    """A station does not change replacement cost, so the whole gain is land:
    percent land gain = percent property gain / land share."""
    return property_effect / land_share


def assessment_ratio(sales: pd.DataFrame, av: pd.DataFrame) -> pd.DataFrame:
    """Median ratio of assessed total value to sale price, by sale year.

    King County values property as of 1 January of the assessment year for taxes payable the
    following year, so a sale in year t is compared with the value for tax year t + 1.
    """
    a = av.assign(total=av.land_val + av.imps_val, sale_year=av.tax_year - 1)
    m = sales.merge(a[["pin", "sale_year", "total"]], on=["pin", "sale_year"], how="inner")
    m = m[m.total > 0]
    m["ratio"] = m.total / m.price
    return m.groupby("sale_year").ratio.agg(["median", "size"]).reset_index()


def assessor_land_share(av: pd.DataFrame, pins: pd.Series, tax_year: int) -> pd.Series:
    v = av[(av.tax_year == tax_year) & av.pin.isin(pins)]
    total = v.land_val + v.imps_val
    return (v.land_val / total.where(total > 0)).rename("land_share_assessor").set_axis(v.pin)


def vacant_land_share(sales_all: pd.DataFrame, improved: pd.DataFrame, parcel: pd.DataFrame,
                      pap: dict, window: int = 5, min_sales: int = 5) -> pd.DataFrame:
    """Land share implied by vacant single-family lot sales in the same area and period.

    land_share = (median vacant $/sq ft in area-window) x lot sq ft / improved sale price
    """
    o, ls = pap["outcome"], pap["land_split"]
    v = sales_all.merge(parcel[["pin", "assessor_area", "present_use", "sqft_lot"]], on="pin")
    v = v[(v.property_class == ls["vacant_property_class"]) & (v.present_use == ls["vacant_present_use"])
          & (v.sale_reason == o["sale_reason"]) & v.sale_instrument.isin(o["sale_instruments"])
          & (v.sale_warning.fillna("") == "") & (v.n_parcels_in_sale == 1)
          & (v.price >= 10_000) & (v.sqft_lot > 0)]
    v["period"] = (v.sale_year // window) * window
    v["usd_per_sqft"] = v.price / v.sqft_lot
    lv = v.groupby(["assessor_area", "period"]).usd_per_sqft.agg(["median", "size"]).reset_index()
    lv = lv[lv["size"] >= min_sales].rename(columns={"median": "land_usd_sqft", "size": "n_vacant"})
    im = improved.assign(period=(improved.sale_year // window) * window)
    im = im.merge(lv, on=["assessor_area", "period"], how="inner")
    im["land_share_vacant"] = (im.land_usd_sqft * im.sqft_lot / im.price).clip(upper=1.0)
    return im[["pin", "sale_year", "assessor_area", "land_share_vacant", "n_vacant"]]


def background_growth(av: pd.DataFrame, pins: pd.Series, first: int, last: int) -> float:
    """Median annual log growth in total assessed value of the given parcels."""
    v = av[av.pin.isin(pins) & av.tax_year.isin([first, last])]
    w = v.assign(total=v.land_val + v.imps_val).pivot_table(index="pin", columns="tax_year",
                                                             values="total")
    w = w.dropna()
    w = w[(w[first] > 0) & (w[last] > 0)]
    return float(np.median(np.log(w[last] / w[first])) / (last - first))


def current_tax_year(av: pd.DataFrame) -> int:
    """Latest tax year that covers most parcels. The extract holds a few hundred parcels with
    tax years beyond the current roll (new plats), which must not define 'current'."""
    n = av.groupby("tax_year").size()
    return int(n[n >= 0.5 * n.max()].index.max())


def load_av() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "fact_assessed_value.parquet")

"""Pure L2 detection metrics on the harmonized ingestion schema."""

from datetime import date

import numpy as np
import pandas as pd


KEYS = ["country", "year", "instrument", "satellite"]
ELIGIBILITY = ["type", "confidence_class"]


def _prepare(df, fields):
    required = list(dict.fromkeys(["country", "instrument", "satellite", "acq_date"] + fields))
    if df.empty:
        numeric = {"latitude", "longitude", "frp", "pixel_area_km2"}
        return pd.DataFrame({
            column: pd.Series(dtype="float64" if column in numeric else "object")
            for column in required + ["year"]
        })
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    result = df[required].copy().reset_index(drop=True)
    dates = result["acq_date"].astype("string")
    formatted = dates.str.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", na=False)
    valid_dates = set()
    for value in dates[formatted].unique():
        try:
            date.fromisoformat(value)
            valid_dates.add(value)
        except ValueError:
            pass
    result = result.loc[dates.isin(valid_dates)].copy()
    result["year"] = dates.loc[result.index].str[:4].astype("int64")
    return result


def _eligible(df, confidence=("n", "h"), type_value=0):
    mask = df["type"].eq(type_value).fillna(False) & df["confidence_class"].isin(confidence)
    return df.loc[mask].copy()


def _finish(df, columns):
    result = df.reindex(columns=columns).copy()
    for column in columns:
        if column in ["year", "n"] or column.startswith("n_"):
            result[column] = result[column].astype("int64")
    return result.sort_values([column for column in columns if column in KEYS or column in ["version", "type_label"]]).reset_index(drop=True)


def obs04_night_pct(df, confidence=("n", "h"), type_value=0):
    """Report nighttime share among eligible records with known day/night."""
    source = _eligible(_prepare(df, ELIGIBILITY + ["daynight"]), confidence, type_value)
    source["n_day"] = source["daynight"].eq("D").fillna(False).astype(int)
    source["n_night"] = source["daynight"].eq("N").fillna(False).astype(int)
    source["n_daynight_unknown"] = (~source["daynight"].isin(["D", "N"])).astype(int)
    counts = ["n_day", "n_night", "n_daynight_unknown"]
    result = source.groupby(KEYS, observed=True, dropna=False)[counts].sum().reset_index()
    denominator = result.n_day + result.n_night
    result["pct_night"] = 100.0 * result.n_night / denominator.replace(0, np.nan)
    return _finish(result, KEYS + counts + ["pct_night"])


def _frp_summary(df, statistic, confidence, type_value):
    source = _eligible(_prepare(df, ELIGIBILITY + ["frp"]), confidence, type_value)
    source["usable_frp"] = source["frp"].where(source["frp"].gt(0))
    groups = source.groupby(KEYS, observed=True, dropna=False)["usable_frp"]
    result = groups.count().rename("n_frp_usable").to_frame()
    if statistic == "median":
        result["frp_median"] = groups.median()
    else:
        result["frp_p90"] = groups.quantile(0.9, interpolation="linear")
    return _finish(result.reset_index(), KEYS + ["n_frp_usable", f"frp_{statistic}"])


def obs05_frp_median(df, confidence=("n", "h"), type_value=0):
    """Return median positive FRP in MW, retaining eligible groups without FRP."""
    return _frp_summary(df, "median", confidence, type_value)


def obs06_frp_p90(df, confidence=("n", "h"), type_value=0):
    """Return the linearly interpolated 90th percentile of positive FRP."""
    return _frp_summary(df, "p90", confidence, type_value)


def obs07_frp_peak(df, confidence=("n", "h"), type_value=0):
    """Select each group's FRP peak using the specified chronological tie break."""
    fields = ["frp", "latitude", "longitude", "acq_time", "acq_datetime_utc"]
    source = _eligible(_prepare(df, ELIGIBILITY + fields), confidence, type_value)
    source = source.loc[source["frp"].gt(0).fillna(False)]
    order = ["frp", "acq_date", "acq_time", "latitude", "longitude", "acq_datetime_utc"]
    result = source.sort_values(order, ascending=[False, True, True, True, True, True]).drop_duplicates(KEYS)
    names = dict(zip(fields + ["acq_date"], ["frp_max", "peak_latitude", "peak_longitude", "peak_acq_time", "peak_datetime_utc", "peak_acq_date"]))
    result = result.rename(columns=names)
    return _finish(result, KEYS + ["frp_max", "peak_latitude", "peak_longitude", "peak_acq_date", "peak_acq_time", "peak_datetime_utc"])


def obs08_frp_availability(df, confidence=("n", "h"), type_value=0):
    """Partition eligible FRP into positive, null, zero and negative values."""
    source = _eligible(_prepare(df, ELIGIBILITY + ["frp"]), confidence, type_value)
    source["n_eligible"] = 1
    source["n_frp_usable"] = source.frp.gt(0).fillna(False).astype(int)
    source["n_frp_null"] = source.frp.isna().astype(int)
    source["n_frp_zero"] = source.frp.eq(0).fillna(False).astype(int)
    source["n_frp_negative"] = source.frp.lt(0).fillna(False).astype(int)
    counts = ["n_eligible", "n_frp_usable", "n_frp_null", "n_frp_zero", "n_frp_negative"]
    result = source.groupby(KEYS, observed=True, dropna=False)[counts].sum().reset_index()
    result["pct_frp_usable"] = 100.0 * result.n_frp_usable / result.n_eligible
    return _finish(result, KEYS + counts + ["pct_frp_usable"])


def obs09_type_distribution(df):
    """Count raw type codes by product version without interpreting their meaning."""
    source = _prepare(df, ["version", "type"])
    source["version"] = source["version"].astype("string")
    source["type_label"] = source["type"].map({0: "0", 1: "1", 2: "2", 3: "3"}).fillna("unknown")
    keys = KEYS + ["version", "type_label"]
    result = source.groupby(keys, observed=True, dropna=False).size().rename("n").reset_index()
    total = result.groupby(KEYS + ["version"], observed=True, dropna=False)["n"].transform("sum")
    result["pct"] = 100.0 * result["n"] / total
    return _finish(result, keys + ["n", "pct"])


def obs10_pixel_area_median(df):
    """Summarize finite positive pixel areas over all detections."""
    source = _prepare(df, ["pixel_area_km2"])
    area = pd.to_numeric(source.pixel_area_km2, errors="coerce")
    source = source.loc[(np.isfinite(area) & area.gt(0)).fillna(False)]
    result = source.groupby(KEYS, observed=True, dropna=False).agg(
        n_area=("pixel_area_km2", "count"), pixel_area_median_km2=("pixel_area_km2", "median")
    ).reset_index()
    return _finish(result, KEYS + ["n_area", "pixel_area_median_km2"])

"""Pure ingestion quality metrics for L2, evaluated after ingestion coercion."""

from datetime import date

import numpy as np
import pandas as pd

from .detections import KEYS, _finish, _prepare


def _is_calendar_date(value: str) -> bool:
    """Validate real dates without pandas' datetime resolution limits."""
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def qa01_schema_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Count schema failures by country and instrument across all input years.

    A row can fail multiple rules but contributes once to ``n_invalid``.
    Missing instruments are retained as ``unknown``. Missing countries are
    retained as null group keys. The calling notebook supplies the file year.
    This validates the coerced records, not records discarded during ingestion.
    """
    required = [
        "country", "instrument", "latitude", "longitude", "acq_date",
        "acq_time", "satellite", "daynight", "confidence_raw",
    ]
    rules = ["coords", "date", "time", "instrument", "satellite", "daynight", "confidence"]
    keys = ["country", "instrument"]
    counts = ["n_rows", "n_valid", "n_invalid"]
    failures = [f"n_fail_{rule}" for rule in rules]
    columns = keys + counts + ["pct_valid"] + failures
    if df.empty:
        dtypes = {column: "int64" for column in counts + failures}
        dtypes.update(country="object", instrument="object", pct_valid="float64")
        return pd.DataFrame({column: pd.Series(dtype=dtypes[column]) for column in columns})

    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # A fresh index makes alignment safe even for concatenated input with duplicate indices.
    source = df[required].reset_index(drop=True)
    latitude = pd.to_numeric(source["latitude"], errors="coerce")
    longitude = pd.to_numeric(source["longitude"], errors="coerce")
    dates = source["acq_date"].astype("string")
    date_format = dates.str.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", na=False)
    valid_dates = dates.where(date_format, "").map(_is_calendar_date)
    times = source["acq_time"].astype("string")
    hours = pd.to_numeric(times.str[:2], errors="coerce")
    minutes = pd.to_numeric(times.str[2:], errors="coerce")
    valid = pd.DataFrame({
        "coords": np.isfinite(latitude) & np.isfinite(longitude)
        & latitude.between(-90, 90) & longitude.between(-180, 180),
        "date": valid_dates,
        "time": times.str.fullmatch(r"[0-9]{4}", na=False)
        & hours.between(0, 23) & minutes.between(0, 59),
        "instrument": source["instrument"].isin(["MODIS", "VIIRS"]),
        "satellite": source["satellite"].astype("string").str.strip().ne(""),
        "daynight": source["daynight"].isin(["D", "N"]),
        "confidence": source["confidence_raw"].notna(),
    }).fillna(False).astype(bool)

    values = source[keys].copy()
    values["instrument"] = values["instrument"].astype("object").fillna("unknown")
    values["n_rows"] = 1
    values["n_valid"] = valid.all(axis=1).astype("int64")
    values["n_invalid"] = 1 - values["n_valid"]
    values[failures] = (~valid).astype("int64").to_numpy()
    result = values.groupby(keys, dropna=False, observed=True)[counts + failures].sum().reset_index()
    result["pct_valid"] = 100.0 * result["n_valid"] / result["n_rows"]
    return result[columns].sort_values(keys).reset_index(drop=True)


def add03_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Count repeated acquisition-coordinate tuples and (0, 0) detections."""
    fields = ["latitude", "longitude", "acq_time"]
    source = _prepare(df, fields)
    source["n_null_island"] = (source.latitude.eq(0) & source.longitude.eq(0)).fillna(False).astype(int)
    source["n_dup_rows"] = source.duplicated(KEYS + fields + ["acq_date"]).astype(int)
    source["n_rows"] = 1
    counts = ["n_rows", "n_dup_rows", "n_null_island"]
    result = source.groupby(KEYS, observed=True, dropna=False)[counts].sum().reset_index()
    result["pct_dup"] = 100.0 * result.n_dup_rows / result.n_rows
    return _finish(result, KEYS + ["n_rows", "n_dup_rows", "pct_dup", "n_null_island"])


def add04_zero_detection_countries(counts: pd.DataFrame) -> pd.DataFrame:
    """Find missing country-years within each instrument's observed year range.

    A missing combination can also represent a missing source file. This metric
    cannot establish observation coverage from processed detections alone.
    """
    columns = ["instrument", "year", "country", "n_years_with_data"]
    if counts.empty:
        return _finish(pd.DataFrame(columns=columns), columns)
    missing = sorted(set(["country", "instrument", "year", "n_rows"]) - set(counts.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    totals = counts.groupby(["instrument", "year", "country"], observed=True, dropna=False).n_rows.sum().reset_index()
    results = []
    for instrument, group in totals.groupby("instrument", observed=True, dropna=False):
        years = range(int(group.year.min()), int(group.year.max()) + 1)
        expected = pd.MultiIndex.from_product([years, group.country.unique()], names=["year", "country"])
        grid = group.set_index(["year", "country"]).n_rows.reindex(expected, fill_value=0)
        absent = grid.loc[grid.eq(0)].reset_index().drop(columns="n_rows")
        active = group.loc[group.n_rows.gt(0)].groupby("country", observed=True, dropna=False).year.nunique()
        absent["instrument"] = instrument
        absent["n_years_with_data"] = absent.country.map(active).fillna(0).astype("int64")
        results.append(absent)
    result = pd.concat(results, ignore_index=True)
    return result[columns].sort_values(["instrument", "year", "country"]).reset_index(drop=True)

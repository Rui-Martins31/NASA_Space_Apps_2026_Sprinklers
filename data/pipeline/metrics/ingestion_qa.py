"""Pure ingestion quality metrics for L2, evaluated after ingestion coercion."""

from datetime import date

import numpy as np
import pandas as pd

from .common import GRID_DEG
from .detections import KEYS, _finish, _prepare


def _is_calendar_date(value: str) -> bool:
    """Validate real dates without pandas' datetime resolution limits."""
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def qa01_schema_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Count schema failures by instrument (global, not per cell) across all input years.

    A row can fail multiple rules but contributes once to ``n_invalid``.
    Missing instruments are retained as ``unknown``. The calling notebook supplies the file
    year. Rows with invalid coordinates are counted here (rule ``coords``), which is why
    the cell metrics can exclude them. This validates the coerced records, not records
    discarded during ingestion.
    """
    required = [
        "instrument", "latitude", "longitude", "acq_date",
        "acq_time", "satellite", "daynight", "confidence_raw",
    ]
    rules = ["coords", "date", "time", "instrument", "satellite", "daynight", "confidence"]
    keys = ["instrument"]
    counts = ["n_rows", "n_valid", "n_invalid"]
    failures = [f"n_fail_{rule}" for rule in rules]
    columns = keys + counts + ["pct_valid"] + failures
    if df.empty:
        dtypes = {column: "int64" for column in counts + failures}
        dtypes.update(instrument="object", pct_valid="float64")
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


def add03_duplicates(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """Count repeated acquisition-coordinate tuples and (0, 0) detections per cell group.

    The key has ``cell`` and no country, so a detection repeated in the files of two
    countries (same cell, date, time and coordinates) is already seen as a duplicate.
    Rows with invalid coordinates or dates are excluded (see ``count_invalid_coords``).
    """
    fields = ["latitude", "longitude", "acq_time"]
    source = _prepare(df, fields, grid_deg)
    source["n_null_island"] = (source.latitude.eq(0) & source.longitude.eq(0)).fillna(False).astype(int)
    source["n_dup_rows"] = source.duplicated(KEYS + fields + ["acq_date"]).astype(int)
    source["n_rows"] = 1
    counts = ["n_rows", "n_dup_rows", "n_null_island"]
    result = source.groupby(KEYS, observed=True, dropna=False)[counts].sum().reset_index()
    result["pct_dup"] = 100.0 * result.n_dup_rows / result.n_rows
    return _finish(result, KEYS + ["n_rows", "n_dup_rows", "pct_dup", "n_null_island"])

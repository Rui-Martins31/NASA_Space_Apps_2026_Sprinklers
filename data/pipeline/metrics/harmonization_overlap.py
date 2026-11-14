"""L6 overlap metrics on eligible MODIS and VIIRS cell-days."""

import pandas as pd

from .common import INSTRUMENTS, require_columns


CAL_START = 2018
KEYS = ["country", "year", "month"]
COUNT_COLUMNS = ["n_modis", "n_viirs", "n_both", "n_union"]
OVERLAP_COLUMNS = KEYS + COUNT_COLUMNS


def _output(frame, columns):
    result = frame.reindex(columns=columns).copy()
    result.columns.name = None
    result["country"] = result.country.astype("object")
    for column in ["year", "month"] + COUNT_COLUMNS:
        result[column] = result[column].astype("int64")
    if "jaccard" in columns:
        result["jaccard"] = result.jaccard.astype("float64")
    return result.sort_values(KEYS).reset_index(drop=True)


def har01_cellday_overlap(cell_days: pd.DataFrame, cal_start=CAL_START) -> pd.DataFrame:
    """Count distinct cell-days within and across instruments in each month.

    Satellite duplicates count once. Dates are normalized to UTC calendar days.
    The compact input is already quality filtered by L1 ``eligible_cell_days``.
    Monthly coverage validity is evaluated separately by HAR-03.
    """
    if cell_days.empty:
        return _output(pd.DataFrame(), OVERLAP_COLUMNS)
    columns = ["country", "date", "cell", "instrument"]
    require_columns(cell_days, columns)
    work = cell_days[columns].copy().reset_index(drop=True)
    work["instrument"] = work.instrument.astype("string").str.upper()
    if not work.instrument.isin(INSTRUMENTS).all():
        raise ValueError("Unknown or missing instrument; expected MODIS or VIIRS")
    work["date"] = pd.to_datetime(work.date, utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    if work.date.isna().any():
        raise ValueError("date contains missing or invalid values")
    work = work.loc[work.date.dt.year.ge(cal_start)]
    if work.empty:
        return _output(pd.DataFrame(), OVERLAP_COLUMNS)

    # Presence flags avoid carrying satellite duplicates into any monthly count.
    presence = work.groupby(
        ["country", "date", "cell", "instrument"], observed=True, dropna=False
    ).size().unstack("instrument", fill_value=0).gt(0)
    presence = presence.reindex(columns=list(INSTRUMENTS), fill_value=False).reset_index()
    presence["year"] = presence.date.dt.year
    presence["month"] = presence.date.dt.month
    presence["n_modis"] = presence["MODIS"].astype("int64")
    presence["n_viirs"] = presence["VIIRS"].astype("int64")
    presence["n_both"] = (presence["MODIS"] & presence["VIIRS"]).astype("int64")
    counts = presence.groupby(KEYS, observed=True, dropna=False)[COUNT_COLUMNS[:3]].sum().reset_index()
    counts["n_union"] = counts.n_modis + counts.n_viirs - counts.n_both
    return _output(counts, OVERLAP_COLUMNS)


def har02_jaccard(overlap: pd.DataFrame) -> pd.DataFrame:
    """Return intersection divided by union, with null for an empty union."""
    columns = OVERLAP_COLUMNS + ["jaccard"]
    if overlap.empty:
        return _output(pd.DataFrame(), columns)
    require_columns(overlap, OVERLAP_COLUMNS)
    result = overlap[OVERLAP_COLUMNS].copy()
    denominator = result.n_union.where(result.n_union.ne(0))
    result["jaccard"] = result.n_both / denominator
    return _output(result, columns)

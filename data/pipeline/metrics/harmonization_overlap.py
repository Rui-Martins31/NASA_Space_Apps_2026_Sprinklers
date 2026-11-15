"""L6 overlap metrics on eligible MODIS and VIIRS cell-days, per grid cell."""

import pandas as pd

from .common import GLOBAL_CELL, INSTRUMENTS, require_columns


CAL_START = 2018
KEYS = ["cell", "year", "month"]
COUNT_COLUMNS = ["n_modis", "n_viirs", "n_both", "n_union"]
OVERLAP_COLUMNS = KEYS + COUNT_COLUMNS


def _output(frame, columns):
    result = frame.reindex(columns=columns).copy()
    result.columns.name = None
    for column in ["cell", "year", "month"] + COUNT_COLUMNS:
        result[column] = result[column].astype("int64")
    if "jaccard" in columns:
        result["jaccard"] = result.jaccard.astype("float64")
    return result.sort_values(KEYS).reset_index(drop=True)


def har01_cellday_overlap(cell_days: pd.DataFrame, cal_start=CAL_START) -> pd.DataFrame:
    """Count distinct cell-days within and across instruments per cell and month.

    ``cell_days`` needs ``cell``, ``date`` and ``instrument`` (the L1
    ``eligible_cell_days`` output; ``satellite`` is not used). Satellite
    duplicates count once. Dates are normalized to UTC calendar days. The
    input is already quality filtered, and monthly coverage validity is
    evaluated separately by HAR-03. Rows are per cell: the counts are
    additive, so sum them (see ``global_overlap``) for any wider region.
    """
    if cell_days.empty:
        return _output(pd.DataFrame(), OVERLAP_COLUMNS)
    columns = ["cell", "date", "instrument"]
    require_columns(cell_days, columns)
    work = cell_days[columns].copy().reset_index(drop=True)
    if work.cell.isna().any():
        raise ValueError("cell contains missing values")
    work["cell"] = work.cell.astype("int64")
    instrument = work.instrument.astype("string").str.upper()
    if not instrument.isin(INSTRUMENTS).all():
        raise ValueError("Unknown or missing instrument; expected MODIS or VIIRS")
    work["date"] = pd.to_datetime(work.date, utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    if work.date.isna().any():
        raise ValueError("date contains missing or invalid values")
    work["modis"] = instrument.eq("MODIS").to_numpy()
    work["viirs"] = instrument.eq("VIIRS").to_numpy()
    work = work.loc[work.date.dt.year.ge(cal_start)]
    if work.empty:
        return _output(pd.DataFrame(), OVERLAP_COLUMNS)

    # One presence flag per instrument and cell-day: satellite duplicates collapse here.
    presence = work.groupby(["cell", "date"], sort=False)[["modis", "viirs"]].max().reset_index()
    presence["n_both"] = (presence.modis & presence.viirs).astype("int64")
    presence["n_modis"] = presence.modis.astype("int64")
    presence["n_viirs"] = presence.viirs.astype("int64")
    presence["year"] = presence.date.dt.year
    presence["month"] = presence.date.dt.month
    counts = presence.groupby(KEYS)[["n_modis", "n_viirs", "n_both"]].sum().reset_index()
    counts["n_union"] = counts.n_modis + counts.n_viirs - counts.n_both
    return _output(counts, OVERLAP_COLUMNS)


def global_overlap(overlap: pd.DataFrame) -> pd.DataFrame:
    """Sum the HAR-01 counts of all cells into one row per month with ``cell = GLOBAL_CELL``.

    Counts add across cells (never the Jaccard ratio): apply ``har02_jaccard``
    to this result for the global ratio. Rows already marked ``GLOBAL_CELL``
    are ignored.
    """
    if overlap.empty:
        return _output(pd.DataFrame(), OVERLAP_COLUMNS)
    require_columns(overlap, OVERLAP_COLUMNS)
    source = overlap.loc[overlap.cell.ne(GLOBAL_CELL)]
    result = source.groupby(["year", "month"])[COUNT_COLUMNS].sum().reset_index()
    result["cell"] = GLOBAL_CELL
    return _output(result, OVERLAP_COLUMNS)


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

"""Build isolated MODIS and S-NPP GLOBAL monthly inputs using the L1 calendar rules."""

import pandas as pd

from .calendar_metrics import (
    eligible_cell_days, cal_coverage, cal_monthly, global_day_counts, month_validity,
)
from .common import GLOBAL_CELL, GRID_DEG, cell_key, parse_dates, require_columns


COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days", "sensor"]
SNPP_SATELLITES = frozenset({"N", "SNPP", "NPP", "SUOMINPP"})
REQUIRED = ["instrument", "satellite", "latitude", "longitude",
            "acq_date", "type", "confidence_class"]


def _output(frame):
    result = frame.reindex(columns=COLUMNS).copy()
    for column in ["series", "sensor"]:
        result[column] = result[column].astype("object")
    for column in ["cell", "year", "month", "cell_days", "n_unknown_days"]:
        result[column] = result[column].astype("int64")
    result["partial"] = result.partial.astype(bool)
    return result.sort_values(["cell", "year", "month", "series"]).reset_index(drop=True)


def global_series(monthly: pd.DataFrame, validity: pd.DataFrame, series: str, sensor: str) -> pd.DataFrame:
    """Global monthly series of one sensor from the sparse per-cell L1 monthly counts.

    ``monthly`` is the sparse L1 ``cal_monthly`` table (``cell, year, month,
    series, cell_days``) and ``validity`` the L1 ``month_validity`` table
    (``series, year, month, partial, n_unknown_days``). The result is dense
    over the interval of ``series``: the cell-days of all cells add up per
    month, months without activity are zero, and ``cell = GLOBAL_CELL``.
    """
    require_columns(monthly, ["year", "month", "series", "cell_days"])
    require_columns(validity, ["series", "year", "month", "partial", "n_unknown_days"])
    months = validity.loc[validity.series.eq(series), ["year", "month", "partial", "n_unknown_days"]]
    sums = (monthly.loc[monthly.series.eq(series)].groupby(["year", "month"]).cell_days.sum()
            .rename("cell_days").reset_index())
    result = months.merge(sums, on=["year", "month"], how="left", validate="one_to_one")
    result["cell_days"] = result.cell_days.fillna(0)
    result["cell"] = GLOBAL_CELL
    result["series"] = series
    result["sensor"] = sensor
    return _output(result)


def build_sensor_monthly(df: pd.DataFrame, sensor: str,
                         grid_deg=GRID_DEG) -> pd.DataFrame:
    """Apply the public L1 pipeline to one isolated sensor and acquisition year.

    The result is the GLOBAL monthly series (``cell = GLOBAL_CELL``: the sum of
    the cell-days of all cells), the input that HAR-12 needs. ``sensor``
    records the caller's source-file provenance. S-NPP input accepts the
    satellite label N and explicit S-NPP name variants. Missing, unknown or
    NOAA-20 satellite labels are rejected before an isolated series is built.
    The original satellite values are preserved while counting cell-days.

    Coverage is the complete interval between the first and last valid raw
    dates. Days without raw observations are unknown. Raw detections establish
    coverage even when all fail the eligibility filter. Missing source years are
    never created because each call accepts at most one acquisition year.
    """
    if sensor not in {"modis", "viirs-snpp"}:
        raise ValueError("sensor must be modis or viirs-snpp")
    cell_key([], [], grid_deg)
    if df.empty:
        return _output(pd.DataFrame())
    require_columns(df, REQUIRED)
    source = df[REQUIRED].copy().reset_index(drop=True)
    expected = "MODIS" if sensor == "modis" else "VIIRS"
    instrument = source.instrument.astype("string").str.upper()
    if not instrument.eq(expected).fillna(False).all():
        raise ValueError(f"Unexpected instrument for sensor {sensor}; expected {expected}")
    source["instrument"] = instrument
    if sensor == "viirs-snpp":
        satellite = source.satellite.astype("string").str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
        if not satellite.isin(SNPP_SATELLITES).all():
            raise ValueError("Expected an S-NPP satellite label (N, SNPP, S-NPP, NPP or Suomi NPP)")

    dates = parse_dates(source.acq_date)
    if dates.dropna().dt.year.nunique() > 1:
        raise ValueError("Input must contain at most one acquisition year")
    if not dates.notna().any():
        return _output(pd.DataFrame())
    compact = eligible_cell_days(source, grid_deg=grid_deg)
    coverage = cal_coverage(global_day_counts(source))
    own_series = "modis" if sensor == "modis" else "viirs"
    if len(compact):
        monthly = cal_monthly(compact, coverage)
    else:
        monthly = pd.DataFrame({"year": pd.Series(dtype="int64"), "month": pd.Series(dtype="int64"),
                                "series": pd.Series(dtype="object"), "cell_days": pd.Series(dtype="int64")})
    return global_series(monthly, month_validity(coverage), own_series, sensor)

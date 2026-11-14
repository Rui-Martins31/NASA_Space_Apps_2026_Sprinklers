"""Build isolated MODIS and S-NPP monthly inputs using the L1 calendar rules."""

import pandas as pd

from .calendar_metrics import (
    eligible_cell_days, cal_daily, global_day_counts, cal_coverage, cal_monthly,
    MONTHLY_COLUMNS,
)
from .common import GRID_DEG, cell_key, parse_dates, require_columns


COLUMNS = MONTHLY_COLUMNS + ["sensor"]
SNPP_SATELLITES = frozenset({"N", "SNPP", "NPP", "SUOMINPP"})
REQUIRED = ["country", "instrument", "satellite", "latitude", "longitude",
            "acq_date", "type", "confidence_class"]


def _output(frame):
    result = frame.reindex(columns=COLUMNS).copy()
    for column in ["country", "series", "sensor"]:
        result[column] = result[column].astype("object")
    for column in ["year", "month", "cell_days", "n_unknown_days"]:
        result[column] = result[column].astype("int64")
    result["partial"] = result.partial.astype(bool)
    return result.sort_values(["country", "year", "month", "series"]).reset_index(drop=True)


def build_sensor_monthly(df: pd.DataFrame, sensor: str,
                         grid_deg=GRID_DEG) -> pd.DataFrame:
    """Apply the public L1 pipeline to one isolated sensor and acquisition year.

    ``sensor`` records the caller's source-file provenance. S-NPP input accepts
    the satellite label N and explicit S-NPP name variants. Missing, unknown or
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
    source["country"] = source.country.astype("string").fillna("unknown")
    countries = sorted(source.loc[dates.notna(), "country"].unique())
    compact = eligible_cell_days(source, grid_deg=grid_deg)
    daily = cal_daily(compact)
    coverage = cal_coverage(global_day_counts(source))
    monthly = cal_monthly(daily, coverage, countries=countries)
    own_series = "modis" if sensor == "modis" else "viirs"
    monthly = monthly.loc[monthly.series.eq(own_series)].copy()
    monthly["sensor"] = sensor
    return _output(monthly)

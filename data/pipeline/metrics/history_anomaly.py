"""Pure L3 historical anomalies with an evaluated-year-excluded reference."""

import pandas as pd

from .calendar_summary import GROUP, MONTHLY, _input, _output, _reference_pool, _valid_mask


ABS_COLUMNS = GROUP + ["year", "month", "cell_days", "valid_month",
                       "n_ref_years", "ref_mean", "anomaly_abs"]
PCT_COLUMNS = GROUP + ["year", "month", "cell_days", "ref_mean", "anomaly_abs", "anomaly_pct"]


def his03_anomaly_abs(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                      min_ref_years=5, max_unknown_days=0) -> pd.DataFrame:
    """Keep every evaluated month, excluding its year from the reference pool."""
    source = _input(monthly, MONTHLY)
    if source.empty:
        return _output(pd.DataFrame(), ABS_COLUMNS)
    keys = GROUP + ["month"]
    pool = _reference_pool(source, ref_start, ref_end, max_unknown_days)
    summary = pool.groupby(keys, observed=True, dropna=False).agg(
        ref_total=("cell_days", "sum"), n_pool=("year", "nunique"),
    ).reset_index()
    # L1 has one row per country-series-year-month. The year join also handles
    # evaluated rows outside the reference interval without excluding a value.
    own = pool[keys + ["year", "cell_days"]].rename(columns={"cell_days": "own_value"})
    result = source.merge(summary, how="left", on=keys).merge(own, how="left", on=keys + ["year"])
    result["valid_month"] = _valid_mask(result, max_unknown_days)
    result["n_ref_years"] = result.n_pool.fillna(0) - result.own_value.notna().astype(int)
    numerator = result.ref_total.fillna(0) - result.own_value.fillna(0)
    enough = result.valid_month & result.n_ref_years.ge(min_ref_years)
    result["ref_mean"] = (numerator / result.n_ref_years.replace(0, float("nan"))).where(enough)
    result["anomaly_abs"] = result.cell_days - result.ref_mean
    return _output(result, ABS_COLUMNS)


def his04_anomaly_pct(his03: pd.DataFrame) -> pd.DataFrame:
    """Express the absolute anomaly as a percentage of its nonzero reference."""
    source = _input(his03, PCT_COLUMNS[:-1])
    if source.empty:
        return _output(pd.DataFrame(), PCT_COLUMNS)
    denominator = source.ref_mean.where(source.ref_mean.ne(0))
    source["anomaly_pct"] = 100.0 * source.anomaly_abs / denominator
    return _output(source, PCT_COLUMNS)

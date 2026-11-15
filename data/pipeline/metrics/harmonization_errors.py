"""L7 errors on comparable held-out months using supplied L6 factors, per grid cell.

One row per cell plus (``include_global=True``) one row with ``cell = GLOBAL_CELL``
built from the summed counts of the comparable cells. As in
``harmonization_factor``, sliced work calls with ``include_global=False`` per
slice and computes the global row once from the summed global series.
"""

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, require_columns
from .harmonization_factor import CAL_START, CAL_END, TEST_START, comparable_pairs


PREDICTION_COLUMNS = [
    "cell", "year", "month", "modis", "viirs", "factor_used",
    "uses_global_fallback", "modis_adjusted", "error_raw", "error_adjusted",
]
SUMMARY_KEYS = ["cell", "period", "n_pairs", "n_adjusted_pairs"]
FACTOR_COLUMNS = ["cell", "factor_used", "uses_global_fallback"]


def _output(frame, columns):
    result = frame.reindex(columns=columns).copy()
    integer_columns = {"cell", "year", "month", "modis", "viirs", "n_pairs", "n_adjusted_pairs"}
    for column in columns:
        if column == "period":
            result[column] = result[column].astype("object")
        elif column in integer_columns:
            result[column] = result[column].astype("int64")
        elif column == "uses_global_fallback":
            result[column] = result[column].astype(bool)
        else:
            result[column] = result[column].astype("float64")
    keys = [column for column in ["cell", "year", "month", "period"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _factors(factors):
    if factors.empty:
        return _output(pd.DataFrame(), FACTOR_COLUMNS)
    require_columns(factors, FACTOR_COLUMNS)
    result = factors[FACTOR_COLUMNS].copy().reset_index(drop=True)
    if result.cell.isna().any():
        raise ValueError("cell contains missing values")
    result["cell"] = result.cell.astype("int64")
    if result.cell.duplicated().any():
        raise ValueError("Duplicate factor cell keys")
    try:
        numeric = pd.to_numeric(result.factor_used, errors="raise").astype("float64")
    except (ValueError, TypeError) as error:
        raise ValueError("factor_used must contain numeric values or nulls") from error
    invalid = numeric.notna() & (~np.isfinite(numeric) | numeric.lt(0))
    if invalid.any():
        raise ValueError("factor_used must be finite and nonnegative when available")
    result["factor_used"] = numeric
    flags = result.uses_global_fallback
    if not flags.dropna().isin([True, False]).all():
        raise ValueError("uses_global_fallback must contain boolean values")
    result["uses_global_fallback"] = flags.astype("boolean").fillna(False).astype(bool)
    return _output(result, FACTOR_COLUMNS)


def test_predictions(monthly: pd.DataFrame, factors: pd.DataFrame,
                     cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                     max_unknown_days=0, include_global=True) -> pd.DataFrame:
    """Apply supplied factors to valid test months and retain unavailable fits.

    The caller supplies the L6 calibration factors (``cell``, ``factor_used``,
    ``uses_global_fallback``: the HAR-06 output). This function derives
    comparable test pairs and uses the supplied ``factor_used`` and fallback
    flag for each cell, including the generated ``GLOBAL_CELL`` series. A cell
    without a factor row keeps its raw error and has no adjusted one.
    """
    pairs = comparable_pairs(monthly, cal_start=cal_start, cal_end=cal_end,
                             test_start=test_start, max_unknown_days=max_unknown_days,
                             include_global=include_global)
    calibration = _factors(factors)
    pairs = pairs.loc[pairs.period.eq("test")].drop(columns="period")
    result = pairs.merge(calibration, on="cell", how="left", validate="many_to_one")
    result["uses_global_fallback"] = result.uses_global_fallback.astype("boolean").fillna(False).astype(bool)
    result["modis_adjusted"] = result.modis * result.factor_used
    result["error_raw"] = result.modis - result.viirs
    result["error_adjusted"] = result.modis_adjusted - result.viirs
    return _output(result, PREDICTION_COLUMNS)


def _error_summary(monthly, factors, cal_start, cal_end, test_start, max_unknown_days, include_global):
    columns = SUMMARY_KEYS + ["mae_raw", "mae_adjusted", "wape_raw", "wape_adjusted",
                              "bias_raw", "bias_adjusted", "error_reduction_pct"]
    predictions = test_predictions(monthly, factors, cal_start=cal_start, cal_end=cal_end,
                                   test_start=test_start, max_unknown_days=max_unknown_days,
                                   include_global=include_global)
    if monthly.empty:
        return _output(pd.DataFrame(), columns)
    cells = pd.Series(monthly.cell.astype("int64").unique())
    if include_global:
        cells = pd.concat([pd.Series([GLOBAL_CELL]), cells], ignore_index=True)
    skeleton = pd.DataFrame({"cell": cells.astype("int64")})
    predictions["abs_raw"] = predictions.error_raw.abs()
    predictions["abs_adjusted"] = predictions.error_adjusted.abs()
    predictions["adjusted_viirs"] = predictions.viirs.where(predictions.error_adjusted.notna())
    summary = predictions.groupby("cell").agg(
        n_pairs=("error_raw", "size"), n_adjusted_pairs=("error_adjusted", "count"),
        mae_raw=("abs_raw", "mean"), mae_adjusted=("abs_adjusted", "mean"),
        bias_raw=("error_raw", "mean"), bias_adjusted=("error_adjusted", "mean"),
        sum_abs_raw=("abs_raw", "sum"), sum_abs_adjusted=("abs_adjusted", "sum"),
        sum_viirs=("viirs", "sum"), sum_adjusted_viirs=("adjusted_viirs", "sum"),
    ).reset_index()
    result = skeleton.merge(summary, on="cell", how="left", validate="one_to_one")
    result["period"] = "test"
    result["n_pairs"] = result.n_pairs.fillna(0)
    result["n_adjusted_pairs"] = result.n_adjusted_pairs.fillna(0)
    raw_denominator = result.sum_viirs.where(result.sum_viirs.ne(0))
    adjusted_denominator = result.sum_adjusted_viirs.where(
        result.sum_adjusted_viirs.ne(0) & result.n_adjusted_pairs.gt(0)
    )
    result["wape_raw"] = 100.0 * result.sum_abs_raw / raw_denominator
    result["wape_adjusted"] = 100.0 * result.sum_abs_adjusted / adjusted_denominator
    result["error_reduction_pct"] = 100.0 * (result.mae_raw - result.mae_adjusted) / result.mae_raw.where(result.mae_raw.gt(0))
    return _output(result, columns)


def har08_mae(monthly: pd.DataFrame, factors: pd.DataFrame,
              cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
              max_unknown_days=0, include_global=True) -> pd.DataFrame:
    """Report mean absolute raw and adjusted errors on comparable test months."""
    result = _error_summary(monthly, factors, cal_start, cal_end, test_start,
                            max_unknown_days, include_global)
    return result[SUMMARY_KEYS + ["mae_raw", "mae_adjusted"]]


def har09_wape(monthly: pd.DataFrame, factors: pd.DataFrame,
               cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
               max_unknown_days=0, include_global=True) -> pd.DataFrame:
    """Report absolute error sums as percentages of aligned VIIRS activity."""
    result = _error_summary(monthly, factors, cal_start, cal_end, test_start,
                            max_unknown_days, include_global)
    return result[SUMMARY_KEYS + ["wape_raw", "wape_adjusted"]]


def har10_bias(monthly: pd.DataFrame, factors: pd.DataFrame,
               cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
               max_unknown_days=0, include_global=True) -> pd.DataFrame:
    """Report signed mean prediction-minus-VIIRS errors for the test window."""
    result = _error_summary(monthly, factors, cal_start, cal_end, test_start,
                            max_unknown_days, include_global)
    return result[SUMMARY_KEYS + ["bias_raw", "bias_adjusted"]]


def har11_error_reduction(monthly: pd.DataFrame, factors: pd.DataFrame,
                          cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                          max_unknown_days=0, include_global=True) -> pd.DataFrame:
    """Return percentage MAE reduction when the initial error is positive."""
    result = _error_summary(monthly, factors, cal_start, cal_end, test_start,
                            max_unknown_days, include_global)
    return result[SUMMARY_KEYS + ["mae_raw", "mae_adjusted", "error_reduction_pct"]]

"""L6 comparable monthly pairs and MODIS-to-VIIRS calibration statistics, per grid cell.

Every statistic is computed per ``cell`` and, when ``include_global`` is true,
for one extra row with ``cell = GLOBAL_CELL`` built from the SUM of the counts
of all cells given (never from ratios or correlations of the cells). The global
row only covers the cells that are in ``monthly``; when the work is sliced by
latitude band, call with ``include_global=False`` per slice, add the
``comparable_pairs`` counts of all slices by (year, month) into one series with
``cell = GLOBAL_CELL`` and call the function once more on that series.

All functions are vectorized over cells (group-by operations, no Python loop
per cell), because they run on slices with tens of thousands of cells.
"""

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, require_columns


CAL_START = 2018
CAL_END = 2021
TEST_START = 2022
MIN_PAIRS = 12
MIN_CAL_MONTHS = 24
MAX_UNKNOWN_DAYS = 0
PERIODS = ("calibration", "test", "all")
MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
PAIR_COLUMNS = ["cell", "year", "month", "period", "modis", "viirs"]
FACTOR_COLUMNS = ["cell", "scope", "n_cal_months", "sum_modis", "sum_viirs",
                  "factor", "factor_used", "uses_global_fallback"]
UNCERTAINTY_COLUMNS = ["cell", "scope", "n_cal_years", "factor",
                       "factor_loo_min", "factor_loo_max", "se_jackknife"]
_STAT_KEYS = ["cell", "period"]


def _output(records, columns):
    result = pd.DataFrame(records, columns=columns)
    integers = {"cell", "year", "month", "modis", "viirs", "n_comparable_months", "n_pairs",
                "n_cal_months", "sum_modis", "sum_viirs", "n_cal_years"}
    floats = {"pearson", "spearman", "factor", "factor_used", "factor_loo_min",
              "factor_loo_max", "se_jackknife"}
    for column in columns:
        if column in integers:
            result[column] = result[column].astype("int64")
        elif column in floats:
            result[column] = result[column].astype("float64")
        elif column == "uses_global_fallback":
            result[column] = result[column].astype(bool)
        else:
            result[column] = result[column].astype("object")
    keys = [column for column in ["cell", "year", "month", "period"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _scope(cell):
    return np.where(np.asarray(cell) == GLOBAL_CELL, "global", "cell")


def _monthly(monthly):
    if monthly.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS)
    require_columns(monthly, MONTHLY_COLUMNS)
    source = monthly[MONTHLY_COLUMNS].copy().reset_index(drop=True)
    keys = ["cell", "year", "month", "series"]
    if source.duplicated(keys).any():
        raise ValueError(f"Duplicate monthly keys: {', '.join(keys)}")
    if source.cell_days.isna().any():
        raise ValueError("cell_days contains missing values")
    if source.cell.isna().any():
        raise ValueError("cell contains missing values")
    source["cell"] = source.cell.astype("int64")
    source["series"] = source.series.astype("object")
    return source


def valid_mask(table: pd.DataFrame, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.Series:
    """A valid month is complete and within the allowed unknown-coverage limit."""
    require_columns(table, ["partial", "n_unknown_days"])
    return (~table["partial"].astype(bool)) & table["n_unknown_days"].le(max_unknown_days)


def _pairs(source, cal_start, cal_end, test_start, max_unknown_days, include_global=True):
    if source.empty:
        return _output([], PAIR_COLUMNS)
    if cal_end < cal_start or test_start <= cal_end:
        raise ValueError("Calibration and test year ranges must be ordered and disjoint")
    if include_global and source.cell.eq(GLOBAL_CELL).any():
        raise ValueError("monthly already contains GLOBAL_CELL rows; call with include_global=False")
    selected = source.loc[valid_mask(source, max_unknown_days) & source.year.ge(cal_start)]
    keys = ["cell", "year", "month"]
    modis = selected.loc[selected.series.eq("modis"), keys + ["cell_days"]].rename(columns={"cell_days": "modis"})
    viirs = selected.loc[selected.series.eq("viirs"), keys + ["cell_days"]].rename(columns={"cell_days": "viirs"})
    pairs = modis.merge(viirs, on=keys, how="inner", validate="one_to_one")
    pairs = pairs.loc[pairs.year.le(cal_end) | pairs.year.ge(test_start)].copy()
    parts = [pairs]
    if include_global and len(pairs):
        global_pairs = pairs.groupby(["year", "month"])[["modis", "viirs"]].sum().reset_index()
        global_pairs["cell"] = GLOBAL_CELL
        parts.append(global_pairs)
    result = pd.concat(parts, ignore_index=True)
    result["period"] = np.where(result.year.le(cal_end), "calibration", "test")
    return _output(result, PAIR_COLUMNS)


def comparable_pairs(monthly: pd.DataFrame, cal_start=CAL_START, cal_end=CAL_END,
                     test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS,
                     include_global=True) -> pd.DataFrame:
    """Pair valid sensor months per cell and add the global sum of comparable cells.

    Each pair appears once with its calibration or test period. The ``all``
    summaries in HAR-03 through HAR-05 use both sets of these pairs together.
    The ``GLOBAL_CELL`` row of a month adds only the cells that are comparable
    in that month.
    """
    return _pairs(_monthly(monthly), cal_start, cal_end, test_start, max_unknown_days, include_global)


def _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days, include_global):
    source = _monthly(monthly)
    pairs = _pairs(source, cal_start, cal_end, test_start, max_unknown_days, include_global)
    cells = np.sort(source.cell.unique()) if len(source) else np.array([], dtype="int64")
    if include_global and len(cells):
        cells = np.concatenate([[GLOBAL_CELL], cells])
    return cells.astype("int64"), pairs


def _stacked(cells, pairs):
    """One row per (cell, period) of the skeleton plus the pairs repeated for ``all``."""
    skeleton = pd.MultiIndex.from_product([cells, list(PERIODS)], names=_STAT_KEYS).to_frame(index=False)
    skeleton["cell"] = skeleton.cell.astype("int64")
    stacked = pd.concat([pairs, pairs.assign(period="all")], ignore_index=True)
    return skeleton, stacked


def _month_text(code):
    """'YYYY-MM' text from year*100+month codes; null where the code is null."""
    result = pd.Series(None, index=code.index, dtype="object")
    present = code.notna()
    values = code[present].astype("int64")
    result[present] = (values // 100).astype(str).str.zfill(4) + "-" + (values % 100).astype(str).str.zfill(2)
    return result


def har03_comparable_months(monthly: pd.DataFrame, cal_start=CAL_START, cal_end=CAL_END,
                            test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS,
                            include_global=True) -> pd.DataFrame:
    """Count comparable months, retaining cell-period rows with no pairs."""
    columns = ["cell", "period", "n_comparable_months", "first_month", "last_month"]
    cells, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days, include_global)
    skeleton, stacked = _stacked(cells, pairs)
    stacked["code"] = stacked.year * 100 + stacked.month
    summary = stacked.groupby(_STAT_KEYS).code.agg(["size", "min", "max"]).reset_index()
    result = skeleton.merge(summary, on=_STAT_KEYS, how="left", validate="one_to_one")
    result["n_comparable_months"] = result["size"].fillna(0)
    result["first_month"] = _month_text(result["min"])
    result["last_month"] = _month_text(result["max"])
    return _output(result, columns)


def _correlations(monthly, statistic, min_pairs, cal_start, cal_end, test_start,
                  max_unknown_days, include_global):
    cells, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days, include_global)
    skeleton, stacked = _stacked(cells, pairs)
    work = stacked[_STAT_KEYS].copy()
    x, y = stacked.modis.astype("float64"), stacked.viirs.astype("float64")
    if statistic == "spearman":
        grouped = stacked.groupby(_STAT_KEYS)
        x = grouped.modis.rank(method="average")
        y = grouped.viirs.rank(method="average")
    work["x"], work["y"] = x, y
    grouped = work.groupby(_STAT_KEYS)
    work["x"] = work.x - grouped.x.transform("mean")
    work["y"] = work.y - grouped.y.transform("mean")
    work["xy"] = work.x * work.y
    work["xx"] = work.x * work.x
    work["yy"] = work.y * work.y
    sums = work.groupby(_STAT_KEYS).agg(n_pairs=("x", "size"), xy=("xy", "sum"),
                                        xx=("xx", "sum"), yy=("yy", "sum")).reset_index()
    sums["denominator"] = np.sqrt(sums.xx * sums.yy)
    usable = sums.n_pairs.ge(min_pairs) & sums.n_pairs.ge(2) & sums.denominator.ne(0)
    sums[statistic] = np.clip(sums.xy / sums.denominator.where(usable), -1, 1)
    result = skeleton.merge(sums[_STAT_KEYS + ["n_pairs", statistic]], on=_STAT_KEYS,
                            how="left", validate="one_to_one")
    result["n_pairs"] = result.n_pairs.fillna(0)
    return _output(result, ["cell", "period", "n_pairs", statistic])


def har04_pearson(monthly: pd.DataFrame, min_pairs=MIN_PAIRS, cal_start=CAL_START,
                  cal_end=CAL_END, test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS,
                  include_global=True) -> pd.DataFrame:
    """Calculate Pearson correlation over comparable raw monthly activity."""
    return _correlations(monthly, "pearson", min_pairs, cal_start, cal_end, test_start,
                         max_unknown_days, include_global)


def har05_spearman(monthly: pd.DataFrame, min_pairs=MIN_PAIRS, cal_start=CAL_START,
                   cal_end=CAL_END, test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS,
                   include_global=True) -> pd.DataFrame:
    """Calculate Pearson correlation of average ranks, including tied values."""
    return _correlations(monthly, "spearman", min_pairs, cal_start, cal_end, test_start,
                         max_unknown_days, include_global)


def _ratio(sum_modis, sum_viirs, n_months, min_cal_months):
    """viirs/modis sums where there are enough months and the divisor is not zero."""
    usable = (n_months >= min_cal_months) & (sum_modis != 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(usable, sum_viirs / np.where(sum_modis != 0, sum_modis, 1), np.nan)


def har06_factor(monthly: pd.DataFrame, min_cal_months=MIN_CAL_MONTHS,
                 cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                 max_unknown_days=MAX_UNKNOWN_DAYS, include_global=True,
                 fallback_factor=None) -> pd.DataFrame:
    """Estimate a ratio of calibration sums per cell and report explicit global fallback.

    A cell without enough calibration months uses the ``GLOBAL_CELL`` factor
    (``uses_global_fallback = True``). ``fallback_factor`` supplies that global
    factor when it is computed elsewhere (sliced work, ``include_global=False``);
    otherwise the factor of the global row of this call is used, if any.
    """
    cells, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days, include_global)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    sums = calibration.groupby("cell").agg(n_cal_months=("modis", "size"),
                                           sum_modis=("modis", "sum"),
                                           sum_viirs=("viirs", "sum")).reset_index()
    result = pd.DataFrame({"cell": cells}).merge(sums, on="cell", how="left", validate="one_to_one")
    for column in ["n_cal_months", "sum_modis", "sum_viirs"]:
        result[column] = result[column].fillna(0).astype("int64")
    result["scope"] = _scope(result.cell)
    result["factor"] = _ratio(result.sum_modis.to_numpy(), result.sum_viirs.to_numpy(),
                              result.n_cal_months.to_numpy(), min_cal_months)
    result["factor_used"] = result.factor
    result["uses_global_fallback"] = False
    global_factor = np.nan if fallback_factor is None else float(fallback_factor)
    own = result.loc[result.cell.eq(GLOBAL_CELL), "factor"]
    if fallback_factor is None and len(own):
        global_factor = own.iloc[0]
    if pd.notna(global_factor):
        fallback = result.factor.isna() & result.cell.ne(GLOBAL_CELL)
        result.loc[fallback, "factor_used"] = global_factor
        result.loc[fallback, "uses_global_fallback"] = True
    return _output(result, FACTOR_COLUMNS)


def har07_factor_uncertainty(monthly: pd.DataFrame, min_cal_months=MIN_CAL_MONTHS,
                             min_cal_years=3, cal_start=CAL_START, cal_end=CAL_END,
                             test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS,
                             include_global=True) -> pd.DataFrame:
    """Report factor dispersion from leave-one-year-out calibration estimates.

    Every omitted-year replicate must satisfy the same minimum calibration
    month count. The reported range describes jackknife dispersion and has
    no formal confidence-interval interpretation. This metric uses each
    cell's own calibration pairs and the separately summed global row; there
    is no global fallback. Replicates come from per-(cell, year) sums, so the
    cost is one group-by, not one fit per year and cell.
    """
    cells, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days, include_global)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    yearly = calibration.groupby(["cell", "year"]).agg(
        n=("modis", "size"), sx=("modis", "sum"), sy=("viirs", "sum")).reset_index()
    total = yearly.groupby("cell").agg(
        n_cal_years=("year", "size"), total_n=("n", "sum"),
        total_x=("sx", "sum"), total_y=("sy", "sum")).reset_index()
    total["full"] = _ratio(total.total_x.to_numpy(), total.total_y.to_numpy(),
                           total.total_n.to_numpy(), min_cal_months)
    yearly = yearly.merge(total, on="cell", how="left", validate="many_to_one")
    yearly["replicate"] = _ratio((yearly.total_x - yearly.sx).to_numpy(),
                                 (yearly.total_y - yearly.sy).to_numpy(),
                                 (yearly.total_n - yearly.n).to_numpy(), min_cal_months)
    grouped = yearly.groupby("cell").replicate
    yearly["squared"] = np.square(yearly.replicate - grouped.transform("mean"))
    replicates = yearly.groupby("cell").agg(
        loo_min=("replicate", "min"), loo_max=("replicate", "max"),
        n_finite=("replicate", "count"), squares=("squared", "sum")).reset_index()
    total = total.merge(replicates, on="cell", how="left", validate="one_to_one")
    total["enough"] = (total.n_cal_years.ge(min_cal_years) & total.full.notna()
                       & total.n_finite.eq(total.n_cal_years))
    total["se"] = np.sqrt((total.n_cal_years - 1) / total.n_cal_years * total.squares)
    result = pd.DataFrame({"cell": cells}).merge(total, on="cell", how="left", validate="one_to_one")
    result["enough"] = result.enough.fillna(False).astype(bool)
    result["n_cal_years"] = result.n_cal_years.fillna(0)
    result["scope"] = _scope(result.cell)
    result["factor"] = result.full.where(result.enough)
    result["factor_loo_min"] = result.loo_min.where(result.enough)
    result["factor_loo_max"] = result.loo_max.where(result.enough)
    result["se_jackknife"] = result.se.where(result.enough)
    return _output(result, UNCERTAINTY_COLUMNS)

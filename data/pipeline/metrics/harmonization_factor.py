"""L6 comparable monthly pairs and MODIS-to-VIIRS calibration statistics."""

import numpy as np
import pandas as pd

from .common import require_columns


CAL_START = 2018
CAL_END = 2021
TEST_START = 2022
MIN_PAIRS = 12
MIN_CAL_MONTHS = 24
MAX_UNKNOWN_DAYS = 0
PERIODS = ("calibration", "test", "all")
MONTHLY_COLUMNS = ["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
PAIR_COLUMNS = ["country", "year", "month", "period", "modis", "viirs"]
FACTOR_COLUMNS = ["country", "scope", "n_cal_months", "sum_modis", "sum_viirs",
                  "factor", "factor_used", "uses_global_fallback"]
UNCERTAINTY_COLUMNS = ["country", "scope", "n_cal_years", "factor",
                       "factor_loo_min", "factor_loo_max", "se_jackknife"]


def _output(records, columns):
    result = pd.DataFrame(records, columns=columns)
    integers = {"year", "month", "modis", "viirs", "n_comparable_months", "n_pairs",
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
    keys = [column for column in ["country", "year", "month", "period"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _monthly(monthly):
    if monthly.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS)
    require_columns(monthly, MONTHLY_COLUMNS)
    source = monthly[MONTHLY_COLUMNS].copy().reset_index(drop=True)
    keys = ["country", "year", "month", "series"]
    if source.duplicated(keys).any():
        raise ValueError(f"Duplicate monthly keys: {', '.join(keys)}")
    if source.cell_days.isna().any():
        raise ValueError("cell_days contains missing values")
    source["country"] = source.country.astype("object")
    source["series"] = source.series.astype("object")
    return source


def valid_mask(table: pd.DataFrame, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.Series:
    """A valid month is complete and within the allowed unknown-coverage limit."""
    require_columns(table, ["partial", "n_unknown_days"])
    return (~table["partial"].astype(bool)) & table["n_unknown_days"].le(max_unknown_days)


def _pairs(source, cal_start, cal_end, test_start, max_unknown_days):
    if source.empty:
        return _output([], PAIR_COLUMNS)
    if cal_end < cal_start or test_start <= cal_end:
        raise ValueError("Calibration and test year ranges must be ordered and disjoint")
    selected = source.loc[valid_mask(source, max_unknown_days) & source.year.ge(cal_start)]
    keys = ["country", "year", "month"]
    modis = selected.loc[selected.series.eq("modis"), keys + ["cell_days"]].rename(columns={"cell_days": "modis"})
    viirs = selected.loc[selected.series.eq("viirs"), keys + ["cell_days"]].rename(columns={"cell_days": "viirs"})
    pairs = modis.merge(viirs, on=keys, how="inner", validate="one_to_one")
    pairs = pairs.loc[pairs.year.le(cal_end) | pairs.year.ge(test_start)].copy()
    global_pairs = pairs.groupby(["year", "month"], observed=True, dropna=False)[["modis", "viirs"]].sum().reset_index()
    global_pairs["country"] = "ALL"
    result = pd.concat([pairs, global_pairs], ignore_index=True)
    result["period"] = np.where(result.year.le(cal_end), "calibration", "test")
    return _output(result, PAIR_COLUMNS)


def comparable_pairs(monthly: pd.DataFrame, cal_start=CAL_START, cal_end=CAL_END,
                     test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Pair valid sensor months and add global sums of comparable countries.

    Each pair appears once with its calibration or test period. The ``all``
    summaries in HAR-03 through HAR-05 use both sets of these pairs together.
    """
    return _pairs(_monthly(monthly), cal_start, cal_end, test_start, max_unknown_days)


def _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days):
    source = _monthly(monthly)
    pairs = _pairs(source, cal_start, cal_end, test_start, max_unknown_days)
    countries = source.country.drop_duplicates().tolist()
    if countries:
        countries.append("ALL")
    return countries, pairs


def _country_pairs(countries, pairs):
    groups = {country: group for country, group in pairs.groupby("country", observed=True, dropna=False)}
    empty = pairs.iloc[:0]
    for country in countries:
        yield country, groups.get(country, empty)


def _period_pairs(countries, pairs):
    for country, group in _country_pairs(countries, pairs):
        for period in PERIODS:
            selected = group if period == "all" else group.loc[group.period.eq(period)]
            yield country, period, selected


def har03_comparable_months(monthly: pd.DataFrame, cal_start=CAL_START, cal_end=CAL_END,
                            test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Count comparable months, retaining country-period rows with no pairs."""
    columns = ["country", "period", "n_comparable_months", "first_month", "last_month"]
    countries, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days)
    records = []
    for country, period, group in _period_pairs(countries, pairs):
        first = last = None
        if len(group):
            ordered = group.sort_values(["year", "month"])
            first_row, last_row = ordered.iloc[0], ordered.iloc[-1]
            first = f"{first_row.year:04d}-{first_row.month:02d}"
            last = f"{last_row.year:04d}-{last_row.month:02d}"
        records.append([country, period, len(group), first, last])
    return _output(records, columns)


def _correlation(x, y, min_pairs):
    if len(x) < min_pairs or len(x) < 2:
        return np.nan
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = np.sqrt(np.dot(x_centered, x_centered) * np.dot(y_centered, y_centered))
    if denominator == 0:
        return np.nan
    return float(np.clip(np.dot(x_centered, y_centered) / denominator, -1, 1))


def _correlations(monthly, statistic, min_pairs, cal_start, cal_end, test_start, max_unknown_days):
    countries, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days)
    records = []
    for country, period, group in _period_pairs(countries, pairs):
        x, y = group.modis, group.viirs
        if statistic == "spearman":
            x, y = x.rank(method="average"), y.rank(method="average")
        records.append([country, period, len(group), _correlation(x, y, min_pairs)])
    return _output(records, ["country", "period", "n_pairs", statistic])


def har04_pearson(monthly: pd.DataFrame, min_pairs=MIN_PAIRS, cal_start=CAL_START,
                   cal_end=CAL_END, test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Calculate Pearson correlation over comparable raw monthly activity."""
    return _correlations(monthly, "pearson", min_pairs, cal_start, cal_end, test_start, max_unknown_days)


def har05_spearman(monthly: pd.DataFrame, min_pairs=MIN_PAIRS, cal_start=CAL_START,
                    cal_end=CAL_END, test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Calculate Pearson correlation of average ranks, including tied values."""
    return _correlations(monthly, "spearman", min_pairs, cal_start, cal_end, test_start, max_unknown_days)


def _factor(group, min_cal_months):
    sum_modis, sum_viirs = int(group.modis.sum()), int(group.viirs.sum())
    factor = np.nan
    if len(group) >= min_cal_months and sum_modis != 0:
        factor = sum_viirs / sum_modis
    return sum_modis, sum_viirs, factor


def har06_factor(monthly: pd.DataFrame, min_cal_months=MIN_CAL_MONTHS,
                  cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                  max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Estimate a ratio of calibration sums and report explicit global fallback."""
    countries, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    records = []
    for country, group in _country_pairs(countries, calibration):
        sum_modis, sum_viirs, factor = _factor(group, min_cal_months)
        scope = "global" if country == "ALL" else "country"
        records.append([country, scope, len(group), sum_modis, sum_viirs, factor, factor, False])
    result = _output(records, FACTOR_COLUMNS)
    global_factor = result.loc[result.country.eq("ALL"), "factor"]
    if len(global_factor) and pd.notna(global_factor.iloc[0]):
        fallback = result.factor.isna() & result.country.ne("ALL")
        result.loc[fallback, "factor_used"] = global_factor.iloc[0]
        result.loc[fallback, "uses_global_fallback"] = True
    return result


def har07_factor_uncertainty(monthly: pd.DataFrame, min_cal_months=MIN_CAL_MONTHS,
                              min_cal_years=3, cal_start=CAL_START, cal_end=CAL_END,
                              test_start=TEST_START, max_unknown_days=MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Report factor dispersion from leave-one-year-out calibration estimates.

    Every omitted-year replicate must satisfy the same minimum calibration
    month count. The reported range describes jackknife dispersion and has
    no formal confidence-interval interpretation. This metric uses each
    country's own calibration pairs, including the separately summed ALL row.
    """
    countries, pairs = _prepared(monthly, cal_start, cal_end, test_start, max_unknown_days)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    records = []
    for country, group in _country_pairs(countries, calibration):
        years = sorted(group.year.unique())
        scope = "global" if country == "ALL" else "country"
        estimates = [np.nan] * 4
        _, _, factor = _factor(group, min_cal_months)
        if len(years) >= min_cal_years and pd.notna(factor):
            replicates = [_factor(group.loc[group.year.ne(year)], min_cal_months)[2] for year in years]
            if np.isfinite(replicates).all():
                values = np.asarray(replicates, dtype=float)
                variance = (len(years) - 1) / len(years) * np.square(values - values.mean()).sum()
                estimates = [factor, values.min(), values.max(), np.sqrt(variance)]
        records.append([country, scope, len(years)] + estimates)
    return _output(records, UNCERTAINTY_COLUMNS)

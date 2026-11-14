"""Pure L3 calendar summaries calculated from the L1 aggregate tables."""

import pandas as pd


GROUP = ["country", "series"]
MONTHLY = GROUP + ["year", "month", "cell_days", "partial", "n_unknown_days"]
ANNUAL = GROUP + ["year", "cell_days", "partial", "n_unknown_days"]
DAILY = GROUP + ["date", "n_cells"]
REFERENCE = GROUP + ["month", "n_years", "mean_cell_days"]


def _output(frame, columns, nullable=()):
    """Normalize output schemas, including empty results and nullable peaks."""
    result = frame.reindex(columns=columns).copy()
    integers = {
        "year", "month", "start_year", "start_month", "end_year", "end_month",
        "first_year", "last_year", "cell_days", "n_cells", "active_days",
        "n_months", "n_partial_months", "n_unknown_days", "n_valid_months",
        "n_valid_years", "n_years", "n_days_in_month", "n_ref_years",
    }
    floats = {"mean_cell_days", "share_pct", "ref_mean", "anomaly_abs", "anomaly_pct"}
    for column in columns:
        if column in integers:
            result[column] = result[column].astype("Int64" if column in nullable else "int64")
        elif column in floats:
            result[column] = result[column].astype("float64")
        elif column in {"valid_month", "is_peak_month"}:
            result[column] = result[column].astype(bool)
        elif column == "date":
            result[column] = pd.to_datetime(result[column]).dt.as_unit("ns")
        elif column in {"country", "series", "years_included"}:
            result[column] = result[column].astype("object")
    keys = [column for column in GROUP + ["year", "month"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _input(table, columns):
    if table.empty:
        return pd.DataFrame({
            column: pd.Series(dtype="bool" if column == "partial" else "object")
            for column in columns
        })
    missing = sorted(set(columns) - set(table.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if "year" in columns:
        keys = GROUP + ["year"]
        if "month" in columns:
            keys += ["month"]
        if table.duplicated(keys).any():
            raise ValueError(f"Duplicate period keys: {', '.join(keys)}")
        if "cell_days" in table.columns and table["cell_days"].isna().any():
            raise ValueError("cell_days contains missing values")
    return table[columns].copy().reset_index(drop=True)


def _valid_mask(table, max_unknown_days=0):
    """Use only complete periods within the allowed unknown-coverage limit."""
    return (~table["partial"].astype(bool)) & table["n_unknown_days"].le(max_unknown_days)


def _reference_pool(table, ref_start=None, ref_end=None, max_unknown_days=0):
    mask = _valid_mask(table, max_unknown_days)
    if ref_start is not None:
        mask &= table.year.ge(ref_start)
    if ref_end is not None:
        mask &= table.year.le(ref_end)
    return table.loc[mask].copy()


def cal05_total_period(monthly: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """Sum observed months in the inclusive selection, retaining partial months."""
    columns = GROUP + ["start_year", "start_month", "end_year", "end_month",
                       "cell_days", "n_months", "n_partial_months", "n_unknown_days"]
    source = _input(monthly, MONTHLY)
    if source.empty:
        return _output(pd.DataFrame(), columns)
    period = source.year * 12 + source.month
    if start is not None:
        source = source.loc[period.ge(start[0] * 12 + start[1])]
    if end is not None:
        source = source.loc[period.loc[source.index].le(end[0] * 12 + end[1])]
    source = source.sort_values(GROUP + ["year", "month"])
    result = source.groupby(GROUP, observed=True, dropna=False).agg(
        start_year=("year", "first"), start_month=("month", "first"),
        end_year=("year", "last"), end_month=("month", "last"),
        cell_days=("cell_days", "sum"), n_months=("month", "size"),
        n_partial_months=("partial", "sum"), n_unknown_days=("n_unknown_days", "sum"),
    ).reset_index()
    if start is not None:
        result["start_year"], result["start_month"] = start
    if end is not None:
        result["end_year"], result["end_month"] = end
    return _output(result, columns)


def _peak_period(source, time_keys, count_column, max_unknown_days):
    columns = GROUP + time_keys + ["cell_days", count_column]
    if source.empty:
        return _output(pd.DataFrame(), columns, nullable=time_keys + ["cell_days"])
    skeleton = source[GROUP].drop_duplicates()
    valid = source.loc[_valid_mask(source, max_unknown_days)]
    counts = valid.groupby(GROUP, observed=True, dropna=False).size().rename(count_column).reset_index()
    peaks = valid.sort_values(["cell_days"] + time_keys,
                             ascending=[False] + [True] * len(time_keys)).drop_duplicates(GROUP)
    result = skeleton.merge(peaks[GROUP + time_keys + ["cell_days"]], how="left", on=GROUP)
    result = result.merge(counts, how="left", on=GROUP)
    result[count_column] = result[count_column].fillna(0)
    return _output(result, columns, nullable=time_keys + ["cell_days"])


def cal06_peak_month(monthly: pd.DataFrame, max_unknown_days=0) -> pd.DataFrame:
    """Find the earliest maximum among valid months, retaining invalid groups."""
    return _peak_period(_input(monthly, MONTHLY), ["year", "month"],
                        "n_valid_months", max_unknown_days)


def cal07_peak_year(annual: pd.DataFrame, max_unknown_days=0) -> pd.DataFrame:
    """Find the earliest maximum among complete, coverage-valid years."""
    return _peak_period(_input(annual, ANNUAL), ["year"], "n_valid_years", max_unknown_days)


def cal08_annual_mean(annual: pd.DataFrame, ref_start=None, ref_end=None,
                      max_unknown_days=0) -> pd.DataFrame:
    """Average valid reference years and report exactly which years were used."""
    columns = GROUP + ["n_years", "mean_cell_days", "first_year", "last_year", "years_included"]
    source = _input(annual, ANNUAL)
    if source.empty:
        return _output(pd.DataFrame(), columns, nullable=["first_year", "last_year"])
    pool = _reference_pool(source, ref_start, ref_end, max_unknown_days).sort_values("year")
    summary = pool.groupby(GROUP, observed=True, dropna=False).agg(
        n_years=("year", "nunique"), mean_cell_days=("cell_days", "mean"),
        first_year=("year", "min"), last_year=("year", "max"),
        years_included=("year", lambda years: ",".join(str(year) for year in sorted(years.unique()))),
    ).reset_index()
    result = source[GROUP].drop_duplicates().merge(summary, how="left", on=GROUP)
    result["n_years"] = result.n_years.fillna(0)
    result["years_included"] = result.years_included.astype("object").fillna("")
    return _output(result, columns, nullable=["first_year", "last_year"])


def cal09_monthly_mean(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                       min_ref_years=5, max_unknown_days=0) -> pd.DataFrame:
    """Build twelve fixed-reference means per existing country and series."""
    source = _input(monthly, MONTHLY)
    if source.empty:
        return _output(pd.DataFrame(), REFERENCE)
    skeleton = source[GROUP].drop_duplicates().merge(pd.DataFrame({"month": range(1, 13)}), how="cross")
    pool = _reference_pool(source, ref_start, ref_end, max_unknown_days)
    summary = pool.groupby(GROUP + ["month"], observed=True, dropna=False).agg(
        n_years=("year", "nunique"), mean_cell_days=("cell_days", "mean"),
    ).reset_index()
    result = skeleton.merge(summary, how="left", on=GROUP + ["month"])
    result["n_years"] = result.n_years.fillna(0)
    result["mean_cell_days"] = result.mean_cell_days.where(result.n_years.ge(min_ref_years))
    return _output(result, REFERENCE)


def cal10_active_days(daily: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Count distinct active UTC dates against the complete monthly skeleton."""
    columns = GROUP + ["year", "month", "active_days", "n_days_in_month"]
    source = _input(daily, DAILY)
    skeleton = _input(monthly, GROUP + ["year", "month"]).drop_duplicates()
    if skeleton.empty:
        return _output(pd.DataFrame(), columns)
    source["date"] = pd.to_datetime(source["date"]).dt.normalize()
    source["year"] = source.date.dt.year
    source["month"] = source.date.dt.month
    active = source.loc[source.n_cells.ge(1)]
    counts = active.groupby(GROUP + ["year", "month"], observed=True, dropna=False).date.nunique()
    result = skeleton.merge(counts.rename("active_days").reset_index(), how="left",
                            on=GROUP + ["year", "month"])
    result["active_days"] = result.active_days.fillna(0)
    result["n_days_in_month"] = pd.to_datetime(result[["year", "month"]].assign(day=1)).dt.days_in_month
    return _output(result, columns)


def cal11_peak_day(daily: pd.DataFrame) -> pd.DataFrame:
    """Return each active year's daily maximum, choosing the earliest tied date."""
    columns = GROUP + ["year", "date", "n_cells"]
    source = _input(daily, DAILY)
    if source.empty:
        return _output(pd.DataFrame(), columns)
    source["date"] = pd.to_datetime(source["date"])
    source["year"] = source.date.dt.year
    source = source.loc[source.n_cells.ge(1)]
    peaks = source.sort_values(["n_cells", "date"], ascending=[False, True]).drop_duplicates(GROUP + ["year"])
    return _output(peaks, columns)


def cal12_seasonal_profile(cal09: pd.DataFrame) -> pd.DataFrame:
    """Calculate shares only for complete nonzero profiles and mark one peak."""
    columns = REFERENCE + ["share_pct", "is_peak_month"]
    source = _input(cal09, REFERENCE)
    if source.empty:
        return _output(pd.DataFrame(), columns)
    groups = source.groupby(GROUP, observed=True, dropna=False)
    totals = groups.mean_cell_days.transform(lambda values: values.sum(min_count=12))
    complete = groups.month.transform("nunique").eq(12)
    source["share_pct"] = 100.0 * source.mean_cell_days / totals.where(complete & totals.ne(0))
    peaks = source.loc[source.mean_cell_days.notna()].sort_values(
        ["mean_cell_days", "month"], ascending=[False, True]
    ).drop_duplicates(GROUP)
    source["is_peak_month"] = source.index.isin(peaks.index)
    return _output(source, columns)

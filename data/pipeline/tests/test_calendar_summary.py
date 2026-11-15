"""L3 calendar summary contracts, with hand-worked expected results."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from helpers_lote3 import CELL, annual, daily, historical_pool, monthly
from metrics import calendar_summary as c


CASES = [
    ("cal05_total_period", lambda: [monthly({})],
     ["cell", "series", "start_year", "start_month", "end_year", "end_month", "cell_days", "n_months", "n_partial_months", "n_unknown_days"]),
    ("cal06_peak_month", lambda: [monthly({})],
     ["cell", "series", "year", "month", "cell_days", "n_valid_months"]),
    ("cal07_peak_year", lambda: [annual({})],
     ["cell", "series", "year", "cell_days", "n_valid_years"]),
    ("cal08_annual_mean", lambda: [annual({})],
     ["cell", "series", "n_years", "mean_cell_days", "first_year", "last_year", "years_included"]),
    ("cal09_monthly_mean", lambda: [historical_pool()],
     ["cell", "series", "month", "n_years", "mean_cell_days"]),
    ("cal10_active_days", lambda: [daily({}), monthly(dict(year=2000, month=2))],
     ["cell", "series", "year", "month", "active_days", "n_days_in_month"]),
    ("cal11_peak_day", lambda: [daily({})],
     ["cell", "series", "year", "date", "n_cells"]),
    ("cal12_seasonal_profile", lambda: [c.cal09_monthly_mean(historical_pool())],
     ["cell", "series", "month", "n_years", "mean_cell_days", "share_pct", "is_peak_month"]),
]


@pytest.mark.parametrize("name,factory,columns", CASES)
def test_empty_contract(name, factory, columns):
    result = getattr(c, name)(*[pd.DataFrame() for _ in factory()])
    assert result.empty
    assert result.columns.tolist() == columns
    assert result.cell.dtype == "int64"
    assert result.series.dtype == "object"


@pytest.mark.parametrize("name,factory,columns", CASES)
def test_missing_columns_named(name, factory, columns):
    args = factory()
    args[0] = args[0].drop(columns="cell")
    with pytest.raises(ValueError, match="cell"):
        getattr(c, name)(*args)


@pytest.mark.parametrize("name,factory,columns", CASES)
def test_immutable_shuffled_and_group_isolated(name, factory, columns):
    args = factory()
    extended = []
    for frame in args:
        other = frame.assign(cell=CELL + 1, series="viirs")
        third = frame.assign(series="combined")
        extended.append(pd.concat([other, third, frame], ignore_index=True))
    before = [frame.copy(deep=True) for frame in extended]
    result = getattr(c, name)(*extended)
    shuffled = [frame.sample(frac=1, random_state=21) for frame in extended]
    assert_frame_equal(result, getattr(c, name)(*shuffled))
    baseline = getattr(c, name)(*args)
    selected = result.loc[result.cell.eq(CELL) & result.series.eq("modis")].reset_index(drop=True)
    assert_frame_equal(selected, baseline)
    for frame, original in zip(extended, before):
        assert_frame_equal(frame, original)


def test_total_period_manual_inclusive_partial_and_unknown():
    source = monthly(dict(year=2000, month=12, cell_days=5),
                     dict(month=1, cell_days=10, partial=True, n_unknown_days=2),
                     dict(month=2, cell_days=20), dict(month=3, cell_days=30))
    result = c.cal05_total_period(source, start=(2001, 1), end=(2001, 2))
    assert result.iloc[0].tolist() == [CELL, "modis", 2001, 1, 2001, 2, 30, 2, 1, 2]
    assert c.cal05_total_period(source).iloc[0].tolist() == [CELL, "modis", 2000, 12, 2001, 3, 65, 4, 1, 2]
    assert c.cal05_total_period(source, start=(2020, 1)).empty


def test_peak_month_ties_invalid_and_custom_unknown_limit():
    source = monthly(dict(year=2002, month=1, cell_days=50),
                     dict(year=2001, month=4, cell_days=50),
                     dict(year=2001, month=3, cell_days=50),
                     dict(month=5, cell_days=999, partial=True),
                     dict(year=2003, cell_days=888, n_unknown_days=1),
                     dict(cell=CELL + 1, partial=True))
    result = c.cal06_peak_month(source)
    assert result.iloc[0].tolist() == [CELL, "modis", 2001, 3, 50, 3]
    assert result.n_valid_months.tolist() == [3, 0]
    assert result.iloc[1][["year", "month", "cell_days"]].isna().all()
    assert c.cal06_peak_month(source, max_unknown_days=1).year.iloc[0] == 2003


def test_peak_year_ties_and_all_invalid():
    source = annual(dict(year=2003, cell_days=100), dict(year=2001, cell_days=100),
                    dict(year=2002, cell_days=999, partial=True),
                    dict(cell=CELL + 1, n_unknown_days=1))
    result = c.cal07_peak_year(source)
    assert result.iloc[0].tolist() == [CELL, "modis", 2001, 100, 2]
    assert result.iloc[1][["year", "cell_days"]].isna().all()
    assert result.n_valid_years.tolist() == [2, 0]


def test_annual_mean_manual_reference_and_no_valid_years():
    source = annual(dict(year=2001, cell_days=100), dict(year=2002, cell_days=200),
                    dict(year=2003, cell_days=300), dict(year=2004, cell_days=999, partial=True),
                    dict(cell=CELL + 1, partial=True))
    result = c.cal08_annual_mean(source)
    assert result.iloc[0].tolist() == [CELL, "modis", 3, 200.0, 2001, 2003, "2001,2002,2003"]
    assert result.n_years.tolist() == [3, 0]
    assert result.years_included.tolist() == ["2001,2002,2003", ""]
    assert result.iloc[1][["mean_cell_days", "first_year", "last_year"]].isna().all()
    selected = c.cal08_annual_mean(source, ref_start=2002, ref_end=2003)
    assert selected.mean_cell_days.iloc[0] == 250
    assert selected.years_included.iloc[0] == "2002,2003"
    assert c.cal08_annual_mean(source, ref_start=2020).n_years.tolist() == [0, 0]


def test_fixed_monthly_mean_literal_pool_and_twelve_months():
    result = c.cal09_monthly_mean(historical_pool())
    assert result.month.tolist() == list(range(1, 13))
    assert result.n_years.tolist() == [0, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert result.mean_cell_days.iloc[2] == 35.0
    assert result.mean_cell_days.isna().sum() == 11
    limited = c.cal09_monthly_mean(historical_pool(), ref_start=2002, ref_end=2005)
    assert limited.n_years.iloc[2] == 4
    assert limited.mean_cell_days.isna().all()
    custom = c.cal09_monthly_mean(historical_pool(), ref_start=2002, ref_end=2005, min_ref_years=4)
    assert custom.mean_cell_days.iloc[2] == 35.0


def test_monthly_reference_excludes_unknown_and_partial():
    source = historical_pool()
    source.loc[0, "n_unknown_days"] = 1
    source.loc[1, "partial"] = True
    assert c.cal09_monthly_mean(source).n_years.iloc[2] == 4
    assert c.cal09_monthly_mean(source).mean_cell_days.isna().all()
    result = c.cal09_monthly_mean(source, max_unknown_days=1)
    assert result.n_years.iloc[2] == 5
    assert result.mean_cell_days.iloc[2] == 38.0


def test_monthly_reference_preserves_groups_without_valid_periods():
    source = monthly(dict(partial=True), dict(cell=CELL + 1, n_unknown_days=1))
    result = c.cal09_monthly_mean(source)
    assert result.groupby("cell", observed=True).size().to_dict() == {CELL: 12, CELL + 1: 12}
    assert result.n_years.eq(0).all()
    assert result.mean_cell_days.isna().all()


@pytest.mark.parametrize("name,factory,columns", CASES[:6])
@pytest.mark.parametrize("problem", ["duplicate", "missing_value"])
def test_calendar_input_rejects_invalid_period_records(name, factory, columns, problem):
    args = factory()
    position = 1 if name == "cal10_active_days" else 0
    source = args[position]
    if problem == "duplicate":
        args[position] = pd.concat([source, source.iloc[:1]], ignore_index=True)
        message = "Duplicate.*cell.*series.*year"
    else:
        source["cell_days"] = source.cell_days.astype("Int64")
        source.loc[0, "cell_days"] = pd.NA
        message = "cell_days.*missing"
    with pytest.raises(ValueError, match=message):
        getattr(c, name)(*args)


def test_active_days_leap_day_duplicate_dates_and_zero_month():
    events = daily({}, {}, dict(date="2000-02-28"), dict(date="2000-02-27", n_cells=0))
    skeleton = monthly(dict(year=2000, month=2), dict(year=2000, month=3), dict(year=2001, month=2))
    result = c.cal10_active_days(events, skeleton)
    assert result.active_days.tolist() == [2, 0, 0]
    assert result.n_days_in_month.tolist() == [29, 31, 28]
    assert (result.active_days <= result.n_days_in_month).all()
    assert c.cal10_active_days(events, pd.DataFrame()).empty
    assert c.cal10_active_days(pd.DataFrame(), skeleton).active_days.tolist() == [0, 0, 0]


def test_peak_day_manual_earliest_tie_and_positive_activity():
    source = daily({}, dict(date="2000-02-28"), dict(date="2001-01-01", n_cells=7),
                   dict(date="2002-01-01", n_cells=0))
    result = c.cal11_peak_day(source)
    assert result.year.tolist() == [2000, 2001]
    assert result.date.tolist() == [pd.Timestamp("2000-02-28"), pd.Timestamp("2001-01-01")]
    assert result.n_cells.tolist() == [3, 7]


def test_seasonal_manual_shares_ties_zero_and_missing_means():
    reference = pd.DataFrame(dict(cell=[CELL] * 12, series=["modis"] * 12,
                                 month=range(1, 13), n_years=[6] * 12,
                                 mean_cell_days=[20.0, 20.0] + [2.0] * 10))
    result = c.cal12_seasonal_profile(reference)
    assert result.share_pct.sum() == pytest.approx(100)
    assert result.share_pct.iloc[0] == pytest.approx(33.333333333333336)
    assert result.is_peak_month.tolist() == [True] + [False] * 11
    zero = c.cal12_seasonal_profile(reference.assign(mean_cell_days=0.0))
    assert zero.share_pct.isna().all()
    assert zero.is_peak_month.tolist() == [True] + [False] * 11
    reference.loc[0, "mean_cell_days"] = np.nan
    incomplete = c.cal12_seasonal_profile(reference)
    assert incomplete.share_pct.isna().all()
    assert incomplete.is_peak_month.tolist() == [False, True] + [False] * 10
    unknown = c.cal12_seasonal_profile(reference.assign(mean_cell_days=np.nan))
    assert unknown.share_pct.isna().all()
    assert not unknown.is_peak_month.any()


def test_seeded_summary_invariants():
    rng = np.random.default_rng(31)
    values = rng.integers(0, 1000, 12)
    source = monthly(*[dict(month=month, cell_days=int(value)) for month, value in enumerate(values, 1)])
    assert c.cal05_total_period(source).cell_days.iloc[0] == sum(map(int, values))
    assert c.cal06_peak_month(source).cell_days.iloc[0] == max(values)
    years = source.drop(columns="month").assign(year=range(2001, 2013))
    assert c.cal07_peak_year(years).cell_days.iloc[0] == max(values)
    assert c.cal08_annual_mean(years).mean_cell_days.iloc[0] == sum(map(int, values)) / 12


@pytest.mark.parametrize("name,factory,columns", CASES)
def test_categorical_series_ignores_unused_categories_without_future_warnings(name, factory, columns):
    import warnings

    args = factory()
    expected = getattr(c, name)(*args)
    for frame in args:
        frame["series"] = pd.Categorical(frame.series, categories=["modis", "viirs", "combined"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = getattr(c, name)(*args)
    assert_frame_equal(result, expected)


"""Leave-one-out monthly anomaly contracts for L3."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from helpers_lote3 import CELL, historical_pool, monthly
from metrics import history_anomaly as h


ABS_COLUMNS = ["cell", "series", "year", "month", "cell_days", "valid_month", "n_ref_years", "ref_mean", "anomaly_abs"]
PCT_COLUMNS = ["cell", "series", "year", "month", "cell_days", "ref_mean", "anomaly_abs", "anomaly_pct"]


def test_worked_example_literal_and_zero_sum():
    result = h.his03_anomaly_abs(historical_pool())
    assert result.n_ref_years.tolist() == [5] * 6
    assert result.ref_mean.tolist() == [40, 38, 36, 34, 32, 30]
    assert result.anomaly_abs.tolist() == [-30, -18, -6, 6, 18, 30]
    assert abs(result.anomaly_abs.sum()) < 1e-9
    percent = h.his04_anomaly_pct(result)
    assert percent.anomaly_pct.iloc[0] == -75.0
    assert percent.anomaly_pct.iloc[2] == pytest.approx(-16.666666666666668)
    assert percent.anomaly_pct.iloc[5] == 100.0


@pytest.mark.parametrize("name,columns", [("his03_anomaly_abs", ABS_COLUMNS), ("his04_anomaly_pct", PCT_COLUMNS)])
def test_empty_and_missing_schema(name, columns):
    result = getattr(h, name)(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns
    argument = historical_pool() if name == "his03_anomaly_abs" else h.his03_anomaly_abs(historical_pool())
    with pytest.raises(ValueError, match="cell"):
        getattr(h, name)(argument.drop(columns="cell"))


@pytest.mark.parametrize("function", [h.his03_anomaly_abs, h.his04_anomaly_pct])
def test_shuffle_immutability_and_group_isolation(function):
    source = historical_pool()
    source = pd.concat([source.assign(cell=CELL + 1, cell_days=100),
                        source.assign(series="combined", cell_days=200), source], ignore_index=True)
    if function.__name__ == "his04_anomaly_pct":
        source = h.his03_anomaly_abs(source)
    original = source.copy(deep=True)
    result = function(source)
    assert_frame_equal(result, function(source.sample(frac=1, random_state=9)))
    subset = source.loc[source.cell.eq(CELL) & source.series.eq("modis")]
    assert_frame_equal(result.loc[result.cell.eq(CELL) & result.series.eq("modis")].reset_index(drop=True), function(subset))
    assert_frame_equal(source, original)


def test_invalid_target_reference_limit_and_custom_threshold():
    source = historical_pool()
    source.loc[0, "n_unknown_days"] = 1
    result = h.his03_anomaly_abs(source)
    assert result.valid_month.tolist() == [False, True, True, True, True, True]
    assert result.n_ref_years.tolist() == [5, 4, 4, 4, 4, 4]
    assert result.ref_mean.iloc[0] == 40.0
    assert result.ref_mean.iloc[1:].isna().all()
    assert result.anomaly_abs.isna().all()
    relaxed = h.his03_anomaly_abs(source, max_unknown_days=1)
    assert relaxed.anomaly_abs.tolist() == [-30, -18, -6, 6, 18, 30]
    restricted = h.his03_anomaly_abs(source, ref_start=2002, ref_end=2005, min_ref_years=3)
    assert len(restricted) == 6
    assert restricted.n_ref_years.tolist() == [4, 3, 3, 3, 3, 4]
    assert restricted.ref_mean.iloc[0] == 35.0
    assert restricted.ref_mean.iloc[1] == 40
    assert restricted.ref_mean.iloc[5] == 35


def test_partial_target_and_four_reference_years():
    source = historical_pool().iloc[:5].copy()
    result = h.his03_anomaly_abs(source)
    assert result.n_ref_years.tolist() == [4] * 5
    assert result.ref_mean.isna().all()
    source.loc[0, "partial"] = True
    result = h.his03_anomaly_abs(source, min_ref_years=3)
    assert not result.valid_month.iloc[0]
    assert result.ref_mean.iloc[0] == 35.0
    assert pd.isna(result.anomaly_abs.iloc[0])


def test_single_year_all_invalid_and_zero_reference():
    assert h.his03_anomaly_abs(monthly({})).n_ref_years.tolist() == [0]
    invalid = h.his03_anomaly_abs(monthly(dict(partial=True)))
    assert not invalid.valid_month.any()
    assert invalid.anomaly_abs.isna().all()
    source = historical_pool().assign(cell_days=0)
    source.loc[0, "cell_days"] = 10
    absolute = h.his03_anomaly_abs(source)
    percent = h.his04_anomaly_pct(absolute)
    assert absolute.ref_mean.iloc[0] == 0
    assert absolute.anomaly_abs.iloc[0] == 10
    assert pd.isna(percent.anomaly_pct.iloc[0])
    assert percent.anomaly_pct.iloc[1] == -100
    absolute.loc[1, "anomaly_abs"] = np.nan
    assert pd.isna(h.his04_anomaly_pct(absolute).anomaly_pct.iloc[1])


def test_seeded_zero_sum_leave_one_out():
    rng = np.random.default_rng(43)
    source = monthly(*[dict(year=year, cell_days=int(value))
                       for year, value in zip(range(2000, 2020), rng.integers(0, 1000, 20))])
    result = h.his03_anomaly_abs(source)
    assert result.n_ref_years.eq(19).all()
    assert abs(result.anomaly_abs.sum()) < 1e-9


@pytest.mark.parametrize("change", [{"partial": True}, {"n_unknown_days": 1}])
def test_invalid_target_keeps_sufficient_pool_description(change):
    source = pd.concat([historical_pool(), monthly(dict(year=2010, cell_days=999) | change)], ignore_index=True)
    result = h.his03_anomaly_abs(source)
    target = result.iloc[-1]
    assert target.n_ref_years == 6
    assert target.ref_mean == 35.0
    assert not target.valid_month
    assert pd.isna(target.anomaly_abs)
    percent = h.his04_anomaly_pct(result).iloc[-1]
    assert percent.ref_mean == 35.0
    assert pd.isna(percent.anomaly_pct)


@pytest.mark.parametrize("function", [h.his03_anomaly_abs, h.his04_anomaly_pct])
@pytest.mark.parametrize("problem", ["duplicate", "missing_value"])
def test_history_input_rejects_invalid_period_records(function, problem):
    source = historical_pool()
    if function.__name__ == "his04_anomaly_pct":
        source = h.his03_anomaly_abs(source)
    if problem == "duplicate":
        source = pd.concat([source, source.iloc[:1]], ignore_index=True)
        message = "Duplicate.*cell.*series.*year.*month"
    else:
        source["cell_days"] = source.cell_days.astype("Int64")
        source.loc[0, "cell_days"] = pd.NA
        message = "cell_days.*missing"
    with pytest.raises(ValueError, match=message):
        function(source)


@pytest.mark.parametrize("function", [h.his03_anomaly_abs, h.his04_anomaly_pct])
def test_categorical_series_key_without_future_warnings(function):
    import warnings

    source = historical_pool()
    if function.__name__ == "his04_anomaly_pct":
        source = h.his03_anomaly_abs(source)
    expected = function(source)
    source["series"] = pd.Categorical(source.series, categories=["modis", "viirs"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = function(source)
    assert_frame_equal(result, expected)

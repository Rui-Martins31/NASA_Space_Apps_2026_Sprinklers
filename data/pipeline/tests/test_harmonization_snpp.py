"""Synthetic per-sensor monthly inputs for the isolated S-NPP analysis."""

import warnings

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.common import GLOBAL_CELL
from metrics.harmonization_snpp import COLUMNS, build_sensor_monthly, global_series


def records(*changes):
    base = dict(instrument="VIIRS", satellite="N",
                latitude=40.0, longitude=-8.0, acq_date="2012-02-01",
                type=0, confidence_class="h")
    frame = pd.DataFrame([base | change for change in changes])
    frame["type"] = frame.type.astype("Int8")
    frame["confidence_class"] = frame.confidence_class.astype("string")
    return frame


def test_manual_snpp_month_and_provenance():
    source = records({}, {}, dict(acq_date="2012-02-29"),
                     dict(acq_date="2012-02-29", latitude=41),
                     dict(acq_date="2012-02-29", confidence_class="l"))
    result = build_sensor_monthly(source, "viirs-snpp")
    assert result.iloc[0].tolist() == [GLOBAL_CELL, 2012, 2, "viirs", 3, False, 27, "viirs-snpp"]
    assert result.columns.tolist() == COLUMNS


def test_modis_satellite_union_and_cells_add_into_one_global_series():
    source = records(dict(instrument="MODIS", satellite="Terra"),
                     dict(instrument="MODIS", satellite="Aqua"),
                     dict(instrument="MODIS", satellite="Terra", acq_date="2012-02-29"),
                     dict(instrument="MODIS", satellite="Terra", latitude=41.0),
                     dict(instrument="MODIS", satellite="Terra", latitude=42.0, type=None))
    result = build_sensor_monthly(source, "modis")
    assert result.cell.tolist() == [GLOBAL_CELL]
    # Terra and Aqua on one cell-day count once (1), plus 29 Feb (1) and the second cell (1).
    assert result.cell_days.tolist() == [3]
    assert result.series.tolist() == ["modis"]
    assert result.sensor.tolist() == ["modis"]


def test_country_column_is_no_longer_required():
    source = records({}, dict(acq_date="2012-02-29"))
    assert "country" not in source
    assert build_sensor_monthly(source, "viirs-snpp").cell_days.tolist() == [2]
    assert_frame_equal(build_sensor_monthly(source.assign(country="Portugal"), "viirs-snpp"),
                       build_sensor_monthly(source, "viirs-snpp"))


def test_dense_calendar_and_partial_endpoint_months():
    source = records(dict(acq_date="2012-01-20"), dict(acq_date="2012-03-12"))
    result = build_sensor_monthly(source, "viirs-snpp")
    assert result.month.tolist() == [1, 2, 3]
    assert result.partial.tolist() == [True, False, True]
    assert result.cell_days.tolist() == [1, 0, 1]
    assert result.n_unknown_days.tolist() == [11, 29, 11]


def test_coverage_uses_raw_records_independently_of_quality_filter():
    source = records(*[dict(acq_date=f"2012-02-{day:02d}", type=None) for day in range(1, 30)])
    result = build_sensor_monthly(source, "viirs-snpp")
    assert result.cell_days.tolist() == [0]
    assert result.partial.tolist() == [False]
    assert result.n_unknown_days.tolist() == [0]


def test_quality_and_coordinate_filters():
    source = records({}, dict(type=None), dict(confidence_class=None), dict(type=1),
                     dict(latitude=100), dict(acq_date="invalid"))
    assert build_sensor_monthly(source, "viirs-snpp").cell_days.tolist() == [1]


@pytest.mark.parametrize("confidence", ["l", None])
def test_ineligible_confidence_in_a_distinct_cell_does_not_add_activity(confidence):
    source = records({}, dict(latitude=41.0, confidence_class=confidence))
    result = build_sensor_monthly(source, "viirs-snpp")
    assert result.cell_days.tolist() == [1]


@pytest.mark.parametrize("label", ["N", "SNPP", "S-NPP", "NPP", "Suomi NPP", "Suomi-NPP"])
def test_snpp_satellite_aliases(label):
    result = build_sensor_monthly(records(dict(satellite=label)), "viirs-snpp")
    assert result.sensor.tolist() == ["viirs-snpp"]


@pytest.mark.parametrize("label", ["N20", "J1", "NOAA20", "NOAA-20", "N21", None, "unknown"])
def test_non_snpp_or_missing_satellite_is_rejected(label):
    with pytest.raises(ValueError, match="S-NPP satellite"):
        build_sensor_monthly(records(dict(satellite=label)), "viirs-snpp")


def test_instrument_sensor_and_schema_validation():
    with pytest.raises(ValueError, match="sensor"):
        build_sensor_monthly(records({}), "viirs-jpss1")
    with pytest.raises(ValueError, match="instrument"):
        build_sensor_monthly(records(dict(instrument="MODIS")), "viirs-snpp")
    with pytest.raises(ValueError, match="confidence_class"):
        build_sensor_monthly(records({}).drop(columns="confidence_class"), "viirs-snpp")


def test_missing_years_are_not_synthesized_from_multi_year_inputs():
    with pytest.raises(ValueError, match="one acquisition year"):
        build_sensor_monthly(records({}, dict(acq_date="2014-02-01")), "viirs-snpp")


def test_empty_and_all_invalid_dates():
    for source in [pd.DataFrame(), records(dict(acq_date="invalid"))]:
        result = build_sensor_monthly(source, "viirs-snpp")
        assert result.empty
        assert result.columns.tolist() == COLUMNS
        assert result.year.dtype == "int64"
        assert result.partial.dtype == "bool"


def test_grid_parameter_changes_cell_counts():
    source = records(dict(latitude=0, longitude=0), dict(latitude=0.11, longitude=0))
    assert build_sensor_monthly(source, "viirs-snpp").cell_days.tolist() == [2]
    assert build_sensor_monthly(source, "viirs-snpp", grid_deg=0.25).cell_days.tolist() == [1]


def test_shuffle_immutability_and_categorical_keys():
    source = records({}, dict(latitude=41.0), dict(acq_date="2012-02-29"))
    original = source.copy(deep=True)
    expected = build_sensor_monthly(source, "viirs-snpp")
    assert_frame_equal(expected, build_sensor_monthly(source.sample(frac=1, random_state=37), "viirs-snpp"))
    assert_frame_equal(source, original)
    source["instrument"] = pd.Categorical(source.instrument, categories=["VIIRS", "MODIS"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        actual = build_sensor_monthly(source, "viirs-snpp")
    assert_frame_equal(actual, expected)


def test_global_series_sums_cells_and_is_dense_over_the_series_interval():
    """Synthetic L1 inputs (no calendar_metrics): the sparse per-cell table becomes one dense global series."""
    monthly = pd.DataFrame([
        [7, 2012, 1, "viirs", 2], [9, 2012, 1, "viirs", 3], [7, 2012, 3, "viirs", 4],
        [7, 2012, 1, "modis", 99], [7, 2012, 1, "combined", 99],
    ], columns=["cell", "year", "month", "series", "cell_days"])
    validity = pd.DataFrame([
        ["viirs", 2012, 1, True, 5], ["viirs", 2012, 2, False, 0], ["viirs", 2012, 3, True, 1],
        ["modis", 2012, 1, False, 0],
    ], columns=["series", "year", "month", "partial", "n_unknown_days"])
    result = global_series(monthly, validity, "viirs", "viirs-snpp")
    assert result.columns.tolist() == COLUMNS
    assert result.values.tolist() == [
        [GLOBAL_CELL, 2012, 1, "viirs", 5, True, 5, "viirs-snpp"],
        [GLOBAL_CELL, 2012, 2, "viirs", 0, False, 0, "viirs-snpp"],
        [GLOBAL_CELL, 2012, 3, "viirs", 4, True, 1, "viirs-snpp"],
    ]
    assert result.cell.dtype == "int64" and result.partial.dtype == "bool"


def test_global_series_without_activity_keeps_zero_months_and_requires_columns():
    validity = pd.DataFrame([["viirs", 2012, 2, False, 0]], columns=["series", "year", "month", "partial", "n_unknown_days"])
    empty = pd.DataFrame({"year": pd.Series(dtype="int64"), "month": pd.Series(dtype="int64"),
                          "series": pd.Series(dtype="object"), "cell_days": pd.Series(dtype="int64")})
    assert global_series(empty, validity, "viirs", "viirs-snpp").cell_days.tolist() == [0]
    with pytest.raises(ValueError, match="cell_days"):
        global_series(empty.drop(columns="cell_days"), validity, "viirs", "viirs-snpp")
    with pytest.raises(ValueError, match="partial"):
        global_series(empty, validity.drop(columns="partial"), "viirs", "viirs-snpp")

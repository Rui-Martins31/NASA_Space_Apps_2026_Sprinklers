"""Synthetic per-sensor monthly inputs for the isolated S-NPP analysis."""

import warnings

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.harmonization_snpp import COLUMNS, build_sensor_monthly


def records(*changes):
    base = dict(country="Portugal", instrument="VIIRS", satellite="N",
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
    assert result.iloc[0].tolist() == ["Portugal", 2012, 2, "viirs", 3, False, 27, "viirs-snpp"]
    assert result.columns.tolist() == COLUMNS


def test_modis_satellite_union_and_country_with_no_eligible_records():
    source = records(dict(instrument="MODIS", satellite="Terra"),
                     dict(instrument="MODIS", satellite="Aqua"),
                     dict(instrument="MODIS", satellite="Terra", acq_date="2012-02-29"),
                     dict(instrument="MODIS", satellite="Terra", country="Spain", type=None))
    result = build_sensor_monthly(source, "modis")
    assert result.country.tolist() == ["Portugal", "Spain"]
    assert result.cell_days.tolist() == [2, 0]
    assert result.series.tolist() == ["modis", "modis"]
    assert result.sensor.tolist() == ["modis", "modis"]


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
    source = records({}, dict(country="Spain"), dict(acq_date="2012-02-29"))
    original = source.copy(deep=True)
    expected = build_sensor_monthly(source, "viirs-snpp")
    assert_frame_equal(expected, build_sensor_monthly(source.sample(frac=1, random_state=37), "viirs-snpp"))
    assert_frame_equal(source, original)
    source["country"] = pd.Categorical(source.country, categories=["Portugal", "Spain", "Unused"])
    source["instrument"] = pd.Categorical(source.instrument, categories=["VIIRS", "MODIS"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        actual = build_sensor_monthly(source, "viirs-snpp")
    assert_frame_equal(actual, expected)

"""Synthetic contract tests for the L2 ingestion quality metrics."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.ingestion_qa import qa01_schema_validation, add03_duplicates, add04_zero_detection_countries


FAILURES = [
    "coords", "date", "time", "instrument", "satellite", "daynight", "confidence"
]
COLUMNS = ["country", "instrument", "n_rows", "n_valid", "n_invalid", "pct_valid"] + [
    f"n_fail_{rule}" for rule in FAILURES
]


def records(*changes):
    """Build records with the nullable/string types produced by ingestion."""
    base = dict(
        country="Portugal", instrument="MODIS", latitude=40.0, longitude=-8.0,
        acq_date="2000-02-29", acq_time="0930", satellite="Terra", daynight="D",
        confidence_raw="80", confidence_class="h", version="6.2", type=0,
    )
    df = pd.DataFrame([base | change for change in changes])
    df["type"] = df["type"].astype("Int8")
    for column in ["version", "acq_time", "confidence_raw", "confidence_class"]:
        df[column] = df[column].astype("string")
    return df


def test_manual_counts_overlapping_failures_and_multiple_years():
    df = records(
        {}, {"latitude": 91, "acq_time": "2400"},
        {"acq_date": "2001-02-29", "daynight": "?", "confidence_raw": None},
        {"acq_date": "2001-03-01"},
    )
    before = df.copy(deep=True)
    expected = pd.DataFrame([
        ["Portugal", "MODIS", 4, 2, 2, 50.0, 1, 1, 1, 0, 0, 1, 1]
    ], columns=COLUMNS)
    assert_frame_equal(qa01_schema_validation(df), expected, check_dtype=False)
    assert_frame_equal(df, before)


@pytest.mark.parametrize("change,rule", [
    ({"latitude": np.inf}, "coords"), ({"longitude": -181}, "coords"),
    ({"latitude": None}, "coords"), ({"longitude": -np.inf}, "coords"),
    ({"acq_date": "2000-2-29"}, "date"), ({"acq_date": "2001-02-29"}, "date"),
    ({"acq_date": None}, "date"), ({"acq_date": "2000-01-01T00:00:00"}, "date"),
    ({"acq_time": "2360"}, "time"), ({"acq_time": "2400"}, "time"),
    ({"acq_time": "930"}, "time"), ({"acq_time": None}, "time"),
    ({"instrument": "unknown"}, "instrument"), ({"instrument": None}, "instrument"),
    ({"satellite": ""}, "satellite"), ({"satellite": "  "}, "satellite"),
    ({"satellite": None}, "satellite"), ({"daynight": None}, "daynight"),
    ({"daynight": "n"}, "daynight"), ({"confidence_raw": None}, "confidence"),
])
def test_each_invalid_field(change, rule):
    result = qa01_schema_validation(records(change)).iloc[0]
    assert result["n_valid"] == 0
    assert result["n_invalid"] == 1
    assert result["pct_valid"] == 0.0
    assert result[f"n_fail_{rule}"] == 1
    assert result[[f"n_fail_{name}" for name in FAILURES]].sum() == 1


@pytest.mark.parametrize("change", [
    {"latitude": -90, "longitude": -180, "acq_time": "0000"},
    {"latitude": 90, "longitude": 180, "acq_time": "2359"},
    {"acq_date": "1600-02-29"}, {"acq_date": "9999-12-31"},
    {"instrument": "VIIRS", "satellite": "N20", "confidence_raw": "n"},
    {"type": None, "confidence_class": None, "confidence_raw": ""},
])
def test_valid_boundaries_and_fields_outside_qa_rules(change):
    result = qa01_schema_validation(records(change)).iloc[0]
    assert result["n_valid"] == 1
    assert result["pct_valid"] == 100.0
    assert result[[f"n_fail_{name}" for name in FAILURES]].sum() == 0


def test_empty_input():
    result = qa01_schema_validation(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == COLUMNS
    assert result["n_rows"].dtype == "int64"
    assert result["pct_valid"].dtype == "float64"


def test_missing_columns_are_named():
    with pytest.raises(ValueError, match="acq_date.*longitude"):
        qa01_schema_validation(records({}).drop(columns=["acq_date", "longitude"]))


def test_all_null_row_remains_in_unknown_instrument_group():
    df = records({})
    df = df.astype(object)
    df.loc[0, :] = None
    result = qa01_schema_validation(df).iloc[0]
    assert pd.isna(result["country"])
    assert result["instrument"] == "unknown"
    assert result["n_rows"] == 1
    assert result["n_invalid"] == 1
    assert result[[f"n_fail_{name}" for name in FAILURES]].tolist() == [1] * 7


def test_sorted_groups_order_invariance_and_count_invariants():
    df = records(
        {"country": "Spain"}, {"country": "Portugal", "instrument": "VIIRS"},
        {"country": "Portugal"}, {"country": "Spain", "acq_time": "2400"},
        {"country": "Portugal", "instrument": None},
    )
    df.index = [9, 9, 2, 1, 1]
    result = qa01_schema_validation(df)
    assert_frame_equal(result, qa01_schema_validation(df.sample(frac=1, random_state=27)))
    assert list(zip(result.country, result.instrument)) == [
        ("Portugal", "MODIS"), ("Portugal", "VIIRS"),
        ("Portugal", "unknown"), ("Spain", "MODIS"),
    ]
    assert result["n_rows"].tolist() == [1, 1, 1, 2]
    assert result["pct_valid"].tolist() == [100.0, 100.0, 0.0, 50.0]
    assert (result.n_valid + result.n_invalid).equals(result.n_rows)
    assert result.index.tolist() == [0, 1, 2, 3]


def test_duplicates_manual_and_null_island():
    df = records({}, {}, {"latitude": 0, "longitude": 0},
                 {"satellite": "Aqua"}, {"acq_date": "invalid"})
    result = add03_duplicates(df)
    assert result.satellite.tolist() == ["Aqua", "Terra"]
    assert result.n_rows.tolist() == [1, 3]
    assert result.n_dup_rows.tolist() == [0, 1]
    assert result.n_null_island.tolist() == [0, 1]
    assert result.pct_dup.tolist() == pytest.approx([0, 33.333333333333336])
    assert_frame_equal(result, add03_duplicates(df.sample(frac=1, random_state=2)))


def test_duplicates_null_tuples_and_distinct_times():
    df = records({"latitude": None}, {"latitude": None}, {"acq_time": "0931"})
    assert add03_duplicates(df).n_dup_rows.tolist() == [1]


def test_zero_countries_manual_missing_years_and_zero_rows():
    counts = pd.DataFrame([
        ["Portugal", "MODIS", 2000, 2], ["Portugal", "MODIS", 2002, 1],
        ["Spain", "MODIS", 2000, 0], ["Spain", "MODIS", 2002, 1],
        ["Portugal", "VIIRS", 2018, 1],
    ], columns=["country", "instrument", "year", "n_rows"])
    before = counts.copy(deep=True)
    expected = pd.DataFrame([
        ["MODIS", 2000, "Spain", 1], ["MODIS", 2001, "Portugal", 2],
        ["MODIS", 2001, "Spain", 1],
    ], columns=["instrument", "year", "country", "n_years_with_data"])
    assert_frame_equal(add04_zero_detection_countries(counts), expected)
    assert_frame_equal(add04_zero_detection_countries(counts.sample(frac=1, random_state=9)), expected)
    assert_frame_equal(counts, before)


@pytest.mark.parametrize("function,columns", [
    (add03_duplicates, ["country", "year", "instrument", "satellite", "n_rows", "n_dup_rows", "pct_dup", "n_null_island"]),
    (add04_zero_detection_countries, ["instrument", "year", "country", "n_years_with_data"]),
])
def test_additional_empty_and_missing_columns(function, columns):
    result = function(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == columns
    with pytest.raises(ValueError, match="country"):
        function(pd.DataFrame({"placeholder": [1]}))


def test_zero_countries_duplicate_counts_and_no_missing_combinations():
    counts = pd.DataFrame({"country": ["Portugal", "Portugal"],
                           "instrument": ["MODIS", "MODIS"], "year": [2000, 2000], "n_rows": [1, 2]})
    assert add04_zero_detection_countries(counts).empty
    counts.n_rows = 0
    result = add04_zero_detection_countries(counts)
    assert result.n_years_with_data.tolist() == [0]


def test_zero_countries_includes_absences_in_last_year():
    counts = pd.DataFrame([["Portugal", "MODIS", 2000, 1], ["Spain", "MODIS", 2002, 1]],
                          columns=["country", "instrument", "year", "n_rows"])
    result = add04_zero_detection_countries(counts)
    assert result[["year", "country"]].values.tolist() == [
        [2000, "Spain"], [2001, "Portugal"], [2001, "Spain"], [2002, "Portugal"]
    ]
    assert result.n_years_with_data.tolist() == [1, 1, 1, 1]

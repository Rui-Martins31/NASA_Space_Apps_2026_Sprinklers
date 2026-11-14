"""Manual examples and edge cases for all L2 detection metrics."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import detections as d


FUNCTIONS = [d.obs04_night_pct, d.obs05_frp_median, d.obs06_frp_p90,
             d.obs07_frp_peak, d.obs08_frp_availability,
             d.obs09_type_distribution, d.obs10_pixel_area_median]
VALUES = [
    ["n_day", "n_night", "n_daynight_unknown", "pct_night"],
    ["n_frp_usable", "frp_median"], ["n_frp_usable", "frp_p90"],
    ["frp_max", "peak_latitude", "peak_longitude", "peak_acq_date", "peak_acq_time", "peak_datetime_utc"],
    ["n_eligible", "n_frp_usable", "n_frp_null", "n_frp_zero", "n_frp_negative", "pct_frp_usable"],
    ["version", "type_label", "n", "pct"], ["n_area", "pixel_area_median_km2"],
]


def records(*changes):
    base = dict(country="Portugal", instrument="MODIS", satellite="Terra",
                acq_date="2000-02-29", acq_time="0930", latitude=40.0, longitude=-8.0,
                acq_datetime_utc=pd.Timestamp("2000-02-29 09:30", tz="UTC"),
                type=0, confidence_raw="80", confidence_class="h", daynight="D", frp=10.0,
                pixel_area_km2=1.0, version="6.03")
    df = pd.DataFrame([base | change for change in changes])
    df["type"] = df["type"].astype("Int8")
    for field in ["version", "acq_time", "confidence_raw", "confidence_class"]:
        df[field] = df[field].astype("string")
    df["frp"] = df["frp"].astype("Float64")
    return df


@pytest.mark.parametrize("function,values", list(zip(FUNCTIONS, VALUES)))
def test_empty_schema(function, values):
    result = function(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == d.KEYS + values
    assert result.year.dtype == "int64"


@pytest.mark.parametrize("function", FUNCTIONS)
def test_missing_fields(function):
    with pytest.raises(ValueError, match="acq_date.*country"):
        function(records({}).drop(columns=["acq_date", "country"]))


@pytest.mark.parametrize("function", FUNCTIONS)
def test_input_is_unchanged_and_shuffle_invariant(function):
    df = records({}, {"frp": 30, "daynight": "N"}, {"country": "Spain"},
                 {"type": None}, {"type": 2}, {"confidence_class": None},
                 {"acq_date": "invalid"}, {"frp": None})
    df.index = [1] * len(df)
    before = df.copy(deep=True)
    result = function(df)
    assert_frame_equal(result, function(df.sample(frac=1, random_state=11)))
    assert_frame_equal(df, before)
    assert result.year.eq(2000).all()


def test_night_manual_unknown_and_zero_denominator():
    df = records({}, {"daynight": "N"}, {"daynight": None},
                 {"country": "Spain", "daynight": "?"}, {"daynight": "N", "type": 1})
    result = d.obs04_night_pct(df)
    assert result[["n_day", "n_night", "n_daynight_unknown"]].values.tolist() == [[1, 1, 1], [0, 0, 1]]
    assert result.pct_night.iloc[0] == 50.0
    assert pd.isna(result.pct_night.iloc[1])


@pytest.mark.parametrize("function,column,expected", [
    (d.obs05_frp_median, "frp_median", 20.0),
    (d.obs06_frp_p90, "frp_p90", 28.0),
])
def test_frp_manual_and_no_usable_groups(function, column, expected):
    df = records({"frp": 10}, {"frp": 30}, {"frp": 0}, {"frp": -2},
                 {"frp": None}, {"frp": 100, "confidence_class": "l"},
                 {"country": "Spain", "frp": None})
    result = function(df)
    assert result.n_frp_usable.tolist() == [2, 0]
    assert result[column].iloc[0] == expected
    assert pd.isna(result[column].iloc[1])
    assert function(records({}))[column].iloc[0] == 10.0


@pytest.mark.parametrize("function", FUNCTIONS[:5])
def test_eligibility_nulls_and_custom_filter(function):
    df = records({"type": None}, {"confidence_class": None}, {"type": 1},
                 {"confidence_class": "l"})
    assert function(df).empty
    custom = function(df, confidence=("l",))
    assert len(custom) == 1
    assert len(function(df, type_value=1)) == 1


def test_peak_manual_ties_and_missing_groups():
    df = records({"frp": 20, "acq_date": "2000-03-01"},
                 {"frp": 20, "acq_time": "1000"},
                 {"frp": 20, "latitude": 41},
                 {"frp": 20, "longitude": -7}, {"frp": 20}, {"frp": 10},
                 {"frp": 0, "country": "Spain"},
                 {"frp": 100, "type": 1})
    result = d.obs07_frp_peak(df)
    assert len(result) == 1
    assert result.iloc[0][VALUES[3]].tolist() == [
        20.0, 40.0, -8.0, "2000-02-29", "0930", pd.Timestamp("2000-02-29 09:30", tz="UTC")
    ]
    assert_frame_equal(result, d.obs07_frp_peak(df.sample(frac=1, random_state=4)))
    assert d.obs07_frp_peak(records({"frp": None})).empty


def test_availability_manual_partition():
    df = records({}, {"frp": 20}, {"frp": None}, {"frp": 0}, {"frp": -1},
                 {"frp": 999, "type": None})
    result = d.obs08_frp_availability(df)
    assert result.iloc[0][VALUES[4]].tolist() == [5, 2, 1, 1, 1, 40.0]
    assert result[["n_frp_usable", "n_frp_null", "n_frp_zero", "n_frp_negative"]].sum(axis=1).equals(result.n_eligible)


def test_type_manual_versions_null_and_unknown_codes():
    df = records({}, {"type": 1}, {"type": 2}, {"type": 3}, {"type": None},
                 {"type": 9}, {"version": "6.2"}, {"version": None})
    result = d.obs09_type_distribution(df)
    group = result.loc[result.version.eq("6.03")]
    assert group.type_label.tolist() == ["0", "1", "2", "3", "unknown"]
    assert group.n.tolist() == [1, 1, 1, 1, 2]
    assert group.pct.iloc[-1] == pytest.approx(33.333333333333336)
    assert result.groupby("version", dropna=False).pct.sum().tolist() == pytest.approx([100, 100, 100])


def test_area_manual_all_rows_and_finite_positive_only():
    df = records({"pixel_area_km2": 1}, {"pixel_area_km2": 3, "type": 1},
                 {"pixel_area_km2": 0}, {"pixel_area_km2": -1},
                 {"pixel_area_km2": np.inf}, {"pixel_area_km2": None})
    result = d.obs10_pixel_area_median(df)
    assert result.iloc[0][VALUES[6]].tolist() == [2, 2.0]
    assert d.obs10_pixel_area_median(records({"pixel_area_km2": None})).empty


def test_seeded_numeric_invariants():
    import statistics

    rng = np.random.default_rng(142)
    values = rng.integers(1, 500, size=101).tolist()
    df = records(*[{"frp": value, "pixel_area_km2": value} for value in values])
    assert d.obs05_frp_median(df).frp_median.iloc[0] == statistics.median(values)
    assert d.obs06_frp_p90(df).frp_p90.iloc[0] == sorted(values)[90]
    assert d.obs07_frp_peak(df).frp_max.iloc[0] == max(values)
    assert d.obs10_pixel_area_median(df).pixel_area_median_km2.iloc[0] == statistics.median(values)
    assert d.obs08_frp_availability(df).n_frp_usable.iloc[0] == 101


@pytest.mark.parametrize("function", FUNCTIONS)
def test_invalid_dates_and_years(function):
    df = records({"acq_date": "2001-02-29"}, {"acq_date": "2000-2-29"},
                 {"acq_date": None}, {"acq_date": "2001-01-01"}, {})
    assert function(df).year.tolist() == [2000, 2001]


def test_notebook_synthetic_pipeline_and_resume(tmp_path):
    import ast
    import contextlib
    import io
    import json
    from pathlib import Path
    import subprocess

    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/03_metrics_lote2.ipynb").read_text(encoding="utf-8"))
    sources = ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    for source in sources:
        ast.parse(source)
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
    processed = tmp_path / "processed"
    processed.mkdir()
    records({}, {"daynight": "N", "frp": 30}).to_parquet(processed / "modis_2000.parquet", index=False)
    records({"acq_date": "2002-01-01", "country": "Spain"}).to_parquet(processed / "modis_2002.parquet", index=False)
    namespace = dict(ROOT=tmp_path, REPO=repo, subprocess=subprocess)
    with contextlib.redirect_stdout(io.StringIO()):
        for source in sources[1:]:
            exec(compile(source, "03_metrics_lote2.ipynb", "exec"), namespace)
        assert len(namespace["tables"]) == 10
        assert namespace["tables"]["l2_obs05_frp_median"].frp_median.tolist() == [20, 10]
        assert namespace["tables"]["l2_qa01_schema_validation"].year.tolist() == [2000, 2002]
        assert len(namespace["tables"]["l2_add04_zero_detection_countries"]) == 4
        metrics = tmp_path / "metrics"
        partial = metrics / "_l2_parts/modis_2000/l2_obs05_frp_median.parquet"
        unchanged_mtime = partial.stat().st_mtime_ns
        exec(sources[2], namespace)
        assert partial.stat().st_mtime_ns == unchanged_mtime
        partial.unlink()
        exec(sources[2], namespace)
        assert partial.exists()
        marker = partial.parent / "_SUCCESS.json"
        marker.write_text('{"interrupted":')
        exec(sources[2], namespace)
        assert "revision" in json.loads(marker.read_text())
        exec(sources[3], namespace)
        exec(sources[4], namespace)
    log = pd.read_csv(metrics / "_log_lote2.csv")
    assert len(log) == 10
    assert len(list(metrics.glob("l2_*.parquet"))) == 10

"""Synthetic contracts for L6 cell-day overlap and Jaccard metrics."""

import random
import warnings

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.calendar_metrics import cal_daily, cal_monthly
from metrics.harmonization_overlap import har01_cellday_overlap, har02_jaccard


COUNTS = ["n_modis", "n_viirs", "n_both", "n_union"]
COLUMNS = ["country", "year", "month"] + COUNTS


def cells(*changes):
    base = dict(country="Portugal", date=pd.Timestamp("2018-02-01"), cell=1,
                instrument="MODIS", satellite="Terra")
    frame = pd.DataFrame([base | change for change in changes])
    frame["date"] = pd.to_datetime(frame.date)
    return frame


def worked_example():
    return cells({}, dict(cell=2), dict(cell=3), dict(cell=2, instrument="VIIRS", satellite="N20"),
                 dict(cell=3, instrument="VIIRS", satellite="N20"),
                 dict(cell=4, instrument="VIIRS", satellite="N20"),
                 dict(cell=5, instrument="VIIRS", satellite="N20"))


def test_literal_overlap_and_jaccard():
    overlap = har01_cellday_overlap(worked_example())
    expected = pd.DataFrame([["Portugal", 2018, 2, 3, 4, 2, 5]], columns=COLUMNS)
    expected["country"] = expected.country.astype("object")
    assert_frame_equal(overlap, expected)
    result = har02_jaccard(overlap)
    assert result.iloc[0].tolist() == ["Portugal", 2018, 2, 3, 4, 2, 5, 0.4]


@pytest.mark.parametrize("function,columns", [
    (har01_cellday_overlap, COLUMNS), (har02_jaccard, COLUMNS + ["jaccard"]),
])
def test_empty_schema(function, columns):
    result = function(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns
    assert result.country.dtype == "object"
    assert all(result[column].dtype == "int64" for column in COLUMNS[1:])
    if function == har02_jaccard:
        assert result.jaccard.dtype == "float64"


@pytest.mark.parametrize("function,source", [
    (har01_cellday_overlap, cells({})),
    (har02_jaccard, pd.DataFrame([["Portugal", 2018, 2, 1, 0, 0, 1]], columns=COLUMNS)),
])
def test_missing_columns_are_named(function, source):
    with pytest.raises(ValueError, match="country"):
        function(source.drop(columns="country"))


def test_satellite_duplicates_and_month_without_viirs():
    source = pd.concat([worked_example(), cells(dict(cell=1, satellite="Aqua"),
                                               dict(date="2018-03-01"),
                                               dict(date="2018-03-01", satellite="Aqua"))], ignore_index=True)
    result = har01_cellday_overlap(source)
    assert result[COUNTS].values.tolist() == [[3, 4, 2, 5], [1, 0, 0, 1]]
    assert har02_jaccard(result).jaccard.tolist() == [0.4, 0.0]
    assert (result.n_modis + result.n_viirs - result.n_both).equals(result.n_union)


def test_viirs_only_and_zero_union_jaccard():
    result = har01_cellday_overlap(cells(dict(instrument="VIIRS", satellite="N20")))
    assert result[COUNTS].values.tolist() == [[0, 1, 0, 1]]
    result.loc[0, COUNTS] = 0
    assert pd.isna(har02_jaccard(result).jaccard.iloc[0])


def test_calibration_start_boundary_and_custom_value():
    source = cells(dict(date="2017-12-31"), dict(date="2018-01-01"), dict(date="2022-01-01"))
    result = har01_cellday_overlap(source)
    assert result.year.tolist() == [2018, 2022]
    assert har01_cellday_overlap(source, cal_start=2022).year.tolist() == [2022]
    assert har01_cellday_overlap(source, cal_start=2023).empty


def test_utc_dates_are_normalized_before_deduplication():
    source = cells(dict(date="2018-02-01 00:00"), dict(date="2018-02-01 14:00", satellite="Aqua"))
    assert har01_cellday_overlap(source).n_modis.tolist() == [1]
    source["date"] = pd.to_datetime(["2018-01-31 23:30-01:00", "2018-02-01 04:00+00:00"], utc=True)
    result = har01_cellday_overlap(source)
    assert result.month.tolist() == [2]
    assert result.n_modis.tolist() == [1]


@pytest.mark.parametrize("instrument", ["UNKNOWN", None])
def test_unknown_instrument_raises(instrument):
    with pytest.raises(ValueError, match="instrument"):
        har01_cellday_overlap(cells(dict(instrument=instrument)))


def test_shuffle_input_immutability_and_group_independence():
    source = pd.concat([worked_example(), cells(dict(country="Spain", cell=99))], ignore_index=True)
    source.index = [1] * len(source)
    original = source.copy(deep=True)
    expected = har01_cellday_overlap(source)
    assert_frame_equal(expected, har01_cellday_overlap(source.sample(frac=1, random_state=17)))
    assert_frame_equal(source, original)
    assert_frame_equal(expected.iloc[:1].reset_index(drop=True), har01_cellday_overlap(worked_example()))
    before = expected.copy(deep=True)
    jaccard = har02_jaccard(expected)
    assert_frame_equal(jaccard, har02_jaccard(expected.sample(frac=1, random_state=17)))
    assert_frame_equal(expected, before)
    assert jaccard.jaccard.between(0, 1).all()


def test_categorical_keys_ignore_unused_categories_without_warnings():
    source = worked_example()
    expected = har01_cellday_overlap(source)
    source["country"] = pd.Categorical(source.country, categories=["Portugal", "Unused"])
    source["instrument"] = pd.Categorical(source.instrument, categories=["MODIS", "VIIRS", "Unused"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = har01_cellday_overlap(source)
    assert_frame_equal(result, expected)


def test_seeded_independent_set_oracle():
    rng = random.Random(602)
    source = cells(*[dict(country=rng.choice(["Portugal", "Spain"]),
                         date=pd.Timestamp(2018, rng.choice([1, 2, 3]), rng.randint(1, 5)),
                         cell=rng.randint(1, 12), instrument=rng.choice(["MODIS", "VIIRS"]),
                         satellite=rng.choice(["Terra", "Aqua", "N20"])) for _ in range(250)])
    pools = {}
    for row in source.itertuples(index=False):
        key = (row.country, row.date.year, row.date.month)
        pool = pools.setdefault(key, {"MODIS": set(), "VIIRS": set()})
        pool[row.instrument].add((row.date.date(), row.cell))
    expected = []
    for key, pool in sorted(pools.items()):
        modis, viirs = pool["MODIS"], pool["VIIRS"]
        expected.append([*key, len(modis), len(viirs), len(modis & viirs), len(modis | viirs)])
    expected = pd.DataFrame(expected, columns=COLUMNS)
    expected["country"] = expected.country.astype("object")
    assert_frame_equal(har01_cellday_overlap(source), expected)


def test_matches_l1_daily_and_monthly_series():
    source = pd.concat([worked_example(), cells(dict(satellite="Aqua"),
                                               dict(date="2018-02-02", cell=1),
                                               dict(country="Spain", cell=7))], ignore_index=True)
    overlap = har01_cellday_overlap(source)
    coverage = pd.DataFrame([
        [instrument, day, 1]
        for instrument in ["MODIS", "VIIRS"]
        for day in pd.date_range("2018-02-01", "2018-02-28")
    ], columns=["instrument", "date", "n_rows_global"])
    monthly = cal_monthly(cal_daily(source), coverage)
    for count, series in [("n_modis", "modis"), ("n_viirs", "viirs"), ("n_union", "combined")]:
        expected = monthly.loc[monthly.series.eq(series)].sort_values(["country", "year", "month"])
        assert overlap[count].tolist() == expected.cell_days.tolist()


@pytest.mark.parametrize("empty", [False, True])
def test_notebook_actual_cells_exports_resume_and_recovery(tmp_path, empty):
    import ast
    import contextlib
    import io
    import json
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/07_metrics_lote6.ipynb").read_text(encoding="utf-8"))
    sources = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            source = "".join(cell["source"])
            ast.parse(source)
            sources.append(source)
    assert "metricas-pipeline" in sources[0]
    processed = tmp_path / "processed"
    metrics = tmp_path / "metrics"
    processed.mkdir()
    metrics.mkdir()
    for year in [2018, 2022]:
        for sensor, instrument, latitudes in [
            ("modis", "MODIS", [0.0, 1.0, 2.0]),
            ("viirs-jpss1", "VIIRS", [1.0, 2.0, 3.0, 4.0]),
        ]:
            frame = pd.DataFrame(dict(country=["Portugal"] * len(latitudes),
                                      instrument=instrument, satellite="Terra" if sensor == "modis" else "N20",
                                      latitude=latitudes, longitude=0.0, acq_date=f"{year}-02-01",
                                      type=pd.Series([0] * len(latitudes), dtype="Int8"),
                                      confidence_class="h"))
            if empty:
                frame = frame.iloc[:0]
            frame.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    monthly = pd.DataFrame([
        ["Portugal", year, 2, series, value, False, 0]
        for year in range(2018, 2024)
        for series, value in [("modis", 3), ("viirs", 4)]
    ], columns=["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"])
    if empty:
        monthly = monthly.iloc[:0]
    monthly_path = metrics / "l1_cal_monthly.parquet"
    monthly.to_parquet(monthly_path, index=False)
    original_monthly = monthly_path.read_bytes()
    namespace = dict(ROOT=tmp_path, REPO=repo)
    with contextlib.redirect_stdout(io.StringIO()):
        for source in sources[1:]:
            exec(compile(source, "07_metrics_lote6.ipynb", "exec"), namespace)
        assert len(namespace["tables"]) == 7
        for name, expected in namespace["tables"].items():
            actual = pd.read_parquet(metrics / f"{name}.parquet")
            text = {column: "object" for column in expected.columns
                    if pd.api.types.is_object_dtype(expected[column].dtype)}
            assert_frame_equal(actual.astype(text), expected)
        if not empty:
            assert namespace["tables"]["l6_har01_overlap"].n_union.tolist() == [5, 5]
            assert namespace["tables"]["l6_har02_jaccard"].jaccard.tolist() == [0.4, 0.4]
        part = metrics / "_partial_lote6/har01_2018.parquet"
        marker = part.with_suffix(".json")
        unchanged = part.stat().st_mtime_ns
        exec(sources[3], namespace)
        assert part.stat().st_mtime_ns == unchanged
        marker.write_text("{", encoding="utf-8")
        exec(sources[3], namespace)
        assert "code" in json.loads(marker.read_text(encoding="utf-8"))
        part.unlink()
        exec(sources[3], namespace)
        assert part.is_file()
        namespace["FORCE"] = True
        exec(sources[3], namespace)
        namespace["FORCE"] = False
        for source in sources[4:]:
            exec(source, namespace)
    assert len(list(metrics.glob("l6_*.parquet"))) == 7
    assert not list(metrics.rglob("*.tmp"))
    assert monthly_path.read_bytes() == original_monthly
    log = pd.read_csv(metrics / "_log_lote6.csv")
    assert len(log) == 7
    parameters = json.loads(log.parameters.iloc[0])
    assert parameters["cal_end"] == 2021
    assert parameters["test_start"] == 2022
    assert parameters["min_pairs"] == 12
    monthly_path.unlink()
    with pytest.raises(FileNotFoundError, match="l1_cal_monthly.*02_metrics_lote1"):
        exec(sources[2], namespace)
    monthly.to_parquet(monthly_path, index=False)
    (processed / "viirs-jpss1_2018.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="Missing processed counterparts.*viirs-jpss1_2018"):
        exec(sources[2], namespace)

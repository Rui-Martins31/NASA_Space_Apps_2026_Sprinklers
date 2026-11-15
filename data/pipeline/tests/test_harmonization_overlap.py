"""Synthetic contracts for L6 per-cell cell-day overlap and Jaccard metrics."""

import random
import warnings

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.common import GLOBAL_CELL
from metrics.harmonization_overlap import global_overlap, har01_cellday_overlap, har02_jaccard


COUNTS = ["n_modis", "n_viirs", "n_both", "n_union"]
COLUMNS = ["cell", "year", "month"] + COUNTS


def cells(*changes):
    base = dict(date=pd.Timestamp("2018-02-01"), cell=1, instrument="MODIS", satellite="Terra")
    frame = pd.DataFrame([base | change for change in changes])
    frame["date"] = pd.to_datetime(frame.date)
    return frame


def worked_example():
    """Cells {1,2,3} for MODIS and {2,3,4,5} for VIIRS on the same day."""
    return cells({}, dict(cell=2), dict(cell=3), dict(cell=2, instrument="VIIRS", satellite="N20"),
                 dict(cell=3, instrument="VIIRS", satellite="N20"),
                 dict(cell=4, instrument="VIIRS", satellite="N20"),
                 dict(cell=5, instrument="VIIRS", satellite="N20"))


def test_literal_per_cell_overlap_and_jaccard():
    overlap = har01_cellday_overlap(worked_example())
    expected = pd.DataFrame([[1, 2018, 2, 1, 0, 0, 1], [2, 2018, 2, 1, 1, 1, 1],
                             [3, 2018, 2, 1, 1, 1, 1], [4, 2018, 2, 0, 1, 0, 1],
                             [5, 2018, 2, 0, 1, 0, 1]], columns=COLUMNS)
    assert_frame_equal(overlap, expected)
    assert har02_jaccard(overlap).jaccard.tolist() == [0.0, 1.0, 1.0, 0.0, 0.0]


def test_global_overlap_adds_cells_and_gives_the_documented_jaccard():
    overlap = har01_cellday_overlap(worked_example())
    result = global_overlap(overlap)
    assert result.values.tolist() == [[GLOBAL_CELL, 2018, 2, 3, 4, 2, 5]]
    assert har02_jaccard(result).iloc[0].tolist() == [GLOBAL_CELL, 2018, 2, 3, 4, 2, 5, 0.4]
    # Only counts are additive: a heavy cell weighs more than a light one in the global ratio.
    uneven = pd.DataFrame([[1, 2018, 2, 9, 9, 9, 9], [2, 2018, 2, 1, 1, 0, 2]], columns=COLUMNS)
    assert har02_jaccard(uneven).jaccard.tolist() == [1.0, 0.0]
    assert har02_jaccard(global_overlap(uneven)).jaccard.tolist() == [9 / 11]


def test_global_overlap_ignores_existing_global_rows_and_handles_empty():
    overlap = har01_cellday_overlap(worked_example())
    again = global_overlap(pd.concat([overlap, global_overlap(overlap)], ignore_index=True))
    assert_frame_equal(again, global_overlap(overlap))
    empty = global_overlap(pd.DataFrame())
    assert empty.empty and empty.columns.tolist() == COLUMNS
    with pytest.raises(ValueError, match="n_union"):
        global_overlap(overlap.drop(columns="n_union"))


@pytest.mark.parametrize("function,columns", [
    (har01_cellday_overlap, COLUMNS), (har02_jaccard, COLUMNS + ["jaccard"]),
    (global_overlap, COLUMNS),
])
def test_empty_schema(function, columns):
    result = function(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns
    assert all(result[column].dtype == "int64" for column in COLUMNS)
    if function == har02_jaccard:
        assert result.jaccard.dtype == "float64"


@pytest.mark.parametrize("function,source", [
    (har01_cellday_overlap, cells({})),
    (har02_jaccard, pd.DataFrame([[1, 2018, 2, 1, 0, 0, 1]], columns=COLUMNS)),
])
def test_missing_columns_are_named(function, source):
    with pytest.raises(ValueError, match="cell"):
        function(source.drop(columns="cell"))


def test_country_is_no_longer_required_or_used():
    source = worked_example().assign(country="anything")
    assert_frame_equal(har01_cellday_overlap(source), har01_cellday_overlap(worked_example()))


def test_missing_cell_values_are_rejected():
    source = cells({}, dict(cell=2)).astype({"cell": "float64"})
    source.loc[0, "cell"] = float("nan")
    with pytest.raises(ValueError, match="cell"):
        har01_cellday_overlap(source)


def test_satellite_duplicates_and_month_without_viirs():
    source = pd.concat([worked_example(), cells(dict(cell=1, satellite="Aqua"),
                                               dict(date="2018-03-01"),
                                               dict(date="2018-03-01", satellite="Aqua"))], ignore_index=True)
    result = har01_cellday_overlap(source)
    assert result.cell.tolist() == [1, 1, 2, 3, 4, 5]
    assert result.month.tolist() == [2, 3, 2, 2, 2, 2]
    assert result[COUNTS].values.tolist() == [[1, 0, 0, 1], [1, 0, 0, 1], [1, 1, 1, 1],
                                              [1, 1, 1, 1], [0, 1, 0, 1], [0, 1, 0, 1]]
    total = global_overlap(result)
    assert total[COUNTS].values.tolist() == [[3, 4, 2, 5], [1, 0, 0, 1]]
    assert har02_jaccard(total).jaccard.tolist() == [0.4, 0.0]
    assert (result.n_modis + result.n_viirs - result.n_both).equals(result.n_union)


def test_same_cell_on_two_days_counts_two_cell_days():
    source = cells(dict(), dict(date="2018-02-02"), dict(instrument="VIIRS", satellite="N20"))
    result = har01_cellday_overlap(source)
    assert result[COUNTS].values.tolist() == [[2, 1, 1, 2]]


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


def test_shuffle_input_immutability_and_cell_independence():
    source = pd.concat([worked_example(), cells(dict(cell=99))], ignore_index=True)
    source.index = [1] * len(source)
    original = source.copy(deep=True)
    expected = har01_cellday_overlap(source)
    assert_frame_equal(expected, har01_cellday_overlap(source.sample(frac=1, random_state=17)))
    assert_frame_equal(source, original)
    # A cell's row does not depend on the other cells.
    alone = har01_cellday_overlap(worked_example())
    assert_frame_equal(expected.loc[expected.cell.ne(99)].reset_index(drop=True), alone)
    before = expected.copy(deep=True)
    jaccard = har02_jaccard(expected)
    assert_frame_equal(jaccard, har02_jaccard(expected.sample(frac=1, random_state=17)).reset_index(drop=True))
    assert_frame_equal(expected, before)
    assert jaccard.jaccard.between(0, 1).all()


def test_categorical_keys_ignore_unused_categories_without_warnings():
    source = worked_example()
    expected = har01_cellday_overlap(source)
    source["instrument"] = pd.Categorical(source.instrument, categories=["MODIS", "VIIRS", "Unused"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = har01_cellday_overlap(source)
    assert_frame_equal(result, expected)


def test_seeded_independent_set_oracle():
    rng = random.Random(602)
    source = cells(*[dict(date=pd.Timestamp(2018, rng.choice([1, 2, 3]), rng.randint(1, 5)),
                         cell=rng.randint(1, 12), instrument=rng.choice(["MODIS", "VIIRS"]),
                         satellite=rng.choice(["Terra", "Aqua", "N20"])) for _ in range(250)])
    pools = {}
    for row in source.itertuples(index=False):
        key = (row.cell, row.date.year, row.date.month)
        pool = pools.setdefault(key, {"MODIS": set(), "VIIRS": set()})
        pool[row.instrument].add(row.date.date())
    expected = []
    for key, pool in sorted(pools.items()):
        modis, viirs = pool["MODIS"], pool["VIIRS"]
        expected.append([*key, len(modis), len(viirs), len(modis & viirs), len(modis | viirs)])
    expected = pd.DataFrame(expected, columns=COLUMNS)
    result = har01_cellday_overlap(source)
    assert_frame_equal(result, expected)
    # Counts are additive: the global rows equal the sums over all cells and the series
    # counts of distinct cell-days (MODIS, VIIRS, union) of each month.
    total = global_overlap(result)
    for row in total.itertuples(index=False):
        modis = {(r.cell, r.date) for r in source.itertuples() if r.instrument == "MODIS"
                 and (r.date.year, r.date.month) == (row.year, row.month)}
        viirs = {(r.cell, r.date) for r in source.itertuples() if r.instrument == "VIIRS"
                 and (r.date.year, r.date.month) == (row.year, row.month)}
        assert [row.n_modis, row.n_viirs, row.n_both, row.n_union] == [
            len(modis), len(viirs), len(modis & viirs), len(modis | viirs)]

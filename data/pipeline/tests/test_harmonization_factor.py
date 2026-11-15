"""Synthetic contracts for L6 per-cell comparable months, correlations and factors."""

import math
import warnings

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_factor as h
from metrics.common import GLOBAL_CELL


PT, ES, FR = 101, 102, 103      # arbitrary cell identifiers (the cells of the old countries)


def monthly_pairs(x, y, start_year=2018, cell=PT):
    records = []
    for index, (modis, viirs) in enumerate(zip(x, y)):
        year, month = start_year + index // 12, index % 12 + 1
        for series, value in [("modis", modis), ("viirs", viirs)]:
            records.append(dict(cell=cell, year=year, month=month, series=series,
                                cell_days=value, partial=False, n_unknown_days=0))
    return pd.DataFrame(records)


def yearly_pairs(x, y, cell=PT):
    result = monthly_pairs(x, y, cell=cell)
    result["year"] = np.repeat(np.arange(2018, 2018 + len(x)), 2)
    result["month"] = 3
    return result


def of(result, cell):
    return result.loc[result.cell.eq(cell)].reset_index(drop=True)


FUNCTIONS = [h.comparable_pairs, h.har03_comparable_months, h.har04_pearson,
             h.har05_spearman, h.har06_factor, h.har07_factor_uncertainty]
SCHEMAS = [
    ["cell", "year", "month", "period", "modis", "viirs"],
    ["cell", "period", "n_comparable_months", "first_month", "last_month"],
    ["cell", "period", "n_pairs", "pearson"],
    ["cell", "period", "n_pairs", "spearman"],
    ["cell", "scope", "n_cal_months", "sum_modis", "sum_viirs", "factor", "factor_used", "uses_global_fallback"],
    ["cell", "scope", "n_cal_years", "factor", "factor_loo_min", "factor_loo_max", "se_jackknife"],
]


@pytest.mark.parametrize("function,columns", list(zip(FUNCTIONS, SCHEMAS)))
def test_empty_output_contract(function, columns):
    result = function(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns
    assert result.cell.dtype == "int64"


@pytest.mark.parametrize("function", FUNCTIONS)
@pytest.mark.parametrize("problem", ["missing", "duplicate", "null_count", "global_cell_mixed"])
def test_invalid_input_schema(function, problem):
    source = monthly_pairs([1, 2], [2, 4])
    if problem == "missing":
        source = source.drop(columns="cell")
        message = "cell"
    elif problem == "duplicate":
        source = pd.concat([source, source.iloc[:1]], ignore_index=True)
        message = "[Dd]uplicate"
    elif problem == "global_cell_mixed":
        source = pd.concat([source, source.assign(cell=GLOBAL_CELL)], ignore_index=True)
        message = "GLOBAL_CELL"
    else:
        source["cell_days"] = source.cell_days.astype("Int64")
        source.loc[0, "cell_days"] = pd.NA
        message = "cell_days"
    with pytest.raises(ValueError, match=message):
        function(source)


def test_global_cell_input_is_accepted_without_the_global_row():
    """Sliced work: a pre-summed global series is processed on its own with include_global=False."""
    source = monthly_pairs([1] * 24, [2] * 24, cell=GLOBAL_CELL)
    result = h.har06_factor(source, include_global=False)
    assert result.cell.tolist() == [GLOBAL_CELL]
    assert result.scope.tolist() == ["global"]
    assert result.factor.tolist() == [2.0]
    assert h.comparable_pairs(source, include_global=False).cell.eq(GLOBAL_CELL).all()


def test_pairs_validity_period_boundaries_and_global_sum():
    source = yearly_pairs([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    source.loc[source.year.eq(2021), "month"] = 12
    source.loc[source.year.eq(2022), "month"] = 1
    extra = monthly_pairs([100, 200], [300, 600], cell=ES)
    extra.loc[0, "partial"] = True
    combined = source.iloc[:1].assign(series="combined", cell_days=999)
    result = h.comparable_pairs(pd.concat([source, extra, combined], ignore_index=True))
    portugal = of(result, PT)
    assert portugal.period.tolist() == ["calibration"] * 4 + ["test"]
    assert portugal.year.tolist() == [2018, 2019, 2020, 2021, 2022]
    global_rows = of(result, GLOBAL_CELL)
    assert global_rows[["year", "month", "modis", "viirs"]].values.tolist() == [
        [2018, 2, 200, 600], [2018, 3, 1, 2], [2019, 3, 2, 4],
        [2020, 3, 3, 6], [2021, 12, 4, 8], [2022, 1, 5, 10],
    ]
    assert result.cell.is_monotonic_increasing and result.cell.iloc[0] == GLOBAL_CELL
    without = h.comparable_pairs(pd.concat([source, extra], ignore_index=True), include_global=False)
    assert GLOBAL_CELL not in without.cell.tolist()


def test_comparable_excludes_partial_unknown_missing_and_precalibration():
    source = monthly_pairs([1, 2, 3, 4], [2, 4, 6, 8])
    source.loc[0, "partial"] = True
    source.loc[3, "n_unknown_days"] = 1
    source = source.drop(index=5)
    previous = monthly_pairs([99], [199], start_year=2017)
    result = h.comparable_pairs(pd.concat([source, previous], ignore_index=True))
    assert result.month.tolist() == [4, 4]
    relaxed = h.comparable_pairs(source, max_unknown_days=1)
    assert of(relaxed, PT).month.tolist() == [2, 4]


def test_manual_month_counts_and_zero_period_rows():
    source = yearly_pairs([10, 20, 30], [20, 40, 60])
    source.loc[source.year.eq(2020), "year"] = 2022
    source = pd.concat([source, monthly_pairs([1], [2], cell=ES).assign(partial=True)], ignore_index=True)
    result = h.har03_comparable_months(source)
    portugal = of(result, PT).set_index("period")
    assert portugal.loc["calibration"].tolist() == [PT, 2, "2018-03", "2019-03"]
    assert portugal.loc["test"].tolist() == [PT, 1, "2022-03", "2022-03"]
    assert portugal.loc["all", "n_comparable_months"] == 3
    spain = of(result, ES)
    assert spain.n_comparable_months.tolist() == [0, 0, 0]
    assert spain[["first_month", "last_month"]].isna().all().all()
    assert len(result) == 9
    assert sorted(result.cell.unique().tolist()) == [GLOBAL_CELL, PT, ES]


@pytest.mark.parametrize("function,column,expected", [
    (h.har04_pearson, "pearson", 0.7745966692414834),
    (h.har05_spearman, "spearman", 0.7378647873726218),
])
def test_literal_correlations(function, column, expected):
    source = monthly_pairs([1, 2, 3, 4, 5], [2, 4, 5, 4, 5])
    result = function(source, min_pairs=5)
    cell = of(result, PT).set_index("period")
    assert cell.loc["calibration", "n_pairs"] == 5
    assert cell.loc["calibration", column] == pytest.approx(expected, abs=1e-14)
    assert cell.loc["all", column] == pytest.approx(expected, abs=1e-14)
    assert pd.isna(cell.loc["test", column])


@pytest.mark.parametrize("function,column", [(h.har04_pearson, "pearson"), (h.har05_spearman, "spearman")])
def test_correlation_minimum_and_constant_boundary(function, column):
    source = monthly_pairs(list(range(1, 13)), list(range(2, 26, 2)))
    eleven = function(source.iloc[:-2])
    assert eleven[column].isna().all()
    twelve = function(source)
    assert twelve.loc[twelve.period.eq("calibration"), column].tolist() == pytest.approx([1, 1])
    assert function(source.assign(cell_days=1))[column].isna().all()
    assert function(source.iloc[:2], min_pairs=1)[column].isna().all()


def test_factor_ratio_of_sums_minimum_and_test_exclusion():
    source = monthly_pairs([1] * 24, [2] * 24)
    test = monthly_pairs([1], [10000], start_year=2022)
    result = h.har06_factor(pd.concat([source, test], ignore_index=True))
    assert result.cell.tolist() == [GLOBAL_CELL, PT]
    assert result.scope.tolist() == ["global", "cell"]
    assert result.n_cal_months.tolist() == [24, 24]
    assert result.sum_modis.tolist() == [24, 24]
    assert result.sum_viirs.tolist() == [48, 48]
    assert result.factor.tolist() == [2.0, 2.0]
    assert result.factor_used.tolist() == [2.0, 2.0]
    assert not result.uses_global_fallback.any()
    assert h.har06_factor(source.iloc[:-2]).factor.isna().all()
    uneven = h.har06_factor(monthly_pairs([1, 9], [3, 9]), min_cal_months=2)
    assert uneven.factor.tolist() == [1.2, 1.2]


def test_factor_global_fallback_and_zero_divisor():
    full = monthly_pairs([1] * 24, [2] * 24)
    short = monthly_pairs([1], [4], cell=ES)
    zero = monthly_pairs([0], [3], cell=FR)
    result = h.har06_factor(pd.concat([full, short, zero], ignore_index=True)).set_index("cell")
    assert result.loc[GLOBAL_CELL, "sum_modis"] == 25
    assert result.loc[GLOBAL_CELL, "sum_viirs"] == 55
    assert result.loc[GLOBAL_CELL, "factor"] == 2.2
    assert result.loc[PT, "factor_used"] == 2
    assert result.loc[ES, "factor_used"] == 2.2
    assert result.loc[FR, "factor_used"] == 2.2
    assert result.uses_global_fallback.to_dict() == {GLOBAL_CELL: False, PT: False, ES: True, FR: True}
    assert pd.isna(result.loc[ES, "factor"])
    none = h.har06_factor(zero)
    assert none.factor_used.isna().all()
    assert not none.uses_global_fallback.any()


def test_factor_fallback_uses_the_supplied_global_factor_when_sliced():
    short = monthly_pairs([1], [4], cell=ES)
    sliced = h.har06_factor(short, include_global=False, fallback_factor=1.5)
    assert sliced.cell.tolist() == [ES]
    assert sliced.factor_used.tolist() == [1.5]
    assert sliced.uses_global_fallback.tolist() == [True]
    assert pd.isna(sliced.factor.iloc[0])
    no_global = h.har06_factor(short, include_global=False)
    assert no_global.factor_used.isna().all() and not no_global.uses_global_fallback.any()
    nan_global = h.har06_factor(short, include_global=False, fallback_factor=np.nan)
    assert nan_global.factor_used.isna().all()
    # An explicit factor wins over the one of the call's own global row.
    both = h.har06_factor(pd.concat([monthly_pairs([1] * 24, [2] * 24), short], ignore_index=True),
                          fallback_factor=9.0).set_index("cell")
    assert both.loc[ES, "factor_used"] == 9.0
    assert both.loc[GLOBAL_CELL, "uses_global_fallback"] == False  # noqa: E712


def test_literal_jackknife_and_full_factor():
    source = yearly_pairs([100, 100, 200, 100], [150, 120, 260, 130])
    result = h.har07_factor_uncertainty(source, min_cal_months=1)
    assert result.scope.tolist() == ["global", "cell"]
    assert result.n_cal_years.tolist() == [4, 4]
    assert result.factor.tolist() == [1.32, 1.32]
    assert result.factor_loo_min.tolist() == pytest.approx([1.275, 1.275])
    assert result.factor_loo_max.tolist() == pytest.approx([1.35, 1.35])
    assert result.se_jackknife.tolist() == pytest.approx([math.sqrt(3 / 1280)] * 2)


def test_jackknife_insufficient_years_and_invalid_replicates():
    two = yearly_pairs([100, 100], [150, 120])
    result = h.har07_factor_uncertainty(two, min_cal_months=1)
    assert result.n_cal_years.tolist() == [2, 2]
    assert result.iloc[:, 3:].isna().all().all()
    zero = yearly_pairs([0, 0, 100], [3, 4, 150])
    result = h.har07_factor_uncertainty(zero, min_cal_months=1)
    assert result.n_cal_years.tolist() == [3, 3]
    assert result.iloc[:, 3:].isna().all().all()
    enough = yearly_pairs([10, 20, 30], [20, 40, 60])
    assert h.har07_factor_uncertainty(enough, min_cal_months=3).iloc[:, 3:].isna().all().all()


@pytest.mark.parametrize("function", FUNCTIONS)
def test_cell_isolation_order_immutability_and_categorical_series(function):
    source = yearly_pairs([100, 100, 200, 100], [150, 120, 260, 130])
    other = monthly_pairs([2, 3], [4, 7], cell=ES)
    merged = pd.concat([source, other], ignore_index=True)
    before = merged.copy(deep=True)
    result = function(merged)
    assert_frame_equal(result, function(merged.sample(frac=1, random_state=21)))
    assert_frame_equal(merged, before)
    baseline = function(source)
    assert_frame_equal(of(result, PT), of(baseline, PT))
    categorized = merged.copy()
    categorized["series"] = pd.Categorical(categorized.series, categories=["modis", "viirs", "combined"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert_frame_equal(function(categorized), result)


def test_custom_period_parameters_and_no_comparable_months():
    source = yearly_pairs([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    pairs = h.comparable_pairs(source, cal_start=2019, cal_end=2020, test_start=2022)
    assert of(pairs, PT).year.tolist() == [2019, 2020, 2022]
    assert of(pairs, PT).period.tolist() == ["calibration", "calibration", "test"]
    with pytest.raises(ValueError, match="disjoint"):
        h.comparable_pairs(source, cal_end=2022)
    invalid = source.assign(partial=True)
    assert h.comparable_pairs(invalid).empty
    assert h.har03_comparable_months(invalid).n_comparable_months.eq(0).all()
    assert h.har06_factor(invalid).factor_used.isna().all()
    assert h.har07_factor_uncertainty(invalid).n_cal_years.eq(0).all()


def test_seeded_pure_python_oracle_for_pairs_and_factor():
    import random
    rng = random.Random(601)
    rows = []
    expected = {}
    for cell in [PT, ES]:
        for year in range(2017, 2024):
            for month in [1, 4, 8]:
                x, y = rng.randint(0, 100), rng.randint(0, 200)
                modis_ok, viirs_ok = rng.choice([True, True, False]), rng.choice([True, True, False])
                for series, value, ok in [("modis", x, modis_ok), ("viirs", y, viirs_ok)]:
                    rows.append(dict(cell=cell, year=year, month=month, series=series,
                                     cell_days=value, partial=not ok, n_unknown_days=0))
                if year >= 2018 and modis_ok and viirs_ok:
                    expected[(cell, year, month)] = (x, y)
    source = pd.DataFrame(rows)
    result = h.comparable_pairs(source)
    actual = {(row.cell, row.year, row.month): (row.modis, row.viirs)
              for row in result.itertuples() if row.cell != GLOBAL_CELL}
    assert actual == expected
    factors = h.har06_factor(source, min_cal_months=1).set_index("cell")
    for cell in [PT, ES]:
        values = [pair for (key, year, month), pair in expected.items() if key == cell and year <= 2021]
        x_total = sum(pair[0] for pair in values)
        y_total = sum(pair[1] for pair in values)
        assert factors.loc[cell, "factor"] == pytest.approx(y_total / x_total)


def test_jackknife_has_no_global_fallback():
    full = monthly_pairs([10] * 48, [20] * 48)
    sparse = yearly_pairs([10, 10], [50, 50], cell=ES)
    source = pd.concat([full, sparse], ignore_index=True)
    point = h.har06_factor(source).set_index("cell")
    assert point.loc[ES, "uses_global_fallback"]
    result = h.har07_factor_uncertainty(source).set_index("cell")
    assert result.loc[GLOBAL_CELL, "n_cal_years"] == 4
    assert pd.notna(result.loc[GLOBAL_CELL, "factor"])
    assert result.loc[ES, "n_cal_years"] == 2
    assert result.loc[ES, ["factor", "factor_loo_min", "factor_loo_max", "se_jackknife"]].isna().all()


def test_global_month_count_and_correlations_use_summed_months():
    portugal = monthly_pairs([1, 3, 2], [6, 2, 4])
    spain = monthly_pairs([1, 2, 3], [1, 4, 7], cell=ES)
    source = pd.concat([portugal, spain], ignore_index=True)
    pairs = h.comparable_pairs(source)
    global_pairs = of(pairs, GLOBAL_CELL)
    assert global_pairs.modis.tolist() == [2, 5, 5]
    assert global_pairs.viirs.tolist() == [7, 6, 11]
    counts = h.har03_comparable_months(source)
    assert of(counts, GLOBAL_CELL).set_index("period").loc["calibration", "n_comparable_months"] == 3
    pearson = h.har04_pearson(source, min_pairs=3).set_index(["cell", "period"])
    # Centered global vectors are [-2, 1, 1] and [-1, -2, 3].
    assert pearson.loc[(GLOBAL_CELL, "calibration"), "pearson"] == pytest.approx(3 / math.sqrt(84))


def test_global_row_is_the_sum_of_cells_not_a_combination_of_their_statistics():
    """The cell with the larger counts dominates the global ratio of sums."""
    big = monthly_pairs([100] * 24, [300] * 24)
    small = monthly_pairs([1] * 24, [1] * 24, cell=ES)
    result = h.har06_factor(pd.concat([big, small], ignore_index=True)).set_index("cell")
    assert result.loc[PT, "factor"] == 3.0
    assert result.loc[ES, "factor"] == 1.0
    assert result.loc[GLOBAL_CELL, "factor"] == pytest.approx(7224 / 2424)


def test_independent_year_block_jackknife_oracle():
    from fractions import Fraction
    from statistics import mean

    source = monthly_pairs([3, 5, 9, 6, 8, 1, 7, 2, 4, 11, 10, 12] * 4,
                           [9, 8, 10, 7, 12, 2, 17, 6, 11, 20, 18, 23] * 4)
    source.loc[source.year.eq(2019), "cell_days"] += 3
    # Independent dictionaries collect the year blocks from the original input.
    blocks = {}
    for row in source.itertuples():
        year = blocks.setdefault(row.year, {"modis": 0, "viirs": 0})
        year[row.series] += row.cell_days
    full_x = sum(block["modis"] for block in blocks.values())
    full_y = sum(block["viirs"] for block in blocks.values())
    replicas = [Fraction(full_y - block["viirs"], full_x - block["modis"]) for block in blocks.values()]
    replica_mean = mean(replicas)
    variance = Fraction(3, 4) * sum((value - replica_mean) ** 2 for value in replicas)
    result = h.har07_factor_uncertainty(source).set_index("cell")
    assert result.loc[PT, "factor"] == pytest.approx(float(Fraction(full_y, full_x)))
    assert result.loc[PT, "factor_loo_min"] == pytest.approx(float(min(replicas)))
    assert result.loc[PT, "factor_loo_max"] == pytest.approx(float(max(replicas)))
    assert result.loc[PT, "se_jackknife"] == pytest.approx(math.sqrt(variance))


# --- reference: the old per-group implementation (slow), ported to `cell` keys ---------------

def _old_output(records, columns):
    result = pd.DataFrame(records, columns=columns)
    integers = {"cell", "year", "month", "modis", "viirs", "n_comparable_months", "n_pairs",
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
    keys = [column for column in ["cell", "year", "month", "period"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _old_prepared(monthly, **kwargs):
    pairs = h.comparable_pairs(monthly, **kwargs)
    cells = monthly.cell.drop_duplicates().tolist()
    if cells:
        cells.append(GLOBAL_CELL)
    return cells, pairs


def _old_period_pairs(cells, pairs):
    groups = {cell: group for cell, group in pairs.groupby("cell")}
    for cell in cells:
        group = groups.get(cell, pairs.iloc[:0])
        for period in h.PERIODS:
            yield cell, period, (group if period == "all" else group.loc[group.period.eq(period)])


def _old_correlation(x, y, min_pairs):
    if len(x) < min_pairs or len(x) < 2:
        return np.nan
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    xc, yc = x - x.mean(), y - y.mean()
    denominator = np.sqrt(np.dot(xc, xc) * np.dot(yc, yc))
    if denominator == 0:
        return np.nan
    return float(np.clip(np.dot(xc, yc) / denominator, -1, 1))


def old_har03(monthly, **kwargs):
    cells, pairs = _old_prepared(monthly, **kwargs)
    records = []
    for cell, period, group in _old_period_pairs(cells, pairs):
        first = last = None
        if len(group):
            ordered = group.sort_values(["year", "month"])
            first = f"{ordered.iloc[0].year:04d}-{ordered.iloc[0].month:02d}"
            last = f"{ordered.iloc[-1].year:04d}-{ordered.iloc[-1].month:02d}"
        records.append([cell, period, len(group), first, last])
    return _old_output(records, ["cell", "period", "n_comparable_months", "first_month", "last_month"])


def old_correlation_table(monthly, statistic, min_pairs, **kwargs):
    cells, pairs = _old_prepared(monthly, **kwargs)
    records = []
    for cell, period, group in _old_period_pairs(cells, pairs):
        x, y = group.modis, group.viirs
        if statistic == "spearman":
            x, y = x.rank(method="average"), y.rank(method="average")
        records.append([cell, period, len(group), _old_correlation(x, y, min_pairs)])
    return _old_output(records, ["cell", "period", "n_pairs", statistic])


def _old_factor(group, min_cal_months):
    sum_modis, sum_viirs = int(group.modis.sum()), int(group.viirs.sum())
    factor = np.nan
    if len(group) >= min_cal_months and sum_modis != 0:
        factor = sum_viirs / sum_modis
    return sum_modis, sum_viirs, factor


def old_har06(monthly, min_cal_months, **kwargs):
    cells, pairs = _old_prepared(monthly, **kwargs)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    groups = {cell: group for cell, group in calibration.groupby("cell")}
    records = []
    for cell in cells:
        group = groups.get(cell, calibration.iloc[:0])
        sum_modis, sum_viirs, factor = _old_factor(group, min_cal_months)
        records.append([cell, "global" if cell == GLOBAL_CELL else "cell", len(group),
                        sum_modis, sum_viirs, factor, factor, False])
    result = _old_output(records, h.FACTOR_COLUMNS)
    global_factor = result.loc[result.cell.eq(GLOBAL_CELL), "factor"]
    if len(global_factor) and pd.notna(global_factor.iloc[0]):
        fallback = result.factor.isna() & result.cell.ne(GLOBAL_CELL)
        result.loc[fallback, "factor_used"] = global_factor.iloc[0]
        result.loc[fallback, "uses_global_fallback"] = True
    return result


def old_har07(monthly, min_cal_months, min_cal_years, **kwargs):
    cells, pairs = _old_prepared(monthly, **kwargs)
    calibration = pairs.loc[pairs.period.eq("calibration")]
    groups = {cell: group for cell, group in calibration.groupby("cell")}
    records = []
    for cell in cells:
        group = groups.get(cell, calibration.iloc[:0])
        years = sorted(group.year.unique())
        estimates = [np.nan] * 4
        _, _, factor = _old_factor(group, min_cal_months)
        if len(years) >= min_cal_years and pd.notna(factor):
            replicates = [_old_factor(group.loc[group.year.ne(year)], min_cal_months)[2] for year in years]
            if np.isfinite(replicates).all():
                values = np.asarray(replicates, dtype=float)
                variance = (len(years) - 1) / len(years) * np.square(values - values.mean()).sum()
                estimates = [factor, values.min(), values.max(), np.sqrt(variance)]
        records.append([cell, "global" if cell == GLOBAL_CELL else "cell", len(years)] + estimates)
    return _old_output(records, h.UNCERTAINTY_COLUMNS)


def random_monthly(seed, n_cells=40):
    """Dense cells with gaps, partial months, ties and a few cells with only a few months."""
    rng = np.random.default_rng(seed)
    rows = []
    for cell in rng.choice(np.arange(1, 10_000), n_cells, replace=False).tolist():
        density = rng.choice([0.05, 0.5, 0.95])
        scale = int(rng.choice([2, 10, 100]))
        for year in range(2017, 2024):
            for month in range(1, 13):
                for series in ["modis", "viirs"]:
                    if rng.random() > density:
                        continue
                    rows.append((cell, year, month, series, int(rng.integers(0, scale)),
                                 bool(rng.random() < 0.05), int(rng.random() < 0.05)))
    return pd.DataFrame(rows, columns=["cell", "year", "month", "series", "cell_days",
                                       "partial", "n_unknown_days"])


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("options", [
    dict(min_pairs=h.MIN_PAIRS, min_cal_months=h.MIN_CAL_MONTHS, min_cal_years=3),
    dict(min_pairs=4, min_cal_months=6, min_cal_years=2),
    dict(min_pairs=2, min_cal_months=1, min_cal_years=1),
])
def test_vectorized_statistics_equal_the_slow_per_group_reference(seed, options):
    source = random_monthly(seed)
    kwargs = dict(max_unknown_days=1)
    assert_frame_equal(h.har03_comparable_months(source, **kwargs), old_har03(source, **kwargs))
    for statistic, function in [("pearson", h.har04_pearson), ("spearman", h.har05_spearman)]:
        assert_frame_equal(function(source, min_pairs=options["min_pairs"], **kwargs),
                           old_correlation_table(source, statistic, options["min_pairs"], **kwargs))
    assert_frame_equal(h.har06_factor(source, min_cal_months=options["min_cal_months"], **kwargs),
                       old_har06(source, options["min_cal_months"], **kwargs))
    assert_frame_equal(
        h.har07_factor_uncertainty(source, min_cal_months=options["min_cal_months"],
                                   min_cal_years=options["min_cal_years"], **kwargs),
        old_har07(source, options["min_cal_months"], options["min_cal_years"], **kwargs))


def test_random_reference_inputs_are_not_trivially_all_missing():
    """Guard for the equivalence test above: it compares real numbers, not only NA."""
    source = random_monthly(0)
    kwargs = dict(max_unknown_days=1)
    assert h.har04_pearson(source, min_pairs=4, **kwargs).pearson.notna().sum() > 5
    assert h.har05_spearman(source, min_pairs=4, **kwargs).spearman.notna().sum() > 5
    factors = h.har06_factor(source, min_cal_months=6, **kwargs)
    assert factors.factor.notna().sum() > 3 and factors.uses_global_fallback.any()
    assert h.har07_factor_uncertainty(source, min_cal_months=6, min_cal_years=2, **kwargs).se_jackknife.notna().sum() > 3


def test_many_cells_run_fast_enough_to_be_vectorized():
    """30 thousand cells x 3 periods must not need a Python loop per group (seconds, not minutes)."""
    import time
    rng = np.random.default_rng(5)
    n_cells = 30_000
    cells = np.repeat(np.arange(n_cells), 2 * 6)
    year = np.tile(np.repeat(np.arange(2018, 2024), 2), n_cells)
    series = np.tile(["modis", "viirs"], 6 * n_cells)
    source = pd.DataFrame(dict(cell=cells, year=year, month=2, series=series,
                               cell_days=rng.integers(0, 5, len(cells)), partial=False,
                               n_unknown_days=0))
    start = time.perf_counter()
    for function in [h.har03_comparable_months, h.har04_pearson, h.har05_spearman,
                     h.har06_factor, h.har07_factor_uncertainty]:
        result = function(source)
        assert len(result) >= n_cells
    assert time.perf_counter() - start < 60

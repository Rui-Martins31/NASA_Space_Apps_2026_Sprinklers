"""Synthetic contracts for L6 comparable months, correlations and factors."""

import math
import warnings

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_factor as h


def monthly_pairs(x, y, start_year=2018, country="Portugal"):
    records = []
    for index, (modis, viirs) in enumerate(zip(x, y)):
        year, month = start_year + index // 12, index % 12 + 1
        for series, value in [("modis", modis), ("viirs", viirs)]:
            records.append(dict(country=country, year=year, month=month, series=series,
                                cell_days=value, partial=False, n_unknown_days=0))
    return pd.DataFrame(records)


def yearly_pairs(x, y, country="Portugal"):
    result = monthly_pairs(x, y, country=country)
    result["year"] = np.repeat(np.arange(2018, 2018 + len(x)), 2)
    result["month"] = 3
    return result


FUNCTIONS = [h.comparable_pairs, h.har03_comparable_months, h.har04_pearson,
             h.har05_spearman, h.har06_factor, h.har07_factor_uncertainty]
SCHEMAS = [
    ["country", "year", "month", "period", "modis", "viirs"],
    ["country", "period", "n_comparable_months", "first_month", "last_month"],
    ["country", "period", "n_pairs", "pearson"],
    ["country", "period", "n_pairs", "spearman"],
    ["country", "scope", "n_cal_months", "sum_modis", "sum_viirs", "factor", "factor_used", "uses_global_fallback"],
    ["country", "scope", "n_cal_years", "factor", "factor_loo_min", "factor_loo_max", "se_jackknife"],
]


@pytest.mark.parametrize("function,columns", list(zip(FUNCTIONS, SCHEMAS)))
def test_empty_output_contract(function, columns):
    result = function(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns


@pytest.mark.parametrize("function", FUNCTIONS)
@pytest.mark.parametrize("problem", ["missing", "duplicate", "null_count"])
def test_invalid_input_schema(function, problem):
    source = monthly_pairs([1, 2], [2, 4])
    if problem == "missing":
        source = source.drop(columns="country")
        message = "country"
    elif problem == "duplicate":
        source = pd.concat([source, source.iloc[:1]], ignore_index=True)
        message = "[Dd]uplicate"
    else:
        source["cell_days"] = source.cell_days.astype("Int64")
        source.loc[0, "cell_days"] = pd.NA
        message = "cell_days"
    with pytest.raises(ValueError, match=message):
        function(source)


def test_pairs_validity_period_boundaries_and_global_sum():
    source = yearly_pairs([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    source.loc[source.year.eq(2021), "month"] = 12
    source.loc[source.year.eq(2022), "month"] = 1
    extra = monthly_pairs([100, 200], [300, 600], country="Spain")
    extra.loc[0, "partial"] = True
    combined = source.iloc[:1].assign(series="combined", cell_days=999)
    result = h.comparable_pairs(pd.concat([source, extra, combined], ignore_index=True))
    portugal = result.loc[result.country.eq("Portugal")]
    assert portugal.period.tolist() == ["calibration"] * 4 + ["test"]
    assert portugal.year.tolist() == [2018, 2019, 2020, 2021, 2022]
    global_rows = result.loc[result.country.eq("ALL")]
    assert global_rows[["year", "month", "modis", "viirs"]].values.tolist() == [
        [2018, 2, 200, 600], [2018, 3, 1, 2], [2019, 3, 2, 4],
        [2020, 3, 3, 6], [2021, 12, 4, 8], [2022, 1, 5, 10],
    ]


def test_comparable_excludes_partial_unknown_missing_and_precalibration():
    source = monthly_pairs([1, 2, 3, 4], [2, 4, 6, 8])
    source.loc[0, "partial"] = True
    source.loc[3, "n_unknown_days"] = 1
    source = source.drop(index=5)
    previous = monthly_pairs([99], [199], start_year=2017)
    result = h.comparable_pairs(pd.concat([source, previous], ignore_index=True))
    assert result.month.tolist() == [4, 4]
    relaxed = h.comparable_pairs(source, max_unknown_days=1)
    assert relaxed.loc[relaxed.country.eq("Portugal"), "month"].tolist() == [2, 4]


def test_manual_month_counts_and_zero_period_rows():
    source = yearly_pairs([10, 20, 30], [20, 40, 60])
    source.loc[source.year.eq(2020), "year"] = 2022
    source = pd.concat([source, monthly_pairs([1], [2], country="Spain").assign(partial=True)], ignore_index=True)
    result = h.har03_comparable_months(source)
    portugal = result.loc[result.country.eq("Portugal")].set_index("period")
    assert portugal.loc["calibration"].tolist() == ["Portugal", 2, "2018-03", "2019-03"]
    assert portugal.loc["test"].tolist() == ["Portugal", 1, "2022-03", "2022-03"]
    assert portugal.loc["all", "n_comparable_months"] == 3
    spain = result.loc[result.country.eq("Spain")]
    assert spain.n_comparable_months.tolist() == [0, 0, 0]
    assert spain[["first_month", "last_month"]].isna().all().all()
    assert len(result) == 9


@pytest.mark.parametrize("function,column,expected", [
    (h.har04_pearson, "pearson", 0.7745966692414834),
    (h.har05_spearman, "spearman", 0.7378647873726218),
])
def test_literal_correlations(function, column, expected):
    source = monthly_pairs([1, 2, 3, 4, 5], [2, 4, 5, 4, 5])
    result = function(source, min_pairs=5)
    country = result.loc[result.country.eq("Portugal")].set_index("period")
    assert country.loc["calibration", "n_pairs"] == 5
    assert country.loc["calibration", column] == pytest.approx(expected, abs=1e-14)
    assert country.loc["all", column] == pytest.approx(expected, abs=1e-14)
    assert pd.isna(country.loc["test", column])


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
    short = monthly_pairs([1], [4], country="Spain")
    zero = monthly_pairs([0], [3], country="France")
    result = h.har06_factor(pd.concat([full, short, zero], ignore_index=True)).set_index("country")
    assert result.loc["ALL", "sum_modis"] == 25
    assert result.loc["ALL", "sum_viirs"] == 55
    assert result.loc["ALL", "factor"] == 2.2
    assert result.loc["Portugal", "factor_used"] == 2
    assert result.loc["Spain", "factor_used"] == 2.2
    assert result.loc["France", "factor_used"] == 2.2
    assert result.uses_global_fallback.to_dict() == {"ALL": False, "France": True, "Portugal": False, "Spain": True}
    assert pd.isna(result.loc["Spain", "factor"])
    none = h.har06_factor(zero)
    assert none.factor_used.isna().all()
    assert not none.uses_global_fallback.any()


def test_literal_jackknife_and_full_factor():
    source = yearly_pairs([100, 100, 200, 100], [150, 120, 260, 130])
    result = h.har07_factor_uncertainty(source, min_cal_months=1)
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
def test_group_isolation_order_immutability_and_categorical_keys(function):
    source = yearly_pairs([100, 100, 200, 100], [150, 120, 260, 130])
    other = monthly_pairs([2, 3], [4, 7], country="Spain")
    merged = pd.concat([source, other], ignore_index=True)
    before = merged.copy(deep=True)
    result = function(merged)
    assert_frame_equal(result, function(merged.sample(frac=1, random_state=21)))
    assert_frame_equal(merged, before)
    portugal = result.loc[result.country.eq("Portugal")].reset_index(drop=True)
    baseline = function(source)
    baseline = baseline.loc[baseline.country.eq("Portugal")].reset_index(drop=True)
    assert_frame_equal(portugal, baseline)
    categorized = merged.copy()
    categorized["country"] = pd.Categorical(categorized.country, categories=["Portugal", "Spain", "Unused"])
    categorized["series"] = pd.Categorical(categorized.series, categories=["modis", "viirs", "combined"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert_frame_equal(function(categorized), result)


def test_custom_period_parameters_and_no_comparable_months():
    source = yearly_pairs([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    pairs = h.comparable_pairs(source, cal_start=2019, cal_end=2020, test_start=2022)
    assert pairs.loc[pairs.country.eq("Portugal"), "year"].tolist() == [2019, 2020, 2022]
    assert pairs.loc[pairs.country.eq("Portugal"), "period"].tolist() == ["calibration", "calibration", "test"]
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
    for country in ["Portugal", "Spain"]:
        for year in range(2017, 2024):
            for month in [1, 4, 8]:
                x, y = rng.randint(0, 100), rng.randint(0, 200)
                modis_ok, viirs_ok = rng.choice([True, True, False]), rng.choice([True, True, False])
                for series, value, ok in [("modis", x, modis_ok), ("viirs", y, viirs_ok)]:
                    rows.append(dict(country=country, year=year, month=month, series=series,
                                     cell_days=value, partial=not ok, n_unknown_days=0))
                if year >= 2018 and modis_ok and viirs_ok:
                    expected[(country, year, month)] = (x, y)
    source = pd.DataFrame(rows)
    result = h.comparable_pairs(source)
    actual = {(row.country, row.year, row.month): (row.modis, row.viirs)
              for row in result.itertuples() if row.country != "ALL"}
    assert actual == expected
    factors = h.har06_factor(source, min_cal_months=1).set_index("country")
    for country in ["Portugal", "Spain"]:
        values = [pair for (key, year, month), pair in expected.items() if key == country and year <= 2021]
        x_total = sum(pair[0] for pair in values)
        y_total = sum(pair[1] for pair in values)
        assert factors.loc[country, "factor"] == pytest.approx(y_total / x_total)


def test_jackknife_has_no_global_fallback():
    full = monthly_pairs([10] * 48, [20] * 48)
    sparse = yearly_pairs([10, 10], [50, 50], country="Spain")
    source = pd.concat([full, sparse], ignore_index=True)
    point = h.har06_factor(source).set_index("country")
    assert point.loc["Spain", "uses_global_fallback"]
    result = h.har07_factor_uncertainty(source).set_index("country")
    assert result.loc["ALL", "n_cal_years"] == 4
    assert pd.notna(result.loc["ALL", "factor"])
    assert result.loc["Spain", "n_cal_years"] == 2
    assert result.loc["Spain", ["factor", "factor_loo_min", "factor_loo_max", "se_jackknife"]].isna().all()


def test_global_month_count_and_correlations_use_summed_months():
    portugal = monthly_pairs([1, 3, 2], [6, 2, 4])
    spain = monthly_pairs([1, 2, 3], [1, 4, 7], country="Spain")
    source = pd.concat([portugal, spain], ignore_index=True)
    pairs = h.comparable_pairs(source)
    global_pairs = pairs.loc[pairs.country.eq("ALL")]
    assert global_pairs.modis.tolist() == [2, 5, 5]
    assert global_pairs.viirs.tolist() == [7, 6, 11]
    counts = h.har03_comparable_months(source)
    assert counts.loc[counts.country.eq("ALL") & counts.period.eq("calibration"), "n_comparable_months"].tolist() == [3]
    pearson = h.har04_pearson(source, min_pairs=3).set_index(["country", "period"])
    # Centered global vectors are [-2, 1, 1] and [-1, -2, 3].
    assert pearson.loc[("ALL", "calibration"), "pearson"] == pytest.approx(3 / math.sqrt(84))


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
    result = h.har07_factor_uncertainty(source).set_index("country")
    assert result.loc["Portugal", "factor"] == pytest.approx(float(Fraction(full_y, full_x)))
    assert result.loc["Portugal", "factor_loo_min"] == pytest.approx(float(min(replicas)))
    assert result.loc["Portugal", "factor_loo_max"] == pytest.approx(float(max(replicas)))
    assert result.loc["Portugal", "se_jackknife"] == pytest.approx(math.sqrt(variance))

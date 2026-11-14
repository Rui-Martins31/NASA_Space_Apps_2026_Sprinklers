"""Synthetic test-window contracts for L7 harmonization error metrics."""

import math
import random
import warnings

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_errors as h


def monthly(x=(10, 20, 30), y=(20, 40, 60), year=2022, country="Portugal"):
    records = []
    for index, (modis, viirs) in enumerate(zip(x, y)):
        for series, value in [("modis", modis), ("viirs", viirs)]:
            records.append(dict(country=country, year=year + index // 12,
                                month=index % 12 + 1, series=series, cell_days=value,
                                partial=False, n_unknown_days=0))
    return pd.DataFrame(records)


def factors(value=2.0, countries=("Portugal", "ALL"), fallback=False):
    return pd.DataFrame(dict(country=list(countries), factor_used=value,
                             uses_global_fallback=fallback))


COMMON = ["country", "period", "n_pairs", "n_adjusted_pairs"]
PREDICTIONS = ["country", "year", "month", "modis", "viirs", "factor_used",
               "uses_global_fallback", "modis_adjusted", "error_raw", "error_adjusted"]
CASES = [
    (h.test_predictions, PREDICTIONS),
    (h.har08_mae, COMMON + ["mae_raw", "mae_adjusted"]),
    (h.har09_wape, COMMON + ["wape_raw", "wape_adjusted"]),
    (h.har10_bias, COMMON + ["bias_raw", "bias_adjusted"]),
    (h.har11_error_reduction, COMMON + ["mae_raw", "mae_adjusted", "error_reduction_pct"]),
]


@pytest.mark.parametrize("function,columns", CASES)
def test_empty_output_schema(function, columns):
    result = function(pd.DataFrame(), pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == columns
    assert result.country.dtype == "object"


def test_literal_predictions_and_four_error_metrics():
    source, calibration = monthly(), factors()
    predictions = h.test_predictions(source, calibration)
    portugal = predictions.loc[predictions.country.eq("Portugal")]
    assert portugal.modis_adjusted.tolist() == [20.0, 40.0, 60.0]
    assert portugal.error_raw.tolist() == [-10.0, -20.0, -30.0]
    assert portugal.error_adjusted.tolist() == [0.0, 0.0, 0.0]
    assert h.har08_mae(source, calibration).iloc[1].tolist() == ["Portugal", "test", 3, 3, 20.0, 0.0]
    assert h.har09_wape(source, calibration).iloc[1].tolist() == ["Portugal", "test", 3, 3, 50.0, 0.0]
    assert h.har10_bias(source, calibration).iloc[1].tolist() == ["Portugal", "test", 3, 3, -20.0, 0.0]
    assert h.har11_error_reduction(source, calibration).iloc[1].tolist() == ["Portugal", "test", 3, 3, 20.0, 0.0, 100.0]


def test_signed_bias_and_error_reduction_can_show_deterioration():
    source = monthly((10, 20, 30), (15, 30, 45))
    result = h.har10_bias(source, factors(3))
    assert result.bias_raw.tolist() == [-10.0, -10.0]
    assert result.bias_adjusted.tolist() == [30.0, 30.0]
    improvement = h.har11_error_reduction(source, factors(3))
    assert improvement.error_reduction_pct.tolist() == [-200.0, -200.0]


def test_wape_uses_sum_of_reference_over_all_test_months():
    result = h.har09_wape(monthly((10, 100, 1), (20, 200, 1)), factors(2))
    assert result.wape_raw.iloc[0] == pytest.approx(100 * 110 / 221)
    assert result.wape_adjusted.iloc[0] == pytest.approx(100 / 221)


def test_zero_reference_and_zero_initial_error_are_unavailable():
    source = monthly((0, 2, 4), (0, 0, 0))
    assert h.har09_wape(source, factors()).iloc[0][["wape_raw", "wape_adjusted"]].isna().all()
    exact = monthly((1, 2, 3), (1, 2, 3))
    result = h.har11_error_reduction(exact, factors(2))
    assert result.mae_raw.tolist() == [0.0, 0.0]
    assert result.error_reduction_pct.isna().all()


@pytest.mark.parametrize("function,columns", CASES[1:])
def test_missing_factors_preserve_raw_metrics(function, columns):
    result = function(monthly(), factors(countries=("ALL",)))
    portugal = result.loc[result.country.eq("Portugal")].iloc[0]
    assert portugal.n_pairs == 3
    assert portugal.n_adjusted_pairs == 0
    adjusted = [column for column in columns if column.endswith("_adjusted") or column == "error_reduction_pct"]
    assert portugal[adjusted].isna().all()
    assert pd.notna(portugal[[column for column in columns if column.endswith("_raw")]]).all()


def test_empty_factors_and_explicit_unavailable_factor():
    missing = h.test_predictions(monthly(), pd.DataFrame())
    assert missing.error_raw.tolist() == [-10.0, -20.0, -30.0] * 2
    assert missing.error_adjusted.isna().all()
    assert not missing.uses_global_fallback.any()
    explicit = h.test_predictions(monthly(), factors(np.nan, fallback=True))
    assert explicit.error_adjusted.isna().all()
    assert explicit.uses_global_fallback.all()


def test_zero_factor_is_usable_and_existing_fallback_flag_is_preserved():
    result = h.har08_mae(monthly(), factors(0, fallback=True))
    assert result.n_adjusted_pairs.tolist() == [3, 3]
    assert result.mae_adjusted.tolist() == [40.0, 40.0]
    predictions = h.test_predictions(monthly(), factors(0, fallback=True))
    assert predictions.uses_global_fallback.all()


def test_test_window_excludes_calibration_invalid_and_unpaired_months():
    source = pd.concat([monthly(year=2021), monthly()], ignore_index=True)
    source.loc[(source.year == 2022) & (source.month == 2) & (source.series == "viirs"), "partial"] = True
    source = source.loc[~((source.year == 2022) & (source.month == 3) & (source.series == "viirs"))]
    source = pd.concat([source, monthly(year=2022).assign(country="Spain", partial=True)], ignore_index=True)
    result = h.har08_mae(source, factors())
    assert result.country.tolist() == ["ALL", "Portugal", "Spain"]
    assert result.n_pairs.tolist() == [1, 1, 0]
    assert result.mae_raw.iloc[1] == 10.0
    assert result.iloc[2][["mae_raw", "mae_adjusted"]].isna().all()
    assert h.test_predictions(source, factors()).year.eq(2022).all()


def test_unknown_coverage_limit_and_custom_test_start():
    source = pd.concat([monthly(year=2021), monthly()], ignore_index=True)
    source.loc[source.year.eq(2022), "n_unknown_days"] = 1
    assert h.har08_mae(source, factors()).n_pairs.tolist() == [0, 0]
    assert h.har08_mae(source, factors(), max_unknown_days=1).n_pairs.tolist() == [3, 3]
    result = h.har08_mae(source, factors(), cal_end=2020, test_start=2021)
    assert result.n_pairs.tolist() == [3, 3]


def test_global_predictions_use_the_supplied_global_factor():
    source = pd.concat([monthly((10,), (20,)), monthly((30,), (90,), country="Spain")], ignore_index=True)
    calibration = pd.DataFrame([
        ["Portugal", 2.0, False], ["Spain", 3.0, False], ["ALL", 2.5, False]
    ], columns=["country", "factor_used", "uses_global_fallback"])
    result = h.test_predictions(source, calibration)
    global_row = result.loc[result.country.eq("ALL")].iloc[0]
    assert global_row.modis == 40
    assert global_row.viirs == 110
    assert global_row.modis_adjusted == 100.0
    assert global_row.error_adjusted == -10.0


def test_single_pair_has_an_error_estimate_without_correlation_minimum():
    source = monthly((10,), (20,))
    assert h.har08_mae(source, factors()).mae_raw.tolist() == [10.0, 10.0]
    assert h.har08_mae(source, factors()).mae_adjusted.tolist() == [0.0, 0.0]
    assert h.har11_error_reduction(source, factors()).error_reduction_pct.tolist() == [100.0, 100.0]


def test_calibration_only_input_keeps_zero_test_counts():
    result = h.har08_mae(monthly(year=2021), factors())
    assert result.country.tolist() == ["ALL", "Portugal"]
    assert result.n_pairs.tolist() == [0, 0]
    assert result.n_adjusted_pairs.tolist() == [0, 0]
    assert result[["mae_raw", "mae_adjusted"]].isna().all().all()


def test_factor_used_is_applied_instead_of_unused_country_factor():
    calibration = factors(2, fallback=True)
    calibration["factor"] = np.nan
    result = h.test_predictions(monthly(), calibration)
    assert result.factor_used.tolist() == [2.0] * 6
    assert result.modis_adjusted.tolist() == [20.0, 40.0, 60.0] * 2
    assert result.uses_global_fallback.all()


@pytest.mark.parametrize("function,columns", CASES)
@pytest.mark.parametrize("problem", ["monthly_missing", "monthly_duplicate", "factor_missing", "factor_duplicate"])
def test_invalid_input_schema_is_descriptive(function, columns, problem):
    source, calibration = monthly(), factors()
    if problem == "monthly_missing":
        source = source.drop(columns="country")
        message = "country"
    elif problem == "monthly_duplicate":
        source = pd.concat([source, source.iloc[:1]], ignore_index=True)
        message = "[Dd]uplicate"
    elif problem == "factor_missing":
        calibration = calibration.drop(columns="factor_used")
        message = "factor_used"
    else:
        calibration = pd.concat([calibration, calibration.iloc[:1]], ignore_index=True)
        message = "[Dd]uplicate"
    with pytest.raises(ValueError, match=message):
        function(source, calibration)


@pytest.mark.parametrize("value", [-1.0, np.inf, -np.inf])
def test_invalid_numeric_factors_raise(value):
    with pytest.raises(ValueError, match="factor_used"):
        h.test_predictions(monthly(), factors(value))


@pytest.mark.parametrize("function,columns", CASES)
def test_shuffle_immutability_and_categorical_keys(function, columns):
    source = pd.concat([monthly(), monthly(country="Spain")], ignore_index=True)
    calibration = factors(countries=("Portugal", "Spain", "ALL"))
    before_source, before_factors = source.copy(deep=True), calibration.copy(deep=True)
    expected = function(source, calibration)
    shuffled = function(source.sample(frac=1, random_state=71), calibration.sample(frac=1, random_state=72))
    assert_frame_equal(shuffled, expected)
    assert_frame_equal(source, before_source)
    assert_frame_equal(calibration, before_factors)
    source["country"] = pd.Categorical(source.country, categories=["Spain", "Portugal", "Unused"])
    source["series"] = pd.Categorical(source.series, categories=["modis", "viirs", "combined"])
    calibration["country"] = pd.Categorical(calibration.country, categories=["Portugal", "Spain", "ALL", "Unused"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert_frame_equal(function(source, calibration), expected)


def test_seeded_independent_error_arithmetic_oracle():
    rng = random.Random(708)
    x = [rng.randint(0, 100) for _ in range(30)]
    y = [rng.randint(1, 200) for _ in range(30)]
    source, calibration = monthly(x, y), factors(1.25)
    raw = [a - b for a, b in zip(x, y)]
    adjusted = [1.25 * a - b for a, b in zip(x, y)]
    expected_mae = sum(map(abs, raw)) / 30
    expected_adjusted_mae = sum(map(abs, adjusted)) / 30
    assert h.har08_mae(source, calibration).mae_raw.iloc[0] == pytest.approx(expected_mae)
    assert h.har08_mae(source, calibration).mae_adjusted.iloc[0] == pytest.approx(expected_adjusted_mae)
    assert h.har09_wape(source, calibration).wape_adjusted.iloc[0] == pytest.approx(100 * sum(map(abs, adjusted)) / sum(y))
    assert h.har10_bias(source, calibration).bias_adjusted.iloc[0] == pytest.approx(sum(adjusted) / 30)
    assert h.har11_error_reduction(source, calibration).error_reduction_pct.iloc[0] == pytest.approx(100 * (expected_mae - expected_adjusted_mae) / expected_mae)
    assert math.isfinite(expected_adjusted_mae)

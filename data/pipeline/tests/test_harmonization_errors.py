"""Synthetic test-window contracts for L7 harmonization error metrics."""

import math
import random
import warnings

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_errors as h
from metrics.common import GLOBAL_CELL


PT, ES = 101, 102      # arbitrary cell identifiers (the cells of the old countries)


def monthly(x=(10, 20, 30), y=(20, 40, 60), year=2022, cell=PT):
    records = []
    for index, (modis, viirs) in enumerate(zip(x, y)):
        for series, value in [("modis", modis), ("viirs", viirs)]:
            records.append(dict(cell=cell, year=year + index // 12,
                                month=index % 12 + 1, series=series, cell_days=value,
                                partial=False, n_unknown_days=0))
    return pd.DataFrame(records)


def factors(value=2.0, cells=(PT, GLOBAL_CELL), fallback=False):
    return pd.DataFrame(dict(cell=list(cells), factor_used=value,
                             uses_global_fallback=fallback))


COMMON = ["cell", "period", "n_pairs", "n_adjusted_pairs"]
PREDICTIONS = ["cell", "year", "month", "modis", "viirs", "factor_used",
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
    assert result.cell.dtype == "int64"


def test_literal_predictions_and_four_error_metrics():
    source, calibration = monthly(), factors()
    predictions = h.test_predictions(source, calibration)
    portugal = predictions.loc[predictions.cell.eq(PT)]
    assert portugal.modis_adjusted.tolist() == [20.0, 40.0, 60.0]
    assert portugal.error_raw.tolist() == [-10.0, -20.0, -30.0]
    assert portugal.error_adjusted.tolist() == [0.0, 0.0, 0.0]
    assert h.har08_mae(source, calibration).iloc[1].tolist() == [PT, "test", 3, 3, 20.0, 0.0]
    assert h.har09_wape(source, calibration).iloc[1].tolist() == [PT, "test", 3, 3, 50.0, 0.0]
    assert h.har10_bias(source, calibration).iloc[1].tolist() == [PT, "test", 3, 3, -20.0, 0.0]
    assert h.har11_error_reduction(source, calibration).iloc[1].tolist() == [PT, "test", 3, 3, 20.0, 0.0, 100.0]


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
    result = function(monthly(), factors(cells=(GLOBAL_CELL,)))
    portugal = result.loc[result.cell.eq(PT)].iloc[0]
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
    source = pd.concat([source, monthly(year=2022).assign(cell=ES, partial=True)], ignore_index=True)
    result = h.har08_mae(source, factors())
    assert result.cell.tolist() == [GLOBAL_CELL, PT, ES]
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
    source = pd.concat([monthly((10,), (20,)), monthly((30,), (90,), cell=ES)], ignore_index=True)
    calibration = pd.DataFrame([
        [PT, 2.0, False], [ES, 3.0, False], [GLOBAL_CELL, 2.5, False]
    ], columns=["cell", "factor_used", "uses_global_fallback"])
    result = h.test_predictions(source, calibration)
    global_row = result.loc[result.cell.eq(GLOBAL_CELL)].iloc[0]
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
    assert result.cell.tolist() == [GLOBAL_CELL, PT]
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
        source = source.drop(columns="cell")
        message = "cell"
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
def test_shuffle_immutability_and_categorical_series(function, columns):
    source = pd.concat([monthly(), monthly(cell=ES)], ignore_index=True)
    calibration = factors(cells=(PT, ES, GLOBAL_CELL))
    before_source, before_factors = source.copy(deep=True), calibration.copy(deep=True)
    expected = function(source, calibration)
    shuffled = function(source.sample(frac=1, random_state=71), calibration.sample(frac=1, random_state=72))
    assert_frame_equal(shuffled, expected)
    assert_frame_equal(source, before_source)
    assert_frame_equal(calibration, before_factors)
    source["series"] = pd.Categorical(source.series, categories=["modis", "viirs", "combined"])
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


def test_include_global_false_omits_global_rows_and_cells_without_factor_keep_raw_errors():
    source = pd.concat([monthly(), monthly(cell=ES)], ignore_index=True)
    calibration = factors(cells=(PT,))
    result = h.har08_mae(source, calibration, include_global=False)
    assert result.cell.tolist() == [PT, ES]
    assert result.n_pairs.tolist() == [3, 3]
    assert result.n_adjusted_pairs.tolist() == [3, 0]
    assert result.mae_adjusted.iloc[1] != result.mae_adjusted.iloc[1]     # NaN: no factor row for ES
    assert result.mae_raw.tolist() == [20.0, 20.0]
    assert GLOBAL_CELL not in h.test_predictions(source, calibration, include_global=False).cell.tolist()


def test_sliced_global_row_from_the_summed_series_equals_the_one_of_a_single_call():
    source = pd.concat([monthly((10, 5), (20, 9)), monthly((30, 7), (90, 7), cell=ES)], ignore_index=True)
    calibration = factors(cells=(PT, ES, GLOBAL_CELL), value=2.5)
    whole = h.har08_mae(source, calibration)
    pairs = h.comparable_pairs(source, include_global=False)
    summed = pairs.groupby(["year", "month"])[["modis", "viirs"]].sum().reset_index()
    series = pd.concat([summed.assign(series="modis", cell_days=summed.modis),
                        summed.assign(series="viirs", cell_days=summed.viirs)], ignore_index=True)
    series = series.assign(cell=GLOBAL_CELL, partial=False, n_unknown_days=0)[
        ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]]
    sliced = h.har08_mae(series, calibration, include_global=False)
    assert_frame_equal(sliced, whole.loc[whole.cell.eq(GLOBAL_CELL)].reset_index(drop=True))


def test_many_cells_match_a_plain_python_oracle():
    rng = random.Random(55)
    records, expected = [], {}
    for cell in range(1, 31):
        factor = rng.choice([0.5, 1.0, 2.0])
        pairs = [(rng.randint(0, 20), rng.randint(0, 40)) for _ in range(rng.randint(0, 6))]
        for index, (x, y) in enumerate(pairs):
            for series, value in [("modis", x), ("viirs", y)]:
                records.append(dict(cell=cell, year=2022, month=index + 1, series=series,
                                    cell_days=value, partial=False, n_unknown_days=0))
        expected[cell] = (factor, pairs)
    if not records:
        pytest.skip("empty draw")
    source = pd.DataFrame(records)
    calibration = pd.DataFrame(dict(cell=list(expected), factor_used=[f for f, _ in expected.values()],
                                    uses_global_fallback=False))
    mae = h.har08_mae(source, calibration, include_global=False).set_index("cell")
    wape = h.har09_wape(source, calibration, include_global=False).set_index("cell")
    bias = h.har10_bias(source, calibration, include_global=False).set_index("cell")
    for cell, (factor, pairs) in expected.items():
        if not pairs:
            assert cell not in mae.index
            continue
        raw = [x - y for x, y in pairs]
        adjusted = [factor * x - y for x, y in pairs]
        assert mae.loc[cell, "n_pairs"] == len(pairs)
        assert mae.loc[cell, "mae_raw"] == pytest.approx(sum(map(abs, raw)) / len(pairs))
        assert mae.loc[cell, "mae_adjusted"] == pytest.approx(sum(map(abs, adjusted)) / len(pairs))
        assert bias.loc[cell, "bias_raw"] == pytest.approx(sum(raw) / len(pairs))
        total = sum(y for _, y in pairs)
        if total:
            assert wape.loc[cell, "wape_adjusted"] == pytest.approx(100 * sum(map(abs, adjusted)) / total)
        else:
            assert pd.isna(wape.loc[cell, "wape_adjusted"])

"""HAR-12 S-NPP segmented-regression contracts and explicit input status."""

import math
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.common import GLOBAL_CELL
from metrics.harmonization_transition import COLUMNS, har12_residual_step


PT, ES = 101, 102      # arbitrary cell identifiers (the cells of the old countries)


def source():
    return pd.DataFrame([
        [PT, 2018, 1, "modis"], [PT, 2018, 1, "viirs"],
        [ES, 2018, 1, "modis"],
    ], columns=["cell", "year", "month", "series"])


def test_unconfigured_monthly_input_requires_separate_snpp_data():
    result = har12_residual_step(source())
    assert result.cell.tolist() == [GLOBAL_CELL]
    assert result.scope.tolist() == ["global"]
    assert result.status.tolist() == ["requires_snpp_inputs"]
    assert result.reason.str.contains("S-NPP monthly", regex=False).all()
    assert result[["transition_year", "step_raw", "step_adjusted"]].isna().all().all()


def test_empty_schema():
    result = har12_residual_step(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == COLUMNS
    assert result.cell.dtype == "int64"
    assert str(result.transition_year.dtype) == "Int64"
    assert result.step_raw.dtype == "float64"


def test_shuffle_immutability_and_duplicate_keys():
    frame = source()
    before = frame.copy(deep=True)
    result = har12_residual_step(frame)
    assert_frame_equal(result, har12_residual_step(frame.sample(frac=1, random_state=7)))
    assert_frame_equal(frame, before)
    with pytest.raises(ValueError, match="Duplicate monthly keys"):
        har12_residual_step(pd.concat([frame, frame.iloc[:1]], ignore_index=True))
    with pytest.raises(ValueError, match="cell"):
        har12_residual_step(frame.drop(columns="cell"))


def model_source(constant=False, cell=GLOBAL_CELL):
    records = []
    for year in range(2007, 2017):
        for month in range(1, 13):
            elapsed = (year - 2012) * 12 + month - 1
            modis = 10 if constant else 200 + elapsed + month - 1
            records.append([cell, year, month, "modis", modis, False, 0])
            if year >= 2012:
                viirs = 20 if constant else modis + 30 + 2 * elapsed
                records.append([cell, year, month, "viirs", viirs, False, 0])
    return pd.DataFrame(records, columns=[
        "cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days",
    ])


def factors(value=1.0, fallback=False):
    return pd.DataFrame(dict(cell=[PT, GLOBAL_CELL], factor_used=[value, value],
                             uses_global_fallback=[fallback, fallback]))


def evaluate(frame, calibration=None, **options):
    return har12_residual_step(frame, factors() if calibration is None else calibration,
                              reference_sensor="viirs-snpp", **options)


def test_known_level_trend_slope_change_and_seasonality():
    result = evaluate(model_source())
    assert result.status.tolist() == ["ok"]
    assert result.transition_year.tolist() == [2012]
    assert result.n_months.tolist() == [120]
    assert result.n_pre_months.tolist() == [60]
    assert result.n_post_months.tolist() == [60]
    assert result.residual_dof.tolist() == [105]
    assert result.step_raw.tolist() == pytest.approx([30], abs=1e-10)
    assert result.step_adjusted.tolist() == pytest.approx([30], abs=1e-10)
    assert result.step_se_raw.lt(1e-10).all()


def test_factor_removes_a_known_multiplicative_sensor_step():
    result = evaluate(model_source(constant=True), factors(2.0, fallback=True))
    assert result.step_raw.tolist() == pytest.approx([10], abs=1e-10)
    assert result.step_adjusted.tolist() == pytest.approx([0], abs=1e-10)
    assert result.factor_used.tolist() == [2.0]
    assert result.uses_global_fallback.tolist() == [True]


def test_absent_years_remain_calendar_gaps():
    frame = model_source()
    frame = frame.loc[~frame.year.isin([2010, 2016])]
    result = evaluate(frame)
    assert result.status.eq("ok").all()
    assert result.n_pre_months.tolist() == [48]
    assert result.n_post_months.tolist() == [48]
    assert result.n_pre_years.tolist() == [4]
    assert result.n_post_years.tolist() == [4]
    assert result.step_raw.tolist() == pytest.approx([30], abs=1e-10)


def test_partial_unknown_months_and_configurable_coverage():
    frame = model_source()
    frame.loc[frame.year.eq(2007), "partial"] = True
    frame.loc[frame.year.eq(2016), "n_unknown_days"] = 1
    result = evaluate(frame)
    assert result.n_pre_months.tolist() == [48]
    assert result.n_post_months.tolist() == [48]
    assert result.step_raw.tolist() == pytest.approx([30], abs=1e-10)
    relaxed = evaluate(frame, max_unknown_days=1)
    assert relaxed.n_post_months.tolist() == [60]


def test_insufficient_counts_years_rank_and_missing_factor():
    frame = model_source()
    result = evaluate(frame.loc[frame.year.ge(2010)])
    assert result.status.eq("insufficient_data").all()
    assert result.step_raw.isna().all()
    ranked = evaluate(frame.loc[frame.month.eq(1)], min_months_each_side=3)
    assert ranked.status.eq("rank_deficient").all()
    missing = evaluate(frame, factors(np.nan))
    assert missing.status.eq("missing_factor").all()
    assert missing[["step_raw", "step_adjusted"]].isna().all().all()


def test_configurable_window_and_exact_minimum():
    result = evaluate(model_source(), window_years=3)
    assert result.status.eq("ok").all()
    assert result.n_pre_months.tolist() == [36]
    assert result.n_post_months.tolist() == [36]
    assert result.n_pre_years.tolist() == [3]
    assert result.step_raw.tolist() == pytest.approx([30], abs=1e-10)
    smaller = model_source().loc[lambda frame: ~(frame.year.eq(2009) & frame.month.eq(1))]
    assert evaluate(smaller, window_years=3).status.eq("insufficient_data").all()


def test_fitted_shuffle_immutability_and_global_sum_of_cells():
    portugal = model_source(cell=PT)
    frame = pd.concat([portugal, model_source(constant=True, cell=ES)], ignore_index=True)
    calibration = factors()
    before = frame.copy(deep=True)
    result = evaluate(frame, calibration)
    assert_frame_equal(result, evaluate(frame.sample(frac=1, random_state=14), calibration))
    assert_frame_equal(frame, before)
    # One global row: the cells add up month by month (30 + 10 = 40).
    assert result.cell.tolist() == [GLOBAL_CELL]
    assert result.scope.tolist() == ["global"]
    assert result.step_raw.tolist() == pytest.approx([40], abs=1e-10)
    assert result.n_months.tolist() == [120]
    # The same series supplied already summed (cell == GLOBAL_CELL) gives the same fit.
    total = frame.groupby(["year", "month", "series"], as_index=False).agg(
        cell_days=("cell_days", "sum"), partial=("partial", "max"), n_unknown_days=("n_unknown_days", "max"))
    total["cell"] = GLOBAL_CELL
    assert_frame_equal(evaluate(total, calibration), result)


def test_only_valid_cells_are_summed_into_the_global_series():
    portugal, spain = model_source(cell=PT), model_source(constant=True, cell=ES)
    spain.loc[spain.year.eq(2008), "partial"] = True
    result = evaluate(pd.concat([portugal, spain], ignore_index=True))
    # 12 months of 2008 are valid only in the first cell but are summed with the valid rows only.
    assert result.n_months.tolist() == [120]
    assert result.status.tolist() == ["ok"]
    assert_frame_equal(evaluate(pd.concat([portugal, spain.loc[~spain.year.eq(2008)]], ignore_index=True)), result)


def test_mixing_global_series_and_cells_is_rejected():
    frame = pd.concat([model_source(cell=PT), model_source()], ignore_index=True)
    with pytest.raises(ValueError, match="GLOBAL_CELL"):
        evaluate(frame)


def test_factor_of_another_cell_is_not_used_and_global_row_is_required():
    only_cell = pd.DataFrame(dict(cell=[PT], factor_used=[2.0], uses_global_fallback=[False]))
    result = evaluate(model_source(), only_cell)
    assert result.status.tolist() == ["missing_factor"]
    assert result.factor_used.isna().all()


@pytest.mark.parametrize("field,value,message", [
    ("cell_days", None, "cell_days"), ("cell_days", -1, "nonnegative"),
    ("month", 13, "calendar"), ("year", 2012.5, "integers"),
])
def test_invalid_model_values(field, value, message):
    frame = model_source()
    frame[field] = frame[field].astype("object")
    frame.loc[0, field] = value
    with pytest.raises(ValueError, match=message):
        evaluate(frame)


@pytest.mark.parametrize("value", [-1, np.inf, "wrong"])
def test_invalid_supplied_factors(value):
    with pytest.raises(ValueError, match="factor_used"):
        evaluate(model_source(), factors(value))


def test_reference_identity_parameters_and_empty_fitted_input():
    with pytest.raises(ValueError, match="reference_sensor"):
        har12_residual_step(model_source(), factors(), reference_sensor="viirs-jpss1")
    with pytest.raises(ValueError, match="window_years"):
        evaluate(model_source(), window_years=0)
    assert evaluate(pd.DataFrame()).empty


def test_model_based_uncertainty_against_fraction_normal_equations():
    from fractions import Fraction

    rng = np.random.default_rng(2012)
    frame = model_source()
    frame["cell_days"] += rng.integers(-3, 4, len(frame))
    selected = frame.loc[(frame.year.lt(2012) & frame.series.eq("modis"))
                         | (frame.year.ge(2012) & frame.series.eq("viirs"))]
    rows, values = [], []
    for row in selected.itertuples(index=False):
        elapsed = 12 * (row.year - 2012) + row.month - 1
        post = int(row.year >= 2012)
        rows.append([1, elapsed, post, elapsed * post] + [int(row.month == month) for month in range(2, 13)])
        values.append(int(row.cell_days))
    size = 15
    # Independent exact normal equations use Fraction elimination instead of SVD.
    augmented = [[Fraction(sum(row[i] * row[j] for row in rows)) for j in range(size)]
                 + [Fraction(sum(row[i] * value for row, value in zip(rows, values))), Fraction(int(i == 2))]
                 for i in range(size)]
    for index in range(size):
        pivot = next(position for position in range(index, size) if augmented[position][index])
        augmented[index], augmented[pivot] = augmented[pivot], augmented[index]
        divisor = augmented[index][index]
        augmented[index] = [value / divisor for value in augmented[index]]
        for position in range(size):
            if position != index:
                multiplier = augmented[position][index]
                augmented[position] = [left - multiplier * right for left, right in zip(augmented[position], augmented[index])]
    beta = [row[size] for row in augmented]
    residual_sum = sum((Fraction(value) - sum(coef * number for coef, number in zip(beta, row))) ** 2
                       for row, value in zip(rows, values))
    standard_error = math.sqrt(float(residual_sum / 105 * augmented[2][size + 1]))
    result = evaluate(frame).iloc[0]
    assert result.step_raw == pytest.approx(float(beta[2]), abs=1e-9)
    assert result.step_se_raw == pytest.approx(standard_error, abs=1e-9)

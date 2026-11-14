"""HAR-12 reports the methodological limitation without inventing a step."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics.harmonization_transition import COLUMNS, har12_residual_step


def source():
    return pd.DataFrame([
        ["Portugal", 2018, 1, "modis"], ["Portugal", 2018, 1, "viirs"],
        ["Spain", 2018, 1, "modis"],
    ], columns=["country", "year", "month", "series"])


def test_current_inventory_is_not_applicable():
    result = har12_residual_step(source())
    assert result.country.tolist() == ["ALL", "Portugal", "Spain"]
    assert result.scope.tolist() == ["global", "country", "country"]
    assert result.status.tolist() == ["not_applicable"] * 3
    assert result.reason.str.contains("S-NPP 2012", regex=False).all()
    assert result[["transition_year", "step_raw", "step_adjusted"]].isna().all().all()


def test_empty_schema():
    result = har12_residual_step(pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == COLUMNS
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
    with pytest.raises(ValueError, match="country"):
        har12_residual_step(frame.drop(columns="country"))

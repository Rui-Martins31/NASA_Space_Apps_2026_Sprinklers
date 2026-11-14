"""Synthetic contracts for L7 grid and confidence sensitivity."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_sensitivity as h


def monthly_rows(*changes):
    base = dict(country="Portugal", year=2018, month=1, series="modis",
                cell_days=2, partial=False, n_unknown_days=0)
    return pd.DataFrame([base | change for change in changes])


def skeleton(year=2018):
    return monthly_rows(dict(year=year), dict(year=year, series="viirs"))


def detections(latitudes=(0.01, 0.11), confidences=None):
    records = []
    for instrument, satellite in [("MODIS", "Terra"), ("VIIRS", "N20")]:
        for index, latitude in enumerate(latitudes):
            records.append(dict(country="Portugal", instrument=instrument, satellite=satellite,
                                latitude=latitude, longitude=0.01, acq_date="2018-01-01",
                                type=0, confidence_class="h" if confidences is None else confidences[index]))
    result = pd.DataFrame(records)
    result["type"] = result.type.astype("Int8")
    result["confidence_class"] = result.confidence_class.astype("string")
    return result


def variant_inputs():
    records = []
    overlaps = []
    for variant, counts in [("grid_0.1", [(2, 4), (3, 5)]),
                            ("grid_0.25", [(1, 2), (2, 3)])]:
        for year, (modis, viirs) in zip([2018, 2022], counts):
            for series, value in [("modis", modis), ("viirs", viirs)]:
                records.append(dict(variant=variant, country="Portugal", year=year, month=1,
                                    series=series, cell_days=value, partial=False, n_unknown_days=0))
            overlaps.append(dict(variant=variant, country="Portugal", year=year, month=1,
                                 n_modis=modis, n_viirs=viirs, n_both=1,
                                 n_union=modis + viirs - 1))
    return pd.DataFrame(records), pd.DataFrame(overlaps)


def test_grid_builder_merges_cells_and_preserves_fixed_coverage():
    source = detections()
    template = skeleton().assign(n_unknown_days=1)
    before = source.copy(deep=True)
    monthly, overlap = h.build_variant_tables(source, template, h.GRID_VARIANTS)
    assert monthly.cell_days.tolist() == [2, 2, 1, 1]
    assert monthly.n_unknown_days.tolist() == [1] * 4
    assert overlap.n_both.tolist() == [2, 1]
    assert overlap.n_union.tolist() == [2, 1]
    assert_frame_equal(source, before)


def test_confidence_builder_retains_only_documented_types_and_classes():
    source = detections((0.01, 0.11, 0.21, 0.31, 0.41), ("h", "n", "l", None, "h"))
    source.loc[source.latitude.eq(0.41), "type"] = pd.NA
    monthly, _ = h.build_variant_tables(source, skeleton(), h.CONFIDENCE_VARIANTS)
    assert monthly.groupby("variant", observed=True).cell_days.first().to_dict() == {
        "all_confidence": 3, "high_only": 1, "nominal_high": 2,
    }


def test_builder_empty_detections_retains_zero_months():
    monthly, overlap = h.build_variant_tables(pd.DataFrame(), skeleton(), h.GRID_VARIANTS)
    assert monthly.cell_days.tolist() == [0, 0, 0, 0]
    assert overlap.empty
    assert list(monthly.columns) == ["variant"] + h.MONTHLY_COLUMNS
    assert list(overlap.columns) == ["variant"] + h.OVERLAP_COLUMNS
    empty_monthly, empty_overlap = h.build_variant_tables(pd.DataFrame(), pd.DataFrame(), h.GRID_VARIANTS)
    assert empty_monthly.empty and empty_overlap.empty


def test_grid_summary_manual_values_and_calibration_only_refit():
    monthly, overlap = variant_inputs()
    result = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    country = result.loc[result.country.eq("Portugal")].set_index("variant")
    assert country.loc["grid_0.1", ["sum_modis", "sum_viirs", "n_both", "n_union"]].tolist() == [3, 5, 1, 7]
    assert country.loc["grid_0.25", ["sum_modis", "sum_viirs", "n_both", "n_union"]].tolist() == [2, 3, 1, 4]
    assert country.factor_used.tolist() == [2.0, 2.0]
    assert country.mae_raw.tolist() == [2.0, 1.0]
    assert country.mae_adjusted.tolist() == [1.0, 1.0]
    assert country.delta_modis_pct.tolist() == pytest.approx([0, -33.333333333333336])
    assert country.delta_viirs_pct.tolist() == pytest.approx([0, -40])
    assert country.delta_mae_adjusted_pct.tolist() == [0, 0]
    assert result.loc[result.country.eq("ALL"), "mae_adjusted"].tolist() == [1, 1]
    # Test VIIRS changes alter evaluation errors, with training factors fixed.
    altered = monthly.copy()
    altered.loc[altered.year.eq(2022) & altered.series.eq("viirs"), "cell_days"] += 100
    altered_overlap = overlap.copy()
    altered_overlap.loc[altered_overlap.year.eq(2022), ["n_viirs", "n_union"]] += 100
    altered_result = h.har13_grid_sensitivity(altered, altered_overlap, min_cal_months=1)
    assert altered_result.factor_used.tolist() == result.factor_used.tolist()


def test_confidence_summary_uses_its_named_baseline():
    monthly, overlap = variant_inputs()
    names = {"grid_0.1": "nominal_high", "grid_0.25": "high_only"}
    monthly.variant = monthly.variant.map(names)
    overlap.variant = overlap.variant.map(names)
    result = h.har14_confidence_sensitivity(monthly, overlap, min_cal_months=1)
    country = result.loc[result.country.eq("Portugal")].set_index("variant")
    assert country.loc["nominal_high", "delta_modis_pct"] == 0
    assert country.loc["high_only", "delta_modis_pct"] == pytest.approx(-33.333333333333336)


def test_common_windows_exclude_month_missing_from_one_variant():
    monthly, overlap = variant_inputs()
    second = monthly.loc[monthly.year.eq(2022)].assign(month=2, cell_days=100)
    monthly = pd.concat([monthly, second.loc[second.variant.eq("grid_0.1")]], ignore_index=True)
    result = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    assert result.n_pairs.tolist() == [1] * 4
    assert result.loc[result.country.eq("Portugal"), "sum_modis"].tolist() == [3, 2]


def test_zero_baselines_and_unavailable_factors():
    monthly, overlap = variant_inputs()
    monthly["cell_days"] = 0
    for column in ["n_modis", "n_viirs", "n_both", "n_union"]:
        overlap[column] = 0
    result = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    assert result.factor_used.isna().all()
    assert result.mae_raw.eq(0).all()
    assert result.mae_adjusted.isna().all()
    assert result.jaccard.isna().all()
    assert result[["delta_modis_pct", "delta_viirs_pct", "delta_mae_adjusted_pct"]].isna().all().all()


@pytest.mark.parametrize("function", [h.har13_grid_sensitivity, h.har14_confidence_sensitivity])
def test_empty_summary_schema(function):
    result = function(pd.DataFrame(), pd.DataFrame())
    assert result.empty
    assert list(result.columns) == h.SUMMARY_COLUMNS


def test_builder_and_summary_reject_missing_or_duplicate_fields():
    with pytest.raises(ValueError, match="country"):
        h.build_variant_tables(detections().drop(columns="country"), skeleton(), h.GRID_VARIANTS)
    with pytest.raises(ValueError, match="Duplicate"):
        h.build_variant_tables(detections(), pd.concat([skeleton(), skeleton()]), h.GRID_VARIANTS)
    monthly, overlap = variant_inputs()
    with pytest.raises(ValueError, match="variant"):
        h.har13_grid_sensitivity(monthly.drop(columns="variant"), overlap)
    with pytest.raises(ValueError, match="baseline"):
        h.har13_grid_sensitivity(monthly, overlap, baseline="missing")
    with pytest.raises(ValueError, match="Duplicate"):
        h.har13_grid_sensitivity(monthly, pd.concat([overlap, overlap]))


def test_missing_nonzero_overlap_is_rejected():
    monthly, overlap = variant_inputs()
    with pytest.raises(ValueError, match="Overlap counts"):
        h.har13_grid_sensitivity(monthly, overlap.loc[overlap.year.eq(2018)], min_cal_months=1)


def test_shuffle_immutability_and_categorical_keys():
    import warnings

    source = detections()
    template = skeleton()
    expected = h.build_variant_tables(source, template, h.GRID_VARIANTS)
    shuffled = h.build_variant_tables(source.sample(frac=1, random_state=17), template.sample(frac=1, random_state=9), h.GRID_VARIANTS)
    for left, right in zip(expected, shuffled):
        assert_frame_equal(left, right)
    monthly, overlap = variant_inputs()
    before = monthly.copy(deep=True), overlap.copy(deep=True)
    expected_summary = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    assert_frame_equal(expected_summary, h.har13_grid_sensitivity(monthly.sample(frac=1, random_state=11), overlap.sample(frac=1, random_state=12), min_cal_months=1))
    assert_frame_equal(monthly, before[0])
    assert_frame_equal(overlap, before[1])
    monthly["country"] = pd.Categorical(monthly.country, categories=["Portugal", "Unused"])
    monthly["variant"] = pd.Categorical(monthly.variant, categories=["grid_0.1", "grid_0.25", "Unused"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert_frame_equal(h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1), expected_summary)


def test_global_membership_uses_only_countries_comparable_in_every_variant():
    monthly, overlap = variant_inputs()
    spain = monthly.assign(country="Spain")
    spain = spain.loc[~(spain.variant.eq("grid_0.25") & spain.year.eq(2022) & spain.series.eq("viirs"))]
    monthly = pd.concat([monthly, spain], ignore_index=True)
    overlap = pd.concat([overlap, overlap.assign(country="Spain")], ignore_index=True)
    result = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    assert result.loc[result.country.eq("Spain"), "n_pairs"].tolist() == [0, 0]
    assert result.loc[result.country.eq("Spain"), "sum_modis"].tolist() == [0, 0]
    assert result.loc[result.country.eq("ALL"), "sum_modis"].tolist() == [3, 2]
    assert result.loc[result.country.eq("ALL"), "n_pairs"].tolist() == [1, 1]


def test_seeded_independent_decimal_grid_and_set_oracle():
    from decimal import Decimal
    import random

    rng = random.Random(713)
    source = pd.concat([detections() for _ in range(20)], ignore_index=True)
    source["latitude"] = [rng.randrange(50) / 100 for _ in range(len(source))]
    source["confidence_class"] = [rng.choice(["l", "n", "h", None]) for _ in range(len(source))]
    source["type"] = pd.Series([rng.choice([0, 0, 1, None]) for _ in range(len(source))], dtype="Int8")
    source["acq_date"] = [rng.choice(["2018-01-01", "2018-01-02"]) for _ in range(len(source))]
    monthly, overlap = h.build_variant_tables(source, skeleton(), h.GRID_VARIANTS)
    for variant, settings in h.GRID_VARIANTS.items():
        sets = {"MODIS": set(), "VIIRS": set()}
        step = Decimal(str(settings["grid_deg"]))
        for row in source.itertuples(index=False):
            if pd.isna(row.type) or row.type != 0 or row.confidence_class not in ["n", "h"]:
                continue
            latitude_cell = int((Decimal(str(row.latitude)) + 90) // step)
            longitude_cell = int((Decimal(str(row.longitude)) + 180) // step)
            sets[row.instrument].add((row.acq_date, latitude_cell, longitude_cell))
        selected = monthly.loc[monthly.variant.eq(variant)].set_index("series")
        assert selected.loc["modis", "cell_days"] == len(sets["MODIS"])
        assert selected.loc["viirs", "cell_days"] == len(sets["VIIRS"])
        actual_overlap = overlap.loc[overlap.variant.eq(variant)].iloc[0]
        assert actual_overlap.n_both == len(sets["MODIS"] & sets["VIIRS"])
        assert actual_overlap.n_union == len(sets["MODIS"] | sets["VIIRS"])


def test_missing_or_invalid_variant_options_are_clear():
    with pytest.raises(ValueError, match="variant options"):
        h.build_variant_tables(detections(), skeleton(), {"broken": {"confidence": ("h",)}})
    with pytest.raises(ValueError, match="confidence"):
        h.build_variant_tables(detections(), skeleton(), {"broken": {"grid_deg": 0.1, "confidence": ("unknown",)}})
    with pytest.raises(ValueError, match="grid_deg"):
        h.build_variant_tables(detections(), skeleton(), {"broken": {"grid_deg": 0, "confidence": ("h",)}})


def test_all_invalid_months_remain_with_zero_comparable_pairs():
    monthly, overlap = variant_inputs()
    monthly["partial"] = True
    result = h.har13_grid_sensitivity(monthly, overlap, min_cal_months=1)
    assert len(result) == 4
    assert result.n_pairs.eq(0).all()
    assert result.factor_used.isna().all()
    assert result.mae_raw.isna().all()

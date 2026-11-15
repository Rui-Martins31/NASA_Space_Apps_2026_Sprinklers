"""L7 grid and confidence comparisons on shared calibration and test windows.

GLOBAL metric (HAR-13/14): the variants change the grid, so their cells are
not comparable one by one. Everything here works on the global monthly series
(``cell = GLOBAL_CELL``: the sum of the cell-days of all cells of the variant)
and the global overlap counts of the same variant. ``build_variant_tables``
produces both from raw detections; the summaries take them as input and
return rows with ``cell = GLOBAL_CELL``.
"""

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, cell_key, eligible, parse_dates, require_columns, valid_coords
from .harmonization_factor import (
    CAL_START, CAL_END, TEST_START, MIN_CAL_MONTHS, comparable_pairs, har06_factor,
)
from .harmonization_errors import har08_mae
from .harmonization_overlap import har01_cellday_overlap, global_overlap, OVERLAP_COLUMNS


GRID_VARIANTS = {
    "grid_0.1": {"grid_deg": 0.1, "confidence": ("n", "h")},
    "grid_0.25": {"grid_deg": 0.25, "confidence": ("n", "h")},
}
CONFIDENCE_VARIANTS = {
    "nominal_high": {"grid_deg": 0.1, "confidence": ("n", "h")},
    "high_only": {"grid_deg": 0.1, "confidence": ("h",)},
    "all_confidence": {"grid_deg": 0.1, "confidence": ("l", "n", "h")},
}
MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
PERIOD_KEYS = ["cell", "year", "month"]
SUMMARY_COLUMNS = [
    "variant", "cell", "period", "n_pairs", "n_adjusted_pairs", "sum_modis", "sum_viirs",
    "n_both", "n_union", "jaccard", "factor_used", "uses_global_fallback", "mae_raw", "mae_adjusted",
    "delta_modis_pct", "delta_viirs_pct", "delta_mae_adjusted_pct",
]


def _typed(frame, columns):
    result = frame.reindex(columns=columns).copy()
    integers = {"cell", "year", "month", "cell_days", "n_unknown_days", "n_pairs", "n_adjusted_pairs",
                "sum_modis", "sum_viirs", "n_modis", "n_viirs", "n_both", "n_union"}
    for column in columns:
        if column in integers:
            result[column] = result[column].astype("int64")
        elif column in {"partial", "uses_global_fallback"}:
            result[column] = result[column].astype(bool)
        elif column in {"variant", "series", "period"}:
            result[column] = result[column].astype("object")
        else:
            result[column] = result[column].astype("float64")
    keys = [column for column in ["variant", "cell", "year", "month", "series", "period"] if column in columns]
    return result.sort_values(keys).reset_index(drop=True)


def _require_global(table):
    if table.cell.isna().any() or table.cell.ne(GLOBAL_CELL).any():
        raise ValueError("HAR-13/14 work on the global series: cell must be GLOBAL_CELL (-1)")


def _monthly(table, with_variant=False):
    columns = (["variant"] if with_variant else []) + MONTHLY_COLUMNS
    if table.empty:
        return _typed(pd.DataFrame(), columns)
    require_columns(table, columns)
    source = table[columns].copy().reset_index(drop=True)
    keys = (["variant"] if with_variant else []) + PERIOD_KEYS + ["series"]
    if source.duplicated(keys).any():
        raise ValueError(f"Duplicate monthly keys: {', '.join(keys)}")
    if source.cell_days.isna().any():
        raise ValueError("cell_days contains missing values")
    _require_global(source)
    return _typed(source.loc[source.series.isin(["modis", "viirs"])], columns)


def build_variant_tables(detections: pd.DataFrame, monthly: pd.DataFrame,
                         variants, cal_start=CAL_START):
    """Recount selected detections as global monthly series using a fixed coverage skeleton.

    Call with both sensors for each selected raw year and the matching L1
    global monthly subset (``cell = GLOBAL_CELL``; only ``partial`` and
    ``n_unknown_days`` are kept, ``cell_days`` is recounted). Coverage flags
    come from L1 and do not change with the confidence filter. Missing
    detections within that supplied scope count zero. Per variant the cells
    are built with its own ``grid_deg``; the monthly count is the sum of the
    distinct cell-days of all cells, and the overlap is the sum of the
    per-cell overlap counts (``cell = GLOBAL_CELL``).
    """
    template = _monthly(monthly)
    monthly_columns = ["variant"] + MONTHLY_COLUMNS
    overlap_columns = ["variant"] + OVERLAP_COLUMNS
    if template.empty or not variants:
        return _typed(pd.DataFrame(), monthly_columns), _typed(pd.DataFrame(), overlap_columns)
    fields = ["instrument", "latitude", "longitude", "acq_date", "type", "confidence_class"]
    if detections.empty:
        source = pd.DataFrame(columns=fields + ["date", "year", "month"])
        source["date"] = pd.to_datetime(source.date)
    else:
        require_columns(detections, fields)
        source = detections[fields].copy().reset_index(drop=True)
        source["instrument"] = source.instrument.astype("string").str.upper()
        if not source.instrument.isin(["MODIS", "VIIRS"]).all():
            raise ValueError("Unknown or missing instrument; expected MODIS or VIIRS")
        source["date"] = parse_dates(source.acq_date).dt.normalize()
        finite = valid_coords(source.latitude, source.longitude)
        source = source.loc[source.date.notna() & finite].copy()
        source["year"] = source.date.dt.year
        source["month"] = source.date.dt.month
    allowed = template[["year", "month", "series"]]
    results, overlaps = [], []
    for variant, options in variants.items():
        require_options = {"grid_deg", "confidence"} - set(options)
        if require_options:
            raise ValueError(f"Missing variant options: {sorted(require_options)}")
        if not set(options["confidence"]).issubset({"l", "n", "h"}):
            raise ValueError("Variant confidence must use l, n or h")
        # The shared grid helper also validates an empty grid configuration.
        cell_key([], [], options["grid_deg"])
        selected = source.loc[eligible(source, confidence=options["confidence"], type_value=0)].copy()
        selected["cell"] = cell_key(selected.latitude, selected.longitude, options["grid_deg"])
        selected["series"] = selected.instrument.astype("string").str.lower()
        selected = selected.merge(allowed, on=["year", "month", "series"], how="inner", validate="many_to_one")
        distinct = selected.drop_duplicates(["date", "cell", "instrument"])
        counts = distinct.groupby(["year", "month", "series"], observed=True, dropna=False).size().rename("cell_days").reset_index()
        result = template.drop(columns="cell_days").merge(counts, how="left", on=["year", "month", "series"])
        result["cell_days"] = result.cell_days.fillna(0)
        result["variant"] = variant
        overlap = global_overlap(har01_cellday_overlap(distinct[["date", "cell", "instrument"]], cal_start=cal_start))
        overlap["variant"] = variant
        results.append(result)
        overlaps.append(overlap)
    return (_typed(pd.concat(results, ignore_index=True), monthly_columns),
            _typed(pd.concat(overlaps, ignore_index=True), overlap_columns))


def _overlap(table):
    columns = ["variant"] + OVERLAP_COLUMNS
    if table.empty:
        return _typed(pd.DataFrame(), columns)
    require_columns(table, columns)
    source = table[columns].copy()
    if source.duplicated(["variant"] + PERIOD_KEYS).any():
        raise ValueError("Duplicate variant overlap keys")
    _require_global(source)
    counts = ["n_modis", "n_viirs", "n_both", "n_union"]
    if source[counts].isna().any().any() or source[counts].lt(0).any().any():
        raise ValueError("Overlap counts must be nonnegative and present")
    if source.n_both.gt(source[["n_modis", "n_viirs"]].min(axis=1)).any():
        raise ValueError("Overlap counts exceed the smaller sensor count")
    if not source.n_union.eq(source.n_modis + source.n_viirs - source.n_both).all():
        raise ValueError("Overlap counts violate the intersection/union identity")
    return _typed(source, columns)


def _common_scope(monthly, variants, period_options):
    candidates = []
    for variant in variants:
        pairs = comparable_pairs(monthly.loc[monthly.variant.eq(variant), MONTHLY_COLUMNS],
                                 include_global=False, **period_options)
        candidates.append(pairs[PERIOD_KEYS].assign(variant=variant))
    all_pairs = pd.concat(candidates, ignore_index=True)
    counts = all_pairs.groupby(PERIOD_KEYS, observed=True, dropna=False).variant.nunique()
    common = counts.loc[counts.eq(len(variants))].reset_index()[PERIOD_KEYS]
    return pd.MultiIndex.from_frame(common)


def _aligned_monthly(source, skeleton, common):
    keys = PERIOD_KEYS + ["series"]
    result = skeleton.merge(source[MONTHLY_COLUMNS], on=keys, how="left", validate="one_to_one")
    present = result.partial.notna()
    result["cell_days"] = result.cell_days.fillna(0)
    result["n_unknown_days"] = result.n_unknown_days.fillna(0)
    result["partial"] = result.partial.astype("boolean").fillna(True)
    inside = pd.MultiIndex.from_frame(result[PERIOD_KEYS]).isin(common)
    result.loc[~(present & inside), "partial"] = True
    return _typed(result, MONTHLY_COLUMNS)


def _overlap_totals(pairs, overlap):
    test = pairs.loc[pairs.period.eq("test")]
    work = test.merge(overlap[OVERLAP_COLUMNS], on=PERIOD_KEYS, how="left", validate="one_to_one")
    counts = ["n_modis", "n_viirs", "n_both", "n_union"]
    work[counts] = work[counts].fillna(0)
    if not (work.modis.eq(work.n_modis) & work.viirs.eq(work.n_viirs)).all():
        raise ValueError("Overlap counts do not match variant monthly counts")
    return work.groupby("cell", observed=True, dropna=False).agg(
        sum_modis=("modis", "sum"), sum_viirs=("viirs", "sum"),
        n_both=("n_both", "sum"), n_union=("n_union", "sum"),
    ).reset_index()


def _sensitivity(variant_monthly, overlap, baseline, min_cal_months,
                 cal_start, cal_end, test_start, max_unknown_days):
    monthly = _monthly(variant_monthly, with_variant=True)
    if monthly.empty:
        return _typed(pd.DataFrame(), SUMMARY_COLUMNS)
    overlap = _overlap(overlap)
    variants = sorted(monthly.variant.unique())
    if baseline not in variants:
        raise ValueError(f"Missing baseline variant: {baseline}")
    options = dict(cal_start=cal_start, cal_end=cal_end, test_start=test_start,
                   max_unknown_days=max_unknown_days)
    common = _common_scope(monthly, variants, options)
    skeleton = monthly[PERIOD_KEYS + ["series"]].drop_duplicates()
    results = []
    for variant in variants:
        aligned = _aligned_monthly(monthly.loc[monthly.variant.eq(variant)], skeleton, common)
        factors = har06_factor(aligned, min_cal_months=min_cal_months, include_global=False, **options)
        errors = har08_mae(aligned, factors, include_global=False, **options)
        pairs = comparable_pairs(aligned, include_global=False, **options)
        totals = _overlap_totals(pairs, overlap.loc[overlap.variant.eq(variant)])
        result = errors.merge(factors[["cell", "factor_used", "uses_global_fallback"]], on="cell", how="left", validate="one_to_one")
        result = result.merge(totals, on="cell", how="left", validate="one_to_one")
        for column in ["sum_modis", "sum_viirs", "n_both", "n_union"]:
            result[column] = result[column].fillna(0)
        result["jaccard"] = result.n_both / result.n_union.replace(0, np.nan)
        result["variant"] = variant
        results.append(result)
    result = pd.concat(results, ignore_index=True)
    values = ["sum_modis", "sum_viirs", "mae_adjusted"]
    reference = result.loc[result.variant.eq(baseline), ["cell", "period"] + values]
    reference = reference.rename(columns={column: f"baseline_{column}" for column in values})
    result = result.merge(reference, on=["cell", "period"], how="left", validate="many_to_one")
    for value, label in [("sum_modis", "delta_modis_pct"), ("sum_viirs", "delta_viirs_pct"),
                         ("mae_adjusted", "delta_mae_adjusted_pct")]:
        denominator = result[f"baseline_{value}"].replace(0, np.nan)
        result[label] = 100.0 * (result[value] - denominator) / denominator
    return _typed(result, SUMMARY_COLUMNS)


def har13_grid_sensitivity(variant_monthly: pd.DataFrame, overlap: pd.DataFrame,
                           baseline="grid_0.1", min_cal_months=MIN_CAL_MONTHS,
                           cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                           max_unknown_days=0) -> pd.DataFrame:
    """Compare grids on the global series, with shared windows and calibration-only variant factors.

    Both inputs carry ``variant`` and ``cell == GLOBAL_CELL`` (the output of
    ``build_variant_tables``); the result has one row per variant with
    ``cell = GLOBAL_CELL``.
    """
    return _sensitivity(variant_monthly, overlap, baseline, min_cal_months,
                        cal_start, cal_end, test_start, max_unknown_days)


def har14_confidence_sensitivity(variant_monthly: pd.DataFrame, overlap: pd.DataFrame,
                                 baseline="nominal_high", min_cal_months=MIN_CAL_MONTHS,
                                 cal_start=CAL_START, cal_end=CAL_END, test_start=TEST_START,
                                 max_unknown_days=0) -> pd.DataFrame:
    """Compare confidence selections on the same valid global calibration/test months."""
    return _sensitivity(variant_monthly, overlap, baseline, min_cal_months,
                        cal_start, cal_end, test_start, max_unknown_days)

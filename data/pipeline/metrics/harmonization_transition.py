"""HAR-12 monthly segmented regression for an explicit S-NPP reference.

GLOBAL metric: it is fitted once, on the global monthly series (the sum of the
cell-days of all cells, ``cell = GLOBAL_CELL`` in the output). The input is
the global series itself (rows with ``cell == GLOBAL_CELL``) or a table of
cells, whose valid months are summed here by (year, month); the two forms are
not mixed. A per-cell fit would almost always fall back to the global one.
"""

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, require_columns


REASON = (
    "Provide separate harmonized S-NPP monthly counts and S-NPP calibration "
    "factors, then select reference_sensor='viirs-snpp' for transition analysis."
)
COLUMNS = [
    "cell", "scope", "status", "reason", "transition_year", "step_raw", "step_adjusted",
    "reference_sensor", "factor_used", "uses_global_fallback", "step_se_raw", "step_se_adjusted",
    "n_months", "n_pre_months", "n_post_months", "n_pre_years", "n_post_years", "residual_dof",
]
KEYS = ["cell", "year", "month", "series"]


def _output(records):
    result = pd.DataFrame(records, columns=COLUMNS)
    for column in ["scope", "status", "reason", "reference_sensor"]:
        result[column] = result[column].astype("object")
    for column in ["step_raw", "step_adjusted", "factor_used", "step_se_raw", "step_se_adjusted"]:
        result[column] = result[column].astype("float64")
    result["cell"] = result.cell.astype("int64")
    result["transition_year"] = result.transition_year.astype("Int64")
    result["uses_global_fallback"] = result.uses_global_fallback.astype(bool)
    for column in ["n_months", "n_pre_months", "n_post_months", "n_pre_years", "n_post_years", "residual_dof"]:
        result[column] = result[column].astype("int64")
    return result.sort_values("cell").reset_index(drop=True)


def _record(status, reason, transition_year=pd.NA, reference_sensor=None):
    return dict(cell=GLOBAL_CELL, scope="global",
                status=status, reason=reason, transition_year=transition_year,
                step_raw=np.nan, step_adjusted=np.nan, reference_sensor=reference_sensor,
                factor_used=np.nan, uses_global_fallback=False,
                step_se_raw=np.nan, step_se_adjusted=np.nan,
                n_months=0, n_pre_months=0, n_post_months=0,
                n_pre_years=0, n_post_years=0, residual_dof=0)


def _monthly(table, fitted):
    require_columns(table, KEYS)
    source = table.copy().reset_index(drop=True)
    if fitted:
        require_columns(source, ["cell_days", "partial", "n_unknown_days"])
        for column in ["year", "month", "cell_days"]:
            source[column] = pd.to_numeric(source[column], errors="coerce")
            if source[column].isna().any() or not np.isfinite(source[column]).all():
                raise ValueError(f"{column} contains missing or nonfinite values")
        if source.year.mod(1).ne(0).any() or source.month.mod(1).ne(0).any():
            raise ValueError("year and month must be integers")
        if not source.month.between(1, 12).all() or not source.year.between(1, 9999).all():
            raise ValueError("year or month is outside the calendar range")
        if source.cell_days.lt(0).any():
            raise ValueError("cell_days must be nonnegative")
        source[["year", "month"]] = source[["year", "month"]].astype("int64")
    if source.duplicated(KEYS).any():
        raise ValueError(f"Duplicate monthly keys: {', '.join(KEYS)}")
    if source.cell.isna().any():
        raise ValueError("cell contains missing values")
    source["cell"] = source.cell.astype("int64")
    if source.cell.eq(GLOBAL_CELL).any() and source.cell.ne(GLOBAL_CELL).any():
        raise ValueError("monthly mixes GLOBAL_CELL rows with cells; supply one or the other")
    return source


def _factors(table):
    require_columns(table, ["cell", "factor_used"])
    if table.cell.duplicated().any():
        raise ValueError("Duplicate factor cell keys")
    result = table.copy().reset_index(drop=True)
    result["factor_used"] = pd.to_numeric(result.factor_used, errors="coerce").astype("float64")
    supplied = table.factor_used.notna().to_numpy()
    if ((~np.isfinite(result.factor_used) | result.factor_used.lt(0)) & supplied).any():
        raise ValueError("factor_used must be finite and nonnegative when supplied")
    if "uses_global_fallback" not in result:
        result["uses_global_fallback"] = False
    flags = result.uses_global_fallback
    if not flags.dropna().isin([True, False]).all():
        raise ValueError("uses_global_fallback must contain boolean values")
    result["uses_global_fallback"] = flags.astype("boolean").fillna(False).astype(bool)
    return result.set_index("cell")


def _design(group, transition_year):
    elapsed = (group.year.to_numpy() - transition_year) * 12 + group.month.to_numpy() - 1
    post = elapsed >= 0
    seasonal = [group.month.eq(month).to_numpy(dtype=float) for month in range(2, 13)]
    return np.column_stack([np.ones(len(group)), elapsed, post, elapsed * post] + seasonal)


def _fit(group, record, min_months_each_side, min_years_each_side):
    before = group.year.lt(record["transition_year"])
    record.update(n_months=len(group), n_pre_months=int(before.sum()),
                  n_post_months=int((~before).sum()),
                  n_pre_years=group.loc[before, "year"].nunique(),
                  n_post_years=group.loc[~before, "year"].nunique())
    if (min(record["n_pre_months"], record["n_post_months"]) < min_months_each_side
            or min(record["n_pre_years"], record["n_post_years"]) < min_years_each_side):
        return record
    design = _design(group, record["transition_year"])
    rank = np.linalg.matrix_rank(design)
    record["residual_dof"] = max(len(group) - rank, 0)
    if rank < design.shape[1]:
        record.update(status="rank_deficient", reason="The seasonal segmented design is rank deficient.")
        return record
    if record["residual_dof"] < 1:
        record["reason"] = "At least one residual degree of freedom is required."
        return record
    if pd.isna(record["factor_used"]):
        record.update(status="missing_factor", reason="No supplied S-NPP calibration factor is available.")
        return record
    raw = group.cell_days.to_numpy(dtype=float)
    adjusted = raw.copy()
    adjusted[before.to_numpy()] *= record["factor_used"]
    values = np.column_stack([raw, adjusted])
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    residuals = values - design @ coefficients
    variances = np.square(residuals).sum(axis=0) / record["residual_dof"]
    step_variance_multiplier = np.square(np.linalg.pinv(design)[2]).sum()
    standard_errors = np.sqrt(variances * step_variance_multiplier)
    record.update(status="ok", reason="Seasonal segmented OLS with model-based standard errors.",
                  step_raw=coefficients[2, 0], step_adjusted=coefficients[2, 1],
                  step_se_raw=standard_errors[0], step_se_adjusted=standard_errors[1])
    return record


def har12_residual_step(monthly: pd.DataFrame, factors=None, reference_sensor=None,
                       transition_year=2012, window_years=5, min_months_each_side=36,
                       min_years_each_side=3, max_unknown_days=0) -> pd.DataFrame:
    """Estimate the 2012 level step in explicit MODIS-to-S-NPP spliced series.

    The raw series uses MODIS before January of ``transition_year`` and S-NPP
    VIIRS from that month. The adjusted series scales the pre-transition MODIS
    values using separately supplied S-NPP calibration factors. The design has
    an intercept, elapsed-month trend, post-transition level and slope terms,
    and eleven calendar-month effects. Missing months remain gaps in time.

    The window contains ``window_years`` calendar years on each side. Estimates
    require adequate valid observations, a full-rank design and residual degrees
    of freedom. Standard errors use conventional OLS residual variance. They
    assume independent model errors and fixed supplied calibration factors.
    A missing factor leaves both estimates
    unavailable, preserving the same observation scope for their comparison.

    The one-argument call reports ``requires_snpp_inputs``. Numerical fitting
    requires explicit ``reference_sensor='viirs-snpp'`` and its factor table.
    The caller supplies separately constructed S-NPP monthly ``viirs`` rows.
    """
    if reference_sensor not in {None, "viirs-snpp"}:
        raise ValueError("reference_sensor must explicitly identify viirs-snpp")
    for name, value in [("transition_year", transition_year), ("window_years", window_years),
                        ("min_months_each_side", min_months_each_side),
                        ("min_years_each_side", min_years_each_side)]:
        if not isinstance(value, (int, np.integer)) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if monthly.empty:
        return _output([])
    fitted = reference_sensor == "viirs-snpp" and factors is not None
    source = _monthly(monthly, fitted)
    if not fitted:
        return _output([_record("requires_snpp_inputs", REASON)])
    calibration = _factors(factors)
    valid = (~source.partial.astype("boolean")) & source.n_unknown_days.le(max_unknown_days)
    selected = source.loc[valid.fillna(False) & source.year.between(
        transition_year - window_years, transition_year + window_years - 1
    )].copy()
    selected = selected.loc[(selected.year.lt(transition_year) & selected.series.eq("modis"))
                            | (selected.year.ge(transition_year) & selected.series.eq("viirs"))]
    # One global series: the cell-days of the valid cells add up per month.
    group = selected.groupby(["year", "month"], observed=True).cell_days.sum().reset_index()
    group = group.sort_values(["year", "month"])
    record = _record("insufficient_data", "Too few valid months or years around the transition.",
                     transition_year, reference_sensor)
    if GLOBAL_CELL in calibration.index:
        record["factor_used"] = calibration.loc[GLOBAL_CELL, "factor_used"]
        record["uses_global_fallback"] = calibration.loc[GLOBAL_CELL, "uses_global_fallback"]
    return _output([_fit(group, record, min_months_each_side, min_years_each_side)])

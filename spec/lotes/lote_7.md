# L7 implementation report and output contracts

## Scope and specification decisions

The repository assigns HAR-08 through HAR-14 to L7 and defines their formulas
in `spec/metricas_modis_viirs.csv`. It has no detailed L7 section or reserved
file list yet. This report records the local output contracts and decisions.
The shared methodology, manifests and code of other batches are preserved.

HAR-08 through HAR-11 implement held-out errors using L1 monthly counts and
the supplied L6 factors. HAR-13 and HAR-14 implement grid and confidence
sensitivity with recalculated counts. HAR-12 is an applicability report for
the documented current sensor inventory. It has no numerical step estimate.
The methodology marks it for review because the dataset lacks the S-NPP 2012
transition. No alternative transition is inferred.

All new source, tests and documentation are in English. Work uses the shared
`metricas-pipeline` branch and the existing L1 and L6 public interfaces.

## Output tables

All tables are sorted by their keys and have a clean integer index. Empty
inputs return empty typed tables. Nonempty inputs with missing required
fields, duplicate monthly keys or invalid supplied factors raise clear errors.

| Metric | Function | Output table |
|---|---|---|
| HAR-08 | harmonization_errors.har08_mae | l7_har08_mae |
| HAR-09 | harmonization_errors.har09_wape | l7_har09_wape |
| HAR-10 | harmonization_errors.har10_bias | l7_har10_bias |
| HAR-11 | harmonization_errors.har11_error_reduction | l7_har11_error_reduction |
| HAR-12 | harmonization_transition.har12_residual_step | l7_har12_residual_step |
| HAR-13 | harmonization_sensitivity.har13_grid_sensitivity | l7_har13_grid_sensitivity |
| HAR-14 | harmonization_sensitivity.har14_confidence_sensitivity | l7_har14_confidence_sensitivity |

HAR-08 through HAR-11 take `(monthly, factors)` with configurable
`cal_start=2018`, `cal_end=2021`, `test_start=2022` and `max_unknown_days=0`.
The shared leading columns are `country, period, n_pairs, n_adjusted_pairs`,
where `period` is always `test`. Their remaining columns are as follows.

| Metric | Remaining columns |
|---|---|
| HAR-08 | mae_raw, mae_adjusted |
| HAR-09 | wape_raw, wape_adjusted |
| HAR-10 | bias_raw, bias_adjusted |
| HAR-11 | mae_raw, mae_adjusted, error_reduction_pct |

`test_predictions(monthly, factors, ...)` is the pure supporting function.
It returns `country, year, month, modis, viirs, factor_used,
uses_global_fallback, modis_adjusted, error_raw, error_adjusted` for valid test
months only. `modis_adjusted = modis * factor_used`; signed errors are
prediction minus VIIRS. Factor input requires `country, factor_used,
uses_global_fallback`, accepting the full L6 factor table as well.

The HAR-12 applicability columns are `country, scope, status, reason,
transition_year, step_raw, step_adjusted`. For each existing country and `ALL`,
`status = not_applicable`, with null year and step estimates and an explicit
reason. This function reports the documented inventory limitation and does
not fit a segmented regression.

`build_variant_tables(detections, monthly, variants, cal_start=2018)` is the
pure annual sensitivity builder. It returns two tables, each with a leading
`variant` column. The first has the L1 monthly schema and the second has the
HAR-01 overlap schema. Both sensors must be supplied for the same raw-year
scope as the monthly template. The template supplies the dense calendar and
coverage flags, so filtering detections does not alter observation coverage.

HAR-13 and HAR-14 take `(variant_monthly, overlap, baseline=...,
min_cal_months=24, cal_start=2018, cal_end=2021, test_start=2022,
max_unknown_days=0)`. The caller supplies the selected variants. Their shared
columns are `variant, country, period, n_pairs, n_adjusted_pairs, sum_modis,
sum_viirs, n_both, n_union, jaccard, factor_used, uses_global_fallback,
mae_raw, mae_adjusted, delta_modis_pct, delta_viirs_pct,
delta_mae_adjusted_pct`.

## Statistical rules

- Comparable months and `ALL` use L6 `comparable_pairs`, with complete periods
  and the configured unknown-day limit. `combined` is excluded. Test months
  start in 2022 by default. Calibration months never enter the error scores.
- Baseline predictions consume stored `factor_used` values, including global
  fallback, without refitting. A missing factor preserves raw scores and
  leaves adjusted scores null. Pair counts distinguish the two cases.
- MAE is the mean absolute monthly error. WAPE is 100 times the absolute-error
  sum divided by the aligned VIIRS sum. Zero reference sums produce null WAPE.
  Bias is the signed mean error. Error reduction is 100 times the difference
  between raw and adjusted MAE divided by positive raw MAE. It can be negative.
  Zero initial MAE produces null reduction.
- A single valid test pair can define an error score. The L6 correlation
  minimum of twelve pairs does not apply to means and sums of errors.
- `ALL` predictions use its supplied global factor on its summed monthly
  activity. They are not obtained by averaging country errors.
- Default HAR-13 grids are 0.1 and 0.25 degrees with nominal/high confidence.
  Default HAR-14 selections are `nominal_high`, `high_only` and
  `all_confidence`, all at 0.1 degrees. Confidence classes are the harmonized
  L1 `l/n/h` values. Missing confidence is excluded in every variant.
- Every sensitivity variant retains `type == 0`, uses the L1 integer grid
  helper and counts each instrument's distinct country/date/cell once across
  satellites. Invalid dates and coordinates follow L1 filtering rules.
- Sensitivity calibration and test windows use the intersection of comparable
  country-month keys across the supplied variants. Global membership is rebuilt
  from those common country-months. Thus variants use the same data windows.
- Each variant fits its own L6 calibration-only factor on the common training
  months, including the L6 global fallback. These factors are separate from
  the stored baseline factors used by HAR-08 through HAR-11.
- Sensitivity `jaccard` pools the test-month intersections and unions over the
  comparable scope. Counts are checked against variant monthly totals.
- Sensitivity deltas are 100 times variant-minus-baseline divided by the
  baseline. Zero or unavailable baselines produce null deltas. A negative
  adjusted-MAE delta means that variant has less error. This sign convention
  differs from the positive-improvement convention of HAR-11.

## Running

From `data/pipeline`, run `python -m pytest tests -q`. L7 has separate tests
for errors, sensitivity, transition applicability and notebook integration.

After the L7 source is available on `metricas-pipeline`, run
`data/pipeline/notebooks/08_metrics_lote7.ipynb` in Colab. It mounts Drive,
clones or switches to the shared branch and imports `data/pipeline`.
Private repository access uses a runtime `GITHUB_TOKEN` Colab secret.

Required baseline inputs are `metrics/l1_cal_monthly.parquet` and
`metrics/l6_har06_factor.parquet` under
`/content/drive/MyDrive/Sprinklers`. Missing inputs produce a clear request
to run notebooks 02 and 07 first. The factor table must come from a compatible
L6 calibration run. The L7 log records its SHA-256 digest.

Sensitivity requires both `processed/modis_<year>.parquet` and
`processed/viirs-jpss1_<year>.parquet` for each selected year at or after
`CAL_START`. `YEARS = None` selects available paired processed years.
Missing counterparts raise an error. Empty files are supported. File
instruments and acquisition-year consistency are checked before processing.

The notebook processes one combined sensor-year at a time using only needed
columns. Annual variant tables and metadata are stored in
`metrics/_partial_lote7`. Completed partials are reused only when source file
metadata, L1 monthly metadata, variants, code digest and repository commit
match. Incomplete or damaged metadata triggers recalculation. `FORCE = True`
recalculates the selected years. Only the current year selection is consolidated.

Baseline errors use all valid test months in the supplied L1 monthly table.
Sensitivity uses the selected processed years and the matching L1 coverage
template. The selected sensitivity years are recorded separately in the log.

The notebook writes seven `l7_*.parquet` tables and `_log_lote7.csv`, using
temporary files followed by replacement. The log records periods, thresholds,
variants, year selection, commit, factor digest, output rows and execution
time. Export is atomic per file. Rerun after an interrupted export and use
one notebook instance per output directory.

## Validation

Before L7, the complete pipeline suite passed with 582 tests and 3 skipped
real-data tests. L7 adds 71 tests. Full suites completed with **653 passed,
3 skipped** on both pandas **2.2.3** and **3.1.1**, using isolated validation
environments in the system temporary directory.

The existing `data/pipeline/scripts/mutate.py` harness ran a clean baseline
of 69 core L7 tests in a temporary copy, then detected **12/12 mutations** by
assertion failures. The production source files were never mutated.

| Mutation | Result |
|---|---|
| HAR-08 removes absolute values | Killed |
| HAR-09 changes percentage scaling | Killed |
| HAR-10 reverses the adjusted bias sign | Killed |
| HAR-11 reverses the reduction sign | Killed |
| Scores calibration months instead of held-out months | Killed |
| Ignores the supplied factor | Killed |
| HAR-13 ignores the alternative grid | Killed |
| HAR-14 ignores confidence variants | Killed |
| Uses the union of variant windows instead of their intersection | Killed |
| Includes test months in calibration | Killed |
| Replaces a zero baseline with a numerical denominator | Killed |
| HAR-12 incorrectly claims availability | Killed |

Independent full-batch review using `.claude/skills/review-gate/SKILL.md`
is complete, with no confirmed code or calculation findings remaining.
The reviewer independently confirmed 653 passing and 3 skipped tests on pandas
2.2.3 and 3.1.1. A separate seeded oracle matched 72 sensitivity checks across
39 common country-months, including global membership, calibration factors,
fallback and held-out errors. HAR-12 remains an applicability report as
explicitly documented above.

Tests include literal arithmetic, zero and unavailable denominators, signed
bias and deterioration, global factors, missing factors, no calibration/test
leakage, grid collisions, confidence retention, unchanged coverage flags,
common variant windows, pooled overlaps, seeded arithmetic/set oracles,
categorical keys, empty inputs, named schema failures, shuffled input and
input immutability.

Notebook integration executes its actual configuration, discovery, annual
processing, computation and export cells against synthetic Parquet files. It
checks seven round-tripped outputs, empty inputs, numerical counts and variant
factors, unchanged L1/L6 inputs, reruns, cache reuse, forced recalculation,
missing-partial recovery, damaged-metadata recovery and missing-input errors.
Every code cell is checked with `ast.parse`, and saved outputs are empty.

## Limitations

HAR-12 has no numerical regression implementation for the current data. It
explicitly reports the methodological limitation until an alternative
transition and suitable series are defined. This choice follows the shared
methodology's review status and is recorded here because L7 has no detailed
shared contract yet.

Colab mounting, private repository authentication and execution against real
datasets have not been exercised locally. No real datasets were read or
downloaded. Global annual VIIRS sensitivity processing may require a
high-memory runtime. This batch adds only L7 files and does not change the
shared methodology or other batches.

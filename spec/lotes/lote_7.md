# L7 implementation report and output contracts

## Scope and specification decisions

The repository assigns HAR-08 through HAR-14 to L7 and defines their formulas
in `spec/metricas_modis_viirs.csv`. It has no detailed L7 section or reserved
file list yet. This report records the local output contracts and decisions.
The shared methodology, manifests and code of other batches are preserved.

HAR-08 through HAR-11 implement held-out errors using L1 monthly counts and
the supplied L6 factors. HAR-13 and HAR-14 implement grid and confidence
sensitivity with recalculated counts. HAR-12 now supports a numerical
segmented regression with explicitly supplied S-NPP monthly data and its own
calibration factors. Calls without those isolated inputs report
`requires_snpp_inputs`. This extends the initial applicability-only result
after the user added S-NPP archives.

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

The leading HAR-12 columns are `country, scope, status, reason,
transition_year, step_raw, step_adjusted`. Diagnostics append `reference_sensor,
factor_used, uses_global_fallback, step_se_raw, step_se_adjusted, n_months,
n_pre_months, n_post_months, n_pre_years, n_post_years, residual_dof`.
Numerical fitting requires explicit `reference_sensor='viirs-snpp'` and
separate S-NPP factors. Other calls return `requires_snpp_inputs`, with no
invented estimate. See the S-NPP execution section below for the model contract.

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

## Initial L7 validation

Before L7, the complete pipeline suite passed with 582 tests and 3 skipped
real-data tests. The initial L7 delivery added 71 tests. Full suites completed with **653 passed,
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
fallback and held-out errors. At that checkpoint HAR-12 was an applicability
report. The S-NPP extension is documented and validated separately below.

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

## S-NPP execution and HAR-12 model

The uploaded archive names follow `viirs-snpp_<year>_all_countries.zip`.
Notebook `01_ingest_harmonize.ipynb` already discovers that pattern recursively.
Use `SENSORS = {'modis', 'viirs-snpp'}` there to produce the required processed
files. Its shared source code is preserved.

NASA FIRMS identifies satellite code `N` as Suomi NPP and lists the active-fire
record from 20 January 2012. The isolated builder accepts that code and explicit
S-NPP labels, while rejecting NOAA-20 and unknown labels. Partial endpoint
months remain excluded under the L1 validity convention.
[NASA FIRMS VIIRS attributes](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html)

Run `data/pipeline/notebooks/09_har12_snpp.ipynb` after ingest. It reads only
`modis_<year>.parquet` and `viirs-snpp_<year>.parquet`, uses public L1 functions
to construct independent monthly tables, and calibrates MODIS to S-NPP with
L6 `har06_factor`. The calibration defaults remain 2018–2021 with at least
24 comparable months. NOAA-20 factors are never applied to S-NPP.

The default numerical model uses MODIS before January 2012 and S-NPP from
January 2012. It selects five calendar years on either side, requires at least
36 valid months and three represented years on each side, and fits an
intercept, elapsed-month trend, post-transition level and trend change, and
eleven calendar-month effects. The adjusted series scales only the MODIS
pre-transition segment using its separately supplied S-NPP factor. The
reported step is the post-level coefficient at the configured boundary.
These defaults were implementation choices based on the requested 2012
analysis and are configurable in `MODEL_OPTIONS`.

Insufficient samples, an unidentified seasonal design or a missing factor
produce explicit statuses and null estimates. Actual elapsed calendar months
are used in the design. Missing years are never replaced with zero activity.
The screenshot did not show 2016 or 2019, and the notebook logs missing
processed years rather than assuming the inventory is complete.

`harmonization_snpp.build_sensor_monthly` accepts one sensor-year at a time,
preserves L1 eligibility and coverage rules, and appends sensor provenance.
Only years needed for the regression window or calibration are processed.
The builder rejects multi-year frames to prevent infilling entire absent years.

The isolated outputs are `l7_har12_snpp_monthly.parquet`,
`l7_har12_snpp_factor.parquet`, `l7_har12_residual_step.parquet`,
`_params_har12_snpp.json` and `_log_har12_snpp.csv`. They record model settings,
source-file metadata, missing years and the Git revision. Notebook 08 uses
these isolated monthly/factor inputs and settings when present, so rerunning
the ordinary L7 export recomputes the numerical HAR-12 result. Without them,
it reports `requires_snpp_inputs`.

The shared notebook 02 currently aggregates all completed sensor partials.
Adding S-NPP to it would change the VIIRS series used by the existing batches.
This extension therefore builds HAR-12 inputs independently and does not run
or edit notebook 02. The shared aggregation needs a separately coordinated
satellite-selection policy before S-NPP is included there.

The Google Drive connector failed to initialize during this session. Archive
contents and processed data on Drive have not been inspected or executed.
Inventory observations above come from the user's screenshot.

The extension has 19 transition-model tests, 25 isolated-input tests and two
notebook integration tests. It adds 43 tests beyond the initial L7 suite,
because the original three applicability tests are retained in the model suite.
The complete pipeline passed with **696 passed, 3 skipped** on pandas
**2.2.3** and **3.1.1**. The skipped tests require real source data.

The synthetic model tests recover known seasonality, pre/post trends and a
known level step. A constant MODIS/S-NPP example with factor two removes a
known step. Missing years retain their actual elapsed-month positions.
An independent exact-Fraction normal-equation calculation verifies the OLS
step coefficient and its model-based standard error.

The isolated notebook integration test builds complete raw coverage but fixed
eligible monthly activity, discovers the missing 2016/2019 S-NPP years, obtains
the expected factor two, recovers a raw step of eight and an adjusted step of
zero, and confirms that existing NOAA-20 factor files retain their bytes.
It then executes notebook 08 with the resulting S-NPP sidecars and confirms
the numerical result is recomputed. A simulated interrupted export invalidates
the parameters marker until a complete input bundle is published. That test
passed again on both pandas versions after the export safeguard was added.

The existing isolated mutation harness passed its 44-test baseline and detected
**9/9 additional mutations**. These changed the step coefficient, pre-segment
scaling, OLS standard-error denominator, transition boundary, actual calendar
spacing, validity filter, satellite isolation, single-year input guard and
confidence eligibility. A surviving confidence mutation in the first run
exposed a test gap involving coincident cells. Two explicit distinct-cell
tests were added, and the final complete mutation run detected every case.

The requested independent review agent could not run because its runtime hit
the account usage limit. The primary agent completed a direct review of the
model, source isolation, export behavior, tests and documentation. An
independent review of this S-NPP extension remains outstanding. The earlier
independent L7 review above applies to the initial delivery, not this extension.

## Limitations

HAR-12 estimates depend on the explicitly configured splice and observation
window. OLS standard errors are conditional on supplied factors and do not
adjust for serial correlation or factor-estimation uncertainty. The global
series sums valid country observations and may be affected by changing country
coverage. It is a descriptive model, not a causal attribution of a sensor effect.

Colab mounting, private repository authentication and execution against real
datasets have not been exercised locally. No real datasets were read or
downloaded. Global annual VIIRS sensitivity processing may require a
high-memory runtime. This batch adds only L7 files and does not change the
shared methodology or other batches.

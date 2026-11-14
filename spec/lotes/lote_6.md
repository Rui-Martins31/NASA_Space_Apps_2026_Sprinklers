# L6 implementation report

## Scope

All seven L6 harmonization validation metrics are implemented according to
sections 3, 6, 7B, 7E, 7G and 9 of `spec/metodologia_metricas.md`.

| Metric | Function | Output table |
|---|---|---|
| HAR-01 | harmonization_overlap.har01_cellday_overlap | l6_har01_overlap |
| HAR-02 | harmonization_overlap.har02_jaccard | l6_har02_jaccard |
| HAR-03 | harmonization_factor.har03_comparable_months | l6_har03_comparable_months |
| HAR-04 | harmonization_factor.har04_pearson | l6_har04_pearson |
| HAR-05 | harmonization_factor.har05_spearman | l6_har05_spearman |
| HAR-06 | harmonization_factor.har06_factor | l6_har06_factor |
| HAR-07 | harmonization_factor.har07_factor_uncertainty | l6_har07_factor_uncertainty |

The factor module also exposes `valid_mask` and `comparable_pairs`. Public
factor functions accept `cal_start`, `cal_end`, `test_start` and
`max_unknown_days`, plus the metric-specific minimum sample parameters.
HAR-01 accepts a configurable `cal_start`.

Only reserved L6 files are added. No shared configuration, L5 code, existing
batch code or package initializer is edited. L6 imports only the permitted
L1 helpers. Comments, tests, notebook content and this report are in English.

## Running

From `data/pipeline`, run `python -m pytest tests -q`.
The L6 tests alone can be run with
`python -m pytest tests/test_harmonization_overlap.py tests/test_harmonization_factor.py -q`.

After the source is available on `metricas-pipeline`, open
`data/pipeline/notebooks/07_metrics_lote6.ipynb` in Colab and run all cells.
The notebook mounts Drive at `/content/drive`, clones or switches to
`metricas-pipeline` and imports from `data/pipeline`. Private repository access
uses a runtime `GITHUB_TOKEN` Colab secret.

The default Drive root is `/content/drive/MyDrive/Sprinklers`. Configure
`CAL_START`, `CAL_END`, `TEST_START`, `MIN_PAIRS`, `MIN_CAL_MONTHS`,
`MIN_CAL_YEARS`, `MAX_UNKNOWN_DAYS`, `GRID_DEG`, `YEARS` and `FORCE`.
The defaults follow section 7E, including calibration in 2018–2021 and test
years starting in 2022.

HAR-01/02 need `processed/modis_<year>.parquet` and
`processed/viirs-jpss1_<year>.parquet` for each selected year at or after
`CAL_START`. `YEARS = None` selects the available processed years. Both sensor
files are required for every selected year. Empty sensor files are supported.
This avoids treating an absent counterpart file as observed zero detections.
The notebook checks file instruments and acquisition-year consistency.

HAR-03 through HAR-07 read only `metrics/l1_cal_monthly.parquet`, using the
full monthly selection independently of the processed-year selection used
for overlap. If this table is missing, the notebook identifies the path and
asks for `02_metrics_lote1.ipynb` to be run first.

The notebook reads only required columns and processes compact cell-days one
year at a time using L1 `eligible_cell_days`. Annual overlap files and metadata
are stored under `metrics/_partial_lote6`. A completed partial is reused only
when its source file metadata, grid, start year, code digest and Git commit
match. Files and metadata use temporary files followed by replacement.
Missing or damaged metadata causes recalculation. `FORCE = True` recalculates
selected overlap years. Consolidation uses only the current year selection.

Outputs are the seven `metrics/l6_*.parquet` tables and `_log_lote6.csv`.
The log records all reference periods, thresholds, grid, selected overlap
years, repository commit, output rows and UTC execution time. Export is atomic
per file. Rerun after an interruption during the seven-table export. Use one
notebook instance per output directory.

## Calculation decisions

- Compact cell-days are already eligible. HAR-01 counts each country/date/cell
  once per instrument, combining satellites. It normalizes timestamps to UTC
  calendar dates, rejects invalid dates or unknown instruments, and excludes
  years before `CAL_START`. It emits no `ALL` rows. Coverage validity belongs
  to the comparable-month analysis.
- HAR-02 divides the intersection count by the union count. Empty unions
  produce null Jaccard values.
- Comparable months require both valid `modis` and `viirs` rows. `combined`
  never enters the pairs. Duplicate monthly keys and missing `cell_days`
  produce descriptive `ValueError` exceptions.
- `comparable_pairs` emits each country-month once as `calibration` or `test`.
  The `all` summaries aggregate the union of those periods. If custom periods
  have a gap, gap years enter neither period. Custom periods must be ordered
  and disjoint.
- `ALL` is a reserved output label. Its monthly values sum only countries
  comparable in that same month. Global month counts count distinct calendar
  months, not country-month observations. The input L1 table is expected to
  contain actual country rows.
- Nonempty monthly input retains every country and the `ALL` row in each
  HAR-03/04/05 period, even when there are zero comparable months. Empty input
  returns the typed empty table. Correlations are null below `MIN_PAIRS` or
  when either series is constant.
- Spearman uses average ranks for ties, then the Pearson correlation of
  ranks. Pearson uses raw monthly activity.
- HAR-06 uses the ratio of calibration sums. Country estimates require
  `MIN_CAL_MONTHS` and nonzero MODIS activity. A country with no estimate uses
  the global estimate when available, with an explicit fallback flag. If
  neither exists, the used factor is null and the fallback flag is false.
- HAR-07 uses each group's own calibration data without global fallback.
  Each omitted-year replicate applies the same `min_cal_months` requirement
  as HAR-06. If there are too few years, the full factor is unavailable, or
  any replicate is unavailable, all four estimates are null while the year
  count remains available.
- The HAR-07 range and jackknife standard error describe leave-one-year-out
  dispersion. They are not a formal confidence interval.

## Validation

Before L6, the pipeline suite had 354 passing and 3 skipped tests. L6 adds
63 tests. Full suites passed with **417 passed, 3 skipped** on both pandas
**2.2.3** and **3.1.1**. The skipped tests require real-data integration fixtures.
Validation environments are isolated in the system temporary directory.

Tests call the actual functions and include all four literal worked examples
from section 7G. They cover satellite deduplication, one-sensor-only months,
empty schemas, named missing columns, invalid periods, duplicate keys, null
counts, minimum sample boundaries, constant series, tied ranks, zero divisors,
global fallback, unavailable jackknife replicates, shuffle invariance, input
immutability and multiple countries. Categorical inputs are checked against
unused categories and `FutureWarning` errors.

Independent Python set and fraction-based oracles check overlap, monthly
pairing, factors and leave-one-year-out dispersion. HAR-01 counts also match
L1 `cal_daily` and `cal_monthly` for the three corresponding series.

Notebook cells are valid Python under `ast.parse`, with no saved outputs.
Integration tests execute its actual configuration, input discovery, annual
processing, consolidation, export and verification cells with synthetic
Parquet files. They check all seven round-tripped tables, normal and empty
inputs, cache reuse, forced recomputation, missing partial recovery, damaged
metadata recovery, unchanged L1 input, logs and clear missing-file errors.

Nine deliberate temporary mutations were run separately and restored in
`finally` blocks. Every mutation caused assertion failures.

| Mutation | Tests failing |
|---|---|
| HAR-01 intersection replaced by union | 6 |
| HAR-02 uses MODIS count instead of intersection | 2 |
| HAR-03 adds an extra comparable month | 3 |
| HAR-04 admits one pair below the minimum | 2 |
| HAR-05 uses dense ranks for ties | 1 |
| HAR-06 excludes the exact minimum calibration count | 2 |
| HAR-06 disables global fallback | 2 |
| HAR-07 removes the jackknife `(n-1)` multiplier | 2 |
| Calibration excludes the 2021 boundary | 6 |

Independent full-batch review using `.claude/skills/review-gate/SKILL.md`
is complete, with no confirmed findings remaining. The reviewer independently
confirmed 417 passing and 3 skipped tests on pandas 2.2.3 and 3.1.1.
A separate seeded oracle matched 282 comparable pairs and 32 correlation,
factor and jackknife checks.

## Limitations

Drive mounting, private repository authentication and execution against real
MODIS/VIIRS Parquet files have not been exercised locally. No real datasets
were read or downloaded. World-scale VIIRS processing may require a Colab
high-memory runtime. L5 remains independent and HAR-08 through HAR-14 belong
to L7. No shared manifest or methodology updates are included in this batch.

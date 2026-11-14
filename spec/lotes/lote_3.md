# L3 implementation report

## Scope

All ten L3 metrics are implemented according to sections 7B and 7C of
`spec/metodologia_metricas.md`.

| Metric | Function | Output table |
|---|---|---|
| CAL-05 | calendar_summary.cal05_total_period | l3_cal05_total_period |
| CAL-06 | calendar_summary.cal06_peak_month | l3_cal06_peak_month |
| CAL-07 | calendar_summary.cal07_peak_year | l3_cal07_peak_year |
| CAL-08 | calendar_summary.cal08_annual_mean | l3_cal08_annual_mean |
| CAL-09 | calendar_summary.cal09_monthly_mean | l3_cal09_monthly_mean |
| CAL-10 | calendar_summary.cal10_active_days | l3_cal10_active_days |
| CAL-11 | calendar_summary.cal11_peak_day | l3_cal11_peak_day |
| CAL-12 | calendar_summary.cal12_seasonal_profile | l3_cal12_seasonal_profile |
| HIS-03 | history_anomaly.his03_anomaly_abs | l3_his03_anomaly_abs |
| HIS-04 | history_anomaly.his04_anomaly_pct | l3_his04_anomaly_pct |

Only reserved L3 files were created. The existing package initializer,
shared configuration and other batches are preserved. Source comments,
tests, notebook instructions and this report are in English.

## Running

Run the pipeline suite from the repository root with
`cd data/pipeline` followed by `python -m pytest tests -q`.

For the L3 suite alone, run `python -m pytest tests/test_calendar_summary.py
tests/test_history_anomaly.py -q` from `data/pipeline`.

After the L3 source is committed and pushed, open
`data/pipeline/notebooks/04_metrics_lote3.ipynb` in Colab and run all cells.
It mounts Drive, clones or fast-forwards the repository and imports modules
from `data/pipeline`. Private repository access uses a `GITHUB_TOKEN` Colab
secret at runtime. No token is stored in the notebook.

The three required inputs are `metrics/l1_cal_monthly.parquet`,
`metrics/l1_cal_annual.parquet` and `metrics/l1_cal_daily.parquet` under
`/content/drive/MyDrive/Sprinklers`. If an input is missing, the notebook names
it and asks for notebook `02_metrics_lote1.ipynb` to be run first.

Configure `REF_START`, `REF_END`, `MIN_REF_YEARS`, `MAX_UNKNOWN_DAYS`,
and the optional CAL-05 `START`/`END` selection. All ten tables are computed
before export. Each output Parquet and the `_log_lote3.csv` file uses temporary
file writing followed by replacement. The log records parameters, repository
commit, row counts and UTC execution time. Rerunning replaces outputs.
The ten-table export is not a single atomic transaction. If export is
interrupted, rerun the notebook to regenerate a consistent set. Use one
notebook instance per output folder.

## Calculation decisions

- Functions are pure and use only their input DataFrames. L3 consumes the
  documented L1 aggregate schemas and never reads `processed/` or L4 outputs.
- A valid month or year is complete and has no unknown-coverage days by
  default. The limit is configurable. CAL-05 includes partial months and
  reports their count and the number of unknown days.
- CAL-05 uses inclusive bounds. Explicit bounds are retained in its output,
  even if the available selected months do not reach a bound. Omitted bounds
  use the first and last observed months of each country-series group.
  Groups with no selected months are omitted.
- CAL-06 and CAL-07 retain groups with no valid periods, returning nullable
  integer peak fields and a valid-period count of zero. Ties choose the
  earliest year/month. CAL-11 similarly chooses the earliest tied date,
  omitting years with no positive daily activity.
- CAL-08 reports the sorted valid reference years as comma-separated text.
  Groups without valid reference years remain with count zero, an empty
  year list and null statistics.
- CAL-09 always returns twelve calendar months for each existing
  country-series group. It uses the fixed valid reference pool and reports
  null means when the pool has fewer than five years by default.
- CAL-10 uses the monthly skeleton and counts distinct active dates. It
  includes zero-activity months and calendar month lengths, including leap
  February. Daily timestamps are normalized for distinct-date counting.
- CAL-12 shares require twelve non-null means and a nonzero total. Missing
  means make shares unavailable. A known zero profile still marks January
  as the earliest tied peak. Known means can define a peak even when another
  month is unknown. An entirely unknown profile has no peak.
- HIS-03 preserves every input month and excludes that month's evaluated
  year from its valid reference pool. Reference bounds restrict the pool,
  not the evaluated rows. Invalid target months retain their reference
  counts but have null means and anomalies. HIS-04 returns null percentages
  for zero or missing reference means and missing absolute anomalies.
- Input L1 keys are unique as specified, with integer counts, valid calendar
  fields and boolean partial flags. No additional aggregation of malformed
  duplicate input keys is inferred.

## Validation

Before L3, the pipeline suite had 156 passing and 3 skipped tests.
The L3 suite adds 46 passing tests. The complete suite has 202 passing and
3 skipped tests. The skipped tests require real-data integration fixtures.

Tests include literal hand-worked examples, the six-year historical example,
empty schemas, missing columns, nullable peak fields, zero denominators,
invalid and partial periods, configurable thresholds and reference bounds,
earliest ties, leap days, shuffled input, input immutability and group
isolation. Seeded invariants check period sums, maxima and zero-sum
leave-one-out anomalies. Seasonal shares sum to 100 when defined, and active
day counts remain within calendar month lengths.

Notebook code cells were parsed with `ast.parse` and have no saved outputs.
Integration tests execute the actual configuration, calculation, export and
verification cells against synthetic L1 Parquet files. They verify all ten
round-tripped output tables, reruns, empty inputs, unchanged L1 files, the
log and the missing-input error message.

Ten deliberate temporary mutations were tested separately and restored
after each run. Each produced failing assertions.

| Metric | Deliberate incorrect behavior | Tests failing |
|---|---|---|
| CAL-05 | Exclude partial months from totals | 1 |
| CAL-06 | Treat partial months as complete | 1 |
| CAL-07 | Treat partial years as complete | 1 |
| CAL-08 | Sum annual values instead of averaging | 2 |
| CAL-09 | Require strictly more than the minimum reference years | 2 |
| CAL-10 | Count duplicate active-date records | 1 |
| CAL-11 | Select the latest tied peak date | 1 |
| CAL-12 | Scale shares by 10 instead of 100 | 1 |
| HIS-03 | Include the evaluated year in reference counts | 5 |
| HIS-04 | Scale percentages by 10 instead of 100 | 2 |

Independent full-batch review using `.claude/skills/review-gate/SKILL.md`
is complete, with no confirmed findings remaining. The reviewer independently
confirmed 202 passing and 3 skipped tests and ran additional seeded oracle
checks over 720 anomaly rows and six peak groups.

## Limitations

Drive mounting, private repository authentication and real-data execution
in Colab have not been exercised locally. No real source datasets were
read or downloaded. Historical comparability remains affected by Aqua
joining MODIS in 2002 and VIIRS joining the combined series in 2018.
Reference-period configuration should be interpreted with these coverage
changes in mind.

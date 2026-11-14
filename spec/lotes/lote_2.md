# L2 implementation report

## Delivered scope

All ten L2 metrics are implemented as pure DataFrame functions.

| Metric | Function | Output table |
|---|---|---|
| OBS-04 | detections.obs04_night_pct | l2_obs04_night_pct |
| OBS-05 | detections.obs05_frp_median | l2_obs05_frp_median |
| OBS-06 | detections.obs06_frp_p90 | l2_obs06_frp_p90 |
| OBS-07 | detections.obs07_frp_peak | l2_obs07_frp_peak |
| OBS-08 | detections.obs08_frp_availability | l2_obs08_frp_availability |
| OBS-09 | detections.obs09_type_distribution | l2_obs09_type_distribution |
| OBS-10 | detections.obs10_pixel_area_median | l2_obs10_pixel_area_median |
| QA-01 | ingestion_qa.qa01_schema_validation | l2_qa01_schema_validation |
| ADD-03 | ingestion_qa.add03_duplicates | l2_add03_duplicates |
| ADD-04 | ingestion_qa.add04_zero_detection_countries | l2_add04_zero_detection_countries |

Only files reserved for L2 were created or edited. The package initializer is
empty. Comments, docstrings, tests, notebook content and this report are in English.

## Running

From `backend`, run `python -m pytest tests -q`.

Commit and push these L2 source files before running the notebook in Colab.
Open `backend/notebooks/03_metrics_lote2.ipynb` and run all cells. The notebook
mounts Drive, clones or fast-forwards the repository, and reads from
`/content/drive/MyDrive/Sprinklers/processed`. Configure `SENSORS`, `YEARS`,
`FORCE`, `CONFIDENCE` and `TYPE_VALUE` in its configuration cell.
For private repositories, enable the `GITHUB_TOKEN` Colab secret.

The notebook reads only the required columns, one sensor-year at a time.
It writes per-year results under `metrics/_l2_parts` and publishes the ten
consolidated `metrics/l2_*.parquet` tables and `metrics/_log_lote2.csv`.
Each Parquet and the log are replaced atomically via a temporary file.
A completion marker is published atomically only after all nine annual tables
succeed. A missing or damaged marker causes the year to be recalculated.
Reruns reuse completed years only when all parts exist and source metadata,
parameters and Git revision match. Incomplete years are recalculated.
The global ADD-04 calculation uses all selected annual ADD-03 counts.
Consolidation uses only the current input selection, excluding older cached runs.
Run a single notebook instance per output directory.

## Method decisions

- Shared conventions and section 7 of `spec/metodologia_metricas.md` define the
  output contracts. Invalid dates are excluded from year-based metrics and
  counted as failures by QA-01. Real dates outside pandas nanosecond timestamp
  ranges are supported by the date validation logic.
- Eligible means `type == 0` and confidence in `n, h` by default. Both filter
  parameters are configurable for OBS-04 through OBS-08. Missing filter values
  are excluded. No spatial grid is used by L2.
- Eligible groups with no usable FRP remain in OBS-05/06 with count zero and
  a null statistic. Such groups are absent from OBS-07. FRP usability follows
  the specified non-null positive rule.
- OBS-07 uses the specified date, time, latitude and longitude tie break.
  For otherwise identical ties, datetime is a final deterministic tie break.
- OBS-09 preserves product version strings and groups raw type codes without
  interpreting their meaning for VIIRS. Unknown type values remain `unknown`.
- OBS-10 uses all records with finite positive pixel area, independent of the
  eligibility filter. Groups without usable areas are absent.
- QA-01 groups all input years together. The notebook adds the filename year
  before consolidation. Missing instruments become `unknown`. Null country
  keys are retained, since no country validity rule is specified.
- Whitespace-only satellite values fail QA-01. Confidence is checked only for
  nullness. Empty input returns a typed empty output, including when it has no
  columns. Nonempty input missing required fields raises `ValueError`.
- ADD-03 counts excess acquisition-coordinate tuples within each group, not
  all members of a repeated tuple. Null tuple values are grouped consistently.
- ADD-04 sums repeated counts, uses each instrument's full minimum-to-maximum
  year range and counts distinct positive-data years per country. Zero counts
  are absences. With automatic year selection, entirely missing years within
  that range also produce absences.

## Validation

`cd backend && python -m pytest tests -q` completed with **80 passed**.
Tests call the real metric functions and the notebook's actual processing cells.
They include manually calculated examples, empty schemas, missing fields,
nullable types, invalid dates, eligibility exclusions and custom parameters,
deterministic peak ties, shuffled input, immutability, count partitions, version
separation and seeded numeric checks using Python statistics and sorted values.

Ten temporary mutations were tested separately, one per metric. Every mutation
caused failing assertions. The correct source was restored in a `finally` block
after each run, and the final complete suite passed.

| Metric | Temporary incorrect rule | Tests failing |
|---|---|---|
| OBS-04 | Include unknown day/night in denominator | 1 |
| OBS-05 | Use maximum instead of median | 2 |
| OBS-06 | Use the 50th instead of 90th percentile | 2 |
| OBS-07 | Select lowest FRP first | 2 |
| OBS-08 | Count zero FRP as usable | 1 |
| OBS-09 | Label type 3 as unknown | 1 |
| OBS-10 | Include zero pixel area | 1 |
| QA-01 | Accept hour 24 | 3 |
| ADD-03 | Count all members of duplicate tuples | 2 |
| ADD-04 | Exclude the last year from the expected range | 3 |

Independent full-batch review using `.claude/skills/review-gate/SKILL.md`
is complete. The reviewer reran the required suite and confirmed 80 passed.
One recovery issue was found and resolved: interrupted marker writes could
block a retry. Markers now use atomic replacement and malformed JSON triggers
recalculation. The regression test was confirmed to fail with `JSONDecodeError`
when that recovery handling was temporarily removed, then pass after restoration.
The final review reported no confirmed findings remaining.

## Limitations

QA-01 validates records after notebook 01 coercion and cannot recover rows
already discarded. ADD-04 cannot distinguish no detections from missing files
or missing coverage. Consult `processed/_ingest_log.csv` for ingestion context.
Specify `YEARS` to require each selected sensor-year file before processing.

The notebook has no saved outputs. All code cells are parsed with `ast.parse`.
Local integration executes its actual processing, consolidation and verification
cells against synthetic Parquet files, including cached resume and recovery
from an incomplete year or damaged marker. Drive mounting, private repository authentication and
execution on real data in Colab require validation in the user's Colab session.
No real datasets were read or downloaded for this implementation.

`pytest` was installed locally during QA-01 work. Shared dependency files were
preserved. Source changes are confined to the reserved L2 paths.

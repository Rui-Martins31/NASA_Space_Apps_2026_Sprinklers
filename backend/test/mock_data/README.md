# Mock data

Files that stand in for the pipeline's database while it is being built.
Each file plays one collection/table. `python main.py` (or `--data mock`)
serves these; the backend asks for a lat/lon box and trims it to the circle
itself, so the real database only needs range queries on `lat` and `lon`.

| File | One row per | Columns |
|---|---|---|
| `hotspots.csv` | detection | `lat`, `lon`, `date_time` (ISO-8601, UTC), `confidence_class` (`low`/`nominal`/`high`), `instrument` (`MODIS`/`VIIRS`), `satellite` (`Terra`/`Aqua`/`N20`), `type` (0/2/3, empty = unknown), `daynight` (`D`/`N`), `frp` (MW, empty = missing), `pixel_area_km2` |
| `chunk_counts.csv` | chunk × month with activity | `lat`, `lon` (chunk centre), `year`, `month`, `count` (cell-days) |
| `chunk_means.csv` | chunk × calendar month | `lat`, `lon` (chunk centre), `month`, `mean` (mean monthly `count` over the reference years) |
| `chunk_metrics.csv.gz` | metric × chunk × time | `metric`, `lat`, `lon`, `year`, `month`, `date`, `key`, `value`, `low`, `high` (gzipped CSV, ~20 MB unpacked) |

- Chunks are 0.01° cells; a chunk belongs to a circle when its centre is inside it.
- A cell-day is a chunk with at least one **eligible** detection (`type` 0, confidence nominal or high) on a UTC day; MODIS and VIIRS together count once.
- Missing rows mean zero: a chunk with no activity in a month has no `chunk_counts` row.
- `count` and `mean` are **additive** over chunks: the backend adds them up for the circle.

### `chunk_metrics.csv.gz`

The pipeline's value of each metric (`metric` = feature name, e.g. `his_05`) for one chunk. Empty cells
mean "does not apply":

| Filled time columns | The value covers | Metrics |
|---|---|---|
| `date` (+ `year`, `month`) | one day | `cal_02` (1 per cell-day), `obs_07` (day of the month's FRP peak) |
| `year` + `month` | one month | `his_05`, `his_06`, `obs_01`…`obs_06`, `obs_08`…`obs_10`, `qa_02`…`qa_05` |
| `month` only | a calendar month of the reference years | `his_01`, `his_02` |
| none | the whole record | `his_10`, `har_*` |

- Empty `lat`/`lon` = a global value, not tied to a place (`qa_05`).
- `key` splits a metric into categories (`obs_01`, `obs_02`, `obs_04`, `obs_09`).
- `low`/`high` hold ranges (`his_02` p10–p90, `har_06`/`har_07` factor interval).

How the backend combines the chunks of a circle is described in
`spec/api/frontend-backend.md` ("Features - Metrics").

The data is invented (mainland Portugal, 2000-11 to 2026-11). To regenerate:

```bash
python test/generate_mock_data.py    # hotspots.csv (fixed seed)
python test/build_mock_chunks.py     # chunk_counts.csv, chunk_means.csv from hotspots.csv
python test/build_mock_metrics.py    # chunk_metrics.csv.gz from hotspots.csv
```

The two `build_*` scripts are only a stand-in for the pipeline: the real
definitions, unit and reference period are the pipeline's to decide.

# Backend

API implementing [spec/api/frontend-backend.md](../spec/api/frontend-backend.md). Only dependency: Flask.

The backend is a middleman. The pipeline computes the metrics per grid chunk
(0.01° cells) and stores them in a database; the backend asks the database for
the lat/lon box around the requested circle, drops the chunks outside the
circle and combines the rest: counts are summed, ratios and statistics are
averaged over the chunks. It computes no statistics of its own.

```
frontend ──POST /api/<feature>──▶ main.py ──▶ features.py ──box query──▶ database/ (mock CSVs | pipeline database)
                                                  └── trim to circle, combine chunks
```

Features: `all`, `hotspots`, `calendar`, `anomalies`, the CSV export, and one
feature per metric of `spec/metricas_modis_viirs.csv` (`/api/cal_05`, ...),
listed in `config.METRICS`.

## Files

| File | What it does |
|---|---|
| `main.py` | Flask app, the endpoints, `--data` switch |
| `src/config.py` | Every setting and constant, the list of metric features, notes and error messages |
| `src/query_validation.py` | Checks the request body / query string |
| `src/features.py` | One function per API feature: query the box, trim to the circle, combine chunks |
| `src/circle_geometry.py` | Helpers: box around a circle (handles poles and the 180° meridian), point in box / circle, chunks in a circle |
| `src/database/__init__.py` | `open_database("mock" \| "database")` and the queries every database answers |
| `src/database/mock_database.py` | Mock files standing in for the database |
| `src/database/pipeline_database.py` | The pipeline's database (not connected yet) |
| `test/mock_data/` | The mock CSV files ([README](test/mock_data/README.md)) |
| `test/` | Tests and the scripts that generate the mock data |

## Run

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python main.py                     # mock data (default)
.venv/bin/python main.py --data database     # the pipeline's database
BACKEND_DATA=database .venv/bin/python main.py   # same, via environment variable
```

`--mock-dir <folder>` serves a different set of mock CSV files.

The API runs at `http://127.0.0.1:8080`. Examples:

```bash
curl -X POST http://127.0.0.1:8080/api/calendar -H 'Content-Type: application/json' -d '{
  "feature": "calendar", "lat": 39.5, "lon": -8.0, "radius": 50,
  "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2021-12-31T23:59:59"}'

# one metric: same body, "feature" = the metric's name
curl -X POST http://127.0.0.1:8080/api/cal_05 -H 'Content-Type: application/json' -d '{
  "feature": "cal_05", "lat": 39.5, "lon": -8.0, "radius": 50,
  "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2021-12-31T23:59:59"}'

# every hotspot in the circle, streamed as CSV (no max_points cap)
curl -o hotspots.csv 'http://127.0.0.1:8080/api/hotspots.csv?lat=39.5&lon=-8.0&radius=50&date_time_from=2020-01-01T00:00:00&date_time_to=2021-12-31T23:59:59'
```

Errors are JSON, `{"error": "<message>"}`: `400` for invalid parameters, `404` for an
unknown endpoint (e.g. `/api/alle`) or a metric not available yet (e.g. `/api/qa_01`),
`405` for the wrong method (e.g. `GET /api/calendar`).

## Adding a metric

1. Add its name (`"cal_05"`) to `config.METRICS` (and remove it from `METRICS_NOT_AVAILABLE`).
2. Write the function of that name in `src/features.py`; it returns `{"value": ...}` and maybe a `"note"`.
3. If it reads new per-chunk values, add them to the mock data (`test/build_mock_metrics.py`).

`main.py` creates `POST /api/<name>` for every name in `config.METRICS`.

## Connecting the database

Implement the methods described in `src/database/__init__.py` in
`src/database/pipeline_database.py`. Each is one range query on `lat`/`lon` (plus month
or date); the trim to the circle stays in `features.py`, so the database never
needs to know about circles.

## Tests

```bash
.venv/bin/python -m unittest discover test
```

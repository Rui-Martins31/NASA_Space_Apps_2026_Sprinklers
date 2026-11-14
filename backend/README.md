# Backend

API implementing [spec/api/frontend-backend.md](../spec/api/frontend-backend.md). Only dependency: Flask.

## Files

| File | What it does |
|---|---|
| `main.py` | Flask app and the 4 endpoints |
| `src/validation.py` | Checks the request body |
| `src/features.py` | Calculations: filter by circle/dates, calendar, anomalies |
| `src/loader.py` | Reads the hotspots CSV |
| `src/config.py` | Host, port, data file, limits |
| `test/` | Mock data generator and tests |

## Run

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# with mock data
.venv/bin/python test/generate_mock_data.py
.venv/bin/python main.py --data test/mock_hotspots.csv

# with real data (data/hotspots.csv)
.venv/bin/python main.py
```

The API runs at `http://127.0.0.1:8080`. Example:

```bash
curl -X POST http://127.0.0.1:8080/api/calendar -H 'Content-Type: application/json' -d '{
  "feature": "calendar", "lat": 39.5, "lon": -8.0, "radius": 50,
  "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2021-12-31T23:59:59"}'
```

Errors return status `400` with `{"error": "<message>"}`.

## Data file

CSV with columns `lat, lon, date_time, confidence_class` (ISO-8601 dates in UTC).

## Tests

```bash
.venv/bin/python -m unittest discover test
```

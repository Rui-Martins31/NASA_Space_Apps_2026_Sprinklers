# API contract (v0.3, frontend ↔ backend)

All endpoints: `POST http://127.0.0.1:8080/api/<feature>` with a JSON body.

`<feature>` is one of `all`, `calendar`, `anomalies`, `hotspots`.

## Request (same for every feature)

```json
{
  "lat": 39.92,
  "lon": -8.15,
  "radius_km": 150,
  "date_from": "2001-01-01",
  "date_to": "2026-11-13",
  "max_points": 5000
}
```

- Coordinates in decimal degrees (WGS84). The frontend converts place names to coordinates; the backend never geocodes.
- `radius_km`: 1 to 500.
- Dates: `YYYY-MM-DD`, inclusive.
- `max_points`: only used by `/hotspots`. If there are more hotspots, return a random sample of that size.

## Responses

`/api/all` returns calendar and anomalies (not hotspots, which can be huge):

```json
{ "feature": "all", "calendar": [ ... ], "anomalies": [ ... ] }
```

`/api/calendar` → `{ "feature": "calendar", "calendar": [ ... ] }`
`/api/anomalies` → `{ "feature": "anomalies", "anomalies": [ ... ] }`
`/api/hotspots` → `{ "feature": "hotspots", "hotspots": [ ... ] }`

### Array items

```json
// calendar: one entry per month in the range, including months with 0, ordered by date
{ "year": 2017, "month": 8, "count": 4210 }

// anomalies: same months as calendar; mean = average of that month over all years in the range
{ "year": 2017, "month": 8, "count": 4210, "mean": 1530.4, "anomaly": 2679.6 }

// hotspots: harmonized hotspots inside the circle and period
{ "lat": 39.95, "lon": -8.21, "date": "2017-06-17", "satellite": "S-NPP", "confidence": "high", "frp": 85.3 }
```

- `count` values are harmonized (VIIRS-equivalent).
- `confidence`: `low`, `nominal` or `high` for both sensors.
- `frp`: fire radiative power in MW.

## Errors

HTTP 400 with `{ "error": "radius_km must be between 5 and 500" }`. The message is shown to the user as is.

## Computed on the frontend (no endpoint needed)

Seasonal profile, year ranking, current month vs median and the CSV exports are all derived from `calendar` and `hotspots`.

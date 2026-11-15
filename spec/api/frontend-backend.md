# API Frontend - Backend

---

## URL

URL: 127.0.0.1 \
Port: 8080 \
Endpoint: /api \
Features: /api/[name_of_feature]

---

## Features

Legend:
- feature:
    1. "all" - all KPIs, profiles, heatmap, etc
    2. "hotspots" - hotspots map
    3. "calendar" - calendar
    4. "anomalies" - graph that compares the values for a set of years (higher than the average is considered an anomaly)

---

## Request

### Common request body

Every request includes these fields:

```json
{
    "feature": str,
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

- `feature`: {
    `"all"`,
    `"hotspots"`,
    `"calendar"`,
    `"anomalies"`
}
- `radius`: radius of the circle, in **km**.

---

## Features - Request and Response

### Feature - all

Method: POST \
Endpoint: 127.0.0.1:8080/api/all

Request:

```json
{
    "feature": "all",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "all",
    "calendar": [],
    "anomalies": []
}
```

### Feature - hotspots

Method: POST \
Endpoint: 127.0.0.1:8080/api/hotspots

Request:

```json
{
    "feature": "hotspots",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime,
    "max_points": int
}
```

Response:

```json
{
    "feature": "hotspots",
    "hotspots": [
        {
            "lat": float,
            "lon": float,
            "date_time": datetime,
            "confidence_class": "low" | "nominal" | "high"
        },
        {
            ...
        }
    ]
}
```

- `confidence_class`: {
    `low`,
    `nominal`,
    `high`
}

### Feature - calendar

Method: POST \
Endpoint: 127.0.0.1:8080/api/calendar

Request:

```json
{
    "feature": "calendar",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "calendar",
    "calendar": [
        {
            "year": int,
            "month": int,
            "count": int
        },
        {
            ...
        }
    ]
}
```

### Feature - anomalies

Method: POST \
Endpoint: 127.0.0.1:8080/api/anomalies

Request:

```json
{
    "feature": "anomalies",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "anomalies",
    "anomalies": [
        {
            "year": int,
            "month": int,
            "count": int,
            "mean": float,
            "anomaly": str
        },
        {
            ...
        }
    ]
}
```

- `mean`: the area's reference mean for that calendar month, as computed by the pipeline over its reference years (not over the requested period).
- `anomaly`: `"above"` when `count > mean`, otherwise `"normal"`.

### Feature -  export hotspots CSV

Method: GET \
Endpoint: 127.0.0.1:8080/api/hotspots.csv

Request:
```
/api/hotspots.csv?lat=39.5&lon=-8.0&radius=50&date_time_from=2020-01-01T00:00:00&date_time_to=2021-12-31T23:59:59
```

Response:
`text/csv` with `Content-Disposition: attachment`, columns `lat,lon,date_time,confidence_class`. Invalid parameters return `400` with `{"error": "<message>"}`.
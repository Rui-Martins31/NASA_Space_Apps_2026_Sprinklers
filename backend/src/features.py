"""The computations behind each feature. Plain functions, no web code."""

import math

EARTH_RADIUS_KM = 6371


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle (haversine) distance between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def select(hotspots, query):
    """Hotspots inside the circle and the date range."""
    return [
        h for h in hotspots
        if query["date_time_from"] <= h["date_time"] <= query["date_time_to"]
        and distance_km(query["lat"], query["lon"], h["lat"], h["lon"]) <= query["radius"]
    ]


def hotspots(selected, max_points):
    return [
        {**h, "date_time": h["date_time"].isoformat()}
        for h in selected[:max_points]
    ]


def calendar(selected, query):
    """Hotspot count for every month in the range (months with no fires are 0)."""
    counts = {}
    for h in selected:
        key = (h["date_time"].year, h["date_time"].month)
        counts[key] = counts.get(key, 0) + 1

    rows = []
    year, month = query["date_time_from"].year, query["date_time_from"].month
    end = (query["date_time_to"].year, query["date_time_to"].month)
    while (year, month) <= end:
        rows.append({"year": year, "month": month, "count": counts.get((year, month), 0)})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return rows


def anomalies(calendar_rows):
    """Compare each month with the mean of the same month across the years in range."""
    by_month = {}
    for row in calendar_rows:
        by_month.setdefault(row["month"], []).append(row["count"])
    mean = {month: sum(counts) / len(counts) for month, counts in by_month.items()}

    return [
        {
            **row,
            "mean": round(mean[row["month"]], 2),
            "anomaly": "above" if row["count"] > mean[row["month"]] else "normal",
        }
        for row in calendar_rows
    ]

"""The API features: one function per endpoint (see spec/api/frontend-backend.md).

The pipeline stores its numbers per grid chunk, never per circle. So every
feature:
  1. asks the database for the rows inside the lat/lon box around the circle;
  2. drops the rows in the corners of the box, outside the circle;
  3. adds up what is left (counts and means are both sums over chunks).

A chunk belongs to the circle when its centre is inside it. Chunk data is
monthly, so a period that starts or ends mid-month includes that whole month.
"""

from itertools import islice

from .circle_geometry import in_circle, query_box


def calendar(database, query):
    """Count for every month of the period (months with no activity are 0)."""
    months = list(_months_in_period(query))
    totals = dict.fromkeys(months, 0)
    for row in database.chunk_counts(query_box(query), months[0], months[-1]):
        if in_circle(query, row["lat"], row["lon"]):
            totals[(row["year"], row["month"])] += row["count"]
    return [{"year": y, "month": m, "count": totals[(y, m)]} for y, m in months]


def anomalies(database, query, calendar_rows=None):
    """Each month of the calendar next to the circle's reference mean for that month."""
    rows = calendar_rows if calendar_rows is not None else calendar(database, query)
    means = dict.fromkeys(range(1, 13), 0.0)
    for row in database.chunk_means(query_box(query)):
        if in_circle(query, row["lat"], row["lon"]):
            means[row["month"]] += row["mean"]
    return [
        {**r, "mean": round(means[r["month"]], 2),
         "anomaly": "above" if r["count"] > means[r["month"]] else "normal"}
        for r in rows
    ]


def hotspots(database, query, limit=None):
    """Hotspots inside the circle, in the database's order; limit=None means all of them."""
    rows = database.hotspots(query_box(query), query["date_time_from"], query["date_time_to"])
    inside = (h for h in rows if in_circle(query, h["lat"], h["lon"]))
    return islice(inside, limit)


def _months_in_period(query):
    """Every (year, month) from date_time_from to date_time_to."""
    start, end = query["date_time_from"], query["date_time_to"]
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

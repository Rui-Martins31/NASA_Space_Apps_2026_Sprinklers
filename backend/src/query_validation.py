"""Check the request body and turn it into a query dict.

Raises ValueError with a readable message when something is wrong.
"""

from datetime import datetime, timezone

from . import config


def parse_date(value, name):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an ISO-8601 date, e.g. 2020-01-01T00:00:00")
    # Everything is compared in UTC; dates without a timezone are assumed UTC.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_number(body, name, low, high):
    value = body.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def parse_query(body, feature):
    """Validate the common request body for the given endpoint feature."""
    if not isinstance(body, dict):
        raise ValueError("request body must be a JSON object")
    if body.get("feature") != feature:
        raise ValueError(f'feature must be "{feature}" for this endpoint')

    query = {
        "feature": feature,
        "lat": parse_number(body, "lat", -90, 90),
        "lon": parse_number(body, "lon", -180, 180),
        "radius": parse_number(body, "radius", 0, config.MAX_RADIUS_KM),
        "date_time_from": parse_date(body.get("date_time_from"), "date_time_from"),
        "date_time_to": parse_date(body.get("date_time_to"), "date_time_to"),
    }
    if query["radius"] == 0:
        raise ValueError("radius must be greater than 0")
    if query["date_time_from"] > query["date_time_to"]:
        raise ValueError("date_time_from must be before date_time_to")

    if feature == "hotspots":
        body.setdefault("max_points", config.DEFAULT_MAX_POINTS)
        query["max_points"] = int(parse_number(body, "max_points", 1, config.MAX_POINTS_LIMIT))

    return query


def parse_query_string(args, feature):
    """Same checks for a GET request, where every value arrives as text."""
    body = dict(args.items())
    for name in ("lat", "lon", "radius"):
        try:
            body[name] = float(body[name])
        except (KeyError, ValueError):
            pass  # left as is, so parse_number reports it
    return parse_query({**body, "feature": feature}, feature)

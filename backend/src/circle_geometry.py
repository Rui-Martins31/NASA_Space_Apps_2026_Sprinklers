"""Geometry helpers: the lat/lon box around a circle, and whether a point is inside it.

The database only answers box queries (a lat range and a lon range); the
features ask for the box around the circle and then keep the points inside
the circle.
"""

import math

from . import config


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle (haversine) distance between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * config.EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat, lon, radius_km):
    """Smallest lat/lon box that contains the circle.

    Returns {"lat_min", "lat_max", "lon_min", "lon_max"}.
    Two special cases:
      - the circle contains a pole: the box takes every longitude;
      - the circle crosses the 180° meridian: lon_min > lon_max, meaning the
        box wraps around (a longitude is inside if lon >= lon_min OR lon <= lon_max).
    """
    dlat = radius_km / config.KM_PER_DEGREE
    lat_min, lat_max = lat - dlat, lat + dlat
    if lat_min <= -90 or lat_max >= 90:
        return {"lat_min": max(lat_min, -90), "lat_max": min(lat_max, 90), "lon_min": -180, "lon_max": 180}

    # How far east/west the circle reaches. Degrees of longitude shrink towards
    # the poles, and the widest point of the circle is slightly poleward of its
    # centre, so this is not simply dlat / cos(lat).
    dlon = math.degrees(math.asin(min(1.0, math.sin(math.radians(dlat)) / math.cos(math.radians(lat)))))
    lon_min, lon_max = lon - dlon, lon + dlon
    if lon_min < -180:
        lon_min += 360
    if lon_max > 180:
        lon_max -= 360
    return {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max}


def query_box(query):
    """Bounding box of the circle in a validated request."""
    return bounding_box(query["lat"], query["lon"], query["radius"])


def in_box(box, lat, lon):
    if not box["lat_min"] <= lat <= box["lat_max"]:
        return False
    if box["lon_min"] <= box["lon_max"]:
        return box["lon_min"] <= lon <= box["lon_max"]
    return lon >= box["lon_min"] or lon <= box["lon_max"]  # box wraps around 180°


def in_circle(query, lat, lon):
    """Whether the point is inside the circle of a validated request."""
    return distance_km(query["lat"], query["lon"], lat, lon) <= query["radius"]

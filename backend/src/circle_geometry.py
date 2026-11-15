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


def chunks_in_circle(query, size=config.CHUNK_SIZE_DEG):
    """How many grid chunks belong to the circle (their centre is inside it), empty ones included.

    The grid is too fine to test every chunk (millions for a large circle), so
    it works one grid row at a time: at the latitude of the row's centres, the
    circle covers the longitudes lon ± half_width, and the chunk centres in
    that range are counted without visiting them.
    """
    lat0, lon0 = math.radians(query["lat"]), query["lon"]
    angle = query["radius"] / config.EARTH_RADIUS_KM  # radius as an angle at the centre of the Earth
    n_rows, n_cols = round(180 / size), round(360 / size)
    box = query_box(query)

    total = 0
    first_row = max(0, math.floor((box["lat_min"] + 90) / size))
    last_row = min(n_rows - 1, math.floor((box["lat_max"] + 90) / size))
    for row in range(first_row, last_row + 1):
        lat = math.radians(-90 + (row + 0.5) * size)
        # Spherical law of cosines: the points of this latitude at exactly `angle`
        # from the centre are lon0 ± half_width.
        denominator = math.cos(lat) * math.cos(lat0)
        if denominator <= 0:
            continue
        cos_half_width = (math.cos(angle) - math.sin(lat) * math.sin(lat0)) / denominator
        if cos_half_width > 1:
            continue  # the circle does not reach this latitude
        if cos_half_width <= -1:
            total += n_cols  # the whole latitude is inside (the circle contains a pole)
            continue
        half_width = math.degrees(math.acos(cos_half_width))
        # Columns whose centre, -180 + (col + 0.5) * size, is within lon0 ± half_width.
        # Counting unwrapped column numbers also handles the 180° meridian.
        first_col = math.ceil((lon0 - half_width + 180) / size - 0.5)
        last_col = math.floor((lon0 + half_width + 180) / size - 0.5)
        total += min(n_cols, max(0, last_col - first_col + 1))
    return total

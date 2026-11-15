"""The bounding box must contain the whole circle, or chunks would be lost before the trim."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.circle_geometry import bounding_box, distance_km, in_box
from src.config import EARTH_RADIUS_KM


def destination(lat, lon, bearing_deg, km):
    """Point reached from (lat, lon) going `km` along `bearing_deg` on the sphere."""
    lat1, lon1, b, d = math.radians(lat), math.radians(lon), math.radians(bearing_deg), km / EARTH_RADIUS_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


class BoundingBoxTest(unittest.TestCase):
    CIRCLES = [
        (38.72, -9.14, 50),    # Lisbon
        (0.0, 20.0, 1000),     # equator, largest radius
        (65.0, 25.0, 500),     # high latitude: the box gets much wider than tall
        (-17.0, 179.9, 300),   # crosses the 180° meridian
        (85.0, 0.0, 800),      # contains the North Pole
    ]

    def test_every_point_on_the_circle_is_in_the_box(self):
        for lat, lon, r in self.CIRCLES:
            box = bounding_box(lat, lon, r)
            for bearing in range(0, 360, 2):
                p = destination(lat, lon, bearing, r * 0.999)
                self.assertAlmostEqual(distance_km(lat, lon, *p), r * 0.999, places=3)
                self.assertTrue(in_box(box, *p), f"circle {(lat, lon, r)}, bearing {bearing}: {p} not in {box}")

    def test_box_is_tight_at_mid_latitude(self):
        box = bounding_box(38.72, -9.14, 50)
        self.assertAlmostEqual(box["lat_max"] - 38.72, 50 / 111.19, places=3)
        self.assertLess(box["lon_max"] - box["lon_min"], 2 * 50 / (111.19 * math.cos(math.radians(39.2))))

    def test_box_wraps_over_the_antimeridian(self):
        box = bounding_box(-17.0, 179.9, 300)
        self.assertGreater(box["lon_min"], box["lon_max"])
        self.assertTrue(in_box(box, -17.0, -179.0))
        self.assertTrue(in_box(box, -17.0, 178.0))
        self.assertFalse(in_box(box, -17.0, 0.0))

    def test_pole_takes_every_longitude(self):
        box = bounding_box(85.0, 0.0, 800)
        self.assertEqual((box["lat_max"], box["lon_min"], box["lon_max"]), (90, -180, 180))


if __name__ == "__main__":
    unittest.main()

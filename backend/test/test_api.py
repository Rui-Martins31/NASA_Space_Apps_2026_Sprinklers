"""API tests using a small hand-made dataset (no files needed).

Run from backend/:  python -m unittest discover test
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from main import create_app

# Lisbon, two points nearby, one in Porto (~275 km away)
HOTSPOTS = [
    {"lat": 38.72, "lon": -9.14, "date_time": datetime(2020, 8, 10, 14, 0), "confidence_class": "high"},
    {"lat": 38.75, "lon": -9.10, "date_time": datetime(2020, 8, 20, 3, 0), "confidence_class": "nominal"},
    {"lat": 38.70, "lon": -9.20, "date_time": datetime(2021, 8, 5, 13, 0), "confidence_class": "low"},
    {"lat": 41.15, "lon": -8.61, "date_time": datetime(2020, 8, 15, 12, 0), "confidence_class": "high"},
]

LISBON = {
    "lat": 38.72, "lon": -9.14, "radius": 50,
    "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2021-12-31T23:59:59",
}


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app(HOTSPOTS).test_client()

    def post(self, feature, **overrides):
        return self.client.post(f"/api/{feature}", json={**LISBON, "feature": feature, **overrides})

    def test_calendar_counts_points_in_circle(self):
        body = self.post("calendar").get_json()
        self.assertEqual(body["feature"], "calendar")
        self.assertEqual(len(body["calendar"]), 24)  # every month of 2020-2021
        aug = {(r["year"], r["month"]): r["count"] for r in body["calendar"]}
        self.assertEqual(aug[(2020, 8)], 2)  # Porto point is outside the radius
        self.assertEqual(aug[(2021, 8)], 1)
        self.assertEqual(aug[(2020, 1)], 0)

    def test_anomalies(self):
        rows = self.post("anomalies").get_json()["anomalies"]
        aug_2020 = next(r for r in rows if (r["year"], r["month"]) == (2020, 8))
        self.assertEqual(aug_2020["mean"], 1.5)
        self.assertEqual(aug_2020["anomaly"], "above")

    def test_hotspots_respects_max_points(self):
        body = self.post("hotspots", max_points=1).get_json()
        self.assertEqual(len(body["hotspots"]), 1)
        self.assertEqual(body["hotspots"][0]["date_time"], "2020-08-10T14:00:00")

    def test_all(self):
        body = self.post("all").get_json()
        self.assertEqual(set(body), {"feature", "calendar", "anomalies"})

    def test_timezone_is_converted_to_utc(self):
        # 15:00+01:00 is 14:00 UTC, so the 14:00 point is included...
        with_tz = self.post("hotspots", date_time_from="2020-08-10T15:00:00+01:00").get_json()
        self.assertEqual(len(with_tz["hotspots"]), 3)
        # ...but 15:00 without a timezone is read as 15:00 UTC, so it is not.
        no_tz = self.post("hotspots", date_time_from="2020-08-10T15:00:00").get_json()
        self.assertEqual(len(no_tz["hotspots"]), 2)

    def test_invalid_requests(self):
        cases = [
            self.client.post("/api/calendar", json={**LISBON, "feature": "hotspots"}),
            self.post("calendar", radius=0),
            self.post("calendar", lat=100),
            self.post("calendar", date_time_from="not a date"),
            self.post("calendar", date_time_from="2022-01-01T00:00:00"),
            self.client.post("/api/calendar", data="not json"),
        ]
        for response in cases:
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()

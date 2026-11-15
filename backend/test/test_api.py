"""API tests on a small hand-made mock database (no files needed).

Run from backend/:  python -m unittest discover test
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from main import create_app
from src.database.mock_database import MockDatabase

# Circle: 50 km around Lisbon. Its bounding box reaches ~38.27..39.17 N, ~-9.72..-8.56 E.
LISBON = {
    "lat": 38.72, "lon": -9.14, "radius": 50,
    "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2021-12-31T23:59:59",
}

CHUNK_COUNTS = [
    {"lat": 38.75, "lon": -9.15, "year": 2020, "month": 8, "count": 2},  # Lisbon
    {"lat": 38.75, "lon": -9.15, "year": 2021, "month": 8, "count": 1},
    {"lat": 38.65, "lon": -9.05, "year": 2020, "month": 8, "count": 1},  # ~10 km away
    {"lat": 38.75, "lon": -9.15, "year": 2019, "month": 8, "count": 9},  # before the period
    {"lat": 39.10, "lon": -8.60, "year": 2020, "month": 8, "count": 7},  # in the box, ~63 km: outside
    {"lat": 41.15, "lon": -8.65, "year": 2020, "month": 8, "count": 5},  # Porto, outside the box
]
CHUNK_MEANS = [
    {"lat": 38.75, "lon": -9.15, "month": 8, "mean": 1.0},
    {"lat": 38.65, "lon": -9.05, "month": 8, "mean": 0.5},
    {"lat": 39.10, "lon": -8.60, "month": 8, "mean": 4.0},
    {"lat": 41.15, "lon": -8.65, "month": 8, "mean": 3.0},
]
HOTSPOTS = [
    {"lat": 38.72, "lon": -9.14, "date_time": datetime(2020, 8, 10, 14, 0), "confidence_class": "high"},
    {"lat": 38.75, "lon": -9.10, "date_time": datetime(2020, 8, 20, 3, 0), "confidence_class": "nominal"},
    {"lat": 38.70, "lon": -9.20, "date_time": datetime(2021, 8, 5, 13, 0), "confidence_class": "low"},
    {"lat": 39.10, "lon": -8.60, "date_time": datetime(2020, 8, 12, 13, 0), "confidence_class": "high"},  # box corner
    {"lat": 41.15, "lon": -8.61, "date_time": datetime(2020, 8, 15, 12, 0), "confidence_class": "high"},  # Porto
]


class ApiTest(unittest.TestCase):
    def setUp(self):
        database = MockDatabase(CHUNK_COUNTS, CHUNK_MEANS, HOTSPOTS)
        self.client = create_app(database).test_client()

    def post(self, feature, **overrides):
        return self.client.post(f"/api/{feature}", json={**LISBON, "feature": feature, **overrides})

    def test_calendar_sums_chunks_inside_the_circle(self):
        body = self.post("calendar").get_json()
        self.assertEqual(body["feature"], "calendar")
        self.assertEqual(len(body["calendar"]), 24)  # every month of 2020-2021
        counts = {(r["year"], r["month"]): r["count"] for r in body["calendar"]}
        self.assertEqual(counts[(2020, 8)], 3)  # 2 + 1; the box corner (7) and Porto (5) are trimmed
        self.assertEqual(counts[(2021, 8)], 1)
        self.assertEqual(counts[(2020, 1)], 0)

    def test_anomalies_add_up_chunk_means(self):
        rows = {(r["year"], r["month"]): r for r in self.post("anomalies").get_json()["anomalies"]}
        self.assertEqual(rows[(2020, 8)], {"year": 2020, "month": 8, "count": 3, "mean": 1.5, "anomaly": "above"})
        self.assertEqual(rows[(2021, 8)]["anomaly"], "normal")  # 1 < 1.5
        self.assertEqual(rows[(2020, 3)]["mean"], 0)

    def test_all(self):
        body = self.post("all").get_json()
        self.assertEqual(list(body), ["feature", "calendar", "anomalies"])
        self.assertEqual([r["count"] for r in body["anomalies"]], [r["count"] for r in body["calendar"]])

    def test_hotspots_trimmed_to_circle_and_max_points(self):
        all_inside = self.post("hotspots").get_json()["hotspots"]
        self.assertEqual([h["confidence_class"] for h in all_inside], ["high", "nominal", "low"])
        one = self.post("hotspots", max_points=1).get_json()["hotspots"]
        self.assertEqual(one, [{"lat": 38.72, "lon": -9.14, "date_time": "2020-08-10T14:00:00",
                                "confidence_class": "high"}])

    def test_timezone_is_converted_to_utc(self):
        # 15:00+01:00 is 14:00 UTC, so the 14:00 point is included...
        with_tz = self.post("hotspots", date_time_from="2020-08-10T15:00:00+01:00").get_json()
        self.assertEqual(len(with_tz["hotspots"]), 3)
        # ...but 15:00 without a timezone is read as 15:00 UTC, so it is not.
        no_tz = self.post("hotspots", date_time_from="2020-08-10T15:00:00").get_json()
        self.assertEqual(len(no_tz["hotspots"]), 2)

    def test_hotspots_csv_has_every_hotspot_in_the_circle(self):
        params = {k: v for k, v in LISBON.items()}
        response = self.client.get("/api/hotspots.csv", query_string=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertEqual(response.headers["Content-Disposition"], "attachment")
        self.assertEqual(response.get_data(as_text=True).splitlines(), [
            "lat,lon,date_time,confidence_class",
            "38.72,-9.14,2020-08-10T14:00:00,high",
            "38.75,-9.1,2020-08-20T03:00:00,nominal",
            "38.7,-9.2,2021-08-05T13:00:00,low",
        ])

    def test_hotspots_csv_invalid_query(self):
        for params in ({**LISBON, "radius": "abc"}, {**LISBON, "lat": 100},
                       {k: v for k, v in LISBON.items() if k != "radius"}):
            response = self.client.get("/api/hotspots.csv", query_string=params)
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.get_json())

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


class AntimeridianTest(unittest.TestCase):
    """A circle over the 180° meridian (Fiji) must get chunks from both sides."""

    def test_chunks_on_both_sides_are_added(self):
        database = MockDatabase(
            chunk_counts=[
                {"lat": -17.05, "lon": 179.95, "year": 2020, "month": 1, "count": 2},
                {"lat": -17.05, "lon": -179.95, "year": 2020, "month": 1, "count": 3},
                {"lat": -17.05, "lon": 0.05, "year": 2020, "month": 1, "count": 100},  # other side of the world
            ],
            chunk_means=[], hotspots=[])
        body = create_app(database).test_client().post("/api/calendar", json={
            "feature": "calendar", "lat": -17.0, "lon": 179.99, "radius": 20,
            "date_time_from": "2020-01-01T00:00:00", "date_time_to": "2020-01-31T23:59:59"}).get_json()
        self.assertEqual(body["calendar"], [{"year": 2020, "month": 1, "count": 5}])


if __name__ == "__main__":
    unittest.main()

"""Choosing mock or real data, and the committed mock files staying consistent with each other."""

import csv
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import create_app
from src import config
from src.database import open_database
from src.database.mock_database import MockDatabase


class OpenDatabaseTest(unittest.TestCase):
    def test_mock_loads_the_csv_files(self):
        self.assertIsInstance(open_database("mock"), MockDatabase)

    def test_mock_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(FileNotFoundError,
                                        "hotspots.csv, chunk_counts.csv, chunk_means.csv, chunk_metrics.csv.gz"):
                open_database("mock", mock_dir=empty)

    def test_pipeline_database_is_not_connected_yet(self):
        with self.assertRaisesRegex(NotImplementedError, "--data mock"):
            open_database("database")

    def test_unknown_option(self):
        with self.assertRaisesRegex(ValueError, "mock, database"):
            open_database("postgres")


class MockDataTest(unittest.TestCase):
    """The chunk tables are built from hotspots.csv; they must still agree with it and with each other."""

    # A circle over all of mainland Portugal, over the whole record.
    PORTUGAL = {"lat": 39.6, "lon": -8.0, "radius": 600,
                "date_time_from": "2000-11-01T00:00:00", "date_time_to": "2026-11-30T23:59:59"}

    @classmethod
    def setUpClass(cls):
        cls.database = open_database("mock")
        cls.client = create_app(cls.database).test_client()
        with open(config.MOCK_DATA_DIR / config.MOCK_HOTSPOTS_FILE, newline="", encoding="utf-8") as f:
            cls.n_hotspots = sum(1 for _ in csv.DictReader(f))
        with open(config.MOCK_DATA_DIR / config.MOCK_CHUNK_COUNTS_FILE, newline="", encoding="utf-8") as f:
            cls.n_cell_days = sum(int(r["count"]) for r in csv.DictReader(f))

    def post(self, feature):
        return self.client.post(f"/api/{feature}", json={**self.PORTUGAL, "feature": feature}).get_json()

    def test_chunk_counts_are_the_daily_cell_days(self):
        # chunk_counts (monthly) and cal_02 (one row per cell-day) count the same cell-days.
        world = {"lat_min": -90, "lat_max": 90, "lon_min": -180, "lon_max": 180}
        daily = list(self.database.chunk_metrics("cal_02", world, datetime.min, datetime.max))
        self.assertEqual(len(daily), self.n_cell_days)
        # A cell-day merges detections, so there are fewer of them than hotspots.
        self.assertLess(self.n_cell_days, self.n_hotspots)

    def test_circle_over_all_of_portugal_sees_everything(self):
        self.assertEqual(sum(r["count"] for r in self.post("calendar")["calendar"]), self.n_cell_days)
        self.assertEqual(self.post("cal_01")["value"], self.n_cell_days)
        self.assertEqual(sum(r["value"] for r in self.post("obs_01")["value"]), self.n_hotspots)
        csv_lines = self.client.get("/api/hotspots.csv", query_string=self.PORTUGAL).get_data(as_text=True).splitlines()
        self.assertEqual(len(csv_lines) - 1, self.n_hotspots)  # header + every hotspot, no max_points cap

    def test_every_metric_answers_on_the_mock_data(self):
        for name in config.METRICS:
            with self.subTest(metric=name):
                body = self.post(name)
                self.assertEqual(body["feature"], name)
                self.assertIn("value", body)


if __name__ == "__main__":
    unittest.main()

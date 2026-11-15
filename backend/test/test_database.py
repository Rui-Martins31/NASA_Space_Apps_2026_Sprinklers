"""Choosing mock or real data, and the committed mock files staying consistent with each other."""

import csv
import sys
import tempfile
import unittest
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
            with self.assertRaisesRegex(FileNotFoundError, "hotspots.csv, chunk_counts.csv, chunk_means.csv"):
                open_database("mock", mock_dir=empty)

    def test_pipeline_database_is_not_connected_yet(self):
        with self.assertRaisesRegex(NotImplementedError, "--data mock"):
            open_database("database")

    def test_unknown_option(self):
        with self.assertRaisesRegex(ValueError, "mock, database"):
            open_database("postgres")


class MockDataTest(unittest.TestCase):
    """The chunk tables are built from hotspots.csv; they must still agree with it."""

    @classmethod
    def setUpClass(cls):
        cls.client = create_app(open_database("mock")).test_client()
        with open(config.MOCK_DATA_DIR / config.MOCK_HOTSPOTS_FILE, newline="", encoding="utf-8") as f:
            cls.n_hotspots = sum(1 for _ in csv.DictReader(f))

    def test_chunk_counts_add_up_to_the_hotspots(self):
        with open(config.MOCK_DATA_DIR / config.MOCK_CHUNK_COUNTS_FILE, newline="", encoding="utf-8") as f:
            self.assertEqual(sum(int(r["count"]) for r in csv.DictReader(f)), self.n_hotspots)

    def test_circle_over_all_of_portugal_sees_every_hotspot(self):
        query = {"feature": "calendar", "lat": 39.6, "lon": -8.0, "radius": 600,
                 "date_time_from": "2000-11-01T00:00:00", "date_time_to": "2026-11-30T23:59:59"}
        calendar = self.client.post("/api/calendar", json=query).get_json()["calendar"]
        self.assertEqual(sum(r["count"] for r in calendar), self.n_hotspots)
        csv_lines = self.client.get("/api/hotspots.csv", query_string=query).get_data(as_text=True).splitlines()
        self.assertEqual(len(csv_lines) - 1, self.n_hotspots)  # header + every hotspot, no max_points cap


if __name__ == "__main__":
    unittest.main()

"""CSV files standing in for the pipeline's database: one file per table.

The columns are described in test/mock_data/README.md. The rows are loaded
once; every method filters them by the box, like the database query will.
"""

import csv
from datetime import datetime
from pathlib import Path

from .. import config
from ..circle_geometry import in_box


class MockDatabase:
    def __init__(self, chunk_counts, chunk_means, hotspots):
        self._chunk_counts = chunk_counts
        self._chunk_means = chunk_means
        self._hotspots = hotspots

    @classmethod
    def from_dir(cls, directory):
        directory = Path(directory)
        files = [config.MOCK_HOTSPOTS_FILE, config.MOCK_CHUNK_COUNTS_FILE, config.MOCK_CHUNK_MEANS_FILE]
        missing = [name for name in files if not (directory / name).is_file()]
        if missing:
            raise FileNotFoundError(f"missing mock data in {directory}: {', '.join(missing)}")

        return cls(
            chunk_counts=[
                {"lat": float(r["lat"]), "lon": float(r["lon"]),
                 "year": int(r["year"]), "month": int(r["month"]), "count": int(r["count"])}
                for r in _read_csv(directory / config.MOCK_CHUNK_COUNTS_FILE)
            ],
            chunk_means=[
                {"lat": float(r["lat"]), "lon": float(r["lon"]),
                 "month": int(r["month"]), "mean": float(r["mean"])}
                for r in _read_csv(directory / config.MOCK_CHUNK_MEANS_FILE)
            ],
            hotspots=[
                {"lat": float(r["lat"]), "lon": float(r["lon"]),
                 "date_time": datetime.fromisoformat(r["date_time"]),
                 "confidence_class": r["confidence_class"]}
                for r in _read_csv(directory / config.MOCK_HOTSPOTS_FILE)
            ],
        )

    def chunk_counts(self, box, first_month, last_month):
        return (r for r in self._chunk_counts
                if first_month <= (r["year"], r["month"]) <= last_month
                and in_box(box, r["lat"], r["lon"]))

    def chunk_means(self, box):
        return (r for r in self._chunk_means if in_box(box, r["lat"], r["lon"]))

    def hotspots(self, box, date_time_from, date_time_to):
        return (h for h in self._hotspots
                if date_time_from <= h["date_time"] <= date_time_to
                and in_box(box, h["lat"], h["lon"]))


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

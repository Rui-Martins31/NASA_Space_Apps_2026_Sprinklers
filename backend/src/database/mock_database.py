"""CSV files standing in for the pipeline's database: one file per table.

The columns are described in test/mock_data/README.md. The rows are loaded
once; every method filters them by the box, like the database query will.
"""

import csv
import gzip
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .. import config
from ..circle_geometry import in_box


class MockDatabase:
    def __init__(self, chunk_counts, chunk_means, hotspots, chunk_metrics=(), record=None):
        """record = (first, last) datetime of the data; by default the first and last hotspot."""
        self._chunk_counts = chunk_counts
        self._chunk_means = chunk_means
        self._hotspots = hotspots
        self._chunk_metrics = defaultdict(list)
        for row in chunk_metrics:
            self._chunk_metrics[row["metric"]].append(row)
        self._record = record

    @classmethod
    def from_dir(cls, directory):
        directory = Path(directory)
        files = [config.MOCK_HOTSPOTS_FILE, config.MOCK_CHUNK_COUNTS_FILE, config.MOCK_CHUNK_MEANS_FILE,
                 config.MOCK_CHUNK_METRICS_FILE]
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
            chunk_metrics=[_metric_row(r) for r in _read_csv(directory / config.MOCK_CHUNK_METRICS_FILE)],
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

    def chunk_metrics(self, metric, box, date_time_from, date_time_to):
        first_month = (date_time_from.year, date_time_from.month)
        last_month = (date_time_to.year, date_time_to.month)

        def in_period(r):
            if r["date"] is not None:
                return date_time_from.date() <= r["date"] <= date_time_to.date()
            if r["month"] is not None and r["year"] is not None:
                return first_month <= (r["year"], r["month"]) <= last_month
            if r["year"] is not None:
                return date_time_from.year <= r["year"] <= date_time_to.year
            return True  # no time: covers the whole record

        return (r for r in self._chunk_metrics[metric]
                if (r["lat"] is None or in_box(box, r["lat"], r["lon"])) and in_period(r))

    def data_range(self):
        if self._record is None:
            dates = [h["date_time"] for h in self._hotspots]
            self._record = (min(dates), max(dates))
        return self._record


def _metric_row(r):
    """A chunk_metrics CSV row, typed; empty cells become None."""
    def number(text, kind=float):
        return kind(text) if text != "" else None
    return {
        "metric": r["metric"],
        "lat": number(r["lat"]), "lon": number(r["lon"]),
        "year": number(r["year"], int), "month": number(r["month"], int),
        "date": date.fromisoformat(r["date"]) if r["date"] else None,
        "key": r["key"] or None,
        "value": number(r["value"]), "low": number(r["low"]), "high": number(r["high"]),
    }


def _read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

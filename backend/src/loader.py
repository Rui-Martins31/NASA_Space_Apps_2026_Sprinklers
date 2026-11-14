"""Load hotspots from a CSV file into a list of dicts."""

import csv
from datetime import datetime


def load_hotspots(path):
    hotspots = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hotspots.append({
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "date_time": datetime.fromisoformat(row["date_time"]),
                "confidence_class": row["confidence_class"],
            })
    return hotspots

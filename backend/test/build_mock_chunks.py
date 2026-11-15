"""Build the mock chunk tables from test/mock_data/hotspots.csv.

Stands in for the pipeline until it writes to the database: it puts every
eligible hotspot on the grid (config.CHUNK_SIZE_DEG) and writes, per chunk,
  - chunk_counts.csv  cell-days per month (only months with activity);
  - chunk_means.csv   mean monthly cell-days per calendar month over the
                      complete years of the record (only non-zero means).

A cell-day is a chunk with at least one eligible detection on a UTC day
(MODIS and VIIRS combined: a cell-day counts once even if both see it).
Eligible = type 0 (vegetation) and confidence nominal or high.

The real pipeline decides the unit and the reference period; these files
only have to look like what it will store. See test/mock_data/README.md.
test/build_mock_metrics.py builds chunk_metrics.csv from the same hotspots.

Run:  python test/build_mock_chunks.py
"""

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from src import config

# Coordinates have at most 4 decimals, so the grid maths is done in integers
# (floor() on floats puts some points in the wrong chunk).
SCALE = 10_000


def chunk_centre(lat, lon, size=config.CHUNK_SIZE_DEG):
    """Centre of the grid chunk that contains the point."""
    step = round(size * SCALE)
    row = (round(lat * SCALE) + 90 * SCALE) // step
    col = (round(lon * SCALE) + 180 * SCALE) // step
    return round(-90 + (row + 0.5) * size, 4), round(-180 + (col + 0.5) * size, 4)


def read_hotspots(path):
    """Every row of hotspots.csv, typed; missing type / frp are None."""
    with open(path, newline="", encoding="utf-8") as f:
        return [{
            "lat": float(r["lat"]), "lon": float(r["lon"]),
            "date_time": datetime.fromisoformat(r["date_time"]),
            "confidence_class": r["confidence_class"],
            "instrument": r["instrument"], "satellite": r["satellite"],
            "type": int(r["type"]) if r["type"] else None,
            "daynight": r["daynight"],
            "frp": float(r["frp"]) if r["frp"] else None,
            "pixel_area_km2": float(r["pixel_area_km2"]),
        } for r in csv.DictReader(f)]


def is_eligible(hotspot, confidence=("nominal", "high")):
    return hotspot["type"] == 0 and hotspot["confidence_class"] in confidence


def cell_days(hotspots, size=config.CHUNK_SIZE_DEG):
    """Distinct (chunk lat, chunk lon, date) of the given hotspots."""
    return {(*chunk_centre(h["lat"], h["lon"], size), h["date_time"].date()) for h in hotspots}


def reference_years(hotspots):
    """Complete years of the record: the first and last year are partial."""
    first = min(h["date_time"] for h in hotspots)
    last = max(h["date_time"] for h in hotspots)
    return range(first.year + 1, last.year)


def build(hotspots):
    """(counts rows, means rows) for a list of hotspots (dicts from read_hotspots)."""
    counts = Counter()
    for lat, lon, day in cell_days(h for h in hotspots if is_eligible(h)):
        counts[(lat, lon, day.year, day.month)] += 1

    ref_years = reference_years(hotspots)
    totals = Counter()
    for (lat, lon, year, month), n in counts.items():
        if year in ref_years:
            totals[(lat, lon, month)] += n

    count_rows = [{"lat": lat, "lon": lon, "year": y, "month": m, "count": n}
                  for (lat, lon, y, m), n in sorted(counts.items())]
    mean_rows = [{"lat": lat, "lon": lon, "month": m, "mean": round(n / len(ref_years), 4)}
                 for (lat, lon, m), n in sorted(totals.items())]
    return count_rows, mean_rows


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    directory = config.MOCK_DATA_DIR
    hotspots = read_hotspots(directory / config.MOCK_HOTSPOTS_FILE)
    count_rows, mean_rows = build(hotspots)
    write(directory / config.MOCK_CHUNK_COUNTS_FILE, count_rows)
    write(directory / config.MOCK_CHUNK_MEANS_FILE, mean_rows)
    print(f"{len(hotspots)} hotspots -> {len(count_rows)} chunk-month rows, {len(mean_rows)} chunk means")


if __name__ == "__main__":
    main()

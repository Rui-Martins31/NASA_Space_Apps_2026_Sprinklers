"""Build the mock chunk tables from test/mock_data/hotspots.csv.

Stands in for the pipeline until it writes to the database: it puts every
hotspot on a 0.1° grid and writes, per chunk,
  - chunk_counts.csv  hotspots per month (only months with activity);
  - chunk_means.csv   mean monthly count per calendar month over the
                      complete years of the record (only non-zero means).

The real pipeline decides the unit and the reference period; these files
only have to look like what it will store. See test/mock_data/README.md.

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


def chunk_centre(lat, lon):
    """Centre of the grid chunk that contains the point."""
    size = config.CHUNK_SIZE_DEG
    step = round(size * SCALE)
    row = (round(lat * SCALE) + 90 * SCALE) // step
    col = (round(lon * SCALE) + 180 * SCALE) // step
    return round(-90 + (row + 0.5) * size, 4), round(-180 + (col + 0.5) * size, 4)


def build(hotspots):
    """(counts rows, means rows) for a list of (lat, lon, datetime)."""
    counts = Counter()
    for lat, lon, dt in hotspots:
        counts[(*chunk_centre(lat, lon), dt.year, dt.month)] += 1

    first = min(dt for _, _, dt in hotspots)
    last = max(dt for _, _, dt in hotspots)
    # Complete years only: the first and last year of the record are partial.
    ref_years = range(first.year + 1, last.year)
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
    with open(directory / config.MOCK_HOTSPOTS_FILE, newline="", encoding="utf-8") as f:
        hotspots = [(float(r["lat"]), float(r["lon"]), datetime.fromisoformat(r["date_time"]))
                    for r in csv.DictReader(f)]
    count_rows, mean_rows = build(hotspots)
    write(directory / config.MOCK_CHUNK_COUNTS_FILE, count_rows)
    write(directory / config.MOCK_CHUNK_MEANS_FILE, mean_rows)
    print(f"{len(hotspots)} hotspots -> {len(count_rows)} chunk-month rows, {len(mean_rows)} chunk means")


if __name__ == "__main__":
    main()

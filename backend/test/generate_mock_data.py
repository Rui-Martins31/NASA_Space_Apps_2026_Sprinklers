"""Write fake hotspots to test/mock_hotspots.csv.

Points are spread over mainland Portugal, 2000-today, with more fires in summer.
The random seed is fixed, so the file is always the same.

Run:  python test/generate_mock_data.py
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT = Path(__file__).parent / "mock_hotspots.csv"
N_POINTS = 20_000

# Relative fire activity per month, Jan..Dec
MONTH_WEIGHT = [1, 1, 2, 3, 3, 5, 12, 18, 14, 6, 2, 1]


def random_date(rng):
    """A random date, more likely in high-activity months."""
    start = datetime(2000, 11, 1)
    days = (datetime.now() - start).days
    while True:
        dt = start + timedelta(days=rng.randrange(days), minutes=rng.randrange(1440))
        if rng.random() * max(MONTH_WEIGHT) <= MONTH_WEIGHT[dt.month - 1]:
            return dt


def main():
    rng = random.Random(42)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["lat", "lon", "date_time", "confidence_class"])
        for _ in range(N_POINTS):
            writer.writerow([
                round(rng.uniform(37.0, 42.0), 4),
                round(rng.uniform(-9.5, -6.2), 4),
                random_date(rng).isoformat(timespec="minutes"),
                rng.choices(["low", "nominal", "high"], weights=[2, 5, 3])[0],
            ])
    print(f"Wrote {N_POINTS} hotspots to {OUTPUT}")


if __name__ == "__main__":
    main()

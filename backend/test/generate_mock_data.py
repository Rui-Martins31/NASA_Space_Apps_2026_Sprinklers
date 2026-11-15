"""Write fake hotspots for mainland Portugal to test/mock_data/hotspots.csv.

Afterwards run test/build_mock_chunks.py to rebuild the chunk tables from them.

The data is invented, but shaped like the real record so the app shows
something recognisable:
  - every point is on land, inside a rough outline of mainland Portugal;
  - background fires are concentrated in the forested centre and north,
    and peak in July-September;
  - the large fire events of 2003-2025 are added as dense clusters in the
    right place and month (Pedrogao Grande, Jun 2017; Oct 2017; Monchique 2018;
    Serra da Estrela 2022; ...).

The random seed is fixed, so the file is always the same.

Run:  python test/generate_mock_data.py
"""

import csv
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from src import config

OUTPUT = config.MOCK_DATA_DIR / config.MOCK_HOTSPOTS_FILE
START = datetime(2000, 11, 1)
N_BACKGROUND = 20_000

# Rough outline of mainland Portugal, (lon, lat), clockwise from Caminha.
PORTUGAL = [
    (-8.87, 41.87), (-8.64, 42.05), (-8.20, 42.15), (-8.08, 41.82), (-7.90, 41.88),
    (-7.45, 41.88), (-6.75, 41.95), (-6.27, 41.55), (-6.55, 41.20), (-6.93, 41.03),
    (-6.80, 40.80), (-6.85, 40.25), (-7.00, 40.20), (-7.00, 39.67), (-7.25, 39.40),
    (-7.05, 39.00), (-7.10, 38.88), (-7.25, 38.73), (-7.30, 38.40), (-6.95, 38.20),
    (-7.35, 37.95), (-7.50, 37.55), (-7.42, 37.18), (-7.93, 37.00), (-8.95, 37.00),
    (-8.80, 37.40), (-8.88, 37.95), (-8.80, 38.45), (-9.21, 38.42), (-9.15, 38.70),
    (-9.50, 38.78), (-9.42, 39.10), (-9.38, 39.36), (-9.07, 39.60), (-8.87, 40.15),
    (-8.75, 40.65), (-8.68, 41.15), (-8.78, 41.55),
]

# Where background fires happen: (lat, lon, spread_km, weight).
# Forested, mountainous interior of the centre and north burns the most.
REGIONS = [
    (40.10, -8.00, 45, 5),  # Pinhal Interior (Pedrogao, Sertã, Mação)
    (40.30, -7.70, 35, 4),  # Serra da Estrela / Covilhã
    (40.75, -8.05, 40, 4),  # Viseu / Vouzela / São Pedro do Sul
    (41.55, -8.10, 40, 4),  # Minho interior / Peneda-Gerês / Basto
    (41.40, -7.30, 50, 3),  # Trás-os-Montes
    (40.90, -8.40, 30, 3),  # Arouca / Serra da Freita
    (39.70, -8.60, 35, 2),  # Leiria / Ourém
    (37.30, -8.50, 25, 2),  # Serra de Monchique / Algarve barrocal
    (38.60, -8.10, 80, 1),  # Alentejo (agricultural burning, fewer fires)
]

# Relative fire activity per month, Jan..Dec
MONTH_WEIGHT = [1, 1, 3, 2, 2, 4, 12, 18, 14, 6, 2, 1]

# Bad and quiet years scale the background (1 = typical).
YEAR_FACTOR = {2003: 1.8, 2005: 2.0, 2010: 1.4, 2012: 1.3, 2013: 1.5, 2016: 1.6,
               2017: 2.2, 2007: 0.5, 2008: 0.5, 2014: 0.4, 2018: 0.7, 2021: 0.5,
               2022: 1.5, 2024: 1.2, 2025: 1.7}

# Large fire events: (name, year, month, first_day, days, lat, lon, spread_km, hotspots)
EVENTS = [
    ("Monchique",               2003, 8,  8,  10, 37.32, -8.56, 18, 900),
    ("Mação / Sertã",           2003, 8,  1,  14, 39.60, -8.00, 25, 1400),
    ("Nisa / Portalegre",       2003, 8,  3,   7, 39.50, -7.65, 20, 700),
    ("Coimbra / Penacova",      2005, 8, 18,  10, 40.25, -8.20, 25, 1100),
    ("Viseu / Tondela",         2005, 8, 10,  12, 40.60, -8.00, 25, 900),
    ("Arouca",                  2016, 8,  8,   7, 40.93, -8.25, 15, 900),
    ("Peneda / Arcos",          2016, 8,  7,   8, 41.90, -8.35, 18, 700),
    ("Pedrógão Grande",         2017, 6, 17,   6, 39.92, -8.15, 18, 1600),
    ("Lousã / Oliveira do Hospital", 2017, 10, 15, 3, 40.36, -7.86, 30, 2200),
    ("Pinhal de Leiria",        2017, 10, 15,  2, 39.80, -8.95, 10, 700),
    ("Vouzela / Oliveira de Frades", 2017, 10, 15, 3, 40.70, -8.15, 18, 900),
    ("Monchique",               2018, 8,  3,   8, 37.32, -8.56, 15, 1300),
    ("Vila de Rei / Mação",     2019, 7, 20,   4, 39.67, -8.05, 12, 700),
    ("Ourém / Leiria",          2022, 7,  9,   6, 39.65, -8.58, 15, 600),
    ("Murça",                   2022, 7, 17,   4, 41.40, -7.45, 12, 600),
    ("Serra da Estrela",        2022, 8,  6,  12, 40.32, -7.60, 18, 1800),
    ("Albergaria / Sever do Vouga", 2024, 9, 15, 5, 40.70, -8.35, 18, 1300),
    ("Nelas / Mangualde",       2024, 9, 15,   4, 40.55, -7.80, 15, 700),
    ("Arganil / Piódão",        2025, 8, 13,  10, 40.20, -7.90, 22, 2000),
    ("Trancoso / Sabugal",      2025, 8, 10,   9, 40.70, -7.20, 25, 1200),
    ("Ponte da Barca",          2025, 8, 12,   6, 41.80, -8.40, 15, 600),
]


def in_portugal(lat, lon):
    """Ray-casting point-in-polygon test against the outline above."""
    inside = False
    j = len(PORTUGAL) - 1
    for i, (xi, yi) in enumerate(PORTUGAL):
        xj, yj = PORTUGAL[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_near(rng, lat, lon, spread_km):
    """A random point on land, normally distributed around (lat, lon)."""
    while True:
        dlat = rng.gauss(0, spread_km) / 111
        dlon = rng.gauss(0, spread_km) / (111 * math.cos(math.radians(lat)))
        p = (lat + dlat, lon + dlon)
        if in_portugal(*p):
            return p


def background_date(rng):
    """A random date since START, more likely in summer and in bad years."""
    days = (datetime.now() - START).days
    max_weight = max(MONTH_WEIGHT) * max(YEAR_FACTOR.values())
    while True:
        dt = START + timedelta(days=rng.randrange(days), minutes=rng.randrange(1440))
        weight = MONTH_WEIGHT[dt.month - 1] * YEAR_FACTOR.get(dt.year, 1)
        if rng.random() * max_weight <= weight:
            return dt


def overpass_time(rng, day):
    """VIIRS/MODIS see Portugal around 01-03 h and 12-14 h UTC."""
    hour = rng.choice([1, 2, 13, 13, 14])  # more daytime detections
    return day + timedelta(hours=hour, minutes=rng.randrange(60))


def rows(rng):
    weights = [r[3] for r in REGIONS]
    for _ in range(N_BACKGROUND):
        lat, lon, spread, _w = rng.choices(REGIONS, weights=weights)[0]
        dt = background_date(rng)
        yield (*point_near(rng, lat, lon, spread), dt,
               rng.choices(["low", "nominal", "high"], weights=[3, 5, 2])[0])

    for _name, year, month, first_day, days, lat, lon, spread, n in EVENTS:
        start = datetime(year, month, first_day)
        if start > datetime.now():
            continue
        for _ in range(n):
            day = start + timedelta(days=min(int(rng.expovariate(2 / days)), days - 1))
            # big fires burn hot: more high-confidence detections
            yield (*point_near(rng, lat, lon, spread), overpass_time(rng, day),
                   rng.choices(["low", "nominal", "high"], weights=[1, 4, 5])[0])


def main():
    rng = random.Random(42)
    data = list(rows(rng))
    # Shuffled, because the backend returns the first max_points rows:
    # this way any prefix is a fair sample in space and time.
    rng.shuffle(data)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["lat", "lon", "date_time", "confidence_class"])
        for lat, lon, dt, confidence in data:
            writer.writerow([round(lat, 4), round(lon, 4), dt.isoformat(timespec="minutes"), confidence])
    print(f"Wrote {len(data)} hotspots ({N_BACKGROUND} background + "
          f"{len(data) - N_BACKGROUND} from {len(EVENTS)} fire events) to {OUTPUT}")


if __name__ == "__main__":
    main()

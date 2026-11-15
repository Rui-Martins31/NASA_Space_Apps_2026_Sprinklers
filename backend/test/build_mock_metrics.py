"""Build test/mock_data/chunk_metrics.csv.gz from test/mock_data/hotspots.csv.

Stands in for the pipeline: it writes the value of every metric per grid
chunk (and per day / month / nothing, depending on the metric), the way the
pipeline will store them in the database. The backend then keeps the chunks
inside the requested circle and combines them (see src/features.py).

The definitions follow spec/metricas_modis_viirs.csv loosely: the numbers
only have to look like what the pipeline will store. Columns and the time
scale of each metric are described in test/mock_data/README.md.

Run (after test/build_mock_chunks.py):  python test/build_mock_metrics.py
"""

import csv
import gzip
import io
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from src import config
from build_mock_chunks import cell_days, chunk_centre, is_eligible, read_hotspots, reference_years

COLUMNS = ["metric", "lat", "lon", "year", "month", "date", "key", "value", "low", "high"]
MIN_REFERENCE_YEARS = 5
MIN_COMPARABLE_MONTHS = 3
COMMON_PERIOD_START = date(2018, 1, 1)  # MODIS and VIIRS (NOAA-20) both observe from here
COARSE_GRID_DEG = 0.25                  # alternative grid for the grid sensitivity (HAR-13)
TYPE_LABELS = {0: "0 · vegetation", 1: "1 · volcano", 2: "2 · other static land source",
               3: "3 · offshore", None: "unknown"}


def row(metric, lat=None, lon=None, year=None, month=None, day=None, key=None,
        value=None, low=None, high=None):
    def text(x):
        if x is None:
            return ""
        return round(x, 4) if isinstance(x, float) else x
    if day is not None:
        year, month = day.year, day.month
    return dict(zip(COLUMNS, map(text, (metric, lat, lon, year, month,
                                        day.isoformat() if day else None, key, value, low, high))))


# --- Small statistics -----------------------------------------------------------

def percentile(values, p):
    """Linear-interpolation percentile (numpy's default)."""
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def theil_sen(xs, ys):
    slopes = [(ys[j] - ys[i]) / (xs[j] - xs[i])
              for i in range(len(xs)) for j in range(i + 1, len(xs))]
    return statistics.median(slopes)


def ranks(values):
    """Ranks starting at 1, ties get the mean rank."""
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            result[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return result


def pearson(xs, ys):
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:  # a constant series
        return None


# --- Metrics --------------------------------------------------------------------

def daily_rows(eligible):
    """CAL-02: one row per active cell-day (value 1)."""
    return [row("cal_02", lat, lon, day=day, value=1)
            for lat, lon, day in sorted(cell_days(eligible))]


def history_rows(eligible, ref_years):
    """HIS-01, HIS-02, HIS-05, HIS-06, HIS-10 per chunk, from its monthly cell-days."""
    monthly = defaultdict(Counter)  # chunk -> (year, month) -> cell-days
    for lat, lon, day in cell_days(eligible):
        monthly[(lat, lon)][(day.year, day.month)] += 1

    rows = []
    for (lat, lon), counts in sorted(monthly.items()):
        for month in range(1, 13):
            series = [counts[(y, month)] for y in ref_years]
            median = statistics.median(series)
            if median > 0:
                rows.append(row("his_01", lat, lon, month=month, value=float(median)))
            p10, p90 = percentile(series, 10), percentile(series, 90)
            if p90 > 0:
                rows.append(row("his_02", lat, lon, month=month, low=float(p10), high=float(p90)))

        for (year, month), count in sorted(counts.items()):
            reference = [counts[(y, month)] for y in ref_years if y != year]
            if len(reference) < MIN_REFERENCE_YEARS:
                continue
            std = statistics.stdev(reference)
            if std > 0:
                rows.append(row("his_05", lat, lon, year, month,
                                value=(count - statistics.mean(reference)) / std))
            below = sum(r < count for r in reference) + 0.5 * sum(r == count for r in reference)
            rows.append(row("his_06", lat, lon, year, month, value=100 * below / len(reference)))

        annual = [sum(counts[(y, m)] for m in range(1, 13)) for y in ref_years]
        if any(annual):
            rows.append(row("his_10", lat, lon, value=float(theil_sen(list(ref_years), annual))))
    return rows


def detection_rows(hotspots):
    """OBS-01..10 and QA-02..04 per chunk and month, from the raw detections."""
    groups = defaultdict(list)
    for h in hotspots:
        dt = h["date_time"]
        groups[(*chunk_centre(h["lat"], h["lon"]), dt.year, dt.month)].append(h)

    rows = []
    for (lat, lon, year, month), group in sorted(groups.items()):
        at = dict(lat=lat, lon=lon, year=year, month=month)
        eligible = [h for h in group if is_eligible(h)]

        for key, n in sorted(Counter(f"{h['instrument']} · {h['satellite']}" for h in group).items()):
            rows.append(row("obs_01", **at, key=key, value=n))
        for key, n in sorted(Counter(f"{h['instrument']} · {h['confidence_class']}" for h in group).items()):
            rows.append(row("obs_02", **at, key=key, value=n))
        if eligible:
            rows.append(row("obs_03", **at, value=len(eligible)))

        for instrument in sorted({h["instrument"] for h in group}):
            seen = [h for h in group if h["instrument"] == instrument]
            night = sum(h["daynight"] == "N" for h in seen)
            rows.append(row("obs_04", **at, key=instrument, value=100 * night / len(seen)))

        usable = [h for h in group if h["frp"] is not None and h["frp"] > 0]
        if usable:
            frps = [h["frp"] for h in usable]
            rows.append(row("obs_05", **at, value=statistics.median(frps)))
            rows.append(row("obs_06", **at, value=percentile(frps, 90)))
            peak = max(usable, key=lambda h: (h["frp"], h["date_time"]))
            rows.append(row("obs_07", lat, lon, day=peak["date_time"].date(), value=peak["frp"]))
        rows.append(row("obs_08", **at, value=100 * len(usable) / len(group)))

        for fire_type, n in sorted(Counter(h["type"] for h in group).items(), key=lambda kv: str(kv[0])):
            rows.append(row("obs_09", **at, key=TYPE_LABELS[fire_type], value=n))
        rows.append(row("obs_10", **at, value=statistics.median(h["pixel_area_km2"] for h in group)))

        rows.append(row("qa_02", **at, value=100 * len(eligible) / len(group)))
        grouped = len(eligible) - len({(h["date_time"].date(), h["satellite"]) for h in eligible})
        if grouped:
            rows.append(row("qa_03", **at, value=grouped))
        satellites = defaultdict(set)
        for h in eligible:
            satellites[(h["date_time"].date(), h["instrument"])].add(h["satellite"])
        redundant = sum(len(s) > 1 for s in satellites.values())
        if redundant:
            rows.append(row("qa_04", **at, value=redundant))
    return rows


def coverage_rows(hotspots):
    """QA-05: days with at least one detection anywhere (global, so no lat/lon)."""
    days = Counter()
    for day in {h["date_time"].date() for h in hotspots}:
        days[(day.year, day.month)] += 1
    return [row("qa_05", year=y, month=m, value=n) for (y, m), n in sorted(days.items())]


def harmonization_rows(hotspots, eligible):
    """HAR-01..11 per chunk over the common period (2018+), HAR-13/14 over the whole record."""
    last = max(h["date_time"] for h in hotspots).date()
    last_complete = date(last.year, last.month, 1)  # months from here on are partial

    def in_common_period(day):
        return COMMON_PERIOD_START <= day < last_complete

    days = {"MODIS": defaultdict(set), "VIIRS": defaultdict(set)}  # sensor -> chunk -> active days
    for instrument, chunks in days.items():
        for lat, lon, day in cell_days(h for h in eligible if h["instrument"] == instrument):
            if in_common_period(day):
                chunks[(lat, lon)].add(day)

    rows = []
    for (lat, lon) in sorted(set(days["MODIS"]) | set(days["VIIRS"])):
        modis, viirs = days["MODIS"][(lat, lon)], days["VIIRS"][(lat, lon)]
        months = sorted({(d.year, d.month) for d in modis | viirs})
        if len(months) < MIN_COMPARABLE_MONTHS:
            continue
        m_counts = Counter((d.year, d.month) for d in modis)
        v_counts = Counter((d.year, d.month) for d in viirs)
        m_series = [m_counts[k] for k in months]
        v_series = [v_counts[k] for k in months]
        at = dict(lat=lat, lon=lon)

        rows.append(row("har_01", **at, value=len(modis & viirs)))
        rows.append(row("har_02", **at, value=len(modis & viirs) / len(modis | viirs)))
        rows.append(row("har_03", **at, value=len(months)))
        r = pearson(m_series, v_series)
        if r is not None:
            rows.append(row("har_04", **at, value=r))
        rho = pearson(ranks(m_series), ranks(v_series))
        if rho is not None:
            rows.append(row("har_05", **at, value=rho))

        if not sum(m_series):
            continue
        factor = sum(v_series) / sum(m_series)
        years = sorted({y for y, _ in months})
        loo = []  # the factor without each year in turn
        for year in years:
            m_rest = sum(n for (y, _), n in m_counts.items() if y != year)
            v_rest = sum(n for (y, _), n in v_counts.items() if y != year)
            if m_rest:
                loo.append(v_rest / m_rest)
        low, high = (min(loo + [factor]), max(loo + [factor]))
        rows.append(row("har_06", **at, value=factor, low=low, high=high))
        rows.append(row("har_07", **at, value=factor, low=low, high=high))

        errors = [v - factor * m for m, v in zip(m_series, v_series)]
        mae = statistics.mean(abs(e) for e in errors)
        rows.append(row("har_08", **at, value=mae))
        if sum(v_series):
            rows.append(row("har_09", **at, value=100 * sum(abs(e) for e in errors) / sum(v_series)))
        rows.append(row("har_10", **at, value=-statistics.mean(errors)))
        mae_raw = statistics.mean(abs(v - m) for m, v in zip(m_series, v_series))
        if mae_raw:
            rows.append(row("har_11", **at, value=100 * (mae_raw - mae) / mae_raw))

    # HAR-13: cell-days on the 0.25° grid vs the chunk grid, per 0.25° cell.
    fine = Counter(chunk_centre(lat, lon, COARSE_GRID_DEG) for lat, lon, _ in cell_days(eligible))
    coarse = Counter(cd[:2] for cd in cell_days(eligible, COARSE_GRID_DEG))
    for lat, lon in sorted({cd[:2] for cd in cell_days(eligible)}):
        parent = chunk_centre(lat, lon, COARSE_GRID_DEG)
        rows.append(row("har_13", lat, lon, value=100 * (coarse[parent] / fine[parent] - 1)))

    # HAR-14: cell-days when low confidence is also accepted, vs the eligible ones.
    with_low = Counter(cd[:2] for cd in cell_days(
        h for h in hotspots if is_eligible(h, confidence=("low", "nominal", "high"))))
    strict = Counter(cd[:2] for cd in cell_days(eligible))
    for (lat, lon), n in sorted(strict.items()):
        rows.append(row("har_14", lat, lon, value=100 * (with_low[(lat, lon)] / n - 1)))
    return rows


def build(hotspots):
    eligible = [h for h in hotspots if is_eligible(h)]
    return (daily_rows(eligible)
            + history_rows(eligible, reference_years(hotspots))
            + detection_rows(hotspots)
            + coverage_rows(hotspots)
            + harmonization_rows(hotspots, eligible))


def main():
    directory = config.MOCK_DATA_DIR
    hotspots = read_hotspots(directory / config.MOCK_HOTSPOTS_FILE)
    rows = build(hotspots)
    # mtime=0 so the same rows always give the same file (no spurious git diffs).
    with open(directory / config.MOCK_CHUNK_METRICS_FILE, "wb") as raw, \
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as packed, \
            io.TextIOWrapper(packed, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    per_metric = Counter(r["metric"] for r in rows)
    print(f"{len(hotspots)} hotspots -> {len(rows)} chunk metric rows "
          f"({', '.join(f'{m}: {n}' for m, n in sorted(per_metric.items()))})")


if __name__ == "__main__":
    main()

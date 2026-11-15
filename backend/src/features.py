"""The API features: one function per endpoint (see spec/api/frontend-backend.md).

The pipeline stores its numbers per grid chunk, never per circle. So every
feature:
  1. asks the database for the rows inside the lat/lon box around the circle;
  2. drops the rows in the corners of the box, outside the circle;
  3. adds up what is left (counts and means are both sums over chunks).

A chunk belongs to the circle when its centre is inside it. Chunk data is
monthly, so a period that starts or ends mid-month includes that whole month.
"""

import calendar as month_calendar
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import islice

from . import config
from .circle_geometry import chunks_in_circle, in_circle, query_box


def calendar(database, query):
    """Count for every month of the period (months with no activity are 0)."""
    months = list(_months_in_period(query))
    totals = dict.fromkeys(months, 0)
    for row in _circle_chunk_counts(database, query):
        totals[(row["year"], row["month"])] += row["count"]
    return [{"year": y, "month": m, "count": totals[(y, m)]} for y, m in months]


def anomalies(database, query, calendar_rows=None):
    """Each month of the calendar next to the circle's reference mean for that month."""
    rows = calendar_rows if calendar_rows is not None else calendar(database, query)
    means = _circle_means(database, query)
    return [
        {**r, "mean": round(means[r["month"]], 2),
         "anomaly": "above" if r["count"] > means[r["month"]] else "normal"}
        for r in rows
    ]


def hotspots(database, query, limit=None):
    """Hotspots inside the circle, in the database's order; limit=None means all of them."""
    rows = database.hotspots(query_box(query), query["date_time_from"], query["date_time_to"])
    inside = (h for h in rows if in_circle(query, h["lat"], h["lon"]))
    return islice(inside, limit)


def _circle_chunk_counts(database, query):
    """chunk_counts rows of the period whose chunk is inside the circle."""
    months = list(_months_in_period(query))
    rows = database.chunk_counts(query_box(query), months[0], months[-1])
    return [r for r in rows if in_circle(query, r["lat"], r["lon"])]


def _circle_means(database, query):
    """The circle's reference mean for each calendar month: {1: ..., 12: ...}."""
    means = dict.fromkeys(range(1, 13), 0.0)
    for row in database.chunk_means(query_box(query)):
        if in_circle(query, row["lat"], row["lon"]):
            means[row["month"]] += row["mean"]
    return means


def _months_in_period(query):
    """Every (year, month) from date_time_from to date_time_to."""
    start, end = query["date_time_from"], query["date_time_to"]
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


# =============================================================================
# Metrics: one feature per metric of spec/metricas_modis_viirs.csv
# ("Features - Metrics" in spec/api/frontend-backend.md). The ones the API
# serves are listed in config.METRICS.
#
# Every function returns {"value": ...} and, when useful, a "note".
# The value is None (null) when there is nothing to compute; the note says why.
#
# Where the values come from:
#   - CAL, HIS-03/04/07/08/09 and ESP: from chunk_counts / chunk_means, the same
#     rows as calendar() and anomalies(), so the numbers always agree with them;
#   - the rest: the pipeline's value per chunk, from chunk_metrics. The chunks
#     inside the circle are combined: counts (and count-like statistics, such
#     as a median of cell-days) are summed; ratios, percentages, correlations
#     and factors are averaged over the chunks. The average is an approximation
#     of the circle's value: the database stores them per chunk, never per circle.
#
# Shapes by time scale:
#   per month           [{"year", "month", "value"}] for every month of the period
#   per day             [{"date", "value"}] for every day of the period
#   per year            [{"year", "value"}] for every year of the period
#   per calendar month  12 values, January to December
#   by category         [{"key", "value"}]
# =============================================================================


# --- CAL: calendar and summary --------------------------------------------------

def cal_01(database, query):
    """Cell-days with detections in the period."""
    return {"value": _total(calendar(database, query))}


def cal_02(database, query):
    """Daily activity: cell-days on each day of the period."""
    per_day = _daily_totals(database, query)
    return {"value": [{"date": d.isoformat(), "value": per_day.get(d, 0)} for d in _days_in_period(query)]}


def cal_03(database, query):
    """Monthly activity: cell-days in each month of the period."""
    return {"value": [{"year": r["year"], "month": r["month"], "value": r["count"]}
                      for r in calendar(database, query)]}


def cal_04(database, query):
    """Annual activity: cell-days in each year of the period."""
    per_year = _yearly_totals(calendar(database, query))
    return {"value": [{"year": y, "value": n} for y, n in per_year.items()]}


def cal_05(database, query):
    """Total activity in the period."""
    return {"value": _total(calendar(database, query))}


def cal_06(database, query):
    """Peak month: the month of the period with the most cell-days (earliest on a tie)."""
    peak = max(calendar(database, query), key=lambda r: r["count"])
    if peak["count"] == 0:
        return {"value": None, "note": config.NOTE_NO_ACTIVITY}
    return {"value": {"year": peak["year"], "month": peak["month"], "count": peak["count"]}}


def cal_07(database, query):
    """Peak year: the complete year of the period with the most cell-days."""
    per_year, note = _complete_year_totals(database, query)
    if not per_year:
        return {"value": None, "note": note}
    year = max(per_year, key=per_year.get)
    return {"value": {"year": year, "count": per_year[year]}, "note": note}


def cal_08(database, query):
    """Mean annual activity over the complete years of the period."""
    per_year, note = _complete_year_totals(database, query)
    if not per_year:
        return {"value": None, "note": note}
    return {"value": _round(statistics.fmean(per_year.values())), "note": note}


def cal_09(database, query):
    """Historical mean of the same calendar month, for each month of the period."""
    return {"value": [{"year": r["year"], "month": r["month"], "value": r["mean"]}
                      for r in anomalies(database, query)]}


def cal_10(database, query):
    """Days with at least one detection in the circle."""
    return {"value": len(_daily_totals(database, query))}


def cal_11(database, query):
    """The day of the period with the most cell-days."""
    per_day = _daily_totals(database, query)
    if not per_day:
        return {"value": None, "note": config.NOTE_NO_ACTIVITY}
    day = min(per_day, key=lambda d: (-per_day[d], d))  # earliest on a tie
    return {"value": {"date": day.isoformat(), "count": per_day[day]}}


def cal_12(database, query):
    """Seasonal profile: the reference mean of each calendar month, January to December."""
    means = _circle_means(database, query)
    return {"value": [_round(means[m]) for m in range(1, 13)]}


# --- HIS: history ---------------------------------------------------------------

def his_01(database, query):
    """Historical median of each calendar month, January to December."""
    return {"value": _per_calendar_month(_metric_rows(database, query, "his_01"), "value")}


def his_02(database, query):
    """Historical band (p10-p90) of each calendar month, January to December."""
    rows = _metric_rows(database, query, "his_02")
    lows, highs = _per_calendar_month(rows, "low"), _per_calendar_month(rows, "high")
    return {"value": [{"low": lo, "high": hi} for lo, hi in zip(lows, highs)]}


def his_03(database, query):
    """Monthly anomaly: cell-days minus the reference mean of that month."""
    return {"value": [{"year": r["year"], "month": r["month"], "value": _round(r["count"] - r["mean"])}
                      for r in anomalies(database, query)]}


def his_04(database, query):
    """Monthly anomaly in % of the reference mean (null when the mean is 0)."""
    return {"value": [{"year": r["year"], "month": r["month"],
                       "value": _percent(r["count"] - r["mean"], r["mean"])}
                      for r in anomalies(database, query)]}


def his_05(database, query):
    """Monthly z-score against the reference years (average over the chunks)."""
    return _per_month_mean(database, query, "his_05")


def his_06(database, query):
    """Historical percentile of each month's activity (average over the chunks)."""
    return _per_month_mean(database, query, "his_06")


def his_07(database, query):
    """Cell-days from 1 January up to the end of each month (year to date)."""
    from_january = {**query, "date_time_from": datetime(query["date_time_from"].year, 1, 1)}
    in_period = set(_months_in_period(query))
    running, result = 0, []
    for r in calendar(database, from_january):
        running = r["count"] if r["month"] == 1 else running + r["count"]
        if (r["year"], r["month"]) in in_period:
            result.append({"year": r["year"], "month": r["month"], "value": running})
    return {"value": result}


def his_08(database, query):
    """Change from the same month one year before, in % (null when that month had 0)."""
    start = query["date_time_from"]
    year_before = {**query, "date_time_from": datetime(start.year - 1, start.month, 1)}
    counts = {(r["year"], r["month"]): r["count"] for r in calendar(database, year_before)}
    return {"value": [{"year": y, "month": m,
                       "value": _percent(counts[(y, m)] - counts[(y - 1, m)], counts[(y - 1, m)])}
                      for y, m in _months_in_period(query)]}


def his_09(database, query):
    """For each year, the months of the period above the historical band (p90)."""
    bands = _per_calendar_month(_metric_rows(database, query, "his_02"), "high")
    above = defaultdict(int)
    for r in calendar(database, query):
        above[r["year"]] += r["count"] > bands[r["month"] - 1]
    return {"value": [{"year": y, "value": n} for y, n in above.items()]}


def his_10(database, query):
    """Trend of the annual totals (cell-days per year)."""
    rows = _metric_rows(database, query, "his_10")
    if not rows:
        return {"value": None, "note": config.NOTE_NO_DATA}
    return {"value": _sum(rows)}


# --- ESP: space -----------------------------------------------------------------

def esp_01(database, query):
    """Cell-days per 1 000 km² of the circle."""
    area_km2 = math.pi * query["radius"] ** 2
    return {"value": _round(_total(calendar(database, query)) / area_km2 * 1000)}


def esp_02(database, query):
    """Distinct chunks with at least one detection in the period."""
    return {"value": len(_active_chunks(database, query))}


def esp_03(database, query):
    """Mean cell-days per active chunk."""
    chunks = _active_chunks(database, query)
    if not chunks:
        return {"value": None, "note": config.NOTE_NO_ACTIVITY}
    return {"value": _round(sum(c["cell_days"] for c in chunks.values()) / len(chunks))}


def esp_04(database, query):
    """Share of the circle's chunks with at least one detection, in %."""
    total = chunks_in_circle(query)
    if total == 0:
        return {"value": None, "note": config.NOTE_TINY_CIRCLE}
    return {"value": _percent(len(_active_chunks(database, query)), total)}


def esp_06(database, query):
    """Mean number of years with detections per active chunk."""
    chunks = _active_chunks(database, query)
    if not chunks:
        return {"value": None, "note": config.NOTE_NO_ACTIVITY}
    return {"value": _round(statistics.fmean(len(c["years"]) for c in chunks.values()))}


# --- OBS: detections ------------------------------------------------------------

def obs_01(database, query):
    """Raw detections by instrument and satellite."""
    return {"value": _by_key(_metric_rows(database, query, "obs_01"), _sum)}


def obs_02(database, query):
    """Raw detections by instrument and confidence class."""
    return {"value": _by_key(_metric_rows(database, query, "obs_02"), _sum)}


def obs_03(database, query):
    """Detections left after the quality filter."""
    return {"value": _sum(_metric_rows(database, query, "obs_03"))}


def obs_04(database, query):
    """Night detections in %, by instrument (average over the chunks)."""
    rows = _metric_rows(database, query, "obs_04")
    if not rows:
        return {"value": None, "note": config.NOTE_NO_DATA}
    return {"value": _by_key(rows, _mean), "note": _chunks_note(rows)}


def obs_05(database, query):
    """Median FRP, MW (average over the chunks)."""
    return _period_mean(database, query, "obs_05")


def obs_06(database, query):
    """90th percentile of FRP, MW (average over the chunks)."""
    return _period_mean(database, query, "obs_06")


def obs_07(database, query):
    """The highest FRP in the period and the day it was seen."""
    rows = _metric_rows(database, query, "obs_07")
    if not rows:
        return {"value": None, "note": config.NOTE_NO_DATA}
    peak = min(rows, key=lambda r: (-r["value"], r["date"]))  # earliest on a tie
    return {"value": {"date": peak["date"].isoformat(), "count": _number(peak["value"])},
            "note": config.NOTE_LOCATION.format(lat=peak["lat"], lon=peak["lon"])}


def obs_08(database, query):
    """Detections with a usable FRP, in % (average over the chunks)."""
    return _period_mean(database, query, "obs_08")


def obs_09(database, query):
    """Detections by thermal source type."""
    return {"value": _by_key(_metric_rows(database, query, "obs_09"), _sum)}


def obs_10(database, query):
    """Median pixel area of the detections, km² (average over the chunks)."""
    return _period_mean(database, query, "obs_10")


# --- QA: quality ----------------------------------------------------------------

def qa_02(database, query):
    """Detections kept by the quality filter, in % (average over the chunks)."""
    return _period_mean(database, query, "qa_02")


def qa_03(database, query):
    """Detections merged into a cell-day of the same satellite."""
    return {"value": _sum(_metric_rows(database, query, "qa_03"))}


def qa_04(database, query):
    """Cell-days seen by more than one satellite of the same sensor."""
    return {"value": _sum(_metric_rows(database, query, "qa_04"))}


def qa_05(database, query):
    """Days of the period with confirmed coverage (global: at least one detection anywhere)."""
    days = _sum(_metric_rows(database, query, "qa_05"))
    total = sum(month_calendar.monthrange(y, m)[1] for y, m in _months_in_period(query))
    return {"value": days, "note": config.NOTE_COVERAGE.format(percent=_percent(days, total), days=total)}


# --- HAR: MODIS / VIIRS harmonization ---------------------------------------------
# Computed by the pipeline over the common period of the two sensors, so they
# do not depend on the selected dates.

def har_01(database, query):
    """Cell-days seen by both MODIS and VIIRS."""
    return _whole_record(database, query, "har_01", _sum)


def har_02(database, query):
    """Jaccard overlap of the MODIS and VIIRS cell-days (average over the chunks)."""
    return _whole_record(database, query, "har_02", _mean)


def har_03(database, query):
    """Comparable months used in the validation (the most of any chunk)."""
    return _whole_record(database, query, "har_03", lambda rows: _number(max(r["value"] for r in rows)))


def har_04(database, query):
    """Pearson correlation of the monthly MODIS and VIIRS series (average over the chunks)."""
    return _whole_record(database, query, "har_04", _mean)


def har_05(database, query):
    """Spearman correlation of the monthly MODIS and VIIRS series (average over the chunks)."""
    return _whole_record(database, query, "har_05", _mean)


def har_06(database, query):
    """MODIS to VIIRS adjustment factor with its uncertainty range (average over the chunks)."""
    return _whole_record(database, query, "har_06", _mean_range)


def har_07(database, query):
    """Uncertainty range of the adjustment factor (average over the chunks)."""
    return _whole_record(database, query, "har_07", _mean_range)


def har_08(database, query):
    """Mean absolute monthly error of the adjusted MODIS series (MAE)."""
    return _whole_record(database, query, "har_08", _sum)


def har_09(database, query):
    """Weighted absolute percentage error of the adjusted series (WAPE, average over the chunks)."""
    return _whole_record(database, query, "har_09", _mean)


def har_10(database, query):
    """Mean monthly bias of the adjusted MODIS series."""
    return _whole_record(database, query, "har_10", _sum)


def har_11(database, query):
    """Error reduction after the adjustment, in % (average over the chunks)."""
    return _whole_record(database, query, "har_11", _mean)


def har_13(database, query):
    """Change in cell-days with a 0.25° grid instead of the chunk grid, in % (average over the chunks)."""
    return _whole_record(database, query, "har_13", _mean, config.NOTE_WHOLE_RECORD)


def har_14(database, query):
    """Change in cell-days when low confidence is also accepted, in % (average over the chunks)."""
    return _whole_record(database, query, "har_14", _mean, config.NOTE_WHOLE_RECORD)


# --- Helpers for the metrics -----------------------------------------------------

def _metric_rows(database, query, metric_id):
    """chunk_metrics rows of one metric in the period, trimmed to the circle (global rows kept)."""
    rows = database.chunk_metrics(metric_id, query_box(query), query["date_time_from"], query["date_time_to"])
    return [r for r in rows if r["lat"] is None or in_circle(query, r["lat"], r["lon"])]


def _period_mean(database, query, metric_id):
    rows = _metric_rows(database, query, metric_id)
    if not rows:
        return {"value": None, "note": config.NOTE_NO_DATA}
    return {"value": _mean(rows), "note": _chunks_note(rows)}


def _per_month_mean(database, query, metric_id):
    by_month = defaultdict(list)
    for r in _metric_rows(database, query, metric_id):
        by_month[(r["year"], r["month"])].append(r)
    return {"value": [{"year": y, "month": m, "value": _mean(by_month[(y, m)])}
                      for y, m in _months_in_period(query)]}


def _whole_record(database, query, metric_id, combine, note=config.NOTE_COMMON_PERIOD):
    rows = _metric_rows(database, query, metric_id)
    if not rows:
        return {"value": None, "note": config.NOTE_NO_DATA}
    return {"value": combine(rows), "note": note}


def _by_key(rows, combine):
    groups = defaultdict(list)
    for r in rows:
        groups[r["key"]].append(r)
    return [{"key": key, "value": combine(groups[key])} for key in sorted(groups)]


def _per_calendar_month(rows, field):
    """Sum of `field` for each calendar month, January to December."""
    totals = [0.0] * 12
    for r in rows:
        totals[r["month"] - 1] += r[field]
    return [_number(t) for t in totals]


def _daily_totals(database, query):
    """{date: cell-days} for the days of the period with activity."""
    totals = defaultdict(float)
    for r in _metric_rows(database, query, "cal_02"):
        totals[r["date"]] += r["value"]
    return {d: _number(n) for d, n in totals.items()}


def _yearly_totals(calendar_rows):
    totals = {}
    for r in calendar_rows:
        totals[r["year"]] = totals.get(r["year"], 0) + r["count"]
    return totals


def _complete_year_totals(database, query):
    """({year: cell-days} for the complete years of the period, note naming them)."""
    first, last = database.data_range()
    start = max(first, query["date_time_from"]).date()
    end = min(last, query["date_time_to"]).date()
    complete = [y for y in range(start.year, end.year + 1)
                if start <= date(y, 1, 1) and date(y, 12, 31) <= end]
    if not complete:
        return {}, config.NOTE_NO_COMPLETE_YEAR
    per_year = _yearly_totals(calendar(database, query))
    note = config.NOTE_COMPLETE_YEARS.format(n=len(complete), first=complete[0], last=complete[-1])
    return {y: per_year[y] for y in complete}, note


def _active_chunks(database, query):
    """{(lat, lon): {"cell_days", "years"}} for the chunks with activity in the period."""
    chunks = {}
    for r in _circle_chunk_counts(database, query):
        if r["count"] > 0:
            chunk = chunks.setdefault((r["lat"], r["lon"]), {"cell_days": 0, "years": set()})
            chunk["cell_days"] += r["count"]
            chunk["years"].add(r["year"])
    return chunks


def _days_in_period(query):
    day, last = query["date_time_from"].date(), query["date_time_to"].date()
    while day <= last:
        yield day
        day += timedelta(days=1)


def _chunks_note(rows):
    return config.NOTE_AVERAGE_OVER_CHUNKS.format(n=len({(r["lat"], r["lon"]) for r in rows}))


def _total(calendar_rows):
    return sum(r["count"] for r in calendar_rows)


def _sum(rows):
    return _number(sum(r["value"] for r in rows))


def _mean(rows):
    values = [r["value"] for r in rows if r["value"] is not None]
    return _round(statistics.fmean(values)) if values else None


def _mean_range(rows):
    return {field: _round(statistics.fmean(r[field] for r in rows)) for field in ("value", "low", "high")}


def _percent(part, whole):
    return _round(100 * part / whole) if whole else None


def _round(x):
    return round(x, config.METRIC_DECIMALS)


def _number(x):
    """Whole numbers as int (3, not 3.0), the rest rounded."""
    return int(x) if float(x).is_integer() else _round(x)

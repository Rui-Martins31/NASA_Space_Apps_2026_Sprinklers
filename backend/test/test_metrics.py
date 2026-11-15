"""Metric features on the small hand-made database of test_api.py, plus chunk_metrics rows.

Every expected value is worked out by hand from the rows below.
Run from backend/:  python -m unittest discover test
"""

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # import backend modules

from main import create_app
from src import config, features
from src.database.mock_database import MockDatabase
from test_api import CHUNK_COUNTS, CHUNK_MEANS, HOTSPOTS, LISBON

# Chunks of test_api.py: two inside the 50 km circle around Lisbon, one in the
# corner of its box (outside the circle).
LISBON_CHUNK = (38.75, -9.15)
NEAR_CHUNK = (38.65, -9.05)
CORNER_CHUNK = (39.10, -8.60)


def m(metric, chunk=(None, None), year=None, month=None, day=None, key=None, value=None, low=None, high=None):
    """One chunk_metrics row, as the database returns it."""
    if day is not None:
        year, month = day.year, day.month
    return {"metric": metric, "lat": chunk[0], "lon": chunk[1], "year": year, "month": month,
            "date": day, "key": key, "value": value, "low": low, "high": high}


CHUNK_METRICS = [
    m("cal_02", LISBON_CHUNK, day=date(2020, 8, 10), value=1),
    m("cal_02", NEAR_CHUNK, day=date(2020, 8, 10), value=1),
    m("cal_02", LISBON_CHUNK, day=date(2020, 8, 11), value=1),
    m("cal_02", CORNER_CHUNK, day=date(2020, 8, 12), value=1),   # outside the circle
    m("cal_02", LISBON_CHUNK, day=date(2019, 8, 1), value=1),    # before the period

    m("his_01", LISBON_CHUNK, month=8, value=1.0),
    m("his_01", NEAR_CHUNK, month=8, value=0.5),
    m("his_01", CORNER_CHUNK, month=8, value=4.0),
    m("his_02", LISBON_CHUNK, month=8, low=0.0, high=1.0),
    m("his_02", NEAR_CHUNK, month=8, low=0.5, high=1.0),
    m("his_05", LISBON_CHUNK, 2020, 8, value=2.0),
    m("his_05", NEAR_CHUNK, 2020, 8, value=1.0),
    m("his_05", CORNER_CHUNK, 2020, 8, value=9.0),

    m("obs_01", LISBON_CHUNK, 2020, 8, key="MODIS · Terra", value=2),
    m("obs_01", NEAR_CHUNK, 2020, 8, key="MODIS · Terra", value=1),
    m("obs_01", LISBON_CHUNK, 2021, 8, key="VIIRS · N20", value=4),
    m("obs_01", CORNER_CHUNK, 2020, 8, key="MODIS · Aqua", value=10),
    m("obs_05", LISBON_CHUNK, 2020, 8, value=10.0),
    m("obs_05", NEAR_CHUNK, 2021, 8, value=20.0),
    m("obs_05", CORNER_CHUNK, 2020, 8, value=100.0),
    m("obs_07", LISBON_CHUNK, day=date(2020, 8, 10), value=50.0),
    m("obs_07", NEAR_CHUNK, day=date(2021, 8, 5), value=50.0),     # same FRP, later day
    m("obs_07", CORNER_CHUNK, day=date(2020, 8, 12), value=999.0),

    m("qa_05", year=2020, month=8, value=31),                      # global: no lat/lon
    m("qa_05", year=2019, month=12, value=31),                     # before the period

    m("har_06", LISBON_CHUNK, value=2.0, low=1.0, high=3.0),
    m("har_06", NEAR_CHUNK, value=1.0, low=0.5, high=1.5),
    m("har_06", CORNER_CHUNK, value=9.0, low=9.0, high=9.0),
]

# The data covers 2019-2021, so 2020 and 2021 are the complete years of LISBON's period.
RECORD = (datetime(2019, 1, 1), datetime(2021, 12, 31, 23, 59))


def monthly(values):
    """{(year, month): value} of a per-month answer."""
    return {(r["year"], r["month"]): r["value"] for r in values}


class MetricTest(unittest.TestCase):
    def setUp(self):
        database = MockDatabase(CHUNK_COUNTS, CHUNK_MEANS, HOTSPOTS, CHUNK_METRICS, record=RECORD)
        self.client = create_app(database).test_client()

    def post(self, feature, **overrides):
        response = self.client.post(f"/api/{feature}", json={**LISBON, "feature": feature, **overrides})
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["feature"], feature)
        return body

    # --- Routing ---

    def test_every_metric_has_a_function_and_an_endpoint(self):
        for name in config.METRICS:
            with self.subTest(metric=name):
                self.assertTrue(callable(getattr(features, name)))
                self.assertIn("value", self.post(name))

    def test_metric_not_available_yet(self):
        for name in config.METRICS_NOT_AVAILABLE:
            response = self.client.post(f"/api/{name}", json={**LISBON, "feature": name})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json(), {"error": f"metric {name} is not available yet"})

    def test_metric_ids_use_underscores(self):
        self.assertEqual(self.client.post("/api/cal-05", json={**LISBON, "feature": "cal-05"}).status_code, 404)

    def test_metric_validates_the_request(self):
        for body in ({**LISBON, "feature": "cal_01"}, {**LISBON, "feature": "cal_05", "radius": 0}):
            response = self.client.post("/api/cal_05", json=body)
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.get_json())
        self.assertEqual(self.client.get("/api/cal_05").status_code, 405)

    # --- CAL: from chunk_counts (Aug 2020: 2 + 1, Aug 2021: 1) and cal_02 ---

    def test_period_totals(self):
        self.assertEqual(self.post("cal_01")["value"], 4)
        self.assertEqual(self.post("cal_05")["value"], 4)

    def test_cal_02_every_day_of_the_period(self):
        days = self.post("cal_02")["value"]
        self.assertEqual(len(days), 366 + 365)  # 2020 is a leap year
        per_day = {d["date"]: d["value"] for d in days}
        self.assertEqual(per_day["2020-08-10"], 2)
        self.assertEqual(per_day["2020-08-11"], 1)
        self.assertEqual(per_day["2020-08-12"], 0)  # the corner chunk is outside the circle

    def test_cal_03_and_cal_04(self):
        months = monthly(self.post("cal_03")["value"])
        self.assertEqual(len(months), 24)
        self.assertEqual(months[(2020, 8)], 3)
        self.assertEqual(self.post("cal_04")["value"], [{"year": 2020, "value": 3}, {"year": 2021, "value": 1}])

    def test_peaks(self):
        self.assertEqual(self.post("cal_06")["value"], {"year": 2020, "month": 8, "count": 3})
        self.assertEqual(self.post("cal_07"), {"feature": "cal_07", "value": {"year": 2020, "count": 3},
                                               "note": "complete years: 2 (2020–2021)"})
        self.assertEqual(self.post("cal_11")["value"], {"date": "2020-08-10", "count": 2})

    def test_cal_08_mean_of_the_complete_years(self):
        self.assertEqual(self.post("cal_08")["value"], 2.0)  # (3 + 1) / 2
        # The record starts in 2019, so a period starting mid-2020 has only 2021 complete.
        body = self.post("cal_08", date_time_from="2020-06-01T00:00:00")
        self.assertEqual(body, {"feature": "cal_08", "value": 1.0, "note": "complete years: 1 (2021–2021)"})

    def test_no_complete_year(self):
        body = self.post("cal_07", date_time_to="2020-12-30T00:00:00")
        self.assertEqual(body, {"feature": "cal_07", "value": None, "note": config.NOTE_NO_COMPLETE_YEAR})

    def test_no_activity(self):
        quiet = {"date_time_from": "2020-01-01T00:00:00", "date_time_to": "2020-03-31T23:59:59"}
        self.assertEqual(self.post("cal_06", **quiet)["value"], None)
        self.assertEqual(self.post("cal_11", **quiet)["note"], config.NOTE_NO_ACTIVITY)

    def test_cal_09_and_cal_12_reference_means(self):
        self.assertEqual(monthly(self.post("cal_09")["value"])[(2021, 8)], 1.5)  # 1.0 + 0.5
        self.assertEqual(self.post("cal_12")["value"], [0, 0, 0, 0, 0, 0, 0, 1.5, 0, 0, 0, 0])

    def test_cal_10_days_with_detections(self):
        self.assertEqual(self.post("cal_10")["value"], 2)  # 10 and 11 August 2020

    # --- HIS ---

    def test_his_01_and_his_02_sum_the_chunks(self):
        self.assertEqual(self.post("his_01")["value"][7], 1.5)  # August; the corner (4.0) is outside
        band = self.post("his_02")["value"]
        self.assertEqual(len(band), 12)
        self.assertEqual(band[7], {"low": 0.5, "high": 2})
        self.assertEqual(band[0], {"low": 0, "high": 0})

    def test_his_03_and_his_04_anomalies(self):
        absolute = monthly(self.post("his_03")["value"])
        self.assertEqual(absolute[(2020, 8)], 1.5)    # 3 - 1.5
        self.assertEqual(absolute[(2021, 8)], -0.5)   # 1 - 1.5
        percent = monthly(self.post("his_04")["value"])
        self.assertEqual(percent[(2020, 8)], 100.0)
        self.assertIsNone(percent[(2020, 1)])         # reference mean 0

    def test_his_05_averages_the_chunks_of_each_month(self):
        values = monthly(self.post("his_05")["value"])
        self.assertEqual(values[(2020, 8)], 1.5)      # (2.0 + 1.0) / 2; the corner (9.0) is outside
        self.assertIsNone(values[(2020, 1)])

    def test_his_07_year_to_date(self):
        values = monthly(self.post("his_07", date_time_from="2020-09-01T00:00:00")["value"])
        self.assertEqual(values[(2020, 9)], 3)        # counts from January, before the period starts
        self.assertEqual(values[(2021, 7)], 0)        # starts again in January
        self.assertEqual(values[(2021, 8)], 1)

    def test_his_08_change_from_a_year_before(self):
        values = monthly(self.post("his_08")["value"])
        self.assertEqual(values[(2020, 8)], -66.67)   # 3 vs 9 in Aug 2019, before the period
        self.assertEqual(values[(2021, 8)], -66.67)   # 1 vs 3
        self.assertIsNone(values[(2020, 1)])          # 0 the year before

    def test_his_09_months_above_the_band(self):
        # August band high = 2: Aug 2020 (3) is above, Aug 2021 (1) is not.
        self.assertEqual(self.post("his_09")["value"], [{"year": 2020, "value": 1}, {"year": 2021, "value": 0}])

    # --- ESP: active chunks Lisbon (2020: 2, 2021: 1) and near (2020: 1) ---

    def test_space(self):
        self.assertEqual(self.post("esp_01")["value"], 0.51)  # 4 / (π · 50²) · 1000
        self.assertEqual(self.post("esp_02")["value"], 2)
        self.assertEqual(self.post("esp_03")["value"], 2.0)   # 4 cell-days / 2 chunks
        self.assertEqual(self.post("esp_06")["value"], 1.5)   # 2 years and 1 year

    def test_esp_04_share_of_the_circle(self):
        n_chunks = features.chunks_in_circle({"lat": LISBON["lat"], "lon": LISBON["lon"], "radius": LISBON["radius"]})
        self.assertEqual(self.post("esp_04")["value"], round(100 * 2 / n_chunks, 2))

    # --- OBS / QA / HAR: chunk_metrics combined over the chunks in the circle ---

    def test_obs_01_sums_each_key(self):
        self.assertEqual(self.post("obs_01")["value"], [{"key": "MODIS · Terra", "value": 3},
                                                        {"key": "VIIRS · N20", "value": 4}])

    def test_obs_05_averages_the_chunks(self):
        self.assertEqual(self.post("obs_05"), {"feature": "obs_05", "value": 15.0,
                                               "note": "average over 2 grid chunk(s)"})

    def test_obs_07_peak_earliest_on_a_tie(self):
        self.assertEqual(self.post("obs_07"), {"feature": "obs_07", "value": {"date": "2020-08-10", "count": 50},
                                               "note": "at 38.75, -9.15"})

    def test_qa_05_global_rows(self):
        self.assertEqual(self.post("qa_05"), {"feature": "qa_05", "value": 31,
                                              "note": "4.24% of the 731 days of the months in the period"})

    def test_har_06_averages_the_range(self):
        self.assertEqual(self.post("har_06"), {"feature": "har_06",
                                               "value": {"value": 1.5, "low": 0.75, "high": 2.25},
                                               "note": config.NOTE_COMMON_PERIOD})

    def test_no_data_in_the_circle(self):
        self.assertEqual(self.post("obs_05", lat=0.0, lon=0.0), {"feature": "obs_05", "value": None,
                                                                 "note": config.NOTE_NO_DATA})
        self.assertEqual(self.post("har_06", lat=0.0, lon=0.0)["value"], None)


if __name__ == "__main__":
    unittest.main()

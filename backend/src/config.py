"""Every setting and constant of the backend, in one place."""

import math
import os
from pathlib import Path

# --- Server -------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8080

# --- Data ---------------------------------------------------------------------
# "mock" = the CSV files in MOCK_DATA_DIR, "database" = the pipeline's database.
# Chosen with `python main.py --data ...` or the BACKEND_DATA environment variable.
DATA_OPTIONS  = ("mock", "database")
DATA          = os.environ.get("BACKEND_DATA", "mock")
MOCK_DATA_DIR = Path(__file__).parent.parent / "test" / "mock_data"

# Mock CSV files: one file per database table.
MOCK_HOTSPOTS_FILE     = "hotspots.csv"
MOCK_CHUNK_COUNTS_FILE = "chunk_counts.csv"
MOCK_CHUNK_MEANS_FILE   = "chunk_means.csv"
MOCK_CHUNK_METRICS_FILE = "chunk_metrics.csv.gz"  # gzipped: ~20 MB as plain CSV

# Side of a grid chunk, in degrees (the pipeline stores its metrics per chunk).
CHUNK_SIZE_DEG = 0.01

# --- Requests -----------------------------------------------------------------
MAX_RADIUS_KM      = 1000
DEFAULT_MAX_POINTS = 1000
MAX_POINTS_LIMIT   = 50_000

FEATURES = [
    "all",
    "hotspots",
    "calendar",
    "anomalies"
]
CONFIDENCE_CLASSES = [
    "low",
    "nominal",
    "high"
]

# --- Metrics ------------------------------------------------------------------
# One feature per metric of spec/metricas_modis_viirs.csv, named after its id
# ("CAL-05" -> "cal_05"). The same name is the endpoint (POST /api/cal_05), the
# "feature" of the request, the function in features.py and the "metric" of
# the chunk_metrics rows in the database.
METRICS = [
    "cal_01", "cal_02", "cal_03", "cal_04", "cal_05", "cal_06",
    "cal_07", "cal_08", "cal_09", "cal_10", "cal_11", "cal_12",
    "his_01", "his_02", "his_03", "his_04", "his_05",
    "his_06", "his_07", "his_08", "his_09", "his_10",
    "esp_01", "esp_02", "esp_03", "esp_04", "esp_06",
    "obs_01", "obs_02", "obs_03", "obs_04", "obs_05",
    "obs_06", "obs_07", "obs_08", "obs_09", "obs_10",
    "qa_02", "qa_03", "qa_04", "qa_05",
    "har_01", "har_02", "har_03", "har_04", "har_05", "har_06", "har_07",
    "har_08", "har_09", "har_10", "har_11", "har_13", "har_14",
]
# Metrics of the CSV not served yet: they answer 404 "not available yet".
METRICS_NOT_AVAILABLE = ["qa_01", "qa_06", "qa_07", "har_12", "esp_05"]

METRIC_DECIMALS = 2  # decimals of averaged / non-integer metric values

# Notes sent with a metric value (shown under it in the app).
NOTE_NO_DATA       = "no data for this area and period"
NOTE_NO_ACTIVITY   = "no activity in the period"
NOTE_COMMON_PERIOD = "MODIS vs VIIRS over their common period (2018 onwards), not the selected dates"
NOTE_WHOLE_RECORD  = "over the whole record, not the selected dates"
NOTE_TINY_CIRCLE   = "the circle is smaller than one grid chunk"
NOTE_NO_COMPLETE_YEAR    = "no complete year in the period"
NOTE_COMPLETE_YEARS      = "complete years: {n} ({first}–{last})"
NOTE_AVERAGE_OVER_CHUNKS = "average over {n} grid chunk(s)"
NOTE_COVERAGE            = "{percent}% of the {days} days of the months in the period"
NOTE_LOCATION            = "at {lat}, {lon}"

# --- Errors -------------------------------------------------------------------
# Every error answer is {"error": <message>}.
ERROR_UNKNOWN_ENDPOINT = "unknown endpoint {path}"
ERROR_NOT_AVAILABLE    = "metric {metric} is not available yet"
ERROR_WRONG_METHOD     = "{method} is not allowed on {path}; use {allowed}"

# Columns of the hotspots CSV export (GET /api/hotspots.csv).
HOTSPOTS_CSV_COLUMNS   = ["lat", "lon", "date_time", "confidence_class"]
CSV_STREAM_PIECE_BYTES = 64_000  # the export is sent in pieces of about this size

# --- Geometry -----------------------------------------------------------------
EARTH_RADIUS_KM = 6371
KM_PER_DEGREE   = math.pi * EARTH_RADIUS_KM / 180  # ~111.2 km along a meridian

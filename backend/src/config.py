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
MOCK_CHUNK_MEANS_FILE  = "chunk_means.csv"

# Side of a grid chunk, in degrees (the pipeline stores its metrics per chunk).
CHUNK_SIZE_DEG = 0.1

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

# Columns of the hotspots CSV export (GET /api/hotspots.csv).
HOTSPOTS_CSV_COLUMNS   = ["lat", "lon", "date_time", "confidence_class"]
CSV_STREAM_PIECE_BYTES = 64_000  # the export is sent in pieces of about this size

# --- Geometry -----------------------------------------------------------------
EARTH_RADIUS_KM = 6371
KM_PER_DEGREE   = math.pi * EARTH_RADIUS_KM / 180  # ~111.2 km along a meridian

from pathlib import Path

HOST = "127.0.0.1"
PORT = 8080

# Harmonized hotspots CSV: lat, lon, date_time, confidence_class
DATA_FILE          = Path(__file__).parent.parent.parent / "data" / "hotspots.csv"

MAX_RADIUS_KM      = 1000
DEFAULT_MAX_POINTS = 1000

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

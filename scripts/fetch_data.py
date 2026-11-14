"""Descarrega a pasta metrics/ da Google Drive para data/metrics/.

Uso:
    DRIVE_METRICS_FOLDER_ID=<id> python scripts/fetch_data.py
"""
import os
import sys
from pathlib import Path

import gdown

DEST = Path(__file__).resolve().parent.parent / "data" / "metrics"


def main() -> int:
    folder_id = os.environ.get("DRIVE_METRICS_FOLDER_ID")
    if not folder_id:
        print("Defina DRIVE_METRICS_FOLDER_ID (ver data/README.md).", file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    gdown.download_folder(id=folder_id, output=str(DEST), quiet=False)
    print(f"Metricas em {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

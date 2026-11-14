"""API minima que serve os agregados de data/metrics/."""
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException

METRICS_DIR = Path(__file__).resolve().parents[2] / "data" / "metrics"

app = FastAPI(title="Sprinklers API")


@app.get("/metrics")
def list_metrics() -> list[str]:
    return sorted(p.name for p in METRICS_DIR.glob("*.parquet"))


@app.get("/metrics/{name}")
def get_metric(name: str, limit: int = 1000):
    path = METRICS_DIR / f"{Path(name).name}.parquet"
    if not path.exists():
        raise HTTPException(404, f"{name} nao encontrado; correu scripts/fetch_data.py?")
    return pd.read_parquet(path).head(limit).to_dict(orient="records")

# NASA Space Apps 2026 – Sprinklers

Calendário harmonizado de queimadas (MODIS + VIIRS FIRMS).

## Arquitetura
Colab (processa, via Drive) → `metrics/` na Drive → backend (FastAPI) → frontend.
Os dados não estão no Git: ver [data/README.md](data/README.md).

## Arranque rápido
```bash
pip install -r requirements.txt
export DRIVE_METRICS_FOLDER_ID=<id>
python data/pipeline/scripts/fetch_data.py
uvicorn backend.app.main:app --reload
```

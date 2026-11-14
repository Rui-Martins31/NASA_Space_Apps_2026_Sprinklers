# Dados

Os dados **não** estão no Git. Ficam numa pasta partilhada do Google Drive:

```
Sprinklers/            <- DRIVE_FOLDER_ID
├── raw/               CSVs FIRMS (MODIS + VIIRS), originais
├── processed/         Parquet harmonizado (gerado no Colab)
└── metrics/           agregados pequenos (gerado no Colab, lido pelo backend)
```

## Fluxo
1. Colab lê `raw/`, harmoniza e calcula métricas (`backend/notebooks/`).
2. Colab grava `processed/` e `metrics/` na Drive.
3. O backend só descarrega `metrics/`:

```bash
pip install -r requirements.txt
export DRIVE_METRICS_FOLDER_ID=<id da pasta metrics/ na Drive>
python scripts/fetch_data.py
```

Os ficheiros ficam em `data/metrics/` (ignorado pelo Git).

## Partilha
A pasta `metrics/` tem de estar partilhada como "Qualquer pessoa com o link pode ver" para o `gdown` funcionar sem login.

Ver `MANIFEST.md` para o que cada ficheiro contém.

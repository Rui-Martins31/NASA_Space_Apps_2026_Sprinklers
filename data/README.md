# Dados

Os dados **não** estão no Git. Ficam numa pasta partilhada do Google Drive:

```
Sprinklers/                       <- dono: pedrolobao200207, partilhada com a equipa
├── raw/
│   ├── MODIS_All_Countries/      modis_<ano>_all_countries.zip        (2000-2025, ~30-90 MB cada)
│   ├── VIIRS NOAA-20/            viirs-jpss1_<ano>_all_countries.zip  (2018-2025)
│   └── VIIRS SNPP/               viirs-snpp_<ano>_all_countries.zip  (2012+, conforme inventário)
├── processed/                    Parquet harmonizado, um por sensor e ano (gerado no Colab)
└── metrics/                      agregados pequenos (gerado no Colab, lido pelo backend)
```

## Formato dos zips em `raw/`
Cada zip tem um CSV por país: `modis/2000/modis_2000_<País>.csv` (países com underscores, ex. `Cote_d_Ivoire`).
Colunas MODIS (15): `latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, instrument,
confidence, version, bright_t31, frp, daynight, type`. VIIRS usa `bright_ti4`/`bright_ti5` e confiança `l/n/h`
(ver a skill `firms-active-fire-attributes`). Amostra verificada: `modis_2000` = 163 países, 261 363 linhas.

Keep the sources separate. NOAA-20 files use `viirs-jpss1` and satellite code
`N20`. Suomi NPP files use `viirs-snpp` and satellite code `N`. Duplicate
archives with the same sensor/year are resolved by notebook 01's existing
discovery rules.

Notebook 02 defaults to MODIS and NOAA-20. Its source selection also controls
cached partials, daily consolidation, coverage and logs. S-NPP is processed
separately by notebook 09 for HAR-12. A source/year subset publishes only
that subset; use a separate validation output folder for pilot runs.

## Fluxo
1. No Colab, `data/pipeline/notebooks/01_ingest_harmonize.ipynb` lê os zips de `raw/`, harmoniza e grava `processed/<sensor>_<ano>.parquet` (coluna `country` incluída). Salta o que já existe.
2. `02_metrics_lote1.ipynb` (métricas do Lote 1) lê `processed/` e grava os agregados em `metrics/` (`l1_*.parquet`, `_log_lote1.csv`, `_params_lote1.json`; parciais em `metrics/_partial_lote1/`). O código vem do repo (`data/pipeline/metrics/`) por `git clone` no Colab. Metodologia e lotes: `spec/metodologia_metricas.md`.
   Testes: `cd data/pipeline && python -m pytest tests -q`.
3. O backend só descarrega `metrics/`:

```bash
pip install -r requirements.txt
export DRIVE_METRICS_FOLDER_ID=<id da pasta metrics/ na Drive>
python data/pipeline/scripts/fetch_data.py
```

Os ficheiros ficam em `data/metrics/` (ignorado pelo Git).

## Acesso
- Colab: a pasta `Sprinklers` pertence a outra conta. Na Drive, *Organizar → Adicionar atalho* em *O Meu Drive*, para o caminho `/content/drive/MyDrive/Sprinklers` funcionar.
- Backend: `metrics/` tem de estar partilhada como "Qualquer pessoa com o link pode ver" para o `gdown` funcionar sem login.

Ver `MANIFEST.md` para o que cada ficheiro contém.

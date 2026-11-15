# Dados

Os dados **não** estão no Git. Ficam numa pasta partilhada do Google Drive:

```
Sprinklers/                       <- dono: pedrolobao200207, partilhada com a equipa
├── raw/
│   ├── MODIS_All_Countries/      modis_<ano>_all_countries.zip        (2000-2025, ~30-90 MB cada)
│   ├── VIIRS NOAA-20/            viirs-jpss1_<ano>_all_countries.zip  (2018-2025)
│   └── VIIRS SNPP/               viirs-snpp_<ano>_all_countries.zip  (2012+, conforme inventário)
├── processed/                    Parquet harmonizado, um por sensor e ano (gerado no Colab)
└── metrics/                      uma pasta Parquet por métrica, por célula (gerado no Colab, lido pelo backend)
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

## Métricas por célula (novo)
As métricas **já não são agrupadas por país**. Cada deteção é atribuída a uma **célula** de uma grelha regular
(`GRID_DEG`, por defeito 0,01° nos notebooks, ~1 km; a biblioteca usa 0,1° se não lhe passarem a grelha). A
chave é `cell` (int64 = `ilat * n_lon + ilon`, ver `data/pipeline/metrics/common.py`). Linhas globais (que
antes eram `country = "ALL"`) têm `cell = -1`.

Cada tabela por célula é **uma pasta Parquet** em `metrics/<nome>/` e tem as colunas
`cell, ilat, ilon, lat, lon, lat_band` (centro da célula; `lat_band` = faixa de 10° de latitude), ordenada por
`(ilat, ilon)` e particionada por `series` e/ou `lat_band`. Assim o backend responde a `(lat, lon, raio)` lendo só
as faixas que o círculo toca, com DuckDB (sem servidor, grátis). Exemplo de referência, testado:

```bash
python data/pipeline/scripts/query_area.py data/metrics l1_cal_monthly 38.72 -9.14 20 combined
```

Tabelas esparsas: só células com atividade. Fora disso, o valor é 0 **dentro do intervalo de cobertura da série**
(`l1_meta_month_validity` / `l1_meta_year_validity` dizem quais os meses/anos parciais e com dias de cobertura
desconhecida). `_runs` regista cada execução (grelha, commit, parâmetros, linhas por tabela) e escreve-se
**por último**: uma execução a meio não fica registada.

Tabelas e colunas: `MANIFEST.md`.

## Fluxo
1. No Colab, `data/pipeline/notebooks/01_ingest_harmonize.ipynb` lê os zips de `raw/`, harmoniza e grava `processed/<sensor>_<ano>.parquet` (coluna `country` incluída, já não usada nas métricas). Salta o que já existe.
2. Os notebooks `02` … `09` leem `processed/` (ou as tabelas já calculadas) e gravam em `metrics/`. O código vem do repo (`data/pipeline/metrics/`) por `git clone` no Colab. Ordem: `02` → `03`, `04`, `05`, `06`, `07` → `08` (o `09` é independente e alimenta o `08`).
   - **Antes da primeira corrida completa**, ligar `RUN_DIAGNOSTIC = True` no notebook 02 (um só ano): imprime o número de células, as linhas por tabela e o tamanho estimado em Parquet para todos os anos, comparado com `DISK_BUDGET_GB`. Se não couber, ajustar `STATS_GRID_DEG` (grelha das estatísticas, p. ex. 0,1°), `MIN_ACTIVE_YEARS` e `SERIES_PUBLISHED` nos parâmetros no topo do notebook, sem tocar no código.
   - Metodologia e lotes: `spec/metodologia_metricas.md`.
   - Testes: `cd data/pipeline && python -m pytest tests -q` (precisa de `pandas`, `numpy`, `pyarrow`, `duckdb`, `pytest`).
3. Publicar as tabelas finais para o disco do backend (ou para uma pasta que se sincroniza com um bucket):

```bash
pip install -r requirements.txt
python data/pipeline/scripts/publish_metrics.py /content/drive/MyDrive/Sprinklers/metrics data/metrics
```

`data/metrics/` fica ignorado pelo Git. Copia só as tabelas finais (ignora `_partial_*`, `_l2_parts`, `*.tmp`).
Para um bucket gratuito (Cloudflare R2 ou Backblaze B2, 10 GB; confirmar condições de saída de dados), sincronizar essa
pasta com `rclone sync data/metrics <remoto>:<bucket>`. O antigo `scripts/fetch_data.py` (gdown da pasta `metrics/`) já
não é o caminho recomendado: as tabelas são pastas particionadas e grandes.

## Acesso
- Colab: a pasta `Sprinklers` pertence a outra conta. Na Drive, *Organizar → Adicionar atalho* em *O Meu Drive*, para o caminho `/content/drive/MyDrive/Sprinklers` funcionar.
- Backend: só precisa das tabelas finais publicadas (disco local ou bucket); não lê a Drive.

Ver `MANIFEST.md` para o que cada ficheiro contém.

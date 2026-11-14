# Manifest dos dados

Atualizar sempre que se gerarem ficheiros novos no Colab. O notebook 01 também escreve `processed/_ingest_log.csv` (linhas, países, horas inválidas por sensor/ano).

## raw (zips FIRMS, ficheiros de origem)
| Pasta | Ficheiros | Anos | Instrumento / satélite | Notas |
|-------|-----------|------|------------------------|-------|
| `raw/MODIS_All_Countries` | `modis_<ano>_all_countries.zip` | 2000-2025 | MODIS (Terra, Aqua) | `version` mistura `6.2` e `6.03` em 2000 |
| `raw/VIIRS NOAA-20` | `viirs-jpss1_<ano>_all_countries.zip` | 2018-2025 | VIIRS (N20) | `viirs-jpss1_2023` duplicado; sem Suomi NPP |

Amostra inspecionada: `modis_2000_all_countries.zip` (4 658 057 bytes): 163 CSVs de países, 261 363 linhas, 0 horas inválidas.

## processed (gerado pelo notebook 01)
| Ficheiro | Conteúdo |
|----------|----------|
| `<sensor>_<ano>.parquet` | todas as deteções do ano, esquema comum MODIS+VIIRS, coluna `country` |

Esquema: `country, source_file, instrument, satellite, version(txt), latitude, longitude, acq_date, acq_time(txt HHMM),
acq_datetime_utc, daynight, type(Int8, NA=desconhecido), confidence_raw, confidence_class(l/n/h),
brightness_primary(+_band), brightness_aux(+_band), scan, track, pixel_area_km2, frp`.

## metrics (gerado por `02_metrics_lote1.ipynb`, Lote 1)
| Ficheiro | Conteúdo | Chave |
|----------|----------|-------|
| `l1_obs01_raw_counts.parquet` | OBS-01 deteções brutas (`n_raw`) | país, ano, mês, instrumento, satélite |
| `l1_obs02_confidence_dist.parquet` | OBS-02 classes de confiança (`n`, `pct`) | país, ano, instrumento, classe |
| `l1_obs03_filtered_counts.parquet` | OBS-03 elegíveis (`n_eligible`) | como OBS-01 |
| `l1_qa02_retention.parquet` | QA-02 retenção do filtro (`pct_retained`) | como OBS-01 |
| `l1_qa03_cellday_grouped.parquet` | QA-03 registos agrupados por célula-dia | país, ano, instrumento, satélite |
| `l1_qa04_redundancy.parquet` | QA-04 redundância entre satélites do sensor | país, ano, instrumento |
| `l1_cal_coverage.parquet` | apoio: calendário completo por sensor (`n_rows_global`; 0 = cobertura desconhecida) | instrumento, data |
| `l1_cal_daily.parquet` | CAL-01/02 células ativas por dia (`n_cells`) | país, data, série |
| `l1_cal_monthly.parquet` | CAL-03 células-dia por mês (`cell_days`, `partial`, `n_unknown_days`) | país, ano, mês, série |
| `l1_cal_annual.parquet` | CAL-04 células-dia por ano | país, ano, série |
| `_log_lote1.csv`, `_params_lote1.json` | linhas por ficheiro, descartes, parâmetros (grelha, filtro, commit) | |

Séries: `modis`, `viirs`, `combined` (união de células-dia; degrau artificial em 2018). SHA-256: a registar após a execução no Colab.

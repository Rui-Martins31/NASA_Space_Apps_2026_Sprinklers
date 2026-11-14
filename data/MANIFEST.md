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

## metrics (gerado pelo notebook 02)
| Ficheiro | Conteúdo | SHA-256 |
|----------|----------|---------|
| _a definir_ | | |

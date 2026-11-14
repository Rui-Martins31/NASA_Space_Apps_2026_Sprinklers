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

### Lote 2 (`03_metrics_lote2.ipynb`, lê `processed/`)
| Ficheiro | Conteúdo |
|----------|----------|
| `l2_obs04_night_pct.parquet` | OBS-04 % de deteções noturnas |
| `l2_obs05_frp_median.parquet`, `l2_obs06_frp_p90.parquet`, `l2_obs07_frp_peak.parquet`, `l2_obs08_frp_availability.parquet` | OBS-05..08 FRP: mediana, percentil 90, pico, disponibilidade |
| `l2_obs09_type_distribution.parquet` | OBS-09 distribuição por tipo de fonte térmica |
| `l2_obs10_pixel_area_median.parquet` | OBS-10 área mediana do píxel |
| `l2_qa01_schema_validation.parquet` | QA-01 taxa de validação do esquema |
| `l2_add03_duplicates.parquet`, `l2_add04_zero_detection_countries.parquet` | ADD-03 duplicados e pontos (0,0); ADD-04 países sem deteções no ano |
| `_log_lote2.csv` | log da execução |

### Lote 4 (`05_metrics_lote4.ipynb`, lê as tabelas `l1_*`)
| Ficheiro | Conteúdo | Chave |
|----------|----------|-------|
| `l4_his01_hist_median.parquet` | HIS-01 mediana histórica do mês (referência fixa) | país, série, mês |
| `l4_his02_hist_band.parquet` | HIS-02 faixa histórica p10–p90 | país, série, mês |
| `l4_his05_zscore.parquet` | HIS-05 z-score mensal (referência sem o ano avaliado) | país, série, ano, mês |
| `l4_his06_percentile.parquet` | HIS-06 percentil histórico | país, série, ano, mês |
| `l4_his07_ytd.parquet` | HIS-07 acumulado no ano comparável com os outros anos | país, série, ano, mês |
| `l4_his08_yoy.parquet` | HIS-08 variação homóloga mensal | país, série, ano, mês |
| `l4_his09_months_above.parquet` | HIS-09 meses acima da faixa histórica (p90 fixo) | país, série, ano |
| `l4_his10_trend.parquet` | HIS-10 tendência anual de Theil-Sen (dispersão dos declives, não IC formal) | país, série |
| `l4_add01_active_satellites.parquet` | ADD-01 satélites ativos por mês (global) | instrumento, ano, mês |
| `l4_add02_zero_days.parquet` | ADD-02 dias sem deteções globais por mês | instrumento, ano, mês |
| `l5_esp02_active_cells.parquet` | ESP-02 células distintas com deteções | país, série, ano |
| `l5_esp03_recurrence.parquet` | ESP-03 recorrência por célula (dias com deteção; baldes 1 / 2–5 / 6–15 / 16+) | país, série, ano |
| `l5_esp06_interannual.parquet` | ESP-06 recorrência interanual por célula (só anos válidos) | país, série |
| `l5_qa05_confirmed_days.parquet` | QA-05 dias com registos globais (proxy de cobertura, não cobertura real) | instrumento, ano, mês |
| `l5_add05_type_sensitivity.parquet` | ADD-05 sensibilidade ao filtro de `type` (3 variantes) | país, ano, instrumento, variante |
| `l5_add06_union_step.parquet` | ADD-06 efeito do degrau MODIS→união (inclui linha `ALL`) | país, ano |
| `_log_lote4.csv`, `_params_lote4.json` | linhas por tabela e parâmetros (referência, mínimos, commit) | |

Estatísticas de histórico: só meses/anos **válidos** (não parciais e sem dias de cobertura desconhecida); mínimo de 5 anos de referência, abaixo disso NA.

# Manifest dos dados

Atualizar sempre que se gerarem ficheiros novos no Colab. O notebook 01 também escreve `processed/_ingest_log.csv` (linhas, países, horas inválidas por sensor/ano).

## raw (zips FIRMS, ficheiros de origem)
| Pasta | Ficheiros | Anos | Instrumento / satélite | Notas |
|-------|-----------|------|------------------------|-------|
| `raw/MODIS_All_Countries` | `modis_<ano>_all_countries.zip` | 2000-2025 | MODIS (Terra, Aqua) | `version` mistura `6.2` e `6.03` em 2000 |
| `raw/VIIRS NOAA-20` | `viirs-jpss1_<ano>_all_countries.zip` | 2018-2025 | VIIRS (N20) | NOAA-20 reference for notebooks 02–08 |
| `raw/VIIRS SNPP` | `viirs-snpp_<ano>_all_countries.zip` | 2012+, subject to inventory | VIIRS (N) | Separate HAR-12 inputs in notebook 09 |

Amostra inspecionada: `modis_2000_all_countries.zip` (4 658 057 bytes): 163 CSVs de países, 261 363 linhas, 0 horas inválidas.

## processed (gerado pelo notebook 01)
| Ficheiro | Conteúdo |
|----------|----------|
| `<sensor>_<ano>.parquet` | todas as deteções do ano, esquema comum MODIS+VIIRS, coluna `country` (já não usada nas métricas) |

Esquema: `country, source_file, instrument, satellite, version(txt), latitude, longitude, acq_date, acq_time(txt HHMM),
acq_datetime_utc, daynight, type(Int8, NA=desconhecido), confidence_raw, confidence_class(l/n/h),
brightness_primary(+_band), brightness_aux(+_band), scan, track, pixel_area_km2, frp`.

## metrics (gerado pelos notebooks 02 a 09)

**Cada entrada é uma pasta Parquet** `metrics/<nome>/` (uma tabela por métrica), não um ficheiro. Convenções (detalhe em `data/README.md`):
- **`cell`** (int64) substitui `country`; **`cell = -1`** é a linha global (antes `country = "ALL"`).
- Tabelas por célula levam `cell, ilat, ilon, lat, lon, lat_band` (centro da célula; `lat_band` = faixa de 10° de latitude), ordenadas por `(ilat, ilon)` e particionadas por `series` e/ou `lat_band`. As que misturam linhas globais não se particionam por `lat_band` (as colunas de célula ficam NA nas linhas globais).
- Esparsas: só células com atividade. Fora disso o valor é 0 **dentro do intervalo de cobertura da série** (`l1_meta_*`).
- Grelha: `GRID_DEG` (0,01° nos notebooks); as estatísticas podem usar `STATS_GRID_DEG` maior. Ambas ficam em `_runs`.
- `_runs` (uma linha por notebook/lote: `lote, run_utc, grid_deg, commit, params, tables`) substitui `_log_loteN.csv` e `_params_loteN.json`; escreve-se **por último**.
- `l1_stats_*`: cópias de `l1_cal_monthly`/`l1_cal_annual` na grelha das estatísticas, só se `STATS_GRID_DEG != GRID_DEG`.

### Lote 1 (`02_metrics_lote1.ipynb`, lê `processed/`)
| Tabela | Conteúdo | Chave (além da célula) |
|--------|----------|------------------------|
| `l1_obs01_raw_counts` | OBS-01 deteções brutas (`n_raw`) | ano, mês, instrumento, satélite |
| `l1_obs02_confidence_dist` | OBS-02 classes de confiança (`n`, `pct`) | ano, instrumento, classe |
| `l1_obs03_filtered_counts` | OBS-03 elegíveis (`n_raw`, `n_eligible`) | como OBS-01 |
| `l1_qa02_retention` | QA-02 retenção do filtro (`pct_retained`) | como OBS-01 |
| `l1_qa03_cellday_grouped` | QA-03 registos agrupados por célula-dia | ano, instrumento, satélite |
| `l1_qa04_redundancy` | QA-04 redundância entre satélites do sensor | ano, instrumento |
| `l1_cal_daily` | CAL-01/02 célula-dia com deteção (`in_modis`, `in_viirs`; `combined` = um dos dois) | data |
| `l1_cal_monthly` | CAL-03 células-dia por mês (`cell_days`), esparsa | ano, mês, série |
| `l1_cal_annual` | CAL-04 células-dia por ano (`cell_days`), esparsa | ano, série |
| `l1_cal_coverage` | global: calendário completo por sensor (`n_rows_global`; 0 = cobertura desconhecida) | instrumento, data |
| `l1_meta_month_validity` | global: `partial`, `n_unknown_days` por mês | série, ano, mês |
| `l1_meta_year_validity` | global: `partial`, `n_unknown_days` por ano | série, ano |

Séries: `modis`, `viirs`, `combined` (união de células-dia; degrau artificial em 2018). A tabela densa antiga (com zeros, `partial`, `n_unknown_days`) obtém-se com `calendar_metrics.densify_monthly/densify_annual`. As células de fronteira contam uma vez (antes contavam uma vez por país); linhas com coordenadas inválidas ficam fora de todas as tabelas por célula. SHA-256: a registar após a execução no Colab.

### Lote 2 (`03_metrics_lote2.ipynb`, lê `processed/`)
Todas por célula + chave `ano, instrumento, satélite` (OBS-09 acrescenta `version, type_label`), exceto QA-01 (global).
| Tabela | Conteúdo |
|--------|----------|
| `l2_obs04_night_pct` | OBS-04 deteções de dia/noite (`n_day`, `n_night`, `pct_night`) |
| `l2_obs05_frp_median`, `l2_obs06_frp_p90`, `l2_obs07_frp_peak`, `l2_obs08_frp_availability` | OBS-05..08 FRP: mediana, percentil 90, pico, disponibilidade. Mediana e p90 não se somam entre células |
| `l2_obs09_type_distribution` | OBS-09 distribuição por tipo de fonte térmica |
| `l2_obs10_pixel_area_median` | OBS-10 área mediana do píxel |
| `l2_qa01_schema_validation` | QA-01 taxa de validação do esquema, global, chave `instrumento, ano` |
| `l2_add03_duplicates` | ADD-03 duplicados e pontos (0,0); já vê duplicados entre ficheiros de países |

ADD-04 (países sem deteções) foi retirada: é uma auditoria por país.

### Lote 3 (`04_metrics_lote3.ipynb`, lê `l1_*`; só células com ≥ `MIN_ACTIVE_YEARS` anos válidos com atividade)
Por célula e `series`: `l3_cal05_total_period`, `l3_cal06_peak_month`, `l3_cal07_peak_year`, `l3_cal08_annual_mean`, `l3_cal09_monthly_mean`, `l3_cal12_seasonal_profile`, `l3_his03_anomaly_abs`, `l3_his04_anomaly_pct`. CAL-10/11 deixam de se publicar (por célula repetem `cell_days`/`l1_cal_daily`).

### Lote 4 (`05_metrics_lote4.ipynb`, lê `l1_*`; mesma poda)
Por célula e `series`: `l4_his01_hist_median`, `l4_his02_hist_band`, `l4_his05_zscore`, `l4_his06_percentile`, `l4_his07_ytd`, `l4_his08_yoy`, `l4_his09_months_above`, `l4_his10_trend` (dispersão dos declives de Theil-Sen, não IC formal). Globais: `l4_add01_active_satellites` (instrumento, ano, mês), `l4_add02_zero_days` (instrumento, ano, mês).

### Lote 5 (`06_metrics_lote5.ipynb`, lê `processed/` e `l1_*`)
| Tabela | Conteúdo | Notas |
|--------|----------|-------|
| `l5_cell_year` | dias com deteção por célula, série e ano (`n_days`) | base da recorrência; por célula |
| `l5_esp06_cell_years_active` | ESP-06 por célula: anos ativos / anos válidos | por célula |
| `l5_esp02_active_cells`, `l5_esp03_recurrence`, `l5_esp06_interannual` | ESP-02/03/06 como estatísticas de **população** sobre todas as células | `cell = -1`; médias/medianas não se somam |
| `l5_add05_type_sensitivity` | ADD-05 sensibilidade ao filtro de `type` por célula + linha global recalculada das somas | `cell = -1` na linha global |
| `l5_qa05_confirmed_days` | QA-05 dias com registos globais (proxy de cobertura) | global |
| `l5_add06_union_step` | ADD-06 degrau MODIS→união por célula + linha global | grelha das estatísticas |

### Lote 6 (`07_metrics_lote6.ipynb`) e Lote 7 (`08_metrics_lote7.ipynb`), harmonização MODIS↔VIIRS (2018+)
- `l6_har01_overlap`, `l6_har02_jaccard`: sobreposição por célula-mês (`n_modis, n_viirs, n_both, n_union`, aditiva).
- `l6_har03_comparable_months`, `l6_har04_pearson`, `l6_har05_spearman`, `l6_har06_factor`, `l6_har07_factor_uncertainty`: por célula + linha global; **a maioria das células fica NA** (≤ 31 contagens/mês, `MIN_PAIRS=12`, `MIN_CAL_MONTHS=24`). `l6_har06_factor` tem `scope` (`cell`/`global`) e `uses_global_fallback`; o fator global é o fallback das células sem dados.
- `l7_har08_mae`, `l7_har09_wape`, `l7_har10_bias`, `l7_har11_error_reduction`: por célula + linha global (calculada sobre a série global, não somada).
- `l7_har12_residual_step`, `l7_har13_grid_sensitivity`, `l7_har14_confidence_sensitivity`: **globais** (`cell = -1`).

### HAR-12 com Suomi NPP (`09_har12_snpp.ipynb`, lê `processed/`)
`l7_har12_snpp_monthly`, `l7_har12_snpp_factor`, `l7_har12_residual_step` (globais). A linha `har12_snpp` de `_runs` é o sentinela: apaga-se antes de escrever e escreve-se por último; o notebook 08 só usa estas tabelas se a linha existir.

Estatísticas de histórico: só meses/anos **válidos** (não parciais e sem dias de cobertura desconhecida); mínimo de 5 anos de referência, abaixo disso NA. Uma estatística de uma área com várias células **não** se obtém combinando as das células (anomalia, z-score e percentil não são aditivos).

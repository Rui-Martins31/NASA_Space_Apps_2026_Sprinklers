# API Frontend - Backend

---

## URL

URL: 127.0.0.1 \
Port: 8080 \
Endpoint: /api \
Features: /api/[name_of_feature]

---

## Features

Legend:
- feature:
    1. "all" - all KPIs, profiles, heatmap, etc
    2. "hotspots" - hotspots map
    3. "calendar" - calendar
    4. "anomalies" - graph that compares the values for a set of years (higher than the average is considered an anomaly)
    5. "[metric_id]" - one feature per metric of `spec/metricas_modis_viirs.csv`, e.g. "cal_05" (see "Features - Metrics")

---

## Request

### Common request body

Every request includes these fields:

```json
{
    "feature": str,
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

- `feature`: {
    `"all"`,
    `"hotspots"`,
    `"calendar"`,
    `"anomalies"`
}
- `radius`: radius of the circle, in **km**.

---

## Features - Request and Response

### Feature - all

Method: POST \
Endpoint: 127.0.0.1:8080/api/all

Request:

```json
{
    "feature": "all",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "all",
    "calendar": [],
    "anomalies": []
}
```

### Feature - hotspots

Method: POST \
Endpoint: 127.0.0.1:8080/api/hotspots

Request:

```json
{
    "feature": "hotspots",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime,
    "max_points": int
}
```

Response:

```json
{
    "feature": "hotspots",
    "hotspots": [
        {
            "lat": float,
            "lon": float,
            "date_time": datetime,
            "confidence_class": "low" | "nominal" | "high"
        },
        {
            ...
        }
    ]
}
```

- `confidence_class`: {
    `low`,
    `nominal`,
    `high`
}

### Feature - calendar

Method: POST \
Endpoint: 127.0.0.1:8080/api/calendar

Request:

```json
{
    "feature": "calendar",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "calendar",
    "calendar": [
        {
            "year": int,
            "month": int,
            "count": int
        },
        {
            ...
        }
    ]
}
```

### Feature - anomalies

Method: POST \
Endpoint: 127.0.0.1:8080/api/anomalies

Request:

```json
{
    "feature": "anomalies",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "anomalies",
    "anomalies": [
        {
            "year": int,
            "month": int,
            "count": int,
            "mean": float,
            "anomaly": str
        },
        {
            ...
        }
    ]
}
```

- `mean`: the area's reference mean for that calendar month, as computed by the pipeline over its reference years (not over the requested period).
- `anomaly`: `"above"` when `count > mean`, otherwise `"normal"`.

### Feature -  export hotspots CSV

Method: GET \
Endpoint: 127.0.0.1:8080/api/hotspots.csv

Request:
```
/api/hotspots.csv?lat=39.5&lon=-8.0&radius=50&date_time_from=2020-01-01T00:00:00&date_time_to=2021-12-31T23:59:59
```

Response:
`text/csv` with `Content-Disposition: attachment`, columns `lat,lon,date_time,confidence_class`. Invalid parameters return `400` with `{"error": "<message>"}`.

### Errors

Every error is JSON, `{"error": "<message>"}`:

| Status | When | Example message |
|--------|------|-----------------|
| `400` | invalid request body or query string | `"radius must be greater than 0"` |
| `404` | unknown endpoint (e.g. `/api/alle`), or a metric not available yet | `"unknown endpoint /api/alle"`, `"metric qa_01 is not available yet"` |
| `405` | the endpoint exists but not for this method (the `Allow` header lists the valid ones) | `"GET is not allowed on /api/calendar; use POST"` |


---

## Features - Metrics

One feature per metric of `spec/metricas_modis_viirs.csv`.
The pipeline computes the values per grid chunk and stores them in the database; the backend keeps the
chunks inside the circle and combines them; the frontend only displays them.

- Feature name = metric `id` in lowercase with `_` (e.g. `CAL-05` → `"cal_05"`). The same name is the endpoint (`/api/cal_05`) and the request's `feature`.
- Metrics `APP-*` (app tests) and `EXT-*` (out of MVP) are not features.
- Names, descriptions and units shown in the app come from the CSV, not from the backend.

### Feature - [metric_id]

Method: POST \
Endpoint: 127.0.0.1:8080/api/[metric_id]

Request:

```json
{
    "feature": "cal_05",
    "lat": float,
    "lon": float,
    "radius": float,
    "date_time_from": datetime,
    "date_time_to": datetime
}
```

Response:

```json
{
    "feature": "cal_05",
    "value": ...,
    "unit": str,
    "note": str
}
```

- `value`: shape depends on the metric (table below).
- `value` = `null` when the metric cannot be computed for this request (e.g. no complete year, no data in the circle); `note` says why. Inside a list, a `null` item means the same for that month.
- `unit` (optional): overrides the unit from the CSV.
- `note` (optional): short remark shown under the value (e.g. `"complete years: 25 (2001–2025)"`, `"average over 37 grid chunk(s)"`).
- A metric that is not implemented yet returns `404` with `{"error": "metric qa_01 is not available yet"}`; the app shows it as "not available yet". Today: `qa_01`, `qa_06`, `qa_07`, `har_12`, `esp_05`.
- Invalid parameters return `400` with `{"error": "<message>"}`, like the other features.

How a circle's value is made from the chunks (0.01° grid):

- Counts (cell-days, detections) are **summed** over the chunks inside the circle; so are count-like statistics (`his_01`, `his_02`, `his_10`, `har_08`, `har_10`).
- Ratios, percentages, correlations and factors are **averaged** over the chunks (`note`: `"average over N grid chunk(s)"`). This approximates the circle's value: the database stores them per chunk, never per circle.
- `cal_*`, `his_03`, `his_04`, `his_07`, `his_08`, `his_09` and `esp_*` use the same rows as `calendar` and `anomalies`, so they always agree with them.
- `har_*` are computed over the whole record (`har_01`…`har_11`: MODIS and VIIRS common period, 2018 onwards), not the selected dates; `note` says so.

Value shapes by time scale:

| shape | JSON |
|-------|------|
| per month | `[{"year": int, "month": int, "value": float \| null}]`, one item per month of the period |
| per day | `[{"date": "YYYY-MM-DD", "value": float}]`, one item per day of the period |
| per year | `[{"year": int, "value": float}]`, one item per year of the period |
| per calendar month | `[float × 12]`, January → December |
| by category | `[{"key": str, "value": float}]`, sorted by key |

### Metrics and value shapes

| feature | metric | unit (CSV) | value | priority |
|---------|--------|------------|-------|----------|
| `cal_01` | Células-dia com deteções | células-dia | `float` | MVP |
| `cal_02` | Atividade diária | células-dia por dia | per day | MVP |
| `cal_03` | Atividade mensal | células-dia por mês | per month | MVP |
| `cal_04` | Atividade anual | células-dia por ano | per year | MVP |
| `cal_05` | Atividade total no período | células-dia | `float` | MVP |
| `cal_06` | Mês-ano de pico | mês-ano e células-dia | `{"year": int, "month": int, "count": float}` | MVP |
| `cal_07` | Ano de pico | ano e células-dia | `{"year": int, "count": float}` (complete years only) | MVP |
| `cal_08` | Média anual de atividade | células-dia por ano | `float` (complete years only) | MVP |
| `cal_09` | Média histórica do mesmo mês | células-dia por mês | per month | MVP |
| `cal_10` | Dias com deteções | dias | `float` | Opcional |
| `cal_11` | Maior atividade diária | data e células-dia | `{"date": "YYYY-MM-DD", "count": float}` | Opcional |
| `cal_12` | Perfil sazonal mensal | células-dia por mês | per calendar month | MVP |
| `his_01` | Mediana histórica mensal | células-dia por mês | per calendar month | Desejável |
| `his_02` | Faixa histórica mensal | células-dia por mês | `[{"low": float, "high": float} × 12]` (Jan → Dec) | Desejável |
| `his_03` | Anomalia mensal absoluta | células-dia | per month | MVP |
| `his_04` | Anomalia mensal percentual | % | per month | Desejável |
| `his_05` | Desvio padronizado mensal (z-score) | desvios-padrão | per month | Desejável |
| `his_06` | Percentil histórico da atividade | percentil (0 a 100) | per month | Desejável |
| `his_07` | Acumulado comparável no ano | células-dia | per month | Desejável |
| `his_08` | Variação homóloga mensal | % | per month | Opcional |
| `his_09` | Meses acima da faixa histórica | meses | per year | Desejável |
| `his_10` | Tendência dos totais anuais | células-dia por ano de tendência | `float` | Opcional |
| `esp_01` | Densidade de atividade | células-dia por 1 000 km² | `float` | Opcional |
| `esp_02` | Células distintas com deteções | células | `float` | Desejável |
| `esp_03` | Recorrência por célula | dias por célula | `float` | Desejável |
| `esp_04` | Proporção da grelha com deteções | % de células | `float` | Opcional |
| `esp_05` | Frequência de deteções por célula | % de dias observados | not available yet (404) | Opcional |
| `esp_06` | Recorrência interanual por célula | anos por célula | `float` | Opcional |
| `obs_01` | Deteções brutas por sensor e satélite | deteções | by category | MVP |
| `obs_02` | Distribuição por classe de confiança | deteções e % | by category | MVP |
| `obs_03` | Deteções após o filtro de qualidade | deteções | `float` | MVP |
| `obs_04` | Percentagem de deteções noturnas | % de deteções | by category (instrument) | Extra |
| `obs_05` | FRP mediana | MW | `float` | Extra |
| `obs_06` | Percentil 90 de FRP | MW | `float` | Extra |
| `obs_07` | Pico de FRP | MW, timestamp e localização | `{"date": "YYYY-MM-DD", "count": float}`; `note` = location | Extra |
| `obs_08` | Disponibilidade de FRP | % de deteções | `float` | Extra |
| `obs_09` | Distribuição por tipo de fonte térmica | deteções e % | by category | Opcional |
| `obs_10` | Área mediana do píxel de deteção | km² por píxel | `float` | Opcional |
| `qa_01` | Taxa de validação do esquema | % de linhas | not available yet (404) | MVP |
| `qa_02` | Taxa de retenção dos filtros | % de linhas | `float` | MVP |
| `qa_03` | Registos agrupados por célula-dia no mesmo satélite | deteções agrupadas | `float` | MVP |
| `qa_04` | Redundância entre satélites do mesmo sensor | observações célula-dia repetidas | `float` | MVP |
| `qa_05` | Dias com cobertura confirmada | dias e % | `float`; `note` = % | MVP |
| `qa_06` | Proporção de atividade provisória | % de células-dia | not available yet (404) | Opcional |
| `qa_07` | Atraso da última observação disponível | horas ou dias | not available yet (404) | Extra |
| `har_01` | Células-dia coincidentes entre MODIS e VIIRS | células-dia | `float` | Validação |
| `har_02` | Índice de sobreposição de Jaccard | índice de 0 a 1 | `float` | Validação |
| `har_03` | Meses comparáveis usados na validação | meses | `float` | Validação |
| `har_04` | Correlação mensal de Pearson | coeficiente de -1 a 1 | `float` | Validação |
| `har_05` | Correlação mensal de Spearman | coeficiente de -1 a 1 | `float` | Opcional |
| `har_06` | Fator de ajuste MODIS para VIIRS | multiplicador | `{"value": float, "low": float, "high": float}` | Validação |
| `har_07` | Intervalo de incerteza do fator de ajuste | limites inferior e superior do multiplicador | `{"value": float, "low": float, "high": float}` | Validação |
| `har_08` | Erro absoluto médio mensal (MAE) | células-dia por mês | `float` | Validação |
| `har_09` | Erro relativo absoluto agregado (WAPE) | % | `float` | Validação |
| `har_10` | Viés mensal médio | células-dia por mês | `float` | Validação |
| `har_11` | Redução do erro após o ajuste | % | `float` | Validação |
| `har_12` | Degrau residual na transição entre sensores | células-dia por mês | not available yet (404) | Validação |
| `har_13` | Sensibilidade à dimensão da grelha | células-dia ou % | `float` (%) | Opcional |
| `har_14` | Sensibilidade ao filtro de confiança | células-dia ou % | `float` (%) | Opcional |

Examples:

```json
{ "feature": "cal_05", "value": 3158 }
{ "feature": "cal_03", "value": [{ "year": 2017, "month": 6, "value": 980 }, { "year": 2017, "month": 7, "value": 412 }] }
{ "feature": "cal_06", "value": { "year": 2017, "month": 6, "count": 980 } }
{ "feature": "cal_08", "value": 1203.4, "note": "complete years: 25 (2001–2025)" }
{ "feature": "cal_12", "value": [0, 1, 1, 1, 1, 40, 16, 42, 7, 11, 1, 1] }
{ "feature": "obs_02", "value": [{ "key": "MODIS · nominal", "value": 640 }, { "key": "VIIRS · high", "value": 412 }] }
{ "feature": "obs_05", "value": 46.35, "note": "average over 37 grid chunk(s)" }
{ "feature": "har_06", "value": { "value": 1.82, "low": 1.61, "high": 2.05 }, "note": "MODIS vs VIIRS over their common period (2018 onwards), not the selected dates" }
{ "feature": "cal_07", "value": null, "note": "no complete year in the period" }
```

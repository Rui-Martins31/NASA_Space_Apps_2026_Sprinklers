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
    5. "[metric_id]" - one feature per metric of `spec/metricas_modis_viirs.csv`, e.g. "cal-05" (see "Features - Metrics")

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


---

## Features - Metrics

One feature per metric of `spec/metricas_modis_viirs.csv`.
The pipeline computes the values; the backend only returns them and the frontend only displays them.

- Feature name = metric `id` in lowercase (e.g. `CAL-05` → `"cal-05"`).
- Metrics `APP-*` (app tests) and `EXT-*` (out of MVP) are not features.
- Names, descriptions and units shown in the app come from the CSV, not from the backend.

### Feature - [metric_id]

Method: POST \
Endpoint: 127.0.0.1:8080/api/[metric_id]

Request:

```json
{
    "feature": "cal-05",
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
    "feature": "cal-05",
    "value": ...,
    "unit": str,
    "note": str
}
```

- `value`: shape depends on the metric (table below).
- `value` = `null` when the metric cannot be computed for this request (e.g. not enough complete years); `note` says why.
- `unit` (optional): overrides the unit from the CSV.
- `note` (optional): short remark shown under the value (e.g. `"mean of 25 complete years (2001–2025)"`).
- A metric that is not implemented yet must return `404`; the app shows it as "not available yet".
- Invalid parameters return `400` with `{"error": "<message>"}`, like the other features.

### Metrics and value shapes

| feature | metric | unit (CSV) | value | priority |
|---------|--------|------------|-------|----------|
| `cal-01` | Células-dia com deteções | células-dia | `float` | MVP |
| `cal-02` | Atividade diária | células-dia por dia | `float` | MVP |
| `cal-03` | Atividade mensal | células-dia por mês | `float` | MVP |
| `cal-04` | Atividade anual | células-dia por ano | `float` | MVP |
| `cal-05` | Atividade total no período | células-dia | `float` | MVP |
| `cal-06` | Mês-ano de pico | mês-ano e células-dia | `{"year": int, "month": int, "count": float}` | MVP |
| `cal-07` | Ano de pico | ano e células-dia | `{"year": int, "count": float}` | MVP |
| `cal-08` | Média anual de atividade | células-dia por ano | `float` | MVP |
| `cal-09` | Média histórica do mesmo mês | células-dia por mês | `float` | MVP |
| `cal-10` | Dias com deteções | dias | `float` | Opcional |
| `cal-11` | Maior atividade diária | data e células-dia | `{"date": "YYYY-MM-DD", "count": float}` | Opcional |
| `cal-12` | Perfil sazonal mensal | células-dia por mês | `[float × 12]` (Jan → Dec) | MVP |
| `his-01` | Mediana histórica mensal | células-dia por mês | `[float × 12]` (Jan → Dec) | Desejável |
| `his-02` | Faixa histórica mensal | células-dia por mês | `[{"low": float, "high": float} × 12]` (Jan → Dec) | Desejável |
| `his-03` | Anomalia mensal absoluta | células-dia | `float` | MVP |
| `his-04` | Anomalia mensal percentual | % | `float` | Desejável |
| `his-05` | Desvio padronizado mensal (z-score) | desvios-padrão | `float` | Desejável |
| `his-06` | Percentil histórico da atividade | percentil (0 a 100) | `float` | Desejável |
| `his-07` | Acumulado comparável no ano | células-dia | `float` | Desejável |
| `his-08` | Variação homóloga mensal | % | `float` | Opcional |
| `his-09` | Meses acima da faixa histórica | meses | `float` | Desejável |
| `his-10` | Tendência dos totais anuais | células-dia por ano de tendência | `float` | Opcional |
| `esp-01` | Densidade de atividade | células-dia por 1 000 km² | `float` | Opcional |
| `esp-02` | Células distintas com deteções | células | `float` | Desejável |
| `esp-03` | Recorrência por célula | dias por célula | `float` | Desejável |
| `esp-04` | Proporção da grelha com deteções | % de células | `float` | Opcional |
| `esp-05` | Frequência de deteções por célula | % de dias observados | `float` | Opcional |
| `esp-06` | Recorrência interanual por célula | anos por célula | `float` | Opcional |
| `obs-01` | Deteções brutas por sensor e satélite | deteções | `[{"key": str, "value": float}]` | MVP |
| `obs-02` | Distribuição por classe de confiança | deteções e % | `[{"key": str, "value": float}]` | MVP |
| `obs-03` | Deteções após o filtro de qualidade | deteções | `float` | MVP |
| `obs-04` | Percentagem de deteções noturnas | % de deteções | `[{"key": str, "value": float}]` | Extra |
| `obs-05` | FRP mediana | MW | `float` | Extra |
| `obs-06` | Percentil 90 de FRP | MW | `float` | Extra |
| `obs-07` | Pico de FRP | MW, timestamp e localização | `{"date": "YYYY-MM-DD", "count": float}` | Extra |
| `obs-08` | Disponibilidade de FRP | % de deteções | `float` | Extra |
| `obs-09` | Distribuição por tipo de fonte térmica | deteções e % | `[{"key": str, "value": float}]` | Opcional |
| `obs-10` | Área mediana do píxel de deteção | km² por píxel | `float` | Opcional |
| `qa-01` | Taxa de validação do esquema | % de linhas | `float` | MVP |
| `qa-02` | Taxa de retenção dos filtros | % de linhas | `float` | MVP |
| `qa-03` | Registos agrupados por célula-dia no mesmo satélite | deteções agrupadas | `float` | MVP |
| `qa-04` | Redundância entre satélites do mesmo sensor | observações célula-dia repetidas | `float` | MVP |
| `qa-05` | Dias com cobertura confirmada | dias e % | `float` | MVP |
| `qa-06` | Proporção de atividade provisória | % de células-dia | `float` | Opcional |
| `qa-07` | Atraso da última observação disponível | horas ou dias | `float` | Extra |
| `har-01` | Células-dia coincidentes entre MODIS e VIIRS | células-dia | `float` | Validação |
| `har-02` | Índice de sobreposição de Jaccard | índice de 0 a 1 | `float` | Validação |
| `har-03` | Meses comparáveis usados na validação | meses | `float` | Validação |
| `har-04` | Correlação mensal de Pearson | coeficiente de -1 a 1 | `float` | Validação |
| `har-05` | Correlação mensal de Spearman | coeficiente de -1 a 1 | `float` | Opcional |
| `har-06` | Fator de ajuste MODIS para VIIRS | multiplicador | `{"value": float, "low": float, "high": float}` | Validação |
| `har-07` | Intervalo de incerteza do fator de ajuste | limites inferior e superior do multiplicador | `{"value": float, "low": float, "high": float}` | Validação |
| `har-08` | Erro absoluto médio mensal (MAE) | células-dia por mês | `float` | Validação |
| `har-09` | Erro relativo absoluto agregado (WAPE) | % | `float` | Validação |
| `har-10` | Viés mensal médio | células-dia por mês | `float` | Validação |
| `har-11` | Redução do erro após o ajuste | % | `float` | Validação |
| `har-12` | Degrau residual na transição entre sensores | células-dia por mês | `float` | Validação |
| `har-13` | Sensibilidade à dimensão da grelha | células-dia ou % | `float` | Opcional |
| `har-14` | Sensibilidade ao filtro de confiança | células-dia ou % | `float` | Opcional |

Examples:

```json
{ "feature": "cal-05", "value": 3158, "unit": "células-dia" }
{ "feature": "cal-06", "value": { "year": 2017, "month": 6, "count": 980 } }
{ "feature": "cal-12", "value": [0, 1, 1, 1, 1, 40, 16, 42, 7, 11, 1, 1] }
{ "feature": "obs-02", "value": [{ "key": "VIIRS · high", "value": 412 }, { "key": "MODIS · nominal", "value": 640 }] }
{ "feature": "har-06", "value": { "value": 1.82, "low": 1.61, "high": 2.05 } }
{ "feature": "his-05", "value": null, "note": "fewer than 5 comparable years" }
```

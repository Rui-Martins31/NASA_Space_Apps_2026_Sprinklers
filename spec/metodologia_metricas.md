# Metodologia de métricas — MODIS + VIIRS (FIRMS)

Documento de orientação e **contrato de trabalho** para implementar as métricas de `spec/metricas_modis_viirs.csv`.
Foi escrito para que duas pessoas, cada uma com o seu Claude, trabalhem **em paralelo e sem ver o trabalho uma da outra** até os dois lados estarem em `main`. Por isso:

- cada lote tem os seus ficheiros, nomes e tabelas de saída, e **ninguém edita ficheiros de outro lote**;
- as regras de cálculo, a qualidade dos testes e a forma de raciocinar são as mesmas nos dois lados;
- onde o CSV deixa uma decisão em aberto, ela está **fixada aqui**. Não reinterprete: se discordar, implemente como está e registe a objeção no relatório do lote.

> **Para o Claude que lê isto:** leia este documento inteiro uma vez, depois só a linha do CSV de cada métrica que vai implementar (`grep "^OBS-04," spec/metricas_modis_viirs.csv`). Não leia o CSV completo nem os dados reais. O seu lote está na secção 6; a especificação exata está na secção 7 (L2), nas secções 7B e 7C (L3) ou na 7D (L4). Há prompts-modelo na secção 11.

---

## 1. Contexto do projeto

Projeto NASA Space Apps 2026 (equipa "Sprinklers"): um **calendário harmonizado de queimadas** que junta deteções ativas de fogo do **MODIS** (Terra e Aqua, ~1 km, desde 2000) e do **VIIRS** (NOAA-20, 375 m, desde 2018), com cartões-resumo, comparação histórica e exportação CSV. As user stories estão em `spec/user_stories_modis_viirs_en.csv`; as que mais pesam aqui são US-01 (limpar e filtrar por confiança e `type`) e US-02 (agregar numa grelha regular em "células-dia", tratando duplicados entre satélites).

Arquitetura (resumo; detalhes em `data/README.md`):

```
Drive: raw/ (zips FIRMS) --notebook 01--> processed/*.parquet --notebooks de métricas--> metrics/*.parquet --> backend FastAPI --> frontend
```

Os cálculos correm no **Google Colab** do Arthur. No Colab o código é obtido com `git clone` do repo. Os dados **nunca** vão para o Git.

## 2. Os dados que cada lote lê: `processed/<sensor>_<ano>.parquet`

Um Parquet por sensor e ano (`modis_2000.parquet`, `viirs-jpss1_2018.parquet`, …), com **todos os países** do ano. Esquema fixo (gerado por `data/pipeline/notebooks/01_ingest_harmonize.ipynb`):

| Coluna | Tipo | Notas |
|---|---|---|
| `country` | texto | do nome do CSV (ex. `Cote_d_Ivoire`) |
| `source_file` | texto | CSV de origem |
| `instrument` | texto | `MODIS` ou `VIIRS` |
| `satellite` | texto | MODIS: `Terra`, `Aqua`; VIIRS: `N20` |
| `version` | texto | **texto**: `6.2`, `6.03`, `2`, `2.0NRT` … |
| `latitude`, `longitude` | float | centro do píxel, graus |
| `acq_date` | texto `YYYY-MM-DD` | **UTC** |
| `acq_time` | texto `HHMM` | 4 dígitos, **texto** |
| `acq_datetime_utc` | datetime UTC | `NaT` se a hora for inválida |
| `daynight` | texto | `D` ou `N` |
| `type` | Int8 (aceita NA) | 0 vegetação presumida, 1 vulcão, 2 fonte estática, 3 offshore; NA = desconhecido |
| `confidence_raw` | texto | MODIS 0–100; VIIRS `l`/`n`/`h` |
| `confidence_class` | texto `l`/`n`/`h` | MODIS: 0–29 `l`, 30–79 `n`, 80–100 `h`; pode ser NA |
| `brightness_primary`, `brightness_aux` (+ `_band`) | float / texto | MODIS `brightness`/`bright_t31`; VIIRS `bright_ti4`/`bright_ti5` |
| `scan`, `track` | float | km |
| `pixel_area_km2` | float | `scan × track` |
| `frp` | float | MW; pode ser nulo ou 0 |

Particularidades que **afetam a interpretação** (registe-as nos seus relatórios quando relevantes):

1. **Aqua só começa em meados de 2002.** Em 2000–2002 o MODIS é só Terra: há um degrau natural de cobertura.
2. **O VIIRS é só NOAA-20 (`N20`) e só desde 2018.** Não há Suomi NPP. Logo, não há transição de 2012 para testar e, num sensor com um único satélite, medidas de redundância entre satélites valem 0.
3. **`version`** mistura valores (`6.2`, `6.03` no MODIS de 2000). É informação de proveniência: nunca a converta para número.
4. **`type` e `confidence_class` podem faltar.** NA nunca é tratado como "bom".
5. **`frp`**: nulo e 0 são possíveis em deteções válidas.
6. A amostra de referência, útil para testes de integração opcionais, é `modis_2000`: **261 363 linhas, 163 países, 0 horas inválidas**, só `Terra`.

## 3. Convenções partilhadas (congeladas)

Valem para todos os lotes. Se uma função precisar de outro valor, tem de receber o parâmetro; o **valor por defeito é este**.

| Convenção | Regra |
|---|---|
| Região | `country` (polígonos ficam para mais tarde) |
| Dia | `acq_date` (já é UTC). O ano é o ano de `acq_date`, o mês é o mês de `acq_date` |
| Elegível | `type == 0` **e** `confidence_class ∈ {n, h}`. `type` NA, `confidence_class` NA, `l`, e `type ∈ {1,2,3}` ficam **fora** |
| Grelha | 0.1° (`GRID_DEG = 0.1`), parametrizável (0.25° é a alternativa das user stories) |
| Célula | `ilat = floor((lat+90)/g)`, `ilon = floor((lon+180)/g)`, calculadas em **inteiros escalados** (ver abaixo) |
| Célula-dia | par distinto (célula, `acq_date`) |
| Séries | `modis`, `viirs`, `combined`; `combined` é a **união** de células-dia (uma célula-dia conta uma vez, mesmo que MODIS e VIIRS a detetem) |
| Aviso sobre `combined` | antes de 2018 só há MODIS, depois há MODIS ∪ VIIRS: a série `combined` ganha um **degrau artificial** em 2018. Quem a usar tem de o saber; por isso `series` é sempre uma coluna explícita |
| Mês/ano parcial | parcial se o mês/ano não está totalmente dentro de `[primeira, última]` `acq_date` presentes nos dados **desse sensor** (global, não por país) |
| Cobertura desconhecida | dia dentro desse intervalo em que o sensor não tem **nenhuma** deteção a nível global |
| Divisão por zero | resultado **NA** (nunca 0, nunca inf) |
| Percentagens | 0–100, float |
| Ordenação | tabelas de saída ordenadas pelas colunas-chave, `reset_index(drop=True)` |

**Cuidado com a grelha (já medido):** `floor((lat+90)/0.1)` em vírgula flutuante **dá o resultado errado** em muitas coordenadas reais (`floor((-89.9+90)/0.1)` dá 0 em vez de 1; só com duas casas decimais há 643 casos entre −89.99 e 89.99). O FIRMS tem no máximo 4 casas decimais, por isso a implementação de referência trabalha em inteiros:

```python
import numpy as np
SCALE = 10_000                                   # 4 casas decimais
def cell_ids(lat, lon, grid_deg=0.1):
    step = round(grid_deg * SCALE)               # 1000 para 0.1°
    ilat = np.rint((np.asarray(lat, float) + 90.0) * SCALE).astype("int64") // step
    ilon = np.rint((np.asarray(lon, float) + 180.0) * SCALE).astype("int64") // step
    return np.minimum(ilat, 180 * SCALE // step - 1), np.minimum(ilon, 360 * SCALE // step - 1)
```

Referência do filtro elegível:

```python
def eligible(df, confidence=("n", "h"), type_value=0):
    return ((df["type"] == type_value).fillna(False).astype(bool)
            & df["confidence_class"].isin(list(confidence)).fillna(False).astype(bool))
```

O lote 2 **não usa grelha**; usa só `eligible`. Cada lote define estas funções no **seu** módulo (o lote 1 coloca-as em `data/pipeline/metrics/common.py`; o lote 2 usa uma cópia privada em `detections.py`). No merge unificam-se; por isso a lógica tem de ser a descrita aqui.

## 4. Como as métricas foram avaliadas

Critérios: (1) **valor para o produto** (serve o calendário, o cartão-resumo, a comparação histórica ou a validação MODIS↔VIIRS?); (2) **calculável com os dados que temos** (só `processed/`? exige metadados, máscaras de cobertura ou dados externos?); (3) **prioridade do CSV** (MVP / Desejável / Opcional / Extra / Validação / Fora do MVP); (4) custo e risco de erro.

Legenda do **Estado**: *A implementar* (tem lote nesta fase) · *Útil, depende de L1* (só faz sentido depois das tabelas do lote 1) · *Útil, requer dados extra* · *Adicional proposta* (não está no CSV, faltava) · *Rever* (a definição ou a utilidade é questionável) · *Bloqueada* (faltam dados que não temos) · *Fora do pipeline* (não é uma métrica de dados).

Leitura global:

- **Mais valiosas:** o núcleo CAL (células-dia, diária, mensal, anual), HIS-03 (anomalia mensal), CAL-09/CAL-12 (referência e sazonalidade), QA-02/03/04 (retenção e duplicados) e OBS-02/03 (confiança e filtro): sem elas não há calendário nem forma de justificar o filtro.
- **Úteis mas secundárias:** OBS-04…OBS-10 descrevem as deteções (FRP, noite, tipo, píxel); enriquecem o ecrã de detalhe mas não bloqueiam o MVP.
- **Validação (HAR):** valiosa para a credibilidade da harmonização, mas só no período comum 2018+ e só depois de L1.
- **Questionáveis:** HAR-12 (sem Suomi NPP não há transição a testar), QA-06 (os arquivos anuais são de processamento padrão, o valor seria ~0), QA-07 (mede-se na aplicação, não em arquivos), HIS-10 (a tendência é fortemente afetada pelos degraus de 2002 e 2018).
- **Fora do pipeline:** APP-01…04 (testes de aplicação/utilizadores) e EXT-01…06 (dados externos: área ardida, FWI, humidade, causas).
- **Já feitas, parcialmente, pelo notebook 01:** QA-01 (só `n_bad_time`), OBS-01 (só `n_rows` por sensor-ano em `_ingest_log.csv`), OBS-10 (`pixel_area_km2` por linha; falta a mediana). **Nenhuma está completa.**
- **Adicionais em falta** (não estão no CSV): **ADD-01** satélites ativos por mês (explica o degrau Terra→Aqua); **ADD-02** dias sem deteções globais por sensor (proxy de falhas de cobertura); **ADD-03** duplicados exatos e pontos (0,0); **ADD-04** países sem deteções num ano; **ADD-05** sensibilidade ao filtro de `type`; **ADD-06** efeito do degrau MODIS→união em 2018.

## 5. As 75 métricas (69 do CSV + 6 adicionais) e o seu lote

Tabela gerada a partir do CSV. A coluna **Adequação** é uma triagem inicial (Alta / Média / Baixa) pelos critérios acima.

| ID | Métrica | Prioridade (CSV) | Lote | Estado | Adequação | Nota |
|---|---|---|---|---|---|---|
| CAL-01 | Células-dia com deteções | MVP | L1 | Implementada | Alta | Base de todo o calendário; ver convenções. |
| CAL-02 | Atividade diária | MVP | L1 | Implementada | Alta | Tabela diária de CAL-01 + flag de cobertura desconhecida. |
| CAL-03 | Atividade mensal | MVP | L1 | Implementada | Alta | Flag de mês parcial. |
| CAL-04 | Atividade anual | MVP | L1 | Implementada | Alta | Flag de ano parcial. |
| OBS-01 | Deteções brutas por sensor e satélite | MVP | L1 | Implementada | Alta | Parcial hoje: o notebook 01 só regista `n_rows` por sensor-ano; falta por satélite/país/mês. |
| OBS-02 | Distribuição por classe de confiança | MVP | L1 | Implementada | Alta |  |
| OBS-03 | Deteções após o filtro de qualidade | MVP | L1 | Implementada | Alta |  |
| QA-02 | Taxa de retenção dos filtros | MVP | L1 | Implementada | Alta |  |
| QA-03 | Registos agrupados por célula-dia no mesmo satélite | MVP | L1 | Implementada | Alta | Define-se sobre elegíveis, por satélite. |
| QA-04 | Redundância entre satélites do mesmo sensor | MVP | L1 | Implementada | Alta | Para VIIRS vale 0 por construção (só NOAA-20). |
| OBS-04 | Percentagem de deteções noturnas | Extra | L2 | Implementada | Baixa |  |
| OBS-05 | FRP mediana | Extra | L2 | Implementada | Baixa | FRP utilizável = não nulo e > 0. |
| OBS-06 | Percentil 90 de FRP | Extra | L2 | Implementada | Baixa |  |
| OBS-07 | Pico de FRP | Extra | L2 | Implementada | Baixa | Desempate determinístico. |
| OBS-08 | Disponibilidade de FRP | Extra | L2 | Implementada | Média |  |
| OBS-09 | Distribuição por tipo de fonte térmica | Opcional | L2 | Implementada | Média | Não interpretar `type` do VIIRS sem confirmar a revisão do produto. |
| OBS-10 | Área mediana do píxel de deteção | Opcional | L2 | Implementada | Média | Parcial hoje: `pixel_area_km2` por linha existe; falta a mediana. |
| QA-01 | Taxa de validação do esquema | MVP | L2 | Implementada | Alta | Parcial hoje: só `n_bad_time`; falta a taxa e as regras. Valida-se após a coerção do notebook 01. |
| CAL-05 | Atividade total no período | MVP | L3 | A implementar | Alta | Soma de CAL-04. |
| CAL-06 | Mês-ano de pico | MVP | L3 | A implementar | Alta | Regra de empate a fixar. |
| CAL-07 | Ano de pico | MVP | L3 | A implementar | Alta | Só anos completos. |
| CAL-08 | Média anual de atividade | MVP | L3 | A implementar | Alta | Só anos completos e elegíveis. |
| CAL-09 | Média histórica do mesmo mês | MVP | L3 | A implementar | Alta | Período de referência a fixar. |
| CAL-10 | Dias com deteções | Opcional | L3 | A implementar | Baixa |  |
| CAL-11 | Maior atividade diária | Opcional | L3 | A implementar | Baixa |  |
| CAL-12 | Perfil sazonal mensal | MVP | L3 | A implementar | Alta | Informar nº de anos por mês. |
| HIS-03 | Anomalia mensal absoluta | MVP | L3 | A implementar | Alta | Depende de CAL-09. |
| HIS-04 | Anomalia mensal percentual | Desejável | L3 | A implementar | Média | Média zero => NA. |
| HIS-01 | Mediana histórica mensal | Desejável | L4 | A implementar | Média |  |
| HIS-02 | Faixa histórica mensal | Desejável | L4 | A implementar | Média | Percentis 10/90; indicar tamanho da amostra. |
| HIS-05 | Desvio padronizado mensal (z-score) | Desejável | L4 | A implementar | Média | Amostra pequena => NA. |
| HIS-06 | Percentil histórico da atividade | Desejável | L4 | A implementar | Média |  |
| HIS-07 | Acumulado comparável no ano | Desejável | L4 | A implementar | Média | Exige série diária multianual. |
| HIS-08 | Variação homóloga mensal | Opcional | L4 | A implementar | Baixa |  |
| HIS-09 | Meses acima da faixa histórica | Desejável | L4 | A implementar | Média | Fixar a referência antes de comparar. |
| HIS-10 | Tendência dos totais anuais | Opcional | L4 | A implementar | Baixa | Theil-Sen só com anos completos e comparáveis; atenção ao degrau MODIS 2002 (Aqua) e 2018. |
| ESP-01 | Densidade de atividade | Opcional | L5 | Útil, requer dados extra | Baixa | Precisa da área de cada país (fonte externa simples). |
| ESP-02 | Células distintas com deteções | Desejável | L5 | Útil, depende de L1 | Média |  |
| ESP-03 | Recorrência por célula | Desejável | L5 | Útil, depende de L1 | Média |  |
| ESP-04 | Proporção da grelha com deteções | Opcional | L5 | Útil, requer dados extra | Baixa | Precisa de grelha recortada ao país. |
| ESP-06 | Recorrência interanual por célula | Opcional | L5 | Útil, depende de L1 | Baixa |  |
| QA-05 | Dias com cobertura confirmada | MVP | L5 | Útil, requer dados extra | Alta | Só dá um proxy (dias com algum registo no sensor); cobertura real exige máscaras. |
| HAR-01 | Células-dia coincidentes entre MODIS e VIIRS | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-02 | Índice de sobreposição de Jaccard | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-03 | Meses comparáveis usados na validação | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-04 | Correlação mensal de Pearson | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-05 | Correlação mensal de Spearman | Opcional | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-06 | Fator de ajuste MODIS para VIIRS | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-07 | Intervalo de incerteza do fator de ajuste | Validação | L6 | Útil, depende de L1 | Alta | Só no período comum 2018+. |
| HAR-08 | Erro absoluto médio mensal (MAE) | Validação | L7 | Útil, depende de L1/L6 | Média | Só no período comum 2018+. |
| HAR-09 | Erro relativo absoluto agregado (WAPE) | Validação | L7 | Útil, depende de L1/L6 | Média | Só no período comum 2018+. |
| HAR-10 | Viés mensal médio | Validação | L7 | Útil, depende de L1/L6 | Média | Só no período comum 2018+. |
| HAR-11 | Redução do erro após o ajuste | Validação | L7 | Útil, depende de L1/L6 | Média | Só no período comum 2018+. |
| HAR-12 | Degrau residual na transição entre sensores | Validação | L7 | Rever | Baixa | Sem Suomi NPP não há transição testável em 2012; com MODIS contínuo não há degrau de sensor a testar. |
| HAR-13 | Sensibilidade à dimensão da grelha | Opcional | L7 | Útil, depende de L1/L6 | Baixa | Só no período comum 2018+. |
| HAR-14 | Sensibilidade ao filtro de confiança | Opcional | L7 | Útil, depende de L1/L6 | Baixa | Só no período comum 2018+. |
| APP-01 | Tempo de resposta do calendário | MVP | — | Fora do pipeline | Alta | Teste da aplicação (frontend/backend), medido mais tarde. |
| APP-02 | Tempo de geração e entrega do CSV | MVP | — | Fora do pipeline | Alta | Teste da aplicação (frontend/backend), medido mais tarde. |
| APP-03 | Divergências entre calendário e CSV agregado | MVP | — | Fora do pipeline | Alta | Teste da aplicação (frontend/backend), medido mais tarde. |
| APP-04 | Taxa de conclusão do fluxo principal | Validação | — | Fora do pipeline | Alta | Teste da aplicação (frontend/backend), medido mais tarde. |
| ESP-05 | Frequência de deteções por célula | Opcional | — | Bloqueada | Baixa | Precisa de máscaras de observação por célula e dia, que não temos. |
| EXT-01 | Área ardida | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| EXT-02 | Número de incêndios registados | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| EXT-03 | Distribuição por causa de ignição | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| EXT-04 | Perigo meteorológico diário de incêndio (FWI) | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| EXT-05 | Dias com perigo meteorológico elevado | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| EXT-06 | Humidade relativa em dias de atividade elevada | Fora do MVP | — | Fora do pipeline | Baixa | Dados externos; fora do MVP. |
| QA-06 | Proporção de atividade provisória | Opcional | — | Rever | Baixa | Os arquivos anuais são de processamento padrão; o valor seria ~0. Faz sentido só com dados NRT. |
| QA-07 | Atraso da última observação disponível | Extra | — | Fora do pipeline | Baixa | Mede-se na ingestão/aplicação, não em arquivos históricos. |
| ADD-01 | Satélites ativos por mês | (nova) | L4 | A implementar | Alta | Satélites ativos por mês: explica o degrau Terra->Aqua em 2002. |
| ADD-02 | Dias sem deteções globais por sensor | (nova) | L4 | A implementar | Alta | Dias sem deteções globais por sensor: proxy de falhas de cobertura. |
| ADD-03 | Duplicados exatos e pontos (0,0) | (nova) | L2 | Implementada | Média | Adicional proposta: duplicados exatos e pontos (0,0). |
| ADD-04 | Países sem deteções num ano | (nova) | L2 | Implementada | Média | Adicional proposta: países sem deteções num ano. |
| ADD-05 | Sensibilidade ao filtro de tipo | (nova) | L5 | Adicional proposta | Média | Sensibilidade ao filtro de `type`. |
| ADD-06 | Efeito do degrau MODIS->união em 2018 | (nova) | L5 | Adicional proposta | Alta | Efeito do degrau MODIS->união em 2018. |

## 6. Lotes e regras anti-conflito

| Lote | Quem | Métricas | Depende de |
|---|---|---|---|
| **L1** | Arthur + Claude | CAL-01, CAL-02, CAL-03, CAL-04, OBS-01, OBS-02, OBS-03, QA-02, QA-03, QA-04 | só `processed/` |
| **L2** (entregue) | Colega + Claude | ADD-03, ADD-04, OBS-04, OBS-05, OBS-06, OBS-07, OBS-08, OBS-09, OBS-10, QA-01 | só `processed/` |
| **L3** | Colega + Claude (2.ª ronda) | CAL-05, CAL-06, CAL-07, CAL-08, CAL-09, CAL-10, CAL-11, CAL-12, HIS-03, HIS-04 | saídas `l1_*` do L1 (já no `main`) |
| **L4** | Arthur + Claude | ADD-01, ADD-02, HIS-01, HIS-02, HIS-05, HIS-06, HIS-07, HIS-08, HIS-09, HIS-10 | saídas `l1_*` do L1 (já no `main`) |
| L5 | depois do merge | ADD-05, ADD-06, ESP-01, ESP-02, ESP-03, ESP-04, ESP-06, QA-05 | L1 (+ dados extra em alguns) |
| L6 | depois do merge | HAR-01, HAR-02, HAR-03, HAR-04, HAR-05, HAR-06, HAR-07 | L1, período 2018+ |
| L7 | depois do merge | HAR-08, HAR-09, HAR-10, HAR-11, HAR-12, HAR-13, HAR-14 | L1/L6, período 2018+ |
| — | não se implementam já | APP-01, APP-02, APP-03, APP-04, ESP-05, EXT-01, EXT-02, EXT-03, EXT-04, EXT-05, EXT-06, QA-06, QA-07 | — |

**L1 e L2 foram independentes e correram em paralelo** (já estão no `main`).

**L3 e L4 também são independentes entre si e correm em paralelo:** ambos leem apenas as tabelas `metrics/l1_*.parquet` e escrevem as suas (`l3_*` / `l4_*`); **nenhum lê saídas do outro**. A partir daqui o L1 é só uma fonte de dados, e quem implementa o L3 ou o L4 não precisa de ler o código do L1 nem do L2.

### Ficheiros reservados por lote (só cria/edita os do seu lote)

| | L1 (Arthur) | L2 (colega) | L3 (colega) | L4 (Arthur) |
|---|---|---|---|---|
| Módulos | `data/pipeline/metrics/common.py`, `counts.py`, `calendar_metrics.py` | `data/pipeline/metrics/detections.py`, `ingestion_qa.py` | `data/pipeline/metrics/calendar_summary.py`, `history_anomaly.py` | `data/pipeline/metrics/history_pool.py`, `history_distribution.py`, `history_cumulative.py`, `coverage_meta.py` |
| Testes | `data/pipeline/tests/test_common.py`, `test_counts.py`, `test_calendar_metrics.py`, `test_integration_sample_lote1.py`, `helpers_lote1.py` | `data/pipeline/tests/test_detections.py`, `test_ingestion_qa.py` | `data/pipeline/tests/test_calendar_summary.py`, `test_history_anomaly.py` (e `helpers_lote3.py` se precisar) | `data/pipeline/tests/test_history_pool.py`, `test_history_distribution.py`, `test_history_cumulative.py`, `test_coverage_meta.py`, `helpers_lote4.py` |
| Notebook | `data/pipeline/notebooks/02_metrics_lote1.ipynb` | `data/pipeline/notebooks/03_metrics_lote2.ipynb` | `data/pipeline/notebooks/04_metrics_lote3.ipynb` | `data/pipeline/notebooks/05_metrics_lote4.ipynb` |
| Relatório | `spec/lotes/lote_1.md` | `spec/lotes/lote_2.md` | `spec/lotes/lote_3.md` | `spec/lotes/lote_4.md` |
| Saídas em `metrics/` | `l1_*.parquet`, `_log_lote1.csv` | `l2_*.parquet`, `_log_lote2.csv` | `l3_*.parquet`, `_log_lote3.csv` | `l4_*.parquet`, `_log_lote4.csv` |
| Onde se faz push | `main` | `main` | `main` | `main` |

`data/pipeline/metrics/__init__.py` já existe (vazio): **não o altere**.

**Ficheiros que ninguém edita** (evitam conflitos de merge): `requirements.txt`, `.gitignore`, `data/README.md`, `data/MANIFEST.md`, `data/pipeline/notebooks/01_ingest_harmonize.ipynb`, `data/pipeline/notebooks/02_metrics.ipynb`, `spec/metricas_modis_viirs.csv`, este documento, `data/pipeline/tests/conftest.py`, `data/pipeline/pytest.ini`. O Arthur atualiza os partilhados depois do merge. `data/pipeline/metrics/__init__.py` pode ser criado por ambos **vazio** (ficheiros iguais fundem sem conflito).

Regras adicionais:

- **Sem `conftest.py` nem `pytest.ini` nem dependências novas.** Cada ficheiro de teste constrói os seus próprios dados com um auxiliar local (`helpers`) no próprio ficheiro ou em `data/pipeline/tests/helpers_lote<N>.py`. Só `pandas`, `numpy`, `pytest` (instale `pytest` à mão se faltar).
- **Como correr os testes:** `cd data/pipeline && python -m pytest tests -q`. Assim `import metrics...` funciona sem configuração.
- Não use `calendar.py` como nome de módulo (colide com a biblioteca padrão); por isso é `calendar_metrics.py`.
- **Push direto para `main`, sem branches:** os dois lotes fazem push para `main`. Como os ficheiros são disjuntos, não há conflitos se cada um respeitar a lista acima. Regras: (1) **antes de cada push**, `git pull --rebase origin main`; (2) cada commit só contém ficheiros do **seu** lote (`git status` antes de `git add`, e nunca `git add -A` ou `git add .`); (3) **nunca** `git push --force` nem reescrever histórico; (4) se o `pull --rebase` der conflito, **pare e avise**: significa que alguém tocou num ficheiro que não era seu; não resolva às cegas.
- **Nunca commitar dados** (`data/` está no `.gitignore`).
- Commits curtos e descritivos (skill `/commit-message`); antes de dizer "feito", correr a skill `/review-gate`. As skills estão em `.claude/skills/`.
- No fim, escrever `spec/lotes/lote_<N>.md`: métricas feitas, decisões e desvios, nº de testes, como correr, limitações. É o que o Arthur lê antes do merge.

## 7. Especificação do Lote 2 (colega)

### 7.1 Contrato das funções

Cada métrica é **uma função pura**: `def nome(df: pd.DataFrame) -> pd.DataFrame`.

- Entrada: DataFrame com o esquema da secção 2 (um ou vários anos, vários países). **Sem I/O**: nada de Drive, ficheiros ou rede.
- Saída: tabela "tidy" com as colunas-chave primeiro e depois os valores, ordenada e com índice limpo.
- Entrada vazia ⇒ saída vazia **com as mesmas colunas e dtypes razoáveis** (nunca erro).
- Colunas em falta no `df` ⇒ `ValueError` com mensagem a dizer quais.
- Determinística e **invariante à ordem das linhas** da entrada.
- Chave padrão: **`country, year, instrument, satellite`**, com `year` = ano de `acq_date`. Linhas com `acq_date` inválida ficam fora (mas contam em QA-01).
- Constantes (`GRID_DEG`, confiança elegível…) como parâmetros com o valor por defeito da secção 3.

### 7.2 Métricas

Todas as tabelas de saída gravam-se em `metrics/` com o prefixo `l2_`. "Base" = linhas sobre as quais se calcula.

**OBS-04 · % de deteções noturnas → `l2_obs04_night_pct`** · `detections.obs04_night_pct`
- Base: elegíveis. Colunas: chave + `n_day`, `n_night`, `n_daynight_unknown`, `pct_night`.
- `pct_night = 100·n_night / (n_day + n_night)`; NA se o denominador for 0. `daynight` fora de `D`/`N` conta em `n_daynight_unknown` e fica fora do denominador.

**OBS-05 · FRP mediana → `l2_obs05_frp_median`** · `detections.obs05_frp_median`
- Base: elegíveis com **FRP utilizável** (`frp` não nulo e `> 0`). Colunas: chave + `n_frp_usable`, `frp_median` (MW). NA se `n_frp_usable == 0`.

**OBS-06 · Percentil 90 de FRP → `l2_obs06_frp_p90`** · `detections.obs06_frp_p90`
- Mesma base. Colunas: chave + `n_frp_usable`, `frp_p90`. Percentil com interpolação linear (`numpy.percentile(..., method="linear")`). NA se não houver observações.

**OBS-07 · Pico de FRP → `l2_obs07_frp_peak`** · `detections.obs07_frp_peak`
- Mesma base. Uma linha por chave: `frp_max`, `peak_latitude`, `peak_longitude`, `peak_acq_date`, `peak_acq_time`, `peak_datetime_utc`.
- Empate no máximo: escolhe-se a menor `(acq_date, acq_time, latitude, longitude)`. Grupo sem FRP utilizável não aparece.

**OBS-08 · Disponibilidade de FRP → `l2_obs08_frp_availability`** · `detections.obs08_frp_availability`
- Base: elegíveis. Colunas: chave + `n_eligible`, `n_frp_usable` (`frp > 0`), `n_frp_null` (`frp` nulo), `n_frp_zero` (`frp == 0`), `n_frp_negative` (`frp < 0`, inválido), `pct_frp_usable = 100·n_frp_usable/n_eligible`.
- Invariante testada: `n_frp_usable + n_frp_null + n_frp_zero + n_frp_negative == n_eligible`. Grupos sem elegíveis não aparecem na tabela.

**OBS-09 · Distribuição por tipo de fonte térmica → `l2_obs09_type_distribution`** · `detections.obs09_type_distribution`
- Base: **todas as linhas** (sem filtro; o objetivo é ver o que o filtro remove). Chave: `country, year, instrument, satellite, version, type_label`, com `type_label ∈ {"0","1","2","3","unknown"}` (NA ⇒ `unknown`; qualquer outro valor também ⇒ `unknown`). Colunas: `n`, `pct` (percentagem dentro de `country, year, instrument, satellite, version`; soma 100).

**OBS-10 · Área mediana do píxel → `l2_obs10_pixel_area_median`** · `detections.obs10_pixel_area_median`
- Base: todas as linhas com `pixel_area_km2` finito e `> 0`. Colunas: chave + `n_area`, `pixel_area_median_km2`.

**QA-01 · Taxa de validação do esquema → `l2_qa01_schema_validation`** · `ingestion_qa.qa01_schema_validation`
- Base: todas as linhas do `df` (que já passaram a coerção do notebook 01: isto valida o que ficou, não o que o ingest descartou; registe esta limitação).
- Chave: `country, instrument` (`instrument` NA ⇒ `"unknown"`). O **notebook** acrescenta `year` a partir do nome do Parquet antes de concatenar.
- Uma linha é **válida** se cumprir **todas** as regras: `coords` (lat/lon finitas, |lat|≤90, |lon|≤180) · `date` (`acq_date` com formato `YYYY-MM-DD` e data real) · `time` (`acq_time` com 4 dígitos, hh<24, mm<60) · `instrument` ∈ {MODIS, VIIRS} · `satellite` não nulo e não vazio · `daynight` ∈ {D, N} · `confidence` (`confidence_raw` não nulo).
- Colunas: chave + `n_rows`, `n_valid`, `n_invalid`, `pct_valid`, `n_fail_coords`, `n_fail_date`, `n_fail_time`, `n_fail_instrument`, `n_fail_satellite`, `n_fail_daynight`, `n_fail_confidence`. Uma linha pode falhar várias regras (a soma dos `n_fail_*` pode exceder `n_invalid`); `n_invalid` conta linhas com **pelo menos** uma falha.

**ADD-03 · Duplicados exatos e pontos (0,0) → `l2_add03_duplicates`** · `ingestion_qa.add03_duplicates`
- Chave padrão. Colunas: `n_rows`, `n_dup_rows`, `pct_dup`, `n_null_island`.
- `n_dup_rows = n_rows − nº de combinações distintas de (latitude, longitude, acq_date, acq_time)` dentro do grupo. `n_null_island` = linhas com `latitude == 0` e `longitude == 0`.

**ADD-04 · Países sem deteções num ano → `l2_add04_zero_detection_countries`** · `ingestion_qa.add04_zero_detection_countries(counts)`
- Entrada diferente: `counts` com colunas `country, instrument, year, n_rows` (o notebook constrói-a somando `n_rows` de `l2_add03_duplicates` por `country, instrument, year`, depois de processar todos os anos).
- Esperado: para cada `instrument`, os países que aparecem em **algum** ano e os anos desde o mínimo ao máximo desse instrumento. Saída: `instrument, year, country, n_years_with_data` para cada combinação esperada **sem linhas** (ou `n_rows == 0`).
- Limitação a registar: a partir de `processed/` não se distingue "país sem deteções" de "ficheiro em falta"; o `n_csv` por sensor-ano está em `processed/_ingest_log.csv`.

## 7B. Convenções de histórico (comuns ao Lote 3 e ao Lote 4)

L3 e L4 **não leem `processed/`**: leem as tabelas do L1 que já estão em `metrics/` (Drive) e no `main`. São independentes entre si e correm em paralelo; **nenhum lê saídas do outro** (L3 → `l3_*`, L4 → `l4_*`). Nos testes usam-se DataFrames sintéticos com os esquemas abaixo, nunca dados reais.

### Esquemas de entrada (tabelas `l1_*`)
| Tabela | Colunas (tipo) | Notas |
|---|---|---|
| `l1_cal_monthly` | `country` (texto), `year` (int), `month` (int 1–12), `series` (`modis`/`viirs`/`combined`), `cell_days` (int), `partial` (bool), `n_unknown_days` (int) | **densa** dentro do intervalo de cada série: meses sem atividade têm `cell_days = 0` |
| `l1_cal_annual` | `country`, `year`, `series`, `cell_days`, `partial` (bool), `n_unknown_days` | soma dos meses; `partial` se falta algum mês ou algum mês é parcial |
| `l1_cal_daily` | `country`, `date` (datetime), `series`, `n_cells` (int) | **só dias com atividade** (um dia sem deteções não tem linha) |
| `l1_cal_coverage` | `instrument` (`MODIS`/`VIIRS`), `date` (datetime), `n_rows_global` (int) | calendário completo de cada sensor; `n_rows_global == 0` ⇒ cobertura desconhecida |
| `l1_obs01_raw_counts` | `country`, `year`, `month`, `instrument`, `satellite`, `n_raw` (int) | deteções brutas |

### Constantes e regras congeladas
| Nome | Valor | Significado |
|---|---|---|
| `MAX_UNKNOWN_DAYS` | `0` | um mês/ano só é **válido** se não for parcial e tiver no máximo estes dias de cobertura desconhecida |
| `MIN_REF_YEARS` | `5` | mínimo de anos na referência; abaixo disso a estatística é **NA** (a linha existe e `n_ref_years` informa) |
| `MIN_TREND_YEARS` | `8` | mínimo de anos para a tendência (HIS-10) |

Referência de implementação da validade (copiar para o seu módulo; é uma cópia privada, como no L2):

```python
def valid_mask(table, max_unknown_days=0):
    """Mes ou ano valido: nao parcial e com no maximo `max_unknown_days` dias de cobertura desconhecida."""
    return (~table["partial"].astype(bool)) & (table["n_unknown_days"] <= max_unknown_days)
```

### Pool de referência
- **Pool** de `(country, series, month)` = valores `cell_days` dos meses **válidos** desse mês civil, um por ano, nos anos do intervalo de referência `[ref_start, ref_end]` (inclusivos; `None` = sem limite).
- **Referência fixa** (CAL-09, CAL-12, HIS-01, HIS-02, HIS-09): usa o pool inteiro.
- **Referência sem o ano avaliado** (HIS-03/04/05/06 e HIS-07): para a linha do ano `Y`, usa o pool **sem o ano `Y`** (leave-one-out). Isto evita que o próprio mês avaliado contamine a referência.
- Se o pool tiver menos de `MIN_REF_YEARS` valores, a estatística é NA.
- Linha avaliada **inválida** (parcial ou com dias desconhecidos): as colunas derivadas ficam NA, `valid_month = False`, e a linha continua na tabela.
- **Estatísticas:** média aritmética; mediana; desvio-padrão **amostral** (`ddof=1`); percentis por interpolação linear (`numpy.percentile(..., method="linear")`).
- Tabelas de saída: sem índice, ordenadas pelas colunas-chave, `year`/`month` inteiros, `series` sempre presente, datas como `datetime`.
- Uma série (`country`, `series`) com menos de 1 valor válido aparece com NA, nunca desaparece em silêncio (salvo indicação em contrário na métrica).

Exemplo trabalhado (use-o como teste literal): mês 3 de um país/série com 6 anos válidos de valores `[10, 20, 30, 40, 50, 60]` nos anos 2001…2006. Referência fixa: média 35, mediana 35, `n_ref_years = 6`. Para o ano 2003 (valor 30) a referência sem o ano avaliado é `[10, 20, 40, 50, 60]`: média 36, ⇒ `anomaly_abs = −6` e `anomaly_pct = −16,666…`. Para 2001 (valor 10): média dos restantes 40, `anomaly_abs = −30`; para 2006 (valor 60): média dos restantes 30, `anomaly_abs = +30`.
Invariante: se todas as linhas desse pool são válidas, **a soma das anomalias absolutas leave-one-out é 0**.

---

## 7C. Especificação do Lote 3 (colega, 2.ª ronda)

Métricas: **CAL-05, CAL-06, CAL-07, CAL-08, CAL-09, CAL-10, CAL-11, CAL-12, HIS-03, HIS-04** (10).
Contrato das funções, ficheiros e testes: como em 7.1 e nas secções 6 e 9. Leia a linha de cada métrica no CSV, mas **o que está aqui prevalece**. Os parâmetros `ref_start`, `ref_end`, `min_ref_years`, `max_unknown_days` têm os valores da secção 7B por defeito.

**Ficheiros reservados do L3** (ver tabela da secção 6): `data/pipeline/metrics/calendar_summary.py` (CAL-05…CAL-12), `data/pipeline/metrics/history_anomaly.py` (HIS-03, HIS-04), `data/pipeline/tests/test_calendar_summary.py`, `data/pipeline/tests/test_history_anomaly.py`, `data/pipeline/notebooks/04_metrics_lote3.ipynb`, `spec/lotes/lote_3.md`, saídas `l3_*.parquet` e `_log_lote3.csv`.

| Métrica | Função (módulo) · tabela de saída | Entrada | Regra e colunas |
|---|---|---|---|
| **CAL-05** Atividade total no período | `cal05_total_period(monthly, start=None, end=None)` (`calendar_summary`) · `l3_cal05_total_period` | `l1_cal_monthly` | `start`/`end` são `(ano, mês)` inclusivos; `None` = primeiro/último mês de cada `(country, series)`. Colunas: `country, series, start_year, start_month, end_year, end_month, cell_days` (soma, **incluindo** meses parciais), `n_months`, `n_partial_months`, `n_unknown_days`. Grupos sem meses no intervalo não aparecem |
| **CAL-06** Mês-ano de pico | `cal06_peak_month(monthly, max_unknown_days=0)` · `l3_cal06_peak_month` | `l1_cal_monthly` | Máximo de `cell_days` entre os meses **válidos**; empate ⇒ o menor `(year, month)`. Colunas: `country, series, year, month, cell_days, n_valid_months`. Sem meses válidos ⇒ uma linha com `year, month, cell_days` NA e `n_valid_months = 0` |
| **CAL-07** Ano de pico | `cal07_peak_year(annual, max_unknown_days=0)` · `l3_cal07_peak_year` | `l1_cal_annual` | Igual a CAL-06 sobre anos **válidos** (só anos completos). Colunas: `country, series, year, cell_days, n_valid_years` |
| **CAL-08** Média anual | `cal08_annual_mean(annual, ref_start=None, ref_end=None, max_unknown_days=0)` · `l3_cal08_annual_mean` | `l1_cal_annual` | Média de `cell_days` dos anos válidos dentro de `[ref_start, ref_end]`. Colunas: `country, series, n_years, mean_cell_days, first_year, last_year, years_included` (texto `"2001,2002,2003"`, ordenado). `n_years = 0` ⇒ média NA, `years_included = ""`, `first_year/last_year` NA |
| **CAL-09** Média histórica do mesmo mês | `cal09_monthly_mean(monthly, ref_start=None, ref_end=None, min_ref_years=5, max_unknown_days=0)` · `l3_cal09_monthly_mean` | `l1_cal_monthly` | **Referência fixa** (sem leave-one-out). 12 linhas (`month` 1–12) por `(country, series)` existente. Colunas: `country, series, month, n_years, mean_cell_days` (NA se `n_years < min_ref_years`) |
| **CAL-10** Dias com deteções | `cal10_active_days(daily, monthly)` · `l3_cal10_active_days` | `l1_cal_daily` + `l1_cal_monthly` | Usa `monthly` como **esqueleto** (uma linha por país-série-mês, 0 se não houver dias ativos). Colunas: `country, series, year, month, active_days` (datas distintas com `n_cells ≥ 1`), `n_days_in_month` (dias do calendário, ano bissexto incluído). Invariante: `active_days ≤ n_days_in_month` |
| **CAL-11** Maior atividade diária | `cal11_peak_day(daily)` · `l3_cal11_peak_day` | `l1_cal_daily` | Por `(country, series, year)`: dia com maior `n_cells`; empate ⇒ a data mais antiga. Colunas: `country, series, year, date, n_cells`. Anos sem atividade não aparecem. O pico de todo o período obtém-se depois como o máximo entre anos |
| **CAL-12** Perfil sazonal | `cal12_seasonal_profile(cal09)` · `l3_cal12_seasonal_profile` | saída de `cal09_monthly_mean` | Colunas: `country, series, month, n_years, mean_cell_days, share_pct` (`100·mean/Σ(mean dos 12 meses)`; NA se algum dos 12 meses tiver média NA ou se a soma for 0) e `is_peak_month` (bool; só o mês de maior média, empate ⇒ o menor mês; médias NA ⇒ False) |
| **HIS-03** Anomalia mensal absoluta | `his03_anomaly_abs(monthly, ref_start=None, ref_end=None, min_ref_years=5, max_unknown_days=0)` (`history_anomaly`) · `l3_his03_anomaly_abs` | `l1_cal_monthly` | **Referência sem o ano avaliado.** Uma linha por linha de entrada. Colunas: `country, series, year, month, cell_days, valid_month, n_ref_years, ref_mean, anomaly_abs` (`cell_days − ref_mean`; positivo = acima da referência). NA se `valid_month` é False ou `n_ref_years < min_ref_years` |
| **HIS-04** Anomalia percentual | `his04_anomaly_pct(his03)` · `l3_his04_anomaly_pct` | saída de `his03_anomaly_abs` | Colunas: `country, series, year, month, cell_days, ref_mean, anomaly_abs, anomaly_pct` (`100·anomaly_abs/ref_mean`; NA se `ref_mean` é NA ou 0 ou a anomalia é NA) |

**Casos de teste mínimos específicos do L3** (além dos 6 pontos da secção 9):
- CAL-06: dois meses empatados no máximo escolhem o mais antigo; um mês parcial com valor maior **não** ganha; todos inválidos ⇒ linha NA com `n_valid_months = 0`.
- CAL-08: anos `[100, 200, 300]` válidos + um ano parcial de valor 999 ⇒ média 200, `years_included = "2001,2002,2003"` (o parcial fica fora).
- CAL-09/HIS-03: o exemplo trabalhado da secção 7B (literal), mais: um mês com `n_unknown_days = 1` fica fora do pool; `n_ref_years = 4` ⇒ médias NA; com `ref_start/ref_end` o pool encolhe mas as linhas avaliadas continuam todas presentes.
- HIS-03: a soma das anomalias leave-one-out de um pool completo é 0 (tolerância `1e-9`).
- CAL-10: dia 29 de fevereiro num ano bissexto (`n_days_in_month = 29`); mês sem dias ativos aparece com 0.
- CAL-12: `share_pct` dos 12 meses soma 100; média zero em todos os meses ⇒ `share_pct` NA.
- Entradas com várias séries e vários países: os resultados de um grupo **não** dependem dos outros.

**Notebook `04_metrics_lote3.ipynb`:** monta a Drive, `git clone`/`pull` do repo, `sys.path.insert(0, ".../data/pipeline")`, lê `metrics/l1_cal_monthly.parquet`, `l1_cal_annual.parquet` e `l1_cal_daily.parquet`, aplica as funções, grava `metrics/l3_*.parquet` (escrita `.tmp` + rename) e `metrics/_log_lote3.csv` (parâmetros usados: `ref_start`, `ref_end`, `min_ref_years`, `max_unknown_days`, commit do repo, nº de linhas por tabela). Falha com mensagem clara se alguma tabela `l1_*` não existir (é preciso ter corrido o notebook 02 antes). As tabelas são pequenas: não precisa de ciclo por ano.

---

## 7D. Especificação do Lote 4 (Arthur + Claude)

Métricas: **HIS-01, HIS-02, HIS-05, HIS-06, HIS-07, HIS-08, HIS-09, HIS-10, ADD-01, ADD-02** (10).
**Ficheiros reservados do L4:** `data/pipeline/metrics/history_pool.py` (pool de referência comum: `valid_mask`, `reference_fixed`, `reference_loo`), `data/pipeline/metrics/history_distribution.py` (HIS-01, HIS-02, HIS-05, HIS-06, HIS-09), `history_cumulative.py` (HIS-07, HIS-08, HIS-10), `coverage_meta.py` (ADD-01, ADD-02); testes `test_history_distribution.py`, `test_history_cumulative.py`, `test_coverage_meta.py`; notebook `05_metrics_lote4.ipynb`; relatório `spec/lotes/lote_4.md`; saídas `l4_*.parquet` e `_log_lote4.csv`.

| Métrica | Tabela | Entrada | Regra e colunas |
|---|---|---|---|
| **HIS-01** Mediana histórica | `l4_his01_hist_median` | `l1_cal_monthly` | Referência fixa. `country, series, month, n_ref_years, median_cell_days` (NA se `n_ref_years < 5`) |
| **HIS-02** Faixa histórica | `l4_his02_hist_band` | `l1_cal_monthly` | Referência fixa. `country, series, month, n_ref_years, p10, p90` (percentis lineares; NA se `n_ref_years < 5`) |
| **HIS-05** z-score mensal | `l4_his05_zscore` | `l1_cal_monthly` | Sem o ano avaliado. `country, series, year, month, cell_days, valid_month, n_ref_years, ref_mean, ref_std, zscore` (`(cell_days − ref_mean)/ref_std`, `ddof=1`; NA se `ref_std == 0` ou amostra insuficiente ou mês inválido) |
| **HIS-06** Percentil histórico | `l4_his06_percentile` | `l1_cal_monthly` | Sem o ano avaliado. `…, valid_month, n_ref_years, percentile` = `100·(#pool < x + 0,5·#pool == x)/n_pool` (NA como acima) |
| **HIS-07** Acumulado comparável no ano | `l4_his07_ytd` | `l1_cal_monthly` | Por `(country, series, year, month)`: `ytd_cell_days` = soma de janeiro até esse mês; `comparable` = todos esses meses são válidos; referência = média do `ytd` do mesmo mês nos **outros** anos comparáveis (`n_ref_years`, `ref_ytd_mean`), `ytd_diff` = `ytd − ref_ytd_mean`. NA se não comparável ou amostra insuficiente. Só cortes ao fim de cada mês |
| **HIS-08** Variação homóloga | `l4_his08_yoy` | `l1_cal_monthly` | `…, cell_days, prev_cell_days, diff_abs, yoy_pct`. Exige o mesmo mês do ano anterior presente e **ambos válidos**; `yoy_pct = 100·diff_abs/prev_cell_days`, NA se `prev_cell_days == 0` (a `diff_abs` continua preenchida) |
| **HIS-09** Meses acima da faixa | `l4_his09_months_above` | `l1_cal_monthly` | **Referência fixa** (HIS-02 com `ref_start/ref_end`), por `(country, series, year)`: `n_months_evaluated` (válidos com p90 definido), `n_months_above` (`cell_days > p90`, estrito), `months_above` (texto `"3,4"`). O ano avaliado pode estar dentro da referência (fixa por definição); registar no relatório |
| **HIS-10** Tendência anual | `l4_his10_trend` | `l1_cal_annual` | Por `(country, series)`, só anos válidos, `n_years ≥ 8`. Declive de Theil-Sen = mediana dos declives de todos os pares de anos; `intercept = mediana(y − declive·x)`. Colunas: `n_years, first_year, last_year, slope_per_year, intercept, slope_p025, slope_p975` (percentis 2,5 e 97,5 dos declives dos pares: dispersão, **não** um intervalo de confiança formal; dizê-lo no relatório). NA se `n_years < 8` |
| **ADD-01** Satélites ativos por mês | `l4_add01_active_satellites` | `l1_obs01_raw_counts` | Global (todos os países somados): `instrument, year, month, n_satellites` (satélites com `n_raw > 0`), `satellites` (texto ordenado `"Aqua,Terra"`) |
| **ADD-02** Dias sem deteções globais | `l4_add02_zero_days` | `l1_cal_coverage` | `instrument, year, month, n_days` (dias do calendário no intervalo do sensor), `n_zero_days` (`n_rows_global == 0`), `pct_zero_days` |

Notebook `05_metrics_lote4.ipynb`: mesmo padrão do notebook do L3, lendo `l1_cal_monthly`, `l1_cal_annual`, `l1_obs01_raw_counts` e `l1_cal_coverage`.

---

## 8. Especificação resumida do Lote 1 (Arthur), para o mesmo nível de rigor

Chave `country, year[, month], instrument, satellite` como no lote 2. Tabelas `l1_*` (alinhadas com o implementado; relatório em `spec/lotes/lote_1.md`):

| Métrica | Tabela | Colunas | Regra |
|---|---|---|---|
| OBS-01 | `l1_obs01_raw_counts` | `country, year, month, instrument, satellite, n_raw` | linhas antes do filtro |
| OBS-02 | `l1_obs02_confidence_dist` | `country, year, instrument, confidence_class, n, pct` | classe NA ⇒ `unknown`; `pct` soma 100 por grupo |
| OBS-03 | `l1_obs03_filtered_counts` | `…, n_eligible` | elegíveis |
| QA-02 | `l1_qa02_retention` | `…, n_raw, n_eligible, pct_retained` | `n_eligible/n_raw`; NA se `n_raw==0` |
| QA-03 | `l1_qa03_cellday_grouped` | `country, year, instrument, satellite, n_eligible, n_cell_days, n_grouped` | `n_grouped = n_eligible − n_cell_days` por satélite |
| QA-04 | `l1_qa04_redundancy` | `country, year, instrument, sum_cell_days_by_satellite, n_cell_days_union, n_redundant` | `Σ células-dia por satélite − união` |
| CAL-01/02 | `l1_cal_daily` | `country, date, series, n_cells` | células ativas por dia (elegíveis, só dias com atividade); `series ∈ {modis, viirs, combined}`; `combined` = união |
| (apoio) | `l1_cal_coverage` | `instrument, date, n_rows_global` | calendário completo `[primeira, última]` de cada sensor; `n_rows_global == 0` ⇒ cobertura desconhecida |
| CAL-03 | `l1_cal_monthly` | `country, year, month, series, cell_days, partial, n_unknown_days` | soma de `l1_cal_daily`; **denso** (meses a 0 aparecem) dentro do intervalo da série |
| CAL-04 | `l1_cal_annual` | `country, year, series, cell_days, partial, n_unknown_days` | soma de `l1_cal_monthly`; `partial` se falta algum mês ou algum mês é parcial |

## 9. Protocolo de testes (obrigatório, igual nos dois lados)

Princípios (skill `/test-design`): **chamar o código real** (nunca reimplementar a fórmula no teste), asserções **exatas**, valores esperados **calculados à mão** e escritos no teste, cobertura com sentido (não por volume).

Para **cada métrica**, no mínimo:

1. **Exemplo manual:** DataFrame pequeno (3–10 linhas) onde o resultado esperado foi calculado à mão e está escrito no teste (`assert_frame_equal` ou comparação exata de valores).
2. **Entrada vazia:** devolve tabela vazia com as colunas certas.
3. **Casos-limite da própria métrica:** denominador zero ⇒ NA; tudo NA; um só elemento; empates (OBS-07); valores 0/negativos/nulos (FRP); `type` e `confidence_class` NA.
4. **Invariância à ordem:** embaralhar as linhas não muda o resultado.
5. **Oráculo independente ou invariante:** comparar com um cálculo em Python puro (dicionários/conjuntos, algoritmo diferente do pandas) sobre dados aleatórios com semente fixa, **ou** testar invariantes (somas que têm de bater, `pct` que soma 100, `n_valid + n_invalid == n_rows`).
6. **Prova de que o teste deteta o erro (vermelho→verde):** estrague temporariamente a regra principal (ex. trocar `> 0` por `>= 0`, ou tirar o filtro elegível) e confirme que **pelo menos um teste falha**; reponha. Registe no relatório que o fez.

Além disso:
- Dados **sintéticos** nos testes; sem dependência de dados reais. Teste de integração opcional com `modis_2000` (marcado `skip` se o ficheiro não existir; esperado: 261 363 linhas, 163 países).
- Os dtypes dos DataFrames de teste devem imitar o notebook 01 (`type` Int8, `version`/`acq_time`/`confidence_*` como texto).
- Os testes têm de passar com `cd data/pipeline && python -m pytest tests -q`.
- Sem `print` de depuração, sem testes que dependem da ordem de execução ou do relógio.

## 10. Notebook de lote (padrão)

`data/pipeline/notebooks/0N_metrics_lote<N>.ipynb`, sem outputs gravados, com estas células:

1. **Setup:** `drive.mount`, `ROOT = /content/drive/MyDrive/Sprinklers`, `git clone https://github.com/Rui-Martins31/NASA_Space_Apps_2026_Sprinklers` para `/content/repo` (ou `git pull` se já existir), `sys.path.insert(0, "/content/repo/data/pipeline")`. Se o repo for privado, usar um token (variável secreta do Colab) e não o escrever no notebook.
2. **Configuração:** `SENSORS`, `YEARS`, `FORCE` (como no notebook 01), `PROCESSED`, `METRICS`.
3. **Ciclo por ano:** ler `processed/<sensor>_<ano>.parquet` **só com as colunas necessárias** (`pd.read_parquet(..., columns=[...])`), `category` nas strings repetidas, aplicar as funções do módulo, guardar o resultado parcial; **saltar** se a saída desse ano já existir e `FORCE` for falso.
4. **Consolidação:** concatenar os anos, ordenar, gravar `metrics/<tabela>.parquet` (escrever para `.tmp` e renomear no fim).
5. **Log:** `metrics/_log_lote<N>.csv` com métrica, parâmetros usados (grelha, filtro), anos, linhas de saída, data da execução.
6. **Verificação rápida:** imprimir dtypes e `head`, e as invariantes principais (somas, `pct`).

**Lotes 3 e 4:** não há ciclo por ano; o notebook lê as tabelas `metrics/l1_*.parquet` (pequenas), aplica as funções e grava `l3_*`/`l4_*` e o log (ver 7C e 7D). Falha com mensagem clara se faltar alguma tabela `l1_*`.

O VIIRS é pesado (cerca de 3 GB comprimidos no raw): processe ano a ano, leia poucas colunas e ative High-RAM se faltar memória.

## 11. Poupar tokens, checklist e prompt-modelo

**Poupar tokens**
- Trabalhe por métrica, não por categoria. Leia só a linha do CSV de cada métrica.
- Escreva primeiro os testes (exemplo manual calculado à mão), depois a função mínima que os faz passar.
- Não leia nem descarregue os dados reais; use fixtures sintéticas. Não reimprima ficheiros grandes.
- Uma execução de `pytest -q` por ciclo; mostre só falhas.

**Checklist "feito" (por lote)**
- [ ] Todas as métricas do lote têm função, testes (os 6 pontos da secção 9) e tabela de saída com as colunas da especificação.
- [ ] `cd data/pipeline && python -m pytest tests -q` verde; o número de testes está no relatório.
- [ ] Provou o vermelho→verde em cada métrica.
- [ ] Notebook do lote sem outputs, validado por `ast.parse` das células; sem caminhos absolutos do seu computador.
- [ ] `spec/lotes/lote_<N>.md` escrito (métricas, decisões/desvios, limitações, como correr).
- [ ] Nenhum ficheiro reservado a outro lote ou partilhado foi alterado; nenhum dado no Git.
- [ ] `/review-gate` corrido.

**Prompt-modelo genérico** (substitua `N`, a secção e os ficheiros do seu lote, tirados da tabela da secção 6)

> Vais implementar o **Lote N** de métricas do projeto Sprinklers. Lê `spec/metodologia_metricas.md` inteiro uma vez. Segue **exatamente** a secção 3 (convenções congeladas), a especificação do teu lote (L2: secção 7; L3: secções 7B e 7C; L4: secção 7D), a secção 6 (ficheiros reservados: só podes criar os ficheiros do teu lote que estão na tabela) e o protocolo de testes da secção 9. Trabalha direto em `main`: antes de cada push faz `git pull --rebase origin main`, nunca uses `git add -A`/`git add .` (adiciona só os ficheiros do teu lote) e nunca faças `push --force`; se houver conflito no rebase, pára e avisa. Para cada métrica, lê só a sua linha em `spec/metricas_modis_viirs.csv`; o que a especificação do lote diz prevalece sobre o CSV. Escreve primeiro os testes (exemplo calculado à mão), depois a função. Não leias nem descarregues dados reais: usa DataFrames sintéticos com os esquemas do documento. Não instales nem alteres dependências partilhadas. Quando houver ambiguidade, aplica o que o documento diz e regista a dúvida no relatório do lote. No fim corre `/review-gate` e apresenta o resumo do relatório.

**Prompt pronto a colar para o Lote 3**

> Vais implementar o **Lote 3** de métricas do projeto Sprinklers (CAL-05, CAL-06, CAL-07, CAL-08, CAL-09, CAL-10, CAL-11, CAL-12, HIS-03, HIS-04). Faz `git pull` primeiro: o código está agora em `data/pipeline/`. Lê `spec/metodologia_metricas.md` inteiro uma vez. Segue **exatamente** a secção 3 (convenções congeladas), as secções **7B e 7C** (convenções de histórico e a especificação do Lote 3, com as colunas exatas de cada tabela), a secção 6 (ficheiros reservados: só podes criar `data/pipeline/metrics/calendar_summary.py`, `data/pipeline/metrics/history_anomaly.py`, `data/pipeline/tests/test_calendar_summary.py`, `data/pipeline/tests/test_history_anomaly.py` (e `helpers_lote3.py` se precisares), `data/pipeline/notebooks/04_metrics_lote3.ipynb` e `spec/lotes/lote_3.md`; **não toques** em `data/pipeline/metrics/__init__.py`, que já existe) e o protocolo de testes da secção 9, incluindo os casos específicos do L3 e o exemplo trabalhado da secção 7B como teste literal. As funções recebem DataFrames no esquema das tabelas `l1_*` (secção 7B) e não leem `processed/` nem dados reais: nos testes usa DataFrames sintéticos. Trabalha direto em `main`: antes de cada push faz `git pull --rebase origin main`, nunca uses `git add -A`/`git add .` (adiciona só os ficheiros do teu lote) e nunca faças `push --force`; se houver conflito no rebase, pára e avisa. Para cada métrica, lê só a sua linha em `spec/metricas_modis_viirs.csv`; a especificação do lote prevalece sobre o CSV. Escreve primeiro os testes, depois a função. Não instales nem alteres dependências partilhadas. Quando houver ambiguidade, aplica o que o documento diz e regista a dúvida em `spec/lotes/lote_3.md`. No fim corre `/review-gate` e apresenta o resumo do relatório.

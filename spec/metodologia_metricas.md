# Metodologia de métricas — MODIS + VIIRS (FIRMS)

Documento de orientação e **contrato de trabalho** para implementar as métricas de `spec/metricas_modis_viirs.csv`.
Foi escrito para que duas pessoas, cada uma com o seu Claude, trabalhem **em paralelo e sem ver o trabalho uma da outra** até os dois lados estarem em `main`. Por isso:

- cada lote tem os seus ficheiros, nomes e tabelas de saída, e **ninguém edita ficheiros de outro lote**;
- as regras de cálculo, a qualidade dos testes e a forma de raciocinar são as mesmas nos dois lados;
- onde o CSV deixa uma decisão em aberto, ela está **fixada aqui**. Não reinterprete: se discordar, implemente como está e registe a objeção no relatório do lote.

> **Para o Claude que lê isto:** leia este documento inteiro uma vez, depois só a linha do CSV de cada métrica que vai implementar (`grep "^OBS-04," spec/metricas_modis_viirs.csv`). Não leia o CSV completo nem os dados reais. O seu lote está na secção 6 e a especificação exata na secção 7. Há um prompt-modelo na secção 11.

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
| OBS-04 | Percentagem de deteções noturnas | Extra | L2 | A implementar | Baixa |  |
| OBS-05 | FRP mediana | Extra | L2 | A implementar | Baixa | FRP utilizável = não nulo e > 0. |
| OBS-06 | Percentil 90 de FRP | Extra | L2 | A implementar | Baixa |  |
| OBS-07 | Pico de FRP | Extra | L2 | A implementar | Baixa | Desempate determinístico. |
| OBS-08 | Disponibilidade de FRP | Extra | L2 | A implementar | Média |  |
| OBS-09 | Distribuição por tipo de fonte térmica | Opcional | L2 | A implementar | Média | Não interpretar `type` do VIIRS sem confirmar a revisão do produto. |
| OBS-10 | Área mediana do píxel de deteção | Opcional | L2 | A implementar | Média | Parcial hoje: `pixel_area_km2` por linha existe; falta a mediana. |
| QA-01 | Taxa de validação do esquema | MVP | L2 | A implementar | Alta | Parcial hoje: só `n_bad_time`; falta a taxa e as regras. Valida-se após a coerção do notebook 01. |
| CAL-05 | Atividade total no período | MVP | L3 | Útil, depende de L1 | Alta | Soma de CAL-04. |
| CAL-06 | Mês-ano de pico | MVP | L3 | Útil, depende de L1 | Alta | Regra de empate a fixar. |
| CAL-07 | Ano de pico | MVP | L3 | Útil, depende de L1 | Alta | Só anos completos. |
| CAL-08 | Média anual de atividade | MVP | L3 | Útil, depende de L1 | Alta | Só anos completos e elegíveis. |
| CAL-09 | Média histórica do mesmo mês | MVP | L3 | Útil, depende de L1 | Alta | Período de referência a fixar. |
| CAL-10 | Dias com deteções | Opcional | L3 | Útil, depende de L1 | Baixa |  |
| CAL-11 | Maior atividade diária | Opcional | L3 | Útil, depende de L1 | Baixa |  |
| CAL-12 | Perfil sazonal mensal | MVP | L3 | Útil, depende de L1 | Alta | Informar nº de anos por mês. |
| HIS-03 | Anomalia mensal absoluta | MVP | L3 | Útil, depende de L1 | Alta | Depende de CAL-09. |
| HIS-04 | Anomalia mensal percentual | Desejável | L3 | Útil, depende de L1 | Média | Média zero => NA. |
| HIS-01 | Mediana histórica mensal | Desejável | L4 | Útil, depende de L1 | Média |  |
| HIS-02 | Faixa histórica mensal | Desejável | L4 | Útil, depende de L1 | Média | Percentis 10/90; indicar tamanho da amostra. |
| HIS-05 | Desvio padronizado mensal (z-score) | Desejável | L4 | Útil, depende de L1 | Média | Amostra pequena => NA. |
| HIS-06 | Percentil histórico da atividade | Desejável | L4 | Útil, depende de L1 | Média |  |
| HIS-07 | Acumulado comparável no ano | Desejável | L4 | Útil, depende de L1 | Média | Exige série diária multianual. |
| HIS-08 | Variação homóloga mensal | Opcional | L4 | Útil, depende de L1 | Baixa |  |
| HIS-09 | Meses acima da faixa histórica | Desejável | L4 | Útil, depende de L1 | Média | Fixar a referência antes de comparar. |
| HIS-10 | Tendência dos totais anuais | Opcional | L4 | Útil, depende de L1 | Baixa | Theil-Sen só com anos completos e comparáveis; atenção ao degrau MODIS 2002 (Aqua) e 2018. |
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
| ADD-01 | Satélites ativos por mês | (nova) | L4 | Adicional proposta | Alta | Satélites ativos por mês: explica o degrau Terra->Aqua em 2002. |
| ADD-02 | Dias sem deteções globais por sensor | (nova) | L4 | Adicional proposta | Alta | Dias sem deteções globais por sensor: proxy de falhas de cobertura. |
| ADD-03 | Duplicados exatos e pontos (0,0) | (nova) | L2 | A implementar | Média | Adicional proposta: duplicados exatos e pontos (0,0). |
| ADD-04 | Países sem deteções num ano | (nova) | L2 | A implementar | Média | Adicional proposta: países sem deteções num ano. |
| ADD-05 | Sensibilidade ao filtro de tipo | (nova) | L5 | Adicional proposta | Média | Sensibilidade ao filtro de `type`. |
| ADD-06 | Efeito do degrau MODIS->união em 2018 | (nova) | L5 | Adicional proposta | Alta | Efeito do degrau MODIS->união em 2018. |

## 6. Lotes e regras anti-conflito

| Lote | Quem | Métricas | Depende de |
|---|---|---|---|
| **L1** | Arthur + Claude | CAL-01, CAL-02, CAL-03, CAL-04, OBS-01, OBS-02, OBS-03, QA-02, QA-03, QA-04 | só `processed/` |
| **L2** | Colega + Claude | ADD-03, ADD-04, OBS-04, OBS-05, OBS-06, OBS-07, OBS-08, OBS-09, OBS-10, QA-01 | só `processed/` |
| L3 | depois do merge | CAL-05, CAL-06, CAL-07, CAL-08, CAL-09, CAL-10, CAL-11, CAL-12, HIS-03, HIS-04 | tabelas do L1 |
| L4 | depois do merge | ADD-01, ADD-02, HIS-01, HIS-02, HIS-05, HIS-06, HIS-07, HIS-08, HIS-09, HIS-10 | tabelas do L1 |
| L5 | depois do merge | ADD-05, ADD-06, ESP-01, ESP-02, ESP-03, ESP-04, ESP-06, QA-05 | L1 (+ dados extra em alguns) |
| L6 | depois do merge | HAR-01, HAR-02, HAR-03, HAR-04, HAR-05, HAR-06, HAR-07 | L1, período 2018+ |
| L7 | depois do merge | HAR-08, HAR-09, HAR-10, HAR-11, HAR-12, HAR-13, HAR-14 | L1/L6, período 2018+ |
| — | não se implementam já | APP-01, APP-02, APP-03, APP-04, ESP-05, EXT-01, EXT-02, EXT-03, EXT-04, EXT-05, EXT-06, QA-06, QA-07 | — |

**L1 e L2 são independentes e correm em paralelo.** Nenhum lê saídas do outro.

### Ficheiros reservados por lote (só cria/edita os do seu lote)

| | L1 (Arthur) | L2 (colega) |
|---|---|---|
| Módulos | `data/pipeline/metrics/common.py`, `counts.py`, `calendar_metrics.py` | `data/pipeline/metrics/detections.py`, `ingestion_qa.py` |
| Testes | `data/pipeline/tests/test_common.py`, `test_counts.py`, `test_calendar_metrics.py`, `test_integration_sample_lote1.py`, `helpers_lote1.py` | `data/pipeline/tests/test_detections.py`, `test_ingestion_qa.py` |
| Notebook | `data/pipeline/notebooks/02_metrics_lote1.ipynb` | `data/pipeline/notebooks/03_metrics_lote2.ipynb` |
| Relatório | `spec/lotes/lote_1.md` | `spec/lotes/lote_2.md` |
| Saídas em `metrics/` | `l1_*.parquet`, `_log_lote1.csv` | `l2_*.parquet`, `_log_lote2.csv` |
| Onde se faz push | `main` | `main` |

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

**Prompt-modelo** (para colar no Claude do colega)

> Vais implementar o **Lote 2** de métricas do projeto Sprinklers. Lê `spec/metodologia_metricas.md` inteiro uma vez. Segue **exatamente** a secção 7 (especificação), a secção 3 (convenções congeladas), a secção 6 (ficheiros reservados: só podes criar `data/pipeline/metrics/detections.py`, `data/pipeline/metrics/ingestion_qa.py`, `data/pipeline/metrics/__init__.py` vazio, `data/pipeline/tests/test_detections.py`, `data/pipeline/tests/test_ingestion_qa.py`, `data/pipeline/notebooks/03_metrics_lote2.ipynb` e `spec/lotes/lote_2.md`) e o protocolo de testes da secção 9. Trabalha direto em `main`: antes de cada push faz `git pull --rebase origin main`, nunca uses `git add -A`/`git add .` (adiciona só os ficheiros do teu lote) e nunca faças `push --force`; se houver conflito no rebase, pára e avisa. Para cada métrica, lê só a sua linha em `spec/metricas_modis_viirs.csv`. Escreve primeiro os testes (exemplo calculado à mão), depois a função. Não leias nem descarregues dados reais. Não instales nem alteres dependências partilhadas. Quando houver ambiguidade, aplica o que o documento diz e regista a dúvida no relatório do lote. No fim corre `/review-gate` e apresenta o resumo do relatório.

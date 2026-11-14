# Relatório do Lote 1

Métricas: **OBS-01, OBS-02, OBS-03, QA-02, QA-03, QA-04, CAL-01, CAL-02, CAL-03, CAL-04**.
Metodologia: `spec/metodologia_metricas.md`. Estado: implementado e testado localmente; **ainda não executado no Colab com os dados completos**.

## Ficheiros
| Tipo | Ficheiro |
|---|---|
| Código | `backend/metrics/common.py`, `counts.py`, `calendar_metrics.py` (+ `__init__.py` vazio) |
| Testes | `backend/tests/test_common.py` (24), `test_counts.py` (33), `test_calendar_metrics.py` (19), `test_integration_sample_lote1.py` (3), auxiliar `helpers_lote1.py` |
| Notebook | `backend/notebooks/02_metrics_lote1.ipynb` (substitui o esqueleto `02_metrics.ipynb`, removido) |
| Partilhados atualizados | `requirements.txt` (+`pytest`), `data/README.md`, `data/MANIFEST.md`, `spec/metodologia_metricas.md` (estado do L1 e secção 8) |

## Como correr
- Testes: `cd backend && python -m pytest tests -q` (79 testes; 3 são de integração e só correm com `SPRINKLERS_SAMPLE_PARQUET=<caminho de modis_2000.parquet>`).
- Notebook: abrir no Colab, correr a célula 1 (monta a Drive e faz `git clone` do repo), e para um teste curto pôr `SENSORS = {'modis'}` e `YEARS = {2000}` na célula 2. Os resultados ficam em `Sprinklers/metrics/l1_*.parquet`.

## Decisões e desvios em relação ao documento de metodologia
1. **Cobertura desconhecida:** o documento previa uma coluna `unknown_coverage` em `l1_cal_daily`. Como a tabela diária só tem dias com atividade, um dia sem nenhuma deteção não teria linha. Passou a existir `l1_cal_coverage` (calendário completo de cada sensor, `n_rows_global == 0` ⇒ desconhecido) e `n_unknown_days` em mensal e anual. Secção 8 do documento atualizada.
2. **Tabelas mensal e anual densas:** meses sem atividade aparecem com `cell_days = 0`, só dentro do intervalo `[primeira, última]` de cada série (o `viirs` não tem linhas antes de 2018).
3. **`combined`** existe sempre, mesmo quando só há MODIS; nessa altura coincide com `modis`.
4. **Coordenadas inválidas** (NaN, fora de intervalo): ficam fora das métricas por célula (QA-03/04 e CAL) mas contam em OBS-01/02/03 e QA-02. **Datas inválidas** ficam fora de todas. As duas contagens vão para `_log_lote1.csv`.
5. **Guardas de consistência:** `cal_monthly` levanta `ValueError` se houver atividade fora do intervalo de cobertura, e o notebook falha se houver chaves repetidas entre ficheiros (indica linhas com data fora do ano do ficheiro).
6. `QA-02` com `n_raw == 0` não ocorre (os grupos vêm das linhas brutas); a proteção de divisão por zero (`_pct`) está testada à parte.

## Verificação feita
- **79 testes verdes** em pandas 3.1 e em pandas 2.2.3 (o Colab costuma ter 2.x).
- **27 mutações deliberadas** do código (grelha ingénua, remover o filtro elegível, contar linhas em vez de células-dia, `combined` sem união, `<=`→`<` no limite do mês, divisão por zero, datas inválidas, etc.): **todas detetadas**, nas duas versões do pandas. Uma primeira ronda deixou sobreviver 3 (divisão `1/0`, datas inválidas e maiúsculas/minúsculas em `global_day_counts`); foram acrescentados testes e passaram a morrer.
- **Notebook executado localmente** numa "Drive" simulada com a amostra real `modis_2000` e dois ficheiros derivados (`modis_2018`, `viirs-jpss1_2018`, sobrepostos de propósito): as tabelas consolidadas são **iguais** às calculadas diretamente sobre todos os dados; `l1_cal_daily` coincide com um oráculo em Python puro (14 071 chaves); a série `combined` de 2018 (25 170) fica entre o maior sensor e a soma (16 994 + 17 665); a segunda execução salta o que já estava feito.
- **Amostra real `modis_2000`:** retenção do filtro 93,1 % (243 432 de 261 363); confiança h 78 044, n 172 450, l 10 869; 126 649 células-dia para 243 432 deteções; cobertura 2000-11-01 a 2000-12-31 sem dias em falta; QA-04 = 0 (só Terra).

## Limitações e riscos
- **Não corrido no Colab com VIIRS real.** O VIIRS tem cerca de 3 GB comprimidos; cada ficheiro é lido com 8 colunas, mas as funções fazem várias passagens e o `acq_date` em texto é pesado. Se faltar memória: *High-RAM*, ou processar por anos (`YEARS`).
- A **cobertura** é um proxy: um dia sem qualquer deteção global num sensor é tratado como desconhecido, mas não distingue falha de dados de ausência real de fogo.
- A série **`combined`** mistura sensores e tem um degrau artificial em 2018; para o histórico completo, usar `modis`.
- `QA-04` para VIIRS vale sempre 0 (só há NOAA-20).
- SHA-256 dos ficheiros de `metrics/` a registar no `MANIFEST.md` após a execução no Colab.

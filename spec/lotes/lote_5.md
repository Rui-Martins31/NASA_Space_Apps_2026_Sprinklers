# Relatório do Lote 5

Métricas: **ESP-02, ESP-03, ESP-06, QA-05, ADD-05, ADD-06** (mais a base comum `build_cell_year`).
Metodologia: `spec/metodologia_metricas.md` (secções 7E e 7F). Estado: implementado e testado localmente; **ainda não executado no Colab com dados reais**. ESP-01 e ESP-04 ficam adiadas (falta a área/máscara por país).

## Ficheiros
| Tipo | Ficheiro |
|---|---|
| Código | `data/pipeline/metrics/cell_recurrence.py` (`build_cell_year`, ESP-02/03/06), `filter_sensitivity.py` (ADD-05), `coverage_steps.py` (QA-05, ADD-06) |
| Testes | `data/pipeline/tests/test_cell_recurrence.py` (73), `test_filter_sensitivity.py` (40), `test_coverage_steps.py` (44), `test_notebook_lote5.py` (8); auxiliares `helpers_lote5.py` |
| Notebook | `data/pipeline/notebooks/06_metrics_lote5.ipynb` |
| Ferramenta (partilhada, `[TOOLS]`) | `data/pipeline/scripts/mutate.py`: harness de mutação que corre primeiro a cópia sem mutação |
| Partilhados atualizados | `data/MANIFEST.md` (tabelas `l5_*`), `spec/metodologia_metricas.md` (estado do L5, ficheiros reservados) |

## Como correr
- Testes: `cd data/pipeline && python -m pytest tests -q`. Os testes do notebook precisam de um motor Parquet (`pyarrow`); sem ele ficam ignorados.
- Notebook: `06_metrics_lote5.ipynb` no Colab, depois de correr os notebooks 01 e 02. Para um teste curto: `SENSORS = {'modis'}`, `YEARS = {2000}`. Em execuções parciais só entram no ESP-06 os (série, ano) realmente calculados; a série `combined` de um ano só existe se **todos** os ficheiros desse ano estiverem processados.
- Mutação: `python data/pipeline/scripts/mutate.py MUTANTES.json --tests tests/test_x.py` (formato no cabeçalho do script).

## Decisões e interpretações
1. **`combined` = união por (país, data, célula) entre sensores**; satélites do mesmo sensor contam uma vez.
2. **ESP-06:** `eligible_years` são os anos válidos de `l1_cal_annual`. Grupos com anos válidos mas sem células aparecem com `n_cells = 0`, `pct_cells_2plus`, `mean_years_per_cell` e `max_years` NA (`max_years` é `Int64`). `eligible_years` vazio (≠ `None`) significa "nenhum ano válido". O notebook inclui também os países sem nenhuma célula elegível.
3. **ADD-05:** variantes `{"types", "include_na_type"}`; confiança sempre `n`/`h`; datas e coordenadas inválidas são ignoradas (como no L1); país ou instrumento NA passa a `"unknown"`; satélites do mesmo sensor contam juntos. Um grupo aparece com as 3 variantes se passar em pelo menos uma.
4. **QA-05:** soma `n_rows_global` de (instrumento, data) repetidos e normaliza a data, como o ADD-02; **é um proxy global**, não cobertura real por região. `pct_confirmed + pct_zero_days = 100`.
5. **ADD-06:** exige o mês válido nas séries `modis` e `combined`; linha `ALL` com `n_months` = meses distintos. Chaves repetidas ou NA em `l1_cal_monthly` ⇒ `ValueError`.
6. **Cópias privadas** de `valid_mask` e `require_no_na` nos módulos (regra 7E: não importar código de L2–L4).

## Verificação feita
- **Testes:** 165 testes do L5. Suite completa: **519 passam e 3 ficam ignorados em pandas 3.1.1 e em pandas 2.2.3** (venvs descartáveis com `pyarrow` e `scipy`).
- **Mutações** (harness `mutate.py`, baseline verificada primeiro): 34 mutantes de `cell_recurrence.py`, 36 de `filter_sensitivity.py`, 37 de `coverage_steps.py`; **107/107 detetados por asserção**. No notebook, 16/18: um mutante equivalente (a asserção `computed` é uma guarda redundante, o filtro de séries já a garante) e um que rebenta por erro de execução em vez de falhar por asserção (retoma desativada, falha alto).
- **Verificação cruzada independente** (Python puro, mundo sintético de 8 anos × 5 países, 11 055 linhas): ESP-02/03 (média, mediana, p90 linear, baldes), ESP-06 com e sem anos elegíveis, ADD-05 (3 variantes, 195 linhas), QA-05 (324 linhas, mais o complemento a 100 do ADD-02) e ADD-06 (inclui `ALL`); e o cell-year contra o CAL-04 do L1 (105 comparações). 0 diferenças, nos dois pandas.
- **Notebook** executado em local com uma Drive simulada (tabelas `l1_*` calculadas com o código do L1): valores literais calculados à mão, retoma, parcial apagado e refeito, mudança de grelha (e voltar atrás), `max_unknown_days`, execuções parciais, seleção vazia, ano sem células elegíveis e tabela `l1_*` em falta (mensagem clara).
- **Revisão independente** por um agente de contexto novo (recebeu código e especificação, não o resumo); cada achado foi reproduzido antes de agir.

## Revisão independente
Não encontrou divergências da especificação nem erros nas seis métricas (oráculos próprios com 200–300 casos cada, pandas 2.2 e 3.1, `category`/`string`, 35 mutantes todos mortos). Os problemas estavam no notebook:

| # | Achado | Verificação | O que foi feito |
|---|---|---|---|
| 1 | Com `SENSORS`/`YEARS` parciais, o ESP-06 usava os anos válidos de todo o `l1_cal_annual`: `PT/modis` saía com 2 anos analisados e 0 % de recorrência quando só um ano tinha sido processado | Confirmado | Só entram (série, ano) calculados por completo; teste com `YEARS={2018}` |
| 2 | A verificação do notebook falhava em execuções parciais legítimas (depois de gravar), e `combined` de um ano podia sair só com MODIS | Confirmado | `combined` só existe se todos os ficheiros do ano estiverem processados; a verificação usa o mesmo critério; testes com MODIS só e VIIRS só |
| 3 | Países com anos válidos e nenhuma célula elegível desapareciam do ESP-06 | Confirmado | O ciclo por blocos inclui os países de `eligible_years`; teste com o país `ZZ` |
| 4 | Ano sem células elegíveis gravava um Parquet vazio com coluna `null` que quebrava a leitura com filtros | Lido no código; o caso não foi reproduzido à parte | Não se grava `cell_year` vazio; teste com um ano só de confiança baixa |
| 5 | Selecionar `viirs` em vez de `viirs-jpss1` dava `No objects to concatenate` | Confirmado | `ValueError` que lista os ficheiros disponíveis; teste |
| – | Dtypes de saída vazia de `build_cell_year`/ADD-05 (`object` vs `string`), leitura sem `category`, log sem os anos efetivamente cobertos | Menor | Cobertos no 4; o log regista agora `series_years_computed`. Dtypes de texto não fixados pela especificação |

## Limitações e passos seguintes
- **Não corrido com dados reais.** Só existem MODIS 2000 e mundos sintéticos. Memória do VIIRS real não medida: o ESP-06 consolida por blocos de países (`ESP06_BLOCK`), mas convém ligar High-RAM.
- O notebook faz `git clone` do `main`, que só terá o código do L5 depois do pull request.
- QA-05 não distingue falha de dados de ausência real de fogo.
- A série `combined` tem o degrau artificial de 2018; para o histórico completo usar `modis`.
- SHA-256 dos ficheiros de `metrics/` a registar no `MANIFEST.md` após a execução no Colab.

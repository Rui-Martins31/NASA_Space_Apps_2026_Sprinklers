# Relatório do Lote 4

Métricas: **HIS-01, HIS-02, HIS-05, HIS-06, HIS-07, HIS-08, HIS-09, HIS-10, ADD-01, ADD-02**.
Metodologia: `spec/metodologia_metricas.md` (secções 7B e 7D). Estado: implementado e testado localmente; **ainda não executado no Colab com as tabelas `l1_*` reais**, que só existem depois de correr o notebook `02_metrics_lote1` com os dados completos.

## Ficheiros
| Tipo | Ficheiro |
|---|---|
| Código | `data/pipeline/metrics/history_pool.py` (pool de referência comum), `history_distribution.py` (HIS-01/02/05/06/09), `history_cumulative.py` (HIS-07/08/10), `coverage_meta.py` (ADD-01/02) |
| Testes | `data/pipeline/tests/test_history_pool.py` (21), `test_history_distribution.py` (55), `test_history_cumulative.py` (30), `test_coverage_meta.py` (18); auxiliares `helpers_lote4.py`, `helpers_lote4_b.py` |
| Notebook | `data/pipeline/notebooks/05_metrics_lote4.ipynb` |
| Partilhados atualizados | `data/MANIFEST.md` (tabelas `l2_*` e `l4_*`), `spec/metodologia_metricas.md` (estado do L4, ficheiros reservados) |

## Como correr
- Testes: `cd data/pipeline && python -m pytest tests -q`. O teste que usa `scipy.stats.theilslopes` como oráculo da tendência só corre se o `scipy` estiver instalado; o Colab tem-no.
- Notebook: abrir `05_metrics_lote4.ipynb` no Colab depois de ter corrido o `02_metrics_lote1`. Não há ciclo por ano; demora cerca de 40 s a 1 min com um mundo do tamanho esperado (170 países × 3 séries × 25 anos, cerca de 150 mil linhas mensais), quase todo em HIS-05 e HIS-06.

## Decisões e interpretações
1. **`reference_fixed` e `reference_loo`** em vez de uma função única com bandeira: a referência fixa e a que exclui o ano avaliado devolvem tabelas de formas diferentes (por mês ou por linha).
2. **Linhas inválidas** (parciais ou com dias desconhecidos) ficam na tabela. Mantêm `n_ref_years`, `ref_mean` e `ref_std` (descrevem o pool), mas `zscore`, `percentile`, `n_below` e `n_equal` ficam NA.
3. **HIS-05** devolve NA (nunca infinito) quando `ref_std == 0`.
4. **HIS-07:** `ytd_cell_days` só é NA se faltar algum mês entre janeiro e o mês avaliado; `comparable` exige também que todos sejam válidos. `ref_start`/`ref_end` limitam só o pool, não as linhas avaliadas.
5. **HIS-09** usa referência fixa mesmo que o ano avaliado esteja na janela de referência, e `>` estrito face ao p90. Um ano sem meses avaliáveis mantém a linha (0, 0, "").
6. **HIS-10:** `slope_p025` e `slope_p975` são percentis dos declives de todos os pares de anos. São uma **dispersão**, não um intervalo de confiança formal. Com menos de 8 anos válidos a linha existe com as estimativas NA.
7. **ADD-01** soma `n_raw` por satélite entre todos os países antes de decidir se está ativo. **ADD-02** soma duplicados `(instrumento, data)` e conta os dias presentes na tabela (não repreenche lacunas).

## Verificação feita
- **Testes:** 124 testes do L4 (21 no pool, 55, 30 e 18 nos três módulos). Suite completa (L1+L2+L4): 280 passam em pandas 3.1 (com `scipy`) e 279 em pandas 2.2 (o teste do `scipy` fica ignorado por não estar instalado).
- **Mutações:** 108 mutantes (pool 16, distribuição 37, cumulativo 24, cobertura 17, guardas da revisão 14); todos detetados nos dois pandas, com uma exceção esperada: o mutante que remove `observed=True` só é observável em pandas 2.2 (onde é detetado), porque em pandas 3 esse é já o comportamento por defeito. Corri tudo com um *harness* que verifica primeiro que a cópia sem mutação passa. Durante o trabalho houve mutantes equivalentes e outros que falhavam por erro de execução e não por asserção; foram substituídos.
- **Verificação cruzada independente** (escrita à parte, em Python puro, sem reutilizar o código testado) sobre um mundo sintético de 3 países × 2 séries × 25 anos (1 338 linhas mensais): HIS-01, 02, 05, 06, 07, 08, 09, 10 (incluindo a comparação com `scipy.stats.theilslopes`), ADD-01 e ADD-02, com e sem janela de referência: **0 diferenças**.
- **Notebook** executado localmente (Drive simulada): com as tabelas `l1_*` reais do ensaio (71 394 linhas mensais, poucos anos, logo muitas estatísticas NA) e com um mundo de 125 970 linhas mensais (cerca de 41 s depois das correções). Passam as invariantes da célula final, e falha com `FileNotFoundError` claro se faltar alguma tabela `l1_*`.
- **Revisão independente** por um agente de contexto novo, que recebeu o código e a especificação mas não o meu resumo. Os achados e o que foi feito com cada um estão na secção seguinte.

## Revisão independente
Feita por um agente de contexto novo, que recebeu o código e a especificação (secções 7B, 7D e 9) mas não o meu resumo. Reproduzi cada achado antes de agir. Não encontrou violações da especificação para entradas bem formadas nem testes tautológicos.

| # | Achado | Verificação | O que foi feito |
|---|---|---|---|
| 1 | O notebook dizia "recalcula tudo em segundos"; HIS-05, 06 e 09 levavam 15 + 15 + 24 s num mundo de 153 mil linhas | Confirmado | Texto corrigido ("cerca de 1 minuto"). O HIS-09 deixou de chamar `reference_loo` (só precisava de `valid_mask` e da faixa fixa): 58 s → 41 s no notebook |
| 2 | HIS-07 e HIS-08 apagavam linhas com chave repetida, contradizendo "uma linha por linha de entrada"; HIS-05/06 contavam o ano duas vezes no pool | Confirmado | `require_unique` em `reference_fixed`, `reference_loo`, HIS-07, HIS-08 e HIS-10: `ValueError` com mensagem clara |
| 3 | HIS-10: `n_years` contava linhas e não anos distintos; com um só ano repetido dava `IndexError` | Confirmado | Coberto pela mesma guarda de unicidade |
| 4 | `cell_days` com valores em falta rebentava com `TypeError` obscuro (HIS-07/08) ou `ValueError` diferente (ADD-01/02) | Confirmado | `require_no_na` com mensagem que nomeia a coluna |
| 5 | ADD-02 contava datas com hora como dias diferentes: 3 dias em vez de 2 | Confirmado (erro silencioso) | `dt.normalize()` antes de agrupar; teste com timestamps no mesmo dia |
| 6 | HIS-10: a especificação dizia "NA se `n_years < 8`" mas o código só põe NA nas quatro estimativas | Ambiguidade da especificação | Especificação clarificada: `n_years`, `first_year` e `last_year` ficam preenchidos |
| 7 | HIS-05 deixa `ref_mean`/`ref_std` preenchidos em linhas inválidas, e a 7B dizia que as colunas derivadas ficam NA | Ambiguidade da especificação | 7B clarificada: ficam NA as colunas derivadas do valor observado; as que descrevem o pool continuam preenchidas |
| 8 | Avisos `FutureWarning` (`observed=False`) em pandas 2.2 com chaves `category` | Confirmado, menor | `observed=True` nos `groupby`; teste que converte os avisos em erro |
| – | `assert` no notebook desaparece com `python -O` | Confirmado, menor | Trocado por `FileNotFoundError` |

Quando se acrescentou a guarda de unicidade ao HIS-09 verificou-se que era código morto (o `reference_fixed` já a aplica antes) e foi retirada.

**Nota para o L3 (colega):** os pontos 6 e 7 clarificam a especificação depois de o lote 3 ter sido entregue ao colega. A 7B passa a dizer que `ref_mean` e `n_ref_years` ficam preenchidos nas linhas inválidas de HIS-03; se o L3 os pôs a NA, o teste cruzado depois do merge vai mostrar a diferença.

## Limitações e passos seguintes
- **Não corrido com dados reais.** Só existem MODIS 2000 e ficheiros derivados; a estatística histórica foi validada com mundos sintéticos. O resultado real vem do Colab.
- Com `MAX_UNKNOWN_DAYS = 0`, qualquer dia de cobertura desconhecida invalida o mês. Se o MODIS real tiver muitas lacunas isoladas, a referência perde anos; é um parâmetro do notebook.
- A série `combined` tem o degrau artificial de 2018; para o histórico completo as tendências e anomalias devem usar `modis`.
- **Teste cruzado com o L3**, depois do merge: o `ref_mean` de HIS-03 (L3) tem de coincidir com o `ref_mean` de `reference_loo` (L4) para as mesmas entradas. As duas implementações são independentes.
- SHA-256 dos ficheiros de `metrics/` a registar no `MANIFEST.md` após a execução no Colab.

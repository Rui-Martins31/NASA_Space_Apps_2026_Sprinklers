"""Metricas de historico do Lote 4: HIS-07 (acumulado no ano), HIS-08 (variacao homologa)
e HIS-10 (tendencia anual de Theil-Sen).

Funcoes puras sobre os esquemas de `l1_cal_monthly` e `l1_cal_annual` (chave `cell`). Regras em
spec/metodologia_metricas.md, 7B e 7D. A validade (nao parcial e com no maximo
`max_unknown_days` dias desconhecidos) vem de `history_pool.valid_mask`.

Desempenho: sem ciclos Python por linha ou por grupo.
- HIS-07: cada (cell, series, year) vira uma linha de uma matriz (grupos x 12 meses); o acumulado e a
  comparabilidade saem de `cumsum` / `logical_and.accumulate` ao longo dos meses; o pool leave-one-out
  de cada (cell, series, month) sai de somas por grupo (`bincount`) menos a propria linha.
- HIS-08: junta a tabela com ela propria deslocada um ano (merge), em vez de um dicionario por linha.
- HIS-10 (Theil-Sen, O(n^2) por grupo em n anos): vetorizado ENTRE grupos. Os grupos com o mesmo
  numero de anos validos n processam-se juntos numa matriz (grupos x pares de anos), com a mesma
  mediana/percentis do calculo por grupo; o custo continua a ser O(n^2) por grupo (n ~ 26 -> 325
  declives), mas sem ciclo Python por grupo (so um ciclo pelos valores distintos de n).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import require_columns
from .history_pool import MAX_UNKNOWN_DAYS, MIN_REF_YEARS, require_no_na, require_unique, valid_mask

MIN_TREND_YEARS = 8

MONTHLY_REQUIRED = ["cell", "series", "year", "month", "cell_days", "partial", "n_unknown_days"]
ANNUAL_REQUIRED = ["cell", "series", "year", "cell_days", "partial", "n_unknown_days"]
YTD_COLUMNS = ["cell", "series", "year", "month", "ytd_cell_days", "comparable",
               "n_ref_years", "ref_ytd_mean", "ytd_diff"]
YOY_COLUMNS = ["cell", "series", "year", "month", "cell_days", "prev_cell_days",
               "valid_pair", "diff_abs", "yoy_pct"]
TREND_COLUMNS = ["cell", "series", "n_years", "first_year", "last_year",
                 "slope_per_year", "intercept", "slope_p025", "slope_p975"]

_TREND_BLOCK_ELEMENTS = 4_000_000       # declives por bloco de grupos no Theil-Sen


def _frame(columns, dtypes) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=dtypes[c]) for c in columns})


def _plain_key(frame: pd.DataFrame) -> pd.DataFrame:
    """Copia sem categorias em `series` (o resultado nao depende de categorias nao usadas)."""
    out = frame.copy()
    if isinstance(out["series"].dtype, pd.CategoricalDtype):
        out["series"] = out["series"].astype(out["series"].cat.categories.dtype)
    return out


def his07_ytd(monthly: pd.DataFrame, ref_start=None, ref_end=None,
              min_ref_years: int = MIN_REF_YEARS,
              max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-07: acumulado de janeiro ate cada mes, comparado com os OUTROS anos (leave-one-out).

    Uma linha por linha de entrada (as chaves da entrada tem de ser unicas: ValueError se nao forem).
    `ytd_cell_days` = soma de `cell_days` de janeiro ao mes,
    NA se algum desses meses falta na entrada. `comparable` = todos os meses de janeiro ao mes
    presentes e validos. Referencia = media do `ytd_cell_days` do mesmo mes nos outros anos
    comparaveis dentro de [ref_start, ref_end] (inclusivos); `n_ref_years` = tamanho desse pool.
    `ref_ytd_mean` e `ytd_diff` sao NA se a linha nao e comparavel ou n_ref_years < min_ref_years.
    """
    require_columns(monthly, MONTHLY_REQUIRED)
    require_unique(monthly, ["cell", "series", "year", "month"])
    require_no_na(monthly, ["cell_days"])
    dtypes = {"cell": "int64", "series": "object", "year": "int64", "month": "int64",
              "ytd_cell_days": "Int64", "comparable": "bool", "n_ref_years": "int64",
              "ref_ytd_mean": "float64", "ytd_diff": "float64"}
    if len(monthly) == 0:
        return _frame(YTD_COLUMNS, dtypes)
    m = _plain_key(monthly[MONTHLY_REQUIRED])
    valid = valid_mask(m, max_unknown_days).to_numpy()
    gid = m.groupby(["cell", "series", "year"], sort=False, observed=True).ngroup().to_numpy()
    keep = gid >= 0                                                   # chaves NA nao entram (como no groupby)
    m, valid, gid = m[keep], valid[keep], gid[keep]
    n_groups = int(gid.max()) + 1
    month = m["month"].to_numpy(dtype="int64")
    year = m["year"].to_numpy(dtype="int64")
    cell_days = m["cell_days"].to_numpy(dtype="int64")
    top = max(int(month.max()), 0)
    # coluna 0 = "antes de janeiro" (acumulado vazio); colunas 1..top = meses
    value = np.zeros((n_groups, top + 1), dtype="int64")
    present = np.zeros((n_groups, top + 1), dtype=bool)
    good = np.zeros((n_groups, top + 1), dtype=bool)
    in_matrix = month >= 1
    value[gid[in_matrix], month[in_matrix]] = cell_days[in_matrix]
    present[gid[in_matrix], month[in_matrix]] = True
    good[gid[in_matrix], month[in_matrix]] = valid[in_matrix]
    present[:, 0] = good[:, 0] = True
    cum_value = np.cumsum(value, axis=1)
    all_present = np.logical_and.accumulate(present, axis=1)
    all_good = np.logical_and.accumulate(present & good, axis=1)
    col = np.clip(month, 0, top)
    defined = all_present[gid, col]                                   # todos os meses 1..month existem
    ytd = np.where(defined, cum_value[gid, col], 0)
    comparable = all_good[gid, col]
    # pool leave-one-out por (cell, series, month): so linhas comparaveis dentro da janela
    in_pool = comparable.copy()
    if ref_start is not None:
        in_pool &= year >= ref_start
    if ref_end is not None:
        in_pool &= year <= ref_end
    pool_id = m.groupby(["cell", "series", "month"], sort=False, observed=True).ngroup().to_numpy()
    pool_n = np.bincount(pool_id, weights=in_pool, minlength=int(pool_id.max()) + 1)
    pool_sum = np.bincount(pool_id, weights=np.where(in_pool, ytd, 0), minlength=len(pool_n))
    n_ref = np.rint(pool_n[pool_id]).astype("int64") - in_pool
    others_sum = pool_sum[pool_id] - np.where(in_pool, ytd, 0)
    ok = comparable & (n_ref >= max(min_ref_years, 1))
    mean = np.where(ok, others_sum / np.where(n_ref > 0, n_ref, 1), np.nan)
    out = m[["cell", "series"]].copy()
    out["year"] = year
    out["month"] = month
    out["ytd_cell_days"] = pd.arrays.IntegerArray(ytd.astype("int64"), ~defined)
    out["comparable"] = comparable.astype(bool)
    out["n_ref_years"] = n_ref.astype("int64")
    out["ref_ytd_mean"] = mean
    out["ytd_diff"] = np.where(ok, ytd - mean, np.nan)
    return out[YTD_COLUMNS].sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)


def his08_yoy(monthly: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-08: variacao homologa face ao mesmo mes do ano anterior.

    `prev_cell_days` = `cell_days` da mesma celula/serie/mes em year-1 (NA se ausente).
    `valid_pair` = os dois meses presentes e validos. `diff_abs` e `yoy_pct` (=100*diff/prev)
    so existem se `valid_pair`; `yoy_pct` e NA tambem se prev_cell_days == 0 (diff_abs fica).
    """
    require_columns(monthly, MONTHLY_REQUIRED)
    require_unique(monthly, ["cell", "series", "year", "month"])
    require_no_na(monthly, ["cell_days"])
    dtypes = {"cell": "int64", "series": "object", "year": "int64", "month": "int64",
              "cell_days": "int64", "prev_cell_days": "Int64", "valid_pair": "bool",
              "diff_abs": "Int64", "yoy_pct": "float64"}
    if len(monthly) == 0:
        return _frame(YOY_COLUMNS, dtypes)
    keys = ["cell", "series", "year", "month"]
    base = _plain_key(monthly[MONTHLY_REQUIRED])
    base["_valid"] = valid_mask(base, max_unknown_days).to_numpy()
    base = base[keys + ["cell_days", "_valid"]].astype({"cell_days": "int64", "year": "int64", "month": "int64"})
    prev = base.rename(columns={"cell_days": "prev_cell_days", "_valid": "_prev_valid"})
    prev["year"] = prev["year"] + 1                                   # a linha de year-1 alinha com a de year
    prev["_prev_valid"] = prev["_prev_valid"].astype("int64")
    joined = base.merge(prev, on=keys, how="left", indicator=True)    # direita unica: 1 linha por linha de entrada
    has_prev = (joined["_merge"] == "both").to_numpy()
    prev_value = np.where(has_prev, joined["prev_cell_days"].fillna(0), 0).astype("int64")
    pair = has_prev & (joined["_prev_valid"].fillna(0).to_numpy() == 1) & joined["_valid"].to_numpy()
    cell_days = joined["cell_days"].to_numpy(dtype="int64")
    diff = np.where(pair, cell_days - prev_value, 0)
    nonzero = pair & (prev_value != 0)
    pct = np.where(nonzero, 100.0 * diff / np.where(prev_value != 0, prev_value, 1), np.nan)
    out = joined[keys + ["cell_days"]].copy()
    out["prev_cell_days"] = pd.arrays.IntegerArray(prev_value, ~has_prev)
    out["valid_pair"] = pair.astype(bool)
    out["diff_abs"] = pd.arrays.IntegerArray(diff.astype("int64"), ~pair)
    out["yoy_pct"] = pct.astype("float64")
    return out[YOY_COLUMNS].sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)


def _theil_sen_rows(x: np.ndarray, y: np.ndarray):
    """Theil-Sen de cada linha de (x, y): matrizes (grupos x n) com x distintos por linha e n >= 2.
    Devolve (declive, intercepto, p2.5, p97.5), um vetor por grupo, com as mesmas operacoes numpy
    do calculo por grupo (mediana e percentis lineares dos declives de todos os pares i<j)."""
    i, j = np.triu_indices(x.shape[1], k=1)
    slopes = (y[:, j] - y[:, i]) / (x[:, j] - x[:, i])
    slope = np.median(slopes, axis=1)
    intercept = np.median(y - slope[:, None] * x, axis=1)
    return (slope, intercept,
            np.percentile(slopes, 2.5, axis=1, method="linear"),
            np.percentile(slopes, 97.5, axis=1, method="linear"))


def his10_trend(annual: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS,
                min_years: int = MIN_TREND_YEARS) -> pd.DataFrame:
    """HIS-10: tendencia de Theil-Sen de `cell_days` por ano, por (cell, series).

    Usa so anos validos. x = ano, y = cell_days; declive = mediana dos declives de todos os
    pares i<j com x distintos; intercept = mediana(y - declive*x). `slope_p025` e `slope_p975`
    sao os percentis 2,5 e 97,5 (interpolacao linear) dos declives dos pares: sao uma
    DISPERSAO dos declives, NAO um intervalo de confianca formal.
    Com menos de `min_years` anos validos a linha existe (n_years, first_year, last_year) mas as
    quatro estimativas sao NA; sem anos validos, n_years = 0 e o resto NA.
    Limitacao: o Theil-Sen e O(n^2) por grupo (todos os pares de anos); aqui vetoriza-se ENTRE
    grupos com o mesmo n (ver docstring do modulo), nao se reduz a complexidade por grupo.
    Com `min_years < 2` os grupos com 1 so ano valido ficam NA (nao ha pares).
    """
    require_columns(annual, ANNUAL_REQUIRED)
    require_unique(annual, ["cell", "series", "year"])
    require_no_na(annual, ["cell_days"])
    dtypes = {"cell": "int64", "series": "object", "n_years": "int64",
              "first_year": "Int64", "last_year": "Int64", "slope_per_year": "float64",
              "intercept": "float64", "slope_p025": "float64", "slope_p975": "float64"}
    if len(annual) == 0:
        return _frame(TREND_COLUMNS, dtypes)
    work = _plain_key(annual[ANNUAL_REQUIRED])
    ok = valid_mask(work, max_unknown_days).to_numpy()
    gid = work.groupby(["cell", "series"], sort=True, observed=True).ngroup().to_numpy()
    keep = gid >= 0
    work, ok, gid = work[keep], ok[keep], gid[keep]
    n_groups = int(gid.max()) + 1
    _, first_row = np.unique(gid, return_index=True)                  # uma linha por grupo, em ordem de gid
    out = work[["cell", "series"]].iloc[first_row].reset_index(drop=True)
    g = gid[ok]
    year = work["year"].to_numpy(dtype="int64")[ok]
    y = work["cell_days"].to_numpy(dtype="float64")[ok]
    order = np.lexsort((year, g))                                     # por grupo, anos ascendentes
    g, year, y = g[order], year[order], y[order]
    n = np.bincount(g, minlength=n_groups)
    start = np.cumsum(n) - n
    has = n > 0
    last_index = max(len(year) - 1, 0)
    first = year[np.minimum(start, last_index)] if len(year) else np.zeros(n_groups, dtype="int64")
    last = year[np.clip(start + n - 1, 0, last_index)] if len(year) else np.zeros(n_groups, dtype="int64")
    est = np.full((4, n_groups), np.nan)
    x = year.astype("float64")
    for size in np.unique(n[n >= max(min_years, 2)]):
        members = np.flatnonzero(n == size)
        block = max(1, _TREND_BLOCK_ELEMENTS // (int(size) * (int(size) - 1) // 2))
        for lo in range(0, len(members), block):
            sel = members[lo:lo + block]
            idx = start[sel][:, None] + np.arange(size)
            est[:, sel] = _theil_sen_rows(x[idx], y[idx])
    out["n_years"] = n.astype("int64")
    out["first_year"] = pd.arrays.IntegerArray(first.astype("int64"), ~has)
    out["last_year"] = pd.arrays.IntegerArray(last.astype("int64"), ~has)
    for name, values in zip(TREND_COLUMNS[5:], est):
        out[name] = values.astype("float64")
    return out[TREND_COLUMNS].sort_values(["cell", "series"]).reset_index(drop=True)

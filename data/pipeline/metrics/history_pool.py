"""Pool de referencia historico partilhado pelas metricas do Lote 4 (HIS-01/02/05/06/07/09).

Funcoes puras sobre o esquema de `l1_cal_monthly` (chave `cell`, int64). Regras em
spec/metodologia_metricas.md, 7B:
- mes valido = nao parcial e com no maximo MAX_UNKNOWN_DAYS dias de cobertura desconhecida;
- pool de (cell, series, month) = valores `cell_days` dos meses validos desse mes civil,
  um por ano, dentro de [ref_start, ref_end] (inclusivos);
- referencia fixa: pool inteiro; leave-one-out: pool sem o ano avaliado;
- abaixo de `min_ref_years` as estatisticas sao NA (n_ref_years informa);
- desvio-padrao amostral (ddof=1); percentis por interpolacao linear.

Desempenho: nao ha ciclos Python por (cell, series, month). Cada pool vira uma linha de uma
matriz (grupos x anos) com mascara de presenca, e as estatisticas calculam-se por linha com numpy
(as mesmas operacoes do calculo original, linha a linha); o leave-one-out apenas retira da mascara o
ano avaliado. A matriz tem uma coluna por ano do intervalo (~26), por isso o custo e
O(linhas x anos); o trabalho e feito em blocos para limitar a memoria.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import require_columns

MAX_UNKNOWN_DAYS = 0
MIN_REF_YEARS = 5

KEYS = ["cell", "series", "month"]
REQUIRED = ["cell", "series", "year", "month", "cell_days", "partial", "n_unknown_days"]
FIXED_COLUMNS = ["cell", "series", "month", "n_ref_years", "ref_mean", "ref_std",
                 "ref_median", "ref_p10", "ref_p90"]
LOO_COLUMNS = ["cell", "series", "year", "month", "cell_days", "valid_month",
               "n_ref_years", "ref_mean", "ref_std", "n_below", "n_equal"]

_BLOCK_ELEMENTS = 4_000_000          # elementos (linhas x anos) por bloco no leave-one-out


def valid_mask(table: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.Series:
    """Mes (ou ano) valido: nao parcial e com no maximo `max_unknown_days` dias desconhecidos."""
    ok = (table["n_unknown_days"] <= max_unknown_days).fillna(False).astype(bool)
    return (~table["partial"].astype(bool)) & ok


def require_unique(table: pd.DataFrame, keys) -> None:
    """ValueError se houver chaves repetidas: as tabelas l1_* tem uma linha por chave, e uma
    repeticao seria apagada (HIS-07/08) ou contada duas vezes no pool em silencio."""
    dup = table.duplicated(list(keys), keep=False)
    if dup.any():
        raise ValueError(f"{int(dup.sum())} linhas com chave repetida em {list(keys)}; "
                         "a entrada deve ter uma linha por chave")


def require_no_na(table: pd.DataFrame, columns) -> None:
    """ValueError claro se alguma das colunas tiver valores em falta."""
    bad = [c for c in columns if table[c].isna().any()]
    if bad:
        raise ValueError(f"valores em falta em {bad}")


def _in_pool(monthly: pd.DataFrame, ref_start, ref_end, max_unknown_days) -> np.ndarray:
    """Mascara das linhas que entram no pool: validas e dentro de [ref_start, ref_end]."""
    ok = valid_mask(monthly, max_unknown_days).to_numpy().copy()
    if ref_start is not None:
        ok &= (monthly["year"] >= ref_start).to_numpy()
    if ref_end is not None:
        ok &= (monthly["year"] <= ref_end).to_numpy()
    return ok


def _group_ids(table: pd.DataFrame):
    """(gid por linha, n de grupos) para as chaves (cell, series, month); gid = -1 se a chave e NA."""
    gid = table.groupby(KEYS, sort=False, observed=True).ngroup().to_numpy()
    return gid, (int(gid.max()) + 1 if len(gid) else 0)


def _pool_matrix(gid: np.ndarray, n_groups: int, year: np.ndarray, value: np.ndarray):
    """Matriz (grupos x anos) com os valores do pool, mascara de presenca e o ano da coluna 0.
    `gid`, `year` e `value` so das linhas do pool (chaves unicas: uma celula por (grupo, ano))."""
    if len(gid) == 0:
        return np.zeros((n_groups, 1)), np.zeros((n_groups, 1), dtype=bool), 0
    ymin = int(year.min())
    width = int(year.max()) - ymin + 1
    vals = np.zeros((n_groups, width))
    present = np.zeros((n_groups, width), dtype=bool)
    col = (year - ymin).astype("int64")
    vals[gid, col] = value
    present[gid, col] = True
    return vals, present, ymin


def _lerp_percentile(sorted_vals: np.ndarray, n: np.ndarray, q: float) -> np.ndarray:
    """Percentil `q` (0-100, interpolacao linear) de cada linha de `sorted_vals` (ascendente,
    so as primeiras `n` colunas contam, n >= 1). Replica `np.percentile(..., method="linear")`."""
    rows = np.arange(len(n))
    virtual = (n - 1) * (q / 100.0)
    prev = np.floor(virtual).astype("int64")
    nxt = np.minimum(prev + 1, n - 1)
    gamma = virtual - prev
    a = sorted_vals[rows, prev]
    b = sorted_vals[rows, nxt]
    diff = b - a
    return np.where(gamma >= 0.5, b - diff * (1 - gamma), a + diff * gamma)


def reference_fixed(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                    min_ref_years: int = MIN_REF_YEARS,
                    max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Referencia FIXA por (cell, series, month), sempre os 12 meses de cada par existente.
    Colunas: cell, series, month, n_ref_years, ref_mean, ref_std (ddof=1), ref_median,
    ref_p10, ref_p90. Estatisticas NA se n_ref_years < min_ref_years."""
    require_columns(monthly, REQUIRED)
    require_unique(monthly, ["cell", "series", "year", "month"])
    pairs = monthly[["cell", "series"]].drop_duplicates().sort_values(["cell", "series"])
    skeleton = pairs.loc[pairs.index.repeat(12)].reset_index(drop=True)
    skeleton["month"] = np.tile(np.arange(1, 13, dtype="int64"), len(pairs))
    pool = monthly[_in_pool(monthly, ref_start, ref_end, max_unknown_days)]
    gid, n_groups = _group_ids(pool)
    keep = gid >= 0
    pool, gid = pool[keep], gid[keep]
    vals, present, _ = _pool_matrix(gid, n_groups, pool["year"].to_numpy(),
                                    pool["cell_days"].to_numpy(dtype="float64"))
    n = present.sum(axis=1)
    ok = n >= max(min_ref_years, 1)
    safe_n = np.where(n > 0, n, 1)
    mean = vals.sum(axis=1) / safe_n
    ss = (present * (vals - mean[:, None]) ** 2).sum(axis=1)
    std = np.where(n > 1, np.sqrt(ss / np.where(n > 1, n - 1, 1)), np.nan)
    ordered = np.sort(np.where(present, vals, np.inf), axis=1)       # pool primeiro, vazios (inf) no fim
    n1 = np.maximum(n, 1)
    rows = np.arange(len(n))
    median = (ordered[rows, (n1 - 1) // 2] + ordered[rows, n1 // 2]) / 2.0
    _, first = np.unique(gid, return_index=True)                     # primeira linha de cada gid (0..G-1, em ordem)
    stats = pool[KEYS].iloc[first].reset_index(drop=True)
    stats["n_ref_years"] = n
    stats["ref_mean"] = np.where(ok, mean, np.nan)
    stats["ref_std"] = np.where(ok, std, np.nan)
    stats["ref_median"] = np.where(ok, median, np.nan)
    stats["ref_p10"] = np.where(ok, _lerp_percentile(ordered, n1, 10), np.nan)
    stats["ref_p90"] = np.where(ok, _lerp_percentile(ordered, n1, 90), np.nan)
    out = skeleton.merge(stats, on=KEYS, how="left")
    out["n_ref_years"] = out["n_ref_years"].fillna(0).astype("int64")
    out["month"] = out["month"].astype("int64")
    for column in ("ref_mean", "ref_std", "ref_median", "ref_p10", "ref_p90"):
        out[column] = out[column].astype("float64")
    return out[FIXED_COLUMNS].reset_index(drop=True)


def reference_loo(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                  min_ref_years: int = MIN_REF_YEARS,
                  max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Referencia SEM O ANO AVALIADO (leave-one-out): uma linha por linha de entrada.
    Colunas: cell, series, year, month, cell_days, valid_month, n_ref_years, ref_mean,
    ref_std (ddof=1), n_below, n_equal (valores do pool abaixo / iguais a cell_days).
    ref_* e n_ref_years descrevem o pool e existem tambem para linhas invalidas;
    n_below/n_equal so existem para linhas validas. Tudo NA se n_ref_years < min_ref_years."""
    require_columns(monthly, REQUIRED)
    require_unique(monthly, ["cell", "series", "year", "month"])
    m = monthly[REQUIRED].copy()
    valid = valid_mask(m, max_unknown_days).to_numpy()
    m["valid_month"] = valid
    gid, n_groups = _group_ids(m)
    m, gid, valid = m[gid >= 0], gid[gid >= 0], valid[gid >= 0]
    if len(m) == 0:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in LOO_COLUMNS})
    in_pool = _in_pool(m, ref_start, ref_end, max_unknown_days)
    year = m["year"].to_numpy()
    x = m["cell_days"].to_numpy(dtype="float64")
    vals, present, ymin = _pool_matrix(gid[in_pool], n_groups, year[in_pool], x[in_pool])
    width = vals.shape[1]
    col = np.where(in_pool, year - ymin, 0).astype("int64")          # coluna do ano avaliado no pool
    need = max(min_ref_years, 1)
    total = len(m)
    n_out = np.zeros(total, dtype="int64")
    mean_out = np.full(total, np.nan)
    std_out = np.full(total, np.nan)
    below_out = np.zeros(total, dtype="int64")
    equal_out = np.zeros(total, dtype="int64")
    block = max(1, _BLOCK_ELEMENTS // width)
    for start in range(0, total, block):
        sl = slice(start, min(start + block, total))
        v, pr = vals[gid[sl]], present[gid[sl]]                      # copias: (bloco x anos)
        own = in_pool[sl]
        pr[np.flatnonzero(own), col[sl][own]] = False                # retira o ano avaliado do pool
        n = pr.sum(axis=1)
        safe_n = np.where(n > 0, n, 1)
        mean = (pr * v).sum(axis=1) / safe_n
        ss = (pr * (v - mean[:, None]) ** 2).sum(axis=1)
        std = np.where(n > 1, np.sqrt(ss / np.where(n > 1, n - 1, 1)), np.nan)
        xs = x[sl][:, None]
        n_out[sl], mean_out[sl], std_out[sl] = n, mean, std
        below_out[sl] = (pr & (v < xs)).sum(axis=1)
        equal_out[sl] = (pr & (v == xs)).sum(axis=1)
    ok = n_out >= need
    pos_ok = ok & valid
    out = m[["cell", "series", "year", "month", "cell_days", "valid_month"]].copy()
    out["n_ref_years"] = n_out
    out["ref_mean"] = np.where(ok, mean_out, np.nan)
    out["ref_std"] = np.where(ok, std_out, np.nan)
    for name, counts in (("n_below", below_out), ("n_equal", equal_out)):
        out[name] = pd.arrays.IntegerArray(np.where(pos_ok, counts, 0), ~pos_ok)
    out["valid_month"] = out["valid_month"].astype(bool)
    return out[LOO_COLUMNS].sort_values(["cell", "series", "year", "month"]).reset_index(drop=True)

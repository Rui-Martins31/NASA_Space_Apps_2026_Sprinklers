"""Pool de referencia historico partilhado pelas metricas do Lote 4 (HIS-01/02/05/06/07/09).

Funcoes puras sobre o esquema de `l1_cal_monthly`. Regras em spec/metodologia_metricas.md, 7B:
- mes valido = nao parcial e com no maximo MAX_UNKNOWN_DAYS dias de cobertura desconhecida;
- pool de (country, series, month) = valores `cell_days` dos meses validos desse mes civil,
  um por ano, dentro de [ref_start, ref_end] (inclusivos);
- referencia fixa: pool inteiro; leave-one-out: pool sem o ano avaliado;
- abaixo de `min_ref_years` as estatisticas sao NA (n_ref_years informa);
- desvio-padrao amostral (ddof=1); percentis por interpolacao linear.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import require_columns

MAX_UNKNOWN_DAYS = 0
MIN_REF_YEARS = 5

KEYS = ["country", "series", "month"]
REQUIRED = ["country", "series", "year", "month", "cell_days", "partial", "n_unknown_days"]
FIXED_COLUMNS = ["country", "series", "month", "n_ref_years", "ref_mean", "ref_std",
                 "ref_median", "ref_p10", "ref_p90"]
LOO_COLUMNS = ["country", "series", "year", "month", "cell_days", "valid_month",
               "n_ref_years", "ref_mean", "ref_std", "n_below", "n_equal"]


def valid_mask(table: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.Series:
    """Mes (ou ano) valido: nao parcial e com no maximo `max_unknown_days` dias desconhecidos."""
    ok = (table["n_unknown_days"] <= max_unknown_days).fillna(False).astype(bool)
    return (~table["partial"].astype(bool)) & ok


def _pool_groups(monthly: pd.DataFrame, ref_start, ref_end, max_unknown_days):
    """{(country, series, month): (anos, valores)} dos meses validos dentro da janela."""
    ok = valid_mask(monthly, max_unknown_days)
    if ref_start is not None:
        ok &= monthly["year"] >= ref_start
    if ref_end is not None:
        ok &= monthly["year"] <= ref_end
    pool = monthly[ok.to_numpy()]
    return {k: (g["year"].to_numpy(), g["cell_days"].to_numpy(dtype="float64"))
            for k, g in pool.groupby(KEYS, sort=False)}


def reference_fixed(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                    min_ref_years: int = MIN_REF_YEARS,
                    max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Referencia FIXA por (country, series, month), sempre os 12 meses de cada par existente.
    Colunas: country, series, month, n_ref_years, ref_mean, ref_std (ddof=1), ref_median,
    ref_p10, ref_p90. Estatisticas NA se n_ref_years < min_ref_years."""
    require_columns(monthly, REQUIRED)
    groups = _pool_groups(monthly, ref_start, ref_end, max_unknown_days)
    pairs = monthly[["country", "series"]].drop_duplicates().sort_values(["country", "series"])
    rows = []
    for country, series in pairs.itertuples(index=False):
        for month in range(1, 13):
            _, vals = groups.get((country, series, month), (None, np.empty(0)))
            n = len(vals)
            ok = n >= max(min_ref_years, 1)
            rows.append({
                "country": country, "series": series, "month": month, "n_ref_years": n,
                "ref_mean": float(vals.mean()) if ok else np.nan,
                "ref_std": (float(vals.std(ddof=1)) if n > 1 else np.nan) if ok else np.nan,
                "ref_median": float(np.median(vals)) if ok else np.nan,
                "ref_p10": float(np.percentile(vals, 10, method="linear")) if ok else np.nan,
                "ref_p90": float(np.percentile(vals, 90, method="linear")) if ok else np.nan})
    out = pd.DataFrame(rows, columns=FIXED_COLUMNS)
    out["month"] = out["month"].astype("int64")
    out["n_ref_years"] = out["n_ref_years"].astype("int64")
    return out.reset_index(drop=True)


def reference_loo(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                  min_ref_years: int = MIN_REF_YEARS,
                  max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """Referencia SEM O ANO AVALIADO (leave-one-out): uma linha por linha de entrada.
    Colunas: country, series, year, month, cell_days, valid_month, n_ref_years, ref_mean,
    ref_std (ddof=1), n_below, n_equal (valores do pool abaixo / iguais a cell_days).
    ref_* e n_ref_years descrevem o pool e existem tambem para linhas invalidas;
    n_below/n_equal so existem para linhas validas. Tudo NA se n_ref_years < min_ref_years."""
    require_columns(monthly, REQUIRED)
    m = monthly[REQUIRED].copy()
    m["valid_month"] = valid_mask(m, max_unknown_days).to_numpy()
    groups = _pool_groups(monthly, ref_start, ref_end, max_unknown_days)
    parts = []
    need = max(min_ref_years, 1)
    for key, g in m.groupby(KEYS, sort=False):
        years, vals = groups.get(key, (np.empty(0, dtype="int64"), np.empty(0)))
        ev_year = g["year"].to_numpy()
        x = g["cell_days"].to_numpy(dtype="float64")
        use = years[None, :] != ev_year[:, None]                     # (linhas, pool): exclui o ano avaliado
        n = use.sum(axis=1)
        ok = n >= need
        safe_n = np.where(n > 0, n, 1)
        mean = (use * vals[None, :]).sum(axis=1) / safe_n
        ss = (use * (vals[None, :] - mean[:, None]) ** 2).sum(axis=1)
        std = np.where(n > 1, np.sqrt(ss / np.where(n > 1, n - 1, 1)), np.nan)
        below = (use & (vals[None, :] < x[:, None])).sum(axis=1)
        equal = (use & (vals[None, :] == x[:, None])).sum(axis=1)
        valid = g["valid_month"].to_numpy()
        pos_ok = ok & valid
        part = g[["country", "series", "year", "month", "cell_days", "valid_month"]].copy()
        part["n_ref_years"] = n.astype("int64")
        part["ref_mean"] = np.where(ok, mean, np.nan)
        part["ref_std"] = np.where(ok, std, np.nan)
        part["n_below"] = pd.array(np.where(pos_ok, below, 0), dtype="Int64")
        part["n_equal"] = pd.array(np.where(pos_ok, equal, 0), dtype="Int64")
        part.loc[~pos_ok, ["n_below", "n_equal"]] = pd.NA
        parts.append(part)
    if not parts:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in LOO_COLUMNS})
    out = pd.concat(parts, ignore_index=True)[LOO_COLUMNS]
    out["valid_month"] = out["valid_month"].astype(bool)
    return out.sort_values(["country", "series", "year", "month"]).reset_index(drop=True)

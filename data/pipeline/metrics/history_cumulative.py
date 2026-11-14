"""Metricas de historico do Lote 4: HIS-07 (acumulado no ano), HIS-08 (variacao homologa)
e HIS-10 (tendencia anual de Theil-Sen).

Funcoes puras sobre os esquemas de `l1_cal_monthly` e `l1_cal_annual`. Regras em
spec/metodologia_metricas.md, 7B e 7D. A validade (nao parcial e com no maximo
`max_unknown_days` dias desconhecidos) vem de `history_pool.valid_mask`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import require_columns
from .history_pool import MAX_UNKNOWN_DAYS, MIN_REF_YEARS, require_no_na, require_unique, valid_mask

MIN_TREND_YEARS = 8

MONTHLY_REQUIRED = ["country", "series", "year", "month", "cell_days", "partial", "n_unknown_days"]
ANNUAL_REQUIRED = ["country", "series", "year", "cell_days", "partial", "n_unknown_days"]
YTD_COLUMNS = ["country", "series", "year", "month", "ytd_cell_days", "comparable",
               "n_ref_years", "ref_ytd_mean", "ytd_diff"]
YOY_COLUMNS = ["country", "series", "year", "month", "cell_days", "prev_cell_days",
               "valid_pair", "diff_abs", "yoy_pct"]
TREND_COLUMNS = ["country", "series", "n_years", "first_year", "last_year",
                 "slope_per_year", "intercept", "slope_p025", "slope_p975"]


def _frame(columns, dtypes) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=dtypes[c]) for c in columns})


def _month_lookup(monthly: pd.DataFrame, max_unknown_days):
    """{(country, series, year, month): (cell_days, valido)}."""
    ok = valid_mask(monthly, max_unknown_days).to_numpy()
    keys = zip(monthly["country"], monthly["series"], monthly["year"], monthly["month"])
    return {k: (int(c), bool(v)) for k, c, v in zip(keys, monthly["cell_days"], ok)}


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
    require_unique(monthly, ["country", "series", "year", "month"])
    require_no_na(monthly, ["cell_days"])
    dtypes = {"country": "object", "series": "object", "year": "int64", "month": "int64",
              "ytd_cell_days": "Int64", "comparable": "bool", "n_ref_years": "int64",
              "ref_ytd_mean": "float64", "ytd_diff": "float64"}
    if len(monthly) == 0:
        return _frame(YTD_COLUMNS, dtypes)
    look = _month_lookup(monthly, max_unknown_days)
    rows = []
    for (country, series, year, month) in look:
        ytd, comparable = 0, True
        for m in range(1, month + 1):
            item = look.get((country, series, year, m))
            if item is None:
                ytd, comparable = None, False
                break
            ytd += item[0]
            comparable &= item[1]
        rows.append([country, series, int(year), int(month), ytd, comparable])
    # pool por (country, series, month): {ano: ytd} so de linhas comparaveis dentro da janela
    pools: dict = {}
    for country, series, year, month, ytd, comp in rows:
        if not comp:
            continue
        if (ref_start is not None and year < ref_start) or (ref_end is not None and year > ref_end):
            continue
        pools.setdefault((country, series, month), {})[year] = ytd
    need = max(min_ref_years, 1)
    out_rows = []
    for country, series, year, month, ytd, comp in rows:
        vals = [v for y, v in pools.get((country, series, month), {}).items() if y != year]
        ok = comp and len(vals) >= need
        mean = sum(vals) / len(vals) if ok else np.nan
        out_rows.append([country, series, year, month, ytd, comp, len(vals), mean,
                         ytd - mean if ok else np.nan])
    out = pd.DataFrame(out_rows, columns=YTD_COLUMNS)
    out["ytd_cell_days"] = pd.array(out["ytd_cell_days"].tolist(), dtype="Int64")
    out["comparable"] = out["comparable"].astype(bool)
    out["n_ref_years"] = out["n_ref_years"].astype("int64")
    out["ref_ytd_mean"] = out["ref_ytd_mean"].astype("float64")
    out["ytd_diff"] = out["ytd_diff"].astype("float64")
    return out.sort_values(["country", "series", "year", "month"]).reset_index(drop=True)


def his08_yoy(monthly: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-08: variacao homologa face ao mesmo mes do ano anterior.

    `prev_cell_days` = `cell_days` do mesmo pais/serie/mes em year-1 (NA se ausente).
    `valid_pair` = os dois meses presentes e validos. `diff_abs` e `yoy_pct` (=100*diff/prev)
    so existem se `valid_pair`; `yoy_pct` e NA tambem se prev_cell_days == 0 (diff_abs fica).
    """
    require_columns(monthly, MONTHLY_REQUIRED)
    require_unique(monthly, ["country", "series", "year", "month"])
    require_no_na(monthly, ["cell_days"])
    dtypes = {"country": "object", "series": "object", "year": "int64", "month": "int64",
              "cell_days": "int64", "prev_cell_days": "Int64", "valid_pair": "bool",
              "diff_abs": "Int64", "yoy_pct": "float64"}
    if len(monthly) == 0:
        return _frame(YOY_COLUMNS, dtypes)
    look = _month_lookup(monthly, max_unknown_days)
    rows = []
    for (country, series, year, month), (cd, valid) in look.items():
        prev = look.get((country, series, year - 1, month))
        pair = prev is not None and prev[1] and valid
        diff = cd - prev[0] if pair else None
        pct = 100.0 * diff / prev[0] if pair and prev[0] != 0 else np.nan
        rows.append([country, series, int(year), int(month), cd,
                     prev[0] if prev is not None else None, pair, diff, pct])
    out = pd.DataFrame(rows, columns=YOY_COLUMNS)
    out["cell_days"] = out["cell_days"].astype("int64")
    out["prev_cell_days"] = pd.array(out["prev_cell_days"].tolist(), dtype="Int64")
    out["diff_abs"] = pd.array(out["diff_abs"].tolist(), dtype="Int64")
    out["valid_pair"] = out["valid_pair"].astype(bool)
    out["yoy_pct"] = out["yoy_pct"].astype("float64")
    return out.sort_values(["country", "series", "year", "month"]).reset_index(drop=True)


def _theil_sen(x: np.ndarray, y: np.ndarray):
    """(declive, intercepto, p2.5, p97.5) de Theil-Sen; so numpy, pares com x distintos."""
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    slopes = (y[j][keep] - y[i][keep]) / dx[keep]
    slope = float(np.median(slopes))
    return (slope, float(np.median(y - slope * x)),
            float(np.percentile(slopes, 2.5, method="linear")),
            float(np.percentile(slopes, 97.5, method="linear")))


def his10_trend(annual: pd.DataFrame, max_unknown_days: int = MAX_UNKNOWN_DAYS,
                min_years: int = MIN_TREND_YEARS) -> pd.DataFrame:
    """HIS-10: tendencia de Theil-Sen de `cell_days` por ano, por (country, series).

    Usa so anos validos. x = ano, y = cell_days; declive = mediana dos declives de todos os
    pares i<j com x distintos; intercept = mediana(y - declive*x). `slope_p025` e `slope_p975`
    sao os percentis 2,5 e 97,5 (interpolacao linear) dos declives dos pares: sao uma
    DISPERSAO dos declives, NAO um intervalo de confianca formal.
    Com menos de `min_years` anos validos a linha existe (n_years, first_year, last_year) mas as
    quatro estimativas sao NA; sem anos validos, n_years = 0 e o resto NA.
    """
    require_columns(annual, ANNUAL_REQUIRED)
    require_unique(annual, ["country", "series", "year"])
    require_no_na(annual, ["cell_days"])
    dtypes = {"country": "object", "series": "object", "n_years": "int64",
              "first_year": "Int64", "last_year": "Int64", "slope_per_year": "float64",
              "intercept": "float64", "slope_p025": "float64", "slope_p975": "float64"}
    if len(annual) == 0:
        return _frame(TREND_COLUMNS, dtypes)
    work = annual[ANNUAL_REQUIRED].copy()
    work["_ok"] = valid_mask(work, max_unknown_days).to_numpy()
    rows = []
    for (country, series), g in work.groupby(["country", "series"], sort=True):
        g = g[g["_ok"]].sort_values("year")
        n = len(g)
        est = [np.nan] * 4
        if n > 0 and n >= min_years:
            est = _theil_sen(g["year"].to_numpy(dtype="float64"),
                             g["cell_days"].to_numpy(dtype="float64"))
        rows.append([country, series, n,
                     int(g["year"].min()) if n else None, int(g["year"].max()) if n else None,
                     *est])
    out = pd.DataFrame(rows, columns=TREND_COLUMNS)
    out["n_years"] = out["n_years"].astype("int64")
    for c in ("first_year", "last_year"):
        out[c] = pd.array(out[c].tolist(), dtype="Int64")
    for c in TREND_COLUMNS[5:]:
        out[c] = out[c].astype("float64")
    return out.sort_values(["country", "series"]).reset_index(drop=True)

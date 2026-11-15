"""Metricas do Lote 5 sobre cobertura e degrau da serie `combined`: QA-05 e ADD-06.

QA-05: dias com cobertura global confirmada (proxy), complemento do ADD-02 do Lote 4.
ADD-06: efeito do degrau MODIS -> uniao (MODIS + VIIRS) a partir de 2018.

Funcoes puras sobre as tabelas `l1_cal_coverage` e `l1_cal_monthly`, sem I/O. Importa so de
`metrics.common`; `valid_mask` e `require_no_na` sao copias privadas (spec 7B/7E).
"""
from __future__ import annotations

import pandas as pd

from .common import GLOBAL_CELL, require_columns

QA05_COLUMNS = ["instrument", "year", "month", "n_days_expected", "n_days_confirmed",
                "pct_confirmed", "scope"]
ADD06_COLUMNS = ["cell", "year", "n_months", "sum_modis", "sum_combined",
                 "ratio_combined_modis", "excess_pct"]
QA05_SCOPE = "global_proxy"

_MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
_MONTH_KEY = ["cell", "year", "month"]


def valid_mask(table: pd.DataFrame, max_unknown_days: int = 0) -> pd.Series:
    """Mes ou ano valido: nao parcial e com no maximo `max_unknown_days` dias de cobertura desconhecida."""
    return (~table["partial"].astype(bool)) & (table["n_unknown_days"] <= max_unknown_days)


def require_no_na(table: pd.DataFrame, columns) -> None:
    """ValueError claro se alguma das colunas tiver valores em falta."""
    bad = [c for c in columns if table[c].isna().any()]
    if bad:
        raise ValueError(f"valores em falta em {bad}")


def qa05_confirmed_days(coverage: pd.DataFrame) -> pd.DataFrame:
    """QA-05: dias com cobertura global confirmada por instrumento e mes (proxy global).
    `n_days_expected` = dias do calendario do sensor nesse mes (meses das pontas podem ser parciais);
    `n_days_confirmed` = dias com n_rows_global > 0; `pct_confirmed` = 100 * confirmed / expected.
    Soma n_rows_global de (instrumento, data) repetidos antes de contar. `scope` = "global_proxy":
    um dia sem registos globais nao distingue falha de dados de ausencia real de fogo."""
    require_columns(coverage, ["instrument", "date", "n_rows_global"])
    require_no_na(coverage, ["instrument", "date", "n_rows_global"])
    work = pd.DataFrame({
        "instrument": coverage["instrument"].astype(object).to_numpy(),
        "date": pd.to_datetime(coverage["date"]).dt.normalize().to_numpy(),   # um dia = uma data (sem hora)
        "n_rows_global": coverage["n_rows_global"].astype("int64").to_numpy(),
    })
    days = work.groupby(["instrument", "date"], observed=True)["n_rows_global"].sum().reset_index()
    days["year"] = days["date"].dt.year.astype("int64")
    days["month"] = days["date"].dt.month.astype("int64")
    days["is_confirmed"] = (days["n_rows_global"] > 0).astype("int64")
    out = (days.groupby(["instrument", "year", "month"], observed=True)
           .agg(n_days_expected=("date", "size"), n_days_confirmed=("is_confirmed", "sum")).reset_index())
    out["n_days_expected"] = out["n_days_expected"].astype("int64")
    out["n_days_confirmed"] = out["n_days_confirmed"].astype("int64")
    out["pct_confirmed"] = (100.0 * out["n_days_confirmed"] / out["n_days_expected"]).astype("float64")
    out["scope"] = QA05_SCOPE
    out = out[QA05_COLUMNS]
    return out.sort_values(["instrument", "year", "month"]).reset_index(drop=True)


def add06_union_step(monthly: pd.DataFrame, max_unknown_days: int = 0) -> pd.DataFrame:
    """ADD-06: degrau da serie `combined` face a `modis` por celula e ano (`l1_cal_monthly` denso, com
    `cell`; saida de `densify_monthly`). So contam os meses (celula, ano, mes) com as series `modis` e
    `combined` ambas validas (`valid_mask`); a serie `viirs` e ignorada. `ratio_combined_modis` =
    sum_combined / sum_modis (NA se sum_modis = 0); `excess_pct` = 100 * (ratio - 1). Linha extra
    `cell = GLOBAL_CELL` por ano (substitui a antiga `ALL`): soma das celulas recebidas, com `n_months` =
    meses distintos em que alguma celula contribui; o racio da linha global sai das somas. A linha
    global so cobre as celulas dadas (fatias disjuntas somam sum_*, mas n_months nao). Colunas: cell,
    year, n_months, sum_modis, sum_combined, ratio_combined_modis, excess_pct.
    Chaves (cell, series, year, month) repetidas => ValueError."""
    require_columns(monthly, _MONTHLY_COLUMNS)
    require_no_na(monthly, _MONTHLY_COLUMNS)
    work = pd.DataFrame({
        "cell": monthly["cell"].astype("int64").to_numpy(),
        "year": monthly["year"].astype("int64").to_numpy(),
        "month": monthly["month"].astype("int64").to_numpy(),
        "series": monthly["series"].astype(object).to_numpy(),
        "cell_days": monthly["cell_days"].astype("int64").to_numpy(),
        "partial": monthly["partial"].astype(bool).to_numpy(),
        "n_unknown_days": monthly["n_unknown_days"].astype("int64").to_numpy(),
    })
    if (work["cell"] < 0).any():
        raise ValueError("cell negativo em l1_cal_monthly (GLOBAL_CELL nao e uma celula)")
    if work.duplicated(["cell", "series", "year", "month"]).any():
        raise ValueError("chaves (cell, series, year, month) repetidas em l1_cal_monthly")
    valid = work[valid_mask(work, max_unknown_days)]
    modis = (valid[valid["series"] == "modis"][_MONTH_KEY + ["cell_days"]]
             .rename(columns={"cell_days": "sum_modis"}))
    combined = (valid[valid["series"] == "combined"][_MONTH_KEY + ["cell_days"]]
                .rename(columns={"cell_days": "sum_combined"}))
    both = modis.merge(combined, on=_MONTH_KEY, how="inner")           # meses validos nas duas series
    per_cell = (both.groupby(["cell", "year"], observed=True)
                .agg(n_months=("month", "size"), sum_modis=("sum_modis", "sum"),
                     sum_combined=("sum_combined", "sum")).reset_index())
    total = (both.groupby("year", observed=True)
             .agg(n_months=("month", "nunique"), sum_modis=("sum_modis", "sum"),
                  sum_combined=("sum_combined", "sum")).reset_index())
    total["cell"] = GLOBAL_CELL
    out = pd.concat([per_cell, total[per_cell.columns]], ignore_index=True)
    for col in ("cell", "year", "n_months", "sum_modis", "sum_combined"):
        out[col] = out[col].astype("int64")
    ratio = out["sum_combined"] / out["sum_modis"].where(out["sum_modis"] != 0)   # sum_modis = 0 => NA
    out["ratio_combined_modis"] = ratio.astype("float64")
    out["excess_pct"] = (100.0 * (ratio - 1.0)).astype("float64")
    out = out[ADD06_COLUMNS]
    return out.sort_values(["cell", "year"]).reset_index(drop=True)

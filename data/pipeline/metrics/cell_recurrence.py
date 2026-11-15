"""Metricas espaciais do Lote 5 sobre celulas ativas: ESP-02, ESP-03 e ESP-06.

Entrada comum: `build_cell_year`, derivada de `cell_days` (saida de `eligible_cell_days` do L1,
chave `cell`; `country` ja nao e chave). `build_cell_year` e a tabela POR CELULA (esparsa: so
celulas-ano com detecao). ESP-02/03/06 sao estatisticas de POPULACAO sobre todas as celulas
recebidas: o resultado e uma linha por (serie, ano) ou por serie, e leva `cell = GLOBAL_CELL`
(-1) fixo, como as restantes tabelas globais do pipeline (assim todas as tabelas partilham a
coluna de chave `cell` e o backend filtra `cell = -1`). Quem chama (o notebook) escolhe o
conjunto de celulas. Por celula ha `esp06_cell_years_active`.
Funcoes puras sobre DataFrames, sem I/O. Especificacao: spec/metodologia_metricas.md (7E, 7F).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import GLOBAL_CELL, as_series_views, require_columns

CELL_YEAR_COLUMNS = ["cell", "series", "year", "n_days"]
_CELL_YEAR_KEY = ["cell", "series", "year"]


def build_cell_year(cell_days: pd.DataFrame) -> pd.DataFrame:
    """Dias distintos com detecao de cada celula, por serie e ano (tabela por celula, esparsa).

    `combined` e a uniao por (data, celula) entre sensores; satelites do mesmo sensor contam uma
    vez. Series sem linhas nao aparecem. Colunas: cell, series, year, n_days (int64 salvo series),
    ordenada por (cell, series, year). Levanta ValueError se faltarem colunas, houver valores em
    falta em date/cell, `cell` negativo (GLOBAL_CELL nao e uma celula) ou um instrumento diferente
    de MODIS/VIIRS."""
    require_columns(cell_days, ["date", "cell", "instrument"])
    for col in ("date", "cell"):
        if cell_days[col].isna().any():
            raise ValueError(f"valores em falta em {col!r}")
    work = pd.DataFrame({
        "date": pd.to_datetime(cell_days["date"]).dt.normalize().to_numpy(),
        "cell": cell_days["cell"].astype("int64").to_numpy(),
        "instrument": cell_days["instrument"].astype(object).to_numpy(),
    })
    if (work["cell"] < 0).any():
        raise ValueError("cell negativo em cell_days (GLOBAL_CELL nao e uma celula)")
    parts = []
    for series, sub in as_series_views(work).items():
        days = sub.drop_duplicates(["cell", "date"])
        g = (days.assign(year=days["date"].dt.year.astype("int64"))
             .groupby(["cell", "year"], observed=True).size().rename("n_days").reset_index())
        g["series"] = series
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)[CELL_YEAR_COLUMNS]
    out = out.astype({"cell": "int64", "year": "int64", "n_days": "int64"})
    return out.sort_values(_CELL_YEAR_KEY).reset_index(drop=True)


# ---------------------------------------------------------------- ESP-02, ESP-03, ESP-06
ESP02_COLUMNS = ["cell", "series", "year", "n_active_cells"]
ESP03_COLUMNS = ["cell", "series", "year", "n_active_cells", "mean_days", "median_days", "p90_days",
                 "max_days", "n_cells_1d", "n_cells_2_5d", "n_cells_6_15d", "n_cells_16plus"]
ESP06_COLUMNS = ["cell", "series", "n_years_analysed", "n_cells", "n_cells_2plus_years",
                 "pct_cells_2plus", "mean_years_per_cell", "max_years"]
ESP06_CELL_COLUMNS = ["cell", "series", "n_years_active", "n_years_valid"]
ELIGIBLE_YEARS_COLUMNS = ["series", "year"]
_ESP02_DTYPES = {"cell": "int64", "series": "object", "year": "int64", "n_active_cells": "int64"}
_ESP03_DTYPES = {"cell": "int64", "series": "object", "year": "int64", "n_active_cells": "int64",
                 "mean_days": "float64", "median_days": "float64", "p90_days": "float64", "max_days": "int64",
                 "n_cells_1d": "int64", "n_cells_2_5d": "int64", "n_cells_6_15d": "int64",
                 "n_cells_16plus": "int64"}
_ESP06_DTYPES = {"cell": "int64", "series": "object", "n_years_analysed": "int64", "n_cells": "int64",
                 "n_cells_2plus_years": "int64", "pct_cells_2plus": "float64",
                 "mean_years_per_cell": "float64", "max_years": "Int64"}
_ESP06_CELL_DTYPES = {"cell": "int64", "series": "object", "n_years_active": "int64",
                      "n_years_valid": "int64"}


def _require_no_na(df: pd.DataFrame, columns) -> None:
    for col in columns:
        if df[col].isna().any():
            raise ValueError(f"valores em falta em {col!r}")


def _empty(dtypes: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in dtypes.items()})


def _clean_cell_year(cell_year: pd.DataFrame) -> pd.DataFrame:
    """Valida e normaliza os dtypes de cell-year. ValueError se faltarem colunas, houver valores em
    falta, n_days <= 0, cell negativo ou chaves (cell, series, year) repetidas."""
    require_columns(cell_year, CELL_YEAR_COLUMNS)
    _require_no_na(cell_year, CELL_YEAR_COLUMNS)
    work = pd.DataFrame({
        "cell": cell_year["cell"].astype("int64").to_numpy(),
        "series": cell_year["series"].astype(object).to_numpy(),
        "year": cell_year["year"].astype("int64").to_numpy(),
        "n_days": cell_year["n_days"].astype("int64").to_numpy(),
    })
    if (work["n_days"] <= 0).any():
        raise ValueError("n_days tem de ser >= 1 em todas as linhas de cell_year")
    if (work["cell"] < 0).any():
        raise ValueError("cell negativo em cell_year (GLOBAL_CELL nao e uma celula)")
    if work.duplicated(_CELL_YEAR_KEY).any():
        raise ValueError("chaves (cell, series, year) duplicadas em cell_year")
    return work


def _global_first(out: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta a coluna `cell = GLOBAL_CELL` (primeira) a uma estatistica de populacao."""
    out.insert(0, "cell", np.full(len(out), GLOBAL_CELL, dtype="int64"))
    return out


def esp02_active_cells(cell_year: pd.DataFrame) -> pd.DataFrame:
    """ESP-02: celulas ativas (distintas, com n_days >= 1) por serie e ano, sobre TODAS as celulas
    de `cell_year`. Linha global: `cell = GLOBAL_CELL`. Soma-se entre fatias disjuntas de celulas."""
    work = _clean_cell_year(cell_year)
    if work.empty:
        return _empty(_ESP02_DTYPES)
    out = (work.groupby(["series", "year"], observed=True).size()
           .rename("n_active_cells").reset_index())
    out = _global_first(out).astype(_ESP02_DTYPES)[ESP02_COLUMNS]
    return out.sort_values(["series", "year"]).reset_index(drop=True)


def esp03_recurrence(cell_year: pd.DataFrame) -> pd.DataFrame:
    """ESP-03: recorrencia (dias com detecao por celula ativa) por serie e ano, sobre TODAS as celulas
    de `cell_year` (`cell = GLOBAL_CELL`). Estatisticas de n_days sobre as celulas ativas; p90 =
    percentil linear; baldes 1, 2-5, 6-15, >=16 dias. Os baldes e n_active_cells somam entre fatias
    disjuntas de celulas; media, mediana e p90 nao (so se calculam com todas as celulas juntas).
    O ciclo e por (serie, ano): no maximo 3 series x anos, nunca por celula."""
    work = _clean_cell_year(cell_year)
    if work.empty:
        return _empty(_ESP03_DTYPES)
    rows = []
    for (series, year), vals in work.groupby(["series", "year"], observed=True)["n_days"]:
        d = vals.to_numpy()
        rows.append((GLOBAL_CELL, series, year, d.size, d.mean(), np.median(d),
                     np.percentile(d, 90, method="linear"), d.max(),
                     int((d == 1).sum()), int(((d >= 2) & (d <= 5)).sum()),
                     int(((d >= 6) & (d <= 15)).sum()), int((d >= 16).sum())))
    out = pd.DataFrame(rows, columns=ESP03_COLUMNS).astype(_ESP03_DTYPES)
    return out.sort_values(["series", "year"]).reset_index(drop=True)


def _eligible_frame(work: pd.DataFrame, eligible_years: pd.DataFrame | None) -> pd.DataFrame:
    """Anos validos (series, year): os fornecidos (validados) ou, se None, os presentes em `work`."""
    if eligible_years is None:
        return work[["series", "year"]].drop_duplicates()
    require_columns(eligible_years, ELIGIBLE_YEARS_COLUMNS)
    _require_no_na(eligible_years, ELIGIBLE_YEARS_COLUMNS)
    eligible = pd.DataFrame({
        "series": eligible_years["series"].astype(object).to_numpy(),
        "year": eligible_years["year"].astype("int64").to_numpy(),
    })
    if eligible.duplicated().any():
        raise ValueError("chaves (series, year) duplicadas em eligible_years")
    return eligible


def esp06_interannual(cell_year: pd.DataFrame, eligible_years: pd.DataFrame | None = None) -> pd.DataFrame:
    """ESP-06: recorrencia interanual das celulas, por serie, sobre TODAS as celulas de `cell_year`
    (`cell = GLOBAL_CELL`). `eligible_years` (series, year) = anos validos (global: nao depende da
    celula); so esses entram (None = todos os presentes em cell_year). Por celula conta-se o nº de
    anos elegiveis com detecao. Series com anos elegiveis mas sem celulas aparecem com n_cells = 0
    (pct, media e max NA); series de cell_year sem ano elegivel, com n_years_analysed = 0.
    ValueError em chaves repetidas ou valores em falta em eligible_years."""
    work = _clean_cell_year(cell_year)
    eligible = _eligible_frame(work, eligible_years)
    gkeys = ["series"]
    groups = pd.concat([eligible[gkeys], work[gkeys]]).drop_duplicates()
    if groups.empty:
        return _empty(_ESP06_DTYPES)
    n_years = eligible.groupby(gkeys, observed=True).size().rename("n_years_analysed").reset_index()
    kept = work.merge(eligible, on=gkeys + ["year"], how="inner")
    per_cell = kept.groupby(gkeys + ["cell"], observed=True).size().rename("years").reset_index()
    per_cell["is_2plus"] = (per_cell["years"] >= 2).astype("int64")
    stats = (per_cell.groupby(gkeys, observed=True)
             .agg(n_cells=("years", "size"), n_cells_2plus_years=("is_2plus", "sum"),
                  mean_years_per_cell=("years", "mean"), max_years=("years", "max")).reset_index())
    out = groups.merge(n_years, on=gkeys, how="left").merge(stats, on=gkeys, how="left")
    for col in ("n_years_analysed", "n_cells", "n_cells_2plus_years"):
        out[col] = out[col].fillna(0).astype("int64")
    has_cells = out["n_cells"] > 0
    out["pct_cells_2plus"] = (100.0 * out["n_cells_2plus_years"] / out["n_cells"]).where(has_cells)
    out["mean_years_per_cell"] = out["mean_years_per_cell"].where(has_cells).astype("float64")
    out["max_years"] = out["max_years"].where(has_cells).astype("Int64")
    out = _global_first(out)[ESP06_COLUMNS].astype(_ESP06_DTYPES)
    return out.sort_values(gkeys).reset_index(drop=True)


def esp06_cell_years_active(cell_year: pd.DataFrame, eligible_years: pd.DataFrame | None = None) -> pd.DataFrame:
    """ESP-06 por celula: anos validos com atividade de cada celula. Tabela ESPARSA com
    cell, series, n_years_active, n_years_valid: `n_years_active` = anos de `eligible_years`
    (series, year) em que a celula tem detecao (>= 1; celulas sem nenhum ano valido ativo nao
    aparecem) e `n_years_valid` = nº de anos validos da serie (igual para todas as celulas da serie:
    o conjunto de anos validos e global). `eligible_years=None` => os anos presentes em `cell_year`.
    Mesmas validacoes que `esp06_interannual`. Ordenada por (cell, series)."""
    work = _clean_cell_year(cell_year)
    eligible = _eligible_frame(work, eligible_years)
    if work.empty or eligible.empty:
        return _empty(_ESP06_CELL_DTYPES)
    n_valid = eligible.groupby("series", observed=True).size().rename("n_years_valid").reset_index()
    kept = work.merge(eligible, on=["series", "year"], how="inner")
    out = (kept.groupby(["cell", "series"], observed=True).size().rename("n_years_active").reset_index()
           .merge(n_valid, on="series", how="left"))
    out = out[ESP06_CELL_COLUMNS].astype(_ESP06_CELL_DTYPES)
    return out.sort_values(["cell", "series"]).reset_index(drop=True)

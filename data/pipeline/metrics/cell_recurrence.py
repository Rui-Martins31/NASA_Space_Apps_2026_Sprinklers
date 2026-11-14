"""Metricas espaciais do Lote 5 sobre celulas ativas: ESP-02, ESP-03 e ESP-06.

Entrada comum: `build_cell_year`, derivada de `cell_days` (saida de `eligible_cell_days` do L1).
Funcoes puras sobre DataFrames, sem I/O. Especificacao: spec/metodologia_metricas.md (7E, 7F).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import as_series_views, require_columns

CELL_YEAR_COLUMNS = ["country", "series", "cell", "year", "n_days"]


def build_cell_year(cell_days: pd.DataFrame) -> pd.DataFrame:
    """Dias distintos com detecao de cada celula, por pais, serie e ano.

    `combined` e a uniao por (pais, data, celula) entre sensores; satelites do mesmo sensor
    contam uma vez. Series sem linhas nao aparecem. Levanta ValueError se faltarem colunas,
    houver valores em falta em country/date/cell ou um instrumento diferente de MODIS/VIIRS."""
    require_columns(cell_days, ["country", "date", "cell", "instrument"])
    for col in ("country", "date", "cell"):
        if cell_days[col].isna().any():
            raise ValueError(f"valores em falta em {col!r}")
    work = pd.DataFrame({
        "country": cell_days["country"].astype(object).to_numpy(),
        "date": pd.to_datetime(cell_days["date"]).dt.normalize().to_numpy(),
        "cell": cell_days["cell"].astype("int64").to_numpy(),
        "instrument": cell_days["instrument"].astype(object).to_numpy(),
    })
    parts = []
    for series, sub in as_series_views(work).items():
        days = sub.drop_duplicates(["country", "date", "cell"])
        g = (days.assign(year=days["date"].dt.year.astype("int64"))
             .groupby(["country", "cell", "year"], observed=True).size().rename("n_days").reset_index())
        g["series"] = series
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)[CELL_YEAR_COLUMNS]
    out = out.astype({"cell": "int64", "year": "int64", "n_days": "int64"})
    return out.sort_values(["country", "series", "cell", "year"]).reset_index(drop=True)


# ---------------------------------------------------------------- ESP-02, ESP-03, ESP-06
ESP02_COLUMNS = ["country", "series", "year", "n_active_cells"]
ESP03_COLUMNS = ["country", "series", "year", "n_active_cells", "mean_days", "median_days", "p90_days",
                 "max_days", "n_cells_1d", "n_cells_2_5d", "n_cells_6_15d", "n_cells_16plus"]
ESP06_COLUMNS = ["country", "series", "n_years_analysed", "n_cells", "n_cells_2plus_years",
                 "pct_cells_2plus", "mean_years_per_cell", "max_years"]
ELIGIBLE_YEARS_COLUMNS = ["country", "series", "year"]
_ESP02_DTYPES = {"country": "object", "series": "object", "year": "int64", "n_active_cells": "int64"}
_ESP03_DTYPES = {"country": "object", "series": "object", "year": "int64", "n_active_cells": "int64",
                 "mean_days": "float64", "median_days": "float64", "p90_days": "float64", "max_days": "int64",
                 "n_cells_1d": "int64", "n_cells_2_5d": "int64", "n_cells_6_15d": "int64",
                 "n_cells_16plus": "int64"}
_ESP06_DTYPES = {"country": "object", "series": "object", "n_years_analysed": "int64", "n_cells": "int64",
                 "n_cells_2plus_years": "int64", "pct_cells_2plus": "float64",
                 "mean_years_per_cell": "float64", "max_years": "Int64"}


def _require_no_na(df: pd.DataFrame, columns) -> None:
    for col in columns:
        if df[col].isna().any():
            raise ValueError(f"valores em falta em {col!r}")


def _empty(dtypes: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in dtypes.items()})


def _clean_cell_year(cell_year: pd.DataFrame) -> pd.DataFrame:
    """Valida e normaliza os dtypes de cell-year. ValueError se faltarem colunas, houver valores em
    falta, n_days <= 0 ou chaves (country, series, cell, year) repetidas."""
    require_columns(cell_year, CELL_YEAR_COLUMNS)
    _require_no_na(cell_year, CELL_YEAR_COLUMNS)
    work = pd.DataFrame({
        "country": cell_year["country"].astype(object).to_numpy(),
        "series": cell_year["series"].astype(object).to_numpy(),
        "cell": cell_year["cell"].astype("int64").to_numpy(),
        "year": cell_year["year"].astype("int64").to_numpy(),
        "n_days": cell_year["n_days"].astype("int64").to_numpy(),
    })
    if (work["n_days"] <= 0).any():
        raise ValueError("n_days tem de ser >= 1 em todas as linhas de cell_year")
    if work.duplicated(["country", "series", "cell", "year"]).any():
        raise ValueError("chaves (country, series, cell, year) duplicadas em cell_year")
    return work


def esp02_active_cells(cell_year: pd.DataFrame) -> pd.DataFrame:
    """ESP-02: celulas ativas (distintas, com n_days >= 1) por pais, serie e ano."""
    work = _clean_cell_year(cell_year)
    if work.empty:
        return _empty(_ESP02_DTYPES)
    out = (work.groupby(["country", "series", "year"], observed=True).size()
           .rename("n_active_cells").reset_index())
    out = out.astype(_ESP02_DTYPES)[ESP02_COLUMNS]
    return out.sort_values(["country", "series", "year"]).reset_index(drop=True)


def esp03_recurrence(cell_year: pd.DataFrame) -> pd.DataFrame:
    """ESP-03: recorrencia (dias com detecao por celula ativa) por pais, serie e ano.
    Estatisticas de n_days sobre as celulas ativas; p90 = percentil linear; baldes 1, 2-5, 6-15, >=16 dias."""
    work = _clean_cell_year(cell_year)
    if work.empty:
        return _empty(_ESP03_DTYPES)
    rows = []
    for (country, series, year), vals in work.groupby(["country", "series", "year"], observed=True)["n_days"]:
        d = vals.to_numpy()
        rows.append((country, series, year, d.size, d.mean(), np.median(d),
                     np.percentile(d, 90, method="linear"), d.max(),
                     int((d == 1).sum()), int(((d >= 2) & (d <= 5)).sum()),
                     int(((d >= 6) & (d <= 15)).sum()), int((d >= 16).sum())))
    out = pd.DataFrame(rows, columns=ESP03_COLUMNS).astype(_ESP03_DTYPES)
    return out.sort_values(["country", "series", "year"]).reset_index(drop=True)


def esp06_interannual(cell_year: pd.DataFrame, eligible_years: pd.DataFrame | None = None) -> pd.DataFrame:
    """ESP-06: recorrencia interanual das celulas, por pais e serie.
    `eligible_years` (country, series, year) = anos validos; so esses entram (None = todos os presentes em
    cell_year). Por celula conta-se o nº de anos elegiveis com detecao. Grupos com anos elegiveis mas sem
    celulas aparecem com n_cells = 0 (pct, media e max NA); grupos de cell_year sem ano elegivel, com
    n_years_analysed = 0. ValueError em chaves repetidas ou valores em falta em eligible_years."""
    work = _clean_cell_year(cell_year)
    gkeys = ["country", "series"]
    if eligible_years is None:
        eligible = work[gkeys + ["year"]].drop_duplicates()
    else:
        require_columns(eligible_years, ELIGIBLE_YEARS_COLUMNS)
        _require_no_na(eligible_years, ELIGIBLE_YEARS_COLUMNS)
        eligible = pd.DataFrame({
            "country": eligible_years["country"].astype(object).to_numpy(),
            "series": eligible_years["series"].astype(object).to_numpy(),
            "year": eligible_years["year"].astype("int64").to_numpy(),
        })
        if eligible.duplicated().any():
            raise ValueError("chaves (country, series, year) duplicadas em eligible_years")
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
    out = out[ESP06_COLUMNS].astype(_ESP06_DTYPES)
    return out.sort_values(gkeys).reset_index(drop=True)

"""Metricas de meta-cobertura do Lote 4: ADD-01 (satelites ativos) e ADD-02 (dias sem deteccoes).

Funcoes puras sobre as tabelas `l1_obs01_raw_counts` e `l1_cal_coverage`, sem I/O.
"""
from __future__ import annotations

import pandas as pd

from .common import require_columns
from .history_pool import require_no_na

ADD01_COLUMNS = ["instrument", "year", "month", "n_satellites", "satellites"]
ADD02_COLUMNS = ["instrument", "year", "month", "n_days", "n_zero_days", "pct_zero_days"]


def add01_active_satellites(obs01: pd.DataFrame) -> pd.DataFrame:
    """ADD-01: satelites ativos por instrumento e mes, a nivel global.
    Soma `n_raw` por (instrumento, ano, mes, satelite) sobre todas as celulas; o satelite e
    ativo se a soma for > 0. Meses sem satelite ativo nao aparecem."""
    require_columns(obs01, ["cell", "year", "month", "instrument", "satellite", "n_raw"])
    require_no_na(obs01, ["year", "month", "instrument", "satellite", "n_raw"])
    work = pd.DataFrame({
        "instrument": obs01["instrument"].astype(object).to_numpy(),
        "year": obs01["year"].astype("int64").to_numpy(),
        "month": obs01["month"].astype("int64").to_numpy(),
        "satellite": obs01["satellite"].astype(object).to_numpy(),
        "n_raw": obs01["n_raw"].astype("int64").to_numpy(),
    })
    summed = work.groupby(["instrument", "year", "month", "satellite"], observed=True)["n_raw"].sum()
    active = summed[summed > 0].reset_index()
    rows = []
    for (inst, year, month), g in active.groupby(["instrument", "year", "month"], observed=True):
        names = sorted(g["satellite"])
        rows.append((inst, int(year), int(month), len(names), ",".join(names)))
    out = pd.DataFrame(rows, columns=ADD01_COLUMNS)
    out["year"] = out["year"].astype("int64")
    out["month"] = out["month"].astype("int64")
    out["n_satellites"] = out["n_satellites"].astype("int64")
    return out.sort_values(["instrument", "year", "month"]).reset_index(drop=True)


def add02_zero_days(coverage: pd.DataFrame) -> pd.DataFrame:
    """ADD-02: dias sem deteccoes globais por instrumento e mes.
    `n_days` = dias do calendario do sensor nesse mes (meses das pontas podem ser parciais);
    `n_zero_days` = dias com n_rows_global == 0; `pct_zero_days` = 100 * n_zero_days / n_days.
    Soma n_rows_global de (instrumento, data) repetidos (varios ficheiros) antes de contar."""
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
    days["is_zero"] = (days["n_rows_global"] == 0).astype("int64")
    out = (days.groupby(["instrument", "year", "month"], observed=True)
           .agg(n_days=("date", "size"), n_zero_days=("is_zero", "sum")).reset_index())
    out["n_days"] = out["n_days"].astype("int64")
    out["n_zero_days"] = out["n_zero_days"].astype("int64")
    out["pct_zero_days"] = (100.0 * out["n_zero_days"] / out["n_days"]).astype("float64")
    out = out[ADD02_COLUMNS]
    return out.sort_values(["instrument", "year", "month"]).reset_index(drop=True)

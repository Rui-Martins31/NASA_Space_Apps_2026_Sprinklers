"""Metricas de calendario do Lote 1: CAL-01/02 (diaria), CAL-03 (mensal), CAL-04 (anual).

Unidade: celula-dia (par distinto celula x dia UTC) sobre deteccoes elegiveis.
Series: `modis`, `viirs` e `combined` (uniao de celulas-dia; uma celula-dia detetada pelos
dois sensores conta 1). Antes de 2018 so existe MODIS, por isso `combined` tem um degrau
artificial em 2018: ver spec/metodologia_metricas.md.
"""
from __future__ import annotations

import pandas as pd

from .common import GRID_DEG, as_series_views, parse_dates, require_columns
from .counts import _eligible_cell_days

SERIES = ("modis", "viirs", "combined")
INSTRUMENTS = ("MODIS", "VIIRS")
MONTHLY_COLUMNS = ["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
ANNUAL_COLUMNS = ["country", "year", "series", "cell_days", "partial", "n_unknown_days"]


def eligible_cell_days(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """Celulas-dia elegiveis distintas por satelite: country, date, cell, instrument, satellite.
    Tabela compacta que o notebook guarda por ficheiro (nao mantem o VIIRS inteiro em memoria)."""
    _, dedup = _eligible_cell_days(df, grid_deg)
    cols = ["country", "date", "cell", "instrument", "satellite"]
    return dedup[cols].sort_values(cols).reset_index(drop=True)


def cal_daily(cell_days: pd.DataFrame) -> pd.DataFrame:
    """CAL-01/CAL-02: celulas ativas por pais, dia e serie (so dias com atividade).
    Levanta ValueError se existir um instrumento diferente de MODIS/VIIRS."""
    require_columns(cell_days, ["country", "date", "cell", "instrument"])
    parts = []
    for series, sub in as_series_views(cell_days).items():
        g = (sub.drop_duplicates(["country", "date", "cell"])
             .groupby(["country", "date"], observed=True).size().rename("n_cells").reset_index())
        g["series"] = series
        parts.append(g[["country", "date", "series", "n_cells"]])
    out = pd.concat(parts, ignore_index=True)
    out["n_cells"] = out["n_cells"].astype("int64")
    return out.sort_values(["country", "date", "series"]).reset_index(drop=True)


def global_day_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Deteccoes (todas as linhas com data valida) por instrumento e dia, a nivel global.
    Por ficheiro; o notebook concatena os anos antes de chamar cal_coverage."""
    require_columns(df, ["instrument", "acq_date"])
    work = pd.DataFrame({"instrument": df["instrument"].astype("string").str.upper().to_numpy(),
                         "date": parse_dates(df["acq_date"]).to_numpy()})
    work = work[work["date"].notna()]
    out = (work.groupby(["instrument", "date"], observed=True).size()
           .rename("n_rows_global").reset_index())
    out["n_rows_global"] = out["n_rows_global"].astype("int64")
    return out.sort_values(["instrument", "date"]).reset_index(drop=True)


def cal_coverage(day_counts: pd.DataFrame) -> pd.DataFrame:
    """Calendario completo de [primeira, ultima] data de cada sensor, com 0 nos dias sem
    nenhuma deteccao global (=> cobertura desconhecida). Soma dias repetidos (varios ficheiros)."""
    require_columns(day_counts, ["instrument", "date", "n_rows_global"])
    parts = []
    for inst, g in day_counts.groupby("instrument", observed=True):
        s = g.groupby("date")["n_rows_global"].sum()
        full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"), fill_value=0)
        parts.append(pd.DataFrame({"instrument": inst, "date": full.index,
                                   "n_rows_global": full.to_numpy().astype("int64")}))
    if not parts:
        return pd.DataFrame({"instrument": pd.Series(dtype="string"),
                             "date": pd.Series(dtype="datetime64[ns]"),
                             "n_rows_global": pd.Series(dtype="int64")})
    return pd.concat(parts, ignore_index=True).sort_values(["instrument", "date"]).reset_index(drop=True)


def _series_ranges(coverage: pd.DataFrame) -> dict:
    """series -> (primeira data, ultima data, datas sem deteccao global). `combined` cobre da
    menor primeira a maior ultima; um dia e desconhecido se a soma dos sensores for 0."""
    unknown_inst = sorted(set(coverage["instrument"]) - set(INSTRUMENTS))
    if unknown_inst:
        raise ValueError(f"instrumento desconhecido na cobertura: {unknown_inst}")
    out = {}
    for inst in INSTRUMENTS:
        g = coverage[coverage["instrument"] == inst]
        if len(g):
            out[inst.lower()] = (g["date"].min(), g["date"].max(),
                                 pd.DatetimeIndex(g.loc[g["n_rows_global"] == 0, "date"]))
    first, last = coverage["date"].min(), coverage["date"].max()
    total = coverage.groupby("date")["n_rows_global"].sum().reindex(
        pd.date_range(first, last, freq="D"), fill_value=0)
    out["combined"] = (first, last, pd.DatetimeIndex(total.index[total.to_numpy() == 0]))
    return out


def cal_monthly(daily: pd.DataFrame, coverage: pd.DataFrame, countries=None) -> pd.DataFrame:
    """CAL-03: celulas-dia por pais, mes e serie, DENSO (meses sem atividade valem 0), apenas
    dentro do intervalo de cada serie. `partial`: o mes nao esta totalmente dentro de
    [primeira, ultima]. `n_unknown_days`: dias do mes sem deteccao global (cobertura desconhecida).
    Levanta ValueError se existirem dias com atividade fora do intervalo da serie."""
    require_columns(daily, ["country", "date", "series", "n_cells"])
    require_columns(coverage, ["instrument", "date", "n_rows_global"])
    empty = pd.DataFrame({c: pd.Series(dtype="object") for c in MONTHLY_COLUMNS})
    if len(coverage) == 0:
        if len(daily):
            raise ValueError("ha atividade diaria mas a cobertura esta vazia")
        return empty
    if countries is None:
        countries = sorted(daily["country"].unique())
    countries = list(countries)
    parts = []
    for series, (first, last, unknown) in _series_ranges(coverage).items():
        d = daily[daily["series"] == series]
        if len(d) and (d["date"].min() < first or d["date"].max() > last):
            raise ValueError(f"atividade diaria fora do intervalo de cobertura da serie '{series}'")
        months = pd.period_range(first, last, freq="M")
        if not countries:
            continue
        idx = pd.MultiIndex.from_product([countries, months], names=["country", "period"])
        frame = idx.to_frame(index=False)
        sums = d.groupby(["country", d["date"].dt.to_period("M")])["n_cells"].sum()
        sums.index = sums.index.set_names(["country", "period"])
        frame["cell_days"] = sums.reindex(idx, fill_value=0).to_numpy().astype("int64")
        unk = pd.Series(unknown.to_period("M")).value_counts()
        frame["n_unknown_days"] = frame["period"].map(unk).fillna(0).astype("int64")
        starts = frame["period"].map(lambda p: p.start_time)
        ends = frame["period"].map(lambda p: p.end_time.normalize())
        frame["partial"] = ~((starts >= first) & (ends <= last))
        frame["year"] = frame["period"].map(lambda p: p.year).astype("int64")
        frame["month"] = frame["period"].map(lambda p: p.month).astype("int64")
        frame["series"] = series
        parts.append(frame[MONTHLY_COLUMNS])
    if not parts:
        return empty
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["country", "year", "month", "series"]).reset_index(drop=True)


def cal_annual(monthly: pd.DataFrame) -> pd.DataFrame:
    """CAL-04: soma dos meses por pais, ano e serie. `partial` se falta algum mes do ano
    (fora do intervalo da serie) ou se algum mes e parcial."""
    require_columns(monthly, MONTHLY_COLUMNS)
    g = monthly.groupby(["country", "year", "series"], observed=True)
    out = g.agg(cell_days=("cell_days", "sum"), n_months=("month", "count"),
                any_partial=("partial", "any"), n_unknown_days=("n_unknown_days", "sum")).reset_index()
    out["partial"] = out["any_partial"] | (out["n_months"] < 12)
    out["cell_days"] = out["cell_days"].astype("int64")
    out["n_unknown_days"] = out["n_unknown_days"].astype("int64")
    return out[ANNUAL_COLUMNS].sort_values(["country", "year", "series"]).reset_index(drop=True)

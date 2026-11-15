"""Metricas de calendario do Lote 1 por celula: CAL-01/02 (diaria), CAL-03 (mensal), CAL-04 (anual).

Unidade: celula-dia (par distinto celula x dia UTC) sobre deteccoes elegiveis. `cell` e o int64 de
`common.cell_key(lat, lon, grid_deg)`; o pais ja nao e chave.
Series: `modis`, `viirs` e `combined` (uniao de celulas-dia; uma celula-dia detetada pelos
dois sensores conta 1). Antes de 2018 so existe MODIS, por isso `combined` tem um degrau
artificial em 2018: ver spec/metodologia_metricas.md.

As tabelas por celula sao ESPARSAS (so celula-meses/anos com atividade). A parte que e igual para
todas as celulas (intervalo de cada serie, `partial`, `n_unknown_days`) vive em tabelas pequenas
(`month_validity`, `year_validity`). `densify_monthly`/`densify_annual` juntam as duas e
preenchem com 0 os meses sem atividade DENTRO do intervalo da serie, so para as celulas pedidas
(nunca para o mundo inteiro), reproduzindo o esquema denso antigo (`country` -> `cell`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import GRID_DEG, coarsen_cell, parse_dates, require_columns
from .counts import _eligible_cell_days

SERIES = ("modis", "viirs", "combined")
INSTRUMENTS = ("MODIS", "VIIRS")
DAILY_COLUMNS = ["cell", "date", "in_modis", "in_viirs"]
CELL_DAYS_COLUMNS = ["date", "cell", "instrument", "satellite"]
MONTH_VALIDITY_COLUMNS = ["series", "year", "month", "partial", "n_unknown_days"]
YEAR_VALIDITY_COLUMNS = ["series", "year", "partial", "n_unknown_days"]
SPARSE_MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days"]
SPARSE_ANNUAL_COLUMNS = ["cell", "year", "series", "cell_days"]
MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
ANNUAL_COLUMNS = ["cell", "year", "series", "cell_days", "partial", "n_unknown_days"]
_DTYPES = {"cell": "int64", "year": "int64", "month": "int64", "cell_days": "int64",
           "n_unknown_days": "int64", "partial": "bool", "in_modis": "bool", "in_viirs": "bool",
           "series": "object", "date": "datetime64[ns]"}


def _empty(columns) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=_DTYPES[c]) for c in columns})


def _upper_instrument(frame: pd.DataFrame) -> np.ndarray:
    """Instrumento em maiusculas (array de objetos); levanta ValueError se houver um diferente
    de MODIS/VIIRS ou ausente."""
    inst = frame["instrument"].astype("string").str.upper()
    unknown = sorted(set(inst.dropna().unique()) - set(INSTRUMENTS))
    if unknown or inst.isna().any():
        raise ValueError(f"instrumento desconhecido ou ausente: {unknown}")
    return inst.to_numpy(dtype=object)


def eligible_cell_days(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """Celulas-dia elegiveis distintas por satelite: date, cell, instrument, satellite
    (deduplicado nas 4 colunas e ordenado). Exige latitude/longitude; linhas com coordenadas ou
    data invalidas ficam fora. Tabela compacta que o notebook guarda por ficheiro (nao mantem o
    VIIRS inteiro em memoria)."""
    _, dedup = _eligible_cell_days(df, grid_deg)
    return dedup[CELL_DAYS_COLUMNS].sort_values(CELL_DAYS_COLUMNS).reset_index(drop=True)


def cal_daily(cell_days: pd.DataFrame) -> pd.DataFrame:
    """CAL-01/CAL-02 por celula: uma linha por celula-dia com atividade e as flags `in_modis` e
    `in_viirs` (bool). A serie `combined` e `in_modis | in_viirs`. Esparso; ordenado por (cell, date).
    Levanta ValueError se existir um instrumento diferente de MODIS/VIIRS."""
    require_columns(cell_days, ["cell", "date", "instrument"])
    if len(cell_days) == 0:
        return _empty(DAILY_COLUMNS)
    inst = _upper_instrument(cell_days)
    frame = pd.DataFrame({"cell": cell_days["cell"].to_numpy(dtype="int64"),
                          "date": cell_days["date"].to_numpy(),
                          "in_modis": inst == "MODIS", "in_viirs": inst == "VIIRS"})
    out = frame.groupby(["cell", "date"], sort=True)[["in_modis", "in_viirs"]].max().reset_index()
    return out.astype({"in_modis": "bool", "in_viirs": "bool"})[DAILY_COLUMNS]


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


def month_validity(coverage: pd.DataFrame) -> pd.DataFrame:
    """Validade de cada mes de cada serie (igual para todas as celulas): DENSA dentro do intervalo
    [primeira, ultima] da serie. `partial`: o mes nao esta totalmente dentro do intervalo.
    `n_unknown_days`: dias do mes sem deteccao global (cobertura desconhecida). Cobertura vazia =>
    tabela vazia. Levanta ValueError se a cobertura tiver um instrumento diferente de MODIS/VIIRS."""
    require_columns(coverage, ["instrument", "date", "n_rows_global"])
    if len(coverage) == 0:
        return _empty(MONTH_VALIDITY_COLUMNS)
    parts = []
    for series, (first, last, unknown) in _series_ranges(coverage).items():
        frame = pd.DataFrame({"period": pd.period_range(first, last, freq="M")})
        unk = pd.Series(unknown.to_period("M")).value_counts()
        frame["n_unknown_days"] = frame["period"].map(unk).fillna(0).astype("int64")
        starts = frame["period"].map(lambda p: p.start_time)
        ends = frame["period"].map(lambda p: p.end_time.normalize())
        frame["partial"] = ~((starts >= first) & (ends <= last))
        frame["year"] = frame["period"].map(lambda p: p.year).astype("int64")
        frame["month"] = frame["period"].map(lambda p: p.month).astype("int64")
        frame["series"] = series
        parts.append(frame[MONTH_VALIDITY_COLUMNS])
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["series", "year", "month"]).reset_index(drop=True)


def year_validity(validity: pd.DataFrame) -> pd.DataFrame:
    """Validade anual de cada serie a partir de `month_validity`: `partial` se falta algum mes do
    ano (fora do intervalo da serie) ou se algum mes e parcial; `n_unknown_days` soma os meses."""
    require_columns(validity, MONTH_VALIDITY_COLUMNS)
    if len(validity) == 0:
        return _empty(YEAR_VALIDITY_COLUMNS)
    g = validity.groupby(["series", "year"], observed=True)
    out = g.agg(n_months=("month", "count"), any_partial=("partial", "any"),
                n_unknown_days=("n_unknown_days", "sum")).reset_index()
    out["partial"] = (out["any_partial"] | (out["n_months"] < 12)).astype("bool")
    out["n_unknown_days"] = out["n_unknown_days"].astype("int64")
    out["year"] = out["year"].astype("int64")
    return out[YEAR_VALIDITY_COLUMNS].sort_values(["series", "year"]).reset_index(drop=True)


def cal_monthly(cell_days: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    """CAL-03 por celula, ESPARSO: celulas-dia por (celula, ano, mes, serie), so onde `cell_days > 0`.
    `combined` e a uniao de celulas-dia distintas dos dois sensores (nao a soma). `coverage` so serve
    para validar: levanta ValueError se existir atividade fora do intervalo de cobertura da serie
    (ou de uma serie sem cobertura) ou um instrumento diferente de MODIS/VIIRS. `partial` e
    `n_unknown_days` vem de `month_validity`; juntar com `densify_monthly`.
    Independente entre anos: pode calcular-se um ano de cada vez."""
    require_columns(cell_days, ["cell", "date", "instrument"])
    require_columns(coverage, ["instrument", "date", "n_rows_global"])
    if len(coverage) == 0:
        if len(cell_days):
            raise ValueError("ha atividade diaria mas a cobertura esta vazia")
        return _empty(SPARSE_MONTHLY_COLUMNS)
    ranges = _series_ranges(coverage)
    inst = _upper_instrument(cell_days) if len(cell_days) else np.array([], dtype=object)
    cells = cell_days["cell"].to_numpy(dtype="int64")
    dates = cell_days["date"].to_numpy()
    parts = []
    for series in SERIES:
        mask = np.ones(len(cells), dtype=bool) if series == "combined" else inst == series.upper()
        sub = pd.DataFrame({"cell": cells[mask], "date": dates[mask]}).drop_duplicates()
        if len(sub) == 0:
            continue
        if series not in ranges:
            raise ValueError(f"atividade diaria fora do intervalo de cobertura da serie '{series}'")
        first, last, _ = ranges[series]
        if sub["date"].min() < first or sub["date"].max() > last:
            raise ValueError(f"atividade diaria fora do intervalo de cobertura da serie '{series}'")
        grouped = (sub.groupby(["cell", sub["date"].dt.year.rename("year"),
                                sub["date"].dt.month.rename("month")], sort=True)
                   .size().rename("cell_days").reset_index())
        grouped["series"] = series
        parts.append(grouped[SPARSE_MONTHLY_COLUMNS])
    if not parts:
        return _empty(SPARSE_MONTHLY_COLUMNS)
    out = pd.concat(parts, ignore_index=True).astype(
        {c: "int64" for c in ("cell", "year", "month", "cell_days")})
    return out.sort_values(["cell", "year", "month", "series"]).reset_index(drop=True)


def cal_annual(monthly: pd.DataFrame) -> pd.DataFrame:
    """CAL-04 por celula, ESPARSO: soma dos meses por (celula, ano, serie), so `cell_days > 0`.
    `partial`/`n_unknown_days` vem de `year_validity`; juntar com `densify_annual`."""
    require_columns(monthly, ["cell", "year", "series", "cell_days"])
    if len(monthly) == 0:
        return _empty(SPARSE_ANNUAL_COLUMNS)
    out = (monthly.groupby(["cell", "year", "series"], sort=True, observed=True)["cell_days"]
           .sum().reset_index())
    out = out[out["cell_days"] > 0].astype({"cell": "int64", "year": "int64", "cell_days": "int64"})
    return out[SPARSE_ANNUAL_COLUMNS].sort_values(["cell", "year", "series"]).reset_index(drop=True)


def _densify(sparse: pd.DataFrame, validity: pd.DataFrame, cells, keys, columns, label) -> pd.DataFrame:
    if cells is None:
        cells = np.sort(sparse["cell"].unique().astype("int64"))
    else:
        cells = np.unique(np.asarray(cells, dtype="int64"))
    if len(validity) == 0:
        if len(sparse):
            raise ValueError(f"ha atividade {label} mas a validade esta vazia")
        return _empty(columns)
    sparse = sparse[sparse["cell"].isin(cells)]
    frame = pd.DataFrame({"cell": np.repeat(cells, len(validity))})
    for col in validity.columns:
        frame[col] = np.tile(validity[col].to_numpy(), len(cells))
    out = frame.merge(sparse[["cell"] + keys + ["cell_days"]], on=["cell"] + keys, how="left")
    out["cell_days"] = out["cell_days"].fillna(0).astype("int64")
    if int(out["cell_days"].sum()) != int(sparse["cell_days"].sum()):
        raise ValueError(f"atividade {label} fora dos periodos da tabela de validade")
    out = out[columns].astype({"cell": "int64", "cell_days": "int64", "year": "int64"})
    order = ["cell"] + [c for c in ("year", "month", "series") if c in columns]
    return out.sort_values(order, kind="mergesort").reset_index(drop=True)


def densify_monthly(monthly: pd.DataFrame, validity: pd.DataFrame, cells=None) -> pd.DataFrame:
    """Tabela mensal DENSA (esquema antigo de `l1_cal_monthly`, com `cell` no lugar de `country`):
    para cada celula de `cells` (por defeito as presentes em `monthly`) e cada (serie, ano, mes) de
    `validity`, `cell_days` (0 se nao ha linha em `monthly`), `partial` e `n_unknown_days`.
    So gera linhas para as celulas pedidas: chame-a por fatias de celulas, nunca para o mundo todo.
    Levanta ValueError se `monthly` tiver atividade num mes que `validity` nao tem."""
    require_columns(monthly, SPARSE_MONTHLY_COLUMNS)
    require_columns(validity, MONTH_VALIDITY_COLUMNS)
    return _densify(monthly, validity[MONTH_VALIDITY_COLUMNS], cells,
                    ["year", "month", "series"], MONTHLY_COLUMNS, "mensal")


def densify_annual(annual: pd.DataFrame, validity: pd.DataFrame, cells=None) -> pd.DataFrame:
    """Tabela anual DENSA (esquema antigo de `l1_cal_annual`, com `cell`): `cell_days` (0 sem linha),
    `partial` e `n_unknown_days` de `year_validity`, para as celulas de `cells` (ver densify_monthly)."""
    require_columns(annual, SPARSE_ANNUAL_COLUMNS)
    require_columns(validity, YEAR_VALIDITY_COLUMNS)
    return _densify(annual, validity[YEAR_VALIDITY_COLUMNS], cells,
                    ["year", "series"], ANNUAL_COLUMNS, "anual")


def active_cells(monthly: pd.DataFrame, validity: pd.DataFrame, min_years: int,
                 max_unknown_days: int = 0) -> np.ndarray:
    """Celulas (int64, ordenadas) com atividade (`cell_days > 0`, em qualquer serie) em pelo menos
    `min_years` anos DISTINTOS, contando so meses validos (nao parciais e com no maximo
    `max_unknown_days` dias desconhecidos: a mesma regra de `valid_mask` das estatisticas).
    Serve para podar as celulas que nunca teriam referencia historica suficiente."""
    require_columns(monthly, SPARSE_MONTHLY_COLUMNS)
    require_columns(validity, MONTH_VALIDITY_COLUMNS)
    ok = validity[(~validity["partial"].astype(bool)) & (validity["n_unknown_days"] <= max_unknown_days)]
    active = monthly[monthly["cell_days"] > 0].merge(
        ok[["series", "year", "month"]], on=["series", "year", "month"], how="inner")
    years = active.drop_duplicates(["cell", "year"]).groupby("cell").size()
    return np.sort(years.index[years >= min_years].to_numpy(dtype="int64"))


def coarsen_cell_days(cell_days: pd.DataFrame, grid_deg: float, to_deg: float) -> pd.DataFrame:
    """Reduz a resolucao de uma tabela `eligible_cell_days`: cada celula de `grid_deg` passa a celula
    de `to_deg` que a contem (`common.coarsen_cell`) e as linhas repetidas (mesma celula grossa, dia,
    instrumento e satelite) sao deduplicadas. `to_deg` tem de ser multiplo de `grid_deg`."""
    require_columns(cell_days, CELL_DAYS_COLUMNS)
    out = cell_days[CELL_DAYS_COLUMNS].copy()
    out["cell"] = coarsen_cell(out["cell"].to_numpy(dtype="int64"), grid_deg, to_deg).astype("int64")
    return out.drop_duplicates().sort_values(CELL_DAYS_COLUMNS).reset_index(drop=True)

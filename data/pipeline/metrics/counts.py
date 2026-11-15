"""Metricas de contagem do Lote 1: OBS-01, OBS-02, OBS-03, QA-02, QA-03, QA-04.

Funcoes puras: DataFrame no esquema de processed/ -> tabela "tidy" ordenada pelas chaves.
Convencoes em spec/metodologia_metricas.md (elegivel, grelha, divisao por zero => NA).
A unidade geografica e a celula (`cell`, int64 = `common.cell_key(lat, lon, grid_deg)`), nao o pais.
Linhas com acq_date invalida (ver count_invalid_dates) ou coordenadas invalidas (ver
count_invalid_coords) ficam fora de TODAS as tabelas: a soma de OBS-01 e igual ao numero de
linhas menos as que tem data ou coordenadas invalidas. Uma deteccao que aparece em ficheiros de
paises diferentes na mesma celula e contada uma vez por linha, mas as celulas-dia de QA-03/QA-04
nao dependem do pais (a mesma celula-dia vinda de dois paises conta 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (GRID_DEG, cell_key, eligible, parse_dates, require_columns,
                     valid_coords)

KEY_MONTH = ["cell", "year", "month", "instrument", "satellite"]
KEY_SAT = ["cell", "year", "instrument", "satellite"]
KEY_INST = ["cell", "year", "instrument"]


def _xy(df: pd.DataFrame):
    """(latitude, longitude) como float64 (NA/texto => NaN), sem falhar com dtypes anulaveis."""
    lat = pd.to_numeric(df["latitude"], errors="coerce").to_numpy(dtype="float64", na_value=np.nan)
    lon = pd.to_numeric(df["longitude"], errors="coerce").to_numpy(dtype="float64", na_value=np.nan)
    return lat, lon


def _prepare(df: pd.DataFrame, columns, with_eligible: bool = False,
             grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """Subconjunto das colunas pedidas, com year/month/date validos e `cell` (int64).
    Linhas com data invalida ou coordenadas invalidas sao removidas (latitude/longitude
    deixam de existir no resultado: so ficam em `cell`). `eligible` (bool) so se with_eligible."""
    columns = list(dict.fromkeys(list(columns) + ["latitude", "longitude"]))
    require_columns(df, columns + (["type", "confidence_class"] if with_eligible else []))
    work = df[columns].copy()
    if with_eligible:
        work["eligible"] = eligible(df).to_numpy()
    date = parse_dates(work["acq_date"]).reset_index(drop=True)
    lat, lon = _xy(work)
    ok = date.notna().to_numpy() & valid_coords(lat, lon)
    work = work[ok].reset_index(drop=True)
    date = date[ok].reset_index(drop=True)
    work["cell"] = cell_key(lat[ok], lon[ok], grid_deg).astype("int64")
    work = work.drop(columns=["latitude", "longitude"])
    work["date"] = date
    work["year"] = date.dt.year.astype("int64")
    work["month"] = date.dt.month.astype("int64")
    for k in ("instrument", "satellite"):
        if k in work:
            work[k] = work[k].astype("string").fillna("unknown")
    return work


def count_invalid_dates(df: pd.DataFrame) -> int:
    """Linhas cuja acq_date nao e uma data real YYYY-MM-DD (ficam fora das metricas)."""
    require_columns(df, ["acq_date"])
    return int(parse_dates(df["acq_date"]).isna().sum())


def count_invalid_coords(df: pd.DataFrame) -> int:
    """Linhas com coordenadas nao finitas ou fora de intervalo (fora de todas as metricas)."""
    require_columns(df, ["latitude", "longitude"])
    return int((~valid_coords(*_xy(df))).sum())


def _pct(num: pd.Series, den: pd.Series) -> pd.Series:
    """100 * num / den; NA onde den == 0 (nunca 0 nem inf)."""
    return 100.0 * num / den.where(den != 0)


def _size(frame: pd.DataFrame, keys, name: str) -> pd.DataFrame:
    out = frame.groupby(keys, sort=True, observed=True).size().rename(name).reset_index()
    out[name] = out[name].astype("int64")
    return out


def _sorted(frame: pd.DataFrame, keys) -> pd.DataFrame:
    return frame.sort_values(keys).reset_index(drop=True)


# --------------------------------------------------------------------------- OBS
def obs01_raw_counts(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """OBS-01: deteccoes brutas (antes do filtro) por celula, ano, mes, instrumento e satelite."""
    work = _prepare(df, ["instrument", "satellite", "acq_date"], grid_deg=grid_deg)
    return _sorted(_size(work, KEY_MONTH, "n_raw"), KEY_MONTH)


def obs03_filtered_counts(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """OBS-03: deteccoes elegiveis, com os mesmos grupos de OBS-01 (0 onde nada passa o filtro)."""
    work = _prepare(df, ["instrument", "satellite", "acq_date"], with_eligible=True, grid_deg=grid_deg)
    raw = _size(work, KEY_MONTH, "n_raw").drop(columns="n_raw")
    elig = _size(work[work["eligible"]], KEY_MONTH, "n_eligible")
    out = raw.merge(elig, on=KEY_MONTH, how="left")
    out["n_eligible"] = out["n_eligible"].fillna(0).astype("int64")
    return _sorted(out, KEY_MONTH)


def qa02_retention(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """QA-02: taxa de retencao do filtro = n_eligible / n_raw (em %), por grupo de OBS-01."""
    work = _prepare(df, ["instrument", "satellite", "acq_date"], with_eligible=True, grid_deg=grid_deg)
    raw = _size(work, KEY_MONTH, "n_raw")
    elig = _size(work[work["eligible"]], KEY_MONTH, "n_eligible")
    out = raw.merge(elig, on=KEY_MONTH, how="left")
    out["n_eligible"] = out["n_eligible"].fillna(0).astype("int64")
    out["pct_retained"] = _pct(out["n_eligible"], out["n_raw"])
    return _sorted(out, KEY_MONTH)


def obs02_confidence_dist(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """OBS-02: distribuicao por classe de confianca (todas as linhas, antes do filtro).
    Classe ausente => 'unknown'. `pct` soma 100 por (celula, ano, instrumento)."""
    require_columns(df, ["confidence_class"])
    work = _prepare(df, ["instrument", "acq_date", "confidence_class"], grid_deg=grid_deg)
    work["confidence_class"] = work["confidence_class"].astype("string").fillna("unknown")
    keys = KEY_INST + ["confidence_class"]
    out = _size(work, keys, "n")
    total = out.groupby(KEY_INST, observed=True)["n"].transform("sum")
    out["pct"] = _pct(out["n"], total)
    return _sorted(out, keys)


# ---------------------------------------------------------------------------- QA
def _eligible_cell_days(df: pd.DataFrame, grid_deg: float):
    """(linhas elegiveis com data e coordenadas validas, com `cell`), e a tabela dessas
    linhas deduplicada por (celula, ano, instrumento, satelite, dia)."""
    work = _prepare(df, ["instrument", "satellite", "acq_date"], with_eligible=True, grid_deg=grid_deg)
    work = work[work["eligible"]].reset_index(drop=True)
    dedup = work.drop_duplicates(KEY_SAT + ["date"])
    return work, dedup


def qa03_cellday_grouped(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """QA-03: por satelite, quantos pontos elegiveis repetem uma celula-dia ja observada
    pelo mesmo satelite. n_grouped = n_eligible - n_cell_days (pares distintos celula-dia).
    n_eligible conta so elegiveis com data e coordenadas validas."""
    work, dedup = _eligible_cell_days(df, grid_deg)
    n_elig = _size(work, KEY_SAT, "n_eligible")
    n_cd = _size(dedup, KEY_SAT, "n_cell_days")
    out = n_elig.merge(n_cd, on=KEY_SAT, how="left")
    out["n_grouped"] = (out["n_eligible"] - out["n_cell_days"]).astype("int64")
    return _sorted(out, KEY_SAT)


def qa04_redundancy(df: pd.DataFrame, grid_deg: float = GRID_DEG) -> pd.DataFrame:
    """QA-04: redundancia entre satelites do mesmo sensor = soma das celulas-dia unicas
    de cada satelite menos a uniao (nunca mistura MODIS com VIIRS)."""
    _, dedup = _eligible_cell_days(df, grid_deg)
    total = _size(dedup, KEY_INST, "sum_cell_days_by_satellite")
    union = _size(dedup.drop_duplicates(KEY_INST + ["date"]), KEY_INST, "n_cell_days_union")
    out = total.merge(union, on=KEY_INST, how="left")
    out["n_redundant"] = (out["sum_cell_days_by_satellite"] - out["n_cell_days_union"]).astype("int64")
    return _sorted(out, KEY_INST)

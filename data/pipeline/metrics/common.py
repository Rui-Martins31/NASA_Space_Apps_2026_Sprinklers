"""Primitivas partilhadas por todos os lotes de metricas. CONGELADO: nao alterar.

Contrato completo em spec/metodologia_metricas.md. Funcoes puras (pandas/numpy),
sem acesso a disco nem a Drive.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --- parametros congelados -------------------------------------------------
GRID_DEG = 0.1                       # lado da celula, em graus
COORD_SCALE = 10_000                 # FIRMS tem no maximo 4 casas decimais
ELIGIBLE_TYPE = 0                    # 0 = presumido fogo de vegetacao
ELIGIBLE_CONFIDENCE = ("n", "h")     # exclui confianca baixa ('l')
INSTRUMENTS = ("MODIS", "VIIRS")
SERIES = ("modis", "viirs", "combined")

# Esquema de processed/<sensor>_<ano>.parquet (gerado pelo notebook 01).
PROCESSED_COLUMNS = (
    "country", "source_file", "instrument", "satellite", "version",
    "latitude", "longitude", "acq_date", "acq_time", "acq_datetime_utc",
    "daynight", "type", "confidence_raw", "confidence_class",
    "brightness_primary", "brightness_primary_band",
    "brightness_aux", "brightness_aux_band",
    "scan", "track", "pixel_area_km2", "frp",
)


def check_processed_schema(df: pd.DataFrame, required=PROCESSED_COLUMNS) -> None:
    """Levanta ValueError se faltarem colunas do esquema de processed/."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"colunas em falta no DataFrame: {missing}")


def _grid_shape(grid_deg: float) -> tuple[int, int, int]:
    step = round(grid_deg * COORD_SCALE)
    if step <= 0 or abs(step - grid_deg * COORD_SCALE) > 1e-6:
        raise ValueError(f"grid_deg={grid_deg} nao e multiplo de 1/{COORD_SCALE} graus")
    if (180 * COORD_SCALE) % step or (360 * COORD_SCALE) % step:
        raise ValueError(f"grid_deg={grid_deg} nao divide 180 e 360 graus exatamente")
    return step, (180 * COORD_SCALE) // step, (360 * COORD_SCALE) // step


def cell_ids(latitude, longitude, grid_deg: float = GRID_DEG):
    """Indices inteiros (ilat, ilon) da celula de cada ponto.

    ilat = floor((lat + 90) / g), ilon = floor((lon + 180) / g), calculados em
    inteiros escalados por COORD_SCALE (evita erros de virgula flutuante, p.ex.
    floor((-89.9 + 90) / 0.1) dar 0 em vez de 1). lat == 90 e lon == 180 pertencem
    a ultima celula. Levanta ValueError se houver NaN/inf ou coordenadas fora de
    [-90, 90] / [-180, 180].
    """
    step, n_lat, n_lon = _grid_shape(grid_deg)
    lat = np.asarray(latitude, dtype="float64")
    lon = np.asarray(longitude, dtype="float64")
    if not (np.isfinite(lat).all() and np.isfinite(lon).all()):
        raise ValueError("coordenadas nao finitas (NaN/inf)")
    if (np.abs(lat) > 90).any() or (np.abs(lon) > 180).any():
        raise ValueError("coordenadas fora de [-90, 90] / [-180, 180]")
    ilat = np.rint((lat + 90.0) * COORD_SCALE).astype("int64") // step
    ilon = np.rint((lon + 180.0) * COORD_SCALE).astype("int64") // step
    return np.minimum(ilat, n_lat - 1), np.minimum(ilon, n_lon - 1)


def cell_key(latitude, longitude, grid_deg: float = GRID_DEG) -> np.ndarray:
    """Identificador unico int64 da celula: ilat * n_lon + ilon."""
    _, _, n_lon = _grid_shape(grid_deg)
    ilat, ilon = cell_ids(latitude, longitude, grid_deg)
    return ilat * n_lon + ilon


def eligible(df: pd.DataFrame,
             confidence=ELIGIBLE_CONFIDENCE,
             type_value: int = ELIGIBLE_TYPE) -> pd.Series:
    """Mascara booleana de deteccoes elegiveis: type == type_value E
    confidence_class em `confidence`. type ou classe ausentes => False."""
    type_ok = (df["type"] == type_value).fillna(False).astype(bool)
    conf_ok = df["confidence_class"].isin(list(confidence)).fillna(False).astype(bool)
    return type_ok & conf_ok


def as_series_views(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """{'modis': ..., 'viirs': ..., 'combined': todas as linhas}.
    Levanta ValueError se existir um instrumento diferente de MODIS/VIIRS."""
    inst = df["instrument"].astype("string").str.upper()
    unknown = sorted(set(inst.dropna().unique()) - set(INSTRUMENTS))
    if unknown or inst.isna().any():
        raise ValueError(f"instrumento desconhecido ou ausente: {unknown}")
    return {
        "modis": df[(inst == "MODIS").to_numpy()],
        "viirs": df[(inst == "VIIRS").to_numpy()],
        "combined": df,
    }


def require_columns(df: pd.DataFrame, columns) -> None:
    """Levanta ValueError a dizer quais colunas faltam."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"colunas em falta no DataFrame: {missing}")


def parse_dates(acq_date) -> pd.Series:
    """acq_date (texto YYYY-MM-DD) -> datetime64; data invalida => NaT."""
    return pd.to_datetime(pd.Series(acq_date).astype("string"), format="%Y-%m-%d", errors="coerce")


def valid_coords(latitude, longitude) -> np.ndarray:
    """Mascara booleana: coordenadas finitas e dentro de [-90, 90] / [-180, 180]."""
    lat = np.asarray(latitude, dtype="float64")
    lon = np.asarray(longitude, dtype="float64")
    return np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180)

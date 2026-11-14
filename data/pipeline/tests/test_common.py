"""Testes das primitivas partilhadas. CONGELADO: nao alterar."""
import math
import random
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from helpers_lote1 import build_processed as make_df
from metrics.common import (
    GRID_DEG, PROCESSED_COLUMNS, as_series_views, cell_ids, cell_key,
    check_processed_schema, eligible,
)


def _exact_cell(lat_str, lon_str, g=Fraction(1, 10)):
    """Oraculo independente: racionais exatos (sem virgula flutuante)."""
    ilat = math.floor((Fraction(lat_str) + 90) / g)
    ilon = math.floor((Fraction(lon_str) + 180) / g)
    return min(ilat, int(180 / g) - 1), min(ilon, int(360 / g) - 1)


@pytest.mark.parametrize("lat,lon,expected", [
    (-90.0, -180.0, (0, 0)),
    (90.0, 180.0, (1799, 3599)),        # extremos pertencem a ultima celula
    (0.0, 0.0, (900, 1800)),
    (-0.05, -0.05, (899, 1799)),        # negativos
    (10.1, -6.2, (1001, 1738)),
    (-89.9, 179.9, (1, 3599)),          # fronteira onde floor((lat+90)/0.1) falha
])
def test_cell_ids_known_values(lat, lon, expected):
    ilat, ilon = cell_ids([lat], [lon])
    assert (int(ilat[0]), int(ilon[0])) == expected


def test_naive_floor_fails_where_cell_ids_is_exact():
    """Regressao: a versao ingenua erra em -89.9 (devia ser 1, da 0)."""
    naive = math.floor((-89.9 + 90) / GRID_DEG)
    assert naive == 0
    assert int(cell_ids([-89.9], [0.0])[0][0]) == 1


def test_cell_ids_matches_exact_rational_oracle():
    rng = random.Random(12345)
    lats = [f"{rng.randint(-900000, 900000) / 10000:.4f}" for _ in range(2000)]
    lons = [f"{rng.randint(-1800000, 1800000) / 10000:.4f}" for _ in range(2000)]
    ilat, ilon = cell_ids([float(x) for x in lats], [float(x) for x in lons])
    expected = [_exact_cell(a, b) for a, b in zip(lats, lons)]
    assert list(zip(ilat.tolist(), ilon.tolist())) == expected


def test_cell_ids_grid_025():
    ilat, ilon = cell_ids([0.0, 0.24, 0.25, -0.01], [0.0, 0.0, 0.0, 0.0], grid_deg=0.25)
    assert ilat.tolist() == [360, 360, 361, 359]


@pytest.mark.parametrize("lat,lon", [(float("nan"), 0.0), (0.0, float("inf")),
                                     (91.0, 0.0), (0.0, -180.1)])
def test_cell_ids_rejects_invalid_coordinates(lat, lon):
    with pytest.raises(ValueError):
        cell_ids([lat], [lon])


def test_cell_ids_rejects_incompatible_grid():
    with pytest.raises(ValueError):
        cell_ids([0.0], [0.0], grid_deg=0.07)


def test_cell_key_is_injective_and_invertible():
    rng = random.Random(7)
    lat = [rng.uniform(-90, 90) for _ in range(5000)]
    lon = [rng.uniform(-180, 180) for _ in range(5000)]
    ilat, ilon = cell_ids(lat, lon)
    key = cell_key(lat, lon)
    assert len(set(key.tolist())) == len(set(zip(ilat.tolist(), ilon.tolist())))
    assert (key // 3600).tolist() == ilat.tolist()
    assert (key % 3600).tolist() == ilon.tolist()


def test_eligible_truth_table():
    rows = [
        {"type": 0, "confidence_class": "h"},     # sim
        {"type": 0, "confidence_class": "n"},     # sim
        {"type": 0, "confidence_class": "l"},     # nao: confianca baixa
        {"type": 2, "confidence_class": "h"},     # nao: fonte estatica
        {"type": 3, "confidence_class": "n"},     # nao: offshore
        {"type": pd.NA, "confidence_class": "h"}, # nao: tipo desconhecido
        {"type": 0, "confidence_class": pd.NA},   # nao: classe desconhecida
    ]
    mask = eligible(make_df(rows))
    assert mask.tolist() == [True, True, False, False, False, False, False]
    assert mask.dtype == bool


def test_eligible_custom_parameters():
    df = make_df([{"type": 0, "confidence_class": "l"}, {"type": 2, "confidence_class": "h"}])
    assert eligible(df, confidence=("l", "n", "h")).tolist() == [True, False]
    assert eligible(df, type_value=2).tolist() == [False, True]


def test_series_views():
    df = make_df([{"instrument": "MODIS"}, {"instrument": "VIIRS", "satellite": "N20"},
                  {"instrument": "MODIS"}])
    views = as_series_views(df)
    assert {k: len(v) for k, v in views.items()} == {"modis": 2, "viirs": 1, "combined": 3}


def test_series_views_rejects_unknown_instrument():
    with pytest.raises(ValueError):
        as_series_views(make_df([{"instrument": "AVHRR"}]))


def test_build_processed_has_contract_schema_and_dtypes():
    df = make_df([{"acq_time": "0814"}, {"acq_time": "2461"}])
    check_processed_schema(df)
    assert list(df.columns) == list(PROCESSED_COLUMNS)
    assert str(df["type"].dtype) == "Int8"
    assert df["acq_datetime_utc"].iloc[0] == pd.Timestamp("2020-01-01 08:14", tz="UTC")
    assert pd.isna(df["acq_datetime_utc"].iloc[1])      # hora invalida => NaT


def test_check_processed_schema_reports_missing_columns():
    with pytest.raises(ValueError, match="frp"):
        check_processed_schema(make_df([{}]).drop(columns=["frp"]))


def test_parse_dates_invalid_becomes_nat():
    from metrics.common import parse_dates
    out = parse_dates(["2020-02-29", "2021-02-29", "2020-13-01", "lixo", None])
    assert out.notna().tolist() == [True, False, False, False, False]
    assert out.iloc[0] == pd.Timestamp("2020-02-29")


def test_valid_coords_mask():
    from metrics.common import valid_coords
    lat = [0.0, 90.0, 90.1, float("nan"), 0.0, 10.0]
    lon = [0.0, 180.0, 0.0, 0.0, float("inf"), -180.5]
    assert valid_coords(lat, lon).tolist() == [True, True, False, False, False, False]


def test_require_columns_lists_all_missing():
    from metrics.common import require_columns
    with pytest.raises(ValueError, match=r"\['b', 'c'\]"):
        require_columns(pd.DataFrame({"a": [1]}), ["a", "b", "c"])

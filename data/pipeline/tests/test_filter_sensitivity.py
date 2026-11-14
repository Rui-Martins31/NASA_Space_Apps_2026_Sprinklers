"""Testes do ADD-05 (sensibilidade ao filtro de `type`), Lote 5.

Valores esperados calculados a mao (ver comentarios). Celulas de 0.1 graus, centros:
A = (10.05, 20.05), B = (10.15, 20.05), C = (10.25, 20.05) estao em celulas distintas.
Com grid_deg=0.25, A e B caem na mesma celula (ilat 400).
Colunas da saida: country, year, instrument, variant, n_eligible, n_cell_days, delta_cell_days_pct.
"""
import datetime as dt
import math
import random

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from helpers_lote5 import processed_df, recs
from metrics.filter_sensitivity import add05_type_sensitivity

COLS = ["country", "year", "instrument", "variant", "n_eligible", "n_cell_days",
        "delta_cell_days_pct"]
A = {"latitude": 10.05, "longitude": 20.05}
B = {"latitude": 10.15, "longitude": 20.05}
C = {"latitude": 10.25, "longitude": 20.05}


def row(country, year, instrument, variant, n_elig, n_cd, delta):
    return dict(country=country, year=year, instrument=instrument, variant=variant,
                n_eligible=n_elig, n_cell_days=n_cd, delta_cell_days_pct=delta)


def triple(country, year, instrument, d, nt, t0u):
    """Linhas das 3 variantes por defeito; cada argumento e (n_eligible, n_cell_days, delta)."""
    return [row(country, year, instrument, "default", *d),
            row(country, year, instrument, "no_type_filter", *nt),
            row(country, year, instrument, "type0_or_unknown", *t0u)]


# --------------------------------------------------------------------------- 1. manual
# Testland / MODIS / 2020. Linhas (celula, dia, type, conf, satelite):
#  r1 A 01-01 0  h Terra   r2 A 01-01 0  n Aqua    r3 B 01-01 0  h Terra
#  r4 A 01-02 NA h         r5 B 01-02 1  h         r6 A 01-03 0  l   (fora em todas)
#  r7 A 01-03 0  NA (fora) r8 C 01-04 2  n         r9 A 01-02 NA n   (mesma celula-dia de r4)
# default (type 0, n/h):            r1 r2 r3          -> 3 linhas; (A,01-01),(B,01-01) = 2
# no_type_filter (type != NA):      r1 r2 r3 r4 r5 r8 r9 -> 7; (A,01),(B,01),(A,02),(B,02),(C,04) = 5
# type0_or_unknown (0 ou NA):       r1 r2 r3 r4 r9    -> 5; (A,01),(B,01),(A,02) = 3
# delta no_type = 100*(5-2)/2 = 150.0 ; delta t0u = 100*(3-2)/2 = 50.0
@pytest.fixture
def d1():
    return processed_df([
        {**A, "acq_date": "2020-01-01", "satellite": "Terra"},
        {**A, "acq_date": "2020-01-01", "satellite": "Aqua", "confidence_class": "n"},
        {**B, "acq_date": "2020-01-01"},
        {**A, "acq_date": "2020-01-02", "type": pd.NA},
        {**B, "acq_date": "2020-01-02", "type": 1},
        {**A, "acq_date": "2020-01-03", "confidence_class": "l"},
        {**A, "acq_date": "2020-01-03", "confidence_class": pd.NA},
        {**C, "acq_date": "2020-01-04", "type": 2, "confidence_class": "n"},
        {**A, "acq_date": "2020-01-02", "type": pd.NA, "confidence_class": "n"},
    ])


def test_manual_example(d1):
    out = add05_type_sensitivity(d1)
    assert list(out.columns) == COLS
    assert recs(out) == triple("Testland", 2020, "MODIS", (3, 2, 0.0), (7, 5, 150.0), (5, 3, 50.0))
    assert str(out["year"].dtype) == "int64"
    assert str(out["n_eligible"].dtype) == "int64"
    assert str(out["n_cell_days"].dtype) == "int64"
    assert str(out["delta_cell_days_pct"].dtype) == "float64"


def test_input_is_not_modified(d1):
    before = d1.copy(deep=True)
    add05_type_sensitivity(d1)
    assert_frame_equal(d1, before)


# --------------------------------------------------------------------------- 2. vazio
def test_empty_input_returns_empty_table_with_columns():
    out = add05_type_sensitivity(processed_df([]))
    assert list(out.columns) == COLS
    assert len(out) == 0
    assert str(out["year"].dtype) == "int64"
    assert str(out["n_eligible"].dtype) == "int64"
    assert str(out["n_cell_days"].dtype) == "int64"
    assert str(out["delta_cell_days_pct"].dtype) == "float64"


def test_input_with_no_eligible_row_in_any_variant_is_empty():
    # l, NA e (type 0 com conf l) e (type NA com conf l): nenhuma variante os aceita
    df = processed_df([
        {**A, "confidence_class": "l"},
        {**A, "confidence_class": pd.NA},
        {**A, "type": pd.NA, "confidence_class": "l"},
        {**A, "type": 3, "confidence_class": pd.NA},
    ])
    out = add05_type_sensitivity(df)
    assert list(out.columns) == COLS
    assert len(out) == 0


# --------------------------------------------------------------------------- 3. limites
@pytest.mark.parametrize("conf", ["l", None])
def test_low_or_missing_confidence_is_out_of_every_variant(conf):
    # uma linha valida (type 0, h) + linhas l/NA de todos os tipos: so a valida conta
    rows = [{**A, "acq_date": "2020-03-03"}]
    for t in (0, 1, 2, 3, pd.NA):
        rows.append({**B, "acq_date": "2020-03-04", "type": t,
                     "confidence_class": pd.NA if conf is None else conf})
    out = add05_type_sensitivity(processed_df(rows))
    assert recs(out) == triple("Testland", 2020, "MODIS", (1, 1, 0.0), (1, 1, 0.0), (1, 1, 0.0))


@pytest.mark.parametrize("t", [1, 2, 3])
def test_types_1_2_3_only_enter_no_type_filter(t):
    out = add05_type_sensitivity(processed_df([{**A, "type": t}]))
    # default sem celulas-dia => delta NA
    assert recs(out) == triple("Testland", 2020, "MODIS", (0, 0, None), (1, 1, None), (0, 0, None))


def test_na_type_enters_only_no_type_filter_and_type0_or_unknown():
    out = add05_type_sensitivity(processed_df([{**A, "type": pd.NA, "confidence_class": "n"}]))
    assert recs(out) == triple("Testland", 2020, "MODIS", (0, 0, None), (1, 1, None), (1, 1, None))


def test_group_only_reached_by_other_variants_and_all_rejected_group_absent():
    # X: so uma linha com type NA (conf h) => default 0 (delta NA), outras 1/1 (delta NA).
    # Y: so linhas de confianca l => nenhuma linha elegivel em nenhuma variante => nao aparece.
    df = processed_df([
        {"country": "X", **A, "acq_date": "2020-05-05", "type": pd.NA},
        {"country": "Y", **A, "acq_date": "2020-05-05", "confidence_class": "l"},
    ])
    out = add05_type_sensitivity(df)
    assert recs(out) == triple("X", 2020, "MODIS", (0, 0, None), (1, 1, None), (1, 1, None))


def test_two_satellites_same_cell_day_count_once_in_cell_days_twice_in_rows():
    df = processed_df([
        {**A, "satellite": "Terra"},
        {**A, "satellite": "Aqua", "confidence_class": "n"},
    ])
    out = add05_type_sensitivity(df)
    assert recs(out) == triple("Testland", 2020, "MODIS", (2, 1, 0.0), (2, 1, 0.0), (2, 1, 0.0))


def test_two_detections_same_cell_day_same_satellite():
    # A (10.05, 20.05) e A' (10.0501, 20.0499) estao na mesma celula 0.1 (ilat 1000, ilon 2000)
    df = processed_df([
        {**A},
        {"latitude": 10.0501, "longitude": 20.0499},
        {"latitude": 10.0501, "longitude": 20.0499, "type": pd.NA},
    ])
    out = add05_type_sensitivity(df)
    # default: 2 linhas, 1 celula-dia; as outras variantes: 3 linhas, 1 celula-dia (delta 0)
    assert recs(out) == triple("Testland", 2020, "MODIS", (2, 1, 0.0), (3, 1, 0.0), (3, 1, 0.0))


def test_same_cell_on_different_days_counts_separately():
    df = processed_df([{**A, "acq_date": "2020-01-01"}, {**A, "acq_date": "2020-01-02"}])
    out = add05_type_sensitivity(df)
    assert recs(out) == triple("Testland", 2020, "MODIS", (2, 2, 0.0), (2, 2, 0.0), (2, 2, 0.0))


def test_invalid_dates_and_coordinates_are_ignored():
    bad_dates = ["2020-13-01", "2020-02-30", "garbage", pd.NA]
    bad_coords = [
        {"latitude": float("nan"), "longitude": 20.05},
        {"latitude": 10.05, "longitude": float("inf")},
        {"latitude": 91.0, "longitude": 20.05},
        {"latitude": 10.05, "longitude": -180.5},
    ]
    rows = [{**A, "acq_date": "2020-01-01"}]
    rows += [{**B, "acq_date": d} for d in bad_dates]
    rows += [{**c, "acq_date": "2020-01-01"} for c in bad_coords]
    rows += [{**c, "acq_date": "2020-01-01", "type": pd.NA} for c in bad_coords]
    out = add05_type_sensitivity(processed_df(rows))
    assert recs(out) == triple("Testland", 2020, "MODIS", (1, 1, 0.0), (1, 1, 0.0), (1, 1, 0.0))


def test_year_boundary_is_taken_from_acq_date():
    # 2020: r1 (type 0). 2021: r2 (type 0, 01-01), r3 (type NA, 01-02).
    # 2020: todas 1/1/0.0. 2021: default 1/1; no_type 2/2 -> 100.0; t0u 2/2 -> 100.0
    df = processed_df([
        {**A, "acq_date": "2020-12-31"},
        {**A, "acq_date": "2021-01-01"},
        {**A, "acq_date": "2021-01-02", "type": pd.NA},
    ])
    out = add05_type_sensitivity(df)
    assert recs(out) == (
        triple("Testland", 2020, "MODIS", (1, 1, 0.0), (1, 1, 0.0), (1, 1, 0.0))
        + triple("Testland", 2021, "MODIS", (1, 1, 0.0), (2, 2, 100.0), (2, 2, 100.0)))


def test_same_cell_and_day_in_different_years_are_not_merged():
    # mesma celula, mesmo mes/dia, anos diferentes: cada ano tem a sua celula-dia
    df = processed_df([{**A, "acq_date": "2020-06-06"}, {**A, "acq_date": "2021-06-06"}])
    out = add05_type_sensitivity(df)
    assert [(r["year"], r["n_cell_days"]) for r in recs(out)] == [(2020, 1)] * 3 + [(2021, 1)] * 3


def test_multiple_countries_and_instruments_are_independent_and_sorted():
    # Testland/MODIS/2020: A 01-01 type 0 h                          -> 1/1 em todas
    # Testland/VIIRS/2020: A 01-01 type 0 n ; A 01-02 type 1 h       -> default 1/1; no_type 2/2 (+100); t0u 1/1
    # Other/MODIS/2020:    B 01-01 type NA n                         -> default 0 (NA); resto 1/1 (NA)
    df = processed_df([
        {**A, "acq_date": "2020-01-01"},
        {**A, "acq_date": "2020-01-01", "instrument": "VIIRS", "satellite": "N20",
         "confidence_class": "n"},
        {**A, "acq_date": "2020-01-02", "instrument": "VIIRS", "satellite": "N20", "type": 1},
        {"country": "Other", **B, "acq_date": "2020-01-01", "type": pd.NA, "confidence_class": "n"},
    ])
    out = add05_type_sensitivity(df)
    assert recs(out) == (
        triple("Other", 2020, "MODIS", (0, 0, None), (1, 1, None), (1, 1, None))
        + triple("Testland", 2020, "MODIS", (1, 1, 0.0), (1, 1, 0.0), (1, 1, 0.0))
        + triple("Testland", 2020, "VIIRS", (1, 1, 0.0), (2, 2, 100.0), (1, 1, 0.0)))


def test_missing_country_or_instrument_becomes_unknown_group():
    df = processed_df([{**A, "country": pd.NA, "instrument": pd.NA}])
    out = add05_type_sensitivity(df)
    assert recs(out) == triple("unknown", 2020, "unknown", (1, 1, 0.0), (1, 1, 0.0), (1, 1, 0.0))


def test_grid_deg_is_used():
    # A e B no mesmo dia: 2 celulas a 0.1 graus, 1 a 0.25 graus
    df = processed_df([{**A}, {**B}])
    fine = add05_type_sensitivity(df)
    coarse = add05_type_sensitivity(df, grid_deg=0.25)
    assert [r["n_cell_days"] for r in recs(fine)] == [2, 2, 2]
    assert [r["n_cell_days"] for r in recs(coarse)] == [1, 1, 1]
    assert [r["n_eligible"] for r in recs(coarse)] == [2, 2, 2]


def test_cells_use_scaled_integers_not_float_division():
    # floor((-89.9+90)/0.1) em float da 0 (erro); em inteiros e 1. -89.9 -> ilat 1 e -89.95 -> ilat 0.
    df = processed_df([
        {"latitude": -89.9, "longitude": 0.05},
        {"latitude": -89.95, "longitude": 0.05},
    ])
    out = add05_type_sensitivity(df)
    assert [r["n_cell_days"] for r in recs(out)] == [2, 2, 2]


# ------------------------------------------------------------ variantes personalizadas
# Testland/MODIS/2020, celulas A/B, dias de janeiro:
#  1 A 01-01 t0 h   2 A 01-02 t1 h   3 B 01-02 t2 n   4 B 01-03 t3 h
#  5 A 01-03 tNA h  6 A 01-03 t2 l (fora em todas)
# default (0):            {1}       -> 1/1
# any_known (None,False): {1,2,3,4} -> 4 linhas, (A,1),(A,2),(B,2),(B,3) = 4  -> +300.0
# t01 (0,1):              {1,2}     -> 2/2 -> +100.0
# types12 (1,2):          {2,3}     -> 2/2 -> +100.0
# unknown_only ((),True): {5}       -> 1/1 -> 0.0
CUSTOM = {
    "default": {"types": (0,), "include_na_type": False},
    "any_known": {"types": None, "include_na_type": False},
    "t01": {"types": (0, 1), "include_na_type": False},
    "types12": {"types": (1, 2), "include_na_type": False},
    "unknown_only": {"types": (), "include_na_type": True},
}


def test_custom_variants():
    df = processed_df([
        {**A, "acq_date": "2020-01-01"},
        {**A, "acq_date": "2020-01-02", "type": 1},
        {**B, "acq_date": "2020-01-02", "type": 2, "confidence_class": "n"},
        {**B, "acq_date": "2020-01-03", "type": 3},
        {**A, "acq_date": "2020-01-03", "type": pd.NA},
        {**A, "acq_date": "2020-01-03", "type": 2, "confidence_class": "l"},
    ])
    out = add05_type_sensitivity(df, variants=CUSTOM)
    assert recs(out) == [
        row("Testland", 2020, "MODIS", "any_known", 4, 4, 300.0),
        row("Testland", 2020, "MODIS", "default", 1, 1, 0.0),
        row("Testland", 2020, "MODIS", "t01", 2, 2, 100.0),
        row("Testland", 2020, "MODIS", "types12", 2, 2, 100.0),
        row("Testland", 2020, "MODIS", "unknown_only", 1, 1, 0.0),
    ]


def test_custom_variants_with_only_default_gives_only_default_rows():
    out = add05_type_sensitivity(processed_df([{**A}, {**B, "type": 1}]),
                                 variants={"default": {"types": (0,), "include_na_type": False}})
    assert recs(out) == [row("Testland", 2020, "MODIS", "default", 1, 1, 0.0)]


def test_custom_default_defines_the_baseline_and_the_default_defaults_are_not_merged():
    # default personalizado = type 1; variante "t0" = type 0. Linhas: A t0, B t1, C t1.
    # default: 2/2 ; t0: 1/1 -> delta = 100*(1-2)/2 = -50.0 ; "no_type_filter" nao existe.
    variants = {"default": {"types": (1,), "include_na_type": False},
                "t0": {"types": (0,), "include_na_type": False}}
    df = processed_df([{**A}, {**B, "type": 1}, {**C, "type": 1}])
    out = add05_type_sensitivity(df, variants=variants)
    assert recs(out) == [
        row("Testland", 2020, "MODIS", "default", 2, 2, 0.0),
        row("Testland", 2020, "MODIS", "t0", 1, 1, -50.0),
    ]


def test_variants_without_default_raises():
    with pytest.raises(ValueError, match="default"):
        add05_type_sensitivity(processed_df([{**A}]),
                               variants={"x": {"types": (0,), "include_na_type": False}})


def test_variants_without_default_raises_even_on_empty_input():
    with pytest.raises(ValueError, match="default"):
        add05_type_sensitivity(processed_df([]),
                               variants={"x": {"types": (0,), "include_na_type": False}})


@pytest.mark.parametrize("col", ["country", "instrument", "latitude", "longitude",
                                 "acq_date", "type", "confidence_class"])
def test_missing_column_raises(col):
    df = processed_df([{**A}]).drop(columns=[col])
    # `except Exception` + assert: um KeyError (validacao em falta) falha por asserção, nao por erro de execucao
    try:
        add05_type_sensitivity(df)
    except Exception as exc:  # noqa: BLE001
        assert isinstance(exc, ValueError) and col in str(exc)
    else:
        pytest.fail("devia levantar ValueError")


def test_satellite_column_is_not_required():
    df = processed_df([{**A}, {**A, "satellite": "Aqua"}]).drop(columns=["satellite"])
    out = add05_type_sensitivity(df)
    assert recs(out) == triple("Testland", 2020, "MODIS", (2, 1, 0.0), (2, 1, 0.0), (2, 1, 0.0))


# ------------------------------------------------------------------ 4. ordem das linhas
def random_rows(rng, n):
    """Linhas aleatorias (semente fixa) numa area pequena, para haver muitas colisoes de
    celula-dia; inclui datas e coordenadas invalidas, type NA e confiancas l/NA."""
    dates = ["2020-12-28", "2020-12-30", "2020-12-31", "2021-01-01", "2021-01-02", "2021-01-03",
             "2020-13-01", "garbage", None]
    rows = []
    for _ in range(n):
        lat = 10 + rng.randint(0, 3000) / 10000
        lon = 20 + rng.randint(0, 2000) / 10000
        k = rng.random()
        if k < 0.03:
            lat = float("nan")
        elif k < 0.06:
            lon = 181.0
        rows.append({
            "country": rng.choice(["Aland", "Bland"]),
            "instrument": rng.choice(["MODIS", "VIIRS"]),
            "satellite": rng.choice(["Terra", "Aqua", "N20"]),
            "latitude": lat, "longitude": lon,
            "acq_date": rng.choice(dates),
            "type": rng.choice([0, 0, 0, 1, 2, 3, pd.NA]),
            "confidence_class": rng.choice(["h", "n", "l", pd.NA, "h", "n"]),
        })
    return rows


def test_row_order_does_not_change_the_result():
    df = processed_df(random_rows(random.Random(7), 400))
    base = add05_type_sensitivity(df)
    for seed in (1, 2, 3):
        shuffled = df.sample(frac=1.0, random_state=seed)
        assert_frame_equal(add05_type_sensitivity(shuffled), base)
    assert_frame_equal(add05_type_sensitivity(df.iloc[::-1]), base)


# --------------------------------------------------------- 5. oraculo e invariantes
def oracle(rows, variants):
    """Python puro: conjuntos/dicionarios, celula por aritmetica inteira propria."""
    def valid_date(s):
        if s is None or s is pd.NA:
            return None
        try:
            return dt.datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    def cell(lat, lon):
        ilat = min(round((lat + 90) * 10000) // 1000, 1799)
        ilon = min(round((lon + 180) * 10000) // 1000, 3599)
        return (ilat, ilon)

    n_rows, days = {}, {}
    for r in rows:
        d = valid_date(r["acq_date"])
        lat, lon = r["latitude"], r["longitude"]
        if d is None or not (math.isfinite(lat) and math.isfinite(lon)
                             and abs(lat) <= 90 and abs(lon) <= 180):
            continue
        conf, t = r["confidence_class"], r["type"]
        if conf is pd.NA or conf not in ("n", "h"):
            continue
        for name, spec in variants.items():
            if t is pd.NA:
                ok = spec["include_na_type"]
            else:
                ok = spec["types"] is None or t in spec["types"]
            if ok:
                key = (r["country"], d.year, r["instrument"], name)
                n_rows[key] = n_rows.get(key, 0) + 1
                days.setdefault(key, set()).add((cell(lat, lon), d))
    groups = {k[:3] for k in n_rows}
    out = []
    for g in sorted(groups):
        base = len(days.get(g + ("default",), ()))
        for name in sorted(variants):
            key = g + (name,)
            n_cd = len(days.get(key, ()))
            delta = None if base == 0 else 100.0 * (n_cd - base) / base
            out.append(dict(country=g[0], year=g[1], instrument=g[2], variant=name,
                            n_eligible=n_rows.get(key, 0), n_cell_days=n_cd,
                            delta_cell_days_pct=delta))
    return out


DEFAULT_VARIANTS = {
    "default": {"types": (0,), "include_na_type": False},
    "no_type_filter": {"types": None, "include_na_type": True},
    "type0_or_unknown": {"types": (0,), "include_na_type": True},
}


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_matches_independent_oracle_default_variants(seed):
    rows = random_rows(random.Random(seed), 600)
    out = add05_type_sensitivity(processed_df(rows))
    expected = oracle(rows, DEFAULT_VARIANTS)
    assert len(expected) > 20
    got = recs(out)
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        assert {k: v for k, v in g.items() if k != "delta_cell_days_pct"} == \
               {k: v for k, v in e.items() if k != "delta_cell_days_pct"}
        if e["delta_cell_days_pct"] is None:
            assert g["delta_cell_days_pct"] is None
        else:
            assert g["delta_cell_days_pct"] == pytest.approx(e["delta_cell_days_pct"], abs=1e-9)


def test_matches_independent_oracle_custom_variants_and_grid():
    rows = random_rows(random.Random(21), 600)
    out = add05_type_sensitivity(processed_df(rows), variants=CUSTOM)
    expected = oracle(rows, CUSTOM)
    got = recs(out)
    assert [(g["country"], g["year"], g["instrument"], g["variant"], g["n_eligible"],
             g["n_cell_days"]) for g in got] == \
           [(e["country"], e["year"], e["instrument"], e["variant"], e["n_eligible"],
             e["n_cell_days"]) for e in expected]
    for g, e in zip(got, expected):
        if e["delta_cell_days_pct"] is None:
            assert g["delta_cell_days_pct"] is None
        else:
            assert g["delta_cell_days_pct"] == pytest.approx(e["delta_cell_days_pct"], abs=1e-9)


def test_invariants_on_random_data():
    out = add05_type_sensitivity(processed_df(random_rows(random.Random(5), 800)))
    assert len(out) > 0 and len(out) % 3 == 0
    assert (out["n_cell_days"] <= out["n_eligible"]).all()
    for _, g in out.groupby(["country", "year", "instrument"]):
        by = g.set_index("variant")
        assert by.loc["no_type_filter", "n_eligible"] >= by.loc["type0_or_unknown", "n_eligible"]
        assert by.loc["type0_or_unknown", "n_eligible"] >= by.loc["default", "n_eligible"]
        assert by.loc["no_type_filter", "n_cell_days"] >= by.loc["type0_or_unknown", "n_cell_days"]
        assert by.loc["type0_or_unknown", "n_cell_days"] >= by.loc["default", "n_cell_days"]
        assert by.loc["no_type_filter", "n_eligible"] > 0 or by.loc["default", "n_eligible"] > 0
        assert by.loc["default", "delta_cell_days_pct"] in (0.0,) or pd.isna(
            by.loc["default", "delta_cell_days_pct"])

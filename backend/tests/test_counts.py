"""Testes das metricas de contagem do Lote 1: OBS-01/02/03, QA-02/03/04.

Os valores esperados foram calculados a mao (ver comentarios). Celulas de 0.1 graus:
A = (10.05, 20.05) e B = (10.15, 20.05) estao no centro de celulas distintas.
"""
import random
from fractions import Fraction

import pandas as pd
import pytest

from helpers_lote1 import build_processed as make_df
from metrics import counts
from metrics.counts import (
    count_invalid_coords, count_invalid_dates, obs01_raw_counts, obs02_confidence_dist,
    obs03_filtered_counts, qa02_retention, qa03_cellday_grouped, qa04_redundancy,
)

A = {"latitude": 10.05, "longitude": 20.05}
B = {"latitude": 10.15, "longitude": 20.05}


def recs(df, cols=None):
    """Lista de dicts (valores python) para comparar com exatidao, sem depender do dtype."""
    cols = cols or list(df.columns)
    return [{c: (None if pd.isna(r[c]) else r[c]) for c in cols}
            for r in df.to_dict("records")]


# --------------------------------------------------------------------------- D1
# r1 Testland MODIS Terra 2020-01-05            elegivel
# r2 Testland MODIS Terra 2020-01-20 conf l     NAO elegivel
# r3 Testland MODIS Aqua  2020-02-01            elegivel
# r4 Other    VIIRS N20   2020-01-05            elegivel
# r5 Testland MODIS Terra 2021-01-01            elegivel
# r6 Testland MODIS Terra 2022-03-03 type 2     NAO elegivel (conf h)
# r7 Testland MODIS Terra 2021-06-01 conf NA    NAO elegivel
@pytest.fixture
def d1():
    return make_df([
        {"acq_date": "2020-01-05"},
        {"acq_date": "2020-01-20", "confidence_class": "l"},
        {"acq_date": "2020-02-01", "satellite": "Aqua"},
        {"country": "Other", "instrument": "VIIRS", "satellite": "N20", "acq_date": "2020-01-05"},
        {"acq_date": "2021-01-01"},
        {"acq_date": "2022-03-03", "type": 2},
        {"acq_date": "2021-06-01", "confidence_class": pd.NA},
    ])


K5 = ["country", "year", "month", "instrument", "satellite"]


def test_obs01_raw_counts_manual(d1):
    out = obs01_raw_counts(d1)
    assert list(out.columns) == K5 + ["n_raw"]
    assert recs(out) == [
        dict(country="Other", year=2020, month=1, instrument="VIIRS", satellite="N20", n_raw=1),
        dict(country="Testland", year=2020, month=1, instrument="MODIS", satellite="Terra", n_raw=2),
        dict(country="Testland", year=2020, month=2, instrument="MODIS", satellite="Aqua", n_raw=1),
        dict(country="Testland", year=2021, month=1, instrument="MODIS", satellite="Terra", n_raw=1),
        dict(country="Testland", year=2021, month=6, instrument="MODIS", satellite="Terra", n_raw=1),
        dict(country="Testland", year=2022, month=3, instrument="MODIS", satellite="Terra", n_raw=1),
    ]


def test_obs03_filtered_counts_manual_keeps_zero_groups(d1):
    out = obs03_filtered_counts(d1)
    assert list(out.columns) == K5 + ["n_eligible"]
    assert [r["n_eligible"] for r in recs(out)] == [1, 1, 1, 1, 0, 0]   # mesmos grupos de OBS-01


def test_qa02_retention_manual(d1):
    out = qa02_retention(d1)
    assert list(out.columns) == K5 + ["n_raw", "n_eligible", "pct_retained"]
    assert [(r["n_raw"], r["n_eligible"], r["pct_retained"]) for r in recs(out)] == [
        (1, 1, 100.0), (2, 1, 50.0), (1, 1, 100.0), (1, 1, 100.0), (1, 0, 0.0), (1, 0, 0.0)]


def test_qa02_retention_zero_denominator_is_na():
    out = counts._pct(pd.Series([1, 1, 0]), pd.Series([2, 0, 0]))
    assert out.iloc[0] == 50.0
    assert pd.isna(out.iloc[1])      # 1/0 daria inf sem a protecao
    assert pd.isna(out.iloc[2])      # 0/0


def test_obs02_confidence_dist_manual(d1):
    out = obs02_confidence_dist(d1)
    assert list(out.columns) == ["country", "year", "instrument", "confidence_class", "n", "pct"]
    got = recs(out)
    assert [(r["country"], r["year"], r["instrument"], r["confidence_class"], r["n"]) for r in got] == [
        ("Other", 2020, "VIIRS", "h", 1),
        ("Testland", 2020, "MODIS", "h", 2),
        ("Testland", 2020, "MODIS", "l", 1),
        ("Testland", 2021, "MODIS", "h", 1),
        ("Testland", 2021, "MODIS", "unknown", 1),     # classe NA vira 'unknown'
        ("Testland", 2022, "MODIS", "h", 1),
    ]
    assert [r["pct"] for r in got] == pytest.approx(
        [100.0, 200 / 3, 100 / 3, 50.0, 50.0, 100.0])


def test_obs02_pct_sums_to_100_per_group(d1):
    out = obs02_confidence_dist(d1)
    sums = out.groupby(["country", "year", "instrument"])["pct"].sum()
    assert sums.tolist() == pytest.approx([100.0] * len(sums))


# --------------------------------------------------------------------------- D2
# Terra Testland: a A 01-05, b A 01-05 (duplicada), c B 01-05, d A 01-06, e A 01-06 conf l (fora)
#   n_eligible 4; celulas-dia {(A,5),(B,5),(A,6)} = 3; agrupados 1
# Aqua  Testland: f A 01-05, g B 01-07 -> 2; 2; 0
# VIIRS N20 Testland: h A 01-05, i A 01-05 -> 2; 1; 1
# Other MODIS Terra: j A 01-05 -> 1; 1; 0
# qa04 MODIS Testland: soma 3+2 = 5; uniao {(A,5),(B,5),(A,6),(B,7)} = 4; redundante 1
@pytest.fixture
def d2():
    return make_df([
        {**A, "acq_date": "2020-01-05"},
        {**A, "acq_date": "2020-01-05"},
        {**B, "acq_date": "2020-01-05"},
        {**A, "acq_date": "2020-01-06"},
        {**A, "acq_date": "2020-01-06", "confidence_class": "l"},
        {**A, "acq_date": "2020-01-05", "satellite": "Aqua"},
        {**B, "acq_date": "2020-01-07", "satellite": "Aqua"},
        {**A, "acq_date": "2020-01-05", "instrument": "VIIRS", "satellite": "N20"},
        {**A, "acq_date": "2020-01-05", "instrument": "VIIRS", "satellite": "N20"},
        {**A, "acq_date": "2020-01-05", "country": "Other"},
    ])


def test_qa03_cellday_grouped_manual(d2):
    out = qa03_cellday_grouped(d2)
    assert list(out.columns) == ["country", "year", "instrument", "satellite",
                                 "n_eligible", "n_cell_days", "n_grouped"]
    assert recs(out) == [
        dict(country="Other", year=2020, instrument="MODIS", satellite="Terra", n_eligible=1, n_cell_days=1, n_grouped=0),
        dict(country="Testland", year=2020, instrument="MODIS", satellite="Aqua", n_eligible=2, n_cell_days=2, n_grouped=0),
        dict(country="Testland", year=2020, instrument="MODIS", satellite="Terra", n_eligible=4, n_cell_days=3, n_grouped=1),
        dict(country="Testland", year=2020, instrument="VIIRS", satellite="N20", n_eligible=2, n_cell_days=1, n_grouped=1),
    ]


def test_qa04_redundancy_manual(d2):
    out = qa04_redundancy(d2)
    assert list(out.columns) == ["country", "year", "instrument",
                                 "sum_cell_days_by_satellite", "n_cell_days_union", "n_redundant"]
    assert recs(out) == [
        dict(country="Other", year=2020, instrument="MODIS", sum_cell_days_by_satellite=1, n_cell_days_union=1, n_redundant=0),
        dict(country="Testland", year=2020, instrument="MODIS", sum_cell_days_by_satellite=5, n_cell_days_union=4, n_redundant=1),
        dict(country="Testland", year=2020, instrument="VIIRS", sum_cell_days_by_satellite=1, n_cell_days_union=1, n_redundant=0),
    ]


def test_qa04_single_satellite_instrument_is_never_redundant(d2):
    only_viirs = d2[d2["instrument"] == "VIIRS"]
    assert qa04_redundancy(only_viirs)["n_redundant"].tolist() == [0]


def test_qa04_does_not_mix_modis_and_viirs():
    """MODIS e VIIRS na mesma celula-dia NAO sao redundancia dentro do sensor."""
    df = make_df([{**A}, {**A, "instrument": "VIIRS", "satellite": "N20"}])
    assert qa04_redundancy(df)["n_redundant"].tolist() == [0, 0]


# ------------------------------------------------------- vazio, datas, esquema, ordem
FUNCS = [obs01_raw_counts, obs02_confidence_dist, obs03_filtered_counts,
         qa02_retention, qa03_cellday_grouped, qa04_redundancy]


@pytest.mark.parametrize("fn", FUNCS)
def test_empty_input_returns_empty_table_with_columns(fn, d1):
    full = fn(d1)
    empty = fn(make_df([]))
    assert len(empty) == 0
    assert list(empty.columns) == list(full.columns)


@pytest.mark.parametrize("fn", FUNCS)
def test_missing_column_raises_value_error(fn, d1):
    with pytest.raises(ValueError, match="acq_date"):
        fn(d1.drop(columns=["acq_date"]))


@pytest.mark.parametrize("fn", FUNCS)
def test_order_of_rows_does_not_matter(fn, d1, d2):
    for df in (d1, d2):
        shuffled = df.sample(frac=1.0, random_state=3).reset_index(drop=True)
        pd.testing.assert_frame_equal(fn(df), fn(shuffled), check_dtype=False)


def test_invalid_dates_are_excluded_and_counted():
    df = make_df([{"acq_date": "2020-01-05"}, {"acq_date": "2020-13-45"}, {"acq_date": "lixo"}])
    assert count_invalid_dates(df) == 2
    assert obs01_raw_counts(df)["n_raw"].tolist() == [1]
    assert qa03_cellday_grouped(df)["n_eligible"].tolist() == [1]


def test_invariants_on_totals(d1, d2):
    for df in (d1, d2):
        valid = df[pd.to_datetime(df["acq_date"], format="%Y-%m-%d", errors="coerce").notna()]
        assert obs01_raw_counts(df)["n_raw"].sum() == len(valid)
        n_elig = int(((df["type"] == 0) & df["confidence_class"].isin(["n", "h"])).sum())
        assert obs03_filtered_counts(df)["n_eligible"].sum() == n_elig
        q3 = qa03_cellday_grouped(df)
        assert q3["n_eligible"].sum() == n_elig
        assert (q3["n_cell_days"] <= q3["n_eligible"]).all()
        assert (q3["n_grouped"] == q3["n_eligible"] - q3["n_cell_days"]).all()
        assert (qa02_retention(df)["pct_retained"].dropna().between(0, 100)).all()
        q4 = qa04_redundancy(df)
        assert (q4["n_redundant"] == q4["sum_cell_days_by_satellite"] - q4["n_cell_days_union"]).all()
        assert (q4["n_redundant"] >= 0).all()


# --------------------------------------------- oraculo independente (conjuntos Python)
def _exact_cell(lat, lon):
    g = Fraction(1, 10)
    return (int((Fraction(str(lat)) + 90) // g), int((Fraction(str(lon)) + 180) // g))


def test_matches_independent_set_oracle_on_random_data():
    rng = random.Random(2024)
    rows = []
    for _ in range(600):
        inst = rng.choice(["MODIS", "VIIRS"])
        sat = rng.choice(["Terra", "Aqua"]) if inst == "MODIS" else "N20"
        rows.append({
            "country": rng.choice(["P", "Q", "R"]), "instrument": inst, "satellite": sat,
            "latitude": rng.choice([10.05, 10.15, 10.25, -33.35]),
            "longitude": rng.choice([20.05, 20.15, -70.45]),
            "acq_date": rng.choice(["2020-01-01", "2020-01-02", "2020-02-29", "2021-03-01"]),
            "type": rng.choice([0, 0, 0, 2, 3, None]),
            "confidence_class": rng.choice(["l", "n", "h", "h", None]),
        })
    df = make_df(rows)
    # oraculo: dicionarios e conjuntos
    elig = {}
    for r in rows:
        if r["type"] == 0 and r["confidence_class"] in ("n", "h"):
            key = (r["country"], int(r["acq_date"][:4]), r["instrument"], r["satellite"])
            cd = (_exact_cell(r["latitude"], r["longitude"]), r["acq_date"])
            n, s = elig.get(key, (0, set()))
            s.add(cd)
            elig[key] = (n + 1, s)
    exp3 = sorted((*k, n, len(s), n - len(s)) for k, (n, s) in elig.items())
    got3 = sorted(tuple(r[c] for c in ["country", "year", "instrument", "satellite",
                                       "n_eligible", "n_cell_days", "n_grouped"])
                  for r in recs(qa03_cellday_grouped(df)))
    assert got3 == exp3

    by_inst = {}
    for (c, y, inst, sat), (n, s) in elig.items():
        tot, union = by_inst.get((c, y, inst), (0, set()))
        by_inst[(c, y, inst)] = (tot + len(s), union | s)
    exp4 = sorted((*k, t, len(u), t - len(u)) for k, (t, u) in by_inst.items())
    got4 = sorted(tuple(r[c] for c in ["country", "year", "instrument",
                                       "sum_cell_days_by_satellite", "n_cell_days_union", "n_redundant"])
                  for r in recs(qa04_redundancy(df)))
    assert got4 == exp4


def test_eligibility_columns_are_required(d1):
    with pytest.raises(ValueError, match="type"):
        qa02_retention(d1.drop(columns=["type"]))


def test_invalid_coordinates_are_excluded_from_cell_metrics_and_counted():
    df = make_df([{**A}, {"latitude": float("nan"), "longitude": 20.05}, {"latitude": 95.0, "longitude": 0.0}])
    assert count_invalid_coords(df) == 2
    assert qa03_cellday_grouped(df)["n_eligible"].tolist() == [1]
    assert obs01_raw_counts(df)["n_raw"].tolist() == [3]           # a contagem bruta nao depende da geografia

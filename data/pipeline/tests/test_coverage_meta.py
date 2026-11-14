"""Testes das metricas de meta-cobertura do Lote 4: ADD-01 (satelites ativos) e ADD-02 (dias sem deteccoes).

Valores esperados calculados a mao (ver comentarios em cada teste); os helpers sao locais.
"""
import datetime as dt
import random

import pandas as pd
import pytest

from metrics.coverage_meta import ADD01_COLUMNS, ADD02_COLUMNS, add01_active_satellites, add02_zero_days


def obs(rows):
    """rows: (country, year, month, instrument, satellite, n_raw) -> l1_obs01_raw_counts."""
    cols = ["country", "year", "month", "instrument", "satellite", "n_raw"]
    df = pd.DataFrame(rows, columns=cols)
    return df.astype({"year": "int64", "month": "int64", "n_raw": "int64"})


def cov(rows):
    """rows: (instrument, 'YYYY-MM-DD', n_rows_global) -> l1_cal_coverage."""
    df = pd.DataFrame(rows, columns=["instrument", "date", "n_rows_global"])
    df["date"] = pd.to_datetime(df["date"])
    df["n_rows_global"] = df["n_rows_global"].astype("int64")
    return df


def calendar(inst, start, values):
    """Dias consecutivos a partir de `start` com as contagens dadas."""
    d0 = dt.date.fromisoformat(start)
    return [(inst, (d0 + dt.timedelta(days=i)).isoformat(), v) for i, v in enumerate(values)]


def tuples(df):
    return [tuple(r) for r in df.itertuples(index=False, name=None)]


# ------------------------------------------------------------------ ADD-01
# MODIS 2001-01: Terra PT 5 + ES 3 = 8 (ativo); Aqua PT 0 (inativo)       -> 1, "Terra"
# MODIS 2003-02: Terra PT 1 (ativo); Aqua PT 0 + ES 2 = 2 (ativo)         -> 2, "Aqua,Terra"
# VIIRS 2018-01: N20 PT 4 (ativo)                                         -> 1, "N20"
# VIIRS 2018-02: N20 PT 0 (nenhum ativo)                                  -> mes ausente
@pytest.fixture
def obs_rows():
    return obs([
        ("PT", 2001, 1, "MODIS", "Terra", 5),
        ("ES", 2001, 1, "MODIS", "Terra", 3),
        ("PT", 2001, 1, "MODIS", "Aqua", 0),
        ("PT", 2003, 2, "MODIS", "Terra", 1),
        ("PT", 2003, 2, "MODIS", "Aqua", 0),
        ("ES", 2003, 2, "MODIS", "Aqua", 2),
        ("PT", 2018, 1, "VIIRS", "N20", 4),
        ("PT", 2018, 2, "VIIRS", "N20", 0),
    ])


def test_add01_manual_example(obs_rows):
    out = add01_active_satellites(obs_rows)
    assert list(out.columns) == ADD01_COLUMNS
    assert tuples(out) == [
        ("MODIS", 2001, 1, 1, "Terra"),
        ("MODIS", 2003, 2, 2, "Aqua,Terra"),
        ("VIIRS", 2018, 1, 1, "N20"),
    ]
    assert list(out.index) == [0, 1, 2]
    assert out["n_satellites"].dtype == "int64"
    assert out["year"].dtype == "int64" and out["month"].dtype == "int64"


def test_add01_zero_across_all_countries_is_inactive():
    out = add01_active_satellites(obs([
        ("PT", 2005, 3, "MODIS", "Terra", 2),
        ("PT", 2005, 3, "MODIS", "Aqua", 0),
        ("ES", 2005, 3, "MODIS", "Aqua", 0),
    ]))
    assert tuples(out) == [("MODIS", 2005, 3, 1, "Terra")]


def test_add01_sum_of_countries_makes_active_and_only_zero_month_absent():
    out = add01_active_satellites(obs([
        ("PT", 2005, 3, "MODIS", "Aqua", 0),
        ("ES", 2005, 3, "MODIS", "Aqua", 1),
        ("PT", 2005, 4, "MODIS", "Aqua", 0),
        ("ES", 2005, 4, "MODIS", "Aqua", 0),
    ]))
    assert tuples(out) == [("MODIS", 2005, 3, 1, "Aqua")]


def test_add01_mixed_case_names_untouched_and_sorted_plainly():
    # ordem alfabetica simples: maiusculas antes de minusculas
    out = add01_active_satellites(obs([
        ("PT", 2010, 7, "MODIS", "aqua", 1),
        ("PT", 2010, 7, "MODIS", "Terra", 1),
        ("PT", 2010, 7, "MODIS", "N20", 1),
    ]))
    assert tuples(out) == [("MODIS", 2010, 7, 3, "N20,Terra,aqua")]


def test_add01_instruments_independent_and_sorted():
    out = add01_active_satellites(obs([
        ("PT", 2019, 5, "VIIRS", "N20", 1),
        ("PT", 2019, 5, "VIIRS", "N21", 1),
        ("PT", 2019, 5, "MODIS", "Terra", 1),
        ("PT", 2018, 12, "VIIRS", "SNPP", 1),
    ]))
    assert tuples(out) == [
        ("MODIS", 2019, 5, 1, "Terra"),
        ("VIIRS", 2018, 12, 1, "SNPP"),
        ("VIIRS", 2019, 5, 2, "N20,N21"),
    ]


def test_add01_empty_and_missing_columns(obs_rows):
    out = add01_active_satellites(obs([]))
    assert out.empty and list(out.columns) == ADD01_COLUMNS
    allzero = add01_active_satellites(obs([("PT", 2001, 1, "MODIS", "Terra", 0)]))
    assert allzero.empty and list(allzero.columns) == ADD01_COLUMNS
    for col in obs_rows.columns:
        with pytest.raises(ValueError):
            add01_active_satellites(obs_rows.drop(columns=[col]))


def test_add01_order_invariance(obs_rows):
    expected = add01_active_satellites(obs_rows)
    for seed in range(3):
        shuffled = obs_rows.sample(frac=1, random_state=seed).reset_index(drop=True)
        pd.testing.assert_frame_equal(add01_active_satellites(shuffled), expected)


def test_add01_random_vs_pure_python_oracle():
    rng = random.Random(42)
    rows = [(rng.choice(["PT", "ES", "FR", "IT"]), rng.choice([2001, 2002]), rng.randint(1, 4),
             rng.choice(["MODIS", "VIIRS"]), rng.choice(["Terra", "Aqua", "N20", "SNPP"]),
             rng.choice([0, 0, 0, 1, 7])) for _ in range(300)]
    totals = {}
    for _, y, m, inst, sat, n in rows:
        totals[(inst, y, m, sat)] = totals.get((inst, y, m, sat), 0) + n
    groups = {}
    for (inst, y, m, sat), n in totals.items():
        if n > 0:
            groups.setdefault((inst, y, m), []).append(sat)
    expected = [(k[0], k[1], k[2], len(v), ",".join(sorted(v))) for k, v in sorted(groups.items())]
    assert len(expected) > 5
    assert tuples(add01_active_satellites(obs(rows))) == expected


# ------------------------------------------------------------------ ADD-02
# MODIS 2000-02-27..2000-03-02 com 5,0,0,3,0 (2000 e bissexto: fevereiro tem 29 dias)
#   2000-02: dias 27,28,29 -> n_days 3, zeros 2 (28 e 29), pct 200/3
#   2000-03: dias 1,2      -> n_days 2, zeros 1 (dia 2), pct 50
def test_add02_manual_example_partial_edge_months():
    out = add02_zero_days(cov(calendar("MODIS", "2000-02-27", [5, 0, 0, 3, 0])))
    assert list(out.columns) == ADD02_COLUMNS
    assert tuples(out) == [("MODIS", 2000, 2, 3, 2, pytest.approx(66.66666666666667)),
                           ("MODIS", 2000, 3, 2, 1, 50.0)]
    assert list(out.index) == [0, 1]
    assert out["n_days"].dtype == "int64" and out["n_zero_days"].dtype == "int64"
    assert out["pct_zero_days"].dtype == "float64"


def test_add02_february_lengths_and_31_30_day_months():
    # Fev 2000 (29 dias) tudo zero -> 29/29 ; Fev 2001 (28 dias) so o dia 1 nao zero -> 27/28
    leap = calendar("MODIS", "2000-02-01", [0] * 29)
    non_leap = calendar("VIIRS", "2001-02-01", [9] + [0] * 27)
    # Jan 2001 (31 dias): so os dias 1 e 2 com deteccoes -> 29 zeros ; Abr 2001 (30 dias): sem zeros
    jan = calendar("VIIRS", "2001-01-01", [1, 1] + [0] * 29)
    apr = calendar("VIIRS", "2001-04-01", [2] * 30)
    out = add02_zero_days(cov(leap + non_leap + jan + apr))
    assert tuples(out) == [
        ("MODIS", 2000, 2, 29, 29, 100.0),
        ("VIIRS", 2001, 1, 31, 29, pytest.approx(93.54838709677419)),
        ("VIIRS", 2001, 2, 28, 27, pytest.approx(96.42857142857143)),
        ("VIIRS", 2001, 4, 30, 0, 0.0),
    ]


def test_add02_duplicates_summed_before_counting():
    # dia 1: 0 + 4 = 4 (nao zero) ; dia 2: 0 + 0 = 0 (zero) ; dia 3: 0 + 0 + 1 = 1 (nao zero)
    out = add02_zero_days(cov([
        ("MODIS", "2002-05-01", 0), ("MODIS", "2002-05-01", 4),
        ("MODIS", "2002-05-02", 0), ("MODIS", "2002-05-02", 0),
        ("MODIS", "2002-05-03", 0), ("MODIS", "2002-05-03", 0), ("MODIS", "2002-05-03", 1),
    ]))
    assert tuples(out) == [("MODIS", 2002, 5, 3, 1, pytest.approx(100 / 3))]


def test_add02_instruments_independent_same_dates():
    out = add02_zero_days(cov([
        ("MODIS", "2019-06-01", 0), ("MODIS", "2019-06-02", 0),
        ("VIIRS", "2019-06-01", 5), ("VIIRS", "2019-06-02", 0),
    ]))
    assert tuples(out) == [("MODIS", 2019, 6, 2, 2, 100.0), ("VIIRS", 2019, 6, 2, 1, 50.0)]


def test_add02_month_boundary_and_year_boundary():
    out = add02_zero_days(cov(calendar("MODIS", "2000-12-31", [0, 1])))
    assert tuples(out) == [("MODIS", 2000, 12, 1, 1, 100.0), ("MODIS", 2001, 1, 1, 0, 0.0)]


def test_add02_empty_and_missing_columns():
    out = add02_zero_days(cov([]))
    assert out.empty and list(out.columns) == ADD02_COLUMNS
    full = cov([("MODIS", "2000-01-01", 1)])
    for col in full.columns:
        with pytest.raises(ValueError):
            add02_zero_days(full.drop(columns=[col]))


def test_add02_order_invariance():
    base = cov(calendar("MODIS", "2000-02-20", [1, 0, 0, 2, 0, 0, 0, 3, 0, 0, 1]) +
               calendar("VIIRS", "2012-01-25", [0, 0, 4, 0, 0, 0, 5, 0, 0, 0]) +
               [("MODIS", "2000-02-21", 0)])
    expected = add02_zero_days(base)
    for seed in range(3):
        shuffled = base.sample(frac=1, random_state=seed).reset_index(drop=True)
        pd.testing.assert_frame_equal(add02_zero_days(shuffled), expected)


def _random_coverage(seed):
    rng = random.Random(seed)
    rows = []
    for inst, start, n in (("MODIS", dt.date(1999, 11, 17), 500), ("VIIRS", dt.date(2011, 12, 5), 420)):
        for i in range(n):
            d = (start + dt.timedelta(days=i)).isoformat()
            rows.append((inst, d, rng.choice([0, 0, 0, 3, 12])))
            if rng.random() < 0.15:
                rows.append((inst, d, rng.choice([0, 0, 5])))  # duplicado
    rng.shuffle(rows)
    return rows


def test_add02_random_vs_pure_python_oracle_and_invariants():
    rows = _random_coverage(7)
    per_day = {}
    for inst, d, n in rows:
        per_day[(inst, d)] = per_day.get((inst, d), 0) + n
    months = {}
    for (inst, d), n in per_day.items():
        key = (inst, int(d[:4]), int(d[5:7]))
        tot, zero = months.get(key, (0, 0))
        months[key] = (tot + 1, zero + (1 if n == 0 else 0))
    expected = [(k[0], k[1], k[2], t, z, 100 * z / t) for k, (t, z) in sorted(months.items())]
    out = add02_zero_days(cov(rows))
    assert len(out) == len(expected) > 20
    assert [t[:5] for t in tuples(out)] == [e[:5] for e in expected]
    assert list(out["pct_zero_days"]) == pytest.approx([e[5] for e in expected])
    assert out["pct_zero_days"].between(0, 100).all()
    assert (out["n_zero_days"] <= out["n_days"]).all()
    assert out["n_days"].sum() == len(per_day)
    assert out["n_zero_days"].sum() == sum(1 for n in per_day.values() if n == 0)


# ------------------------------------------------ guardas de entrada (revisao independente)
def test_add02_timestamps_within_the_same_day_count_as_one_day():
    # 01-01 00:00 (0) + 01-01 12:00 (5) = 5 deteccoes nesse dia (nao e dia vazio); 01-02 00:00 (0) e dia vazio
    c = pd.DataFrame({"instrument": "MODIS",
                      "date": pd.to_datetime(["2000-01-01 00:00", "2000-01-01 12:00", "2000-01-02 00:00"]),
                      "n_rows_global": [0, 5, 0]})
    assert tuples(add02_zero_days(c)) == [("MODIS", 2000, 1, 2, 1, 50.0)]


def test_missing_values_raise_a_clear_value_error():
    o = obs([("PT", 2001, 1, "MODIS", "Terra", 5)])
    o["n_raw"] = pd.array([pd.NA], dtype="Int64")
    with pytest.raises(ValueError, match="n_raw"):
        add01_active_satellites(o)
    c = cov([("MODIS", "2000-01-01", 1)])
    c["n_rows_global"] = pd.array([pd.NA], dtype="Int64")
    with pytest.raises(ValueError, match="n_rows_global"):
        add02_zero_days(c)

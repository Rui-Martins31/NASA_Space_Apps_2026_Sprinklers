"""Testes do Lote 5 (QA-05 e ADD-06): dias com cobertura confirmada e degrau MODIS -> uniao em 2018.

Valores esperados calculados a mao (ver comentarios em cada teste); os oraculos usam so Python puro
(dicionarios, conjuntos, datetime, Fraction) e nunca importam codigo de outros lotes.
"""
import datetime as dt
import random
from fractions import Fraction

import pandas as pd
import pytest

from helpers_lote5 import calendar, coverage_df, monthly_df, tuples
from metrics.coverage_steps import (ADD06_COLUMNS, QA05_COLUMNS, add06_union_step,
                                    qa05_confirmed_days)


def _dtypes_ok_qa05(out):
    return (out["year"].dtype == "int64" and out["month"].dtype == "int64"
            and out["n_days_expected"].dtype == "int64" and out["n_days_confirmed"].dtype == "int64"
            and out["pct_confirmed"].dtype == "float64")


# ====================================================================== QA-05
# MODIS 2000-02-27..2000-03-02 com 5,0,0,3,0 ; VIIRS 2012-01-30..2012-02-02 com 1,2,0,4
#   MODIS 2000-02: dias 27,28,29 (5,0,0)  -> esperados 3, confirmados 1 (dia 27), pct 100/3
#   MODIS 2000-03: dias 1,2 (3,0)         -> esperados 2, confirmados 1 (dia 1), pct 50
#   VIIRS 2012-01: dias 30,31 (1,2)       -> esperados 2, confirmados 2, pct 100
#   VIIRS 2012-02: dias 1,2 (0,4)         -> esperados 2, confirmados 1 (dia 2), pct 50
def test_qa05_manual_example_partial_edge_months():
    cov = coverage_df(calendar("MODIS", "2000-02-27", [5, 0, 0, 3, 0])
                      + calendar("VIIRS", "2012-01-30", [1, 2, 0, 4]))
    out = qa05_confirmed_days(cov)
    assert list(out.columns) == QA05_COLUMNS
    assert QA05_COLUMNS == ["instrument", "year", "month", "n_days_expected", "n_days_confirmed",
                            "pct_confirmed", "scope"]
    assert tuples(out) == [
        ("MODIS", 2000, 2, 3, 1, pytest.approx(33.333333333333336), "global_proxy"),
        ("MODIS", 2000, 3, 2, 1, 50.0, "global_proxy"),
        ("VIIRS", 2012, 1, 2, 2, 100.0, "global_proxy"),
        ("VIIRS", 2012, 2, 2, 1, 50.0, "global_proxy"),
    ]
    assert list(out.index) == [0, 1, 2, 3]
    assert _dtypes_ok_qa05(out)


def test_qa05_zero_rows_are_not_confirmed_boundary_one_row():
    # n_rows_global = 0 nao confirma; n_rows_global = 1 (o minimo) confirma
    out = qa05_confirmed_days(coverage_df(calendar("MODIS", "2005-06-01", [0, 1, 0, 1, 1])))
    assert tuples(out) == [("MODIS", 2005, 6, 5, 3, 60.0, "global_proxy")]


def test_qa05_month_lengths_28_29_30_31():
    # MODIS fev/2000 (29 dias): confirmados so os dias 1-4        -> 4/29 -> 100*4/29
    # VIIRS fev/2001 (28 dias): todos confirmados                  -> 28/28 -> 100
    # VIIRS jan/2001 (31 dias): confirmados 10                     -> 10/31 -> 100*10/31
    # VIIRS abr/2001 (30 dias): nenhum confirmado                  -> 0/30 -> 0
    rows = (calendar("MODIS", "2000-02-01", [3] * 4 + [0] * 25)
            + calendar("VIIRS", "2001-01-01", [2] * 10 + [0] * 21)
            + calendar("VIIRS", "2001-02-01", [1] * 28)
            + calendar("VIIRS", "2001-04-01", [0] * 30))
    out = qa05_confirmed_days(coverage_df(rows))
    assert tuples(out) == [
        ("MODIS", 2000, 2, 29, 4, pytest.approx(13.793103448275861), "global_proxy"),
        ("VIIRS", 2001, 1, 31, 10, pytest.approx(32.25806451612903), "global_proxy"),
        ("VIIRS", 2001, 2, 28, 28, 100.0, "global_proxy"),
        ("VIIRS", 2001, 4, 30, 0, 0.0, "global_proxy"),
    ]


def test_qa05_year_boundary_and_instruments_independent():
    # MODIS 2000-12-30..2001-01-02 com 0,1,2,0:
    #   2000-12 -> dias 30,31 (0,1): esperados 2, confirmados 1 ; 2001-01 -> dias 1,2 (2,0): 2 e 1
    # VIIRS 2000-12-31 com 0 (mesma data, outro instrumento) -> 1 esperado, 0 confirmados
    out = qa05_confirmed_days(coverage_df(calendar("MODIS", "2000-12-30", [0, 1, 2, 0])
                                          + [("VIIRS", "2000-12-31", 0)]))
    assert tuples(out) == [
        ("MODIS", 2000, 12, 2, 1, 50.0, "global_proxy"),
        ("MODIS", 2001, 1, 2, 1, 50.0, "global_proxy"),
        ("VIIRS", 2000, 12, 1, 0, 0.0, "global_proxy"),
    ]


def test_qa05_repeated_rows_for_same_day_are_summed_before_counting():
    # dia 1: 0 + 4 = 4 (confirmado) ; dia 2: 0 + 0 = 0 (nao) ; dia 3: 0 + 0 + 1 = 1 (confirmado)
    # => 3 dias esperados (nao 7 linhas), 2 confirmados, pct 200/3
    out = qa05_confirmed_days(coverage_df([
        ("MODIS", "2002-05-01", 0), ("MODIS", "2002-05-01", 4),
        ("MODIS", "2002-05-02", 0), ("MODIS", "2002-05-02", 0),
        ("MODIS", "2002-05-03", 0), ("MODIS", "2002-05-03", 0), ("MODIS", "2002-05-03", 1),
    ]))
    assert tuples(out) == [("MODIS", 2002, 5, 3, 2, pytest.approx(66.66666666666667), "global_proxy")]


def test_qa05_timestamps_within_the_same_day_count_as_one_day():
    # 01-01 00:00 (0) + 01-01 12:00 (5) = dia 1 confirmado ; 01-02 00:00 (0) = dia 2 nao confirmado
    cov = pd.DataFrame({"instrument": "MODIS",
                        "date": pd.to_datetime(["2000-01-01 00:00", "2000-01-01 12:00", "2000-01-02 00:00"]),
                        "n_rows_global": [0, 5, 0]})
    assert tuples(qa05_confirmed_days(cov)) == [("MODIS", 2000, 1, 2, 1, 50.0, "global_proxy")]


def test_qa05_scope_is_global_proxy_in_every_row():
    out = qa05_confirmed_days(coverage_df(calendar("MODIS", "2000-01-30", [1, 0, 2, 0])
                                          + calendar("VIIRS", "2012-03-01", [0, 5])))
    assert len(out) == 3
    assert list(out["scope"]) == ["global_proxy"] * 3


def test_qa05_empty_and_missing_columns():
    out = qa05_confirmed_days(coverage_df([]))
    assert out.empty and list(out.columns) == QA05_COLUMNS
    assert _dtypes_ok_qa05(out)
    # tambem com colunas vazias sem tipo (object/float64), como numa leitura de ficheiro vazio
    bare = qa05_confirmed_days(pd.DataFrame({"instrument": [], "date": [], "n_rows_global": []}))
    assert bare.empty and list(bare.columns) == QA05_COLUMNS and _dtypes_ok_qa05(bare)
    full = coverage_df([("MODIS", "2000-01-01", 1)])
    for col in full.columns:
        with pytest.raises(ValueError, match=col):
            qa05_confirmed_days(full.drop(columns=[col]))


def test_qa05_missing_values_raise_a_clear_value_error():
    base = coverage_df([("MODIS", "2000-01-01", 1), ("MODIS", "2000-01-02", 0)])
    na_n = base.copy()
    na_n["n_rows_global"] = pd.array([1, pd.NA], dtype="Int64")
    with pytest.raises(ValueError, match="n_rows_global"):
        qa05_confirmed_days(na_n)
    na_date = base.copy()
    na_date["date"] = pd.to_datetime(["2000-01-01", None])
    with pytest.raises(ValueError, match="date"):
        qa05_confirmed_days(na_date)
    na_inst = base.copy()
    na_inst["instrument"] = ["MODIS", None]
    with pytest.raises(ValueError, match="instrument"):
        qa05_confirmed_days(na_inst)


def test_qa05_order_invariance():
    base = coverage_df(calendar("MODIS", "2000-02-20", [1, 0, 0, 2, 0, 0, 0, 3, 0, 0, 1])
                       + calendar("VIIRS", "2012-01-25", [0, 0, 4, 0, 0, 0, 5, 0, 0, 0])
                       + [("MODIS", "2000-02-21", 0), ("MODIS", "2000-02-20", 7)])
    expected = qa05_confirmed_days(base)
    assert len(expected) == 4
    for seed in range(4):
        shuffled = base.sample(frac=1, random_state=seed).reset_index(drop=True)
        pd.testing.assert_frame_equal(qa05_confirmed_days(shuffled), expected)


def _random_coverage_rows(seed):
    rng = random.Random(seed)
    rows = []
    for inst, start, n in (("MODIS", dt.date(1999, 11, 17), 500), ("VIIRS", dt.date(2011, 12, 5), 420)):
        for i in range(n):
            d = (start + dt.timedelta(days=i)).isoformat()
            rows.append((inst, d, rng.choice([0, 0, 0, 3, 12])))
            if rng.random() < 0.15:
                rows.append((inst, d, rng.choice([0, 0, 5])))  # linha repetida do mesmo dia
    rng.shuffle(rows)
    return rows


def test_qa05_random_vs_pure_python_oracle():
    rows = _random_coverage_rows(7)
    # oraculo: totais por (instrumento, dia) em dicionario; por mes, conjuntos de dias e de dias confirmados
    totals = {}
    for inst, d, n in rows:
        key = (inst, dt.date.fromisoformat(d))
        totals[key] = totals.get(key, 0) + n
    days_by_month, confirmed_by_month = {}, {}
    for (inst, day), n in totals.items():
        mk = (inst, day.year, day.month)
        days_by_month.setdefault(mk, set()).add(day)
        if n > 0:
            confirmed_by_month.setdefault(mk, set()).add(day)
    out = qa05_confirmed_days(coverage_df(rows))
    assert len(out) == len(days_by_month) > 25
    assert [(r[0], r[1], r[2]) for r in tuples(out)] == sorted(days_by_month)
    for r in tuples(out):
        mk = (r[0], r[1], r[2])
        n_exp, n_conf = len(days_by_month[mk]), len(confirmed_by_month.get(mk, set()))
        assert (r[3], r[4]) == (n_exp, n_conf)
        assert r[5] == pytest.approx(float(Fraction(100 * n_conf, n_exp)))
        assert r[6] == "global_proxy"
    assert out["n_days_expected"].sum() == len(totals)
    assert out["pct_confirmed"].between(0, 100).all()


def test_qa05_cross_invariant_with_zero_days_counted_by_hand():
    # Contagem manual dos dias sem registos ("zero") por mes; a invariante do ADD-02:
    #   pct_confirmed + 100 * n_zero_days / n_days = 100
    # VIIRS jan/2001 (31 dias): 3 zeros  -> 28 confirmados -> 100*28/31 ; zeros 100*3/31
    # VIIRS fev/2001 (28 dias): 7 zeros  -> 21 confirmados -> 75.0      ; zeros 25.0
    # VIIRS abr/2001 (30 dias): 12 zeros -> 18 confirmados -> 60.0      ; zeros 40.0
    # MODIS fev/2000 (29 dias): 29 zeros ->  0 confirmados -> 0.0       ; zeros 100.0
    # MODIS mar/2000 (31 dias): 0 zeros  -> 31 confirmados -> 100.0     ; zeros 0.0
    rows = (calendar("VIIRS", "2001-01-01", [1] * 28 + [0] * 3)
            + calendar("VIIRS", "2001-02-01", [0] * 7 + [4] * 21)
            + calendar("VIIRS", "2001-04-01", [9] * 18 + [0] * 12)
            + calendar("MODIS", "2000-02-01", [0] * 29)
            + calendar("MODIS", "2000-03-01", [2] * 31))
    zero_by_hand = {("VIIRS", 2001, 1): 3, ("VIIRS", 2001, 2): 7, ("VIIRS", 2001, 4): 12,
                    ("MODIS", 2000, 2): 29, ("MODIS", 2000, 3): 0}
    out = qa05_confirmed_days(coverage_df(rows))
    assert tuples(out) == [
        ("MODIS", 2000, 2, 29, 0, 0.0, "global_proxy"),
        ("MODIS", 2000, 3, 31, 31, 100.0, "global_proxy"),
        ("VIIRS", 2001, 1, 31, 28, pytest.approx(90.32258064516128), "global_proxy"),
        ("VIIRS", 2001, 2, 28, 21, 75.0, "global_proxy"),
        ("VIIRS", 2001, 4, 30, 18, 60.0, "global_proxy"),
    ]
    for r in tuples(out):
        n_zero = zero_by_hand[(r[0], r[1], r[2])]
        assert r[5] + 100 * n_zero / r[3] == pytest.approx(100.0)
        assert r[3] - r[4] == n_zero


# ====================================================================== ADD-06
def _pair(country="P", year=2018, month=1, modis=0, combined=0, **extra):
    """Duas linhas (modis e combined) de um mes; `extra` aplica-se as duas."""
    base = {"country": country, "year": year, "month": month, **extra}
    return [{**base, "series": "modis", "cell_days": modis},
            {**base, "series": "combined", "cell_days": combined}]


# Esperado (a mao):
#   P 2017: meses 1 e 2, modis 10+20, combined 10+20 (antes de 2018 combined = modis) -> 2 meses, 30, 30, 1, 0
#   P 2018: mes 1 (modis 100, combined 130, viirs 30 ignorado) e mes 2 (modis 300, combined 370):
#           2 meses, 400, 500, ratio 1.25, excesso 25. O mes 3 tem modis parcial -> fora.
#   Q 2017: meses 2 e 3, modis 5+7, combined 5+7 -> 2 meses, 12, 12, 1, 0
#   Q 2018: mes 1 modis 100 combined 120 -> 1 mes, 100, 120, ratio 1.2, excesso 20
#   ALL 2017: meses distintos {1,2} U {2,3} = 3 ; modis 30+12 = 42, combined 42 -> 1, 0
#   ALL 2018: meses distintos {1,2} U {1} = 2 ; modis 400+100 = 500, combined 500+120 = 620 -> 1.24, 24
@pytest.fixture
def monthly_manual():
    rows = (_pair("P", 2017, 1, 10, 10) + _pair("P", 2017, 2, 20, 20)
            + _pair("P", 2018, 1, 100, 130) + _pair("P", 2018, 2, 300, 370)
            + [{"country": "P", "year": 2018, "month": 1, "series": "viirs", "cell_days": 30},
               {"country": "P", "year": 2018, "month": 2, "series": "viirs", "cell_days": 70}]
            + [{"country": "P", "year": 2018, "month": 3, "series": "modis", "cell_days": 999, "partial": True},
               {"country": "P", "year": 2018, "month": 3, "series": "combined", "cell_days": 888}]
            + _pair("Q", 2017, 2, 5, 5) + _pair("Q", 2017, 3, 7, 7)
            + _pair("Q", 2018, 1, 100, 120))
    return monthly_df(rows)


def test_add06_manual_example(monthly_manual):
    out = add06_union_step(monthly_manual)
    assert list(out.columns) == ADD06_COLUMNS
    assert ADD06_COLUMNS == ["country", "year", "n_months", "sum_modis", "sum_combined",
                             "ratio_combined_modis", "excess_pct"]
    assert tuples(out) == [
        ("ALL", 2017, 3, 42, 42, 1.0, 0.0),
        ("ALL", 2018, 2, 500, 620, pytest.approx(1.24), pytest.approx(24.0)),
        ("P", 2017, 2, 30, 30, 1.0, 0.0),
        ("P", 2018, 2, 400, 500, 1.25, 25.0),
        ("Q", 2017, 2, 12, 12, 1.0, 0.0),
        ("Q", 2018, 1, 100, 120, pytest.approx(1.2), pytest.approx(20.0)),
    ]
    assert list(out.index) == list(range(6))
    for c in ("year", "n_months", "sum_modis", "sum_combined"):
        assert out[c].dtype == "int64", c
    assert out["ratio_combined_modis"].dtype == "float64" and out["excess_pct"].dtype == "float64"


def test_add06_empty_input_and_nothing_countable():
    out = add06_union_step(monthly_df([]))
    assert out.empty and list(out.columns) == ADD06_COLUMNS
    assert out["year"].dtype == "int64" and out["n_months"].dtype == "int64"
    assert out["sum_modis"].dtype == "int64" and out["sum_combined"].dtype == "int64"
    assert out["ratio_combined_modis"].dtype == "float64" and out["excess_pct"].dtype == "float64"
    bare = add06_union_step(pd.DataFrame({c: [] for c in monthly_df([]).columns}))
    assert bare.empty and list(bare.columns) == ADD06_COLUMNS and bare["n_months"].dtype == "int64"
    # so viirs, ou so um mes invalido: nenhum pais-ano contavel, nada aparece
    only = add06_union_step(monthly_df([
        {"series": "viirs", "cell_days": 5},
        {"month": 4, "series": "modis", "cell_days": 5, "partial": True},
        {"month": 4, "series": "combined", "cell_days": 5},
    ]))
    assert only.empty and list(only.columns) == ADD06_COLUMNS
    assert only["sum_modis"].dtype == "int64" and only["excess_pct"].dtype == "float64"


@pytest.mark.parametrize("label, bad_rows", [
    ("combined ausente", [{"series": "modis", "cell_days": 900}]),
    ("modis ausente", [{"series": "combined", "cell_days": 900}]),
    ("modis parcial", [{"series": "modis", "cell_days": 900, "partial": True},
                       {"series": "combined", "cell_days": 900}]),
    ("combined parcial", [{"series": "modis", "cell_days": 900},
                          {"series": "combined", "cell_days": 900, "partial": True}]),
    ("modis com dias desconhecidos", [{"series": "modis", "cell_days": 900, "n_unknown_days": 1},
                                      {"series": "combined", "cell_days": 900}]),
    ("combined com dias desconhecidos", [{"series": "modis", "cell_days": 900},
                                         {"series": "combined", "cell_days": 900, "n_unknown_days": 1}]),
    ("so viirs valido", [{"series": "viirs", "cell_days": 900}]),
])
def test_add06_month_out_unless_modis_and_combined_both_valid(label, bad_rows):
    # mes 1 (valido nas duas series): modis 10, combined 12 ; o mes 2 (`bad_rows`) tem de ficar fora
    rows = [{"month": 1, "series": "modis", "cell_days": 10, "year": 2018},
            {"month": 1, "series": "combined", "cell_days": 12, "year": 2018}]
    rows += [{**r, "month": 2, "year": 2018} for r in bad_rows]
    out = add06_union_step(monthly_df(rows))
    assert tuples(out) == [
        ("ALL", 2018, 1, 10, 12, pytest.approx(1.2), pytest.approx(20.0)),
        ("P", 2018, 1, 10, 12, pytest.approx(1.2), pytest.approx(20.0)),
    ], label


def test_add06_viirs_series_is_ignored_even_when_invalid_or_huge():
    rows = _pair(modis=10, combined=14) + [
        {"series": "viirs", "cell_days": 10_000, "partial": True, "n_unknown_days": 5}]
    out = add06_union_step(monthly_df(rows))
    assert tuples(out)[1] == ("P", 2018, 1, 10, 14, pytest.approx(1.4), pytest.approx(40.0))


def test_add06_max_unknown_days_boundary_inclusive_and_non_default():
    # 4 meses, n_unknown_days = 0,1,2,3 nas duas series; modis = 1,10,100,1000 ; combined = o dobro
    rows = []
    for month, unk, m in ((1, 0, 1), (2, 1, 10), (3, 2, 100), (4, 3, 1000)):
        rows += _pair(month=month, modis=m, combined=2 * m, n_unknown_days=unk)
    monthly = monthly_df(rows)
    # (max_unknown_days, n_months, sum_modis): <= inclusivo
    for max_unk, n_months, sum_modis in ((None, 1, 1), (0, 1, 1), (1, 2, 11), (2, 3, 111), (3, 4, 1111)):
        out = add06_union_step(monthly) if max_unk is None else add06_union_step(monthly, max_unknown_days=max_unk)
        p = tuples(out)[1]
        assert p[:5] == ("P", 2018, n_months, sum_modis, 2 * sum_modis), max_unk
        assert p[5] == 2.0 and p[6] == 100.0


def test_add06_max_unknown_days_applies_to_each_series_separately():
    # modis tem 0 dias desconhecidos, combined tem 2: com max=1 o mes fica fora, com max=2 entra
    monthly = monthly_df(_pair(month=1, modis=5, combined=6, n_unknown_days=0)[:1]
                         + _pair(month=1, modis=5, combined=6, n_unknown_days=2)[1:])
    assert add06_union_step(monthly, max_unknown_days=1).empty
    assert tuples(add06_union_step(monthly, max_unknown_days=2))[1][:5] == ("P", 2018, 1, 5, 6)


def test_add06_zero_modis_gives_na_ratio_and_excess():
    # A: modis 0, combined 5 -> sum_modis 0 => ratio e excesso NA (nem inf nem 0)
    # B: modis 0, combined 0 -> idem (nao 1)
    # C: modis 10, combined 10 ; ALL = 10, 15 -> 1.5, 50 (sum_modis do total nao e 0)
    rows = (_pair("A", month=1, modis=0, combined=5) + _pair("B", month=1, modis=0, combined=0)
            + _pair("C", month=1, modis=10, combined=10) + _pair("C", month=2, modis=0, combined=5))
    out = add06_union_step(monthly_df(rows))
    assert tuples(out) == [
        ("A", 2018, 1, 0, 5, None, None),
        ("ALL", 2018, 2, 10, 20, pytest.approx(2.0), pytest.approx(100.0)),
        ("B", 2018, 1, 0, 0, None, None),
        ("C", 2018, 2, 10, 15, pytest.approx(1.5), pytest.approx(50.0)),
    ]
    assert out["ratio_combined_modis"].dtype == "float64"
    assert out["ratio_combined_modis"].isna().tolist() == [True, False, True, False]
    assert out["excess_pct"].isna().tolist() == [True, False, True, False]


def test_add06_all_row_ratio_is_na_when_total_modis_is_zero():
    out = add06_union_step(monthly_df(_pair("A", month=1, modis=0, combined=0)
                                      + _pair("B", month=1, modis=0, combined=3)))
    # ALL: sum_modis 0, sum_combined 3, 1 mes distinto => ratio e excesso NA
    assert tuples(out) == [("A", 2018, 1, 0, 0, None, None),
                           ("ALL", 2018, 1, 0, 3, None, None),
                           ("B", 2018, 1, 0, 3, None, None)]


def test_add06_all_row_only_adds_countable_months_and_distinct_months():
    # A mes 1: modis 10 combined 15 (valido). B mes 1: modis 100 valido mas combined parcial -> B fora e
    # nao entra no ALL. C meses 1 e 2: 1+2, 3+4 ; ALL: meses distintos {1,2} (n_months = 2, nao 3)
    rows = (_pair("A", month=1, modis=10, combined=15)
            + [{"country": "B", "year": 2018, "month": 1, "series": "modis", "cell_days": 100},
               {"country": "B", "year": 2018, "month": 1, "series": "combined", "cell_days": 100, "partial": True}]
            + _pair("C", month=1, modis=1, combined=3) + _pair("C", month=2, modis=2, combined=4))
    out = add06_union_step(monthly_df(rows))
    assert [r[:5] for r in tuples(out)] == [
        ("A", 2018, 1, 10, 15),
        ("ALL", 2018, 2, 13, 22),
        ("C", 2018, 2, 3, 7),
    ]
    all_row = tuples(out)[1]
    assert all_row[5] == pytest.approx(22 / 13) and all_row[6] == pytest.approx(100 * 9 / 13)


def test_add06_years_are_independent_and_ordered_by_country_then_year():
    # ordenacao textual simples: "AA" < "ALL" < "ZW"; dentro do pais, por ano
    rows = (_pair("ZW", 2018, 1, 1, 1) + _pair("AA", 2019, 1, 2, 2) + _pair("AA", 2018, 5, 4, 4)
            + _pair("ZW", 2019, 3, 8, 8))
    out = add06_union_step(monthly_df(rows))
    assert [(r[0], r[1], r[2], r[3]) for r in tuples(out)] == [
        ("AA", 2018, 1, 4), ("AA", 2019, 1, 2),
        ("ALL", 2018, 2, 5), ("ALL", 2019, 2, 10),
        ("ZW", 2018, 1, 1), ("ZW", 2019, 1, 8),
    ]
    # ALL 2018: meses {5} U {1} = 2 distintos ; ALL 2019: {1} U {3} = 2


def test_add06_before_2018_union_equals_modis_exactly():
    rows = []
    for year in (2005, 2010, 2017):
        for month, val in ((1, 3), (6, 11), (12, 0)):
            rows += _pair("P", year, month, val, val) + _pair("Q", year, month, val + 1, val + 1)
    out = add06_union_step(monthly_df(rows))
    pre = out[out["year"] < 2018]
    assert len(pre) == 9  # (P, Q, ALL) x 3 anos
    # P 2005: modis = combined = 3 + 11 + 0 = 14 ; Q: 4 + 12 + 1 = 17 ; ALL = 31
    assert tuples(pre)[:3] == [("ALL", 2005, 3, 31, 31, 1.0, 0.0), ("ALL", 2010, 3, 31, 31, 1.0, 0.0),
                               ("ALL", 2017, 3, 31, 31, 1.0, 0.0)]
    assert (pre["ratio_combined_modis"] == 1.0).all() and (pre["excess_pct"] == 0.0).all()


def test_add06_step_after_2018_ratio_above_one_when_viirs_adds_cells():
    # 2017: combined = modis -> 1.0 ; 2018: viirs acrescenta -> combined 150 > modis 100 -> ratio 1.5, excesso 50
    rows = (_pair("P", 2017, 7, 100, 100) + _pair("P", 2018, 7, 100, 150)
            + [{"country": "P", "year": 2018, "month": 7, "series": "viirs", "cell_days": 90}])
    out = add06_union_step(monthly_df(rows))
    p = {(r[0], r[1]): r for r in tuples(out)}
    assert p[("P", 2017)][5:] == (1.0, 0.0)
    assert p[("P", 2018)][5:] == (1.5, 50.0)


def test_add06_errors():
    base = monthly_df(_pair(modis=1, combined=2))
    # chave repetida (country, series, year, month), mesmo na serie viirs ou com valores iguais
    dup = pd.concat([base, base.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repetid"):
        add06_union_step(dup)
    viirs_dup = monthly_df(_pair(modis=1, combined=2)
                           + [{"series": "viirs", "cell_days": 1}, {"series": "viirs", "cell_days": 2}])
    with pytest.raises(ValueError, match="repetid"):
        add06_union_step(viirs_dup)
    # colunas em falta
    for col in base.columns:
        with pytest.raises(ValueError, match=col):
            add06_union_step(base.drop(columns=[col]))
    # mesma chave em series diferentes e meses diferentes NAO e repetida
    ok = monthly_df(_pair(month=1, modis=1, combined=1) + _pair(month=2, modis=1, combined=1))
    assert len(add06_union_step(ok)) == 2


@pytest.mark.parametrize("col", ["cell_days", "country", "year", "month", "series", "partial",
                                 "n_unknown_days"])
def test_add06_missing_values_raise_a_clear_value_error(col):
    base = monthly_df(_pair(modis=1, combined=2))
    na = base.copy()
    na[col] = na[col].astype("object")
    na.loc[0, col] = None
    with pytest.raises(ValueError, match=col):
        add06_union_step(na)


def test_add06_order_invariance(monthly_manual):
    expected = add06_union_step(monthly_manual)
    for seed in range(4):
        shuffled = monthly_manual.sample(frac=1, random_state=seed).reset_index(drop=True)
        pd.testing.assert_frame_equal(add06_union_step(shuffled), expected)


def test_add06_does_not_mutate_input(monthly_manual):
    before = monthly_manual.copy()
    add06_union_step(monthly_manual)
    pd.testing.assert_frame_equal(monthly_manual, before)


# ---- oraculo independente (Python puro) e invariantes
def _random_monthly_rows(seed):
    rng = random.Random(seed)
    rows = []
    for country in ("AA", "BB", "CC", "DD"):
        for year in range(2015, 2021):
            for month in range(1, 13):
                m = rng.randint(1, 40) if rng.random() > 0.2 else 0
                v = rng.randint(0, 30) if year >= 2018 else 0
                c = rng.randint(max(m, v), m + v) if year >= 2018 else m
                for series, val in (("modis", m), ("viirs", v), ("combined", c)):
                    if series != "viirs" and rng.random() < 0.1:
                        continue                                        # linha em falta
                    rows.append({"country": country, "year": year, "month": month, "series": series,
                                 "cell_days": val, "partial": rng.random() < 0.1,
                                 "n_unknown_days": rng.choice([0, 0, 0, 0, 1, 2])})
    rng.shuffle(rows)
    return rows


def _oracle_add06(rows, max_unknown_days):
    by_month = {}
    for r in rows:
        by_month.setdefault((r["country"], r["year"], r["month"]), {})[r["series"]] = r

    def valid(r):
        return (not r["partial"]) and r["n_unknown_days"] <= max_unknown_days

    per_country, per_year = {}, {}
    for (country, year, month), s in by_month.items():
        if "modis" in s and "combined" in s and valid(s["modis"]) and valid(s["combined"]):
            a = per_country.setdefault((country, year), [0, 0, 0, 0])
            a[0] += 1
            a[1] += s["modis"]["cell_days"]
            a[2] += s["combined"]["cell_days"]
            a[3] += s["viirs"]["cell_days"]                              # viirs existe sempre nestes dados
            b = per_year.setdefault(year, [set(), 0, 0, 0])
            b[0].add(month)
            b[1] += s["modis"]["cell_days"]
            b[2] += s["combined"]["cell_days"]
            b[3] += s["viirs"]["cell_days"]
    expected = {k: (v[0], v[1], v[2], v[3]) for k, v in per_country.items()}
    expected.update({("ALL", y): (len(v[0]), v[1], v[2], v[3]) for y, v in per_year.items()})
    return expected


@pytest.mark.parametrize("seed, max_unknown_days", [(11, 0), (12, 0), (13, 1), (14, 2)])
def test_add06_random_vs_pure_python_oracle_and_invariants(seed, max_unknown_days):
    rows = _random_monthly_rows(seed)
    expected = _oracle_add06(rows, max_unknown_days)
    out = add06_union_step(monthly_df(rows), max_unknown_days=max_unknown_days)
    assert len(expected) == len(out) > 15
    assert [(r[0], r[1]) for r in tuples(out)] == sorted(expected)
    for r in tuples(out):
        n_months, sm, sc, sv = expected[(r[0], r[1])]
        assert (r[2], r[3], r[4]) == (n_months, sm, sc)
        if sm == 0:
            assert r[5] is None and r[6] is None
        else:
            assert r[5] == pytest.approx(float(Fraction(sc, sm)))
            assert r[6] == pytest.approx(float(100 * (Fraction(sc, sm) - 1)))
            # combined >= modis em cada mes dos dados => ratio >= 1 e excesso >= 0
            assert r[5] >= 1.0 and r[6] >= 0.0
        # combined <= modis + viirs em cada mes dos dados (uniao nunca excede a soma)
        assert sm <= sc <= sm + sv
        if r[1] < 2018:
            assert sc == sm                                              # antes de 2018 combined == modis
            if sm > 0:
                assert r[5] == 1.0 and r[6] == 0.0
    # ALL = soma dos paises, e n_months entre o maximo e a soma dos paises
    for year in {r[1] for r in tuples(out)}:
        ctry = [r for r in tuples(out) if r[1] == year and r[0] != "ALL"]
        all_row = [r for r in tuples(out) if r[1] == year and r[0] == "ALL"][0]
        assert all_row[3] == sum(r[3] for r in ctry) and all_row[4] == sum(r[4] for r in ctry)
        assert max(r[2] for r in ctry) <= all_row[2] <= min(12, sum(r[2] for r in ctry))

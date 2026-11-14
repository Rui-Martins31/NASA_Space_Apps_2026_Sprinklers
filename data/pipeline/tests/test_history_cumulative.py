"""Testes de HIS-07 (acumulado no ano), HIS-08 (variacao homologa) e HIS-10 (tendencia Theil-Sen).

Valores esperados calculados a mao (ver comentarios). Regras: spec/metodologia_metricas.md, 7B/7D.
"""
import random

import numpy as np
import pandas as pd
import pytest

from helpers_lote4 import monthly_df, recs
from helpers_lote4_b import annual_df, annual_series
from metrics.history_cumulative import his07_ytd, his08_yoy, his10_trend

YTD_COLS = ["country", "series", "year", "month", "ytd_cell_days", "comparable",
            "n_ref_years", "ref_ytd_mean", "ytd_diff"]
YOY_COLS = ["country", "series", "year", "month", "cell_days", "prev_cell_days",
            "valid_pair", "diff_abs", "yoy_pct"]
TREND_COLS = ["country", "series", "n_years", "first_year", "last_year",
              "slope_per_year", "intercept", "slope_p025", "slope_p975"]


def year_months(year, values, **extra):
    """Linhas mensais de um ano: meses 1..len(values)."""
    return [{"year": year, "month": m, "cell_days": v, **extra} for m, v in enumerate(values, 1)]


def ytd_rows(df, cols=YTD_COLS):
    return [tuple(r[c] for c in cols) for r in recs(df, cols)]


# 3 anos x 3 meses, tudo valido (P/modis):
#   2001: 1,2,3 -> ytd 1,3,6 | 2002: 2,2,2 -> ytd 2,4,6 | 2003: 3,5,1 -> ytd 3,8,9
THREE_YEARS = (year_months(2001, [1, 2, 3]) + year_months(2002, [2, 2, 2])
               + year_months(2003, [3, 5, 1]))


# ================================================================= HIS-07
def test_his07_hand_example():
    out = his07_ytd(monthly_df(THREE_YEARS), min_ref_years=2)
    assert list(out.columns) == YTD_COLS
    # mes 1 (ytd 1,2,3): 2001 ref (2+3)/2=2.5; 2002 ref (1+3)/2=2.0; 2003 ref (1+2)/2=1.5
    # mes 2 (ytd 3,4,8): 2001 ref (4+8)/2=6; 2002 ref (3+8)/2=5.5; 2003 ref (3+4)/2=3.5
    # mes 3 (ytd 6,6,9): 2001 ref (6+9)/2=7.5; 2002 ref 7.5; 2003 ref (6+6)/2=6
    assert ytd_rows(out) == [
        ("P", "modis", 2001, 1, 1, True, 2, 2.5, -1.5),
        ("P", "modis", 2001, 2, 3, True, 2, 6.0, -3.0),
        ("P", "modis", 2001, 3, 6, True, 2, 7.5, -1.5),
        ("P", "modis", 2002, 1, 2, True, 2, 2.0, 0.0),
        ("P", "modis", 2002, 2, 4, True, 2, 5.5, -1.5),
        ("P", "modis", 2002, 3, 6, True, 2, 7.5, -1.5),
        ("P", "modis", 2003, 1, 3, True, 2, 1.5, 1.5),
        ("P", "modis", 2003, 2, 8, True, 2, 3.5, 4.5),
        ("P", "modis", 2003, 3, 9, True, 2, 6.0, 3.0)]
    assert out["comparable"].dtype == bool


def test_his07_default_min_ref_years_gives_na_but_reports_pool_size():
    out = his07_ytd(monthly_df(THREE_YEARS))       # min_ref_years=5 por defeito
    assert out["n_ref_years"].tolist() == [2] * 9
    assert out["ref_ytd_mean"].isna().all() and out["ytd_diff"].isna().all()
    assert out["ytd_cell_days"].tolist() == [1, 3, 6, 2, 4, 6, 3, 8, 9]
    assert out["comparable"].all()


def test_his07_min_ref_years_boundary():
    # pool de 2 outros anos: min 2 chega, min 3 nao
    assert his07_ytd(monthly_df(THREE_YEARS), min_ref_years=2)["ytd_diff"].notna().all()
    assert his07_ytd(monthly_df(THREE_YEARS), min_ref_years=3)["ytd_diff"].isna().all()


def test_his07_reference_window_is_inclusive_and_excludes_outside_years():
    df = monthly_df(THREE_YEARS)
    out = his07_ytd(df, ref_start=2002, min_ref_years=2)
    # pool do mes 1 = {2002, 2003}: 2001 usa ambos (2.5), 2002 so tem 2003 (n=1 -> NA)
    r = {(x["year"], x["month"]): x for x in recs(out)}
    assert (r[(2001, 1)]["n_ref_years"], r[(2001, 1)]["ref_ytd_mean"]) == (2, 2.5)
    assert (r[(2002, 1)]["n_ref_years"], r[(2002, 1)]["ref_ytd_mean"], r[(2002, 1)]["ytd_diff"]) == (1, None, None)
    # linha fora da janela continua a ter a sua propria linha, avaliada contra o pool
    assert (r[(2001, 2)]["ytd_cell_days"], r[(2001, 2)]["n_ref_years"]) == (3, 2)
    out = his07_ytd(df, ref_end=2002, min_ref_years=2)
    r = {(x["year"], x["month"]): x for x in recs(out)}
    # pool do mes 1 = {2001, 2002}: 2003 usa ambos ((1+2)/2=1.5); 2001 so tem 2002 (n=1)
    assert (r[(2003, 1)]["n_ref_years"], r[(2003, 1)]["ref_ytd_mean"]) == (2, 1.5)
    assert (r[(2001, 1)]["n_ref_years"], r[(2001, 1)]["ref_ytd_mean"]) == (1, None)


def test_his07_partial_month_breaks_comparability_of_later_months():
    rows = [dict(r) for r in THREE_YEARS]
    for r in rows:
        if r["year"] == 2001 and r["month"] == 2:
            r["partial"] = True
    out = his07_ytd(monthly_df(rows), min_ref_years=2)
    r = {(x["year"], x["month"]): x for x in recs(out)}
    # 2001: mes 1 comparavel; meses 2 e 3 nao (soma continua calculada: 3 e 6), sem referencia
    assert [(r[(2001, m)]["ytd_cell_days"], r[(2001, m)]["comparable"]) for m in (1, 2, 3)] == [
        (1, True), (3, False), (6, False)]
    assert all(r[(2001, m)][c] is None for m in (2, 3) for c in ("ref_ytd_mean", "ytd_diff"))
    # 2001 nao entra no pool dos meses 2 e 3: 2002 fica com n=1 (so 2003) -> NA
    assert (r[(2002, 2)]["n_ref_years"], r[(2002, 2)]["ytd_diff"]) == (1, None)
    assert (r[(2002, 3)]["n_ref_years"], r[(2002, 3)]["ytd_diff"]) == (1, None)
    # mes 1 continua com os 3 anos: 2002 ref (1+3)/2 = 2.0
    assert (r[(2002, 1)]["n_ref_years"], r[(2002, 1)]["ref_ytd_mean"]) == (2, 2.0)


def test_his07_unknown_days_threshold():
    rows = [dict(r) for r in THREE_YEARS]
    for r in rows:
        if r["year"] == 2003 and r["month"] == 1:
            r["n_unknown_days"] = 2
    df = monthly_df(rows)
    out = his07_ytd(df, min_ref_years=2)
    assert out[out["year"] == 2003]["comparable"].tolist() == [False, False, False]
    out = his07_ytd(df, min_ref_years=2, max_unknown_days=2)       # limite inclusivo
    assert out["comparable"].all()


def test_his07_missing_month_makes_ytd_na():
    # 2001 so tem meses 1 e 3 (falta o 2); 2002 completo
    rows = [{"year": 2001, "month": 1, "cell_days": 4}, {"year": 2001, "month": 3, "cell_days": 7}]
    rows += year_months(2002, [1, 1, 1])
    out = his07_ytd(monthly_df(rows), min_ref_years=1)
    assert ytd_rows(out) == [
        ("P", "modis", 2001, 1, 4, True, 1, 1.0, 3.0),
        ("P", "modis", 2001, 3, None, False, 1, None, None),
        ("P", "modis", 2002, 1, 1, True, 1, 4.0, -3.0),
        ("P", "modis", 2002, 2, 2, True, 0, None, None),
        ("P", "modis", 2002, 3, 3, True, 0, None, None)]
    # mes 3 de 2002 nao usa 2001 como referencia (ytd NA, nao comparavel)


def test_his07_groups_are_independent():
    rows = list(THREE_YEARS)
    rows += [{**r, "country": "Q"} for r in year_months(2001, [100, 100, 100])]
    rows += [{**r, "series": "viirs"} for r in year_months(2001, [50, 50, 50])]
    out = his07_ytd(monthly_df(rows), min_ref_years=1)
    q = out[out["country"] == "Q"]
    v = out[out["series"] == "viirs"]
    assert q["ytd_cell_days"].tolist() == [100, 200, 300] and q["n_ref_years"].tolist() == [0, 0, 0]
    assert v["ytd_cell_days"].tolist() == [50, 100, 150] and v["n_ref_years"].tolist() == [0, 0, 0]
    base = out[(out["country"] == "P") & (out["series"] == "modis")]
    assert base["n_ref_years"].tolist() == [2] * 9


def test_his07_empty_and_missing_columns():
    out = his07_ytd(monthly_df([]))
    assert list(out.columns) == YTD_COLS and len(out) == 0
    with pytest.raises(ValueError, match="partial"):
        his07_ytd(monthly_df(THREE_YEARS).drop(columns=["partial"]))


def test_his07_order_invariance():
    df = monthly_df(THREE_YEARS + [{**r, "country": "Q"} for r in year_months(2001, [9, 9, 9])])
    ref = his07_ytd(df, min_ref_years=2)
    shuffled = df.sample(frac=1, random_state=3).reset_index(drop=True)
    pd.testing.assert_frame_equal(his07_ytd(shuffled, min_ref_years=2), ref)


def test_his07_december_ytd_equals_annual_sum_and_oracle():
    """Invariante: ytd do mes 12 = soma do ano; oraculo em Python puro do pool leave-one-out."""
    rng = random.Random(42)
    rows, annual_sum, flag = [], {}, {}
    for year in range(2001, 2009):
        vals = [rng.randint(0, 20) for _ in range(12)]
        bad = rng.random() < 0.3
        bad_m = rng.randint(1, 12)
        for m, v in enumerate(vals, 1):
            rows.append({"year": year, "month": m, "cell_days": v, "partial": bad and m == bad_m})
        annual_sum[year] = sum(vals)
        flag[year] = (bad, bad_m)
    out = his07_ytd(monthly_df(rows), min_ref_years=3)
    dec = out[out["month"] == 12]
    assert dict(zip(dec["year"], dec["ytd_cell_days"])) == annual_sum
    cumulative = {(r["year"], r["month"]): 0 for r in rows}
    for r in rows:
        for m in range(r["month"], 13):
            cumulative[(r["year"], m)] += r["cell_days"]
    for row in recs(out):
        y, m = row["year"], row["month"]
        bad, bad_m = flag[y]
        assert row["ytd_cell_days"] == cumulative[(y, m)]
        assert row["comparable"] == (not (bad and bad_m <= m))
        pool = [cumulative[(o, m)] for o in range(2001, 2009)
                if o != y and not (flag[o][0] and flag[o][1] <= m)]
        assert row["n_ref_years"] == len(pool)
        if row["comparable"] and len(pool) >= 3:
            assert row["ref_ytd_mean"] == pytest.approx(sum(pool) / len(pool))
            assert row["ytd_diff"] == pytest.approx(row["ytd_cell_days"] - sum(pool) / len(pool))
        else:
            assert row["ref_ytd_mean"] is None and row["ytd_diff"] is None


# ================================================================= HIS-08
def test_his08_hand_example():
    rows = [
        {"year": 2001, "cell_days": 10},                      # sem ano anterior
        {"year": 2002, "cell_days": 15},                      # 15-10 = 5 -> 50%
        {"year": 2003, "cell_days": 0},                       # 0-15 = -15 -> -100%
        {"year": 2004, "cell_days": 5},                       # prev 0 -> diff 5, pct NA
        {"year": 2006, "cell_days": 8},                       # 2005 ausente
        {"year": 2007, "cell_days": 9, "partial": True},      # atual parcial
        {"year": 2008, "cell_days": 12},                      # anterior (2007) parcial
    ]
    out = his08_yoy(monthly_df(rows))
    assert list(out.columns) == YOY_COLS
    assert ytd_rows(out, YOY_COLS) == [
        ("P", "modis", 2001, 3, 10, None, False, None, None),
        ("P", "modis", 2002, 3, 15, 10, True, 5, 50.0),
        ("P", "modis", 2003, 3, 0, 15, True, -15, -100.0),
        ("P", "modis", 2004, 3, 5, 0, True, 5, None),
        ("P", "modis", 2006, 3, 8, None, False, None, None),
        ("P", "modis", 2007, 3, 9, 8, False, None, None),
        ("P", "modis", 2008, 3, 12, 9, False, None, None)]
    assert out["valid_pair"].dtype == bool


def test_his08_negative_and_fractional_pct():
    out = his08_yoy(monthly_df([{"year": 2001, "cell_days": 8}, {"year": 2002, "cell_days": 6}]))
    # 6-8 = -2 -> 100*(-2)/8 = -25
    assert (out.loc[1, "diff_abs"], out.loc[1, "yoy_pct"]) == (-2, -25.0)
    out = his08_yoy(monthly_df([{"year": 2001, "cell_days": 3}, {"year": 2002, "cell_days": 4}]))
    assert out.loc[1, "yoy_pct"] == pytest.approx(100 / 3)


def test_his08_unknown_days_and_months_do_not_mix():
    rows = [{"year": 2001, "month": 5, "cell_days": 10, "n_unknown_days": 1},
            {"year": 2002, "month": 5, "cell_days": 14},
            {"year": 2002, "month": 6, "cell_days": 99},                      # mes 6 de 2001 ausente
            {"year": 2002, "month": 5, "cell_days": 7, "country": "Q"},       # outro pais sem 2001
            {"year": 2002, "month": 5, "cell_days": 7, "series": "viirs"}]    # outra serie sem 2001
    df = monthly_df(rows)
    out = his08_yoy(df)
    assert out["valid_pair"].tolist() == [False] * 5
    assert out["prev_cell_days"].isna().sum() == 4          # so (P, modis, 2002, 5) tem prev (10)
    out = his08_yoy(df, max_unknown_days=1)                  # limite inclusivo
    r = {(x["country"], x["series"], x["year"], x["month"]): x for x in recs(out)}
    assert r[("P", "modis", 2002, 5)]["valid_pair"]
    assert (r[("P", "modis", 2002, 5)]["diff_abs"], r[("P", "modis", 2002, 5)]["yoy_pct"]) == (4, 40.0)
    assert r[("P", "modis", 2002, 6)]["prev_cell_days"] is None
    assert sum(1 for x in r.values() if x["valid_pair"]) == 1


def test_his08_empty_and_missing_columns():
    out = his08_yoy(monthly_df([]))
    assert list(out.columns) == YOY_COLS and len(out) == 0
    with pytest.raises(ValueError, match="cell_days"):
        his08_yoy(monthly_df(THREE_YEARS).drop(columns=["cell_days"]))


def test_his08_order_invariance():
    df = monthly_df(THREE_YEARS + [{"year": 2002, "month": 3, "cell_days": 4, "country": "Q"}])
    ref = his08_yoy(df)
    shuffled = df.sample(frac=1, random_state=5).reset_index(drop=True)
    pd.testing.assert_frame_equal(his08_yoy(shuffled), ref)


def test_his08_random_oracle():
    rng = random.Random(7)
    rows, truth = [], {}
    for year in range(2001, 2011):
        if rng.random() < 0.15:
            continue                                        # ano ausente
        v, part = rng.randint(0, 6), rng.random() < 0.2
        rows.append({"year": year, "cell_days": v, "partial": part})
        truth[year] = (v, part)
    out = his08_yoy(monthly_df(rows))
    assert len(out) == len(rows)
    for r in recs(out):
        y = r["year"]
        prev = truth.get(y - 1)
        assert r["prev_cell_days"] == (None if prev is None else prev[0])
        pair = prev is not None and not prev[1] and not truth[y][1]
        assert r["valid_pair"] == pair
        if not pair:
            assert r["diff_abs"] is None and r["yoy_pct"] is None
            continue
        assert r["diff_abs"] == truth[y][0] - prev[0]
        if prev[0] == 0:
            assert r["yoy_pct"] is None
        else:
            assert r["yoy_pct"] == pytest.approx(100 * (truth[y][0] - prev[0]) / prev[0])


# ================================================================= HIS-10
def test_his10_hand_example_three_years():
    # anos 2000, 2001, 2003 com y = 1, 5, 7; min_years=3
    # declives: (5-1)/1=4, (7-1)/3=2, (7-5)/2=1 -> ordenados 1,2,4: mediana 2
    # y - 2x = 1-4000, 5-4002, 7-4006 = -3999, -3997, -3999 -> mediana -3999
    # p2.5: posicao 0.05 -> 1 + 0.05*(2-1) = 1.05 ; p97.5: posicao 1.95 -> 2 + 0.95*(4-2) = 3.9
    df = annual_df([{"year": 2000, "cell_days": 1}, {"year": 2001, "cell_days": 5},
                    {"year": 2003, "cell_days": 7}])
    out = his10_trend(df, min_years=3)
    assert list(out.columns) == TREND_COLS
    assert len(out) == 1
    r = recs(out)[0]
    assert (r["country"], r["series"], r["n_years"], r["first_year"], r["last_year"]) == (
        "P", "modis", 3, 2000, 2003)
    assert r["slope_per_year"] == 2.0 and r["intercept"] == -3999.0
    assert r["slope_p025"] == pytest.approx(1.05) and r["slope_p975"] == pytest.approx(3.9)


def test_his10_hand_example_eight_years():
    # y = 2*(ano-2000) + ruido, ruido = 0,1,0,0,1,0,0,1  ->  y = 0,3,4,6,9,10,12,15
    # 28 declives de pares ordenados: 1,1,1.5,1.5,1.75,1.8,2 (x13),2.14286,2.2,2.25,2.25,2.5,2.5,3,3,3
    # mediana = media das posicoes 13 e 14 = 2 ; y - 2x = ruido - 4000 -> mediana (0) -> -4000
    # p2.5: posicao 0.675 entre 1 e 1 -> 1 ; p97.5: posicao 26.325 entre 3 e 3 -> 3
    df = annual_df(annual_series([0, 3, 4, 6, 9, 10, 12, 15]))
    r = recs(his10_trend(df))[0]
    assert r["n_years"] == 8 and (r["first_year"], r["last_year"]) == (2000, 2007)
    assert r["slope_per_year"] == 2.0
    assert r["intercept"] == -4000.0
    assert r["slope_p025"] == 1.0 and r["slope_p975"] == 3.0


def test_his10_exact_for_linear_data_and_constant_data():
    out = recs(his10_trend(annual_df(annual_series([3 * t + 5 for t in range(10)]))))[0]
    # y = 3*(ano-2000) + 5 = 3*ano - 5995 -> declive 3, intercepto -5995, todos os declives 3
    assert (out["slope_per_year"], out["intercept"]) == (3.0, -5995.0)
    assert (out["slope_p025"], out["slope_p975"]) == (3.0, 3.0)
    flat = recs(his10_trend(annual_df(annual_series([4] * 8))))[0]       # empates em y
    assert (flat["slope_per_year"], flat["intercept"]) == (0.0, 4.0)
    assert (flat["slope_p025"], flat["slope_p975"]) == (0.0, 0.0)
    down = recs(his10_trend(annual_df(annual_series([20 - 2 * t for t in range(8)]))))[0]
    assert (down["slope_per_year"], down["intercept"]) == (-2.0, 4020.0)   # 20 + 2*2000


def test_his10_min_years_boundary_seven_vs_eight():
    seven = recs(his10_trend(annual_df(annual_series([1, 2, 3, 4, 5, 6, 7]))))[0]
    assert (seven["n_years"], seven["first_year"], seven["last_year"]) == (7, 2000, 2006)
    assert all(seven[c] is None for c in TREND_COLS[5:])
    eight = recs(his10_trend(annual_df(annual_series([1, 2, 3, 4, 5, 6, 7, 8]))))[0]
    assert eight["n_years"] == 8 and eight["slope_per_year"] == 1.0
    # parametro: com min_years=7 os sete anos ja estimam
    assert recs(his10_trend(annual_df(annual_series([1, 2, 3, 4, 5, 6, 7])), min_years=7))[0][
        "slope_per_year"] == 1.0


def test_his10_only_valid_years_are_used():
    # 8 anos, o 2003 parcial (valor absurdo) -> 7 validos -> NA; n_years=7
    vals = [1, 2, 3, 1000, 5, 6, 7, 8]
    rows = annual_series(vals)
    rows[3]["partial"] = True
    r = recs(his10_trend(annual_df(rows)))[0]
    assert (r["n_years"], r["first_year"], r["last_year"], r["slope_per_year"]) == (7, 2000, 2007, None)
    # com min_years=7 o ano parcial e ignorado: y = ano-1999 nos restantes -> declive 1, intercepto -1999
    r = recs(his10_trend(annual_df(rows), min_years=7))[0]
    assert (r["slope_per_year"], r["intercept"]) == (1.0, -1999.0)
    # n_unknown_days acima do limite tambem invalida; limite inclusivo
    rows = annual_series(range(1, 9))
    rows[0]["n_unknown_days"] = 3
    assert recs(his10_trend(annual_df(rows)))[0]["n_years"] == 7
    assert recs(his10_trend(annual_df(rows), max_unknown_days=3))[0]["n_years"] == 8


def test_his10_no_valid_years_and_multiple_groups():
    rows = annual_series(range(1, 9), country="Q", series="viirs")
    rows += [{"country": "A", "series": "modis", "year": 2005, "cell_days": 3, "partial": True}]
    rows += annual_series([1, 4, 9, 16, 25, 36, 49, 64], country="Q", series="modis")
    out = his10_trend(annual_df(rows))
    assert [(r["country"], r["series"], r["n_years"]) for r in recs(out)] == [
        ("A", "modis", 0), ("Q", "modis", 8), ("Q", "viirs", 8)]
    a = recs(out)[0]
    assert all(a[c] is None for c in TREND_COLS[3:])
    assert recs(out)[2]["slope_per_year"] == 1.0
    # y = u^2 com u = 1..8: declive do par = u_i+u_j; as 28 somas (3..15) tem multiplicidades
    # 1,1,2,2,3,3,4,3,3,2,2,1,1; acumulado 12 em 8 e 16 em 9 -> posicoes 14 e 15 valem 9
    assert recs(out)[1]["slope_per_year"] == 9.0


def test_his10_empty_and_missing_columns():
    out = his10_trend(annual_df([]))
    assert list(out.columns) == TREND_COLS and len(out) == 0
    with pytest.raises(ValueError, match="year"):
        his10_trend(annual_df(annual_series(range(8))).drop(columns=["year"]))


def test_his10_order_invariance():
    df = annual_df(annual_series([0, 3, 4, 6, 9, 10, 12, 15])
                   + annual_series([5, 1, 7, 2, 8, 3, 9, 4], country="Q"))
    ref = his10_trend(df)
    pd.testing.assert_frame_equal(his10_trend(df.sample(frac=1, random_state=11).reset_index(drop=True)), ref)


def test_his10_random_oracle_pure_python():
    rng = random.Random(2026)
    ys = [rng.randint(0, 100) for _ in range(12)]
    years = list(range(1995, 2007))
    slopes = sorted((ys[j] - ys[i]) / (years[j] - years[i])
                    for i in range(12) for j in range(i + 1, 12))
    n = len(slopes)                                          # 66, par
    slope = (slopes[n // 2 - 1] + slopes[n // 2]) / 2
    res = sorted(y - slope * x for x, y in zip(years, ys))
    intercept = (res[5] + res[6]) / 2
    pos_lo, pos_hi = 0.025 * (n - 1), 0.975 * (n - 1)
    lo = slopes[int(pos_lo)] + (pos_lo % 1) * (slopes[int(pos_lo) + 1] - slopes[int(pos_lo)])
    hi = slopes[int(pos_hi)] + (pos_hi % 1) * (slopes[int(pos_hi) + 1] - slopes[int(pos_hi)])
    r = recs(his10_trend(annual_df(annual_series(ys, first_year=1995))))[0]
    assert r["slope_per_year"] == pytest.approx(slope)
    assert r["intercept"] == pytest.approx(intercept)
    assert r["slope_p025"] == pytest.approx(lo) and r["slope_p975"] == pytest.approx(hi)


def test_his10_matches_scipy_theilslopes_slope():
    stats = pytest.importorskip("scipy.stats")
    rng = random.Random(99)
    ys = [rng.randint(0, 500) for _ in range(15)]
    r = recs(his10_trend(annual_df(annual_series(ys))))[0]
    expected = stats.theilslopes(ys, list(range(2000, 2015)))[0]
    assert r["slope_per_year"] == pytest.approx(expected)


# ------------------------------------------------ guardas de entrada (revisao independente)
def test_monthly_metrics_reject_duplicate_keys_instead_of_dropping_rows():
    dup = monthly_df([{"year": 2003, "month": 2, "cell_days": 10}, {"year": 2003, "month": 2, "cell_days": 99},
                      {"year": 2003, "month": 1, "cell_days": 1}])
    for fn in (his07_ytd, his08_yoy):
        with pytest.raises(ValueError, match="repetida"):
            fn(dup)


def test_monthly_metrics_reject_missing_cell_days_with_a_clear_message():
    na = monthly_df([{"year": 2001}, {"year": 2002}, {"year": 2003}])
    na["cell_days"] = pd.array([1, pd.NA, 3], dtype="Int64")
    for fn in (his07_ytd, his08_yoy):
        with pytest.raises(ValueError, match="cell_days"):
            fn(na)


def test_trend_rejects_repeated_years_and_missing_values():
    rep = annual_df(annual_series(range(8)) + [{"year": 2003, "cell_days": 999}])
    with pytest.raises(ValueError, match="repetida"):
        his10_trend(rep)
    same_year = annual_df([{"year": 2000, "cell_days": v} for v in range(9)])      # antes: IndexError
    with pytest.raises(ValueError, match="repetida"):
        his10_trend(same_year)
    na = annual_df(annual_series(range(9)))
    na["cell_days"] = pd.array([0, pd.NA, 2, 3, 4, 5, 6, 7, 8], dtype="Int64")
    with pytest.raises(ValueError, match="cell_days"):
        his10_trend(na)

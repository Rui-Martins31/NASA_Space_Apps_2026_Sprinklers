"""Testes das metricas de distribuicao historica do Lote 4: HIS-01, HIS-02, HIS-05, HIS-06, HIS-09.

Exemplo trabalhado (spec 7B): mes 3, anos 2001..2006, valores 10..60.
- fixa: n=6, mediana 35, p10 = 15 (posicao 0,5), p90 = 55 (posicao 4,5);
- sem 2003: pool [10,20,40,50,60], media 36, var amostral 1720/4 = 430;
- sem 2001: pool [20..60], media 40, var = 1000/4 = 250; sem 2006: pool [10..50], media 30, var 250.
"""
import math
import random
import statistics

import pandas as pd
import pytest

from helpers_lote4 import monthly_df, recs, series_rows
from metrics.history_distribution import (
    HIS01_COLUMNS, HIS02_COLUMNS, HIS05_COLUMNS, HIS06_COLUMNS, HIS09_COLUMNS,
    his01_hist_median, his02_hist_band, his05_zscore, his06_percentile, his09_months_above,
)

SIX = [10, 20, 30, 40, 50, 60]
METRICS = [(his01_hist_median, HIS01_COLUMNS), (his02_hist_band, HIS02_COLUMNS),
           (his05_zscore, HIS05_COLUMNS), (his06_percentile, HIS06_COLUMNS),
           (his09_months_above, HIS09_COLUMNS)]
IDS = ["his01", "his02", "his05", "his06", "his09"]


def six(**extra):
    return monthly_df(series_rows(SIX, **extra))


def row_of(df, **key):
    sel = df
    for k, v in key.items():
        sel = sel[sel[k] == v]
    assert len(sel) == 1
    return recs(sel)[0]


# ------------------------------------------------------------------ comuns
def test_column_constants():
    assert HIS01_COLUMNS == ["country", "series", "month", "n_ref_years", "median_cell_days"]
    assert HIS02_COLUMNS == ["country", "series", "month", "n_ref_years", "p10", "p90"]
    assert HIS05_COLUMNS == ["country", "series", "year", "month", "cell_days", "valid_month",
                             "n_ref_years", "ref_mean", "ref_std", "zscore"]
    assert HIS06_COLUMNS == ["country", "series", "year", "month", "cell_days", "valid_month",
                             "n_ref_years", "percentile"]
    assert HIS09_COLUMNS == ["country", "series", "year", "n_months_evaluated",
                             "n_months_above", "months_above"]


@pytest.mark.parametrize("fn,cols", METRICS, ids=IDS)
def test_empty_input_gives_empty_table_with_columns(fn, cols):
    out = fn(monthly_df([]))
    assert list(out.columns) == cols
    assert len(out) == 0


@pytest.mark.parametrize("fn,cols", METRICS, ids=IDS)
def test_missing_column_raises(fn, cols):
    with pytest.raises(ValueError):
        fn(six().drop(columns=["n_unknown_days"]))


@pytest.mark.parametrize("fn,cols", METRICS, ids=IDS)
def test_output_columns_sorted_and_index_reset(fn, cols):
    rows = (series_rows(SIX, country="Z", series="viirs") + series_rows(SIX, country="A")
            + series_rows(SIX, month=4, country="A", series="combined"))
    out = fn(monthly_df(rows).iloc[::-1])
    assert list(out.columns) == cols
    keys = [c for c in ["country", "series", "year", "month"] if c in cols]
    assert out[keys].values.tolist() == sorted(out[keys].values.tolist())
    assert list(out.index) == list(range(len(out)))


@pytest.mark.parametrize("fn,cols", METRICS, ids=IDS)
def test_row_order_invariance(fn, cols):
    rng = random.Random(7)
    rows = (series_rows([3, 8, 8, 1, 9, 4, 7], country="B") + series_rows(SIX, month=5)
            + series_rows([0, 0, 5, 0, 0, 2], month=5, series="viirs"))
    rows[2]["partial"] = True
    base = monthly_df(rows)
    expected = fn(base)
    for _ in range(3):
        shuffled = base.sample(frac=1.0, random_state=rng.randint(0, 10_000)).reset_index(drop=True)
        pd.testing.assert_frame_equal(fn(shuffled), expected)


# ------------------------------------------------------------------ HIS-01
def test_his01_hand_example():
    out = his01_hist_median(six())
    assert len(out) == 12                                   # sempre os 12 meses do par
    assert row_of(out, month=3) == {"country": "P", "series": "modis", "month": 3,
                                    "n_ref_years": 6, "median_cell_days": 35.0}
    assert row_of(out, month=4) == {"country": "P", "series": "modis", "month": 4,
                                    "n_ref_years": 0, "median_cell_days": None}


def test_his01_even_and_odd_pool():
    out = his01_hist_median(monthly_df(series_rows([5, 1, 9, 3, 7])))       # impar: 5
    assert row_of(out, month=3)["median_cell_days"] == 5.0
    out = his01_hist_median(monthly_df(series_rows([5, 1, 9, 3, 7, 100])))   # par: (5+7)/2
    assert row_of(out, month=3)["median_cell_days"] == 6.0


def test_his01_na_below_min_ref_years():
    df = monthly_df(series_rows([10, 20, 30, 40]))
    r = row_of(his01_hist_median(df), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (4, None)
    r = row_of(his01_hist_median(df, min_ref_years=4), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (4, 25.0)


def test_his01_exactly_min_ref_years_is_defined():
    r = row_of(his01_hist_median(monthly_df(series_rows([1, 2, 3, 4, 100]))), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (5, 3.0)


def test_his01_excludes_invalid_months_from_pool():
    rows = series_rows(SIX)
    rows[0]["partial"] = True                # 10 fora
    rows[5]["n_unknown_days"] = 1            # 60 fora
    r = row_of(his01_hist_median(monthly_df(rows), min_ref_years=4), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (4, 35.0)      # [20,30,40,50]
    r = row_of(his01_hist_median(monthly_df(rows), min_ref_years=4, max_unknown_days=1), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (5, 40.0)      # [20,30,40,50,60]


def test_his01_reference_window_inclusive():
    r = row_of(his01_hist_median(six(), ref_start=2003, ref_end=2006, min_ref_years=4), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (4, 45.0)      # [30,40,50,60]
    r = row_of(his01_hist_median(six(), ref_start=2002, ref_end=2005, min_ref_years=4), month=3)
    assert (r["n_ref_years"], r["median_cell_days"]) == (4, 35.0)      # [20,30,40,50]


def test_his01_pairs_are_independent():
    rows = series_rows(SIX, country="A") + series_rows([0, 0, 0, 0, 0, 7], country="B", series="viirs")
    out = his01_hist_median(monthly_df(rows))
    assert row_of(out, country="A", month=3)["median_cell_days"] == 35.0
    assert row_of(out, country="B", month=3)["median_cell_days"] == 0.0


# ------------------------------------------------------------------ HIS-02
def test_his02_hand_example():
    out = his02_hist_band(six())
    assert len(out) == 12
    assert row_of(out, month=3) == {"country": "P", "series": "modis", "month": 3,
                                    "n_ref_years": 6, "p10": 15.0, "p90": 55.0}
    assert row_of(out, month=9) == {"country": "P", "series": "modis", "month": 9,
                                    "n_ref_years": 0, "p10": None, "p90": None}


def test_his02_na_below_min_and_param():
    df = monthly_df(series_rows([10, 20, 30, 40]))
    assert row_of(his02_hist_band(df), month=3) == {
        "country": "P", "series": "modis", "month": 3, "n_ref_years": 4, "p10": None, "p90": None}
    r = row_of(his02_hist_band(df, min_ref_years=4), month=3)       # posicoes 0,3 e 2,7
    assert (r["p10"], r["p90"]) == (pytest.approx(13.0), pytest.approx(37.0))


def test_his02_reference_window_and_invalid():
    r = row_of(his02_hist_band(six(), ref_start=2003, min_ref_years=4), month=3)   # [30,40,50,60]
    assert (r["n_ref_years"], r["p10"], r["p90"]) == (4, pytest.approx(33.0), pytest.approx(57.0))
    rows = series_rows(SIX)
    rows[5]["partial"] = True
    r = row_of(his02_hist_band(monthly_df(rows)), month=3)           # [10..50]
    assert (r["n_ref_years"], r["p10"], r["p90"]) == (5, pytest.approx(14.0), pytest.approx(46.0))


# ------------------------------------------------------------------ HIS-05
def test_his05_hand_example():
    out = his05_zscore(six())
    assert len(out) == 6
    r = row_of(out, year=2003)
    assert r["country"] == "P" and r["series"] == "modis" and r["month"] == 3
    assert (r["cell_days"], r["valid_month"], r["n_ref_years"], r["ref_mean"]) == (30, True, 5, 36.0)
    assert r["ref_std"] == pytest.approx(math.sqrt(430), rel=1e-12)
    assert r["zscore"] == pytest.approx(-0.2893456933022473, rel=1e-12)
    assert row_of(out, year=2001)["zscore"] == pytest.approx(-1.8973665961010275, rel=1e-12)
    r6 = row_of(out, year=2006)
    assert r6["ref_mean"] == 30.0
    assert r6["zscore"] == pytest.approx(1.8973665961010275, rel=1e-12)
    assert r6["ref_std"] == pytest.approx(math.sqrt(250), rel=1e-12)


def test_his05_na_below_min_ref_years():
    df = monthly_df(series_rows([10, 20, 30, 40, 50]))                  # LOO: so 4 anos
    out = his05_zscore(df)
    assert out["n_ref_years"].tolist() == [4] * 5
    assert out["zscore"].isna().all() and out["ref_mean"].isna().all() and out["ref_std"].isna().all()
    assert his05_zscore(df, min_ref_years=4)["zscore"].notna().all()


def test_his05_zero_std_is_na():
    out = his05_zscore(monthly_df(series_rows([5, 5, 5, 5, 5, 5])))
    assert out["ref_std"].tolist() == [0.0] * 6
    assert out["ref_mean"].tolist() == [5.0] * 6
    assert out["zscore"].isna().all()
    out = his05_zscore(monthly_df(series_rows([5, 5, 5, 5, 5, 9])))
    assert row_of(out, year=2006)["zscore"] is None             # pool tudo 5: std 0
    assert row_of(out, year=2006)["ref_std"] == 0.0
    # 2001: pool [5,5,5,5,9], media 5,8, var = (4*0,64 + 10,24)/4 = 3,2
    assert row_of(out, year=2001)["zscore"] == pytest.approx(-0.4472135954999579, rel=1e-12)


def test_his05_invalid_month_is_na_but_keeps_pool_stats():
    rows = series_rows(SIX)
    rows[2]["partial"] = True                                  # 2003 (30) parcial
    out = his05_zscore(monthly_df(rows), min_ref_years=4)
    r = row_of(out, year=2003)
    assert (r["valid_month"], r["n_ref_years"], r["zscore"]) == (False, 5, None)
    assert r["ref_mean"] == 36.0
    r = row_of(out, year=2001)          # 2003 fora do pool: [20,40,50,60], media 42,5, soma dq 875
    assert (r["valid_month"], r["n_ref_years"], r["ref_mean"]) == (True, 4, 42.5)
    assert r["zscore"] == pytest.approx(-32.5 / math.sqrt(875 / 3), rel=1e-12)


def test_his05_unknown_days_threshold():
    rows = series_rows(SIX)
    rows[2]["n_unknown_days"] = 2
    assert row_of(his05_zscore(monthly_df(rows), min_ref_years=4), year=2003)["valid_month"] is False
    assert row_of(his05_zscore(monthly_df(rows), min_ref_years=4, max_unknown_days=2),
                  year=2003)["valid_month"] is True


def test_his05_reference_window_and_row_outside_window():
    # janela 2002..2005 = [20,30,40,50]; 2006 (fora da janela) usa o pool inteiro da janela
    out = his05_zscore(six(), ref_start=2002, ref_end=2005, min_ref_years=4)
    r = row_of(out, year=2006)
    assert (r["n_ref_years"], r["ref_mean"]) == (4, 35.0)
    assert r["zscore"] == pytest.approx(1.9364916731037085, rel=1e-12)    # 25/sqrt(500/3)
    r = row_of(out, year=2002)           # dentro da janela: sem 2002 -> [30,40,50] (3 anos)
    assert (r["n_ref_years"], r["zscore"]) == (3, None)


# ------------------------------------------------------------------ HIS-06
def test_his06_hand_example():
    out = his06_percentile(six())
    assert len(out) == 6
    assert out["percentile"].tolist() == [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    r = row_of(out, year=2003)
    assert r == {"country": "P", "series": "modis", "year": 2003, "month": 3, "cell_days": 30,
                 "valid_month": True, "n_ref_years": 5, "percentile": 40.0}


def test_his06_ties_count_half():
    out = his06_percentile(monthly_df(series_rows([10, 20, 20, 20, 30, 40])))
    # 2002: pool [10,20,20,30,40], abaixo 1, iguais 2 -> 100*(1+1)/5 = 40
    assert row_of(out, year=2002)["percentile"] == 40.0
    # 2001: pool [20,20,20,30,40], abaixo 0, iguais 0 -> 0
    assert row_of(out, year=2001)["percentile"] == 0.0
    # tudo igual: 100*(0 + 0,5*5)/5 = 50
    out = his06_percentile(monthly_df(series_rows([7] * 6)))
    assert out["percentile"].tolist() == [50.0] * 6


def test_his06_na_cases():
    out = his06_percentile(monthly_df(series_rows([10, 20, 30, 40, 50])))     # LOO: 4 anos
    assert out["percentile"].isna().all() and (out["n_ref_years"] == 4).all()
    rows = series_rows(SIX)
    rows[2]["partial"] = True
    out = his06_percentile(monthly_df(rows), min_ref_years=4)
    r = row_of(out, year=2003)
    assert (r["valid_month"], r["n_ref_years"], r["percentile"]) == (False, 5, None)
    r = row_of(out, year=2006)           # pool [10,20,40,50]; abaixo 4 -> 100
    assert (r["n_ref_years"], r["percentile"]) == (4, 100.0)


def test_his06_reference_window():
    out = his06_percentile(six(), ref_start=2002, ref_end=2005, min_ref_years=4)
    assert row_of(out, year=2006)["percentile"] == 100.0           # pool [20,30,40,50]
    assert row_of(out, year=2001)["percentile"] == 0.0
    assert row_of(out, year=2002)["percentile"] is None            # pool so 3 anos
    assert row_of(out, year=2004)["n_ref_years"] == 3


# ------------------------------------------------------------------ HIS-09
def test_his09_hand_example():
    rows = series_rows(SIX, month=3) + series_rows([1, 1, 1, 1, 1, 9], month=4)
    out = his09_months_above(monthly_df(rows))
    # p90: mes 3 = 55; mes 4 = (1+9)/2 = 5
    base = {"country": "P", "series": "modis", "n_months_evaluated": 2,
            "n_months_above": 0, "months_above": ""}
    expected = [{**base, "year": y} for y in range(2001, 2006)]
    expected.append({**base, "year": 2006, "n_months_above": 2, "months_above": "3,4"})
    assert recs(out) == [{k: e[k] for k in out.columns} for e in expected]
    assert out["n_months_above"].dtype.kind == "i" and out["n_months_evaluated"].dtype.kind == "i"


def test_his09_months_text_ascending_regardless_of_row_order():
    rows = series_rows(SIX, month=9) + series_rows(SIX, month=2) + series_rows(SIX, month=11)
    out = his09_months_above(monthly_df(rows).iloc[::-1].reset_index(drop=True))
    assert row_of(out, year=2006)["months_above"] == "2,9,11"
    assert row_of(out, year=2006)["n_months_above"] == 3
    assert row_of(out, year=2001)["months_above"] == ""


def test_his09_equal_to_p90_is_not_above():
    out = his09_months_above(monthly_df(series_rows([10, 20, 30, 40, 50, 50])))   # p90 = 50
    assert out["n_months_above"].tolist() == [0] * 6
    assert out["months_above"].tolist() == [""] * 6
    out = his09_months_above(monthly_df(series_rows([10, 20, 30, 40, 50, 51])))   # p90 = 50,5
    assert out["n_months_above"].tolist() == [0, 0, 0, 0, 0, 1]


def test_his09_month_without_defined_p90_is_not_evaluated():
    rows = series_rows([10, 20, 30, 40], month=3)            # so 4 anos: p90 NA
    rows += series_rows([0, 0, 0, 0, 0, 5], month=4)         # 6 anos: p90 = 2,5
    out = his09_months_above(monthly_df(rows))
    assert row_of(out, year=2006) == {
        "country": "P", "series": "modis", "year": 2006, "n_months_evaluated": 1,
        "n_months_above": 1, "months_above": "4"}
    r = row_of(out, year=2001)
    assert (r["n_months_evaluated"], r["n_months_above"], r["months_above"]) == (1, 0, "")


def test_his09_year_with_zero_evaluated_months_still_has_row():
    rows = series_rows(SIX)
    rows[5]["partial"] = True                               # 2006 invalido
    rows += [{"year": 2010, "cell_days": 99}]               # 2010 valido: pool [10..50,99]
    out = his09_months_above(monthly_df(rows))
    r = row_of(out, year=2006)
    assert (r["n_months_evaluated"], r["n_months_above"], r["months_above"]) == (0, 0, "")
    r = row_of(out, year=2010)
    assert (r["n_months_evaluated"], r["n_months_above"], r["months_above"]) == (1, 1, "3")
    assert len(out) == 7
    short = his09_months_above(monthly_df(series_rows([1, 2, 3])))     # sem p90 em lado nenhum
    assert short["n_months_evaluated"].tolist() == [0, 0, 0]
    assert short["months_above"].tolist() == ["", "", ""]


def test_his09_invalid_month_not_counted_even_if_high():
    rows = series_rows(SIX)
    rows[5] = {**rows[5], "cell_days": 500, "n_unknown_days": 3}      # 2006 alto mas invalido
    out = his09_months_above(monthly_df(rows), min_ref_years=4)
    r = row_of(out, year=2006)
    assert (r["n_months_evaluated"], r["n_months_above"], r["months_above"]) == (0, 0, "")


def test_his09_reference_is_fixed_even_if_year_inside_window():
    # pool inteiro [10..50,51]: p90 = 50,5. 2005 (50) nao esta acima; com leave-one-out
    # (pool sem 2005: p90 = 46,6) estaria acima.
    out = his09_months_above(monthly_df(series_rows([10, 20, 30, 40, 50, 51])))
    assert row_of(out, year=2005)["n_months_above"] == 0
    assert row_of(out, year=2006)["n_months_above"] == 1


def test_his09_reference_window_applies_to_pool_not_to_evaluated_years():
    # janela 2001..2005 -> pool [10..50], p90 = 46; 2006 = 60 fora da janela e ainda avaliado
    out = his09_months_above(six(), ref_start=2001, ref_end=2005)
    assert out["year"].tolist() == [2001, 2002, 2003, 2004, 2005, 2006]
    assert out["n_months_above"].tolist() == [0, 0, 0, 0, 1, 1]       # 50 > 46 e 60 > 46
    assert row_of(out, year=2005)["months_above"] == "3"
    out = his09_months_above(six(), ref_start=2002, ref_end=2005, min_ref_years=4)   # [20..50]: 47
    assert out["n_months_above"].tolist() == [0, 0, 0, 0, 1, 1]
    out = his09_months_above(six(), ref_start=2002, ref_end=2005)    # 4 anos < 5: p90 NA
    assert out["n_months_evaluated"].tolist() == [0] * 6


def test_his09_groups_by_country_and_series():
    rows = series_rows(SIX, country="A") + series_rows([0, 0, 0, 0, 0, 3], country="B", series="viirs")
    out = his09_months_above(monthly_df(rows))
    assert out[["country", "series", "year"]].values.tolist() == (
        [["A", "modis", y] for y in range(2001, 2007)] + [["B", "viirs", y] for y in range(2001, 2007)])
    assert out["n_months_above"].tolist() == [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1]


# ------------------------------------------------------------------ oraculo independente
def _random_monthly(seed):
    rng = random.Random(seed)
    rows = []
    for country in ("A", "B"):
        for series in ("modis", "combined"):
            for month in (1, 6, 12):
                for year in range(2000, 2016):
                    if rng.random() < 0.1:
                        continue
                    rows.append({"country": country, "series": series, "year": year,
                                 "month": month, "cell_days": rng.choice([0, 1, 2, 5, 5, 9, 17, 30]),
                                 "partial": rng.random() < 0.1,
                                 "n_unknown_days": rng.choice([0, 0, 0, 0, 3])})
    rng.shuffle(rows)
    return rows


def _oracle_pools(rows, ref_start, ref_end):
    """Pools por (country, series, month) em Python puro: {chave: {ano: valor}}."""
    pools = {}
    for r in rows:
        if r["partial"] or r["n_unknown_days"] > 0:
            continue
        if not (ref_start <= r["year"] <= ref_end):
            continue
        pools.setdefault((r["country"], r["series"], r["month"]), {})[r["year"]] = r["cell_days"]
    return pools


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_oracle_matches_pure_python(seed):
    ref_start, ref_end, min_n = 2003, 2012, 5
    rows = _random_monthly(seed)
    df = monthly_df(rows)
    pools = _oracle_pools(rows, ref_start, ref_end)

    med = {(r["country"], r["series"], r["month"]): r
           for r in recs(his01_hist_median(df, ref_start, ref_end))}
    band = {(r["country"], r["series"], r["month"]): r
            for r in recs(his02_hist_band(df, ref_start, ref_end))}
    assert len(med) == len(band) == 4 * 12
    for key, row in med.items():
        vals = list(pools.get(key, {}).values())
        assert row["n_ref_years"] == len(vals) == band[key]["n_ref_years"]
        if len(vals) >= min_n:
            assert row["median_cell_days"] == statistics.median(vals)
            q = statistics.quantiles(vals, n=10, method="inclusive")
            assert band[key]["p10"] == pytest.approx(q[0], abs=1e-9)
            assert band[key]["p90"] == pytest.approx(q[8], abs=1e-9)
        else:
            assert row["median_cell_days"] is None
            assert band[key]["p10"] is None and band[key]["p90"] is None

    z = his05_zscore(df, ref_start, ref_end)
    p = his06_percentile(df, ref_start, ref_end)
    assert len(z) == len(p) == len(rows)
    zmap = {(r["country"], r["series"], r["year"], r["month"]): r for r in recs(z)}
    pmap = {(r["country"], r["series"], r["year"], r["month"]): r for r in recs(p)}
    n_defined = 0
    for r in rows:
        k = (r["country"], r["series"], r["year"], r["month"])
        valid = (not r["partial"]) and r["n_unknown_days"] == 0
        pool = [v for y, v in pools.get((r["country"], r["series"], r["month"]), {}).items()
                if y != r["year"]]
        assert zmap[k]["valid_month"] == valid == pmap[k]["valid_month"]
        assert zmap[k]["n_ref_years"] == len(pool) == pmap[k]["n_ref_years"]
        if len(pool) < min_n or not valid:
            assert zmap[k]["zscore"] is None and pmap[k]["percentile"] is None
            continue
        n_defined += 1
        exp_pct = 100 * (sum(v < r["cell_days"] for v in pool)
                         + 0.5 * sum(v == r["cell_days"] for v in pool)) / len(pool)
        assert pmap[k]["percentile"] == pytest.approx(exp_pct, abs=1e-9)
        sd = statistics.stdev(pool)
        if sd == 0:
            assert zmap[k]["zscore"] is None
        else:
            assert zmap[k]["zscore"] == pytest.approx(
                (r["cell_days"] - statistics.mean(pool)) / sd, abs=1e-9)
    assert n_defined > 50

    exp = {}
    for r in rows:
        e = exp.setdefault((r["country"], r["series"], r["year"]), [0, []])
        valid = (not r["partial"]) and r["n_unknown_days"] == 0
        vals = list(pools.get((r["country"], r["series"], r["month"]), {}).values())
        if valid and len(vals) >= min_n:
            e[0] += 1
            if r["cell_days"] > statistics.quantiles(vals, n=10, method="inclusive")[8]:
                e[1].append(r["month"])
    a = his09_months_above(df, ref_start, ref_end)
    assert len(a) == len(exp)
    assert sum(len(v[1]) for v in exp.values()) > 0
    for row in recs(a):
        n_ev, above = exp[(row["country"], row["series"], row["year"])]
        assert row["n_months_evaluated"] == n_ev
        assert row["n_months_above"] == len(above)
        assert row["months_above"] == ",".join(str(m) for m in sorted(above))


def test_percentile_invariants():
    df = monthly_df(series_rows([3, 8, 8, 1, 9, 4, 7, 2]))
    pct = his06_percentile(df)["percentile"]
    assert ((pct >= 0) & (pct <= 100)).all()
    # valores distintos: soma dos percentis LOO de n=6 anos = 0+20+40+60+80+100
    d = his06_percentile(monthly_df(series_rows([1, 2, 3, 4, 5, 6])))
    assert d["percentile"].sum() == 300.0


# ------------------------------------------------ guardas de entrada (revisao independente)
def test_his09_rejects_duplicate_keys_and_does_not_depend_on_loo_columns():
    dup = monthly_df(series_rows([10, 20, 30, 40, 50, 60]) + [{"year": 2003, "cell_days": 99}])
    with pytest.raises(ValueError, match="repetida"):
        his09_months_above(dup)
    # 2007 (valor 1000) e valido e muito acima do p90 dos 6 anos anteriores -> 1 mes acima
    rows = series_rows([10, 20, 30, 40, 50, 60, 1000])
    got = recs(his09_months_above(monthly_df(rows), min_ref_years=5))
    assert got[-1]["year"] == 2007 and got[-1]["n_months_above"] == 1 and got[-1]["months_above"] == "3"

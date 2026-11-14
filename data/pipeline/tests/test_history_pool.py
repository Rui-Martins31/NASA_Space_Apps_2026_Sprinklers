"""Testes do pool de referencia historico (Lote 4). Valores esperados calculados a mao."""
import random
import statistics

import pandas as pd
import pytest

from helpers_lote4 import monthly_df, recs, series_rows
from metrics.history_pool import (
    MAX_UNKNOWN_DAYS, MIN_REF_YEARS, reference_fixed, reference_loo, valid_mask,
)

SIX = [10, 20, 30, 40, 50, 60]          # mes 3, anos 2001..2006 (exemplo trabalhado da secao 7B)


def test_constants_are_frozen():
    assert (MAX_UNKNOWN_DAYS, MIN_REF_YEARS) == (0, 5)


# --------------------------------------------------------------------- valid_mask
def test_valid_mask_truth_table():
    t = pd.DataFrame({"partial": [False, True, False, True, False],
                      "n_unknown_days": [0, 0, 1, 3, 2]})
    assert valid_mask(t).tolist() == [True, False, False, False, False]
    assert valid_mask(t, max_unknown_days=1).tolist() == [True, False, True, False, False]
    assert valid_mask(t, max_unknown_days=2).tolist() == [True, False, True, False, True]


# ------------------------------------------------------------------ reference_fixed
def test_fixed_worked_example():
    out = reference_fixed(monthly_df(series_rows(SIX)))
    row = [r for r in recs(out) if r["month"] == 3][0]
    assert row["n_ref_years"] == 6
    assert row["ref_mean"] == 35.0 and row["ref_median"] == 35.0
    assert row["ref_std"] == pytest.approx(18.708286933869708)       # sqrt(1750/5), ddof=1
    assert row["ref_p10"] == 15.0 and row["ref_p90"] == 55.0         # interpolacao linear


def test_fixed_has_twelve_months_per_country_series_with_empty_months_na():
    out = reference_fixed(monthly_df(series_rows(SIX)))
    assert list(out.columns) == ["country", "series", "month", "n_ref_years", "ref_mean",
                                 "ref_std", "ref_median", "ref_p10", "ref_p90"]
    assert out["month"].tolist() == list(range(1, 13))
    jan = recs(out)[0]
    assert jan["n_ref_years"] == 0 and jan["ref_mean"] is None and jan["ref_p90"] is None


def test_fixed_excludes_invalid_months():
    rows = series_rows([10, 20, 30, 40, 50, 60, 70])
    rows[2].update(partial=True, cell_days=999)             # 2003 parcial
    rows[4].update(n_unknown_days=1, cell_days=888)         # 2005 com dia desconhecido
    row = [r for r in recs(reference_fixed(monthly_df(rows), min_ref_years=4)) if r["month"] == 3][0]
    assert row["n_ref_years"] == 5                          # 10, 20, 40, 60, 70
    assert row["ref_mean"] == 40.0
    with_tolerance = reference_fixed(monthly_df(rows), min_ref_years=4, max_unknown_days=1)
    assert [r for r in recs(with_tolerance) if r["month"] == 3][0]["n_ref_years"] == 6


def test_fixed_is_na_below_min_ref_years_but_reports_n():
    row = [r for r in recs(reference_fixed(monthly_df(series_rows([10, 20, 30, 40])))) if r["month"] == 3][0]
    assert row["n_ref_years"] == 4
    assert all(row[c] is None for c in ("ref_mean", "ref_std", "ref_median", "ref_p10", "ref_p90"))


def test_fixed_reference_window_is_inclusive():
    kw = dict(min_ref_years=4)
    row = [r for r in recs(reference_fixed(monthly_df(series_rows(SIX)), ref_start=2002, ref_end=2005, **kw))
           if r["month"] == 3][0]
    assert row["n_ref_years"] == 4 and row["ref_mean"] == 35.0      # 20, 30, 40, 50
    only_start = [r for r in recs(reference_fixed(monthly_df(series_rows(SIX)), ref_start=2005, **kw))
                  if r["month"] == 3][0]
    assert only_start["n_ref_years"] == 2 and only_start["ref_mean"] is None


def test_fixed_groups_are_independent():
    rows = (series_rows(SIX) + series_rows([1, 1, 1, 1, 1], country="Q") +
            series_rows([100, 200, 300, 400, 500], series="viirs"))
    out = reference_fixed(monthly_df(rows))
    pick = {(r["country"], r["series"]): r for r in recs(out) if r["month"] == 3}
    assert pick[("P", "modis")]["ref_mean"] == 35.0
    assert pick[("Q", "modis")]["ref_mean"] == 1.0 and pick[("Q", "modis")]["ref_std"] == 0.0
    assert pick[("P", "viirs")]["ref_mean"] == 300.0


# -------------------------------------------------------------------- reference_loo
def test_loo_worked_example():
    out = reference_loo(monthly_df(series_rows(SIX)))
    assert list(out.columns) == ["country", "series", "year", "month", "cell_days", "valid_month",
                                 "n_ref_years", "ref_mean", "ref_std", "n_below", "n_equal"]
    got = recs(out)
    assert [r["n_ref_years"] for r in got] == [5] * 6
    assert [r["ref_mean"] for r in got] == [40.0, 38.0, 36.0, 34.0, 32.0, 30.0]
    assert got[2]["ref_std"] == pytest.approx(20.736441353327718)    # outros: 10, 20, 40, 50, 60
    assert [r["n_below"] for r in got] == [0, 1, 2, 3, 4, 5]
    assert [r["n_equal"] for r in got] == [0] * 6


def test_loo_anomalies_sum_to_zero():
    out = reference_loo(monthly_df(series_rows(SIX)))
    assert (out["cell_days"] - out["ref_mean"]).sum() == pytest.approx(0.0, abs=1e-9)


def test_loo_counts_ties():
    # valores 10, 20, 20, 20, 30, 40; para um ano com valor 20 os outros sao 10, 20, 20, 30, 40
    out = reference_loo(monthly_df(series_rows([10, 20, 20, 20, 30, 40])))
    got = recs(out)
    assert (got[1]["n_below"], got[1]["n_equal"]) == (1, 2)
    assert (got[0]["n_below"], got[0]["n_equal"]) == (0, 0)
    assert (got[5]["n_below"], got[5]["n_equal"]) == (5, 0)


def test_loo_invalid_evaluated_row_keeps_pool_stats_but_no_position():
    rows = series_rows([10, 20, 30, 40, 50, 60, 70])
    rows[3].update(partial=True, cell_days=999)             # 2004 parcial: nao entra no pool
    got = recs(reference_loo(monthly_df(rows)))
    bad = got[3]
    assert bad["valid_month"] is False
    assert bad["n_ref_years"] == 6 and bad["ref_mean"] == 40.0     # (10+20+30+50+60+70)/6
    assert bad["n_below"] is None and bad["n_equal"] is None
    assert got[0]["n_ref_years"] == 5                                # nao conta o proprio nem o parcial


def test_loo_na_when_pool_too_small_after_removing_own_year():
    got = recs(reference_loo(monthly_df(series_rows([10, 20, 30, 40, 50]))))    # 5 anos: sem o proprio, 4
    assert all(r["n_ref_years"] == 4 and r["ref_mean"] is None and r["n_below"] is None for r in got)
    assert recs(reference_loo(monthly_df(series_rows([10, 20, 30, 40, 50])), min_ref_years=4))[0]["ref_mean"] == 35.0


def test_loo_reference_window_rows_outside_window_use_whole_pool():
    got = recs(reference_loo(monthly_df(series_rows(SIX)), ref_start=2002, ref_end=2005, min_ref_years=3))
    by_year = {r["year"]: r for r in got}
    assert by_year[2001]["n_ref_years"] == 4 and by_year[2001]["ref_mean"] == 35.0      # fora da janela
    assert by_year[2006]["n_ref_years"] == 4 and by_year[2006]["ref_mean"] == 35.0
    assert by_year[2003]["n_ref_years"] == 3
    assert by_year[2003]["ref_mean"] == pytest.approx((20 + 40 + 50) / 3)               # dentro da janela, sem si


def test_loo_months_and_groups_are_independent():
    rows = series_rows(SIX) + series_rows([5, 5, 5, 5, 5, 5], month=4) + series_rows(SIX, country="Q")
    got = recs(reference_loo(monthly_df(rows)))
    assert [r["ref_mean"] for r in got if r["month"] == 4] == [5.0] * 6
    assert [r["ref_mean"] for r in got if r["country"] == "Q"] == [40.0, 38.0, 36.0, 34.0, 32.0, 30.0]


# --------------------------------------------------- vazio, esquema, ordem, oraculo
def test_empty_and_missing_columns():
    empty = monthly_df([])
    assert len(reference_fixed(empty)) == 0 and len(reference_loo(empty)) == 0
    assert list(reference_loo(empty).columns)[:3] == ["country", "series", "year"]
    with pytest.raises(ValueError, match="partial"):
        reference_loo(monthly_df(series_rows(SIX)).drop(columns=["partial"]))
    with pytest.raises(ValueError, match="n_unknown_days"):
        reference_fixed(monthly_df(series_rows(SIX)).drop(columns=["n_unknown_days"]))


def test_order_of_rows_does_not_matter():
    df = monthly_df(series_rows(SIX) + series_rows(SIX, country="Q"))
    shuffled = df.sample(frac=1.0, random_state=9).reset_index(drop=True)
    for fn in (reference_loo, reference_fixed):
        pd.testing.assert_frame_equal(fn(df), fn(shuffled), check_dtype=False)


def _linear_percentile(sorted_vals, p):
    pos = (len(sorted_vals) - 1) * p / 100
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def test_matches_pure_python_oracle_on_random_world():
    rng = random.Random(77)
    rows = []
    for country in ("P", "Q"):
        for series in ("modis", "viirs"):
            for month in (1, 2, 3):
                for year in range(2001, 2021):
                    rows.append({"country": country, "series": series, "month": month, "year": year,
                                 "cell_days": rng.randint(0, 200),
                                 "partial": rng.random() < 0.1, "n_unknown_days": rng.choice([0, 0, 0, 2])})
    df = monthly_df(rows)
    valid = {(r["country"], r["series"], r["month"], r["year"]): r["cell_days"]
             for r in rows if not r["partial"] and r["n_unknown_days"] == 0}
    # fixa
    for r in recs(reference_fixed(df)):
        vals = sorted(v for (c, s, m, y), v in valid.items() if (c, s, m) == (r["country"], r["series"], r["month"]))
        assert r["n_ref_years"] == len(vals)
        if len(vals) >= 5:
            assert r["ref_mean"] == pytest.approx(statistics.mean(vals))
            assert r["ref_std"] == pytest.approx(statistics.stdev(vals))
            assert r["ref_median"] == pytest.approx(statistics.median(vals))
            assert r["ref_p10"] == pytest.approx(_linear_percentile(vals, 10))
            assert r["ref_p90"] == pytest.approx(_linear_percentile(vals, 90))
        else:
            assert r["ref_mean"] is None
    # leave-one-out
    for r in recs(reference_loo(df)):
        key = (r["country"], r["series"], r["month"])
        others = [v for (c, s, m, y), v in valid.items() if (c, s, m) == key and y != r["year"]]
        assert r["n_ref_years"] == len(others)
        if len(others) >= 5:
            assert r["ref_mean"] == pytest.approx(statistics.mean(others))
            assert r["ref_std"] == pytest.approx(statistics.stdev(others))
            if r["valid_month"]:
                assert r["n_below"] == sum(v < r["cell_days"] for v in others)
                assert r["n_equal"] == sum(v == r["cell_days"] for v in others)
        else:
            assert r["ref_mean"] is None


# ------------------------------------------------ guardas de entrada (revisao independente)
def test_duplicate_keys_raise_instead_of_inflating_the_pool():
    dup = monthly_df(series_rows(SIX) + [{"year": 2003, "cell_days": 99}])      # 2003 repetido
    for fn in (reference_fixed, reference_loo):
        with pytest.raises(ValueError, match="repetida"):
            fn(dup)


def test_require_no_na_names_the_columns():
    from metrics.history_pool import require_no_na
    df = monthly_df(series_rows(SIX))
    df["cell_days"] = pd.array([1, pd.NA, 3, 4, 5, 6], dtype="Int64")
    with pytest.raises(ValueError, match=r"\['cell_days'\]"):
        require_no_na(df, ["cell_days", "year"])
    require_no_na(df, ["year", "month"])                                      # sem falta: nao levanta


def test_category_dtype_keys_give_same_result_and_no_future_warning():
    import warnings
    df = monthly_df(series_rows(SIX) + series_rows(SIX, country="Q"))
    cat = df.astype({"country": "category", "series": "category"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")                                        # FutureWarning vira erro
        loo, fixed = reference_loo(cat), reference_fixed(cat)
    pd.testing.assert_frame_equal(loo.astype({"country": "object", "series": "object"}),
                                  reference_loo(df).astype({"country": "object", "series": "object"}), check_dtype=False)
    assert len(fixed) == 24

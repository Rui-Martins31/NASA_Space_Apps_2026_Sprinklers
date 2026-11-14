"""Testes das metricas de calendario do Lote 1: CAL-01/02 (diaria), CAL-03 (mensal), CAL-04 (anual).

Celulas de 0.1 graus: A = (10.05, 20.05) e B = (10.15, 20.05) estao em celulas distintas.
Valores esperados calculados a mao (ver comentarios em cada fixture).
"""
import random
from fractions import Fraction

import pandas as pd
import pytest

from helpers_lote1 import build_processed as make_df
from metrics.calendar_metrics import (
    cal_annual, cal_coverage, cal_daily, cal_monthly, eligible_cell_days, global_day_counts,
)

A = {"latitude": 10.05, "longitude": 20.05}
B = {"latitude": 10.15, "longitude": 20.05}
V = {"instrument": "VIIRS", "satellite": "N20"}
T = pd.Timestamp


def recs(df):
    return [{c: (None if pd.isna(r[c]) else r[c]) for c in df.columns} for r in df.to_dict("records")]


# --------------------------------------------------------------- eligible_cell_days
def test_eligible_cell_days_filters_and_dedups():
    df = make_df([
        {**A, "acq_date": "2020-01-30"},                                 # ok
        {**A, "acq_date": "2020-01-30"},                                 # duplicada exata -> 1
        {**A, "acq_date": "2020-01-30", "satellite": "Aqua"},            # outro satelite -> linha propria
        {**A, "acq_date": "2020-02-03", "confidence_class": "l"},        # nao elegivel
        {**A, "acq_date": "2020-02-03", "type": 2},                      # nao elegivel
        {"latitude": float("nan"), "longitude": 1.0, "acq_date": "2020-02-03"},   # coord invalida
        {**A, "acq_date": "2020-02-31"},                                 # data invalida
    ])
    out = eligible_cell_days(df)
    assert list(out.columns) == ["country", "date", "cell", "instrument", "satellite"]
    assert [(r["satellite"], r["date"]) for r in recs(out)] == [
        ("Aqua", T("2020-01-30")), ("Terra", T("2020-01-30"))]
    assert out["cell"].nunique() == 1


# --------------------------------------------------------------------- cal_daily
# MODIS Terra A 01-30 ; MODIS Aqua A 01-30 (mesma celula-dia noutro satelite) ; MODIS Terra B 02-01
# VIIRS A 02-01 ; VIIRS B 02-01 ; MODIS A 02-03 com confianca baixa (ignorada)
# modis : 01-30 -> {A} = 1 ; 02-01 -> {B} = 1
# viirs : 02-01 -> {A, B} = 2
# combined: 01-30 -> 1 ; 02-01 -> {B} U {A, B} = 2   (e nao 3: a uniao conta uma vez)
@pytest.fixture
def day_rows():
    return make_df([
        {**A, "acq_date": "2020-01-30"},
        {**A, "acq_date": "2020-01-30", "satellite": "Aqua"},
        {**B, "acq_date": "2020-02-01"},
        {**A, "acq_date": "2020-02-01", **V},
        {**B, "acq_date": "2020-02-01", **V},
        {**A, "acq_date": "2020-02-03", "confidence_class": "l"},
    ])


def test_cal_daily_manual_union_counts_once(day_rows):
    out = cal_daily(eligible_cell_days(day_rows))
    assert list(out.columns) == ["country", "date", "series", "n_cells"]
    assert recs(out) == [
        dict(country="Testland", date=T("2020-01-30"), series="combined", n_cells=1),
        dict(country="Testland", date=T("2020-01-30"), series="modis", n_cells=1),
        dict(country="Testland", date=T("2020-02-01"), series="combined", n_cells=2),
        dict(country="Testland", date=T("2020-02-01"), series="modis", n_cells=1),
        dict(country="Testland", date=T("2020-02-01"), series="viirs", n_cells=2),
    ]


def test_cal_daily_combined_bounds(day_rows):
    out = cal_daily(eligible_cell_days(day_rows))
    wide = out.pivot_table(index=["country", "date"], columns="series", values="n_cells").fillna(0)
    assert (wide["combined"] <= wide["modis"] + wide["viirs"]).all()
    assert (wide["combined"] >= wide[["modis", "viirs"]].max(axis=1)).all()


def test_cal_daily_empty_and_unknown_instrument(day_rows):
    empty = cal_daily(eligible_cell_days(make_df([])))
    assert len(empty) == 0 and list(empty.columns) == ["country", "date", "series", "n_cells"]
    bad = eligible_cell_days(day_rows).assign(instrument="AVHRR")
    with pytest.raises(ValueError):
        cal_daily(bad)


# ----------------------------------------------------- global_day_counts / cal_coverage
def test_global_day_counts_uses_all_rows_with_valid_date(day_rows):
    out = global_day_counts(day_rows)
    assert list(out.columns) == ["instrument", "date", "n_rows_global"]
    assert [(r["instrument"], r["date"], r["n_rows_global"]) for r in recs(out)] == [
        ("MODIS", T("2020-01-30"), 2), ("MODIS", T("2020-02-01"), 1), ("MODIS", T("2020-02-03"), 1),
        ("VIIRS", T("2020-02-01"), 2)]       # inclui a linha nao elegivel de 02-03


@pytest.fixture
def day_counts():
    # MODIS: 01-30 (5), 02-01 (3), 02-03 (2) ; VIIRS: 02-01 (4), 02-02 (1)
    rows = [("MODIS", "2020-01-30", 5), ("MODIS", "2020-02-01", 3), ("MODIS", "2020-02-03", 2),
            ("VIIRS", "2020-02-01", 4), ("VIIRS", "2020-02-02", 1)]
    return pd.DataFrame(rows, columns=["instrument", "date", "n_rows_global"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))


def test_cal_coverage_fills_gaps_with_zero(day_counts):
    out = cal_coverage(day_counts)
    assert [(r["instrument"], r["date"], r["n_rows_global"]) for r in recs(out)] == [
        ("MODIS", T("2020-01-30"), 5), ("MODIS", T("2020-01-31"), 0), ("MODIS", T("2020-02-01"), 3),
        ("MODIS", T("2020-02-02"), 0), ("MODIS", T("2020-02-03"), 2),
        ("VIIRS", T("2020-02-01"), 4), ("VIIRS", T("2020-02-02"), 1)]


def test_cal_coverage_sums_duplicate_days_from_several_files(day_counts):
    twice = pd.concat([day_counts, day_counts.iloc[[0]]], ignore_index=True)
    assert cal_coverage(twice).iloc[0]["n_rows_global"] == 10


# --------------------------------------------------------------------- cal_monthly
# Intervalos: modis 01-30..02-03 ; viirs 02-01..02-02 ; combined 01-30..02-03.
# Dias sem deteccao global: modis 01-31 e 02-02 ; viirs nenhum ;
# combined (soma dos sensores por dia): 01-31 = 0 -> desconhecido ; 02-02 = 0 + 1 = 1 -> conhecido.
@pytest.fixture
def cov(day_counts):
    return cal_coverage(day_counts)


@pytest.fixture
def daily(day_rows):
    return cal_daily(eligible_cell_days(day_rows))


def test_cal_monthly_manual_dense_with_partial_and_unknown(daily, cov):
    out = cal_monthly(daily, cov, countries=["Testland", "Zeroland"])
    assert list(out.columns) == ["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
    got = [(r["country"], r["year"], r["month"], r["series"], r["cell_days"], r["partial"], r["n_unknown_days"])
           for r in recs(out)]
    assert got == [
        ("Testland", 2020, 1, "combined", 1, True, 1),
        ("Testland", 2020, 1, "modis", 1, True, 1),
        ("Testland", 2020, 2, "combined", 2, True, 0),
        ("Testland", 2020, 2, "modis", 1, True, 1),
        ("Testland", 2020, 2, "viirs", 2, True, 0),
        ("Zeroland", 2020, 1, "combined", 0, True, 1),     # pais sem atividade aparece com 0
        ("Zeroland", 2020, 1, "modis", 0, True, 1),
        ("Zeroland", 2020, 2, "combined", 0, True, 0),
        ("Zeroland", 2020, 2, "modis", 0, True, 1),
        ("Zeroland", 2020, 2, "viirs", 0, True, 0),
    ]                                                      # viirs nao tem janeiro (fora do intervalo)


def _long_cov():
    """MODIS de 2019-12-01 a 2021-01-31 (so os extremos tem deteccoes; o resto e 0)."""
    return cal_coverage(pd.DataFrame(
        [("MODIS", "2019-12-01", 1), ("MODIS", "2021-01-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))


def _long_daily():
    return pd.DataFrame(
        [("P", "2020-02-29", "modis", 3), ("P", "2020-06-15", "modis", 2)],
        columns=["country", "date", "series", "n_cells"]).assign(date=lambda d: pd.to_datetime(d["date"]))


def test_cal_monthly_full_months_are_not_partial_and_leap_year():
    out = cal_monthly(_long_daily(), _long_cov(), countries=["P"])
    out = out[out["series"] == "modis"]                     # a fixture so tem a serie modis
    m = {(r["year"], r["month"]): r for r in recs(out)}
    assert len(out) == 14                                   # 2019-12 .. 2021-01
    assert m[(2019, 12)]["partial"] is False                # comeca no dia 1
    assert m[(2021, 1)]["partial"] is False                 # termina exatamente no dia 31
    assert m[(2020, 2)]["cell_days"] == 3
    assert m[(2020, 2)]["n_unknown_days"] == 29             # bissexto: 29 dias, todos sem deteccao global
    assert m[(2020, 6)]["cell_days"] == 2 and m[(2020, 7)]["cell_days"] == 0
    assert m[(2020, 3)]["n_unknown_days"] == 31


def test_cal_monthly_month_starting_one_day_late_is_partial():
    cov2 = cal_coverage(pd.DataFrame(
        [("MODIS", "2020-01-02", 1), ("MODIS", "2020-01-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))
    out = cal_monthly(_long_daily().iloc[0:0], cov2, countries=["P"])
    assert recs(out)[0]["partial"] is True


def test_cal_monthly_empty_inputs():
    out = cal_monthly(_long_daily().iloc[0:0], cal_coverage(_long_cov().iloc[0:0]), countries=[])
    assert len(out) == 0
    assert list(out.columns) == ["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]


# --------------------------------------------------------------------- cal_annual
def test_cal_annual_manual():
    monthly = cal_monthly(_long_daily(), _long_cov(), countries=["P"])
    out = cal_annual(monthly)
    out = out[out["series"] == "modis"]
    assert list(out.columns) == ["country", "year", "series", "cell_days", "partial", "n_unknown_days"]
    assert [(r["year"], r["cell_days"], r["partial"]) for r in recs(out)] == [
        (2019, 0, True),       # so dezembro (1 mes)
        (2020, 5, False),      # 12 meses completos: 3 + 2
        (2021, 0, True)]       # so janeiro (1 mes)
    assert recs(out)[1]["n_unknown_days"] == 366           # 2020 inteiro (bissexto) sem deteccoes globais


def test_cal_annual_is_partial_if_any_month_is_partial():
    cov2 = cal_coverage(pd.DataFrame(
        [("MODIS", "2020-01-02", 1), ("MODIS", "2020-12-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))
    out = cal_annual(cal_monthly(_long_daily().iloc[0:0], cov2, countries=["P"]))
    assert recs(out)[0]["partial"] is True                 # 12 meses presentes mas janeiro e parcial


# ------------------------------------------------- invariantes e oraculo independente
def _random_world(seed=11):
    rng = random.Random(seed)
    rows = []
    for _ in range(500):
        inst = rng.choice(["MODIS", "VIIRS"])
        rows.append({
            "country": rng.choice(["P", "Q"]), "instrument": inst,
            "satellite": rng.choice(["Terra", "Aqua"]) if inst == "MODIS" else "N20",
            "latitude": rng.choice([10.05, 10.15, -33.35]), "longitude": rng.choice([20.05, -70.45]),
            "acq_date": rng.choice(["2019-12-31", "2020-01-01", "2020-02-29", "2020-03-01", "2021-01-15"]),
            "type": rng.choice([0, 0, 2]), "confidence_class": rng.choice(["l", "n", "h", "h"]),
        })
    return rows, make_df(rows)


def _cell(lat, lon):
    g = Fraction(1, 10)
    return int((Fraction(str(lat)) + 90) // g), int((Fraction(str(lon)) + 180) // g)


def test_daily_matches_independent_set_oracle():
    rows, df = _random_world()
    exp = {}
    for r in rows:
        if r["type"] == 0 and r["confidence_class"] in ("n", "h"):
            cell = _cell(r["latitude"], r["longitude"])
            for s in (r["instrument"].lower(), "combined"):
                exp.setdefault((r["country"], r["acq_date"], s), set()).add(cell)
    got = {(r["country"], r["date"].strftime("%Y-%m-%d"), r["series"]): r["n_cells"]
           for r in recs(cal_daily(eligible_cell_days(df)))}
    assert got == {k: len(v) for k, v in exp.items()}


def test_totals_are_consistent_across_daily_monthly_annual():
    rows, df = _random_world()
    daily = cal_daily(eligible_cell_days(df))
    cov = cal_coverage(global_day_counts(df))
    countries = sorted(df["country"].unique())
    monthly = cal_monthly(daily, cov, countries)
    annual = cal_annual(monthly)
    for s in ("modis", "viirs", "combined"):
        d = daily.loc[daily["series"] == s, "n_cells"].sum()
        assert monthly.loc[monthly["series"] == s, "cell_days"].sum() == d
        assert annual.loc[annual["series"] == s, "cell_days"].sum() == d
    assert monthly.groupby("series")["n_unknown_days"].sum().to_dict() == \
        annual.groupby("series")["n_unknown_days"].sum().to_dict()
    # a serie combinada nunca excede a soma dos sensores nem fica abaixo do maior
    w = monthly.pivot_table(index=["country", "year", "month"], columns="series", values="cell_days").fillna(0)
    assert (w["combined"] <= w["modis"] + w["viirs"]).all()
    assert (w["combined"] >= w[["modis", "viirs"]].max(axis=1)).all()


def test_order_of_rows_does_not_matter():
    _, df = _random_world()
    shuffled = df.sample(frac=1.0, random_state=5).reset_index(drop=True)
    for fn in (lambda d: cal_daily(eligible_cell_days(d)), global_day_counts):
        a, b = fn(df), fn(shuffled)
        pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=False)


def test_cal_monthly_rejects_activity_outside_coverage_range(cov):
    bad = pd.DataFrame([("Testland", "2019-12-31", "modis", 1)],
                       columns=["country", "date", "series", "n_cells"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))
    with pytest.raises(ValueError, match="fora do intervalo"):
        cal_monthly(bad, cov, countries=["Testland"])


def test_cal_monthly_rejects_unknown_instrument_in_coverage(cov, daily):
    with pytest.raises(ValueError, match="AVHRR"):
        cal_monthly(daily, cov.assign(instrument="AVHRR"), countries=["Testland"])


def test_global_day_counts_ignores_invalid_dates_and_normalizes_instrument_case():
    df = make_df([{"acq_date": "2020-01-30"}, {"acq_date": "2020-02-31"}, {"acq_date": "lixo"},
                  {"acq_date": "2020-01-30", "instrument": "modis"}])
    out = global_day_counts(df)
    assert [(r["instrument"], r["date"], r["n_rows_global"]) for r in recs(out)] == [
        ("MODIS", T("2020-01-30"), 2)]        # 2 validas (MODIS e modis juntos); as 2 invalidas ficam fora

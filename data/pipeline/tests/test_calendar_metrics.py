"""Testes das metricas de calendario do Lote 1 por celula: CAL-01/02 (diaria), CAL-03 (mensal), CAL-04 (anual).

Celulas de 0.1 graus: A = (10.05, 20.05) e B = (10.15, 20.05) estao em celulas distintas.
Valores esperados calculados a mao (ver comentarios em cada fixture). `densify_*` tem de reproduzir o
`cal_monthly`/`cal_annual` DENSOS antigos (por pais): a referencia antiga esta reimplementada aqui
(`old_cal_monthly`/`old_cal_annual`) com `country = str(cell)`.
"""
import random
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from helpers_lote1 import build_processed as make_df
from metrics.calendar_metrics import (
    _series_ranges, active_cells, cal_annual, cal_coverage, cal_daily, cal_monthly, coarsen_cell_days,
    densify_annual, densify_monthly, eligible_cell_days, global_day_counts, month_validity,
    year_validity,
)
from metrics.common import cell_key, cell_to_ids

A = {"latitude": 10.05, "longitude": 20.05}
B = {"latitude": 10.15, "longitude": 20.05}
V = {"instrument": "VIIRS", "satellite": "N20"}
CA = int(cell_key([10.05], [20.05])[0])
CB = int(cell_key([10.15], [20.05])[0])
CZ = 7                      # celula sem atividade (so serve para testar zeros)
T = pd.Timestamp


def recs(df):
    return [{c: (None if pd.isna(r[c]) else r[c]) for c in df.columns} for r in df.to_dict("records")]


# ----------------------------------------------------------- referencia ANTIGA (por pais, densa)
def old_cal_monthly(daily, coverage, countries=None):
    """Copia do cal_monthly antigo (`country`, `n_cells`); a referencia de equivalencia."""
    cols = ["country", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
    if countries is None:
        countries = sorted(daily["country"].unique())
    countries = list(countries)
    parts = []
    for series, (first, last, unknown) in _series_ranges(coverage).items():
        d = daily[daily["series"] == series]
        if len(d) and (d["date"].min() < first or d["date"].max() > last):
            raise ValueError("fora do intervalo")
        months = pd.period_range(first, last, freq="M")
        if not countries:
            continue
        idx = pd.MultiIndex.from_product([countries, months], names=["country", "period"])
        frame = idx.to_frame(index=False)
        sums = d.groupby(["country", d["date"].dt.to_period("M")])["n_cells"].sum()
        sums.index = sums.index.set_names(["country", "period"])
        frame["cell_days"] = sums.reindex(idx, fill_value=0).to_numpy().astype("int64")
        unk = pd.Series(unknown.to_period("M")).value_counts()
        frame["n_unknown_days"] = frame["period"].map(unk).fillna(0).astype("int64")
        starts = frame["period"].map(lambda p: p.start_time)
        ends = frame["period"].map(lambda p: p.end_time.normalize())
        frame["partial"] = ~((starts >= first) & (ends <= last))
        frame["year"] = frame["period"].map(lambda p: p.year).astype("int64")
        frame["month"] = frame["period"].map(lambda p: p.month).astype("int64")
        frame["series"] = series
        parts.append(frame[cols])
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["country", "year", "month", "series"]).reset_index(drop=True)


def old_cal_annual(monthly):
    g = monthly.groupby(["country", "year", "series"], observed=True)
    out = g.agg(cell_days=("cell_days", "sum"), n_months=("month", "count"),
                any_partial=("partial", "any"), n_unknown_days=("n_unknown_days", "sum")).reset_index()
    out["partial"] = out["any_partial"] | (out["n_months"] < 12)
    out["cell_days"] = out["cell_days"].astype("int64")
    out["n_unknown_days"] = out["n_unknown_days"].astype("int64")
    return out[["country", "year", "series", "cell_days", "partial", "n_unknown_days"]].sort_values(
        ["country", "year", "series"]).reset_index(drop=True)


def old_daily_from_cell_days(cell_days):
    """Esquema antigo (country=str(cell), n_cells por dia/serie) a partir das celulas-dia."""
    parts = []
    inst = cell_days["instrument"].astype("string").str.upper()
    for series, sub in {"modis": cell_days[inst == "MODIS"], "viirs": cell_days[inst == "VIIRS"],
                        "combined": cell_days}.items():
        g = sub.drop_duplicates(["cell", "date"]).assign(country=lambda d: d["cell"].astype(str))
        g = g.groupby(["country", "date"]).size().rename("n_cells").reset_index()
        g["series"] = series
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def old_to_cell(frame):
    """Converte o `country` (= str(cell)) da referencia antiga em `cell` int64 e ordena como o novo."""
    out = frame.copy()
    out.insert(0, "cell", out.pop("country").astype("int64"))
    keys = [c for c in ("cell", "year", "month", "series") if c in out.columns]
    return out.sort_values(keys).reset_index(drop=True)


# --------------------------------------------------------------- eligible_cell_days
def test_eligible_cell_days_filters_and_dedups():
    df = make_df([
        {**A, "acq_date": "2020-01-30"},                                 # ok
        {**A, "acq_date": "2020-01-30"},                                 # duplicada exata -> 1
        {**A, "acq_date": "2020-01-30", "country": "Outro"},             # outro pais, mesma celula-dia -> 1
        {**A, "acq_date": "2020-01-30", "satellite": "Aqua"},            # outro satelite -> linha propria
        {**A, "acq_date": "2020-02-03", "confidence_class": "l"},        # nao elegivel
        {**A, "acq_date": "2020-02-03", "type": 2},                      # nao elegivel
        {"latitude": float("nan"), "longitude": 1.0, "acq_date": "2020-02-03"},   # coord invalida
        {**A, "acq_date": "2020-02-31"},                                 # data invalida
    ])
    out = eligible_cell_days(df)
    assert list(out.columns) == ["date", "cell", "instrument", "satellite"]
    assert out["cell"].dtype == "int64"
    assert [(r["satellite"], r["date"], r["cell"]) for r in recs(out)] == [
        ("Aqua", T("2020-01-30"), CA), ("Terra", T("2020-01-30"), CA)]


def test_eligible_cell_days_grid_deg_and_empty():
    df = make_df([{"latitude": 10.05, "longitude": 20.05, "acq_date": "2020-01-30"},
                  {"latitude": 10.051, "longitude": 20.054, "acq_date": "2020-01-30"},
                  {"latitude": 10.06, "longitude": 20.05, "acq_date": "2020-01-30"}])
    assert len(eligible_cell_days(df)) == 1                       # 0.1: tudo na mesma celula
    fine = eligible_cell_days(df, grid_deg=0.01)
    assert fine["cell"].tolist() == sorted(cell_key([10.05, 10.06], [20.05, 20.05], 0.01).tolist())
    empty = eligible_cell_days(make_df([]))
    assert len(empty) == 0 and list(empty.columns) == ["date", "cell", "instrument", "satellite"]


# --------------------------------------------------------------------- cal_daily
# MODIS Terra A 01-30 ; MODIS Aqua A 01-30 (mesma celula-dia noutro satelite) ; MODIS Terra B 02-01
# VIIRS A 02-01 ; VIIRS B 02-01 ; MODIS A 02-03 com confianca baixa (ignorada)
# celula A: 01-30 so modis ; 02-01 so viirs        celula B: 02-01 modis E viirs
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


def test_cal_daily_manual_flags(day_rows):
    out = cal_daily(eligible_cell_days(day_rows))
    assert list(out.columns) == ["cell", "date", "in_modis", "in_viirs"]
    assert out["in_modis"].dtype == bool and out["in_viirs"].dtype == bool
    assert recs(out) == [
        dict(cell=CA, date=T("2020-01-30"), in_modis=True, in_viirs=False),
        dict(cell=CA, date=T("2020-02-01"), in_modis=False, in_viirs=True),
        dict(cell=CB, date=T("2020-02-01"), in_modis=True, in_viirs=True),     # uniao: 1 linha, nao 2
    ]


def test_cal_daily_one_row_per_cell_day_and_never_all_false(day_rows):
    out = cal_daily(eligible_cell_days(day_rows))
    assert not out.duplicated(["cell", "date"]).any()
    assert (out["in_modis"] | out["in_viirs"]).all()


def test_cal_daily_empty_and_unknown_instrument(day_rows):
    empty = cal_daily(eligible_cell_days(make_df([])))
    assert len(empty) == 0 and list(empty.columns) == ["cell", "date", "in_modis", "in_viirs"]
    bad = eligible_cell_days(day_rows).assign(instrument="AVHRR")
    with pytest.raises(ValueError, match="AVHRR"):
        cal_daily(bad)
    with pytest.raises(ValueError, match="cell"):
        cal_daily(eligible_cell_days(day_rows).drop(columns=["cell"]))


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


# ------------------------------------------------- validade (igual para todas as celulas)
# Intervalos: modis 01-30..02-03 ; viirs 02-01..02-02 ; combined 01-30..02-03.
# Dias sem deteccao global: modis 01-31 e 02-02 ; viirs nenhum ;
# combined (soma dos sensores por dia): 01-31 = 0 -> desconhecido ; 02-02 = 0 + 1 = 1 -> conhecido.
@pytest.fixture
def cov(day_counts):
    return cal_coverage(day_counts)


@pytest.fixture
def cdays(day_rows):
    return eligible_cell_days(day_rows)


def test_month_validity_manual(cov):
    out = month_validity(cov)
    assert list(out.columns) == ["series", "year", "month", "partial", "n_unknown_days"]
    assert [(r["series"], r["year"], r["month"], r["partial"], r["n_unknown_days"]) for r in recs(out)] == [
        ("combined", 2020, 1, True, 1), ("combined", 2020, 2, True, 0),
        ("modis", 2020, 1, True, 1), ("modis", 2020, 2, True, 1),
        ("viirs", 2020, 2, True, 0)]                         # viirs nao tem janeiro (fora do intervalo)


def test_year_validity_manual(cov):
    out = year_validity(month_validity(cov))
    assert list(out.columns) == ["series", "year", "partial", "n_unknown_days"]
    assert [(r["series"], r["year"], r["partial"], r["n_unknown_days"]) for r in recs(out)] == [
        ("combined", 2020, True, 1), ("modis", 2020, True, 2), ("viirs", 2020, True, 0)]


def _long_cov():
    """MODIS de 2019-12-01 a 2021-01-31 (so os extremos tem deteccoes; o resto e 0)."""
    return cal_coverage(pd.DataFrame(
        [("MODIS", "2019-12-01", 1), ("MODIS", "2021-01-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))


def _long_cell_days():
    """Duas celulas-dia MODIS: a de CA em 2020-02-29 (bissexto) e a de CB em 2020-06-15."""
    return pd.DataFrame(
        [("2020-02-29", CA, "MODIS", "Terra"), ("2020-06-15", CB, "MODIS", "Terra")],
        columns=["date", "cell", "instrument", "satellite"]).assign(date=lambda d: pd.to_datetime(d["date"]))


def test_month_validity_full_months_are_not_partial_and_leap_year():
    out = month_validity(_long_cov())
    m = {(r["year"], r["month"]): r for r in recs(out)}
    assert out.groupby("series").size().to_dict() == {"combined": 14, "modis": 14}     # 2019-12 .. 2021-01
    assert m[(2019, 12)]["partial"] is False                # comeca no dia 1
    assert m[(2021, 1)]["partial"] is False                 # termina exatamente no dia 31
    assert m[(2020, 2)]["n_unknown_days"] == 29             # bissexto: 29 dias, todos sem deteccao global
    assert m[(2020, 3)]["n_unknown_days"] == 31


def test_month_validity_month_starting_one_day_late_is_partial():
    cov2 = cal_coverage(pd.DataFrame(
        [("MODIS", "2020-01-02", 1), ("MODIS", "2020-01-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))
    assert recs(month_validity(cov2))[0]["partial"] is True


def test_year_validity_partial_if_any_month_partial_or_missing_months():
    out = year_validity(month_validity(_long_cov()))
    out = out[out["series"] == "modis"]
    assert [(r["year"], r["partial"], r["n_unknown_days"]) for r in recs(out)] == [
        (2019, True, 30),       # so dezembro (1 mes); 31 dias menos o dia 1 com detecao
        (2020, False, 366),     # 12 meses completos; ano bissexto sem deteccoes globais
        (2021, True, 30)]       # so janeiro: 31 dias menos o dia 31 com deteccao
    cov2 = cal_coverage(pd.DataFrame(
        [("MODIS", "2020-01-02", 1), ("MODIS", "2020-12-31", 1)],
        columns=["instrument", "date", "n_rows_global"]).assign(date=lambda d: pd.to_datetime(d["date"])))
    assert recs(year_validity(month_validity(cov2)))[0]["partial"] is True   # 12 meses mas janeiro parcial


def test_validity_empty_and_errors():
    empty_cov = cal_coverage(_long_cov().iloc[0:0])
    assert len(month_validity(empty_cov)) == 0
    assert list(month_validity(empty_cov).columns) == ["series", "year", "month", "partial", "n_unknown_days"]
    assert len(year_validity(month_validity(empty_cov))) == 0
    with pytest.raises(ValueError, match="AVHRR"):
        month_validity(_long_cov().assign(instrument="AVHRR"))
    with pytest.raises(ValueError, match="month"):
        year_validity(month_validity(_long_cov()).drop(columns=["month"]))


# --------------------------------------------------------------------- cal_monthly (esparso)
# celula A: modis 01 (01-30) ; viirs 02 (02-01) ; combined 01 (1) e 02 (1)
# celula B: modis 02 (02-01) ; viirs 02 (02-01) ; combined 02 = 1 (a uniao conta a celula-dia uma vez)
def test_cal_monthly_manual_sparse_and_union(cdays, cov):
    out = cal_monthly(cdays, cov)
    assert list(out.columns) == ["cell", "year", "month", "series", "cell_days"]
    assert [(r["cell"], r["year"], r["month"], r["series"], r["cell_days"]) for r in recs(out)] == [
        (CA, 2020, 1, "combined", 1), (CA, 2020, 1, "modis", 1),
        (CA, 2020, 2, "combined", 1), (CA, 2020, 2, "viirs", 1),
        (CB, 2020, 2, "combined", 1), (CB, 2020, 2, "modis", 1), (CB, 2020, 2, "viirs", 1)]
    assert (out["cell_days"] > 0).all()                    # esparso: nunca linhas a 0


def test_cal_monthly_counts_distinct_days_per_month_and_sums_satellites_once():
    cd = pd.DataFrame(
        [("2020-01-30", CA, "MODIS", "Terra"), ("2020-01-30", CA, "MODIS", "Aqua"),
         ("2020-01-31", CA, "MODIS", "Aqua"), ("2020-01-31", CA, "VIIRS", "N20")],
        columns=["date", "cell", "instrument", "satellite"]).assign(date=lambda d: pd.to_datetime(d["date"]))
    cov2 = cal_coverage(pd.DataFrame(
        [("MODIS", "2020-01-30", 1), ("MODIS", "2020-01-31", 1), ("VIIRS", "2020-01-30", 1),
         ("VIIRS", "2020-01-31", 1)], columns=["instrument", "date", "n_rows_global"]).assign(
        date=lambda d: pd.to_datetime(d["date"])))
    out = cal_monthly(cd, cov2)
    assert {r["series"]: r["cell_days"] for r in recs(out)} == {"modis": 2, "viirs": 1, "combined": 2}


def test_cal_monthly_empty_inputs():
    out = cal_monthly(_long_cell_days().iloc[0:0], _long_cov())
    assert len(out) == 0
    assert list(out.columns) == ["cell", "year", "month", "series", "cell_days"]
    out = cal_monthly(_long_cell_days().iloc[0:0], cal_coverage(_long_cov().iloc[0:0]))
    assert len(out) == 0


def test_cal_monthly_rejects_activity_outside_coverage_range(cov):
    bad = pd.DataFrame([("2019-12-31", CA, "MODIS", "Terra")],
                       columns=["date", "cell", "instrument", "satellite"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))
    with pytest.raises(ValueError, match="fora do intervalo"):
        cal_monthly(bad, cov)
    late = bad.assign(date=pd.Timestamp("2020-02-04"))
    with pytest.raises(ValueError, match="fora do intervalo"):
        cal_monthly(late, cov)
    # VIIRS em 01-31 esta fora do intervalo do viirs (02-01..02-02) mesmo estando dentro do combined
    viirs_early = bad.assign(date=pd.Timestamp("2020-01-31"), instrument="VIIRS")
    with pytest.raises(ValueError, match="viirs"):
        cal_monthly(viirs_early, cov)


def test_cal_monthly_rejects_series_without_coverage_and_empty_coverage():
    only_modis = _long_cov()
    viirs = _long_cell_days().assign(instrument="VIIRS")
    with pytest.raises(ValueError, match="viirs"):
        cal_monthly(viirs, only_modis)
    with pytest.raises(ValueError, match="cobertura"):
        cal_monthly(_long_cell_days(), cal_coverage(_long_cov().iloc[0:0]))


def test_cal_monthly_rejects_unknown_instrument(cdays, cov):
    with pytest.raises(ValueError, match="AVHRR"):
        cal_monthly(cdays, cov.assign(instrument="AVHRR"))
    with pytest.raises(ValueError, match="AVHRR"):
        cal_monthly(cdays.assign(instrument="AVHRR"), cov)


def test_cal_annual_manual_and_sparse():
    monthly = cal_monthly(_long_cell_days(), _long_cov())
    out = cal_annual(monthly)
    assert list(out.columns) == ["cell", "year", "series", "cell_days"]
    assert [(r["cell"], r["year"], r["series"], r["cell_days"]) for r in recs(out)] == [
        (CA, 2020, "combined", 1), (CA, 2020, "modis", 1),
        (CB, 2020, "combined", 1), (CB, 2020, "modis", 1)]
    assert len(cal_annual(monthly.iloc[0:0])) == 0
    assert list(cal_annual(monthly.iloc[0:0]).columns) == ["cell", "year", "series", "cell_days"]


# --------------------------------------------------------------------- densify
def test_densify_monthly_manual_zeros_flags_and_requested_cells_only(cdays, cov):
    sparse = cal_monthly(cdays, cov)
    validity = month_validity(cov)
    out = densify_monthly(sparse, validity, cells=[CB, CZ, CA])         # ordem dada nao importa
    assert list(out.columns) == ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
    assert len(out) == 3 * len(validity)                                # so as 3 celulas pedidas
    assert set(out["cell"]) == {CA, CB, CZ}
    z = out[out["cell"] == CZ]
    assert (z["cell_days"] == 0).all() and z["partial"].all()
    assert [(r["year"], r["month"], r["series"], r["cell_days"], r["partial"], r["n_unknown_days"])
            for r in recs(out[out["cell"] == CA])] == [
        (2020, 1, "combined", 1, True, 1), (2020, 1, "modis", 1, True, 1),
        (2020, 2, "combined", 1, True, 0), (2020, 2, "modis", 0, True, 1), (2020, 2, "viirs", 1, True, 0)]
    # a soma da tabela densa e a da esparsa (nada se perde nem se inventa)
    assert out["cell_days"].sum() == sparse["cell_days"].sum()
    # nunca cria linhas fora do intervalo da serie (viirs nao tem janeiro)
    assert not ((out["series"] == "viirs") & (out["month"] == 1)).any()


def test_densify_monthly_default_cells_are_those_in_monthly(cdays, cov):
    sparse = cal_monthly(cdays, cov)
    out = densify_monthly(sparse, month_validity(cov))
    assert set(out["cell"]) == {CA, CB}


def test_densify_slice_of_cells_is_slice_of_full(cdays, cov):
    sparse = cal_monthly(cdays, cov)
    validity = month_validity(cov)
    full = densify_monthly(sparse, validity, cells=[CA, CB, CZ])
    part = densify_monthly(sparse, validity, cells=[CB])
    pd.testing.assert_frame_equal(part, full[full["cell"] == CB].reset_index(drop=True))


def test_densify_monthly_empty_cases_and_errors(cdays, cov):
    sparse = cal_monthly(cdays, cov)
    validity = month_validity(cov)
    assert len(densify_monthly(sparse, validity, cells=[])) == 0
    assert len(densify_monthly(sparse.iloc[0:0], validity)) == 0
    assert list(densify_monthly(sparse.iloc[0:0], validity).columns) == [
        "cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]
    with pytest.raises(ValueError, match="validade"):
        densify_monthly(sparse, validity.iloc[0:0])
    assert len(densify_monthly(sparse.iloc[0:0], validity.iloc[0:0])) == 0
    # atividade num mes que a validade nao tem (aqui: so a serie combined existe)
    with pytest.raises(ValueError, match="validade"):
        densify_monthly(sparse, validity[validity["series"] == "combined"], cells=[CA, CB])
    with pytest.raises(ValueError, match="cell_days"):
        densify_monthly(sparse.drop(columns=["cell_days"]), validity)


def test_densify_annual_manual():
    monthly = cal_monthly(_long_cell_days(), _long_cov())
    annual = cal_annual(monthly)
    yv = year_validity(month_validity(_long_cov()))
    out = densify_annual(annual, yv, cells=[CA, CB, CZ])
    assert list(out.columns) == ["cell", "year", "series", "cell_days", "partial", "n_unknown_days"]
    assert len(out) == 3 * len(yv)
    a = out[(out["cell"] == CA) & (out["series"] == "modis")]
    assert [(r["year"], r["cell_days"], r["partial"], r["n_unknown_days"]) for r in recs(a)] == [
        (2019, 0, True, 30), (2020, 1, False, 366), (2021, 0, True, 30)]
    assert (out[out["cell"] == CZ]["cell_days"] == 0).all()
    with pytest.raises(ValueError, match="validade"):
        densify_annual(annual, yv.iloc[0:0])


# ------------------------------------------------- EQUIVALENCIA com o calendario antigo por pais
def _random_world(seed=11, n=500):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        inst = rng.choice(["MODIS", "VIIRS"])
        rows.append({
            "country": rng.choice(["P", "Q"]), "instrument": inst,
            "satellite": rng.choice(["Terra", "Aqua"]) if inst == "MODIS" else "N20",
            "latitude": rng.choice([10.05, 10.15, -33.35, 0.0]), "longitude": rng.choice([20.05, -70.45, 179.99]),
            "acq_date": rng.choice(["2019-12-31", "2020-01-01", "2020-02-29", "2020-03-01", "2021-01-15"]),
            "type": rng.choice([0, 0, 2]), "confidence_class": rng.choice(["l", "n", "h", "h"]),
        })
    return rows, make_df(rows)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_densify_reproduces_the_old_dense_monthly_and_annual(seed):
    rows, df = _random_world(seed)
    # VIIRS so comeca em 2020 e termina antes de MODIS: intervalos diferentes, meses parciais e dias sem dados
    df = df[~((df["instrument"] == "VIIRS") & (df["acq_date"] < "2020-01-01"))].reset_index(drop=True)
    cd = eligible_cell_days(df)
    cov_ = cal_coverage(global_day_counts(df))
    cells = sorted(cd["cell"].unique().tolist()) + [CZ]            # inclui uma celula sem atividade
    # novo
    validity = month_validity(cov_)
    monthly_sparse = cal_monthly(cd, cov_)
    new_monthly = densify_monthly(monthly_sparse, validity, cells)
    new_annual = densify_annual(cal_annual(monthly_sparse), year_validity(validity), cells)
    # antigo (country = str(cell))
    old_daily = old_daily_from_cell_days(cd)
    old_monthly = old_cal_monthly(old_daily, cov_, countries=[str(c) for c in cells])
    old_annual = old_cal_annual(old_monthly)
    pd.testing.assert_frame_equal(new_monthly, old_to_cell(old_monthly), check_dtype=True)
    pd.testing.assert_frame_equal(new_annual, old_to_cell(old_annual), check_dtype=True)
    # sem `cells`: so as celulas com atividade, igual ao antigo com countries=None
    default = densify_monthly(monthly_sparse, validity)
    pd.testing.assert_frame_equal(default, old_to_cell(old_cal_monthly(old_daily, cov_)))


def test_equivalence_holds_year_by_year():
    """cal_monthly/cal_annual sao independentes entre anos: calcular ano a ano e concatenar da o mesmo."""
    _, df = _random_world(21, 800)
    cd = eligible_cell_days(df)
    cov_ = cal_coverage(global_day_counts(df))
    whole = cal_monthly(cd, cov_)
    parts = [cal_monthly(cd[cd["date"].dt.year == y], cov_) for y in sorted(cd["date"].dt.year.unique())]
    stitched = pd.concat(parts, ignore_index=True).sort_values(
        ["cell", "year", "month", "series"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(stitched, whole)
    annual_parts = [cal_annual(p) for p in parts]
    pd.testing.assert_frame_equal(
        pd.concat(annual_parts, ignore_index=True).sort_values(["cell", "year", "series"]).reset_index(drop=True),
        cal_annual(whole))


# ------------------------------------------------- invariantes e oraculo independente
def _cell(lat, lon):
    g = Fraction(1, 10)
    return int((Fraction(str(lat)) + 90) // g), int((Fraction(str(lon)) + 180) // g)


def test_daily_and_monthly_match_independent_set_oracle():
    rows, df = _random_world()
    exp = {}                                  # (celula, data) -> conjunto de instrumentos
    for r in rows:
        if r["type"] == 0 and r["confidence_class"] in ("n", "h"):
            exp.setdefault((_cell(r["latitude"], r["longitude"]), r["acq_date"]), set()).add(r["instrument"])
    daily = cal_daily(eligible_cell_days(df))
    ilat, ilon = cell_to_ids(daily["cell"].to_numpy())
    got = {((int(a), int(b)), d.strftime("%Y-%m-%d")): ({"MODIS"} if m else set()) | ({"VIIRS"} if v else set())
           for a, b, d, m, v in zip(ilat, ilon, daily["date"], daily["in_modis"], daily["in_viirs"])}
    assert got == exp
    # mensal: contagem por (celula, ano, mes, serie) a partir do oraculo
    cov_ = cal_coverage(global_day_counts(df))
    monthly = cal_monthly(eligible_cell_days(df), cov_)
    exp_m = {}
    for (cell, d), insts in exp.items():
        for s in [i.lower() for i in insts] + ["combined"]:
            key = (cell, int(d[:4]), int(d[5:7]), s)
            exp_m[key] = exp_m.get(key, 0) + 1
    ilat, ilon = cell_to_ids(monthly["cell"].to_numpy())
    got_m = {((int(a), int(b)), y, m, s): n for a, b, y, m, s, n in
             zip(ilat, ilon, monthly["year"], monthly["month"], monthly["series"], monthly["cell_days"])}
    assert got_m == exp_m


def test_totals_are_consistent_across_daily_monthly_annual():
    _, df = _random_world()
    cd = eligible_cell_days(df)
    daily = cal_daily(cd)
    cov_ = cal_coverage(global_day_counts(df))
    monthly = cal_monthly(cd, cov_)
    annual = cal_annual(monthly)
    totals = {"modis": int(daily["in_modis"].sum()), "viirs": int(daily["in_viirs"].sum()),
              "combined": int((daily["in_modis"] | daily["in_viirs"]).sum())}
    for s, d in totals.items():
        assert monthly.loc[monthly["series"] == s, "cell_days"].sum() == d
        assert annual.loc[annual["series"] == s, "cell_days"].sum() == d
    # a serie combinada nunca excede a soma dos sensores nem fica abaixo do maior
    w = monthly.pivot_table(index=["cell", "year", "month"], columns="series", values="cell_days").fillna(0)
    assert (w["combined"] <= w["modis"] + w["viirs"]).all()
    assert (w["combined"] >= w[["modis", "viirs"]].max(axis=1)).all()
    # os dias desconhecidos somam igual nos meses e nos anos
    mv = month_validity(cov_)
    yv = year_validity(mv)
    assert mv.groupby("series")["n_unknown_days"].sum().to_dict() == yv.groupby("series")["n_unknown_days"].sum().to_dict()


def test_order_of_rows_does_not_matter():
    _, df = _random_world()
    shuffled = df.sample(frac=1.0, random_state=5).reset_index(drop=True)
    for fn in (lambda d: eligible_cell_days(d), lambda d: cal_daily(eligible_cell_days(d)), global_day_counts,
               lambda d: cal_monthly(eligible_cell_days(d), cal_coverage(global_day_counts(d)))):
        a, b = fn(df), fn(shuffled)
        pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=False)


# --------------------------------------------------------------------- active_cells
def _validity():
    rows = [("modis", 2018, 1, False, 0), ("modis", 2019, 1, False, 0), ("modis", 2020, 1, True, 0),
            ("modis", 2021, 1, False, 3), ("modis", 2022, 1, False, 0),
            ("combined", 2018, 1, False, 0)]
    return pd.DataFrame(rows, columns=["series", "year", "month", "partial", "n_unknown_days"])


def _monthly(rows):
    return pd.DataFrame(rows, columns=["cell", "year", "month", "series", "cell_days"]).astype(
        {"cell": "int64", "year": "int64", "month": "int64", "cell_days": "int64"})


def test_active_cells_counts_distinct_years_in_valid_months_only():
    monthly = _monthly([
        (1, 2018, 1, "modis", 2), (1, 2019, 1, "modis", 1), (1, 2020, 1, "modis", 4),   # 2020 parcial
        (1, 2021, 1, "modis", 1), (1, 2022, 1, "modis", 1),                              # 2021 com dias desconhecidos
        (2, 2018, 1, "modis", 1), (2, 2019, 1, "modis", 1),
        (3, 2018, 1, "modis", 1), (3, 2019, 1, "modis", 1), (3, 2022, 1, "modis", 0),    # 0 nao conta
        (4, 2018, 1, "modis", 1), (4, 2018, 1, "combined", 1),                           # mesmo ano, 2 series: 1 ano
    ])
    v = _validity()
    assert active_cells(monthly, v, 3).tolist() == [1]            # cell 1: 2018, 2019, 2022 validos
    assert active_cells(monthly, v, 2).tolist() == [1, 2, 3]
    assert active_cells(monthly, v, 1).tolist() == [1, 2, 3, 4]
    assert active_cells(monthly, v, 3, max_unknown_days=3).tolist() == [1]   # 2021 passa a valido: 4 anos
    assert active_cells(monthly, v, 4).tolist() == []
    assert active_cells(monthly, v, 4, max_unknown_days=3).tolist() == [1]
    out = active_cells(monthly, v, 2)
    assert out.dtype == np.int64


def test_active_cells_empty_and_errors():
    assert active_cells(_monthly([]), _validity(), 1).tolist() == []
    assert active_cells(_monthly([(1, 2018, 1, "modis", 1)]), _validity().iloc[0:0], 1).tolist() == []
    with pytest.raises(ValueError, match="partial"):
        active_cells(_monthly([]), _validity().drop(columns=["partial"]), 1)


# --------------------------------------------------------------------- coarsen_cell_days
def test_coarsen_cell_days_merges_children_and_keeps_distinct_days_and_sensors():
    df = make_df([
        {"latitude": 10.05, "longitude": 20.05, "acq_date": "2020-01-30"},
        {"latitude": 10.051, "longitude": 20.054, "acq_date": "2020-01-30"},    # mesma celula 0.01 que a 1.
        {"latitude": 10.06, "longitude": 20.05, "acq_date": "2020-01-30"},      # outra celula 0.01, mesma 0.1
        {"latitude": 10.06, "longitude": 20.05, "acq_date": "2020-01-31"},      # outro dia
        {"latitude": 10.06, "longitude": 20.05, "acq_date": "2020-01-30", "satellite": "Aqua"},
        {"latitude": 10.06, "longitude": 20.05, "acq_date": "2020-01-30", **V},
    ])
    fine = eligible_cell_days(df, grid_deg=0.01)
    assert fine["cell"].nunique() == 2
    coarse = coarsen_cell_days(fine, 0.01, 0.1)
    assert list(coarse.columns) == ["date", "cell", "instrument", "satellite"]
    assert len(coarse) == 4                                    # (Terra,30), (Terra,31), (Aqua,30), (N20,30)
    pd.testing.assert_frame_equal(coarse, eligible_cell_days(df, grid_deg=0.1))
    same = coarsen_cell_days(fine, 0.01, 0.01)
    pd.testing.assert_frame_equal(same, fine)


def test_coarsen_cell_days_matches_computing_directly_on_random_data():
    _, df = _random_world(31, 600)
    fine = eligible_cell_days(df, grid_deg=0.01)
    pd.testing.assert_frame_equal(coarsen_cell_days(fine, 0.01, 0.1), eligible_cell_days(df, grid_deg=0.1))


def test_coarsen_cell_days_errors_and_empty():
    df = make_df([{**A, "acq_date": "2020-01-30"}])
    fine = eligible_cell_days(df, grid_deg=0.01)
    with pytest.raises(ValueError):
        coarsen_cell_days(fine, 0.1, 0.01)                     # to_deg nao e multiplo de grid_deg
    with pytest.raises(ValueError, match="cell"):
        coarsen_cell_days(fine.drop(columns=["cell"]), 0.01, 0.1)
    assert len(coarsen_cell_days(fine.iloc[0:0], 0.01, 0.1)) == 0


# --------------------------------------------------------------------- global_day_counts
def test_global_day_counts_ignores_invalid_dates_and_normalizes_instrument_case():
    df = make_df([{"acq_date": "2020-01-30"}, {"acq_date": "2020-02-31"}, {"acq_date": "lixo"},
                  {"acq_date": "2020-01-30", "instrument": "modis"}])
    out = global_day_counts(df)
    assert [(r["instrument"], r["date"], r["n_rows_global"]) for r in recs(out)] == [
        ("MODIS", T("2020-01-30"), 2)]        # 2 validas (MODIS e modis juntos); as 2 invalidas ficam fora


def test_year_validity_eleven_full_months_is_still_partial():
    """Feb..Dec completos (11 meses, nenhum parcial): o ano falta de janeiro e e parcial; com 12 nao."""
    def cov_between(first, last):
        return cal_coverage(pd.DataFrame([("MODIS", first, 1), ("MODIS", last, 1)],
                                         columns=["instrument", "date", "n_rows_global"]).assign(
            date=lambda d: pd.to_datetime(d["date"])))
    eleven = month_validity(cov_between("2020-02-01", "2020-12-31"))
    assert not eleven["partial"].any()
    assert year_validity(eleven)["partial"].tolist() == [True, True]          # combined e modis
    twelve = month_validity(cov_between("2020-01-01", "2020-12-31"))
    assert year_validity(twelve)["partial"].tolist() == [False, False]

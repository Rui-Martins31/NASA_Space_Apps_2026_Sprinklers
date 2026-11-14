"""Testes do Lote 5: build_cell_year (comum) e, a seguir, ESP-02, ESP-03 e ESP-06.

Valores esperados calculados a mao (ver comentarios em cada teste).
"""
import random

import pandas as pd
import pytest

from helpers_lote5 import CELL_YEAR_COLUMNS, cell_days_df, tuples
from metrics.cell_recurrence import build_cell_year


# ------------------------------------------------------------------ build_cell_year
# ES celula 10: MODIS 2020-01-01 (Terra e Aqua = 1 dia), 2020-01-02; VIIRS 2020-01-02, 2020-01-03;
#               MODIS 2021-01-01.   ES celula 11: VIIRS 2020-05-05.   PT celula 10: MODIS 2020-01-01.
# modis   ES c10 2020 = {01-01, 01-02} = 2 ; ES c10 2021 = 1 ; PT c10 2020 = 1
# viirs   ES c10 2020 = {01-02, 01-03} = 2 ; ES c11 2020 = 1
# combined ES c10 2020 = {01-01, 01-02, 01-03} = 3 (01-02 nos dois sensores conta 1) ; ES c10 2021 = 1 ;
#          ES c11 2020 = 1 ; PT c10 2020 = 1
ROWS = [
    ("ES", "2020-01-01", 10, "MODIS", "Terra"),
    ("ES", "2020-01-01", 10, "MODIS", "Aqua"),
    ("ES", "2020-01-02", 10, "MODIS", "Terra"),
    ("ES", "2020-01-02", 10, "VIIRS", "N20"),
    ("ES", "2020-01-03", 10, "VIIRS", "N20"),
    ("ES", "2021-01-01", 10, "MODIS", "Terra"),
    ("ES", "2020-05-05", 11, "VIIRS", "N20"),
    ("PT", "2020-01-01", 10, "MODIS", "Terra"),
]
EXPECTED = [
    ("ES", "combined", 10, 2020, 3), ("ES", "combined", 10, 2021, 1), ("ES", "combined", 11, 2020, 1),
    ("ES", "modis", 10, 2020, 2), ("ES", "modis", 10, 2021, 1),
    ("ES", "viirs", 10, 2020, 2), ("ES", "viirs", 11, 2020, 1),
    ("PT", "combined", 10, 2020, 1), ("PT", "modis", 10, 2020, 1),
]


def test_build_cell_year_manual_example():
    out = build_cell_year(cell_days_df(ROWS))
    assert list(out.columns) == CELL_YEAR_COLUMNS
    assert tuples(out) == EXPECTED
    assert all(out[c].dtype == "int64" for c in ("cell", "year", "n_days"))


def test_build_cell_year_empty_keeps_columns_and_dtypes():
    out = build_cell_year(cell_days_df([]))
    assert list(out.columns) == CELL_YEAR_COLUMNS
    assert len(out) == 0
    assert all(out[c].dtype == "int64" for c in ("cell", "year", "n_days"))


def test_build_cell_year_year_boundary_and_leap_day():
    rows = [("ES", "2020-12-31", 5, "MODIS", "Terra"), ("ES", "2021-01-01", 5, "MODIS", "Terra"),
            ("ES", "2020-02-29", 5, "MODIS", "Aqua")]
    out = build_cell_year(cell_days_df(rows))
    # 2020: {02-29, 12-31} = 2 ; 2021: {01-01} = 1 (so a serie modis e a combined, iguais)
    assert tuples(out) == [("ES", "combined", 5, 2020, 2), ("ES", "combined", 5, 2021, 1),
                           ("ES", "modis", 5, 2020, 2), ("ES", "modis", 5, 2021, 1)]


def test_build_cell_year_only_viirs_has_no_modis_rows():
    out = build_cell_year(cell_days_df([("ES", "2019-03-03", 1, "VIIRS", "N20")]))
    assert tuples(out) == [("ES", "combined", 1, 2019, 1), ("ES", "viirs", 1, 2019, 1)]


def test_build_cell_year_is_order_invariant():
    base = build_cell_year(cell_days_df(ROWS))
    rows = list(ROWS)
    random.Random(7).shuffle(rows)
    pd.testing.assert_frame_equal(build_cell_year(cell_days_df(rows)), base)


def test_build_cell_year_duplicate_input_rows_do_not_change_result():
    pd.testing.assert_frame_equal(build_cell_year(cell_days_df(ROWS + ROWS)),
                                  build_cell_year(cell_days_df(ROWS)))


@pytest.mark.parametrize("bad, match", [
    (lambda d: d.drop(columns=["cell"]), "cell"),
    (lambda d: d.assign(instrument=d["instrument"].replace({"VIIRS": "AVHRR"})), "instrumento"),
    (lambda d: d.assign(cell=d["cell"].astype("float64").where(d["cell"] != 11)), "cell"),
    (lambda d: d.assign(date=d["date"].where(d["cell"] != 11)), "date"),
])
def test_build_cell_year_rejects_bad_input(bad, match):
    with pytest.raises(ValueError, match=match):
        build_cell_year(bad(cell_days_df(ROWS)))


def test_build_cell_year_matches_pure_python_oracle_and_series_invariants():
    rng = random.Random(2024)
    rows = [(rng.choice(["ES", "PT", "FR"]),
             f"{rng.choice([2018, 2019, 2020])}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
             rng.randint(0, 6), rng.choice(["MODIS", "VIIRS"]), rng.choice(["Terra", "Aqua", "N20"]))
            for _ in range(400)]
    out = build_cell_year(cell_days_df(rows))
    days = {}                                   # (pais, serie, celula, ano) -> conjunto de datas
    for country, date, cell, inst, _sat in rows:
        for series in (inst.lower(), "combined"):
            days.setdefault((country, series, cell, int(date[:4])), set()).add(date)
    assert tuples(out) == sorted((*k, len(v)) for k, v in days.items())
    by = {(r[0], r[1], r[2], r[3]): r[4] for r in tuples(out)}
    for (country, series, cell, year), n in by.items():
        if series != "combined":
            continue
        m, v = by.get((country, "modis", cell, year), 0), by.get((country, "viirs", cell, year), 0)
        assert max(m, v) <= n <= m + v


# ================================================================== ESP-02, ESP-03, ESP-06
import math  # noqa: E402
import statistics  # noqa: E402

from helpers_lote5 import cell_year_df, recs  # noqa: E402
from metrics.cell_recurrence import esp02_active_cells, esp03_recurrence, esp06_interannual  # noqa: E402

ESP02_COLUMNS = ["country", "series", "year", "n_active_cells"]
ESP03_COLUMNS = ["country", "series", "year", "n_active_cells", "mean_days", "median_days", "p90_days",
                 "max_days", "n_cells_1d", "n_cells_2_5d", "n_cells_6_15d", "n_cells_16plus"]
ESP06_COLUMNS = ["country", "series", "n_years_analysed", "n_cells", "n_cells_2plus_years",
                 "pct_cells_2plus", "mean_years_per_cell", "max_years"]
ESP02_DTYPES = {"country": "object", "series": "object", "year": "int64", "n_active_cells": "int64"}
ESP03_DTYPES = {"country": "object", "series": "object", "year": "int64", "n_active_cells": "int64",
                "mean_days": "float64", "median_days": "float64", "p90_days": "float64", "max_days": "int64",
                "n_cells_1d": "int64", "n_cells_2_5d": "int64", "n_cells_6_15d": "int64",
                "n_cells_16plus": "int64"}
ESP06_DTYPES = {"country": "object", "series": "object", "n_years_analysed": "int64", "n_cells": "int64",
                "n_cells_2plus_years": "int64", "pct_cells_2plus": "float64",
                "mean_years_per_cell": "float64", "max_years": "Int64"}


def _dtypes(df):
    return df.dtypes.astype(str).to_dict()


def _shuffled(rows, seed):
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    return rows


def _eligible_df(rows):
    """eligible_years sintetico: (country, series, year) -> DataFrame com year int64."""
    return pd.DataFrame(rows, columns=["country", "series", "year"]).astype({"year": "int64"})


# ------------------------------------------------------------------ ESP-02
# O valor de n_days nao interessa: cada celula com n_days >= 1 conta uma vez (celula 3 de ES/modis/2020 tem 40 dias).
# ES modis 2020: celulas 1, 2, 3 = 3 ; ES modis 2021: celula 1 = 1 ; ES viirs 2020: celula 2 = 1
# PT modis 2020: celulas 1, 2 = 2 (os mesmos ids de celula noutro pais contam em separado)
# ES combined 2020: celulas 1, 2, 3 = 3
CY02 = [
    ("ES", "modis", 1, 2020, 3), ("ES", "modis", 2, 2020, 1), ("ES", "modis", 3, 2020, 40),
    ("ES", "modis", 1, 2021, 2),
    ("ES", "viirs", 2, 2020, 1),
    ("PT", "modis", 1, 2020, 1), ("PT", "modis", 2, 2020, 2),
    ("ES", "combined", 1, 2020, 3), ("ES", "combined", 2, 2020, 2), ("ES", "combined", 3, 2020, 40),
]
EXPECTED02 = [
    ("ES", "combined", 2020, 3), ("ES", "modis", 2020, 3), ("ES", "modis", 2021, 1),
    ("ES", "viirs", 2020, 1), ("PT", "modis", 2020, 2),
]


def test_esp02_manual_example():
    out = esp02_active_cells(cell_year_df(CY02))
    assert list(out.columns) == ESP02_COLUMNS
    assert tuples(out) == EXPECTED02
    assert _dtypes(out) == ESP02_DTYPES
    assert list(out.index) == list(range(len(out)))


def test_esp02_empty_keeps_columns_and_dtypes():
    out = esp02_active_cells(cell_year_df([]))
    assert list(out.columns) == ESP02_COLUMNS
    assert len(out) == 0
    assert _dtypes(out) == ESP02_DTYPES


def test_esp02_single_cell_with_one_day_counts():
    out = esp02_active_cells(cell_year_df([("ES", "viirs", 9, 2019, 1)]))
    assert tuples(out) == [("ES", "viirs", 2019, 1)]


def test_esp02_is_order_invariant():
    base = esp02_active_cells(cell_year_df(CY02))
    for seed in (1, 2, 3):
        pd.testing.assert_frame_equal(esp02_active_cells(cell_year_df(_shuffled(CY02, seed))), base)


# ------------------------------------------------------------------ ESP-03
# ES modis 2020: 11 celulas com n_days = 1, 2, 5, 6, 15, 16, 20, 23, 30, 40, 51 (inseridas fora de ordem)
#   soma = 209 -> media 209/11 = 19.0 ; mediana = 6.o de 11 ordenados = 16 ;
#   p90 linear: posicao 0.9*(11-1) = 9 -> 10.o valor = 40 ; max 51
#   baldes: 1d {1} = 1 ; 2-5d {2, 5} = 2 ; 6-15d {6, 15} = 2 ; 16+ {16, 20, 23, 30, 40, 51} = 6 (soma 11)
# ES modis 2021: n_days = 4, 4 -> media = mediana = p90 = 4.0, max 4, 2-5d = 2
# PT viirs 2020: uma so celula com 7 dias -> tudo 7 ; 6-15d = 1
DAYS_ES_2020 = [51, 1, 20, 6, 40, 2, 16, 30, 5, 23, 15]
CY03 = (
    [("ES", "modis", i + 1, 2020, d) for i, d in enumerate(DAYS_ES_2020)]
    + [("ES", "modis", 1, 2021, 4), ("ES", "modis", 2, 2021, 4), ("PT", "viirs", 1, 2020, 7)]
)
EXPECTED03 = [
    ("ES", "modis", 2020, 11, 19.0, 16.0, 40.0, 51, 1, 2, 2, 6),
    ("ES", "modis", 2021, 2, 4.0, 4.0, 4.0, 4, 0, 2, 0, 0),
    ("PT", "viirs", 2020, 1, 7.0, 7.0, 7.0, 7, 0, 0, 1, 0),
]


def test_esp03_manual_example():
    out = esp03_recurrence(cell_year_df(CY03))
    assert list(out.columns) == ESP03_COLUMNS
    assert tuples(out) == EXPECTED03
    assert _dtypes(out) == ESP03_DTYPES
    assert list(out.index) == list(range(len(out)))


def test_esp03_empty_keeps_columns_and_dtypes():
    out = esp03_recurrence(cell_year_df([]))
    assert list(out.columns) == ESP03_COLUMNS
    assert len(out) == 0
    assert _dtypes(out) == ESP03_DTYPES


@pytest.mark.parametrize("n_days, buckets", [
    (1, (1, 0, 0, 0)), (2, (0, 1, 0, 0)), (3, (0, 1, 0, 0)), (5, (0, 1, 0, 0)), (6, (0, 0, 1, 0)),
    (15, (0, 0, 1, 0)), (16, (0, 0, 0, 1)), (17, (0, 0, 0, 1)), (366, (0, 0, 0, 1)),
])
def test_esp03_bucket_boundaries_single_cell(n_days, buckets):
    # uma celula com n_days: cai num so balde e media = mediana = p90 = max = n_days (um so elemento)
    out = esp03_recurrence(cell_year_df([("ES", "modis", 1, 2020, n_days)]))
    assert tuples(out) == [("ES", "modis", 2020, 1, float(n_days), float(n_days), float(n_days), n_days,
                            *buckets)]


def test_esp03_bucket_boundaries_all_together():
    # n_days = 1, 2, 5, 6, 15, 16 numa so tabela: um por fronteira -> baldes 1, 2, 2, 1.
    # soma = 45 -> media 7.5 ; mediana = (5+6)/2 = 5.5 ; p90: posicao 0.9*5 = 4.5 -> entre 15 e 16 = 15.5
    days = [1, 2, 5, 6, 15, 16]
    out = esp03_recurrence(cell_year_df([("ES", "modis", i, 2020, d) for i, d in enumerate(days)]))
    row = recs(out)[0]
    assert (row["n_active_cells"], row["max_days"]) == (6, 16)
    assert (row["n_cells_1d"], row["n_cells_2_5d"], row["n_cells_6_15d"], row["n_cells_16plus"]) == (1, 2, 2, 1)
    assert (row["mean_days"], row["median_days"]) == (7.5, 5.5)
    assert row["p90_days"] == pytest.approx(15.5, abs=1e-12)


def test_esp03_p90_is_linear_interpolation_not_nearest_rank():
    # n_days = 1, 2, 3, 4: posicao 0.9*3 = 2.7 -> 3 + 0.7*(4-3) = 3.7 ; media = mediana = 2.5
    out = esp03_recurrence(cell_year_df([("ES", "modis", i, 2020, i) for i in (1, 2, 3, 4)]))
    row = recs(out)[0]
    assert row["p90_days"] == pytest.approx(3.7, abs=1e-12)
    assert (row["mean_days"], row["median_days"], row["max_days"]) == (2.5, 2.5, 4)


def test_esp03_mean_differs_from_median_with_outlier():
    # n_days = 1, 1, 10: media 4.0, mediana 1.0 ; p90: posicao 0.9*2 = 1.8 -> 1 + 0.8*9 = 8.2
    out = esp03_recurrence(cell_year_df([("ES", "modis", 1, 2020, 1), ("ES", "modis", 2, 2020, 1),
                                         ("ES", "modis", 3, 2020, 10)]))
    row = recs(out)[0]
    assert (row["mean_days"], row["median_days"], row["max_days"]) == (4.0, 1.0, 10)
    assert row["p90_days"] == pytest.approx(8.2, abs=1e-12)
    assert (row["n_cells_1d"], row["n_cells_2_5d"], row["n_cells_6_15d"], row["n_cells_16plus"]) == (2, 0, 1, 0)


def test_esp03_groups_are_independent_across_country_series_year():
    # mesma celula em grupos diferentes: cada grupo calcula so com as suas celulas
    rows = [("ES", "modis", 1, 2020, 2), ("ES", "viirs", 1, 2020, 20), ("PT", "modis", 1, 2020, 6),
            ("ES", "modis", 1, 2021, 1)]
    out = esp03_recurrence(cell_year_df(rows))
    assert [(r["country"], r["series"], r["year"], r["max_days"]) for r in recs(out)] == [
        ("ES", "modis", 2020, 2), ("ES", "modis", 2021, 1), ("ES", "viirs", 2020, 20), ("PT", "modis", 2020, 6)]


def test_esp03_is_order_invariant():
    base = esp03_recurrence(cell_year_df(CY03))
    for seed in (1, 2, 3):
        pd.testing.assert_frame_equal(esp03_recurrence(cell_year_df(_shuffled(CY03, seed))), base)


# ------------------------------------------------------------------ erros comuns (cell_year)
def _break_missing_column(d):
    return d.drop(columns=["n_days"])


def _break_zero_days(d):
    return d.assign(n_days=d["n_days"].where(d["cell"] != 2, 0))


def _break_negative_days(d):
    return d.assign(n_days=d["n_days"].where(d["cell"] != 2, -3))


def _break_duplicate_key(d):
    return pd.concat([d, d.iloc[[0]].assign(n_days=7)], ignore_index=True)


def _break_na_country(d):
    return d.assign(country=d["country"].where(d["cell"] != 2))


def _break_na_year(d):
    return d.assign(year=d["year"].astype("float64").where(d["cell"] != 2))


@pytest.mark.parametrize("func", [esp02_active_cells, esp03_recurrence, esp06_interannual])
@pytest.mark.parametrize("bad, match", [
    (_break_missing_column, "colunas em falta"),
    (_break_zero_days, "n_days"),
    (_break_negative_days, "n_days"),
    (_break_duplicate_key, "duplicad"),
    (_break_na_country, "valores em falta"),
    (_break_na_year, "valores em falta"),
])
def test_esp_rejects_bad_cell_year(func, bad, match):
    with pytest.raises(ValueError, match=match):
        func(bad(cell_year_df(CY02)))


# ------------------------------------------------------------------ ESP-06
# Celulas por (pais, serie) e anos com detecao:
#   ES modis: c1 {2018, 2019, 2020}, c2 {2019}, c3 {2020, 2021}, c4 {2021}, c5 {2018}
#   PT modis: c7 {2019, 2020} ; FR combined: c1 {2020}  (o id de celula 1 repete-se em ES e FR: independentes)
CY06 = [
    ("ES", "modis", 1, 2018, 10), ("ES", "modis", 1, 2019, 3), ("ES", "modis", 1, 2020, 1),
    ("ES", "modis", 2, 2019, 5),
    ("ES", "modis", 3, 2020, 2), ("ES", "modis", 3, 2021, 9),
    ("ES", "modis", 4, 2021, 4),
    ("ES", "modis", 5, 2018, 1),
    ("PT", "modis", 7, 2019, 1), ("PT", "modis", 7, 2020, 1),
    ("FR", "combined", 1, 2020, 1),
]
# Anos validos: ES modis 2017-2020 (2021 e parcial: fora; 2017 sem nenhuma detecao), PT modis 2019-2020,
# ES viirs 2020 (sem nenhuma celula em cell_year). FR combined nao tem nenhum ano valido.
ELIG06 = [("ES", "modis", 2017), ("ES", "modis", 2018), ("ES", "modis", 2019), ("ES", "modis", 2020),
          ("PT", "modis", 2019), ("PT", "modis", 2020), ("ES", "viirs", 2020)]
# Com ELIG06 (so conta o que esta nos anos validos):
#   ES modis: n_years = 4 ; anos validos por celula: c1 = 3, c2 = 1, c3 = 1 (2021 fora), c4 = 0 (so 2021: sai),
#             c5 = 1 -> n_cells = 4, 2+ anos = 1 (c1), pct = 100*1/4 = 25.0, media = (3+1+1+1)/4 = 1.5, max 3
#   ES viirs: n_years = 1, sem celulas -> n_cells 0 e o resto NA
#   FR combined: n_years = 0, n_cells = 0 (esta em cell_year mas nao tem anos validos)
#   PT modis: n_years = 2 ; c7 = 2 -> n_cells 1, 2+ = 1, pct 100.0, media 2.0, max 2
EXPECTED06 = [
    ("ES", "modis", 4, 4, 1, 25.0, 1.5, 3),
    ("ES", "viirs", 1, 0, 0, None, None, None),
    ("FR", "combined", 0, 0, 0, None, None, None),
    ("PT", "modis", 2, 1, 1, 100.0, 2.0, 2),
]
# Sem eligible_years (todos os anos presentes contam):
#   ES modis: anos 2018-2021 = 4 ; c1 = 3, c2 = 1, c3 = 2, c4 = 1, c5 = 1 -> n_cells 5, 2+ = 2 (c1, c3),
#             pct = 100*2/5 = 40.0, media = 8/5 = 1.6, max 3
#   FR combined: 1 ano, c1 = 1 -> 1, 0, 0.0, 1.0, 1 ; PT modis: 2 anos, c7 = 2 -> 2, 1, 1, 100.0, 2.0, 2
EXPECTED06_ALL_YEARS = [
    ("ES", "modis", 4, 5, 2, 40.0, 1.6, 3),
    ("FR", "combined", 1, 1, 0, 0.0, 1.0, 1),
    ("PT", "modis", 2, 1, 1, 100.0, 2.0, 2),
]


def test_esp06_manual_example_with_eligible_years():
    out = esp06_interannual(cell_year_df(CY06), _eligible_df(ELIG06))
    assert list(out.columns) == ESP06_COLUMNS
    assert tuples(out) == EXPECTED06
    assert _dtypes(out) == ESP06_DTYPES
    assert list(out.index) == list(range(len(out)))


def test_esp06_manual_example_without_eligible_years_uses_all_present_years():
    out = esp06_interannual(cell_year_df(CY06))
    assert list(out.columns) == ESP06_COLUMNS
    assert tuples(out) == EXPECTED06_ALL_YEARS
    assert _dtypes(out) == ESP06_DTYPES


def test_esp06_empty_inputs_keep_columns_and_dtypes():
    for eligible in (None, _eligible_df([])):
        out = esp06_interannual(cell_year_df([]), eligible)
        assert list(out.columns) == ESP06_COLUMNS
        assert len(out) == 0
        assert _dtypes(out) == ESP06_DTYPES


def test_esp06_empty_cell_year_with_eligible_years_gives_zero_cell_rows():
    out = esp06_interannual(cell_year_df([]), _eligible_df([("ES", "modis", 2019), ("ES", "modis", 2020),
                                                            ("PT", "viirs", 2020)]))
    assert tuples(out) == [("ES", "modis", 2, 0, 0, None, None, None), ("PT", "viirs", 1, 0, 0, None, None, None)]
    assert _dtypes(out) == ESP06_DTYPES


def test_esp06_empty_eligible_years_means_no_valid_year_anywhere():
    # eligible_years vazio e diferente de None: nenhum ano e valido, logo ninguem tem celulas
    out = esp06_interannual(cell_year_df(CY06), _eligible_df([]))
    assert tuples(out) == [("ES", "modis", 0, 0, 0, None, None, None),
                           ("FR", "combined", 0, 0, 0, None, None, None),
                           ("PT", "modis", 0, 0, 0, None, None, None)]


def test_esp06_partial_year_outside_eligible_years_does_not_count():
    # celula 1 detetada em 2020 e 2021, mas 2021 e parcial: com so 2020 valido, a celula tem 1 ano
    rows = [("ES", "modis", 1, 2020, 5), ("ES", "modis", 1, 2021, 5)]
    only_2020 = esp06_interannual(cell_year_df(rows), _eligible_df([("ES", "modis", 2020)]))
    assert tuples(only_2020) == [("ES", "modis", 1, 1, 0, 0.0, 1.0, 1)]
    both = esp06_interannual(cell_year_df(rows), _eligible_df([("ES", "modis", 2020), ("ES", "modis", 2021)]))
    assert tuples(both) == [("ES", "modis", 2, 1, 1, 100.0, 2.0, 2)]


def test_esp06_eligible_years_of_other_group_do_not_leak():
    # 2021 e valido para ES/viirs mas nao para ES/modis: a detecao modis de 2021 nao conta
    rows = [("ES", "modis", 1, 2020, 1), ("ES", "modis", 1, 2021, 1), ("ES", "viirs", 1, 2021, 1)]
    elig = _eligible_df([("ES", "modis", 2020), ("ES", "viirs", 2021), ("PT", "modis", 2021)])
    out = esp06_interannual(cell_year_df(rows), elig)
    assert tuples(out) == [("ES", "modis", 1, 1, 0, 0.0, 1.0, 1), ("ES", "viirs", 1, 1, 0, 0.0, 1.0, 1),
                           ("PT", "modis", 1, 0, 0, None, None, None)]


def test_esp06_cell_in_a_single_year_has_pct_zero():
    out = esp06_interannual(cell_year_df([("ES", "modis", 1, 2020, 9)]))
    assert tuples(out) == [("ES", "modis", 1, 1, 0, 0.0, 1.0, 1)]


def test_esp06_pct_and_mean_non_terminating_fractions():
    # c1 {2020, 2021}, c2 {2020}, c3 {2021}: n_cells 3, 2+ = 1 -> pct = 100/3 ; media = 4/3
    rows = [("ES", "modis", 1, 2020, 1), ("ES", "modis", 1, 2021, 1), ("ES", "modis", 2, 2020, 1),
            ("ES", "modis", 3, 2021, 1)]
    row = recs(esp06_interannual(cell_year_df(rows)))[0]
    assert (row["n_years_analysed"], row["n_cells"], row["n_cells_2plus_years"], row["max_years"]) == (2, 3, 1, 2)
    assert row["pct_cells_2plus"] == pytest.approx(33.33333333333333, rel=1e-12)
    assert row["mean_years_per_cell"] == pytest.approx(1.3333333333333333, rel=1e-12)


def test_esp06_two_plus_years_means_at_least_two():
    # c1 = 3 anos, c2 = 2 anos, c3 = 1 ano -> n_cells 3, 2+ = 2 (c1 e c2), media = 6/3 = 2.0, max 3
    rows = [("ES", "modis", 1, 2018, 1), ("ES", "modis", 1, 2019, 1), ("ES", "modis", 1, 2020, 1),
            ("ES", "modis", 2, 2018, 1), ("ES", "modis", 2, 2019, 1), ("ES", "modis", 3, 2020, 1)]
    out = esp06_interannual(cell_year_df(rows))
    assert tuples(out) == [("ES", "modis", 3, 3, 2, pytest.approx(66.66666666666667, rel=1e-12), 2.0, 3)]


def test_esp06_is_order_invariant():
    base = esp06_interannual(cell_year_df(CY06), _eligible_df(ELIG06))
    for seed in (1, 2, 3):
        out = esp06_interannual(cell_year_df(_shuffled(CY06, seed)), _eligible_df(_shuffled(ELIG06, seed)))
        pd.testing.assert_frame_equal(out, base)


@pytest.mark.parametrize("bad, match", [
    (lambda e: e.drop(columns=["year"]), "colunas em falta"),
    (lambda e: pd.concat([e, e.iloc[[0]]], ignore_index=True), "duplicad"),
    (lambda e: e.assign(country=e["country"].where(e["year"] != 2018)), "valores em falta"),
    (lambda e: e.assign(year=e["year"].astype("float64").where(e["year"] != 2018)), "valores em falta"),
])
def test_esp06_rejects_bad_eligible_years(bad, match):
    with pytest.raises(ValueError, match=match):
        esp06_interannual(cell_year_df(CY06), bad(_eligible_df(ELIG06)))


# ------------------------------------------------------------------ oraculos em Python puro + invariantes
def _random_cell_year(seed, n=300):
    """Linhas (pais, serie, celula, ano, n_days) aleatorias sem chaves repetidas."""
    rng = random.Random(seed)
    seen = {}
    for _ in range(n):
        key = (rng.choice(["ES", "PT", "FR"]), rng.choice(["modis", "viirs", "combined"]),
               rng.randint(0, 14), rng.randint(2016, 2021))
        seen[key] = rng.choice([1, 1, 2, 3, 5, 6, 9, 15, 16, 17, 40, 120, 366])
    return [(*k, v) for k, v in seen.items()]


def _percentile_linear(values, q):
    """Percentil linear em Python puro (posicao q/100*(n-1) com interpolacao)."""
    v = sorted(values)
    pos = q / 100 * (len(v) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_esp02_esp03_match_pure_python_oracle_and_invariants(seed):
    rows = _random_cell_year(seed)
    groups = {}                                   # (pais, serie, ano) -> lista de n_days
    for country, series, _cell, year, n_days in rows:
        groups.setdefault((country, series, year), []).append(n_days)
    out02 = esp02_active_cells(cell_year_df(rows))
    out03 = esp03_recurrence(cell_year_df(_shuffled(rows, seed)))
    assert tuples(out02) == sorted((*k, len(v)) for k, v in groups.items())
    assert [(r["country"], r["series"], r["year"]) for r in recs(out03)] == sorted(groups)
    for r in recs(out03):
        vals = groups[(r["country"], r["series"], r["year"])]
        assert r["n_active_cells"] == len(vals)
        assert r["max_days"] == max(vals)
        assert r["mean_days"] == pytest.approx(statistics.mean(vals), rel=1e-12)
        assert r["median_days"] == pytest.approx(statistics.median(vals), rel=1e-12)
        assert r["p90_days"] == pytest.approx(_percentile_linear(vals, 90), rel=1e-12)
        assert (r["n_cells_1d"], r["n_cells_2_5d"], r["n_cells_6_15d"], r["n_cells_16plus"]) == (
            sum(1 for d in vals if d == 1), sum(1 for d in vals if 2 <= d <= 5),
            sum(1 for d in vals if 6 <= d <= 15), sum(1 for d in vals if d >= 16))
        # invariantes
        assert r["n_cells_1d"] + r["n_cells_2_5d"] + r["n_cells_6_15d"] + r["n_cells_16plus"] == r["n_active_cells"]
        assert 1 <= r["median_days"] <= r["p90_days"] <= r["max_days"]
        assert 1 <= r["mean_days"] <= r["max_days"]
    assert out02["n_active_cells"].tolist() == out03["n_active_cells"].tolist()


@pytest.mark.parametrize("seed", [21, 22, 23])
@pytest.mark.parametrize("use_eligible", [False, True])
def test_esp06_matches_pure_python_oracle_and_invariants(seed, use_eligible):
    rows = _random_cell_year(seed)
    rng = random.Random(seed + 100)
    present = {(c, s) for c, s, *_ in rows}
    elig = sorted({(c, s, y) for c, s in sorted(present | {("DE", "modis")}) for y in range(2015, 2023)
                   if rng.random() < 0.6})
    years_by_cell = {}                            # (pais, serie, celula) -> anos com detecao
    for country, series, cell, year, _n in rows:
        years_by_cell.setdefault((country, series, cell), set()).add(year)
    valid_years = {}                              # (pais, serie) -> anos validos
    if use_eligible:
        for c, s, y in elig:
            valid_years.setdefault((c, s), set()).add(y)
        group_keys = set(valid_years) | present
        out = esp06_interannual(cell_year_df(_shuffled(rows, seed)), _eligible_df(_shuffled(elig, seed)))
    else:
        for c, s, _cell, y, _n in rows:
            valid_years.setdefault((c, s), set()).add(y)
        group_keys = set(valid_years)
        out = esp06_interannual(cell_year_df(rows))
    expected = []
    for key in sorted(group_keys):
        per_cell = [len(ys & valid_years.get(key, set()))
                    for (c, s, _cell), ys in years_by_cell.items() if (c, s) == key]
        per_cell = [k for k in per_cell if k >= 1]
        n_cells = len(per_cell)
        n2 = sum(1 for k in per_cell if k >= 2)
        expected.append((key[0], key[1], len(valid_years.get(key, set())), n_cells, n2,
                         None if n_cells == 0 else 100 * n2 / n_cells,
                         None if n_cells == 0 else sum(per_cell) / n_cells,
                         None if n_cells == 0 else max(per_cell)))
    got = tuples(out)
    assert [g[:5] for g in got] == [e[:5] for e in expected]
    assert [g[7] for g in got] == [e[7] for e in expected]
    for g, e in zip(got, expected):
        for i in (5, 6):
            assert (g[i] is None) == (e[i] is None)
            if e[i] is not None:
                assert g[i] == pytest.approx(e[i], rel=1e-12)
        assert g[4] <= g[3]                         # 2+ anos nunca excede as celulas
        assert g[7] is None or g[7] <= g[2]         # max_years nunca excede os anos analisados

"""Auxiliares de teste do Lote 5: constroem DataFrames sinteticos nos esquemas usados pelo L5.

Sem conftest.py. Esquemas: ver spec/metodologia_metricas.md (7B, 7E, 7F).
"""
import datetime as dt

import pandas as pd

# ---- cell_days (saida de eligible_cell_days): date, cell, instrument, satellite (sem country)
CELL_DAYS_COLUMNS = ["date", "cell", "instrument", "satellite"]


def cell_days_df(rows):
    """rows: ('YYYY-MM-DD', cell, instrument, satellite) -> DataFrame com date datetime64 e cell int64."""
    df = pd.DataFrame(rows, columns=CELL_DAYS_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["cell"] = df["cell"].astype("int64")
    return df


# ---- cell-year (saida de build_cell_year): cell, series, year, n_days
CELL_YEAR_COLUMNS = ["cell", "series", "year", "n_days"]


def cell_year_df(rows):
    """rows: (cell, series, year, n_days) -> DataFrame com cell/year/n_days int64."""
    df = pd.DataFrame(rows, columns=CELL_YEAR_COLUMNS)
    return df.astype({"cell": "int64", "year": "int64", "n_days": "int64"})


# ---- l1_cal_monthly
MONTHLY_DEFAULTS = {"cell": 1, "series": "modis", "year": 2001, "month": 3,
                    "cell_days": 0, "partial": False, "n_unknown_days": 0}
MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]


def monthly_df(rows):
    """l1_cal_monthly a partir de uma lista de dicts (so o que difere dos defeitos)."""
    recs_ = [{**MONTHLY_DEFAULTS, **r} for r in rows]
    df = pd.DataFrame.from_records(recs_, columns=list(MONTHLY_DEFAULTS))
    for c in ("cell", "year", "month", "cell_days", "n_unknown_days"):
        df[c] = df[c].astype("int64")
    df["partial"] = df["partial"].astype(bool)
    return df[MONTHLY_COLUMNS]


# ---- l1_cal_annual
ANNUAL_COLUMNS = ["cell", "year", "series", "cell_days", "partial", "n_unknown_days"]


def annual_df(rows):
    """l1_cal_annual a partir de uma lista de dicts (defeitos: celula 1, 2001, modis, 0, False, 0)."""
    defaults = {"cell": 1, "year": 2001, "series": "modis", "cell_days": 0,
                "partial": False, "n_unknown_days": 0}
    df = pd.DataFrame.from_records([{**defaults, **r} for r in rows], columns=list(defaults))
    for c in ("cell", "year", "cell_days", "n_unknown_days"):
        df[c] = df[c].astype("int64")
    df["partial"] = df["partial"].astype(bool)
    return df[ANNUAL_COLUMNS]


# ---- l1_cal_coverage
def coverage_df(rows):
    """rows: (instrument, 'YYYY-MM-DD', n_rows_global) -> l1_cal_coverage."""
    df = pd.DataFrame(rows, columns=["instrument", "date", "n_rows_global"])
    df["date"] = pd.to_datetime(df["date"])
    df["n_rows_global"] = df["n_rows_global"].astype("int64")
    return df


def calendar(inst, start, values):
    """Dias consecutivos a partir de `start` com as contagens dadas: tuplos (inst, data, n)."""
    d0 = dt.date.fromisoformat(start)
    return [(inst, (d0 + dt.timedelta(days=i)).isoformat(), v) for i, v in enumerate(values)]


# ---- processed/ (esquema do notebook 01), para o ADD-05 (`country` existe mas as metricas ignoram-no)
PROCESSED_DEFAULTS = {
    "country": "Testland", "instrument": "MODIS", "satellite": "Terra",
    "latitude": 10.05, "longitude": 20.05, "acq_date": "2020-01-01",
    "type": 0, "confidence_class": "h",
}


def processed_df(rows):
    """Linhas de processed/ com so as colunas que o ADD-05 usa (dtypes como no notebook 01:
    type=Int8, confidence_class=string, acq_date=string). `rows` = dicts com o que difere dos defeitos."""
    df = pd.DataFrame.from_records([{**PROCESSED_DEFAULTS, **r} for r in rows],
                                   columns=list(PROCESSED_DEFAULTS))
    df["type"] = pd.array(df["type"], dtype="Int8")
    for c in ("acq_date", "confidence_class"):
        df[c] = df[c].astype("string")
    return df


def recs(df, cols=None):
    """Lista de dicts com None no lugar de NA, para comparar com exatidao."""
    cols = cols or list(df.columns)
    return [{c: (None if pd.isna(r[c]) else r[c]) for c in cols} for r in df.to_dict("records")]


def tuples(df):
    """Linhas como tuplos (NA => None)."""
    return [tuple(None if pd.isna(v) else v for v in r) for r in df.itertuples(index=False, name=None)]

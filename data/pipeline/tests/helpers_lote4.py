"""Auxiliares de teste do Lote 4: constroem DataFrames no esquema das tabelas l1_* (chave `cell`)."""
import pandas as pd

MONTHLY_DEFAULTS = {"cell": 1, "series": "modis", "year": 2001, "month": 3,
                    "cell_days": 0, "partial": False, "n_unknown_days": 0}
MONTHLY_COLUMNS = ["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"]


def monthly_df(rows):
    """l1_cal_monthly a partir de uma lista de dicts (so o que difere dos defeitos)."""
    recs = [{**MONTHLY_DEFAULTS, **r} for r in rows]
    df = pd.DataFrame.from_records(recs, columns=list(MONTHLY_DEFAULTS))
    for c in ("cell", "year", "month", "cell_days", "n_unknown_days"):
        df[c] = df[c].astype("int64")
    df["partial"] = df["partial"].astype(bool)
    return df[MONTHLY_COLUMNS]


def series_rows(values, first_year=2001, **extra):
    """Uma linha mensal por valor, anos consecutivos a partir de first_year (mesmo mes)."""
    return [{"year": first_year + i, "cell_days": v, **extra} for i, v in enumerate(values)]


def recs(df, cols=None):
    """Lista de dicts com None no lugar de NA, para comparar com exatidao."""
    cols = cols or list(df.columns)
    return [{c: (None if pd.isna(r[c]) else r[c]) for c in cols} for r in df.to_dict("records")]

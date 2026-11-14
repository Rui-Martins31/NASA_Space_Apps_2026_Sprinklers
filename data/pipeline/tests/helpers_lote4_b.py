"""Auxiliares de teste do Lote 4 (parte B): tabela anual no esquema de `l1_cal_annual`."""
import pandas as pd

ANNUAL_DEFAULTS = {"country": "P", "series": "modis", "year": 2001,
                   "cell_days": 0, "partial": False, "n_unknown_days": 0}
ANNUAL_COLUMNS = ["country", "year", "series", "cell_days", "partial", "n_unknown_days"]


def annual_df(rows):
    """l1_cal_annual a partir de uma lista de dicts (so o que difere dos defeitos)."""
    recs = [{**ANNUAL_DEFAULTS, **r} for r in rows]
    df = pd.DataFrame.from_records(recs, columns=list(ANNUAL_DEFAULTS))
    for c in ("year", "cell_days", "n_unknown_days"):
        df[c] = df[c].astype("int64")
    df["partial"] = df["partial"].astype(bool)
    return df[ANNUAL_COLUMNS]


def annual_series(values, first_year=2000, **extra):
    """Uma linha anual por valor, anos consecutivos a partir de first_year."""
    return [{"year": first_year + i, "cell_days": v, **extra} for i, v in enumerate(values)]

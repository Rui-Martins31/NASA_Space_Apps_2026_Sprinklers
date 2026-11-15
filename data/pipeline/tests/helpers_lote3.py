"""Synthetic L1 output tables for L3 contract tests (key column `cell`, int64)."""

import pandas as pd

CELL = 1001            # celula "principal" dos testes; CELL + 1 faz o papel da segunda celula


def monthly(*changes):
    base = dict(cell=CELL, series="modis", year=2001, month=3,
                cell_days=10, partial=False, n_unknown_days=0)
    return pd.DataFrame([base | change for change in changes])


def annual(*changes):
    return monthly(*changes).drop(columns="month")


def daily(*changes):
    base = dict(cell=CELL, series="modis", date=pd.Timestamp("2000-02-29"), n_cells=3)
    result = pd.DataFrame([base | change for change in changes])
    result["date"] = pd.to_datetime(result["date"])
    return result


def historical_pool():
    return monthly(*[dict(year=year, cell_days=value)
                     for year, value in zip(range(2001, 2007), [10, 20, 30, 40, 50, 60])])

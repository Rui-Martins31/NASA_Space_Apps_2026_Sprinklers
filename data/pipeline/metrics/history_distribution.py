"""Metricas de distribuicao historica do Lote 4: HIS-01, HIS-02, HIS-05, HIS-06, HIS-09.

Funcoes puras sobre o esquema de `l1_cal_monthly`; a referencia vem de `history_pool`
(spec/metodologia_metricas.md, 7B e 7D):
- HIS-01/02/09: referencia FIXA (pool inteiro de [ref_start, ref_end]);
- HIS-05/06: referencia sem o ano avaliado (leave-one-out);
- abaixo de `min_ref_years` as estatisticas sao NA; desvio-padrao amostral (ddof=1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .history_pool import (
    MAX_UNKNOWN_DAYS, MIN_REF_YEARS, reference_fixed, reference_loo, valid_mask,
)

HIS01_COLUMNS = ["country", "series", "month", "n_ref_years", "median_cell_days"]
HIS02_COLUMNS = ["country", "series", "month", "n_ref_years", "p10", "p90"]
HIS05_COLUMNS = ["country", "series", "year", "month", "cell_days", "valid_month",
                 "n_ref_years", "ref_mean", "ref_std", "zscore"]
HIS06_COLUMNS = ["country", "series", "year", "month", "cell_days", "valid_month",
                 "n_ref_years", "percentile"]
HIS09_COLUMNS = ["country", "series", "year", "n_months_evaluated", "n_months_above",
                 "months_above"]
_SORT_FIXED = ["country", "series", "month"]
_SORT_LOO = ["country", "series", "year", "month"]


def _finish(table: pd.DataFrame, columns, sort_cols) -> pd.DataFrame:
    """Seleciona colunas, ordena pela chave e repoe o indice."""
    return table[columns].sort_values(sort_cols).reset_index(drop=True)


def his01_hist_median(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                      min_ref_years: int = MIN_REF_YEARS,
                      max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-01: mediana historica de cell_days por (country, series, month), referencia fixa.
    NA se n_ref_years < min_ref_years."""
    ref = reference_fixed(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    ref = ref.rename(columns={"ref_median": "median_cell_days"})
    return _finish(ref, HIS01_COLUMNS, _SORT_FIXED)


def his02_hist_band(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                    min_ref_years: int = MIN_REF_YEARS,
                    max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-02: faixa historica (p10, p90 lineares) por (country, series, month), referencia fixa.
    NA se n_ref_years < min_ref_years."""
    ref = reference_fixed(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    ref = ref.rename(columns={"ref_p10": "p10", "ref_p90": "p90"})
    return _finish(ref, HIS02_COLUMNS, _SORT_FIXED)


def his05_zscore(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                 min_ref_years: int = MIN_REF_YEARS,
                 max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-05: z-score mensal (cell_days - ref_mean)/ref_std com a referencia sem o ano avaliado.
    NA se o mes e invalido, a amostra e insuficiente ou ref_std == 0."""
    loo = reference_loo(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    if loo.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in HIS05_COLUMNS})
    std = loo["ref_std"].astype("float64")
    num = loo["cell_days"].astype("float64") - loo["ref_mean"].astype("float64")
    ok = loo["valid_month"].astype(bool) & std.notna() & (std != 0)
    z = (num / std.where(std != 0)).where(ok)
    out = loo.assign(zscore=z.astype("float64"))
    return _finish(out, HIS05_COLUMNS, _SORT_LOO)


def his06_percentile(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                     min_ref_years: int = MIN_REF_YEARS,
                     max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-06: percentil historico 100*(n_below + 0,5*n_equal)/n_ref_years, referencia sem o
    ano avaliado. NA se o mes e invalido ou a amostra e insuficiente (n_below NA)."""
    loo = reference_loo(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    if loo.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in HIS06_COLUMNS})
    below = loo["n_below"].astype("Float64")
    equal = loo["n_equal"].astype("Float64")
    n = loo["n_ref_years"].astype("Float64")
    pct = (100.0 * (below + 0.5 * equal) / n).astype("float64")
    pct = pct.where(below.notna().to_numpy(), np.nan)
    out = loo.assign(percentile=pct.to_numpy(dtype="float64", na_value=np.nan))
    return _finish(out, HIS06_COLUMNS, _SORT_LOO)


def his09_months_above(monthly: pd.DataFrame, ref_start=None, ref_end=None,
                       min_ref_years: int = MIN_REF_YEARS,
                       max_unknown_days: int = MAX_UNKNOWN_DAYS) -> pd.DataFrame:
    """HIS-09: por (country, series, year), meses validos com cell_days > p90 (ESTRITO).
    Referencia FIXA (HIS-02), mesmo que o ano avaliado esteja dentro da janela.
    n_months_evaluated = meses validos com p90 definido; months_above = "3,4" (vazio se nenhum)."""
    band = his02_hist_band(monthly, ref_start, ref_end, min_ref_years, max_unknown_days)
    if monthly.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in HIS09_COLUMNS})
    m = monthly[["country", "series", "year", "month", "cell_days"]].assign(
        valid_month=valid_mask(monthly, max_unknown_days).to_numpy()).merge(
        band[["country", "series", "month", "p90"]], on=["country", "series", "month"], how="left")
    evaluated = m["valid_month"].astype(bool) & m["p90"].notna()
    above = evaluated & (m["cell_days"].astype("float64") > m["p90"])
    rows = []
    for (country, series, year), idx in m.groupby(["country", "series", "year"], sort=False, observed=True).groups.items():
        ev = evaluated.loc[idx]
        ab = above.loc[idx]
        months = sorted(int(x) for x in m.loc[idx][ab.to_numpy()]["month"])
        rows.append({"country": country, "series": series, "year": year,
                     "n_months_evaluated": int(ev.sum()), "n_months_above": int(ab.sum()),
                     "months_above": ",".join(str(x) for x in months)})
    out = pd.DataFrame(rows, columns=HIS09_COLUMNS)
    out["year"] = out["year"].astype("int64")
    return _finish(out, HIS09_COLUMNS, ["country", "series", "year"])

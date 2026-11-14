"""Integracao opcional do Lote 1 com a amostra real modis_2000 (gerada pelo notebook 01).

Corre so se SPRINKLERS_SAMPLE_PARQUET apontar para o ficheiro. Esperado (verificado no
notebook 01): 261 363 linhas, 163 paises, 0 horas invalidas, so o satelite Terra.
"""
import os
from pathlib import Path

import pandas as pd
import pytest

from metrics.calendar_metrics import (
    cal_annual, cal_coverage, cal_daily, cal_monthly, eligible_cell_days, global_day_counts,
)
from metrics.counts import (
    obs01_raw_counts, obs02_confidence_dist, obs03_filtered_counts, qa02_retention,
    qa03_cellday_grouped, qa04_redundancy,
)

PATH = os.environ.get("SPRINKLERS_SAMPLE_PARQUET", "")
pytestmark = pytest.mark.skipif(not (PATH and Path(PATH).exists()),
                                reason="defina SPRINKLERS_SAMPLE_PARQUET=<modis_2000.parquet>")


@pytest.fixture(scope="module")
def sample():
    return pd.read_parquet(PATH)


def test_sample_known_totals(sample):
    assert len(sample) == 261_363
    assert sample["country"].nunique() == 163
    assert obs01_raw_counts(sample)["n_raw"].sum() == 261_363
    assert set(sample["satellite"]) == {"Terra"}


def test_counts_are_consistent_on_real_data(sample):
    n_raw = obs01_raw_counts(sample)["n_raw"].sum()
    n_elig = obs03_filtered_counts(sample)["n_eligible"].sum()
    assert 0 < n_elig < n_raw
    assert abs(obs02_confidence_dist(sample)["n"].sum() - n_raw) == 0
    q2 = qa02_retention(sample)
    assert q2["pct_retained"].between(0, 100).all()
    q3 = qa03_cellday_grouped(sample)
    assert (q3["n_grouped"] >= 0).all() and q3["n_eligible"].sum() == n_elig
    assert (qa04_redundancy(sample)["n_redundant"] == 0).all()       # so Terra em 2000


def test_calendar_totals_are_consistent_on_real_data(sample):
    daily = cal_daily(eligible_cell_days(sample))
    cov = cal_coverage(global_day_counts(sample))
    monthly = cal_monthly(daily, cov, sorted(sample["country"].unique()))
    annual = cal_annual(monthly)
    for s in ("modis", "combined"):
        d = daily.loc[daily["series"] == s, "n_cells"].sum()
        assert monthly.loc[monthly["series"] == s, "cell_days"].sum() == d
        assert annual.loc[annual["series"] == s, "cell_days"].sum() == d
    assert (daily.loc[daily["series"] == "modis", "n_cells"].sum()
            == daily.loc[daily["series"] == "combined", "n_cells"].sum())     # sem VIIRS: iguais
    assert annual.loc[annual["series"] == "modis", "partial"].all()           # 2000 comeca em novembro
    assert cov["date"].min() == pd.Timestamp("2000-11-01")

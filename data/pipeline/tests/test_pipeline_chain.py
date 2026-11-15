"""Cadeia completa 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 08 sobre dados `processed/` sinteticos.

Cada notebook ja tem testes proprios, mas com entradas L1 escritas a mao. Aqui cada notebook le o que o
anterior REALMENTE gravou, para apanhar incompatibilidades de esquema, particoes, tipos ou nomes entre
notebooks. Os valores sao poucos e pequenos; o objetivo e a cadeia correr sem erro e ser consistente.
"""
import ast
import contextlib
import io
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from metrics.common import GLOBAL_CELL, cell_key
from metrics.store import ParquetSink

REPO = Path(__file__).resolve().parents[3]
NOTEBOOKS = {
    "02": "02_metrics_lote1", "03": "03_metrics_lote2", "04": "04_metrics_lote3", "05": "05_metrics_lote4",
    "06": "06_metrics_lote5", "07": "07_metrics_lote6", "08": "08_metrics_lote7",
}
YEARS = [2018, 2019, 2020, 2021, 2022, 2023]
CELL_A, CELL_B, CELL_C = (10.005, 20.005), (10.055, 20.005), (-33.995, 151.205)
GRID = 0.01


def tagged_cells(key):
    notebook = json.loads((REPO / f"data/pipeline/notebooks/{NOTEBOOKS[key]}.ipynb").read_text(encoding="utf-8"))
    cells, plain = [], []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        ast.parse(source)
        plain.append(source)
        if source.startswith("# cell: "):
            cells.append((source.splitlines()[0][len("# cell: "):], source))
    # notebook 03 nao tem etiquetas: todas as celulas depois do bootstrap, por ordem
    return cells or [(f"cell{i}", source) for i, source in enumerate(plain) if i > 0]


def make_processed(root):
    processed = root / "processed"
    processed.mkdir()
    for sensor, instrument, satellite, step in [("modis", "MODIS", "Terra", 3), ("viirs-jpss1", "VIIRS", "N20", 2)]:
        for year in YEARS:
            days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
            rows = []
            for i, day in enumerate(days):
                d = day.strftime("%Y-%m-%d")
                rows.append((CELL_A, d, "h"))                                   # cobertura global diaria completa
                if i % step == 0:
                    rows.append((CELL_B, d, "n"))
                if day.month == 1 and year in (2019, 2021):
                    rows.append((CELL_C, d, "h"))
                if i % 17 == 0:
                    rows.append((CELL_B, d, "l"))                               # baixa confianca: nao elegivel
            dates = [r[1] for r in rows]
            frame = pd.DataFrame(dict(
                country="Testland", source_file=f"{sensor}_{year}_Testland.csv", instrument=instrument,
                satellite=satellite, version="6.2",
                latitude=[r[0][0] for r in rows], longitude=[r[0][1] for r in rows], acq_date=dates,
                acq_time="1200", acq_datetime_utc=pd.to_datetime([f"{d} 12:00" for d in dates], utc=True),
                daynight="D", type=pd.Series([0] * len(rows), dtype="Int8"),
                confidence_raw="h", confidence_class=pd.Series([r[2] for r in rows], dtype="string"),
                brightness_primary=330.0, brightness_primary_band="brightness",
                brightness_aux=300.0, brightness_aux_band="bright_t31",
                scan=1.0, track=1.0, pixel_area_km2=1.0, frp=5.0))
            frame.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    metrics = root / "metrics"
    metrics.mkdir()
    return processed, metrics


def run_notebook(key, processed, metrics, overrides=None, skip=("diagnostic",)):
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=REPO, ROOT=processed.parent,
                     subprocess=subprocess, display=lambda value: None)
    overrides = overrides or {}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for tag, source in tagged_cells(key):
            if tag in skip:
                continue
            exec(source, namespace)
            if tag == "params":
                namespace.update(overrides)
    return namespace, out.getvalue()


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    root = tmp_path_factory.mktemp("chain")
    processed, metrics = make_processed(root)
    small = dict(CHUNK_CELLS=2)
    stats = dict(CHUNK_CELLS=2, MIN_ACTIVE_YEARS=1)
    namespaces = {}
    namespaces["02"], _ = run_notebook("02", processed, metrics, dict(MIN_ACTIVE_YEARS=1))
    namespaces["03"], _ = run_notebook("03", processed, metrics)
    namespaces["04"], _ = run_notebook("04", processed, metrics, stats)
    namespaces["05"], _ = run_notebook("05", processed, metrics, dict(stats, MIN_TREND_YEARS=3))
    namespaces["06"], _ = run_notebook("06", processed, metrics, small)
    namespaces["07"], _ = run_notebook("07", processed, metrics, small)
    namespaces["08"], _ = run_notebook("08", processed, metrics, small)
    return metrics, ParquetSink(metrics), namespaces


def test_every_notebook_registers_its_run_last_and_leaves_no_temp_folders(chain):
    metrics, sink, _ = chain
    runs = sink.read("_runs")
    assert runs["lote"].tolist() == ["lote1", "lote2", "lote3", "lote4", "lote5", "lote6", "lote7"]
    assert (runs["grid_deg"] == GRID).all()
    for _, row in runs.iterrows():
        for name in json.loads(row["tables"]):
            assert sink.exists(name), f"{row['lote']} registou {name} mas a tabela nao existe"
    assert not [p for p in metrics.rglob("*") if p.name.endswith((".tmp", ".old"))]


def test_l1_tables_have_the_cell_schema_and_expected_cells(chain):
    _, sink, _ = chain
    monthly = sink.read("l1_cal_monthly")
    assert {"cell", "ilat", "ilon", "lat", "lon", "lat_band", "year", "month", "series", "cell_days"} <= set(monthly.columns)
    assert "partial" not in monthly.columns and "country" not in monthly.columns
    cells = {int(cell_key([lat], [lon], GRID)[0]) for lat, lon in (CELL_A, CELL_B, CELL_C)}
    assert set(monthly["cell"]) == cells
    assert (monthly["cell_days"] > 0).all()                                   # esparso
    # celula A: um registo por dia => cell_days = dias do mes
    a = monthly[(monthly["cell"] == int(cell_key([CELL_A[0]], [CELL_A[1]], GRID)[0])) & (monthly["series"] == "combined")]
    assert a[(a["year"] == 2020) & (a["month"] == 2)]["cell_days"].tolist() == [29]
    assert sink.read("l1_meta_month_validity")["partial"].dtype == bool


def test_l1_annual_equals_sum_of_monthly(chain):
    _, sink, _ = chain
    monthly, annual = sink.read("l1_cal_monthly"), sink.read("l1_cal_annual")
    expected = monthly.groupby(["cell", "year", "series"], as_index=False)["cell_days"].sum()
    got = annual[["cell", "year", "series", "cell_days"]]
    key = ["cell", "year", "series"]
    pd.testing.assert_frame_equal(got.sort_values(key).reset_index(drop=True),
                                  expected.sort_values(key).reset_index(drop=True), check_dtype=False)


def test_statistics_notebooks_read_the_real_l1_output(chain):
    _, sink, _ = chain
    his03 = sink.read("l3_his03_anomaly_abs")
    cell_a = int(cell_key([CELL_A[0]], [CELL_A[1]], GRID)[0])
    row = his03[(his03["cell"] == cell_a) & (his03["series"] == "combined") & (his03["year"] == 2020) & (his03["month"] == 1)]
    # janeiro tem sempre 31 celula-dias na celula A => referencia 31 e anomalia 0 (6 anos validos >= MIN_REF_YEARS)
    assert row["cell_days"].tolist() == [31] and row["anomaly_abs"].tolist() == [0.0]
    assert sink.read("l4_his01_hist_median")["cell"].nunique() == 3
    assert not sink.read("l3_cal05_total_period").empty and not sink.read("l4_his05_zscore").empty
    assert set(sink.read("l4_add01_active_satellites")["instrument"]) == {"MODIS", "VIIRS"}


def test_recurrence_and_cell_year_agree_with_l1(chain):
    _, sink, _ = chain
    cell_year = sink.read("l5_cell_year")
    annual = sink.read("l1_cal_annual")
    key = ["cell", "series", "year"]
    a = cell_year.merge(annual, on=key, how="outer", suffixes=("_cy", "_l1"), indicator=True)
    assert (a["_merge"] == "both").all() and (a["n_days"] == a["cell_days"]).all()
    assert sink.read("l5_esp06_interannual")["cell"].eq(GLOBAL_CELL).all()
    add05 = sink.read("l5_add05_type_sensitivity")
    assert GLOBAL_CELL in set(add05["cell"])


def test_harmonization_chain_has_the_global_factor_row_and_runs(chain):
    _, sink, _ = chain
    factor = sink.read("l6_har06_factor")
    assert GLOBAL_CELL in set(factor["cell"]) and "scope" in factor.columns
    g = factor[factor["cell"] == GLOBAL_CELL].iloc[0]
    assert g["scope"] == "global" and g["n_cal_months"] == 48                  # 2018-2021
    assert not sink.read("l6_har01_overlap").empty
    assert set(sink.read("l7_har08_mae").columns) >= {"cell", "period"}
    step = sink.read("l7_har12_residual_step")
    assert step["cell"].tolist() == [GLOBAL_CELL] and step["status"].tolist() == ["requires_snpp_inputs"]


def test_queries_by_area_work_on_the_real_published_tables(chain):
    metrics, _, _ = chain
    import importlib.util
    spec = importlib.util.spec_from_file_location("query_area", REPO / "data/pipeline/scripts/query_area.py")
    query = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(query)
    near_a = query.area_monthly_series(metrics, "l1_cal_monthly", 10.01, 20.01, 2, "combined")
    # so a celula A (cobre todos os dias): 365/366 dias por ano somados nos meses
    assert near_a.groupby("year")["cell_days"].sum().to_dict() == {y: (366 if y % 4 == 0 else 365) for y in YEARS}
    big = query.area_monthly_series(metrics, "l1_cal_monthly", 10.03, 20.0, 20, "combined")
    assert big["n_cells"].max() == 2                                           # A e B, nao C

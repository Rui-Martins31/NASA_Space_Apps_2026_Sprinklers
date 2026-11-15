"""Testes do notebook 05 (L4, por celula): executam as celulas reais sobre tabelas L1 sinteticas.

Usa o mesmo mundo sintetico de test_notebook_lote3.py (celulas A, C, B, D; marco de A com 5, 10, 15, 20, 25, 30
celulas-dia em 2001..2006; julho de 2003 sem cobertura em 2 dias, logo invalido), mais `l1_obs01_raw_counts`
e `l1_cal_coverage` para ADD-01/ADD-02. HIS-10 usa MIN_TREND_YEARS = 5 (o mundo so tem 6 anos, 5 deles validos).
"""
import json
import shutil

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

from metrics.store import ParquetSink  # noqa: E402
from test_notebook_lote3 import (  # noqa: E402
    A, B, C, cell_of, one, pick, prepare as prepare_world, run_all, snapshot, write_l1, world_cell_days,
)

NOTEBOOK = "05_metrics_lote4.ipynb"
SLICE_TABLES = {
    "l4_his01_hist_median", "l4_his02_hist_band", "l4_his05_zscore", "l4_his06_percentile",
    "l4_his07_ytd", "l4_his08_yoy", "l4_his09_months_above", "l4_his10_trend",
}
GLOBAL_TABLES = {"l4_add01_active_satellites", "l4_add02_zero_days"}
L4_TABLES = SLICE_TABLES | GLOBAL_TABLES
CELL_COLUMNS = {"cell", "ilat", "ilon", "lat", "lon", "lat_band"}


def prepare(tmp_path, **world):
    source, metrics, sink, namespace = prepare_world(tmp_path, notebook=NOTEBOOK, **world)
    namespace["MIN_TREND_YEARS"] = 5
    return source, metrics, sink, namespace


def test_notebook_has_the_expected_parameters_and_tags(tmp_path):
    source, _, _, namespace = prepare_world(tmp_path, notebook=NOTEBOOK)
    assert set(source) == {"params", "defs", "run", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01 and namespace["STATS_GRID_DEG"] == namespace["GRID_DEG"]
    assert (namespace["MIN_ACTIVE_YEARS"], namespace["CHUNK_CELLS"], namespace["MIN_TREND_YEARS"]) == (5, 20000, 8)
    assert (namespace["REF_START"], namespace["REF_END"], namespace["MIN_REF_YEARS"]) == (None, None, 5)
    assert (namespace["MAX_UNKNOWN_DAYS"], namespace["FORCE"]) == (0, False)
    text = "".join(source.values())
    for obsolete in ("atomic_write", "_log_lote4", "_params_lote4", "country", "pd.read_parquet(METRICS"):
        assert obsolete not in text


def test_roundtrip_values_ordering_and_clean_outputs(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    before = snapshot(metrics)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert {n for n in sink.names() if n.startswith("l4_")} == L4_TABLES
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))
    assert snapshot(metrics) == before                                              # entradas L1 intactas
    for name in SLICE_TABLES:
        table = sink.read(name)
        assert CELL_COLUMNS <= set(table.columns) and "country" not in table.columns
        assert set(table["cell"]) == {cell_of(A), cell_of(C)}                      # B e D podadas
        for _, part in table.groupby(["series", "lat_band"]):
            pairs = list(zip(part["ilat"], part["ilon"]))
            assert pairs == sorted(pairs)
    for name in GLOBAL_TABLES:                                                      # globais: sem colunas de celula
        assert not (CELL_COLUMNS & set(sink.read(name).columns))
    a, c = cell_of(A), cell_of(C)
    # HIS-01/02 (referencia fixa; julho de 2003 invalido deixa 5 anos)
    h1 = sink.read("l4_his01_hist_median")
    row = one(h1, cell=a, series="modis", month=3)
    assert (row.n_ref_years, row.median_cell_days) == (6, 17.5)
    assert (one(h1, cell=a, series="modis", month=7).n_ref_years, one(h1, cell=a, series="modis", month=7).median_cell_days) == (5, 0.0)
    row = one(sink.read("l4_his02_hist_band"), cell=a, series="modis", month=3)
    assert (row.p10, row.p90) == (7.5, 27.5)
    # HIS-05/06 (referencia sem o ano avaliado)
    z = sink.read("l4_his05_zscore")
    row = one(z, cell=a, series="modis", year=2006, month=3)
    assert (row.cell_days, row.n_ref_years, row.ref_mean) == (30, 5, 15.0)
    assert row.ref_std == pytest.approx(np.sqrt(62.5)) and row.zscore == pytest.approx(15 / np.sqrt(62.5))
    assert pd.isna(one(z, cell=c, series="modis", year=2004, month=3).zscore)       # desvio-padrao 0
    p = sink.read("l4_his06_percentile")
    assert [one(p, cell=a, series="modis", year=y, month=3).percentile for y in (2001, 2003, 2006)] == [0.0, 40.0, 100.0]
    assert one(p, cell=c, series="modis", year=2004, month=3).percentile == 50.0   # empates valem meio
    assert pd.isna(one(p, cell=a, series="modis", year=2003, month=7).percentile)  # mes invalido
    # HIS-07/08
    y = sink.read("l4_his07_ytd")
    row = one(y, cell=a, series="modis", year=2006, month=3)
    assert (row.ytd_cell_days, bool(row.comparable), row.n_ref_years, row.ref_ytd_mean, row.ytd_diff) == (30, True, 5, 15.0, 15.0)
    assert not one(y, cell=a, series="modis", year=2003, month=7).comparable
    yo = sink.read("l4_his08_yoy")
    row = one(yo, cell=a, series="modis", year=2002, month=3)
    assert (row.prev_cell_days, bool(row.valid_pair), row.diff_abs, row.yoy_pct) == (5, True, 5, 100.0)
    row = one(yo, cell=a, series="modis", year=2004, month=3)
    assert (row.prev_cell_days, row.diff_abs) == (15, 5) and row.yoy_pct == pytest.approx(100 * 5 / 15)
    assert not one(yo, cell=a, series="modis", year=2001, month=3).valid_pair
    assert not one(yo, cell=a, series="modis", year=2004, month=7).valid_pair      # julho de 2003 invalido
    # HIS-09
    h9 = sink.read("l4_his09_months_above")
    row = one(h9, cell=a, series="modis", year=2006)
    assert (row.n_months_evaluated, row.n_months_above, row.months_above) == (12, 1, "3")
    assert one(h9, cell=a, series="modis", year=2003).n_months_evaluated == 11
    assert one(h9, cell=c, series="modis", year=2004).n_months_above == 0
    # HIS-10 (2003 invalido: 5 anos validos; todos os declives dos pares valem 5)
    tr = sink.read("l4_his10_trend")
    row = one(tr, cell=a, series="modis")
    assert (row.n_years, row.first_year, row.last_year, row.slope_per_year, row.intercept) == (5, 2001, 2006, 5.0, -10000.0)
    assert (row.slope_p025, row.slope_p975) == (5.0, 5.0)
    row = one(tr, cell=c, series="combined")
    assert (row.slope_per_year, row.intercept) == (0.0, 7.0)
    # ADD-01 (soma de n_raw de todas as celulas) e ADD-02 (cobertura global)
    a1 = sink.read("l4_add01_active_satellites")
    assert a1.to_dict("records") == [
        dict(instrument="MODIS", year=2003, month=3, n_satellites=2, satellites="Aqua,Terra"),
        dict(instrument="VIIRS", year=2004, month=6, n_satellites=1, satellites="N20")]
    a2 = sink.read("l4_add02_zero_days")
    assert len(a2) == 72 and set(a2.instrument) == {"MODIS"}
    row = one(a2, year=2003, month=7)
    assert (row.n_days, row.n_zero_days) == (31, 2) and row.pct_zero_days == pytest.approx(100 * 2 / 31)
    assert one(a2, year=2001, month=1).n_zero_days == 0
    # _runs
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote1", "lote4"]
    row = runs[runs.lote == "lote4"].iloc[0]
    assert row.grid_deg == 0.01 and set(json.loads(row.tables)) == L4_TABLES
    assert json.loads(row.tables)["l4_add02_zero_days"] == 72
    params = json.loads(row.params)
    assert params["min_trend_years"] == 5 and params["min_active_years"] == 5 and params["n_active_cells"] == 2


def test_dense_row_counts_and_cells_match_the_l1_tables(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    n_months = int(sink.read("l1_meta_month_validity").groupby("series").size().sum())     # modis + combined
    for name in ("l4_his05_zscore", "l4_his06_percentile", "l4_his07_ytd", "l4_his08_yoy"):
        assert len(sink.read(name)) == 2 * n_months                                       # 2 celulas ativas
    assert len(sink.read("l4_his01_hist_median")) == 2 * 2 * 12                           # celula x serie x mes
    assert len(sink.read("l4_his10_trend")) == 2 * 2
    obs = sink.read("l1_obs01_raw_counts")                                                 # ADD-01 reconstroi-se a partir das celulas
    assert obs.groupby(["instrument", "year", "month"]).n_raw.sum().gt(0).sum() == len(sink.read("l4_add01_active_satellites"))


def test_small_chunks_give_the_same_tables_and_min_active_years_controls_pruning(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source)
    reference = {n: ParquetSink(metrics).read(n) for n in L4_TABLES}
    namespace.update(CHUNK_CELLS=1)
    run_all(namespace, source)
    assert sorted(p.name for p in (metrics / "_partial_lote4").iterdir()) == ["b10_c0", "b10_c1"]
    for name, table in reference.items():
        keys = [c for c in ("cell", "instrument", "series", "year", "month") if c in table.columns]
        pd.testing.assert_frame_equal(ParquetSink(metrics).read(name).sort_values(keys).reset_index(drop=True),
                                      table.sort_values(keys).reset_index(drop=True))
    namespace.update(MIN_ACTIVE_YEARS=2, MIN_TREND_YEARS=2)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert sorted(p.name for p in (metrics / "_partial_lote4").iterdir()) == ["b10_c0", "b10_c1", "b13_c0"]
    b = cell_of(B)
    assert set(sink.read("l4_his01_hist_median").cell) == {cell_of(A), cell_of(C), b}
    row = one(sink.read("l4_his10_trend"), cell=b, series="modis")                     # anos validos 2001, 02, 04, 05, 06: 0, 3, 0, 0, 0
    assert (row.n_years, row.slope_per_year, row.intercept) == (5, 0.0, 0.0)
    assert row.slope_p025 == pytest.approx(-1.3875) and row.slope_p975 == pytest.approx(2.325)   # dos 10 declives dos pares
    assert one(sink.read("l4_his01_hist_median"), cell=b, series="modis", month=3).n_ref_years == 6
    assert set(sink.read("l4_his05_zscore").lat_band) == {10, 13}


def test_resume_reuses_slices_and_invalidates_on_changes(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace.update(CHUNK_CELLS=1)
    run_all(namespace, source)
    part = metrics / "_partial_lote4"
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    assert len(files) == 2 * len(SLICE_TABLES)
    run_all(namespace, source)
    assert {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")} == files
    (part / "b10_c1" / "l4_his10_trend.parquet").unlink()                                # saida em falta
    run_all(namespace, source)
    now = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    assert all(now[p] != files[p] for p in files if p.parent.name == "b10_c1")
    assert all(now[p] == files[p] for p in files if p.parent.name == "b10_c0")           # a outra fatia nao se refaz
    files = now
    namespace["MIN_TREND_YEARS"] = 6                                                      # so afeta HIS-10, mas e parametro da fatia
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)
    assert pd.isna(one(ParquetSink(metrics).read("l4_his10_trend"), cell=cell_of(A), series="modis").slope_per_year)
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    namespace["FORCE"] = True
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)
    namespace["FORCE"] = False
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    write_l1(metrics, cell_days=world_cell_days().iloc[:-5])                              # o notebook 02 refez o L1
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)


def test_stats_grid_uses_the_stats_tables_and_the_coarser_cells(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path, stats_grid=0.1)
    namespace["STATS_GRID_DEG"] = 0.1
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert set(sink.read("l4_his01_hist_median").cell) == {cell_of(A, 0.1), cell_of(C, 0.1)}
    assert one(sink.read("l4_his01_hist_median"), cell=cell_of(A, 0.1), series="modis", month=3).median_cell_days == 17.5
    assert one(sink.read("l4_his10_trend"), cell=cell_of(A, 0.1), series="modis").slope_per_year == 5.0
    assert len(sink.read("l4_add01_active_satellites")) == 2                            # ADD-01 vem de obs01 a GRID_DEG
    params = json.loads(sink.read("_runs").params.iloc[1])
    assert params["stats_grid_deg"] == 0.1 and "l1_stats_cal_monthly" in params["inputs"]


def test_grid_must_match_the_lote1_run(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace.update(GRID_DEG=0.1, STATS_GRID_DEG=0.1)
    with pytest.raises(ValueError, match="grid_deg=0.01"):
        run_all(namespace, source, ("defs", "run"))
    assert not (metrics / "_partial_lote4").exists()


@pytest.mark.parametrize("missing", ["l1_cal_monthly", "l1_cal_annual", "l1_meta_month_validity",
                                     "l1_meta_year_validity", "l1_obs01_raw_counts", "l1_cal_coverage"])
def test_missing_l1_input_fails_clearly_and_writes_nothing(tmp_path, missing):
    source, metrics, sink, namespace = prepare(tmp_path)
    shutil.rmtree(metrics / missing)
    with pytest.raises(FileNotFoundError, match=f"02_metrics_lote1.*{missing}"):
        run_all(namespace, source, ("defs", "run"))
    assert not (metrics / "_partial_lote4").exists()
    assert not any(n.startswith("l4_") for n in ParquetSink(metrics).names())


def test_runs_is_written_last_and_a_failing_slice_leaves_no_run(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source, ("defs",))
    seen = []
    original = namespace["write_run"]
    namespace["write_run"] = lambda sink, *a, **k: (seen.append(set(sink.names())), original(sink, *a, **k))[1]
    run_all(namespace, source, ("run", "publish", "verify"))
    assert len(seen) == 1 and L4_TABLES <= seen[0]                    # quando _runs e chamado ja existem as 10 tabelas
    assert ParquetSink(metrics).read("_runs").lote.tolist() == ["lote1", "lote4"]
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    source, metrics, sink, namespace = prepare(fresh)
    namespace.update(CHUNK_CELLS=1)
    run_all(namespace, source, ("defs",))
    original_compute, calls = namespace["compute"], []

    def exploding(monthly, annual):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("falha simulada")
        return original_compute(monthly, annual)

    namespace["compute"] = exploding
    with pytest.raises(RuntimeError, match="falha simulada"):
        run_all(namespace, source, ("run", "publish", "verify"))
    assert ParquetSink(metrics).read("_runs").lote.tolist() == ["lote1"]
    assert not any(n.startswith("l4_") for n in ParquetSink(metrics).names())
    namespace["compute"] = original_compute                           # retoma: a 1a fatia ja estava feita
    done = (metrics / "_partial_lote4" / "b10_c0" / "_done.json").stat().st_mtime_ns
    run_all(namespace, source, ("run", "publish", "verify"))
    assert (metrics / "_partial_lote4" / "b10_c0" / "_done.json").stat().st_mtime_ns == done
    assert ParquetSink(metrics).read("_runs").lote.tolist() == ["lote1", "lote4"]
    assert {n for n in ParquetSink(metrics).names() if n.startswith("l4_")} == L4_TABLES


def test_no_active_cells_still_publishes_global_tables_and_empty_cell_tables(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path, cell_days=world_cell_days().iloc[:0])
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    for name in SLICE_TABLES:
        table = sink.read(name)
        assert len(table) == 0 and {"cell", "ilat", "ilon", "lat", "lon", "lat_band", "series"} <= set(table.columns)
    assert len(sink.read("l4_add01_active_satellites")) == 2 and len(sink.read("l4_add02_zero_days")) == 72
    tables = json.loads(sink.read("_runs").tables.iloc[1])
    assert tables == {**{n: 0 for n in SLICE_TABLES}, "l4_add01_active_satellites": 2, "l4_add02_zero_days": 72}


def test_empty_obs01_gives_an_empty_add01(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path, obs01=pd.DataFrame(
        {"cell": pd.Series(dtype="int64"), "year": pd.Series(dtype="int64"), "month": pd.Series(dtype="int64"),
         "instrument": pd.Series(dtype="string"), "satellite": pd.Series(dtype="string"),
         "n_raw": pd.Series(dtype="int64")}))
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    add01 = sink.read("l4_add01_active_satellites")
    assert len(add01) == 0 and list(add01.columns) == ["instrument", "year", "month", "n_satellites", "satellites"]
    assert len(pick(sink.read("l4_his01_hist_median"), cell=cell_of(A))) == 2 * 12

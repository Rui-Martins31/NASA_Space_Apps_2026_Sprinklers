"""Testes do notebook 04 (L3, por celula): executam as celulas reais sobre tabelas L1 sinteticas.

Mundo sintetico (grelha 0.01, MODIS, cobertura global diaria 2001-2006 exceto 2003-07-14/15):
  A (10.05, 20.05) : marco com 5, 10, 15, 20, 25, 30 celulas-dia em 2001..2006 (faixa 10)
  C (10.05, 20.15) : marco com 7 celulas-dia todos os anos (faixa 10, a mesma faixa de A)
  B (40.05, -3.05) : marco de 2002 e 2003 com 3 celulas-dia (so 2 anos ativos: podada com 5; faixa 13)
  D (50.05,  5.05) : so 2004 (1 ano ativo: podada sempre; faixa 14)
Julho de 2003 tem 2 dias de cobertura desconhecida, logo o ano 2003 e julho de 2003 sao invalidos.
"""
import ast
import contextlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

from metrics import common  # noqa: E402
from metrics.calendar_metrics import (  # noqa: E402
    cal_annual, cal_monthly, coarsen_cell_days, month_validity, year_validity,
)
from metrics.common import GLOBAL_CELL, cell_key  # noqa: E402
from metrics.store import ParquetSink, write_run, write_table  # noqa: E402

NOTEBOOK = "04_metrics_lote3.ipynb"
L3_TABLES = {
    "l3_cal05_total_period", "l3_cal06_peak_month", "l3_cal07_peak_year", "l3_cal08_annual_mean",
    "l3_cal09_monthly_mean", "l3_cal12_seasonal_profile", "l3_his03_anomaly_abs", "l3_his04_anomaly_pct",
}
CELL_COLUMNS = {"cell", "ilat", "ilon", "lat", "lon", "lat_band"}
A, C, B, D = (10.05, 20.05), (10.05, 20.15), (40.05, -3.05), (50.05, 5.05)
YEARS = range(2001, 2007)


# --------------------------------------------------------------------------- notebook e mundo
def notebook_cells(name=NOTEBOOK):
    """(repo, {tag: codigo}) com as celulas de codigo etiquetadas por `# cell: <tag>`."""
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks" / name).read_text(encoding="utf-8"))
    sources = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        ast.parse(source)
        assert cell["outputs"] == [] and cell["execution_count"] is None      # notebook limpo
        if source.startswith("# cell: "):
            sources[source.splitlines()[0][len("# cell: "):]] = source
    return repo, sources


def cell_of(point, grid=0.01):
    return int(cell_key([point[0]], [point[1]], grid)[0])


def cell_days_of(point, per_year, month=3, grid=0.01):
    """Celulas-dia (esquema de `eligible_cell_days`): `per_year` = {ano: n}, dias 1..n do mes."""
    rows = [(pd.Timestamp(year, month, day), "MODIS", "Terra") for year, n in per_year.items() for day in range(1, n + 1)]
    out = pd.DataFrame(rows, columns=["date", "instrument", "satellite"])
    out.insert(1, "cell", cell_of(point, grid))
    return out[["date", "cell", "instrument", "satellite"]]


def world_cell_days():
    return pd.concat([
        cell_days_of(A, dict(zip(YEARS, [5, 10, 15, 20, 25, 30]))),
        cell_days_of(C, {year: 7 for year in YEARS}),
        cell_days_of(B, {2002: 3, 2003: 3}),
        cell_days_of(D, {2004: 5}),
    ], ignore_index=True)


def world_coverage():
    days = pd.date_range("2001-01-01", "2006-12-31")
    coverage = pd.DataFrame(dict(instrument="MODIS", date=days, n_rows_global=1))
    coverage.loc[coverage["date"].isin(pd.to_datetime(["2003-07-14", "2003-07-15"])), "n_rows_global"] = 0
    return coverage


def world_obs01():
    """Contagens brutas por celula: MODIS 2003-03 tem Terra (5 + 3), Aqua (0 + 1: so ativo somando as celulas) e
    um satelite sem nenhuma observacao; VIIRS 2004-06 tem N20 (celula B)."""
    rows = [(cell_of(A), 2003, 3, "MODIS", "Terra", 5), (cell_of(C), 2003, 3, "MODIS", "Terra", 3),
            (cell_of(A), 2003, 3, "MODIS", "Aqua", 0), (cell_of(C), 2003, 3, "MODIS", "Aqua", 1),
            (cell_of(A), 2003, 3, "MODIS", "Zero", 0), (cell_of(B), 2004, 6, "VIIRS", "N20", 2)]
    return pd.DataFrame(rows, columns=["cell", "year", "month", "instrument", "satellite", "n_raw"])


def write_l1(metrics, grid=0.01, stats_grid=None, cell_days=None, with_runs=True, obs01=None):
    """Grava as tabelas L1 que o notebook 02 publicaria (com as funcoes reais de calendar_metrics)."""
    cell_days = world_cell_days() if cell_days is None else cell_days
    coverage = world_coverage()
    sink = ParquetSink(metrics)
    monthly = cal_monthly(cell_days, coverage)
    validity = month_validity(coverage)
    tables = {"l1_cal_monthly": monthly, "l1_cal_annual": cal_annual(monthly)}
    if stats_grid is not None:
        s_monthly = cal_monthly(coarsen_cell_days(cell_days, grid, stats_grid), coverage)
        tables.update(l1_stats_cal_monthly=s_monthly, l1_stats_cal_annual=cal_annual(s_monthly))
    for name, table in tables.items():
        write_table(sink, name, table, grid_deg=stats_grid if "stats" in name else grid)
    for name, table in {"l1_meta_month_validity": validity, "l1_meta_year_validity": year_validity(validity),
                        "l1_cal_coverage": coverage,
                        "l1_obs01_raw_counts": world_obs01() if obs01 is None else obs01}.items():
        write_table(sink, name, table, grid_deg=grid, partition_by=[] if "obs01" not in name else None)
    if with_runs:
        write_run(sink, "lote1", grid_deg=grid, tables={}, params=dict(grid_deg=grid, stats_grid_deg=stats_grid or grid))
    return sink


def new_namespace(repo, metrics, **overrides):
    return dict(METRICS=metrics, REPO=repo, display=lambda value: None, **overrides)


def prepare(tmp_path, notebook=NOTEBOOK, **world):
    repo, source = notebook_cells(notebook)
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    sink = write_l1(metrics, **world)
    namespace = new_namespace(repo, metrics)
    exec(source["params"], namespace)
    return source, metrics, sink, namespace


def run_all(namespace, source, tags=("defs", "run", "publish", "verify")):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in tags:
            exec(source[tag], namespace)


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.parquet"))
            if not p.relative_to(root).as_posix().startswith(("_runs/", "_partial", "l3_", "l4_"))}


def pick(table, **where):
    mask = np.ones(len(table), dtype=bool)
    for column, value in where.items():
        mask &= (table[column] == value).to_numpy()
    return table[mask]


def one(table, **where):
    rows = pick(table, **where)
    assert len(rows) == 1, f"{len(rows)} linhas para {where}"
    return rows.iloc[0]


# --------------------------------------------------------------------------- testes
def test_notebook_has_the_expected_parameters_and_tags(tmp_path):
    source, _, _, namespace = prepare(tmp_path)
    assert set(source) == {"params", "defs", "run", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01 and namespace["STATS_GRID_DEG"] == namespace["GRID_DEG"]
    assert namespace["MIN_ACTIVE_YEARS"] == 5 and namespace["CHUNK_CELLS"] == 20000
    assert (namespace["REF_START"], namespace["REF_END"], namespace["MIN_REF_YEARS"]) == (None, None, 5)
    assert (namespace["MAX_UNKNOWN_DAYS"], namespace["START"], namespace["END"], namespace["FORCE"]) == (0, None, None, False)
    text = "".join(source.values())
    for obsolete in ("atomic_write", "_log_lote3", "_params_lote3", "country", "cal10", "cal11", "l1_cal_daily"):
        assert obsolete not in text.replace("CAL-10 e CAL-11", "")


def test_roundtrip_values_ordering_and_clean_outputs(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    before = snapshot(metrics)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert {n for n in sink.names() if n.startswith("l3_")} == L3_TABLES      # sem CAL-10/CAL-11
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))
    assert snapshot(metrics) == before                                           # entradas L1 intactas
    for name in L3_TABLES:
        table = sink.read(name)
        assert CELL_COLUMNS <= set(table.columns) and "country" not in table.columns
        assert set(table["cell"]) == {cell_of(A), cell_of(C)}                   # B (2 anos) e D (1 ano) foram podadas
        assert (table["cell"] != GLOBAL_CELL).all()
        for _, part in table.groupby(["series", "lat_band"]):                   # ordenada por (ilat, ilon) por particao
            pairs = list(zip(part["ilat"], part["ilon"]))
            assert pairs == sorted(pairs)
    # valores a mao da celula A (modis; julho de 2003 invalido -> o ano 2003 tambem)
    a = cell_of(A)
    t = sink.read("l3_cal05_total_period")
    row = one(t, cell=a, series="modis")
    assert (row.cell_days, row.n_months, row.n_partial_months, row.n_unknown_days) == (105, 72, 0, 2)
    assert (row.start_year, row.start_month, row.end_year, row.end_month) == (2001, 1, 2006, 12)
    row = one(sink.read("l3_cal06_peak_month"), cell=a, series="modis")
    assert (row.year, row.month, row.cell_days, row.n_valid_months) == (2006, 3, 30, 71)
    row = one(sink.read("l3_cal07_peak_year"), cell=a, series="modis")
    assert (row.year, row.cell_days, row.n_valid_years) == (2006, 30, 5)
    row = one(sink.read("l3_cal08_annual_mean"), cell=a, series="modis")           # 2003 excluido: (5+10+20+25+30)/5
    assert (row.n_years, row.mean_cell_days, row.years_included) == (5, 18.0, "2001,2002,2004,2005,2006")
    cal09 = sink.read("l3_cal09_monthly_mean")
    row = one(cal09, cell=a, series="modis", month=3)
    assert (row.n_years, row.mean_cell_days) == (6, 17.5)
    assert one(cal09, cell=a, series="modis", month=7).n_years == 5
    assert one(sink.read("l3_cal09_monthly_mean"), cell=cell_of(C), series="modis", month=3).mean_cell_days == 7.0
    profile = sink.read("l3_cal12_seasonal_profile")
    assert one(profile, cell=a, series="modis", month=3).share_pct == 100.0
    assert bool(one(profile, cell=a, series="modis", month=3).is_peak_month)
    assert len(pick(profile, cell=a, series="modis")) == 12
    h3 = sink.read("l3_his03_anomaly_abs")
    row = one(h3, cell=a, series="modis", year=2006, month=3)
    assert (row.cell_days, row.n_ref_years, row.ref_mean, row.anomaly_abs) == (30, 5, 15.0, 15.0)
    row = one(h3, cell=a, series="modis", year=2001, month=3)
    assert (row.ref_mean, row.anomaly_abs) == (20.0, -15.0)
    assert not one(h3, cell=a, series="modis", year=2003, month=7).valid_month
    h4 = sink.read("l3_his04_anomaly_pct")
    assert one(h4, cell=a, series="modis", year=2006, month=3).anomaly_pct == 100.0
    assert one(h4, cell=a, series="modis", year=2001, month=3).anomaly_pct == -75.0
    assert pd.isna(one(h4, cell=a, series="modis", year=2006, month=4).anomaly_pct)     # referencia 0
    # _runs: uma linha por lote, escrita com as tabelas todas
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote1", "lote3"]
    row = runs[runs.lote == "lote3"].iloc[0]
    assert row.grid_deg == 0.01
    assert set(json.loads(row.tables)) == L3_TABLES
    params = json.loads(row.params)
    assert params["min_active_years"] == 5 and params["n_active_cells"] == 2 and params["n_chunks"] == 1
    assert params["chunk_cells"] == 20000 and params["stats_grid_deg"] == 0.01 and params["start"] is None


def test_cell_sums_equal_the_l1_totals_and_the_dense_row_count(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    l1 = sink.read("l1_cal_monthly")
    l1 = l1[l1.cell.isin([cell_of(A), cell_of(C)])]
    expected = l1.groupby("series").cell_days.sum()
    total = sink.read("l3_cal05_total_period").groupby("series").cell_days.sum()
    pd.testing.assert_series_equal(total.astype("int64"), expected.astype("int64"), check_names=False)
    assert expected.to_dict() == {"combined": 147, "modis": 147}
    n_months = sink.read("l1_meta_month_validity").groupby("series").size()
    assert len(sink.read("l3_his03_anomaly_abs")) == 2 * int(n_months.sum())       # 2 celulas x (modis + combined) x 72 meses
    assert len(sink.read("l3_his04_anomaly_pct")) == len(sink.read("l3_his03_anomaly_abs"))


def test_small_chunks_give_the_same_tables_and_min_active_years_controls_pruning(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source)
    reference = {n: ParquetSink(metrics).read(n) for n in L3_TABLES}
    assert sorted(p.name for p in (metrics / "_partial_lote3").iterdir()) == ["b10_c0"]
    namespace.update(CHUNK_CELLS=1)
    run_all(namespace, source)
    assert sorted(p.name for p in (metrics / "_partial_lote3").iterdir()) == ["b10_c0", "b10_c1"]   # stale b10_c0 refeita; 2 fatias
    for name, table in reference.items():
        keys = [c for c in ("cell", "series", "year", "month") if c in table.columns]
        got = ParquetSink(metrics).read(name)
        pd.testing.assert_frame_equal(got.sort_values(keys).reset_index(drop=True),
                                      table.sort_values(keys).reset_index(drop=True))
    # com 2 anos a faixa 13 (celula B) entra, noutra faixa; D (1 ano) continua de fora
    namespace.update(MIN_ACTIVE_YEARS=2, CHUNK_CELLS=1)
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert sorted(p.name for p in (metrics / "_partial_lote3").iterdir()) == ["b10_c0", "b10_c1", "b13_c0"]
    assert set(sink.read("l3_cal05_total_period").cell) == {cell_of(A), cell_of(C), cell_of(B)}
    row = one(sink.read("l3_cal05_total_period"), cell=cell_of(B), series="modis")
    assert row.cell_days == 6 and row.n_months == 72
    assert one(sink.read("l3_cal09_monthly_mean"), cell=cell_of(B), series="modis", month=3).n_years == 6
    assert one(sink.read("l3_cal09_monthly_mean"), cell=cell_of(B), series="modis", month=3).mean_cell_days == 1.0
    assert set(sink.read("l3_his03_anomaly_abs").lat_band) == {10, 13}
    params = json.loads(sink.read("_runs").params.iloc[1])
    assert params["n_active_cells"] == 3 and params["n_chunks"] == 3 and params["min_active_years"] == 2


def test_cal05_period_selection(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace.update(START=(2002, 1), END=(2003, 12))
    run_all(namespace, source)
    row = one(ParquetSink(metrics).read("l3_cal05_total_period"), cell=cell_of(A), series="modis")
    assert (row.cell_days, row.n_months, row.start_year, row.start_month, row.end_year, row.end_month) == (25, 24, 2002, 1, 2003, 12)
    assert row.n_unknown_days == 2
    assert json.loads(ParquetSink(metrics).read("_runs").params.iloc[1])["start"] == [2002, 1]


def test_resume_reuses_slices_and_invalidates_on_changes(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace.update(CHUNK_CELLS=1)
    run_all(namespace, source)
    part = metrics / "_partial_lote3"
    marker = part / "b10_c0" / "_done.json"
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    assert len(files) == 2 * len(L3_TABLES)
    run_all(namespace, source)
    assert {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")} == files          # nada foi recalculado
    namespace["FORCE"] = True
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)                          # FORCE refaz tudo
    namespace["FORCE"] = False
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    marker.write_text("{")                                                                # marcador corrompido: so essa fatia
    (part / "b10_c1" / "l3_cal05_total_period.parquet").unlink()                          # saida em falta: so essa fatia
    run_all(namespace, source)
    now = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    assert all(now[p] != files[p] for p in files)
    assert json.loads(marker.read_text())["n_cells"] == 1
    files = now
    namespace["MIN_REF_YEARS"] = 3                                                        # parametro de referencia mudou
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)
    assert one(ParquetSink(metrics).read("l3_cal09_monthly_mean"), cell=cell_of(A), series="modis", month=7).mean_cell_days == 0.0
    files = {p: p.stat().st_mtime_ns for p in part.rglob("*.parquet")}
    write_l1(metrics, cell_days=world_cell_days().iloc[:-5])                              # o notebook 02 refez o L1 (sem D)
    run_all(namespace, source)
    assert all(p.stat().st_mtime_ns != files[p] for p in files)


def test_stats_grid_uses_the_stats_tables_and_the_coarser_cells(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path, stats_grid=0.1)
    namespace["STATS_GRID_DEG"] = 0.1
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    table = sink.read("l3_cal05_total_period")
    assert set(table.cell) == {cell_of(A, 0.1), cell_of(C, 0.1)}
    assert set(table.lat.round(3)) == {10.05} and set(table.lon.round(3)) == {20.05, 20.15}
    assert one(table, cell=cell_of(A, 0.1), series="modis").cell_days == 105
    assert json.loads(sink.read("_runs").params.iloc[1])["inputs"] == ["l1_stats_cal_monthly", "l1_stats_cal_annual"]
    assert sink.read("_runs").grid_deg.tolist() == [0.01, 0.01]
    second = tmp_path / "second"                                                  # L1 sem as tabelas l1_stats_*
    second.mkdir()
    source2, metrics2, sink2, namespace2 = prepare(second, with_runs=False)
    namespace2["STATS_GRID_DEG"] = 0.1
    with pytest.raises(FileNotFoundError, match="02_metrics_lote1.*l1_stats_cal_monthly"):
        run_all(namespace2, source2, ("defs", "run"))


def test_grid_must_match_the_lote1_run(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace.update(GRID_DEG=0.1, STATS_GRID_DEG=0.1)
    with pytest.raises(ValueError, match="grid_deg=0.01"):
        run_all(namespace, source, ("defs", "run"))
    assert not (metrics / "_partial_lote3").exists() and not (metrics / "l3_cal05_total_period").exists()
    namespace.update(GRID_DEG=0.01, STATS_GRID_DEG=0.1)
    with pytest.raises(ValueError, match="stats_grid_deg"):
        run_all(namespace, source, ("defs", "run"))
    namespace.update(GRID_DEG=0.01, STATS_GRID_DEG=0.015)
    with pytest.raises(ValueError):                                                       # nao e multiplo
        run_all(namespace, source, ("defs",))


@pytest.mark.parametrize("missing", ["l1_cal_monthly", "l1_cal_annual", "l1_meta_month_validity", "l1_meta_year_validity"])
def test_missing_l1_input_fails_clearly_and_writes_nothing(tmp_path, missing):
    import shutil
    source, metrics, sink, namespace = prepare(tmp_path)
    shutil.rmtree(metrics / missing)
    with pytest.raises(FileNotFoundError, match=f"02_metrics_lote1.*{missing}"):
        run_all(namespace, source, ("defs", "run"))
    assert not (metrics / "_partial_lote3").exists()
    assert not any(n.startswith("l3_") for n in ParquetSink(metrics).names())


def test_runs_is_written_last_and_a_failing_slice_leaves_no_run(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    run_all(namespace, source, ("defs",))
    seen = []
    original = namespace["write_run"]
    namespace["write_run"] = lambda sink, *a, **k: (seen.append(set(sink.names())), original(sink, *a, **k))[1]
    run_all(namespace, source, ("run", "publish", "verify"))
    assert len(seen) == 1 and L3_TABLES <= seen[0]                    # quando _runs e chamado ja existem as 8 tabelas
    assert "_runs" in seen[0]                                         # so a linha lote1 existia; lote3 vem depois
    assert ParquetSink(metrics).read("_runs").lote.tolist() == ["lote1", "lote3"]
    # uma execucao que falha a meio (2a fatia) nao regista o lote nem publica tabelas novas
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
    assert not any(n.startswith("l3_") for n in ParquetSink(metrics).names())
    namespace["compute"] = original_compute                           # retoma: a 1a fatia ja estava feita
    done = (metrics / "_partial_lote3" / "b10_c0" / "_done.json").stat().st_mtime_ns
    run_all(namespace, source, ("run", "publish", "verify"))
    assert (metrics / "_partial_lote3" / "b10_c0" / "_done.json").stat().st_mtime_ns == done
    assert ParquetSink(metrics).read("_runs").lote.tolist() == ["lote1", "lote3"]
    assert {n for n in ParquetSink(metrics).names() if n.startswith("l3_")} == L3_TABLES


def test_no_active_cells_publishes_empty_tables_with_the_schema(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path, cell_days=world_cell_days().iloc[:0])
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    for name in L3_TABLES:
        table = sink.read(name)
        assert len(table) == 0 and {"cell", "ilat", "ilon", "lat", "lon", "lat_band", "series"} <= set(table.columns)
    assert json.loads(sink.read("_runs").tables.iloc[1]) == {name: 0 for name in L3_TABLES}
    assert json.loads(sink.read("_runs").params.iloc[1])["n_chunks"] == 0


def test_all_cells_pruned_still_publishes_schema_from_the_partials(tmp_path):
    source, metrics, sink, namespace = prepare(tmp_path)
    namespace["MIN_ACTIVE_YEARS"] = 7                                 # ninguem tem 7 anos: nenhuma fatia
    run_all(namespace, source)
    sink = ParquetSink(metrics)
    assert all(len(sink.read(name)) == 0 for name in L3_TABLES)
    assert json.loads(sink.read("_runs").params.iloc[1])["n_active_cells"] == 0

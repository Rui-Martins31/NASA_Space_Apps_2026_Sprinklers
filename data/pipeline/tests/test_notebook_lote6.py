"""Executa as celulas reais do notebook 07 (L6, HAR-01..07 por celula) com tabelas L1 e `processed/` sinteticos.

Celulas (grelha 0.01): A (lat 0), B (lat 1), C (lat 2), D (lat 3, lon 0) e E (lat 3, lon 1: o mesmo ilat que D).
Valores mensais (todos os meses de 2018..2023, validos): A modis 3 / viirs 6, B 2 / 2, C 0 / 1, D m / 2m (m = mes),
E 1 / 0. Calibracao 2018-2021 (48 meses), teste 2022-2023 (24 meses).
"""

import ast
import contextlib
import io
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from metrics import harmonization_factor as hf
from metrics.common import GLOBAL_CELL, cell_key
from metrics.store import ParquetSink, write_table

TABLES = {
    "l6_har01_overlap", "l6_har02_jaccard", "l6_har03_comparable_months", "l6_har04_pearson",
    "l6_har05_spearman", "l6_har06_factor", "l6_har07_factor_uncertainty",
}
CELL_COLUMNS = ["ilat", "ilon", "lat", "lon", "lat_band"]
POINTS = {"A": (0.0, 0.0), "B": (1.0, 0.0), "C": (2.0, 0.0), "D": (3.0, 0.0), "E": (3.0, 1.0)}
YEARS = range(2018, 2024)
GLOBAL_FACTOR = 1056 / 600


def cell_of(name, grid=0.01):
    return int(cell_key([POINTS[name][0]], [POINTS[name][1]], grid)[0])


def counts(name, month):
    """(modis, viirs) de uma celula num mes (iguais em todos os anos)."""
    return {"A": (3, 6), "B": (2, 2), "C": (0, 1), "D": (month, 2 * month), "E": (1, 0)}[name]


def monthly_frames(empty=False):
    rows, validity = [], []
    for year in YEARS:
        for month in range(1, 13):
            for series in ["modis", "viirs", "combined"]:
                validity.append([series, year, month, False, 0])
            for name in POINTS:
                modis, viirs = counts(name, month)
                for series, value in [("modis", modis), ("viirs", viirs), ("combined", max(modis, viirs))]:
                    if value > 0:
                        rows.append([cell_of(name), year, month, series, value])
    monthly = pd.DataFrame(rows, columns=["cell", "year", "month", "series", "cell_days"])
    validity = pd.DataFrame(validity, columns=["series", "year", "month", "partial", "n_unknown_days"])
    return (monthly.iloc[:0], validity.iloc[:0]) if empty else (monthly, validity)


def dense_frame():
    """A tabela densa antiga (todas as celulas, todos os meses), construida a mao."""
    rows = [[cell_of(name), year, month, series, counts(name, month)[0 if series == "modis" else 1], False, 0]
            for name in POINTS for year in YEARS for month in range(1, 13) for series in ["modis", "viirs"]]
    return pd.DataFrame(rows, columns=["cell", "year", "month", "series", "cell_days", "partial", "n_unknown_days"])


def notebook_cells():
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/07_metrics_lote6.ipynb").read_text(encoding="utf-8"))
    sources = {}
    codes = []
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        assert cell["outputs"] == [] and cell["execution_count"] is None
        source = "".join(cell["source"])
        ast.parse(source)
        codes.append(source)
        if source.startswith("# cell: "):
            sources[source.splitlines()[0][len("# cell: "):]] = source
    assert "metricas-pipeline" in codes[0]
    return repo, sources


def fixture(root, empty=False):
    processed, metrics = root / "processed", root / "metrics"
    processed.mkdir()
    metrics.mkdir()
    for year in [2018, 2022]:
        for sensor, instrument, latitudes in [("modis", "MODIS", [0.0, 1.0, 2.0]), ("viirs-jpss1", "VIIRS", [1.0, 2.0, 3.0, 4.0])]:
            frame = pd.DataFrame(dict(instrument=instrument, satellite="Terra" if sensor == "modis" else "N20",
                                      latitude=latitudes, longitude=0.0, acq_date=f"{year}-02-01",
                                      type=pd.Series([0] * len(latitudes), dtype="Int8"), confidence_class="h"))
            (frame.iloc[:0] if empty else frame).to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    monthly, validity = monthly_frames(empty)
    sink = ParquetSink(metrics)
    write_table(sink, "l1_cal_monthly", monthly, grid_deg=0.01, sort_by=["year", "month", "series"])
    write_table(sink, "l1_meta_month_validity", validity, grid_deg=0.01, partition_by=[])
    return processed, metrics, sink


def prepare(tmp_path, empty=False, chunk=2):
    repo, source = notebook_cells()
    processed, metrics, sink = fixture(tmp_path, empty)
    namespace = dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)
    exec(source["params"], namespace)
    namespace["CHUNK_CELLS"] = chunk
    return source, processed, metrics, sink, namespace


def run(namespace, source, tags=("defs", "inputs", "overlap", "slices", "global", "publish", "verify")):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in tags:
            exec(source[tag], namespace)


def table(sink, name):
    out = sink.read(name)
    keys = [c for c in ["cell", "year", "month", "period"] if c in out.columns]
    return out.sort_values(keys).reset_index(drop=True)


def without_cell_columns(frame):
    return frame.drop(columns=[c for c in CELL_COLUMNS if c in frame.columns])


def cell_row(frame, name, **extra):
    rows = frame[frame["cell"].eq(cell_of(name))]
    for column, value in extra.items():
        rows = rows[rows[column].eq(value)]
    assert len(rows) == 1
    return rows.iloc[0]


def test_notebook_parameters_tags_and_no_country(tmp_path):
    source, _, _, _, namespace = prepare(tmp_path)
    assert set(source) == {"params", "defs", "inputs", "overlap", "slices", "global", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01 and namespace["STATS_GRID_DEG"] == namespace["GRID_DEG"]
    assert namespace["CHUNK_CELLS"] == 2 and namespace["FORCE"] is False
    assert (namespace["CAL_START"], namespace["CAL_END"], namespace["TEST_START"]) == (2018, 2021, 2022)
    text = "".join(source.values())
    for obsolete in ["country", "atomic_parquet", "_log_lote6", "l1_cal_monthly.parquet"]:
        assert obsolete not in text


@pytest.mark.parametrize("chunk", [1, 2, 20000])
def test_roundtrip_hand_values_and_equals_the_unsliced_computation(tmp_path, chunk):
    source, processed, metrics, sink, namespace = prepare(tmp_path, chunk=chunk)
    l1_bytes = {p: p.read_bytes() for p in (metrics / "l1_cal_monthly").rglob("*.parquet")}
    seen = []
    with contextlib.redirect_stdout(io.StringIO()):
        exec(source["defs"], namespace)
        original = namespace["write_run"]
        namespace["write_run"] = lambda s, *a, **k: (seen.append(set(s.names())), original(s, *a, **k))[1]
    run(namespace, source, ("inputs", "overlap", "slices", "global", "publish", "verify"))
    # `_runs` e a ultima coisa escrita: quando e chamada existem as 7 tabelas e ainda nao existe `_runs`
    assert len(seen) == 1 and TABLES <= seen[0] and "_runs" not in seen[0]
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote6"] and runs.grid_deg.tolist() == [0.01]
    assert set(json.loads(runs.tables.iloc[0])) == TABLES
    params = json.loads(runs.params.iloc[0])
    assert params["cal_end"] == 2021 and params["test_start"] == 2022 and params["min_pairs"] == 12
    assert params["chunk_cells"] == chunk and params["overlap_years"] == [2018, 2022]
    assert {n for n in sink.names() if n.startswith("l6_")} == TABLES

    # HAR-06 escrito a mao: A, B, C, D, E e a linha global (a soma das celulas)
    factor = table(sink, "l6_har06_factor")
    assert factor.cell.tolist().count(GLOBAL_CELL) == 1 and len(factor) == 6
    a, b, c, d, e = (cell_row(factor, n) for n in "ABCDE")
    assert (a.n_cal_months, a.sum_modis, a.sum_viirs, a.factor, a.uses_global_fallback) == (48, 144, 288, 2.0, False)
    assert (b.sum_modis, b.sum_viirs, b.factor) == (96, 96, 1.0)
    assert (d.sum_modis, d.sum_viirs, d.factor) == (312, 624, 2.0)
    assert (e.sum_modis, e.sum_viirs, e.factor, e.uses_global_fallback) == (48, 0, 0.0, False)
    assert np.isnan(c.factor) and c.sum_modis == 0 and c.uses_global_fallback            # sem modis: fallback global
    assert c.factor_used == pytest.approx(GLOBAL_FACTOR)
    g = factor[factor.cell.eq(GLOBAL_CELL)].iloc[0]
    assert (g.scope, g.n_cal_months, g.sum_modis, g.sum_viirs) == ("global", 48, 600, 1056)
    assert g.factor == pytest.approx(GLOBAL_FACTOR) and g.factor_used == pytest.approx(GLOBAL_FACTOR)
    assert not g.uses_global_fallback
    assert (factor.loc[factor.cell.ne(GLOBAL_CELL), "sum_modis"].sum(), factor.loc[factor.cell.ne(GLOBAL_CELL), "sum_viirs"].sum()) == (600, 1056)
    assert (factor.loc[factor.cell.ne(GLOBAL_CELL), "scope"] == "cell").all()

    # HAR-03, HAR-04, HAR-07 (varios valores NA por construcao: series constantes nao tem correlacao)
    months = table(sink, "l6_har03_comparable_months")
    row = cell_row(months, "A", period="calibration")
    assert (row.n_comparable_months, row.first_month, row.last_month) == (48, "2018-01", "2021-12")
    assert cell_row(months, "A", period="all").n_comparable_months == 72
    assert cell_row(months, "A", period="test").first_month == "2022-01"
    assert len(months) == 18
    pearson = table(sink, "l6_har04_pearson")
    assert cell_row(pearson, "D", period="calibration").pearson == pytest.approx(1.0)
    assert cell_row(pearson, "D", period="calibration").n_pairs == 48
    assert np.isnan(cell_row(pearson, "A", period="calibration").pearson)             # modis e viirs constantes
    assert pearson[(pearson.cell == GLOBAL_CELL) & (pearson.period == "all")].pearson.iloc[0] == pytest.approx(1.0)
    assert cell_row(table(sink, "l6_har05_spearman"), "D", period="test").spearman == pytest.approx(1.0)
    uncertainty = table(sink, "l6_har07_factor_uncertainty")
    row = cell_row(uncertainty, "A")
    assert (row.n_cal_years, row.factor, row.factor_loo_min, row.factor_loo_max, row.se_jackknife) == (4, 2.0, 2.0, 2.0, 0.0)
    assert np.isnan(cell_row(uncertainty, "C").factor)

    # HAR-01/02: 2018 e 2022 (modis lat 0,1,2; viirs lat 1,2,3,4 no mesmo dia)
    overlap = table(sink, "l6_har01_overlap")
    assert len(overlap) == 12 and set(overlap.year) == {2018, 2022} and set(overlap.month) == {2}
    cells = overlap[overlap.cell.ne(GLOBAL_CELL)]
    first = lambda cell, year=2018: overlap[(overlap.cell == cell) & (overlap.year == year)].iloc[0]
    lat_cell = lambda lat: int(cell_key([lat], [0.0], 0.01)[0])
    assert [(r.n_modis, r.n_viirs, r.n_both, r.n_union) for r in (first(lat_cell(x)) for x in [0.0, 1.0, 3.0])] == [
        (1, 0, 0, 1), (1, 1, 1, 1), (0, 1, 0, 1)]
    assert [(first(GLOBAL_CELL, y).n_modis, first(GLOBAL_CELL, y).n_viirs, first(GLOBAL_CELL, y).n_both,
             first(GLOBAL_CELL, y).n_union) for y in (2018, 2022)] == [(3, 4, 2, 5)] * 2
    assert cells.groupby("year")[["n_modis", "n_viirs", "n_both", "n_union"]].sum().eq(
        overlap[overlap.cell.eq(GLOBAL_CELL)].set_index("year")[["n_modis", "n_viirs", "n_both", "n_union"]]).all().all()
    jaccard = table(sink, "l6_har02_jaccard")
    assert jaccard[jaccard.cell == GLOBAL_CELL].jaccard.tolist() == [0.4, 0.4]
    assert jaccard[jaccard.cell == lat_cell(1.0)].jaccard.tolist() == [1.0, 1.0]
    assert jaccard[jaccard.cell == lat_cell(0.0)].jaccard.tolist() == [0.0, 0.0]

    # as colunas de celula acompanham as linhas por celula; a linha global fica sem ilat/lat
    for name in TABLES:
        frame = sink.read(name)
        assert {"cell", *CELL_COLUMNS} <= set(frame.columns) and "country" not in frame.columns
        glob = frame[frame.cell == GLOBAL_CELL]
        assert glob[CELL_COLUMNS].isna().all().all() and frame[frame.cell != GLOBAL_CELL].ilat.notna().all()

    # a computacao por fatias == a funcao sem fatias sobre a tabela densa (include_global=True, uma so chamada)
    dense, options = dense_frame(), dict(cal_start=2018, cal_end=2021, test_start=2022, max_unknown_days=0)
    expected = {
        "l6_har03_comparable_months": hf.har03_comparable_months(dense, **options),
        "l6_har04_pearson": hf.har04_pearson(dense, min_pairs=12, **options),
        "l6_har05_spearman": hf.har05_spearman(dense, min_pairs=12, **options),
        "l6_har06_factor": hf.har06_factor(dense, min_cal_months=24, **options),
        "l6_har07_factor_uncertainty": hf.har07_factor_uncertainty(dense, min_cal_months=24, min_cal_years=3, **options),
    }
    for name, frame in expected.items():
        actual = without_cell_columns(table(sink, name))
        keys = [c for c in ["cell", "period"] if c in frame.columns]
        assert_frame_equal(actual[frame.columns], frame.sort_values(keys).reset_index(drop=True), check_dtype=False)

    # nada de `*.tmp`/`*.old` e as tabelas L1 ficam intactas
    assert not list(metrics.rglob("*.tmp")) and not list(metrics.rglob("*.old"))
    assert {p: p.read_bytes() for p in (metrics / "l1_cal_monthly").rglob("*.parquet")} == l1_bytes


def test_slices_cover_the_cells_of_each_ilat_and_chunking_does_not_change_results(tmp_path):
    results = {}
    for chunk in (1, 20000):
        root = tmp_path / f"chunk{chunk}"
        root.mkdir()
        source, _, metrics, sink, namespace = prepare(root, chunk=chunk)
        run(namespace, source)
        slices = sorted(p.name for p in (metrics / "_partial_lote6").glob("har_*"))
        results[chunk] = (slices, {name: without_cell_columns(table(sink, name)) for name in TABLES})
    assert len(results[1][0]) == 4 and len(results[20000][0]) == 1          # 4 ilat distintos: 1 fatia por ilat vs uma so
    for name in TABLES:
        assert_frame_equal(results[1][1][name], results[20000][1][name], check_dtype=False)


def test_resume_markers_signatures_and_force(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source)
    partial = metrics / "_partial_lote6"
    slice_part = sorted(partial.glob("har_*"))[0] / "har06.parquet"
    slice_marker = slice_part.parent / "_done.json"
    year_part, year_marker = partial / "har01_2018.parquet", partial / "har01_2018.json"
    times = (slice_part.stat().st_mtime_ns, year_part.stat().st_mtime_ns)
    run(namespace, source, ("inputs", "overlap", "slices"))                      # nada mudou: reutiliza
    assert (slice_part.stat().st_mtime_ns, year_part.stat().st_mtime_ns) == times
    assert "code" in json.loads(year_marker.read_text(encoding="utf-8"))
    assert json.loads(year_marker.read_text(encoding="utf-8"))["stats_grid_deg"] == 0.01
    year_marker.write_text("{", encoding="utf-8")                                 # marcador corrompido: recalcula
    slice_marker.write_text("{", encoding="utf-8")
    run(namespace, source, ("inputs", "overlap", "slices"))
    assert "code" in json.loads(year_marker.read_text(encoding="utf-8"))
    assert json.loads(slice_marker.read_text(encoding="utf-8"))["signature"]["chunk_cells"] == 2
    slice_part.unlink()                                                           # parcial em falta: recalcula
    year_part.unlink()
    run(namespace, source, ("inputs", "overlap", "slices"))
    assert slice_part.is_file() and year_part.is_file()
    reused = slice_part.stat().st_mtime_ns
    namespace["FORCE"] = True
    run(namespace, source, ("inputs", "overlap", "slices"))
    assert slice_part.stat().st_mtime_ns != reused
    namespace["FORCE"] = False

    # outra regra NA (MIN_CAL_MONTHS = 49 > 48 meses de calibracao): as fatias refazem-se e nao ha fatores
    before = slice_part.stat().st_mtime_ns
    namespace["MIN_CAL_MONTHS"] = 49
    run(namespace, source)
    assert slice_part.stat().st_mtime_ns != before
    factor = table(sink, "l6_har06_factor")
    assert factor.factor.isna().all() and factor.factor_used.isna().all() and not factor.uses_global_fallback.any()
    assert json.loads(sink.read("_runs").params.iloc[0])["min_cal_months"] == 49
    # outro CHUNK_CELLS tambem muda a assinatura das fatias
    namespace["MIN_CAL_MONTHS"], namespace["CHUNK_CELLS"] = 24, 3
    run(namespace, source)
    assert table(sink, "l6_har06_factor").factor.notna().sum() == 5
    assert not list(metrics.rglob("*.tmp"))

    # fonte processada alterada: so o ano afetado e recalculado (a fatia nao depende de `processed/`)
    year_2022 = partial / "har01_2022.parquet"
    other = year_2022.stat().st_mtime_ns
    frame = pd.read_parquet(processed / "modis_2018.parquet")
    pd.concat([frame, frame.assign(latitude=5.0)], ignore_index=True).to_parquet(processed / "modis_2018.parquet", index=False)
    run(namespace, source)
    assert year_2022.stat().st_mtime_ns == other
    assert table(sink, "l6_har01_overlap").query("cell == -1 and year == 2018").n_modis.iloc[0] == 4

    # outra grelha: HAR-01 recalcula-se com as novas celulas
    namespace["GRID_DEG"] = namespace["STATS_GRID_DEG"] = 0.1
    run(namespace, source, ("defs", "inputs", "overlap"))
    assert json.loads(year_marker.read_text(encoding="utf-8"))["stats_grid_deg"] == 0.1
    assert set(pd.read_parquet(year_part).cell) == {-1, *cell_key([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], [0.0] * 6, 0.1)}


def test_input_errors_are_explicit(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    (tmp_path / "other").mkdir()
    other_metrics = fixture(tmp_path / "other")[1]
    run(namespace, source, ("defs",))
    shutil.rmtree(metrics / "l1_cal_monthly")
    with pytest.raises(FileNotFoundError, match="l1_cal_monthly.*02_metrics_lote1"):
        exec(source["inputs"], namespace)
    shutil.copytree(other_metrics / "l1_cal_monthly", metrics / "l1_cal_monthly")
    shutil.rmtree(metrics / "l1_meta_month_validity")
    with pytest.raises(FileNotFoundError, match="l1_meta_month_validity.*02_metrics_lote1"):
        exec(source["inputs"], namespace)
    shutil.copytree(other_metrics / "l1_meta_month_validity", metrics / "l1_meta_month_validity")
    (processed / "viirs-jpss1_2018.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="Missing processed counterparts.*viirs-jpss1_2018"):
        exec(source["inputs"], namespace)
    for path in processed.glob("*.parquet"):
        path.unlink()
    with pytest.raises(FileNotFoundError, match="No selected processed sensor-year files"):
        exec(source["inputs"], namespace)
    namespace["YEARS"] = {2017}
    with pytest.raises(FileNotFoundError, match="No selected processed"):
        exec(source["inputs"], namespace)


def test_wrong_instrument_and_dates_outside_the_file_year_are_rejected(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    frame = pd.read_parquet(processed / "viirs-jpss1_2022.parquet")
    frame.assign(instrument="MODIS").to_parquet(processed / "viirs-jpss1_2022.parquet", index=False)
    with pytest.raises(ValueError, match="Unexpected instrument"):
        run(namespace, source, ("defs", "inputs", "overlap"))
    frame.assign(acq_date="2021-02-01").to_parquet(processed / "viirs-jpss1_2022.parquet", index=False)
    with pytest.raises(ValueError, match="outside filename year"):
        run(namespace, source, ("inputs", "overlap"))
    assert not (metrics / "_runs").exists()


def test_runs_is_not_written_when_a_stage_fails(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source, ("defs", "inputs", "overlap", "slices", "global"))

    def broken(name, files, order_by, keys):
        if name == "l6_har07_factor_uncertainty":
            raise OSError("simulated failure while consolidating")
        return original(name, files, order_by, keys)

    original = namespace["consolidate"]
    namespace["consolidate"] = broken
    with pytest.raises(OSError, match="simulated"):
        run(namespace, source, ("publish",))
    assert not sink.exists("_runs")
    namespace["consolidate"] = original
    run(namespace, source, ("publish", "verify"))
    assert sink.read("_runs").lote.tolist() == ["lote6"]


def test_empty_inputs_publish_empty_tables(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path, empty=True)
    run(namespace, source)
    assert {n for n in sink.names() if n.startswith("l6_")} == TABLES
    for name in TABLES:
        assert len(sink.read(name)) == 0
    assert json.loads(sink.read("_runs").tables.iloc[0]) == {name: 0 for name in TABLES}
    assert not list(metrics.rglob("*.tmp"))


def test_the_global_row_of_har06_is_the_fallback_for_other_notebooks(tmp_path):
    source, processed, metrics, sink, namespace = prepare(tmp_path)
    run(namespace, source)
    factor = sink.read("l6_har06_factor", columns=["cell", "factor_used", "uses_global_fallback"])
    assert factor.cell.is_unique and (factor.cell == GLOBAL_CELL).sum() == 1
    fallback = factor[factor.uses_global_fallback]
    assert fallback.cell.tolist() == [cell_of("C")]
    assert fallback.factor_used.iloc[0] == pytest.approx(factor[factor.cell == GLOBAL_CELL].factor_used.iloc[0])

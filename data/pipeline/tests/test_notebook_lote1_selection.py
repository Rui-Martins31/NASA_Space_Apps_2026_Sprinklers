"""Execute L1 notebook cells (por celula) with sensor/year selections, stale caches and the diagnostic."""

import ast
import contextlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from metrics.calendar_metrics import year_validity
from metrics.common import cell_key
from metrics.store import ParquetSink

CORE_TABLES = {
    "l1_obs01_raw_counts", "l1_obs02_confidence_dist", "l1_obs03_filtered_counts", "l1_qa02_retention",
    "l1_qa03_cellday_grouped", "l1_qa04_redundancy", "l1_cal_coverage", "l1_cal_daily", "l1_cal_monthly",
    "l1_cal_annual", "l1_meta_month_validity", "l1_meta_year_validity",
}
CELL_COLUMNS = {"cell", "ilat", "ilon", "lat", "lon", "lat_band"}


def cells():
    """(repo, {tag: codigo}) com as celulas de codigo etiquetadas por `# cell: <tag>`."""
    repo = Path(__file__).resolve().parents[3]
    notebook = json.loads((repo / "data/pipeline/notebooks/02_metrics_lote1.ipynb").read_text(encoding="utf-8"))
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


def fixture(root):
    processed = root / "processed"
    metrics = root / "metrics"
    processed.mkdir()
    metrics.mkdir()
    for sensor, instrument, satellite, latitude in [
        ("modis", "MODIS", "Terra", 0.0),
        ("viirs-jpss1", "VIIRS", "N20", 1.0),
        ("viirs-snpp", "VIIRS", "N", 2.0),
    ]:
        for year in [2018, 2020]:
            source = pd.DataFrame(dict(country=["Portugal"], instrument=[instrument],
                                       satellite=[satellite], latitude=[latitude], longitude=[0.0],
                                       acq_date=[f"{year}-01-01"], type=pd.Series([0], dtype="Int8"),
                                       confidence_class=pd.Series(["h"], dtype="string")))
            source.to_parquet(processed / f"{sensor}_{year}.parquet", index=False)
    return processed, metrics


def new_namespace(repo, processed, metrics):
    return dict(PROCESSED=processed, METRICS=metrics, REPO=repo, display=lambda value: None)


def prepare(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    namespace = new_namespace(repo, processed, metrics)
    exec(source["params"], namespace)
    return repo, source, processed, metrics, namespace


def start(namespace, source):
    exec(source["defs"], namespace)


def run_selected(namespace, source):
    with contextlib.redirect_stdout(io.StringIO()):
        for tag in ["run", "publish", "verify"]:
            exec(source[tag], namespace)


def cell_of(latitude, longitude, grid=0.01):
    return int(cell_key([latitude], [longitude], grid)[0])


def test_notebook_has_the_expected_parameters_and_tags(tmp_path):
    _, source, _, _, namespace = prepare(tmp_path)
    assert set(source) == {"params", "defs", "diagnostic", "run", "publish", "verify"}
    assert namespace["GRID_DEG"] == 0.01
    assert namespace["STATS_GRID_DEG"] == namespace["GRID_DEG"]
    assert namespace["MIN_ACTIVE_YEARS"] == 5
    assert tuple(namespace["SERIES_PUBLISHED"]) == ("modis", "viirs", "combined")
    assert namespace["DIAG_YEAR"] == 2018 and namespace["RUN_DIAGNOSTIC"] is False
    assert namespace["SENSORS"] == {"modis", "viirs-jpss1"}
    text = "".join(source.values())
    assert "atomic_write" not in text and "_log_lote1" not in text and "_params_lote1" not in text
    assert "country" not in "".join(src for tag, src in source.items() if tag in {"run", "publish", "verify"})


def test_default_selection_excludes_snpp_and_old_partials(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    start(namespace, source)
    stale = metrics / "_partial_lote1/viirs-snpp_2018"
    stale.mkdir()
    (stale / "_done.json").write_text(json.dumps(dict(sensor="viirs-snpp", year=2018, grid_deg=0.1)))
    # Deliberately incomplete old S-NPP / old-schema caches must never be read.
    pd.DataFrame(dict(country=["Wrong"], date=pd.to_datetime(["2018-01-01"]), series=["viirs"], n_cells=[999])).to_parquet(
        metrics / "_partial_lote1/cal_daily_2018.parquet", index=False)
    seen = []
    original = namespace["write_run"]
    namespace["write_run"] = lambda sink, *a, **k: (seen.append(set(sink.names())), original(sink, *a, **k))[1]
    run_selected(namespace, source)
    sink = ParquetSink(metrics)
    assert set(namespace["log"].sensor) == {"modis", "viirs-jpss1"}
    assert set(sink.read("l1_obs01_raw_counts").satellite) == {"Terra", "N20"}

    # _runs e a ULTIMA coisa a ser escrita: quando e chamada ja existem as 12 tabelas, e ele ainda nao
    assert len(seen) == 1 and CORE_TABLES <= seen[0] and "_runs" not in seen[0]
    runs = sink.read("_runs")
    assert runs.lote.tolist() == ["lote1"] and runs.grid_deg.tolist() == [0.01]
    assert set(json.loads(runs.tables.iloc[0])) == CORE_TABLES
    params = json.loads(runs.params.iloc[0])
    assert params["grid_deg"] == 0.01 and params["stats_grid_deg"] == 0.01
    assert params["min_active_years"] == 5 and params["series_published"] == ["modis", "viirs", "combined"]
    assert {n for n in sink.names() if n.startswith("l1_")} == CORE_TABLES       # sem tabelas stats com a mesma grelha

    modis_cell, viirs_cell = cell_of(0.0, 0.0), cell_of(1.0, 0.0)
    daily = sink.read("l1_cal_daily")
    assert CELL_COLUMNS <= set(daily.columns) and "country" not in daily.columns
    assert [(r.cell, r.in_modis, r.in_viirs) for r in daily.itertuples()] == [
        (modis_cell, True, False), (modis_cell, True, False), (viirs_cell, False, True), (viirs_cell, False, True)]
    assert daily["date"].astype(str).str[:10].tolist() == ["2018-01-01", "2020-01-01"] * 2
    monthly = sink.read("l1_cal_monthly")
    assert set(monthly.year) == {2018, 2020}
    assert monthly.groupby("series", observed=True).cell_days.sum().to_dict() == {"combined": 4, "modis": 2, "viirs": 2}
    assert {"cell", "year", "month", "series", "cell_days"} <= set(monthly.columns)
    assert "partial" not in monthly.columns                              # vive em l1_meta_month_validity
    validity = sink.read("l1_meta_month_validity")
    assert list(validity.columns) == ["series", "year", "month", "partial", "n_unknown_days"]
    pd.testing.assert_frame_equal(sink.read("l1_meta_year_validity").sort_values(["series", "year"]).reset_index(drop=True),
                                  year_validity(validity), check_dtype=False)
    for _, group in monthly.groupby("series"):                           # ordenada por (ilat, ilon) em cada particao
        pairs = list(zip(group.ilat, group.ilon))
        assert pairs == sorted(pairs)

    # Change the selection without deleting any previous source/year caches.
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    assert namespace["log"].sensor.tolist() == ["modis"]
    assert namespace["log"].year.tolist() == [2018]
    daily = sink.read("l1_cal_daily")
    assert [(r.cell, r.in_modis, r.in_viirs) for r in daily.itertuples()] == [(modis_cell, True, False)]
    assert sink.read("l1_cal_monthly").year.unique().tolist() == [2018]
    assert sink.read("l1_cal_monthly").series.tolist() == ["combined", "modis"]
    assert namespace["cov"].instrument.unique().tolist() == ["MODIS"]
    params = json.loads(sink.read("_runs").params.iloc[0])
    assert params["sensors"] == ["modis"]
    assert params["years"] == [2018]


def test_stats_grid_tables_use_the_coarser_grid(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    namespace["STATS_GRID_DEG"] = 0.1
    start(namespace, source)
    run_selected(namespace, source)
    sink = ParquetSink(metrics)
    assert {"l1_stats_cal_monthly", "l1_stats_cal_annual"} <= set(sink.names())
    fine, coarse = sink.read("l1_cal_monthly"), sink.read("l1_stats_cal_monthly")
    assert set(fine.cell) == {cell_of(0.0, 0.0), cell_of(1.0, 0.0)}
    assert set(coarse.cell) == {cell_of(0.0, 0.0, 0.1), cell_of(1.0, 0.0, 0.1)}
    assert set(coarse.lat.round(3)) == {0.05, 1.05} and set(fine.lat.round(3)) == {0.005, 1.005}
    assert coarse.cell_days.sum() == fine.cell_days.sum()
    assert json.loads(sink.read("_runs").params.iloc[0])["stats_grid_deg"] == 0.1
    assert set(json.loads(sink.read("_runs").tables.iloc[0])) == CORE_TABLES | {"l1_stats_cal_monthly", "l1_stats_cal_annual"}


def test_series_published_filters_monthly_and_annual_only(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    namespace["SERIES_PUBLISHED"] = ("combined",)
    start(namespace, source)
    run_selected(namespace, source)
    sink = ParquetSink(metrics)
    assert set(sink.read("l1_cal_monthly").series) == {"combined"}
    assert set(sink.read("l1_cal_annual").series) == {"combined"}
    assert set(sink.read("l1_meta_month_validity").series) == {"combined", "modis", "viirs"}
    assert sink.read("l1_cal_daily").in_viirs.any()                   # os sinalizadores diarios nao se filtram


def test_reuse_checks_source_metadata_and_missing_outputs(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    start(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    sink = ParquetSink(metrics)
    part = metrics / "_partial_lote1/modis_2018/obs01.parquet"
    year_part = metrics / "_partial_lote1/cal_monthly_2018.parquet"
    original_time, year_time = part.stat().st_mtime_ns, year_part.stat().st_mtime_ns
    run_selected(namespace, source)
    assert part.stat().st_mtime_ns == original_time
    assert year_part.stat().st_mtime_ns == year_time                  # o ano do calendario tambem e reutilizado
    frame = pd.read_parquet(processed / "modis_2018.parquet")
    frame.loc[1] = frame.iloc[0]
    frame.to_parquet(processed / "modis_2018.parquet", index=False)
    run_selected(namespace, source)
    assert sink.read("l1_obs01_raw_counts").n_raw.sum() == 2
    assert sink.read("l1_qa03_cellday_grouped").n_grouped.sum() == 1   # duas deteccoes na mesma celula-dia
    assert year_part.stat().st_mtime_ns != year_time                  # fonte mudou: o ano foi recalculado
    part.unlink()
    run_selected(namespace, source)
    assert part.exists()
    marker = metrics / "_partial_lote1/modis_2018/_done.json"
    marker.write_text("{")
    run_selected(namespace, source)
    assert json.loads(marker.read_text())["sensor"] == "modis"
    year_part.unlink()
    run_selected(namespace, source)
    assert year_part.exists()
    assert sink.read("l1_cal_monthly").cell_days.sum() == 2           # combined e modis: 1 + 1


def test_changing_the_grid_invalidates_the_caches(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    start(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    sink = ParquetSink(metrics)
    assert sink.read("l1_obs01_raw_counts").cell.tolist() == [cell_of(0.0, 0.0, 0.01)]
    namespace["GRID_DEG"] = namespace["STATS_GRID_DEG"] = 0.1
    start(namespace, source)
    run_selected(namespace, source)
    assert sink.read("l1_obs01_raw_counts").cell.tolist() == [cell_of(0.0, 0.0, 0.1)]
    assert sink.read("_runs").grid_deg.tolist() == [0.1]


def test_invalid_coordinates_and_dates_are_excluded_and_counted(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    frame = pd.read_parquet(processed / "modis_2018.parquet")
    extra = pd.concat([frame] * 4, ignore_index=True)
    extra.loc[1, "latitude"] = np.nan
    extra.loc[2, "longitude"] = 500.0
    extra.loc[3, ["latitude", "acq_date"]] = [np.nan, "2018-99-99"]       # data E coordenada invalidas: conta 1 vez
    extra.to_parquet(processed / "modis_2018.parquet", index=False)
    start(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    run_selected(namespace, source)
    log = namespace["log"].iloc[0]
    assert (log.n_rows, log.n_invalid_dates, log.n_invalid_coords, log.n_excluded) == (4, 1, 3, 3)
    sink = ParquetSink(metrics)
    assert sink.read("l1_obs01_raw_counts").n_raw.sum() == 1


def test_unsupported_or_missing_selection_is_clear(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    start(namespace, source)
    namespace["SENSORS"] = {"viirs-snpp"}
    with pytest.raises(ValueError, match="09_har12_snpp"):
        run_selected(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={1999})
    with pytest.raises(FileNotFoundError, match="selected"):
        run_selected(namespace, source)


def test_selected_files_without_valid_dates_fail_clearly(tmp_path):
    repo, source = cells()
    processed, metrics = fixture(tmp_path)
    frame = pd.read_parquet(processed / "modis_2018.parquet").iloc[:0]
    frame.to_parquet(processed / "modis_2018.parquet", index=False)
    namespace = new_namespace(repo, processed, metrics)
    exec(source["params"], namespace)
    start(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    with pytest.raises(ValueError, match="no valid acquisition dates"):
        run_selected(namespace, source)


def test_dates_outside_the_file_year_fail_clearly(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    frame = pd.read_parquet(processed / "modis_2018.parquet")
    frame.loc[1] = frame.iloc[0]
    frame.loc[1, "acq_date"] = "2019-01-01"
    frame.to_parquet(processed / "modis_2018.parquet", index=False)
    start(namespace, source)
    namespace.update(SENSORS={"modis"}, YEARS={2018})
    with pytest.raises(ValueError, match="fora do ano"):
        run_selected(namespace, source)
    assert not (metrics / "_runs").exists()                               # nada ficou registado


# ------------------------------------------------------------------------------ diagnostico
def full_year_rows(year, latitude, countries=("Portugal",)):
    """Uma deteccao por dia do ano na mesma celula (cobertura global completa: sem dias desconhecidos)."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31").strftime("%Y-%m-%d")
    rows = [(country, day) for day in days for country in countries]
    return pd.DataFrame(dict(country=[r[0] for r in rows], instrument="MODIS", satellite="Terra",
                             latitude=latitude, longitude=0.0, acq_date=[r[1] for r in rows],
                             type=pd.Series([0] * len(rows), dtype="Int8"),
                             confidence_class=pd.Series(["h"] * len(rows), dtype="string")))


def test_diagnostic_is_off_by_default(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    start(namespace, source)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(source["diagnostic"], namespace)
    assert namespace["diag"] == {} and "desligado" in out.getvalue()
    assert not list((metrics / "_partial_lote1").glob("modis_*"))


def test_diagnostic_reports_volume_active_cells_and_country_overlap(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    # 2018: duas celulas (lat 0.0 em dois paises, lat 3.0 so em um), um registo por dia do ano
    rows = pd.concat([full_year_rows(2018, 0.0, ("Portugal", "Spain")), full_year_rows(2018, 3.0)], ignore_index=True)
    rows.to_parquet(processed / "modis_2018.parquet", index=False)
    namespace.update(RUN_DIAGNOSTIC=True, DIAG_YEAR=2018, SENSORS={"modis"})
    start(namespace, source)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(source["diagnostic"], namespace)
    diag = namespace["diag"]
    assert diag["year"] == 2018 and diag["active_cells"] == 2
    assert diag["monthly_rows"] == 2 * 12 * 2                              # 2 celulas x 12 meses x (modis, combined)
    assert diag["cells_pass_1_valid_year"] == 2                            # todos os meses validos (sem dias desconhecidos)
    assert diag["n_years"] == 2                                            # 2018 e 2020 nas fontes escolhidas
    assert diag["mb_cal_daily"] > 0 and diag["mb_cal_monthly"] > 0
    assert diag["est_gb"] == pytest.approx((diag["mb_cal_daily"] + diag["mb_cal_monthly"]) * 2 / 1000)
    assert diag["detections_in_several_countries"] == 365                  # lat 0.0: cada dia em 2 paises
    assert diag["distinct_detections"] == 365 * 2                          # (cell, data, lat, lon): 365 + 365
    text = out.getvalue()
    assert "GB" in text and "CABE" in text and "mais de um country" in text
    assert not (metrics / "_diag").exists()                                # limpa os ficheiros temporarios
    assert not (metrics / "_runs").exists() and not any(n.startswith("l1_") for n in ParquetSink(metrics).names())


def test_diagnostic_compares_with_the_budget_and_stats_grid(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    full_year_rows(2018, 0.0).to_parquet(processed / "modis_2018.parquet", index=False)
    namespace.update(RUN_DIAGNOSTIC=True, DIAG_YEAR=2018, STATS_GRID_DEG=0.1, DISK_BUDGET_GB=0.0, SENSORS={"modis"})
    start(namespace, source)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(source["diagnostic"], namespace)
    assert "NAO CABE" in out.getvalue()
    assert namespace["diag"]["mb_stats_monthly"] > 0 and "0.1" in out.getvalue()


def test_diagnostic_missing_year_fails_clearly(tmp_path):
    repo, source, processed, metrics, namespace = prepare(tmp_path)
    namespace.update(RUN_DIAGNOSTIC=True, DIAG_YEAR=1999)
    start(namespace, source)
    with pytest.raises(FileNotFoundError, match="1999"):
        exec(source["diagnostic"], namespace)
